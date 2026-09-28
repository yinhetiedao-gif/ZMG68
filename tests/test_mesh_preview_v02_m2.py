"""v0.2-M2: the lightweight preview is a read-only view of Gate V output."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import math
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from time import perf_counter
import unittest

import numpy as np

from ppg.foundation import Canvas, CircleElement, FoundationPipeline, PatternDocument, Reference
from xiaomang_pattern_lab.manufacturing_backend import TrimeshBackend
from xiaomang_pattern_lab.manufacturing_geometry import Manufacturing2DGeometry, ManufacturingPolygon
from xiaomang_pattern_lab.manufacturing_ui import ManufacturingDialog, ManufacturingWorkflow
from xiaomang_pattern_lab.mesh_preview import MeshPreviewModel, MeshSoftwareRenderer, PreviewCamera
from xiaomang_pattern_lab.parametric import GridParametricModel
from xiaomang_pattern_lab.placement_assignment import ShapePrototypeRegistry
from xiaomang_pattern_lab.session import PatternLabSession
from xiaomang_pattern_lab.shared_fields import FieldMapping, FieldRegistry, SharedFieldEngine, SizeModifier, WaveField
from xiaomang_pattern_lab.stl_export import STLExporter
from xiaomang_pattern_lab.ui_harness import PatternLabApp


def polygon(identifier: str, points, holes=()):
    return ManufacturingPolygon(identifier, tuple(points), tuple(tuple(hole) for hole in holes))


def geometry(*polygons):
    all_points = [point for item in polygons for point in item.outer]
    xs, ys = zip(*all_points)
    return Manufacturing2DGeometry(tuple(polygons), "mm", (min(xs), min(ys), max(xs), max(ys)))


def document(elements):
    return PatternDocument(Canvas(160, 120, "mm", 1.0), Reference("", False), list(elements))


def rectangle_result(width=20.0, height=10.0, depth=2.0):
    return TrimeshBackend().extrude(
        geometry(polygon("rect", ((0, 0), (width, 0), (width, height), (0, height)))), depth,
    )


class MeshPreviewModelTests(unittest.TestCase):
    def test_preview_consumes_result_and_preserves_twenty_by_ten_by_two_bounds(self):
        result = rectangle_result()
        model = MeshPreviewModel.from_manufacturing_result(result)
        self.assertEqual(model.size, (20.0, 10.0, 2.0))
        self.assertEqual(model.component_count, 1)
        self.assertEqual(model.source_vertex_count, result.vertex_count)
        self.assertEqual(model.source_face_count, result.face_count)
        self.assertFalse(model.vertices.flags.writeable)
        self.assertFalse(model.faces.flags.writeable)

    def test_preview_copy_camera_and_renderer_do_not_modify_source_mesh(self):
        result = rectangle_result()
        vertices = result.mesh.vertices.copy(); faces = result.mesh.faces.copy()
        model = MeshPreviewModel.from_manufacturing_result(result)
        camera = PreviewCamera(); camera.orbit(40, -12); camera.zoom_by(1.4); camera.fit(); camera.reset()
        rendered = MeshSoftwareRenderer().render(model, camera, 480, 360)
        self.assertEqual(rendered.rendered_face_count, result.face_count)
        self.assertTrue(np.array_equal(result.mesh.vertices, vertices))
        self.assertTrue(np.array_equal(result.mesh.faces, faces))

    def test_hole_is_not_visually_capped_in_top_projection(self):
        result = TrimeshBackend().extrude(geometry(polygon(
            "plate", ((0, 0), (20, 0), (20, 20), (0, 20)),
            holes=(((6, 6), (14, 6), (14, 14), (6, 14)),),
        )), 2.0)
        model = MeshPreviewModel.from_manufacturing_result(result)
        renderer = MeshSoftwareRenderer(); camera = PreviewCamera(azimuth=0, elevation=90, zoom=1)
        image = renderer.render(model, camera, 400, 400).image
        self.assertEqual(image.getpixel((200, 200)), renderer.background)
        self.assertNotEqual(image.getpixel((200, 145)), renderer.background)

    def test_disconnected_components_keep_their_count_and_position(self):
        result = TrimeshBackend().extrude(geometry(
            polygon("left", ((0, 0), (5, 0), (5, 5), (0, 5))),
            polygon("right", ((20, 0), (25, 0), (25, 5), (20, 5))),
            polygon("top", ((10, 15), (15, 15), (15, 20), (10, 20))),
        ), 2.0)
        model = MeshPreviewModel.from_manufacturing_result(result)
        self.assertEqual(model.component_count, 3)
        self.assertEqual(model.bounds, result.bounds)
        self.assertTrue(np.array_equal(model.vertices, result.mesh.vertices))

    def test_invalid_mesh_is_rejected(self):
        result = rectangle_result()
        result.mesh.faces[0, 0] = len(result.mesh.vertices) + 1
        with self.assertRaises(ValueError):
            MeshPreviewModel.from_manufacturing_result(result)


class MeshPreviewWorkflowTests(unittest.TestCase):
    def test_camera_preview_does_not_change_document_dirty_or_undo(self):
        with TemporaryDirectory() as temporary:
            session = PatternLabSession(
                FoundationPipeline(None, None), Path(temporary),
                document=document([CircleElement("dot", 30, 30, 16, 16)]),
            )
            workflow = ManufacturingWorkflow(); result = workflow.prepare(session, 2)
            before = (deepcopy(session.document.to_dict()), session.revision,
                      session.saved_revision, session.undo_record_count, session.is_dirty)
            model = MeshPreviewModel.from_manufacturing_result(result.build.mesh_result)
            camera = PreviewCamera(); camera.orbit(120, 35); camera.zoom_by(0.8)
            MeshSoftwareRenderer().render(model, camera, 500, 420)
            after = (session.document.to_dict(), session.revision,
                     session.saved_revision, session.undo_record_count, session.is_dirty)
            self.assertEqual(before, after)

    def test_stl_bytes_are_identical_before_and_after_preview(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary); result = rectangle_result()
            before_path, after_path = root / "before.stl", root / "after.stl"
            STLExporter().export(result, before_path)
            model = MeshPreviewModel.from_manufacturing_result(result)
            MeshSoftwareRenderer().render(model, PreviewCamera(110, 24, 1.7), 500, 400)
            STLExporter().export(result, after_path)
            digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(digest(before_path), digest(after_path))

    def test_dialog_requires_mesh_and_marks_height_and_design_changes_stale(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary); app = PatternLabApp(str(root), app_data_dir=root / "appdata")
            try:
                app.withdraw(); app.session.document = document([CircleElement("dot", 30, 30, 16, 16)])
                dialog = ManufacturingDialog(app, app.session); dialog.withdraw(); dialog.update()
                self.assertEqual(str(dialog.preview_button.cget("state")), "disabled")
                dialog.open_preview(); self.assertIsNone(dialog._preview_dialog)
                result = dialog.prepare(); self.assertTrue(result.ready)
                self.assertEqual(str(dialog.preview_button.cget("state")), "normal")
                dialog.open_preview(); preview = dialog._preview_dialog
                self.assertIsNotNone(preview); preview.withdraw(); preview.update()
                original_camera = (preview.camera.azimuth, preview.camera.elevation, preview.camera.zoom)
                preview._press(SimpleNamespace(x=100, y=100))
                preview._drag(SimpleNamespace(x=140, y=115))
                preview._wheel(SimpleNamespace(delta=120))
                self.assertNotEqual(
                    (preview.camera.azimuth, preview.camera.elevation, preview.camera.zoom), original_camera,
                )
                preview.reset_view()
                self.assertEqual(
                    (preview.camera.azimuth, preview.camera.elevation, preview.camera.zoom), (45.0, 28.0, 1.0),
                )
                dialog.height_var.set("3")
                self.assertIn("厚度已变化", dialog.status_var.get())
                self.assertTrue(preview._forced_stale)
                dialog.height_var.set("2"); dialog.prepare(); dialog.open_preview()
                refreshed_preview = dialog._preview_dialog
                self.assertIsNot(refreshed_preview, preview)
                preview = refreshed_preview
                app.session.begin_transaction("edit")
                app.session.document.elements[0].x += 1
                app.session.commit_transaction()
                self.assertTrue(preview.is_stale())
                if preview._stale_after:
                    preview.after_cancel(preview._stale_after)
                    preview._stale_after = None
                preview._poll_stale()
                self.assertIn("请重新生成", preview.status_var.get())
                dialog.close()
            finally:
                app.destroy()

    def test_physical_validation_pattern_opens_as_three_component_preview(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary); app = PatternLabApp(str(root), app_data_dir=root / "appdata")
            try:
                app.withdraw()
                model = GridParametricModel(
                    rows=1, columns=3, spacing_x=21, spacing_y=21,
                    element_width=16, element_height=16, offset_x=33, offset_y=15,
                    prototype=ShapePrototypeRegistry.with_builtins().get("star"),
                )
                app.session.document = document(model.generate()); app.session.activate_grid(model)
                engine = SharedFieldEngine(
                    FieldRegistry([WaveField(
                        "print-wave", wavelength=84,
                        phase=-math.pi / 2 - 2 * math.pi * 12 / 84,
                    )]),
                    [SizeModifier(
                        "print-size", "print-wave", FieldMapping(min_output=0.625, max_output=1.375),
                    )],
                )
                graph = engine.to_dict()
                app.session.document.fields, app.session.document.modifiers = graph["fields"], graph["modifiers"]
                before = deepcopy(app.session.document.to_dict())
                state = (app.session.revision, app.session.undo_record_count, app.session.is_dirty)
                dialog = ManufacturingDialog(app, app.session); dialog.withdraw()
                result = dialog.prepare(); dialog.open_preview(); preview = dialog._preview_dialog
                self.assertTrue(result.ready); self.assertIsNotNone(preview)
                self.assertEqual(preview.model.component_count, 3)
                self.assertAlmostEqual(preview.model.size[0], 57.2169065, places=4)
                self.assertAlmostEqual(preview.model.size[1], 19.8991871, places=4)
                self.assertEqual(preview.model.size[2], 2.0)
                self.assertEqual(app.session.document.to_dict(), before)
                self.assertEqual((app.session.revision, app.session.undo_record_count, app.session.is_dirty), state)
                dialog.close()
            finally:
                app.destroy()

    def test_five_hundred_circle_preview_is_usable_and_keeps_full_mesh(self):
        circles = [
            CircleElement("dot-%d" % (row * 25 + column), 5 + column * 4, 5 + row * 4, 3, 3)
            for row in range(20) for column in range(25)
        ]
        with TemporaryDirectory() as temporary:
            session = PatternLabSession(
                FoundationPipeline(None, None), Path(temporary), document=document(circles),
            )
            result = ManufacturingWorkflow().prepare(session, 2)
            self.assertTrue(result.ready)
            model = MeshPreviewModel.from_manufacturing_result(result.build.mesh_result)
            started = perf_counter()
            rendered = MeshSoftwareRenderer().render(model, PreviewCamera(), 800, 600)
            elapsed = perf_counter() - started
            self.assertEqual(rendered.rendered_face_count, result.build.mesh_result.face_count)
            self.assertGreaterEqual(rendered.rendered_face_count, 20_000)
            self.assertLess(elapsed, 10.0)


if __name__ == "__main__":
    unittest.main()
