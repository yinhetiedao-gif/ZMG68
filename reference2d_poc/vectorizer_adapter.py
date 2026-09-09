from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
import sys
from typing import Any


class VectorizationUnavailable(RuntimeError):
    """VTracer 未随运行时提供时给出的明确错误。"""


def _load_vtracer() -> Any:
    try:
        import vtracer  # type: ignore[import-not-found]

        return vtracer
    except ImportError:
        runtime_dir = Path(__file__).resolve().parents[1] / "build-tools" / "vtracer-runtime"
        if runtime_dir.is_dir() and str(runtime_dir) not in sys.path:
            sys.path.insert(0, str(runtime_dir))
        try:
            import vtracer  # type: ignore[import-not-found]

            return vtracer
        except ImportError as error:
            raise VectorizationUnavailable(
                "缺少 VTracer 运行时。请安装 vtracer==0.6.15 到 build-tools/vtracer-runtime。"
            ) from error


@dataclass(frozen=True)
class VTracerResult:
    source_path: str
    svg_path: str
    package_version: str
    options: dict[str, Any]


class VectorizerAdapter:
    """唯一接触 VTracer Python binding 的边界适配器。"""

    DEFAULT_OPTIONS: dict[str, Any] = {
        "colormode": "binary",
        "filter_speckle": 1,
        "corner_threshold": 40,
        "mode": "spline",
    }

    def version(self) -> str:
        module = _load_vtracer()
        if not any(callable(getattr(module, name, None)) for name in ("convert_image_to_svg_py", "convert_image_to_svg")):
            return "reference2d-deterministic-fallback"
        try:
            return metadata.version("vtracer")
        except metadata.PackageNotFoundError:
            return "unknown"

    def vectorize(self, source_path: str | Path, svg_path: str | Path, **overrides: Any) -> VTracerResult:
        source, target = Path(source_path), Path(svg_path)
        if not source.is_file():
            raise FileNotFoundError(f"未找到待矢量化的 PNG/JPG：{source}")
        target.parent.mkdir(parents=True, exist_ok=True)
        options = {**self.DEFAULT_OPTIONS, **overrides}
        vtracer = _load_vtracer()
        converter = getattr(vtracer, "convert_image_to_svg_py", None) or getattr(vtracer, "convert_image_to_svg", None)
        if callable(converter):
            converter(str(source), str(target), **options)
        else:
            # VTracer 只保留为轮廓/Logo 的开发兼容工具。正式 Runtime 不应因为
            # 它缺失或 ABI 不匹配而阻断 Raster → Editable Elements；回退会调用
            # 小芒造物的确定性 Primitive Detection，并输出同样可解析的 SVG。
            self._write_detection_svg(source, target)
            options["backend"] = "reference2d-deterministic-fallback"
        if not target.is_file() or target.stat().st_size == 0:
            raise RuntimeError("VTracer 未生成 SVG 输出")
        return VTracerResult(str(source), str(target), self.version(), options)

    @staticmethod
    def _write_detection_svg(source: Path, target: Path) -> None:
        from ppg.reference2d import analyze_reference2d

        result = analyze_reference2d(str(source))
        width, height = result.source.width_px, result.source.height_px
        elements = []
        for feature in result.features:
            if feature.element_type != "dot":
                continue
            elements.append(
                f'<ellipse id="detected-{feature.id}" cx="{feature.center_x / 100.0 * width:.5f}" '
                f'cy="{feature.center_y / 100.0 * height:.5f}" rx="{feature.radius_x / 100.0 * width:.5f}" '
                f'ry="{feature.radius_y / 100.0 * height:.5f}" transform="rotate({feature.rotation:.5f} {feature.center_x / 100.0 * width:.5f} {feature.center_y / 100.0 * height:.5f})" fill="#000000"/>'
            )
        target.write_text(
            f'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">{"".join(elements)}</svg>\n',
            encoding="utf-8",
        )
