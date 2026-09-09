from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageDraw

from .models import Document2D
from .primitive_recognizer import PrimitiveRecognizer
from .reference2d_service import Reference2DService
from .svg_parser import SVGParser


FIXTURE_DOTS = (
    (24, 22, 4), (56, 22, 6), (92, 22, 9), (132, 22, 5),
    (24, 56, 8), (56, 56, 6), (92, 56, 4), (132, 56, 7),
    (24, 92, 5), (56, 92, 9), (92, 92, 7), (132, 92, 4),
)


def create_dot_halftone_fixture(path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("L", (160, 120), "white")
    drawer = ImageDraw.Draw(image)
    for x, y, radius in FIXTURE_DOTS:
        drawer.ellipse((x - radius, y - radius, x + radius, y + radius), fill="black")
    image.save(path)
    return path


def render_geometry(document: Document2D, path: str | Path) -> Path:
    """仅渲染 GeometryLayer，用于“隐藏原图仍存在”的可视化回归证据。"""
    path = Path(path)
    image = Image.new("RGB", (round(document.reference_layer.width), round(document.reference_layer.height)), "white")
    drawer = ImageDraw.Draw(image)
    for dot in document.geometry_layer.dots:
        drawer.ellipse(
            (dot.x - dot.radius_x, dot.y - dot.radius_y, dot.x + dot.radius_x, dot.y + dot.radius_y),
            fill=dot.fill,
        )
    image.save(path)
    return path


def run(output_dir: str | Path, trace_validation_svg: str | Path | None = None) -> dict[str, object]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    source = create_dot_halftone_fixture(output / "dot_halftone_input.png")
    result = Reference2DService().reconstruct(source, output / "dot_halftone_vtracer.svg")
    document = result.document
    document.hide_reference()
    render_geometry(document, output / "geometry_reference_hidden.png")

    first = document.geometry_layer.dots[0]
    document.select_at(first.x, first.y)
    before_radius = first.radius_x
    document.set_dot_radius(first.id, before_radius * 1.5)
    document.move_dot(first.id, first.x + 3, first.y + 2)
    edited = document.geometry_layer.get_dot(first.id)
    document.delete_selected()
    project_path = output / "editable_geometry_project.json"
    document.save(project_path)
    restore_process = subprocess.run(
        [sys.executable, "-m", "reference2d_poc.restore_check", str(project_path)],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )
    restored_payload = json.loads(restore_process.stdout)

    (output / "dot_objects.json").write_text(
        json.dumps([dot.to_dict() for dot in document.geometry_layer.dots], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report = {
        **result.report(),
        "reference_visible_after_reconstruction": document.reference_layer.visible,
        "geometry_count_after_delete": len(document.geometry_layer.dots),
        "single_dot_edit": {
            "id": edited.id,
            "radius_before": before_radius,
            "radius_after": edited.radius_x,
            "position_after": [edited.x, edited.y],
            "deleted": edited.id not in {dot.id for dot in document.geometry_layer.dots},
        },
        "saved_project": str(project_path),
        "restored_geometry_count": restored_payload["geometry_count"],
        "restored_reference_visible": restored_payload["reference_visible"],
        "restored_in_fresh_process": True,
        "restored_without_reanalysis": True,
    }
    if trace_validation_svg:
        trace_path = Path(trace_validation_svg)
        if not trace_path.is_file():
            raise FileNotFoundError(f"未找到 trace 验证 SVG：{trace_path}")
        trace_paths = SVGParser().parse_file(trace_path).paths
        trace_candidates = PrimitiveRecognizer().recognize(trace_paths)
        report["trace_validation"] = {
            "svg_path": str(trace_path),
            "svg_path_count": len(trace_paths),
            "dot_count": sum(candidate.accepted_as_dot for candidate in trace_candidates),
            "rejected_count": sum(not candidate.accepted_as_dot for candidate in trace_candidates),
            "purpose": "仅开发/验证；正式运行时不调用 trace CLI",
        }
    (output / "acceptance_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Reference2D Stage A POC")
    parser.add_argument("--output", default="reference2d_poc/artifacts", help="输出目录")
    parser.add_argument("--trace-validation-svg", help="可选：由 vision-tools trace 生成的 SVG，用于独立交叉验证")
    args = parser.parse_args()
    report = run(args.output, args.trace_validation_svg)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
