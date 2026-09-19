"""Read-only minimum connected-component analysis for final 2D geometry.

Gate U-Core intentionally answers only one manufacturing question: how many
separate material pieces exist in the evaluated design?  It is not a persistent
PatternGraph and it never inserts connectors, repairs paths, or mutates a
PatternDocument.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import median
from typing import Iterable

from ppg.foundation.models import Element, FilledRegionElement, PathElement, PatternDocument
from ppg.foundation.region_geometry import element_polygons, filled_region_polygons

from .evaluation import evaluate_pattern_document
from .geometry_validation import GeometryValidator


Point = tuple[float, float]
Bounds = tuple[float, float, float, float]


@dataclass(frozen=True)
class ConnectivityComponent:
    component_id: str
    element_ids: tuple[str, ...]
    element_count: int
    bounds: Bounds | None = None


@dataclass(frozen=True)
class ConnectivityReport:
    total_element_count: int
    component_count: int
    isolated_element_ids: tuple[str, ...]
    isolated_count: int
    largest_component_size: int
    skipped_invalid_count: int
    components: tuple[ConnectivityComponent, ...]
    candidate_pair_count: int = 0
    connected_pair_count: int = 0


@dataclass(frozen=True)
class _GeometryUnit:
    element: Element
    polygons: tuple[tuple[Point, ...], ...]
    bounds: Bounds


class ConnectivityAnalyzer:
    """Determine components from overlap/touch only, with a replaceable broad phase."""

    def __init__(self, *, epsilon: float = 1e-6, bucket_size: float | None = None) -> None:
        self.epsilon = max(float(epsilon), 1e-12)
        self.bucket_size = None if bucket_size is None else max(float(bucket_size), self.epsilon)

    def analyze_document(self, document: PatternDocument) -> ConnectivityReport:
        """Analyze the transient result of the one established Evaluate pipeline."""

        return self.analyze_elements(evaluate_pattern_document(document))

    def analyze_elements(self, elements: Iterable[Element]) -> ConnectivityReport:
        final_elements = [element for element in elements if element.visible]
        validation = GeometryValidator(epsilon=self.epsilon).validate_elements(final_elements)
        invalid_ids = {issue.element_id for issue in validation.issues if issue.severity == "error"}
        units: list[_GeometryUnit] = []
        skipped = 0
        for element in final_elements:
            if element.id in invalid_ids:
                skipped += 1
                continue
            try:
                polygons = final_material_polygons(element)
            except Exception:
                skipped += 1
                continue
            if not polygons:
                skipped += 1
                continue
            points = [point for polygon in polygons for point in polygon]
            if not points or not all(math.isfinite(x) and math.isfinite(y) for x, y in points):
                skipped += 1
                continue
            units.append(_GeometryUnit(element, polygons, _bounds(points)))

        parent = list(range(len(units)))
        degree = [0] * len(units)
        candidates = self._candidate_pairs(units)
        connected_pairs = 0
        for left, right in candidates:
            if _units_connect(units[left], units[right], self.epsilon):
                connected_pairs += 1
                degree[left] += 1
                degree[right] += 1
                _union(parent, left, right)

        grouped: dict[int, list[int]] = {}
        for index in range(len(units)):
            grouped.setdefault(_find(parent, index), []).append(index)
        ordered_groups = sorted(grouped.values(), key=lambda indexes: min(units[index].element.id for index in indexes))
        components = tuple(
            ConnectivityComponent(
                component_id="component-%d" % (component_index + 1),
                element_ids=tuple(sorted(units[index].element.id for index in indexes)),
                element_count=len(indexes),
                bounds=_bounds([point for index in indexes for polygon in units[index].polygons for point in polygon]),
            )
            for component_index, indexes in enumerate(ordered_groups)
        )
        isolated = tuple(sorted(units[index].element.id for index, value in enumerate(degree) if value == 0))
        return ConnectivityReport(
            total_element_count=len(units),
            component_count=len(components),
            isolated_element_ids=isolated,
            isolated_count=len(isolated),
            largest_component_size=max((component.element_count for component in components), default=0),
            skipped_invalid_count=skipped,
            components=components,
            candidate_pair_count=len(candidates),
            connected_pair_count=connected_pairs,
        )

    def _candidate_pairs(self, units: list[_GeometryUnit]) -> list[tuple[int, int]]:
        """Spatial-hash overlapping bounding boxes before precise geometry work."""

        if not units:
            return []
        bucket = self.bucket_size or _suggest_bucket_size(units, self.epsilon)
        cells: dict[tuple[int, int], list[int]] = {}
        for index, unit in enumerate(units):
            min_x, min_y, max_x, max_y = unit.bounds
            start_x, end_x = math.floor((min_x - self.epsilon) / bucket), math.floor((max_x + self.epsilon) / bucket)
            start_y, end_y = math.floor((min_y - self.epsilon) / bucket), math.floor((max_y + self.epsilon) / bucket)
            for cell_x in range(start_x, end_x + 1):
                for cell_y in range(start_y, end_y + 1):
                    cells.setdefault((cell_x, cell_y), []).append(index)
        pairs: set[tuple[int, int]] = set()
        for indexes in cells.values():
            for offset, left in enumerate(indexes):
                for right in indexes[offset + 1:]:
                    if _bounds_overlap_or_touch(units[left].bounds, units[right].bounds, self.epsilon):
                        pairs.add((min(left, right), max(left, right)))
        return sorted(pairs)


def final_material_polygons(element: Element) -> tuple[tuple[Point, ...], ...]:
    """Small final-geometry adapter; no type logic escapes this boundary."""

    if isinstance(element, (FilledRegionElement,)):
        polygons = filled_region_polygons(element)
    elif isinstance(element, PathElement):
        # Gate T has already established that only a valid, filled, closed Path
        # reaches this point.  The local helper accepts its matching geometry.
        polygons = filled_region_polygons(element)  # type: ignore[arg-type]
    else:
        polygons = element_polygons(element, samples=48)
    normalized: list[tuple[Point, ...]] = []
    for polygon in polygons:
        points = tuple(polygon[:-1] if len(polygon) > 1 and polygon[0] == polygon[-1] else polygon)
        if len(points) >= 3:
            normalized.append(points)
    return tuple(normalized)


def _suggest_bucket_size(units: list[_GeometryUnit], epsilon: float) -> float:
    spans = [max(unit.bounds[2] - unit.bounds[0], unit.bounds[3] - unit.bounds[1]) for unit in units]
    return max(float(median(spans)), epsilon * 4.0)


def _bounds(points: Iterable[Point]) -> Bounds:
    values = list(points)
    xs, ys = zip(*values)
    return min(xs), min(ys), max(xs), max(ys)


def _bounds_overlap_or_touch(left: Bounds, right: Bounds, epsilon: float) -> bool:
    return not (
        left[2] < right[0] - epsilon or right[2] < left[0] - epsilon
        or left[3] < right[1] - epsilon or right[3] < left[1] - epsilon
    )


def _units_connect(left: _GeometryUnit, right: _GeometryUnit, epsilon: float) -> bool:
    for polygon_left in left.polygons:
        for polygon_right in right.polygons:
            if _polygons_connect(polygon_left, polygon_right, epsilon):
                return True
    return False


def _polygons_connect(left: tuple[Point, ...], right: tuple[Point, ...], epsilon: float) -> bool:
    for index, point_a in enumerate(left):
        next_a = left[(index + 1) % len(left)]
        for second, point_b in enumerate(right):
            next_b = right[(second + 1) % len(right)]
            if _segments_intersect_or_touch(point_a, next_a, point_b, next_b, epsilon):
                return True
    return _point_in_or_on_polygon(left[0], right, epsilon) or _point_in_or_on_polygon(right[0], left, epsilon)


def polygons_touch_or_overlap(
    left: Iterable[tuple[Point, ...]], right: Iterable[tuple[Point, ...]], epsilon: float = 1e-6,
) -> bool:
    """Public, read-only final-geometry query shared by manufacturing adapters."""

    return any(_polygons_connect(first, second, epsilon) for first in left for second in right)


def _segments_intersect_or_touch(a: Point, b: Point, c: Point, d: Point, epsilon: float) -> bool:
    def orient(p: Point, q: Point, r: Point) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    ab_c, ab_d = orient(a, b, c), orient(a, b, d)
    cd_a, cd_b = orient(c, d, a), orient(c, d, b)
    if abs(ab_c) <= epsilon and _on_segment(a, b, c, epsilon): return True
    if abs(ab_d) <= epsilon and _on_segment(a, b, d, epsilon): return True
    if abs(cd_a) <= epsilon and _on_segment(c, d, a, epsilon): return True
    if abs(cd_b) <= epsilon and _on_segment(c, d, b, epsilon): return True
    return (ab_c > epsilon) != (ab_d > epsilon) and (cd_a > epsilon) != (cd_b > epsilon)


def _point_in_or_on_polygon(point: Point, polygon: tuple[Point, ...], epsilon: float) -> bool:
    x, y = point
    inside = False
    for index, start in enumerate(polygon):
        end = polygon[(index + 1) % len(polygon)]
        if abs((end[0] - start[0]) * (y - start[1]) - (end[1] - start[1]) * (x - start[0])) <= epsilon and _on_segment(start, end, point, epsilon):
            return True
        if (start[1] > y) != (end[1] > y):
            crossing_x = (end[0] - start[0]) * (y - start[1]) / (end[1] - start[1]) + start[0]
            if crossing_x >= x - epsilon:
                inside = not inside
    return inside


def _on_segment(a: Point, b: Point, point: Point, epsilon: float) -> bool:
    return (
        min(a[0], b[0]) - epsilon <= point[0] <= max(a[0], b[0]) + epsilon
        and min(a[1], b[1]) - epsilon <= point[1] <= max(a[1], b[1]) + epsilon
    )


def _find(parent: list[int], index: int) -> int:
    while parent[index] != index:
        parent[index] = parent[parent[index]]
        index = parent[index]
    return index


def _union(parent: list[int], left: int, right: int) -> None:
    root_left, root_right = _find(parent, left), _find(parent, right)
    if root_left != root_right:
        parent[max(root_left, root_right)] = min(root_left, root_right)
