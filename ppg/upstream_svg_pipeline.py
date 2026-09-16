"""Upstream image-to-SVG integration.

This module deliberately contains no raster tracing algorithm.  It is a thin
adapter around the vendored ``ujo78/imagetosvg-mcp`` MCP server.  The server
owns conversion, SVG inspection, editing, rendering and optimization; this
module only provides a stable Python boundary for the desktop application and
turns inspected SVG layers into editable element records.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import xml.etree.ElementTree as ET

from .runtime_paths import is_frozen, resource_path


class UpstreamSVGError(RuntimeError):
    """Raised when the upstream MCP server cannot complete a requested step."""


def _default_root() -> Path:
    # PACK-1 deliberately uses a short bundle path. Node dependency filenames
    # can otherwise exceed the classic Windows 260-character limit.
    return resource_path("mcp") if is_frozen() else resource_path("external", "imagetosvg-mcp")


def _default_bridge() -> Path:
    return resource_path("imagetosvg_bridge.cjs") if is_frozen() else resource_path("external", "imagetosvg_bridge.cjs")


def _default_node() -> str:
    """Prefer the packaged Node runtime; source mode keeps using PATH."""
    bundled = resource_path("tools", "node.exe")
    return str(bundled) if bundled.is_file() else "node"


class ImageToSVGClient:
    """Call the original MCP tools through its stdio bridge."""

    def __init__(self, server_root: Optional[str] = None, node: str | None = None,
                 bridge: Optional[str] = None, timeout: float = 180.0):
        self.server_root = Path(server_root or _default_root()).resolve()
        self.node = node or _default_node()
        self.bridge = Path(bridge or _default_bridge()).resolve()
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return self.server_root.joinpath("dist", "index.js").is_file() and self.bridge.is_file()

    def call(self, tool: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.available:
            raise UpstreamSVGError(
                "上游 imagetosvg-mcp 未构建：请在 external/imagetosvg-mcp 目录运行 npm install。"
            )
        request = json.dumps({"tool": tool, "arguments": arguments or {}}, ensure_ascii=False)
        command = [self.node, str(self.bridge), str(self.server_root)]
        try:
            completed = subprocess.run(
                command,
                input=request,
                text=True,
                # The MCP bridge exchanges JSON that may include a Chinese
                # Windows path.  ``text=True`` otherwise defaults to the
                # process ANSI code page (often GBK), corrupting the UTF-8
                # request before Node receives it.  The protocol is JSON, so
                # UTF-8 is the explicit and portable contract.
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=self.timeout,
                cwd=str(self.server_root),
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise UpstreamSVGError("无法启动 imagetosvg-mcp：%s" % exc) from exc
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "未知错误").strip()
            raise UpstreamSVGError("imagetosvg-mcp 调用失败：%s" % detail)
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        if not lines:
            raise UpstreamSVGError("imagetosvg-mcp 没有返回结果。")
        try:
            result = json.loads(lines[-1])
        except json.JSONDecodeError as exc:
            raise UpstreamSVGError("无法解析 MCP 返回值：%s" % lines[-1][:500]) from exc
        if result.get("error"):
            raise UpstreamSVGError(str(result["error"]))
        if result.get("isError"):
            text = _first_text(result) or "未知 MCP 错误"
            raise UpstreamSVGError(text)
        return result

    def convert_image_to_svg(self, input_path: str, output_path: Optional[str] = None,
                             mode: str = "auto", max_colors: Optional[int] = None) -> Dict[str, Any]:
        args: Dict[str, Any] = {"input_path": str(Path(input_path).resolve()), "mode": mode}
        if output_path:
            args["output_path"] = str(Path(output_path).resolve())
        if max_colors is not None:
            args["max_colors"] = int(max_colors)
        result = self.call("convert_image_to_svg", args)
        payload = _json_text(_first_text(result))
        # imagetosvg-mcp intentionally emits a compact width/height SVG.  The
        # installed svg-skill quality contract requires an explicit viewBox;
        # add that structural metadata without touching any path geometry.
        if isinstance(payload, dict):
            _ensure_svg_viewbox(output_path or payload.get("svgPath"))
        return payload if isinstance(payload, dict) else {"raw": payload}

    def inspect_svg(self, svg_path: str) -> Dict[str, Any]:
        result = self.call("inspect_svg", {"svg_path": str(Path(svg_path).resolve())})
        payload = _json_text(_first_text(result))
        if not isinstance(payload, dict):
            raise UpstreamSVGError("inspect_svg 返回格式不正确。")
        return payload

    def edit_svg(self, svg_path: str, operations: Iterable[Dict[str, Any]],
                 output_path: Optional[str] = None) -> Dict[str, Any]:
        args: Dict[str, Any] = {
            "svg_path": str(Path(svg_path).resolve()),
            "operations": list(operations),
        }
        if output_path:
            args["output_path"] = str(Path(output_path).resolve())
        result = self.call("edit_svg", args)
        payload = _json_text(_first_text(result))
        return payload if isinstance(payload, dict) else {"raw": payload}

    def render_svg(self, svg_path: str, width: Optional[int] = None,
                   scale: Optional[float] = None) -> Dict[str, Any]:
        args: Dict[str, Any] = {"svg_path": str(Path(svg_path).resolve())}
        if width is not None:
            args["width"] = int(width)
        if scale is not None:
            args["scale"] = float(scale)
        result = self.call("render_svg", args)
        payload = _json_text(_first_text(result))
        return payload if isinstance(payload, dict) else {"raw": payload}

    def optimize_svg(self, svg_path: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        args: Dict[str, Any] = {"svg_path": str(Path(svg_path).resolve())}
        if output_path:
            args["output_path"] = str(Path(output_path).resolve())
        result = self.call("optimize_svg", args)
        payload = _json_text(_first_text(result))
        return payload if isinstance(payload, dict) else {"raw": payload}


def _first_text(result: Dict[str, Any]) -> str:
    for block in result.get("content", []):
        if isinstance(block, dict) and block.get("type") == "text":
            return str(block.get("text", ""))
    return ""


def _json_text(text: str) -> Any:
    try:
        return json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return text


@dataclass
class EditableSVGElement:
    """A real SVG layer, addressable by the upstream ``edit_svg`` tool."""

    id: str
    tag: str
    fill: Optional[str] = None
    stroke: Optional[str] = None
    bbox: Optional[List[float]] = None
    transform: Optional[str] = None
    enabled: bool = True
    source_confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "primitive_type": self.tag,
            "fill": self.fill,
            "stroke": self.stroke,
            "bbox": list(self.bbox or []),
            "transform": self.transform,
            "enabled": self.enabled,
            "confidence": self.source_confidence,
        }


@dataclass
class EditableSVGDocument:
    """Editable 2D document with a separate, hideable reference layer."""

    reference_path: str
    svg_path: str
    elements: List[EditableSVGElement] = field(default_factory=list)
    reference_visible: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_inspection(cls, reference_path: str, svg_path: str,
                        inspection: Dict[str, Any]) -> "EditableSVGDocument":
        layers = inspection.get("layers", [])
        by_id: Dict[str, Dict[str, Any]] = {
            str(layer.get("id")): layer for layer in layers if layer.get("id")
        }
        transforms: Dict[str, str] = {}
        try:
            root = ET.parse(svg_path).getroot()
            for child in list(root):
                if not isinstance(child.tag, str):
                    continue
                node_id = child.attrib.get("id")
                if node_id:
                    transforms[node_id] = child.attrib.get("transform", "")
                    by_id.setdefault(node_id, {}).setdefault("tag", _local_name(child.tag))
                    by_id[node_id].setdefault("fill", child.attrib.get("fill"))
                    by_id[node_id].setdefault("stroke", child.attrib.get("stroke"))
        except (OSError, ET.ParseError):
            # inspect_svg remains authoritative; malformed XML will be caught by
            # the upstream tool and is reported to the user.
            pass
        elements = [
            EditableSVGElement(
                id=node_id,
                tag=str(layer.get("tag", "path")),
                fill=layer.get("fill"),
                stroke=layer.get("stroke"),
                bbox=list(layer.get("bbox") or []),
                transform=transforms.get(node_id),
            )
            for node_id, layer in by_id.items()
        ]
        return cls(
            str(Path(reference_path).resolve()),
            str(Path(svg_path).resolve()),
            elements,
            True,
            {"width": inspection.get("width"), "height": inspection.get("height"),
             "viewBox": inspection.get("viewBox"), "source": "ujo78/imagetosvg-mcp"},
        )

    def hide_reference(self) -> None:
        self.reference_visible = False

    def element(self, element_id: str) -> EditableSVGElement:
        for element in self.elements:
            if element.id == element_id:
                return element
        raise KeyError(element_id)

    def edit(self, client: ImageToSVGClient, element_id: str,
             *, translate: Optional[List[float]] = None,
             scale: Optional[float] = None, rotate: Optional[float] = None) -> Dict[str, Any]:
        operation: Dict[str, Any] = {"op": "transform", "id": element_id}
        if translate is not None:
            operation["translate"] = [float(translate[0]), float(translate[1])]
        if scale is not None:
            operation["scale"] = float(scale)
        if rotate is not None:
            operation["rotate"] = float(rotate)
        result = client.edit_svg(self.svg_path, [operation])
        element = self.element(element_id)
        if translate is not None:
            element.transform = "%s translate(%g,%g)" % (element.transform or "", translate[0], translate[1])
        return result

    def render(self, client: ImageToSVGClient, width: Optional[int] = None) -> Dict[str, Any]:
        return client.render_svg(self.svg_path, width=width)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reference": {"path": self.reference_path, "visible": self.reference_visible},
            "geometry": {"svg_path": self.svg_path,
                         "elements": [element.to_dict() for element in self.elements]},
            "metadata": dict(self.metadata),
        }


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_svg_viewbox(path: Optional[str]) -> None:
    if not path:
        return
    target = Path(path)
    if not target.is_file():
        return
    try:
        tree = ET.parse(str(target))
        root = tree.getroot()
        if root.attrib.get("viewBox"):
            return
        width = _svg_number(root.attrib.get("width"))
        height = _svg_number(root.attrib.get("height"))
        if width is None or height is None or width <= 0 or height <= 0:
            return
        root.set("viewBox", "0 0 %g %g" % (width, height))
        ET.register_namespace("", "http://www.w3.org/2000/svg")
        tree.write(str(target), encoding="utf-8", xml_declaration=True)
    except (OSError, ET.ParseError, ValueError):
        return


def _svg_number(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    match = re.match(r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)", str(value))
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None
