"""FOUNDATION 0 acceptance tests — entirely headless, no UI or generators."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
import shutil
import unittest
import xml.etree.ElementTree as ET

from ppg.foundation import (
    CircleElement,
    EllipseElement,
    FoundationPipeline,
    PassthroughImageProcessingAdapter,
    SVGNormalizer,
    load_pattern_document,
    pattern_document_to_svg,
    save_pattern_document,
)
from ppg.foundation.adapters import PreprocessResult, VectorizationResult
from ppg.integrations import ImageToSVGVectorizationAdapter


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
OUT = ROOT / "work" / "foundation0"
CASES = (
    "test_dot_grid.png",
    "test_dot_gradient.png",
    "test_dot_star.png",
    "test_dense_dot_matrix.png",
    "test_simple_geometry.png",
)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Foundation0AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.fixtures.generate_foundation0_fixtures import dense_dot_matrix, simple_geometric_pattern
        dense_dot_matrix()
        simple_geometric_pattern()
        OUT.mkdir(parents=True, exist_ok=True)
        cls.pipeline = FoundationPipeline(
            PassthroughImageProcessingAdapter(),
            ImageToSVGVectorizationAdapter(mode="simple"),
            SVGNormalizer(),
        )

    def test_native_svg_primitives_and_reliable_path_recovery(self):
        document = SVGNormalizer().normalize_file(str(FIXTURES / "native_primitives.svg"))
        self.assertEqual(
            [element.type for element in document.elements],
            ["circle", "ellipse", "rect", "rect", "ellipse", "path"],
        )
        self.assertTrue(any(isinstance(element, CircleElement) for element in document.elements))
        self.assertEqual(document.groups[0].element_ids, [element.id for element in document.elements])
        # A non-uniform size edit of a circle must remain real geometry, so the
        # document promotes it to an ellipse rather than losing its height on SVG export.
        circle = next(element for element in document.elements if isinstance(element, CircleElement))
        resized = document.resize_element(circle.id, 16.0, 9.0)
        self.assertIsInstance(resized, EllipseElement)
        self.assertEqual((resized.width, resized.height), (16.0, 9.0))
        output = OUT / "native-primitives-roundtrip.svg"
        pattern_document_to_svg(document, str(output))
        root = ET.parse(str(output)).getroot()
        self.assertEqual(root.tag.rsplit("}", 1)[0].strip("{"), "http://www.w3.org/2000/svg")
        self.assertTrue(root.attrib.get("viewBox"))

    def test_raster_to_vector_to_pattern_document_edit_save_load(self):
        report = []
        for fixture_name in CASES:
            source = FIXTURES / fixture_name
            case_dir = OUT / source.stem
            case_dir.mkdir(parents=True, exist_ok=True)
            vector_svg = case_dir / "vectorized.svg"
            result = self.pipeline.import_raster(str(source), str(vector_svg))
            document = result.document

            self.assertTrue(vector_svg.is_file(), fixture_name)
            self.assertFalse(document.reference.visible, fixture_name)
            self.assertGreater(len(document.elements), 0, fixture_name)
            self.assertTrue(all(element.type in {"circle", "ellipse", "rect", "path"} for element in document.elements))
            self.assertNotIn("<image", vector_svg.read_text(encoding="utf-8").lower())

            initial_count = len(document.elements)
            original = document.elements[0]
            original_id = original.id
            original_position = (original.x, original.y)
            original_size = (original.width, original.height)

            # Required real element operations: move, resize, duplicate, delete.
            document.move_element(original_id, 7.0, 3.0)
            document.resize_element(original_id, original.width * 1.25, original.height * 1.10)
            duplicate = document.duplicate_element(original_id, dx=11.0, dy=5.0)
            deleted = document.delete_element(original_id)
            self.assertEqual(deleted.id, original_id)
            self.assertNotIn(original_id, [element.id for element in document.elements])
            self.assertIn(duplicate.id, [element.id for element in document.elements])
            self.assertEqual(len(document.elements), initial_count)
            self.assertNotEqual((duplicate.x, duplicate.y), original_position)
            self.assertNotEqual((duplicate.width, duplicate.height), original_size)

            editable_svg = case_dir / "editable.svg"
            pattern_document_to_svg(document, str(editable_svg))
            self.assertTrue(editable_svg.is_file())
            self.assertNotEqual(_hash(vector_svg), _hash(editable_svg), "SVG 编辑没有物化到文件：%s" % fixture_name)
            self.assertNotIn("<image", editable_svg.read_text(encoding="utf-8").lower())

            reread = SVGNormalizer().normalize_file(str(editable_svg), reference_path=str(source))
            self.assertEqual(len(reread.elements), initial_count)
            reread_duplicate = reread.element(duplicate.id)
            self.assertAlmostEqual(reread_duplicate.x, duplicate.x, places=5)
            self.assertAlmostEqual(reread_duplicate.y, duplicate.y, places=5)
            self.assertAlmostEqual(reread_duplicate.width, duplicate.width, places=5)
            self.assertAlmostEqual(reread_duplicate.height, duplicate.height, places=5)

            project_path = case_dir / "document.pattern.json"
            save_pattern_document(document, str(project_path))
            loaded = load_pattern_document(str(project_path))
            self.assertEqual(document.to_dict(), loaded.to_dict())

            report.append({
                "fixture": fixture_name,
                "vector_engine": result.vectorization.engine,
                "element_count": initial_count,
                "element_types": sorted({element.type for element in document.elements}),
                "element_type_counts": dict(sorted(Counter(element.type for element in document.elements).items())),
                "reference_visible": document.reference.visible,
                "vector_svg": str(vector_svg),
                "editable_svg": str(editable_svg),
                "pattern_document": str(project_path),
                "deleted_id": original_id,
                "duplicate_id": duplicate.id,
                "operations_verified": ["move", "resize", "duplicate", "delete", "svg-reload"],
                "save_load_equal": document.to_dict() == loaded.to_dict(),
            })
        report_path = OUT / "foundation0-acceptance-report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        self.assertTrue(report_path.is_file())

    def test_vectorization_adapter_is_replaceable(self):
        class StaticVectorizer:
            def vectorize(self, image_path: str, output_svg: str) -> VectorizationResult:
                target = Path(output_svg)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(FIXTURES / "native_primitives.svg", target)
                return VectorizationResult(str(target), "test-static-vectorizer", {"source": image_path})

        pipeline = FoundationPipeline(PassthroughImageProcessingAdapter(), StaticVectorizer(), SVGNormalizer())
        result = pipeline.import_raster(str(FIXTURES / "test_dot_grid.png"), str(OUT / "replaceable-engine.svg"))
        self.assertEqual(result.vectorization.engine, "test-static-vectorizer")
        self.assertEqual([element.type for element in result.document.elements][:3], ["circle", "ellipse", "rect"])
        self.assertEqual(result.document.metadata["vector_engine"], "test-static-vectorizer")

    def test_image_processing_adapter_is_replaceable(self):
        class StaticProcessor:
            def preprocess(self, image_path: str, output_dir: str = None) -> PreprocessResult:
                return PreprocessResult(str(FIXTURES / "test_dot_grid.png"), "test-static-processor", {"changed": True})

        class StaticVectorizer:
            def vectorize(self, image_path: str, output_svg: str) -> VectorizationResult:
                target = Path(output_svg)
                shutil.copyfile(FIXTURES / "native_primitives.svg", target)
                return VectorizationResult(str(target), "test-static-vectorizer")

        result = FoundationPipeline(StaticProcessor(), StaticVectorizer(), SVGNormalizer()).import_raster(
            str(FIXTURES / "test_dot_gradient.png"), str(OUT / "replaceable-processor.svg")
        )
        self.assertEqual(result.preprocess.engine, "test-static-processor")
        self.assertEqual(result.document.reference.metadata["preprocessor"], "test-static-processor")


if __name__ == "__main__":
    unittest.main()
