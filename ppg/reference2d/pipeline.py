from __future__ import annotations

from .classifier import classify_image
from .features import detect_dot_features
from .fields import estimate_spatial_fields
from .importer import decode_reference
from .matching import match_generator
from .models import PreprocessConfig, Reference2DResult
from .preprocessing import preprocess_reference
from .reconstruction import build_editable_geometry, build_editable_document
from .similarity import evaluate_geometry


def analyze_reference2d(path: str, *, target_width_mm: float | None = None, config: PreprocessConfig | None = None, debug: dict | None = None) -> Reference2DResult:
    """执行 Reference → Editable 2D P0 管线，并保留旧 AnalysisResult 兼容字段。"""
    # 延迟导入避免 image_analysis 与本包的兼容桥产生循环导入。
    from ..image_analysis import analyze_reference

    legacy = analyze_reference(path)
    source = decode_reference(path, target_width_mm=target_width_mm)
    preprocessed = preprocess_reference(source, config)
    features = detect_dot_features(preprocessed.binary_mask, min_area=(config.min_area if config else 3), debug=debug)
    classification = classify_image(preprocessed, features)
    fields = estimate_spatial_fields(features)
    geometry = build_editable_geometry(features)
    generator, modifiers = match_generator(classification, fields, legacy.generator_key, features)
    similarity = evaluate_geometry(preprocessed.binary_mask, geometry)
    editable_document = build_editable_document(features, width_px=source.width_px, height_px=source.height_px, source_path=source.source_path, generator=generator, modifiers=modifiers, fields=fields.to_dict(), reference=source.metadata(), metadata={"classification": classification.to_dict(), "similarity": similarity})
    return Reference2DResult(legacy, source, preprocessed, classification, tuple(features), fields, geometry, generator, modifiers, similarity, editable_document, debug)
