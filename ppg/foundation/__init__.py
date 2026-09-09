"""FOUNDATION 0 — third-party-neutral editable vector document core.

This package intentionally has no UI, generator, renderer, or manufacturing
dependency.  It owns the stable PatternDocument data model only.
"""

from .adapters import (
    ImageProcessingAdapter,
    PassthroughImageProcessingAdapter,
    VectorizationAdapter,
)
from .models import (
    Canvas,
    CircleElement,
    EllipseElement,
    FilledRegionElement,
    Group,
    PathElement,
    PatternDocument,
    RectElement,
    Reference,
    Transform,
)
from .pipeline import FoundationPipeline
from .storage import load_pattern_document, save_pattern_document
from .svg_exporter import pattern_document_to_svg
from .svg_normalizer import SVGNormalizer

__all__ = [
    "Canvas", "Reference", "Transform", "Group", "PatternDocument",
    "CircleElement", "EllipseElement", "RectElement", "PathElement", "FilledRegionElement",
    "ImageProcessingAdapter", "VectorizationAdapter",
    "PassthroughImageProcessingAdapter",
    "SVGNormalizer", "FoundationPipeline", "pattern_document_to_svg",
    "save_pattern_document", "load_pattern_document",
]
