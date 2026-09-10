"""Real Tk callback smoke test; not a substitute for visual acceptance."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from xiaomang_pattern_lab.ui_harness import PatternLabApp


class GateZeroTkSmokeTests(unittest.TestCase):
    def test_import_select_inspector_grid_save_and_reload(self):
        with TemporaryDirectory() as directory:
            app = PatternLabApp(directory)
            try:
                app.update()
                self.assertIn('Xiaomang Pattern Lab', app.title())
                def fail_dialog(*args, **kwargs):
                    raise AssertionError(f'Unexpected UI error: {args}')
                with patch('xiaomang_pattern_lab.ui_harness.messagebox.showerror', side_effect=fail_dialog):
                    for suffix in ('.png', '.jpg'):
                        source = app._fixtures['regular_dot_matrix'].with_suffix(suffix)
                        app._import(str(source))
                        app.update()
                        self.assertEqual(len(app.session.document.elements), 144)
                    app.hide_reference.set(True)
                    app.refresh_canvas()
                    app.update()
                    self.assertEqual(len(app._static_element_items), 144)
                    element = app.session.document.elements[0]
                    app.session.select(element.id)
                    app.refresh_fields(force=True)
                    x = element.x
                    app.x_var.set(str(x + 5))
                    app.apply_position()
                    self.assertAlmostEqual(app.session.document.element(element.id).x, x + 5)
                    app.undo()
                    self.assertAlmostEqual(app.session.document.element(element.id).x, x)
                    app.redo()
                    self.assertAlmostEqual(app.session.document.element(element.id).x, x + 5)
                    app.undo()
                    app.try_parametric()
                    app.convert_pending_grid()
                    self.assertEqual(app.session.pattern_mode.value, 'grid')
                    app.grid_vars['rows'].set('10')
                    app._commit_grid_from_controls()
                    self.assertEqual(len(app.session.document.elements), 120)
                    path = str(Path(directory) / 'gate0.pattern.json')
                    app.session.save_document(path)
                    before = app.session.document.to_dict()
                    app.session.load_document(path)
                    self.assertEqual(app.session.document.to_dict(), before)
                    svg = Path(directory) / 'gate0.svg'
                    app.session.export_svg(str(svg))
                    self.assertTrue(svg.is_file())
            finally:
                app.destroy()

    def test_matrix_parameter_panel_scrolls_as_one_page(self):
        """All matrix controls remain reachable when the window is shorter than the form."""
        with TemporaryDirectory() as directory:
            app = PatternLabApp(directory)
            try:
                app.update()
                notebooks = []
                stack = list(app.winfo_children())
                while stack:
                    widget = stack.pop()
                    stack.extend(widget.winfo_children())
                    if widget.winfo_class() == "TNotebook":
                        notebooks.append(widget)
                self.assertTrue(notebooks)
                notebook = notebooks[0]
                notebook.select(1)
                app.update()
                scroll_canvas = app._matrix_scroll_canvas
                self.assertIsNotNone(scroll_canvas)
                self.assertGreater(scroll_canvas.winfo_height(), 100)
                _x0, y0, _x1, y1 = map(float, scroll_canvas.cget("scrollregion").split())
                self.assertGreater(y1, scroll_canvas.winfo_height())
                scroll_canvas.yview_moveto(1.0)
                app.update()
                first, last = scroll_canvas.yview()
                self.assertGreater(first, 0.5)
                self.assertAlmostEqual(last, 1.0, delta=0.02)
            finally:
                app.destroy()
