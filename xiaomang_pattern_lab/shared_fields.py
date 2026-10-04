"""Shared scalar fields, reusable registry, mappings and a size consumer.

No UI, image analysis, source mutation or persistent second geometry list.
Coordinates and linear start/end distances use the document's world units
(Pattern Lab: mm). Gate A adds Ring without changing the existing consumers.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field as runtime_field
import math
from pathlib import Path
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


@dataclass(frozen=True)
class RingField:
    """A radial band whose peak is at ``radius``.

    ``ring_width`` is the full-width support of the band: at
    ``radius ± ring_width / 2`` the scalar is zero, and at ``radius`` it is
    one.  The value is computed from element world coordinates, independent of
    Canvas pixels, element dimensions, or document bounds.
    """

    id: str
    center_x: float = 0.0
    center_y: float = 0.0
    radius: float = 50.0
    ring_width: float = 10.0
    falloff: float = 1.0
    invert: bool = False

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("环形场 ID 不能为空。")
        for name in ("center_x", "center_y", "radius", "ring_width", "falloff"):
            object.__setattr__(self, name, _finite(getattr(self, name)))
        if self.radius < 0:
            raise ValueError("环形场半径不能小于 0。")
        if self.ring_width <= 0:
            raise ValueError("环形场宽度必须大于 0。")
        if self.falloff <= 0:
            raise ValueError("环形场衰减必须大于 0。")
        if not isinstance(self.invert, bool):
            raise ValueError("环形场反转参数必须为布尔值。")

    def evaluate(self, element: Element, context: FieldContext) -> float:
        del context  # Ring is world-coordinate based and does not need bounds.
        distance = math.hypot(_finite(element.x) - self.center_x,
                              _finite(element.y) - self.center_y)
        half_width = self.ring_width / 2.0
        support = _unit(1.0 - abs(distance - self.radius) / half_width)
        value = support ** self.falloff
        return _unit(1.0 - value if self.invert else value)

    def to_dict(self) -> dict:
        return {"id": self.id, "type": "ring", "parameters": {
            "center_x": self.center_x, "center_y": self.center_y,
            "radius": self.radius, "ring_width": self.ring_width,
            "falloff": self.falloff, "invert": self.invert}}


@dataclass(frozen=True)
class WaveField:
    """A deterministic sinusoidal scalar in world coordinates.

    ``amplitude`` is the peak-to-peak normalized range and ``offset`` is the
    lower baseline.  Projection uses millimetre/world coordinates, so Canvas
    pixels and margins never change the result.
    """

    id: str
    angle: float = 0.0
    wavelength: float = 50.0
    phase: float = 0.0
    amplitude: float = 1.0
    offset: float = 0.0
    invert: bool = False

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("波浪场 ID 不能为空。")
        for name in ("angle", "wavelength", "phase", "amplitude", "offset"):
            object.__setattr__(self, name, _finite(getattr(self, name)))
        if self.wavelength <= 0:
            raise ValueError("波浪场波长必须大于 0。")
        if not 0 <= self.amplitude <= 1 or not 0 <= self.offset <= 1:
            raise ValueError("波浪场振幅和偏移必须在 0～1 范围内。")
        if not isinstance(self.invert, bool):
            raise ValueError("波浪场反转参数必须为布尔值。")

    def evaluate(self, element: Element, context: FieldContext) -> float:
        del context
        angle = math.radians(self.angle)
        projection = _finite(element.x) * math.cos(angle) + _finite(element.y) * math.sin(angle)
        phase = (2.0 * math.pi * projection / self.wavelength) + self.phase
        value = self.offset + self.amplitude * 0.5 * (math.sin(phase) + 1.0)
        value = _unit(value)
        return _unit(1.0 - value if self.invert else value)

    def to_dict(self) -> dict:
        return {"id": self.id, "type": "wave", "parameters": {
            "angle": self.angle, "wavelength": self.wavelength, "phase": self.phase,
            "amplitude": self.amplitude, "offset": self.offset, "invert": self.invert}}


def _noise_hash(seed: int, x: int, y: int) -> float:
    """Stable integer lattice hash, independent of Python's randomized hash()."""

    value = (int(seed) * 0x9E3779B1 + int(x) * 0x85EBCA77 + int(y) * 0xC2B2AE3D) & 0xFFFFFFFF
    value ^= value >> 16
    value = (value * 0x7FEB352D) & 0xFFFFFFFF
    value ^= value >> 15
    value = (value * 0x846CA68B) & 0xFFFFFFFF
    value ^= value >> 16
    return value / 0xFFFFFFFF


def _noise_fade(value: float) -> float:
    """Quintic smoothing keeps neighbouring value-noise cells continuous."""

    value = _unit(value)
    return value * value * value * (value * (value * 6.0 - 15.0) + 10.0)


def _value_noise(seed: int, x: float, y: float) -> float:
    """Continuous deterministic 2D value noise in the normalized 0..1 range."""

    x0, y0 = math.floor(x), math.floor(y)
    tx, ty = _noise_fade(x - x0), _noise_fade(y - y0)
    a = _noise_hash(seed, x0, y0)
    b = _noise_hash(seed, x0 + 1, y0)
    c = _noise_hash(seed, x0, y0 + 1)
    d = _noise_hash(seed, x0 + 1, y0 + 1)
    top = a + (b - a) * tx
    bottom = c + (d - c) * tx
    return _unit(top + (bottom - top) * ty)


@dataclass(frozen=True)
class NoiseField:
    """Lightweight deterministic, continuous spatial noise in world units.

    ``scale`` is the world/mm size of a broad base feature: larger values yield
    slower, larger regions.  ``strength`` blends the fractal result around the
    neutral scalar 0.5, so disabling its influence does not create an abrupt
    field discontinuity.  This field never samples screen pixels, mutates
    Elements, or depends on traversal order.
    """

    id: str
    scale: float = 50.0
    strength: float = 1.0
    seed: int = 1
    offset_x: float = 0.0
    offset_y: float = 0.0
    octaves: int = 3
    contrast: float = 1.0
    invert: bool = False

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("有机噪声场 ID 不能为空。")
        for name in ("scale", "strength", "offset_x", "offset_y", "contrast"):
            object.__setattr__(self, name, _finite(getattr(self, name)))
        if self.scale <= 0:
            raise ValueError("有机噪声尺度必须大于 0。")
        if not 0 <= self.strength <= 1:
            raise ValueError("有机噪声强度必须在 0～1 范围内。")
        if self.contrast <= 0:
            raise ValueError("有机噪声对比度必须大于 0。")
        if isinstance(self.seed, bool):
            raise ValueError("有机噪声种子必须是整数。")
        seed = int(self.seed)
        if seed != self.seed:
            raise ValueError("有机噪声种子必须是整数。")
        object.__setattr__(self, "seed", seed)
        octaves = int(self.octaves)
        if octaves != self.octaves or not 1 <= octaves <= 8:
            raise ValueError("有机噪声层数必须是 1～8 的整数。")
        object.__setattr__(self, "octaves", octaves)
        if not isinstance(self.invert, bool):
            raise ValueError("有机噪声反转参数必须为布尔值。")

    def evaluate(self, element: Element, context: FieldContext) -> float:
        del context
        x = (_finite(element.x) + self.offset_x) / self.scale
        y = (_finite(element.y) + self.offset_y) / self.scale
        total = 0.0
        weight = 0.0
        amplitude = 1.0
        frequency = 1.0
        for octave in range(self.octaves):
            total += _value_noise(self.seed + octave * 1013, x * frequency, y * frequency) * amplitude
            weight += amplitude
            frequency *= 2.0
            amplitude *= 0.5
        value = total / max(weight, 1e-12)
        value = _unit(0.5 + (value - 0.5) * self.strength)
        value = _unit(0.5 + (value - 0.5) * self.contrast)
        return _unit(1.0 - value if self.invert else value)

    def to_dict(self) -> dict:
        return {"id": self.id, "type": "noise", "parameters": {
            "scale": self.scale, "strength": self.strength, "seed": self.seed,
            "offset_x": self.offset_x, "offset_y": self.offset_y,
            "octaves": self.octaves, "contrast": self.contrast,
            "invert": self.invert}}


_IMAGE_SAMPLE_CACHE: dict[tuple[str, int, int], tuple[int, int, tuple[int, ...]]] = {}


@dataclass(frozen=True)
class ImageField:
    """Read-only grayscale field sampled from the current Reference image.

    World coordinates are mapped against the source-element center bounds
    supplied by :class:`FieldContext`; Canvas zoom/pan therefore never changes
    the sampled value.  The cached tuple is only an acceleration detail and is
    invalidated automatically by file mtime/size changes.
    """

    id: str
    image_path: str = ""
    contrast: float = 1.0
    black_point: float = 0.0
    white_point: float = 1.0
    invert: bool = False
    out_of_bounds: str = "clamp"
    # Optional image registration in document world units. Legacy fields keep
    # their center-bounds mapping and brightness polarity unchanged.
    sample_bounds: tuple[float, float, float, float] | None = None
    black_is_one: bool = False
    sampling_mode: str = "grayscale"
    threshold: float = 0.5
    _prepared_pixels: tuple | None = runtime_field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("图片场 ID 不能为空。")
        object.__setattr__(self, "image_path", str(self.image_path or ""))
        contrast = _finite(self.contrast)
        if contrast <= 0:
            raise ValueError("图片场对比度必须大于 0。")
        object.__setattr__(self, "contrast", contrast)
        black, white = _unit(self.black_point), _unit(self.white_point)
        if white <= black:
            raise ValueError("图片场白场必须大于黑场。")
        object.__setattr__(self, "black_point", black)
        object.__setattr__(self, "white_point", white)
        if self.out_of_bounds not in ("clamp", "zero"):
            raise ValueError("图片场超出范围策略只能是 clamp 或 zero。")
        if self.sample_bounds is not None:
            bounds = FieldContext(tuple(self.sample_bounds)).bounds
            if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
                raise ValueError("图片场映射范围必须有正面积。")
            object.__setattr__(self, "sample_bounds", bounds)
        if self.sampling_mode not in ("grayscale", "mask"):
            raise ValueError("图片场采样只能是 grayscale 或 mask。")
        if type(self.invert) is not bool or type(self.black_is_one) is not bool:
            raise ValueError("图片场反转/黑白语义必须是布尔值。")
        threshold = _finite(self.threshold)
        if not 0 <= threshold <= 1:
            raise ValueError("图片场阈值必须在 0～1 之间。")
        object.__setattr__(self, "threshold", threshold)

    def available(self) -> bool:
        return bool(self.image_path) and Path(self.image_path).is_file()

    def prepare_sampling(self) -> None:
        """Pin one read-only pixel snapshot for this request's field registry.

        Subsequent requests build a new registry and recheck file mtime/size;
        legacy single-sample callers keep their existing invalidation behavior.
        """
        image = self._pixels()
        if image is None:
            raise ValueError("图片场源图片无法读取。")
        object.__setattr__(self, "_prepared_pixels", image)

    def _pixels(self) -> tuple[int, int, tuple[int, ...]] | None:
        path = Path(self.image_path)
        if not path.is_file():
            return None
        try:
            stat = path.stat()
            key = (str(path.resolve()), int(stat.st_mtime_ns), int(stat.st_size))
            cached = _IMAGE_SAMPLE_CACHE.get(key)
            if cached is not None:
                return cached
            # Pillow remains an optional/lazy dependency for the field module;
            # importing a document without an ImageField never reads an image.
            from PIL import Image
            with Image.open(path) as image:
                gray = image.convert("L")
                width, height = gray.size
                pixels = tuple(int(item) for item in gray.getdata())
            # Drop stale versions of the same path to keep long sessions bounded.
            resolved = str(path.resolve())
            for old in tuple(_IMAGE_SAMPLE_CACHE):
                if old[0] == resolved and old != key:
                    _IMAGE_SAMPLE_CACHE.pop(old, None)
            _IMAGE_SAMPLE_CACHE[key] = (width, height, pixels)
            return _IMAGE_SAMPLE_CACHE[key]
        except (OSError, ValueError):
            return None

    def evaluate(self, element: Element, context: FieldContext) -> float:
        image = self._prepared_pixels or self._pixels()
        if image is None:
            # Missing Reference is a safe neutral scalar; the caller can expose
            # ``available()`` in diagnostics without breaking project loading.
            return 0.5
        width, height, pixels = image
        x0, y0, x1, y1 = self.sample_bounds or context.bounds
        span_x, span_y = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)
        u = (float(element.x) - x0) / span_x
        v = (float(element.y) - y0) / span_y
        if self.out_of_bounds == "zero" and (u < 0 or u > 1 or v < 0 or v > 1):
            return 0.0
        u, v = min(1.0, max(0.0, u)), min(1.0, max(0.0, v))
        fx, fy = u * (width - 1), v * (height - 1)
        x_left, y_top = int(math.floor(fx)), int(math.floor(fy))
        x_right, y_bottom = min(x_left + 1, width - 1), min(y_top + 1, height - 1)
        tx, ty = fx - x_left, fy - y_top
        row = width
        p00 = pixels[y_top * row + x_left] / 255.0
        p10 = pixels[y_top * row + x_right] / 255.0
        p01 = pixels[y_bottom * row + x_left] / 255.0
        p11 = pixels[y_bottom * row + x_right] / 255.0
        value = (p00 * (1 - tx) + p10 * tx) * (1 - ty) + (p01 * (1 - tx) + p11 * tx) * ty
        value = _unit((value - self.black_point) / max(self.white_point - self.black_point, 1e-9))
        value = _unit((value - 0.5) * self.contrast + 0.5)
        if self.black_is_one:
            value = 1.0 - value
        value = _unit(1.0 - value if self.invert else value)
        return float(value >= self.threshold) if self.sampling_mode == "mask" else value

    def to_dict(self) -> dict:
        return {"id": self.id, "type": "image", "parameters": {
            "image_path": self.image_path, "contrast": self.contrast,
            "black_point": self.black_point, "white_point": self.white_point,
            "invert": self.invert, "out_of_bounds": self.out_of_bounds,
            "sample_bounds": self.sample_bounds, "black_is_one": self.black_is_one,
            "sampling_mode": self.sampling_mode, "threshold": self.threshold}}


@dataclass(frozen=True)
class StripeField:
    """Periodic banded scalar field with an optional soft edge."""

    id: str
    angle: float = 0.0
    period: float = 50.0
    phase: float = 0.0
    duty_cycle: float = 0.5
    smoothness: float = 0.0
    invert: bool = False

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("条纹场 ID 不能为空。")
        for name in ("angle", "period", "phase", "duty_cycle", "smoothness"):
            object.__setattr__(self, name, _finite(getattr(self, name)))
        if self.period <= 0 or not 0 <= self.duty_cycle <= 1 or not 0 <= self.smoothness <= 0.5:
            raise ValueError("条纹场周期、占空比或平滑度参数无效。")
        if not isinstance(self.invert, bool):
            raise ValueError("条纹场反转参数必须为布尔值。")

    def evaluate(self, element: Element, context: FieldContext) -> float:
        del context
        angle = math.radians(self.angle)
        projection = _finite(element.x) * math.cos(angle) + _finite(element.y) * math.sin(angle)
        position = (projection / self.period + self.phase) % 1.0
        duty = self.duty_cycle
        if duty <= 0:
            value = 0.0
        elif duty >= 1:
            value = 1.0
        elif self.smoothness <= 0:
            value = float(position < duty)
        else:
            # Distance to the nearest band boundary, measured on the unit cycle.
            distance = min(position, 1.0 - position, abs(position - duty))
            edge = self.smoothness / 2.0
            if position < duty and distance >= edge:
                value = 1.0
            elif distance >= edge:
                value = 0.0
            else:
                t = distance / max(edge, 1e-9)
                value = t * t * (3.0 - 2.0 * t)
                if position >= duty:
                    value = 1.0 - value
        return _unit(1.0 - value if self.invert else value)

    def to_dict(self) -> dict:
        return {"id": self.id, "type": "stripe", "parameters": {
            "angle": self.angle, "period": self.period, "phase": self.phase,
            "duty_cycle": self.duty_cycle, "smoothness": self.smoothness, "invert": self.invert}}


@dataclass(frozen=True)
class CheckerField:
    """Alternating world-coordinate cells."""

    id: str
    cell_width: float = 20.0
    cell_height: float = 20.0
    angle: float = 0.0
    offset_x: float = 0.0
    offset_y: float = 0.0
    invert: bool = False

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("棋盘场 ID 不能为空。")
        for name in ("cell_width", "cell_height", "angle", "offset_x", "offset_y"):
            object.__setattr__(self, name, _finite(getattr(self, name)))
        if self.cell_width <= 0 or self.cell_height <= 0:
            raise ValueError("棋盘格尺寸必须大于 0。")
        if not isinstance(self.invert, bool):
            raise ValueError("棋盘场反转参数必须为布尔值。")

    def evaluate(self, element: Element, context: FieldContext) -> float:
        del context
        angle = math.radians(-self.angle)
        dx, dy = _finite(element.x) - self.offset_x, _finite(element.y) - self.offset_y
        x = dx * math.cos(angle) - dy * math.sin(angle)
        y = dx * math.sin(angle) + dy * math.cos(angle)
        value = float((math.floor(x / self.cell_width) + math.floor(y / self.cell_height)) % 2 == 0)
        return _unit(1.0 - value if self.invert else value)

    def to_dict(self) -> dict:
        return {"id": self.id, "type": "checker", "parameters": {
            "cell_width": self.cell_width, "cell_height": self.cell_height, "angle": self.angle,
            "offset_x": self.offset_x, "offset_y": self.offset_y, "invert": self.invert}}


@dataclass(frozen=True)
class SpiralField:
    """Polar spiral scalar field normalized against the source bounds."""

    id: str
    center_x: float = 0.0
    center_y: float = 0.0
    turns: float = 3.0
    phase: float = 0.0
    direction: int = 1
    falloff: float = 1.0
    invert: bool = False

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("螺旋场 ID 不能为空。")
        for name in ("center_x", "center_y", "turns", "phase", "falloff"):
            object.__setattr__(self, name, _finite(getattr(self, name)))
        if self.turns < 0 or self.falloff <= 0 or self.direction not in (-1, 1):
            raise ValueError("螺旋场参数无效。")
        if not isinstance(self.invert, bool):
            raise ValueError("螺旋场反转参数必须为布尔值。")

    def evaluate(self, element: Element, context: FieldContext) -> float:
        dx, dy = _finite(element.x) - self.center_x, _finite(element.y) - self.center_y
        diagonal = max(math.hypot(context.bounds[2] - context.bounds[0], context.bounds[3] - context.bounds[1]), 1e-9)
        radial = math.hypot(dx, dy) / diagonal
        angle = math.atan2(dy, dx) / (2.0 * math.pi)
        value = (self.direction * (angle + self.turns * radial) + self.phase) % 1.0
        value = _unit(value ** self.falloff)
        return _unit(1.0 - value if self.invert else value)

    def to_dict(self) -> dict:
        return {"id": self.id, "type": "spiral", "parameters": {
            "center_x": self.center_x, "center_y": self.center_y, "turns": self.turns,
            "phase": self.phase, "direction": self.direction, "falloff": self.falloff,
            "invert": self.invert}}


@dataclass(frozen=True)
class CompositeField:
    """A non-owning scalar-field node that combines two stable field IDs."""

    id: str
    input_a_field_id: str
    input_b_field_id: str
    operator: str = "multiply"
    mix: float = .5

    def __post_init__(self):
        if not all(isinstance(value, str) and value for value in
                   (self.id, self.input_a_field_id, self.input_b_field_id)):
            raise ValueError("组合场及其输入 ID 不能为空。")
        if self.operator not in {"add", "multiply", "min", "max", "blend"}:
            raise ValueError("不支持的组合场运算：%s" % self.operator)
        object.__setattr__(self, "mix", _finite(self.mix))
        if not 0.0 <= self.mix <= 1.0:
            raise ValueError("组合场混合比例必须在 0～1 之间。")

    def to_dict(self) -> dict:
        return {"id": self.id, "type": "composite", "parameters": {
            "input_a_field_id": self.input_a_field_id,
            "input_b_field_id": self.input_b_field_id, "operator": self.operator,
            "mix": self.mix}}


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

    def dependents_of(self, field_id: str) -> tuple[str, ...]:
        """Return direct composite dependents; used by deletion UIs for safety."""
        return tuple(field.id for field in self._fields.values()
                     if isinstance(field, CompositeField)
                     and field_id in (field.input_a_field_id, field.input_b_field_id))

    def remove(self, field_id: str) -> None:
        """Remove an unreferenced field, never leaving a broken composite.

        The registry is deliberately the one place that enforces this rule so
        a future Field UI cannot accidentally duplicate dependency checks.
        """
        self.get(field_id)
        dependents = self.dependents_of(field_id)
        if dependents:
            raise ValueError("无法删除参数场 %s：仍被组合场引用（%s）。" %
                             (field_id, "、".join(dependents)))
        del self._fields[field_id]

    def get(self, field_id: str) -> SharedField:
        if field_id not in self._fields:
            raise ValueError("修饰器引用了不存在的参数场：%s" % field_id)
        return self._fields[field_id]

    def to_list(self) -> list[dict]:
        return [field.to_dict() for field in self._fields.values()]

    def evaluate(self, field_id: str, element: Element, context: FieldContext,
                 trail: tuple[str, ...] = ()) -> float:
        if field_id in trail:
            raise ValueError("检测到组合场循环引用：%s" % " → ".join((*trail, field_id)))
        field = self.get(field_id)
        if not isinstance(field, CompositeField):
            return _unit(field.evaluate(element, context))
        # A project/preset from a newer or manually edited version can lose an
        # input field.  Keep the document usable and make the absent input a
        # neutral scalar instead of crashing Canvas, export or project load.
        # Cycles remain a hard error because silently evaluating them would
        # create an unbounded recursive graph.
        a = (self.evaluate(field.input_a_field_id, element, context, (*trail, field_id))
             if field.input_a_field_id in self._fields else 0.5)
        b = (self.evaluate(field.input_b_field_id, element, context, (*trail, field_id))
             if field.input_b_field_id in self._fields else 0.5)
        if field.operator == "add": value = a + b
        elif field.operator == "multiply": value = a * b
        elif field.operator == "min": value = min(a, b)
        elif field.operator == "max": value = max(a, b)
        else: value = a * (1.0 - field.mix) + b * field.mix
        return _unit(value)

    def validate_dependencies(self) -> None:
        """Fail early for self references and indirect cycles.

        Missing *composite inputs* intentionally remain loadable and evaluate
        neutral (see :meth:`evaluate`).  That is the safe forward-compatible
        behaviour required for presets whose optional source field is absent.
        """
        def visit(identifier: str, trail: tuple[str, ...]) -> None:
            if identifier in trail:
                raise ValueError("检测到组合场循环引用：%s" % " → ".join((*trail, identifier)))
            field = self._fields.get(identifier)
            if not isinstance(field, CompositeField):
                # Missing input IDs are a supported degraded-load case; a
                # normal scalar node has no graph dependencies to inspect.
                return
            visit(field.input_a_field_id, (*trail, identifier))
            visit(field.input_b_field_id, (*trail, identifier))

        for identifier, field in self._fields.items():
            if isinstance(field, CompositeField):
                visit(identifier, ())

    @classmethod
    def from_list(cls, payload: list[dict]) -> "FieldRegistry":
        constructors = {"constant": ConstantField, "linear": LinearField, "ring": RingField,
                        "wave": WaveField, "stripe": StripeField, "checker": CheckerField,
                        "spiral": SpiralField, "image": ImageField, "noise": NoiseField,
                        "composite": CompositeField}
        fields = []
        for raw in payload:
            constructor = constructors.get(raw.get("type"))
            if constructor is None:
                raise ValueError("本 Gate 不支持参数场类型：%s" % raw.get("type"))
            fields.append(constructor(id=raw["id"], **raw.get("parameters", {})))
        registry = cls(fields)
        registry.validate_dependencies()
        return registry


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


@dataclass(frozen=True)
class RotationModifier:
    """Consume a scalar field as a rotation angle in world/degrees."""

    id: str
    field_id: str
    mapping: FieldMapping = FieldMapping(-30.0, 30.0)
    enabled: bool = True

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id or not isinstance(self.field_id, str) or not self.field_id:
            raise ValueError("旋转修饰器及其参数场引用 ID 不能为空。")
        if not isinstance(self.enabled, bool):
            raise ValueError("旋转修饰器启用状态必须为布尔值。")

    def angle(self, value: float) -> float:
        return self.mapping.evaluate(value, neutral=0.0) if self.enabled else 0.0

    def to_dict(self) -> dict:
        return {"id": self.id, "type": "rotation", "field_id": self.field_id,
                "mapping": asdict(self.mapping), "enabled": self.enabled}


@dataclass(frozen=True)
class FieldPositionModifier:
    """Move derived geometry from a reusable scalar field without source edits."""

    id: str
    field_id: str
    offset_x: FieldMapping = FieldMapping(-10.0, 10.0)
    offset_y: FieldMapping = FieldMapping(-10.0, 10.0)
    enabled: bool = True

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id or not isinstance(self.field_id, str) or not self.field_id:
            raise ValueError("位置修饰器及其参数场引用 ID 不能为空。")
        if not isinstance(self.enabled, bool):
            raise ValueError("位置修饰器启用状态必须为布尔值。")

    def displacement(self, value: float) -> tuple[float, float]:
        if not self.enabled:
            return (0.0, 0.0)
        return (self.offset_x.evaluate(value, neutral=0.0),
                self.offset_y.evaluate(value, neutral=0.0))

    def to_dict(self) -> dict:
        return {"id": self.id, "type": "field_position", "field_id": self.field_id,
                "offset_x": asdict(self.offset_x), "offset_y": asdict(self.offset_y),
                "enabled": self.enabled}


@dataclass(frozen=True)
class DensityModifier:
    """Keep or hide derived elements using a scalar field threshold.

    This is deliberately a generic field consumer: NoiseField is one possible
    input, alongside image, wave, ring or a later combined field.
    """

    id: str
    field_id: str
    threshold: float = 0.5
    invert: bool = False
    enabled: bool = True

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id or not isinstance(self.field_id, str) or not self.field_id:
            raise ValueError("密度修饰器及其参数场引用 ID 不能为空。")
        object.__setattr__(self, "threshold", _unit(self.threshold))
        if not isinstance(self.invert, bool) or not isinstance(self.enabled, bool):
            raise ValueError("密度修饰器开关必须为布尔值。")

    def is_visible(self, value: float) -> bool:
        if not self.enabled:
            return True
        visible = _unit(value) >= self.threshold
        return not visible if self.invert else visible

    def to_dict(self) -> dict:
        return {"id": self.id, "type": "density", "field_id": self.field_id,
                "threshold": self.threshold, "invert": self.invert, "enabled": self.enabled}


class SharedFieldEngine:
    def __init__(self, fields: FieldRegistry, modifiers: Iterable[SizeModifier | RotationModifier | FieldPositionModifier | DensityModifier]):
        self.fields = fields
        self.modifiers = tuple(modifiers)
        if len({modifier.id for modifier in self.modifiers}) != len(self.modifiers):
            raise ValueError("修饰器 ID 不能重复。")
        for modifier in self.modifiers:
            self.fields.get(modifier.field_id)
        self.fields.validate_dependencies()

    def evaluate_fields(self, elements: Iterable[Element]) -> dict[str, tuple[float, ...]]:
        source = list(elements)
        context = FieldContext.from_elements(source)
        values = {}
        for modifier in self.modifiers:
            if modifier.enabled and modifier.field_id not in values:
                values[modifier.field_id] = tuple(self.fields.evaluate(modifier.field_id, e, context) for e in source)
        return values

    def apply(self, elements: Iterable[Element]) -> list[Element]:
        source = list(elements)
        values = self.evaluate_fields(source)
        result = deepcopy(source)
        for modifier in self.modifiers:
            if not modifier.enabled: continue
            for element, value in zip(result, values[modifier.field_id]):
                if isinstance(modifier, SizeModifier):
                    scale = modifier.scale(value)
                    element.width = max(0.01, element.width * scale)
                    element.height = max(0.01, element.height * scale)
                elif isinstance(modifier, RotationModifier):
                    element.rotation += modifier.angle(value)
                elif isinstance(modifier, FieldPositionModifier):
                    dx, dy = modifier.displacement(value)
                    element.x += dx
                    element.y += dy
                elif isinstance(modifier, DensityModifier):
                    element.visible = element.visible and modifier.is_visible(value)
        return result

    @property
    def has_size_modifier(self) -> bool:
        return any(isinstance(modifier, SizeModifier) for modifier in self.modifiers)

    @property
    def has_rotation_modifier(self) -> bool:
        return any(isinstance(modifier, RotationModifier) for modifier in self.modifiers)

    def to_dict(self) -> dict:
        return {"version": 1, "fields": self.fields.to_list(),
                "modifiers": [modifier.to_dict() for modifier in self.modifiers]}

    @classmethod
    def from_dict(cls, payload: dict) -> "SharedFieldEngine":
        if payload.get("version", 1) != 1:
            raise ValueError("不支持的 SharedFieldEngine 版本。")
        modifiers = []
        for raw in payload.get("modifiers", []):
            if not isinstance(raw, dict) or not raw.get("id") or not raw.get("field_id"):
                raise ValueError("SharedFieldEngine 修饰器必须包含非空 id 和 field_id。")
            mapping = FieldMapping(**raw.get("mapping", {}))
            if raw.get("type") == "size":
                modifiers.append(SizeModifier(raw["id"], raw["field_id"], mapping, raw.get("enabled", True)))
            elif raw.get("type") == "rotation":
                modifiers.append(RotationModifier(raw["id"], raw["field_id"], mapping, raw.get("enabled", True)))
            elif raw.get("type") == "field_position":
                modifiers.append(FieldPositionModifier(
                    raw["id"], raw["field_id"], FieldMapping(**raw.get("offset_x", {})),
                    FieldMapping(**raw.get("offset_y", {})), raw.get("enabled", True)))
            elif raw.get("type") == "density":
                modifiers.append(DensityModifier(raw["id"], raw["field_id"], raw.get("threshold", .5),
                                                 raw.get("invert", False), raw.get("enabled", True)))
            else:
                raise ValueError("不支持的 SharedFieldEngine 修饰器类型：%s" % raw.get("type"))
        return cls(FieldRegistry.from_list(payload.get("fields", [])), modifiers)
