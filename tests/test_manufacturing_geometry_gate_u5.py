"""Gate U.5: Design final geometry → read-only, mm-native manufacturing areas."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from ppg.foundation import (
    Canvas, CircleElement, EllipseElement, FilledRegionElement, FoundationPipeline,
    PathElement, PatternDocument, RectElement, Reference,
)
from xiaomang_pattern_lab.connectivity import polygons_touch_or_overlap
from xiaomang_pattern_lab.manufacturing_geometry import ManufacturingGeometryAdapter
from xiaomang_pattern_lab.parametric import GridParametricModel
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.shared_modifiers import ModifierScope, ModifierScopeMode, PositionModifier, SharedModifierStack
from xiaomang_pattern_lab.parametric_families import RotationFieldModifier, SizeFieldModifier


def document(elements, *, canvas: Canvas | None = None) -> PatternDocument:
    return PatternDocument(canvas or Canvas(200, 200, "mm", 1.0), Reference("", False), list(elements))


def circle(identifier: str, x: float = 20.0, y: float = 20.0, size: float = 10.0) -> CircleElement:
    return CircleElement(identifier, x, y, size, size, style={"fill": "#000"})


def region(identifier: str, path_data: str, *, evenodd: bool = False) -> FilledRegionElement:
    style = {"fill": "#000"}
    if evenodd:
        style["fill-rule"] = "evenodd"
    return FilledRegionElement(
        identifier, 10, 10, 20, 20, style=style, path_data=path_data,
        base_x=10, base_y=10, base_width=20, base_height=20,
    )


class ManufacturingGeometryGateU5Tests(unittest.TestCase):
    def setUp(self):
        self.adapter = ManufacturingGeometryAdapter(curve_tolerance_mm=0.05)

    def test_circle_and_ellipse_become_closed_mm_polygons(self):
        result = self.adapter.adapt_document(document([
            circle("circle"), EllipseElement("ellipse", 60, 20, 20, 10, rotation=20, style={"fill": "#000"}),
        ]))
        self.assertEqual((result.report.converted_count, result.geometry.units), (2, "mm"))
        self.assertTrue(all(len(item.outer) >= 8 for item in result.geometry.polygons))
        self.assertTrue(all(item.outer[0] != item.outer[-1] for item in result.geometry.polygons))

    def test_rectangle_bounds_remain_twenty_by_ten_mm_and_are_canvas_independent(self):
        item = RectElement("rect", 40, 30, 20, 10, style={"fill": "#000"})
        source = document([item])
        first = self.adapter.adapt_document(source)
        second = self.adapter.adapt_document(source)
        self.assertEqual(first.geometry, second.geometry)
        xmin, ymin, xmax, ymax = first.geometry.bounds
        self.assertAlmostEqual(xmax - xmin, 20.0)
        self.assertAlmostEqual(ymax - ymin, 10.0)
        # Canvas zoom/pan are UI-only and absent from this document-side call.
        self.assertEqual(source.to_dict(), document([item]).to_dict())

    def test_shape_replacement_converts_final_star_not_original_circle(self):
        with tempfile.TemporaryDirectory() as temporary:
            session = PatternLabSession(FoundationPipeline(None, None), Path(temporary), document=document([circle("shape")]))
            session.select("shape")
            session.replace_selected_shape("star")
            result = session.adapt_manufacturing_geometry()
            self.assertEqual(result.report.converted_count, 1)
            self.assertGreaterEqual(len(result.geometry.polygons[0].outer), 10)

    def test_size_rotation_and_position_effects_are_taken_from_final_geometry(self):
        item = circle("effect", 10, 10, 8)
        source = document([item])
        stack = SharedModifierStack(source_elements=source.elements)
        scope = ModifierScope(mode=ModifierScopeMode.ALL)
        stack.add_modifier("size", SizeFieldModifier(min_scale=2, max_scale=2).to_dict(), scope=scope)
        stack.add_modifier("rotation", RotationFieldModifier(angle=30).to_dict(), scope=scope)
        stack.add_modifier("position", PositionModifier(mode="offset", offset_x=12, offset_y=4).to_dict(), scope=scope)
        stack.attach(source)
        result = self.adapter.adapt_document(source)
        xmin, ymin, xmax, ymax = result.geometry.bounds
        self.assertAlmostEqual((xmin + xmax) / 2, 22.0, delta=0.01)
        self.assertAlmostEqual((ymin + ymax) / 2, 14.0, delta=0.01)
        self.assertGreater(xmax - xmin, 15.5)

    def test_evenodd_hole_is_preserved_as_one_outer_with_one_hole(self):
        item = region(
            "hole", "M 0 0 L 20 0 L 20 20 L 0 20 Z M 5 5 L 15 5 L 15 15 L 5 15 Z", evenodd=True,
        )
        result = self.adapter.adapt_document(document([item]))
        self.assertEqual((result.report.converted_count, result.geometry.polygon_count), (1, 1))
        self.assertEqual(len(result.geometry.polygons[0].holes), 1)

    def test_multiple_filled_polygons_remain_multiple_manufacturing_polygons(self):
        item = region("multi", "M 0 0 L 5 0 L 5 5 L 0 5 Z M 10 10 L 15 10 L 15 15 L 10 15 Z")
        result = self.adapter.adapt_document(document([item]))
        self.assertEqual((result.report.converted_count, result.geometry.polygon_count), (1, 2))

    def test_valid_open_line_is_skipped_without_inventing_width(self):
        line = PathElement("line", 20, 20, 20, 1, style={"fill": "none", "stroke": "#000"},
                           path_data="M 0 0 L 20 0", base_width=20, base_height=1)
        result = self.adapter.adapt_document(document([line]))
        self.assertEqual((result.report.converted_count, result.report.skipped_open_count), (0, 1))
        self.assertEqual(result.report.skipped[0].reason, "unsupported_open_geometry")

    def test_invalid_geometry_is_skipped_and_reported(self):
        bad = circle("bad")
        bad.width = bad.height = 1e-9
        result = self.adapter.adapt_document(document([bad]))
        self.assertEqual((result.report.converted_count, result.report.skipped_invalid_count), (0, 1))
        self.assertEqual(result.report.skipped[0].reason, "skipped_invalid")

    def test_design_tangent_circles_stay_connected_after_conversion(self):
        source = document([circle("left", 10), circle("right", 20)])
        result = self.adapter.adapt_document(source)
        left, right = result.geometry.polygons
        self.assertTrue(polygons_touch_or_overlap((left.outer,), (right.outer,)))
        self.assertEqual(result.report.topology_changed_element_ids, ())

    def test_missing_mm_mapping_is_explicit_and_never_guessed(self):
        source = document([circle("no-mm")], canvas=Canvas(100, 100, "svg_user_unit", None))
        result = self.adapter.adapt_document(source)
        self.assertEqual((result.report.converted_count, result.report.skipped_count), (0, 1))
        self.assertIn("未声明 mm", result.report.warnings[0])

    def test_real_pattern_lab_final_geometry_is_read_only_and_deterministic(self):
        model = GridParametricModel(rows=2, columns=3, spacing_x=12, spacing_y=12,
                                    element_width=8, element_height=8, offset_x=30, offset_y=30)
        with tempfile.TemporaryDirectory() as temporary:
            session = PatternLabSession(FoundationPipeline(None, None), Path(temporary), document=document(model.generate()))
            session.activate_grid(model)
            before = deepcopy(session.document.to_dict())
            revision, undo_count = session.revision, session.undo_record_count
            first = session.adapt_manufacturing_geometry()
            second = session.adapt_manufacturing_geometry()
            self.assertEqual(first, second)
            self.assertEqual(first.report.converted_count, 6)
            self.assertEqual(session.document.to_dict(), before)
            self.assertEqual((session.revision, session.undo_record_count), (revision, undo_count))


if __name__ == "__main__":
    unittest.main()
