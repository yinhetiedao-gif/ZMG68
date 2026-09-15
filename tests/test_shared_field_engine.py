"""Gate 1: independent legacy oracle, real evaluation, persistence and Tk parity."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ppg.foundation import Canvas, CircleElement, EllipseElement, RectElement, Reference, PatternDocument, FoundationPipeline
from ppg.foundation.svg_exporter import pattern_document_to_svg
from xiaomang_pattern_lab.parametric import LocalOverride
from xiaomang_pattern_lab.parametric_families import SizeFieldMode, SizeFieldModifier
from xiaomang_pattern_lab.shared_fields import (
    ConstantField, LinearField, FieldContext, FieldRegistry, FieldMapping, SizeModifier, SharedFieldEngine,
)
from xiaomang_pattern_lab.shared_modifiers import SharedModifierStack
from xiaomang_pattern_lab.session import PatternLabSession


def elements():
    return [CircleElement("a", -12, 8, 4, 4), EllipseElement("b", 5, 20, 8, 3),
            RectElement("c", 35, 57, 12, 7, rotation=25),
            CircleElement("invisible", 60, 80, 2, 2, visible=False)]


def legacy_linear(source, settings):
    """Frozen pre-Gate-1 formula, deliberately independent of new engine."""
    result = deepcopy(source)
    if not result: return result
    attr = "x" if settings.mode is SizeFieldMode.LINEAR_X else "y"
    low, high = min(getattr(e, attr) for e in result), max(getattr(e, attr) for e in result)
    for e in result:
        value = (getattr(e, attr) - low) / max(high - low, 0.01)
        scale = settings.min_scale + (settings.max_scale - settings.min_scale) * value
        scale = 1.0 + (scale - 1.0) * settings.strength
        e.width = max(0.01, e.width * scale)
        e.height = max(0.01, e.height * scale)
    return result


class SharedFieldEngineTests(unittest.TestCase):
    def test_normalized_fields_do_not_mutate_source(self):
        source = elements(); before = deepcopy(source); context = FieldContext.from_elements(source)
        for scalar in (ConstantField("constant", .73), LinearField("x"), LinearField("y", 90),
                       LinearField("diagonal", 37), LinearField("explicit", 0, 0, 20)):
            for e in source:
                self.assertTrue(0 <= scalar.evaluate(e, context) <= 1)
        self.assertEqual(source, before)

    def test_world_coordinates_not_canvas_margin_or_element_size(self):
        source = elements(); field = LinearField("x")
        values = [field.evaluate(e, FieldContext.from_elements(source)) for e in source]
        for e in source:
            e.width *= 100; e.height *= .03
        self.assertEqual(values, [field.evaluate(e, FieldContext.from_elements(source)) for e in source])
        self.assertEqual((values[0], values[-1]), (0.0, 1.0))

    def test_explicit_linear_domain_and_diagonal(self):
        f = LinearField("explicit", 0, 10, 30)
        context = FieldContext((0, 0, 100, 100))
        for x, expected in ((-10, 0), (10, 0), (20, .5), (30, 1), (100, 1)):
            self.assertEqual(f.evaluate(CircleElement("p", x, 0, 1, 1), context), expected)
        self.assertAlmostEqual(LinearField("diagonal", 45).evaluate(CircleElement("p", 50, 50, 1, 1), context), .5)

    def test_degenerate_and_sub_resolution_spans_keep_legacy_output(self):
        for source in ([], [CircleElement("one", 7, 9, 4, 4)],
                       [CircleElement("a", 0, 0, 4, 4), CircleElement("b", .002, .004, 4, 4)]):
            for mode in (SizeFieldMode.LINEAR_X, SizeFieldMode.LINEAR_Y):
                settings = SizeFieldModifier(mode=mode, min_scale=.1, max_scale=3)
                self.assertEqual(settings.shared_engine().apply(source), legacy_linear(source, settings))

    def test_linear_migration_matches_legacy_exactly_across_types(self):
        source = elements()
        for mode in (SizeFieldMode.LINEAR_X, SizeFieldMode.LINEAR_Y):
            for low, high in ((.25, 3), (3, .25), (1, 1), (.01, 8)):
                for strength in (0, .3, 1):
                    with self.subTest(mode=mode, low=low, high=high, strength=strength):
                        settings = SizeFieldModifier(mode=mode, min_scale=low, max_scale=high, strength=strength)
                        actual = SharedModifierStack(size_field=settings).apply(source)
                        self.assertEqual(actual, legacy_linear(source, settings))
        self.assertEqual(source, elements())

    def test_registry_identity_and_one_evaluation_per_shared_field(self):
        class CountingField:
            id = "shared"
            calls = 0
            def evaluate(self, element, context):
                self.calls += 1
                return .5
        scalar = CountingField()
        registry = FieldRegistry([scalar])
        engine = SharedFieldEngine(registry, [SizeModifier("first", scalar.id, FieldMapping(1, 2)),
                                             SizeModifier("second", scalar.id, FieldMapping(2, 4))])
        source = elements(); result = engine.apply(source)
        self.assertIs(registry.get("shared"), scalar)
        self.assertEqual(scalar.calls, len(source))
        self.assertEqual(result[0].width, source[0].width * 1.5 * 3)
        self.assertEqual(source, elements())

    def test_missing_duplicate_and_unknown_references_fail_explicitly(self):
        with self.assertRaises(ValueError): FieldRegistry([LinearField("same"), ConstantField("same")])
        with self.assertRaises(ValueError): SharedFieldEngine(FieldRegistry(), [SizeModifier("s", "missing", FieldMapping())])
        with self.assertRaises(ValueError): FieldRegistry.from_list([{"id": "bad", "type": "unsupported"}])
        with self.assertRaises(ValueError): SharedFieldEngine.from_dict({"version": 99})
        with self.assertRaises(ValueError): SharedFieldEngine.from_dict({"modifiers": [{"type": "rotation"}]})

    def test_non_finite_and_invalid_input_are_rejected(self):
        for bad in (float("nan"), float("inf"), -float("inf")):
            with self.assertRaises(ValueError): LinearField("bad", angle=bad)
            with self.assertRaises(ValueError): ConstantField("bad", bad)
            with self.assertRaises(ValueError): FieldMapping(min_output=bad)
            with self.assertRaises(ValueError): FieldMapping().evaluate(bad, neutral=1)
        with self.assertRaises(ValueError): LinearField("bad", start=0)
        with self.assertRaises(ValueError): LinearField("bad", start=10, end=0)
        with self.assertRaises(ValueError): FieldMapping(strength=2)
        with self.assertRaises(ValueError): FieldMapping(falloff=0)
        with self.assertRaises(ValueError): FieldMapping(remap_curve="unknown")
        with self.assertRaises(ValueError): FieldMapping(clamp=False).evaluate(2, neutral=1)
        with self.assertRaises(ValueError): FieldMapping(invert="false")
        with self.assertRaises(ValueError): SizeModifier("s", "f", FieldMapping(), enabled="false")

    def test_serialized_numeric_strings_are_normalized(self):
        field = LinearField("f", angle="90", start="10", end="30")
        mapping = FieldMapping(min_output="1", max_output="3", strength="0.5")
        e = CircleElement("p", 0, 20, 1, 1)
        self.assertEqual(field.evaluate(e, FieldContext((0, 0, 30, 30))), .5)
        self.assertEqual(mapping.evaluate(.5, neutral=1), 1.5)

    def test_mapping_order_strength_invert_remap_and_output_units(self):
        self.assertAlmostEqual(FieldMapping(2, 10).evaluate(.73, neutral=1), 7.84)
        self.assertEqual(FieldMapping(2, 10, strength=0).evaluate(.73, neutral=1), 1)
        self.assertEqual(FieldMapping(2, 10, invert=True).evaluate(.25, neutral=1), 8)
        self.assertEqual(FieldMapping(2, 10, falloff=2).evaluate(.5, neutral=1), 4)
        for curve, expected in (("linear", .25), ("ease_in", .0625), ("ease_out", .4375),
                                ("bell", .75), ("inverse_bell", .25), ("step", 0)):
            self.assertEqual(FieldMapping(remap_curve=curve).evaluate(.25, neutral=0), expected)
        self.assertEqual(FieldMapping().evaluate(2, neutral=0), 1)

    def test_disabled_size_and_empty_input(self):
        engine = SharedFieldEngine(FieldRegistry([LinearField("f")]),
                                   [SizeModifier("s", "f", FieldMapping(4, 10), enabled=False)])
        self.assertEqual(engine.apply(elements()), elements())
        self.assertEqual(engine.apply([]), [])

    def test_registry_graph_roundtrip_preserves_ids_mapping_and_results(self):
        engine = SharedFieldEngine(FieldRegistry([LinearField("shared", 37)]), [
            SizeModifier("s1", "shared", FieldMapping(.5, 2)),
            SizeModifier("s2", "shared", FieldMapping(1, 1.2, invert=True, strength=.4))])
        payload = json.loads(json.dumps(engine.to_dict()))
        restored = SharedFieldEngine.from_dict(payload)
        self.assertEqual(restored.to_dict(), payload)
        self.assertEqual(restored.apply(elements()), engine.apply(elements()))
        self.assertEqual(len(payload["fields"]), 1)

    def test_existing_project_payload_needs_no_schema_migration(self):
        raw = {"mode": "linear_y", "min_scale": .5, "max_scale": 2,
               "center_x": 10.0, "center_y": 20.0, "radius": 30.0, "strength": .3}
        restored = SizeFieldModifier.from_dict(raw)
        self.assertEqual(restored.to_dict(), raw)
        self.assertEqual(restored.shared_engine().apply(elements()), legacy_linear(elements(), restored))
        for mode in (SizeFieldMode.CONSTANT, SizeFieldMode.RADIAL, SizeFieldMode.ATTRACTOR):
            self.assertIsNone(SizeFieldModifier(mode=mode).shared_engine())

    def test_local_override_is_after_linear_size_and_source_is_untouched(self):
        source = elements()
        settings = SizeFieldModifier(mode=SizeFieldMode.LINEAR_X, min_scale=.5, max_scale=2)
        stack = SharedModifierStack(size_field=settings, local_overrides={
            "a": LocalOverride(offset_x=500, scale_x=1.5, scale_y=1.5)})
        result = stack.apply(source)
        expected = legacy_linear(source, settings)
        self.assertEqual(result[0].width, expected[0].width * 1.5)
        self.assertEqual(result[0].x, source[0].x + 500)
        self.assertEqual(result[1:], expected[1:])
        self.assertEqual(source, elements())

    def test_session_undo_redo_save_reload_and_disable_restore_source(self):
        with TemporaryDirectory() as directory:
            doc = PatternDocument(Canvas(200, 160), Reference(""), elements())
            session = PatternLabSession(FoundationPipeline(None, None), Path(directory), document=doc)
            stack = SharedModifierStack(size_field=SizeFieldModifier(mode=SizeFieldMode.LINEAR_Y, max_scale=3))
            session.activate_shared_modifiers(stack)
            expected = deepcopy(doc.elements)
            self.assertEqual(len(doc.fields), 1)
            self.assertEqual(doc.modifiers[0]["field_id"], doc.fields[0]["id"])
            session.undo(); self.assertEqual(session.document.elements, elements())
            session.redo(); self.assertEqual(session.document.elements, expected)
            saved = session.save_document(str(Path(directory) / "field.pattern.json"))
            before = session.document.to_dict()
            session.load_document(str(saved))
            self.assertEqual(session.document.to_dict(), before)
            self.assertEqual(session.document.modifiers[0]["field_id"], session.document.fields[0]["id"])
            self.assertEqual(session.evaluate_elements(), expected)
            session.deactivate_shared_modifiers()
            self.assertEqual(session.document.elements, elements())

    def test_exported_svg_is_byte_identical_to_old_formula(self):
        with TemporaryDirectory() as directory:
            for mode in (SizeFieldMode.LINEAR_X, SizeFieldMode.LINEAR_Y):
                settings = SizeFieldModifier(mode=mode, min_scale=.5, max_scale=3, strength=.7)
                old = PatternDocument(Canvas(150, 150), Reference(""), legacy_linear(elements(), settings))
                new = PatternDocument(Canvas(150, 150), Reference(""), SharedModifierStack(size_field=settings).apply(elements()))
                p1 = pattern_document_to_svg(old, str(Path(directory) / "old.svg"))
                p2 = pattern_document_to_svg(new, str(Path(directory) / "new.svg"))
                self.assertEqual(p1.read_bytes(), p2.read_bytes())

    def test_real_tk_canvas_matches_legacy_after_session_apply(self):
        from xiaomang_pattern_lab.ui_harness import PatternLabApp
        with TemporaryDirectory() as directory:
            app = PatternLabApp(directory)
            try:
                app.update()
                app.session.document = PatternDocument(Canvas(150, 150), Reference(""), elements())
                app.hide_reference.set(True)
                settings = SizeFieldModifier(mode=SizeFieldMode.LINEAR_Y, min_scale=.5, max_scale=3)
                app.session.activate_shared_modifiers(SharedModifierStack(size_field=settings))
                app.refresh_canvas(); app.update()
                def primitives():
                    return [(app.canvas.type(i), app.canvas.coords(i), app.canvas.itemcget(i, "fill"))
                            for i in app.canvas.find_withtag("geometry")]
                actual = primitives()
                app.session.document.elements = legacy_linear(elements(), settings)
                app.refresh_canvas(); app.update()
                self.assertTrue(actual)
                self.assertEqual(actual, primitives())
            finally:
                app.destroy()

    def test_existing_ui_apply_repeatedly_never_compounds_source(self):
        from xiaomang_pattern_lab.ui_harness import PatternLabApp
        with TemporaryDirectory() as directory:
            app = PatternLabApp(directory)
            try:
                app.update()
                app.session.document = PatternDocument(Canvas(150, 150), Reference(""), elements())
                app.hide_reference.set(True)
                app.family_size_mode_var.set("linear_x")
                app.family_min_scale_var.set("0.5")
                for maximum in (2, 3, 2):
                    app.family_max_scale_var.set(str(maximum))
                    with patch("xiaomang_pattern_lab.ui_harness.messagebox.showerror",
                               side_effect=AssertionError("Unexpected field UI error")):
                        app.apply_family_fields(); app.update()
                    stack = SharedModifierStack.from_document(app.session.document)
                    self.assertEqual(stack.source_snapshot(), elements())
                    expected = legacy_linear(elements(), SizeFieldModifier(
                        mode=SizeFieldMode.LINEAR_X, min_scale=.5, max_scale=maximum))
                    self.assertEqual(app.session.evaluate_elements(), expected)
                app.session.deactivate_shared_modifiers()
                self.assertEqual(app.session.document.elements, elements())
            finally:
                app.destroy()

    def test_harness_destroy_cancels_refresh_timer(self):
        from xiaomang_pattern_lab.ui_harness import PatternLabApp
        with TemporaryDirectory() as directory:
            app = PatternLabApp(directory)
            app.update()
            callback_id = app._performance_after
            self.assertIsNotNone(callback_id)
            app.destroy()
            self.assertTrue(app._closing)


if __name__ == "__main__":
    unittest.main()
