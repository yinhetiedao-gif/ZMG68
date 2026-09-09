"""Gate 1: pure scalar fields, reusable registry, mappings and a size consumer.

No UI, image analysis, source mutation or persistent second geometry list.
Coordinates and linear start/end distances use the document's world units
(Pattern Lab: mm). Only Constant/Linear and Size are enabled in this gate.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import math
from typing import Iterable, Protocol

from ppg.foundation.models import Element


def _finite(value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("参数场数值必须是有限数字。")
    return value


def _unit(value: float) -> float:
    return min(1.0, max(0.0, _finite(value)))


@dataclass(frozen=True)
class FieldContext:
    """Bounds of SOURCE centers, not Canvas bounds or modified dimensions."""

    bounds: tuple[float, float, float, float]

    def __post_init__(self):
        if len(self.bounds) != 4:
            raise ValueError("参数场范围必须包含四个有限坐标。")
        object.__setattr__(self, "bounds", tuple(_finite(v) for v in self.bounds))
        x0, y0, x1, y1 = self.bounds
        if x1 < x0 or y1 < y0:
            raise ValueError("参数场范围的最大坐标不能小于最小坐标。")

    @classmethod
    def from_elements(cls, elements: Iterable[Element]) -> "FieldContext":
        elements = list(elements)
        if not elements:
            return cls((0.0, 0.0, 0.0, 0.0))
        return cls((min(e.x for e in elements), min(e.y for e in elements),
                    max(e.x for e in elements), max(e.y for e in elements)))


class SharedField(Protocol):
    id: str

    def evaluate(self, element: Element, context: FieldContext) -> float: ...
    def to_dict(self) -> dict: ...


Field = SharedField


@dataclass(frozen=True)
class ConstantField:
    id: str
    value: float = 0.5

    def __post_init__(self):
        object.__setattr__(self, "value", _finite(self.value))
        if not isinstance(self.id, str) or not self.id or not 0 <= self.value <= 1:
            raise ValueError("常量场需要非空 ID 和 0～1 的数值。")

    def evaluate(self, element: Element, context: FieldContext) -> float:
        return float(self.value)

    def to_dict(self) -> dict:
        return {"id": self.id, "type": "constant", "parameters": {"value": self.value}}


@dataclass(frozen=True)
class LinearField:
    id: str
    angle: float = 0.0
    start: float | None = None
    end: float | None = None

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("线性场 ID 不能为空。")
        object.__setattr__(self, "angle", _finite(self.angle))
        if (self.start is None) != (self.end is None):
            raise ValueError("线性场起点和终点必须同时指定。")
        if self.start is not None:
            object.__setattr__(self, "start", _finite(self.start))
            object.__setattr__(self, "end", _finite(self.end))
            if self.end <= self.start:
                raise ValueError("线性场终点必须大于起点。")

    def evaluate(self, element: Element, context: FieldContext) -> float:
        angle = self.angle % 360.0
        # Exact cardinal vectors preserve legacy X/Y output without trig drift.
        cardinal = {0.0: (1.0, 0.0), 90.0: (0.0, 1.0),
                    180.0: (-1.0, 0.0), 270.0: (0.0, -1.0)}
        direction = cardinal.get(angle)
        dx, dy = direction if direction else (math.cos(math.radians(angle)), math.sin(math.radians(angle)))
        if self.start is None:
            x0, y0, x1, y1 = context.bounds
            corners = (x0 * dx + y0 * dy, x0 * dx + y1 * dy,
                       x1 * dx + y0 * dy, x1 * dx + y1 * dy)
            start, end = min(corners), max(corners)
            # Compatibility: old Linear Size used a 0.01 world-unit floor.
            span = max(end - start, 0.01)
        else:
            start, end = self.start, self.end
            span = end - start
        return _unit((_finite(element.x) * dx + _finite(element.y) * dy - start) / span)

    def to_dict(self) -> dict:
        return {"id": self.id, "type": "linear", "parameters": {
            "angle": self.angle, "start": self.start, "end": self.end}}


class FieldRegistry:
    """One definition per ID; consumers reference it without duplicating it."""

    def __init__(self, fields: Iterable[SharedField] = ()):
        self._fields: dict[str, SharedField] = {}
        for field in fields:
            self.add(field)

    def add(self, field: SharedField) -> None:
        if not field.id or field.id in self._fields:
            raise ValueError("参数场 ID 为空或重复：%s" % field.id)
        self._fields[field.id] = field

    def get(self, field_id: str) -> SharedField:
        if field_id not in self._fields:
            raise ValueError("修饰器引用了不存在的参数场：%s" % field_id)
        return self._fields[field_id]

    def to_list(self) -> list[dict]:
        return [field.to_dict() for field in self._fields.values()]

    @classmethod
    def from_list(cls, payload: list[dict]) -> "FieldRegistry":
        constructors = {"constant": ConstantField, "linear": LinearField}
        fields = []
        for raw in payload:
            constructor = constructors.get(raw.get("type"))
            if constructor is None:
                raise ValueError("本 Gate 不支持参数场类型：%s" % raw.get("type"))
            fields.append(constructor(id=raw["id"], **raw.get("parameters", {})))
        return cls(fields)


@dataclass(frozen=True)
class FieldMapping:
    min_output: float = 0.0
    max_output: float = 1.0
    invert: bool = False
    clamp: bool = True
    strength: float = 1.0
    falloff: float = 1.0
    remap_curve: str = "linear"

    def __post_init__(self):
        for name in ("min_output", "max_output", "strength", "falloff"):
            object.__setattr__(self, name, _finite(getattr(self, name)))
        if not isinstance(self.invert, bool) or not isinstance(self.clamp, bool):
            raise ValueError("参数场反转和钳制开关必须为布尔值。")
        if not 0 <= self.strength <= 1 or self.falloff <= 0:
            raise ValueError("参数场强度必须为 0～1，衰减指数必须大于 0。")
        if self.remap_curve not in ("linear", "ease_in", "ease_out", "bell", "inverse_bell", "step"):
            raise ValueError("未知的参数场映射曲线：%s" % self.remap_curve)

    def evaluate(self, value: float, *, neutral: float) -> float:
        """Clamp → invert → power falloff → remap → range → neutral blend.

        `clamp=False` validates rather than clipping out-of-domain inputs;
        scalar fields still MUST emit [0,1]. Strength=0 returns the consumer's
        neutral value (size scale=1), not a zero-sized/deleted element.
        """
        value = _finite(value)
        if self.clamp:
            value = _unit(value)
        elif not 0 <= value <= 1:
            raise ValueError("未钳制的 Scalar Field 值必须在 0～1 范围内。")
        if self.invert:
            value = 1.0 - value
        value **= self.falloff
        if self.remap_curve == "ease_in": value *= value
        elif self.remap_curve == "ease_out": value = 1.0 - (1.0 - value) ** 2
        elif self.remap_curve == "bell": value = 4.0 * value * (1.0 - value)
        elif self.remap_curve == "inverse_bell": value = 1.0 - 4.0 * value * (1.0 - value)
        elif self.remap_curve == "step": value = float(value >= 0.5)
        output = self.min_output + (self.max_output - self.min_output) * value
        return _finite(neutral + (output - neutral) * self.strength)


@dataclass(frozen=True)
class SizeModifier:
    id: str
    field_id: str
    mapping: FieldMapping
    enabled: bool = True

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id or not isinstance(self.field_id, str) or not self.field_id:
            raise ValueError("尺寸修饰器及其参数场引用 ID 不能为空。")
        if not isinstance(self.enabled, bool):
            raise ValueError("尺寸修饰器启用状态必须为布尔值。")
        if min(self.mapping.min_output, self.mapping.max_output) < 0:
            raise ValueError("尺寸比例不能小于 0。")

    def scale(self, value: float) -> float:
        return self.mapping.evaluate(value, neutral=1.0) if self.enabled else 1.0

    def to_dict(self) -> dict:
        return {"id": self.id, "type": "size", "field_id": self.field_id,
                "mapping": asdict(self.mapping), "enabled": self.enabled}


class SharedFieldEngine:
    def __init__(self, fields: FieldRegistry, modifiers: Iterable[SizeModifier]):
        self.fields = fields
        self.modifiers = tuple(modifiers)
        if len({modifier.id for modifier in self.modifiers}) != len(self.modifiers):
            raise ValueError("修饰器 ID 不能重复。")
        for modifier in self.modifiers:
            self.fields.get(modifier.field_id)

    def evaluate_fields(self, elements: Iterable[Element]) -> dict[str, tuple[float, ...]]:
        source = list(elements)
        context = FieldContext.from_elements(source)
        values = {}
        for modifier in self.modifiers:
            if modifier.enabled and modifier.field_id not in values:
                field = self.fields.get(modifier.field_id)
                values[modifier.field_id] = tuple(_unit(field.evaluate(e, context)) for e in source)
        return values

    def apply(self, elements: Iterable[Element]) -> list[Element]:
        source = list(elements)
        values = self.evaluate_fields(source)
        result = deepcopy(source)
        for modifier in self.modifiers:
            if not modifier.enabled: continue
            for element, value in zip(result, values[modifier.field_id]):
                scale = modifier.scale(value)
                element.width = max(0.01, element.width * scale)
                element.height = max(0.01, element.height * scale)
        return result

    def to_dict(self) -> dict:
        return {"version": 1, "fields": self.fields.to_list(),
                "modifiers": [modifier.to_dict() for modifier in self.modifiers]}

    @classmethod
    def from_dict(cls, payload: dict) -> "SharedFieldEngine":
        if payload.get("version", 1) != 1:
            raise ValueError("不支持的 SharedFieldEngine 版本。")
        modifiers = []
        for raw in payload.get("modifiers", []):
            if raw.get("type") != "size":
                raise ValueError("本 Gate 只支持尺寸修饰器。")
            modifiers.append(SizeModifier(raw["id"], raw["field_id"],
                            FieldMapping(**raw.get("mapping", {})), raw.get("enabled", True)))
        return cls(FieldRegistry.from_list(payload.get("fields", [])), modifiers)
