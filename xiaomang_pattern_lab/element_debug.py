"""Auditable Element/renderer diagnostics for Pattern Lab."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any

from ppg.foundation.models import CircleElement, EllipseElement, FilledRegionElement, PathElement, RectElement, PatternDocument


@dataclass(frozen=True)
class ElementDebugRecord:
    id: str
    type: str
    x: float
    y: float
    width: float
    height: float
    radius: float | None
    fill: str
    stroke: str
    visible: bool
    confidence: float | None
    source: str
    renderable: bool
    filled: bool
    valid_geometry: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ElementDebugSummary:
    detected_element_count: int
    renderable_element_count: int
    visible_filled_element_count: int
    invalid_geometry_count: int
    unknown_primitive_count: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


KNOWN_PRIMITIVES = (CircleElement, EllipseElement, RectElement, PathElement, FilledRegionElement)


def element_debug_record(element) -> ElementDebugRecord:
    fill = str(element.style.get("fill", "#000000"))
    stroke = str(element.style.get("stroke", "none"))
    valid = all(math.isfinite(float(value)) for value in (element.x, element.y, element.width, element.height)) and element.width > 0 and element.height > 0
    filled = fill.strip().lower() not in {"", "none", "transparent"}
    path_ok = not isinstance(element, PathElement) or bool(element.path_data.strip())
    renderable = bool(element.visible and valid and isinstance(element, KNOWN_PRIMITIVES) and path_ok)
    radius = (element.width + element.height) / 4.0 if isinstance(element, (CircleElement, EllipseElement)) else None
    confidence = element.metadata.get("source_confidence")
    try:
        confidence = None if confidence is None else float(confidence)
    except (TypeError, ValueError):
        confidence = None
    return ElementDebugRecord(
        id=element.id, type=element.type, x=element.x, y=element.y,
        width=element.width, height=element.height, radius=radius,
        fill=fill, stroke=stroke, visible=element.visible, confidence=confidence,
        source=str(element.metadata.get("source") or element.metadata.get("primitive_source") or "svg_normalizer"),
        renderable=renderable, filled=filled, valid_geometry=valid,
    )


def element_debug_summary(document: PatternDocument) -> ElementDebugSummary:
    records = [element_debug_record(element) for element in document.elements]
    return ElementDebugSummary(
        detected_element_count=len(records),
        renderable_element_count=sum(item.renderable for item in records),
        visible_filled_element_count=sum(item.visible and item.filled and item.renderable for item in records),
        invalid_geometry_count=sum(not item.valid_geometry for item in records),
        unknown_primitive_count=sum(not isinstance(element, KNOWN_PRIMITIVES) for element in document.elements),
    )
