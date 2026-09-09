"""Acceptance tests for Raster → Filled Geometry, independent of generators."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw

from ppg.foundation import Canvas, CircleElement, FilledRegionElement, PatternDocument, Reference, SVGNormalizer, load_pattern_document, pattern_document_to_svg
from ppg.integrations import ImageToSVGVectorizationAdapter
from xiaomang_pattern_lab.adapters import BinaryThresholdImageProcessingAdapter
from xiaomang_pattern_lab.faithful_mapping import ConversionMode, FaithfulMappingAdapter
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.ui_harness import PatternLabApp
from xiaomang_pattern_lab.view_transform import CanvasViewTransform
from ppg.foundation import FoundationPipeline
from ppg.foundation.region_geometry import filled_region_polygons


def _complex_reference(path: Path) -> None:
    """A connected black point/line/region figure that must not become outline UI."""
    image = Image.new("L", (240, 180), "white")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((20, 58, 126, 122), radius=17, fill="black")
    draw.line((112, 90, 194, 42), fill="black", width=15)
    draw.ellipse((174, 22, 216, 64), fill="black")
    draw.line((122, 106, 190, 143), fill="black", width=12)
    draw.polygon(((181, 126), (220, 151), (183, 168)), fill="black")
    draw.ellipse((61, 76, 88, 104), fill="white")
    image.save(path)


class FaithfulMappingTests(unittest.TestCase):
    def _mapper(self) -> FaithfulMappingAdapter:
        return FaithfulMappingAdapter(
            BinaryThresholdImageProcessingAdapter(),
            ImageToSVGVectorizationAdapter(mode="simple"),
            SVGNormalizer(),
        )

    def test_complex_black_structure_becomes_filled_editable_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "complex.png"; _complex_reference(source)
            result = self._mapper().map_raster(str(source), str(root / "faithful.svg"))
            document = result.document
            self.assertEqual(document.metadata["mapping_mode"], ConversionMode.FAITHFUL.value)
            self.assertFalse(document.reference.visible, "隐藏 Raster 后仍必须保留 Geometry")
            self.assertTrue(document.elements)
            self.assertTrue(any(isinstance(element, FilledRegionElement) for element in document.elements))
            for element in document.elements:
                self.assertEqual(str(element.style.get("fill")).lower(), "#000000")
                self.assertEqual(str(element.style.get("stroke")).lower(), "none")
            filled = [element for element in document.elements if isinstance(element, FilledRegionElement)]
            self.assertTrue(
                all(any(len(polygon) >= 3 for polygon in filled_region_polygons(element)) for element in filled),
                "保真 SVG 的实际闭合路径必须能被 Canvas 转为实心多边形。",
            )

            output = pattern_document_to_svg(document, str(root / "editable.svg"))
            root_node = ET.parse(output).getroot()
            geometry_nodes = [node for node in root_node if node.tag.rsplit("}", 1)[-1] in {"path", "circle", "ellipse", "rect"}]
            self.assertTrue(geometry_nodes)
            for node in geometry_nodes:
                self.assertEqual(node.attrib.get("fill"), "#000000")
                self.assertEqual(node.attrib.get("stroke"), "none")
            reread = SVGNormalizer().normalize_file(str(output), normalization_mode="semantic")
            self.assertTrue(any(isinstance(element, FilledRegionElement) for element in reread.elements))

    def test_session_defaults_to_faithful_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "complex.png"
            _complex_reference(source)
            processor = BinaryThresholdImageProcessingAdapter()
            vectorizer = ImageToSVGVectorizationAdapter(mode="simple")
            session = PatternLabSession(
                FoundationPipeline(processor, vectorizer, SVGNormalizer()),
                root,
                faithful_mapping=FaithfulMappingAdapter(processor, vectorizer, SVGNormalizer()),
            )
            document = session.import_image(str(source))
            self.assertEqual(session.conversion_mode, ConversionMode.FAITHFUL)
            self.assertEqual(document.metadata.get("mapping_mode"), ConversionMode.FAITHFUL.value)
            self.assertTrue(any(isinstance(element, FilledRegionElement) for element in document.elements))

    def test_filled_region_move_scale_duplicate_save_reload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            region = FilledRegionElement(
                id="region", x=20, y=20, width=20, height=20,
                style={"fill": "#000000", "stroke": "none"},
                path_data="M 10 10 L 30 10 L 30 30 L 10 30 Z",
                base_x=20, base_y=20, base_width=20, base_height=20,
            )
            document = PatternDocument(Canvas(80, 80, "mm", 1.0), Reference("source.png", False), [region])
            session = PatternLabSession(FoundationPipeline(None, None), root, document=document)
            session.select("region")
            session.move_selected(7, -4)
            session.resize_selected(30, 16)
            clone_id = session.duplicate_selected(5, 3)
            self.assertEqual(len(session.document.elements), 2)
            self.assertNotEqual(clone_id, "region")
            project = session.save_document(str(root / "geometry.pattern.json"))
            restored = load_pattern_document(str(project))
            self.assertEqual(restored.to_dict(), session.document.to_dict())
            svg = session.export_svg(str(root / "geometry.svg"))
            self.assertIn('data-foundation-element-type="filled_region"', svg.read_text(encoding="utf-8"))

    def test_canvas_draws_faithful_region_as_black_material_not_wireframe(self) -> None:
        """The Canvas bridge must paint polygons; a contour rectangle is a regression."""

        class FakeCanvas:
            def __init__(self):
                self.polygons = []

            def create_polygon(self, *points, **options):
                self.polygons.append((points, options))
                return len(self.polygons)

        region = FilledRegionElement(
            id="silhouette", x=30, y=25, width=40, height=30,
            style={"fill": "#000000", "stroke": "none"},
            path_data="M 10 10 L 50 10 L 50 40 L 10 40 Z",
            base_x=30, base_y=25, base_width=40, base_height=30,
        )
        harness = type("CanvasHarness", (), {})()
        harness.canvas = FakeCanvas()
        harness._view_transform = CanvasViewTransform(80, 60, 800, 600)
        item_ids = PatternLabApp._draw_filled_region(
            harness, region, fill="#000000", outline="", tags=("static", "geometry"),
        )
        self.assertEqual(item_ids, [1])
        points, options = harness.canvas.polygons[0]
        self.assertGreaterEqual(len(points), 6)
        self.assertEqual(options["fill"], "#000000")
        self.assertEqual(options["outline"], "")
        self.assertEqual(options["tags"], ("static", "geometry"))

    def test_multiselection_and_boolean_regions_are_real_document_edits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = PatternDocument(
                Canvas(100, 100, "mm", 1.0), Reference("source.png", False),
                [CircleElement("left", 30, 50, 30, 30), CircleElement("right", 50, 50, 30, 30)],
            )
            session = PatternLabSession(FoundationPipeline(None, None), root, document=document)
            session.select_many(["left", "right"])
            session.move_selected(2, 3)
            self.assertEqual((document.element("left").x, document.element("right").x), (32, 52))
            result_id = session.union_selected()
            self.assertEqual(len(document.elements), 1)
            self.assertIsInstance(document.element(result_id), FilledRegionElement)
            self.assertTrue(session.undo())
            self.assertEqual(len(session.document.elements), 2)

            # Last selected is the primary region; include right as its cutter.
            session.select("right")
            session.select("left", additive=True)
            difference_id = session.difference_selected()
            difference = session.document.element(difference_id)
            self.assertIsInstance(difference, FilledRegionElement)
            self.assertEqual(difference.style.get("fill-rule"), "evenodd")


if __name__ == "__main__":
    unittest.main()
