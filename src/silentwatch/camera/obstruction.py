"""Explainable lens-obstruction classifier with temporal debounce and hysteresis.

Darkness alone is never proof of obstruction (Book section 22). The decisive evidence is a *collapse of scene
structure* relative to the calibrated baseline: contrast, edges, tile variation and low-frequency structure.
A dark room that still shows structure (screen glow) is reported as POSSIBLE at most.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

from silentwatch.camera.calibration import Baseline
from silentwatch.camera.integrity import FrameFeatures
from silentwatch.config.models import ObstructionConfig
from silentwatch.storage import EventStore, EventType, Severity


class ObstructionState(str, enum.Enum):
    NORMAL = "NORMAL"
    POSSIBLE_OBSTRUCTION = "POSSIBLE_OBSTRUCTION"
    PARTIAL_OBSTRUCTION = "PARTIAL_OBSTRUCTION"
    CONFIRMED_OBSTRUCTION = "CONFIRMED_OBSTRUCTION"
    UNKNOWN = "UNKNOWN"


class _Raw(enum.Enum):
    NORMAL = 0
    DARKER = 1     # much darker but structure still present (lights off / dim)
    PARTIAL = 2
    FULL = 3


@dataclass(frozen=True)
class Thresholds:
    """Tunable in M3.4 against recorded clips. Ratios are relative to the calibration baseline."""

    lost_ratio: float = 0.30          # contrast/edge ratio below this counts as 'lost'
    flat_tiles_full: float = 0.85     # fraction of flat tiles for a full cover
    flat_gain_partial: float = 0.35   # extra flat-tile fraction (vs baseline) for a partial cover
    structure_floor: float = 0.15     # structure_ratio below this = noise-like
    darker_ratio: float = 0.25        # mean luma below this x baseline = 'much darker'
    gap_reset_s: float = 1.0          # a frame gap longer than this resets debounce timers


@dataclass(frozen=True)
class ObstructionResult:
    state: ObstructionState
    reasons: list[str] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    changed: bool = False
    pending_s: float = 0.0


class ObstructionClassifier:
    def __init__(
        self,
        baseline: Baseline | None,
        cfg: ObstructionConfig,
        mode: str = "balanced",
        thresholds: Thresholds | None = None,
    ):
        self.baseline = baseline
        self.cfg = cfg
        self.mode = mode
        self.t = thresholds or Thresholds()
        self.state = ObstructionState.UNKNOWN if baseline is None else ObstructionState.NORMAL
        self._since: float | None = None      # when the current raw condition started
        self._raw_kind: _Raw = _Raw.NORMAL
        self._last_ts: float | None = None
        self._normal_run = 0

    @property
    def debounce_s(self) -> float:
        return self.cfg.strict_debounce_s if self.mode == "strict" else self.cfg.confirm_debounce_s

    def set_baseline(self, baseline: Baseline | None) -> None:
        self.baseline = baseline
        self.state = ObstructionState.UNKNOWN if baseline is None else ObstructionState.NORMAL
        self._since, self._raw_kind, self._normal_run = None, _Raw.NORMAL, 0

    # -- per-frame evidence -------------------------------------------------------
    def _raw(self, f: FrameFeatures) -> tuple[_Raw, list[str], dict[str, float]]:
        b = self.baseline.stats  # type: ignore[union-attr]
        base_std = max(b["std_luma"].mean, 3.0)
        base_edge = max(b["edge_density"].mean, 0.004)
        base_mean = max(b["mean_luma"].mean, 1.0)
        base_flat = b["tile_flat_ratio"].mean
        base_struct = b["structure_ratio"].mean

        contrast = f.std_luma / base_std
        edge = f.edge_density / base_edge
        bright = f.mean_luma / base_mean
        flat_gain = f.tile_flat_ratio - base_flat
        # With under ~2 gray levels of total contrast the structure ratio is just quantisation noise, so it is
        # not trusted: such an image is featureless by definition.
        struct_lost = f.std_luma < 2.0 or f.structure_ratio < max(self.t.structure_floor, 0.4 * base_struct)
        scores = {
            "contrast_ratio": round(contrast, 3),
            "edge_ratio": round(edge, 3),
            "brightness_ratio": round(bright, 3),
            "flat_tiles": round(f.tile_flat_ratio, 3),
            "flat_gain": round(flat_gain, 3),
            "structure_ratio": round(f.structure_ratio, 3),
        }
        t = self.t
        reasons: list[str] = []

        if (
            contrast < t.lost_ratio
            and edge < t.lost_ratio
            and f.tile_flat_ratio >= t.flat_tiles_full
            and struct_lost
        ):
            reasons += [
                f"contrast {contrast:.2f}x baseline",
                f"edges {edge:.2f}x baseline",
                f"{f.tile_flat_ratio * 16:.0f}/16 tiles flat",
                f"structure {f.structure_ratio:.2f} (baseline {base_struct:.2f})",
            ]
            if bright < t.darker_ratio:
                reasons.append(f"brightness {bright:.2f}x baseline")
            return _Raw.FULL, reasons, scores

        if flat_gain >= t.flat_gain_partial and edge < 0.7:
            reasons += [f"{flat_gain * 16:.0f} more tiles flat than baseline", f"edges {edge:.2f}x baseline"]
            return _Raw.PARTIAL, reasons, scores

        if bright < t.darker_ratio:
            reasons.append(
                f"much darker ({bright:.2f}x baseline) but scene structure remains (lights off/dim, not a cover)"
            )
            return _Raw.DARKER, reasons, scores
        return _Raw.NORMAL, reasons, scores

    # -- temporal logic --------------------------------------------------------------
    def update(self, f: FrameFeatures, ts: float) -> ObstructionResult:
        if self.baseline is None:
            return ObstructionResult(ObstructionState.UNKNOWN, ["calibration required"])

        if self._last_ts is not None and ts - self._last_ts > self.t.gap_reset_s:
            self._since, self._raw_kind = None, _Raw.NORMAL  # camera hiccup: do not count the gap as evidence
        self._last_ts = ts

        raw, reasons, scores = self._raw(f)
        if raw != self._raw_kind:
            self._raw_kind = raw
            self._since = ts if raw != _Raw.NORMAL else None
        dur = 0.0 if self._since is None else ts - self._since

        prev = self.state
        new = prev
        if raw == _Raw.NORMAL:
            self._normal_run += 1
            if prev != ObstructionState.NORMAL and self._normal_run >= self.cfg.clear_frames:
                new = ObstructionState.NORMAL
        else:
            self._normal_run = 0
            if raw == _Raw.FULL:
                if dur >= self.debounce_s:
                    new = ObstructionState.CONFIRMED_OBSTRUCTION
                elif dur >= self.cfg.min_debounce_s and prev == ObstructionState.NORMAL:
                    new = ObstructionState.POSSIBLE_OBSTRUCTION
            elif raw == _Raw.PARTIAL:
                if dur >= self.debounce_s and prev != ObstructionState.CONFIRMED_OBSTRUCTION:
                    new = ObstructionState.PARTIAL_OBSTRUCTION
                elif dur >= self.cfg.min_debounce_s and prev == ObstructionState.NORMAL:
                    new = ObstructionState.POSSIBLE_OBSTRUCTION
            else:  # DARKER: informational only, can never confirm
                if dur >= self.cfg.min_debounce_s and prev == ObstructionState.NORMAL:
                    new = ObstructionState.POSSIBLE_OBSTRUCTION

        self.state = new
        return ObstructionResult(new, reasons, scores, changed=new != prev, pending_s=dur)


_EVENT = {
    ObstructionState.POSSIBLE_OBSTRUCTION: (EventType.OBSTRUCTION_POSSIBLE, Severity.INFO),
    ObstructionState.PARTIAL_OBSTRUCTION: (EventType.OBSTRUCTION_PARTIAL, Severity.WARNING),
    ObstructionState.CONFIRMED_OBSTRUCTION: (EventType.OBSTRUCTION_CONFIRMED, Severity.CRITICAL),
    ObstructionState.NORMAL: (EventType.OBSTRUCTION_CLEARED, Severity.INFO),
}


def log_obstruction(store: EventStore, result: ObstructionResult) -> None:
    """Persist a state change (deduplicated by the caller via result.changed) with its explanation."""
    mapped = _EVENT.get(result.state)
    if not result.changed or mapped is None:
        return
    etype, sev = mapped
    store.append(etype, sev, "obstruction", details={"reasons": result.reasons, "scores": result.scores})
