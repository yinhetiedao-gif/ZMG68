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
    # Gate H: optional ordered layers.  Legacy size_field/rotation_field stay
    # intact for old documents; when this list is non-empty it becomes the
    # explicit, user-manageable execution order.
    modifiers: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Accept both serialized records and Element instances at the API
        # boundary, then keep one durable representation internally.
        normalized: list[dict[str, Any]] = []
        for item in self.source_elements:
            if isinstance(item, Element):
                normalized.append(asdict(item))
            elif isinstance(item, Mapping):
                normalized.append(deepcopy(dict(item)))
            else:
                raise TypeError("source_elements 必须是 Element 或字典记录。")
        self.source_elements = normalized

    def apply(self, elements: Iterable[Element], *, include_overrides: bool = True,
              include_size: bool = True, include_rotation: bool = True) -> list[Element]:
        """Apply the legacy stack to a source.

        ``PatternDocument.fields/modifiers`` is the durable shared-field graph.
        When the evaluator has already consumed that graph, ``include_size`` is
        set to false so a migrated Linear/Ring size field cannot be applied a
        second time by this compatibility stack.  Rotation, mask and local
        overrides still run in the same order.
        """
        overrides = self.local_overrides if include_overrides else {}
        if self.modifiers:
            result = deepcopy(list(elements))
            # Each layer is evaluated from the result of the previous layer;
            # source geometry is never mutated.  Mask/overrides are applied
            # once at the end so reordering layers remains deterministic.
            for layer in self.modifiers:
                if not bool(layer.get("enabled", True)):
                    continue
                layer_type = str(layer.get("type", ""))
                params = layer.get("parameters") or {}
                if layer_type == "size":
                    size = SizeFieldModifier.from_dict(params)
                    result = _apply_fields(
                        result, size, RotationFieldModifier(), MaskModifier(), {},
                        apply_size=True, apply_rotation=False,
                    )
                elif layer_type == "rotation":
                    rotation = RotationFieldModifier.from_dict(params)
                    result = _apply_fields(
                        result, SizeFieldModifier(), rotation, MaskModifier(), {},
                        apply_size=False, apply_rotation=True,
                    )
                else:
                    raise ValueError("不支持的 Modifier Stack 层类型：%s" % layer_type)
            result = _apply_fields(
                result, SizeFieldModifier(), RotationFieldModifier(), self.mask, overrides,
                apply_size=False, apply_rotation=False,
            )
            return result
        return _apply_fields(
            deepcopy(list(elements)),
            self.size_field,
            self.rotation_field,
            self.mask,
            overrides,
            apply_size=include_size,
            apply_rotation=include_rotation,
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
            "modifiers": deepcopy(self.modifiers),
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
            modifiers=[deepcopy(item) for item in (value.get("modifiers") or []) if isinstance(item, Mapping)],
        )

    def add_modifier(self, modifier_type: str, parameters: Mapping[str, Any], *,
                     modifier_id: str | None = None, enabled: bool = True) -> str:
        """Append one explicit Size/Rotation layer and return its stable ID."""
        modifier_type = str(modifier_type)
        if modifier_type not in ("size", "rotation"):
            raise ValueError("Modifier Stack 只支持 size 或 rotation。")
        identifier = str(modifier_id or "%s-%d" % (modifier_type, len(self.modifiers) + 1))
        if any(str(item.get("id")) == identifier for item in self.modifiers):
            raise ValueError("Modifier ID 不能重复：%s" % identifier)
        self.modifiers.append({"id": identifier, "type": modifier_type,
                               "enabled": bool(enabled), "parameters": deepcopy(dict(parameters))})
        return identifier

    def _check_index(self, index: int) -> int:
        index = int(index)
        if index < 0 or index >= len(self.modifiers):
            raise IndexError("Modifier Stack 索引超出范围。")
        return index

    def set_enabled(self, index: int, enabled: bool) -> None:
        self.modifiers[self._check_index(index)]["enabled"] = bool(enabled)

    def delete_modifier(self, index: int) -> dict[str, Any]:
        return self.modifiers.pop(self._check_index(index))

    def duplicate_modifier(self, index: int) -> str:
        source = deepcopy(self.modifiers[self._check_index(index)])
        base = str(source.get("id") or source.get("type") or "modifier")
        candidate = base + "-copy"
        suffix = 2
        ids = {str(item.get("id")) for item in self.modifiers}
        while candidate in ids:
            candidate = "%s-%d" % (base, suffix); suffix += 1
        source["id"] = candidate
        self.modifiers.insert(index + 1, source)
        return candidate

    def move_modifier(self, index: int, delta: int) -> int:
        index = self._check_index(index)
        target = index + int(delta)
        if target < 0 or target >= len(self.modifiers):
            return index
        self.modifiers[index], self.modifiers[target] = self.modifiers[target], self.modifiers[index]
        return target

    def reset_modifier(self, index: int) -> None:
        item = self.modifiers[self._check_index(index)]
        item["enabled"] = True
        item["parameters"] = {}

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
        if self.modifiers:
            # Explicit Gate-H layers are evaluated by this stack; clear the
            # compatibility graph to prevent a second application.
            document.fields = []
            document.modifiers = []
        else:
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
