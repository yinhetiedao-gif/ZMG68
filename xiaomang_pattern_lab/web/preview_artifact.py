"""Read-only GLB presentation artifact from the validated manufacturing mesh."""
from __future__ import annotations

from xiaomang_pattern_lab.manufacturing_backend import ManufacturingMeshResult


def export_preview_glb(mesh_result: ManufacturingMeshResult) -> bytes:
    """Serialize the retained mesh; never regenerate or repair manufacturing geometry."""
    if not mesh_result.is_watertight or mesh_result.face_count <= 0:
        raise ValueError("只有有效的最终制造网格才能生成预览。")
    data = mesh_result.mesh.export(file_type="glb")
    if not isinstance(data, bytes) or len(data) < 20 or data[:4] != b"glTF":
        raise ValueError("最终网格未生成有效 GLB 预览。")
    return data
