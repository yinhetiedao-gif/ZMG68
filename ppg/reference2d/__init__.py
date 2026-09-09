"""Reference Image → Editable 2D 的本地 P0 管线。

本包只负责点阵/半调的可解释分析与数据交接；参考位图永远不会成为生成结果。
它复用现有 ``ppg.image_analysis`` 的兼容建议字段，同时提供更完整的结构化结果，
方便后续加入线、面和新的 Generator，而不改变当前中文 UI 的产品方向。
"""
from .models import (
    ClassificationResult,
    DotFeature,
    EditableGeometry,
    PreprocessConfig,
    PreprocessedImage,
    Reference2DResult,
    ReferenceImage,
    SpatialFields,
)
from .editable_document import EditableElement, EditablePatternDocument
from .pipeline import analyze_reference2d
from .matching import fit_generator
from .rebuild import rebuild_document
from .service import ReferenceReconstructionService
from .manufacturing import document_to_primitives

__all__ = [
    "analyze_reference2d",
    "ClassificationResult",
    "DotFeature",
    "EditableGeometry",
    "PreprocessConfig",
    "PreprocessedImage",
    "Reference2DResult",
    "ReferenceImage",
    "SpatialFields",
    "EditableElement",
    "EditablePatternDocument",
    "fit_generator",
    "rebuild_document",
    "ReferenceReconstructionService",
    "document_to_primitives",
]
