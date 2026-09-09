"""The third-party-neutral PatternDocument model used by FOUNDATION 0."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Type
import copy
import math
import uuid


DOCUMENT_SCHEMA_VERSION = 1


@dataclass
class Canvas:
    """Canvas dimensions in SVG user units, with optional millimetre mapping."""

    width: float
    height: float
    unit: str = "svg_user_unit"
    mm_per_unit: Optional[float] = None
    origin_x: float = 0.0
    origin_y: float = 0.0

    def validate(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Canvas 宽高必须大于 0。")
        if self.mm_per_unit is not None and self.mm_per_unit <= 0:
            raise ValueError("mm_per_unit 必须大于 0。")

    def value_in_mm(self, value: float) -> float:
        if self.mm_per_unit is None:
            raise ValueError("当前文档没有毫米映射。")
        return float(value) * self.mm_per_unit


@dataclass
class Reference:
    """The source raster is metadata only; it is never geometry."""

    source_path: str
    visible: bool = False
    preprocessing: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Transform:
    """A normalized transform record mirrored from an element's editable state."""

    element_id: str
    x: float
    y: float
    rotation: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0


@dataclass
class Group:
    id: str
    name: str = ""
    element_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Element:
    """Base element. x/y always identify the element's visual centre."""

    id: str
    type: str
    x: float
    y: float
    width: float
    height: float
    rotation: float = 0.0
    visible: bool = True
    style: Dict[str, Any] = field(default_factory=dict)
    group_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.id:
            raise ValueError("Element id 不能为空。")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Element 尺寸必须大于 0：%s" % self.id)


@dataclass
class CircleElement(Element):
    type: str = field(default="circle", init=False)


@dataclass
class EllipseElement(Element):
    type: str = field(default="ellipse", init=False)


@dataclass
class RectElement(Element):
    rx: float = 0.0
    ry: float = 0.0
    type: str = field(default="rect", init=False)


@dataclass
class PathElement(Element):
    path_data: str = ""
    source_transform: str = ""
    base_x: float = 0.0
    base_y: float = 0.0
    base_width: float = 1.0
    base_height: float = 1.0
    type: str = field(default="path", init=False)

    def validate(self) -> None:
        super().validate()
        if not self.path_data:
            raise ValueError("PathElement 缺少 path_data：%s" % self.id)


@dataclass
class FilledRegionElement(PathElement):
    """A closed, filled SVG path preserved from a raster reference.

    Unlike :class:`PathElement`, this explicitly represents visible material
    rather than an abstract contour.  It is the loss-minimising primitive used
    by Faithful Mapping: raster black pixels become an independently editable
    closed region without being forced through circle/line semantic recovery.
    """

    type: str = field(default="filled_region", init=False)

    def validate(self) -> None:
        super().validate()
        fill = str(self.style.get("fill", "#000000")).strip().lower()
        if fill in {"", "none", "transparent"}:
            raise ValueError("FilledRegionElement 必须有可见 fill：%s" % self.id)


ELEMENT_TYPES: Dict[str, Type[Element]] = {
    "circle": CircleElement,
    "ellipse": EllipseElement,
    "rect": RectElement,
    "path": PathElement,
    "filled_region": FilledRegionElement,
}


@dataclass
class PatternDocument:
    """The only FOUNDATION 0 document model.

    Element geometry is independent from the Reference layer. `transforms` is
    explicitly persisted so future UI/manufacturing systems can consume a
    stable transform channel without inferring it from SVG text.
    """

    canvas: Canvas
    reference: Reference
    elements: List[Element] = field(default_factory=list)
    groups: List[Group] = field(default_factory=list)
    transforms: Dict[str, Transform] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    schema_version: int = DOCUMENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        self.canvas.validate()
        self._sync_transforms()
        self.validate()

    def validate(self) -> None:
        self.canvas.validate()
        ids = [element.id for element in self.elements]
        if len(ids) != len(set(ids)):
            raise ValueError("PatternDocument 中存在重复 Element id。")
        for element in self.elements:
            element.validate()
        known = set(ids)
        for group in self.groups:
            if not group.id:
                raise ValueError("Group id 不能为空。")
            unknown = set(group.element_ids) - known
            if unknown:
                raise ValueError("Group 引用了不存在的 Element：%s" % sorted(unknown))

    def _sync_transforms(self) -> None:
        active = {element.id for element in self.elements}
        self.transforms = {key: value for key, value in self.transforms.items() if key in active}
        for element in self.elements:
            current = self.transforms.get(element.id)
            scale_x = current.scale_x if current else 1.0
            scale_y = current.scale_y if current else 1.0
            self.transforms[element.id] = Transform(element.id, element.x, element.y, element.rotation, scale_x, scale_y)

    def element(self, element_id: str) -> Element:
        for element in self.elements:
            if element.id == element_id:
                return element
        raise KeyError("找不到 Element：%s" % element_id)

    def add_element(self, element: Element) -> Element:
        if any(existing.id == element.id for existing in self.elements):
            raise ValueError("Element id 已存在：%s" % element.id)
        element.validate()
        self.elements.append(element)
        self._sync_transforms()
        return element

    def move_element(self, element_id: str, dx: float, dy: float) -> Element:
        element = self.element(element_id)
        element.x += float(dx)
        element.y += float(dy)
        self._sync_transforms()
        return element

    def resize_element(self, element_id: str, width: float, height: Optional[float] = None) -> Element:
        element = self.element(element_id)
        target_width = float(width)
        target_height = float(height if height is not None else width)
        # SVG circles cannot represent non-uniform sizing.  Preserve the user's
        # requested editable geometry by promoting it to an ellipse rather than
        # silently discarding the requested height in the SVG exporter.
        if isinstance(element, CircleElement) and not math.isclose(target_width, target_height, rel_tol=1e-9, abs_tol=1e-9):
            replacement = EllipseElement(
                id=element.id, x=element.x, y=element.y,
                width=target_width, height=target_height, rotation=element.rotation,
                visible=element.visible, style=copy.deepcopy(element.style),
                group_id=element.group_id, metadata=copy.deepcopy(element.metadata),
            )
            index = self.elements.index(element)
            self.elements[index] = replacement
            element = replacement
        else:
            element.width = target_width
            element.height = target_height
        element.validate()
        self._sync_transforms()
        return element

    def rotate_element(self, element_id: str, rotation: float) -> Element:
        element = self.element(element_id)
        element.rotation = float(rotation)
        self._sync_transforms()
        return element

    def delete_element(self, element_id: str) -> Element:
        element = self.element(element_id)
        self.elements = [candidate for candidate in self.elements if candidate.id != element_id]
        for group in self.groups:
            group.element_ids = [candidate for candidate in group.element_ids if candidate != element_id]
        self._sync_transforms()
        return element

    def duplicate_element(self, element_id: str, dx: float = 4.0, dy: float = 4.0) -> Element:
        source = self.element(element_id)
        duplicate = copy.deepcopy(source)
        duplicate.id = self._new_element_id(source.id + "-copy")
        duplicate.x += float(dx)
        duplicate.y += float(dy)
        self.add_element(duplicate)
        if duplicate.group_id:
            for group in self.groups:
                if group.id == duplicate.group_id:
                    group.element_ids.append(duplicate.id)
        return duplicate

    def boolean_union(self, element_ids: Iterable[str]) -> FilledRegionElement:
        """Combine material Elements into one editable compound filled region."""
        identifiers = list(dict.fromkeys(element_ids))
        if len(identifiers) < 2:
            raise ValueError("布尔并集至少需要两个 Element。")
        return self._boolean_compose(identifiers[0], identifiers[1:], operation="union")

    def boolean_difference(self, base_id: str, subtract_ids: Iterable[str]) -> FilledRegionElement:
        """Create a closed filled region using SVG's even-odd difference rule."""
        cutters = [identifier for identifier in dict.fromkeys(subtract_ids) if identifier != base_id]
        if not cutters:
            raise ValueError("布尔差集需要主区域以外的至少一个 Element。")
        return self._boolean_compose(base_id, cutters, operation="difference")

    def _boolean_compose(self, base_id: str, other_ids: Iterable[str], *, operation: str) -> FilledRegionElement:
        from .region_geometry import bounds_of_polygons, element_polygons, path_data_from_polygons

        source_ids = [base_id] + list(other_ids)
        sources = [self.element(identifier) for identifier in source_ids]
        polygons = []
        for source in sources:
            source_polygons = element_polygons(source)
            if not source_polygons:
                raise ValueError("%s 不是可进行保真布尔运算的实心几何。" % source.id)
            polygons.extend(source_polygons)
        xmin, ymin, xmax, ymax = bounds_of_polygons(polygons)
        identifier = self._new_element_id("region-" + operation)
        shared_group = sources[0].group_id if all(source.group_id == sources[0].group_id for source in sources) else None
        style = {"fill": "#000000", "stroke": "none"}
        if operation == "difference":
            style["fill-rule"] = "evenodd"
        region = FilledRegionElement(
            id=identifier, x=(xmin + xmax) / 2.0, y=(ymin + ymax) / 2.0,
            width=max(xmax - xmin, 1e-9), height=max(ymax - ymin, 1e-9),
            style=style, group_id=shared_group,
            path_data=path_data_from_polygons(polygons),
            base_x=(xmin + xmax) / 2.0, base_y=(ymin + ymax) / 2.0,
            base_width=max(xmax - xmin, 1e-9), base_height=max(ymax - ymin, 1e-9),
            metadata={"geometry_role": "filled_region", "boolean_operation": operation, "source_ids": source_ids},
        )
        for identifier_to_remove in source_ids:
            self.delete_element(identifier_to_remove)
        self.add_element(region)
        if shared_group:
            for group in self.groups:
                if group.id == shared_group:
                    group.element_ids.append(region.id)
                    break
        return region

    def _new_element_id(self, prefix: str) -> str:
        existing = {element.id for element in self.elements}
        index = 1
        candidate = "%s-%d" % (prefix, index)
        while candidate in existing:
            index += 1
            candidate = "%s-%d" % (prefix, index)
        return candidate

    def to_dict(self) -> Dict[str, Any]:
        self._sync_transforms()
        return {
            "schema_version": self.schema_version,
            "canvas": asdict(self.canvas),
            "reference": asdict(self.reference),
            "elements": [asdict(element) for element in self.elements],
            "groups": [asdict(group) for group in self.groups],
            "transforms": {element_id: asdict(transform) for element_id, transform in self.transforms.items()},
            "metadata": copy.deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "PatternDocument":
        canvas = Canvas(**dict(payload["canvas"]))
        reference = Reference(**dict(payload.get("reference") or {}))
        elements: List[Element] = []
        for raw in payload.get("elements", []):
            values = dict(raw)
            element_type = values.pop("type", None)
            element_class = ELEMENT_TYPES.get(element_type)
            if element_class is None:
                raise ValueError("不支持的 Element type：%s" % element_type)
            elements.append(element_class(**values))
        groups = [Group(**dict(raw)) for raw in payload.get("groups", [])]
        transforms = {
            str(element_id): Transform(**dict(raw))
            for element_id, raw in (payload.get("transforms") or {}).items()
        }
        return cls(
            canvas=canvas,
            reference=reference,
            elements=elements,
            groups=groups,
            transforms=transforms,
            metadata=copy.deepcopy(payload.get("metadata") or {}),
            schema_version=int(payload.get("schema_version", DOCUMENT_SCHEMA_VERSION)),
        )


def new_element_id(prefix: str = "element") -> str:
    return "%s-%s" % (prefix, uuid.uuid4().hex[:12])
