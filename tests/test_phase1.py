import tempfile
import time
import struct
import json
import os
import unittest
import tkinter as tk
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageDraw, ImageTk

from ppg.exporters import write_dxf, write_png, write_svg, write_field_dxf, write_field_png, write_field_svg
from ppg.geometry import builtin_contour, element_polygon, generate_items, has_self_intersection, smooth_noise
from ppg.model import PatternSettings, Project
from ppg.project_io import load_project, save_project
from ppg.raster_print import convert_image
from ppg.image_analysis import analyze_reference
from ppg.field_generators import generate_field
from ppg.blender_worker import find_blender, run_blender_job
from ppg.raster_print import audit_stl
from ppg.final_geometry import apply_height_field, primitives_bounds
from ppg.preview_provider import NullPreviewProvider
from ppg.app import PatternApp
from ppg.reference2d import EditableElement, EditablePatternDocument, PreprocessConfig, analyze_reference2d
from ppg.reference2d.importer import decode_reference
from ppg.reference2d.manufacturing import document_to_primitives


def _tk_gui_available() -> bool:
    """构建 Python 有时被沙箱禁止读取 Tcl；这不是产品 Canvas 的失败。"""
    try:
        root = tk.Tk()
        root.withdraw(); root.update_idletasks(); root.destroy()
        return True
    except tk.TclError:
        return False


TK_GUI_AVAILABLE = _tk_gui_available()


class PhaseOneTests(unittest.TestCase):
    def test_builtin_contours_are_valid(self):
        for shape in ("圆形", "椭圆", "圆角矩形", "星形", "多边形", "心形", "有机形", "波浪形"):
            with self.subTest(shape=shape):
                contour = builtin_contour(shape, 42)
                self.assertGreaterEqual(len(contour), 3)
                self.assertFalse(has_self_intersection(contour))

    def test_seed_is_deterministic_and_smooth_noise_is_continuous(self):
        settings = PatternSettings(seed=42, count=300, noise_strength=30, noise_scale=28)
        contour = builtin_contour("有机形", 42)
        self.assertEqual(generate_items(contour, settings), generate_items(contour, settings))
        values = smooth_noise(300, .3, 28, __import__("random").Random(42))
        self.assertLess(max(abs(values[i] - values[i-1]) for i in range(1, len(values))), .1)

    def test_export_and_project_roundtrip(self):
        settings = PatternSettings(seed=42, count=100)
        contour = builtin_contour("圆形", 42)
        items = generate_items(contour, settings)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_svg(str(root / "a.svg"), contour, items, settings)
            write_png(str(root / "a.png"), contour, items, settings)
            write_dxf(str(root / "a.dxf"), contour, items, settings)
            project = Project(settings=settings, contour=contour, contour_source="builtin", height_controls=[{"x": 10, "y": 20, "delta": 1.5, "radius": 8, "falloff": 55}], view_2d={"zoom": 1.4, "pan_x": 13, "pan_y": -4})
            save_project(str(root / "a.ppg"), project)
            loaded = load_project(str(root / "a.ppg"))
            self.assertEqual(loaded.settings.seed, 42)
            self.assertEqual(len(loaded.contour), len(contour))
            self.assertEqual(loaded.height_controls[0]["delta"], 1.5)
            self.assertEqual(loaded.view_2d["zoom"], 1.4)
            self.assertNotIn("view_3d", loaded.to_dict())
            for name in ("a.svg", "a.png", "a.dxf", "a.ppg"):
                self.assertGreater((root / name).stat().st_size, 100)

    def test_generation_scales_to_1000_elements(self):
        contour = builtin_contour("有机形", 1)
        started = time.perf_counter()
        for count in (100, 300, 500, 1000):
            self.assertEqual(len(generate_items(contour, PatternSettings(count=count, seed=1))), count)
        self.assertLess(time.perf_counter() - started, 3.0)

    def test_element_and_distribution_api(self):
        contour = builtin_contour("圆形", 6)
        for distribution in ("均匀", "随机", "渐变", "曲率"):
            settings = PatternSettings(count=80, seed=6, distribution=distribution)
            self.assertEqual(generate_items(contour, settings), generate_items(contour, settings))
        item = generate_items(contour, PatternSettings(count=10))[0]
        for kind in ("三角形", "矩形", "叶片", "水滴"):
            self.assertGreaterEqual(len(element_polygon(item, kind)), 3)
        custom = [(-1, -1), (1, -1), (0, 1)]
        self.assertEqual(len(element_polygon(item, "自定义 SVG", custom)), 3)

    def test_non_line_elements_export(self):
        contour = builtin_contour("椭圆", 9)
        with tempfile.TemporaryDirectory() as temp:
            for element in ("三角形", "矩形", "叶片", "水滴", "珠子", "自定义 SVG"):
                settings = PatternSettings(count=30, element_type=element, seed=9)
                target = Path(temp) / (element + ".svg")
                write_svg(str(target), contour, generate_items(contour, settings), settings, [(-1,-1),(1,-1),(0,1)])
                self.assertGreater(target.stat().st_size, 500)

    def test_black_white_image_to_svg_and_stl(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.png"
            image = Image.new("L", (80, 80), "white")
            draw = ImageDraw.Draw(image)
            draw.ellipse((8, 8, 72, 72), fill="black")
            draw.line((40, 0, 40, 79), fill="black", width=8)
            image.save(source)
            result = convert_image(str(source), str(Path(temp) / "result"), width_mm=100, thickness_mm=.8)
            self.assertTrue(result.connected)
            self.assertIsNotNone(result.triangles)
            self.assertGreater(result.triangles, 0)
            self.assertTrue(result.mesh_valid)
            stl = Path(result.output_dir) / "图案.stl"
            with stl.open("rb") as handle:
                handle.seek(80); count = struct.unpack("<I", handle.read(4))[0]
            self.assertEqual(count, result.triangles)
            self.assertEqual(stl.stat().st_size, 84 + count * 50)
            for name in ("图案.svg", "图案.stl", "黑白预览.png", "连通性检测.json", "参数公式说明.md"):
                self.assertTrue((Path(result.output_dir) / name).exists())

    def test_reference_analysis_is_honest_about_low_contrast(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "low.png"
            Image.new("L", (80, 80), 130).save(source)
            result = analyze_reference(str(source))
            self.assertTrue(result.needs_new_generator)
            self.assertIsNone(result.generator_key)

    def test_dot_matrix_analysis_generates_editable_field_and_exports(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "dots.png"
            image = Image.new("L", (180, 180), "white"); draw = ImageDraw.Draw(image)
            for y in range(12, 172, 20):
                for x in range(12, 172, 20):
                    radius = max(2, int(8 - abs(x-90)/28))
                    draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill="black")
            image.save(source)
            result = analyze_reference(str(source))
            self.assertFalse(result.needs_new_generator)
            self.assertIn(result.generator_key, {"dot_matrix", "halftone", "gradient_dots", "point_line_plane"})
            settings = PatternSettings(**result.suggestions)
            first = generate_field(settings); second = generate_field(settings)
            self.assertEqual(first, second)
            self.assertGreater(len(first), 10)
            root = Path(temp)
            write_field_svg(str(root / "field.svg"), first, settings)
            write_field_png(str(root / "field.png"), first)
            write_field_dxf(str(root / "field.dxf"), first)
            for name in ("field.svg", "field.png", "field.dxf"):
                self.assertGreater((root / name).stat().st_size, 100)

    def test_extended_field_parameters_are_reproducible_and_effective(self):
        settings = PatternSettings(
            active_generator="field", field_generator="wave_field", field_element="面", field_shape="六边形",
            grid_columns=16, grid_rows=12, min_size=.4, max_size=3.8, field_density=82,
            gradient_mode="中心 → 边缘", gradient_center_x=44, gradient_center_y=55,
            random_size=16, random_rotation=35, random_position=12, random_density=10,
            field_noise=25, noise_frequency=1.8, noise_offset=4, noise_octaves=3,
            distortion_wave=28, distortion_twist=18, distortion_flow=12, seed=71,
        )
        first, second = generate_field(settings), generate_field(settings)
        self.assertEqual(first, second)
        self.assertGreater(len(first), 20)
        self.assertTrue(any(item.kind == "hexagon" for item in first))
        changed = generate_field(PatternSettings(**{**settings.to_dict(), "noise_offset": 44}))
        self.assertNotEqual(first, changed)

    @unittest.skipUnless(TK_GUI_AVAILABLE, "当前测试运行时无法初始化 Tcl/Tk；需在带完整 Tk 的桌面/打包 EXE 环境运行 Canvas 回归。")
    def test_reference_image_side_by_side_uses_two_complete_canvas_panes(self):
        """GUI 回归：左右对比不能再把位于中心的原图或生成图从中间裁断。"""
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "reference.png"
            image = Image.new("RGB", (240, 180), "white")
            draw = ImageDraw.Draw(image)
            draw.ellipse((65, 35, 175, 145), fill="black")
            image.save(source)
            app = PatternApp()
            try:
                app.update_idletasks(); app.update()
                app.vars["reference_image"].set(str(source))
                app.vars["reference_compare_mode"].set("左右对比")
                app.reference_visible.set(True)
                app.update_preview(); app.update_idletasks(); app.update()
                preview = ImageTk.getimage(app._preview_photo).convert("RGB")
                split = preview.width // 2
                self.assertGreater(preview.width, 300)
                self.assertGreater(preview.height, 250)
                self.assertEqual(len(app.canvas.find_all()), 1)

                def dark_pixels(region):
                    return sum(1 for pixel in region.getdata() if max(pixel) < 180)

                # 原图与参数化结果必须分别完整存在于两侧；不依赖固定像素位置，
                # 因此窗口尺寸、系统 DPI 或画布缩放变化不会制造脆弱的假失败。
                self.assertGreater(dark_pixels(preview.crop((0, 0, split, preview.height))), 800)
                self.assertGreater(dark_pixels(preview.crop((split, 0, preview.width, preview.height))), 400)

                # 其余两个带参考图模式也必须继续由同一个真实 Canvas 位图提交。
                # 这防止修复左右栏后，让“原图”或“叠加对比”重新变成空白层。
                for mode in ("原图", "叠加对比"):
                    app.vars["reference_compare_mode"].set(mode)
                    app.update_preview(); app.update_idletasks(); app.update()
                    mode_preview = ImageTk.getimage(app._preview_photo).convert("RGB")
                    self.assertEqual(mode_preview.size, preview.size)
                    self.assertEqual(len(app.canvas.find_all()), 1)
                    self.assertGreater(dark_pixels(mode_preview), 800, msg=mode)
            finally:
                app.on_close()

    @unittest.skipUnless(TK_GUI_AVAILABLE, "当前测试运行时无法初始化 Tcl/Tk；需在带完整 Tk 的桌面/打包 EXE 环境运行 Canvas 回归。")
    def test_reference_analysis_apply_updates_field_canvas_after_editable_elements(self):
        """GUI 回归：分析并应用参考图后，带 reference_elements 的缓存 key 仍可哈希。"""
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "reference.png"
            image = Image.new("L", (320, 240), "white")
            draw = ImageDraw.Draw(image)
            draw.ellipse((20, 20, 150, 150), fill="black")
            draw.line((160, 20, 300, 220), fill="black", width=18)
            image.save(source)
            app = PatternApp()
            try:
                app.update_idletasks(); app.update()
                with patch("ppg.app.filedialog.askopenfilename", return_value=str(source)), \
                     patch("ppg.app.messagebox.askyesno", return_value=True), \
                     patch("ppg.app.messagebox.showinfo", return_value=None), \
                     patch("ppg.app.messagebox.showerror", return_value=None):
                    app.analyze_reference_image()
                app.update_idletasks(); app.update()
                self.assertEqual(app.vars["active_generator"].get(), "field")
                self.assertEqual(app.vars["reference_compare_mode"].get(), "左右对比")
                # Detection now persists EditablePatternDocument, not the old
                # generator's reference_elements list. Check the real objects
                # and their persisted payload, then explicitly retain the old
                # non-hashable settings/cache regression below.
                self.assertIsNotNone(app._editable_pattern_document)
                self.assertGreater(len(app._editable_pattern_document.elements), 0)
                self.assertEqual(app.project.editable_pattern_document,
                                 app._editable_pattern_document.to_dict())
                app.project.settings.reference_elements = [{"type": "circle", "x": 25, "y": 25, "radius": 4}]
                app.update_preview(); app.update_idletasks(); app.update()
                preview = ImageTk.getimage(app._preview_photo).convert("RGB")
                split = preview.width // 2
                self.assertGreater(preview.width, 300)
                self.assertEqual(len(app.canvas.find_all()), 1)
                self.assertGreater(sum(1 for px in preview.crop((0, 0, split, preview.height)).getdata() if max(px) < 180), 500)
                self.assertGreater(sum(1 for px in preview.crop((split, 0, preview.width, preview.height)).getdata() if max(px) < 180), 100)
                self.assertNotIn("unhashable", app.status.get())
            finally:
                app.on_close()

    @unittest.skipUnless(TK_GUI_AVAILABLE, "当前测试运行时无法初始化 Tcl/Tk；需在带完整 Tk 的桌面/打包 EXE 环境运行 Canvas 回归。")
    def test_reference2d_poc_is_connected_to_canvas_and_project(self):
        """正式 Canvas 回归：POC DOT 可见、可选、改半径、拖动、删除并保存。"""
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "editable-dots.png"
            image = Image.new("L", (160, 120), "white"); draw = ImageDraw.Draw(image)
            for x, y, radius in ((24, 22, 5), (56, 22, 7), (92, 22, 9), (132, 22, 5), (24, 56, 8), (56, 56, 6), (92, 56, 4), (132, 56, 7), (24, 92, 5), (56, 92, 8), (92, 92, 6), (132, 92, 4)):
                draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill="black")
            image.save(source)
            app = PatternApp()
            try:
                app.update_idletasks(); app.update()
                with patch("ppg.app.filedialog.askopenfilename", return_value=str(source)), \
                     patch("ppg.app.messagebox.askyesno", return_value=False), \
                     patch("ppg.app.messagebox.showinfo", return_value=None), \
                     patch("ppg.app.messagebox.showerror", return_value=None):
                    app.analyze_reference_image()
                app.vars["reference_compare_mode"].set("重建结果"); app.reference_visible.set(False); app.update_preview(); app.update_idletasks(); app.update()
                self.assertIsNotNone(app._reference2d_document)
                self.assertEqual(len(app._reference2d_document.geometry_layer.dots), 12)
                preview = ImageTk.getimage(app._preview_photo).convert("RGB")
                self.assertGreater(sum(1 for pixel in preview.getdata() if max(pixel) < 80), 300)
                dot = app._reference2d_document.geometry_layer.dots[0]
                world_x, world_y = dot.x / app._reference2d_document.reference_layer.width * 100, dot.y / app._reference2d_document.reference_layer.height * 100
                scale, ox, oy = app._last_transform
                event = tk.Event(); event.x, event.y = round(world_x * scale + ox), round(world_y * scale + oy)
                app.draw_start(event)
                self.assertEqual(app._reference2d_document.selected_object_id, dot.id)
                old_radius = dot.radius_x; app.vars["reference2d_radius"].set(str(old_radius * 1.4)); app.apply_reference2d_radius()
                self.assertGreater(dot.radius_x, old_radius)
                moved = tk.Event(); moved.x, moved.y = event.x + 12, event.y + 8; app.draw_move(moved); app.draw_end(moved)
                self.assertNotEqual((dot.x, dot.y), (24.5, 22.5))
                app.delete_reference2d_selected(); self.assertEqual(len(app._reference2d_document.geometry_layer.dots), 11)
                project_path = Path(temp) / "canvas-reference2d.ppg"; app.project_path = str(project_path); app.save_current()
                loaded = load_project(str(project_path)); self.assertEqual(len(loaded.reference2d_document["geometry_layer"]["objects"]), 11)
            finally:
                app.on_close()

    def test_reference2d_p0_pipeline_emits_editable_scene_and_spatial_fields(self):
        """P0：点阵参考图必须输出真实点对象、尺寸/密度场和可解释匹配结果。"""
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "dot_gradient.webp"
            image = Image.new("L", (220, 220), "white")
            draw = ImageDraw.Draw(image)
            for row in range(10):
                for column in range(10):
                    x, y = 20 + column * 20, 20 + row * 20
                    radius = 3 + int((column + row) / 18 * 5)
                    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="black")
            image.save(source, format="WEBP", quality=95)
            decoded = decode_reference(str(source), target_width_mm=100.0)
            self.assertEqual((decoded.width_px, decoded.height_px), (220, 220))
            # Pillow 将 WEBP 灰度编码规范化为 RGB；两者都属于有效源色彩空间。
            self.assertIn(decoded.color_space, {"L", "RGB"})
            self.assertEqual(decoded.physical_width_mm, 100.0)
            result = analyze_reference2d(str(source), target_width_mm=100.0, config=PreprocessConfig(min_area=4))
            self.assertEqual(result.classification.primary_type, "DOT")
            self.assertGreaterEqual(len(result.features), 80)
            self.assertGreaterEqual(len(result.geometry.dots), 80)
            self.assertEqual(len(result.geometry.lines), 0)
            self.assertIn(result.generator["base_generator"], {"dot_matrix", "halftone"})
            self.assertEqual(len(result.fields.density_field), 16)
            self.assertGreater(result.fields.nearest_neighbor_mean, 1.0)
            self.assertGreater(result.similarity["mask_dice"], 0.45)
            self.assertIn("分类主类型", result.details)
            # 结构化结果可直接保存为 JSON，不包含 Image/ndarray 等不可序列化对象。
            json.dumps(result.to_dict(), ensure_ascii=False)

    def test_reference_reconstruction_has_editable_void_corner_and_vortex_rules(self):
        """回归：中心旋转留白、角点大点与轻微涡旋必须转成规则，不复制像素。"""
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "reference_compound.png"
            image = Image.new("L", (240, 240), "white"); draw = ImageDraw.Draw(image)
            for y in range(14, 230, 18):
                for x in range(14, 230, 18):
                    corner = abs(x-120)/120 * abs(y-120)/120
                    radius = int(2 + 6*corner)
                    draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill="black")
            # 中心旋转方形留白，模拟用户的点阵结构而非原图复制。
            draw.polygon([(120,75),(165,120),(120,165),(75,120)],fill="white")
            image.save(source)
            result = analyze_reference(str(source))
            self.assertFalse(result.needs_new_generator)
            self.assertTrue(result.suggestions["reference_rebuild_enabled"])
            settings = PatternSettings(**result.suggestions)
            settings.grid_columns=settings.grid_rows=25
            settings.reference_void_size=max(15,settings.reference_void_size)
            settings.reference_corner_emphasis=max(35,settings.reference_corner_emphasis)
            settings.reference_vortex=22
            rebuilt=generate_field(settings)
            self.assertGreater(len(rebuilt), 100)
            self.assertFalse(any(abs(item.x-50)<4 and abs(item.y-50)<4 for item in rebuilt))
            corners=[item.size for item in rebuilt if item.x<18 and item.y<18]
            near_center=[item.size for item in rebuilt if 38<item.x<45 and 38<item.y<45]
            self.assertGreater(sum(corners)/max(1,len(corners)),sum(near_center)/max(1,len(near_center)))

    def test_field_generation_scales_to_5000_elements(self):
        started=time.perf_counter();records=[]
        for count in (196,500,1000,3000,5000):
            cols=max(1,int(count ** .5));rows=(count+cols-1)//cols
            settings=PatternSettings(active_generator="field",field_generator="gradient_dots",grid_columns=cols,grid_rows=rows,field_density=100,field_threshold=0,gradient_mode="均匀",mask_type="无 Mask",seed=42)
            frame_started=time.perf_counter();items=generate_field(settings);elapsed=time.perf_counter()-frame_started
            records.append((count,elapsed));self.assertGreaterEqual(len(items),int(count*.9))
        self.assertLess(time.perf_counter()-started,5.0,msg=str(records))

    def test_blender_worker_generates_watertight_stl_when_blender_is_available(self):
        info = find_blender()
        if not info:
            self.skipTest("本机未安装 Blender；Worker 会在运行时给出中文安装提示。")
        with tempfile.TemporaryDirectory() as temp:
            primitives = [
                {"kind":"dot", "x":46, "y":50, "size":4},
                {"kind":"dot", "x":50, "y":50, "size":4},
                {"kind":"dot", "x":54, "y":50, "size":4},
                # 与点阵相交，验证最终制造模型是真正单一连通主体。
                {"kind":"line", "x":44, "y":53, "x2":56, "y2":53, "size":1.2},
            ]
            target = Path(temp) / "blender.stl"
            result = run_blender_job(primitives, str(target), thickness=1.2, quality="标准", timeout=180)
            audit = audit_stl(target)
            self.assertGreater(result.triangles, 100)
            self.assertTrue(audit["watertight"])
            self.assertEqual(audit["naked_edges"], 0)
            self.assertEqual(audit["connected_components"], 1)

    def test_blender_worker_blocks_disconnected_final_model(self):
        info = find_blender()
        if not info:
            self.skipTest("本机未安装 Blender；Worker 会在运行时给出中文安装提示。")
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "fragments.stl"
            with self.assertRaisesRegex(RuntimeError, "独立组件"):
                run_blender_job([
                    {"kind": "dot", "x": 20, "y": 20, "size": 2},
                    {"kind": "dot", "x": 80, "y": 80, "size": 2},
                ], str(target), thickness=1.2, quality="草稿", timeout=180)
            self.assertFalse(target.exists())

    def test_native_backend_does_not_require_blender(self):
        """安装干净的电脑没有 Blender 时，STL 仍可在软件内部完成。"""
        primitives = [
            {"kind": "dot", "x": 46, "y": 50, "size": 4},
            {"kind": "dot", "x": 50, "y": 50, "size": 4},
            {"kind": "dot", "x": 54, "y": 50, "size": 4},
            {"kind": "line", "x": 44, "y": 53, "x2": 56, "y2": 53, "size": 1.2},
        ]
        with tempfile.TemporaryDirectory() as temp, patch("ppg.blender_worker.find_blender", return_value=None):
            target = Path(temp) / "native.stl"
            result = run_blender_job(primitives, str(target), thickness=1.2, quality="草稿", timeout=180)
            self.assertEqual(result.blender_path, "native")
            self.assertTrue(result.audit["watertight"])
            self.assertEqual(result.audit["connected_components"], 1)

    def test_height_field_feeds_final_manufacturing_mesh(self):
        source = [
            {"kind": "dot", "x": 48, "y": 50, "size": 4},
            {"kind": "dot", "x": 52, "y": 50, "size": 4},
            {"kind": "line", "x": 46, "y": 51, "x2": 54, "y2": 51, "size": 1.2},
        ]
        raised = apply_height_field(source, 1.2, [{"x": 50, "y": 50, "delta": 2.0, "radius": 12, "falloff": 70}])
        self.assertGreater(min(item["height"] for item in raised), 1.2)
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"XIAOMANG_3D_BACKEND": "native"}, clear=False):
            target = Path(temp) / "height_field.stl"
            result = run_blender_job(raised, str(target), thickness=1.2, quality="标准", timeout=180)
            self.assertTrue(result.audit["watertight"])
            self.assertEqual(result.audit["connected_components"], 1)

    def test_editable_document_is_the_final_manufacturing_source(self):
        document = EditablePatternDocument(
            canvas={"width_mm": 100.0, "height_mm": 100.0},
            elements=[
                EditableElement(id="dot-a", primitive_type="dot", x=45, y=50, width=10, height=10, radius=5),
                EditableElement(id="ellipse-b", primitive_type="ellipse", x=55, y=50, width=12, height=8, radius=6, rotation=20),
            ],
        )
        primitives = document_to_primitives(document)
        self.assertEqual([item["element_id"] for item in primitives], ["dot-a", "ellipse-b"])
        self.assertEqual(primitives[1]["kind"], "ellipse")
        self.assertEqual(primitives[1]["radius_y"], 4.0)
        rotated_bounds = primitives_bounds([primitives[1]])
        self.assertGreater(rotated_bounds[3] - rotated_bounds[1], 8.0)
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"XIAOMANG_3D_BACKEND": "native"}, clear=False):
            result = run_blender_job(primitives, str(Path(temp) / "document-source.stl"), thickness=1.2, quality="草稿")
            self.assertTrue(result.audit["watertight"])
            self.assertEqual(result.audit["connected_components"], 1)

    def test_null_preview_provider_does_not_hold_model_or_render_state(self):
        provider = NullPreviewProvider()
        self.assertIsNone(provider.load_model({"path": "final.stl"}))
        self.assertIsNone(provider.open_model())
        self.assertIsNone(provider.update_model({"path": "final.stl"}))
        self.assertIsNone(provider.fit_view())
        self.assertIsNone(provider.get_bounds())
        self.assertIsNone(provider.capture_preview())
        self.assertIsNone(provider.close())

    def test_radial_manufacturing_primitives_form_one_watertight_model(self):
        """覆盖应用实际使用的“根部脊环 + 放射线 + 节点”制造工作单。"""
        info = find_blender()
        if not info:
            self.skipTest("本机未安装 Blender；Worker 会在运行时给出中文安装提示。")
        settings = PatternSettings(
            contour_type="圆形", element_type="线条 + 圆点", count=32, length=12,
            width=1.2, dot_radius=2.2, seed=42, three_d_min_feature=.8,
        )
        items = generate_items(builtin_contour(settings.contour_type, settings.seed), settings)
        primitives = []
        root_width = max(settings.width, settings.three_d_min_feature)
        for index, item in enumerate(items):
            following = items[(index + 1) % len(items)]
            primitives.append({"kind": "line", "x": item.start[0], "y": item.start[1],
                               "x2": following.start[0], "y2": following.start[1], "size": root_width})
            primitives.append({"kind": "line", "x": item.start[0], "y": item.start[1],
                               "x2": item.end[0], "y2": item.end[1], "size": item.width})
            primitives.append({"kind": "dot", "x": item.end[0], "y": item.end[1], "size": item.radius})
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "radial.stl"
            result = run_blender_job(primitives, str(target), thickness=1.2, quality="标准", timeout=180)
            self.assertTrue(result.audit["watertight"])
            self.assertEqual(result.audit["connected_components"], 1)
            self.assertEqual(result.audit["floating_components"], 0)


if __name__ == "__main__":
    unittest.main()
