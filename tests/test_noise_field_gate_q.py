"""Gate Q: deterministic continuous NoiseField through the shared field path."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ppg.foundation import Canvas, CircleElement, FoundationPipeline, PatternDocument, Reference
from ppg.foundation.svg_exporter import pattern_document_to_svg
from xiaomang_pattern_lab.evaluation import evaluate_pattern_document
from xiaomang_pattern_lab.parametric_families import SizeFieldMode, SizeFieldModifier
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.shared_fields import (
    FieldContext,
    DensityModifier,
    FieldMapping,
    FieldPositionModifier,
    FieldRegistry,
    NoiseField,
    RotationModifier,
    SharedFieldEngine,
    SizeModifier,
)
from xiaomang_pattern_lab.shared_modifiers import SharedModifierStack


def dots() -> list[CircleElement]:
    return [CircleElement("dot-%d" % index, float(index * 5), float((index % 3) * 4), 4.0, 4.0)
            for index in range(12)]


class NoiseFieldGateQTests(unittest.TestCase):
    def test_noise_is_bounded_continuous_and_repeatable(self) -> None:
        field = NoiseField("noise", scale=40, seed=42, octaves=3, contrast=1.2)
        context = FieldContext((0, 0, 100, 100))
        points = [CircleElement("p%d" % index, float(index), 12.5, 1, 1) for index in range(9)]
        values = [field.evaluate(point, context) for point in points]
        self.assertEqual(values, [field.evaluate(point, context) for point in points])
        self.assertTrue(all(0.0 <= value <= 1.0 for value in values))
        # A world-space field must vary smoothly over a one-millimetre step,
        # not behave like independent element-level random values.
        self.assertLess(max(abs(right - left) for left, right in zip(values, values[1:])), 0.20)

    def test_seed_offsets_and_engine_consumers_are_deterministic(self) -> None:
        source = dots(); before = deepcopy(source)
        first = NoiseField("noise", scale=30, seed=7, offset_x=4, offset_y=-3, octaves=4)
        second = NoiseField("noise", scale=30, seed=7, offset_x=4, offset_y=-3, octaves=4)
        other = NoiseField("noise-other", scale=30, seed=8, offset_x=4, offset_y=-3, octaves=4)
        context = FieldContext.from_elements(source)
        self.assertEqual([first.evaluate(item, context) for item in source],
                         [second.evaluate(item, context) for item in source])
        self.assertNotEqual([first.evaluate(item, context) for item in source],
                            [other.evaluate(item, context) for item in source])

        engine = SharedFieldEngine(FieldRegistry([first]), [
            SizeModifier("size", first.id, FieldMapping(.5, 1.6)),
            RotationModifier("rotation", first.id, FieldMapping(-30, 30)),
            FieldPositionModifier("position", first.id,
                                  FieldMapping(-2, 2), FieldMapping(-1, 1)),
            DensityModifier("density", first.id, threshold=.15),
        ])
        result = engine.apply(source)
        self.assertNotEqual([(item.width, item.rotation, item.x, item.visible) for item in result],
                            [(item.width, item.rotation, item.x, item.visible) for item in source])
        self.assertEqual(source, before)
        payload = engine.to_dict()
        self.assertEqual(SharedFieldEngine.from_dict(payload).apply(source), result)

    def test_legacy_size_ui_payload_save_load_preset_and_svg(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = dots()
            document = PatternDocument(Canvas(120, 80, unit="mm", mm_per_unit=1), Reference(""), source)
            session = PatternLabSession(FoundationPipeline(None, None), root, document=document)
            settings = SizeFieldModifier(
                mode=SizeFieldMode.NOISE, min_scale=.5, max_scale=1.8,
                noise_scale=24, noise_strength=.8, noise_seed=42,
                noise_offset_x=5, noise_offset_y=-2, noise_octaves=4,
                noise_contrast=1.3,
            )
            session.activate_shared_modifiers(SharedModifierStack(size_field=settings))
            final_before = session.evaluate_elements()
            self.assertEqual(session.document.fields[0]["type"], "noise")
            self.assertEqual(source, dots())
            path = session.save_document(root / "noise.pattern.json")
            preset = session.save_parametric_preset("有机噪声")
            session.undo()
            self.assertEqual(session.document.elements, dots())
            session.redo()
            self.assertEqual(session.evaluate_elements(), final_before)
            reloaded = PatternLabSession(FoundationPipeline(None, None), root / "reloaded")
            reloaded.load_document(str(path))
            self.assertEqual(reloaded.evaluate_elements(), final_before)
            self.assertIn("noise", (root / "presets" / (preset.preset_id + ".preset.json")).read_text(encoding="utf-8"))
            svg_path = pattern_document_to_svg(PatternDocument(Canvas(120, 80), Reference(""), final_before), root / "noise.svg")
            self.assertIn("<circle", svg_path.read_text(encoding="utf-8"))

    def test_document_graph_evaluation_does_not_modify_source(self) -> None:
        source = dots(); before = deepcopy(source)
        field = NoiseField("noise", scale=20, seed=99)
        graph = SharedFieldEngine(FieldRegistry([field]), [SizeModifier("size", field.id, FieldMapping(.4, 1.8))]).to_dict()
        document = PatternDocument(Canvas(120, 80), Reference(""), source,
                                   fields=graph["fields"], modifiers=graph["modifiers"])
        evaluated = evaluate_pattern_document(document)
        self.assertNotEqual([item.width for item in evaluated], [item.width for item in source])
        self.assertEqual(document.elements, before)

    def test_tk_noise_panel_commits_one_existing_shared_field_path(self) -> None:
        from xiaomang_pattern_lab.ui_harness import PatternLabApp

        with TemporaryDirectory() as directory:
            app = PatternLabApp(directory)
            try:
                app.update()
                app.session.document = PatternDocument(Canvas(120, 80), Reference(""), dots())
                app.family_size_mode_var.set(SizeFieldMode.NOISE.value)
                app.family_size_display_var.set("有机噪声")
                app.family_noise_seed_var.set("73")
                app.family_noise_scale_var.set("28")
                app._build_family_field_panel()
                with patch("xiaomang_pattern_lab.ui_harness.messagebox.showerror",
                           side_effect=AssertionError("Noise UI unexpectedly opened an error dialog")):
                    app.apply_family_fields()
                app.update()
                self.assertEqual(app.session.document.fields[0]["type"], "noise")
                self.assertEqual(app.session.document.fields[0]["parameters"]["seed"], 73)
                self.assertEqual(SharedModifierStack.from_document(app.session.document).source_snapshot(), dots())
            finally:
                app.destroy()


if __name__ == "__main__":
    unittest.main()
