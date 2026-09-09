from __future__ import annotations

"""Reference Reconstruction 的稳定服务边界。"""

from pathlib import Path

from .models import PreprocessConfig, Reference2DResult
from .pipeline import analyze_reference2d


class ReferenceReconstructionService:
    """封装 Stage A/B，保证 Stage B 失败时仍返回 Stage A 的 elements。"""

    def analyze(self, image_path: str | Path, *, target_width_mm: float | None = None,
                config: PreprocessConfig | None = None, debug: dict | None = None) -> Reference2DResult:
        return analyze_reference2d(str(image_path), target_width_mm=target_width_mm, config=config, debug=debug)

