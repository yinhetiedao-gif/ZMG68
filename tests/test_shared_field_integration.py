"""Gate A.5: PatternDocument field graph is a real evaluation input."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ppg.foundation import Canvas, CircleElement, FoundationPipeline, PatternDocument, Reference, load_pattern_document
from ppg.foundation.svg_exporter import pattern_document_to_svg
from xiaomang_pattern_lab.evaluation import evaluate_pattern_document, materialize_evaluated_elements
from xiaomang_pattern_lab.parametric import GridParametricModel, PARAMETRIC_METADATA_KEY
from xiaomang_pattern_lab.parametric_families import SizeFieldMode, SizeFieldModifier
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.shared_fields import FieldMapping, RingField, SharedFieldEngine, FieldRegistry, SizeModifier
from xiaomang_pattern_lab.shared_modifiers import SharedModifierStack


def ring_graph(*, radius: float = 10.0, ring_width: float = 4.0) -> dict:
    engine = SharedFieldEngine(
        FieldRegistry([RingField("ring", radius=radius, ring_width=ring_width)]),
        [SizeModifier("size", "ring", FieldMapping(min_output=1.0, max_output=2.0))],
    )
    return engine.to_dict()


class SharedFieldIntegrationTests(unittest.TestCase):
    def test_document_graph_ring_is_consumed_without_a_stack(self) -> None:
        source = [CircleElement("peak", 10, 0, 4, 4), CircleElement("center", 0, 0, 4, 4)]
        document = PatternDocument(Canvas(100, 100, unit="mm", mm_per_unit=1), Reference(""), source)
        graph = ring_graph()
        document.fields, document.modifiers = graph["fields"], graph["modifiers"]
        evaluated = evaluate_pattern_document(document)
        self.assertAlmostEqual(evaluated[0].width, 8.0)
        self.assertAlmostEqual(evaluated[1].width, 4.0)
        self.assertEqual(document.elements, source, "评估不能把 Field Graph 写回源元素")

    def test_linear_graph_and_compatibility_stack_do_not_double_apply(self) -> None:
        source = [CircleElement("left", 0, 0, 4, 4), CircleElement("right", 10, 0, 4, 4)]
        document = PatternDocument(Canvas(40, 40), Reference(""), source)
        stack = SharedModifierStack(size_field=SizeFieldModifier(mode=SizeFieldMode.LINEAR_X, min_scale=1, max_scale=2))
        stack.attach(document, source_elements=source)
        evaluated = evaluate_pattern_document(document)
        self.assertEqual([item.width for item in evaluated], [4.0, 8.0])
        self.assertEqual([item.width for item in document.elements], [4, 4])

    def test_grid_source_composes_with_document_ring_graph(self) -> None:
        model = GridParametricModel(rows=1, columns=3, spacing_x=10, spacing_y=10, element_width=4)
        document = PatternDocument(
            Canvas(80, 50, unit="mm", mm_per_unit=1), Reference(""), model.generate(),
            metadata={PARAMETRIC_METADATA_KEY: {"mode": "grid", "grid": model.to_dict()}},
        )
        graph = ring_graph(radius=10, ring_width=4)
        document.fields, document.modifiers = graph["fields"], graph["modifiers"]
        evaluated = evaluate_pattern_document(document)
        widths = {round(item.x, 5): item.width for item in evaluated}
        self.assertAlmostEqual(widths[-10.0], 8.0)
        self.assertAlmostEqual(widths[0.0], 4.0)
        self.assertAlmostEqual(widths[10.0], 8.0)

    def test_ring_graph_save_load_and_svg_materialization(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = [CircleElement("peak", 10, 0, 4, 4), CircleElement("center", 0, 0, 4, 4)]
            document = PatternDocument(Canvas(100, 100, unit="mm", mm_per_unit=1), Reference(""), source)
            graph = ring_graph()
            document.fields, document.modifiers = graph["fields"], graph["modifiers"]
            session = PatternLabSession(FoundationPipeline(None, None), root, document=document)
            saved = session.save_document(root / "ring.pattern.json")
            restored = load_pattern_document(str(saved))
            self.assertEqual(restored.fields, document.fields)
            self.assertEqual(restored.modifiers, document.modifiers)
            materialize_evaluated_elements(restored)
            svg = pattern_document_to_svg(restored, str(root / "ring.svg"))
            text = svg.read_text(encoding="utf-8")
            self.assertIn('id="peak"', text)
            self.assertIn('r="4"', text)

    def test_ui_size_modifier_ring_serializes_as_ring_mode(self) -> None:
        modifier = SizeFieldModifier(mode=SizeFieldMode.RING, center_x=2, center_y=3, radius=12, ring_width=5, invert=True)
        payload = modifier.to_dict()
        restored = SizeFieldModifier.from_dict(payload)
        self.assertEqual(restored, modifier)
        self.assertEqual(restored.shared_engine().fields.to_list()[0]["type"], "ring")

    def test_tk_shared_field_panel_writes_ring_graph_and_canvas_geometry(self) -> None:
        from unittest.mock import patch
        from xiaomang_pattern_lab.ui_harness import PatternLabApp

        with TemporaryDirectory() as directory:
            app = PatternLabApp(directory)
            try:
                app.update()
                source = [CircleElement("peak", 10, 0, 4, 4), CircleElement("center", 0, 0, 4, 4)]
                app.session.document = PatternDocument(Canvas(100, 100), Reference(""), source)
                app.hide_reference.set(True)
                app.family_size_mode_var.set("ring")
                app.family_min_scale_var.set("1")
                app.family_max_scale_var.set("2")
                app.family_center_x_var.set("0")
                app.family_center_y_var.set("0")
                app.family_radius_var.set("10")
                app.family_ring_width_var.set("4")
                app.family_ring_invert_var.set(False)
                with patch("xiaomang_pattern_lab.ui_harness.messagebox.showerror",
                           side_effect=AssertionError("Ring UI apply failed")):
                    app.apply_family_fields()
                    app.update()
                self.assertEqual(app.session.document.fields[0]["type"], "ring")
                self.assertEqual([item.width for item in app.session.evaluate_elements()], [8.0, 4.0])
            finally:
                app.destroy()


if __name__ == "__main__":
    unittest.main()
