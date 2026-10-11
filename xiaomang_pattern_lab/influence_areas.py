"""Consumer-local influence weights; never edits the shared scalar field.

Line/curve use distance to a finite axis with rounded ends. Ellipse uses a
filled rotated ellipse, not a RingField. Overlap is maximum, independent of
list order. Curves are quadratic Beziers sampled at 128 fixed intervals.
"""
from dataclasses import dataclass
from functools import cached_property
import math
from .parameter_definitions import parameter_definitions, validate_parameter


def segment_distance(x, y, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    squared = dx * dx + dy * dy
    t = max(0., min(1., ((x - a[0]) * dx + (y - a[1]) * dy) / squared)) if squared else 0.
    return math.hypot(x - a[0] - t * dx, y - a[1] - t * dy)


@dataclass(frozen=True)
class InfluenceArea:
    id: str
    type: str
    parameters: dict
    enabled: bool = True

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id or type(self.enabled) is not bool:
            raise ValueError("影响区身份或启用状态无效。")
        schema = parameter_definitions()["definitions"]["design"].get(self.type)
        if self.type not in ("line", "ellipse", "curve") or schema is None or not isinstance(self.parameters, dict):
            raise ValueError("影响区类型/参数无效。")
        expected = {p["id"] for p in schema["parameters"]}
        if set(self.parameters) != expected:
            raise ValueError("影响区参数不完整或包含未知参数。")
        for definition in schema["parameters"]:
            validate_parameter(definition, self.parameters[definition["id"]])
        if self.parameters["feather"] > self.parameters["width"] / 2:
            raise ValueError("影响区过渡不能大于半宽。")
        if self.type == "curve" and math.hypot(self.parameters["x2"] - self.parameters["x0"], self.parameters["y2"] - self.parameters["y0"]) <= 1e-9:
            raise ValueError("曲线轴起终点不能重合。")

    @cached_property
    def segments(self):
        p = self.parameters
        if self.type == "line":
            theta = math.radians(p["angle"])
            dx, dy = p["length"] / 2 * math.cos(theta), p["length"] / 2 * math.sin(theta)
            return [((p["x"] - dx, p["y"] - dy), (p["x"] + dx, p["y"] + dy))]
        points = [((1-t)**2*p["x0"] + 2*(1-t)*t*p["x1"] + t*t*p["x2"],
                   (1-t)**2*p["y0"] + 2*(1-t)*t*p["y1"] + t*t*p["y2"])
                  for t in (i / 128 for i in range(129))]
        return list(zip(points, points[1:]))

    def weight(self, element):
        if not self.enabled:
            return 0.
        p = self.parameters
        if self.type == "ellipse":
            theta = math.radians(p["angle"])
            dx, dy = element.x - p["x"], element.y - p["y"]
            u = (dx * math.cos(theta) + dy * math.sin(theta)) / (p["length"] / 2)
            v = (-dx * math.sin(theta) + dy * math.cos(theta)) / (p["width"] / 2)
            edge = (1 - math.hypot(u, v)) * min(p["length"], p["width"]) / 2
        else:
            edge = p["width"] / 2 - min(segment_distance(element.x, element.y, a, b) for a, b in self.segments)
        if edge < 0:
            return 0.
        return min(1., edge / p["feather"]) if p["feather"] else 1.

    def to_dict(self):
        return dict(id=self.id, type=self.type, parameters=dict(self.parameters), enabled=self.enabled)
