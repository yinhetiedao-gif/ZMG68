"""Tk presentation for the headless, physically validated manufacturing service."""
from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import traceback

from .manufacturing_service import (
    ManufacturingService,
    ManufacturingServiceResult,
    ManufacturingWorkflow,
    ManufacturingWorkflowResult,
    parse_height_mm,
)
from .mesh_preview import MeshPreviewDialog, MeshPreviewModel


class ManufacturingDialog(tk.Toplevel):
    """User-facing checks, readonly manufacturing preview, and STL export."""

    def __init__(self, parent, session, *, on_close=None):
        super().__init__(parent)
        self.parent, self.session, self.on_close = parent, session, on_close
        self.service = ManufacturingService()
        self.result: ManufacturingServiceResult | None = None
        self._preview_dialog: MeshPreviewDialog | None = None
        self.height_var = tk.StringVar(value="2.0")
        self.status_var = tk.StringVar(value="尚未检查。请设置厚度，然后点击“检查并生成”。")
        self.geometry_var = tk.StringVar(value="Geometry：—")
        self.connectivity_var = tk.StringVar(value="Connectivity：—")
        self.conversion_var = tk.StringVar(value="Manufacturing：—")
        self.mesh_var = tk.StringVar(value="Mesh：—")
        self.title("制造 / Manufacture")
        self.geometry("610x590")
        self.minsize(520, 480)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._build()
        self.height_var.trace_add("write", self._height_changed)

    def _build(self) -> None:
        root = ttk.Frame(self, padding=14); root.pack(fill="both", expand=True)
        ttk.Label(root, text="制造模型", font=("Microsoft YaHei UI", 13, "bold")).pack(anchor="w")
        ttk.Label(root, text="使用当前二维设计生成临时制造网格；不会修改工程或创建撤销记录。",
                  wraplength=560).pack(anchor="w", pady=(3, 12))
        row = ttk.Frame(root); row.pack(fill="x")
        ttk.Label(row, text="厚度").pack(side="left")
        ttk.Entry(row, textvariable=self.height_var, width=12).pack(side="left", padx=(10, 5))
        ttk.Label(row, text="mm").pack(side="left")
        self.prepare_button = ttk.Button(row, text="检查并生成", command=self.prepare)
        self.prepare_button.pack(side="right")

        summary = ttk.LabelFrame(root, text="制造检查摘要", padding=10); summary.pack(fill="x", pady=(12, 8))
        ttk.Label(summary, textvariable=self.status_var, wraplength=540, font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w", pady=(0, 7))
        for variable in (self.geometry_var, self.connectivity_var, self.conversion_var, self.mesh_var):
            ttk.Label(summary, textvariable=variable, wraplength=540).pack(anchor="w", pady=2)

        details_box = ttk.LabelFrame(root, text="详情 / 开发日志", padding=6); details_box.pack(fill="both", expand=True, pady=(4, 8))
        self.details = tk.Text(details_box, height=12, wrap="word", state="disabled")
        scroll = ttk.Scrollbar(details_box, orient="vertical", command=self.details.yview)
        self.details.configure(yscrollcommand=scroll.set)
        self.details.pack(side="left", fill="both", expand=True); scroll.pack(side="right", fill="y")

        actions = ttk.Frame(root); actions.pack(fill="x")
        self.export_button = ttk.Button(actions, text="导出 STL", command=self.export_stl, state="disabled")
        self.export_button.pack(side="right")
        self.preview_button = ttk.Button(actions, text="3D 预览", command=self.open_preview, state="disabled")
        self.preview_button.pack(side="right", padx=(0, 8))
        ttk.Button(actions, text="关闭", command=self.close).pack(side="right", padx=(0, 8))

    def _height_changed(self, *_args) -> None:
        if self.result is not None:
            self._mark_preview_stale()
            self.result = None
            self.export_button.configure(state="disabled")
            self.preview_button.configure(state="disabled")
            self.status_var.set("厚度已变化，请重新检查并生成。")

    def prepare(self) -> ManufacturingServiceResult | None:
        self._mark_preview_stale("已重新生成制造模型，请重新打开 3D 预览。")
        self._close_preview()
        self.export_button.configure(state="disabled")
        self.preview_button.configure(state="disabled")
        try:
            result = self.service.build(self.session, parse_height_mm(self.height_var.get()))
        except Exception as error:
            self.result = None
            self.status_var.set("✕ 无法生成制造模型：%s" % self._friendly_error(error))
            self._set_details(traceback.format_exc())
            self._developer_log("Manufacturing prepare", error)
            return None
        self.result = result
        self._show_result(result)
        self.export_button.configure(state="normal" if result.ready else "disabled")
        self.preview_button.configure(state="normal" if result.ready else "disabled")
        return result

    def open_preview(self) -> None:
        result = self.result
        if result is None or result.build is None or not result.ready:
            self.status_var.set("请先完成制造检查并生成有效 Mesh。")
            return
        if not self.service.is_current(self.session, result, self.height_var.get()):
            self.export_button.configure(state="disabled")
            self.preview_button.configure(state="disabled")
            self.status_var.set("当前设计或厚度已变化，请重新检查并生成。")
            self._mark_preview_stale()
            return
        dialog = self._preview_dialog
        if dialog is not None and dialog.winfo_exists():
            dialog.lift(); dialog.focus_force(); return
        model = MeshPreviewModel.from_manufacturing_result(result.build.mesh_result)
        self._preview_dialog = MeshPreviewDialog(
            self, model,
            is_stale=lambda: not self.service.is_current(self.session, result, self.height_var.get()),
            on_close=lambda: setattr(self, "_preview_dialog", None),
        )

    def _mark_preview_stale(self, message: str = "设计或厚度已修改，请重新生成制造模型。") -> None:
        dialog = self._preview_dialog
        if dialog is not None and dialog.winfo_exists():
            dialog.mark_stale(message)

    def _close_preview(self) -> None:
        dialog = self._preview_dialog
        if dialog is not None and dialog.winfo_exists():
            dialog.close()
        self._preview_dialog = None

    def _show_result(self, result: ManufacturingServiceResult) -> None:
        g, c, a, m = result.geometry_report, result.connectivity_report, result.conversion.report, result.mesh_report
        self.geometry_var.set(("✓" if g.error_count == 0 else "✕") + " Geometry：%d 有效，%d 错误，%d 警告" % (g.valid_count, g.error_count, g.warning_count))
        marker = "⚠" if c.component_count > 1 else "✓"
        self.connectivity_var.set("%s Connectivity：Components %d，Isolated %d" % (marker, c.component_count, c.isolated_count))
        self.conversion_var.set(("✓" if not a.skipped_count else "⚠") + " Manufacturing：Converted %d，Skipped %d" % (a.converted_count, a.skipped_count))
        if m is None:
            self.mesh_var.set("✕ Mesh：未生成")
        else:
            marker = "✓" if m.error_count == 0 and m.is_watertight else "✕"
            self.mesh_var.set("%s Mesh：Watertight %s，Non-manifold %d，Degenerate %d，Components %d" % (
                marker, "是" if m.is_watertight else "否", m.non_manifold_edge_count,
                m.degenerate_face_count, m.component_count,
            ))
        if result.ready:
            self.status_var.set("⚠ 可以导出 STL；当前包含 %d 个独立组件。" % c.component_count if c.component_count > 1 else "✓ 可以导出 STL。")
        else:
            self.status_var.set("✕ 无法导出，请查看下方详情。")
        lines = [
            "厚度：%g mm" % result.height_mm,
            "Gate T issues：" + ("无" if not g.issues else "；".join(issue.message for issue in g.issues)),
            "Gate U components：%d；isolated IDs：%s" % (c.component_count, ", ".join(c.isolated_element_ids) or "无"),
            "U.5 units：%s；bounds：%s；warnings：%s" % (a.units, a.bounds, "；".join(a.warnings) or "无"),
        ]
        if result.build is not None and m is not None:
            lines.extend((
                "Mesh bounds：%s" % (result.build.mesh_result.bounds,),
                "Vertices / Faces：%d / %d" % (m.vertex_count, m.face_count),
                "Gate W issues：" + ("无" if not m.issues else "；".join(issue.message for issue in m.issues)),
            ))
        self._set_details("\n".join(lines))

    def export_stl(self) -> None:
        result = self.result
        if result is None or not self.service.is_current(self.session, result, self.height_var.get()):
            self.export_button.configure(state="disabled")
            self.status_var.set("当前设计或厚度已变化，请重新检查并生成。")
            return
        target = filedialog.asksaveasfilename(
            parent=self, title="导出 STL", defaultextension=".stl",
            filetypes=[("STL 模型", "*.stl")], confirmoverwrite=False,
        )
        if not target:
            return
        path = Path(target)
        overwrite = False
        if path.exists():
            overwrite = messagebox.askyesno("覆盖 STL", "目标文件已存在，是否覆盖？", parent=self)
            if not overwrite:
                return
        try:
            exported = self.service.export_stl(self.session, result, path, overwrite=overwrite)
        except Exception as error:
            self.status_var.set("✕ STL 导出失败：%s" % self._friendly_error(error))
            self._set_details(self.details.get("1.0", "end").rstrip() + "\n\n" + traceback.format_exc())
            self._developer_log("Manufacturing STL export", error)
            return
        size = result.build.mesh_result.size
        self.status_var.set("✓ STL 导出成功。")
        messagebox.showinfo(
            "STL 导出成功",
            "路径：%s\n\n尺寸：%.3f × %.3f × %.3f mm\nComponents：%d" % (
                exported.output_path, size[0], size[1], size[2], exported.component_count,
            ), parent=self,
        )

    @staticmethod
    def _friendly_error(error: Exception) -> str:
        message = str(error).strip()
        return message if message else "内部制造检查失败，技术详情已记录。"

    def _developer_log(self, context: str, error: Exception) -> None:
        if hasattr(self.parent, "_log_exception"):
            self.parent._log_exception(context, error)
        if hasattr(self.parent, "refresh_log"):
            self.parent.refresh_log()

    def _set_details(self, text: str) -> None:
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", text)
        self.details.configure(state="disabled")

    def close(self) -> None:
        self._close_preview()
        if self.on_close:
            self.on_close()
        self.destroy()
