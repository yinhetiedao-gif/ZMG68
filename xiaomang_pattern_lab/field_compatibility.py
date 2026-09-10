"""Compatibility audit for the shared field -> modifier evaluation path.

The audit intentionally calls :func:`evaluate_pattern_document`, not a field's
``evaluate`` method in isolation.  It is small and deterministic so it can run
in CI and when diagnosing a project on a user's machine.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable

from ppg.foundation.models import Canvas, CircleElement, PatternDocument, Reference

from .evaluation import evaluate_pattern_document
from .parametric_families import SizeFieldMode
from .shared_fields import (
    CheckerField, ConstantField, FieldMapping, LinearField, RingField,
    RotationModifier, SizeModifier, SpiralField, StripeField, WaveField,
)

FIELD_IDS = (
    "constant", "linear_x", "linear_y", "radial", "attractor", "ring",
    "wave", "stripe", "checker", "spiral",
)

@dataclass(frozen=True)
class CompatibilityResult:
    field: str
    size: str
    rotation: str
    position: str
    detail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

def _document() -> PatternDocument:
    elements = [
        CircleElement(id="audit:a", x=-20.0, y=-10.0, width=4.0, height=4.0),
        CircleElement(id="audit:b", x=20.0, y=15.0, width=4.0, height=4.0),
    ]
    return PatternDocument(Canvas(100.0, 100.0), Reference("audit.png"), elements)

def _field(field_id: str):
    if field_id == "constant": return ConstantField("audit-field", 0.5)
    if field_id == "linear_x": return LinearField("audit-field", angle=0.0)
    if field_id == "linear_y": return LinearField("audit-field", angle=90.0)
    if field_id == "ring": return RingField("audit-field", radius=25.0, ring_width=20.0)
    if field_id == "wave": return WaveField("audit-field", wavelength=40.0)
    if field_id == "stripe": return StripeField("audit-field", period=40.0)
    if field_id == "checker": return CheckerField("audit-field", cell_width=30.0, cell_height=30.0)
    if field_id == "spiral": return SpiralField("audit-field", turns=2.0)
    return None  # radial/attractor are legacy SizeField modes, not shared ids.

def _changed(before, after, attribute: str) -> bool:
    return any(abs(float(getattr(a, attribute)) - float(getattr(b, attribute))) > 1e-8
               for a, b in zip(before, after))

def audit_field_compatibility(field_ids: Iterable[str] = FIELD_IDS) -> list[CompatibilityResult]:
    """Return formal Size/Rotation/Position support for every registered UI id."""
    results: list[CompatibilityResult] = []
    for field_id in field_ids:
        scalar = _field(field_id)
        if scalar is None:
            # These two remain supported by the legacy SizeFieldModifier but
            # have no persisted shared scalar definition or Position consumer.
            results.append(CompatibilityResult(field_id, "supported (legacy)", "unsupported", "unsupported",
                                                "当前仅由 SizeFieldModifier 兼容层实现。"))
            continue
        base = _document()
        base.fields = [scalar.to_dict()]
        base.modifiers = [
            SizeModifier("audit-size", scalar.id, FieldMapping(0.2, 0.8)).to_dict(),
        ]
        sized = evaluate_pattern_document(base)
        size_ok = _changed(base.elements, sized, "width")
        rotation_doc = _document()
        rotation_doc.fields = [scalar.to_dict()]
        rotation_doc.modifiers = [
            RotationModifier("audit-rotation", scalar.id, FieldMapping(10.0, 50.0)).to_dict(),
        ]
        rotated = evaluate_pattern_document(rotation_doc)
        rotation_ok = _changed(rotation_doc.elements, rotated, "rotation")
        results.append(CompatibilityResult(field_id, "supported" if size_ok else "broken",
                                            "supported" if rotation_ok else "broken", "unsupported"))
    return results

def compatibility_matrix() -> dict[str, dict[str, str]]:
    return {row.field: {"size": row.size, "rotation": row.rotation,
                        "position": row.position, "detail": row.detail}
            for row in audit_field_compatibility()}
