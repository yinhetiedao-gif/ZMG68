"""无 Rhino 依赖的二维几何核心。

保留原 Rhino 原型的关键逻辑：等弧长采样、经内部/外部测试的法线，
以及凹轮廓的放射线安全裁剪。所有计算单位均为内部 mm。
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .model import PatternSettings, Point

EPS = 1e-8


@dataclass(frozen=True)
class RadialItem:
    start: Point
    end: Point
    radius: float
    width: float
    direction: Point = (0.0, 1.0)


def distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def sub(a: Point, b: Point) -> Point:
    return a[0] - b[0], a[1] - b[1]


def add(a: Point, b: Point) -> Point:
    return a[0] + b[0], a[1] + b[1]


def mul(a: Point, scalar: float) -> Point:
    return a[0] * scalar, a[1] * scalar


def unit(v: Point) -> Point | None:
    length = math.hypot(v[0], v[1])
    return None if length < EPS else (v[0] / length, v[1] / length)


def cross(a: Point, b: Point) -> float:
    return a[0] * b[1] - a[1] * b[0]


def clean_contour(points: list[Point]) -> list[Point]:
    cleaned: list[Point] = []
    for point in points:
        if not cleaned or distance(point, cleaned[-1]) > EPS:
            cleaned.append(point)
    if len(cleaned) > 1 and distance(cleaned[0], cleaned[-1]) < EPS:
        cleaned.pop()
    if len(cleaned) < 3:
        raise ValueError("轮廓至少需要三个不同的点。")
    if abs(polygon_area(cleaned)) < EPS:
        raise ValueError("轮廓面积过小，无法生成纹样。")
    return cleaned


def polygon_area(points: list[Point]) -> float:
    return sum(points[i][0] * points[(i + 1) % len(points)][1] - points[(i + 1) % len(points)][0] * points[i][1] for i in range(len(points))) * 0.5


def point_inside(point: Point, polygon: list[Point]) -> bool:
    """射线法；边界按内部处理，便于外法线选择。"""
    x, y = point
    inside = False
    for index, a in enumerate(polygon):
        b = polygon[(index + 1) % len(polygon)]
        if abs(cross(sub(point, a), sub(b, a))) < EPS and min(a[0], b[0]) - EPS <= x <= max(a[0], b[0]) + EPS and min(a[1], b[1]) - EPS <= y <= max(a[1], b[1]) + EPS:
            return True
        if (a[1] > y) != (b[1] > y):
            hit_x = (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]
            if x < hit_x:
                inside = not inside
    return inside


def has_self_intersection(points: list[Point]) -> bool:
    def intersects(a: Point, b: Point, c: Point, d: Point) -> bool:
        def orient(p: Point, q: Point, r: Point) -> float: return cross(sub(q, p), sub(r, p))
        o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
        return (o1 * o2 < -EPS and o3 * o4 < -EPS)
    count = len(points)
    for i in range(count):
        for j in range(i + 1, count):
            if j in (i, (i + 1) % count) or i == (j + 1) % count:
                continue
            if intersects(points[i], points[(i + 1) % count], points[j], points[(j + 1) % count]):
                return True
    return False


def sample_evenly(points: list[Point], count: int) -> list[tuple[Point, Point]]:
    if count < 3:
        raise ValueError("数量至少为 3。")
    lengths = [distance(points[i], points[(i + 1) % len(points)]) for i in range(len(points))]
    total = sum(lengths)
    if total < EPS:
        raise ValueError("轮廓长度无效。")
    result: list[tuple[Point, Point]] = []
    edge, accumulated = 0, 0.0
    for n in range(count):
        target = total * n / count
        while edge < len(lengths) - 1 and accumulated + lengths[edge] < target - EPS:
            accumulated += lengths[edge]
            edge += 1
        ratio = (target - accumulated) / max(lengths[edge], EPS)
        a, b = points[edge], points[(edge + 1) % len(points)]
        result.append((add(a, mul(sub(b, a), ratio)), unit(sub(b, a)) or (1.0, 0.0)))
    return result


def sample_at_fractions(points: list[Point], fractions: list[float]) -> list[tuple[Point, Point]]:
    """以 0~1 的弧长位置采样，用于随机与渐变分布。"""
    lengths = [distance(points[i], points[(i + 1) % len(points)]) for i in range(len(points))]
    total = sum(lengths); result = []
    for fraction in fractions:
        target = min(.999999, max(0.0, fraction)) * total; edge = 0; passed = 0.0
        while edge < len(lengths)-1 and passed + lengths[edge] < target:
            passed += lengths[edge]; edge += 1
        a, b = points[edge], points[(edge+1) % len(points)]; ratio = (target-passed) / max(lengths[edge], EPS)
        result.append((add(a,mul(sub(b,a),ratio)),unit(sub(b,a)) or (1.0,0.0)))
    return result


def distribute_samples(points: list[Point], count: int, mode: str, rng: random.Random) -> list[tuple[Point, Point]]:
    if mode == "均匀": return sample_evenly(points, count)
    if mode == "随机":
        fractions = sorted(max(0.0,min(.999999,(i+rng.uniform(-.47,.47))/count)) for i in range(count))
        return sample_at_fractions(points, fractions)
    if mode == "渐变":
        # 由左上起点渐变聚集，沿闭合曲线平滑地从疏到密。
        return sample_at_fractions(points, [((i+.5)/count)**1.55 for i in range(count)])
    # 曲率：在拐角/曲率较大位置追加权重，保留最低等弧长密度。
    weights=[]; n=len(points)
    for i in range(n):
        previous=unit(sub(points[i],points[i-1])) or (1.,0.); following=unit(sub(points[(i+1)%n],points[i])) or (1.,0.)
        turn=abs(math.atan2(cross(previous,following), previous[0]*following[0]+previous[1]*following[1]))
        weights.append(distance(points[i],points[(i+1)%n])*(1.0+turn*2.2))
    total=sum(weights); cumulative=[];current=0.0
    for weight in weights: current+=weight; cumulative.append(current)
    fractions=[]
    for i in range(count):
        target=total*(i+.5)/count; edge=next(j for j,v in enumerate(cumulative) if v>=target); before=cumulative[edge-1] if edge else 0.0
        segment=(target-before)/max(weights[edge],EPS); # convert weighted segment to approximate arc fraction
        fractions.append((sum(distance(points[j],points[(j+1)%n]) for j in range(edge))+segment*distance(points[edge],points[(edge+1)%n]))/perimeter(points))
    return sample_at_fractions(points,fractions)


def outward_normal(point: Point, tangent: Point, polygon: list[Point]) -> Point:
    candidate = unit((-tangent[1], tangent[0])) or (0.0, 1.0)
    probe = add(point, mul(candidate, max(0.01, perimeter(polygon) * 1e-5)))
    return mul(candidate, -1.0) if point_inside(probe, polygon) else candidate


def perimeter(points: list[Point]) -> float:
    return sum(distance(points[i], points[(i + 1) % len(points)]) for i in range(len(points)))


def ray_segment_hit(origin: Point, direction: Point, a: Point, b: Point) -> float | None:
    edge = sub(b, a)
    denominator = cross(direction, edge)
    if abs(denominator) < EPS:
        return None
    rel = sub(a, origin)
    t, u = cross(rel, edge) / denominator, cross(rel, direction) / denominator
    return t if t > EPS and -EPS <= u <= 1.0 + EPS else None


def safe_length(point: Point, normal: Point, desired: float, polygon: list[Point]) -> float:
    nearest = desired
    for index, a in enumerate(polygon):
        hit = ray_segment_hit(point, normal, a, polygon[(index + 1) % len(polygon)])
        if hit is not None:
            nearest = min(nearest, hit - 0.02)
    return max(0.0, nearest)


def smooth_noise(count: int, strength: float, scale: float, rng: random.Random) -> list[float]:
    """可复现的环形连续噪声，范围约为 [-strength, strength]。"""
    if strength <= 0:
        return [0.0] * count
    controls = max(3, min(count, int(max(3.0, count / max(scale, 1.0)))))
    values = [rng.uniform(-strength, strength) for _ in range(controls)]
    result = []
    for i in range(count):
        position = i * controls / count
        base, fraction = int(position) % controls, position % 1.0
        eased = (1.0 - math.cos(math.pi * fraction)) * 0.5
        result.append(values[base] * (1.0 - eased) + values[(base + 1) % controls] * eased)
    return result


def rotate(vector: Point, radians: float) -> Point:
    return vector[0]*math.cos(radians)-vector[1]*math.sin(radians), vector[0]*math.sin(radians)+vector[1]*math.cos(radians)


def generate_items(contour: list[Point], settings: PatternSettings, preview_count: int | None = None, cached_samples: list[tuple[Point, Point]] | None = None) -> list[RadialItem]:
    contour = clean_contour(contour)
    if has_self_intersection(contour):
        raise ValueError("轮廓存在自相交，请使用简单闭合轮廓。")
    requested_count = settings.count
    if settings.spacing > EPS:
        requested_count = max(3, min(requested_count, int(perimeter(contour) / settings.spacing)))
    count = min(requested_count, preview_count) if preview_count else requested_count
    rng = random.Random(settings.seed)
    samples = cached_samples if settings.distribution == "均匀" and cached_samples is not None and len(cached_samples) == count else distribute_samples(contour,count,settings.distribution,rng)
    smooth = smooth_noise(count, settings.noise_strength / 100.0, settings.noise_scale, rng)
    items = []
    for index, (point, tangent) in enumerate(samples):
        normal = outward_normal(point, tangent, contour)
        if settings.direction == "向内法线": normal = mul(normal, -1)
        elif settings.direction == "朝向中心":
            center = centroid(contour); normal = unit(sub(center, point)) or normal
        elif settings.direction == "远离中心":
            center = centroid(contour); normal = unit(sub(point, center)) or normal
        normal = unit(rotate(normal, math.radians(settings.rotation))) or normal
        length_random = rng.uniform(-settings.length_random, settings.length_random) / 100.0
        dot_random = rng.uniform(-settings.dot_random, settings.dot_random) / 100.0
        gradient = 0.75 + 0.5 * index / max(count-1,1) if settings.distribution == "渐变" else 1.0
        length = max(0.2, settings.length * settings.scale * gradient * (1.0 + length_random + smooth[index]))
        radius = max(0.1, settings.dot_radius * settings.scale * (1.0 + dot_random + smooth[index] * 0.5))
        start = add(point,mul(normal,settings.offset))
        length = safe_length(start, normal, length, contour) if settings.direction != "向内法线" else length
        if length > EPS:
            items.append(RadialItem(start, add(start, mul(normal, length)), radius, max(0.1, settings.width*settings.scale), normal))
    return items


def centroid(points: list[Point]) -> Point:
    return sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)


def builtin_contour(kind: str, seed: int = 42) -> list[Point]:
    rng = random.Random(seed)
    if kind == "圆角矩形":
        out = []
        for corner, start in [((-125, -75), math.pi), ((125, -75), -math.pi / 2), ((125, 75), 0), ((-125, 75), math.pi / 2)]:
            for i in range(12):
                a = start + i * math.pi / 2 / 11; out.append((corner[0] + 35 * math.cos(a), corner[1] + 35 * math.sin(a)))
        return out
    count = 180
    result = []
    for i in range(count):
        a = math.tau * i / count
        if kind == "圆形": radius = 150
        elif kind == "椭圆": return [(180 * math.cos(math.tau*j/count), 115 * math.sin(math.tau*j/count)) for j in range(count)]
        elif kind == "星形": radius = 150 + 38 * math.cos(8 * a)
        elif kind == "多边形": radius = 150 / max(abs(math.cos((a % (math.tau/6)) - math.tau/12)), 0.55)
        elif kind == "心形":
            x = 12 * math.sin(a) ** 3; y = 10 * math.cos(a) - 4 * math.cos(2*a) - 2 * math.cos(3*a) - math.cos(4*a); result.append((x * 12, y * 12)); continue
        elif kind == "波浪形": radius = 150 + 22 * math.sin(7*a)
        else: radius = 150 + 18*math.sin(3*a+.45) + 10*math.sin(5*a-.8) + 5*math.sin(9*a+rng.random())
        result.append((radius * math.cos(a), radius * math.sin(a)))
    return result


def simplify_polyline(points: list[Point], min_distance: float = 3.0) -> list[Point]:
    """将手绘输入去抖、去除相邻重复点；闭合和平滑由调用方完成。"""
    out = []
    for point in points:
        if not out or distance(point, out[-1]) >= min_distance:
            out.append(point)
    return out


def element_polygon(item: RadialItem, kind: str, custom: list[Point] | None = None) -> list[Point]:
    """把非线性元素标准化为可在 Canvas/SVG/DXF 使用的闭合多边形。"""
    direction=item.direction; perpendicular=(-direction[1],direction[0]); center=item.end; size=max(item.radius,item.width)*2
    if kind == "三角形": return [add(center,mul(direction,size)),add(center,mul(perpendicular,size*.75)),add(center,mul(perpendicular,-size*.75))]
    if kind == "矩形":
        a=add(center,mul(direction,size*.7));b=add(center,mul(direction,-size*.7));return [add(a,mul(perpendicular,size*.55)),add(a,mul(perpendicular,-size*.55)),add(b,mul(perpendicular,-size*.55)),add(b,mul(perpendicular,size*.55))]
    if kind in ("叶片","水滴"):
        points=[]
        for i in range(18):
            t=math.tau*i/18; radial=(math.cos(t)*(.55 if kind=="叶片" else .42),math.sin(t)*.7)
            forward=math.sin(t)*(.2 if kind=="叶片" else .45)
            points.append(add(center,add(mul(perpendicular,radial[0]*size),mul(direction,(radial[1]+forward)*size))))
        return points
    if kind == "自定义 SVG" and custom:
        maxabs=max(max(abs(x),abs(y)) for x,y in custom) or 1.0
        return [add(center,add(mul(perpendicular,x/maxabs*size),mul(direction,y/maxabs*size))) for x,y in custom]
    return []
