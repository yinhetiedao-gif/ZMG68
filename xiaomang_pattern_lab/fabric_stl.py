"""Validation-gated artifact adapter, not a second STL serialization algorithm."""
from dataclasses import asdict
from time import perf_counter
import numpy as np
from .fabric_fusion import FabricFusionFailure
from .mesh_validation import MeshValidator
from .stl_export import STLExporter, STLExportBlockedError

class _ExportTimingValidator(MeshValidator):
    """Telemetry only; returns the unchanged standard validator's report."""
    def validate(self,result):
        started=perf_counter()
        report=super().validate(result)
        self.elapsed_ms=(perf_counter()-started)*1000
        return report

def export_validated_fabric_stl(final):
    report=final.report
    if (report.get('final_fabric_mesh_ready') is not True or report.get('fused') is not True
        or report.get('connected_component_count') != 1 or report.get('watertight') is not True
        or not np.isfinite(report.get('volume_mm3',0)) or report.get('volume_mm3',0) <= 0 or report['validation_report']['error_count']
        or report['validation_report']['degenerate_face_count']):
        raise FabricFusionFailure('stl_export_gate','最终网格未通过检查，Fabric STL 不可导出。')
    started=perf_counter()
    validator=_ExportTimingValidator()
    try:
        payload=STLExporter(validator=validator).export_bytes(final.mesh_result)
    except STLExportBlockedError as error:
        raise FabricFusionFailure('stl_export','最终网格检查失败，已阻止导出。',
            validation_report=asdict(error.report),final_mesh_report=report) from error
    except (RuntimeError,ValueError,TypeError) as error:
        raise FabricFusionFailure('stl_export','STL 序列化失败，已阻止下载。',
            exception_type=type(error).__name__,final_mesh_report=report) from error
    serialized=perf_counter()
    try:
        reopened=STLExporter.reload_bytes_as_mesh_result(payload)
    except (RuntimeError,ValueError,TypeError) as error:
        raise FabricFusionFailure('stl_roundtrip','STL 无法读回，已阻止下载。',
            exception_type=type(error).__name__,final_mesh_report=report) from error
    reloaded=perf_counter()
    checked=MeshValidator().validate(reopened)
    volume=float(reopened.mesh.volume)
    # STL stores float32 positions. Check faithful readback using its explicit
    # quantization bound, never relax topology or triangle-area tolerances.
    tolerance=float(max(1e-6,float(np.abs(final.mesh_result.mesh.vertices).max())*np.finfo(np.float32).eps))
    bounds_match=np.allclose(reopened.mesh.bounds,final.mesh_result.mesh.bounds,rtol=0,atol=tolerance)
    volume_match=np.isclose(volume,report['volume_mm3'],rtol=2e-5,atol=1e-6)
    if (not checked.is_valid or not checked.is_watertight or checked.component_count != 1
        or not np.isfinite(volume) or volume <= 0 or not bounds_match or not volume_match
        or checked.face_count != final.mesh_result.face_count):
        raise FabricFusionFailure('stl_roundtrip','STL 读回检查失败，已阻止下载。',
            validation_report=asdict(checked),bounds_mm=reopened.mesh.bounds.tolist(),volume_mm3=volume,
            bounds_match=bool(bounds_match),volume_match=bool(volume_match),final_mesh_report=report,
            exporter_report={'file_size_bytes':len(payload),'format':'binary_stl'})
    return payload,{'format':'binary_stl','file_size_bytes':len(payload),'triangle_count':checked.face_count,
        'roundtrip_validation':asdict(checked),'bounds_mm':reopened.mesh.bounds.tolist(),'volume_mm3':volume,
        'bounds_tolerance_mm':tolerance,'timings_ms':{'export_validation_and_serialization':(serialized-started)*1000,
        'export_validation':validator.elapsed_ms,
        'stl_serialization':max(0,(serialized-started)*1000-validator.elapsed_ms),
        'reload':(reloaded-serialized)*1000,'roundtrip_validation':(perf_counter()-reloaded)*1000,
        'total_export':(perf_counter()-started)*1000}}
