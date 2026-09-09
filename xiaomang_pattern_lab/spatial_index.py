"""A replaceable hit-testing boundary for the Pattern Lab canvas.

The initial implementation is a cached bounding-box index.  Its query remains
linear, but it avoids repeatedly extracting geometry from the document and
gives future Quadtree/R-tree implementations a stable interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Protocol

from ppg.foundation.models import Element


@dataclass(frozen=True)
class IndexedBounds:
    element_id: str
    left: float
    top: float
    right: float
    bottom: float
    order: int

    def contains(self, x: float, y: float, tolerance: float = 0.0) -> bool:
        return (
            self.left - tolerance <= x <= self.right + tolerance
            and self.top - tolerance <= y <= self.bottom + tolerance
        )


class SpatialIndex(Protocol):
    def rebuild(self, elements: Iterable[Element]) -> None: ...

    def hit_test(self, x: float, y: float, tolerance: float = 0.0) -> Optional[str]: ...


class BoundingBoxSpatialIndex:
    """Cached bounds baseline; later replaceable with a Quadtree/R-tree."""

    def __init__(self) -> None:
        self._entries: list[IndexedBounds] = []

    def rebuild(self, elements: Iterable[Element]) -> None:
        self._entries = []
        for order, element in enumerate(elements):
            if not element.visible:
                continue
            left = element.x - element.width / 2.0
            top = element.y - element.height / 2.0
            self._entries.append(
                IndexedBounds(
                    element_id=element.id,
                    left=left,
                    top=top,
                    right=left + element.width,
                    bottom=top + element.height,
                    order=order,
                )
            )

    def hit_test(self, x: float, y: float, tolerance: float = 0.0) -> Optional[str]:
        for entry in reversed(self._entries):
            if entry.contains(x, y, tolerance):
                return entry.element_id
        return None
