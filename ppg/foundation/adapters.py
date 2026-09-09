"""Replaceable boundaries for image processing and vectorization engines."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Protocol


@dataclass(frozen=True)
class PreprocessResult:
    image_path: str
    engine: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VectorizationResult:
    svg_path: str
    engine: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class ImageProcessingAdapter(Protocol):
    """Input conditioning boundary; no core module depends on an implementation."""

    def preprocess(self, image_path: str, output_dir: Optional[str] = None) -> PreprocessResult:
        ...


class VectorizationAdapter(Protocol):
    """Raster-to-SVG boundary; engines can be exchanged without data-model changes."""

    def vectorize(self, image_path: str, output_svg: str) -> VectorizationResult:
        ...


class PassthroughImageProcessingAdapter:
    """Default FOUNDATION 0 processor for already-clean input images."""

    def preprocess(self, image_path: str, output_dir: Optional[str] = None) -> PreprocessResult:
        source = Path(image_path).resolve()
        if not source.is_file():
            raise FileNotFoundError("输入图片不存在：%s" % source)
        return PreprocessResult(str(source), "passthrough", {"changed": False})

