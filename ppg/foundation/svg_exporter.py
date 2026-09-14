"""PatternDocument → standalone editable SVG."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional
import xml.etree.ElementTree as ET

from .models import CircleElement, EllipseElement, Element, FilledRegionElement, PathElement, PatternDocument, RectElement


SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def pattern_document_to_svg(document: PatternDocument, output_path: str) -> Path:
    document.validate()
    canvas = document.canvas
    root = ET.Element("{%s}svg" % SVG_NS, {
        "width": _number(canvas.width),
        "height": _number(canvas.height),
        "viewBox": "%s %s %s %s" % (_number(canvas.origin_x), _number(canvas.origin_y), _number(canvas.width), _number(canvas.height)),
        "version": "1.1",
    })
    containers: Dict[Optional[str], ET.Element] = {None: root}
    for group in document.groups:
        containers[group.id] = ET.SubElement(root, "{%s}g" % SVG_NS, {"id": group.id, "data-name": group.name or group.id})
    for element in document.elements:
        # SVG export is a manufacturing/design output, not a project-state
        # snapshot.  Visibility is persisted in PatternDocument JSON; hidden
        # slots (including Gate N Occupancy) must not leak into a downstream
        # SVG, cutter, or later STL pipeline as display:none geometry.
        if not element.visible:
            continue
        parent = containers.get(element.group_id, root)
        _append_element(parent, element)
    tree = ET.ElementTree(root)
    try:
        ET.indent(tree, space="  ")
    except AttributeError:
        pass
    target = Path(output_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(target), encoding="utf-8", xml_declaration=True)
    return target


def _append_element(parent: ET.Element, element: Element) -> None:
    attributes = _common_attributes(element)
    if isinstance(element, CircleElement):
        attributes.update({"cx": _number(element.x), "cy": _number(element.y), "r": _number(element.width / 2.0)})
        _set_rotation(attributes, element)
        ET.SubElement(parent, "{%s}circle" % SVG_NS, attributes)
    elif isinstance(element, EllipseElement):
        attributes.update({"cx": _number(element.x), "cy": _number(element.y),
                           "rx": _number(element.width / 2.0), "ry": _number(element.height / 2.0)})
        _set_rotation(attributes, element)
        ET.SubElement(parent, "{%s}ellipse" % SVG_NS, attributes)
    elif isinstance(element, RectElement):
        attributes.update({"x": _number(element.x - element.width / 2.0), "y": _number(element.y - element.height / 2.0),
                           "width": _number(element.width), "height": _number(element.height)})
        if element.rx:
            attributes["rx"] = _number(element.rx)
        if element.ry:
            attributes["ry"] = _number(element.ry)
        _set_rotation(attributes, element)
        ET.SubElement(parent, "{%s}rect" % SVG_NS, attributes)
    elif isinstance(element, PathElement):
        attributes["d"] = element.path_data
        # Keep the editable document state in portable SVG metadata.  The path and
        # its visual transform remain ordinary SVG; these attributes only avoid
        # losing exact logical bounds when this application reopens an SVG after a
        # scale / move edit.  External SVGs never require these attributes.
        attributes.update({
            "data-foundation-x": _number(element.x),
            "data-foundation-y": _number(element.y),
            "data-foundation-width": _number(element.width),
            "data-foundation-height": _number(element.height),
            "data-foundation-rotation": _number(element.rotation),
            "data-foundation-base-x": _number(element.base_x),
            "data-foundation-base-y": _number(element.base_y),
            "data-foundation-base-width": _number(element.base_width),
            "data-foundation-base-height": _number(element.base_height),
        })
        if isinstance(element, FilledRegionElement):
            attributes["data-foundation-element-type"] = "filled_region"
        if element.source_transform:
            attributes["data-foundation-source-transform"] = element.source_transform
        transform = _path_transform(element)
        if transform:
            attributes["transform"] = transform
        ET.SubElement(parent, "{%s}path" % SVG_NS, attributes)
    else:
        raise TypeError("不支持导出的 Element：%s" % element.type)


def _common_attributes(element: Element) -> Dict[str, str]:
    attributes = {"id": element.id}
    for key in ("fill", "stroke", "stroke-width", "opacity"):
        value = element.style.get(key)
        if value is not None:
            attributes[key] = str(value)
    if "fill" not in attributes:
        attributes["fill"] = "#000000"
    if isinstance(element, FilledRegionElement):
        # Do not inherit an accidental contour stroke from a source SVG.  The
        # region path itself is the black material in Faithful Mapping mode.
        attributes["fill"] = str(element.style.get("fill") or "#000000")
        attributes["stroke"] = "none"
        fill_rule = element.style.get("fill-rule")
        if fill_rule:
            attributes["fill-rule"] = str(fill_rule)
    if not element.visible:
        attributes["display"] = "none"
    return attributes


def _set_rotation(attributes: Dict[str, str], element: Element) -> None:
    if element.rotation:
        attributes["transform"] = "rotate(%s %s %s)" % (_number(element.rotation), _number(element.x), _number(element.y))


def _path_transform(element: PathElement) -> str:
    parts = [part for part in (element.source_transform or "").split() if part]
    dx, dy = element.x - element.base_x, element.y - element.base_y
    if dx or dy:
        parts.append("translate(%s %s)" % (_number(dx), _number(dy)))
    if element.width != element.base_width or element.height != element.base_height:
        sx = element.width / max(element.base_width, 1e-9)
        sy = element.height / max(element.base_height, 1e-9)
        parts.extend([
            "translate(%s %s)" % (_number(element.base_x), _number(element.base_y)),
            "scale(%s %s)" % (_number(sx), _number(sy)),
            "translate(%s %s)" % (_number(-element.base_x), _number(-element.base_y)),
        ])
    if element.rotation:
        parts.append("rotate(%s %s %s)" % (_number(element.rotation), _number(element.base_x), _number(element.base_y)))
    return " ".join(parts)


def _number(value: float) -> str:
    return ("%.8f" % float(value)).rstrip("0").rstrip(".") or "0"
