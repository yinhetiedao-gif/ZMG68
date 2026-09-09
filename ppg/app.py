from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
import random
import re
import tempfile
import threading
from dataclasses import replace
import tkinter as tk
import xml.etree.ElementTree as ET
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from PIL import Image, ImageDraw, ImageTk, ImageOps

from . import APP_NAME, APP_VERSION
from .exporters import write_dxf, write_png, write_svg, write_field_dxf, write_field_png, write_field_svg, write_editable_document_svg, write_editable_document_png, write_editable_document_dxf
from .geometry import builtin_contour, clean_contour, element_polygon, generate_items, sample_evenly, simplify_polyline
from .history import History
from .i18n import I18N
from .model import PatternSettings, Point, Project
from .project_io import load_project, save_preset, save_project
from .raster_print import audit_stl, convert_image
from .theme import COLORS, apply as apply_theme
from .generators import default_registry
from .reference2d import EditablePatternDocument, ReferenceReconstructionService
from .field_generators import generate_field, primitive_polygon
from .xiaomang_pipeline import run_project_stl_pipeline
from .final_geometry import apply_height_field, primitives_bounds, scale_primitives_to_width
from .preview_provider import NullPreviewProvider
from .reference2d.manufacturing import document_to_primitives
from .mascot import draw_mango_cat
from .ui import CanvasLayers, GeneratorShelf, ParameterControl, ToolButton
from reference2d_poc import Document2D, Reference2DService, ReferenceLayer, GeometryLayer, DotObject


class Tooltip:
    def __init__(self, widget, text: str):
        self.widget, self.text, self.tip = widget, text, None
        widget.bind("<Enter>", self.show, add=True); widget.bind("<Leave>", self.hide, add=True)
    def show(self, _event=None):
        if self.tip or not self.text: return
        x, y = self.widget.winfo_rootx() + 16, self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget); self.tip.wm_overrideredirect(True); self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, justify="left", background="#172839", foreground="#e4edf5", relief="solid", borderwidth=1, padx=7, pady=4).pack()
    def hide(self, _event=None):
        if self.tip: self.tip.destroy(); self.tip = None


class PatternApp(tk.Tk):
    AUTOSAVE_SECONDS = 180
    SHAPES = ["圆形", "椭圆", "圆角矩形", "星形", "多边形", "心形", "有机形", "波浪形"]
    ELEMENTS = ["线条 + 圆点", "直线", "圆点", "三角形", "矩形", "叶片", "水滴", "珠子", "自定义 SVG"]
    FIELD_GENERATORS = {"半调点阵":"halftone","规则点阵":"dot_matrix","渐变点阵":"gradient_dots","点线面构成":"point_line_plane","轮廓遮罩":"shape_mask","网格变形":"grid_distortion","流场":"flow_field","波场":"wave_field","噪声场":"noise_field"}
    GEOMETRIC_VARS = ("length","width","dot_radius","spacing","field_spacing","dot_size","line_width","row_spacing","column_spacing","min_size","max_size","field_offset_x","field_offset_y","feather","edge_softness","three_d_thickness","three_d_min_feature","target_width_mm")

    def __init__(self):
        super().__init__()
        self.t = I18N().t
        self.title(f"{APP_NAME} · AI 参数化创意设计与 3D 制造 {APP_VERSION}")
        self.minsize(1050, 690); self.geometry("1250x800")
        self.configure(bg=COLORS["space"])
        self.project = Project(); self.project.contour = builtin_contour("有机形", self.project.settings.seed)
        self.generator_registry = default_registry()
        self.project_path: str | None = None
        self.history = History(); self._after_id = None; self._interaction_after_id = None; self._layout_retry_id = None; self._autosave_id = None; self._drawing_points: list[Point] = []
        self._dragging = False; self._sample_cache: dict[tuple, list] = {}; self._field_cache: dict[tuple, list] = {}; self._analysis_cache: dict[tuple, object] = {}; self._last_transform = None
        self._preview_photo = None; self._reference_photo = None; self._reference_preview_cache = {}; self._reference_pane_cache = {}; self._two_d_drag = None; self._two_d_pan_drag = None; self._reference2d_document: Document2D | None = None; self._editable_pattern_document: EditablePatternDocument | None = None; self._reference2d_drag_id: str | None = None; self._reference2d_drag_ids: list[str] = []; self._reference2d_drag_last = None; self._reference2d_box_start = None; self._reference2d_box_item = None; self._unit_display="mm"; self._last_target_width=s.target_width_mm if (s:=self.project.settings) else 100.0
        self._two_d_zoom = float(self.project.view_2d.get("zoom",1.0));self._two_d_pan_x=float(self.project.view_2d.get("pan_x",0.0));self._two_d_pan_y=float(self.project.view_2d.get("pan_y",0.0))
        self.preview_provider = NullPreviewProvider(); self._final_model_result = None
        self._build_variables(); self._build_ui(); self._bind_shortcuts(); self._load_builtin("有机形", remember=False)
        self.update_preview(); self.remember(); self._autosave_id = self.after(self.AUTOSAVE_SECONDS * 1000, self.autosave); self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_variables(self):
        s = self.project.settings
        self.vars = {"contour_type": tk.StringVar(value=s.contour_type), "element_type":tk.StringVar(value=s.element_type), "distribution":tk.StringVar(value=s.distribution), "direction":tk.StringVar(value=s.direction), "preview_quality":tk.StringVar(value=s.preview_quality), "units":tk.StringVar(value=s.units), "active_generator":tk.StringVar(value=s.active_generator), "field_generator":tk.StringVar(value=next((label for label,key in self.FIELD_GENERATORS.items() if key==s.field_generator),"半调点阵")), "field_element":tk.StringVar(value=s.field_element), "field_shape":tk.StringVar(value=s.field_shape), "gradient_mode":tk.StringVar(value=s.gradient_mode), "mask_type":tk.StringVar(value=s.mask_type), "reference_image":tk.StringVar(value=s.reference_image), "gradient_curve":tk.StringVar(value=s.gradient_curve), "element_fill":tk.StringVar(value=s.element_fill), "image_invert":tk.BooleanVar(value=s.image_invert)}
        for name in ("count", "length", "width", "dot_radius", "length_random", "dot_random", "noise_strength", "noise_scale", "rotation", "offset", "scale", "spacing", "seed", "target_width_mm"):
            self.vars[name] = tk.StringVar(value=str(getattr(s, name)))
        for name in ("field_spacing","dot_size","line_width","field_scale","gradient_strength","field_contrast","field_threshold","feather","field_blur","field_rotation","field_noise","smooth_noise","row_spacing","column_spacing","min_size","max_size","field_density","field_offset_x","field_offset_y","image_gamma","mask_strength","edge_softness","gradient_center_x","gradient_center_y","random_strength","random_size","random_rotation","random_position","random_density","noise_frequency","noise_offset","distortion_wave","distortion_twist","distortion_bend","distortion_curl","distortion_flow","attraction","repulsion","element_aspect"):
            self.vars[name] = tk.StringVar(value=str(getattr(s, name)))
        for name in ("grid_columns","grid_rows","image_levels","noise_octaves"):
            self.vars[name] = tk.StringVar(value=str(getattr(s, name)))
        for name in ("three_d_thickness","three_d_quality","three_d_roundness","three_d_blend","three_d_min_feature"):
            self.vars[name] = tk.StringVar(value=str(getattr(s, name)))
        for name in ("reference_compare_mode",):
            self.vars[name] = tk.StringVar(value=str(getattr(s, name)))
        self.vars["reference2d_radius"] = tk.StringVar(value="2.0")
        self.vars["reference2d_rotation"] = tk.StringVar(value="0.0")
        self.vars["reference2d_rule_x"] = tk.StringVar(value="1.0")
        self.vars["reference2d_rule_y"] = tk.StringVar(value="1.0")
        self.vars["reference2d_rule_rotation"] = tk.StringVar(value="0.0")
        self.vars["reference2d_size_gradient"] = tk.StringVar(value="0.0")
        self.vars["reference2d_density"] = tk.StringVar(value="0.0")
        self.vars["reference2d_warp"] = tk.StringVar(value="0.0")
        self.vars["reference2d_mask_radius"] = tk.StringVar(value="50.0")
        self.vars["reference_rebuild_enabled"]=tk.BooleanVar(value=s.reference_rebuild_enabled)
        for name in ("reference_strength","reference_structure_preservation","reference_creative_variation","reference_void_size","reference_void_rotation","reference_void_feather","reference_corner_emphasis","reference_vortex","reference_center_x","reference_center_y","reference_warp_radius","reference_corner_density","reference_size_gradient","reference_density_gradient","reference_match_score","reference_opacity"):
            self.vars[name]=tk.StringVar(value=str(getattr(s,name)))
        self.vars["reference_use_extracted_elements"]=tk.BooleanVar(value=s.reference_use_extracted_elements)

    def _build_ui(self):
        apply_theme(self)
        self._build_menu()
        self._build_toolbar()
        # 左侧参数、右侧大尺寸可编辑二维工作区；最终 3D 建模在后台独立执行。
        body = ttk.Panedwindow(self, orient="horizontal"); body.pack(fill="both", expand=True, padx=10, pady=(0,7))
        left = ttk.Frame(body, width=315); right = ttk.Frame(body); body.add(left, weight=0); body.add(right, weight=1)
        self._build_preview(right); self._build_controls(left)
        footer = ttk.Frame(self, padding=(10, 8)); footer.pack(fill="x")
        ttk.Button(footer, text=self.t("randomize"), command=self.randomize, style="Action.TButton").pack(side="left")
        ttk.Button(footer, text="生成变体", command=self.generate_variants).pack(side="left", padx=5)
        ttk.Button(footer, text="生成三维模型", command=self.generate_3d_model, style="Action.TButton").pack(side="left", padx=5)
        ttk.Button(footer, text="导出 STL", command=self.export_stl, style="Action.TButton").pack(side="left", padx=5)
        ttk.Button(footer, text=self.t("save_preset"), command=self.save_current_preset).pack(side="left", padx=5)
        ttk.Button(footer, text=self.t("load_preset"), command=self.load_preset).pack(side="left")
        for key, kind in [("export_svg","svg"),("export_png","png"),("export_dxf","dxf")]: ttk.Button(footer, text=self.t(key), command=lambda kind=kind: self.export(kind), style="Action.TButton").pack(side="right", padx=3)
        status_row=ttk.Frame(self,padding=(10,4));status_row.pack(fill="x",side="bottom")
        self.status = tk.StringVar(value=self.t("ready"));ttk.Label(status_row,textvariable=self.status,anchor="w").pack(side="left",fill="x",expand=True)
        self.dimension_status=tk.StringVar(value="100.00 × 100.00 × 1.20 mm · 0 个元素 · 参考匹配度：— · 自动保存：已开启")
        ttk.Label(status_row,textvariable=self.dimension_status,anchor="e",foreground=COLORS["muted"]).pack(side="right")

    def _on_navigation(self, key: str) -> None:
        """导航只切换当前工作区，不销毁或重建窗口。"""
        tabs = {"radial": 0, "field": 1, "preview": 2}
        if key in tabs:
            self.control_notebook.select(tabs[key])
        elif key == "more":
            self.show_generators()

    def _select_shelf_generator(self, key: str) -> None:
        mapping = {"dot_matrix": "规则点阵", "gradient_dots": "渐变点阵", "halftone": "半调点阵", "wave_field": "波场", "grid_distortion": "网格变形", "flow_field": "流场"}
        if key == "more":
            self.show_generators(); return
        if key in mapping:
            self.vars["active_generator"].set("field")
            self.vars["field_generator"].set(mapping[key])
            self.activate_field_generator()

    def _build_toolbar(self):
        toolbar=ttk.Frame(self,padding=(10,7));toolbar.pack(fill="x")
        brand=ttk.Frame(toolbar);brand.pack(side="left",padx=(0,12));ttk.Label(brand,text="小芒造物",font=("Microsoft YaHei UI",13,"bold"),foreground=COLORS["blue"]).pack(anchor="w");ttk.Label(brand,text="AI 参数化创意设计平台",foreground=COLORS["muted"]).pack(anchor="w")
        ttk.Label(toolbar,text="单位：").pack(side="right",padx=(8,2));unit_box=ttk.Combobox(toolbar,textvariable=self.vars["units"],values=["mm","cm","inch"],width=6,state="readonly");unit_box.pack(side="right");unit_box.bind("<<ComboboxSelected>>",self.change_units,add=True)
        actions=[(self.t("new"),self.new_project),(self.t("open"),self.open_project),(self.t("save"),self.save_current),(self.t("undo"),self.undo),(self.t("redo"),self.redo),("导入参考图",self.analyze_reference_image),(self.t("import"),self.import_contour),(self.t("draw"),self.begin_draw),("图片转 SVG / STL",self.image_to_print),("生成最终模型",self.generate_3d_model),("导出 STL",self.export_stl),(self.t("randomize"),self.randomize)]
        self._toolbar_actions=actions;ttk.Button(toolbar,text="‹",width=3,command=lambda:self._scroll_toolbar(-4)).pack(side="left")
        canvas=tk.Canvas(toolbar,bg=COLORS["surface"],height=40,highlightthickness=0);canvas.pack(side="left",fill="x",expand=True,padx=2);inner=ttk.Frame(canvas);window=canvas.create_window((0,0),window=inner,anchor="nw")
        primary_labels={"导出 STL","生成最终模型"}
        for label,command in actions:
            button=ToolButton(inner,text=label,command=command,primary=label in primary_labels);button.pack(side="left",padx=2);button.bind("<MouseWheel>",self._toolbar_wheel);button.bind("<Shift-MouseWheel>",self._toolbar_wheel)
        inner.bind("<Configure>",lambda _e:canvas.configure(scrollregion=canvas.bbox("all")));canvas.bind("<Configure>",lambda event:canvas.itemconfigure(window,height=event.height));canvas.bind("<MouseWheel>",self._toolbar_wheel);canvas.bind("<Shift-MouseWheel>",self._toolbar_wheel);canvas.bind("<ButtonPress-1>",lambda event:canvas.scan_mark(event.x,event.y));canvas.bind("<B1-Motion>",lambda event:canvas.scan_dragto(event.x,event.y,gain=1))
        self._toolbar_canvas=canvas;ttk.Button(toolbar,text="›",width=3,command=lambda:self._scroll_toolbar(4)).pack(side="left")
        more=ttk.Menubutton(toolbar,text="更多 ▾");menu=tk.Menu(more,tearoff=False)
        for label,command in actions:menu.add_command(label=label,command=command)
        more.configure(menu=menu);more.pack(side="left",padx=(4,0))

    def _scroll_toolbar(self,units): self._toolbar_canvas.xview_scroll(units,"units")
    def _toolbar_wheel(self,event):
        # Windows 鼠标滚轮、Shift+滚轮与触控板横移统一转为横向浏览。
        amount=-1*(event.delta//120 or 1);self._scroll_toolbar(amount if event.state&1 else amount*2);return "break"

    def _build_menu(self):
        menu = tk.Menu(self); file_menu = tk.Menu(menu, tearoff=False)
        for label, command in [(self.t("new"),self.new_project),(self.t("open"),self.open_project),(self.t("save"),self.save_current),(self.t("save_as"),self.save_as)]: file_menu.add_command(label=label, command=command)
        file_menu.add_separator(); file_menu.add_command(label="退出", command=self.on_close); menu.add_cascade(label="文件", menu=file_menu)
        edit = tk.Menu(menu, tearoff=False); edit.add_command(label=self.t("undo"),command=self.undo); edit.add_command(label=self.t("redo"),command=self.redo); menu.add_cascade(label="编辑",menu=edit)
        help_menu = tk.Menu(menu, tearoff=False); help_menu.add_command(label="关于", command=lambda: messagebox.showinfo("关于", f"{APP_NAME}\n版本 {APP_VERSION}\n\nAI 参数化创意设计与 3D 制造。")); menu.add_cascade(label="帮助",menu=help_menu); self.config(menu=menu)

    def _build_controls(self, parent):
        notebook = ttk.Notebook(parent); notebook.pack(fill="both", expand=True)
        self.control_notebook=notebook
        design = ttk.Frame(notebook, padding=10); field = ttk.Frame(notebook, padding=10); advanced = ttk.Frame(notebook, padding=10)
        notebook.add(design, text="放射设计"); notebook.add(field, text="点线面 / 半调"); notebook.add(advanced, text="随机与制造");self.field_tab=field
        notebook.bind("<<NotebookTabChanged>>",self._on_tab_changed)
        self._group_contour(design); self._group_elements(design); self._group_parameters(design); self._group_noise(advanced); self._group_preview(advanced); self._build_manufacturing_controls(advanced)
        self._build_field_tab(field)

    def _frame(self, parent, title):
        f = ttk.LabelFrame(parent, text=title, padding=8); f.pack(fill="x", pady=(0,8)); return f

    def _build_field_tab(self,parent):
        search=ttk.Frame(parent);search.pack(fill="x",padx=10,pady=(10,4));ttk.Label(search,text="搜索参数：").pack(side="left")
        self.field_parameter_search=tk.StringVar();entry=ttk.Entry(search,textvariable=self.field_parameter_search);entry.pack(side="left",fill="x",expand=True);entry.bind("<KeyRelease>",self.filter_field_parameters);ttk.Button(search,text="清除",command=lambda:self.field_parameter_search.set("")).pack(side="left",padx=(4,0))
        shell=ttk.Frame(parent);shell.pack(fill="both",expand=True);bar=ttk.Scrollbar(shell,orient="vertical");bar.pack(side="right",fill="y");canvas=tk.Canvas(shell,bg=COLORS["surface"],highlightthickness=0,yscrollcommand=bar.set);canvas.pack(side="left",fill="both",expand=True);bar.configure(command=canvas.yview)
        inner=ttk.Frame(canvas,padding=(10,2,10,10));window=canvas.create_window((0,0),window=inner,anchor="nw")
        inner.bind("<Configure>",lambda _e:canvas.configure(scrollregion=canvas.bbox("all")));canvas.bind("<Configure>",lambda event:canvas.itemconfigure(window,width=event.width));canvas.bind("<MouseWheel>",lambda event:canvas.yview_scroll(-1*(event.delta//120),"units"));self._field_parameter_rows=[]
        self._group_field_generator(inner)

    def _field_slider(self,parent,key,label,lo,hi,resolution,suffix="",tip=""):
        scale=self._slider(parent,key,label,lo,hi,resolution,suffix,tip);self._field_parameter_rows.append((label.lower(),scale.master));return scale

    def filter_field_parameters(self,_event=None):
        query=self.field_parameter_search.get().strip().lower()
        for label,row in self._field_parameter_rows:
            if not query or query in label:row.pack(fill="x",pady=3)
            else:row.pack_forget()

    def _combo(self, parent, label, var, values, tip=""):
        row = ttk.Frame(parent); row.pack(fill="x", pady=3); lab = ttk.Label(row,text=label,width=11); lab.pack(side="left"); box=ttk.Combobox(row,textvariable=var,values=values,state="readonly",width=16);box.pack(side="right",fill="x",expand=True);box.bind("<<ComboboxSelected>>",self.on_choice);Tooltip(lab,tip);return box

    def _slider(self, parent, key, label, lo, hi, resolution, suffix="", tip=""):
        control=ParameterControl(parent,label=label,variable=self.vars[key],lower=lo,upper=hi,resolution=resolution,suffix=suffix,on_change=self.on_slider,default=self.vars[key].get())
        control.pack(fill="x",pady=3)
        control.scale.bind("<ButtonPress-1>",lambda _e:setattr(self,"_dragging",True),add=True)
        control.scale.bind("<ButtonRelease-1>",self.on_slider_release,add=True)
        Tooltip(control,tip)
        return control.scale

    def _group_contour(self,parent):
        f=self._frame(parent,self.t("contour")); self._combo(f,"内置轮廓",self.vars["contour_type"],self.SHAPES,"选择后将使用内置闭合轮廓；导入或自由绘制会保留自定义轮廓。")
        actions=ttk.Frame(f);actions.pack(fill="x",pady=(5,0));ttk.Button(actions,text=self.t("import"),command=self.import_contour).pack(side="left",expand=True,fill="x",padx=(0,3));ttk.Button(actions,text=self.t("draw"),command=self.begin_draw).pack(side="left",expand=True,fill="x",padx=(3,0))
    def _group_elements(self,parent):
        f=self._frame(parent,self.t("element"));self._combo(f,"外围元素",self.vars["element_type"],self.ELEMENTS,"支持线、点、三角、矩形、叶片、水滴、珠子和自定义 SVG。")
        ttk.Button(f,text="导入 SVG 作为元素",command=self.import_element).pack(fill="x",pady=(4,3))
        self._combo(f,"分布方式",self.vars["distribution"],["均匀","随机","渐变","曲率"],"均匀：等弧长；随机：可复现的轻微位置变化；渐变：由疏到密；曲率：更关注转折处。");self._combo(f,"方向",self.vars["direction"],["向外法线","向内法线","朝向中心","远离中心"],"向外法线会自动根据轮廓内外侧判定方向。")
    def _group_parameters(self,parent):
        f=self._frame(parent,self.t("parameters"));self._slider(f,"count",self.t("count"),10,1000,1,tip="沿轮廓按等弧长放置的元素数量。");self._slider(f,"spacing","最小间距",0,50,.5,tip="大于 0 时限制相邻元素的最小弧长间距。");self._slider(f,"length",self.t("length"),1,150,0.5,tip="放射结构的基础长度，内部单位为毫米。");self._slider(f,"width",self.t("width"),0.2,10,0.1,tip="导出的矢量线条宽度。");self._slider(f,"dot_radius",self.t("dot_radius"),0.2,30,0.1,tip="末端元素的基础半径或大小。")
        self._slider(f,"rotation","旋转",-180,180,1,"°","在当前方向基础上旋转元素。");self._slider(f,"offset","偏移",0,50,.5,"","让元素与轮廓之间留出距离。");self._slider(f,"scale","缩放",.2,3,.05,"×","统一缩放外围元素。")

    def _group_field_generator(self,parent):
        f=self._frame(parent,"生成器与元素")
        box=self._combo(f,"生成器",self.vars["field_generator"],list(self.FIELD_GENERATORS),"半调、规则点阵、渐变点阵、点线面构成、轮廓遮罩、网格变形。")
        box.bind("<<ComboboxSelected>>",self.activate_field_generator)
        self._combo(f,"基础元素",self.vars["field_element"],["点","线","胶囊","面","点线面"],"点线面构成可自动混合；胶囊会生成圆头线元素。")
        self._combo(f,"元素形状",self.vars["field_shape"],["圆","方形","三角","菱形","六边形","水滴","叶片"],"支持圆、方、三角、菱形、六边形、水滴和叶片。")
        self._combo(f,"填充方式",self.vars["element_fill"],["实心","空心","描边"],"空心和描边会输出可编辑的矢量描边。")
        self._combo(f,"排列 / 渐变",self.vars["gradient_mode"],["参考明暗","径向","中心 → 边缘","边缘 → 中心","线性","X 方向","Y 方向","波纹","均匀"],"参考明暗从导入图提取密度规律；其他模式生成新的可控构图。")
        self._combo(f,"渐变曲线",self.vars["gradient_curve"],["线性","平滑","S 曲线"],"控制从低密度到高密度的变化曲线。")
        self._combo(f,"Mask 轮廓",self.vars["mask_type"],["无 Mask","圆形","星形","心形","圆角矩形"],"限制点线面生成的范围。参考图只用于密度场，不直接复制像素。")
        ttk.Button(f,text="导入 / 更换参考图片",command=self.analyze_reference_image).pack(fill="x",pady=(5,0))
        f=self._frame(parent,"可编辑检测元素")
        self.reference2d_selection_info=tk.StringVar(value="导入点阵图后，可在 2D 画布中点击、拖动真实元素。")
        ttk.Label(f,textvariable=self.reference2d_selection_info,wraplength=250,foreground=COLORS["muted"]).pack(anchor="w")
        self._slider(f,"reference2d_radius","选中元素半径",0.2,40,.1,"px","只修改选中的真实元素；应用后写入 EditablePatternDocument。")
        ttk.Button(f,text="应用元素尺寸",command=self.apply_reference2d_radius).pack(fill="x",pady=(3,2))
        self._slider(f,"reference2d_rotation","选中元素旋转",-180,180,1,"°","可批量修改选中真实元素的旋转；会保存为 Local Override。")
        ttk.Button(f,text="应用元素旋转",command=self.apply_reference2d_rotation).pack(fill="x",pady=(0,2))
        ttk.Button(f,text="组合选中元素",command=self.group_reference2d_selected).pack(fill="x",pady=(0,2))
        ttk.Button(f,text="按规则重新构建",command=self.rebuild_editable_pattern).pack(fill="x",pady=(0,2))
        ttk.Button(f,text="删除选中元素",command=self.delete_reference2d_selected).pack(fill="x")
        ttk.Button(f,text="导出检测调试图",command=self.export_reference_debug).pack(fill="x",pady=(3,0))
        f=self._frame(parent,"参数化规则（仅参数化模式）")
        self.reference2d_rule_info=tk.StringVar(value="导入后显示 Base Generator 与 Modifier Stack；直接元素模式不强制套用规则。")
        ttk.Label(f,textvariable=self.reference2d_rule_info,wraplength=250,foreground=COLORS["muted"]).pack(anchor="w",pady=(0,4))
        for label,name in (("横向 / 半径缩放","reference2d_rule_x"),("纵向缩放","reference2d_rule_y"),("规则旋转（°）","reference2d_rule_rotation"),("尺寸渐变","reference2d_size_gradient"),("密度渐变","reference2d_density"),("简单变形","reference2d_warp"),("圆形 Mask 半径","reference2d_mask_radius")):
            row=ttk.Frame(f);row.pack(fill="x",pady=1);ttk.Label(row,text=label,width=14).pack(side="left");ttk.Entry(row,textvariable=self.vars[name],width=9).pack(side="right")
        ttk.Button(f,text="应用规则并重建",command=self.apply_reference2d_rules).pack(fill="x",pady=(4,0))
        f=self._frame(parent,"参考图重建规则")
        ttk.Label(f,text="Reference Layer 与 Geometry Layer 独立保存；隐藏原图不会删除元素。",wraplength=250,foreground=COLORS["muted"]).pack(anchor="w")
        self._combo(f,"对比视图",self.vars["reference_compare_mode"],["重建结果","原图","左右对比","叠加对比"],"查看原图、生成规则重建结果或二者的叠加；不将原图导出为生成结果。")
        ttk.Button(f,text="隐藏参考原图（只看参数化结果）",command=self.hide_reference_image).pack(fill="x",pady=(2,3))
        self._field_slider(f,"reference_opacity","原图透明度",0,100,1,"%","仅用于对比视图的显示透明度。")
        self._field_slider(f,"reference_strength","参考强度",0,100,1,"%","参考图分析出的空间规则对当前构图的影响。")
        self._field_slider(f,"reference_structure_preservation","结构保留",0,100,1,"%","保留中心留白、密度场和锚点关系的程度。")
        self._field_slider(f,"reference_creative_variation","创意变化",0,100,1,"%","降低规则约束，生成同类但不同构图的版本。")
        self._field_slider(f,"reference_void_size","中心留白",0,70,1,"%","分析出的中心方形/菱形留白，可独立修改。")
        self._field_slider(f,"reference_void_rotation","留白旋转",-90,90,1,"°","中心留白的方向。")
        self._field_slider(f,"reference_void_feather","留白过渡",.2,15,.2,"","留白边缘的连续过渡。")
        self._field_slider(f,"reference_corner_emphasis","角点强调",0,100,1,"%","角落元素的尺寸/密度加强。")
        self._field_slider(f,"reference_vortex","中心涡旋",-100,100,1,"%","由位置场推导出的连续旋转扭曲。")
        self.reference_stack_text=tk.StringVar(value="基础生成器：等待导入参考图\n修改器：—")
        ttk.Label(f,textvariable=self.reference_stack_text,justify="left",wraplength=250,foreground="#526170").pack(anchor="w",pady=(5,3))
        ttk.Button(f,text="自动优化匹配",command=self.optimize_reference_match).pack(fill="x")
        f=self._frame(parent,"基础网格")
        self._field_slider(f,"grid_columns","横向数量",0,120,1,"","0 时由列距自动决定。")
        self._field_slider(f,"grid_rows","纵向数量",0,120,1,"","0 时由行距自动决定。")
        self._field_slider(f,"field_spacing","点间距",1.2,16,.1,"mm","未指定行/列距时的统一间距。")
        self._field_slider(f,"row_spacing","行距",0,16,.1,"mm","0 时使用点间距。")
        self._field_slider(f,"column_spacing","列距",0,16,.1,"mm","0 时使用点间距。")
        self._field_slider(f,"min_size","最小尺寸",.05,10,.05,"mm","密度最低处的元素尺寸。")
        self._field_slider(f,"max_size","最大尺寸",.1,14,.05,"mm","密度最高处的元素尺寸。")
        self._field_slider(f,"line_width","线宽",.1,5,.1,"mm","线和胶囊的宽度。")
        self._field_slider(f,"element_aspect","长宽比",.2,3,.05,"×","圆、点和面在 X 方向的比例。")
        self._field_slider(f,"field_density","密度",0,100,1,"%","保留网格元素的比例。")
        self._field_slider(f,"field_scale","整体缩放",.2,3,.05,"×","统一改变元素尺寸。")
        self._field_slider(f,"field_offset_x","X 偏移",-30,30,.5,"mm","整个网格的横向偏移。")
        self._field_slider(f,"field_offset_y","Y 偏移",-30,30,.5,"mm","整个网格的纵向偏移。")
        self._field_slider(f,"field_rotation","旋转",-180,180,1,"°","线性渐变和元素初始方向。")
        f=self._frame(parent,"图像映射")
        self._field_slider(f,"field_contrast","对比度",0,100,1,"%","提高明暗变化的影响。")
        self._field_slider(f,"image_gamma","Gamma",.2,3,.05,"","调整参考图亮度映射。")
        self._field_slider(f,"image_levels","Levels",0,16,1,"","0 为连续灰阶；大于 1 时量化为层级。")
        ttk.Checkbutton(f,text="反相亮度映射",variable=self.vars["image_invert"],command=self.schedule_preview).pack(anchor="w",pady=3)
        self._field_slider(f,"field_threshold","阈值",0,95,1,"%","低于阈值的区域不生成元素。")
        self._field_slider(f,"field_blur","模糊",0,20,.2,"","平滑参考图的明暗场。")
        self._field_slider(f,"feather","Feather",0,15,.2,"mm","Mask 基础边缘过渡。")
        self._field_slider(f,"edge_softness","边缘柔化",0,15,.2,"mm","额外柔化 Mask 边缘。")
        self._field_slider(f,"mask_strength","Mask 强度",0,100,1,"%","0 为忽略 Mask；100 为完全按 Mask 限制。")
        f=self._frame(parent,"渐变")
        self._field_slider(f,"gradient_strength","渐变强度",0,100,1,"%","控制明暗或程序渐变的影响。")
        self._field_slider(f,"gradient_center_x","渐变中心 X",0,100,1,"","径向渐变中心。")
        self._field_slider(f,"gradient_center_y","渐变中心 Y",0,100,1,"","径向渐变中心。")
        f=self._frame(parent,"Random")
        self._field_slider(f,"random_strength","Random Strength",0,100,1,"%","统一随机扰动。")
        self._field_slider(f,"random_size","Random Size",0,100,1,"%","独立随机尺寸。")
        self._field_slider(f,"random_rotation","Random Rotation",0,180,1,"°","独立随机旋转。")
        self._field_slider(f,"random_position","Random Position",0,100,1,"%","独立随机位置。")
        self._field_slider(f,"random_density","Random Density",0,100,1,"%","随机保留/减少元素。")
        f=self._frame(parent,"Smooth Noise")
        self._field_slider(f,"field_noise","Noise Strength",0,100,1,"%","连续噪声对密度和方向的影响。")
        self._field_slider(f,"smooth_noise","Noise Scale",2,40,1,"","数值越大，变化越平滑。")
        self._field_slider(f,"noise_frequency","Noise Frequency",.1,5,.1,"","噪声重复频率。")
        self._field_slider(f,"noise_offset","Noise Offset",-100,100,1,"","平移噪声场但保持 Seed。")
        self._field_slider(f,"noise_octaves","Noise Octaves",1,6,1,"","叠加细节层数。")
        f=self._frame(parent,"Distortion")
        self._field_slider(f,"distortion_wave","Wave",0,100,1,"%","波形位置扭曲。")
        self._field_slider(f,"distortion_twist","Twist",-180,180,1,"°","围绕渐变中心扭转。")
        self._field_slider(f,"distortion_bend","Bend",-100,100,1,"%","沿 X 方向弯曲。")
        self._field_slider(f,"distortion_curl","Curl",-100,100,1,"%","增加旋涡感。")
        self._field_slider(f,"distortion_flow","Flow",0,100,1,"%","噪声驱动的流场位移。")
        self._field_slider(f,"attraction","Attraction",0,100,1,"%","向渐变中心吸引。")
        self._field_slider(f,"repulsion","Repulsion",0,100,1,"%","从渐变中心排斥。")
        row=ttk.Frame(f);row.pack(fill="x",pady=4);lab=ttk.Label(row,text="随机种子",width=11);lab.pack(side="left");entry=ttk.Entry(row,textvariable=self.vars["seed"],justify="right");entry.pack(side="right",fill="x",expand=True);entry.bind("<Return>",self.on_entry);entry.bind("<FocusOut>",self.on_entry);Tooltip(lab,"相同参数和 Seed 会得到相同的生成结果。")

    def _group_noise(self,parent):
        f=self._frame(parent,self.t("noise"));self._slider(f,"length_random",self.t("length_random"),0,100,1,"%","每根线的独立随机变化范围。");self._slider(f,"dot_random",self.t("dot_random"),0,100,1,"%","每个圆点的独立随机变化范围。");self._slider(f,"noise_strength",self.t("noise_strength"),0,80,1,"%","相邻元素连续变化的程度，而非跳跃式随机。");self._slider(f,"noise_scale",self.t("noise_scale"),3,100,1,"","控制随机变化的连续范围。数值越大，相邻元素之间的变化越平缓。")
        row=ttk.Frame(f);row.pack(fill="x",pady=4);lab=ttk.Label(row,text=self.t("seed"),width=11);lab.pack(side="left");entry=ttk.Entry(row,textvariable=self.vars["seed"],justify="right");entry.pack(side="right",fill="x",expand=True);entry.bind("<Return>",self.on_entry);entry.bind("<FocusOut>",self.on_entry);Tooltip(lab,"相同 Seed 与相同参数将生成完全相同的图案。")
    def _group_preview(self,parent):
        f=self._frame(parent,"预览与成品尺寸");self._combo(f,self.t("preview_quality"),self.vars["preview_quality"],["快速","标准","高质量"],"快速：最多 80 个元素；标准：最多 250 个；高质量：完整数量。拖动滑块时自动临时使用快速预览。")
        self._slider(f,"target_width_mm","目标宽度",10,500,.5,"mm","二维、三维和最终 STL 共享此成品宽度；内部统一用 mm。")
        ttk.Label(f,text="提示：拖动参数时会在约 80ms 后刷新，松开后自动恢复所选预览质量。",wraplength=260,foreground="#555").pack(anchor="w",pady=(5,0))

    def _build_manufacturing_controls(self,parent):
        f=self._frame(parent,"最终制造模型")
        ttk.Button(f,text="生成最终模型",command=self.generate_3d_model,style="Action.TButton").pack(fill="x",pady=(0,4))
        ttk.Button(f,text="导出 STL",command=self.export_stl,style="Action.TButton").pack(fill="x")
        ttk.Label(f,text="不会创建实时三维预览。点击后在后台生成最终制造网格，并报告尺寸、三角面、组件和封闭性。",wraplength=260,foreground="#555").pack(anchor="w",pady=(6,0))
        f=self._frame(parent,"制造参数")
        self._slider(f,"three_d_thickness","基础厚度",.2,12,.1,"mm","最终模型的基础厚度。")
        self._slider(f,"three_d_roundness","圆润程度",0,100,1,"%","结构清晰到液态圆润的总控。")
        self._slider(f,"three_d_blend","有机融合",0,100,1,"%","控制图元之间的连续融合感。")
        self._slider(f,"three_d_min_feature","最小结构宽度",.2,3,.1,"mm","制造清理的最小保留宽度；0.4 mm 喷嘴建议不低于 0.8 mm。")
        self._combo(f,"最终模型质量",self.vars["three_d_quality"],["草稿","标准","精细","超精细"],"仅点击导出 STL 时使用；不会在拖动参数时重建最终网格。")

    def _build_preview(self,parent):
        header=ttk.Frame(parent);header.pack(fill="x",pady=(0,5));ttk.Label(header,text="2D 设计工作区",font=("Microsoft YaHei UI",12,"bold")).pack(side="left",padx=(0,10))
        ttk.Label(header,text="Editable Pattern Document",foreground=COLORS["muted"]).pack(side="left")
        self.preview_info=tk.StringVar(value="");ttk.Label(header,textvariable=self.preview_info,foreground="#666").pack(side="right")
        reference_bar=ttk.Frame(parent);reference_bar.pack(fill="x",pady=(0,5))
        self.reference_visible=tk.BooleanVar(value=True)
        ttk.Checkbutton(reference_bar,text="显示参考图",variable=self.reference_visible,command=lambda:self.schedule_preview(40)).pack(side="left")
        self._combo(reference_bar,"对比",self.vars["reference_compare_mode"],["重建结果","原图","左右对比","叠加对比"],"参考图只显示在 Reference Layer，不会改变生成几何。")
        ttk.Label(reference_bar,text="Reference Layer 与 Geometry Layer 已分离",foreground=COLORS["muted"]).pack(side="right")
        self.preview_stack=ttk.Frame(parent);self.preview_stack.pack(fill="both",expand=True)
        self.canvas=tk.Canvas(self.preview_stack,bg=COLORS["canvas"],highlightthickness=1,highlightbackground=COLORS["ice"],cursor="crosshair");self.canvas.pack(fill="both",expand=True);self.canvas.bind("<Configure>",lambda _e:self.schedule_preview(120));self.canvas.bind("<ButtonPress-1>",self.draw_start);self.canvas.bind("<B1-Motion>",self.draw_move);self.canvas.bind("<ButtonRelease-1>",self.draw_end);self.canvas.bind("<ButtonPress-2>",self._two_d_pan_start);self.canvas.bind("<B2-Motion>",self._two_d_pan_move);self.canvas.bind("<ButtonRelease-2>",lambda _e:setattr(self,"_two_d_pan_drag",None));self.canvas.bind("<MouseWheel>",self._two_d_wheel);self.canvas.bind("<Escape>",lambda _e:self.canvas.configure(cursor="crosshair"))
        self.canvas_layers=CanvasLayers(self.canvas)
        self.generator_shelf=GeneratorShelf(parent, [("dot_matrix","规则点阵"),("gradient_dots","放射点阵"),("halftone","螺旋点阵"),("wave_field","波纹点阵"),("grid_distortion","网格点阵"),("flow_field","流动点阵"),("gradient_dots","密度渐变"),("more","更多")], self._select_shelf_generator)
        self.generator_shelf.pack(fill="x", side="bottom")

    def _two_d_pan_start(self,event): self._two_d_pan_drag=(event.x,event.y)
    def _two_d_pan_move(self,event):
        if not self._two_d_pan_drag:return
        x,y=self._two_d_pan_drag;self._two_d_pan_x+=event.x-x;self._two_d_pan_y+=event.y-y;self._two_d_pan_drag=(event.x,event.y);self.project.view_2d={"zoom":self._two_d_zoom,"pan_x":self._two_d_pan_x,"pan_y":self._two_d_pan_y};self.update_preview()
    def _two_d_wheel(self,event):
        self._two_d_zoom=max(.25,min(4.,self._two_d_zoom*(1.12 if event.delta>0 else .89)));self.project.view_2d={"zoom":self._two_d_zoom,"pan_x":self._two_d_pan_x,"pan_y":self._two_d_pan_y};self.update_preview();return "break"

    def _bind_shortcuts(self):
        self.bind_all("<Control-s>",lambda _e:self.save_current());self.bind_all("<Control-o>",lambda _e:self.open_project());self.bind_all("<Control-n>",lambda _e:self.new_project());self.bind_all("<Control-z>",lambda _e:self.undo());self.bind_all("<Control-Shift-Z>",lambda _e:self.redo());self.bind_all("<Control-e>",lambda _e:self.export_stl());self.bind_all("<Delete>",lambda _e:self.delete_reference2d_selected());self.bind_all("<Control-a>",lambda _e:self.select_all_reference2d());self.bind_all("<Control-d>",lambda _e:self.duplicate_reference2d_selected());self.bind_all("<Control-g>",lambda _e:self.group_reference2d_selected());self.bind_all("<Escape>",lambda _e:self.cancel_interaction())

    def cancel_interaction(self):
        self._drawing_points=[]
        self._reference2d_box_start = None
        self._reference2d_drag_id = None; self._reference2d_drag_ids = []; self._reference2d_drag_last = None
        if getattr(self, "_reference2d_box_item", None) is not None and hasattr(self, "canvas"):
            self.canvas.delete(self._reference2d_box_item); self._reference2d_box_item = None
        if hasattr(self, "canvas"): self.canvas.configure(cursor="crosshair")
        self.status.set("已取消当前操作。")

    @staticmethod
    def _unit_factor(unit: str) -> float:
        return {"mm":1.0,"cm":10.0,"inch":25.4}.get(unit,1.0)

    def change_units(self,_event=None):
        """只转换 UI 显示值；PatternSettings 和 STL 工作单持续以 mm 保存。"""
        new=self.vars["units"].get();old=self._unit_display
        if new==old:return
        factor=self._unit_factor(old)/self._unit_factor(new)
        for name in self.GEOMETRIC_VARS:
            if name not in self.vars:continue
            try:self.vars[name].set(f"{float(self.vars[name].get())*factor:.4g}")
            except ValueError:continue
        self._unit_display=new;self.status.set(f"已切换到 {new} 显示；内部建模与 STL 始终使用 mm。");self.schedule_preview(80)

    def settings_from_ui(self) -> PatternSettings:
        try:
            return self._extended_settings()
        except ValueError as error: raise ValueError("参数格式不正确。") from error

    def _extended_settings(self) -> PatternSettings:
        data={name:getattr(PatternSettings(),name) for name in PatternSettings.__dataclass_fields__}
        for name in ("count","seed","grid_columns","grid_rows","image_levels","noise_octaves"):data[name]=int(float(self.vars[name].get()))
        for name in ("length","width","dot_radius","length_random","dot_random","noise_strength","noise_scale","rotation","offset","scale","spacing","field_spacing","dot_size","line_width","field_scale","gradient_strength","field_contrast","field_threshold","feather","field_blur","field_rotation","field_noise","smooth_noise","row_spacing","column_spacing","min_size","max_size","field_density","field_offset_x","field_offset_y","image_gamma","mask_strength","edge_softness","gradient_center_x","gradient_center_y","random_strength","random_size","random_rotation","random_position","random_density","noise_frequency","noise_offset","distortion_wave","distortion_twist","distortion_bend","distortion_curl","distortion_flow","attraction","repulsion","element_aspect","three_d_thickness","three_d_roundness","three_d_blend","three_d_min_feature","reference_strength","reference_structure_preservation","reference_creative_variation","reference_void_size","reference_void_rotation","reference_void_feather","reference_corner_emphasis","reference_vortex","reference_center_x","reference_center_y","reference_warp_radius","reference_corner_density","reference_size_gradient","reference_density_gradient","reference_match_score","reference_opacity","target_width_mm"):data[name]=float(self.vars[name].get())
        for name in ("contour_type","element_type","distribution","direction","preview_quality","units","active_generator","field_element","field_shape","gradient_mode","mask_type","reference_image","gradient_curve","element_fill","three_d_quality","reference_compare_mode"):data[name]=self.vars[name].get()
        # 所有长度从当前显示单位转换为唯一的内部 mm 世界单位。
        factor=self._unit_factor(data["units"])
        for name in self.GEOMETRIC_VARS:
            if name in data:data[name]*=factor
        data["field_generator"]=self.FIELD_GENERATORS.get(self.vars["field_generator"].get(),self.vars["field_generator"].get());data["image_invert"]=bool(self.vars["image_invert"].get());data["reference_rebuild_enabled"]=bool(self.vars["reference_rebuild_enabled"].get());data["reference_use_extracted_elements"]=bool(self.vars["reference_use_extracted_elements"].get());data["reference_elements"]=self.project.settings.reference_elements
        data["count"]=max(10,min(1000,data["count"]));data["field_spacing"]=max(1.2,data["field_spacing"]);data["min_size"]=max(.05,data["min_size"]);data["max_size"]=max(data["min_size"],data["max_size"]);data["field_density"]=max(0,min(100,data["field_density"]));data["noise_octaves"]=max(1,min(6,data["noise_octaves"]));data["three_d_thickness"]=max(.1,data["three_d_thickness"]);data["three_d_min_feature"]=max(.1,data["three_d_min_feature"])
        return PatternSettings(**data)

    def _restore_reference2d_document(self):
        self._reference2d_document = None
        self._editable_pattern_document = None
        editable_payload = getattr(self.project, "editable_pattern_document", None)
        if isinstance(editable_payload, dict):
            try:
                self._editable_pattern_document = EditablePatternDocument.from_dict(editable_payload)
            except (KeyError, TypeError, ValueError) as error:
                self.status.set(f"EditablePatternDocument 恢复失败：{error}")
        payload = getattr(self.project, "reference2d_document", None)
        if not isinstance(payload, dict):
            if hasattr(self, "reference2d_selection_info"):
                count = len(self._editable_pattern_document.elements) if self._editable_pattern_document else 0
                self.reference2d_selection_info.set(f"已恢复 {count} 个可编辑元素；点击画布可选中、拖动或删除。" if count else "导入点阵图后，可在 2D 画布中点击、拖动真实元素。")
            self._sync_reference2d_rule_controls()
            return
        try:
            self._reference2d_document = Document2D.from_dict(payload)
            if self._editable_pattern_document is None:
                width = self._reference2d_document.reference_layer.width; height = self._reference2d_document.reference_layer.height
                from .reference2d.editable_document import EditableElement
                self._editable_pattern_document = EditablePatternDocument(
                    canvas={"width": 100.0, "height": 100.0, "units": "percent", "source_width_px": width, "source_height_px": height},
                    reference=self._reference2d_document.reference_layer.to_dict(),
                    generator={"mode": "direct", "base": None, "score": 0.0},
                    elements=[EditableElement(id=dot.id, primitive_type="circle" if abs(dot.radius_x-dot.radius_y) < .5 else "ellipse", x=dot.x/width*100.0, y=dot.y/height*100.0, width=dot.radius_x/width*200.0, height=dot.radius_y/height*200.0, radius=(dot.radius_x+dot.radius_y)/width*100.0, rotation=dot.rotation, confidence=dot.source_confidence) for dot in self._reference2d_document.geometry_layer.dots],
                    metadata={"migrated_from": "xiaomang-reference2d-poc"},
                )
            count = len(self._reference2d_document.geometry_layer.dots)
            if hasattr(self, "reference2d_selection_info"):
                self.reference2d_selection_info.set(f"已恢复 {count} 个真实 DOT；点击画布可选中并编辑。")
            self._sync_reference2d_rule_controls()
        except (KeyError, TypeError, ValueError) as error:
            self.status.set(f"Reference2D 几何恢复失败：{error}")

    def _set_ui_from_project(self):
        self._unit_display=self.project.settings.units
        for name,value in self.project.settings.to_dict().items():
            if name=="field_generator":value=next((label for label,key in self.FIELD_GENERATORS.items() if key==value),value)
            if name in self.GEOMETRIC_VARS:value=float(value)/self._unit_factor(self._unit_display)
            if name in self.vars:self.vars[name].set(value if isinstance(self.vars[name],tk.BooleanVar) else str(value))
        self._two_d_zoom=float(self.project.view_2d.get("zoom",1.0));self._two_d_pan_x=float(self.project.view_2d.get("pan_x",0.0));self._two_d_pan_y=float(self.project.view_2d.get("pan_y",0.0));self._restore_reference2d_document()

    def _sync_reference2d_project(self):
        self.project.reference2d_document=self._reference2d_document.to_dict() if self._reference2d_document is not None else None
        self.project.editable_pattern_document=self._editable_pattern_document.to_dict() if self._editable_pattern_document is not None else None

    def snapshot(self) -> dict:
        self.project.settings=self.settings_from_ui();self.project.view_2d={"zoom":self._two_d_zoom,"pan_x":self._two_d_pan_x,"pan_y":self._two_d_pan_y};self._sync_reference2d_project();return self.project.to_dict()
    def remember(self): self.history.push(self.snapshot())
    def restore(self,snapshot): self.project=Project.from_dict(snapshot);self._set_ui_from_project();self._sample_cache.clear();self._field_cache.clear();self.update_preview()
    def undo(self):
        try:
            item=self.history.undo(self.snapshot())
            if item:self.restore(item);self.status.set("已撤销。")
        except ValueError: pass
    def redo(self):
        try:
            item=self.history.redo(self.snapshot())
            if item:self.restore(item);self.status.set("已重做。")
        except ValueError: pass

    def on_choice(self,_event=None):
        if self.vars["contour_type"].get() in self.SHAPES and self.project.contour_source=="builtin": self._load_builtin(self.vars["contour_type"].get(),remember=True)
        else: self.remember();self.schedule_preview()
    def activate_field_generator(self,_event=None):
        self.vars["active_generator"].set("field");self.remember();self.schedule_preview()
    def _on_tab_changed(self,_event=None):
        if self.control_notebook.nametowidget(self.control_notebook.select()) is self.field_tab:
            self.vars["active_generator"].set("field");self.schedule_preview()
    def on_slider(self):
        self._dragging=True
        if self._interaction_after_id:self.after_cancel(self._interaction_after_id)
        # 约 30 FPS 的交互节流：只生成快速工作单，不做最终 STL 检查。
        self._interaction_after_id=self.after(33,self.update_preview)
        self.schedule_preview(140)
    def on_slider_release(self,_event=None):
        self._dragging=False
        if self._interaction_after_id:self.after_cancel(self._interaction_after_id);self._interaction_after_id=None
        self.remember();self.schedule_preview(120)
    def on_entry(self,_event=None): self.remember();self.schedule_preview(120)
    def schedule_preview(self,delay=120):
        if self._after_id:self.after_cancel(self._after_id)
        self._after_id=self.after(delay,self.update_preview)

    def _preview_canvas_size(self):
        """返回已完成布局的画布尺寸，避免把启动时 1×1 写成永久预览。"""
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if width >= 32 and height >= 32:
            return width, height
        # Tk 在窗口首次映射、Notebook 切页或 PanedWindow 重排期间可能暂时报告
        # 1×1。此时不要生成 1×1 PhotoImage；等布局完成后再重跑同一条管线。
        if self._layout_retry_id is None:
            self._layout_retry_id = self.after(80, self._retry_preview_after_layout)
        return None

    def _retry_preview_after_layout(self):
        self._layout_retry_id = None
        if self.winfo_exists():
            self.update_preview()
    def _load_builtin(self,kind,remember=True):
        if remember:self.remember()
        try:self.project.contour=builtin_contour(kind,int(float(self.vars["seed"].get())));self.project.contour_source="builtin";self._sample_cache.clear();self.update_preview()
        except ValueError:pass
    def _preview_count(self,s):
        if self._dragging:return min(80,s.count)
        return min(s.count,{"快速":80,"标准":250,"高质量":s.count}.get(s.preview_quality,250))

    def update_preview(self):
        self._after_id=None
        try:
            settings=self.settings_from_ui()
            previous_width=float(getattr(self.project.settings,"target_width_mm",settings.target_width_mm) or settings.target_width_mm)
            if abs(previous_width-settings.target_width_mm)>1e-6 and self.project.height_controls:
                factor=settings.target_width_mm/max(.001,previous_width)
                for control in self.project.height_controls:
                    for key in ("x","y","radius"):
                        if key in control:control[key]=round(float(control[key])*factor,5)
            self.project.settings=settings
            if settings.active_generator=="field":
                # Reference Reconstruction 的正式 2D 路径：Canvas 仅消费已经
                # 物化的 EditablePatternDocument，绝不再由 Raster 或旧 Generator
                # 重新画一张相似图。规则变化必须显式调用 document.rebuild()。
                if self._editable_pattern_document is not None:
                    self.draw_field_preview([],settings)
                    self._refresh_reference_stack(settings)
                    count=len(self._editable_pattern_document.elements)
                    mode="参数化模式" if self._editable_pattern_document.mode=="parametric" else "直接元素模式"
                    self.preview_info.set(f"{count} 个真实可编辑元素 · {mode}")
                    self.status.set("参考图重建已由 EditablePatternDocument 渲染。")
                    self._update_editable_dimension_status(settings)
                    return
                limit=80 if self._dragging else {"快速":196,"标准":1000,"高质量":None}.get(settings.preview_quality,1000)
                # PatternSettings 包含 reference_elements（list[dict]）。直接将
                # ``to_dict().items()`` 放进缓存 key 会在“分析参考图 → 应用”后
                # 触发 unhashable type: 'list'，update_preview 随即清空 Canvas，
                # 用户看到的就是导入图片和重建结果都消失。用稳定 JSON 快照作为
                # key，既保留所有参数变化的失效语义，也支持可编辑元素工作单。
                key=(json.dumps(settings.to_dict(), ensure_ascii=False, sort_keys=True, default=str),limit)
                items=self._field_cache.get(key)
                if items is None:
                    items=generate_field(settings,preview_limit=limit);self._field_cache[key]=items
                    if len(self._field_cache)>20:self._field_cache.pop(next(iter(self._field_cache)))
                self.draw_field_preview(items,settings);self._refresh_reference_stack(settings);display_count=len(self._editable_pattern_document.elements) if self._editable_pattern_document is not None else len(items);label="可编辑元素" if self._editable_pattern_document is not None else "点线面元素";self.preview_info.set(f"{display_count} 个{label} · {settings.field_generator} · {'交互预览' if self._dragging else '标准预览'}");self.status.set("点线面生成器已实时更新。 ");self._update_dimension_status(settings,items);return
            count=self._preview_count(settings);key=(tuple((round(x,5),round(y,5)) for x,y in self.project.contour),count)
            if key not in self._sample_cache:self._sample_cache[key]=sample_evenly(clean_contour(self.project.contour),count)
            items=generate_items(self.project.contour,settings,preview_count=count,cached_samples=self._sample_cache[key]);self.draw_preview(self.project.contour,items,settings);self.preview_info.set(f"{len(items)} / {settings.count} 个元素 · {settings.units}");self.status.set(self.t("ready"));self._update_dimension_status(settings,items)
        except Exception as error:
            self.canvas.delete("all");self.status.set(self.t("invalid",error=str(error)))

    def _update_editable_dimension_status(self, settings):
        document=self._editable_pattern_document
        if document is None or not document.elements:
            self.dimension_status.set("0 个可编辑元素 · 自动保存：已开启")
            return
        left=min(item.x-item.width/2 for item in document.elements); right=max(item.x+item.width/2 for item in document.elements)
        top=min(item.y-item.height/2 for item in document.elements); bottom=max(item.y+item.height/2 for item in document.elements)
        scale=float(settings.target_width_mm)/100.0
        self.dimension_status.set(f"{(right-left)*scale:.2f} × {(bottom-top)*scale:.2f} mm · {len(document.elements)} 个真实元素 · {document.mode} · 自动保存：已开启")

    def _update_dimension_status(self, settings, items):
        try:
            raw=[{"kind":item.kind,"x":item.x,"y":item.y,"size":item.size,"x2":item.x2,"y2":item.y2} for item in items]
            width,height,depth=self._physical_dimensions(scale_primitives_to_width(raw,settings.target_width_mm),settings.three_d_thickness)
            score=f"{settings.reference_match_score:.0f}%" if settings.reference_image else "—"
            self.dimension_status.set(f"{width:.2f} × {height:.2f} × {depth:.2f} mm · {len(items)} 个元素 · 参考匹配度：{score} · 自动保存：已开启")
        except Exception:pass

    def _final_primitives(self, settings):
        """把当前二维几何转为唯一的最终制造工作单，不创建 Preview Mesh。"""
        if self._editable_pattern_document is not None:
            primitives = document_to_primitives(self._editable_pattern_document)
        else:
            primitives = self._blender_primitives(settings)
        normalized = scale_primitives_to_width(primitives, settings.target_width_mm)
        return apply_height_field(normalized, settings.three_d_thickness, self.project.height_controls)

    @staticmethod
    def _physical_dimensions(primitives, thickness):
        min_x,min_y,max_x,max_y=primitives_bounds(primitives)
        depth=max([float(item.get("height", thickness)) for item in primitives] or [float(thickness)])
        return max(0.,max_x-min_x),max(0.,max_y-min_y),max(.1,depth)

    def _temporary_final_stl_path(self) -> str:
        folder = Path(tempfile.gettempdir()) / "xiaomang_final_models"
        folder.mkdir(parents=True, exist_ok=True)
        handle = tempfile.NamedTemporaryFile(prefix="final_", suffix=".stl", dir=folder, delete=False)
        handle.close(); Path(handle.name).unlink(missing_ok=True)
        return handle.name

    def generate_3d_model(self):
        """后台构建最终制造模型；界面始终保留在 Editable 2D Canvas。"""
        try:
            settings=self.settings_from_ui();self.project.settings=settings;self.project.view_2d={"zoom":self._two_d_zoom,"pan_x":self._two_d_pan_x,"pan_y":self._two_d_pan_y}
            primitives=self._final_primitives(settings)
            output=self._temporary_final_stl_path()
        except Exception as error:
            messagebox.showerror("无法生成最终模型",str(error),parent=self);return
        self._start_final_model_build(primitives, output, settings, show_dialog=False)

    def _start_final_model_build(self, primitives, output, settings, *, show_dialog: bool):
        self.status.set(f"正在后台生成最终制造模型并执行制造检查（{len(primitives)} 个元素）…");self.update_idletasks()
        def worker():
            try:
                pipeline=run_project_stl_pipeline(primitives,output,settings=settings);result=pipeline.blender_result
                self.after(0,lambda:self._final_model_finished(result,result.audit,Path(pipeline.handoff_path),show_dialog=show_dialog))
            except Exception as error:
                self.after(0,lambda:self._final_model_failed(str(error),show_dialog=show_dialog))
        threading.Thread(target=worker,name="XiaomangFinalModelWorker",daemon=True).start()

    def _final_model_finished(self,result,audit,report,*,show_dialog: bool):
        self._final_model_result=result
        # 可选显示适配器只接收最终模型产物；NullPreviewProvider 默认不显示任何内容。
        self.preview_provider.load_model(result.stl_path)
        width,height,depth=self._physical_dimensions(self._final_primitives(self.project.settings),self.project.settings.three_d_thickness)
        backend="本地 SDF" if result.blender_path=="native" else "Blender"
        message=(f"模型已生成 · {backend}\n尺寸：{width:.2f} × {height:.2f} × {depth:.2f} mm\n"
                 f"三角面：{result.triangles:,}\n组件：{audit.get('connected_components', 0)}\n"
                 f"Watertight：{'是' if audit.get('watertight') else '否'}\n制造检查：{'通过' if audit.get('watertight') and int(audit.get('connected_components',0))==1 else '未通过'}")
        self.dimension_status.set(message.replace("\n", " · "))
        self.status.set("最终制造模型已生成；2D 设计仍可继续编辑。")
        if show_dialog:
            messagebox.showinfo("STL 已成功生成",message+f"\n\nSTL：\n{result.stl_path}\n\n检查报告：\n{report}",parent=self)

    def _final_model_failed(self,error,*,show_dialog: bool):
        self.status.set("最终模型生成失败。")
        if show_dialog:
            messagebox.showerror("最终模型生成失败",error,parent=self)
        else:
            messagebox.showerror("无法生成最终模型",error,parent=self)

    def _reference_layer(self, settings, canvas_width, canvas_height, scale, ox, oy):
        """生成保持比例的参考图层，并让 PhotoImage 由实例持有，避免 Canvas 变空。"""
        path = str(getattr(settings, "reference_image", "") or "").strip()
        if not path or not Path(path).is_file() or not getattr(self, "reference_visible", tk.BooleanVar(value=True)).get():
            return None
        try:
            source_path = Path(path).resolve(); stat = source_path.stat()
            box_w, box_h = max(1, int(100 * scale)), max(1, int(100 * scale))
            mode = str(getattr(settings, "reference_compare_mode", "原图"))
            opacity = 1.0 if mode in ("原图", "左右对比") else max(0.0, min(1.0, float(getattr(settings, "reference_opacity", 45.0)) / 100.0))
            key = (str(source_path), stat.st_mtime_ns, box_w, box_h, round(opacity, 3))
            cached = self._reference_preview_cache.get(key)
            if cached is None:
                image = Image.open(source_path).convert("RGBA")
                ratio = min(box_w / max(1, image.width), box_h / max(1, image.height))
                size = (max(1, int(image.width * ratio)), max(1, int(image.height * ratio)))
                image = image.resize(size, Image.Resampling.LANCZOS)
                if opacity < 1.0:
                    alpha = image.getchannel("A").point(lambda value: int(value * opacity))
                    image.putalpha(alpha)
                cached = (image, size)
                self._reference_preview_cache[key] = cached
                if len(self._reference_preview_cache) > 12:
                    self._reference_preview_cache.pop(next(iter(self._reference_preview_cache)))
            image, (image_w, image_h) = cached
            layer = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
            px = int(ox + (box_w - image_w) / 2); py = int(oy + (box_h - image_h) / 2)
            px = max(-image_w + 1, min(canvas_width - 1, px)); py = max(-image_h + 1, min(canvas_height - 1, py))
            layer.alpha_composite(image, (px, py))
            return layer
        except (OSError, ValueError, TypeError):
            return None

    def _show_reference_on_canvas(self, settings, canvas_width, canvas_height, scale, ox, oy):
        layer = self._reference_layer(settings, canvas_width, canvas_height, scale, ox, oy)
        if layer is None or str(getattr(settings, "reference_compare_mode", "重建结果")) == "重建结果":
            return
        self._reference_photo = ImageTk.PhotoImage(layer)
        self.canvas.create_image(0, 0, anchor="nw", image=self._reference_photo)

    def _reference_pane(self, settings, pane_width, canvas_height):
        """将原始参考文件独立置入左右对比的左栏。

        这里刻意不复用 ``_reference_layer``：后者会按照参数化图形的世界坐标
        缩放并定位图片，直接再裁成半幅时会把中心内容切开。左右对比必须把原图
        当作一张独立参考图，在自己的画幅中等比居中，才能稳定看见完整图片。
        """
        path = str(getattr(settings, "reference_image", "") or "").strip()
        if not path or not Path(path).is_file():
            return None
        try:
            source_path = Path(path).resolve(); stat = source_path.stat()
            key = (str(source_path), stat.st_mtime_ns, max(1, pane_width), max(1, canvas_height))
            cached = self._reference_pane_cache.get(key)
            if cached is not None:
                return cached.copy()
            with Image.open(source_path) as opened:
                source = opened.convert("RGBA")
            pane = Image.new("RGBA", (max(1, pane_width), max(1, canvas_height)), (251, 252, 253, 255))
            fitted = ImageOps.contain(
                source,
                (max(1, pane.width - 24), max(1, pane.height - 24)),
                Image.Resampling.LANCZOS,
            )
            pane.alpha_composite(fitted, ((pane.width - fitted.width) // 2, (pane.height - fitted.height) // 2))
            self._reference_pane_cache[key] = pane.copy()
            if len(self._reference_pane_cache) > 12:
                self._reference_pane_cache.pop(next(iter(self._reference_pane_cache)))
            return pane
        except (OSError, ValueError, TypeError):
            return None

    def _compose_reference_preview(self, base, settings, canvas_width, canvas_height, scale, ox, oy):
        """把参考图和参数化图形合成为一个明确的 2D 预览层。

        旧实现把参考图作为最后一个 Canvas item 直接盖在 Geometry Layer 上，
        导致“左右对比”也会遮住生成结果，看起来像 2D 预览没有运行。现在四种
        模式都在同一张 RGBA 位图中合成，再一次性显示，避免层级和 PhotoImage
        引用问题。
        """
        mode = str(getattr(settings, "reference_compare_mode", "重建结果"))
        if mode == "重建结果" or not getattr(self, "reference_visible", tk.BooleanVar(value=True)).get():
            return base
        base_rgba = base.convert("RGBA")
        background = Image.new("RGBA", (canvas_width, canvas_height), (251, 252, 253, 255))
        if mode == "左右对比":
            # 左栏使用原始文件的独立画幅，右栏使用完整参数化构图。两者都不能
            # 从同一张全画布图片裁切，否则中心元素会被分割线切开。
            split = max(1, canvas_width // 2)
            def fit(source, width):
                fitted = ImageOps.contain(source, (width, canvas_height), Image.Resampling.LANCZOS)
                pane = Image.new("RGBA", (width, canvas_height), (251, 252, 253, 255))
                pane.alpha_composite(fitted, ((width - fitted.width) // 2, (canvas_height - fitted.height) // 2))
                return pane
            left = self._reference_pane(settings, split, canvas_height)
            if left is None:
                return base
            right = fit(base_rgba, canvas_width - split)
            result = Image.new("RGBA", (canvas_width, canvas_height), (251, 252, 253, 255))
            result.alpha_composite(left, (0, 0)); result.alpha_composite(right, (split, 0))
            ImageDraw.Draw(result).line((split, 0, split, canvas_height), fill="#7d8791", width=2)
            return result
        overlay = self._reference_layer(settings, canvas_width, canvas_height, scale, ox, oy)
        if overlay is None:
            return base
        reference = Image.alpha_composite(background, overlay)
        if mode == "原图":
            return reference
        opacity = max(0.0, min(1.0, float(getattr(settings, "reference_opacity", 45.0)) / 100.0))
        return Image.blend(base_rgba, Image.alpha_composite(base_rgba, overlay), opacity)

    def draw_preview(self,contour,items,settings):
        size=self._preview_canvas_size()
        if size is None:return
        self.canvas.delete("all");w,h=size;allp=contour+[p for i in items for p in (i.start,i.end)];minx,miny=min(x for x,y in allp),min(y for x,y in allp);maxx,maxy=max(x for x,y in allp),max(y for x,y in allp);span=max(maxx-minx,maxy-miny,1);scale=min((w-70)/span,(h-70)/span)*self._two_d_zoom;ox=(w-(maxx-minx)*scale)/2-minx*scale+self._two_d_pan_x;oy=(h-(maxy-miny)*scale)/2-miny*scale+self._two_d_pan_y
        def tr(p):return p[0]*scale+ox,p[1]*scale+oy
        self._last_transform=(scale,ox,oy)
        if len(items)>180 or (settings.reference_image and settings.reference_compare_mode!="重建结果" and self.reference_visible.get()):
            image=Image.new("RGB",(w,h),COLORS["canvas"]);draw=ImageDraw.Draw(image)
            draw.line([tr(point) for point in contour+[contour[0]]],fill="#16181d",width=max(1,round(settings.width*scale)),joint="curve")
            for item in items:
                if settings.element_type in ("线条 + 圆点","直线"):draw.line([tr(item.start),tr(item.end)],fill="#111111",width=max(1,round(item.width*scale)))
                if settings.element_type in ("线条 + 圆点","圆点","珠子"):
                    x,y=tr(item.end);r=max(1,item.radius*scale*(1.3 if settings.element_type=="珠子" else 1));draw.ellipse((x-r,y-r,x+r,y+r),fill="#111111")
                polygon=element_polygon(item,settings.element_type,self.project.custom_element)
                if polygon:draw.polygon([tr(point) for point in polygon],fill="#111111")
            image=self._compose_reference_preview(image,settings,w,h,scale,ox,oy)
            self._preview_photo=ImageTk.PhotoImage(image);self.canvas.create_image(0,0,anchor="nw",image=self._preview_photo);return
        self.canvas.create_line(*[coordinate for point in contour+[contour[0]] for coordinate in tr(point)],fill="#16181d",width=max(1,round(settings.width*scale)),smooth=True)
        for item in items:
            if settings.element_type in ("线条 + 圆点","直线"):self.canvas.create_line(*tr(item.start),*tr(item.end),fill="#111",width=max(1,round(item.width*scale)),capstyle="round")
            if settings.element_type in ("线条 + 圆点","圆点","珠子"):
                x,y=tr(item.end);r=max(1,item.radius*scale*(1.3 if settings.element_type=="珠子" else 1));self.canvas.create_oval(x-r,y-r,x+r,y+r,fill="#111",outline="")
            polygon=element_polygon(item,settings.element_type,self.project.custom_element)
            if polygon:self.canvas.create_polygon(*[coordinate for point in polygon for coordinate in tr(point)],fill="#111",outline="")

    def _reference2d_world_dots(self):
        """将 POC 的源图像素坐标映射到现有 0–100 设计空间。"""
        document = self._reference2d_document
        if document is None or not document.geometry_layer.dots:
            return ()
        width=max(1.0,float(document.reference_layer.width));height=max(1.0,float(document.reference_layer.height))
        return tuple((dot, dot.x/width*100.0, dot.y/height*100.0, dot.radius_x/width*100.0, dot.radius_y/height*100.0) for dot in document.geometry_layer.dots)

    @staticmethod
    def _rotated_ellipse_points(cx,cy,rx,ry,rotation,steps=24):
        angle=math.radians(rotation);cosine,sine=math.cos(angle),math.sin(angle)
        return [(cx+rx*math.cos(2*math.pi*i/steps)*cosine-ry*math.sin(2*math.pi*i/steps)*sine,cy+rx*math.cos(2*math.pi*i/steps)*sine+ry*math.sin(2*math.pi*i/steps)*cosine) for i in range(steps)]

    def draw_field_preview(self,items,settings=None):
        size=self._preview_canvas_size()
        if size is None:return
        self.canvas.delete("all");w,h=size;scale=min((w-60)/100,(h-60)/100)*self._two_d_zoom;ox=(w-100*scale)/2+self._two_d_pan_x;oy=(h-100*scale)/2+self._two_d_pan_y;self._last_transform=(scale,ox,oy)
        image=Image.new("RGBA",(w,h),(251,252,253,255));draw=ImageDraw.Draw(image);draw.rectangle((ox,oy,ox+100*scale,oy+100*scale),outline="#cbd3dc",width=1)
        editable = self._editable_pattern_document.elements if self._editable_pattern_document is not None else []
        reference_dots=self._reference2d_world_dots()
        if editable:
            for element in editable:
                if not element.enabled: continue
                cx,cy=element.x*scale/100.0+ox,element.y*scale/100.0+oy
                if element.primitive_type == "line":
                    angle=math.radians(element.rotation); length=max(1.0,element.width*scale/2.0); dx,dy=math.cos(angle)*length,math.sin(angle)*length
                    draw.line((cx-dx,cy-dy,cx+dx,cy+dy),fill="#15191e",width=max(1,round(element.height*scale)))
                else:
                    points=self._rotated_ellipse_points(cx,cy,max(.6,element.width*scale/2.0),max(.6,element.height*scale/2.0),element.rotation)
                    draw.polygon(points,fill="#15191e")
            # 选择框由真实 Element ID 决定；ReferenceLayer 永远不能被选中。
            selected=set(self._editable_pattern_document.selected_ids)
            for element in editable:
                if element.id not in selected or not element.enabled: continue
                cx,cy=element.x*scale/100.0+ox,element.y*scale/100.0+oy
                if element.primitive_type == "line":
                    angle=math.radians(element.rotation); length=max(1.0,element.width*scale/2.0); dx,dy=math.cos(angle)*length,math.sin(angle)*length
                    draw.line((cx-dx,cy-dy,cx+dx,cy+dy),fill="#2f6fed",width=max(1,round(element.height*scale)+2))
                else:
                    points=self._rotated_ellipse_points(cx,cy,max(.8,element.width*scale/2.0+1.2),max(.8,element.height*scale/2.0+1.2),element.rotation)
                    draw.line(points+[points[0]],fill="#2f6fed",width=1,joint="curve")
        elif reference_dots:
            for dot,x_world,y_world,rx_world,ry_world in reference_dots:
                points=self._rotated_ellipse_points(x_world*scale+ox,y_world*scale+oy,max(.6,rx_world*scale),max(.6,ry_world*scale),dot.rotation)
                draw.polygon(points,fill=dot.fill or "#15191e")
        else:
            for item in items:
                if item.kind=="dot":
                    x,y=item.x*scale+ox,item.y*scale+oy;r=max(.6,item.size*scale);draw.ellipse((x-r,y-r,x+r,y+r),fill="#15191e")
                elif item.kind=="line":draw.line((item.x*scale+ox,item.y*scale+oy,item.x2*scale+ox,item.y2*scale+oy),fill="#15191e",width=max(1,round(item.size*scale)))
                else:draw.polygon([(p[0]*scale+ox,p[1]*scale+oy) for p in primitive_polygon(item)],fill="#15191e")
        if settings and settings.reference_image:
            image = self._compose_reference_preview(image, settings, w, h, scale, ox, oy)
        self._preview_photo=ImageTk.PhotoImage(image);self.canvas.create_image(0,0,anchor="nw",image=self._preview_photo)

    def randomize(self):
        self.remember();rng=random.SystemRandom();self.vars["seed"].set(str(rng.randint(1,2147483647)))
        if self.vars["active_generator"].get()=="field":
            self.vars["field_noise"].set(str(rng.choice([0,6,12,18,25])));self.vars["field_rotation"].set(str(rng.choice([-45,-20,0,20,45])));self.vars["dot_size"].set(str(round(rng.uniform(1.1,4.6),1)));self.update_preview();self.status.set("已生成新的点线面可复现方案。")
        else:
            self.vars["length_random"].set(str(rng.choice([8,12,18,24,30])));self.vars["noise_strength"].set(str(rng.choice([0,8,12,18,25])));self._load_builtin(self.vars["contour_type"].get(),remember=False);self.update_preview();self.status.set("已生成新的可复现方案。")

    def import_element(self):
        path=filedialog.askopenfilename(title="导入 SVG 图形元素",filetypes=[("SVG 图形","*.svg")])
        if not path:return
        try:
            points=read_contour(path);self.remember();self.project.custom_element=clean_contour(points);self.vars["element_type"].set("自定义 SVG");self.update_preview();self.status.set(f"已导入 SVG 元素：{os.path.basename(path)}")
        except Exception as error:messagebox.showerror("SVG 元素导入失败",str(error))

    def image_to_print(self):
        """面向非程序员的一键黑白图片转换入口。"""
        image_path=filedialog.askopenfilename(title="选择黑白图片",filetypes=[("图片文件","*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff"), ("所有文件","*.*")])
        if not image_path:return
        width=simpledialog.askfloat("成品宽度","成品宽度（mm）：",initialvalue=100.0,minvalue=1.0,parent=self)
        if width is None:return
        thickness=simpledialog.askfloat("打印厚度","无底板 STL 厚度（mm，建议 0.8–1.2）：",initialvalue=.8,minvalue=.1,parent=self)
        if thickness is None:return
        quality=simpledialog.askstring("最终模型质量","最终模型质量：草稿 / 标准 / 精细 / 超精细",initialvalue="标准",parent=self)
        if quality is None:return
        quality=quality.strip()
        if quality not in ("草稿","标准","精细","超精细"):
            messagebox.showerror("质量设置无效","请输入：草稿、标准、精细或超精细。",parent=self);return
        roundness=simpledialog.askfloat("表面质量","圆润程度（0=结构清晰，100=液态圆润）：",initialvalue=55.0,minvalue=0,maxvalue=100,parent=self)
        if roundness is None:return
        blend=simpledialog.askfloat("有机融合","有机融合（0=边界明确，100=液态融合）：",initialvalue=55.0,minvalue=0,maxvalue=100,parent=self)
        if blend is None:return
        output_dir=filedialog.askdirectory(title="选择导出文件夹",initialdir=os.path.dirname(image_path))
        if not output_dir:return
        target=os.path.join(output_dir,Path(image_path).stem+"_SVG_STL")
        try:
            self.status.set("正在转换图片并检查连通性…");self.update_idletasks()
            result=convert_image(image_path,target,width_mm=width,thickness_mm=thickness,quality=quality,roundness=roundness,organic_blend=blend)
            if not result.connected:
                proceed=messagebox.askyesno("检测到断开区域",f"检测到 {result.components} 个互不连接的黑色区域。\n\nSVG、预览和检测报告已生成，但默认未导出 STL。\n是否仍导出多个独立部件的 STL？",parent=self)
                if proceed: result=convert_image(image_path,target,width_mm=width,thickness_mm=thickness,allow_multipart=True,quality=quality,roundness=roundness,organic_blend=blend)
            if result.triangles:
                messagebox.showinfo("转换完成",f"已导出无底板 SVG 与高质量 STL。\n尺寸：{result.width_mm:.1f} × {result.height_mm:.1f} mm\n质量：{result.quality} · 圆润程度 {result.roundness:.0f}\n三角面：{result.triangles:,}\n\n文件夹：\n{result.output_dir}",parent=self)
                self.status.set("图片已转换为 SVG 与 STL。")
            else:self.status.set("SVG 已生成；检测到断开区域，未导出 STL。")
        except Exception as error:
            messagebox.showerror("图片转换失败",f"无法转换图片：\n{error}",parent=self);self.status.set("图片转换失败。")

    def _blender_primitives(self, settings):
        """兼容名称：把非 Editable Document 的二维规则转换为最终制造工作单。"""
        if settings.active_generator=="field":
            return [{"kind":item.kind,"x":item.x,"y":item.y,"size":item.size,"rotation":item.rotation,"x2":item.x2,"y2":item.y2} for item in generate_field(settings,preview_limit=None)]
        items=generate_items(self.project.contour,settings,preview_count=None);result=[]
        # 线性放射结构增加连续根部脊环：原本每一根放射线是独立组件，不能当作单件 STL 输出。
        if settings.element_type in ("线条 + 圆点","直线") and len(items) > 2:
            root_width=max(float(settings.width),float(settings.three_d_min_feature))
            for index,item in enumerate(items):
                next_item=items[(index+1)%len(items)]
                result.append({"kind":"line","x":item.start[0],"y":item.start[1],"x2":next_item.start[0],"y2":next_item.start[1],"size":root_width,"rotation":0})
        for item in items:
            if settings.element_type in ("线条 + 圆点","直线"):
                result.append({"kind":"line","x":item.start[0],"y":item.start[1],"x2":item.end[0],"y2":item.end[1],"size":item.width,"rotation":0})
            if settings.element_type in ("线条 + 圆点","圆点","珠子"):
                result.append({"kind":"dot","x":item.end[0],"y":item.end[1],"size":item.radius*(1.3 if settings.element_type=="珠子" else 1),"rotation":0})
            if settings.element_type in ("三角形","矩形","叶片","水滴","自定义 SVG"):
                result.append({"kind":"triangle" if settings.element_type=="三角形" else "square","x":item.end[0],"y":item.end[1],"size":item.radius,"rotation":0})
        return result

    def export_stl(self):
        """软件内一键最终制造：默认使用本地 SDF 后端，不要求安装 Blender。"""
        try:
            settings=self.settings_from_ui();primitives=self._final_primitives(settings)
        except Exception as error: messagebox.showerror("无法准备 3D 模型",str(error),parent=self);return
        width,height,depth=self._physical_dimensions(primitives,settings.three_d_thickness)
        if not messagebox.askokcancel("确认 STL 尺寸",f"当前最终模型尺寸：\n\n宽：{width:.2f} mm\n高：{height:.2f} mm\n厚：{depth:.2f} mm\n单位：mm\n\n将按此尺寸生成 STL，是否继续？",parent=self):return
        output=filedialog.asksaveasfilename(title="保存最终 STL",defaultextension=".stl",initialfile="小芒造物_最终模型.stl",filetypes=[("STL 三维模型","*.stl")])
        if not output:return
        self.project.settings=settings
        self._start_final_model_build(primitives, output, settings, show_dialog=True)

    def generate_blender_stl(self):
        """保留旧入口的兼容别名。"""
        self.export_stl()

    def _refresh_reference_stack(self, settings):
        if not hasattr(self,"reference_stack_text"):
            return
        document=self._editable_pattern_document
        if document is not None:
            if document.mode=="direct":
                self.reference_stack_text.set(f"基础：Direct Element Mode\n真实元素：{len(document.elements)}\n未强制猜测 Generator")
            else:
                stack=" → ".join(str(item.get("name")) for item in document.modifiers) or "无"
                self.reference_stack_text.set(f"基础：{document.generator.get('base')}\n修改器：{stack}\n局部覆盖：{len(document.overrides)} 个")
            return
        if not settings.reference_rebuild_enabled:
            self.reference_stack_text.set("基础生成器：未启用参考重建\n修改器：可导入参考图后自动建立")
            return
        generator=next((label for label,key in self.FIELD_GENERATORS.items() if key==settings.field_generator),settings.field_generator)
        stack=["① 尺寸 / 密度场"]
        if settings.reference_corner_emphasis>1:stack.append("② 四角强调")
        if settings.reference_vortex or settings.distortion_twist:stack.append("③ 中心扭曲 / 旋转场")
        if settings.reference_void_size>1:stack.append("④ 旋转方形留白")
        if settings.mask_type!="无 Mask":stack.append("⑤ 外部 Mask")
        self.reference_stack_text.set(f"基础生成器：{generator}\n修改器：{'  '.join(stack)}\n当前规则匹配度：{settings.reference_match_score:.0f}%")

    def optimize_reference_match(self):
        """只重新拟合并物化当前文档；不会回到 Raster → 猜 Generator 的旧路径。"""
        document=self._editable_pattern_document
        if document is None:
            messagebox.showinfo("重新拟合规则","请先导入一张点阵、半调或几何参考图。",parent=self);return
        if document.mode=="direct":
            messagebox.showinfo("重新拟合规则","当前图像未达到可靠的参数化拟合阈值，已保留 Direct Element Mode。\n\n所有检测元素都可继续直接编辑；不会为了显示 Generator 而伪造规则。",parent=self);return
        self._sync_reference2d_rule_controls();self.rebuild_editable_pattern()

    def hide_reference_image(self):
        """强制进入只看重建结果模式，验证生成结果不依赖参考位图。"""
        self.vars["reference_compare_mode"].set("重建结果");self.schedule_preview(40);self.status.set("已隐藏参考原图；当前预览只显示参数化生成结果。")

    def export_reference_debug(self):
        path = self.vars["reference_image"].get().strip()
        if not path or not Path(path).is_file():
            messagebox.showinfo("检测调试图", "请先导入一张点阵参考图。", parent=self); return
        output = filedialog.asksaveasfilename(title="保存检测调试图", defaultextension=".png", initialfile="reference_detection_debug.png", filetypes=[("PNG 图片", "*.png")])
        if not output: return
        try:
            from .reference2d.debug_visualization import render_debug
            debug = {}; result = ReferenceReconstructionService().analyze(path, target_width_mm=self.project.settings.target_width_mm, debug=debug)
            render_debug(result.preprocessed, result.features, debug, output)
            self.status.set(f"检测调试图已保存：{output}")
            messagebox.showinfo("检测调试图", f"已输出原图、中心点、半径和 Watershed 检测结果。\n\n{output}", parent=self)
        except Exception as error:
            messagebox.showerror("检测调试图失败", str(error), parent=self)

    def _ingest_reference2d(self, path):
        """把图片送入 Reference Reconstruction：检测优先，拟合失败也保留元素。"""
        if Path(path).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}:
            return None
        result = ReferenceReconstructionService().analyze(path, target_width_mm=self.project.settings.target_width_mm)
        if not result.editable_document or not result.editable_document.elements:
            raise ValueError("未检测到可编辑的点、线或面元素。")
        self._editable_pattern_document = result.editable_document
        # 旧 Canvas 交互仍使用 POC DOT 适配层；正式项目同时保存完整 EditablePatternDocument。
        width = float(result.source.width_px); height = float(result.source.height_px)
        dots = [DotObject(id=item.id, x=item.x / 100.0 * width, y=item.y / 100.0 * height,
                          radius_x=item.width / 200.0 * width, radius_y=item.height / 200.0 * height,
                          rotation=item.rotation, fill="#15191e", source_confidence=item.confidence)
                for item in self._editable_pattern_document.elements if item.primitive_type in ("circle", "ellipse", "dot")]
        self._reference2d_document = Document2D(ReferenceLayer(str(Path(path).resolve()), width, height), GeometryLayer(dots))
        self._sync_reference2d_project()
        # 检测出的真实元素作为 GeometryLayer 的基础层；用户仍可切回现有 Generator。
        self.vars["active_generator"].set("field")
        self.vars["field_generator"].set("规则点阵" if result.generator.get("mode") == "parametric" else "半调点阵")
        self.vars["reference_use_extracted_elements"].set(bool(self._editable_pattern_document.elements))
        self._field_cache.clear()
        self._sync_reference2d_rule_controls()
        if hasattr(self, "reference2d_selection_info"):
            mode = "参数化模式" if self._editable_pattern_document.mode == "parametric" else "直接元素模式"
            self.reference2d_selection_info.set(f"已检测 {len(self._editable_pattern_document.elements)} 个真实元素 · {mode}；点击画布可选中、拖动或删除。")
        return result

    def analyze_reference_image(self):
        path=filedialog.askopenfilename(title="选择灵感参考图",filetypes=[("图片或 SVG","*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.svg"),("所有文件","*.*")])
        if not path:return
        if path.lower().endswith(".svg"):
            messagebox.showinfo("分析提示","SVG 可直接作为轮廓或外围元素导入。复杂 SVG 的生成规律分析将在 AI 设计实验室模块中扩展。",parent=self);return
        # 固定工作流：Reference → Detection → Editable Elements → Fitting。
        # 不再先让旧分析器猜 Generator，再绘制一张相似位图。
        self.vars["reference_image"].set(str(Path(path).resolve()))
        self.reference_visible.set(True)
        self.vars["reference_compare_mode"].set("原图")
        try:
            self.remember()
            result=self._ingest_reference2d(path)
            key=(str(Path(path).resolve()),Path(path).stat().st_mtime_ns); self._analysis_cache[key]=result
            self.vars["reference_compare_mode"].set("左右对比")
            self.reference_visible.set(True)
            self.control_notebook.select(self.field_tab)
            self.update_idletasks(); self.update_preview(); self.canvas.update_idletasks(); self.schedule_preview(40)
            details="\n".join(f"{key}：{value}" for key,value in result.details.items())
            mode="参数化模式" if result.editable_document.mode=="parametric" else "直接元素模式"
            messagebox.showinfo("参考图 → 可编辑二维元素",f"已完成 Stage A：检测到 {len(result.editable_document.elements)} 个真实元素。\n当前：{mode}\n\n{details}\n\n参考图只在 Reference Layer；隐藏它后，Geometry Layer 仍可单独选择、移动、缩放、旋转、删除、复制和保存。",parent=self)
        except (OSError, RuntimeError, ValueError) as error:
            self._reference2d_document = None
            self._editable_pattern_document = None
            self.project.reference2d_document = None
            self.project.editable_pattern_document = None
            self.update_idletasks(); self.update_preview()
            messagebox.showwarning("未检测到可编辑元素",f"参考图已载入 Reference Layer，但没有检测到本阶段支持的 DOT / HALFTONE / 几何点阵元素。\n\n{error}",parent=self)

    def show_generators(self):
        window=tk.Toplevel(self);window.title("生成器库 · 小芒造物");window.geometry("520x440");ttk.Label(window,text="Generator Library",padding=12,font=("Microsoft YaHei UI",12,"bold")).pack(anchor="w")
        text=tk.Text(window,bg=COLORS["surface"],fg=COLORS["silver"],insertbackground=COLORS["ice"],relief="flat",wrap="word",padx=12,pady=8);text.pack(fill="both",expand=True,padx=12,pady=(0,12))
        for spec in self.generator_registry.all():text.insert("end",f"{'● 已可用' if spec.available else '○ 规划中'}  {spec.name_zh}  ·  {spec.category}\n{spec.description}\n\n")
        text.configure(state="disabled")

    def show_settings(self):
        messagebox.showinfo("设置", "当前设置：简体中文界面\n内部长度单位：mm\n自动保存：已开启\n\n更多显示与导出选项将在设置模块中继续扩展。", parent=self)

    def show_help(self):
        messagebox.showinfo("帮助", "小芒造物工作流：\n1. 导入参考图或轮廓\n2. 在 2D 画布编辑真实元素并实时预览\n3. 点击生成最终模型\n4. 查看尺寸、三角面数与制造检查结果\n5. 导出 STL\n\n当前没有实时三维查看器。快捷键：Ctrl+S 保存，Ctrl+E 导出 STL。", parent=self)

    def show_feedback(self):
        messagebox.showinfo("反馈", "感谢使用小芒造物。\n请在项目目录的 work 文件夹中附上日志与复现步骤，便于后续优化。", parent=self)

    def begin_draw(self):
        self._drawing_points=[];self.canvas.configure(cursor="pencil");self.status.set(self.t("draw_help"))
    def _canvas_to_model(self,event):
        if not self._last_transform:return (event.x,event.y)
        scale,ox,oy=self._last_transform;return (event.x-ox)/scale,(event.y-oy)/scale
    def _canvas_to_reference2d_source(self,event):
        document=self._reference2d_document
        if document is None:return None
        x,y=self._canvas_to_model(event);width=max(1.,float(document.reference_layer.width));height=max(1.,float(document.reference_layer.height))
        return x/100.*width,y/100.*height
    def _select_reference2d_at(self,event):
        source_point=self._canvas_to_reference2d_source(event)
        if source_point is None:return None
        if self._editable_pattern_document is not None:
            width=max(1.0,float(self._editable_pattern_document.canvas.get("source_width_px", 1.0))); height=max(1.0,float(self._editable_pattern_document.canvas.get("source_height_px", 1.0)))
            additive_ids=list(self._editable_pattern_document.selected_ids) if getattr(event, "state", 0) & 0x0001 else []
            element=self._editable_pattern_document.select_at(source_point[0]/width*100.0,source_point[1]/height*100.0,tolerance=1.0)
            if element is not None:
                if getattr(event, "state", 0) & 0x0001:
                    self._editable_pattern_document.selected_ids = list(dict.fromkeys(additive_ids + [element.id]))
                if self._reference2d_document is not None and any(dot.id == element.id for dot in self._reference2d_document.geometry_layer.dots): self._reference2d_document.selected_object_id = element.id
                self.vars["reference2d_radius"].set(str(round(element.radius,2)))
                self.vars["reference2d_rotation"].set(str(round(element.rotation,2)))
                if hasattr(self,"reference2d_selection_info"): self.reference2d_selection_info.set(f"已选中 {element.id} · {element.primitive_type} · 尺寸 {element.width:.2f} × {element.height:.2f} · 置信度 {element.confidence:.0%}")
                return element
        dot=self._reference2d_document.select_at(*source_point)
        if dot is None:
            if hasattr(self,"reference2d_selection_info"):self.reference2d_selection_info.set("未选中 DOT；请点击黑色点对象。")
            return None
        self.vars["reference2d_radius"].set(str(round(dot.radius_x,2)))
        if hasattr(self,"reference2d_selection_info"):self.reference2d_selection_info.set(f"已选中 {dot.id} · 半径 {dot.radius_x:.2f}px · 置信度 {dot.source_confidence:.0%}")
        return dot
    def apply_reference2d_radius(self):
        if self._editable_pattern_document is not None and self._editable_pattern_document.selected_ids:
            try: radius=max(.2,float(self.vars["reference2d_radius"].get()))
            except ValueError: self.status.set("元素尺寸必须是数字。"); return
            self.remember(); ids=list(self._editable_pattern_document.selected_ids); self._editable_pattern_document.set_radius(ids,radius); self._sync_legacy_reference2d(); self._sync_reference2d_project(); self.reference2d_selection_info.set(f"已更新 {len(ids)} 个元素 · 半径 {radius:.2f}"); self.update_preview(); return
        document=self._reference2d_document
        if document is None or not document.selected_object_id:
            self.status.set("请先在 2D 画布中点击一个 DOT。");return
        try:radius=max(.2,float(self.vars["reference2d_radius"].get()))
        except ValueError:
            self.status.set("DOT 半径必须是数字。");return
        self.remember();dot=document.set_dot_radius(document.selected_object_id,radius);self._sync_reference2d_project();self.reference2d_selection_info.set(f"已更新 {dot.id} · 半径 {dot.radius_x:.2f}px");self.update_preview()

    def apply_reference2d_rotation(self):
        document=self._editable_pattern_document
        if document is None or not document.selected_ids:
            self.status.set("请先选择一个或多个真实元素。"); return
        try: rotation=float(self.vars["reference2d_rotation"].get())
        except ValueError:
            self.status.set("元素旋转必须是数字。"); return
        self.remember(); ids=list(document.selected_ids); document.set_rotation(ids,rotation); self._sync_legacy_reference2d(); self._sync_reference2d_project(); self.reference2d_selection_info.set(f"已更新 {len(ids)} 个元素 · 旋转 {rotation:.1f}°"); self.update_preview()

    def group_reference2d_selected(self):
        document=self._editable_pattern_document
        if document is None or not document.selected_ids:
            self.status.set("请先选择两个或更多元素再组合。"); return
        self.remember(); group_id=document.group(); self._sync_reference2d_project(); self.reference2d_selection_info.set(f"已组合 {len(document.selected_ids)} 个元素 · {group_id}"); self.update_preview()

    def rebuild_editable_pattern(self):
        document=self._editable_pattern_document
        if document is None:
            self.status.set("请先导入点阵、半调或几何参考图。"); return
        self.remember(); before=len(document.elements); document.rebuild(); self._sync_legacy_reference2d(); self._sync_reference2d_project()
        mode="参数化模式" if document.mode=="parametric" else "直接元素模式"
        self.reference2d_selection_info.set(f"已按 {mode} 重建 {len(document.elements)} 个元素；Local Override 已保留。")
        self.status.set(f"Rebuild 完成：{before} → {len(document.elements)} 个真实元素。"); self.update_preview()

    def _sync_reference2d_rule_controls(self):
        document=self._editable_pattern_document
        if document is None:
            return
        base=str(document.generator.get("base", "无")) if document.mode=="parametric" else "Direct Element"
        params=document.generator.get("parameters", {}) if isinstance(document.generator.get("parameters", {}),dict) else {}
        if document.mode=="parametric" and document.generator.get("base")=="radial":
            self.vars["reference2d_rule_x"].set(str(params.get("radius_scale",1.0)))
            self.vars["reference2d_rule_y"].set("1.0")
            self.vars["reference2d_rule_rotation"].set(str(params.get("rotation",0.0)))
        else:
            self.vars["reference2d_rule_x"].set(str(params.get("scale_x",1.0)))
            self.vars["reference2d_rule_y"].set(str(params.get("scale_y",1.0)))
            self.vars["reference2d_rule_rotation"].set("0.0")
        modifiers={str(item.get("name")):item.get("parameters",{}) for item in document.modifiers if isinstance(item,dict)}
        self.vars["reference2d_size_gradient"].set(str(modifiers.get("SizeGradient",{}).get("strength",0.0)))
        self.vars["reference2d_density"].set(str(modifiers.get("DensityField",{}).get("strength",0.0)))
        self.vars["reference2d_warp"].set(str(modifiers.get("SimpleWarp",{}).get("amplitude",0.0)))
        self.vars["reference2d_mask_radius"].set(str(modifiers.get("Mask",{}).get("radius",50.0)))
        if hasattr(self,"reference2d_rule_info"):
            if document.mode=="direct":
                self.reference2d_rule_info.set(f"直接元素模式 · {len(document.elements)} 个对象。可编辑，但不强行套用 Generator。")
            else:
                stack="、".join(str(item.get("name")) for item in document.modifiers) or "无"
                self.reference2d_rule_info.set(f"Base Generator：{base} · 分数 {float(document.generator.get('score',0)):.2f}\nModifier Stack：{stack}")

    def apply_reference2d_rules(self):
        document=self._editable_pattern_document
        if document is None:
            self.status.set("请先导入点阵、半调或几何参考图。"); return
        if document.mode!="parametric":
            self.status.set("当前为直接元素模式：检测结果仍可编辑，但没有可信 Generator 可套用。"); return
        try:
            rule_x=float(self.vars["reference2d_rule_x"].get()); rule_y=float(self.vars["reference2d_rule_y"].get())
            rule_rotation=float(self.vars["reference2d_rule_rotation"].get()); size_strength=float(self.vars["reference2d_size_gradient"].get())
            density=float(self.vars["reference2d_density"].get()); warp=float(self.vars["reference2d_warp"].get())
            mask_radius=float(self.vars["reference2d_mask_radius"].get())
        except ValueError:
            self.status.set("规则参数必须是数字。"); return
        self.remember(); params=document.generator.setdefault("parameters",{})
        if document.generator.get("base")=="radial":
            params["radius_scale"]=max(.01,rule_x); params["rotation"]=rule_rotation
        else:
            params["scale_x"]=max(.01,rule_x); params["scale_y"]=max(.01,rule_y)
        for modifier in document.modifiers:
            if not isinstance(modifier,dict): continue
            name=str(modifier.get("name")); values=modifier.setdefault("parameters",{})
            if name=="SizeGradient": values["enabled"]=abs(size_strength)>1e-9; values["strength"]=size_strength
            elif name=="DensityField": values["enabled"]=abs(density)>1e-9; values["strength"]=max(0.0,min(1.0,density))
            elif name=="RotationField":
                # Radial 将规则旋转直接放在 Base Generator；网格则用 Rotation Field。
                values["enabled"]=document.generator.get("base")!="radial" and abs(rule_rotation)>1e-9; values["strength"]=rule_rotation
            elif name=="SimpleWarp": values["enabled"]=abs(warp)>1e-9; values["amplitude"]=warp
            elif name=="Mask": values["enabled"]=mask_radius<49.999; values["radius"]=max(.001,mask_radius)
        document.rebuild(); self._sync_legacy_reference2d(); self._sync_reference2d_project(); self._sync_reference2d_rule_controls(); self.update_preview()
        self.status.set("已应用 Base Generator + Modifier Stack；局部 Override 已重新叠加。")
    def delete_reference2d_selected(self,_event=None):
        if self._editable_pattern_document is not None and self._editable_pattern_document.selected_ids:
            self.remember(); deleted=self._editable_pattern_document.delete(); self._sync_legacy_reference2d(); self._sync_reference2d_project(); self.reference2d_selection_info.set(f"已删除 {len(deleted)} 个元素；剩余 {len(self._editable_pattern_document.elements)} 个。"); self.update_preview(); return "break" if _event is not None else None
        document=self._reference2d_document
        if document is None or not document.selected_object_id:return "break" if _event is not None else None
        self.remember();deleted=document.delete_selected();self._sync_reference2d_project();self.reference2d_selection_info.set(f"已删除 {deleted.id}；剩余 {len(document.geometry_layer.dots)} 个 DOT。");self.update_preview();return "break" if _event is not None else None

    def select_all_reference2d(self):
        if self._editable_pattern_document is None: return
        self._editable_pattern_document.selected_ids = [item.id for item in self._editable_pattern_document.elements if item.enabled]
        self.reference2d_selection_info.set(f"已框选 {len(self._editable_pattern_document.selected_ids)} 个可编辑元素。")

    def duplicate_reference2d_selected(self):
        if self._editable_pattern_document is None or not self._editable_pattern_document.selected_ids: return
        self.remember(); self._editable_pattern_document.duplicate(); self._sync_legacy_reference2d(); self._sync_reference2d_project(); self.update_preview()
    def draw_start(self,event):
        if self._drawing_points is not None and self.canvas["cursor"]=="pencil":self._drawing_points=[self._canvas_to_model(event)];return
        if self._reference2d_document is not None:
            previous_ids = list(self._editable_pattern_document.selected_ids) if self._editable_pattern_document is not None else []
            dot=self._select_reference2d_at(event)
            if dot is not None:
                self.remember();self._reference2d_drag_id=dot.id
                if self._editable_pattern_document is not None:
                    source=self._canvas_to_reference2d_source(event); width=max(1.,float(self._editable_pattern_document.canvas.get("source_width_px",1.))); height=max(1.,float(self._editable_pattern_document.canvas.get("source_height_px",1.)))
                    self._reference2d_drag_ids=list(self._editable_pattern_document.selected_ids); self._reference2d_drag_last=(source[0]/width*100.,source[1]/height*100.) if source is not None else None
                    self.status.set(f"正在移动 {len(self._reference2d_drag_ids)} 个元素；松开鼠标确认位置。")
                else:self.status.set(f"正在移动 {dot.id}；松开鼠标确认位置。")
            elif self._editable_pattern_document is not None and getattr(event, "state", 0) & 0x0001:
                # Shift+拖动空白区域：真实框选 GeometryLayer 元素，不把参考位图当作选择对象。
                self._editable_pattern_document.selected_ids = previous_ids
                self._reference2d_box_start = (event.x, event.y)
                self._reference2d_box_item = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="#2f6fed", dash=(4, 2), width=1)
                self.status.set("正在框选可编辑元素；松开鼠标确认。")
    def draw_move(self,event):
        if self._reference2d_box_start is not None:
            x0, y0 = self._reference2d_box_start
            if self._reference2d_box_item is not None: self.canvas.coords(self._reference2d_box_item, x0, y0, event.x, event.y)
            return
        if self._reference2d_drag_id and self._editable_pattern_document is not None:
            source_point=self._canvas_to_reference2d_source(event)
            if source_point is not None:
                width=max(1.,float(self._editable_pattern_document.canvas.get("source_width_px",1.))); height=max(1.,float(self._editable_pattern_document.canvas.get("source_height_px",1.)))
                current=(source_point[0]/width*100.,source_point[1]/height*100.)
                if self._reference2d_drag_last is not None:
                    self._editable_pattern_document.move(self._reference2d_drag_ids or [self._reference2d_drag_id],current[0]-self._reference2d_drag_last[0],current[1]-self._reference2d_drag_last[1])
                    self._reference2d_drag_last=current
                self._sync_legacy_reference2d(); self._sync_reference2d_project(); self.update_preview()
            return
        if self._reference2d_drag_id and self._reference2d_document is not None:
            source_point=self._canvas_to_reference2d_source(event)
            if source_point is not None:self._reference2d_document.move_dot(self._reference2d_drag_id,*source_point);self._sync_reference2d_project();self.update_preview()
            return
        if self.canvas["cursor"]=="pencil" and self._drawing_points:
            self._drawing_points.append(self._canvas_to_model(event));self.canvas.create_line(event.x-1,event.y-1,event.x+1,event.y+1,fill="#d1523d",width=2)
    def draw_end(self,event):
        if self._reference2d_box_start is not None:
            x0, y0 = self._reference2d_box_start
            self._reference2d_box_start = None
            if self._reference2d_box_item is not None: self.canvas.delete(self._reference2d_box_item); self._reference2d_box_item = None
            try:
                p0 = self._canvas_to_reference2d_source(type("Point", (), {"x": x0, "y": y0})())
                p1 = self._canvas_to_reference2d_source(event)
                width = max(1.0, float(self._editable_pattern_document.canvas.get("source_width_px", 1.0)))
                height = max(1.0, float(self._editable_pattern_document.canvas.get("source_height_px", 1.0)))
                selected = self._editable_pattern_document.select_rect(p0[0] / width * 100.0, p0[1] / height * 100.0, p1[0] / width * 100.0, p1[1] / height * 100.0, additive=True)
                self.reference2d_selection_info.set(f"已框选 {len(selected)} 个可编辑元素，可拖动、删除或复制。")
                self.update_preview()
            except Exception as error:
                self.status.set(f"框选失败：{error}")
            return
        if self._reference2d_drag_id:
            self._reference2d_drag_id=None;self._reference2d_drag_ids=[];self._reference2d_drag_last=None;self.status.set("元素位置已更新并写入 EditablePatternDocument。");return
        if self.canvas["cursor"]!="pencil" or len(self._drawing_points)<3:return
        try:
            self.remember();points=simplify_polyline(self._drawing_points,max(1.5,perimeter_estimate(self._drawing_points)/700));self.project.contour=clean_contour(points);self.project.contour_source="drawn";self._sample_cache.clear();self.canvas.configure(cursor="crosshair");self.status.set("自由绘制轮廓已自动简化并闭合。");self.update_preview()
        except Exception as error:messagebox.showerror("绘制失败",str(error));self.canvas.configure(cursor="crosshair")

    def _sync_legacy_reference2d(self):
        """将新版 EditablePatternDocument 的 DOT 投影同步到旧 Canvas 适配层。"""
        if self._editable_pattern_document is None or self._reference2d_document is None: return
        by_id={item.id:item for item in self._editable_pattern_document.elements}
        synced=[]
        for dot in self._reference2d_document.geometry_layer.dots:
            item=by_id.get(dot.id)
            if item is None: continue
            width=max(1.,float(self._editable_pattern_document.canvas.get("source_width_px",self._reference2d_document.reference_layer.width))); height=max(1.,float(self._editable_pattern_document.canvas.get("source_height_px",self._reference2d_document.reference_layer.height)))
            dot.x=item.x/100.*width; dot.y=item.y/100.*height; dot.radius_x=item.width/200.*width; dot.radius_y=item.height/200.*height; dot.rotation=item.rotation
            synced.append(dot)
        self._reference2d_document.geometry_layer.dots = synced

    def import_contour(self):
        path=filedialog.askopenfilename(title="导入闭合轮廓",filetypes=[("SVG 或 DXF","*.svg *.dxf"),("SVG","*.svg"),("DXF","*.dxf")])
        if not path:return
        try:
            self.remember();points=read_contour(path);self.project.contour=clean_contour(points);self.project.contour_source="imported";self._sample_cache.clear();self.update_preview();self.status.set(f"已导入轮廓：{os.path.basename(path)}")
        except Exception as error:messagebox.showerror("导入失败",self.t("import_error",error=str(error)))

    def current_items(self):
        settings=self.settings_from_ui();return settings,generate_items(self.project.contour,settings)
    def export(self,kind):
        try:
            settings=self.settings_from_ui()
            document=self._editable_pattern_document if settings.active_generator=="field" else None
            if document is not None:
                # SVG/PNG/DXF 与 2D Canvas 使用同一份物化 Element 数据。
                items=[]
            elif settings.active_generator=="field":items=generate_field(settings)
            else:settings,items=self.current_items()
        except Exception as error:messagebox.showerror("无法导出",self.t("invalid",error=str(error)));return
        extension="."+kind;path=filedialog.asksaveasfilename(title="导出 "+kind.upper(),defaultextension=extension,initialfile="parametric_pattern"+extension,filetypes=[(kind.upper(),"*"+extension)])
        if not path:return
        if document is not None:
            {"svg":write_editable_document_svg,"png":write_editable_document_png,"dxf":write_editable_document_dxf}[kind](path,document)
        elif settings.active_generator=="field":
            if kind=="svg":write_field_svg(path,items,settings)
            elif kind=="png":write_field_png(path,items)
            else:write_field_dxf(path,items)
        else:{"svg":write_svg,"png":write_png,"dxf":write_dxf}[kind](path,self.project.contour,items,settings,self.project.custom_element)
        self.status.set(self.t("exported",path=path))

    def generate_variants(self):
        if self.vars["active_generator"].get()!="field":
            self.randomize();return
        base=self.settings_from_ui();window=tk.Toplevel(self);window.title("点线面变体 · 小芒造物");window.resizable(False,False);ttk.Label(window,text="点击喜欢的变体，即可应用并继续编辑。",padding=(12,10,12,4)).pack(anchor="w");grid=ttk.Frame(window,padding=10);grid.pack()
        rng=random.Random(base.seed)
        for index in range(6):
            candidate=replace(base,seed=rng.randint(1,2147483647),field_noise=max(0,min(35,base.field_noise+rng.choice([-8,0,8,14]))),field_rotation=base.field_rotation+rng.choice([-30,-15,0,15,30]),dot_size=max(.4,base.dot_size*rng.uniform(.78,1.28)))
            cell=ttk.Frame(grid,padding=4);cell.grid(row=index//3,column=index%3,padx=4,pady=4);canvas=tk.Canvas(cell,width=150,height=150,bg="white",highlightthickness=1,highlightbackground="#c9d0d7");canvas.pack();self._draw_variant_canvas(canvas,generate_field(candidate,preview_limit=260))
            def apply_variant(value=candidate):
                for key,val in value.to_dict().items():
                    if key in self.vars:self.vars[key].set(str(val))
                self.remember();self.update_preview();window.destroy();self.status.set("已应用变体；所有参数均可继续调整。")
            ttk.Button(cell,text=f"应用变体 {index+1}",command=apply_variant).pack(fill="x",pady=(3,0))

    def _draw_variant_canvas(self,canvas,items):
        scale=1.2;ox=15;oy=15
        for item in items:
            if item.kind=="dot":
                r=max(.4,item.size*scale);canvas.create_oval(item.x*scale+ox-r,item.y*scale+oy-r,item.x*scale+ox+r,item.y*scale+oy+r,fill="#15191e",outline="")
            elif item.kind=="line":canvas.create_line(item.x*scale+ox,item.y*scale+oy,item.x2*scale+ox,item.y2*scale+oy,fill="#15191e",width=max(1,round(item.size*scale)))
            else:canvas.create_polygon(*[v for p in primitive_polygon(item) for v in (p[0]*scale+ox,p[1]*scale+oy)],fill="#15191e",outline="")

    def new_project(self):
        self.remember();self.project=Project();self.project.contour=builtin_contour("有机形",42);self.project_path=None;self._set_ui_from_project();self._sample_cache.clear();self._field_cache.clear();self.update_preview();self.status.set("已新建项目。")
    def open_project(self):
        path=filedialog.askopenfilename(title="打开 PPG 项目",filetypes=[("PPG 项目","*.ppg"),("所有 JSON","*.json")]);
        if not path:return
        try:self.remember();self.project=load_project(path);self.project_path=path;self._set_ui_from_project();self._sample_cache.clear();self._field_cache.clear();self.update_preview();self.status.set(f"已打开：{os.path.basename(path)}")
        except Exception as error:messagebox.showerror("打开失败",str(error))
    def save_current(self):
        if not self.project_path:return self.save_as()
        try:self.project.settings=self.settings_from_ui();self._sync_reference2d_project();save_project(self.project_path,self.project);self.status.set(self.t("saved",path=self.project_path))
        except Exception as error:messagebox.showerror("保存失败",str(error))
    def save_as(self):
        path=filedialog.asksaveasfilename(title="保存 PPG 项目",defaultextension=".ppg",initialfile="未命名纹样.ppg",filetypes=[("PPG 项目","*.ppg")]);
        if path:self.project_path=path;self.save_current()
    def save_current_preset(self):
        path=filedialog.asksaveasfilename(title="保存预设",defaultextension=".ppg",initialfile="我的预设.ppg",filetypes=[("PPG 预设","*.ppg")]);
        if path:self.project.settings=self.settings_from_ui();self._sync_reference2d_project();save_preset(path,self.project);self.status.set("预设已保存。")
    def load_preset(self): self.open_project()
    def autosave(self):
        try:
            autosave=Path.home()/"AppData"/"Local"/"ParametricPatternGenerator"/"autosave.ppg";autosave.parent.mkdir(parents=True,exist_ok=True);self.project.settings=self.settings_from_ui();self._sync_reference2d_project();save_project(str(autosave),self.project)
        except Exception:pass
        if self.winfo_exists():
            self._autosave_id = self.after(self.AUTOSAVE_SECONDS*1000,self.autosave)
    def on_close(self):
        # 退出前取消所有延迟预览/自动保存回调，避免 Tcl 在 destroy 后执行失效命令。
        self._cancel_scheduled_callbacks()
        try:
            autosave=Path.home()/"AppData"/"Local"/"ParametricPatternGenerator"/"autosave.ppg";autosave.parent.mkdir(parents=True,exist_ok=True);self.project.settings=self.settings_from_ui();self._sync_reference2d_project();save_project(str(autosave),self.project)
        except Exception:pass
        self.destroy()

    def _cancel_scheduled_callbacks(self):
        """取消由应用注册的 after 回调，也清掉未被属性追踪的重绘回调。"""
        for name in ("_after_id","_interaction_after_id","_layout_retry_id","_autosave_id"):
            callback=getattr(self,name,None)
            if callback:
                try:self.after_cancel(callback)
                except tk.TclError:pass
                setattr(self,name,None)
        # Configure 事件可能在属性被清空后又排入一个同名 Tcl 命令；销毁窗口
        # 前枚举当前 root 的 after 队列，防止测试/快速关闭时出现 invalid command。
        try:
            pending=self.tk.call("after","info")
            for callback in pending:
                try:self.after_cancel(callback)
                except tk.TclError:pass
        except tk.TclError:
            pass

    def destroy(self):
        try:self._cancel_scheduled_callbacks()
        except Exception:pass
        return super().destroy()


def perimeter_estimate(points): return sum(math.hypot(points[i][0]-points[i-1][0],points[i][1]-points[i-1][1]) for i in range(1,len(points)))


def read_contour(path: str) -> list[Point]:
    if path.lower().endswith(".dxf"):
        lines=Path(path).read_text(encoding="utf-8",errors="ignore").replace("\r","").split("\n");points=[]
        for i in range(len(lines)-3):
            if lines[i].strip()=="10" and lines[i+2].strip()=="20":
                try:points.append((float(lines[i+1]),float(lines[i+3])))
                except ValueError:pass
        if len(points)<3:raise ValueError("DXF 中没有找到可用的闭合 LWPOLYLINE。")
        return points
    root=ET.parse(path).getroot()
    for node in root.iter():
        tag=node.tag.split("}")[-1]
        if tag in ("polygon","polyline"):
            values=re.findall(r"[-+]?(?:\d*\.\d+|\d+)",node.attrib.get("points",""));return [(float(values[i]),float(values[i+1])) for i in range(0,len(values)-1,2)]
        if tag=="path":
            values=re.findall(r"[-+]?(?:\d*\.\d+|\d+)",node.attrib.get("d",""));return [(float(values[i]),float(values[i+1])) for i in range(0,len(values)-1,2)]
    raise ValueError("SVG 中没有找到 polygon、polyline 或简单 path 轮廓。")


def main():
    parser=argparse.ArgumentParser(add_help=False);parser.add_argument("--self-test",action="store_true");args,_=parser.parse_known_args()
    if args.self_test:
        settings=PatternSettings(seed=42,noise_strength=16);c=builtin_contour("有机形",42);a=generate_items(c,settings);b=generate_items(c,settings)
        assert len(a)==len(b)==settings.count and a==b
        final_primitives=apply_height_field([{"kind":"dot","x":50,"y":50,"size":3}],1.2,[{"x":50,"y":50,"delta":1,"radius":8,"falloff":55}])
        assert final_primitives[0]["height"] > 1.2
        from .preview_provider import NullPreviewProvider
        from .reference2d import EditableElement, EditablePatternDocument, document_to_primitives
        editable_probe = EditablePatternDocument(elements=[EditableElement(id="selftest-dot", primitive_type="dot", x=50, y=50, width=6, height=6, radius=3)])
        assert document_to_primitives(editable_probe)[0]["element_id"] == "selftest-dot"
        assert NullPreviewProvider().get_bounds() is None
        # 打包版自检也覆盖 Reference2D 动态导入，避免 PyInstaller 漏收新模块。
        from tempfile import TemporaryDirectory
        from .reference2d import analyze_reference2d
        from reference2d_poc import Reference2DService
        with TemporaryDirectory() as temp:
            probe = Path(temp) / "reference2d_probe.png"
            probe_image = Image.new("L", (96, 96), "white"); probe_draw = ImageDraw.Draw(probe_image)
            for y in range(12, 84, 18):
                for x in range(12, 84, 18): probe_draw.ellipse((x-3, y-3, x+3, y+3), fill="black")
            probe_image.save(probe)
            probe_result = analyze_reference2d(str(probe), target_width_mm=100.0)
            assert probe_result.features and probe_result.geometry.dots and probe_result.fields.density_field
            poc_probe = Path(temp) / "reference2d_poc_probe.png"
            poc_image = Image.new("L", (120, 96), "white"); poc_draw = ImageDraw.Draw(poc_image)
            for y in (20, 48, 76):
                for x in (20, 60, 100): poc_draw.ellipse((x-6, y-6, x+6, y+6), fill="black")
            poc_image.save(poc_probe)
            poc_result = Reference2DService().reconstruct(poc_probe, Path(temp) / "reference2d_poc_probe.svg")
            assert len(poc_result.recovery.dots) == 9
        print("PPG self-test passed")
    else:
        mutex=ctypes.windll.kernel32.CreateMutexW(None,False,"Local\\XiaomangStudio_SingleInstance")
        if ctypes.windll.kernel32.GetLastError()==183:
            probe=tk.Tk();probe.withdraw();messagebox.showinfo("小芒造物已在运行","小芒造物已经打开。请在现有窗口中继续工作；升级前请先关闭所有窗口。",parent=probe);probe.destroy();return
        app=PatternApp();app.mainloop()
        ctypes.windll.kernel32.CloseHandle(mutex)


if __name__=="__main__":main()
