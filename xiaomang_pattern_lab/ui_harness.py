"""Tk test harness with native Canvas direct manipulation.

Circle/Ellipse/Rect elements are held as native Canvas items. Pointer motion
only changes an InteractionState and paints a small overlay via ``after_idle``;
the PatternDocument and SVG are written once, on pointer release.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from time import perf_counter
import math
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from ppg.foundation import CircleElement, EllipseElement, FilledRegionElement, FoundationPipeline, PathElement, RectElement, SVGNormalizer
from ppg.integrations import ImageToSVGVectorizationAdapter

from .adapters import BinaryThresholdImageProcessingAdapter, ImageToSVGMCPPreviewAdapter, SVGPreviewAdapter
from .fixtures import build_fixed_suite
from .faithful_mapping import ConversionMode, FaithfulMappingAdapter
from .interaction import InteractionState
from .parametric import GridParametricModel, MaskMode, MaskModifier, PatternMode, SizeGradientMode, SizeGradientModifier
from .parametric_families import RotationFieldMode, RotationFieldModifier, SizeFieldMode, SizeFieldModifier
from .shared_modifiers import POSITION_MODES, PositionModifier, SharedModifierStack
from .pattern_analyzer import AnalysisTolerance
from .performance import PerformanceMetrics
from .field_ui import (
    FIELD_ORDER, field_description, field_label, rotation_description,
    rotation_label,
)
from ppg.foundation.region_geometry import filled_region_polygons
from .session import PatternLabSession, ViewMode
from .spatial_index import BoundingBoxSpatialIndex
from .view_transform import CanvasViewTransform


POSITION_MODE_LABELS = {
    "offset": "整体偏移",
    "attractor": "吸引",
    "repeller": "排斥",
    "radial_push": "径向推开",
    "twist": "扭曲",
    "wave": "波浪位移",
}
POSITION_LABEL_TO_MODE = {label: mode for mode, label in POSITION_MODE_LABELS.items()}
POSITION_MODE_DESCRIPTIONS = {
    "offset": "将全部元素沿 X / Y 方向整体移动。",
    "attractor": "将元素向指定控制点吸引。",
    "repeller": "将元素从指定控制点向外推开。",
    "radial_push": "元素根据距离中心的位置沿径向向外或向内移动。",
    "twist": "围绕指定中心对元素位置进行旋转式扭曲。",
    "wave": "让元素位置沿指定方向产生周期性波浪位移。",
}
POSITION_MODE_FIELDS = {
    "offset": ("offset_x", "offset_y"),
    "attractor": ("center_x", "center_y", "strength", "radius", "falloff"),
    "repeller": ("center_x", "center_y", "strength", "radius", "falloff"),
    "radial_push": ("center_x", "center_y", "amount", "radius", "falloff"),
    "twist": ("center_x", "center_y", "angle", "strength", "radius", "falloff"),
    # Gate I's Wave implementation uses a centre/radius falloff as well as the
    # visible sine parameters, so those controls remain explicit rather than
    # hiding active model state from the user.
    "wave": ("angle", "wavelength", "phase", "amount", "center_x", "center_y", "strength", "radius", "falloff"),
}


def parse_int_ui_value(value: object, name: str, *, minimum: int = 1) -> int:
    """Parse an integer Tk value without silently truncating bad input."""
    text = str(value).strip()
    if not text:
        raise ValueError(f"{name}不能为空。")
    number = float(text)
    if not number.is_integer():
        raise ValueError(f"{name}必须是整数。")
    result = int(number)
    if result < minimum:
        raise ValueError(f"{name}必须不小于 {minimum}。")
    return result


def parse_float_ui_value(value: object, name: str, *, minimum: float | None = None) -> float:
    """Parse a finite continuous value from a Tk Entry/StringVar."""
    text = str(value).strip()
    if not text:
        raise ValueError(f"{name}不能为空。")
    result = float(text)
    if not math.isfinite(result):
        raise ValueError(f"{name}必须是有限数字。")
    if minimum is not None and result < minimum:
        raise ValueError(f"{name}必须不小于 {minimum:g}。")
    return result


class PatternLabApp(tk.Tk):
    """Deliberately small UI: durable state remains in PatternDocument."""

    INSPECTOR_INTERVAL_MS = 66
    PARAMETER_PREVIEW_INTERVAL_MS = 50

    def __init__(self, workspace: str, preview_adapter: SVGPreviewAdapter | None = None):
        super().__init__()
        self.title("小芒图案实验室 / Xiaomang Pattern Lab")
        self.geometry("1280x840")
        self.minsize(1000, 640)
        processor = BinaryThresholdImageProcessingAdapter()
        vectorizer = ImageToSVGVectorizationAdapter(mode="simple")
        self.session = PatternLabSession(
            FoundationPipeline(processor, vectorizer, SVGNormalizer()),
            Path(workspace),
            faithful_mapping=FaithfulMappingAdapter(processor, vectorizer, SVGNormalizer()),
        )
        self._ui_log_path = Path(workspace) / "diagnostics" / "pattern_lab-ui.log"
        self._ui_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.preview_adapter = preview_adapter or ImageToSVGMCPPreviewAdapter()
        self.metrics = PerformanceMetrics()
        self._reference_photo: ImageTk.PhotoImage | None = None
        self._reference_cache_key: tuple[str, int, int] | None = None
        self._reference_cache_image: Image.Image | None = None
        self._view_transform: CanvasViewTransform | None = None
        self._hover_id: str | None = None
        self._interaction: InteractionState | None = None
        self._interaction_after: str | None = None
        self._inspector_after: str | None = None
        self._parameter_after: str | None = None
        self._resize_after: str | None = None
        self._performance_after: str | None = None
        self._closing = False
        self._pan_drag: tuple[int, int] | None = None
        self._static_element_items: dict[str, list[int]] = {}
        self._spatial_index = BoundingBoxSpatialIndex()
        self._pending_grid_fit = None
        self._pending_family_analysis = None
        self._preview_grid_elements = None
        self._status_text = tk.StringVar(value="X: -- mm    Y: -- mm")
        self._zoom_text = tk.StringVar(value="100%")
        self._perf_text = tk.StringVar(value="性能数据等待交互…")
        self.mode = tk.StringVar(value=ViewMode.OVERLAY.value)
        self.conversion_mode = tk.StringVar(value=ConversionMode.FAITHFUL.value)
        self.hide_reference = tk.BooleanVar(value=False)
        self.fixture = tk.StringVar()
        self.selection = tk.StringVar(value="未选择")
        self._parametric_text = tk.StringVar(value="尚未分析当前 Elements。")
        self._element_debug_text = tk.StringVar(value="导入后显示 Element Debug。")
        self.x_var = tk.StringVar(); self.y_var = tk.StringVar(); self.width_var = tk.StringVar(); self.height_var = tk.StringVar(); self.rotation_var = tk.StringVar()
        self.pattern_mode_var = tk.StringVar(value=PatternMode.FREE.value)
        self.lock_aspect_var = tk.BooleanVar(value=True)
        self.gradient_mode_var = tk.StringVar(value=SizeGradientMode.NONE.value)
        self.mask_enabled_var = tk.BooleanVar(value=False)
        self.mask_invert_var = tk.BooleanVar(value=False)
        self.mask_mode_var = tk.StringVar(value=MaskMode.NONE.value)
        self.analysis_tolerance_var = tk.StringVar(value=AnalysisTolerance.STANDARD.value)
        self.family_size_mode_var = tk.StringVar(value=SizeFieldMode.CONSTANT.value)
        self.family_rotation_mode_var = tk.StringVar(value=RotationFieldMode.CONSTANT.value)
        self.family_min_scale_var = tk.StringVar(value="1.0"); self.family_max_scale_var = tk.StringVar(value="1.0")
        self.family_strength_var = tk.StringVar(value="1.0")
        self.family_center_x_var = tk.StringVar(value="0"); self.family_center_y_var = tk.StringVar(value="0")
        self.family_radius_var = tk.StringVar(value="100"); self.family_ring_width_var = tk.StringVar(value="10")
        self.family_ring_invert_var = tk.BooleanVar(value=False); self.family_field_angle_var = tk.StringVar(value="0")
        self.family_wavelength_var = tk.StringVar(value="50"); self.family_phase_var = tk.StringVar(value="0")
        self.family_amplitude_var = tk.StringVar(value="1"); self.family_offset_var = tk.StringVar(value="0")
        self.family_falloff_var = tk.StringVar(value="1"); self.family_duty_cycle_var = tk.StringVar(value="0.5")
        self.family_smoothness_var = tk.StringVar(value="0"); self.family_cell_width_var = tk.StringVar(value="20")
        self.family_cell_height_var = tk.StringVar(value="20"); self.family_turns_var = tk.StringVar(value="3")
        self.family_direction_var = tk.StringVar(value="1"); self.family_rotation_var = tk.StringVar(value="0")
        self.position_mode_var = tk.StringVar(value="offset")
        self.position_mode_display_var = tk.StringVar(value="整体偏移")
        self.position_offset_x_var = tk.StringVar(value="0")
        self.position_offset_y_var = tk.StringVar(value="0")
        self.position_center_x_var = tk.StringVar(value="0")
        self.position_center_y_var = tk.StringVar(value="0")
        self.position_amount_var = tk.StringVar(value="10")
        self.position_radius_var = tk.StringVar(value="100")
        self.position_angle_var = tk.StringVar(value="30")
        self.position_wavelength_var = tk.StringVar(value="50")
        self.position_phase_var = tk.StringVar(value="0")
        self.position_strength_var = tk.StringVar(value="100")
        self.position_falloff_var = tk.StringVar(value="20")
        self._position_description_var = tk.StringVar(value=POSITION_MODE_DESCRIPTIONS["offset"])
        self.family_size_display_var = tk.StringVar(value=field_label(SizeFieldMode.CONSTANT.value))
        self.family_rotation_display_var = tk.StringVar(value=rotation_label(RotationFieldMode.CONSTANT.value))
        self._family_description_var = tk.StringVar(value=field_description(SizeFieldMode.CONSTANT.value))
        self._family_rotation_description_var = tk.StringVar(value=rotation_description(RotationFieldMode.CONSTANT.value))
        self._family_dynamic_frame: ttk.Frame | None = None
        self._family_rotation_frame: ttk.Frame | None = None
        self._matrix_scroll_canvas: tk.Canvas | None = None
        self._matrix_scrollbar: ttk.Scrollbar | None = None
        self._modifier_stack_list: tk.Listbox | None = None
        self._position_dynamic_frame: ttk.Frame | None = None
        self._position_control_widgets: dict[str, tuple[tk.Scale, ttk.Entry]] = {}
        self._position_visible_keys: tuple[str, ...] = ()
        self._position_preview_after: str | None = None
        self._pending_stack_selection: int | None = None
        self._family_preview_after: str | None = None
        self._family_controls_ready = False
        self.grid_vars: dict[str, tk.StringVar] = {}
        self._grid_control_widgets: list[tk.Widget] = []
        self._build()
        for widget in self._grid_control_widgets:
            try: widget.configure(state="disabled")
            except tk.TclError: pass
        self._load_fixtures()
        self._performance_after = self.after(200, self._refresh_performance_panel)

    def _build(self) -> None:
        toolbar = ttk.Frame(self, padding=8); toolbar.pack(fill="x")
        ttk.Button(toolbar, text="导入 PNG / JPG", command=self.import_image).pack(side="left")
        ttk.Radiobutton(toolbar, text="保真映射", value=ConversionMode.FAITHFUL.value, variable=self.conversion_mode).pack(side="left", padx=(8, 0))
        ttk.Radiobutton(toolbar, text="参数化识别", value=ConversionMode.PARAMETRIC.value, variable=self.conversion_mode).pack(side="left", padx=(2, 0))
        ttk.Button(toolbar, text="加载固定测试图", command=self.load_fixture).pack(side="left", padx=(6, 0))
        self.fixture_box = ttk.Combobox(toolbar, state="readonly", width=24, textvariable=self.fixture); self.fixture_box.pack(side="left", padx=6)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(toolbar, text="撤销", command=self.undo).pack(side="left")
        ttk.Button(toolbar, text="重做", command=self.redo).pack(side="left", padx=(2, 8))
        ttk.Button(toolbar, text="－", width=3, command=lambda: self.change_zoom(0.8)).pack(side="left")
        ttk.Label(toolbar, textvariable=self._zoom_text, width=6, anchor="center").pack(side="left")
        ttk.Button(toolbar, text="＋", width=3, command=lambda: self.change_zoom(1.25)).pack(side="left")
        ttk.Button(toolbar, text="重置视图", command=self.reset_view).pack(side="left", padx=(4, 8))
        for mode, label in ((ViewMode.REFERENCE, "原图"), (ViewMode.VECTOR, "矢量"), (ViewMode.OVERLAY, "叠加")):
            ttk.Radiobutton(toolbar, text=label, value=mode.value, variable=self.mode, command=self.refresh_canvas).pack(side="left", padx=3)
        ttk.Checkbutton(toolbar, text="隐藏原图（验证 Geometry）", variable=self.hide_reference, command=self.refresh_canvas).pack(side="left", padx=8)
        ttk.Button(toolbar, text="导出 SVG", command=self.export_svg).pack(side="right")
        ttk.Button(toolbar, text="保存工程", command=self.save_document).pack(side="right", padx=5)
        ttk.Button(toolbar, text="重新打开工程", command=self.open_document).pack(side="right")

        body = ttk.Panedwindow(self, orient="horizontal"); body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        left = ttk.Frame(body, padding=6); body.add(left, weight=0)
        center = ttk.Frame(body, padding=3); body.add(center, weight=1)
        right = ttk.Frame(body, padding=6); body.add(right, weight=0)
        self._build_left_panel(left); self._build_viewport(center); self._build_debug_panel(right)

    def _build_left_panel(self, parent: ttk.Frame) -> None:
        tabs = ttk.Notebook(parent); tabs.pack(fill="both", expand=True)
        element_tab = ttk.Frame(tabs, padding=8); tabs.add(element_tab, text="元素编辑")
        matrix_tab = ttk.Frame(tabs, padding=5); tabs.add(matrix_tab, text="规则矩阵测试")
        ttk.Label(element_tab, text="Element 编辑", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w")
        ttk.Label(element_tab, textvariable=self.selection, wraplength=240).pack(anchor="w", pady=(4, 10))
        for label, variable in (("X", self.x_var), ("Y", self.y_var), ("宽度", self.width_var), ("高度", self.height_var), ("旋转", self.rotation_var)):
            row = ttk.Frame(element_tab); row.pack(fill="x", pady=3)
            ttk.Label(row, text=label, width=6).pack(side="left")
            entry = ttk.Entry(row, textvariable=variable, width=15); entry.pack(side="left", fill="x", expand=True)
            entry.bind("<Return>", lambda _event, position=label in {"X", "Y"}, rotation=label == "旋转": self.apply_position() if position else self.apply_rotation() if rotation else self.apply_size())
        ttk.Button(element_tab, text="应用位置", command=self.apply_position).pack(fill="x", pady=(10, 3))
        ttk.Button(element_tab, text="应用尺寸", command=self.apply_size).pack(fill="x", pady=3)
        ttk.Button(element_tab, text="应用旋转", command=self.apply_rotation).pack(fill="x", pady=3)
        ttk.Button(element_tab, text="复制选中元素", command=self.duplicate).pack(fill="x", pady=(12, 3))
        ttk.Button(element_tab, text="删除选中元素", command=self.delete).pack(fill="x", pady=3)
        ttk.Button(element_tab, text="布尔并集", command=self.union_selected).pack(fill="x", pady=(12, 3))
        ttk.Button(element_tab, text="布尔差集（主选 - 其余）", command=self.difference_selected).pack(fill="x", pady=3)
        ttk.Label(element_tab, text="直接操作：点击选择；Shift+点击多选；拖动移动；\n拖动四角控制点缩放。Canvas 始终读取 PatternDocument。", foreground="#56616f", wraplength=250).pack(anchor="w", pady=(18, 0))
        self._build_matrix_panel(matrix_tab)

    def _build_matrix_panel(self, parent: ttk.Frame) -> None:
        # The matrix tab contains more controls than a typical laptop viewport.
        # Keep the whole tab (shared fields + grid + mask) in one scroll region;
        # previously only the bottom grid form scrolled, leaving the top controls
        # visible while silently clipping the remaining options.
        scroll_shell = ttk.Frame(parent)
        scroll_shell.pack(fill="both", expand=True)
        scroll_canvas = tk.Canvas(scroll_shell, highlightthickness=0, background="#f8fafc")
        scroll_bar = ttk.Scrollbar(scroll_shell, orient="vertical", command=scroll_canvas.yview)
        self._matrix_scroll_canvas = scroll_canvas
        self._matrix_scrollbar = scroll_bar
        scroll_canvas.configure(yscrollcommand=scroll_bar.set)
        scroll_bar.pack(side="right", fill="y")
        scroll_canvas.pack(side="left", fill="both", expand=True)
        content = ttk.Frame(scroll_canvas, padding=5)
        content_window = scroll_canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>", lambda _event: scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all")))
        scroll_canvas.bind("<Configure>", lambda event: scroll_canvas.itemconfigure(content_window, width=event.width))
        scroll_canvas.bind("<Enter>", lambda _event: scroll_canvas.focus_set())
        # Route the wheel only while the pointer is inside this panel.  A
        # bind_all is safe here because the handler returns ``break`` only for
        # descendants of this scroll canvas; the main design Canvas keeps its
        # own wheel-to-zoom binding untouched.
        self.bind_all("<MouseWheel>", self._route_matrix_mousewheel, add="+")
        # Build all controls in the scrollable content frame from this point on.
        parent = content

        header = ttk.Frame(parent); header.pack(fill="x")
        ttk.Label(header, text="基础结构：").pack(side="left")
        ttk.Radiobutton(header, text="原始元素", value=PatternMode.FREE.value, variable=self.pattern_mode_var, command=self._switch_mode).pack(side="left")
        ttk.Radiobutton(header, text="矩阵结构", value=PatternMode.GRID.value, variable=self.pattern_mode_var, command=self._switch_mode).pack(side="left", padx=(8, 0))
        ttk.Button(parent, text="尝试参数化", command=self.try_parametric).pack(fill="x", pady=(6, 3))
        self.convert_family_button = ttk.Button(parent, text="转换为推荐结构", command=self.convert_pending_grid)
        self.convert_family_button.pack(fill="x", pady=(0, 3))
        ttk.Button(parent, text="进入自由参数化", command=self.enter_free_parametric).pack(fill="x", pady=(0, 6))
        ttk.Button(parent, text="烘焙为自由元素", command=self.bake_to_free_elements).pack(fill="x", pady=(0, 6))
        ttk.Label(parent, textvariable=self._parametric_text, foreground="#44515e", wraplength=250, justify="left").pack(anchor="w", pady=(0, 6))
        fields = ttk.LabelFrame(parent, text="参数化效果（适用于所有结构）", padding=5)
        fields.pack(fill="x", pady=(0, 6))
        ttk.Label(fields, text="尺寸场").grid(row=0, column=0, sticky="w")
        size_combo = ttk.Combobox(fields, state="readonly", textvariable=self.family_size_display_var,
                                  values=tuple(field_label(item.value) for item in SizeFieldMode), width=14)
        size_combo.grid(row=0, column=1, sticky="ew")
        size_combo.bind("<<ComboboxSelected>>", self._on_family_size_selected)
        ttk.Label(fields, textvariable=self._family_description_var, foreground="#56616f", wraplength=230,
                  justify="left").grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 5))
        self._family_dynamic_frame = ttk.Frame(fields)
        self._family_dynamic_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
        ttk.Separator(fields, orient="horizontal").grid(row=3, column=0, columnspan=2, sticky="ew", pady=5)
        ttk.Label(fields, text="旋转场").grid(row=4, column=0, sticky="w")
        rotation_combo = ttk.Combobox(fields, state="readonly", textvariable=self.family_rotation_display_var,
                                      values=tuple(rotation_label(item.value) for item in RotationFieldMode), width=14)
        rotation_combo.grid(row=4, column=1, sticky="ew")
        rotation_combo.bind("<<ComboboxSelected>>", self._on_family_rotation_selected)
        ttk.Label(fields, textvariable=self._family_rotation_description_var, foreground="#56616f", wraplength=230,
                  justify="left").grid(row=5, column=0, columnspan=2, sticky="w", pady=(2, 5))
        self._family_rotation_frame = ttk.Frame(fields)
        self._family_rotation_frame.grid(row=6, column=0, columnspan=2, sticky="ew")
        fields.columnconfigure(1, weight=1)
        ttk.Button(fields, text="重置参数", command=self.reset_family_fields).grid(row=7, column=0, columnspan=2, sticky="ew", pady=(3, 0))
        ttk.Button(fields, text="应用共享参数场", command=self.apply_family_fields).grid(row=8, column=0, columnspan=2, sticky="ew", pady=(3, 0))
        self._build_family_field_panel()
        self._family_controls_ready = True
        self._build_modifier_stack_panel(parent)
        tolerance_row = ttk.Frame(parent); tolerance_row.pack(fill="x", pady=(0, 5))
        ttk.Label(tolerance_row, text="分析容差", width=9).pack(side="left")
        tolerance_combo = ttk.Combobox(tolerance_row, state="readonly", textvariable=self.analysis_tolerance_var,
                                       values=(AnalysisTolerance.STRICT.value, AnalysisTolerance.STANDARD.value, AnalysisTolerance.LENIENT.value), width=14)
        tolerance_combo.pack(side="left", fill="x", expand=True)
        tolerance_combo.bind("<<ComboboxSelected>>", lambda _event: self.session.set_grid_analysis_tolerance(self.analysis_tolerance_var.get()))
        # Grid and mask parameters are part of the same scrollable page.  This
        # avoids a nested, nearly-zero-height scrollbar that made these options
        # appear to disappear on smaller windows.
        form = ttk.Frame(parent, padding=6)
        form.pack(fill="x", pady=(2, 0))
        self._add_grid_number(form, "rows", "行数", 1, 120, 1, "12")
        self._add_grid_number(form, "columns", "列数", 1, 120, 1, "12")
        self._add_grid_number(form, "spacing_x", "Spacing U (mm)", 0.1, 120, 0.1, "12")
        self._add_grid_number(form, "spacing_y", "Spacing V (mm)", 0.1, 120, 0.1, "12")
        ttk.Label(form, text="二维基向量（允许旋转、斜向与非正交格子）", foreground="#44515e", wraplength=245).pack(anchor="w", pady=(5, 0))
        self._add_grid_number(form, "basis_u_x", "Basis U · X (mm)", -120, 120, 0.1, "12")
        self._add_grid_number(form, "basis_u_y", "Basis U · Y (mm)", -120, 120, 0.1, "0")
        self._add_grid_number(form, "basis_v_x", "Basis V · X (mm)", -120, 120, 0.1, "0")
        self._add_grid_number(form, "basis_v_y", "Basis V · Y (mm)", -120, 120, 0.1, "12")
        self._add_grid_number(form, "element_width", "单元宽度 (mm)", 0.1, 80, 0.1, "6")
        self._add_grid_number(form, "element_height", "单元高度 (mm)", 0.1, 80, 0.1, "6")
        ttk.Checkbutton(form, text="锁定单元比例", variable=self.lock_aspect_var, command=self._schedule_grid_preview).pack(anchor="w", pady=3)
        self._add_grid_number(form, "rotation", "整体旋转 (°)", -180, 180, 1, "0")
        self._add_grid_number(form, "offset_x", "X 偏移 (mm)", -200, 200, 0.1, "0")
        self._add_grid_number(form, "offset_y", "Y 偏移 (mm)", -200, 200, 0.1, "0")
        ttk.Separator(form, orient="horizontal").pack(fill="x", pady=6)
        ttk.Label(form, text="Size Gradient").pack(anchor="w")
        combo = ttk.Combobox(form, state="readonly", textvariable=self.gradient_mode_var, values=(SizeGradientMode.NONE.value, SizeGradientMode.HORIZONTAL.value, SizeGradientMode.VERTICAL.value, SizeGradientMode.CENTER_TO_EDGE.value, SizeGradientMode.EDGE_TO_CENTER.value, SizeGradientMode.RADIAL.value, SizeGradientMode.ELLIPTICAL_RADIAL.value))
        combo.pack(fill="x", pady=2); combo.bind("<<ComboboxSelected>>", lambda _event: self._schedule_grid_preview())
        self._add_grid_number(form, "min_size", "最小尺寸 (mm)", 0.1, 80, 0.1, "3")
        self._add_grid_number(form, "max_size", "最大尺寸 (mm)", 0.1, 80, 0.1, "10")
        self._add_grid_number(form, "center_x", "渐变中心 X", -200, 200, 0.1, "0")
        self._add_grid_number(form, "center_y", "渐变中心 Y", -200, 200, 0.1, "0")
        self._add_grid_number(form, "radius_x", "尺寸场半径 X", 0.1, 500, 0.1, "50")
        self._add_grid_number(form, "radius_y", "尺寸场半径 Y", 0.1, 500, 0.1, "50")
        self._add_grid_number(form, "falloff", "尺寸场衰减", 0.05, 5, 0.05, "1")
        self._add_grid_number(form, "strength", "渐变强度", 0, 1, 0.01, "1")
        ttk.Separator(form, orient="horizontal").pack(fill="x", pady=6)
        ttk.Label(form, text="Mask Modifier").pack(anchor="w")
        ttk.Checkbutton(form, text="启用掩膜", variable=self.mask_enabled_var, command=self._schedule_grid_preview).pack(anchor="w", pady=(2, 0))
        ttk.Checkbutton(form, text="反转掩膜", variable=self.mask_invert_var, command=self._schedule_grid_preview).pack(anchor="w")
        mask_combo = ttk.Combobox(form, state="readonly", textvariable=self.mask_mode_var, values=(MaskMode.NONE.value, MaskMode.RECTANGLE.value, MaskMode.CIRCLE.value, MaskMode.IMPORTED_PATH.value))
        mask_combo.pack(fill="x", pady=2); mask_combo.bind("<<ComboboxSelected>>", lambda _event: self._schedule_grid_preview())
        self._add_grid_number(form, "mask_center_x", "掩膜中心 X", -200, 200, 0.1, "0")
        self._add_grid_number(form, "mask_center_y", "掩膜中心 Y", -200, 200, 0.1, "0")
        self._add_grid_number(form, "mask_width", "矩形宽度 (mm)", 0.1, 500, 0.1, "100")
        self._add_grid_number(form, "mask_height", "矩形高度 (mm)", 0.1, 500, 0.1, "100")
        self._add_grid_number(form, "mask_radius", "圆形半径 (mm)", 0.1, 500, 0.1, "50")
        ttk.Label(form, text="滑块拖动仅预览；松开后一次提交。", foreground="#56616f", wraplength=245).pack(anchor="w", pady=(8, 2))

    def _build_modifier_stack_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.LabelFrame(parent, text="效果堆栈（可组合）", padding=5)
        panel.pack(fill="x", pady=(0, 6))
        self._modifier_stack_list = tk.Listbox(panel, height=4, exportselection=False,
                                               activestyle="dotbox", relief="solid", borderwidth=1)
        self._modifier_stack_list.pack(fill="x", pady=(0, 4))
        self._modifier_stack_list.bind("<<ListboxSelect>>", self._on_stack_selection)
        add_row = ttk.Frame(panel); add_row.pack(fill="x", pady=(0, 3))
        ttk.Button(add_row, text="添加尺寸层", command=lambda: self._add_current_stack_layer("size")).pack(side="left", fill="x", expand=True)
        ttk.Button(add_row, text="添加旋转层", command=lambda: self._add_current_stack_layer("rotation")).pack(side="left", fill="x", expand=True, padx=(3, 0))
        position_box = ttk.LabelFrame(panel, text="位置 / 变形", padding=4)
        position_box.pack(fill="x", pady=(2, 4))
        mode_combo = ttk.Combobox(position_box, state="readonly", values=tuple(POSITION_MODE_LABELS.values()),
                                   textvariable=self.position_mode_display_var)
        mode_combo.pack(fill="x", pady=(0, 3))
        mode_combo.bind("<<ComboboxSelected>>", self._on_position_mode_selected)
        ttk.Label(position_box, textvariable=self._position_description_var, foreground="#56616f",
                  wraplength=245, justify="left").pack(anchor="w", pady=(0, 3))
        self._position_dynamic_frame = ttk.Frame(position_box)
        self._position_dynamic_frame.pack(fill="x")
        self._build_position_parameter_panel()
        ttk.Button(position_box, text="添加位置/变形层", command=lambda: self._add_current_stack_layer("position")).pack(fill="x", pady=(3, 0))
        action_row = ttk.Frame(panel); action_row.pack(fill="x")
        for label, callback in (("启用/停用", self._toggle_stack_layer), ("↑", lambda: self._move_stack_layer(-1)),
                                ("↓", lambda: self._move_stack_layer(1)), ("复制", self._duplicate_stack_layer),
                                ("删除", self._delete_stack_layer), ("重置", self._reset_stack_layer)):
            ttk.Button(action_row, text=label, command=callback, width=7).pack(side="left", padx=(0, 2))
        ttk.Label(panel, text="每层独立保存；调整顺序不会修改 source geometry。", foreground="#56616f",
                  wraplength=245).pack(anchor="w", pady=(4, 0))

    def _stack_from_document(self) -> SharedModifierStack | None:
        document = self.session.document
        if document is None:
            return None
        stack = SharedModifierStack.from_document(document)
        return stack if stack is not None and stack.modifiers else None

    def _refresh_modifier_stack(self) -> None:
        if self._modifier_stack_list is None:
            return
        previous = self._pending_stack_selection
        if previous is None:
            selected = self._modifier_stack_list.curselection()
            previous = int(selected[0]) if selected else None
        self._modifier_stack_list.delete(0, "end")
        stack = self._stack_from_document()
        if stack is None:
            self._modifier_stack_list.insert("end", "暂无独立效果层（可从上方参数添加）")
            self._pending_stack_selection = None
            return
        labels = {"size": "尺寸", "rotation": "旋转", "position": "位置/变形"}
        for item in stack.modifiers:
            state = "启用" if bool(item.get("enabled", True)) else "停用"
            self._modifier_stack_list.insert("end", "%s  %s → %s" % (state, item.get("id", "modifier"), labels.get(item.get("type"), item.get("type"))))
        if previous is not None and stack.modifiers:
            previous = min(max(0, previous), len(stack.modifiers) - 1)
            self._modifier_stack_list.selection_set(previous)
            self._modifier_stack_list.see(previous)
            item = stack.modifiers[previous]
            if item.get("type") == "position":
                self._load_position_controls(PositionModifier.from_dict(item.get("parameters")))
        self._pending_stack_selection = None

    def _selected_stack_index(self) -> int | None:
        if self._modifier_stack_list is None:
            return None
        selected = self._modifier_stack_list.curselection()
        if not selected or self._stack_from_document() is None:
            return None
        return int(selected[0])

    def _add_current_stack_layer(self, modifier_type: str) -> None:
        def action() -> None:
            if modifier_type == "position":
                parameters = self._position_parameters_from_controls()
            else:
                size, rotation = self._family_modifiers_from_controls()
                parameters = size.to_dict() if modifier_type == "size" else rotation.to_dict()
            self.session.add_modifier_layer(modifier_type, parameters)
            stack = self._stack_from_document()
            self._pending_stack_selection = len(stack.modifiers) - 1 if stack else None
            self._after_document_change()
        self._handle(action)

    def _position_parameters_from_controls(self) -> dict:
        values = {
            "mode": self.position_mode_var.get(),
            "offset_x": parse_float_ui_value(self.position_offset_x_var.get(), "偏移 X"),
            "offset_y": parse_float_ui_value(self.position_offset_y_var.get(), "偏移 Y"),
            "center_x": parse_float_ui_value(self.position_center_x_var.get(), "中心 X"),
            "center_y": parse_float_ui_value(self.position_center_y_var.get(), "中心 Y"),
            "strength": min(1.0, max(0.0, parse_float_ui_value(self.position_strength_var.get(), "强度", minimum=0.0) / 100.0)),
            "amount": parse_float_ui_value(self.position_amount_var.get(), "幅度/距离"),
            "radius": parse_float_ui_value(self.position_radius_var.get(), "影响半径", minimum=1e-9),
            "angle": parse_float_ui_value(self.position_angle_var.get(), "角度"),
            "wavelength": parse_float_ui_value(self.position_wavelength_var.get(), "波长", minimum=1e-9),
            "phase": math.radians(parse_float_ui_value(self.position_phase_var.get(), "相位")),
            "falloff": max(0.05, parse_float_ui_value(self.position_falloff_var.get(), "衰减", minimum=0.0) / 20.0),
        }
        return PositionModifier(**values).to_dict()

    def _position_world_ranges(self) -> dict[str, tuple[float, float, float, str]]:
        document = self.session.document
        stack = self._stack_from_document()
        elements = stack.source_snapshot() if stack and stack.source_elements else (document.elements if document else [])
        if elements:
            min_x = min(item.x - item.width / 2 for item in elements); max_x = max(item.x + item.width / 2 for item in elements)
            min_y = min(item.y - item.height / 2 for item in elements); max_y = max(item.y + item.height / 2 for item in elements)
        elif document:
            min_x, min_y = document.canvas.origin_x, document.canvas.origin_y
            max_x, max_y = min_x + document.canvas.width, min_y + document.canvas.height
        else:
            min_x = min_y = -100.0; max_x = max_y = 100.0
        width = max(1.0, max_x - min_x); height = max(1.0, max_y - min_y)
        diagonal = max(1.0, math.hypot(width, height))
        if max_x - min_x < 1e-9: min_x, max_x = min_x - 1.0, max_x + 1.0
        if max_y - min_y < 1e-9: min_y, max_y = min_y - 1.0, max_y + 1.0
        return {
            "offset_x": (-width, width, 0.1, "mm"), "offset_y": (-height, height, 0.1, "mm"),
            "center_x": (min_x, max_x, 0.1, "mm"), "center_y": (min_y, max_y, 0.1, "mm"),
            "strength": (0.0, 100.0, 1.0, "%"), "amount": (-diagonal, diagonal, 0.1, "mm"),
            "radius": (0.1, diagonal * 2.0, 0.1, "mm"), "angle": (-180.0, 180.0, 1.0, "°"),
            "wavelength": (0.1, diagonal * 2.0, 0.1, "mm"), "phase": (-180.0, 180.0, 1.0, "°"),
            "falloff": (0.0, 100.0, 1.0, "%"),
        }

    def _position_variables(self) -> dict[str, tk.StringVar]:
        return {
            "offset_x": self.position_offset_x_var, "offset_y": self.position_offset_y_var,
            "center_x": self.position_center_x_var, "center_y": self.position_center_y_var,
            "strength": self.position_strength_var, "amount": self.position_amount_var,
            "radius": self.position_radius_var, "angle": self.position_angle_var,
            "wavelength": self.position_wavelength_var, "phase": self.position_phase_var,
            "falloff": self.position_falloff_var,
        }

    def _add_position_slider(self, parent: ttk.Frame, key: str, label: str,
                             limits: tuple[float, float, float, str]) -> None:
        minimum, maximum, resolution, unit = limits
        variable = self._position_variables()[key]
        row = ttk.Frame(parent); row.pack(fill="x", pady=1)
        ttk.Label(row, text=label, width=11, anchor="w").pack(side="left")
        scale = tk.Scale(row, from_=minimum, to=maximum, resolution=resolution, orient="horizontal",
                         showvalue=False, variable=variable, highlightthickness=0, length=115,
                         command=lambda _value: self._schedule_position_preview())
        scale.pack(side="left", fill="x", expand=True)
        entry = ttk.Entry(row, textvariable=variable, width=7); entry.pack(side="right", padx=(3, 0))
        if unit: ttk.Label(row, text=unit, width=3).pack(side="right")
        scale.bind("<ButtonRelease-1>", lambda _event: self._commit_position_controls())
        entry.bind("<KeyRelease>", lambda _event: self._schedule_position_preview())
        entry.bind("<Return>", lambda _event: self._commit_position_controls())
        entry.bind("<FocusOut>", lambda _event: self._commit_position_controls())
        self._position_control_widgets[key] = (scale, entry)

    def _build_position_parameter_panel(self) -> None:
        frame = self._position_dynamic_frame
        if frame is None: return
        for child in frame.winfo_children(): child.destroy()
        self._position_control_widgets.clear()
        mode = self.position_mode_var.get()
        if mode not in POSITION_MODES: mode = "offset"; self.position_mode_var.set(mode)
        self.position_mode_display_var.set(POSITION_MODE_LABELS[mode])
        self._position_description_var.set(POSITION_MODE_DESCRIPTIONS[mode])
        labels = {
            "offset_x": "偏移 X", "offset_y": "偏移 Y", "center_x": "中心 X", "center_y": "中心 Y",
            "strength": "强度", "amount": "幅度/距离", "radius": "影响半径", "angle": "角度",
            "wavelength": "波长", "phase": "相位", "falloff": "衰减",
        }
        limits = self._position_world_ranges()
        self._position_visible_keys = POSITION_MODE_FIELDS[mode]
        for key in self._position_visible_keys:
            self._add_position_slider(frame, key, labels[key], limits[key])

    def _load_position_controls(self, modifier: PositionModifier, *, rebuild: bool = True) -> None:
        self.position_mode_var.set(modifier.mode); self.position_mode_display_var.set(POSITION_MODE_LABELS[modifier.mode])
        self.position_offset_x_var.set("%.6g" % modifier.offset_x); self.position_offset_y_var.set("%.6g" % modifier.offset_y)
        self.position_center_x_var.set("%.6g" % modifier.center_x); self.position_center_y_var.set("%.6g" % modifier.center_y)
        self.position_amount_var.set("%.6g" % modifier.amount); self.position_radius_var.set("%.6g" % modifier.radius)
        self.position_angle_var.set("%.6g" % modifier.angle); self.position_wavelength_var.set("%.6g" % modifier.wavelength)
        self.position_phase_var.set("%.6g" % math.degrees(modifier.phase)); self.position_strength_var.set("%.6g" % (modifier.strength * 100.0))
        self.position_falloff_var.set("%.6g" % (modifier.falloff * 20.0))
        if rebuild: self._build_position_parameter_panel()

    def _on_stack_selection(self, _event=None) -> None:
        index = self._selected_stack_index(); stack = self._stack_from_document()
        if index is None or stack is None: return
        item = stack.modifiers[index]
        if item.get("type") == "position": self._load_position_controls(PositionModifier.from_dict(item.get("parameters")))

    def _on_position_mode_selected(self, _event=None) -> None:
        mode = POSITION_LABEL_TO_MODE.get(self.position_mode_display_var.get(), "offset")
        self._load_position_controls(PositionModifier(mode=mode))
        index = self._selected_stack_index(); stack = self._stack_from_document()
        if index is not None and stack is not None and stack.modifiers[index].get("type") == "position":
            self._commit_position_controls(label="切换位置/变形模式")

    def _schedule_position_preview(self) -> None:
        index = self._selected_stack_index(); stack = self._stack_from_document()
        if index is None or stack is None or stack.modifiers[index].get("type") != "position": return
        if self._position_preview_after is None:
            self._position_preview_after = self.after(self.PARAMETER_PREVIEW_INTERVAL_MS, self._run_position_preview)

    def _run_position_preview(self) -> None:
        self._position_preview_after = None
        try:
            index = self._selected_stack_index(); stack = self._stack_from_document()
            if index is None or stack is None or stack.modifiers[index].get("type") != "position": return
            preview = self.session.preview_modifier_parameters(index, self._position_parameters_from_controls())
            self._preview_grid_elements = preview
            self._render_static_layer(elements=preview, update_index=False); self._render_interaction_layer()
        except Exception as error:
            self._log_exception("位置/变形参数预览", error)

    def _commit_position_controls(self, *, label: str = "更新位置/变形层") -> None:
        if self._position_preview_after:
            try: self.after_cancel(self._position_preview_after)
            except tk.TclError: pass
            self._position_preview_after = None
        index = self._selected_stack_index(); stack = self._stack_from_document()
        if index is None or stack is None or stack.modifiers[index].get("type") != "position": return
        parameters = self._position_parameters_from_controls()
        self._pending_stack_selection = index
        self._handle(lambda: (self.session.update_modifier_parameters(index, parameters, label=label), self._after_document_change()))

    def _toggle_stack_layer(self) -> None:
        index = self._selected_stack_index()
        stack = self._stack_from_document()
        if index is None or stack is None:
            return
        self._pending_stack_selection = index
        self._handle(lambda: (self.session.set_modifier_enabled(index, not bool(stack.modifiers[index].get("enabled", True))), self._after_document_change()))

    def _move_stack_layer(self, delta: int) -> None:
        index = self._selected_stack_index()
        if index is not None:
            def action() -> None:
                self._pending_stack_selection = self.session.move_modifier_layer(index, delta)
                self._after_document_change()
            self._handle(action)

    def _duplicate_stack_layer(self) -> None:
        index = self._selected_stack_index()
        if index is not None:
            self._pending_stack_selection = index + 1
            self._handle(lambda: (self.session.duplicate_modifier_layer(index), self._after_document_change()))

    def _delete_stack_layer(self) -> None:
        index = self._selected_stack_index()
        if index is not None:
            self._pending_stack_selection = max(0, index - 1)
            self._handle(lambda: (self.session.delete_modifier_layer(index), self._after_document_change()))

    def _reset_stack_layer(self) -> None:
        index = self._selected_stack_index()
        stack = self._stack_from_document()
        if index is None or stack is None: return
        self._pending_stack_selection = index
        if stack.modifiers[index].get("type") == "position":
            mode = PositionModifier.from_dict(stack.modifiers[index].get("parameters")).mode
            defaults = PositionModifier(mode=mode)
            self._load_position_controls(defaults)
            self._handle(lambda: (self.session.update_modifier_parameters(index, defaults.to_dict(), label="重置位置/变形层"), self._after_document_change()))
        else:
            self._handle(lambda: (self.session.reset_modifier_layer(index), self._after_document_change()))

    def _route_matrix_mousewheel(self, event: tk.Event):
        """Scroll the matrix page when the pointer is over any child control."""
        canvas = self._matrix_scroll_canvas
        if canvas is None or not canvas.winfo_exists():
            return None
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget is canvas:
                delta = int(-event.delta / 120) if getattr(event, "delta", 0) else 0
                if delta:
                    canvas.yview_scroll(delta, "units")
                return "break"
            try:
                widget = widget.master
            except AttributeError:
                widget = None
        return None

    def _add_grid_number(self, parent, key: str, label: str, minimum: float, maximum: float, resolution: float, initial: str) -> None:
        variable = tk.StringVar(value=initial); self.grid_vars[key] = variable
        ttk.Label(parent, text=label).pack(anchor="w", pady=(4, 0))
        row = ttk.Frame(parent); row.pack(fill="x")
        scale = tk.Scale(row, from_=minimum, to=maximum, resolution=resolution, orient="horizontal", showvalue=False, variable=variable, command=lambda _value: self._schedule_grid_preview(), highlightthickness=0)
        scale.pack(side="left", fill="x", expand=True)
        entry = ttk.Entry(row, textvariable=variable, width=8); entry.pack(side="right", padx=(4, 0))
        self._grid_control_widgets.extend((scale, entry))
        entry.bind("<Return>", lambda _event: self._commit_grid_from_controls())
        scale.bind("<ButtonRelease-1>", lambda _event: self._commit_grid_from_controls())

    def _build_viewport(self, center: ttk.Frame) -> None:
        viewport = ttk.Frame(center); viewport.pack(fill="both", expand=True)
        self.ruler_x = tk.Canvas(viewport, height=24, background="#f3f6f9", highlightthickness=0); self.ruler_x.pack(side="top", fill="x")
        self.ruler_y = tk.Canvas(viewport, width=42, background="#f3f6f9", highlightthickness=0); self.ruler_y.pack(side="left", fill="y")
        self.canvas = tk.Canvas(viewport, background="white", highlightthickness=1, highlightbackground="#aeb8c5", cursor="crosshair"); self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self.canvas_press); self.canvas.bind("<B1-Motion>", self.canvas_drag); self.canvas.bind("<ButtonRelease-1>", self.canvas_release)
        self.canvas.bind("<Motion>", self.canvas_motion); self.canvas.bind("<Leave>", lambda _event: self._set_cursor_status(None))
        self.canvas.bind("<ButtonPress-2>", self.pan_press); self.canvas.bind("<B2-Motion>", self.pan_drag); self.canvas.bind("<ButtonRelease-2>", self.pan_release)
        self.canvas.bind("<MouseWheel>", self.wheel_zoom); self.canvas.bind("<Escape>", self.cancel_interaction); self.canvas.bind("<Configure>", self._canvas_resized)
        self.bind_all("<Control-z>", self._shortcut_undo); self.bind_all("<Control-Shift-Z>", self._shortcut_redo); self.bind_all("<Control-y>", self._shortcut_redo)
        self.ruler_x.bind("<Configure>", lambda _event: self.refresh_rulers()); self.ruler_y.bind("<Configure>", lambda _event: self.refresh_rulers())
        ttk.Label(center, textvariable=self._status_text, anchor="w", foreground="#56616f").pack(fill="x", pady=(4, 0))

    def _build_debug_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Element Debug", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w")
        ttk.Label(parent, textvariable=self._element_debug_text, justify="left", foreground="#44515e", wraplength=280).pack(anchor="w", pady=(4, 10))
        ttk.Label(parent, text="转换日志", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w")
        self.log = tk.Text(parent, width=36, height=30, state="disabled", background="#f6f8fb", relief="flat", wrap="word"); self.log.pack(fill="both", expand=True, pady=(4, 8))
        ttk.Label(parent, text="性能 Debug", font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w")
        ttk.Label(parent, textvariable=self._perf_text, justify="left", foreground="#44515e", wraplength=280).pack(anchor="w", pady=(3, 0))

    def _load_fixtures(self) -> None:
        self._fixtures = build_fixed_suite(); self.fixture_box["values"] = tuple(self._fixtures.keys()); self.fixture.set(next(iter(self._fixtures)))

    def _handle(self, callback) -> None:
        try: callback()
        except Exception as error:
            self._log_exception("UI callback", error)
            self.refresh_log()
            messagebox.showerror("小芒图案实验室", str(error), parent=self)

    def _log_exception(self, context: str, error: BaseException | None = None) -> None:
        """Persist the complete traceback; never reduce a UI failure to TypeError text."""
        trace = traceback.format_exc() if error is not None else traceback.format_exc()
        if trace.strip() == "NoneType: None":
            trace = "".join(traceback.format_stack())
        message = f"{context} 异常:\n{trace}"
        try:
            self.session.log(message, "ERROR")
            with self._ui_log_path.open("a", encoding="utf-8") as stream:
                stream.write(message + "\n")
        except Exception:
            # Diagnostics must never turn the original callback failure into a
            # second failure that hides its traceback.
            pass

    def import_image(self) -> None:
        path = filedialog.askopenfilename(parent=self, title="导入参考图", filetypes=[("图片", "*.png;*.jpg;*.jpeg"), ("所有文件", "*.*")])
        if path: self._handle(lambda: self._import(path))

    def load_fixture(self) -> None:
        if self.fixture.get(): self._handle(lambda: self._import(str(self._fixtures[self.fixture.get()])))

    def _import(self, path: str) -> None:
        self.session.import_image(path, self.conversion_mode.get()); self.session.document.canvas.unit = "mm"; self.session.document.canvas.mm_per_unit = 1.0
        self._pending_grid_fit = None; self._pending_family_analysis = None; self._parametric_text.set("当前为自由元素模式；可点击“尝试参数化”。")
        self.pattern_mode_var.set(PatternMode.FREE.value); self._view_transform = None; self._reference_cache_key = None; self._reference_cache_image = None; self._preview_grid_elements = None
        self.refresh_all()

    # Direct editing: document is intentionally not mutated until release.
    def canvas_press(self, event: tk.Event) -> None:
        document, transform = self.session.document, self._view_transform
        if not document or transform is None or self._preview_grid_elements is not None: return
        world_x, world_y = transform.screenToWorld(event.x, event.y); handle = self._scale_handle_at(event.x, event.y); selected = self.session.selected_id
        if handle and selected:
            self._begin_interaction("scale", document.element(selected), world_x, world_y, handle); return
        self.metrics.spatial_queries += 1; selected = self._spatial_index.hit_test(world_x, world_y, tolerance=1.5 / transform.scale)
        additive = bool(event.state & 0x0001)
        self.session.select(selected, additive=additive)
        if selected and not additive: self._begin_interaction("move", document.element(selected), world_x, world_y, None)
        else: self._render_interaction_layer()
        self.refresh_fields(force=True); self.refresh_element_debug()

    def _begin_interaction(self, kind: str, element, world_x: float, world_y: float, handle: str | None) -> None:
        self._interaction = InteractionState(kind=kind, element_id=element.id, handle=handle, start_pointer_x=world_x, start_pointer_y=world_y, start_x=element.x, start_y=element.y, start_width=element.width, start_height=element.height, start_rotation=element.rotation, current_x=element.x, current_y=element.y, current_width=element.width, current_height=element.height, current_rotation=element.rotation)
        self.session.begin_transaction("移动" if kind == "move" else "缩放")
        for item in self._static_element_items.get(element.id, []):
            self.canvas.itemconfigure(item, state="hidden")
        self.canvas.configure(cursor="fleur" if kind == "move" else "sizing"); self._schedule_interaction_frame()

    def canvas_drag(self, event: tk.Event) -> None:
        interaction, transform = self._interaction, self._view_transform
        if not interaction or not transform: return
        started = perf_counter(); world_x, world_y = transform.screenToWorld(event.x, event.y)
        if interaction.kind == "move":
            interaction.set_position(interaction.start_x + world_x - interaction.start_pointer_x, interaction.start_y + world_y - interaction.start_pointer_y); self._status_text.set("X: %.2f mm    Y: %.2f mm    移动预览" % (world_x, world_y))
        else:
            self._apply_corner_scale(interaction, world_x, world_y); self._status_text.set("宽度: %.2f mm    高度: %.2f mm    缩放预览" % (interaction.current_width, interaction.current_height))
        self.metrics.pointer_moves += 1; self.metrics.record_interaction(perf_counter() - started); self._schedule_interaction_frame(); self._schedule_inspector_refresh()

    def canvas_release(self, event: tk.Event) -> None:
        interaction = self._interaction
        if interaction:
            self._cancel_scheduled_interaction_frame(); commit_started = perf_counter()
            self._handle(lambda: self.session.commit_interaction(interaction)); self.metrics.record_commit(perf_counter() - commit_started); self._interaction = None
            self._update_static_element(interaction.element_id); self._spatial_index.rebuild(self.session.require_document().elements)
        self.canvas.configure(cursor="crosshair"); self.refresh_fields(force=True); self.refresh_element_debug(); self.refresh_log(); self._render_interaction_layer()
        if self._view_transform: self._set_cursor_status(self._view_transform.screenToWorld(event.x, event.y))

    def cancel_interaction(self, _event: tk.Event | None = None) -> None:
        if self._interaction:
            selected = self._interaction.element_id; self._cancel_scheduled_interaction_frame(); self.session.cancel_transaction(); self._interaction = None
            self._update_static_element(selected); self.canvas.configure(cursor="crosshair"); self.refresh_fields(force=True); self.refresh_element_debug(); self.refresh_log(); self._render_interaction_layer()

    def canvas_motion(self, event: tk.Event) -> None:
        transform = self._view_transform
        if not transform: return
        world_x, world_y = transform.screenToWorld(event.x, event.y)
        if not self._interaction and self._preview_grid_elements is None:
            self.metrics.spatial_queries += 1; hover = self._spatial_index.hit_test(world_x, world_y, tolerance=1.5 / transform.scale)
            if hover != self._hover_id:
                self._hover_id = hover; self.canvas.configure(cursor="hand2" if hover else "crosshair"); self._render_interaction_layer()
        self._set_cursor_status((world_x, world_y))

    def _apply_corner_scale(self, interaction: InteractionState, pointer_x: float, pointer_y: float) -> None:
        cx, cy, width, height = interaction.start_x, interaction.start_y, interaction.start_width, interaction.start_height
        left, top, right, bottom = cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2; handle = interaction.handle or "se"
        anchor_x = right if "w" in handle else left; anchor_y = bottom if "n" in handle else top; sign_x = -1 if "w" in handle else 1; sign_y = -1 if "n" in handle else 1
        raw_width, raw_height = abs(pointer_x - anchor_x), abs(pointer_y - anchor_y)
        if isinstance(self.session.require_document().element(interaction.element_id), CircleElement): raw_width = raw_height = max(raw_width, raw_height, 0.01)
        interaction.set_position(anchor_x + sign_x * raw_width / 2, anchor_y + sign_y * raw_height / 2); interaction.set_size(raw_width, raw_height)

    def _schedule_interaction_frame(self) -> None:
        if self._interaction_after is None: self._interaction_after = self.after_idle(self._paint_scheduled_interaction)
    def _cancel_scheduled_interaction_frame(self) -> None:
        if self._interaction_after:
            try: self.after_cancel(self._interaction_after)
            except tk.TclError: pass
        self._interaction_after = None
    def _paint_scheduled_interaction(self) -> None:
        self._interaction_after = None; self._render_interaction_layer()
    def _schedule_inspector_refresh(self) -> None:
        if self._inspector_after is None: self._inspector_after = self.after(self.INSPECTOR_INTERVAL_MS, self._flush_inspector_refresh)
    def _flush_inspector_refresh(self) -> None:
        self._inspector_after = None; self.refresh_fields(force=False)

    def pan_press(self, event: tk.Event) -> None: self._pan_drag = (event.x, event.y); self.canvas.configure(cursor="fleur")
    def pan_drag(self, event: tk.Event) -> None:
        if not self._pan_drag or not self._view_transform: return
        last_x, last_y = self._pan_drag; dx, dy = event.x - last_x, event.y - last_y; self._view_transform.pan_pixels(dx, dy); self._pan_drag = (event.x, event.y)
        self.canvas.move("static", dx, dy); self._render_interaction_layer(); self.refresh_rulers()
    def pan_release(self, _event: tk.Event) -> None: self._pan_drag = None; self.canvas.configure(cursor="crosshair")
    def wheel_zoom(self, event: tk.Event) -> None:
        if not self._view_transform: return
        self._view_transform.set_zoom_at(self._view_transform.zoom * (1.15 if event.delta > 0 else 1 / 1.15), event.x, event.y); self._zoom_text.set(self._view_transform.format_zoom()); self.refresh_canvas()
    def change_zoom(self, factor: float) -> None:
        if not self._view_transform: return
        self._view_transform.set_zoom_at(self._view_transform.zoom * factor, self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2); self._zoom_text.set(self._view_transform.format_zoom()); self.refresh_canvas()
    def reset_view(self) -> None:
        if self._view_transform: self._view_transform.reset(); self._zoom_text.set(self._view_transform.format_zoom()); self.refresh_canvas()
    def _canvas_resized(self, _event: tk.Event) -> None:
        if self._resize_after is None: self._resize_after = self.after(60, self._finish_canvas_resize)
    def _finish_canvas_resize(self) -> None:
        self._resize_after = None
        if self.session.document: self.refresh_canvas()

    def undo(self) -> None: self._handle(lambda: (self.session.undo(), self._after_document_change()))
    def redo(self) -> None: self._handle(lambda: (self.session.redo(), self._after_document_change()))
    def _shortcut_undo(self, _event: tk.Event): self.undo(); return "break"
    def _shortcut_redo(self, _event: tk.Event): self.redo(); return "break"

    # Grid controls remain deliberately intact; structure recognition now
    # chooses Grid, Radial, Along Curve, or the non-destructive free fallback.
    def _switch_mode(self) -> None:
        requested = PatternMode(self.pattern_mode_var.get())
        if requested is PatternMode.FREE:
            if self.session.has_parametric_model: self._handle(lambda: (self.session.deactivate_grid(), self._after_document_change()))
        elif self.session.pattern_mode is not PatternMode.GRID:
            # Parameterization is deliberately two-step: measure first, then
            # materialise only after the user presses the conversion action.
            self.pattern_mode_var.set(PatternMode.FREE.value); self.try_parametric()

    def try_parametric(self) -> None:
        def action() -> None:
            self.session.set_grid_analysis_tolerance(self.analysis_tolerance_var.get())
            analysis = self.session.analyze_families()
            self._pending_family_analysis = analysis
            grid = analysis.candidate("grid")
            radial = analysis.candidate("radial")
            curve = analysis.candidate("along_curve")
            fit = grid.fit
            self._pending_grid_fit = fit
            scores = (f"Grid：{grid.confidence * 100:.0f}%\n"
                      f"放射：{radial.confidence * 100:.0f}%\n"
                      f"沿曲线：{curve.confidence * 100:.0f}%")
            recommendation = analysis.recommended
            if recommendation is None:
                self.pattern_mode_var.set(PatternMode.FREE.value)
                debug = self.session.grid_analysis_debug
                details = (
                    f"候选={debug.candidate_count}；内点={debug.inlier_count}；网格={debug.rows}×{debug.columns}\n"
                    f"间距 U/V={debug.spacing_u:.3f} / {debug.spacing_v:.3f} mm；残差={debug.position_residual:.3f}\n"
                    f"方向/间距/位置={debug.direction_score:.3f} / {debug.spacing_score:.3f} / {debug.position_score:.3f}\n"
                    f"占用率={debug.occupancy_ratio * 100:.1f}%；内点率={debug.inlier_ratio * 100:.1f}%；分数={debug.grid_fit_score:.3f}\n"
                    f"原因：{debug.failure_reason or '未达到当前容差的网格拟合条件。'}"
                )
                self._parametric_text.set(f"{scores}\n\n未检测到可靠的整体生成结构。\n当前 Elements 仍可直接编辑，也可进入自由参数化。\n{details}")
                self.convert_family_button.configure(text="转换为推荐结构")
                self.session.log(f"结构分析未给出可靠推荐：{debug.failure_reason or '可使用自由参数化'}", "INFO")
                return
            labels = {"grid": "规则矩阵", "radial": "放射结构", "along_curve": "沿曲线结构"}
            label = labels[recommendation.family]
            self.convert_family_button.configure(text="转换为%s" % label)
            if recommendation.family != "grid":
                details = recommendation.parameters
                self._parametric_text.set("%s\n\n推荐：%s\n参数：%s\n点击“转换为%s”，或保留元素进入自由参数化。" % (scores, label, "；".join("%s=%s" % item for item in details.items()), label, label))
                self.session.log("结构候选：%s，score=%.3f。请确认转换。" % (label, recommendation.confidence))
                return
            gradient = "；尺寸渐变：%s" % fit.gradient.modifier.mode.value if fit.gradient else "；未拟合可靠尺寸渐变"
            holes = "；缺失单元：%d" % fit.missing_cell_count if fit.missing_cell_count else ""
            debug = fit.debug
            d = debug or self.session.grid_analysis_debug
            self._parametric_text.set(
                f"{scores}\n\n推荐：规则矩阵\n检测到二维格子：{fit.rows} 行 × {fit.columns} 列\n"
                f"单元原型：{fit.prototype_kind}；间距 U/V：{fit.spacing_x:.3f} × {fit.spacing_y:.3f} mm\n"
                f"Basis U：({fit.basis_u[0]:.3f}, {fit.basis_u[1]:.3f})；Basis V：({fit.basis_v[0]:.3f}, {fit.basis_v[1]:.3f})\n"
                f"旋转：{fit.rotation:.2f}°；占用率：{fit.occupancy * 100:.1f}%；内点率：{fit.inlier_ratio * 100:.1f}%\n"
                f"方向/间距/位置：{d.direction_score:.3f} / {d.spacing_score:.3f} / {d.position_score:.3f}\n"
                f"Fit Score：{fit.fit_score:.3f}{holes}{gradient}"
            )
            self.session.log(f"规则矩阵候选：{fit.rows} × {fit.columns}，原型={fit.prototype_kind}，score={fit.fit_score:.3f}，残差={fit.residual_error:.3f} mm，缺失单元={fit.missing_cell_count}。请确认转换。")
        self._handle(action)
        self.refresh_log()

    def convert_pending_grid(self) -> None:
        def action() -> None:
            analysis = self._pending_family_analysis or self.session.analyze_families()
            recommendation = analysis.recommended
            if recommendation is None or recommendation.model is None:
                self.pattern_mode_var.set(PatternMode.FREE.value)
                self._parametric_text.set("未检测到可靠整体结构；当前 Elements 仍可直接编辑。可点击“进入自由参数化”。")
                self.session.log("转换取消：当前图案没有可靠结构候选。", "INFO")
                return
            if recommendation.family == "grid":
                fit = recommendation.fit
                self.session.activate_grid(recommendation.model); self.pattern_mode_var.set(PatternMode.GRID.value); self._load_grid_controls(recommendation.model)
                self._parametric_text.set("已转换为参数化矩阵：%d 行 × %d 列；单元原型：%s；Fit Score：%.3f" % (fit.rows, fit.columns, fit.prototype_kind, fit.fit_score))
                self.session.log("已转换为规则矩阵：%d 行 × %d 列，原型=%s，score=%.3f。" % (fit.rows, fit.columns, fit.prototype_kind, fit.fit_score))
            elif recommendation.family == "radial":
                self.session.activate_radial(recommendation.model); self.pattern_mode_var.set(PatternMode.RADIAL.value)
                self._parametric_text.set("已转换为放射参数化：数量=%d；Fit Score：%.3f" % (recommendation.parameters["count"], recommendation.confidence))
                self.session.log("已转换为放射结构，score=%.3f。" % recommendation.confidence)
            else:
                self.session.activate_along_curve(recommendation.model); self.pattern_mode_var.set(PatternMode.ALONG_CURVE.value)
                self._parametric_text.set("已转换为沿曲线参数化：数量=%d；Fit Score：%.3f" % (recommendation.parameters["count"], recommendation.confidence))
                self.session.log("已转换为沿曲线结构，score=%.3f。" % recommendation.confidence)
            self._after_document_change()
        self._handle(action)

    def enter_free_parametric(self) -> None:
        def action() -> None:
            analysis = self._pending_family_analysis or self.session.analyze_families()
            self.session.activate_free_parametric(analysis.fallback.model)
            self.pattern_mode_var.set(PatternMode.FREE_PARAMETRIC.value)
            self._parametric_text.set("已进入自由参数化：保留原始元素，可继续使用共享尺寸场、旋转场、掩膜和局部覆盖。")
            self.session.log("已进入自由参数化模式。")
            self._after_document_change()
        self._handle(action)

    def _on_family_size_selected(self, _event=None) -> None:
        """Translate a Chinese display label back to the stable schema id."""
        selected = self.family_size_display_var.get()
        for item in SizeFieldMode:
            if field_label(item.value) == selected:
                self.family_size_mode_var.set(item.value)
                break
        self._family_description_var.set(field_description(self.family_size_mode_var.get()))
        self._build_family_field_panel()
        self._schedule_family_preview()

    def _on_family_rotation_selected(self, _event=None) -> None:
        selected = self.family_rotation_display_var.get()
        for item in RotationFieldMode:
            if rotation_label(item.value) == selected:
                self.family_rotation_mode_var.set(item.value)
                break
        self._family_rotation_description_var.set(rotation_description(self.family_rotation_mode_var.get()))
        self._build_family_rotation_panel()
        self._schedule_family_preview()

    def _add_family_slider(self, parent, label: str, variable: tk.StringVar, minimum: float,
                           maximum: float, resolution: float = 0.1, unit: str = "") -> None:
        row = ttk.Frame(parent); row.pack(fill="x", pady=1)
        ttk.Label(row, text=label, width=11).pack(side="left")
        scale = tk.Scale(row, from_=minimum, to=maximum, resolution=resolution, orient="horizontal",
                         showvalue=False, variable=variable, highlightthickness=0, length=125,
                         command=lambda _value: self._schedule_family_preview())
        scale.pack(side="left", fill="x", expand=True)
        entry = ttk.Entry(row, textvariable=variable, width=8)
        entry.pack(side="right", padx=(4, 0))
        if unit:
            ttk.Label(row, text=unit, width=3).pack(side="right")
        scale.bind("<ButtonRelease-1>", lambda _event: self._commit_family_preview())
        entry.bind("<KeyRelease>", lambda _event: self._schedule_family_preview())
        entry.bind("<Return>", lambda _event: self._commit_family_preview())
        entry.bind("<FocusOut>", lambda _event: self._commit_family_preview())

    def _add_family_checkbox(self, parent, label: str, variable: tk.BooleanVar) -> None:
        ttk.Checkbutton(parent, text=label, variable=variable,
                        command=self._commit_family_preview).pack(anchor="w", pady=2)

    def _build_family_field_panel(self) -> None:
        if self._family_dynamic_frame is None:
            return
        for child in self._family_dynamic_frame.winfo_children():
            child.destroy()
        mode = self.family_size_mode_var.get()
        self._family_description_var.set(field_description(mode))
        self._add_family_slider(self._family_dynamic_frame, "最小缩放", self.family_min_scale_var, 0.01, 3.0, 0.01)
        self._add_family_slider(self._family_dynamic_frame, "最大缩放", self.family_max_scale_var, 0.01, 3.0, 0.01)
        self._add_family_slider(self._family_dynamic_frame, "作用强度", self.family_strength_var, 0.0, 1.0, 0.01)
        if mode in {SizeFieldMode.RADIAL.value, SizeFieldMode.ATTRACTOR.value, SizeFieldMode.RING.value,
                    SizeFieldMode.CHECKER.value, SizeFieldMode.SPIRAL.value}:
            self._add_family_slider(self._family_dynamic_frame, "中心 X", self.family_center_x_var, -500.0, 500.0, 0.1, "mm")
            self._add_family_slider(self._family_dynamic_frame, "中心 Y", self.family_center_y_var, -500.0, 500.0, 0.1, "mm")
        if mode in {SizeFieldMode.RADIAL.value, SizeFieldMode.ATTRACTOR.value, SizeFieldMode.RING.value}:
            self._add_family_slider(self._family_dynamic_frame, "半径", self.family_radius_var, 0.1, 1000.0, 0.1, "mm")
            self._add_family_slider(self._family_dynamic_frame, "衰减", self.family_falloff_var, 0.1, 5.0, 0.05)
        if mode == SizeFieldMode.RING.value:
            self._add_family_slider(self._family_dynamic_frame, "环宽", self.family_ring_width_var, 0.1, 500.0, 0.1, "mm")
            self._add_family_checkbox(self._family_dynamic_frame, "反转", self.family_ring_invert_var)
        elif mode == SizeFieldMode.WAVE.value:
            self._add_family_slider(self._family_dynamic_frame, "方向角度", self.family_field_angle_var, -180.0, 180.0, 1.0, "°")
            self._add_family_slider(self._family_dynamic_frame, "波长", self.family_wavelength_var, 1.0, 1000.0, 0.1, "mm")
            self._add_family_slider(self._family_dynamic_frame, "相位（弧度）", self.family_phase_var, -6.283, 6.283, 0.01)
            self._add_family_slider(self._family_dynamic_frame, "振幅", self.family_amplitude_var, 0.0, 1.0, 0.01)
            self._add_family_slider(self._family_dynamic_frame, "偏移", self.family_offset_var, 0.0, 1.0, 0.01)
            self._add_family_checkbox(self._family_dynamic_frame, "反转", self.family_ring_invert_var)
        elif mode == SizeFieldMode.STRIPE.value:
            self._add_family_slider(self._family_dynamic_frame, "方向角度", self.family_field_angle_var, -180.0, 180.0, 1.0, "°")
            self._add_family_slider(self._family_dynamic_frame, "周期", self.family_wavelength_var, 1.0, 1000.0, 0.1, "mm")
            self._add_family_slider(self._family_dynamic_frame, "相位（周期）", self.family_phase_var, 0.0, 1.0, 0.01)
            self._add_family_slider(self._family_dynamic_frame, "占空比", self.family_duty_cycle_var, 0.0, 1.0, 0.01)
            self._add_family_slider(self._family_dynamic_frame, "边缘平滑", self.family_smoothness_var, 0.0, 0.5, 0.01)
            self._add_family_checkbox(self._family_dynamic_frame, "反转", self.family_ring_invert_var)
        elif mode == SizeFieldMode.CHECKER.value:
            self._add_family_slider(self._family_dynamic_frame, "旋转", self.family_field_angle_var, -180.0, 180.0, 1.0, "°")
            self._add_family_slider(self._family_dynamic_frame, "格宽", self.family_cell_width_var, 1.0, 500.0, 0.1, "mm")
            self._add_family_slider(self._family_dynamic_frame, "格高", self.family_cell_height_var, 1.0, 500.0, 0.1, "mm")
            self._add_family_checkbox(self._family_dynamic_frame, "反转", self.family_ring_invert_var)
        elif mode == SizeFieldMode.SPIRAL.value:
            self._add_family_slider(self._family_dynamic_frame, "圈数", self.family_turns_var, 0.0, 20.0, 0.1)
            self._add_family_slider(self._family_dynamic_frame, "相位（周期）", self.family_phase_var, 0.0, 1.0, 0.01)
            direction_row = ttk.Frame(self._family_dynamic_frame); direction_row.pack(fill="x", pady=1)
            ttk.Label(direction_row, text="方向", width=11).pack(side="left")
            direction_combo = ttk.Combobox(direction_row, state="readonly", width=10, textvariable=self.family_direction_var,
                                           values=("1", "-1"))
            direction_combo.pack(side="left")
            direction_combo.bind("<<ComboboxSelected>>", lambda _event: self._schedule_family_preview())
            self._add_family_slider(self._family_dynamic_frame, "衰减", self.family_falloff_var, 0.1, 5.0, 0.05)
            self._add_family_checkbox(self._family_dynamic_frame, "反转", self.family_ring_invert_var)

        self._build_family_rotation_panel()

    def _build_family_rotation_panel(self) -> None:
        if self._family_rotation_frame is None:
            return
        for child in self._family_rotation_frame.winfo_children():
            child.destroy()
        mode = self.family_rotation_mode_var.get()
        self._family_rotation_description_var.set(rotation_description(mode))
        self._add_family_slider(self._family_rotation_frame, "旋转角度", self.family_rotation_var, -180.0, 180.0, 1.0, "°")
        if mode != RotationFieldMode.CONSTANT.value:
            self._add_family_slider(self._family_rotation_frame, "中心 X", self.family_center_x_var, -500.0, 500.0, 0.1, "mm")
            self._add_family_slider(self._family_rotation_frame, "中心 Y", self.family_center_y_var, -500.0, 500.0, 0.1, "mm")

    def _schedule_family_preview(self) -> None:
        if not self._family_controls_ready or self._family_preview_after is not None:
            return
        self._family_preview_after = self.after(self.PARAMETER_PREVIEW_INTERVAL_MS, self._run_family_preview)

    def _run_family_preview(self) -> None:
        self._family_preview_after = None
        try:
            document = self.session.document
            if not document:
                return
            size, rotation = self._family_modifiers_from_controls()
            model = self.session.parametric_model
            if model is not None and hasattr(model, "size_field") and self.session.pattern_mode is not PatternMode.GRID:
                candidate = deepcopy(model)
                candidate.size_field = size; candidate.rotation_field = rotation
                preview = candidate.generate()
            else:
                current = SharedModifierStack.from_document(document)
                source = current.source_snapshot() if current and current.source_elements else document.elements
                if model is not None and self.session.pattern_mode is PatternMode.GRID:
                    source = model.generate()
                stack = current or SharedModifierStack(source_kind="preview")
                stack.size_field = size; stack.rotation_field = rotation
                preview = stack.apply(source)
            self._render_static_layer(elements=preview, update_index=False); self._render_interaction_layer()
        except Exception as error:
            self._log_exception("共享参数场预览", error)

    def _commit_family_preview(self) -> None:
        if self._family_preview_after:
            try: self.after_cancel(self._family_preview_after)
            except tk.TclError: pass
            self._family_preview_after = None
        if self._family_controls_ready:
            self.apply_family_fields()

    def reset_family_fields(self) -> None:
        """Restore semantic defaults and commit as one normal Undo transaction."""
        size = SizeFieldModifier(mode=SizeFieldMode(self.family_size_mode_var.get()))
        rotation = RotationFieldModifier(mode=RotationFieldMode(self.family_rotation_mode_var.get()))
        self.family_min_scale_var.set(str(size.min_scale)); self.family_max_scale_var.set(str(size.max_scale))
        self.family_strength_var.set(str(size.strength)); self.family_center_x_var.set(str(size.center_x)); self.family_center_y_var.set(str(size.center_y))
        self.family_radius_var.set(str(size.radius)); self.family_ring_width_var.set(str(size.ring_width)); self.family_ring_invert_var.set(size.invert)
        self.family_field_angle_var.set(str(size.field_angle)); self.family_wavelength_var.set(str(size.wavelength)); self.family_phase_var.set(str(size.phase))
        self.family_amplitude_var.set(str(size.amplitude)); self.family_offset_var.set(str(size.offset)); self.family_falloff_var.set(str(size.falloff))
        self.family_duty_cycle_var.set(str(size.duty_cycle)); self.family_smoothness_var.set(str(size.smoothness)); self.family_cell_width_var.set(str(size.cell_width)); self.family_cell_height_var.set(str(size.cell_height))
        self.family_turns_var.set(str(size.turns)); self.family_direction_var.set(str(size.direction)); self.family_rotation_var.set(str(rotation.angle))
        self._build_family_field_panel()
        self.apply_family_fields()

    def _load_family_field_controls(self, model) -> None:
        """Reflect common modifier values without giving Canvas another state."""
        if not hasattr(model, "size_field"):
            return
        size, rotation = model.size_field, model.rotation_field
        self.family_size_mode_var.set(size.mode.value); self.family_rotation_mode_var.set(rotation.mode.value)
        self.family_size_display_var.set(field_label(size.mode.value)); self.family_rotation_display_var.set(rotation_label(rotation.mode.value))
        self._family_description_var.set(field_description(size.mode.value)); self._family_rotation_description_var.set(rotation_description(rotation.mode.value))
        self.family_min_scale_var.set(str(size.min_scale)); self.family_max_scale_var.set(str(size.max_scale))
        self.family_strength_var.set(str(size.strength))
        self.family_center_x_var.set(str(size.center_x)); self.family_center_y_var.set(str(size.center_y)); self.family_radius_var.set(str(size.radius))
        self.family_ring_width_var.set(str(size.ring_width)); self.family_ring_invert_var.set(bool(size.invert))
        self.family_field_angle_var.set(str(size.field_angle)); self.family_wavelength_var.set(str(size.wavelength)); self.family_phase_var.set(str(size.phase))
        self.family_amplitude_var.set(str(size.amplitude)); self.family_offset_var.set(str(size.offset)); self.family_falloff_var.set(str(size.falloff))
        self.family_duty_cycle_var.set(str(size.duty_cycle)); self.family_smoothness_var.set(str(size.smoothness))
        self.family_cell_width_var.set(str(size.cell_width)); self.family_cell_height_var.set(str(size.cell_height))
        self.family_turns_var.set(str(size.turns)); self.family_direction_var.set(str(size.direction))
        self.family_rotation_var.set(str(rotation.angle))
        self._build_family_field_panel()

    def _family_modifiers_from_controls(self) -> tuple[SizeFieldModifier, RotationFieldModifier]:
        size = SizeFieldModifier(
            mode=SizeFieldMode(self.family_size_mode_var.get()),
            min_scale=parse_float_ui_value(self.family_min_scale_var.get(), "最小缩放", minimum=0.0),
            max_scale=parse_float_ui_value(self.family_max_scale_var.get(), "最大缩放", minimum=0.0),
            center_x=parse_float_ui_value(self.family_center_x_var.get(), "控制点 X"),
            center_y=parse_float_ui_value(self.family_center_y_var.get(), "控制点 Y"),
            radius=max(.01, parse_float_ui_value(self.family_radius_var.get(), "影响半径", minimum=0.0)),
            strength=min(1.0, max(0.0, parse_float_ui_value(self.family_strength_var.get(), "作用强度", minimum=0.0))),
            ring_width=max(.01, parse_float_ui_value(self.family_ring_width_var.get(), "环宽", minimum=0.0)),
            invert=bool(self.family_ring_invert_var.get()),
            field_angle=parse_float_ui_value(self.family_field_angle_var.get(), "场角度"),
            wavelength=max(.01, parse_float_ui_value(self.family_wavelength_var.get(), "波长", minimum=0.0)),
            phase=parse_float_ui_value(self.family_phase_var.get(), "相位"),
            amplitude=min(1.0, max(0.0, parse_float_ui_value(self.family_amplitude_var.get(), "振幅", minimum=0.0))),
            offset=min(1.0, max(0.0, parse_float_ui_value(self.family_offset_var.get(), "偏移", minimum=0.0))),
            falloff=max(.01, parse_float_ui_value(self.family_falloff_var.get(), "衰减", minimum=0.0)),
            duty_cycle=min(1.0, max(0.0, parse_float_ui_value(self.family_duty_cycle_var.get(), "占空比", minimum=0.0))),
            smoothness=min(.5, max(0.0, parse_float_ui_value(self.family_smoothness_var.get(), "平滑度", minimum=0.0))),
            cell_width=max(.01, parse_float_ui_value(self.family_cell_width_var.get(), "格宽", minimum=0.0)),
            cell_height=max(.01, parse_float_ui_value(self.family_cell_height_var.get(), "格高", minimum=0.0)),
            turns=max(0.0, parse_float_ui_value(self.family_turns_var.get(), "圈数", minimum=0.0)),
            direction=1 if int(parse_float_ui_value(self.family_direction_var.get(), "方向")) >= 0 else -1,
        )
        rotation = RotationFieldModifier(
            mode=RotationFieldMode(self.family_rotation_mode_var.get()),
            angle=parse_float_ui_value(self.family_rotation_var.get(), "固定角度"),
            center_x=size.center_x, center_y=size.center_y, strength=1.0,
        )
        return size, rotation

    def apply_family_fields(self) -> None:
        """Commit shared Size/Rotation fields for every structure source.

        Grid is a placement source, not a reason to disable the common effect
        layer.  The old implementation rejected Grid here and made the panel
        appear to work while silently doing nothing.
        """
        def action() -> None:
            model = self.session.parametric_model
            size, rotation = self._family_modifiers_from_controls()
            if self.session.pattern_mode is PatternMode.GRID:
                # Keep Grid's own size gradient intact; this stack is an
                # additive, source-independent effects layer.
                stack = SharedModifierStack.from_document(self.session.require_document()) or SharedModifierStack(source_kind="grid")
                stack.size_field = size; stack.rotation_field = rotation
                self.session.update_shared_modifiers(stack)
            elif model is not None and hasattr(model, "size_field"):
                model.size_field = size; model.rotation_field = rotation
                self.session._mutate("更新共享参数场", self.session._rebuild_parametric_document)
            else:
                stack = SharedModifierStack.from_document(self.session.require_document()) or SharedModifierStack()
                stack.size_field = size; stack.rotation_field = rotation
                self.session.update_shared_modifiers(stack)
            self._after_document_change()
        self._handle(action)
    def _load_grid_controls(self, model: GridParametricModel) -> None:
        values = model.to_dict(); gradient = values["size_gradient"]; mask = values["mask"]
        for key in ("rows", "columns", "spacing_x", "spacing_y", "element_width", "element_height", "rotation", "offset_x", "offset_y"): self.grid_vars[key].set(str(values[key]))
        for key, value in zip(("basis_u_x", "basis_u_y"), model.basis_u): self.grid_vars[key].set(str(value))
        for key, value in zip(("basis_v_x", "basis_v_y"), model.basis_v): self.grid_vars[key].set(str(value))
        for key in ("min_size", "max_size", "center_x", "center_y", "radius_x", "radius_y", "falloff", "strength"): self.grid_vars[key].set(str(gradient[key]))
        for key in ("center_x", "center_y", "width", "height", "radius"):
            self.grid_vars["mask_" + key].set(str(mask[key]))
        self.lock_aspect_var.set(bool(values["lock_aspect"])); self.gradient_mode_var.set(gradient["mode"])
        self.mask_enabled_var.set(bool(mask["enabled"])); self.mask_invert_var.set(bool(mask["invert"])); self.mask_mode_var.set(mask["mode"])
    def _grid_from_controls(self) -> GridParametricModel:
        current = self.session.grid_model or GridParametricModel()
        try: gradient_mode = SizeGradientMode(self.gradient_mode_var.get())
        except ValueError: gradient_mode = SizeGradientMode.NONE
        try: mask_mode = MaskMode(self.mask_mode_var.get())
        except ValueError: mask_mode = MaskMode.NONE
        value = lambda key: parse_float_ui_value(self.grid_vars[key].get(), key)
        mask = MaskModifier(mode=mask_mode, enabled=self.mask_enabled_var.get(), invert=self.mask_invert_var.get(), center_x=value("mask_center_x"), center_y=value("mask_center_y"), width=value("mask_width"), height=value("mask_height"), radius=max(0.0, value("mask_radius")), path_points=list(current.mask.path_points))
        requested_u = (value("basis_u_x"), value("basis_u_y"))
        requested_v = (value("basis_v_x"), value("basis_v_y"))
        basis_was_edited = any(abs(left - right) > 1e-6 for left, right in ((requested_u[0], current.basis_u[0]), (requested_u[1], current.basis_u[1]), (requested_v[0], current.basis_v[0]), (requested_v[1], current.basis_v[1])))
        model = GridParametricModel(rows=parse_int_ui_value(self.grid_vars["rows"].get(), "行数"), columns=parse_int_ui_value(self.grid_vars["columns"].get(), "列数"), spacing_x=value("spacing_x"), spacing_y=value("spacing_y"), element_width=max(.01, value("element_width")), element_height=max(.01, value("element_height")), rotation=value("rotation"), offset_x=value("offset_x"), offset_y=value("offset_y"), lock_aspect=self.lock_aspect_var.get(), basis_u_vector=requested_u, basis_v_vector=requested_v, prototype=deepcopy(current.prototype), size_gradient=SizeGradientModifier(mode=gradient_mode, min_size=max(.01, value("min_size")), max_size=max(.01, value("max_size")), center_x=value("center_x"), center_y=value("center_y"), radius_x=max(.01, value("radius_x")), radius_y=max(.01, value("radius_y")), falloff=max(0.0, value("falloff")), strength=value("strength")), mask=mask, local_overrides=deepcopy(current.local_overrides)).normalized()
        # The rotation control rotates both bases as a unit.  Editing a Basis
        # component takes priority for that event, so a designer can build a
        # genuinely skewed lattice without the UI silently orthogonalising it.
        if not basis_was_edited:
            model.set_rotation(value("rotation"))
        return model
    def _schedule_grid_preview(self) -> None:
        if self.session.pattern_mode is PatternMode.GRID and self._parameter_after is None: self._parameter_after = self.after(self.PARAMETER_PREVIEW_INTERVAL_MS, self._run_grid_preview)
    def _run_grid_preview(self) -> None:
        self._parameter_after = None
        try:
            self._preview_grid_elements = self.session.preview_grid(self._grid_from_controls()); self._render_static_layer(elements=self._preview_grid_elements, update_index=False); self._render_interaction_layer()
        except Exception as error:
            self._log_exception("Grid 交互预览", error)
            self._perf_text.set("Grid 参数预览失败，详细 traceback 已写入 diagnostics/pattern_lab-ui.log")
    def _commit_grid_from_controls(self) -> None:
        if self.session.pattern_mode is not PatternMode.GRID: return
        if self._parameter_after:
            try: self.after_cancel(self._parameter_after)
            except tk.TclError: pass
            self._parameter_after = None
        self._handle(lambda: (self.session.update_grid(self._grid_from_controls()), self._after_document_change()))

    def bake_to_free_elements(self) -> None:
        self._handle(lambda: (self.session.bake_to_free_elements(), self._after_document_change()))

    def apply_position(self) -> None:
        def action() -> None:
            element = self.session.require_document().element(self.session.selected_id or "")
            x = parse_float_ui_value(self.x_var.get(), "X"); y = parse_float_ui_value(self.y_var.get(), "Y")
            self.session.move_selected(x - element.x, y - element.y); self._after_document_change()
        self._handle(action)
    def apply_size(self) -> None:
        self._handle(lambda: (self.session.resize_selected(parse_float_ui_value(self.width_var.get(), "宽度", minimum=0.01), parse_float_ui_value(self.height_var.get(), "高度", minimum=0.01)), self._after_document_change()))
    def apply_rotation(self) -> None:
        self._handle(lambda: (self.session.rotate_selected(parse_float_ui_value(self.rotation_var.get(), "旋转")), self._after_document_change()))
    def duplicate(self) -> None: self._handle(lambda: (self.session.duplicate_selected(), self._after_document_change()))
    def delete(self) -> None: self._handle(lambda: (self.session.delete_selected(), self._after_document_change()))
    def union_selected(self) -> None: self._handle(lambda: (self.session.union_selected(), self._after_document_change()))
    def difference_selected(self) -> None: self._handle(lambda: (self.session.difference_selected(), self._after_document_change()))
    def export_svg(self) -> None:
        path = filedialog.asksaveasfilename(parent=self, title="导出 SVG", defaultextension=".svg", filetypes=[("SVG", "*.svg")])
        if path: self._handle(lambda: (self.session.export_svg(path), self.refresh_log()))
    def save_document(self) -> None:
        path = filedialog.asksaveasfilename(parent=self, title="保存 PatternDocument", defaultextension=".pattern.json", filetypes=[("PatternDocument", "*.json")])
        if path: self._handle(lambda: (self.session.save_document(path), self.refresh_log()))
    def open_document(self) -> None:
        path = filedialog.askopenfilename(parent=self, title="打开 PatternDocument", filetypes=[("PatternDocument", "*.json")])
        if path: self._handle(lambda: (self.session.load_document(path), self._after_document_change()))

    def _after_document_change(self) -> None:
        self._preview_grid_elements = None; self.pattern_mode_var.set(self.session.pattern_mode.value)
        grid_enabled = self.session.pattern_mode is PatternMode.GRID
        for widget in self._grid_control_widgets:
            try:
                widget.configure(state="normal" if grid_enabled else "disabled")
            except tk.TclError:
                pass
        if self.session.grid_model: self._load_grid_controls(self.session.grid_model)
        elif self.session.parametric_model is not None: self._load_family_field_controls(self.session.parametric_model)
        self.refresh_all()
    def refresh_all(self) -> None: self.refresh_fields(force=True); self.refresh_element_debug(); self.refresh_log(); self._refresh_modifier_stack(); self.refresh_canvas()
    def refresh_fields(self, *, force: bool = False) -> None:
        self.metrics.inspector_refreshes += 1; document, selected = self.session.document, self.session.selected_id
        if not document or not selected:
            self.selection.set("未选择")
            for variable in (self.x_var, self.y_var, self.width_var, self.height_var, self.rotation_var): variable.set("")
            return
        element = document.element(selected)
        if self._interaction and self._interaction.element_id == selected: x, y, width, height = self._interaction.current_x, self._interaction.current_y, self._interaction.current_width, self._interaction.current_height
        else: x, y, width, height = element.x, element.y, element.width, element.height
        prefix = "%d 个元素；主选：" % len(self.session.selected_ids) if len(self.session.selected_ids) > 1 else ""
        self.selection.set("%s%s  (%s)" % (prefix, element.id, element.type)); self.x_var.set("%.4g" % x); self.y_var.set("%.4g" % y); self.width_var.set("%.4g" % width); self.height_var.set("%.4g" % height); self.rotation_var.set("%.4g" % element.rotation)
    def refresh_log(self) -> None:
        self.log.configure(state="normal"); self.log.delete("1.0", "end"); self.log.insert("end", "\n".join("[%s] %s: %s" % (entry.timestamp, entry.level, entry.message) for entry in self.session.logs)); self.log.see("end"); self.log.configure(state="disabled")

    def refresh_element_debug(self) -> None:
        if not self.session.document:
            self._element_debug_text.set("导入后显示 Element Debug。")
            return
        summary = self.session.debug_summary(); selected = self.session.debug_element()
        header = "Detected Element Count：%d\nRenderable Element Count：%d\nVisible Filled Element Count：%d\nInvalid Geometry Count：%d\nUnknown Primitive Count：%d" % (
            summary.detected_element_count, summary.renderable_element_count, summary.visible_filled_element_count,
            summary.invalid_geometry_count, summary.unknown_primitive_count,
        )
        if selected is None:
            self._element_debug_text.set(header + "\n当前未选择 Element。")
            return
        radius = "--" if selected.radius is None else "%.3f" % selected.radius
        confidence = "--" if selected.confidence is None else "%.3f" % selected.confidence
        self._element_debug_text.set(header + "\n\n选中：%s\ntype=%s  x=%.3f  y=%.3f\nwidth=%.3f  height=%.3f  radius=%s\nfill=%s  stroke=%s  visible=%s\nconfidence=%s  source=%s" % (
            selected.id, selected.type, selected.x, selected.y, selected.width, selected.height, radius,
            selected.fill, selected.stroke, selected.visible, confidence, selected.source,
        ))

    def refresh_canvas(self) -> None:
        document = self.session.document
        if not document:
            self.canvas.delete("all"); self.metrics.full_canvas_rebuilds += 1; self.canvas.create_text(20, 20, anchor="nw", text="导入 PNG/JPG 或加载固定测试图。", fill="#56616f"); return
        width, height = max(self.canvas.winfo_width(), 640), max(self.canvas.winfo_height(), 480)
        if self._view_transform is None: self._view_transform = CanvasViewTransform(document.canvas.width, document.canvas.height, width, height, world_origin_x=document.canvas.origin_x, world_origin_y=document.canvas.origin_y)
        else: self._view_transform.resize_viewport(width, height)
        self._zoom_text.set(self._view_transform.format_zoom()); self._render_static_layer(); self._render_interaction_layer(); self.refresh_rulers()

    # Never called from B1-Motion: whole geometry is static during a drag.
    def _render_static_layer(self, *, elements=None, update_index: bool = True) -> None:
        document, transform = self.session.document, self._view_transform
        if not document or not transform: return
        started = perf_counter(); self.canvas.delete("static"); self._static_element_items.clear(); mode = ViewMode(self.mode.get())
        if self.hide_reference.get() and mode is ViewMode.REFERENCE: mode = ViewMode.VECTOR; self.mode.set(mode.value)
        if not self.hide_reference.get() and mode in (ViewMode.REFERENCE, ViewMode.OVERLAY):
            self._reference_photo = ImageTk.PhotoImage(self._reference_image(document.reference.source_path, int(document.canvas.width * transform.scale), int(document.canvas.height * transform.scale)))
            self.canvas.create_image(transform.origin_x, transform.origin_y, anchor="nw", image=self._reference_photo, tags=("static", "reference"))
        if mode is not ViewMode.REFERENCE:
            for element in list(elements if elements is not None else document.elements):
                items = self._create_static_element(element)
                if items: self._static_element_items[element.id] = items
        if update_index: self._spatial_index.rebuild(document.elements)
        self.metrics.record_render(perf_counter() - started, static=True)
    def _create_static_element(self, element) -> list[int]:
        if not element.visible or not self._view_transform: return []
        x0, y0, x1, y1 = self._screen_bounds(element.x, element.y, element.width, element.height); tags = ("static", "geometry", "element:" + element.id)
        if isinstance(element, (CircleElement, EllipseElement)):
            return [self.canvas.create_oval(x0, y0, x1, y1, fill="#000000", outline="", tags=tags)]
        if isinstance(element, RectElement):
            return [self.canvas.create_rectangle(x0, y0, x1, y1, fill="#000000", outline="", tags=tags)]
        if isinstance(element, FilledRegionElement):
            return self._draw_filled_region(element, fill=str(element.style.get("fill") or "#000000"), outline="", tags=tags)
        if isinstance(element, PathElement) and self._is_filled_path(element):
            # The semantic pipeline can preserve a closed cubic path when its
            # roundness is below primitive-recovery confidence.  It is still
            # real black material, never an empty bounds rectangle.
            return self._draw_filled_region(element, fill=str(element.style.get("fill") or "#000000"), outline="", tags=tags)
        return [self.canvas.create_rectangle(x0, y0, x1, y1, outline="#6d7d8d", width=1, tags=tags)]
    def _update_static_element(self, element_id: str) -> None:
        document = self.session.document
        if not document: return
        items = self._static_element_items.get(element_id, [])
        try: element = document.element(element_id)
        except KeyError:
            for item in items: self.canvas.delete(item)
            self._static_element_items.pop(element_id, None); return
        # Filled paths may contain multiple subpaths and cannot be updated with
        # a single Canvas coordinate call.  Recreate only this element, never
        # the complete static layer.
        for item in items: self.canvas.delete(item)
        self._static_element_items.pop(element_id, None)
        if self.mode.get() != ViewMode.REFERENCE.value:
            created = self._create_static_element(element)
            if created: self._static_element_items[element_id] = created
    def _render_interaction_layer(self) -> None:
        if not self._view_transform: return
        started = perf_counter(); self.canvas.delete("interaction"); interaction, document = self._interaction, self.session.document
        if interaction and document:
            base = document.element(interaction.element_id); self._draw_geometry(interaction.current_x, interaction.current_y, interaction.current_width, interaction.current_height, base, fill="#161b22", outline="#1577c0")
            self._draw_bounds(interaction.current_x, interaction.current_y, interaction.current_width, interaction.current_height, "#1577c0", (5, 2), 2)
            for x, y in self._handle_positions_for(interaction.current_x, interaction.current_y, interaction.current_width, interaction.current_height).values(): self.canvas.create_rectangle(x - 5, y - 5, x + 5, y + 5, fill="white", outline="#1577c0", width=2, tags="interaction")
            interaction.dirty = False; self.metrics.interaction_renders += 1
        elif document and self.session.selected_id:
            for selected_id in self.session.selected_ids or [self.session.selected_id]:
                element = document.element(selected_id); color = "#1577c0" if selected_id == self.session.selected_id else "#5c8fb7"
                self._draw_bounds(element.x, element.y, element.width, element.height, color, (5, 2), 2)
            element = document.element(self.session.selected_id)
            for x, y in self._handle_positions_for(element.x, element.y, element.width, element.height).values(): self.canvas.create_rectangle(x - 5, y - 5, x + 5, y + 5, fill="white", outline="#1577c0", width=2, tags="interaction")
        if document and self._hover_id and self._hover_id != self.session.selected_id:
            element = document.element(self._hover_id); self._draw_bounds(element.x, element.y, element.width, element.height, "#6d7d8d", (3, 2), 1)
        self.metrics.record_frame(perf_counter() - started)
    def _draw_geometry(self, x: float, y: float, width: float, height: float, source, *, fill: str, outline: str) -> None:
        x0, y0, x1, y1 = self._screen_bounds(x, y, width, height)
        if isinstance(source, (CircleElement, EllipseElement)): self.canvas.create_oval(x0, y0, x1, y1, fill=fill, outline=outline, width=1, tags="interaction")
        elif isinstance(source, RectElement): self.canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline, width=1, tags="interaction")
        elif isinstance(source, FilledRegionElement) or (isinstance(source, PathElement) and self._is_filled_path(source)): self._draw_filled_region(source, fill=fill, outline=outline, tags="interaction", x=x, y=y, width=width, height=height)
        else: self.canvas.create_rectangle(x0, y0, x1, y1, outline=outline, width=2, tags="interaction")

    @staticmethod
    def _is_filled_path(element: PathElement) -> bool:
        fill = str(element.style.get("fill", "")).strip().lower()
        return bool(element.path_data.strip()) and fill not in {"", "none", "transparent"} and "z" in element.path_data.lower()

    def _draw_filled_region(self, element: FilledRegionElement, *, fill: str, outline: str, tags, x: float | None = None, y: float | None = None, width: float | None = None, height: float | None = None) -> list[int]:
        """Draw actual closed material polygons, never their bounding boxes."""
        transform = self._view_transform
        if transform is None:
            return []
        result: list[int] = []
        polygons = filled_region_polygons(element, x=x, y=y, width=width, height=height)
        even_odd = str(element.style.get("fill-rule", "")).lower() == "evenodd"
        for index, polygon in enumerate(polygons):
            if len(polygon) < 3:
                continue
            points = [coordinate for point in polygon for coordinate in transform.worldToScreen(*point)]
            # Compound difference paths use an even-odd fill.  Tk has no
            # native fill-rule; paint the later subpaths in canvas white.
            region_fill = "white" if even_odd and index > 0 else fill
            result.append(self.canvas.create_polygon(*points, fill=region_fill, outline=outline if index == 0 else "", width=1 if outline else 0, tags=tags, smooth=False))
        return result
    def _screen_bounds(self, x: float, y: float, width: float, height: float) -> tuple[float, float, float, float]:
        transform = self._view_transform; x0, y0 = transform.worldToScreen(x - width / 2, y - height / 2); x1, y1 = transform.worldToScreen(x + width / 2, y + height / 2); return x0, y0, x1, y1
    def _draw_bounds(self, x: float, y: float, width: float, height: float, color: str, dash: tuple[int, int], stroke: int) -> None: self.canvas.create_rectangle(*self._screen_bounds(x, y, width, height), outline=color, width=stroke, dash=dash, tags="interaction")
    def _scale_handle_at(self, screen_x: float, screen_y: float) -> str | None:
        document, selected = self.session.document, self.session.selected_id
        if not document or not selected or not self._view_transform: return None
        element = document.element(selected)
        for name, (x, y) in self._handle_positions_for(element.x, element.y, element.width, element.height).items():
            if (screen_x - x) ** 2 + (screen_y - y) ** 2 <= 10 ** 2: return name
        return None
    def _handle_positions_for(self, x: float, y: float, width: float, height: float) -> dict[str, tuple[float, float]]:
        left, top, right, bottom = x - width / 2, y - height / 2, x + width / 2, y + height / 2; transform = self._view_transform
        return {name: transform.worldToScreen(px, py) for name, (px, py) in {"nw": (left, top), "ne": (right, top), "sw": (left, bottom), "se": (right, bottom)}.items()}

    def refresh_rulers(self) -> None:
        transform = self._view_transform
        if not transform: self.ruler_x.delete("all"); self.ruler_y.delete("all"); return
        self.ruler_x.delete("all"); self.ruler_y.delete("all"); left, top, right, bottom = transform.visible_world_bounds(); step_x = self._nice_step(abs(right - left)); step_y = self._nice_step(abs(bottom - top))
        value = math.floor(left / step_x) * step_x
        while value <= right + step_x:
            x, _ = transform.worldToScreen(value, 0)
            if 0 <= x <= self.canvas.winfo_width(): self.ruler_x.create_line(x, 16, x, 24, fill="#8996a4"); self.ruler_x.create_text(x + 2, 2, text="%.0f" % value, anchor="nw", fill="#56616f", font=("Arial", 8))
            value += step_x
        value = math.floor(top / step_y) * step_y
        while value <= bottom + step_y:
            _, y = transform.worldToScreen(0, value)
            if 0 <= y <= self.canvas.winfo_height(): self.ruler_y.create_line(34, y, 42, y, fill="#8996a4"); self.ruler_y.create_text(2, y, text="%.0f" % value, anchor="w", fill="#56616f", font=("Arial", 8))
            value += step_y
    def _refresh_performance_panel(self) -> None:
        self._performance_after = None
        if self._closing or not self.winfo_exists():
            return
        self.metrics.svg_serializations = self.session.svg_serialize_count; self.metrics.document_commits = self.session.document_commit_count; self.metrics.undo_records = self.session.undo_record_count
        data = self.metrics.snapshot(); count = len(self.session.document.elements) if self.session.document else 0
        self._perf_text.set("Element: {count}\nFPS: {fps}  Frame: {frame_ms} ms\nRender: {render_ms} ms  Interaction: {interaction_ms} ms\nCommit: {commit_ms} ms\nPointerMove: {pointer_moves}  Interaction Render: {interaction_renders}\nStatic Render: {static_renders}  Full Canvas: {full_canvas_rebuilds}\nDocument Commit: {document_commits}  Undo: {undo_records}\nSVG Serialize: {svg_serializations}  Hit Test: {spatial_queries}".format(count=count, **data))
        self._performance_after = self.after(300, self._refresh_performance_panel)

    def destroy(self) -> None:
        """Cancel harness timers before Tcl tears down the test/application root."""
        if self._closing:
            return
        self._closing = True
        for callback_id in (self._interaction_after, self._inspector_after, self._parameter_after,
                            self._family_preview_after, self._resize_after, self._performance_after):
            if callback_id:
                try:
                    self.after_cancel(callback_id)
                except tk.TclError:
                    pass
        super().destroy()
    def _set_cursor_status(self, world: tuple[float, float] | None) -> None:
        if world is None: self._status_text.set("X: -- mm    Y: -- mm")
        elif not self._interaction: self._status_text.set("X: %.2f mm    Y: %.2f mm" % world)
    @staticmethod
    def _nice_step(span: float) -> float:
        target = max(span / 8.0, 1e-6); magnitude = 10 ** math.floor(math.log10(target)); normalized = target / magnitude
        return magnitude * (1 if normalized <= 1 else 2 if normalized <= 2 else 5 if normalized <= 5 else 10)
    def _reference_image(self, path: str, width: int, height: int) -> Image.Image:
        key = (str(Path(path).resolve()), max(1, width), max(1, height))
        if self._reference_cache_key != key or self._reference_cache_image is None:
            with Image.open(path) as image: self._reference_cache_image = image.convert("RGBA").resize((key[1], key[2]), Image.Resampling.LANCZOS)
            self._reference_cache_key = key
        return self._reference_cache_image


def run_pattern_lab(workspace: str) -> None:
    app = PatternLabApp(workspace); app.mainloop()
