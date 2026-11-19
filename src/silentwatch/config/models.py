"""Typed, validated, immutable configuration sections."""

from __future__ import annotations

from dataclasses import dataclass


def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


@dataclass(frozen=True)
class CameraConfig:
    backend: str
    index: int
    width: int
    height: int
    analysis_fps: float
    warmup_frames: int
    frozen_frames: int
    read_fail_limit: int
    max_backoff_s: float
    queue_size: int

    def __post_init__(self) -> None:
        _check(self.backend in ("dshow", "msmf"), "camera.backend must be dshow or msmf")
        _check(0 <= self.index <= 16, "camera.index out of range")
        _check(160 <= self.width <= 3840 and 120 <= self.height <= 2160, "camera size out of range")
        _check(0.5 <= self.analysis_fps <= 30, "camera.analysis_fps must be 0.5..30")
        _check(0 <= self.warmup_frames <= 120, "camera.warmup_frames must be 0..120")
        _check(2 <= self.frozen_frames <= 600, "camera.frozen_frames must be 2..600")
        _check(1 <= self.read_fail_limit <= 100, "camera.read_fail_limit must be 1..100")
        _check(1 <= self.max_backoff_s <= 600, "camera.max_backoff_s must be 1..600")
        _check(1 <= self.queue_size <= 256, "camera.queue_size must be 1..256")


@dataclass(frozen=True)
class ObstructionConfig:
    confirm_debounce_s: float
    strict_debounce_s: float
    min_debounce_s: float
    clear_frames: int
    calibration_seconds: float
    calibration_stale_days: int

    def __post_init__(self) -> None:
        _check(0.05 <= self.min_debounce_s <= 5, "obstruction.min_debounce_s must be 0.05..5")
        # Safety bound: a single frame must never be able to trigger a lock.
        _check(self.confirm_debounce_s >= 0.2, "obstruction.confirm_debounce_s must be >= 0.2")
        _check(self.strict_debounce_s >= 0.2, "obstruction.strict_debounce_s must be >= 0.2")
        _check(self.confirm_debounce_s <= 30 and self.strict_debounce_s <= 30, "debounce must be <= 30 s")
        _check(1 <= self.clear_frames <= 100, "obstruction.clear_frames must be 1..100")
        _check(1 <= self.calibration_seconds <= 60, "obstruction.calibration_seconds must be 1..60")
        _check(1 <= self.calibration_stale_days <= 3650, "obstruction.calibration_stale_days invalid")


@dataclass(frozen=True)
class PresenceConfig:
    enabled: bool
    present_detections: int
    pending_s: float
    lock_after_s: float
    min_confidence: float

    def __post_init__(self) -> None:
        _check(1 <= self.present_detections <= 30, "presence.present_detections must be 1..30")
        _check(0.5 <= self.pending_s <= 300, "presence.pending_s must be 0.5..300")
        _check(1 <= self.lock_after_s <= 3600, "presence.lock_after_s must be 1..3600")
        _check(self.lock_after_s >= self.pending_s, "presence.lock_after_s must be >= pending_s")
        _check(0.0 <= self.min_confidence <= 1.0, "presence.min_confidence must be 0..1")


@dataclass(frozen=True)
class PolicyConfig:
    mode: str
    dry_run: bool
    lock_cooldown_s: float
    post_unlock_grace_s: float
    signal_expiry_s: float

    def __post_init__(self) -> None:
        _check(self.mode in ("strict", "balanced"), "policy.mode must be strict or balanced")
        _check(0 <= self.lock_cooldown_s <= 600, "policy.lock_cooldown_s must be 0..600")
        _check(0 <= self.post_unlock_grace_s <= 600, "policy.post_unlock_grace_s must be 0..600")
        _check(1 <= self.signal_expiry_s <= 3600, "policy.signal_expiry_s must be 1..3600")


@dataclass(frozen=True)
class PrivacyConfig:
    snapshots: bool
    retention_days: int
    snapshot_retention_days: int
    consent_given: bool

    def __post_init__(self) -> None:
        _check(1 <= self.retention_days <= 3650, "privacy.retention_days must be 1..3650")
        _check(1 <= self.snapshot_retention_days <= 365, "privacy.snapshot_retention_days must be 1..365")


@dataclass(frozen=True)
class HandConfig:
    enabled: bool
    approach_growth: float

    def __post_init__(self) -> None:
        _check(0.05 <= self.approach_growth <= 5.0, "hand.approach_growth must be 0.05..5")


@dataclass(frozen=True)
class BluetoothConfig:
    enabled: bool
    missing_after_s: float

    def __post_init__(self) -> None:
        _check(5 <= self.missing_after_s <= 3600, "bluetooth.missing_after_s must be 5..3600")


@dataclass(frozen=True)
class UsbConfig:
    enabled: bool


@dataclass(frozen=True)
class LoggingConfig:
    level: str

    def __post_init__(self) -> None:
        _check(self.level in ("DEBUG", "INFO", "WARNING", "ERROR"), "logging.level invalid")


@dataclass(frozen=True)
class Config:
    camera: CameraConfig
    obstruction: ObstructionConfig
    presence: PresenceConfig
    policy: PolicyConfig
    privacy: PrivacyConfig
    hand: HandConfig
    bluetooth: BluetoothConfig
    usb: UsbConfig
    logging: LoggingConfig


SECTIONS: dict[str, type] = {
    "camera": CameraConfig,
    "obstruction": ObstructionConfig,
    "presence": PresenceConfig,
    "policy": PolicyConfig,
    "privacy": PrivacyConfig,
    "hand": HandConfig,
    "bluetooth": BluetoothConfig,
    "usb": UsbConfig,
    "logging": LoggingConfig,
}
