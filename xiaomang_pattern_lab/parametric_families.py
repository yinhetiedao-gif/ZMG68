"""Additional parametric families for Xiaomang Pattern Lab.

The Grid model remains in :mod:`parametric` for backwards compatibility.
This module deliberately shares its ``ElementPrototype``, mask and local
override representation instead of creating a second kind of Canvas geometry.
Every family produces the same Foundation ``Element`` objects.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from enum import Enum
import math
from typing import Iterable, Optional, Protocol

from ppg.foundation.models import ELEMENT_TYPES, Element

from .parametric import ElementPrototype, LocalOverride, MaskModifier
from .shared_fields import (FieldMapping, FieldRegistry, LinearField, RingField, SharedFieldEngine,
                             SizeModifier, StripeField, CheckerField, SpiralField, WaveField)


class ParametricModel(Protocol):
    """Shared non-UI contract for every parameterisation family.

    It is structural on purpose: the established Grid model can conform without
    being rewritten, while Radial, Curve and Free models remain replaceable.
    Canvas, persistence and SVG evaluation only need this contract.
    """

    local_overrides: dict[str, LocalOverride]
    mask: MaskModifier

    def generate(self, *, include_overrides: bool = True) -> list[Element]: ...
    def base_element(self, element_id: str) -> Optional[Element]: ...
    def to_dict(self) -> dict: ...


class SizeFieldMode(str, Enum):
    CONSTANT = "constant"
    LINEAR_X = "linear_x"
    LINEAR_Y = "linear_y"
    RADIAL = "radial"
    ATTRACTOR = "attractor"
    RING = "ring"
    WAVE = "wave"
    STRIPE = "stripe"
    CHECKER = "checker"
    SPIRAL = "spiral"


class RotationFieldMode(str, Enum):
    CONSTANT = "constant"
    FACE_CENTER = "face_center"
    TANGENTIAL = "tangential"
    ATTRACTOR = "attractor"


@dataclass
class SizeFieldModifier:
    mode: SizeFieldMode = SizeFieldMode.CONSTANT
    min_scale: float = 1.0
    max_scale: float = 1.0
    center_x: float = 0.0
    center_y: float = 0.0
    radius: float = 100.0
    strength: float = 1.0
    ring_width: float = 10.0
    invert: bool = False
    field_angle: float = 0.0
    wavelength: float = 50.0
    phase: float = 0.0
    amplitude: float = 1.0
    offset: float = 0.0
    duty_cycle: float = 0.5
    smoothness: float = 0.0
    cell_width: float = 20.0
    cell_height: float = 20.0
    turns: float = 3.0
    direction: int = 1
    falloff: float = 1.0

    def shared_engine(self) -> SharedFieldEngine | None:
        """Gate 1 compatibility adapter; old UI/project parameters stay authoritative.

        Only Linear Size is migrated. No duplicate persistent field settings,
        no schema migration, and no changed Rotation/Mask/Grid behaviour.
        """
        if self.mode not in (SizeFieldMode.LINEAR_X, SizeFieldMode.LINEAR_Y, SizeFieldMode.RING,
                             SizeFieldMode.WAVE, SizeFieldMode.STRIPE, SizeFieldMode.CHECKER,
                             SizeFieldMode.SPIRAL):
            return None
        if self.mode is SizeFieldMode.RING:
            scalar = RingField("legacy-ring-size", center_x=self.center_x, center_y=self.center_y,
                               radius=self.radius, ring_width=self.ring_width, falloff=self.falloff, invert=self.invert)
            field_id = scalar.id
            modifier_id = "legacy-ring-size"
        elif self.mode is SizeFieldMode.WAVE:
            scalar = WaveField("legacy-wave-size", angle=self.field_angle,
                               wavelength=self.wavelength, phase=self.phase,
                               amplitude=self.amplitude, offset=self.offset, invert=self.invert)
            field_id = scalar.id
            modifier_id = "legacy-wave-size"
        elif self.mode is SizeFieldMode.STRIPE:
            scalar = StripeField("legacy-stripe-size", angle=self.field_angle,
                                 period=self.wavelength, phase=self.phase,
                                 duty_cycle=self.duty_cycle, smoothness=self.smoothness,
                                 invert=self.invert)
            field_id = scalar.id
            modifier_id = "legacy-stripe-size"
        elif self.mode is SizeFieldMode.CHECKER:
            scalar = CheckerField("legacy-checker-size", angle=self.field_angle,
                                  cell_width=self.cell_width, cell_height=self.cell_height,
                                  offset_x=self.center_x, offset_y=self.center_y, invert=self.invert)
            field_id = scalar.id
            modifier_id = "legacy-checker-size"
        elif self.mode is SizeFieldMode.SPIRAL:
            scalar = SpiralField("legacy-spiral-size", center_x=self.center_x, center_y=self.center_y,
                                 turns=self.turns, phase=self.phase, direction=self.direction,
                                 falloff=self.falloff, invert=self.invert)
            field_id = scalar.id
            modifier_id = "legacy-spiral-size"
        else:
            scalar = LinearField("legacy-linear-size", angle=0.0 if self.mode is SizeFieldMode.LINEAR_X else 90.0)
            field_id = scalar.id
            modifier_id = "legacy-size"
        mapping = FieldMapping(min_output=self.min_scale, max_output=self.max_scale, strength=self.strength)
        return SharedFieldEngine(FieldRegistry([scalar]), [SizeModifier(modifier_id, field_id, mapping)])

    def to_dict(self) -> dict:
        result = {"mode": self.mode.value, "min_scale": self.min_scale, "max_scale": self.max_scale,
                  "center_x": self.center_x, "center_y": self.center_y, "radius": self.radius, "strength": self.strength}
        # Keep old JSON byte-for-byte compatible for every pre-Ring mode.
        if self.mode is SizeFieldMode.RING:
            result.update({"ring_width": self.ring_width, "falloff": self.falloff, "invert": self.invert})
        elif self.mode is SizeFieldMode.WAVE:
            result.update({"field_angle": self.field_angle, "wavelength": self.wavelength,
                           "phase": self.phase, "amplitude": self.amplitude,
                           "offset": self.offset, "invert": self.invert})
        elif self.mode is SizeFieldMode.STRIPE:
            result.update({"field_angle": self.field_angle, "wavelength": self.wavelength,
                           "phase": self.phase, "duty_cycle": self.duty_cycle,
                           "smoothness": self.smoothness, "invert": self.invert})
        elif self.mode is SizeFieldMode.CHECKER:
            result.update({"field_angle": self.field_angle, "cell_width": self.cell_width,
                           "cell_height": self.cell_height, "invert": self.invert})
        elif self.mode is SizeFieldMode.SPIRAL:
            result.update({"turns": self.turns, "phase": self.phase, "direction": self.direction,
                           "falloff": self.falloff, "invert": self.invert})
        return result

    @classmethod
    def from_dict(cls, value: dict | None) -> "SizeFieldModifier":
        value = value or {}
        try: mode = SizeFieldMode(value.get("mode", SizeFieldMode.CONSTANT.value))
        except ValueError: mode = SizeFieldMode.CONSTANT
        return cls(mode=mode, min_scale=max(0.01, float(value.get("min_scale", 1.0))),
                   max_scale=max(0.01, float(value.get("max_scale", 1.0))),
                   center_x=float(value.get("center_x", 0.0)), center_y=float(value.get("center_y", 0.0)),
                   radius=max(0.01, float(value.get("radius", 100.0))), strength=min(1.0, max(0.0, float(value.get("strength", 1.0)))),
                   ring_width=max(0.01, float(value.get("ring_width", 10.0))), invert=bool(value.get("invert", False)),
                   field_angle=float(value.get("field_angle", 0.0)), wavelength=max(0.01, float(value.get("wavelength", 50.0))),
                   phase=float(value.get("phase", 0.0)), amplitude=min(1.0, max(0.0, float(value.get("amplitude", 1.0)))),
                   offset=min(1.0, max(0.0, float(value.get("offset", 0.0)))),
                   duty_cycle=min(1.0, max(0.0, float(value.get("duty_cycle", 0.5)))),
                   smoothness=min(0.5, max(0.0, float(value.get("smoothness", 0.0)))),
                   cell_width=max(0.01, float(value.get("cell_width", 20.0))), cell_height=max(0.01, float(value.get("cell_height", 20.0))),
                   turns=max(0.0, float(value.get("turns", 3.0))), direction=1 if int(value.get("direction", 1)) >= 0 else -1,
                   falloff=max(0.01, float(value.get("falloff", 1.0))))


@dataclass
class RotationFieldModifier:
    mode: RotationFieldMode = RotationFieldMode.CONSTANT
    angle: float = 0.0
    center_x: float = 0.0
    center_y: float = 0.0
    strength: float = 1.0

    def to_dict(self) -> dict:
        return {"mode": self.mode.value, "angle": self.angle, "center_x": self.center_x, "center_y": self.center_y, "strength": self.strength}

    @classmethod
    def from_dict(cls, value: dict | None) -> "RotationFieldModifier":
        value = value or {}
        try: mode = RotationFieldMode(value.get("mode", RotationFieldMode.CONSTANT.value))
        except ValueError: mode = RotationFieldMode.CONSTANT
        return cls(mode=mode, angle=float(value.get("angle", 0.0)), center_x=float(value.get("center_x", 0.0)),
                   center_y=float(value.get("center_y", 0.0)), strength=min(1.0, max(0.0, float(value.get("strength", 1.0)))))


def _element_from_dict(raw: dict) -> Element:
    values = dict(raw); kind = values.pop("type")
    return ELEMENT_TYPES[kind](**values)


def _element_dicts(elements: Iterable[Element]) -> list[dict]:
    return [asdict(item) for item in elements]


def _apply_override(element: Element, override: LocalOverride | None) -> Element:
    if override is None:
        return element
    element.x += override.offset_x; element.y += override.offset_y
    element.width = max(0.01, element.width * override.scale_x); element.height = max(0.01, element.height * override.scale_y)
    element.rotation += override.rotation_offset
    if override.visible is not None: element.visible = override.visible
    return element


def _field_factor(field: SizeFieldModifier, element: Element, bounds: tuple[float, float, float, float]) -> float:
    xmin, ymin, xmax, ymax = bounds
    if field.mode is SizeFieldMode.CONSTANT: return 0.5
    if field.mode in (SizeFieldMode.LINEAR_X, SizeFieldMode.LINEAR_Y, SizeFieldMode.RING,
                      SizeFieldMode.WAVE, SizeFieldMode.STRIPE, SizeFieldMode.CHECKER,
                      SizeFieldMode.SPIRAL):
        raise ValueError("共享标量尺寸场必须通过 SharedFieldEngine 计算。")
    return min(1.0, math.hypot(element.x - field.center_x, element.y - field.center_y) / field.radius)


def _apply_fields(elements: list[Element], size_field: SizeFieldModifier, rotation_field: RotationFieldModifier,
                  mask: MaskModifier, overrides: dict[str, LocalOverride], *, apply_size: bool = True,
                  apply_rotation: bool = True) -> list[Element]:
    if not elements: return []
    xmin, xmax = min(item.x for item in elements), max(item.x for item in elements)
    ymin, ymax = min(item.y for item in elements), max(item.y for item in elements)
    engine = size_field.shared_engine() if apply_size else None
    values = engine.evaluate_fields(elements) if engine else {}
    consumer = engine.modifiers[0] if engine else None
    for index, element in enumerate(elements):
        if not apply_size:
            scale = 1.0
        elif consumer:
            scale = consumer.scale(values[consumer.field_id][index])
        else:
            factor = _field_factor(size_field, element, (xmin, ymin, xmax, ymax))
            scale = size_field.min_scale + (size_field.max_scale - size_field.min_scale) * factor
            scale = 1.0 + (scale - 1.0) * size_field.strength
        element.width = max(0.01, element.width * scale); element.height = max(0.01, element.height * scale)
        if apply_rotation:
            dx, dy = element.x - rotation_field.center_x, element.y - rotation_field.center_y
            if rotation_field.mode is RotationFieldMode.FACE_CENTER: target = math.degrees(math.atan2(dy, dx))
            elif rotation_field.mode is RotationFieldMode.TANGENTIAL: target = math.degrees(math.atan2(dy, dx)) + 90.0
            elif rotation_field.mode is RotationFieldMode.ATTRACTOR: target = math.degrees(math.atan2(dy, dx))
            else: target = rotation_field.angle
            element.rotation += target * rotation_field.strength
        element.visible = element.visible and mask.contains(element.x, element.y)
        _apply_override(element, overrides.get(element.id))
    return elements


@dataclass
class RadialParametricModel:
    count: int = 12
    center_x: float = 0.0
    center_y: float = 0.0
    start_angle: float = 0.0
    end_angle: float = 360.0
    base_radius: float = 50.0
    end_radius: float = 50.0
    element_width: float = 6.0
    element_height: float = 6.0
    rotation: float = 0.0
    prototype: ElementPrototype = field(default_factory=ElementPrototype)
    size_field: SizeFieldModifier = field(default_factory=SizeFieldModifier)
    rotation_field: RotationFieldModifier = field(default_factory=RotationFieldModifier)
    mask: MaskModifier = field(default_factory=MaskModifier)
    local_overrides: dict[str, LocalOverride] = field(default_factory=dict)

    family: str = field(default="radial", init=False)

    @staticmethod
    def element_id(index: int) -> str: return "radial:i%d" % index

    def normalized(self) -> "RadialParametricModel":
        self.count = max(1, int(self.count)); self.base_radius = max(0.0, float(self.base_radius)); self.end_radius = max(0.0, float(self.end_radius))
        self.element_width = max(0.01, float(self.element_width)); self.element_height = max(0.01, float(self.element_height)); return self

    def _base(self) -> list[Element]:
        self.normalized(); closed = abs(abs(self.end_angle - self.start_angle) - 360.0) < 1e-4
        divisor = self.count if closed else max(1, self.count - 1)
        result = []
        for index in range(self.count):
            factor = index / divisor; angle = math.radians(self.start_angle + (self.end_angle - self.start_angle) * factor + self.rotation)
            radius = self.base_radius + (self.end_radius - self.base_radius) * factor
            result.append(self.prototype.instantiate(element_id=self.element_id(index), x=self.center_x + math.cos(angle) * radius,
                y=self.center_y + math.sin(angle) * radius, width=self.element_width, height=self.element_height, rotation=math.degrees(angle), visible=True))
        return result

    def generate(self, *, include_overrides: bool = True) -> list[Element]:
        items = self._base(); return _apply_fields(items, self.size_field, self.rotation_field, self.mask, self.local_overrides if include_overrides else {})
    def base_element(self, element_id: str) -> Optional[Element]: return next((item for item in self.generate(include_overrides=False) if item.id == element_id), None)
    def to_dict(self) -> dict:
        return {"count": self.count, "center_x": self.center_x, "center_y": self.center_y, "start_angle": self.start_angle, "end_angle": self.end_angle,
                "base_radius": self.base_radius, "end_radius": self.end_radius, "element_width": self.element_width, "element_height": self.element_height,
                "rotation": self.rotation, "prototype": self.prototype.to_dict(), "size_field": self.size_field.to_dict(), "rotation_field": self.rotation_field.to_dict(),
                "mask": self.mask.to_dict(), "local_overrides": {key: value.to_dict() for key, value in self.local_overrides.items()}}
    @classmethod
    def from_dict(cls, raw: dict | None) -> "RadialParametricModel":
        raw = raw or {}; model = cls(**{key: raw.get(key, getattr(cls(), key)) for key in ("count", "center_x", "center_y", "start_angle", "end_angle", "base_radius", "end_radius", "element_width", "element_height", "rotation")},
            prototype=ElementPrototype.from_dict(raw.get("prototype")), size_field=SizeFieldModifier.from_dict(raw.get("size_field")), rotation_field=RotationFieldModifier.from_dict(raw.get("rotation_field")), mask=MaskModifier.from_dict(raw.get("mask")))
        model.local_overrides = {key: LocalOverride.from_dict(value) for key, value in (raw.get("local_overrides") or {}).items()}; return model.normalized()


@dataclass
class AlongCurveParametricModel:
    path_points: list[tuple[float, float]] = field(default_factory=list)
    count: int = 2
    element_width: float = 6.0
    element_height: float = 6.0
    rotate_along_path: bool = True
    prototype: ElementPrototype = field(default_factory=ElementPrototype)
    size_field: SizeFieldModifier = field(default_factory=SizeFieldModifier)
    rotation_field: RotationFieldModifier = field(default_factory=RotationFieldModifier)
    mask: MaskModifier = field(default_factory=MaskModifier)
    local_overrides: dict[str, LocalOverride] = field(default_factory=dict)
    family: str = field(default="along_curve", init=False)

    @staticmethod
    def element_id(index: int) -> str: return "curve:i%d" % index
    def normalized(self) -> "AlongCurveParametricModel":
        self.count = max(1, int(self.count)); self.element_width = max(0.01, float(self.element_width)); self.element_height = max(0.01, float(self.element_height))
        if len(self.path_points) < 2: raise ValueError("沿曲线模型至少需要两个路径点。")
        self.path_points = [(float(x), float(y)) for x, y in self.path_points]; return self
    def _sample(self, distance: float) -> tuple[float, float, float]:
        lengths = [math.hypot(x2-x1, y2-y1) for (x1,y1),(x2,y2) in zip(self.path_points, self.path_points[1:])]; total = sum(lengths)
        remaining = min(max(0.0, distance), total)
        for (x1,y1),(x2,y2),length in zip(self.path_points, self.path_points[1:], lengths):
            # ``lengths[-1]`` is a value, not a segment index.  Treating an
            # equal-length first segment as the last segment used to clamp
            # every later sample back into that first segment.  Only the
            # remaining distance decides which segment owns the sample.
            if remaining <= length:
                factor = remaining / max(length, 1e-9); return x1+(x2-x1)*factor, y1+(y2-y1)*factor, math.degrees(math.atan2(y2-y1,x2-x1))
            remaining -= length
        x,y=self.path_points[-1]; return x,y,0.0
    def _base(self) -> list[Element]:
        self.normalized(); total=sum(math.hypot(x2-x1,y2-y1) for (x1,y1),(x2,y2) in zip(self.path_points,self.path_points[1:])); divisor=max(1,self.count-1); result=[]
        for index in range(self.count):
            x,y,angle=self._sample(total*index/divisor); result.append(self.prototype.instantiate(element_id=self.element_id(index),x=x,y=y,width=self.element_width,height=self.element_height,rotation=angle if self.rotate_along_path else 0.0,visible=True))
        return result
    def generate(self, *, include_overrides: bool=True) -> list[Element]: return _apply_fields(self._base(),self.size_field,self.rotation_field,self.mask,self.local_overrides if include_overrides else {})
    def base_element(self, element_id:str)->Optional[Element]: return next((item for item in self.generate(include_overrides=False) if item.id==element_id),None)
    def to_dict(self)->dict: return {"path_points":[list(item) for item in self.path_points],"count":self.count,"element_width":self.element_width,"element_height":self.element_height,"rotate_along_path":self.rotate_along_path,"prototype":self.prototype.to_dict(),"size_field":self.size_field.to_dict(),"rotation_field":self.rotation_field.to_dict(),"mask":self.mask.to_dict(),"local_overrides":{k:v.to_dict() for k,v in self.local_overrides.items()}}
    @classmethod
    def from_dict(cls,raw:dict|None)->"AlongCurveParametricModel":
        raw=raw or {}; model=cls(path_points=[(float(p[0]),float(p[1])) for p in raw.get("path_points",[]) if len(p)==2],count=int(raw.get("count",2)),element_width=float(raw.get("element_width",6)),element_height=float(raw.get("element_height",6)),rotate_along_path=bool(raw.get("rotate_along_path",True)),prototype=ElementPrototype.from_dict(raw.get("prototype")),size_field=SizeFieldModifier.from_dict(raw.get("size_field")),rotation_field=RotationFieldModifier.from_dict(raw.get("rotation_field")),mask=MaskModifier.from_dict(raw.get("mask")))
        model.local_overrides={k:LocalOverride.from_dict(v) for k,v in (raw.get("local_overrides") or {}).items()}; return model.normalized()


@dataclass
class FreeParametricModel:
    """Fields over imported Elements when no global generator is trustworthy."""
    base_elements: list[dict] = field(default_factory=list)
    size_field: SizeFieldModifier = field(default_factory=SizeFieldModifier)
    rotation_field: RotationFieldModifier = field(default_factory=RotationFieldModifier)
    mask: MaskModifier = field(default_factory=MaskModifier)
    local_overrides: dict[str, LocalOverride] = field(default_factory=dict)
    family: str = field(default="free", init=False)
    @classmethod
    def from_elements(cls,elements:Iterable[Element])->"FreeParametricModel": return cls(base_elements=_element_dicts(elements))
    def generate(self, *,include_overrides:bool=True)->list[Element]: return _apply_fields([_element_from_dict(item) for item in self.base_elements],self.size_field,self.rotation_field,self.mask,self.local_overrides if include_overrides else {})
    def base_element(self,element_id:str)->Optional[Element]: return next((item for item in self.generate(include_overrides=False) if item.id==element_id),None)
    def to_dict(self)->dict:return {"base_elements":deepcopy(self.base_elements),"size_field":self.size_field.to_dict(),"rotation_field":self.rotation_field.to_dict(),"mask":self.mask.to_dict(),"local_overrides":{k:v.to_dict() for k,v in self.local_overrides.items()}}
    @classmethod
    def from_dict(cls,raw:dict|None)->"FreeParametricModel":
        raw=raw or {}; return cls(base_elements=deepcopy(raw.get("base_elements") or []),size_field=SizeFieldModifier.from_dict(raw.get("size_field")),rotation_field=RotationFieldModifier.from_dict(raw.get("rotation_field")),mask=MaskModifier.from_dict(raw.get("mask")),local_overrides={k:LocalOverride.from_dict(v) for k,v in (raw.get("local_overrides") or {}).items()})


def parametric_model_from_payload(family: str, payload: dict):
    if family == "radial": return RadialParametricModel.from_dict(payload)
    if family == "along_curve": return AlongCurveParametricModel.from_dict(payload)
    # Metadata stores the UI mode (``free_parametric``), whereas the model's
    # own family name is simply ``free``.  Both describe the same durable
    # field-over-imported-elements model.
    if family in {"free", "free_parametric"}: return FreeParametricModel.from_dict(payload)
    return None
