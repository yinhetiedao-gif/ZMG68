"""SVG → normalized, independently editable PatternDocument."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple
import xml.etree.ElementTree as ET

from .models import (
    Canvas,
    CircleElement,
    EllipseElement,
    FilledRegionElement,
    Group,
    PathElement,
    PatternDocument,
    RectElement,
    Reference,
)


NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
NUMBER_RE = re.compile(NUMBER)
RECT_PATH_RE = re.compile(
    r"^\s*M\s*(%s)[ ,]+(%s)\s*H\s*(%s)\s*V\s*(%s)\s*H\s*(%s)\s*[zZ]\s*$" % (NUMBER, NUMBER, NUMBER, NUMBER, NUMBER),
    re.IGNORECASE,
)
ELLIPSE_PATH_RE = re.compile(
    r"^\s*M\s*(%s)[ ,]+(%s)\s*A\s*(%s)[ ,]+(%s)\s+0[ ,]+1[ ,]+0\s+(%s)[ ,]+(%s)"
    r"\s*A\s*(%s)[ ,]+(%s)\s+0[ ,]+1[ ,]+0\s+(%s)[ ,]+(%s)\s*[zZ]?\s*$"
    % (NUMBER, NUMBER, NUMBER, NUMBER, NUMBER, NUMBER, NUMBER, NUMBER, NUMBER, NUMBER),
    re.IGNORECASE,
)
PATH_TOKEN_RE = re.compile(r"[MmCcZz]|" + NUMBER)


@dataclass
class _TransformInfo:
    tx: float = 0.0
    ty: float = 0.0
    sx: float = 1.0
    sy: float = 1.0
    rotation: float = 0.0
    raw: List[str] = field(default_factory=list)

    def extend(self, text: str) -> "_TransformInfo":
        if not text:
            return self
        result = _TransformInfo(self.tx, self.ty, self.sx, self.sy, self.rotation, list(self.raw))
        result.raw.append(text)
        for name, body in re.findall(r"([A-Za-z]+)\s*\(([^)]*)\)", text):
            values = [float(value) for value in NUMBER_RE.findall(body)]
            lowered = name.lower()
            if lowered == "translate" and values:
                result.tx += values[0]
                result.ty += values[1] if len(values) > 1 else 0.0
            elif lowered == "scale" and values:
                result.sx *= values[0]
                result.sy *= values[1] if len(values) > 1 else values[0]
            elif lowered == "rotate" and values:
                result.rotation += values[0]
        return result

    @property
    def raw_text(self) -> str:
        return " ".join(item for item in self.raw if item)


class SVGNormalizer:
    """Convert SVG nodes into concrete Elements; unsupported geometry stays Path."""

    def normalize_file(self, svg_path: str, reference_path: Optional[str] = None,
                       reference_metadata: Optional[Dict[str, Any]] = None,
                       normalization_mode: str = "semantic") -> PatternDocument:
        if normalization_mode not in {"semantic", "faithful"}:
            raise ValueError("不支持的 SVG 归一化模式：%s" % normalization_mode)
        source = Path(svg_path).resolve()
        tree = ET.parse(str(source))
        root = tree.getroot()
        canvas = _canvas_from_root(root)
        reference = Reference(str(Path(reference_path or source).resolve()), False,
                              metadata=dict(reference_metadata or {}))
        state = _NormalizerState(canvas, reference, normalization_mode=normalization_mode)
        self._visit(root, state, _TransformInfo(), {}, None)
        document = PatternDocument(canvas, reference, state.elements, state.groups,
                                   metadata={"normalizer": "foundation-svg-normalizer", "source_svg": str(source), "normalization_mode": normalization_mode})
        return document

    def _visit(self, node: ET.Element, state: "_NormalizerState", inherited_transform: _TransformInfo,
               inherited_style: Dict[str, Any], group_id: Optional[str]) -> None:
        for child in list(node):
            if not isinstance(child.tag, str):
                continue
            tag = _local_name(child.tag)
            style = _merge_style(inherited_style, child)
            transform = inherited_transform.extend(child.attrib.get("transform", ""))
            if tag == "g":
                identifier = state.unique_id(child.attrib.get("id") or "group")
                group = Group(identifier, child.attrib.get("data-name") or identifier)
                state.groups.append(group)
                self._visit(child, state, transform, style, identifier)
                continue
            element = self._element_from_node(child, tag, state, transform, style, group_id)
            if element is None:
                continue
            state.elements.append(element)
            if group_id:
                for group in state.groups:
                    if group.id == group_id:
                        group.element_ids.append(element.id)
                        break

    def _element_from_node(self, node: ET.Element, tag: str, state: "_NormalizerState",
                           transform: _TransformInfo, style: Dict[str, Any], group_id: Optional[str]):
        identifier = state.unique_id(node.attrib.get("id") or tag)
        if state.normalization_mode == "faithful":
            style = _force_filled_style(style)
        visible = _is_visible(style, node)
        if tag == "circle":
            center_x, center_y = _point(_number(node.attrib.get("cx")), _number(node.attrib.get("cy")), transform)
            radius = _number(node.attrib.get("r"))
            width = 2 * radius * abs(transform.sx)
            height = 2 * radius * abs(transform.sy)
            element_class = CircleElement if math.isclose(width, height, rel_tol=1e-8, abs_tol=1e-8) else EllipseElement
            return element_class(identifier, center_x, center_y, max(width, 1e-9), max(height, 1e-9), transform.rotation,
                                 visible, style, group_id)
        if tag == "ellipse":
            center_x, center_y = _point(_number(node.attrib.get("cx")), _number(node.attrib.get("cy")), transform)
            return EllipseElement(identifier, center_x, center_y,
                                  max(2 * _number(node.attrib.get("rx")) * abs(transform.sx), 1e-9),
                                  max(2 * _number(node.attrib.get("ry")) * abs(transform.sy), 1e-9),
                                  transform.rotation, visible, style, group_id)
        if tag == "rect":
            raw_x = _number(node.attrib.get("x")); raw_y = _number(node.attrib.get("y"))
            raw_width = _number(node.attrib.get("width")); raw_height = _number(node.attrib.get("height"))
            center_x, center_y = _point(raw_x + raw_width / 2.0, raw_y + raw_height / 2.0, transform)
            return RectElement(
                id=identifier, x=center_x, y=center_y,
                width=max(raw_width * abs(transform.sx), 1e-9),
                height=max(raw_height * abs(transform.sy), 1e-9), rotation=transform.rotation,
                visible=visible, style=style, group_id=group_id,
                rx=_number(node.attrib.get("rx")), ry=_number(node.attrib.get("ry")),
            )
        if tag == "path":
            path_data = node.attrib.get("d", "").strip()
            if state.normalization_mode == "faithful" and path_data:
                return _filled_region_element(identifier, path_data, _path_bounds(path_data), transform, visible, style, group_id)
            foundation_path = _foundation_path_element(identifier, node, path_data, visible, style, group_id)
            if foundation_path is not None:
                return foundation_path
            recovered = _recover_path_primitive(identifier, path_data, transform, visible, style, group_id)
            if recovered is not None:
                return recovered
            bounds = _path_bounds(path_data)
            return _path_element(identifier, path_data, bounds, transform, visible, style, group_id)
        if tag == "polygon":
            values = [float(value) for value in NUMBER_RE.findall(node.attrib.get("points", ""))]
            pairs = list(zip(values[0::2], values[1::2]))
            if len(pairs) >= 3:
                path_data = "M " + " L ".join("%g %g" % pair for pair in pairs) + " Z"
                return _filled_region_element(identifier, path_data, _path_bounds(path_data), transform, visible, style, group_id)
        return None


@dataclass
class _NormalizerState:
    canvas: Canvas
    reference: Reference
    elements: List[Any] = field(default_factory=list)
    groups: List[Group] = field(default_factory=list)
    ids: set = field(default_factory=set)
    normalization_mode: str = "semantic"

    def unique_id(self, preferred: str) -> str:
        seed = re.sub(r"[^A-Za-z0-9_.:-]+", "-", preferred).strip("-") or "element"
        candidate = seed
        index = 1
        while candidate in self.ids:
            index += 1
            candidate = "%s-%d" % (seed, index)
        self.ids.add(candidate)
        return candidate


def _canvas_from_root(root: ET.Element) -> Canvas:
    viewbox = [float(value) for value in NUMBER_RE.findall(root.attrib.get("viewBox", ""))]
    if len(viewbox) == 4 and viewbox[2] > 0 and viewbox[3] > 0:
        width, height = viewbox[2], viewbox[3]
        origin_x, origin_y = viewbox[0], viewbox[1]
    else:
        width, height = _number(root.attrib.get("width"), 100.0), _number(root.attrib.get("height"), 100.0)
        origin_x = origin_y = 0.0
    raw_width = root.attrib.get("width", "")
    if raw_width.strip().endswith("mm") and width > 0:
        millimetres = _number(raw_width)
        mm_per_unit = millimetres / width
    else:
        mm_per_unit = None
    return Canvas(width, height, "svg_user_unit", mm_per_unit, origin_x, origin_y)


def _recover_path_primitive(identifier: str, path_data: str, transform: _TransformInfo,
                            visible: bool, style: Dict[str, Any], group_id: Optional[str]):
    rect = RECT_PATH_RE.fullmatch(path_data)
    if rect:
        x0, y0, x1, y1, x2 = [float(value) for value in rect.groups()]
        if math.isclose(x0, x2, rel_tol=1e-8, abs_tol=1e-8):
            raw_width, raw_height = abs(x1 - x0), abs(y1 - y0)
            cx, cy = _point((x0 + x1) / 2.0, (y0 + y1) / 2.0, transform)
            return RectElement(id=identifier, x=cx, y=cy, width=max(raw_width * abs(transform.sx), 1e-9),
                               height=max(raw_height * abs(transform.sy), 1e-9), rotation=transform.rotation,
                               visible=visible, style=style, group_id=group_id)
    ellipse = ELLIPSE_PATH_RE.fullmatch(path_data)
    if ellipse:
        x1, y1, rx1, ry1, x2, y2, rx2, ry2, x3, y3 = [float(value) for value in ellipse.groups()]
        if (math.isclose(rx1, rx2, rel_tol=1e-8, abs_tol=1e-8)
                and math.isclose(ry1, ry2, rel_tol=1e-8, abs_tol=1e-8)
                and math.isclose(x1, x3, rel_tol=1e-8, abs_tol=1e-8)
                and math.isclose(y1, y3, rel_tol=1e-8, abs_tol=1e-8)
                and math.isclose(y1, y2, rel_tol=1e-8, abs_tol=1e-8)):
            cx, cy = _point((x1 + x2) / 2.0, y1, transform)
            width, height = 2 * abs(rx1) * abs(transform.sx), 2 * abs(ry1) * abs(transform.sy)
            element_class = CircleElement if math.isclose(width, height, rel_tol=1e-8, abs_tol=1e-8) else EllipseElement
            return element_class(identifier, cx, cy, max(width, 1e-9), max(height, 1e-9),
                                 transform.rotation, visible, style, group_id)
    cubic_ellipse = _recover_closed_cubic_ellipse(path_data)
    if cubic_ellipse is not None:
        raw_center_x, raw_center_y, raw_width, raw_height = cubic_ellipse
        center_x, center_y = _point(raw_center_x, raw_center_y, transform)
        width = raw_width * abs(transform.sx)
        height = raw_height * abs(transform.sy)
        element_class = CircleElement if math.isclose(width, height, rel_tol=0.015, abs_tol=1e-8) else EllipseElement
        return element_class(identifier, center_x, center_y, max(width, 1e-9), max(height, 1e-9),
                             transform.rotation, visible, style, group_id)
    return None


def _recover_closed_cubic_ellipse(path_data: str) -> Optional[Tuple[float, float, float, float]]:
    """Conservatively recover a circle/ellipse from a closed cubic-only SVG path.

    Raster vectorizers commonly emit anti-aliased dots as closed cubic paths rather
    than ``<circle>``.  Sampling the actual Bezier curves (not merely the control
    point box) lets those dots become editable primitive elements.  A path is
    accepted only when it is closed, contains cubic curves only, and every sampled
    point remains close to one axis-aligned ellipse; all other paths stay a
    :class:`PathElement`.
    """
    tokens = PATH_TOKEN_RE.findall(path_data)
    if not tokens:
        return None
    index = 0
    command: Optional[str] = None
    start: Optional[Tuple[float, float]] = None
    current: Optional[Tuple[float, float]] = None
    segments: List[Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float], Tuple[float, float]]] = []
    closed = False
    while index < len(tokens):
        if tokens[index].isalpha():
            command = tokens[index]
            index += 1
            if command in "Zz":
                closed = True
                current = start
                continue
        if command is None or command.islower():
            return None
        if command == "M":
            if index + 1 >= len(tokens) or start is not None:
                return None
            start = (float(tokens[index]), float(tokens[index + 1]))
            current = start
            index += 2
            # SVG permits implicit lineto coordinates after M; they are not a
            # reliable ellipse signal and are therefore rejected.
            command = None
        elif command == "C":
            if current is None or index + 5 >= len(tokens):
                return None
            p1 = (float(tokens[index]), float(tokens[index + 1]))
            p2 = (float(tokens[index + 2]), float(tokens[index + 3]))
            end = (float(tokens[index + 4]), float(tokens[index + 5]))
            segments.append((current, p1, p2, end))
            current = end
            index += 6
        else:
            return None
    if not closed or start is None or current is None or len(segments) < 3:
        return None
    if math.dist(current, start) > 1e-5:
        return None

    samples: List[Tuple[float, float]] = []
    for segment in segments:
        samples.extend(_sample_cubic(*segment, count=12))
    xs, ys = zip(*samples)
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    rx, ry = (xmax - xmin) / 2.0, (ymax - ymin) / 2.0
    if rx <= 1e-6 or ry <= 1e-6:
        return None
    cx, cy = (xmin + xmax) / 2.0, (ymin + ymax) / 2.0
    errors = [abs(math.hypot((x - cx) / rx, (y - cy) / ry) - 1.0) for x, y in samples]
    # This deliberately rejects paths with even modest non-elliptic variation.
    # The threshold is large enough for raster-traced, anti-aliased circular dots
    # and small enough to leave rounded polygons and organic outlines as paths.
    # Binary raster tracers deliberately simplify tiny circles to only four to
    # six cubic segments.  Their sampled outline is visibly circular but does
    # not satisfy the much stricter tolerance appropriate for a hand-authored
    # Bézier ellipse.  Keeping the previous threshold made those dots fall
    # through as generic PathElement instances, which a conservative Canvas
    # renderer could only show as bounding boxes.  The command/closure checks
    # above still reject arbitrary paths; these relaxed residual limits only
    # admit compact, closed, ellipse-like tracer output.
    if (sum(error * error for error in errors) / len(errors)) ** 0.5 > 0.080 or max(errors) > 0.140:
        return None
    return cx, cy, 2.0 * rx, 2.0 * ry


def _sample_cubic(p0: Tuple[float, float], p1: Tuple[float, float], p2: Tuple[float, float], p3: Tuple[float, float],
                  count: int) -> List[Tuple[float, float]]:
    result = []
    for index in range(count + 1):
        t = index / float(count)
        u = 1.0 - t
        result.append((
            u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
            u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1],
        ))
    return result


def _path_element(identifier: str, path_data: str, bounds: Tuple[float, float, float, float],
                  transform: _TransformInfo, visible: bool, style: Dict[str, Any], group_id: Optional[str]) -> PathElement:
    xmin, ymin, xmax, ymax = bounds
    raw_width, raw_height = max(xmax - xmin, 1e-9), max(ymax - ymin, 1e-9)
    raw_center_x, raw_center_y = (xmin + xmax) / 2.0, (ymin + ymax) / 2.0
    center_x, center_y = _point(raw_center_x, raw_center_y, transform)
    return PathElement(
        id=identifier, x=center_x, y=center_y,
        width=raw_width * abs(transform.sx), height=raw_height * abs(transform.sy),
        rotation=transform.rotation, visible=visible, style=style, group_id=group_id,
        path_data=path_data, source_transform=transform.raw_text,
        base_x=center_x, base_y=center_y,
        base_width=raw_width * abs(transform.sx), base_height=raw_height * abs(transform.sy),
    )


def _filled_region_element(identifier: str, path_data: str, bounds: Tuple[float, float, float, float],
                           transform: _TransformInfo, visible: bool, style: Dict[str, Any], group_id: Optional[str]) -> FilledRegionElement:
    """Preserve a traced closed silhouette as material, never as a wireframe."""

    xmin, ymin, xmax, ymax = bounds
    raw_width, raw_height = max(xmax - xmin, 1e-9), max(ymax - ymin, 1e-9)
    raw_center_x, raw_center_y = (xmin + xmax) / 2.0, (ymin + ymax) / 2.0
    center_x, center_y = _point(raw_center_x, raw_center_y, transform)
    filled_style = _force_filled_style(style)
    return FilledRegionElement(
        id=identifier, x=center_x, y=center_y,
        width=raw_width * abs(transform.sx), height=raw_height * abs(transform.sy),
        rotation=transform.rotation, visible=visible, style=filled_style, group_id=group_id,
        path_data=path_data, source_transform=transform.raw_text,
        base_x=center_x, base_y=center_y,
        base_width=raw_width * abs(transform.sx), base_height=raw_height * abs(transform.sy),
        metadata={"geometry_role": "filled_region", "source": "faithful_mapping"},
    )


def _foundation_path_element(identifier: str, node: ET.Element, path_data: str,
                             visible: bool, style: Dict[str, Any], group_id: Optional[str]) -> Optional[PathElement]:
    """Restore an application-exported PathElement without numerical transform drift.

    This is deliberately narrow: metadata is honoured only when the complete set
    written by :mod:`svg_exporter` is present.  SVGs from other tools continue
    through the ordinary conservative path normalisation route.
    """
    required = (
        "data-foundation-x", "data-foundation-y",
        "data-foundation-width", "data-foundation-height",
        "data-foundation-rotation", "data-foundation-base-x",
        "data-foundation-base-y", "data-foundation-base-width",
        "data-foundation-base-height",
    )
    if not path_data or any(key not in node.attrib for key in required):
        return None
    element_type = node.attrib.get("data-foundation-element-type", "path")
    element_class = FilledRegionElement if element_type == "filled_region" else PathElement
    element_style = dict(style)
    if element_class is FilledRegionElement:
        if str(element_style.get("fill", "")).strip().lower() in {"", "none", "transparent"}:
            element_style["fill"] = "#000000"
        element_style["stroke"] = "none"
    return element_class(
        id=identifier,
        x=_number(node.attrib["data-foundation-x"]),
        y=_number(node.attrib["data-foundation-y"]),
        width=max(_number(node.attrib["data-foundation-width"]), 1e-9),
        height=max(_number(node.attrib["data-foundation-height"]), 1e-9),
        rotation=_number(node.attrib["data-foundation-rotation"]),
        visible=visible,
        style=element_style,
        group_id=group_id,
        path_data=path_data,
        source_transform=node.attrib.get("data-foundation-source-transform", ""),
        base_x=_number(node.attrib["data-foundation-base-x"]),
        base_y=_number(node.attrib["data-foundation-base-y"]),
        base_width=max(_number(node.attrib["data-foundation-base-width"]), 1e-9),
        base_height=max(_number(node.attrib["data-foundation-base-height"]), 1e-9),
    )


def _path_bounds(path_data: str) -> Tuple[float, float, float, float]:
    values = [float(value) for value in NUMBER_RE.findall(path_data)]
    pairs = list(zip(values[0::2], values[1::2]))
    if not pairs:
        return 0.0, 0.0, 1.0, 1.0
    xs, ys = zip(*pairs)
    return min(xs), min(ys), max(xs), max(ys)


def _point(x: float, y: float, transform: _TransformInfo) -> Tuple[float, float]:
    return x * transform.sx + transform.tx, y * transform.sy + transform.ty


def _number(value: Optional[str], default: float = 0.0) -> float:
    if value is None:
        return default
    match = NUMBER_RE.search(str(value))
    return float(match.group(0)) if match else default


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _merge_style(parent: Dict[str, Any], node: ET.Element) -> Dict[str, Any]:
    style = dict(parent)
    for key in ("fill", "stroke", "stroke-width", "fill-rule", "opacity", "display", "visibility"):
        if key in node.attrib:
            style[key] = node.attrib[key]
    for declaration in node.attrib.get("style", "").split(";"):
        if ":" in declaration:
            key, value = declaration.split(":", 1)
            style[key.strip()] = value.strip()
    return style


def _force_filled_style(style: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a binary raster trace to material fill rather than contour ink."""
    filled_style = dict(style)
    if str(filled_style.get("fill", "")).strip().lower() in {"", "none", "transparent"}:
        filled_style["fill"] = "#000000"
    filled_style["stroke"] = "none"
    return filled_style


def _is_visible(style: Dict[str, Any], node: ET.Element) -> bool:
    return style.get("display") != "none" and style.get("visibility") != "hidden" and node.attrib.get("display") != "none"
