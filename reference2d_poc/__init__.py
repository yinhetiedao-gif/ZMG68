"""独立的 Raster Image → Editable 2D Geometry 验证闭环。

这个包刻意不依赖现有 Canvas、Generator、3D 或 STL 代码。它是后续正式
Reference2D 接入前的 Stage A 可验证实现。
"""

from .models import Document2D, DotObject, GeometryLayer, ReferenceLayer
from .reference2d_service import Reference2DService, ReconstructionResult

__all__ = [
    "Document2D",
    "DotObject",
    "GeometryLayer",
    "ReferenceLayer",
    "Reference2DService",
    "ReconstructionResult",
]
