"""Small final-element contour adapter, not a new shape/field/extrusion engine."""
from dataclasses import dataclass, replace
from functools import lru_cache
import math
import numpy as np
from .evaluation import evaluate_pattern_document
from .manufacturing_geometry import ManufacturingGeometryAdapter, Manufacturing2DGeometry, ManufacturingPolygon
from .manufacturing_backend import TrimeshBackend
from .fabric_plan import FabricInstance, FabricInstancePlan, _plan_indices
from .fabric_field_modifiers import apply_fabric_field_modifiers


@dataclass(frozen=True)
class OriginalShapeFrame:
    """1mm local frame, not a registered Unit Cell or guessed box geometry."""
    type: str = 'original_contour'
    width_mm: float = 1.
    depth_mm: float = 1.
    height_mm: float = 1.


@lru_cache(maxsize=256)
def _contour_mesh(rings):
    polygons = tuple(ManufacturingPolygon('original-contour', outer, holes) for outer, holes in rings)
    mesh = TrimeshBackend().extrude(Manufacturing2DGeometry(polygons), 1.).mesh
    mesh.vertices.flags.writeable = False
    mesh.faces.flags.writeable = False
    return mesh


def original_plan(document, raw, base_z, *, preview_limit):
    values = raw.get('original_shape')
    if not isinstance(values, dict):
        raise ValueError('原图形状配置缺失。')
    size, height = values.get('size_scale'), values.get('height_mm')
    if any(type(v) not in (float, int) or not math.isfinite(v) or v <= 0 for v in (size, height)):
        raise ValueError('原图大小和高度必须是有限正数。')
    final = tuple(e for e in evaluate_pattern_document(document) if e.visible)
    conversion = ManufacturingGeometryAdapter().adapt_evaluated_document(document, final)
    if conversion.report.skipped or conversion.report.topology_changed_element_ids:
        reasons = [f'{s.element_id}: {s.message}' for s in conversion.report.skipped]
        reasons += list(conversion.report.topology_changed_element_ids)
        raise ValueError('原图轮廓无法安全转换：' + '; '.join(reasons))
    if not final or not conversion.geometry.polygons:
        raise ValueError('没有有效原图面积，不能生成空模型。')
    by_id = {}
    for polygon in conversion.geometry.polygons:
        by_id.setdefault(polygon.source_element_id, []).append(polygon)
    factor = document.canvas.mm_per_unit if document.canvas.mm_per_unit is not None else 1.
    instances, prototypes = [], {}
    for index in _plan_indices(len(final), preview_limit):
        element = final[index]
        polygons = by_id.get(element.id)
        if not polygons:
            raise ValueError(f'原图元素 {element.id} 没有可挤出轮廓。')
        xy = np.asarray([p for polygon in polygons for p in polygon.outer])
        width, depth = np.ptp(xy, axis=0)
        if min(width, depth) <= ManufacturingGeometryAdapter().epsilon_mm:
            raise ValueError(f'原图元素 {element.id} 太小，无法制造。')
        x, y = element.x*factor, element.y*factor
        def local(ring):
            return tuple(((px-x)/width, (py-y)/depth) for px, py in ring)
        rings = tuple((local(p.outer), tuple(local(h) for h in p.holes)) for p in polygons)
        key = f'fabric:original:{element.id}'
        prototypes[key] = _contour_mesh(rings)
        # Rotation and 2D size are already baked once by the authoritative adapter.
        instances.append(FabricInstance(key, x, y, base_z, 'original_contour', height,
            source_id=element.id, final_geometry_id=element.id, scale=size,
            scale_x=float(width), scale_y=float(depth), base_width_mm=1., base_depth_mm=1., base_height_mm=1.,
            cell_width_mm=float(width)*size, cell_depth_mm=float(depth)*size))
    centers = [(e.x*factor, e.y*factor) for e in final]
    field_bounds = (min(p[0] for p in centers), min(p[1] for p in centers), max(p[0] for p in centers), max(p[1] for p in centers))
    plan = FabricInstancePlan(OriginalShapeFrame(), tuple(instances), ((0, 0, base_z), (0, 0, base_z+height)),
        next(iter(prototypes.values())), total_count=len(final), field_bounds_mm=field_bounds, contour_prototypes=prototypes)
    plan = apply_fabric_field_modifiers(plan, document, raw.get('field_modifiers'))
    if not any(item.enabled for item in plan.instances):
        raise ValueError('没有启用的原图元素，不能只生成基底或空 STL。')
    bounds = []
    for item in plan.instances:
        if not item.enabled:
            continue
        mesh = prototypes[item.id]
        angle = math.radians(item.rotation_deg)
        matrix = np.array([[math.cos(angle)*item.cell_width_mm, -math.sin(angle)*item.cell_depth_mm, 0],
            [math.sin(angle)*item.cell_width_mm, math.cos(angle)*item.cell_depth_mm, 0], [0, 0, item.height_mm]])
        vertices = mesh.vertices @ matrix.T + [item.x_mm, item.y_mm, item.z_mm]
        bounds.append((vertices.min(axis=0), vertices.max(axis=0)))
    if bounds:
        plan = replace(plan, bounds_mm=(tuple(np.min([b[0] for b in bounds], axis=0)), tuple(np.max([b[1] for b in bounds], axis=0))))
    return plan
