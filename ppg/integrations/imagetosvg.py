"""Adapter for the optional upstream ujo78/imagetosvg-mcp runtime."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ppg.foundation.adapters import VectorizationResult


class ImageToSVGVectorizationAdapter:
    """Implement the Core's VectorizationAdapter protocol using an MCP bridge."""

    def __init__(self, client: Any = None, mode: str = "simple"):
        self._client = client
        self.mode = mode

    @property
    def client(self) -> Any:
        if self._client is None:
            from ppg.upstream_svg_pipeline import ImageToSVGClient
            self._client = ImageToSVGClient()
        return self._client

    def vectorize(self, image_path: str, output_svg: str) -> VectorizationResult:
        result = self.client.convert_image_to_svg(image_path, output_svg, mode=self.mode)
        path = Path(result.get("svgPath") or output_svg).resolve()
        if not path.is_file():
            raise RuntimeError("VectorizationAdapter 未生成 SVG：%s" % path)
        return VectorizationResult(str(path), "ujo78/imagetosvg-mcp", dict(result))
