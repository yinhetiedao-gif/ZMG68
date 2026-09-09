"""Faithful Mapping: raster mask → filled, editable vector regions.

This module is an orchestration adapter, not part of ``ppg.foundation``.  The
Core still only knows ``PatternDocument`` plus its replaceable image/vector
protocols; a different raster tracer can replace this adapter's dependencies
without changing editable geometry, persistence, or the Canvas.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from ppg.foundation.adapters import ImageProcessingAdapter, PreprocessResult, VectorizationAdapter, VectorizationResult
from ppg.foundation.models import PatternDocument
from ppg.foundation.svg_normalizer import SVGNormalizer


class ConversionMode(str, Enum):
    FAITHFUL = "faithful"
    PARAMETRIC = "parametric"


@dataclass(frozen=True)
class FaithfulMappingResult:
    preprocess: PreprocessResult
    vectorization: VectorizationResult
    document: PatternDocument


class FaithfulMappingAdapter:
    """Convert black raster material into closed ``FilledRegionElement`` data.

    The vector engine supplies contour paths; the faithful normalizer converts
    every traced path into a *filled* region with ``stroke=none``.  No circle,
    line, grid, or generator inference is attempted on this route.
    """

    def __init__(self, image_processor: ImageProcessingAdapter, vectorizer: VectorizationAdapter,
                 normalizer: SVGNormalizer | None = None):
        self.image_processor = image_processor
        self.vectorizer = vectorizer
        self.normalizer = normalizer or SVGNormalizer()

    def map_raster(self, image_path: str, output_svg: str) -> FaithfulMappingResult:
        source = Path(image_path).resolve()
        prepared = self.image_processor.preprocess(str(source), str(Path(output_svg).resolve().parent))
        vectorized = self.vectorizer.vectorize(prepared.image_path, output_svg)
        document = self.normalizer.normalize_file(
            vectorized.svg_path,
            reference_path=str(source),
            reference_metadata={
                "preprocessor": prepared.engine,
                "preprocessed_path": prepared.image_path,
                "vectorizer": vectorized.engine,
                "conversion_mode": ConversionMode.FAITHFUL.value,
            },
            normalization_mode=ConversionMode.FAITHFUL.value,
        )
        document.reference.visible = False
        document.metadata.update({
            "mapping_mode": ConversionMode.FAITHFUL.value,
            "mapping_pipeline": "Raster Image → Binary Mask → Filled Vector Geometry → Editable 2D Geometry",
            "vector_engine": vectorized.engine,
        })
        return FaithfulMappingResult(prepared, vectorized, document)
