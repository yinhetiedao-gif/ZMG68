"""Gate A: RingField is additive and uses the existing scalar-field contract."""
from copy import deepcopy
import json
import unittest

from ppg.foundation import CircleElement
from xiaomang_pattern_lab.shared_fields import (
    FieldContext, FieldMapping, FieldRegistry, RingField, SharedFieldEngine, SizeModifier,
)


class RingFieldTests(unittest.TestCase):
    def setUp(self):
        self.context = FieldContext((-100.0, -100.0, 100.0, 100.0))

    def test_peak_support_and_world_coordinate_falloff(self):
        field = RingField("ring", center_x=10, center_y=-5, radius=20, ring_width=10)
        samples = {
            "center": CircleElement("center", 10, -5, 2, 2),
            "inner_edge": CircleElement("inner", 25, -5, 2, 2),
            "peak": CircleElement("peak", 30, -5, 2, 2),
            "outer_edge": CircleElement("outer", 35, -5, 2, 2),
            "off_axis_peak": CircleElement("off-axis", 10, 15, 200, 1),
        }
        self.assertEqual(field.evaluate(samples["peak"], self.context), 1.0)
        self.assertEqual(field.evaluate(samples["inner_edge"], self.context), 0.0)
        self.assertEqual(field.evaluate(samples["outer_edge"], self.context), 0.0)
        self.assertEqual(field.evaluate(samples["center"], self.context), 0.0)
        self.assertEqual(field.evaluate(samples["off_axis_peak"], self.context), 1.0)
        # Same world point, different element dimensions: dimensions do not
        # leak into the spatial field.
        self.assertEqual(field.evaluate(samples["peak"], FieldContext((0, 0, 1, 1))), 1.0)

    def test_falloff_and_invert_are_normalized(self):
        field = RingField("ring", radius=10, ring_width=20, falloff=2)
        quarter = field.evaluate(CircleElement("q", 5, 0, 1, 1), self.context)
        self.assertEqual(quarter, .25)
        inverted = RingField("inverse", radius=10, ring_width=20, invert=True)
        self.assertEqual(inverted.evaluate(CircleElement("peak", 10, 0, 1, 1), self.context), 0.0)
        self.assertEqual(inverted.evaluate(CircleElement("edge", 0, 0, 1, 1), self.context), 1.0)
        for distance in range(0, 51):
            value = field.evaluate(CircleElement("p", distance, 0, 1, 1), self.context)
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)

    def test_generic_size_modifier_consumes_ring_without_second_pipeline(self):
        source = [CircleElement("small", 0, 0, 4, 4), CircleElement("ring", 20, 0, 4, 4),
                  CircleElement("other", 40, 0, 4, 4)]
        before = deepcopy(source)
        ring = RingField("shared-ring", radius=20, ring_width=10)
        engine = SharedFieldEngine(FieldRegistry([ring]), [
            SizeModifier("size-from-ring", ring.id, FieldMapping(min_output=.5, max_output=2))])
        result = engine.apply(source)
        self.assertEqual(result[1].width, 8.0)
        self.assertEqual(result[0].width, 2.0)
        self.assertEqual(result[2].width, 2.0)
        self.assertEqual(source, before)

    def test_registry_and_engine_roundtrip_preserves_ring(self):
        ring = RingField("field-ring", center_x=3, center_y=4, radius=25,
                         ring_width=7, falloff=1.5, invert=True)
        engine = SharedFieldEngine(FieldRegistry([ring]), [
            SizeModifier("modifier-size", ring.id, FieldMapping(.2, 1.8, strength=.75))])
        payload = json.loads(json.dumps(engine.to_dict()))
        restored = SharedFieldEngine.from_dict(payload)
        self.assertEqual(restored.to_dict(), payload)
        source = [CircleElement("a", 3, 29, 4, 4), CircleElement("b", 3, 4, 4, 4)]
        self.assertEqual(restored.apply(source), engine.apply(source))

    def test_ring_rejects_invalid_parameters_and_nonfinite_coordinates(self):
        with self.assertRaises(ValueError): RingField("")
        with self.assertRaises(ValueError): RingField("bad", radius=-1)
        with self.assertRaises(ValueError): RingField("bad", ring_width=0)
        with self.assertRaises(ValueError): RingField("bad", falloff=0)
        with self.assertRaises(ValueError): RingField("bad", center_x=float("nan"))
        with self.assertRaises(ValueError): RingField("bad", invert=1)
        field = RingField("valid")
        with self.assertRaises(ValueError): field.evaluate(CircleElement("bad", float("inf"), 0, 1, 1), self.context)


if __name__ == "__main__":
    unittest.main()
