"""General 2D Lattice Detection for Matrix Parameterization V3.

The only input is a collection of real ``PatternDocument.elements``.  The
detector intentionally treats every visible Element as an anchor and ignores
its shape and size until a stable pair of lattice bases has been found:

``P(row, column) = origin + column * BasisU + row * BasisV``.

This makes a diagonal halftone, a skewed rectangular matrix, or a cropped
section of a lattice a Grid for the same reason as a horizontal dot matrix:
two repeatable neighbour vectors explain its *centres*.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
import math
from statistics import fmean, median
from typing import Iterable, Optional

from ppg.foundation.models import CircleElement, EllipseElement, Element, FilledRegionElement, PathElement, RectElement

from .parametric import (
    ElementAnchor,
    ElementPrototype,
    GridParametricModel,
    LocalOverride,
    SizeGradientMode,
    SizeGradientModifier,
)
from .family_analyzers import AlongCurveAnalyzer, AlongCurveFitResult, FreeParametricFallback, RadialAnalyzer, RadialFitResult


class AnalysisTolerance(str, Enum):
    STRICT = "strict"
    STANDARD = "standard"
    LENIENT = "lenient"


@dataclass(frozen=True)
class _TolerancePolicy:
    assignment_fraction: float
    minimum_occupancy: float
    minimum_inlier_ratio: float


_POLICY = {
    AnalysisTolerance.STRICT: _TolerancePolicy(0.16, 0.70, 0.94),
    # Standard mode accepts a genuinely partial/cropped lattice, but does not
    # promote a sparse silhouette that happens to sit on a latent grid into a
    # parameterized matrix.  Use lenient mode when an intentional mask removes
    # more than half of the cells.
    AnalysisTolerance.STANDARD: _TolerancePolicy(0.25, 0.50, 0.85),
    AnalysisTolerance.LENIENT: _TolerancePolicy(0.34, 0.15, 0.72),
}


@dataclass(frozen=True)
class _AnchorSample:
    element: Element
    anchor: ElementAnchor

    @property
    def x(self) -> float: return self.anchor.centroid_x

    @property
    def y(self) -> float: return self.anchor.centroid_y

    @property
    def width(self) -> float: return self.anchor.bbox_width

    @property
    def height(self) -> float: return self.anchor.bbox_height

    @property
    def rotation(self) -> float: return self.anchor.rotation


@dataclass(frozen=True)
class SizeGradientFit:
    modifier: SizeGradientModifier
    residual_error: float
    baseline_error: float
    score: float


# A V3 name that communicates the correct separation.  Keep the former name
# in exported results for V2 compatibility.
SizeFieldFit = SizeGradientFit


@dataclass(frozen=True)
class GridAnalysisDebug:
    candidate_count: int = 0
    inlier_count: int = 0
    rows: int = 0
    columns: int = 0
    basis_angle_u: float = 0.0
    basis_angle_v: float = 90.0
    spacing_u: float = 0.0
    spacing_v: float = 0.0
    position_residual: float = float("inf")
    direction_score: float = 0.0
    spacing_score: float = 0.0
    position_score: float = 0.0
    occupancy_ratio: float = 0.0
    inlier_ratio: float = 0.0
    shape_cluster_ratio: float = 0.0
    size_field_score: float = 0.0
    grid_fit_score: float = 0.0
    tolerance: str = AnalysisTolerance.STANDARD.value
    failure_reason: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass(frozen=True)
class GridFitResult:
    model: GridParametricModel
    rows: int
    columns: int
    spacing_x: float
    spacing_y: float
    element_width: float
    element_height: float
    rotation: float
    offset_x: float
    offset_y: float
    fit_score: float
    residual_error: float
    occupancy: float
    inlier_ratio: float = 1.0
    shape_cluster_ratio: float = 1.0
    prototype_kind: str = "circle"
    missing_cell_count: int = 0
    missing_cell_ids: tuple[str, ...] = ()
    gradient: Optional[SizeGradientFit] = None
    debug: Optional[GridAnalysisDebug] = None

    @property
    def score(self) -> float: return self.fit_score

    @property
    def position_error(self) -> float: return self.residual_error

    @property
    def basis_u(self) -> tuple[float, float]: return self.model.basis_u

    @property
    def basis_v(self) -> tuple[float, float]: return self.model.basis_v


@dataclass
class _LatticeCandidate:
    basis_u: tuple[float, float]
    basis_v: tuple[float, float]
    origin: tuple[float, float]
    assigned: list[tuple[_AnchorSample, int, int, float]]
    rows: int
    columns: int
    occupancy: float
    inlier_ratio: float
    residual: float
    direction_score: float
    spacing_score: float
    position_score: float
    score: float


class SizeFieldAnalyzer:
    """Fit size after Grid positions are known; never veto a Grid decision."""

    def analyze(self, assigned: list[tuple[_AnchorSample, int, int]], model: GridParametricModel) -> Optional[SizeGradientFit]:
        if len(assigned) < 6:
            return None
        sizes = [(sample.width + sample.height) / 2.0 for sample, _, _ in assigned]
        baseline = fmean(sizes)
        baseline_error = math.sqrt(fmean((size - baseline) ** 2 for size in sizes))
        if baseline_error < 0.08:
            return None
        candidates: list[SizeGradientFit] = []
        modes = (SizeGradientMode.HORIZONTAL, SizeGradientMode.VERTICAL, SizeGradientMode.CENTER_TO_EDGE,
                 SizeGradientMode.EDGE_TO_CENTER, SizeGradientMode.RADIAL, SizeGradientMode.ELLIPTICAL_RADIAL)
        positions = {element.id: element for element in model.generate(include_overrides=False)}
        # Data-driven centers are deliberately modest: centroid covers usual
        # matrices, extrema cover off-centre size fields without an optimiser.
        centers = [(model.offset_x, model.offset_y)]
        largest = max(zip(sizes, assigned), key=lambda value: value[0])[1][0]
        smallest = min(zip(sizes, assigned), key=lambda value: value[0])[1][0]
        centers.extend([(largest.x, largest.y), (smallest.x, smallest.y)])
        for mode in modes:
            possible_centers = centers if mode in (SizeGradientMode.RADIAL, SizeGradientMode.ELLIPTICAL_RADIAL) else [(0.0, 0.0)]
            for center_x, center_y in possible_centers:
                radius_x = max(max(abs(sample.x - center_x) for sample, _, _ in assigned), 0.01)
                radius_y = max(max(abs(sample.y - center_y) for sample, _, _ in assigned), 0.01)
                # A circular radius uses the maximum radial reach, an ellipse
                # uses x/y spans independently.  Both keep all factors in 0..1.
                circular_radius = max(math.hypot(sample.x - center_x, sample.y - center_y) for sample, _, _ in assigned)
                modifier = SizeGradientModifier(mode=mode, center_x=center_x, center_y=center_y,
                                                radius_x=max(0.01, circular_radius if mode is SizeGradientMode.RADIAL else radius_x),
                                                radius_y=radius_y, falloff=1.0, strength=1.0)
                factors = [self._factor(model, modifier, row, column, positions[model.element_id(row, column)]) for _, row, column in assigned]
                intercept, slope = self._linear_fit(factors, sizes)
                predicted = [intercept + slope * factor for factor in factors]
                residual = math.sqrt(fmean((actual - expected) ** 2 for actual, expected in zip(sizes, predicted)))
                modifier.min_size, modifier.max_size = max(0.01, intercept), max(0.01, intercept + slope)
                candidates.append(SizeGradientFit(modifier, residual, baseline_error, max(0.0, 1.0 - residual / max(baseline_error, 0.01))))
        best = min(candidates, key=lambda item: item.residual_error)
        if best.residual_error >= baseline_error * 0.72 or abs(best.modifier.max_size - best.modifier.min_size) < 0.20:
            return None
        return best

    @staticmethod
    def _factor(model: GridParametricModel, modifier: SizeGradientModifier, row: int, column: int, element: Element) -> float:
        """Return precisely the same 0..1 field used by Grid generation.

        Fitting an unnormalised row number is statistically valid, but storing
        its intercept/slope as ``min_size`` / ``max_size`` would make the
        rebuilt document differ from the observed image.  Keep the analysis
        and modifier evaluation in the same coordinate convention instead.
        """
        if modifier.mode is SizeGradientMode.HORIZONTAL:
            return column / max(1, model.columns - 1)
        if modifier.mode is SizeGradientMode.VERTICAL:
            return row / max(1, model.rows - 1)
        if modifier.mode in (SizeGradientMode.CENTER_TO_EDGE, SizeGradientMode.EDGE_TO_CENTER):
            local_x = (column - (model.columns - 1) / 2.0) * model.spacing_x
            local_y = (row - (model.rows - 1) / 2.0) * model.spacing_y
            max_x = max(abs(-((model.columns - 1) * model.spacing_x) / 2.0 - modifier.center_x), abs(((model.columns - 1) * model.spacing_x) / 2.0 - modifier.center_x), 0.01)
            max_y = max(abs(-((model.rows - 1) * model.spacing_y) / 2.0 - modifier.center_y), abs(((model.rows - 1) * model.spacing_y) / 2.0 - modifier.center_y), 0.01)
            value = min(1.0, math.hypot((local_x - modifier.center_x) / max_x, (local_y - modifier.center_y) / max_y))
            return 1.0 - value if modifier.mode is SizeGradientMode.EDGE_TO_CENTER else value
        if modifier.mode is SizeGradientMode.RADIAL:
            return math.hypot(element.x - modifier.center_x, element.y - modifier.center_y) / modifier.radius_x
        return math.hypot((element.x - modifier.center_x) / modifier.radius_x, (element.y - modifier.center_y) / modifier.radius_y)

    @staticmethod
    def _linear_fit(factors: list[float], values: list[float]) -> tuple[float, float]:
        mean_factor, mean_value = fmean(factors), fmean(values)
        denominator = sum((item - mean_factor) ** 2 for item in factors)
        if denominator < 1e-9: return mean_value, 0.0
        slope = sum((factor - mean_factor) * (value - mean_value) for factor, value in zip(factors, values)) / denominator
        return mean_value - slope * mean_factor, slope


# Retained public name for V2 imports/tests.
SizeGradientAnalyzer = SizeFieldAnalyzer


class GridAnalyzer:
    """RANSAC-style General 2D Lattice detector using Element anchor centres."""

    def __init__(self, *, threshold: float = 0.75, tolerance: AnalysisTolerance | str = AnalysisTolerance.STANDARD):
        self.threshold = float(threshold)
        self.tolerance = AnalysisTolerance(tolerance)
        self.size_gradient_analyzer = SizeFieldAnalyzer()
        self.last_debug = GridAnalysisDebug(tolerance=self.tolerance.value)

    def analyze(self, elements: Iterable[Element]) -> Optional[GridFitResult]:
        samples = [item for element in elements if (item := self._anchor_sample(element)) is not None]
        if len(samples) < 4:
            self.last_debug = GridAnalysisDebug(candidate_count=len(samples), tolerance=self.tolerance.value, failure_reason="可见 Element 少于 4 个，无法建立二维格子。")
            return None
        candidate = self._best_lattice(samples)
        if candidate is None:
            self.last_debug = GridAnalysisDebug(candidate_count=len(samples), tolerance=self.tolerance.value, failure_reason="邻域方向直方图未找到两个稳定且不共线的基向量。")
            return None
        prototype, shape_ratio = self._dominant_prototype(samples)
        model = GridParametricModel(
            rows=candidate.rows, columns=candidate.columns,
            spacing_x=math.hypot(*candidate.basis_u), spacing_y=math.hypot(*candidate.basis_v),
            element_width=fmean(item.width for item, _, _, _ in candidate.assigned),
            element_height=fmean(item.height for item, _, _, _ in candidate.assigned),
            rotation=math.degrees(math.atan2(candidate.basis_u[1], candidate.basis_u[0])),
            # GridParametricModel stores its offset at the visual centre, not
            # at cell 0/0.  Convert RANSAC origin accordingly.
            offset_x=candidate.origin[0] + (candidate.columns - 1) * candidate.basis_u[0] / 2 + (candidate.rows - 1) * candidate.basis_v[0] / 2,
            offset_y=candidate.origin[1] + (candidate.columns - 1) * candidate.basis_u[1] / 2 + (candidate.rows - 1) * candidate.basis_v[1] / 2,
            lock_aspect=prototype.kind == "circle", prototype=prototype,
            basis_u_vector=candidate.basis_u, basis_v_vector=candidate.basis_v,
        ).normalized()
        assigned = [(sample, row, column) for sample, row, column, _ in candidate.assigned]
        gradient = self.size_gradient_analyzer.analyze(assigned, model)
        if gradient is not None:
            model.size_gradient = gradient.modifier
        base = {element.id: element for element in model.generate(include_overrides=False)}
        occupied: set[tuple[int, int]] = set()
        for sample, row, column, _ in candidate.assigned:
            identifier = model.element_id(row, column)
            generated = base[identifier]
            model.local_overrides[identifier] = LocalOverride(
                offset_x=sample.x - generated.x, offset_y=sample.y - generated.y,
                scale_x=sample.width / max(generated.width, 0.01), scale_y=sample.height / max(generated.height, 0.01),
                rotation_offset=sample.rotation - generated.rotation, visible=None,
            )
            occupied.add((row, column))
        missing = []
        for row in range(model.rows):
            for column in range(model.columns):
                if (row, column) not in occupied:
                    identifier = model.element_id(row, column)
                    model.local_overrides[identifier] = LocalOverride(visible=False)
                    missing.append(identifier)
        debug = GridAnalysisDebug(
            candidate_count=len(samples), inlier_count=len(candidate.assigned), rows=model.rows, columns=model.columns,
            basis_angle_u=model.basis_angle_u, basis_angle_v=model.basis_angle_v,
            spacing_u=model.spacing_x, spacing_v=model.spacing_y, position_residual=candidate.residual,
            direction_score=candidate.direction_score, spacing_score=candidate.spacing_score,
            position_score=candidate.position_score, occupancy_ratio=candidate.occupancy,
            inlier_ratio=candidate.inlier_ratio, shape_cluster_ratio=shape_ratio,
            size_field_score=gradient.score if gradient else 0.0, grid_fit_score=candidate.score,
            tolerance=self.tolerance.value,
        )
        policy = _POLICY[self.tolerance]
        if candidate.occupancy < policy.minimum_occupancy or candidate.inlier_ratio < policy.minimum_inlier_ratio or candidate.score < self.threshold:
            reasons = []
            if candidate.occupancy < policy.minimum_occupancy: reasons.append("占用率 %.1f%% 低于阈值 %.1f%%" % (candidate.occupancy * 100, policy.minimum_occupancy * 100))
            if candidate.inlier_ratio < policy.minimum_inlier_ratio: reasons.append("内点率 %.1f%% 低于阈值 %.1f%%" % (candidate.inlier_ratio * 100, policy.minimum_inlier_ratio * 100))
            if candidate.score < self.threshold: reasons.append("位置格子分数 %.3f 低于阈值 %.3f" % (candidate.score, self.threshold))
            self.last_debug = GridAnalysisDebug(**{**debug.to_dict(), "failure_reason": "；".join(reasons)})
            return None
        self.last_debug = debug
        return GridFitResult(model=model, rows=model.rows, columns=model.columns, spacing_x=model.spacing_x, spacing_y=model.spacing_y,
                             element_width=model.element_width, element_height=model.element_height, rotation=model.basis_angle_u,
                             offset_x=model.offset_x, offset_y=model.offset_y, fit_score=candidate.score,
                             residual_error=candidate.residual, occupancy=candidate.occupancy,
                             inlier_ratio=candidate.inlier_ratio, shape_cluster_ratio=shape_ratio,
                             prototype_kind=prototype.kind, missing_cell_count=len(missing), missing_cell_ids=tuple(missing),
                             gradient=gradient, debug=debug)

    def _best_lattice(self, samples: list[_AnchorSample]) -> Optional[_LatticeCandidate]:
        vectors = self._knn_vectors(samples)
        directions = self._direction_candidates(vectors)
        policy = _POLICY[self.tolerance]
        best: Optional[_LatticeCandidate] = None
        # Test direction pairs; RANSAC origins then selects the best inlier
        # explanation.  This is intentionally deterministic for reproducible
        # projects and tests.
        for index, (candidate_angle_u, candidate_spacing_u, _) in enumerate(directions):
            for candidate_angle_v, candidate_spacing_v, _ in directions[index + 1:]:
                # Never mutate the outer-loop candidate: otherwise selecting a
                # horizontal U for one pair corrupts the next pair and can
                # accidentally skip the true U/V combination.
                angle_u, spacing_u = candidate_angle_u, candidate_spacing_u
                angle_v, spacing_v = candidate_angle_v, candidate_spacing_v
                separation = self._angle_difference(angle_u, angle_v)
                if separation < math.radians(12) or separation > math.radians(168):
                    continue
                # Stable ID convention: where a familiar screen-horizontal
                # direction exists it is Basis U / columns.  This preserves
                # V1/V2 row/column meaning; arbitrary skew still uses two
                # equally valid lattice directions.
                if self._horizontal_distance(angle_v) < self._horizontal_distance(angle_u):
                    angle_u, angle_v, spacing_u, spacing_v = angle_v, angle_u, spacing_v, spacing_u
                u = spacing_u * math.cos(angle_u), spacing_u * math.sin(angle_u)
                v = spacing_v * math.cos(angle_v), spacing_v * math.sin(angle_v)
                if abs(self._cross(u, v)) < max(spacing_u, spacing_v) ** 2 * 0.12:
                    continue
                for origin_sample in self._seed_samples(samples):
                    candidate = self._fit_from_seed(samples, vectors, u, v, (origin_sample.x, origin_sample.y), policy)
                    if candidate and (best is None or candidate.score > best.score):
                        best = candidate
        return best

    @staticmethod
    def _seed_samples(samples: list[_AnchorSample], maximum: int = 36) -> list[_AnchorSample]:
        """Bound deterministic RANSAC seeds without privilege for a fixture.

        Every lattice point is a valid origin, so evenly sampling source order
        is sufficient and avoids a quadratic-looking cost on dense imports.
        """
        if len(samples) <= maximum:
            return samples
        step = (len(samples) - 1) / float(maximum - 1)
        return [samples[int(round(index * step))] for index in range(maximum)]

    def _fit_from_seed(self, samples: list[_AnchorSample], vectors: list[tuple[float, float]], u: tuple[float, float], v: tuple[float, float], seed: tuple[float, float], policy: _TolerancePolicy) -> Optional[_LatticeCandidate]:
        origin, basis_u, basis_v = seed, u, v
        # Alternating integer assignment and affine least squares is a small
        # deterministic robust fit.  It gives the RANSAC seed a chance to
        # absorb rasterisation jitter without ever using Element size.
        for _ in range(3):
            raw = self._integer_assignments(samples, origin, basis_u, basis_v)
            if len(raw) < 4:
                return None
            fitted = self._fit_affine(raw)
            if fitted is None:
                return None
            origin, basis_u, basis_v = fitted
        raw = self._integer_assignments(samples, origin, basis_u, basis_v)
        spacing_u, spacing_v = math.hypot(*basis_u), math.hypot(*basis_v)
        limit = max(0.25, min(spacing_u, spacing_v) * policy.assignment_fraction)
        # One physical element may map to one lattice cell.  Retain the closest
        # sample in a collision, treating others as outliers rather than
        # inventing duplicate cells.
        unique: dict[tuple[int, int], tuple[_AnchorSample, int, int, float]] = {}
        for sample, column, row, error in raw:
            if error > limit:
                continue
            key = (row, column)
            current = unique.get(key)
            if current is None or error < current[3]:
                unique[key] = (sample, row, column, error)
        if len(unique) < 4:
            return None
        min_row, max_row = min(key[0] for key in unique), max(key[0] for key in unique)
        min_col, max_col = min(key[1] for key in unique), max(key[1] for key in unique)
        # Shift to stable, non-negative document IDs and update the lattice
        # origin to logical cell 0/0.
        origin = (origin[0] + min_col * basis_u[0] + min_row * basis_v[0], origin[1] + min_col * basis_u[1] + min_row * basis_v[1])
        assigned = [(sample, row - min_row, col - min_col, error) for sample, row, col, error in unique.values()]
        rows, columns = max_row - min_row + 1, max_col - min_col + 1
        occupancy = len(assigned) / float(rows * columns)
        inlier_ratio = len(assigned) / len(samples)
        residual = fmean(item[3] for item in assigned)
        direction_score, spacing_score = self._vector_consistency(vectors, basis_u, basis_v)
        position_score = max(0.0, 1.0 - min(1.0, residual / max(limit * 1.6, 0.01)))
        # Occupancy is informative but not the structural gate: a cropped or
        # deliberately masked lattice can be sparse.  Direction, spacing,
        # position and inliers are the decisive factors.
        # A KNN set necessarily includes diagonal neighbours as well as the
        # two fundamental directions.  Direction/spacing evidence therefore
        # establishes the candidate pair, while the fitted lattice residual
        # and inlier rate are the dominant acceptance proof.
        structural = 0.04 * direction_score + 0.04 * spacing_score + 0.55 * position_score + 0.37 * inlier_ratio
        score = structural * (0.70 + 0.30 * occupancy)
        return _LatticeCandidate(basis_u, basis_v, origin, assigned, rows, columns, occupancy, inlier_ratio, residual, direction_score, spacing_score, position_score, score)

    @staticmethod
    def _integer_assignments(samples: list[_AnchorSample], origin: tuple[float, float], u: tuple[float, float], v: tuple[float, float]) -> list[tuple[_AnchorSample, int, int, float]]:
        determinant = GridAnalyzer._cross(u, v)
        if abs(determinant) < 1e-9:
            return []
        result = []
        for sample in samples:
            dx, dy = sample.x - origin[0], sample.y - origin[1]
            column_value = (dx * v[1] - dy * v[0]) / determinant
            row_value = (u[0] * dy - u[1] * dx) / determinant
            column, row = int(round(column_value)), int(round(row_value))
            px, py = origin[0] + column * u[0] + row * v[0], origin[1] + column * u[1] + row * v[1]
            result.append((sample, column, row, math.hypot(sample.x - px, sample.y - py)))
        return result

    @staticmethod
    def _fit_affine(assignments: list[tuple[_AnchorSample, int, int, float]]) -> Optional[tuple[tuple[float, float], tuple[float, float], tuple[float, float]]]:
        # Solve X = o + c*u + r*v separately for x and y using normal equations.
        matrix = [[0.0] * 3 for _ in range(3)]
        rhs_x, rhs_y = [0.0] * 3, [0.0] * 3
        for sample, column, row, _ in assignments:
            values = (1.0, float(column), float(row))
            for i in range(3):
                rhs_x[i] += values[i] * sample.x; rhs_y[i] += values[i] * sample.y
                for j in range(3): matrix[i][j] += values[i] * values[j]
        solved_x, solved_y = GridAnalyzer._solve_3x3(matrix, rhs_x), GridAnalyzer._solve_3x3(matrix, rhs_y)
        if solved_x is None or solved_y is None:
            return None
        return (solved_x[0], solved_y[0]), (solved_x[1], solved_y[1]), (solved_x[2], solved_y[2])

    @staticmethod
    def _solve_3x3(matrix: list[list[float]], rhs: list[float]) -> Optional[list[float]]:
        augmented = [list(row) + [rhs[index]] for index, row in enumerate(matrix)]
        for column in range(3):
            pivot = max(range(column, 3), key=lambda row: abs(augmented[row][column]))
            if abs(augmented[pivot][column]) < 1e-9:
                return None
            augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
            scale = augmented[column][column]
            augmented[column] = [value / scale for value in augmented[column]]
            for row in range(3):
                if row == column: continue
                factor = augmented[row][column]
                augmented[row] = [value - factor * pivot_value for value, pivot_value in zip(augmented[row], augmented[column])]
        return [augmented[row][3] for row in range(3)]

    @staticmethod
    def _knn_vectors(samples: list[_AnchorSample], neighbours: int = 8) -> list[tuple[float, float]]:
        result = []
        for sample in samples:
            closest = sorted((other for other in samples if other is not sample), key=lambda other: math.hypot(other.x - sample.x, other.y - sample.y))[:neighbours]
            result.extend((other.x - sample.x, other.y - sample.y) for other in closest)
        return [vector for vector in result if math.hypot(*vector) > 1e-6]

    @staticmethod
    def _direction_candidates(vectors: list[tuple[float, float]]) -> list[tuple[float, float, int]]:
        """Histogram neighbour directions modulo π, then estimate base spacing."""
        bin_size = math.radians(6.0)
        buckets: dict[int, list[tuple[float, float]]] = {}
        for vector in vectors:
            angle = math.atan2(vector[1], vector[0]) % math.pi
            buckets.setdefault(int(angle / bin_size) % int(math.ceil(math.pi / bin_size)), []).append(vector)
        candidates = []
        for bucket, items in buckets.items():
            # double-angle mean handles the π direction equivalence.
            sine = fmean(math.sin(2 * (math.atan2(y, x) % math.pi)) for x, y in items)
            cosine = fmean(math.cos(2 * (math.atan2(y, x) % math.pi)) for x, y in items)
            angle = (math.atan2(sine, cosine) / 2) % math.pi
            magnitudes = sorted(math.hypot(x, y) for x, y in items)
            spacing = median(magnitudes[:max(1, (len(magnitudes) + 1) // 2)])
            candidates.append((angle, spacing, len(items)))
        # Adjacent bins that represent one noisy direction are merged by
        # keeping the strongest candidate; non-adjacent diagonals survive.
        candidates.sort(key=lambda item: item[2], reverse=True)
        selected = []
        for item in candidates:
            if all(GridAnalyzer._angle_difference(item[0], kept[0]) > math.radians(8) for kept in selected):
                selected.append(item)
            if len(selected) >= 10: break
        return selected

    @staticmethod
    def _vector_consistency(vectors: list[tuple[float, float]], u: tuple[float, float], v: tuple[float, float]) -> tuple[float, float]:
        angle_u, angle_v = math.atan2(u[1], u[0]) % math.pi, math.atan2(v[1], v[0]) % math.pi
        lengths = (math.hypot(*u), math.hypot(*v))
        direction_hits, spacing_hits = 0, 0
        for vector in vectors:
            angle, length = math.atan2(vector[1], vector[0]) % math.pi, math.hypot(*vector)
            direction_index = 0 if GridAnalyzer._angle_difference(angle, angle_u) <= GridAnalyzer._angle_difference(angle, angle_v) else 1
            if GridAnalyzer._angle_difference(angle, (angle_u, angle_v)[direction_index]) <= math.radians(10):
                direction_hits += 1
                ratio = length / max(lengths[direction_index], 1e-9)
                if abs(ratio - round(ratio)) <= 0.18:
                    spacing_hits += 1
        total = max(1, len(vectors))
        return direction_hits / total, spacing_hits / total

    @staticmethod
    def _cross(a: tuple[float, float], b: tuple[float, float]) -> float: return a[0] * b[1] - a[1] * b[0]

    @staticmethod
    def _angle_difference(left: float, right: float) -> float:
        difference = abs((left - right) % math.pi)
        return min(difference, math.pi - difference)

    @staticmethod
    def _horizontal_distance(angle: float) -> float:
        """Angular distance to the screen x-axis, modulo π."""
        return min(abs(angle), abs(math.pi - angle))

    @staticmethod
    def _anchor_sample(element: Element) -> Optional[_AnchorSample]:
        if not element.visible or element.width <= 0 or element.height <= 0: return None
        if isinstance(element, CircleElement): area = math.pi * (element.width / 2.0) ** 2
        elif isinstance(element, EllipseElement): area = math.pi * element.width * element.height / 4.0
        else: area = float(element.metadata.get("recognized_area", element.width * element.height))
        return _AnchorSample(element, ElementAnchor(element.id, float(element.x), float(element.y), float(element.width), float(element.height), max(0.0, area), float(element.rotation), element.type))

    @staticmethod
    def _dominant_prototype(samples: list[_AnchorSample]) -> tuple[ElementPrototype, float]:
        keys = [GridAnalyzer._prototype_key(sample.element) for sample in samples]
        dominant, count = Counter(keys).most_common(1)[0]
        candidates = [sample for sample, key in zip(samples, keys) if key == dominant]
        median_aspect = median(sample.anchor.aspect_ratio for sample in candidates)
        representative = min(candidates, key=lambda sample: abs(sample.anchor.aspect_ratio - median_aspect))
        return ElementPrototype.from_element(representative.element), count / len(samples)

    @staticmethod
    def _prototype_key(element: Element) -> str:
        if isinstance(element, CircleElement): return "circle"
        if isinstance(element, EllipseElement): return "ellipse"
        if isinstance(element, RectElement): return "rect"
        if isinstance(element, FilledRegionElement): return "filled_region"
        if isinstance(element, PathElement): return "path"
        return element.type


@dataclass(frozen=True)
class AnalysisResult:
    """One auditable Pattern Family candidate.

    ``parameters`` is deliberately a plain serialisable dictionary so a UI can
    show every candidate without learning the Python type behind it.
    """
    family: str
    confidence: float
    parameters: dict
    diagnostics: dict
    model: object | None = None
    fit: object | None = None


@dataclass(frozen=True)
class MultiFamilyAnalysis:
    candidates: tuple[AnalysisResult, ...]
    recommended: AnalysisResult | None
    fallback: AnalysisResult

    def candidate(self, family: str) -> AnalysisResult:
        return next(item for item in self.candidates if item.family == family)


class PatternAnalyzer:
    """Document-only dispatcher for Grid, Radial, Curve and free fields.

    The compatibility ``analyze`` method still returns a Grid fit for old
    Matrix callers.  Product code should use ``analyze_families`` so Grid is
    no longer the entire parameterisation system.
    """

    def __init__(self, *, grid_threshold: float = 0.75, tolerance: AnalysisTolerance | str = AnalysisTolerance.STANDARD):
        self.grid = GridAnalyzer(threshold=grid_threshold, tolerance=tolerance)
        self.radial = RadialAnalyzer()
        self.along_curve = AlongCurveAnalyzer()
        self.free = FreeParametricFallback()
        self.last_multi: MultiFamilyAnalysis | None = None

    @property
    def last_debug(self) -> GridAnalysisDebug: return self.grid.last_debug

    def set_tolerance(self, tolerance: AnalysisTolerance | str) -> None:
        self.grid.tolerance = AnalysisTolerance(tolerance)

    def analyze(self, elements: Iterable[Element]) -> Optional[GridFitResult]:
        return self.grid.analyze(elements)

    def analyze_families(self, elements: Iterable[Element]) -> MultiFamilyAnalysis:
        # Materialise once. No candidate can inspect filename/preset/image
        # state; all evidence comes from the actual editable Element list.
        source = list(elements)
        grid_fit = self.grid.analyze(source)
        radial_fit = self.radial.analyze(source)
        curve_fit = self.along_curve.analyze(source)
        grid = AnalysisResult("grid", grid_fit.fit_score if grid_fit else 0.0,
            {"rows": grid_fit.rows, "columns": grid_fit.columns, "spacing_u": grid_fit.spacing_x, "spacing_v": grid_fit.spacing_y,
             "basis_u": list(grid_fit.basis_u), "basis_v": list(grid_fit.basis_v)} if grid_fit else {},
            grid_fit.debug.to_dict() if grid_fit and grid_fit.debug else self.grid.last_debug.to_dict(), grid_fit.model if grid_fit else None, grid_fit)
        radial = AnalysisResult("radial", radial_fit.fit_score if radial_fit else 0.0,
            {"center_x": radial_fit.center_x, "center_y": radial_fit.center_y, "count": radial_fit.count, "start_angle": radial_fit.start_angle,
             "end_angle": radial_fit.end_angle, "angle_step": radial_fit.angle_step, "base_radius": radial_fit.base_radius, "radius_range": radial_fit.radius_range} if radial_fit else {},
            radial_fit.diagnostics if radial_fit else {"reason": "未检测到共同中心、半径和角度间距。"}, radial_fit.model if radial_fit else None, radial_fit)
        curve = AnalysisResult("along_curve", curve_fit.fit_score if curve_fit else 0.0,
            {"count": curve_fit.count, "average_spacing": curve_fit.average_spacing, "path_points": [list(point) for point in curve_fit.path_points]} if curve_fit else {},
            curve_fit.diagnostics if curve_fit else (self.along_curve.last_diagnostics or {"reason": "未检测到稳定的一维连续路径。"}),
            curve_fit.model if curve_fit else None, curve_fit)
        candidates = (grid, radial, curve)
        eligible = [item for item in candidates if item.model is not None and item.confidence >= 0.72]
        recommended = max(eligible, key=lambda item: item.confidence) if eligible else None
        fallback_model = self.free.analyze(source)
        fallback = AnalysisResult("free", 1.0, {"element_count": len(fallback_model.base_elements)},
            {"message": "未检测到可靠的整体生成结构，可使用自由参数化。"}, fallback_model, fallback_model)
        self.last_multi = MultiFamilyAnalysis(candidates, recommended, fallback)
        return self.last_multi
