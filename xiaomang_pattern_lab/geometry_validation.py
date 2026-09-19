"""Read-only minimum manufacturing-geometry checks for final 2D output.

Gate T deliberately validates the *evaluated* result rather than a project's
editable source.  It is therefore safe to call before a later 2D-to-3D build:
this module never repairs, bakes, serializes, or writes a PatternDocument.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import re
from typing import Iterable, Optional

from ppg.foundation.models import (
    CircleElement,
    Element,
    EllipseElement,
    FilledRegionElement,
    PathElement,
    PatternDocument,
    RectElement,
)
from ppg.foundation.region_geometry import filled_region_polygons

from .evaluation import evaluate_pattern_document


Point = tuple[float, float]
Bounds = tuple[float, float, float, float]


@dataclass(frozen=True)
class GeometryValidationIssue:
    """One non-mutating observation about a final geometry element."""

    issue_type: str
    severity: str
    element_id: str
    message: str
    bounds: Optional[Bounds] = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class GeometryValidationReport:
    """A compact report suitable for a later manufacturing UI or exporter."""

    checked_count: int
    valid_count: int
    warning_count: int
    error_count: int
    issues: tuple[GeometryValidationIssue, ...] = ()

    @property
    def is_valid(self) -> bool:
        return self.error_count == 0

    def issues_for(self, element_id: str) -> tuple[GeometryValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.element_id == element_id)


class GeometryValidator:
    """Validate material boundaries without changing their construction.

    ``epsilon`` is deliberately explicit and relative checks are not guessed:
    higher manufacturing layers can choose a unit-aware tolerance later.  The
    Gate T core default only protects against numerically collapsed geometry.
    """

    def __init__(self, *, epsilon: float = 1e-6) -> None:
        self.epsilon = max(float(epsilon), 1e-12)

    def validate_document(self, document: PatternDocument) -> GeometryValidationReport:
        """Run the existing single evaluator and inspect its transient output."""

        return self.validate_elements(evaluate_pattern_document(document))

    def validate_elements(self, elements: Iterable[Element]) -> GeometryValidationReport:
        issues: list[GeometryValidationIssue] = []
        checked = 0
        valid = 0
        for element in elements:
            if not element.visible:
                continue
            checked += 1
            before = len(issues)
            self._validate_element(element, issues)
            if len(issues) == before:
                valid += 1
        errors = sum(issue.severity == "error" for issue in issues)
        warnings = sum(issue.severity == "warning" for issue in issues)
        return GeometryValidationReport(
            checked_count=checked,
            valid_count=valid,
            warning_count=warnings,
            error_count=errors,
            issues=tuple(issues),
        )

    def _validate_element(self, element: Element, issues: list[GeometryValidationIssue]) -> None:
        bounds = _element_bounds(element)
        values = [element.x, element.y, element.width, element.height, element.rotation]
        if isinstance(element, PathElement):
            values.extend([element.base_x, element.base_y, element.base_width, element.base_height])
        if not all(_finite(value) for value in values):
            self._issue(issues, "invalid_geometry", element, "元素包含 NaN、Infinity 或非法坐标。", bounds)
            return
        if element.width <= self.epsilon or element.height <= self.epsilon:
            label = "圆点半径" if isinstance(element, CircleElement) else "宽度或高度"
            self._issue(issues, "degenerate_geometry", element, "%s接近零，不能形成制造边界。" % label, bounds)
            return

        if isinstance(element, (CircleElement, EllipseElement, RectElement)):
            # These primitives intrinsically describe a closed, filled region
            # after their finite positive dimension check above.
            return
        if not isinstance(element, PathElement):
            self._issue(issues, "invalid_geometry", element, "不支持的二维几何类型，无法构造制造边界。", bounds)
            return

        material = _is_filled_material(element)
        explicitly_closed = bool(re.search(r"[Zz]", element.path_data or ""))
        if not material:
            # An open contour is valid design geometry.  Only reject an open
            # line if it has no measurable length, never merely because it is
            # not a solid boundary.
            if _open_path_length(element.path_data) <= self.epsilon:
                self._issue(issues, "degenerate_geometry", element, "开放线长度接近零。", bounds)
            return
        if not explicitly_closed:
            self._issue(issues, "open_contour", element, "实心制造区域必须使用闭合轮廓。", bounds)
            return
        try:
            polygons = filled_region_polygons(element)  # PathElement is duck-typed by the helper.
        except Exception as error:  # malformed SVG must be reported, never escape as an app crash
            self._issue(issues, "invalid_geometry", element, "无法构造实心边界：%s" % error, bounds)
            return
        if not polygons:
            self._issue(issues, "invalid_geometry", element, "闭合 Path 未产生可用制造边界。", bounds)
            return
        for polygon in polygons:
            self._validate_polygon(element, polygon, issues, bounds)

    def _validate_polygon(
        self, element: Element, polygon: Iterable[Point], issues: list[GeometryValidationIssue], bounds: Bounds
    ) -> None:
        raw = list(polygon)
        if not raw or not all(_finite(x) and _finite(y) for x, y in raw):
            self._issue(issues, "invalid_geometry", element, "轮廓包含非法坐标。", bounds)
            return
        points = _remove_terminal_and_adjacent_duplicates(raw, self.epsilon)
        if len(points) < 3:
            self._issue(issues, "degenerate_geometry", element, "轮廓没有足够的独立顶点。", bounds)
            return
        # A bow-tie has zero signed area too.  Test topology first so the
        # report explains the real manufacturing failure rather than hiding it
        # behind a secondary zero-area symptom.
        if _has_self_intersection(points, self.epsilon):
            self._issue(issues, "self_intersection", element, "闭合轮廓存在自相交，不能直接制造。", bounds)
            return
        area = abs(_signed_area(points))
        if area <= self.epsilon * self.epsilon:
            self._issue(issues, "degenerate_geometry", element, "闭合轮廓面积接近零。", bounds, {"area": area})
            return

    @staticmethod
    def _issue(
        issues: list[GeometryValidationIssue], issue_type: str, element: Element,
        message: str, bounds: Bounds, metadata: Optional[dict] = None,
    ) -> None:
        issues.append(GeometryValidationIssue(
            issue_type=issue_type, severity="error", element_id=element.id,
            message=message, bounds=bounds, metadata=metadata or {},
        ))


def _finite(value: float) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _element_bounds(element: Element) -> Bounds:
    return (
        element.x - element.width / 2.0,
        element.y - element.height / 2.0,
        element.x + element.width / 2.0,
        element.y + element.height / 2.0,
    )


def _is_filled_material(element: PathElement) -> bool:
    if isinstance(element, FilledRegionElement):
        return True
    fill = str(element.style.get("fill", "none")).strip().lower()
    return fill not in {"", "none", "transparent"}


def _open_path_length(path_data: str) -> float:
    """Conservative length probe for ordinary M/L open paths.

    It intentionally never claims a legal curved path is invalid.  When SVG
    commands do not expose coordinate pairs cleanly (for example H/V/A), zero
    cannot be proven and the open path remains valid at this core stage.
    """

    pairs = re.findall(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*[ ,]\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)", path_data or "")
    if len(pairs) < 2:
        return math.inf
    points = [(float(x), float(y)) for x, y in pairs]
    return sum(math.hypot(bx - ax, by - ay) for (ax, ay), (bx, by) in zip(points, points[1:]))


def _remove_terminal_and_adjacent_duplicates(points: list[Point], epsilon: float) -> list[Point]:
    if len(points) > 1 and _same_point(points[0], points[-1], epsilon):
        points = points[:-1]
    result: list[Point] = []
    for point in points:
        if not result or not _same_point(result[-1], point, epsilon):
            result.append(point)
    if len(result) > 1 and _same_point(result[0], result[-1], epsilon):
        result.pop()
    return result


def _same_point(a: Point, b: Point, epsilon: float) -> bool:
    return math.hypot(a[0] - b[0], a[1] - b[1]) <= epsilon


def _signed_area(points: list[Point]) -> float:
    return 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]))


def _has_self_intersection(points: list[Point], epsilon: float) -> bool:
    count = len(points)
    for first in range(count):
        a, b = points[first], points[(first + 1) % count]
        for second in range(first + 1, count):
            # Adjacent edges share a legal endpoint.  First/last are adjacent
            # as well because this is a closed ring.
            if second in {first, (first + 1) % count} or (first == 0 and second == count - 1):
                continue
            c, d = points[second], points[(second + 1) % count]
            if _segments_intersect(a, b, c, d, epsilon):
                return True
    return False


def _segments_intersect(a: Point, b: Point, c: Point, d: Point, epsilon: float) -> bool:
    def orient(p: Point, q: Point, r: Point) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    ab_c, ab_d = orient(a, b, c), orient(a, b, d)
    cd_a, cd_b = orient(c, d, a), orient(c, d, b)
    # Collinear overlap between non-adjacent edges also creates an ambiguous
    # boundary, so it is treated as self-intersection.
    if abs(ab_c) <= epsilon and _on_segment(a, b, c, epsilon): return True
    if abs(ab_d) <= epsilon and _on_segment(a, b, d, epsilon): return True
    if abs(cd_a) <= epsilon and _on_segment(c, d, a, epsilon): return True
    if abs(cd_b) <= epsilon and _on_segment(c, d, b, epsilon): return True
    return (ab_c > epsilon) != (ab_d > epsilon) and (cd_a > epsilon) != (cd_b > epsilon)


def _on_segment(a: Point, b: Point, point: Point, epsilon: float) -> bool:
    return (
        min(a[0], b[0]) - epsilon <= point[0] <= max(a[0], b[0]) + epsilon
        and min(a[1], b[1]) - epsilon <= point[1] <= max(a[1], b[1]) + epsilon
    )
