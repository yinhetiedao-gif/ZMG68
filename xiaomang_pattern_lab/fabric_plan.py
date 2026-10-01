"""F2 regular placement and immutable derived instance plan."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

from .fabric_cells import UNIT_CELL_REGISTRY, UnitCellDefinition


MAX_PREVIEW_INSTANCES = 10000


@dataclass(frozen=True)
class RegularPlacement:
    spacing_x_mm: float
    spacing_y_mm: float

    def __post_init__(self) -> None:
        for value, key in ((self.spacing_x_mm, "spacing_x_mm"),
                           (self.spacing_y_mm, "spacing_y_mm")):
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"布点 {key} 必须是大于 0 的有限毫米数值。")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "RegularPlacement":
        values = []
        for key in ("spacing_x_mm", "spacing_y_mm"):
            value = raw.get(key)
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"布点 {key} 必须是大于 0 的有限毫米数值。")
            values.append(float(value))
        return cls(*values)


@dataclass(frozen=True)
class FabricInstance:
    id: str
    x_mm: float
    y_mm: float
    z_mm: float
    cell_type: str
    height_mm: float
    rotation_deg: float = 0.0
    scale: float = 1.0
    source_id: str | None = None


@dataclass(frozen=True)
class FabricInstancePlan:
    cell: UnitCellDefinition
    instances: tuple[FabricInstance, ...]
    bounds_mm: tuple[tuple[float, float, float], tuple[float, float, float]]
    prototype: Any

    @property
    def count(self) -> int:
        return len(self.instances)

    def preview_payload(self) -> dict[str, Any]:
        return {"schema_version": "1.0", "kind": "fabric_instance_preview",
                "cell_type": self.cell.type, "count": self.count,
                "bounds_mm": self.bounds_mm,
                "prototype": {"vertices": self.prototype.vertices.tolist(),
                              "faces": self.prototype.faces.tolist()},
                "instances": [{"id": item.id, "x_mm": item.x_mm, "y_mm": item.y_mm,
                               "z_mm": item.z_mm, "rotation_deg": item.rotation_deg,
                               "scale": item.scale, "height_mm": item.height_mm,
                               "cell_type": item.cell_type, "source_id": item.source_id}
                              for item in self.instances],
                "manufacturing_status": "preview_only_not_in_stl"}


class FabricPlanner:
    def plan(self, base_bounds_mm: tuple[float, float, float, float], base_top_z: float,
             cell: UnitCellDefinition, placement: RegularPlacement) -> FabricInstancePlan:
        if len(base_bounds_mm) != 4 or any(not math.isfinite(value) for value in base_bounds_mm):
            raise ValueError("Fabric Base 范围必须是有限毫米坐标。")
        left, bottom, right, top = base_bounds_mm
        if right <= left or top <= bottom or not math.isfinite(base_top_z) or base_top_z <= 0:
            raise ValueError("Fabric Base 范围或顶部高度无效。")
        columns = math.floor((right - left) / placement.spacing_x_mm + 1e-9)
        rows = math.floor((top - bottom) / placement.spacing_y_mm + 1e-9)
        if columns < 1 or rows < 1:
            raise ValueError("布点间距大于基底尺寸，无法生成 Unit Cell。")
        if columns * rows > MAX_PREVIEW_INSTANCES:
            raise ValueError("Unit Cell 数量超过 F2 预览上限，请增大布点间距。")
        prototype = UNIT_CELL_REGISTRY.create(cell)
        instances = tuple(FabricInstance(f"fabric:r{row}:c{column}",
                          left + (column + .5) * placement.spacing_x_mm,
                          bottom + (row + .5) * placement.spacing_y_mm, base_top_z,
                          cell.type, cell.height_mm)
                          for row in range(rows) for column in range(columns))
        xs = [item.x_mm for item in instances]
        ys = [item.y_mm for item in instances]
        bounds = ((min(xs) - cell.width_mm / 2, min(ys) - cell.depth_mm / 2, base_top_z),
                  (max(xs) + cell.width_mm / 2, max(ys) + cell.depth_mm / 2,
                   base_top_z + cell.height_mm))
        return FabricInstancePlan(cell, instances, bounds, prototype)


def plan_from_fabric_config(config, manufacturing_bounds_mm):
    raw = config.get("unit_cell")
    if raw is None:
        return None
    placement_raw = config.get("placement")
    if not isinstance(raw, Mapping) or not isinstance(placement_raw, Mapping):
        raise ValueError("Unit Cell 需要定义单元类型和规则布点。")
    base = config["base"]
    margin = float(base.get("margin_mm", 0))
    left, bottom, right, top = manufacturing_bounds_mm
    return FabricPlanner().plan((left - margin, bottom - margin, right + margin, top + margin),
                                float(base["thickness_mm"]), UnitCellDefinition.from_mapping(raw),
                                RegularPlacement.from_mapping(placement_raw))
