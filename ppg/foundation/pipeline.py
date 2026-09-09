"""FOUNDATION 0 headless Raster → SVG → PatternDocument pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .adapters import ImageProcessingAdapter, PreprocessResult, VectorizationAdapter, VectorizationResult
from .models import PatternDocument
from .svg_normalizer import SVGNormalizer


@dataclass(frozen=True)
class FoundationResult:
    preprocess: PreprocessResult
    vectorization: VectorizationResult
    document: PatternDocument


class FoundationPipeline:
    def __init__(self, image_processor: ImageProcessingAdapter, vectorizer: VectorizationAdapter,
                 normalizer: Optional[SVGNormalizer] = None):
        self.image_processor = image_processor
        self.vectorizer = vectorizer
        self.normalizer = normalizer or SVGNormalizer()

    def import_raster(self, image_path: str, output_svg: str) -> FoundationResult:
        prepared = self.image_processor.preprocess(image_path, str(Path(output_svg).resolve().parent))
        vectorized = self.vectorizer.vectorize(prepared.image_path, output_svg)
        document = self.normalizer.normalize_file(
            vectorized.svg_path,
            # The editable geometry is reconstructed from the prepared image,
            # while the Reference layer must retain the user's original import
            # so an external UI can show original/vector/overlay comparisons.
            reference_path=image_path,
            reference_metadata={
                "preprocessor": prepared.engine,
                "preprocessed_path": prepared.image_path,
                "vectorizer": vectorized.engine,
            },
        )
        document.reference.visible = False
        document.metadata.update({"foundation_stage": "FOUNDATION 0", "vector_engine": vectorized.engine})
        return FoundationResult(prepared, vectorized, document)
