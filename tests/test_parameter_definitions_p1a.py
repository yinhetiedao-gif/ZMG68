import unittest

from fastapi.testclient import TestClient

from xiaomang_pattern_lab.parameter_definitions import parameter_definitions, validate_parameter
from xiaomang_pattern_lab.web.app import create_app


class ParameterDefinitionTests(unittest.TestCase):
    def test_catalog_has_current_model_families(self):
        catalog = parameter_definitions()
        self.assertEqual(catalog["units"], "mm")
        definitions = catalog["definitions"]
        self.assertEqual(set(definitions["layout"]), {"free", "grid", "radial", "along_curve"})
        self.assertEqual(set(definitions["field"]), {
            "constant", "linear", "ring", "wave", "stripe", "checker", "spiral", "noise", "image", "distance"})
        self.assertEqual(set(definitions["modifier"]), {"size", "rotation", "position"})
        for category in definitions.values():
            for group in category.values():
                for item in group["parameters"]:
                    self.assertTrue({"id", "label", "type", "default", "value", "min", "max",
                                     "step", "unit", "options"}.issubset(item))

    def test_validation_rejects_invalid_numbers_and_enums(self):
        grid = parameter_definitions()["definitions"]["layout"]["grid"]["parameters"]
        rows = next(item for item in grid if item["id"] == "rows")
        self.assertEqual(validate_parameter(rows, 12), 12)
        for value in (0, 1.5, float("nan"), float("inf"), True):
            with self.assertRaises(ValueError):
                validate_parameter(rows, value)
        choice = {"type": "select", "options": [{"value": "a"}]}
        self.assertEqual(validate_parameter(choice, "a"), "a")
        with self.assertRaises(ValueError):
            validate_parameter(choice, "b")

    def test_recommended_slider_ranges_are_separate_from_legal_bounds(self):
        catalog = parameter_definitions()["definitions"]
        numeric = [item for groups in catalog.values() for group in groups.values()
                   for item in group["parameters"] if item["type"] in ("number", "integer")]
        self.assertGreaterEqual(len(numeric), 70)
        for item in numeric:
            self.assertTrue({"slider_min", "slider_max", "slider_step"}.issubset(item))
            if item["id"] == "seed":
                self.assertIsNone(item["slider_min"])
                continue
            self.assertLessEqual(item["min"], item["slider_min"])
            self.assertLess(item["slider_min"], item["slider_max"])
            self.assertLessEqual(item["slider_max"], item["max"])
            self.assertGreater(item["slider_step"], 0)
            if item["unit"] == "mm":
                self.assertLessEqual(item["slider_max"], 300)
        wave = catalog["field"]["wave"]["parameters"]
        wavelength = next(item for item in wave if item["id"] == "wavelength")
        self.assertEqual((wavelength["min"], wavelength["max"]), (0.01, 10000))
        self.assertEqual((wavelength["slider_min"], wavelength["slider_max"]), (1, 300))
        self.assertEqual(validate_parameter(wavelength, 750), 750)
        self.assertEqual(catalog["layout"]["radial"]["parameters"][4]["slider_max"], 360)
        self.assertEqual(catalog["modifier"]["size"]["parameters"][1]["slider_max"], 3)
        self.assertEqual(catalog["element"]["transform"]["parameters"][2]["slider_max"], 300)

    def test_web_contract_exposes_engine_catalog(self):
        with TestClient(create_app()) as client:
            response = client.get("/api/v1/contract")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["parameter_definitions"], parameter_definitions())


if __name__ == "__main__":
    unittest.main()
