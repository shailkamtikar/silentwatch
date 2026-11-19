"""Frame container and the FrameSource abstraction (real camera, fake, or recorded clip)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class Frame:
    image: np.ndarray        # BGR uint8
    monotonic_ts: float
    index: int

    @property
    def height(self) -> int:
        return int(self.image.shape[0])

    @property
    def width(self) -> int:
        return int(self.image.shape[1])


class FrameSource(Protocol):
    """Anything that can yield frames. Implementations must be safe to open/release repeatedly."""

    name: str

    def open(self) -> bool: ...

    def read(self) -> tuple[bool, np.ndarray | None]: ...

    def release(self) -> None: ...
