"""Gate T-Core: minimum read-only checks for final 2D manufacturing geometry."""
from __future__ import annotations

import math
from pathlib import Path
import tempfile
import unittest

from ppg.foundation import (
    Canvas,
    CircleElement,
    FilledRegionElement,
    FoundationPipeline,
    PathElement,
    PatternDocument,
    Reference,
)
from xiaomang_pattern_lab.geometry_validation import GeometryValidator
from xiaomang_pattern_lab.parametric import GridParametricModel
from xiaomang_pattern_lab.session import PatternLabSession


def circle(identifier: str = "circle-1", *, width: float = 10.0) -> CircleElement:
    return CircleElement(id=identifier, x=20.0, y=20.0, width=width, height=width, style={"fill": "#000"})


def region(identifier: str, path_data: str) -> FilledRegionElement:
    return FilledRegionElement(
        id=identifier, x=10.0, y=10.0, width=20.0, height=20.0,
        path_data=path_data, base_x=10.0, base_y=10.0,
        base_width=20.0, base_height=20.0, style={"fill": "#000"},
    )


def document(elements):
    return PatternDocument(Canvas(100, 100, "mm", 1.0), Reference("", False), list(elements))


class GeometryValidationCoreTests(unittest.TestCase):
    def test_normal_circle_is_a_valid_closed_material_primitive(self):
        report = GeometryValidator().validate_document(document([circle()]))
        self.assertTrue(report.is_valid)
        self.assertEqual((report.checked_count, report.valid_count, report.error_count), (1, 1, 0))

    def test_near_zero_circle_is_reported_with_epsilon(self):
        item = circle(width=1.0)
        item.width = item.height = 1e-9  # simulate corrupted/imported final geometry
        report = GeometryValidator().validate_document(document([item]))
        self.assertEqual(report.error_count, 1)
        self.assertEqual(report.issues[0].issue_type, "degenerate_geometry")

    def test_non_finite_coordinate_is_invalid(self):
        item = circle()
        item.x = math.nan
        report = GeometryValidator().validate_document(document([item]))
        self.assertEqual(report.issues[0].issue_type, "invalid_geometry")

    def test_normal_filled_polygon_passes(self):
        item = region("square", "M 0 0 L 20 0 L 20 20 L 0 20 Z")
        report = GeometryValidator().validate_document(document([item]))
        self.assertTrue(report.is_valid)
        self.assertEqual(report.valid_count, 1)

    def test_bow_tie_closed_path_reports_self_intersection(self):
        item = region("bow-tie", "M 0 0 L 20 20 L 0 20 L 20 0 Z")
        report = GeometryValidator().validate_document(document([item]))
        self.assertIn("self_intersection", {issue.issue_type for issue in report.issues})

    def test_near_zero_area_polygon_is_degenerate(self):
        item = region("thin", "M 0 0 L 20 0.0000000001 L 40 0 Z")
        report = GeometryValidator(epsilon=1e-4).validate_document(document([item]))
        self.assertIn("degenerate_geometry", {issue.issue_type for issue in report.issues})

    def test_legitimate_open_line_is_not_an_open_material_error(self):
        item = PathElement(
            id="open-line", x=10.0, y=10.0, width=20.0, height=1.0,
            path_data="M 0 0 L 20 0", base_width=20.0, base_height=1.0,
            style={"fill": "none", "stroke": "#000"},
        )
        report = GeometryValidator().validate_document(document([item]))
        self.assertTrue(report.is_valid)
        self.assertFalse(any(issue.issue_type == "open_contour" for issue in report.issues))

    def test_filled_region_without_close_is_an_error(self):
        item = region("not-closed", "M 0 0 L 20 0 L 20 20")
        report = GeometryValidator().validate_document(document([item]))
        self.assertIn("open_contour", {issue.issue_type for issue in report.issues})

    def test_session_validates_final_evaluated_grid_without_mutation_or_undo(self):
        model = GridParametricModel(rows=2, columns=3, spacing_x=10, spacing_y=12,
                                    element_width=5, element_height=5, offset_x=20, offset_y=20)
        with tempfile.TemporaryDirectory() as temporary:
            source = document(model.generate())
            session = PatternLabSession(FoundationPipeline(None, None), Path(temporary), document=source)
            session.activate_grid(model)
            before = session.document.to_dict()
            revision = session.revision
            undo_count = session.undo_record_count
            report = session.validate_final_geometry()
            self.assertTrue(report.is_valid)
            self.assertEqual((report.checked_count, report.valid_count), (6, 6))
            self.assertEqual(session.document.to_dict(), before)
            self.assertEqual(session.revision, revision)
            self.assertEqual(session.undo_record_count, undo_count)


if __name__ == "__main__":
    unittest.main()
