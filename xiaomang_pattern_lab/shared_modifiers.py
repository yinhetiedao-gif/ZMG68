"""Shared, source-independent modifier stack for Pattern Lab.

Structure (Imported Elements, Grid, Radial, Curve) and effects are separate:
the source produces Elements, then this stack applies size, rotation, mask and
local overrides.  It is additive and opt-in so legacy model payloads keep their
existing evaluation path.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping

from ppg.foundation.models import ELEMENT_TYPES, Element, PatternDocument

from .parametric import LocalOverride, MaskModifier
from .parametric_families import (
    RotationFieldModifier,
    SizeFieldModifier,
    _apply_fields,
)


SHARED_MODIFIER_METADATA_KEY = "xiaomang_pattern_lab.shared_modifiers"


def _element_from_dict(raw: Mapping[str, Any]) -> Element:
    values = dict(raw)
    kind = values.pop("type")
    return ELEMENT_TYPES[str(kind)](**values)


@dataclass
class SharedModifierStack:
    """Effects that can be applied to any Geometry Source.

    ``source_elements`` is a non-destructive snapshot for imported geometry;
    it prevents a materialised result from becoming the next source after a
    Save/Load cycle.  Grid/Radial/Curve sources may leave it empty and are
    rebuilt from their existing model metadata first.
    """

    size_field: SizeFieldModifier = field(default_factory=SizeFieldModifier)
    rotation_field: RotationFieldModifier = field(default_factory=RotationFieldModifier)
    mask: MaskModifier = field(default_factory=MaskModifier)
    local_overrides: dict[str, LocalOverride] = field(default_factory=dict)
    source_kind: str = "imported_elements"
    source_elements: list[dict[str, Any]] = field(default_factory=list)
    enabled: bool = True

    def apply(self, elements: Iterable[Element], *, include_overrides: bool = True) -> list[Element]:
        overrides = self.local_overrides if include_overrides else {}
        return _apply_fields(
            deepcopy(list(elements)),
            self.size_field,
            self.rotation_field,
            self.mask,
            overrides,
        )

    def source_snapshot(self) -> list[Element]:
        return [_element_from_dict(item) for item in self.source_elements]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "enabled": self.enabled,
            "source_kind": self.source_kind,
            "source_elements": deepcopy(self.source_elements),
            "size_field": self.size_field.to_dict(),
            "rotation_field": self.rotation_field.to_dict(),
            "mask": self.mask.to_dict(),
            "local_overrides": {key: value.to_dict() for key, value in self.local_overrides.items()},
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "SharedModifierStack":
        value = value or {}
        return cls(
            size_field=SizeFieldModifier.from_dict(value.get("size_field")),
            rotation_field=RotationFieldModifier.from_dict(value.get("rotation_field")),
            mask=MaskModifier.from_dict(value.get("mask")),
            local_overrides={
                str(key): LocalOverride.from_dict(item)
                for key, item in (value.get("local_overrides") or {}).items()
            },
            source_kind=str(value.get("source_kind", "imported_elements")),
            source_elements=deepcopy(value.get("source_elements") or []),
            enabled=bool(value.get("enabled", True)),
        )

    def attach(self, document: PatternDocument, *, source_kind: str | None = None,
               source_elements: Iterable[Element] | None = None) -> None:
        if source_kind is not None:
            self.source_kind = str(source_kind)
        if source_elements is not None:
            self.source_elements = [asdict(item) for item in source_elements]
        # Gate 1's Linear Size migration leaves existing projects and controls
        # compatible while persisting a real, replaceable field→modifier graph
        # on PatternDocument. Other legacy fields have no SharedField analogue
        # in this Gate and therefore do not pretend to be one.
        engine = self.size_field.shared_engine()
        if engine is not None:
            graph = engine.to_dict()
            document.fields = graph["fields"]
            document.modifiers = graph["modifiers"]
        else:
            document.fields = []
            document.modifiers = []
        document.metadata[SHARED_MODIFIER_METADATA_KEY] = self.to_dict()

    @classmethod
    def from_document(cls, document: PatternDocument) -> "SharedModifierStack | None":
        raw = document.metadata.get(SHARED_MODIFIER_METADATA_KEY)
        if not isinstance(raw, Mapping) or not bool(raw.get("enabled", True)):
            return None
        return cls.from_dict(raw)
