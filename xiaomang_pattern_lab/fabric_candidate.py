"""F5-A unfused candidate and factual attachment preflight; no export/repair.

Consumes an authoritative FabricInstancePlan. No Field, Image, Density or
Orientation evaluation occurs here. ATTACHED means contact, never fusion.
"""
from dataclasses import asdict, dataclass
import math
from time import perf_counter
from typing import Any

import numpy as np
from shapely import affinity
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union, polygonize
from shapely.strtree import STRtree
import trimesh

from .fabric_base import BaseDefinition, FabricBaseBuilder
from .fabric_plan import FabricInstancePlan
from .manufacturing_backend import TrimeshBackend
from .manufacturing_geometry import ManufacturingGeometryAdapter
from .mesh_validation import MeshValidator


@dataclass(frozen=True)
class FabricManufacturingCandidate:
    base_mesh: Any
    cell_meshes: tuple[Any, ...]
    instance_transforms: tuple[dict, ...]
    mesh: Any
    report: dict


def instance_matrix(instance, cell):
    """Same T × Rz × S as Three.js; final dimensions include both scales once."""
    a = math.radians(instance.rotation_deg)
    sx = instance.cell_width_mm / cell.width_mm
    sy = instance.cell_depth_mm / cell.depth_mm
    sz = instance.height_mm / cell.height_mm
    return np.array(((math.cos(a)*sx, -math.sin(a)*sy, 0, instance.x_mm),
                     (math.sin(a)*sx, math.cos(a)*sy, 0, instance.y_mm),
                     (0, 0, sz, instance.z_mm), (0, 0, 0, 1)), dtype=float)


def _message(level, code, message, **measured):
    return {'level':level, 'code':code, 'message':message, 'measured':{
        key:None if isinstance(value,float) and not math.isfinite(value) else value
        for key,value in measured.items()}}


def _prototype_components(mesh):
    """Index-connected prototype parts, no optional graph dependency or welding."""
    neighbors = [[] for _ in mesh.faces]
    by_vertex = {}
    for index, face in enumerate(mesh.faces):
        for vertex in face:
            previous = by_vertex.setdefault(int(vertex), index)
            if previous != index:
                neighbors[index].append(previous)
                neighbors[previous].append(index)
    remaining = set(range(len(mesh.faces)))
    while remaining:
        stack = [remaining.pop()]
        faces = []
        while stack:
            current = stack.pop()
            faces.append(current)
            for neighbor in neighbors[current]:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    stack.append(neighbor)
        yield trimesh.Trimesh(vertices=mesh.vertices, faces=mesh.faces[faces], process=False)


def _contact_section(component, local_z, epsilon):
    """Read-only plane intersection for penetrated cells, not mesh modification."""
    segments = []
    for triangle in component.vertices[component.faces]:
        points = []
        for a, b in ((triangle[0],triangle[1]),(triangle[1],triangle[2]),(triangle[2],triangle[0])):
            if abs(a[2]-local_z) <= epsilon:
                points.append(a[:2])
            elif (a[2]-local_z)*(b[2]-local_z) < 0:
                points.append((a+(b-a)*((local_z-a[2])/(b[2]-a[2])))[:2])
        unique = []
        for point in points:
            if not any(np.linalg.norm(point-other) <= epsilon for other in unique):
                unique.append(point)
        if len(unique) == 2:
            segments.append(LineString(unique))
    return unary_union(list(polygonize(unary_union(segments))))


def build_fabric_candidate(plan: FabricInstancePlan | None, base: BaseDefinition,
                           design_bounds_mm, *, document_id: str,
                           document_revision: int) -> FabricManufacturingCandidate:
    started = perf_counter()
    epsilon = ManufacturingGeometryAdapter().epsilon_mm
    area_epsilon = MeshValidator().degenerate_face_epsilon_mm2
    geometry = FabricBaseBuilder().geometry(design_bounds_mm, base)
    base_result = TrimeshBackend().extrude(geometry, base.thickness_mm)
    # Same actual F1 material, including Grid holes. This 2D material union is
    # for contact measurement only, never Boolean/fusion of candidate meshes.
    triangles = base_result.mesh.vertices[base_result.mesh.faces]
    top = triangles[np.all(abs(triangles[:,:,2]-base.thickness_mm) <= epsilon,axis=1)]
    # Index the actual extruded top triangles once. Grid contact queries only
    # visit nearby material, not every hole or every other cell (no N² loop).
    top_material = [Polygon(triangle[:,:2]) for triangle in top]
    material_index = STRtree(top_material)
    base_at = perf_counter()
    pieces = []
    if plan is not None:
        for component in _prototype_components(plan.prototype):
            low = float(component.vertices[:,2].min())
            bottom_faces = component.faces[np.all(
                abs(component.vertices[component.faces,2]-low) <= epsilon, axis=1)]
            polygons = [Polygon(component.vertices[face,:2]) for face in bottom_faces]
            pieces.append((unary_union(polygons),component))
    prototype_at = perf_counter()
    entries, meshes, transforms = [], [], []
    issues = [_message('INFO','unfused_candidate',
        '这是未融合候选；共面接触不代表已融合，最终 Fabric STL 尚未开放。')]
    transform_ms = contact_ms = bounds_ms = 0.
    all_finite = True
    component_attached = component_detached = 0
    prototype_faces = plan.prototype.faces if plan else np.empty((0,3),dtype=int)
    for instance in plan.instances if plan else ():
        if not instance.enabled:
            continue
        sample_started = perf_counter()
        raw = asdict(instance)
        # JSON diagnostics explicitly represent invalid values, not NaN JSON.
        raw = {k:(None if isinstance(v,float) and not math.isfinite(v) else v) for k,v in raw.items()}
        problems = []
        measurements = {'width_mm':instance.cell_width_mm,'depth_mm':instance.cell_depth_mm,
                        'height_mm':instance.height_mm}
        numeric = (instance.x_mm,instance.y_mm,instance.z_mm,instance.rotation_deg,
                   instance.scale,instance.scale_x,instance.scale_y,
                   instance.cell_width_mm,instance.cell_depth_mm,instance.height_mm)
        finite = all(type(v) in (int,float) and math.isfinite(v) for v in numeric)
        if not finite:
            problems.append(_message('ERROR','non_finite_transform','单元变换包含非有限或缺失数值。'))
        elif min(instance.scale,instance.scale_x,instance.scale_y) <= 0:
            problems.append(_message('ERROR','invalid_scale','单元比例必须大于零。'))
        elif min(instance.cell_width_mm,instance.cell_depth_mm) <= epsilon:
            problems.append(_message('ERROR','cell_too_small','单元尺寸过小。',**measurements))
        if finite and instance.height_mm <= epsilon:
            problems.append(_message('ERROR','height_too_small','单元高度过低/异常。',**measurements))
        mesh = matrix = None
        lower = upper = None
        if finite:
            matrix = instance_matrix(instance,plan.cell)
            vertices = plan.prototype.vertices @ matrix[:3,:3].T + matrix[:3,3]
            if np.isfinite(vertices).all():
                mesh = trimesh.Trimesh(vertices=vertices,faces=prototype_faces.copy(),process=False)
                triangles = vertices[prototype_faces]
                areas = np.linalg.norm(np.cross(triangles[:,1]-triangles[:,0],
                    triangles[:,2]-triangles[:,0]),axis=1)/2
                measurements['min_triangle_area_mm2'] = float(areas.min()) if len(areas) else None
                if not len(areas) or not np.isfinite(areas).all() or np.any(areas <= area_epsilon):
                    problems.append(_message('ERROR','invalid_transformed_mesh',
                        '单元变换产生退化三角面。',**measurements))
                bounds_started = perf_counter()
                lower,upper = vertices.min(axis=0),vertices.max(axis=0)
                bounds_ms += (perf_counter()-bounds_started)*1000
            else:
                finite = False
                problems.append(_message('ERROR','non_finite_mesh','单元 Mesh 含有非有限坐标。'))
        transform_ms += (perf_counter()-sample_started)*1000
        contact_started = perf_counter()
        part_status, areas = [], []
        gap = overlap = None
        if mesh is not None:
            gap = float(lower[2]-base.thickness_mm)
            overlap = max(0.,min(base.thickness_mm,float(upper[2]))-max(0.,float(lower[2])))
            if lower[2] < -epsilon:
                problems.append(_message('ERROR','cell_below_base','单元低于底布底部。',bottom_z_mm=float(lower[2])))
            for bottom_footprint, component in pieces:
                m = matrix
                footprint = (_contact_section(component,(base.thickness_mm-m[2,3])/m[2,2],
                    epsilon/abs(m[2,2])) if gap < -epsilon and m[2,2] > 0 else bottom_footprint)
                placed = affinity.affine_transform(footprint,
                    (m[0,0],m[0,1],m[1,0],m[1,1],m[0,3],m[1,3]))
                area = float(sum(placed.intersection(top_material[int(index)]).area
                    for index in material_index.query(placed,predicate='intersects')))
                areas.append(area)
                tiny_area = max(area_epsilon,epsilon*placed.length)
                if placed.is_empty:
                    state = 'DETACHED'
                elif not placed.is_valid:
                    state = 'INVALID'
                elif area <= area_epsilon or gap > epsilon*10:
                    state = 'DETACHED'
                elif gap > epsilon or area <= tiny_area or area < placed.area*.05:
                    state = 'MARGINAL'
                else:
                    state = 'ATTACHED'
                part_status.append(state)
            if not pieces:
                problems.append(_message('ERROR','missing_bottom','无法获取可靠单元底面。'))
            component_attached += part_status.count('ATTACHED')
            component_detached += sum(s != 'ATTACHED' for s in part_status)
        state = ('INVALID' if any(p['level']=='ERROR' for p in problems) else
                 'DETACHED' if 'DETACHED' in part_status else
                 'MARGINAL' if 'MARGINAL' in part_status else
                 'INVALID' if 'INVALID' in part_status else 'ATTACHED')
        if state == 'DETACHED':
            problems.append(_message('WARNING','detached','单元未连接到底布。',
                                     gap_mm=gap,contact_area_mm2=sum(areas)))
        if state == 'MARGINAL':
            problems.append(_message('WARNING','marginal_contact','接触面积过小或仅接近底布。',
                                     gap_mm=gap,contact_area_mm2=sum(areas)))
        if state == 'INVALID' and not any(p['level']=='ERROR' for p in problems):
            problems.append(_message('ERROR','invalid_contact','单元底面接触几何无效。'))
        contact_ms += (perf_counter()-contact_started)*1000
        all_finite = all_finite and mesh is not None
        meshes.append(mesh)
        transforms.append(raw | {'matrix':matrix.tolist() if matrix is not None else None})
        entries.append({'instance_id':instance.id,'source_id':instance.source_id,
            'final_geometry_id':instance.final_geometry_id,'status':state,'fused':False,
            'gap_mm':gap,'overlap_depth_mm':overlap,'contact_area_mm2':sum(areas),
            'component_statuses':part_status,'issues':problems,'measured':{
                **{k:(v if v is None or math.isfinite(v) else None) for k,v in measurements.items()},
                'bounds_mm':[lower.tolist(),upper.tolist()] if lower is not None else None}})
    assembled_at = perf_counter()
    # Concatenation preserves separate bodies and shared/coplanar interfaces.
    # It is intentionally NOT a ManufacturingMeshResult or exportable artifact.
    mesh = trimesh.util.concatenate([base_result.mesh,*meshes]) if all_finite else None
    assembly_ms = (perf_counter()-assembled_at)*1000
    bounds_started = perf_counter()
    bounds = mesh.bounds.tolist() if mesh is not None else None
    bounds_ms += (perf_counter()-bounds_started)*1000
    counts = {key:sum(e['status']==key for e in entries) for key in
              ('ATTACHED','MARGINAL','DETACHED','INVALID')}
    if not entries:
        issues.append(_message('WARNING','no_enabled_cells','没有启用的单元；候选仅包含底布。'))
    if len(entries) >= 1000:
        issues.append(_message('WARNING','large_instance_count','实例数量较大，最终制造可能较慢。'))
    if bounds is not None and max(abs(v) for row in bounds for v in row) > 10000:
        issues.append(_message('WARNING','extreme_bounds','候选坐标范围超过 10000 mm，请核对真实尺寸。'))
    report = {'schema_version':'1.0','kind':'fabric_manufacturing_candidate',
        'document_id':document_id,'document_revision':document_revision,
        'status':'error' if counts['INVALID'] else 'warning' if counts['MARGINAL']+counts['DETACHED']
            or any(issue['level']=='WARNING' for issue in issues) else 'checked',
        'fused':False,'export_available':False,'bounds_mm':bounds,
        'instance_count':len(plan.instances) if plan else 0,'enabled_instance_count':len(entries),
        'attachment_counts':counts,'attachments':entries,'issues':issues,
        'tolerances':{'distance_mm':epsilon,'triangle_area_mm2':area_epsilon,
            'near_contact_distance_mm':10*epsilon,'marginal_contact_fraction':.05},
        'components':{'base_components':base_result.component_count,
            'cell_components':len(pieces)*len(entries),
            'prefusion_components':base_result.component_count+len(pieces)*len(entries),
            'attached_cell_components':component_attached,'unattached_cell_components':component_detached,
            'expected_post_fusion_target':base_result.component_count+component_detached if not counts['INVALID'] else None,
            'target_is_estimate':True,'cell_cell_contacts_analyzed':False},
        'vertex_count':len(mesh.vertices) if mesh is not None else None,
        'face_count':len(mesh.faces) if mesh is not None else None,
        'memory_estimate_bytes':sum(m.vertices.nbytes+m.faces.nbytes for m in [base_result.mesh,*meshes] if m is not None)
            +(mesh.vertices.nbytes+mesh.faces.nbytes if mesh is not None else 0),
        'timings_ms':{'base_build':(base_at-started)*1000,
            'prototype_preparation':(prototype_at-base_at)*1000,'transformed_mesh_generation':transform_ms,
            'attachment_preflight':contact_ms,'candidate_assembly':assembly_ms,'bounds':bounds_ms,
            'total':(perf_counter()-started)*1000}}
    return FabricManufacturingCandidate(base_result.mesh,tuple(meshes),tuple(transforms),mesh,report)
