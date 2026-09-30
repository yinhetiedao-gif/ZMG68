"""P1-C: Web schema describes real SharedFieldEngine types; toggles are derived."""
from copy import deepcopy
import unittest

from ppg.foundation import Canvas, CircleElement, PatternDocument, Reference
from xiaomang_pattern_lab.evaluation import field_engine_from_document
from xiaomang_pattern_lab.parameter_definitions import parameter_definitions
from xiaomang_pattern_lab.shared_fields import FieldRegistry


class WebFieldTests(unittest.TestCase):
    def test_creatable_schema_defaults_load_in_existing_registry(self):
        definitions = parameter_definitions()["definitions"]["field"]
        for kind, group in definitions.items():
            parameters = {item["id"]: item["default"] for item in group["parameters"]}
            if kind == "spiral":
                parameters["direction"] = int(parameters["direction"])
            with self.subTest(kind=kind):
                self.assertEqual(FieldRegistry.from_list([
                    {"id": "web-1", "type": kind, "parameters": parameters}
                ]).to_list()[0]["type"], kind)

    def test_disabled_field_suspends_consumer_without_mutating_project(self):
        doc = PatternDocument(Canvas(100, 100), Reference(""), [
            CircleElement("a", 10, 10, 4, 4), CircleElement("b", 60, 10, 4, 4)])
        doc.fields = [{"id": "f", "type": "linear", "enabled": True,
                       "parameters": {"angle": 0, "start": 0, "end": 100}}]
        doc.modifiers = [{"id": "m", "type": "size", "field_id": "f", "enabled": True,
                          "mapping": {"min_output": .5, "max_output": 2}}]
        source = deepcopy(doc.to_dict())
        active = field_engine_from_document(doc).apply(doc.elements)
        self.assertNotEqual(active[0].width, doc.elements[0].width)
        doc.fields[0]["enabled"] = False
        disabled = field_engine_from_document(doc).apply(doc.elements)
        self.assertEqual([item.width for item in disabled], [4, 4])
        self.assertEqual(doc.modifiers, source["modifiers"])
        doc.fields[0]["enabled"] = True
        self.assertEqual(field_engine_from_document(doc).apply(doc.elements), active)

    def test_disabling_composite_input_suspends_dependent_consumer(self):
        doc = PatternDocument(Canvas(100, 100), Reference(""), [CircleElement("a", 10, 10, 4, 4)])
        doc.fields = [
            {"id": "a", "type": "constant", "parameters": {"value": .2}, "enabled": False},
            {"id": "b", "type": "constant", "parameters": {"value": .8}},
            {"id": "mix", "type": "composite", "parameters": {
                "input_a_field_id": "a", "input_b_field_id": "b", "operator": "multiply", "mix": .5}},
        ]
        doc.modifiers = [{"id": "m", "type": "size", "field_id": "mix", "enabled": True,
                          "mapping": {"min_output": .5, "max_output": 2}}]
        self.assertEqual(field_engine_from_document(doc).apply(doc.elements)[0].width, 4)


if __name__ == "__main__":
    unittest.main()
