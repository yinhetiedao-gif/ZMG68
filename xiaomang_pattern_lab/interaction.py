"""Transient, frame-coalesced canvas interaction data.

The canvas owns an :class:`InteractionState` while a pointer is down.  It is
deliberately separate from ``PatternDocument``: pointer motion can update this
small structure as often as the OS sends events without cloning or serializing
the document.  The final geometry is committed exactly once on pointer-up.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


InteractionKind = Literal["move", "scale"]


@dataclass
class InteractionState:
    """The minimal transient state needed to draw a direct manipulation."""

    kind: InteractionKind
    element_id: str
    handle: str | None
    start_pointer_x: float
    start_pointer_y: float
    start_x: float
    start_y: float
    start_width: float
    start_height: float
    start_rotation: float
    current_x: float
    current_y: float
    current_width: float
    current_height: float
    current_rotation: float
    dirty: bool = True
    pointer_events: int = 0

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """Current axis-aligned bounds in PatternDocument world units (mm)."""

        return (
            self.current_x - self.current_width / 2.0,
            self.current_y - self.current_height / 2.0,
            self.current_x + self.current_width / 2.0,
            self.current_y + self.current_height / 2.0,
        )

    def set_position(self, x: float, y: float) -> None:
        self.current_x = float(x)
        self.current_y = float(y)
        self.pointer_events += 1
        self.dirty = True

    def set_size(self, width: float, height: float) -> None:
        self.current_width = max(0.01, float(width))
        self.current_height = max(0.01, float(height))
        self.pointer_events += 1
        self.dirty = True
