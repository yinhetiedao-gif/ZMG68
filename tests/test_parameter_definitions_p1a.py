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
        self.assertEqual(set(definitions["field"]), {"linear", "wave", "ring"})
        self.assertEqual(set(definitions["modifier"]), {"size", "rotation"})
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

    def test_web_contract_exposes_engine_catalog(self):
        with TestClient(create_app()) as client:
            response = client.get("/api/v1/contract")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["parameter_definitions"], parameter_definitions())


if __name__ == "__main__":
    unittest.main()
