"""P1-D payloads must remain compatible with the existing Python evaluator."""

from copy import deepcopy
import unittest

from ppg.foundation import Canvas, CircleElement, PatternDocument, Reference
from xiaomang_pattern_lab.evaluation import evaluate_pattern_document
from xiaomang_pattern_lab.parameter_definitions import parameter_definitions
from xiaomang_pattern_lab.shared_modifiers import PositionModifier


class WebModifierPayloadTests(unittest.TestCase):
    def test_position_schema_defaults_are_accepted_by_existing_modifier(self):
        definitions = parameter_definitions()["definitions"]["modifier"]["position"]["parameters"]
        parameters = {item["id"]: item["default"] for item in definitions}
        position = PositionModifier.from_dict(parameters)
        self.assertEqual(position.mode, "offset")
        self.assertEqual(position.offset_x, 0)
        self.assertEqual(position.radius, 100)

    def test_one_field_drives_size_and_rotation_then_position_without_source_mutation(self):
        document = PatternDocument(Canvas(100, 100, unit="mm", mm_per_unit=1), Reference(""), [
            CircleElement("a", 0, 0, 4, 4), CircleElement("b", 10, 0, 4, 4),
        ])
        document.fields = [{"id": "wave-1", "type": "wave", "parameters": {
            "angle": 0, "wavelength": 40, "phase": 0, "amplitude": 1, "offset": 0,
        }}]
        document.modifiers = [
            {"id": "size-1", "type": "size", "field_id": "wave-1", "enabled": True,
             "mapping": {"min_output": .5, "max_output": 1.5, "strength": 1, "falloff": 1}},
            {"id": "rotation-1", "type": "rotation", "field_id": "wave-1", "enabled": True,
             "mapping": {"min_output": -30, "max_output": 30, "strength": 1, "falloff": 1}},
        ]
        document.metadata["xiaomang_pattern_lab.shared_modifiers"] = {
            "version": 1, "enabled": True, "source_kind": "imported_elements",
            "source_elements": [deepcopy(item) for item in document.to_dict()["elements"]],
            "modifiers": [{"id": "position-1", "type": "position", "enabled": True,
                           "parameters": {"mode": "offset", "offset_x": 5, "offset_y": 0},
                           "scope": {"mode": "all"}}],
        }
        original = deepcopy(document.to_dict())
        result = evaluate_pattern_document(document)
        self.assertAlmostEqual(result[1].x, 15)
        self.assertGreater(result[1].width, 4)
        self.assertNotEqual(result[1].rotation, 0)
        self.assertEqual(document.to_dict(), original)
        self.assertEqual(evaluate_pattern_document(PatternDocument.from_dict(original)), result)
        document.modifiers[1]["enabled"] = False
        self.assertEqual(evaluate_pattern_document(document)[1].rotation, 0)
        document.metadata["xiaomang_pattern_lab.shared_modifiers"]["modifiers"][0]["enabled"] = False
        self.assertEqual(evaluate_pattern_document(document)[1].x, 10)


if __name__ == "__main__":
    unittest.main()
