"""The running service: camera -> analysis -> DecisionCore -> real lock, with clean shutdown."""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable

from silentwatch.app.core import DecisionCore
from silentwatch.camera.calibration import (
    CalibrationError,
    CalibrationStatus,
    CalibrationStore,
    collect_features,
    compute_baseline,
    log_result,
)
from silentwatch.camera.capture import CameraCaptureService
from silentwatch.camera.events import log_camera_status
from silentwatch.camera.frame import Frame, FrameSource
from silentwatch.camera.integrity import FeatureExtractor
from silentwatch.camera.obstruction import ObstructionClassifier, ObstructionState, log_obstruction
from silentwatch.config.models import Config
from silentwatch.policy import Action, ActionKind, State
from silentwatch.presence.estimator import FaceBackend, PresenceEstimator
from silentwatch.storage import Database, EventStore, EventType, Severity
from silentwatch.windows.lock import WindowsLockService
from silentwatch.windows.session import is_workstation_locked

log = logging.getLogger(__name__)


@dataclass
class ServiceStatus:
    state: State
    obstruction: ObstructionState
    presence: str
    camera: str
    frames: int
    fps: float


class SilentWatchService:
    def __init__(
        self,
        cfg: Config,
        db: Database,
        source_factory: Callable[[], FrameSource],
        face_backend: FaceBackend | None,
        lock_service: WindowsLockService,
        clock: Callable[[], float] = time.monotonic,
        session_locked_fn: Callable[[], bool] = is_workstation_locked,
        camera_id: str = "camera0",
        on_status_line: Callable[[str], None] | None = None,
    ):
        self.cfg = cfg
        self.db = db
        self.store = EventStore(db)
        self.calibration = CalibrationStore(db)
        self.lock_service = lock_service
        self.clock = clock
        self._session_locked = session_locked_fn
        self._camera_id = camera_id
        self._say = on_status_line or (lambda s: None)

        self.core = DecisionCore(cfg.policy, cfg.presence, clock, presence_enabled=face_backend is not None and cfg.presence.enabled)
        self.estimator = PresenceEstimator(face_backend, cfg.presence.min_confidence) if face_backend is not None else None
        self.extractor = FeatureExtractor()
        self.classifier = ObstructionClassifier(None, cfg.obstruction, cfg.policy.mode)
        self._factory = source_factory
        self._capture: CameraCaptureService | None = None
        self._status_q: queue.Queue[tuple[str, str]] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._locked = False
        self._frames = 0
        self._t0 = clock()
        self._last_obs = "UNKNOWN"
        self.lock_actions: list[Action] = []   # every LOCK decision (for tests and diagnostics)

    # -- lifecycle ------------------------------------------------------------------------
    def start(self) -> None:
        self._stop.clear()
        self.store.append(EventType.APP_STARTED, source="service", details={"mode": self.cfg.policy.mode, "dry_run": self.lock_service.dry_run})
        self._thread = threading.Thread(target=self._run, name="silentwatch-service", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None
        self._release_camera()
        self.store.append(EventType.APP_STOPPED, source="service")

    def status(self) -> ServiceStatus:
        cam = self._capture.state.value if self._capture else "STOPPED"
        elapsed = max(1e-6, self.clock() - self._t0)
        return ServiceStatus(self.core.state, self.classifier.state, self.core.tracker.state.value, cam, self._frames, self._frames / elapsed)

    # -- camera handling --------------------------------------------------------------------
    def _make_capture(self) -> CameraCaptureService:
        c = self.cfg.camera
        return CameraCaptureService(
            self._factory, c.analysis_fps, c.warmup_frames, c.queue_size, c.frozen_frames, c.read_fail_limit,
            c.frozen_seconds, c.frozen_reopen_interval_s, on_status=lambda k, d: self._status_q.put((k, d)),
        )

    def _release_camera(self) -> None:
        if self._capture is not None:
            self._capture.stop()
            self._capture = None

    def _calibrate_if_needed(self, first: Frame) -> None:
        res = f"{first.width}x{first.height}"
        status = self.calibration.status(self._camera_id, res, self.cfg.obstruction.calibration_stale_days)
        if status == CalibrationStatus.OK:
            self.classifier.set_baseline(self.calibration.load(self._camera_id, res))
            return
        self.core.engine.set_phase(State.CALIBRATING)
        self._say(f"calibrating ({status.value}); keep the lens uncovered")
        cap = self._capture
        feats = collect_features(
            lambda: (lambda f: f.image if f else None)(cap.get(timeout=0.5)),
            self.cfg.obstruction.calibration_seconds,
            self.clock,
        )
        try:
            baseline = compute_baseline(feats, self._camera_id, res)
            self.calibration.save(baseline)
            self.classifier.set_baseline(baseline)
            log_result(self.store, True, f"{baseline.n_frames} frames")
        except CalibrationError as exc:
            log_result(self.store, False, str(exc))
            self._say(f"calibration rejected: {exc}")
        self.core.start_monitoring()

    # -- main loop -----------------------------------------------------------------------------
    def _run(self) -> None:
        try:
            self.core.start_monitoring()
            self._capture = self._make_capture()
            self._capture.start()
            first = self._wait_first_frame()
            if first is not None:
                self._calibrate_if_needed(first)
            while not self._stop.is_set():
                self._poll_session()
                if self._locked:
                    self._stop.wait(0.3)
                    continue
                self._drain_camera_status()
                frame = self._capture.get(timeout=0.2) if self._capture else None
                if frame is not None:
                    self._process(frame)
                self._dispatch(self.core.tick())
        except Exception:  # noqa: BLE001 - the loop must not die silently
            log.exception("service loop crashed")
            self.store.append(EventType.ERROR, Severity.CRITICAL, "service", details={"detail": "service loop crashed"})

    def _wait_first_frame(self, timeout: float = 20.0) -> Frame | None:
        end = self.clock() + timeout
        while not self._stop.is_set() and self.clock() < end:
            self._drain_camera_status()
            f = self._capture.get(timeout=0.2)
            if f is not None:
                return f
        return None

    def _poll_session(self) -> None:
        locked = self._session_locked()
        if locked == self._locked:
            return
        self._locked = locked
        if locked:
            self._release_camera()                 # do not keep the camera on while Windows is locked
            self._dispatch(self.core.on_session(True))
            self.store.append(EventType.SESSION_LOCKED, source="session")
        else:
            self._dispatch(self.core.on_session(False))
            self.store.append(EventType.SESSION_UNLOCKED, source="session")
            self.extractor.reset()
            self._capture = self._make_capture()
            self._capture.start()

    def _drain_camera_status(self) -> None:
        while True:
            try:
                kind, detail = self._status_q.get_nowait()
            except queue.Empty:
                return
            log_camera_status(self.store, kind, detail)
            self._dispatch(self.core.on_camera_status(kind, detail))

    def _process(self, frame: Frame) -> None:
        self._frames += 1
        feats = self.extractor.update(frame.image)
        result = self.classifier.update(feats, frame.monotonic_ts)
        log_obstruction(self.store, result)
        self._dispatch(self.core.on_obstruction(result))
        if self.estimator is not None:
            obs = self.estimator.observe(frame.image)
            self._dispatch(self.core.on_presence(obs, frame.monotonic_ts))

    # -- actions ------------------------------------------------------------------------------------
    def _dispatch(self, actions: list[Action]) -> None:
        for a in actions:
            if a.kind == ActionKind.LOCK:
                self.lock_actions.append(a)
                res = self.lock_service.lock(a.reason)
                self.core.engine.on_lock_result(res.requested or res.suppressed)
                self._say(f"LOCK: {a.reason} ({'dry-run' if res.dry_run else 'real'})")
            elif a.rule == "transition":
                self.store.append(EventType.STATE_CHANGED, source="policy", details={"detail": a.reason})
                self._say(a.reason)
            elif a.kind == ActionKind.NOTIFY:
                self.store.append(EventType.STATE_CHANGED, Severity.WARNING, "policy", details={"notify": a.reason})
                self._say(f"NOTE: {a.reason}")
            elif a.kind == ActionKind.LOG:
                log.info("policy: %s", a.reason)
