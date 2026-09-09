"""Headless acceptance runner for Xiaomang Pattern Lab's fixed image suite."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from time import perf_counter
from typing import Dict, Iterable, List

from ppg.foundation import FoundationPipeline, SVGNormalizer
from ppg.integrations import ImageToSVGVectorizationAdapter

from .adapters import BinaryThresholdImageProcessingAdapter
from .faithful_mapping import ConversionMode
from .fixtures import ROOT as FIXTURE_ROOT, build_fixed_suite, ground_truth
from .session import PatternLabSession, ViewMode


@dataclass(frozen=True)
class PatternLabMetric:
    case: str
    source_element_count: int
    detected_element_count: int
    editable_element_count: int
    primitive_types: Dict[str, int]
    matched_count: int
    mean_position_error: float
    mean_size_error: float
    conversion_time_seconds: float
    raster_hidden_geometry_intact: bool
    svg_roundtrip_preserved: bool
    save_reload_preserved: bool


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _error_metrics(elements: Iterable, truth: List[dict]) -> tuple[int, float, float]:
    remaining = list(elements)
    position_errors: List[float] = []
    size_errors: List[float] = []
    for source in truth:
        if not remaining:
            break
        element = min(remaining, key=lambda candidate: (candidate.x - source["x"]) ** 2 + (candidate.y - source["y"]) ** 2)
        remaining.remove(element)
        position_errors.append(math.dist((element.x, element.y), (source["x"], source["y"])))
        size_errors.append((abs(element.width - source["width"]) + abs(element.height - source["height"])) / 2.0)
    matched = len(position_errors)
    return matched, (sum(position_errors) / matched if matched else float("inf")), (sum(size_errors) / matched if matched else float("inf"))


def _new_session(workspace: Path) -> PatternLabSession:
    return PatternLabSession(
        FoundationPipeline(
            BinaryThresholdImageProcessingAdapter(),
            ImageToSVGVectorizationAdapter(mode="simple"),
            SVGNormalizer(),
        ),
        workspace,
    )


def run_fixed_suite(workspace: str) -> List[PatternLabMetric]:
    """Run the actual PNG → editable geometry → edit → SVG → save/load loop."""
    fixtures = build_fixed_suite()
    root = Path(workspace).resolve()
    root.mkdir(parents=True, exist_ok=True)
    report: List[PatternLabMetric] = []
    for case, image_path in fixtures.items():
        session = _new_session(root / case)
        started = perf_counter()
        # Keep FOUNDATION 0's existing dot-recognition benchmarks stable.  The
        # public/session default is Faithful Mapping; this suite specifically
        # exercises the separate semantic reconstruction route.
        document = session.import_image(str(image_path), ConversionMode.PARAMETRIC)
        elapsed = perf_counter() - started
        source = ground_truth(case)
        initial_count = len(document.elements)
        if not document.elements:
            raise AssertionError("%s 未检测到 Element" % case)
        if document.reference.visible:
            raise AssertionError("%s 的 Raster Reference 不应作为 Geometry 可见层" % case)
        if initial_count != len(source):
            raise AssertionError("%s 检测数 %d 不等于固定真值 %d" % (case, initial_count, len(source)))
        if session.view_mode is not ViewMode.OVERLAY:
            raise AssertionError("实验台默认视图必须支持叠加验证")
        # Accuracy measures the reconstruction itself, before the following
        # intentional local edit test changes one of the elements.
        matched, position_error, size_error = _error_metrics(document.elements, source)
        svg_before = Path(session.editable_svg_path)
        svg_before_hash = _file_hash(svg_before)

        original = document.elements[0]
        original_id = original.id
        session.select(original_id)
        session.move_selected(4.0, -3.0)
        session.resize_selected(original.width * 1.15, original.height * 1.10)
        duplicate_id = session.duplicate_selected(dx=9.0, dy=7.0)
        session.delete_selected()
        # Delete selected duplicate to exercise deletion, then keep a stable
        # count by duplicating the edited original before deleting the original.
        session.select(original_id)
        duplicate_id = session.duplicate_selected(dx=9.0, dy=7.0)
        session.select(original_id)
        session.delete_selected()
        if len(document.elements) != initial_count:
            raise AssertionError("%s 编辑后 Element 数量不稳定" % case)
        edited_svg = session.export_svg(str(root / case / "edited.svg"))
        if _file_hash(edited_svg) == svg_before_hash:
            raise AssertionError("%s 的编辑没有写入 SVG" % case)
        if "<image" in edited_svg.read_text(encoding="utf-8").lower():
            raise AssertionError("%s 导出 SVG 含 Raster 图层" % case)
        reread = SVGNormalizer().normalize_file(str(edited_svg), reference_path=str(image_path))
        duplicate = document.element(duplicate_id)
        reread_duplicate = reread.element(duplicate_id)
        for current, restored in ((duplicate.x, reread_duplicate.x), (duplicate.y, reread_duplicate.y),
                                  (duplicate.width, reread_duplicate.width), (duplicate.height, reread_duplicate.height)):
            if not math.isclose(current, restored, rel_tol=1e-6, abs_tol=1e-6):
                raise AssertionError("%s SVG 重读没有保留编辑" % case)
        project = session.save_document(str(root / case / "edited.pattern.json"))
        before_payload = document.to_dict()
        session.load_document(str(project))
        save_reload = session.document.to_dict() == before_payload
        if not save_reload:
            raise AssertionError("%s 保存/加载丢失 Element 数据" % case)
        report.append(PatternLabMetric(
            case=case,
            source_element_count=len(source),
            detected_element_count=initial_count,
            editable_element_count=len(document.elements),
            primitive_types=dict(sorted(Counter(item.type for item in document.elements).items())),
            matched_count=matched,
            mean_position_error=round(position_error, 6),
            mean_size_error=round(size_error, 6),
            conversion_time_seconds=round(elapsed, 6),
            raster_hidden_geometry_intact=True,
            svg_roundtrip_preserved=True,
            save_reload_preserved=save_reload,
        ))
    report_path = root / "pattern-lab-report.json"
    report_path.write_text(json.dumps([asdict(metric) for metric in report], ensure_ascii=False, indent=2), encoding="utf-8")
    return report
