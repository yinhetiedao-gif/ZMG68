"""First deliberately small parametric layer: a grid plus a size gradient.

This module is independent of the UI.  It produces the same real Foundation
``Element`` instances used by Free Element Mode, so SVG export, save/load and
direct editing keep a single source of truth.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
import math
import re
from typing import Dict, Iterable, Optional, Sequence

from ppg.foundation.models import (
    CircleElement,
    EllipseElement,
    Element,
    FilledRegionElement,
    PathElement,
    RectElement,
)


PARAMETRIC_METADATA_KEY = "xiaomang_pattern_lab.parametric"


class PatternMode(str, Enum):
    FREE = "free"
    GRID = "grid"
    RADIAL = "radial"
    ALONG_CURVE = "along_curve"
    FREE_PARAMETRIC = "free_parametric"


class SizeGradientMode(str, Enum):
    NONE = "none"
    HORIZONTAL = "horizontal_x"
    VERTICAL = "vertical_y"
    CENTER_TO_EDGE = "center_to_edge"
    EDGE_TO_CENTER = "edge_to_center"
    RADIAL = "radial"
    ELLIPTICAL_RADIAL = "elliptical_radial"


class MaskMode(str, Enum):
    """The deliberately small, non-destructive V1 mask vocabulary."""

    NONE = "none"
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    IMPORTED_PATH = "imported_path"


@dataclass(frozen=True)
class ElementAnchor:
    """A shape-independent position sample used by the Grid analyser.

    A lattice is a relationship between centroids, not a special kind of
    circle.  Keeping this record separate from an Element means size-gradient
    analysis and prototype recovery never decide whether the positions form a
    Grid.  All values use the PatternDocument world coordinate system (mm in
    the current Pattern Lab UI).
    """

    element_id: str
    centroid_x: float
    centroid_y: float
    bbox_width: float
    bbox_height: float
    area: float
    rotation: float
    source_type: str

    @property
    def aspect_ratio(self) -> float:
        return self.bbox_width / max(self.bbox_height, 1e-9)


@dataclass
class ElementPrototype:
    """Serializable template for a Grid cell.

    This intentionally stores only a single *representative* editable shape.
    Grid controls change placement and dimensions; they do not reinterpret a
    star, diamond, or imported closed SVG path as a circle.  Unknown SVG path
    data is retained verbatim as ``CustomPathPrototype``.
    """

    kind: str = "circle"
    style: dict = field(default_factory=lambda: {"fill": "#000000", "stroke": "none"})
    metadata: dict = field(default_factory=dict)
    rx_ratio: float = 0.0
    ry_ratio: float = 0.0
    path_data: str = ""
    source_transform: str = ""
    base_x: float = 0.0
    base_y: float = 0.0
    base_width: float = 1.0
    base_height: float = 1.0
    filled: bool = False
    intrinsic_rotation: float = 0.0

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "style": deepcopy(self.style),
            "metadata": deepcopy(self.metadata),
            "rx_ratio": self.rx_ratio,
            "ry_ratio": self.ry_ratio,
            "path_data": self.path_data,
            "source_transform": self.source_transform,
            "base_x": self.base_x,
            "base_y": self.base_y,
            "base_width": self.base_width,
            "base_height": self.base_height,
            "filled": self.filled,
            "intrinsic_rotation": self.intrinsic_rotation,
        }

    @classmethod
    def from_dict(cls, value: dict | None) -> "ElementPrototype":
        value = value or {}
        kind = str(value.get("kind", "circle"))
        prototype_cls = {
            "circle": CirclePrototype,
            "ellipse": EllipsePrototype,
            "rect": RectPrototype,
            "polygon": PolygonPrototype,
            "custom_path": CustomPathPrototype,
        }.get(kind, CustomPathPrototype)
        return prototype_cls(
            kind=kind,
            style=deepcopy(value.get("style") or {"fill": "#000000", "stroke": "none"}),
            metadata=deepcopy(value.get("metadata") or {}),
            rx_ratio=max(0.0, float(value.get("rx_ratio", 0.0))),
            ry_ratio=max(0.0, float(value.get("ry_ratio", 0.0))),
            path_data=str(value.get("path_data", "")),
            source_transform=str(value.get("source_transform", "")),
            base_x=float(value.get("base_x", 0.0)),
            base_y=float(value.get("base_y", 0.0)),
            base_width=max(0.01, float(value.get("base_width", 1.0))),
            base_height=max(0.01, float(value.get("base_height", 1.0))),
            filled=bool(value.get("filled", False)),
            intrinsic_rotation=float(value.get("intrinsic_rotation", 0.0)),
        )

    @classmethod
    def from_element(cls, element: Element) -> "ElementPrototype":
        style = deepcopy(element.style) or {"fill": "#000000", "stroke": "none"}
        metadata = deepcopy(element.metadata)
        if isinstance(element, CircleElement):
            return CirclePrototype(kind="circle", style=style, metadata=metadata, intrinsic_rotation=element.rotation)
        if isinstance(element, EllipseElement):
            return EllipsePrototype(kind="ellipse", style=style, metadata=metadata, intrinsic_rotation=element.rotation)
        if isinstance(element, RectElement):
            return RectPrototype(
                kind="rect", style=style, metadata=metadata,
                rx_ratio=element.rx / max(element.width, 0.01),
                ry_ratio=element.ry / max(element.height, 0.01),
                intrinsic_rotation=element.rotation,
            )
        if isinstance(element, PathElement):
            # Polygon is deliberately a retained filled path until a future
            # polygon-native Element model exists.  This is safer than
            # reconstructing coordinates and changing the user's SVG outline.
            closed = "z" in element.path_data.lower()
            kind = "polygon" if closed and str(element.metadata.get("primitive_hint", "")).lower() == "polygon" else "custom_path"
            prototype_cls = PolygonPrototype if kind == "polygon" else CustomPathPrototype
            return prototype_cls(
                kind=kind, style=style, metadata=metadata, path_data=element.path_data,
                source_transform=element.source_transform, base_x=element.base_x,
                base_y=element.base_y, base_width=max(0.01, element.base_width),
                base_height=max(0.01, element.base_height),
                filled=isinstance(element, FilledRegionElement) or str(style.get("fill", "")).lower() not in {"", "none", "transparent"},
                intrinsic_rotation=element.rotation,
            )
        # Foundation currently has no other Element implementations, but keep
        # the fallback explicit so a future primitive never silently becomes a
        # dot during parameterisation.
        return CustomPathPrototype(kind="custom_path", style=style, metadata=metadata)

    def instantiate(self, *, element_id: str, x: float, y: float, width: float, height: float,
                    rotation: float, visible: bool) -> Element:
        style = deepcopy(self.style) or {"fill": "#000000", "stroke": "none"}
        metadata = deepcopy(self.metadata)
        metadata["grid_prototype_kind"] = self.kind
        common = dict(id=element_id, x=x, y=y, width=width, height=height,
                      rotation=rotation + self.intrinsic_rotation, visible=visible, style=style, metadata=metadata)
        if self.kind == "circle":
            # CirclePrototype preserves a circle even if an Inspector requests
            # asymmetric values; Grid normalisation prevents that by locking
            # the cell aspect in the corresponding model.
            size = min(width, height)
            common.update(width=size, height=size)
            return CircleElement(**common)
        if self.kind == "ellipse":
            return EllipseElement(**common)
        if self.kind == "rect":
            return RectElement(
                **common,
                rx=max(0.0, self.rx_ratio * width),
                ry=max(0.0, self.ry_ratio * height),
            )
        path_common = dict(
            **common,
            path_data=self.path_data,
            source_transform=self.source_transform,
            base_x=self.base_x,
            base_y=self.base_y,
            base_width=max(0.01, self.base_width),
            base_height=max(0.01, self.base_height),
        )
        if self.filled:
            path_common["style"] = {**style, "fill": style.get("fill") or "#000000", "stroke": "none"}
            return FilledRegionElement(**path_common)
        return PathElement(**path_common)


@dataclass
class CirclePrototype(ElementPrototype):
    kind: str = "circle"


@dataclass
class EllipsePrototype(ElementPrototype):
    kind: str = "ellipse"


@dataclass
class RectPrototype(ElementPrototype):
    kind: str = "rect"


@dataclass
class PolygonPrototype(ElementPrototype):
    kind: str = "polygon"
    filled: bool = True


@dataclass
class CustomPathPrototype(ElementPrototype):
    kind: str = "custom_path"


@dataclass
class SizeGradientModifier:
    mode: SizeGradientMode = SizeGradientMode.NONE
    min_size: float = 4.0
    max_size: float = 10.0
    center_x: float = 0.0
    center_y: float = 0.0
    strength: float = 1.0
    radius_x: float = 50.0
    radius_y: float = 50.0
    falloff: float = 1.0

    def to_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "min_size": self.min_size,
            "max_size": self.max_size,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "strength": self.strength,
            "radius_x": self.radius_x,
            "radius_y": self.radius_y,
            "falloff": self.falloff,
        }

    @classmethod
    def from_dict(cls, value: dict | None) -> "SizeGradientModifier":
        value = value or {}
        try:
            mode = SizeGradientMode(value.get("mode", SizeGradientMode.NONE.value))
        except ValueError:
            mode = SizeGradientMode.NONE
        return cls(
            mode=mode,
            min_size=float(value.get("min_size", 4.0)),
            max_size=float(value.get("max_size", 10.0)),
            center_x=float(value.get("center_x", 0.0)),
            center_y=float(value.get("center_y", 0.0)),
            strength=float(value.get("strength", 1.0)),
            radius_x=max(0.01, float(value.get("radius_x", 50.0))),
            radius_y=max(0.01, float(value.get("radius_y", 50.0))),
            falloff=max(0.05, float(value.get("falloff", 1.0))),
        )


@dataclass
class MaskModifier:
    """Decide which generated cells are visible without altering the Grid.

    Rectangle and circle controls are expressed in PatternDocument world units
    (currently mm).  ``path_points`` is a closed polygon extracted from an
    imported filled path; it intentionally stores geometry rather than a file
    reference, so Save / Load has no hidden external dependency.
    """

    mode: MaskMode = MaskMode.NONE
    enabled: bool = False
    invert: bool = False
    center_x: float = 0.0
    center_y: float = 0.0
    width: float = 100.0
    height: float = 100.0
    radius: float = 50.0
    path_points: list[tuple[float, float]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "enabled": self.enabled,
            "invert": self.invert,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "width": self.width,
            "height": self.height,
            "radius": self.radius,
            "path_points": [[x, y] for x, y in self.path_points],
        }

    @classmethod
    def from_dict(cls, value: dict | None) -> "MaskModifier":
        value = value or {}
        try:
            mode = MaskMode(value.get("mode", MaskMode.NONE.value))
        except ValueError:
            mode = MaskMode.NONE
        points: list[tuple[float, float]] = []
        for item in value.get("path_points") or []:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                points.append((float(item[0]), float(item[1])))
        return cls(
            mode=mode,
            enabled=bool(value.get("enabled", False)),
            invert=bool(value.get("invert", False)),
            center_x=float(value.get("center_x", 0.0)),
            center_y=float(value.get("center_y", 0.0)),
            width=max(0.01, float(value.get("width", 100.0))),
            height=max(0.01, float(value.get("height", 100.0))),
            radius=max(0.01, float(value.get("radius", 50.0))),
            path_points=points,
        )

    def contains(self, x: float, y: float) -> bool:
        if not self.enabled or self.mode is MaskMode.NONE:
            return True
        if self.mode is MaskMode.RECTANGLE:
            inside = abs(x - self.center_x) <= self.width / 2.0 and abs(y - self.center_y) <= self.height / 2.0
        elif self.mode is MaskMode.CIRCLE:
            inside = math.hypot(x - self.center_x, y - self.center_y) <= self.radius
        elif self.mode is MaskMode.IMPORTED_PATH:
            inside = self._point_in_polygon(x, y, self.path_points)
        else:
            inside = True
        return not inside if self.invert else inside

    @staticmethod
    def _point_in_polygon(x: float, y: float, points: Sequence[tuple[float, float]]) -> bool:
        if len(points) < 3:
            return False
        inside = False
        previous = len(points) - 1
        for index, (current_x, current_y) in enumerate(points):
            previous_x, previous_y = points[previous]
            if (current_y > y) != (previous_y > y):
                crossing = (previous_x - current_x) * (y - current_y) / ((previous_y - current_y) or 1e-12) + current_x
                if x < crossing:
                    inside = not inside
            previous = index
        return inside


@dataclass
class LocalOverride:
    offset_x: float = 0.0
    offset_y: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    rotation_offset: float = 0.0
    visible: Optional[bool] = None

    def to_dict(self) -> dict:
        return {
            "offset_x": self.offset_x,
            "offset_y": self.offset_y,
            "scale_x": self.scale_x,
            "scale_y": self.scale_y,
            "rotation_offset": self.rotation_offset,
            "visible": self.visible,
        }

    @classmethod
    def from_dict(cls, value: dict | None) -> "LocalOverride":
        value = value or {}
        visible = value.get("visible")
        return cls(
            offset_x=float(value.get("offset_x", 0.0)),
            offset_y=float(value.get("offset_y", 0.0)),
            scale_x=max(0.01, float(value.get("scale_x", 1.0))),
            scale_y=max(0.01, float(value.get("scale_y", 1.0))),
            rotation_offset=float(value.get("rotation_offset", 0.0)),
            visible=None if visible is None else bool(visible),
        )


@dataclass
class GridParametricModel:
    """General 2D lattice placement plus an independent cell prototype.

    A V1/V2 project has no explicit vectors, so it remains an orthogonal Grid
    derived from ``spacing_x`` / ``spacing_y`` / ``rotation``.  V3 stores an
    optional pair of true basis vectors.  This permits any stable lattice:
    horizontal, rotated, skewed, or non-orthogonal—without changing the
    semantics of legacy project files.
    """

    rows: int = 12
    columns: int = 12
    spacing_x: float = 12.0
    spacing_y: float = 12.0
    element_width: float = 6.0
    element_height: float = 6.0
    rotation: float = 0.0
    offset_x: float = 0.0
    offset_y: float = 0.0
    lock_aspect: bool = True
    basis_u_vector: Optional[tuple[float, float]] = None
    basis_v_vector: Optional[tuple[float, float]] = None
    prototype: ElementPrototype = field(default_factory=CirclePrototype)
    size_gradient: SizeGradientModifier = field(default_factory=SizeGradientModifier)
    mask: MaskModifier = field(default_factory=MaskModifier)
    local_overrides: Dict[str, LocalOverride] = field(default_factory=dict)

    def normalized(self) -> "GridParametricModel":
        self.rows = max(1, int(self.rows))
        self.columns = max(1, int(self.columns))
        self.spacing_x = max(0.01, float(self.spacing_x))
        self.spacing_y = max(0.01, float(self.spacing_y))
        if self.basis_u_vector is not None or self.basis_v_vector is not None:
            if self.basis_u_vector is None or self.basis_v_vector is None:
                raise ValueError("二维格子必须同时具有 Basis U 与 Basis V。")
            ux, uy = float(self.basis_u_vector[0]), float(self.basis_u_vector[1])
            vx, vy = float(self.basis_v_vector[0]), float(self.basis_v_vector[1])
            determinant = ux * vy - uy * vx
            if abs(determinant) < 1e-6:
                raise ValueError("Basis U 与 Basis V 不能共线。")
            self.basis_u_vector, self.basis_v_vector = (ux, uy), (vx, vy)
            self.spacing_x, self.spacing_y = max(0.01, math.hypot(ux, uy)), max(0.01, math.hypot(vx, vy))
            self.rotation = math.degrees(math.atan2(uy, ux))
        self.element_width = max(0.01, float(self.element_width))
        # V1 used this flag to mean "circle".  In V2 it is generic cell
        # aspect locking.  A CirclePrototype always needs it, while imported
        # paths/rectangles may opt into independent dimensions.
        if self.prototype.kind == "circle" or self.lock_aspect:
            self.element_height = self.element_width
        else:
            self.element_height = max(0.01, float(self.element_height))
        self.size_gradient.min_size = max(0.01, self.size_gradient.min_size)
        self.size_gradient.max_size = max(0.01, self.size_gradient.max_size)
        self.size_gradient.strength = min(1.0, max(0.0, self.size_gradient.strength))
        self.size_gradient.radius_x = max(0.01, float(self.size_gradient.radius_x))
        self.size_gradient.radius_y = max(0.01, float(self.size_gradient.radius_y))
        self.size_gradient.falloff = max(0.05, float(self.size_gradient.falloff))
        self.mask.width = max(0.01, float(self.mask.width))
        self.mask.height = max(0.01, float(self.mask.height))
        self.mask.radius = max(0.01, float(self.mask.radius))
        return self

    @property
    def basis_u(self) -> tuple[float, float]:
        if self.basis_u_vector is not None:
            return self.basis_u_vector
        angle = math.radians(self.rotation)
        return self.spacing_x * math.cos(angle), self.spacing_x * math.sin(angle)

    @property
    def basis_v(self) -> tuple[float, float]:
        if self.basis_v_vector is not None:
            return self.basis_v_vector
        angle = math.radians(self.rotation)
        return -self.spacing_y * math.sin(angle), self.spacing_y * math.cos(angle)

    @property
    def basis_angle_u(self) -> float:
        u = self.basis_u
        return math.degrees(math.atan2(u[1], u[0]))

    @property
    def basis_angle_v(self) -> float:
        v = self.basis_v
        return math.degrees(math.atan2(v[1], v[0]))

    def set_basis_vectors(self, u: tuple[float, float], v: tuple[float, float]) -> "GridParametricModel":
        """Set a non-orthogonal lattice explicitly and keep display fields synced."""

        self.basis_u_vector = (float(u[0]), float(u[1]))
        self.basis_v_vector = (float(v[0]), float(v[1]))
        return self.normalized()

    def set_rotation(self, rotation: float) -> "GridParametricModel":
        """Rotate both bases together, preserving any skew angle and spacing."""

        old = self.basis_angle_u
        delta = math.radians(float(rotation) - old)
        cosine, sine = math.cos(delta), math.sin(delta)
        def rotate(vector: tuple[float, float]) -> tuple[float, float]:
            return vector[0] * cosine - vector[1] * sine, vector[0] * sine + vector[1] * cosine
        self.basis_u_vector = rotate(self.basis_u)
        self.basis_v_vector = rotate(self.basis_v)
        return self.normalized()

    @staticmethod
    def element_id(row: int, column: int) -> str:
        return "grid:r{}:c{}".format(row, column)

    @staticmethod
    def canonical_element_id(element_id: str) -> str:
        """Read V1's stable IDs and migrate the previous preview convention."""

        legacy = re.fullmatch(r"grid-r(\d+)-c(\d+)", str(element_id))
        if legacy:
            return GridParametricModel.element_id(int(legacy.group(1)), int(legacy.group(2)))
        return str(element_id)

    def _gradient_factor(self, row: int, column: int, local_x: float, local_y: float,
                         world_x: float, world_y: float) -> float:
        modifier = self.size_gradient
        if modifier.mode == SizeGradientMode.NONE:
            return -1.0
        if modifier.mode == SizeGradientMode.HORIZONTAL:
            raw = column / max(1, self.columns - 1)
        elif modifier.mode == SizeGradientMode.VERTICAL:
            raw = row / max(1, self.rows - 1)
        elif modifier.mode in (SizeGradientMode.CENTER_TO_EDGE, SizeGradientMode.EDGE_TO_CENTER):
            center_x = modifier.center_x
            center_y = modifier.center_y
            # Legacy center-to-edge operates in lattice-local coordinates;
            # local_x/local_y remain valid even when the world lattice is
            # skewed.  New RADIAL modes below use document world coordinates.
            max_x = max(abs(-((self.columns - 1) * self.spacing_x) / 2.0 - center_x), abs(((self.columns - 1) * self.spacing_x) / 2.0 - center_x), 0.01)
            max_y = max(abs(-((self.rows - 1) * self.spacing_y) / 2.0 - center_y), abs(((self.rows - 1) * self.spacing_y) / 2.0 - center_y), 0.01)
            raw = min(1.0, math.hypot((local_x - center_x) / max_x, (local_y - center_y) / max_y))
            if modifier.mode == SizeGradientMode.EDGE_TO_CENTER:
                raw = 1.0 - raw
        elif modifier.mode == SizeGradientMode.RADIAL:
            raw = min(1.0, math.hypot(world_x - modifier.center_x, world_y - modifier.center_y) / modifier.radius_x)
            raw = raw ** modifier.falloff
        else:  # ELLIPTICAL_RADIAL
            raw = min(1.0, math.hypot((world_x - modifier.center_x) / modifier.radius_x, (world_y - modifier.center_y) / modifier.radius_y))
            raw = raw ** modifier.falloff
        # Strength blends the modifier back into the base grid size.
        return (1.0 - modifier.strength) * 0.5 + modifier.strength * raw

    def _element_size(self, row: int, column: int, local_x: float, local_y: float,
                      world_x: float, world_y: float) -> tuple[float, float]:
        factor = self._gradient_factor(row, column, local_x, local_y, world_x, world_y)
        if factor < 0.0:
            return self.element_width, self.element_height
        modifier = self.size_gradient
        size = modifier.min_size + (modifier.max_size - modifier.min_size) * factor
        if self.lock_aspect:
            return size, size
        ratio = self.element_height / max(self.element_width, 0.01)
        return size, max(0.01, size * ratio)

    def generate(self, *, include_overrides: bool = True) -> list[Element]:
        self.normalized()
        basis_u, basis_v = self.basis_u, self.basis_v
        out: list[Element] = []
        for row in range(self.rows):
            row_factor = row - (self.rows - 1) / 2.0
            local_y = row_factor * self.spacing_y
            for column in range(self.columns):
                column_factor = column - (self.columns - 1) / 2.0
                local_x = column_factor * self.spacing_x
                x = self.offset_x + column_factor * basis_u[0] + row_factor * basis_v[0]
                y = self.offset_y + column_factor * basis_u[1] + row_factor * basis_v[1]
                width, height = self._element_size(row, column, local_x, local_y, x, y)
                element_id = self.element_id(row, column)
                override = self.local_overrides.get(element_id) if include_overrides else None
                if override is not None:
                    x += override.offset_x
                    y += override.offset_y
                    width *= override.scale_x
                    height *= override.scale_y
                # Modifiers run before Local Overrides.  A deliberate local
                # visibility edit is therefore allowed to reveal/hide one cell
                # after the global mask has been evaluated.
                visible = self.mask.contains(x, y)
                if override is not None and override.visible is not None:
                    visible = override.visible
                out.append(self.prototype.instantiate(
                    element_id=element_id,
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    rotation=self.basis_angle_u + (override.rotation_offset if override else 0.0),
                    visible=visible,
                ))
        return out

    def base_element(self, element_id: str) -> Optional[Element]:
        element_id = self.canonical_element_id(element_id)
        for element in self.generate(include_overrides=False):
            if element.id == element_id:
                return element
        return None

    def to_dict(self) -> dict:
        self.normalized()
        return {
            "rows": self.rows,
            "columns": self.columns,
            "spacing_x": self.spacing_x,
            "spacing_y": self.spacing_y,
            # Derived, human-readable lattice bases.  Rotation and spacing
            # remain the source of truth so legacy V1 project files stay
            # compatible and cannot contain contradictory basis values.
            "basis_u": list(self.basis_u),
            "basis_v": list(self.basis_v),
            "basis_u_vector": list(self.basis_u) if self.basis_u_vector is not None else None,
            "basis_v_vector": list(self.basis_v) if self.basis_v_vector is not None else None,
            "element_width": self.element_width,
            "element_height": self.element_height,
            "rotation": self.rotation,
            "offset_x": self.offset_x,
            "offset_y": self.offset_y,
            "lock_aspect": self.lock_aspect,
            "prototype": self.prototype.to_dict(),
            "size_gradient": self.size_gradient.to_dict(),
            "mask": self.mask.to_dict(),
            "local_overrides": {key: item.to_dict() for key, item in self.local_overrides.items()},
        }

    @classmethod
    def from_dict(cls, value: dict | None) -> "GridParametricModel":
        value = value or {}
        def vector(key: str) -> Optional[tuple[float, float]]:
            raw = value.get(key)
            if isinstance(raw, (list, tuple)) and len(raw) == 2:
                return float(raw[0]), float(raw[1])
            return None
        # ``basis_u``/``basis_v`` were derived display fields in V2.  Only
        # explicit V3 ``*_vector`` values change the legacy orthogonal model.
        model = cls(
            rows=int(value.get("rows", 12)),
            columns=int(value.get("columns", 12)),
            spacing_x=float(value.get("spacing_x", 12.0)),
            spacing_y=float(value.get("spacing_y", 12.0)),
            element_width=float(value.get("element_width", 6.0)),
            element_height=float(value.get("element_height", 6.0)),
            rotation=float(value.get("rotation", 0.0)),
            offset_x=float(value.get("offset_x", 0.0)),
            offset_y=float(value.get("offset_y", 0.0)),
            lock_aspect=bool(value.get("lock_aspect", True)),
            basis_u_vector=vector("basis_u_vector"),
            basis_v_vector=vector("basis_v_vector"),
            prototype=ElementPrototype.from_dict(value.get("prototype")),
            size_gradient=SizeGradientModifier.from_dict(value.get("size_gradient")),
            mask=MaskModifier.from_dict(value.get("mask")),
        )
        model.local_overrides = {
            cls.canonical_element_id(key): LocalOverride.from_dict(item)
            for key, item in (value.get("local_overrides") or {}).items()
        }
        return model.normalized()


def infer_regular_grid(elements: Iterable[Element], *, threshold: float = 0.82):
    """Compatibility facade for the independent document-only GridAnalyzer.

    New code should use :class:`pattern_analyzer.PatternAnalyzer`; this function
    stays so existing callers do not acquire fixture-specific branching.
    """

    from .pattern_analyzer import GridAnalyzer

    return GridAnalyzer(threshold=threshold).analyze(elements)
