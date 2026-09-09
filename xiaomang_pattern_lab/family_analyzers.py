"""Non-grid structural analyzers used by the PatternAnalyzer dispatcher."""
from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import fmean, median
from typing import Iterable, Optional

from ppg.foundation.models import Element

from .parametric import ElementPrototype, LocalOverride
from .parametric_families import AlongCurveParametricModel, FreeParametricModel, RadialParametricModel


@dataclass(frozen=True)
class RadialFitResult:
    model: RadialParametricModel
    center_x: float
    center_y: float
    count: int
    start_angle: float
    end_angle: float
    angle_step: float
    base_radius: float
    radius_range: float
    fit_score: float
    radial_residual: float
    angular_coverage: float
    diagnostics: dict


@dataclass(frozen=True)
class AlongCurveFitResult:
    model: AlongCurveParametricModel
    count: int
    average_spacing: float
    fit_score: float
    path_points: tuple[tuple[float, float], ...]
    spacing_residual: float
    diagnostics: dict
    eligible: bool = True
    intrinsic_dimension_score: float = 0.0


def _visible(elements: Iterable[Element]) -> list[Element]:
    return [item for item in elements if item.visible and item.width > 0 and item.height > 0]


def _prototype(elements: list[Element]) -> ElementPrototype:
    # A full dominant-shape clustering remains Grid's specialty.  For V1
    # Radial/Curve the first real Element is safer than turning an SVG path
    # into an invented circle.
    return ElementPrototype.from_element(elements[0])


class RadialAnalyzer:
    """Fit a common centre and a single angular sequence from Element centres."""

    def __init__(self, threshold: float = 0.72): self.threshold = threshold

    def analyze(self, elements: Iterable[Element]) -> Optional[RadialFitResult]:
        items = _visible(elements)
        if len(items) < 5: return None
        center = self._circle_center([(item.x, item.y) for item in items])
        if center is None: return None
        radii = [math.hypot(item.x - center[0], item.y - center[1]) for item in items]
        radius = median(radii)
        if radius < 1e-6: return None
        residual = math.sqrt(fmean((value - radius) ** 2 for value in radii)) / radius
        angles = sorted(math.atan2(item.y - center[1], item.x - center[0]) for item in items)
        gaps = [right - left for left, right in zip(angles, angles[1:])]
        gaps.append(angles[0] + 2 * math.pi - angles[-1])
        largest_gap = max(gaps)
        coverage = max(0.0, 2 * math.pi - largest_gap)
        # Circular spacing is measured only over expected active gaps.  An arc
        # keeps its large closing gap out of the consistency statistic.
        active = [gap for gap in gaps if gap < largest_gap * 0.80 or coverage > math.radians(300)]
        if not active: active = gaps
        step = median(active)
        step_error = math.sqrt(fmean((gap - step) ** 2 for gap in active)) / max(step, 1e-6)
        radius_score = max(0.0, 1.0 - residual / 0.16)
        spacing_score = max(0.0, 1.0 - step_error / 0.40)
        coverage_score = min(1.0, coverage / math.radians(100))
        score = 0.52 * radius_score + 0.34 * spacing_score + 0.14 * coverage_score
        if score < self.threshold: return None
        closed = coverage > math.radians(300)
        start = math.degrees(angles[0])
        end = start + (360.0 if closed else math.degrees(coverage))
        prototype = _prototype(items)
        model = RadialParametricModel(count=len(items), center_x=center[0], center_y=center[1], start_angle=start,
            end_angle=end, base_radius=radius, end_radius=radius, element_width=fmean(item.width for item in items),
            element_height=fmean(item.height for item in items), prototype=prototype)
        base = {item.id: item for item in model.generate(include_overrides=False)}
        # Associate observed positions by angle rank with generated index.
        observed = sorted(items, key=lambda item: math.atan2(item.y-center[1], item.x-center[0]))
        for index, item in enumerate(observed):
            identifier = model.element_id(index); expected = base[identifier]
            model.local_overrides[identifier] = LocalOverride(offset_x=item.x-expected.x, offset_y=item.y-expected.y,
                scale_x=item.width/max(expected.width, .01), scale_y=item.height/max(expected.height,.01), rotation_offset=item.rotation-expected.rotation)
        return RadialFitResult(model, center[0], center[1], len(items), start, end, math.degrees(step), radius,
            max(radii)-min(radii), score, residual * radius, math.degrees(coverage),
            {"radius_score": radius_score, "angle_spacing_score": spacing_score, "coverage_score": coverage_score})

    @staticmethod
    def _circle_center(points: list[tuple[float, float]]) -> Optional[tuple[float, float]]:
        # Linear least-squares solve of x²+y² + A*x + B*y + C = 0.
        sx=sxx=sy=syy=sxy=sbx=sby=sb=0.0
        for x,y in points:
            q=x*x+y*y; sx+=x; sy+=y; sxx+=x*x; syy+=y*y; sxy+=x*y; sbx+=x*q; sby+=y*q; sb+=q
        matrix=[[sxx,sxy,sx],[sxy,syy,sy],[sx,sy,float(len(points))]]; rhs=[-sbx,-sby,-sb]
        for col in range(3):
            pivot=max(range(col,3),key=lambda row:abs(matrix[row][col]))
            if abs(matrix[pivot][col]) < 1e-9:return None
            matrix[col],matrix[pivot]=matrix[pivot],matrix[col]; rhs[col],rhs[pivot]=rhs[pivot],rhs[col]
            factor=matrix[col][col]; matrix[col]=[v/factor for v in matrix[col]]; rhs[col]/=factor
            for row in range(3):
                if row==col:continue
                factor=matrix[row][col]; matrix[row]=[v-factor*w for v,w in zip(matrix[row],matrix[col])]; rhs[row]-=factor*rhs[col]
        return -rhs[0]/2.0,-rhs[1]/2.0


class AlongCurveAnalyzer:
    """Recognise an evenly-spaced one-dimensional sequence without Grid."""
    def __init__(self, threshold: float = 0.70):
        self.threshold = threshold
        self.last_diagnostics: dict = {}

    def analyze(self, elements: Iterable[Element]) -> Optional[AlongCurveFitResult]:
        items=_visible(elements)
        self.last_diagnostics = {}
        if len(items)<4:
            self.last_diagnostics = {"reason": "元素数量不足。", "intrinsic_dimension_score": 0.0}
            return None
        intrinsic_score, dimension_ratio, direction_score = self._intrinsic_dimension(items)
        # A curve is intrinsically one-dimensional.  A regular 2D lattice has
        # a greedy nearest-neighbour chain too, but its second covariance
        # eigenvalue is not small.  Reject it before chain scoring so Grid can
        # win on structural evidence rather than an arbitrary raw score.
        if intrinsic_score < 0.62 or dimension_ratio > 0.30:
            self.last_diagnostics = {
                "reason": "候选结构不是内在一维路径，二维 Grid 不进入 Along Curve。",
                "intrinsic_dimension_score": intrinsic_score,
                "dimension_ratio": dimension_ratio,
                "direction_consistency": direction_score,
            }
            return None
        ordered=self._chain(items)
        if ordered is None:
            self.last_diagnostics = {"reason": "无法建立连续路径。", "intrinsic_dimension_score": intrinsic_score}
            return None
        distances=[math.hypot(right.x-left.x,right.y-left.y) for left,right in zip(ordered,ordered[1:])]
        average=fmean(distances)
        if average<1e-6:
            self.last_diagnostics = {"reason": "路径间距过小。", "intrinsic_dimension_score": intrinsic_score}
            return None
        residual=math.sqrt(fmean((value-average)**2 for value in distances))/average
        # A chain that repeatedly shortcuts across its own path is likely an
        # unstructured cloud.  Require each segment to be near its endpoint's
        # local nearest neighbour scale.
        nearest=[]
        for item in items:
            values=sorted(math.hypot(item.x-other.x,item.y-other.y) for other in items if other is not item)
            nearest.append(values[0])
        local=median(nearest)
        continuity=sum(1 for value in distances if value <= local*1.7)/max(1,len(distances))
        spacing_score=max(0.0,1.0-residual/.45)
        # A ring is also a perfectly even nearest-neighbour chain once one
        # arbitrary link is cut.  It belongs to Radial, not Along Curve: its
        # two apparent chain ends are neighbours in the original geometry.
        closing_distance=math.hypot(ordered[0].x-ordered[-1].x, ordered[0].y-ordered[-1].y)
        closed_loop = closing_distance <= average * 1.55
        loop_score = 0.0 if closed_loop else 1.0
        # Preserve the established curve score semantics for genuine arcs/S
        # curves; the intrinsic gate above is what prevents a 2D lattice from
        # entering this family.  A small direction bonus is diagnostic only.
        score=min(1.0, .55*spacing_score+.33*continuity+.12*loop_score+
                  .03*max(0.0, intrinsic_score - 0.62) +
                  .02*max(0.0, direction_score - 0.70))
        if score<self.threshold:
            self.last_diagnostics = {"reason": "一维路径一致性分数低于阈值。", "score": score,
                                     "intrinsic_dimension_score": intrinsic_score, "dimension_ratio": dimension_ratio}
            return None
        points=tuple((item.x,item.y) for item in ordered)
        model=AlongCurveParametricModel(path_points=list(points),count=len(ordered),element_width=fmean(item.width for item in items),element_height=fmean(item.height for item in items),prototype=_prototype(items))
        base={item.id:item for item in model.generate(include_overrides=False)}
        for index,item in enumerate(ordered):
            expected=base[model.element_id(index)]; model.local_overrides[expected.id]=LocalOverride(offset_x=item.x-expected.x,offset_y=item.y-expected.y,scale_x=item.width/max(.01,expected.width),scale_y=item.height/max(.01,expected.height),rotation_offset=item.rotation-expected.rotation)
        self.last_diagnostics = {
            "spacing_score":spacing_score,"continuity_score":continuity,
            "closed_loop":closed_loop,"intrinsic_dimension_score":intrinsic_score,
            "dimension_ratio":dimension_ratio,"direction_consistency":direction_score,
        }
        return AlongCurveFitResult(model,len(items),average,score,points,residual*average,{
            "spacing_score":spacing_score,"continuity_score":continuity,
            "closed_loop":closed_loop,"intrinsic_dimension_score":intrinsic_score,
            "dimension_ratio":dimension_ratio,"direction_consistency":direction_score,
        }, True, intrinsic_score)

    @staticmethod
    def _intrinsic_dimension(items: list[Element]) -> tuple[float, float, float]:
        """Return (one_d_score, lambda2/lambda1, local_direction_score).

        This deliberately uses a tiny dependency-free 2x2 eigensolver.  The
        analyser must remain usable in the headless Pattern Lab runtime even
        when optional scientific packages are unavailable.
        """
        mean_x = fmean(item.x for item in items); mean_y = fmean(item.y for item in items)
        xx = fmean((item.x - mean_x) ** 2 for item in items)
        yy = fmean((item.y - mean_y) ** 2 for item in items)
        xy = fmean((item.x - mean_x) * (item.y - mean_y) for item in items)
        trace = xx + yy
        disc = math.sqrt(max(0.0, (xx - yy) ** 2 + 4.0 * xy * xy))
        largest = max(0.5 * (trace + disc), 1e-12)
        smallest = max(0.0, 0.5 * (trace - disc))
        ratio = min(1.0, smallest / largest)
        one_d = max(0.0, min(1.0, 1.0 - ratio / 0.30))
        # A one-dimensional neighbourhood has two nearly collinear nearest
        # vectors.  This secondary score protects against elongated clouds.
        collinear = []
        for item in items:
            neighbours = sorted(
                (other for other in items if other is not item),
                key=lambda other: (item.x - other.x) ** 2 + (item.y - other.y) ** 2,
            )[:2]
            if len(neighbours) < 2: continue
            a = (neighbours[0].x - item.x, neighbours[0].y - item.y)
            b = (neighbours[1].x - item.x, neighbours[1].y - item.y)
            na = math.hypot(*a); nb = math.hypot(*b)
            if na < 1e-9 or nb < 1e-9: continue
            # Opposite neighbours are collinear; use the absolute cross
            # product so direction sign does not matter.
            collinear.append(1.0 - min(1.0, abs(a[0] * b[1] - a[1] * b[0]) / (na * nb)))
        direction = fmean(collinear) if collinear else 0.0
        return one_d, ratio, direction

    @staticmethod
    def _chain(items:list[Element])->Optional[list[Element]]:
        # Endpoints are the farthest pair; greedily selecting the nearest
        # unvisited neighbour creates a deterministic polyline for arcs/S
        # curves without assuming screen X/Y ordering.
        first,last=max(((left,right) for index,left in enumerate(items) for right in items[index+1:]),key=lambda pair:(pair[0].x-pair[1].x)**2+(pair[0].y-pair[1].y)**2)
        result=[first]; remaining=[item for item in items if item is not first]
        while remaining:
            current=result[-1]; next_item=min(remaining,key=lambda item:(item.x-current.x)**2+(item.y-current.y)**2)
            result.append(next_item); remaining.remove(next_item)
        # Choose the orientation whose endpoint sits closest to farthest mate.
        if math.hypot(result[-1].x-last.x,result[-1].y-last.y)>math.hypot(result[0].x-last.x,result[0].y-last.y): result.reverse()
        return result


class FreeParametricFallback:
    """Always provides editable field parametrisation, never a failure."""
    def analyze(self,elements:Iterable[Element])->FreeParametricModel:
        return FreeParametricModel.from_elements(_visible(elements))
