"""Small, dependency-free SVG path helpers for filled editable regions.

The helpers intentionally cover the commands emitted by the local raster
vectorizer (M/L/H/V/C/Q/Z).  Unsupported arc/smooth commands retain their end
point instead of inventing semantic geometry.  That keeps a complete filled
silhouette editable while allowing a future, replaceable high-accuracy path
engine to improve tessellation without changing ``PatternDocument``.
"""
from __future__ import annotations

import math
import re
from typing import Iterable, List, Sequence, Tuple

from .models import CircleElement, EllipseElement, FilledRegionElement, RectElement


Point = Tuple[float, float]
TOKEN_RE = re.compile(r"[AaCcHhLlMmQqSsTtVvZz]|[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
NUMBER_RE = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")


def path_subpaths(path_data: str, samples_per_curve: int = 8) -> List[List[Point]]:
    """Flatten common SVG path commands into independently drawable polygons."""

    tokens = TOKEN_RE.findall(path_data or "")
    subpaths: List[List[Point]] = []
    current: Point = (0.0, 0.0)
    start: Point | None = None
    path: List[Point] = []
    command: str | None = None
    index = 0

    def take(count: int) -> List[float] | None:
        nonlocal index
        # ``tokens[index:index + count]`` already yields token strings.  Using
        # each token as a list index made every filled SVG path fail as soon as
        # Canvas tried to tessellate it, which in turn looked like a wireframe
        # or missing faithful-mapping result.  Reject command tokens directly.
        if index + count > len(tokens) or any(token.isalpha() for token in tokens[index:index + count]):
            return None
        values = [float(value) for value in tokens[index:index + count]]
        index += count
        return values

    def emit(point: Point) -> None:
        nonlocal current
        current = point
        if not path or point != path[-1]:
            path.append(point)

    def close() -> None:
        nonlocal path, start
        if path:
            if start is not None and path[-1] != start:
                path.append(start)
            if len(path) >= 4:
                subpaths.append(path)
        path = []
        start = None

    while index < len(tokens):
        if tokens[index].isalpha():
            command = tokens[index]
            index += 1
            if command in "Zz":
                close()
                continue
        if command is None:
            break
        relative = command.islower()
        name = command.upper()
        if name == "M":
            values = take(2)
            if values is None:
                break
            if path:
                close()
            point = (values[0] + (current[0] if relative else 0.0), values[1] + (current[1] if relative else 0.0))
            current = point
            start = point
            path = [point]
            command = "l" if relative else "L"
        elif name == "L":
            values = take(2)
            if values is None:
                break
            emit((values[0] + (current[0] if relative else 0.0), values[1] + (current[1] if relative else 0.0)))
        elif name == "H":
            values = take(1)
            if values is None:
                break
            emit((values[0] + (current[0] if relative else 0.0), current[1]))
        elif name == "V":
            values = take(1)
            if values is None:
                break
            emit((current[0], values[0] + (current[1] if relative else 0.0)))
        elif name == "C":
            values = take(6)
            if values is None:
                break
            ox, oy = current if relative else (0.0, 0.0)
            p0, p1, p2, p3 = current, (values[0] + ox, values[1] + oy), (values[2] + ox, values[3] + oy), (values[4] + ox, values[5] + oy)
            for sample in _sample_cubic(p0, p1, p2, p3, samples_per_curve)[1:]:
                emit(sample)
        elif name == "Q":
            values = take(4)
            if values is None:
                break
            ox, oy = current if relative else (0.0, 0.0)
            p0, p1, p2 = current, (values[0] + ox, values[1] + oy), (values[2] + ox, values[3] + oy)
            for sample in _sample_quadratic(p0, p1, p2, samples_per_curve)[1:]:
                emit(sample)
        elif name in {"S", "T", "A"}:
            # Preserve endpoints for commands not emitted by the current
            # vectorizer.  This is intentionally conservative, not a fake
            # primitive recovery.
            count = {"S": 4, "T": 2, "A": 7}[name]
            values = take(count)
            if values is None:
                break
            endpoint = values[-2:]
            emit((endpoint[0] + (current[0] if relative else 0.0), endpoint[1] + (current[1] if relative else 0.0)))
        else:
            break
    if path:
        close()
    return subpaths


def filled_region_polygons(
    element: FilledRegionElement,
    *,
    x: float | None = None,
    y: float | None = None,
    width: float | None = None,
    height: float | None = None,
    rotation: float | None = None,
) -> List[List[Point]]:
    """Return a region's actual material boundary in document coordinates."""

    result = _apply_svg_transform(path_subpaths(element.path_data), element.source_transform)
    target_x = element.x if x is None else float(x)
    target_y = element.y if y is None else float(y)
    target_width = element.width if width is None else float(width)
    target_height = element.height if height is None else float(height)
    target_rotation = element.rotation if rotation is None else float(rotation)
    sx = target_width / max(element.base_width, 1e-9)
    sy = target_height / max(element.base_height, 1e-9)
    dx, dy = target_x - element.base_x, target_y - element.base_y
    transformed = [[((px - element.base_x) * sx + element.base_x + dx, (py - element.base_y) * sy + element.base_y + dy) for px, py in polygon] for polygon in result]
    if not target_rotation:
        return transformed
    radians = math.radians(target_rotation)
    cosine, sine = math.cos(radians), math.sin(radians)
    return [[(target_x + (px - target_x) * cosine - (py - target_y) * sine,
              target_y + (px - target_x) * sine + (py - target_y) * cosine) for px, py in polygon] for polygon in transformed]


def element_polygons(element, samples: int = 32) -> List[List[Point]]:
    """Convert supported material Elements into world-space polygons."""

    if isinstance(element, FilledRegionElement):
        return filled_region_polygons(element)
    if isinstance(element, CircleElement) or isinstance(element, EllipseElement):
        points = []
        radians = math.radians(element.rotation)
        cosine, sine = math.cos(radians), math.sin(radians)
        for index in range(samples + 1):
            angle = 2.0 * math.pi * index / samples
            local_x, local_y = math.cos(angle) * element.width / 2.0, math.sin(angle) * element.height / 2.0
            points.append((element.x + local_x * cosine - local_y * sine, element.y + local_x * sine + local_y * cosine))
        return [points]
    if isinstance(element, RectElement):
        raw = [(-element.width / 2.0, -element.height / 2.0), (element.width / 2.0, -element.height / 2.0), (element.width / 2.0, element.height / 2.0), (-element.width / 2.0, element.height / 2.0)]
        radians = math.radians(element.rotation)
        cosine, sine = math.cos(radians), math.sin(radians)
        points = [(element.x + px * cosine - py * sine, element.y + px * sine + py * cosine) for px, py in raw]
        return [points + [points[0]]]
    return []


def path_data_from_polygons(polygons: Iterable[Sequence[Point]]) -> str:
    parts: List[str] = []
    for polygon in polygons:
        points = list(polygon)
        if len(points) < 3:
            continue
        if points[0] == points[-1]:
            points = points[:-1]
        parts.append("M " + " L ".join("%.7g %.7g" % (x, y) for x, y in points) + " Z")
    return " ".join(parts)


def bounds_of_polygons(polygons: Iterable[Sequence[Point]]) -> Tuple[float, float, float, float]:
    points = [point for polygon in polygons for point in polygon]
    if not points:
        return 0.0, 0.0, 1.0, 1.0
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs), max(ys)


def _apply_svg_transform(polygons: List[List[Point]], text: str) -> List[List[Point]]:
    result = [list(polygon) for polygon in polygons]
    for name, body in re.findall(r"([A-Za-z]+)\s*\(([^)]*)\)", text or ""):
        values = [float(value) for value in NUMBER_RE.findall(body)]
        lowered = name.lower()
        if lowered == "translate" and values:
            dx, dy = values[0], values[1] if len(values) > 1 else 0.0
            result = [[(x + dx, y + dy) for x, y in polygon] for polygon in result]
        elif lowered == "scale" and values:
            sx, sy = values[0], values[1] if len(values) > 1 else values[0]
            result = [[(x * sx, y * sy) for x, y in polygon] for polygon in result]
        elif lowered == "rotate" and values:
            degrees = math.radians(values[0]); cx, cy = (values[1], values[2]) if len(values) > 2 else (0.0, 0.0)
            cosine, sine = math.cos(degrees), math.sin(degrees)
            result = [[(cx + (x - cx) * cosine - (y - cy) * sine, cy + (x - cx) * sine + (y - cy) * cosine) for x, y in polygon] for polygon in result]
    return result


def _sample_cubic(p0: Point, p1: Point, p2: Point, p3: Point, count: int) -> List[Point]:
    return [((1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t * t * p2[0] + t ** 3 * p3[0],
             (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t * t * p2[1] + t ** 3 * p3[1]) for t in (index / float(count) for index in range(count + 1))]


def _sample_quadratic(p0: Point, p1: Point, p2: Point, count: int) -> List[Point]:
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in (index / float(count) for index in range(count + 1))]
