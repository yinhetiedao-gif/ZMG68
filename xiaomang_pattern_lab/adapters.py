"""Replaceable, non-core adapters used by the Pattern Lab harness."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Protocol

from PIL import Image

from ppg.foundation.adapters import PreprocessResult


class SVGPreviewAdapter(Protocol):
    """UI-only SVG display boundary.  It is intentionally not a Core Engine API."""

    def render(self, svg_path: str, width: int = 800) -> str:
        ...


class BinaryThresholdImageProcessingAdapter:
    """Deterministic PNG/JPG cleanup through the core ImageProcessingAdapter boundary.

    The implementation is deliberately small and disposable.  More advanced
    image-processing Skills/CLIs can replace this class without changing the
    Core Engine or PatternDocument.
    """

    def __init__(self, threshold: int = 190):
        if not 0 < int(threshold) < 256:
            raise ValueError("二值阈值必须在 1 至 255 之间。")
        self.threshold = int(threshold)

    def preprocess(self, image_path: str, output_dir: Optional[str] = None) -> PreprocessResult:
        source = Path(image_path).resolve()
        if source.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            raise ValueError("实验台仅支持 PNG、JPG、JPEG：%s" % source.suffix)
        if not source.is_file():
            raise FileNotFoundError("导入图片不存在：%s" % source)
        directory = Path(output_dir or source.parent).resolve() / "preprocessed"
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / (source.stem + "-binary.png")
        with Image.open(source) as image:
            grayscale = image.convert("L")
            binary = grayscale.point(lambda value: 0 if value < self.threshold else 255, mode="1")
            binary.convert("L").save(target)
        return PreprocessResult(
            str(target),
            "pattern-lab-binary-threshold",
            {"threshold": self.threshold, "source_path": str(source), "output_path": str(target)},
        )


class ImageToSVGMCPPreviewAdapter:
    """Thin UI adapter for the upstream render_svg capability, with no Core import."""

    def __init__(self, client: Any = None):
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            from ppg.upstream_svg_pipeline import ImageToSVGClient
            self._client = ImageToSVGClient()
        return self._client

    def render(self, svg_path: str, width: int = 800) -> str:
        result: Dict[str, Any] = self.client.render_svg(svg_path, width=width)
        preview_path = result.get("previewPath")
        if not preview_path or not Path(preview_path).is_file():
            raise RuntimeError("SVG 预览适配器未生成 PNG。")
        return str(Path(preview_path).resolve())
