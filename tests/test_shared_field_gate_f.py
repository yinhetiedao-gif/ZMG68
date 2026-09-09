"""Gate F: final compatibility and source-integrity pass for shared fields."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ppg.foundation import Canvas, CircleElement, FoundationPipeline, PatternDocument, Reference, load_pattern_document
from ppg.foundation.svg_exporter import pattern_document_to_svg
from xiaomang_pattern_lab.evaluation import evaluate_pattern_document, materialize_evaluated_elements
from xiaomang_pattern_lab.parametric import GridParametricModel, PARAMETRIC_METADATA_KEY
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.shared_fields import (
    CheckerField, FieldMapping, FieldRegistry, RingField, RotationModifier, SharedFieldEngine,
    SizeModifier, SpiralField, StripeField, WaveField,
)


def source():
    return [CircleElement("a", -20, 0, 4, 4), CircleElement("b", 0, 0, 4, 4), CircleElement("c", 20, 0, 4, 4)]


class SharedFieldGateFTests(unittest.TestCase):
    def test_document_without_fields_is_legacy_compatible(self):
        document = PatternDocument(Canvas(80, 40), Reference(""), source())
        before = deepcopy(document.elements)
        self.assertEqual(evaluate_pattern_document(document), before)
        self.assertEqual(document.elements, before)

    def test_disable_all_and_repeated_evaluate_preserve_source(self):
        document = PatternDocument(Canvas(80, 40), Reference(""), source())
        before = deepcopy(document.elements)
        for field in (
            RingField("ring", radius=20, ring_width=10),
            WaveField("wave", wavelength=30),
            StripeField("stripe", period=30),
            CheckerField("checker", cell_width=20, cell_height=20),
            SpiralField("spiral", turns=3),
        ):
            engine = SharedFieldEngine(FieldRegistry([field]), [SizeModifier("size", field.id, FieldMapping(1, 2))])
            document.fields, document.modifiers = engine.to_dict()["fields"], engine.to_dict()["modifiers"]
            first = evaluate_pattern_document(document)
            second = evaluate_pattern_document(document)
            self.assertEqual(first, second)
            self.assertEqual(document.elements, before)
        document.fields, document.modifiers = [], []
        self.assertEqual(evaluate_pattern_document(document), before)

    def test_all_field_graphs_roundtrip_and_svg_materialization(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for field in (
                RingField("ring", radius=20, ring_width=10), WaveField("wave", wavelength=30),
                StripeField("stripe", period=30), CheckerField("checker", cell_width=20, cell_height=20),
                SpiralField("spiral", turns=3),
            ):
                engine = SharedFieldEngine(FieldRegistry([field]), [
                    SizeModifier("size", field.id, FieldMapping(1, 2)),
                    RotationModifier("rotation", field.id, FieldMapping(-10, 10)),
                ])
                payload = engine.to_dict()
                document = PatternDocument(Canvas(80, 40), Reference(""), source(),
                    fields=payload["fields"], modifiers=payload["modifiers"])
                session = PatternLabSession(FoundationPipeline(None, None), root / field.id, document=document)
                path = session.save_document(root / (field.id + ".pattern.json"))
                restored = load_pattern_document(str(path))
                self.assertEqual(restored.fields, document.fields)
                self.assertEqual(restored.modifiers, document.modifiers)
                materialize_evaluated_elements(restored)
                svg = pattern_document_to_svg(restored, str(root / (field.id + ".svg")))
                self.assertTrue(svg.exists())
                self.assertIn('id="a"', svg.read_text(encoding="utf-8"))

    def test_grid_structure_survives_shared_field_evaluation(self):
        model = GridParametricModel(rows=2, columns=3, spacing_x=15, spacing_y=12, element_width=4)
        before = model.generate()
        engine = SharedFieldEngine(FieldRegistry([CheckerField("checker", cell_width=15, cell_height=12)]),
                                   [SizeModifier("size", "checker", FieldMapping(1, 2))])
        payload = engine.to_dict()
        document = PatternDocument(Canvas(100, 80), Reference(""), before,
            metadata={PARAMETRIC_METADATA_KEY: {"mode": "grid", "grid": model.to_dict()}},
            fields=payload["fields"], modifiers=payload["modifiers"])
        evaluated = evaluate_pattern_document(document)
        self.assertEqual([item.id for item in evaluated], [item.id for item in before])
        self.assertEqual(model.rows, 2); self.assertEqual(model.columns, 3)
        self.assertEqual(model.spacing_x, 15); self.assertEqual(model.spacing_y, 12)


if __name__ == "__main__":
    unittest.main()
