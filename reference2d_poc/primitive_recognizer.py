from __future__ import annotations

from dataclasses import dataclass
import math

from .svg_parser import Point, VectorPath


@dataclass(frozen=True)
class PrimitiveCandidate:
    source_id: str
    fill: str
    center_x: float
    center_y: float
    radius_x: float
    radius_y: float
    rotation: float
    bounding_box: tuple[float, float, float, float]
    area: float
    perimeter: float
    aspect_ratio: float
    circularity: float
    ellipse_fit: float
    confidence: float
    accepted_as_dot: bool
    reject_reason: str | None = None


def _distance(first: Point, second: Point) -> float:
    return math.hypot(first[0] - second[0], first[1] - second[1])


def _is_white(fill: str) -> bool:
    normalized = fill.strip().lower().replace(" ", "")
    return normalized in {"white", "#fff", "#ffffff", "rgb(255,255,255)", "none", "transparent"}


class PrimitiveRecognizer:
    """按面积、周长、外接框、圆度、长宽比和椭圆拟合识别 DOT。"""

    min_area: float = 2.0
    min_circularity: float = 0.58
    max_aspect_ratio: float = 1.60

    def recognize(self, paths: tuple[VectorPath, ...]) -> tuple[PrimitiveCandidate, ...]:
        return tuple(self._recognize(path) for path in paths)

    def _recognize(self, path: VectorPath) -> PrimitiveCandidate:
        points = list(path.points)
        if len(points) >= 2 and _distance(points[0], points[-1]) < 1e-9:
            points.pop()
        if len(points) < 3:
            return PrimitiveCandidate(path.id, path.fill, 0, 0, 0, 0, 0, (0, 0, 0, 0), 0, 0, 0, 0, 0, 0, False, "轮廓点不足")
        xs, ys = [point[0] for point in points], [point[1] for point in points]
        min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
        width, height = max_x - min_x, max_y - min_y
        center_x, center_y = sum(xs) / len(xs), sum(ys) / len(ys)
        signed_area = sum(points[index][0] * points[(index + 1) % len(points)][1] - points[(index + 1) % len(points)][0] * points[index][1] for index in range(len(points))) / 2.0
        area = abs(signed_area)
        perimeter = sum(_distance(points[index], points[(index + 1) % len(points)]) for index in range(len(points)))
        circularity = 4 * math.pi * area / (perimeter * perimeter) if perimeter else 0.0
        aspect_ratio = max(width, height) / max(min(width, height), 1e-9)

        covariance_xx = sum((x - center_x) ** 2 for x in xs) / len(points)
        covariance_yy = sum((y - center_y) ** 2 for y in ys) / len(points)
        covariance_xy = sum((x - center_x) * (y - center_y) for x, y in points) / len(points)
        rotation = math.degrees(0.5 * math.atan2(2 * covariance_xy, covariance_xx - covariance_yy))
        radians = math.radians(rotation)
        cosine, sine = math.cos(radians), math.sin(radians)
        projected_x = [(x - center_x) * cosine + (y - center_y) * sine for x, y in points]
        projected_y = [-(x - center_x) * sine + (y - center_y) * cosine for x, y in points]
        radius_x, radius_y = max(abs(value) for value in projected_x), max(abs(value) for value in projected_y)
        ellipse_ratio = min(radius_x, radius_y) / max(radius_x, radius_y, 1e-9)
        ellipse_fit = max(0.0, min(1.0, (circularity - 0.45) / 0.55 * 0.7 + ellipse_ratio * 0.3))
        confidence = max(0.0, min(1.0, circularity * 0.65 + ellipse_ratio * 0.25 + ellipse_fit * 0.10))

        reason: str | None = None
        if _is_white(path.fill):
            reason = "非墨色填充"
        elif area < self.min_area:
            reason = "面积过小"
        elif circularity < self.min_circularity:
            reason = "圆度不足"
        elif aspect_ratio > self.max_aspect_ratio:
            reason = "长宽比过大"
        elif ellipse_fit < 0.55:
            reason = "椭圆拟合不足"
        return PrimitiveCandidate(
            source_id=path.id,
            fill=path.fill,
            center_x=center_x,
            center_y=center_y,
            radius_x=radius_x,
            radius_y=radius_y,
            rotation=rotation,
            bounding_box=(min_x, min_y, max_x, max_y),
            area=area,
            perimeter=perimeter,
            aspect_ratio=aspect_ratio,
            circularity=circularity,
            ellipse_fit=ellipse_fit,
            confidence=confidence,
            accepted_as_dot=reason is None,
            reject_reason=reason,
        )
