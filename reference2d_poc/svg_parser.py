from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import re
from typing import Iterable
from xml.etree import ElementTree as ET


Point = tuple[float, float]
Matrix = tuple[float, float, float, float, float, float]
_IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
_TOKEN = re.compile(r"[AaCcHhLlMmQqSsTtVvZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_TRANSFORM = re.compile(r"([a-zA-Z]+)\s*\(([^)]*)\)")


@dataclass(frozen=True)
class VectorPath:
    id: str
    fill: str
    points: tuple[Point, ...]
    source_element: str = "path"


@dataclass(frozen=True)
class ParsedSVG:
    width: float
    height: float
    paths: tuple[VectorPath, ...]


def _number(value: str | None, fallback: float = 0.0) -> float:
    if not value:
        return fallback
    match = re.search(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", value)
    return float(match.group(0)) if match else fallback


def _multiply(first: Matrix, second: Matrix) -> Matrix:
    a1, b1, c1, d1, e1, f1 = first
    a2, b2, c2, d2, e2, f2 = second
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def _apply(matrix: Matrix, point: Point) -> Point:
    a, b, c, d, e, f = matrix
    x, y = point
    return a * x + c * y + e, b * x + d * y + f


def _transform(value: str | None) -> Matrix:
    matrix = _IDENTITY
    for name, raw_values in _TRANSFORM.findall(value or ""):
        values = [float(item) for item in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", raw_values)]
        name = name.lower()
        local = _IDENTITY
        if name == "translate" and values:
            local = (1.0, 0.0, 0.0, 1.0, values[0], values[1] if len(values) > 1 else 0.0)
        elif name == "scale" and values:
            local = (values[0], 0.0, 0.0, values[1] if len(values) > 1 else values[0], 0.0, 0.0)
        elif name == "rotate" and values:
            radians = math.radians(values[0])
            cosine, sine = math.cos(radians), math.sin(radians)
            rotation = (cosine, sine, -sine, cosine, 0.0, 0.0)
            if len(values) >= 3:
                pivot = (1.0, 0.0, 0.0, 1.0, values[1], values[2])
                inverse = (1.0, 0.0, 0.0, 1.0, -values[1], -values[2])
                local = _multiply(_multiply(pivot, rotation), inverse)
            else:
                local = rotation
        elif name == "matrix" and len(values) == 6:
            local = tuple(values)  # type: ignore[assignment]
        matrix = _multiply(matrix, local)
    return matrix


def _cubic(start: Point, control1: Point, control2: Point, end: Point, steps: int = 10) -> list[Point]:
    result: list[Point] = []
    for index in range(1, steps + 1):
        t = index / steps
        inverse = 1.0 - t
        result.append(
            (
                inverse**3 * start[0] + 3 * inverse**2 * t * control1[0] + 3 * inverse * t**2 * control2[0] + t**3 * end[0],
                inverse**3 * start[1] + 3 * inverse**2 * t * control1[1] + 3 * inverse * t**2 * control2[1] + t**3 * end[1],
            )
        )
    return result


def _quadratic(start: Point, control: Point, end: Point, steps: int = 8) -> list[Point]:
    result: list[Point] = []
    for index in range(1, steps + 1):
        t = index / steps
        inverse = 1.0 - t
        result.append(
            (
                inverse**2 * start[0] + 2 * inverse * t * control[0] + t**2 * end[0],
                inverse**2 * start[1] + 2 * inverse * t * control[1] + t**2 * end[1],
            )
        )
    return result


def _parse_path_data(data: str) -> list[list[Point]]:
    tokens = _TOKEN.findall(data)
    index = 0
    command: str | None = None
    current: Point = (0.0, 0.0)
    start: Point = (0.0, 0.0)
    last_cubic: Point | None = None
    last_quadratic: Point | None = None
    paths: list[list[Point]] = []
    path: list[Point] = []

    def is_command(value: str) -> bool:
        return len(value) == 1 and value.isalpha()

    def read(count: int) -> list[float]:
        nonlocal index
        if index + count > len(tokens) or any(is_command(token) for token in tokens[index : index + count]):
            raise ValueError("SVG path 参数不完整")
        values = [float(token) for token in tokens[index : index + count]]
        index += count
        return values

    while index < len(tokens):
        if is_command(tokens[index]):
            command = tokens[index]
            index += 1
        if command is None:
            raise ValueError("SVG path 缺少命令")
        relative = command.islower()
        op = command.upper()
        if op == "M":
            x, y = read(2)
            if relative:
                x, y = x + current[0], y + current[1]
            if path:
                paths.append(path)
            path = [(x, y)]
            current = start = (x, y)
            command = "l" if relative else "L"
            last_cubic = last_quadratic = None
        elif op == "L":
            x, y = read(2)
            if relative:
                x, y = x + current[0], y + current[1]
            current = (x, y)
            path.append(current)
            last_cubic = last_quadratic = None
        elif op == "H":
            (x,) = read(1)
            current = (x + current[0] if relative else x, current[1])
            path.append(current)
            last_cubic = last_quadratic = None
        elif op == "V":
            (y,) = read(1)
            current = (current[0], y + current[1] if relative else y)
            path.append(current)
            last_cubic = last_quadratic = None
        elif op == "C":
            x1, y1, x2, y2, x, y = read(6)
            if relative:
                x1, y1, x2, y2, x, y = x1 + current[0], y1 + current[1], x2 + current[0], y2 + current[1], x + current[0], y + current[1]
            control1, control2, end = (x1, y1), (x2, y2), (x, y)
            path.extend(_cubic(current, control1, control2, end))
            current, last_cubic, last_quadratic = end, control2, None
        elif op == "S":
            x2, y2, x, y = read(4)
            if relative:
                x2, y2, x, y = x2 + current[0], y2 + current[1], x + current[0], y + current[1]
            control1 = (2 * current[0] - last_cubic[0], 2 * current[1] - last_cubic[1]) if last_cubic else current
            control2, end = (x2, y2), (x, y)
            path.extend(_cubic(current, control1, control2, end))
            current, last_cubic, last_quadratic = end, control2, None
        elif op == "Q":
            x1, y1, x, y = read(4)
            if relative:
                x1, y1, x, y = x1 + current[0], y1 + current[1], x + current[0], y + current[1]
            control, end = (x1, y1), (x, y)
            path.extend(_quadratic(current, control, end))
            current, last_quadratic, last_cubic = end, control, None
        elif op == "T":
            x, y = read(2)
            if relative:
                x, y = x + current[0], y + current[1]
            control = (2 * current[0] - last_quadratic[0], 2 * current[1] - last_quadratic[1]) if last_quadratic else current
            end = (x, y)
            path.extend(_quadratic(current, control, end))
            current, last_quadratic, last_cubic = end, control, None
        elif op == "A":
            # Stage A 的 VTracer spline 输出不会出现 Arc。为兼容输入 SVG，保留其
            # 终点而不将它误认为完整圆弧；此类路径会因低圆度被安全拒绝。
            rx, ry, rotation, large_arc, sweep, x, y = read(7)
            del rx, ry, rotation, large_arc, sweep
            if relative:
                x, y = x + current[0], y + current[1]
            current = (x, y)
            path.append(current)
            last_cubic = last_quadratic = None
        elif op == "Z":
            if path and path[-1] != start:
                path.append(start)
            current = start
            last_cubic = last_quadratic = None
            command = None
        else:
            raise ValueError(f"不支持的 SVG path 命令：{command}")
    if path:
        paths.append(path)
    return paths


def _style(element: ET.Element, inherited_fill: str = "#000000") -> str:
    style_values: dict[str, str] = {}
    for part in element.attrib.get("style", "").split(";"):
        if ":" in part:
            key, value = part.split(":", 1)
            style_values[key.strip()] = value.strip()
    return element.attrib.get("fill", style_values.get("fill", inherited_fill)).strip().lower()


class SVGParser:
    """把 VTracer SVG path 拆为可以被 PrimitiveRecognizer 判断的真实轮廓。"""

    def parse_file(self, svg_path: str | Path) -> ParsedSVG:
        root = ET.parse(svg_path).getroot()
        view_box = [float(value) for value in root.attrib.get("viewBox", "").replace(",", " ").split()]
        width = _number(root.attrib.get("width"), view_box[2] if len(view_box) == 4 else 0.0)
        height = _number(root.attrib.get("height"), view_box[3] if len(view_box) == 4 else 0.0)
        paths: list[VectorPath] = []

        def walk(element: ET.Element, parent_matrix: Matrix, inherited_fill: str) -> None:
            matrix = _multiply(parent_matrix, _transform(element.attrib.get("transform")))
            fill = _style(element, inherited_fill)
            tag = element.tag.rsplit("}", 1)[-1].lower()
            prefix = element.attrib.get("id", f"{tag}-{len(paths):04d}")
            if tag == "path" and element.attrib.get("d"):
                for sub_index, points in enumerate(_parse_path_data(element.attrib["d"])):
                    if len(points) >= 3:
                        paths.append(VectorPath(f"{prefix}-{sub_index:03d}", fill, tuple(_apply(matrix, point) for point in points), "path"))
            elif tag in {"circle", "ellipse"}:
                cx, cy = _number(element.attrib.get("cx")), _number(element.attrib.get("cy"))
                rx = _number(element.attrib.get("r"), _number(element.attrib.get("rx")))
                ry = _number(element.attrib.get("r"), _number(element.attrib.get("ry"), rx))
                points = tuple(
                    _apply(matrix, (cx + rx * math.cos(2 * math.pi * index / 32), cy + ry * math.sin(2 * math.pi * index / 32)))
                    for index in range(32)
                )
                paths.append(VectorPath(prefix, fill, points, tag))
            for child in element:
                walk(child, matrix, fill)

        walk(root, _IDENTITY, "#000000")
        return ParsedSVG(width, height, tuple(paths))
