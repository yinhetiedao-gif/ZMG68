"""F3.5 changes suggested sliders, never the Engine's legal parameter bounds."""
import unittest

from xiaomang_pattern_lab.parameter_definitions import parameter_definitions


class FabricRangeF35Tests(unittest.TestCase):
    def test_fabric_recommended_ranges_are_distinct_from_legal_bounds(self):
        definitions = parameter_definitions()["definitions"]
        def field(section, variant, key):
            return next(item for item in definitions[section][variant]["parameters"] if item["id"] == key)
        for section, variant in (("fabric_base", "grid"), ("fabric_placement", "regular")):
            for key in ("spacing_x_mm", "spacing_y_mm"):
                item = field(section, variant, key)
                self.assertEqual((item["slider_min"], item["slider_max"]), (.5, 50))
                self.assertGreater(item["max"], 50)
        for key in ("min_height_mm", "max_height_mm"):
            item = field("fabric_modifier", "height", key)
            self.assertEqual((item["slider_min"], item["slider_max"]), (.5, 10))
            self.assertGreater(item["max"], 10)
        for key in ("min_scale", "max_scale"):
            item = field("fabric_modifier", "scale", key)
            self.assertEqual((item["slider_min"], item["slider_max"]), (.3, 3))
            self.assertGreater(item["max"], 3)
        for key in ("min_angle_deg", "max_angle_deg"):
            item = field("fabric_modifier", "orientation", key)
            self.assertEqual((item["slider_min"], item["slider_max"]), (-180, 180))
            self.assertEqual((item["min"], item["max"]), (-360, 360))
        item = field("fabric_modifier", "density", "threshold")
        self.assertEqual((item["slider_min"], item["slider_max"]), (0, 1))
        for variant in ("cylinder", "cone", "pyramid", "double_tower", "fin"):
            mode = field("fabric_cell", variant, "size_mode")
            self.assertEqual(mode["default"], "follow_pattern")
            self.assertEqual({option["value"] for option in mode["options"]},
                             {"fixed", "follow_pattern"})
        for section, variant, key, expected in (
            ("fabric_base", "grid", "line_width_mm", (.5, 10)),
            ("fabric_cell", "fin", "width_mm", (.3, 20)),
            ("fabric_cell", "fin", "depth_mm", (.3, 20)),
            ("fabric_cell", "fin", "height_mm", (.5, 10)),
            ("fabric_base", "solid", "margin_mm", (0, 50)),
        ):
            item = field(section, variant, key)
            self.assertEqual((item["slider_min"], item["slider_max"]), expected)


if __name__ == "__main__":
    unittest.main()
