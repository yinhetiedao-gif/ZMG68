"""Derived, millimetre-native 2D geometry for the future manufacturing backend.

This Gate U.5 adapter is deliberately not a repair or boolean layer.  It reads
the established final evaluation output, converts supported material areas to
normalised polygons/holes, and reports every omission explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from statistics import median
from typing import Iterable

from ppg.foundation.models import CircleElement, Element, EllipseElement, FilledRegionElement, PathElement, PatternDocument, RectElement
from ppg.foundation.region_geometry import filled_region_polygons

from .connectivity import final_material_polygons, polygons_touch_or_overlap
from .evaluation import evaluate_pattern_document
from .geometry_validation import GeometryValidationReport, GeometryValidator


Point = tuple[float, float]
Bounds = tuple[float, float, float, float]


@dataclass(frozen=True)
class ManufacturingPolygon:
    """One area body with an exterior boundary and zero or more holes, in mm."""

    source_element_id: str
    outer: tuple[Point, ...]
    holes: tuple[tuple[Point, ...], ...] = ()

    @property
    def bounds(self) -> Bounds:
        return _bounds(self.outer)


@dataclass(frozen=True)
class Manufacturing2DGeometry:
    """A non-persistent MultiPolygon-like manufacturing payload in millimetres."""

    polygons: tuple[ManufacturingPolygon, ...]
    units: str = "mm"
    bounds: Bounds | None = None

    @property
    def polygon_count(self) -> int:
        return len(self.polygons)


@dataclass(frozen=True)
class ManufacturingSkip:
    element_id: str
    reason: str
    message: str


@dataclass(frozen=True)
class ManufacturingConversionReport:
    input_count: int
    converted_count: int
    skipped_count: int
    skipped_invalid_count: int
    skipped_open_count: int
    skipped: tuple[ManufacturingSkip, ...]
    units: str
    bounds: Bounds | None
    warnings: tuple[str, ...] = ()
    topology_changed_element_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ManufacturingConversionResult:
    geometry: Manufacturing2DGeometry
    report: ManufacturingConversionReport


class ManufacturingGeometryAdapter:
    """Translate final Pattern Lab geometry to deterministic mm polygons only."""

    def __init__(self, *, curve_tolerance_mm: float = 0.05, epsilon_mm: float = 1e-6) -> None:
        self.curve_tolerance_mm = max(float(curve_tolerance_mm), 1e-5)
        self.epsilon_mm = max(float(epsilon_mm), 1e-9)

    def adapt_document(self, document: PatternDocument) -> ManufacturingConversionResult:
        """Evaluate once, then adapt only the transient final result to millimetres."""

        return self.adapt_evaluated_document(document, evaluate_pattern_document(document))

    def adapt_evaluated_document(
        self, document: PatternDocument, final_elements: Iterable[Element],
        *, validation_report: GeometryValidationReport | None = None,
    ) -> ManufacturingConversionResult:
        """Reuse a caller's final geometry while preserving document scale/missing-mm semantics."""

        final_elements = tuple(final_elements)
        scale = _mm_per_world_unit(document)
        if scale is None:
            skips = tuple(
                ManufacturingSkip(element.id, "missing_mm_mapping", "画布没有毫米映射，不能生成制造几何。")
                for element in final_elements if element.visible
            )
            report = ManufacturingConversionReport(
                input_count=len(skips), converted_count=0, skipped_count=len(skips),
                skipped_invalid_count=0, skipped_open_count=0, skipped=skips, units="mm", bounds=None,
                warnings=("当前 Canvas 未声明 mm 或 mm_per_unit；未猜测制造尺寸。",),
            )
            return ManufacturingConversionResult(Manufacturing2DGeometry((), "mm", None), report)
        # Gate T can be reused only when its world-space epsilon is identical.
        same_epsilon = math.isclose(self.epsilon_mm / scale, 1e-6, rel_tol=0.0, abs_tol=1e-15)
        return self.adapt_elements(final_elements, mm_per_world_unit=scale,
                                   validation_report=validation_report if same_epsilon else None)

    def adapt_elements(
        self, final_elements: Iterable[Element], *, mm_per_world_unit: float = 1.0,
        validation_report: GeometryValidationReport | None = None,
    ) -> ManufacturingConversionResult:
        """Adapt an already-evaluated final element sequence without mutating it."""

        scale = float(mm_per_world_unit)
        if not math.isfinite(scale) or scale <= 0:
            raise ValueError("mm_per_world_unit 必须为有限正数。")
        visible = [element for element in final_elements if element.visible]
        epsilon_world = self.epsilon_mm / scale
        tolerance_world = self.curve_tolerance_mm / scale
        validation = validation_report or GeometryValidator(epsilon=epsilon_world).validate_elements(visible)
        invalid_ids = {issue.element_id for issue in validation.issues if issue.severity == "error"}
        output: list[ManufacturingPolygon] = []
        converted_ids: list[str] = []
        skips: list[ManufacturingSkip] = []
        final_polygons: dict[str, tuple[tuple[Point, ...], ...]] = {}
        manufactured_by_id: dict[str, list[tuple[Point, ...]]] = {}

        for element in visible:
            if element.id in invalid_ids:
                skips.append(ManufacturingSkip(element.id, "skipped_invalid", "Gate T 校验失败，未转换该几何。"))
                continue
            if _is_unsupported_open_geometry(element):
                skips.append(ManufacturingSkip(element.id, "unsupported_open_geometry", "开放线/开放 Path 没有明确面积，未擅自赋予线宽。"))
                continue
            try:
                rings = self._rings_for_element(element, tolerance_world)
            except (TypeError, ValueError, ZeroDivisionError) as error:
                skips.append(ManufacturingSkip(element.id, "unsupported_geometry", "无法转换为制造面积：%s" % error))
                continue
            if not rings:
                skips.append(ManufacturingSkip(element.id, "unsupported_geometry", "该 Element 不包含可制造的面积边界。"))
                continue
            if not _uses_evenodd(element) and _rings_have_nesting(rings):
                # Gate U.5 deliberately does not infer complex SVG nonzero
                # winding semantics.  Refuse this one ambiguous region rather
                # than turn an intended hole into an apparently valid solid.
                skips.append(ManufacturingSkip(
                    element.id, "ambiguous_nonzero_fill",
                    "嵌套的 nonzero 填充语义尚未支持，未生成制造几何。",
                ))
                continue
            converted = _rings_to_manufacturing_polygons(
                element.id, _scale_rings(rings, scale), _uses_evenodd(element), self.epsilon_mm,
            )
            if not converted:
                skips.append(ManufacturingSkip(element.id, "unsupported_geometry", "标准化后没有保留有效制造边界。"))
                continue
            output.extend(converted)
            converted_ids.append(element.id)
            manufactured_by_id[element.id] = [polygon.outer for polygon in converted]
            final_polygons[element.id] = final_material_polygons(element)

        topology_changed = _topology_changes(final_polygons, manufactured_by_id, epsilon_world, self.epsilon_mm)
        warnings = () if not topology_changed else (
            "曲线近似后检测到连接关系变化；请调整曲线近似容差或检查相关几何。",
        )
        all_points = [point for polygon in output for point in polygon.outer]
        bounds = _bounds(all_points) if all_points else None
        skipped_invalid = sum(item.reason == "skipped_invalid" for item in skips)
        skipped_open = sum(item.reason == "unsupported_open_geometry" for item in skips)
        geometry = Manufacturing2DGeometry(tuple(output), "mm", bounds)
        report = ManufacturingConversionReport(
            input_count=len(visible), converted_count=len(converted_ids), skipped_count=len(skips),
            skipped_invalid_count=skipped_invalid, skipped_open_count=skipped_open,
            skipped=tuple(skips), units="mm", bounds=bounds, warnings=warnings,
            topology_changed_element_ids=tuple(sorted(topology_changed)),
        )
        return ManufacturingConversionResult(geometry, report)

    def _rings_for_element(self, element: Element, tolerance_world: float) -> tuple[tuple[Point, ...], ...]:
        if isinstance(element, (CircleElement, EllipseElement)):
            return (_ellipse_ring(element.x, element.y, element.width / 2.0, element.height / 2.0,
                                  element.rotation, tolerance_world),)
        if isinstance(element, RectElement):
            return (_rect_ring(element),)
        if isinstance(element, PathElement) and _is_area_path(element):
            samples = _curve_samples(tolerance_world, max(element.width, element.height))
            rings = filled_region_polygons(element, samples_per_curve=samples)  # type: ignore[arg-type]
            return tuple(tuple(ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring) for ring in rings)
        raise ValueError("不支持的非面积 Element 类型：%s" % element.type)


def _mm_per_world_unit(document: PatternDocument) -> float | None:
    if document.canvas.mm_per_unit is not None:
        return float(document.canvas.mm_per_unit)
    return 1.0 if str(document.canvas.unit).lower() == "mm" else None


def _is_area_path(element: PathElement) -> bool:
    if isinstance(element, FilledRegionElement):
        return bool(re.search(r"[Zz]", element.path_data or ""))
    fill = str(element.style.get("fill", "none")).strip().lower()
    return fill not in {"", "none", "transparent"} and bool(re.search(r"[Zz]", element.path_data or ""))


def _is_unsupported_open_geometry(element: Element) -> bool:
    if not isinstance(element, PathElement):
        return False
    return not _is_area_path(element)


def _uses_evenodd(element: Element) -> bool:
    return str(element.style.get("fill-rule", "")).strip().lower() == "evenodd"


def _ellipse_ring(cx: float, cy: float, radius_x: float, radius_y: float, rotation: float, tolerance: float) -> tuple[Point, ...]:
    segments = _curve_samples(tolerance, max(radius_x, radius_y) * 2.0)
    radians = math.radians(rotation)
    cosine, sine = math.cos(radians), math.sin(radians)
    return tuple(
        (cx + radius_x * math.cos(2 * math.pi * index / segments) * cosine - radius_y * math.sin(2 * math.pi * index / segments) * sine,
         cy + radius_x * math.cos(2 * math.pi * index / segments) * sine + radius_y * math.sin(2 * math.pi * index / segments) * cosine)
        for index in range(segments)
    )


def _curve_samples(tolerance: float, diameter: float) -> int:
    radius = max(diameter / 2.0, tolerance)
    ratio = max(-1.0, min(1.0, 1.0 - tolerance / radius))
    angle = max(2.0 * math.acos(ratio), math.pi / 180.0)
    segments = max(8, min(1024, int(math.ceil((2.0 * math.pi) / angle))))
    # Preserve the cardinal points: tangent circles on horizontal/vertical
    # axes retain their design-level touch after curve polygonisation.
    return int(math.ceil(segments / 4.0) * 4)


def _rect_ring(element: RectElement) -> tuple[Point, ...]:
    local = ((-element.width / 2, -element.height / 2), (element.width / 2, -element.height / 2),
             (element.width / 2, element.height / 2), (-element.width / 2, element.height / 2))
    radians = math.radians(element.rotation)
    cosine, sine = math.cos(radians), math.sin(radians)
    return tuple((element.x + x * cosine - y * sine, element.y + x * sine + y * cosine) for x, y in local)


def _scale_rings(rings: Iterable[tuple[Point, ...]], scale: float) -> tuple[tuple[Point, ...], ...]:
    return tuple(tuple((x * scale, y * scale) for x, y in ring) for ring in rings)


def _rings_to_manufacturing_polygons(
    element_id: str, rings: tuple[tuple[Point, ...], ...], evenodd: bool, epsilon: float,
) -> tuple[ManufacturingPolygon, ...]:
    cleaned = [ring for ring in (_normalise_ring(ring, epsilon) for ring in rings) if len(ring) >= 3 and abs(_signed_area(ring)) > epsilon * epsilon]
    if not evenodd:
        return tuple(ManufacturingPolygon(element_id, _oriented(ring, clockwise=False), ()) for ring in cleaned)
    records: list[dict] = []
    for ring in sorted(cleaned, key=lambda value: abs(_signed_area(value)), reverse=True):
        parents = [index for index, item in enumerate(records) if _point_in_polygon(ring[0], item["ring"])]
        parent = min(parents, key=lambda index: abs(_signed_area(records[index]["ring"]))) if parents else None
        depth = (records[parent]["depth"] + 1) if parent is not None else 0
        records.append({"ring": ring, "parent": parent, "depth": depth})
    result: list[ManufacturingPolygon] = []
    outer_indexes: dict[int, int] = {}
    for index, item in enumerate(records):
        if item["depth"] % 2 == 0:
            outer_indexes[index] = len(result)
            result.append(ManufacturingPolygon(element_id, _oriented(item["ring"], clockwise=False), ()))
    for index, item in enumerate(records):
        if item["depth"] % 2 == 1:
            ancestor = item["parent"]
            while ancestor is not None and records[ancestor]["depth"] % 2 == 1:
                ancestor = records[ancestor]["parent"]
            if ancestor is not None and ancestor in outer_indexes:
                target = outer_indexes[ancestor]
                current = result[target]
                result[target] = ManufacturingPolygon(
                    current.source_element_id, current.outer,
                    current.holes + (_oriented(item["ring"], clockwise=True),),
                )
    return tuple(result)


def _rings_have_nesting(rings: tuple[tuple[Point, ...], ...]) -> bool:
    for index, ring in enumerate(rings):
        if not ring:
            continue
        for other_index, other in enumerate(rings):
            if index != other_index and len(other) >= 3 and _point_in_polygon(ring[0], other):
                return True
    return False


def _normalise_ring(ring: Iterable[Point], epsilon: float) -> tuple[Point, ...]:
    result: list[Point] = []
    for point in ring:
        if not result or math.hypot(point[0] - result[-1][0], point[1] - result[-1][1]) > epsilon:
            result.append((float(point[0]), float(point[1])))
    if len(result) > 1 and math.hypot(result[0][0] - result[-1][0], result[0][1] - result[-1][1]) <= epsilon:
        result.pop()
    # Raster-derived straight sides are often encoded as cubic paths.  After
    # rotation their many sampled points are only *nearly* collinear in float
    # arithmetic; earcut may then make zero-area cap triangles.  Discard only
    # a middle point that lies on the segment between its neighbours within
    # the existing manufacturing-coordinate epsilon.  Corners and actual
    # curvature are preserved.
    changed = True
    while changed and len(result) > 3:
        changed = False
        for index in range(len(result)):
            start, middle, end = result[index - 1], result[index], result[(index + 1) % len(result)]
            dx, dy = end[0] - start[0], end[1] - start[1]
            length_squared = dx * dx + dy * dy
            if length_squared <= epsilon * epsilon:
                continue
            projection = ((middle[0] - start[0]) * dx + (middle[1] - start[1]) * dy) / length_squared
            if not 0.0 <= projection <= 1.0:
                continue
            distance = abs((middle[0] - start[0]) * dy - (middle[1] - start[1]) * dx) / math.sqrt(length_squared)
            if distance <= epsilon:
                result.pop(index)
                changed = True
                break
    return tuple(result)


def _oriented(ring: tuple[Point, ...], *, clockwise: bool) -> tuple[Point, ...]:
    is_clockwise = _signed_area(ring) < 0
    return tuple(reversed(ring)) if is_clockwise != clockwise else ring


def _signed_area(ring: tuple[Point, ...]) -> float:
    return 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]))


def _bounds(points: Iterable[Point]) -> Bounds:
    values = tuple(points)
    xs, ys = zip(*values)
    return min(xs), min(ys), max(xs), max(ys)


def _point_in_polygon(point: Point, ring: tuple[Point, ...]) -> bool:
    x, y = point
    inside = False
    for start, end in zip(ring, ring[1:] + ring[:1]):
        if (start[1] > y) != (end[1] > y):
            crossing = (end[0] - start[0]) * (y - start[1]) / (end[1] - start[1]) + start[0]
            if crossing > x:
                inside = not inside
    return inside


def _topology_changes(
    final_by_id: dict[str, tuple[tuple[Point, ...], ...]], manufactured_by_id: dict[str, list[tuple[Point, ...]]],
    final_epsilon: float, manufactured_epsilon: float,
) -> set[str]:
    identifiers = sorted(set(final_by_id) & set(manufactured_by_id))
    changed: set[str] = set()
    # Compare only pairs that could connect in either representation.  A
    # disconnected 500-element matrix must not trigger 124,750 expensive
    # polygon-pair checks merely to prove that it remains disconnected.
    final_bounds = {identifier: _bounds(point for ring in final_by_id[identifier] for point in ring) for identifier in identifiers}
    manufactured_bounds = {identifier: _bounds(point for ring in manufactured_by_id[identifier] for point in ring) for identifier in identifiers}
    candidates = _spatial_candidate_pairs(final_bounds, final_epsilon) | _spatial_candidate_pairs(manufactured_bounds, manufactured_epsilon)
    for left_id, right_id in candidates:
        final_connected = polygons_touch_or_overlap(final_by_id[left_id], final_by_id[right_id], final_epsilon)
        manufactured_connected = polygons_touch_or_overlap(manufactured_by_id[left_id], manufactured_by_id[right_id], manufactured_epsilon)
        if final_connected != manufactured_connected:
            changed.update((left_id, right_id))
    return changed


def _spatial_candidate_pairs(bounds_by_id: dict[str, Bounds], epsilon: float) -> set[tuple[str, str]]:
    if len(bounds_by_id) < 2:
        return set()
    spans = [max(bounds[2] - bounds[0], bounds[3] - bounds[1]) for bounds in bounds_by_id.values()]
    bucket = max(float(median(spans)), epsilon * 4.0)
    cells: dict[tuple[int, int], list[str]] = {}
    for identifier, (min_x, min_y, max_x, max_y) in bounds_by_id.items():
        for cell_x in range(math.floor((min_x - epsilon) / bucket), math.floor((max_x + epsilon) / bucket) + 1):
            for cell_y in range(math.floor((min_y - epsilon) / bucket), math.floor((max_y + epsilon) / bucket) + 1):
                cells.setdefault((cell_x, cell_y), []).append(identifier)
    candidates: set[tuple[str, str]] = set()
    for identifiers in cells.values():
        for index, left in enumerate(identifiers):
            for right in identifiers[index + 1:]:
                first, second = sorted((left, right))
                left_bounds, right_bounds = bounds_by_id[first], bounds_by_id[second]
                if not (left_bounds[2] < right_bounds[0] - epsilon or right_bounds[2] < left_bounds[0] - epsilon
                        or left_bounds[3] < right_bounds[1] - epsilon or right_bounds[3] < left_bounds[1] - epsilon):
                    candidates.add((first, second))
    return candidates
