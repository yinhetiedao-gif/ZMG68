"""F5-B headless true-solid union. Never evaluates design or exports artifacts."""
from collections import OrderedDict
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from importlib.metadata import version
from threading import RLock
from time import perf_counter, monotonic
from uuid import uuid4
import json
import numpy as np
import trimesh

from .fabric_candidate import FabricManufacturingCandidate
from .manufacturing_backend import ManufacturingMeshResult
from .mesh_validation import MeshValidator


class FabricFusionFailure(ValueError):
    def __init__(self, stage, message, **diagnostic):
        super().__init__(message)
        self.report = {'stage':stage,'message':message,'failure_id':uuid4().hex,
            'backend':'manifold3d-mesh64','final_fabric_mesh_ready':False,
            'export_available':False,**diagnostic}


@dataclass(frozen=True)
class FinalFabricMesh:
    mesh_result: ManufacturingMeshResult
    report: dict


class FabricFusionService:
    """Bounded cache and deterministic balanced solid union, never mesh repair."""
    @staticmethod
    def _union(solids):
        # Preserve stable candidate order. Native batch union produced a zero-
        # area face for boundary-touching cones; this balanced tree evaluates
        # the same exact operands without a growing global accumulator.
        level = list(solids)
        while len(level) > 1:
            level = [level[index] + level[index + 1] if index + 1 < len(level)
                     else level[index] for index in range(0, len(level), 2)]
        return level[0]

    def __init__(self, capacity=4, ttl_seconds=1800, max_bytes=128*1024*1024):
        self.capacity, self.ttl_seconds, self.max_bytes = capacity,ttl_seconds,max_bytes
        self._cache = OrderedDict()
        self._lock = RLock()

    def build(self, candidate: FabricManufacturingCandidate) -> FinalFabricMesh:
        started = perf_counter()
        source = candidate.report
        blocked = [entry for entry in source['attachments'] if entry['status'] in ('INVALID','DETACHED')]
        if blocked or candidate.mesh is None:
            raise FabricFusionFailure('preflight','存在无效或未连接单元，已阻止实体融合。',
                attachment_counts=source['attachment_counts'],instances=[{
                    'instance_id':e['instance_id'],'source_id':e['source_id'],
                    'final_geometry_id':e['final_geometry_id'],'status':e['status'],
                    'measured':e['measured'],'issues':e['issues']} for e in blocked],
                pre_component_count=source['components']['prefusion_components'])
        try:
            import manifold3d as manifold
        except ImportError as error:
            raise FabricFusionFailure('backend','缺少 Fabric 实体融合依赖 manifold3d。') from error
        fingerprint = sha256(json.dumps({'document_id':source['document_id'],
            'document_revision':source['document_revision'],'backend':version('manifold3d'),
            'interface_overlap_mm':0,'document_fingerprint':source.get('document_fingerprint'),
            'schema':'f5b-1-balanced'},sort_keys=True).encode())
        meshes = (candidate.base_mesh,*candidate.cell_meshes)
        for mesh in meshes:
            fingerprint.update(str((mesh.vertices.shape, mesh.faces.shape)).encode())
            fingerprint.update(np.asarray(mesh.vertices,dtype='<f8').tobytes())
            fingerprint.update(np.asarray(mesh.faces,dtype='<i8').tobytes())
        key = fingerprint.hexdigest()
        # Single flight under a bounded service lock; cache does not expose
        # candidates or final mesh through the ordinary STL result store.
        with self._lock:
            cached = self._cache.get(key)
            if cached and monotonic()-cached[0] < self.ttl_seconds:
                self._cache.move_to_end(key)
                return FinalFabricMesh(cached[1].mesh_result,{**deepcopy(cached[1].report),'cache_hit':True})
            if cached:
                del self._cache[key]
            solids = []
            try:
                for index, mesh in enumerate(meshes):
                    solid = manifold.Manifold(manifold.Mesh64(
                        vert_properties=np.asarray(mesh.vertices,dtype=np.float64),
                        tri_verts=np.asarray(mesh.faces,dtype=np.uint64)))
                    if solid.status() != manifold.Error.NoError or solid.is_empty() or solid.volume() <= 0:
                        raise FabricFusionFailure('boolean_input','输入不是有效的定向封闭实体。',
                            instance_id=None if index==0 else source['attachments'][index-1]['instance_id'],
                            backend_status=str(solid.status()))
                    solids.append(solid)
                prepared = perf_counter()
                united = self._union(solids)
                output = united.to_mesh64()  # evaluate lazy Boolean before timing
                fused = perf_counter()
                if united.status() != manifold.Error.NoError or united.is_empty():
                    raise FabricFusionFailure('boolean_union','实体布尔并集失败。',backend_status=str(united.status()))
                mesh = trimesh.Trimesh(vertices=np.asarray(output.vert_properties[:,:3],dtype=float),
                    faces=np.asarray(output.tri_verts,dtype=np.int64),process=False)
                components = len(united.decompose())
                exact_components = components
                connected = perf_counter()
                result = ManufacturingMeshResult(mesh,tuple(map(tuple,mesh.bounds)),len(mesh.vertices),
                    len(mesh.faces),components,float(np.ptp(mesh.vertices[:,2])),
                    'manifold3d-mesh64',bool(mesh.is_watertight))
                validation = MeshValidator().validate(result)
                validated = perf_counter()
                if components != 1 or validation.component_count != 1:
                    raise FabricFusionFailure('connectivity','融合后仍有分离实体。',
                        connected_component_count=validation.component_count,
                        solid_component_count=components,component_bounds=[
                            part.bounding_box() for part in united.decompose()])
                volume = float(mesh.volume)
                if not validation.is_valid or not validation.is_watertight or not np.isfinite(volume) or volume <= 0:
                    raise FabricFusionFailure('mesh_validation','最终网格未通过正式制造检查。',
                        validation_report=asdict(validation),volume_mm3=volume,
                        pre_component_count=source['components']['prefusion_components'],
                        post_component_count=validation.component_count,
                        interface_overlap_mm=0,
                        min_triangle_area_mm2=float(mesh.area_faces.min()),
                        degenerate_face_indices=np.flatnonzero(mesh.area_faces <= MeshValidator().degenerate_face_epsilon_mm2).tolist(),
                        timings_ms={'fusion_preparation':(prepared-started)*1000,
                            'boolean_union':(fused-prepared)*1000,'final_connectivity':(connected-fused)*1000,
                            'mesh_validation':(validated-connected)*1000,'total':(validated-started)*1000})
                tolerance = source['tolerances']['distance_mm']
                if not np.allclose(mesh.bounds,np.asarray(source['bounds_mm']),rtol=0,atol=tolerance):
                    raise FabricFusionFailure('bounds','融合改变了设计边界，已阻止就绪。',
                        candidate_bounds_mm=source['bounds_mm'],final_bounds_mm=mesh.bounds.tolist())
                report = {'schema_version':'1.0','kind':'final_fabric_mesh',
                    'document_id':source['document_id'],'document_revision':source['document_revision'],
                    'document_fingerprint':source.get('document_fingerprint'),
                    'final_fabric_mesh_id':'fabric-final-'+key,'final_fabric_mesh_ready':True,
                    'fused':True,'export_available':False,'backend':'manifold3d-mesh64',
                    'backend_version':version('manifold3d'),'interface_overlap_mm':0,
                    'fusion_strategy':'balanced_tree_mesh64',
                    'exact_contact_component_count':exact_components,
                    'max_bottom_extension_mm':0,'top_z_preserved':True,
                    'bounds_mm':mesh.bounds.tolist(),'candidate_bounds_mm':source['bounds_mm'],
                    'enabled_instance_count':source['enabled_instance_count'],
                    'pre_component_count':source['components']['prefusion_components'],
                    'connected_component_count':validation.component_count,'watertight':validation.is_watertight,
                    'volume_mm3':volume,'validation_report':asdict(validation),'cache_hit':False,
                    'timings_ms':{'fusion_preparation':(prepared-started)*1000,
                        'boolean_union':(fused-prepared)*1000,'final_connectivity':(connected-fused)*1000,
                        'mesh_validation':(validated-connected)*1000,'total':(validated-started)*1000}}
                final = FinalFabricMesh(replace(result,component_count=validation.component_count),report)
                mesh.vertices.flags.writeable = False
                mesh.faces.flags.writeable = False
                size = mesh.vertices.nbytes+mesh.faces.nbytes
                if size <= self.max_bytes:
                    self._cache[key] = (monotonic(),FinalFabricMesh(final.mesh_result,deepcopy(report)),size,None)
                    while len(self._cache)>self.capacity or sum(v[2] for v in self._cache.values())>self.max_bytes:
                        self._cache.popitem(last=False)
                return final
            except FabricFusionFailure:
                raise
            except Exception as error:
                raise FabricFusionFailure('boolean_union','融合后端发生错误，请查看失败编号。',
                    exception_type=type(error).__name__) from error

    def export_stl(self,result_id,document_id,document_revision,document_fingerprint):
        from .fabric_stl import export_validated_fabric_stl
        key=result_id.removeprefix('fabric-final-') if result_id.startswith('fabric-final-') else ''
        with self._lock:
            entry=self._cache.get(key)
            if not entry or monotonic()-entry[0] >= self.ttl_seconds:
                raise FabricFusionFailure('stale_result','制造结果不存在或已过期，请重新生成。')
            report=entry[1].report
            if (report['document_id'] != document_id or report['document_revision'] != document_revision
                or report.get('document_fingerprint') != document_fingerprint):
                raise FabricFusionFailure('stale_result','设计已变化，请重新生成后导出。')
            if entry[3] is not None:
                return entry[3]
            artifact=export_validated_fabric_stl(entry[1])
            size=entry[2]+len(artifact[0])
            if size <= self.max_bytes:
                self._cache[key]=(entry[0],entry[1],size,artifact)
                self._cache.move_to_end(key)
                while sum(value[2] for value in self._cache.values())>self.max_bytes:
                    self._cache.popitem(last=False)
            return artifact
