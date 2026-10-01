"""Read-only F2.5 timing probe; run explicitly, not part of unit tests."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
import json

from ppg.integrations import ImageToSVGVectorizationAdapter
from xiaomang_pattern_lab.adapters import BinaryThresholdImageProcessingAdapter
from xiaomang_pattern_lab.connectivity import ConnectivityAnalyzer
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.evaluation import evaluate_pattern_document
from xiaomang_pattern_lab.faithful_mapping import FaithfulMappingAdapter
from xiaomang_pattern_lab.fabric_base import BaseDefinition, FabricBaseBuilder
from xiaomang_pattern_lab.fabric_cells import UnitCellDefinition
from xiaomang_pattern_lab.fabric_plan import FabricPlanner, RegularPlacement
from xiaomang_pattern_lab.fabric_preview import build_fabric_preview
from xiaomang_pattern_lab.geometry_validation import GeometryValidator
from xiaomang_pattern_lab.manufacturing_geometry import ManufacturingGeometryAdapter
from xiaomang_pattern_lab.mesh_validation import MeshValidator


def measured(name, function):
    start = perf_counter()
    value = function()
    print(f"{name}: {(perf_counter() - start) * 1000:.3f} ms", flush=True)
    return value


def main():
    fixture = Path(__file__).resolve().parents[1] / "tests/fixtures/field_manufacturing_matrix_169.jpg"
    with TemporaryDirectory() as temporary:
        document = measured("raster import", lambda: FaithfulMappingAdapter(
            BinaryThresholdImageProcessingAdapter(), ImageToSVGVectorizationAdapter(mode="simple")
        ).map_raster(str(fixture), str(Path(temporary) / "matrix.svg")).document)
        document.canvas.mm_per_unit = 1
        document.reference.source_path = ""
        document.reference.metadata["preprocessed_path"] = ""
        document.metadata["source_svg"] = ""
        document.metadata["fabric_config"] = {"config_version": 1,
            "base": {"type": "grid", "thickness_mm": .6, "margin_mm": 0,
                     "spacing_x_mm": 5, "spacing_y_mm": 5, "line_width_mm": 1},
            "unit_cell": {"type": "cone", "width_mm": 2, "depth_mm": 2, "height_mm": 3},
            "placement": {"mode": "pattern_points", "spacing_x_mm": 5, "spacing_y_mm": 5}}
        dto = PatternDocumentDTO.from_document(document, "profile-169", 1)
        start = perf_counter()
        preview = measured("new preview evaluate + plan", lambda: build_fabric_preview(document, dto))
        measured("new preview JSON serialization", lambda: json.dumps(preview, separators=(",", ":")))
        print(f"new preview total: {(perf_counter() - start) * 1000:.3f} ms", flush=True)
        print(f"new preview instances: {preview['count']}", flush=True)
        start = perf_counter()
        final = measured("old evaluate", lambda: evaluate_pattern_document(document))
        gate_t = measured("old Gate T validation", lambda: GeometryValidator().validate_elements(final))
        measured("old connectivity", lambda: ConnectivityAnalyzer().analyze_elements(final, validation_report=gate_t))
        conversion = measured("old manufacturing adapter", lambda: ManufacturingGeometryAdapter().adapt_evaluated_document(
            document, final, validation_report=gate_t))
        base = BaseDefinition.from_mapping(document.metadata["fabric_config"]["base"])
        mesh = measured("old fabric base build + extrusion", lambda: FabricBaseBuilder().build(conversion.geometry.bounds, base))
        measured("old mesh validation", lambda: MeshValidator().validate(mesh))
        measured("old instance plan", lambda: FabricPlanner().plan(conversion.geometry.bounds, .6,
            UnitCellDefinition("cone", 2, 2, 3), RegularPlacement(5, 5)))
        print(f"old full manufacturing prerequisite total: {(perf_counter() - start) * 1000:.3f} ms", flush=True)
        for count in (100, 400, 1000, 5000):
            cell = UnitCellDefinition("cone", 2, 2, 3)
            started = perf_counter()
            plan = FabricPlanner().plan((0, 0, count, 1), .6, cell, RegularPlacement(1, 1))
            planned = perf_counter()
            json.dumps(plan.preview_payload(), separators=(",", ":"))
            serialized = perf_counter()
            print(f"instances={count} plan={(planned-started)*1000:.3f} ms "
                  f"serialization={(serialized-planned)*1000:.3f} ms", flush=True)


if __name__ == "__main__":
    main()
