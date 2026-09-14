"""Gate P: grayscale Reference Image as a shared scalar field."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from ppg.foundation import Canvas, CircleElement, FoundationPipeline, PatternDocument, Reference
from xiaomang_pattern_lab.evaluation import evaluate_pattern_document, materialize_evaluated_elements
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.shared_fields import FieldMapping, ImageField, SizeModifier


class ImageFieldTests(unittest.TestCase):
    def _document(self, path: Path) -> PatternDocument:
        document = PatternDocument(
            Canvas(100, 100, unit="mm", mm_per_unit=1.0), Reference(str(path)),
            [CircleElement("black", 0.0, 0.0, 10.0, 10.0),
             CircleElement("mid", 50.0, 0.0, 10.0, 10.0),
             CircleElement("white", 100.0, 0.0, 10.0, 10.0)],
        )
        field = ImageField("reference-brightness", image_path=str(path))
        modifier = SizeModifier("image-size", field.id, FieldMapping(min_output=0.5, max_output=1.5))
        document.fields = [field.to_dict()]
        document.modifiers = [modifier.to_dict()]
        return document

    def test_bilinear_brightness_drives_size_without_revectorizing(self):
        with TemporaryDirectory() as directory:
            image_path = Path(directory) / "gradient.png"
            Image.new("L", (3, 1)).putdata([0, 128, 255])
            image = Image.new("L", (3, 1)); image.putdata([0, 128, 255]); image.save(image_path)
            document = self._document(image_path)
            before = deepcopy(document.elements)
            evaluated = evaluate_pattern_document(document)
            self.assertLess(evaluated[0].width, evaluated[1].width)
            self.assertLess(evaluated[1].width, evaluated[2].width)
            self.assertEqual(document.elements, before)

            raw = ImageField("f", image_path=str(image_path)).to_dict()
            raw["parameters"]["invert"] = True
            inverted = ImageField("f", **raw["parameters"])
            self.assertGreater(inverted.evaluate(document.elements[0], __import__("xiaomang_pattern_lab.shared_fields", fromlist=["FieldContext"]).FieldContext.from_elements(document.elements)),
                               inverted.evaluate(document.elements[2], __import__("xiaomang_pattern_lab.shared_fields", fromlist=["FieldContext"]).FieldContext.from_elements(document.elements)))

    def test_reference_path_fills_missing_image_path_and_missing_file_is_safe(self):
        with TemporaryDirectory() as directory:
            image_path = Path(directory) / "one.png"
            Image.new("L", (2, 2), 255).save(image_path)
            document = self._document(image_path)
            document.fields[0]["parameters"].pop("image_path")
            session = PatternLabSession(FoundationPipeline(None, None), Path(directory), document=document)
            materialize_evaluated_elements(session.document)
            self.assertGreater(session.document.elements[-1].width, session.document.elements[0].width - 1e-9)
            missing = ImageField("missing", image_path=str(Path(directory) / "none.png"))
            context = __import__("xiaomang_pattern_lab.shared_fields", fromlist=["FieldContext"]).FieldContext.from_elements(document.elements)
            self.assertAlmostEqual(missing.evaluate(document.elements[0], context), 0.5)

    def test_image_field_save_load_and_preset_keep_parameters_not_pixels(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            image_path = root / "gradient.png"
            image = Image.new("L", (2, 1)); image.putdata([0, 255]); image.save(image_path)
            session = PatternLabSession(FoundationPipeline(None, None), root, document=self._document(image_path))
            original = [item.width for item in session.document.elements]
            session.document.elements = evaluate_pattern_document(session.document)
            saved = session.save_document(root / "image-field.pattern.json")
            restored = PatternLabSession(FoundationPipeline(None, None), root / "reload")
            restored.load_document(str(saved))
            self.assertEqual([item.width for item in restored.document.elements], [item.width for item in session.document.elements])
            preset = restored.save_parametric_preset("图片亮度")
            payload = (root / "reload" / "presets" / (preset.preset_id + ".preset.json")).read_text(encoding="utf-8")
            self.assertNotIn("pixels", payload)
            self.assertIn("reference-brightness", payload)
            self.assertEqual(original, [10.0, 10.0, 10.0])


if __name__ == "__main__":
    unittest.main()
