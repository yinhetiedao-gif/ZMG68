"""Shared, source-independent modifier stack for Pattern Lab.

Structure (Imported Elements, Grid, Radial, Curve) and effects are separate:
the source produces Elements, then this stack applies size, rotation, mask and
local overrides.  It is additive and opt-in so legacy model payloads keep their
existing evaluation path.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from enum import Enum
import math
from typing import Any, Iterable, Mapping

from ppg.foundation.models import ELEMENT_TYPES, Element, PatternDocument

from .parametric import LocalOverride, MaskModifier
from .parametric_families import (
    RotationFieldModifier,
    SizeFieldModifier,
    _apply_fields,
)


SHARED_MODIFIER_METADATA_KEY = "xiaomang_pattern_lab.shared_modifiers"


POSITION_MODES = (
    "offset",
    "attractor",
    "repeller",
    "radial_push",
    "twist",
    "wave",
)


class ModifierScopeMode(str, Enum):
    """Stable scope identifiers persisted independently from translated UI labels."""

    ALL = "all"
    SELECTED = "selected"
    CIRCLE = "circle"
    RECTANGLE = "rectangle"


@dataclass
class ModifierScope:
    """Non-destructive 0/1 influence mask shared by every stack layer.

    Scope evaluates an Element at the point where its Modifier is reached in
    the ordered stack.  It never changes visibility or source geometry: a
    non-matching Element simply keeps the result from the preceding layer.
    """

    mode: ModifierScopeMode = ModifierScopeMode.ALL
    invert: bool = False
    selected_element_ids: list[str] = field(default_factory=list)
    center_x: float = 0.0
    center_y: float = 0.0
    radius: float = 50.0
    width: float = 100.0
    height: float = 100.0
    _selected_lookup: frozenset[str] = field(default_factory=frozenset, init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.mode, ModifierScopeMode):
            try:
                self.mode = ModifierScopeMode(str(self.mode))
            except ValueError as error:
                raise ValueError("不支持的 Modifier 作用范围：%s" % self.mode) from error
        self.selected_element_ids = list(dict.fromkeys(str(item) for item in self.selected_element_ids if str(item)))
        self._selected_lookup = frozenset(self.selected_element_ids)
        for name in ("center_x", "center_y", "radius", "width", "height"):
            value = float(getattr(self, name))
            if not math.isfinite(value):
                raise ValueError("ModifierScope 参数必须是有限数字：%s" % name)
            setattr(self, name, value)
        if self.radius <= 0 or self.width <= 0 or self.height <= 0:
            raise ValueError("ModifierScope 的半径、宽度和高度必须大于 0。")

    def contains(self, element: Element) -> bool:
        if self.mode is ModifierScopeMode.ALL:
            inside = True
        elif self.mode is ModifierScopeMode.SELECTED:
            inside = element.id in self._selected_lookup
        elif self.mode is ModifierScopeMode.CIRCLE:
            inside = math.hypot(element.x - self.center_x, element.y - self.center_y) <= self.radius
        elif self.mode is ModifierScopeMode.RECTANGLE:
            inside = (
                abs(element.x - self.center_x) <= self.width / 2.0
                and abs(element.y - self.center_y) <= self.height / 2.0
            )
        else:  # pragma: no cover - guarded by __post_init__
            inside = True
        return not inside if self.invert else inside

    def influence(self, element: Element) -> float:
        return 1.0 if self.contains(element) else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "invert": self.invert,
            "selected_element_ids": list(self.selected_element_ids),
            "center_x": self.center_x,
            "center_y": self.center_y,
            "radius": self.radius,
            "width": self.width,
            "height": self.height,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "ModifierScope":
        raw = dict(value or {})
        try:
            mode = ModifierScopeMode(str(raw.get("mode", ModifierScopeMode.ALL.value)))
        except ValueError:
            mode = ModifierScopeMode.ALL
        return cls(
            mode=mode,
            invert=bool(raw.get("invert", False)),
            selected_element_ids=list(raw.get("selected_element_ids") or []),
            center_x=float(raw.get("center_x", 0.0)),
            center_y=float(raw.get("center_y", 0.0)),
            radius=max(0.01, float(raw.get("radius", 50.0))),
            width=max(0.01, float(raw.get("width", 100.0))),
            height=max(0.01, float(raw.get("height", 100.0))),
        )


def _merge_scoped_results(before: list[Element], after: list[Element],
                          scope: ModifierScope) -> list[Element]:
    """Keep the prior layer result outside Scope without changing order/IDs."""

    if len(before) != len(after):
        raise ValueError("Modifier 作用范围合并时 Element 数量发生变化。")
    result: list[Element] = []
    for original, transformed in zip(before, after):
        if original.id != transformed.id:
            raise ValueError("Modifier 作用范围合并时 Element 顺序或 ID 发生变化。")
        result.append(transformed if scope.contains(original) else original)
    return result


@dataclass
class PositionModifier:
    """Non-destructive position/deformation layer for derived Elements.

    The modifier deliberately works on element centres only.  It never edits
    ``source_elements`` or the reference image, so it can be reordered with
    other stack layers and evaluated repeatedly with identical results.
    ``amount`` is measured in document units (normally mm); ``angle`` and
    ``phase`` are degrees/radians respectively where noted below.
    """

    id: str = "position"
    mode: str = "offset"
    enabled: bool = True
    offset_x: float = 0.0
    offset_y: float = 0.0
    center_x: float = 0.0
    center_y: float = 0.0
    amount: float = 10.0
    radius: float = 100.0
    angle: float = 30.0
    wavelength: float = 50.0
    phase: float = 0.0
    strength: float = 1.0
    falloff: float = 1.0

    def __post_init__(self) -> None:
        self.mode = str(self.mode or "offset")
        if self.mode not in POSITION_MODES:
            raise ValueError("不支持的位置/变形模式：%s" % self.mode)
        for name in (
            "offset_x", "offset_y", "center_x", "center_y", "amount",
            "radius", "angle", "wavelength", "phase", "strength", "falloff",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value):
                raise ValueError("PositionModifier 参数必须是有限数字：%s" % name)
            setattr(self, name, value)
        if self.radius <= 0:
            raise ValueError("PositionModifier.radius 必须大于 0。")
        if self.wavelength <= 0:
            raise ValueError("PositionModifier.wavelength 必须大于 0。")
        if self.falloff <= 0:
            raise ValueError("PositionModifier.falloff 必须大于 0。")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "PositionModifier":
        raw = dict(value or {})
        allowed = {
            "id", "mode", "enabled", "offset_x", "offset_y", "center_x",
            "center_y", "amount", "radius", "angle", "wavelength", "phase",
            "strength", "falloff",
        }
        return cls(**{key: raw[key] for key in allowed if key in raw})

    def _influence(self, distance: float) -> float:
        normalized = max(0.0, 1.0 - distance / self.radius)
        return normalized ** self.falloff

    def apply(self, elements: Iterable[Element]) -> list[Element]:
        """Return transformed copies; no input Element is mutated."""

        result = deepcopy(list(elements))
        if not self.enabled:
            return result
        cx, cy = self.center_x, self.center_y
        theta = math.radians(self.angle)
        axis_x, axis_y = math.cos(theta), math.sin(theta)
        normal_x, normal_y = -axis_y, axis_x
        for element in result:
            px, py = float(element.x), float(element.y)
            dx = dy = 0.0
            if self.mode == "offset":
                dx = self.offset_x * self.strength
                dy = self.offset_y * self.strength
            else:
                vx, vy = px - cx, py - cy
                distance = math.hypot(vx, vy)
                influence = self._influence(distance)
                if self.mode in ("attractor", "repeller", "radial_push"):
                    if distance > 1e-12:
                        ux, uy = vx / distance, vy / distance
                    else:
                        ux, uy = 0.0, 0.0
                    sign = -1.0 if self.mode == "attractor" else 1.0
                    magnitude = self.amount * self.strength * influence
                    dx, dy = sign * ux * magnitude, sign * uy * magnitude
                elif self.mode == "twist":
                    local_angle = theta * self.strength * influence
                    cos_a, sin_a = math.cos(local_angle), math.sin(local_angle)
                    nx = vx * cos_a - vy * sin_a
                    ny = vx * sin_a + vy * cos_a
                    dx, dy = nx - vx, ny - vy
                elif self.mode == "wave":
                    coordinate = px * axis_x + py * axis_y
                    displacement = self.amount * self.strength * math.sin(
                        (2.0 * math.pi * coordinate / self.wavelength) + self.phase
                    ) * influence
                    dx, dy = normal_x * displacement, normal_y * displacement
            element.x = px + dx
            element.y = py + dy
        return result


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
                scope = ModifierScope.from_dict(layer.get("scope"))
                before = deepcopy(result)
                if layer_type == "size":
                    size = SizeFieldModifier.from_dict(params)
                    transformed = _apply_fields(
                        result, size, RotationFieldModifier(), MaskModifier(), {},
                        apply_size=True, apply_rotation=False,
                    )
                elif layer_type == "rotation":
                    rotation = RotationFieldModifier.from_dict(params)
                    transformed = _apply_fields(
                        result, SizeFieldModifier(), rotation, MaskModifier(), {},
                        apply_size=False, apply_rotation=True,
                    )
                elif layer_type == "position":
                    transformed = PositionModifier.from_dict(params).apply(result)
                else:
                    raise ValueError("不支持的 Modifier Stack 层类型：%s" % layer_type)
                result = _merge_scoped_results(before, transformed, scope)
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
                     modifier_id: str | None = None, enabled: bool = True,
                     scope: ModifierScope | Mapping[str, Any] | None = None) -> str:
        """Append one explicit Size/Rotation/Position layer and return its stable ID."""
        modifier_type = str(modifier_type)
        if modifier_type not in ("size", "rotation", "position"):
            raise ValueError("Modifier Stack 只支持 size、rotation 或 position。")
        identifier = str(modifier_id or "%s-%d" % (modifier_type, len(self.modifiers) + 1))
        if any(str(item.get("id")) == identifier for item in self.modifiers):
            raise ValueError("Modifier ID 不能重复：%s" % identifier)
        normalized_scope = scope if isinstance(scope, ModifierScope) else ModifierScope.from_dict(scope)
        self.modifiers.append({"id": identifier, "type": modifier_type,
                               "enabled": bool(enabled), "parameters": deepcopy(dict(parameters)),
                               "scope": normalized_scope.to_dict()})
        return identifier

    def scope_for(self, index: int) -> ModifierScope:
        item = self.modifiers[self._check_index(index)]
        return ModifierScope.from_dict(item.get("scope"))

    def set_modifier_scope(self, index: int,
                           scope: ModifierScope | Mapping[str, Any]) -> None:
        item = self.modifiers[self._check_index(index)]
        normalized = scope if isinstance(scope, ModifierScope) else ModifierScope.from_dict(scope)
        item["scope"] = normalized.to_dict()

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
