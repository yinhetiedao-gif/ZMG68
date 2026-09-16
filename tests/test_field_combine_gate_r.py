"""Gate R contract: composable scalar fields stay inside SharedFieldEngine."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ppg.foundation import Canvas, CircleElement, FoundationPipeline, PatternDocument, Reference
from ppg.foundation.svg_exporter import pattern_document_to_svg
from xiaomang_pattern_lab.evaluation import evaluate_pattern_document
from xiaomang_pattern_lab.presets import ParametricPreset
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.shared_fields import (
    CompositeField, ConstantField, FieldContext, FieldMapping, FieldRegistry,
    LinearField, RotationModifier, SharedFieldEngine, SizeModifier,
)


def dots():
    return [CircleElement("dot-%d" % value, float(value * 10), 10.0, 5.0, 5.0)
            for value in range(3)]


class FieldCombineGateRTests(unittest.TestCase):
    def setUp(self):
        self.context = FieldContext((0, 0, 20, 20))
        self.element = CircleElement("probe", 10, 10, 2, 2)

    def test_all_operators_are_bounded_and_nested(self):
        for operator, expected in {
            "add": .75, "multiply": .125, "min": .25, "max": .5, "blend": .3125,
        }.items():
            with self.subTest(operator=operator):
                registry = FieldRegistry([
                    ConstantField("a", .25), ConstantField("b", .5),
                    CompositeField("combined", "a", "b", operator, .25),
                ])
                self.assertAlmostEqual(registry.evaluate("combined", self.element, self.context), expected)
        nested = FieldRegistry([
            ConstantField("a", .25), ConstantField("b", .5),
            CompositeField("sum", "a", "b", "add"),
            CompositeField("nested", "sum", "a", "multiply"),
        ])
        self.assertEqual(nested.evaluate("nested", self.element, self.context), .1875)

    def test_cycles_are_rejected_and_missing_inputs_are_safe_neutral(self):
        with self.assertRaisesRegex(ValueError, "混合比例"):
            CompositeField("bad-mix", "a", "b", "blend", 1.01)
        with self.assertRaisesRegex(ValueError, "循环引用"):
            SharedFieldEngine(FieldRegistry([
                CompositeField("a", "a", "b"), ConstantField("b", .5),
            ]), [])
        with self.assertRaisesRegex(ValueError, "循环引用"):
            SharedFieldEngine(FieldRegistry([
                CompositeField("a", "b", "base"), CompositeField("b", "a", "base"),
                ConstantField("base", .5),
            ]), [])
        registry = FieldRegistry([CompositeField("safe", "lost", "kept", "blend", .2),
                                  ConstantField("kept", 1.0)])
        self.assertAlmostEqual(registry.evaluate("safe", self.element, self.context), .6)
        restored = FieldRegistry.from_list([
            {"id": "safe", "type": "composite", "parameters": {
                "input_a_field_id": "lost", "input_b_field_id": "kept", "operator": "blend", "mix": .2}},
            {"id": "kept", "type": "constant", "parameters": {"value": 1.0}},
        ])
        self.assertAlmostEqual(restored.evaluate("safe", self.element, self.context), .6)

    def test_engine_consumers_keep_source_and_graph_roundtrip(self):
        source, before = dots(), deepcopy(dots())
        registry = FieldRegistry([
            LinearField("horizontal"), ConstantField("half", .5),
            CompositeField("field", "horizontal", "half", "blend", .4),
        ])
        engine = SharedFieldEngine(registry, [
            SizeModifier("size", "field", FieldMapping(.5, 1.5)),
            RotationModifier("rotation", "field", FieldMapping(-30, 30)),
        ])
        result = engine.apply(source)
        self.assertEqual(source, before)
        self.assertNotEqual(result, source)
        payload = json.loads(json.dumps(engine.to_dict()))
        self.assertEqual(SharedFieldEngine.from_dict(payload).apply(source), result)
        self.assertIn("composite", [field["type"] for field in payload["fields"]])

    def test_dependency_protection_document_save_preset_and_svg(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            engine = SharedFieldEngine(FieldRegistry([
                LinearField("x"), ConstantField("flat", .5),
                CompositeField("combined", "x", "flat", "multiply"),
            ]), [SizeModifier("size", "combined", FieldMapping(.4, 1.6))])
            with self.assertRaisesRegex(ValueError, "仍被组合场引用"):
                engine.fields.remove("x")
            graph = engine.to_dict()
            document = PatternDocument(Canvas(40, 30), Reference(""), dots(),
                                       fields=graph["fields"], modifiers=graph["modifiers"])
            expected = evaluate_pattern_document(document)
            session = PatternLabSession(FoundationPipeline(None, None), root, document=document)
            path = session.save_document(root / "combined.pattern.json")
            restored = PatternLabSession(FoundationPipeline(None, None), root / "again")
            restored.load_document(str(path))
            self.assertEqual(restored.evaluate_elements(), expected)
            preset = ParametricPreset("组合场", fields=graph["fields"], modifiers=graph["modifiers"])
            self.assertEqual(ParametricPreset.from_dict(preset.to_dict()).fields, graph["fields"])
            session.preset_repository.save(preset)
            target = PatternLabSession(FoundationPipeline(None, None), root / "preset-target",
                                       document=PatternDocument(Canvas(80, 60), Reference(""), dots()))
            # Use the source repository deliberately: applying a preset must
            # preserve its internal field references rather than remapping
            # only some IDs and accidentally joining the wrong input.
            target.workspace = root
            target.apply_parametric_preset(preset.preset_id)
            self.assertEqual(target.document.modifiers[0]["field_id"], "combined")
            self.assertEqual([item["id"] for item in target.document.fields],
                             [item["id"] for item in graph["fields"]])
            svg = pattern_document_to_svg(PatternDocument(Canvas(40, 30), Reference(""), expected), root / "combined.svg")
            self.assertIn("<circle", svg.read_text(encoding="utf-8"))

    def test_tk_panel_commits_one_composite_graph_transaction(self):
        from xiaomang_pattern_lab.ui_harness import PatternLabApp

        with TemporaryDirectory() as directory:
            app = PatternLabApp(directory)
            try:
                graph = SharedFieldEngine(FieldRegistry([
                    LinearField("x"), ConstantField("half", .5),
                ]), [SizeModifier("size", "x", FieldMapping(.5, 1.5))]).to_dict()
                app.session.document = PatternDocument(Canvas(40, 30), Reference(""), dots(),
                                                       fields=graph["fields"], modifiers=graph["modifiers"])
                app._refresh_composite_field_choices()
                app.composite_input_a_var.set("x")
                app.composite_input_b_var.set("half")
                app.composite_operator_var.set("混合")
                app.composite_mix_var.set("0.25")
                app.apply_composite_field(); app.update()
                document = app.session.document
                self.assertEqual(len(app.session._undo_stack), 1)
                self.assertIn("composite", [item["type"] for item in document.fields])
                self.assertEqual(document.modifiers[0]["field_id"], "composite-field")
                app.session.undo()
                self.assertEqual(app.session.document.modifiers[0]["field_id"], "x")
                app.session.redo()
                self.assertEqual(app.session.document.modifiers[0]["field_id"], "composite-field")
            finally:
                app.destroy()

    def test_tk_panel_can_add_a_second_existing_family_input(self):
        from xiaomang_pattern_lab.parametric_families import SizeFieldMode
        from xiaomang_pattern_lab.ui_harness import PatternLabApp

        with TemporaryDirectory() as directory:
            app = PatternLabApp(directory)
            try:
                graph = SharedFieldEngine(FieldRegistry([LinearField("x")]), [
                    SizeModifier("size", "x", FieldMapping(.5, 1.5))]).to_dict()
                app.session.document = PatternDocument(Canvas(40, 30), Reference(""), dots(),
                                                       fields=graph["fields"], modifiers=graph["modifiers"])
                app.family_size_mode_var.set(SizeFieldMode.NOISE.value)
                app.family_noise_seed_var.set("7")
                app.add_current_family_field_input(); app.update()
                identifiers = [item["id"] for item in app.session.document.fields]
                self.assertIn("x", identifiers)
                self.assertEqual(app.composite_input_b_var.get(), "composite-input-1")
                self.assertIn("composite-input-1", identifiers)
            finally:
                app.destroy()


if __name__ == "__main__":
    unittest.main()
