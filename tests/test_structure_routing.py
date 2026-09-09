"""Regression tests for family routing and UI value normalization."""
from __future__ import annotations

import unittest

from ppg.foundation import CircleElement
from xiaomang_pattern_lab.pattern_analyzer import PatternAnalyzer
from xiaomang_pattern_lab.ui_harness import parse_float_ui_value, parse_int_ui_value


class StructureRoutingTests(unittest.TestCase):
    def test_regular_matrix_is_not_along_curve(self) -> None:
        elements = [CircleElement(id=f"g-{row}-{column}", x=20 + column * 12,
                                  y=30 + row * 12, width=4, height=4,
                                  style={"fill": "#000000"})
                    for row in range(12) for column in range(12)]
        result = PatternAnalyzer().analyze_families(elements)
        self.assertIsNotNone(result.recommended)
        self.assertEqual(result.recommended.family, "grid")
        self.assertIsNone(result.candidate("along_curve").model)

    def test_ui_numeric_values_have_explicit_types(self) -> None:
        self.assertEqual(parse_int_ui_value("12.0", "行数"), 12)
        self.assertAlmostEqual(parse_float_ui_value(" 1.25 ", "间距"), 1.25)
        with self.assertRaises(ValueError):
            parse_int_ui_value("12.5", "行数")
        with self.assertRaises(ValueError):
            parse_float_ui_value("nan", "间距")


if __name__ == "__main__":
    unittest.main()
