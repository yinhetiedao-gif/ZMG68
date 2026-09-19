"""File-workflow UI only. PatternLabSession owns document and revision state."""
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .parametric import GridParametricModel
from .session import ViewMode


class ProjectChoiceDialog(simpledialog.Dialog):
    def __init__(self, parent, title, message, choices):
        self.message, self.choices = message, choices
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text=self.message, wraplength=420).pack(padx=18, pady=14)

    def buttonbox(self):
        row = ttk.Frame(self)
        row.pack(pady=(0, 12))
        for label, value in self.choices:
            ttk.Button(row, text=label, command=lambda v=value: self.choose(v)).pack(side="left", padx=5)
        self.bind("<Escape>", self.cancel)

    def choose(self, value):
        self.result = value
        self.cancel()


class ProjectWorkflowUI:
    AUTOSAVE_DELAY_MS = 2000
    _PROJECT_PREVIEW_COMMITS = {
        "grid": "_commit_grid_from_controls", "family": "_commit_family_preview",
        "position": "_commit_position_controls", "scope": "_commit_scope_controls",
        "pool": "_commit_shape_pool_controls", "random": "_commit_random_transform_controls",
    }

    def _build_project_workflow(self):
        self._autosave_after = None
        self._pending_project_preview = None
        self._flushing_project_edits = False
        menu = tk.Menu(self)
        files = tk.Menu(menu, tearoff=False)
        menu.add_cascade(label="文件", menu=files)
        for label, command, accelerator in (
            ("新建项目", self.new_project, "Ctrl+N"),
            ("打开项目", self.open_document, "Ctrl+O"),
            ("保存", self.save_document, "Ctrl+S"),
            ("另存为", self.save_document_as, "Ctrl+Shift+S"),
        ):
            files.add_command(label=label, command=command, accelerator=accelerator)
        self._recent_menu = tk.Menu(files, tearoff=False, postcommand=self._refresh_recent_projects)
        files.add_cascade(label="最近项目", menu=self._recent_menu)
        files.add_command(label="重新定位参考图片", command=self.relink_reference)
        files.add_separator()
        files.add_command(label="退出", command=self.request_close)
        self.configure(menu=menu)
        for sequence, command in (
            ("<Control-n>", self.new_project), ("<Control-o>", self.open_document),
            ("<Control-s>", self.save_document), ("<Control-Shift-S>", self.save_document_as),
        ):
            self.bind(sequence, lambda _event, callback=command: (callback(), "break")[1])
        self.protocol("WM_DELETE_WINDOW", self.request_close)
        self.session.on_project_change = self._on_project_state_changed
        self._on_project_state_changed()

    def _on_project_state_changed(self):
        self.title("小芒图案实验室 / Xiaomang Pattern Lab — %s%s" % (
            self.session.current_project_name, " *" if self.session.is_dirty else ""))
        if self._autosave_after:
            self.after_cancel(self._autosave_after)
            self._autosave_after = None
        if self.session.is_dirty:
            self._autosave_after = self.after(self.AUTOSAVE_DELAY_MS, self._autosave_due)
        else:
            self.session._discard_own_recovery()

    def _autosave_due(self):
        self._autosave_after = None
        if self.session.transaction_active or self._pending_project_preview:
            self._autosave_after = self.after(self.AUTOSAVE_DELAY_MS, self._autosave_due)
            return
        try:
            self.session.autosave_recovery()
        except Exception as error:
            self._log_exception("自动恢复副本保存失败（正式项目未受影响）", error)
            self._status_text.set("自动恢复保存失败，请手动保存；详情见转换日志。")
            self.refresh_log()

    def _flush_project_edits(self):
        """Finish the current gesture/preview before saving or asking to discard."""
        self._flushing_project_edits = True
        try:
            if self._interaction:
                self.session.commit_interaction(
                    self._interaction, element_ids=list(self._interaction_element_ids))
                self._interaction = None
                self._interaction_element_ids = ()
                self._cancel_scheduled_interaction_frame()
            pending = self._pending_project_preview
            if pending:
                getattr(self, self._PROJECT_PREVIEW_COMMITS[pending])()
                self._pending_project_preview = None
            if self.session.transaction_active:
                self.session.commit_transaction()
        finally:
            self._flushing_project_edits = False

    def _ask_unsaved_changes(self):
        return ProjectChoiceDialog(self, "未保存的修改", "当前项目有未保存的修改。", (
            ("保存", "save"), ("不保存", "discard"), ("取消", "cancel"),
        )).result

    def _confirm_project_transition(self):
        try:
            self._flush_project_edits()
        except Exception as error:
            messagebox.showerror("无法切换项目", str(error), parent=self)
            return False
        if not self.session.is_dirty:
            return True
        choice = self._ask_unsaved_changes()
        return choice == "discard" or (choice == "save" and self.save_document())

    def _reset_project_view(self):
        for name in ("_parameter_after", "_family_preview_after", "_position_preview_after",
                     "_scope_preview_after", "_shape_pool_preview_after", "_random_transform_preview_after",
                     "_interaction_after", "_inspector_after"):
            timer = getattr(self, name, None)
            if timer:
                self.after_cancel(timer)
            setattr(self, name, None)
        self._pending_project_preview = None
        self._interaction = None
        self._interaction_element_ids = ()
        self._selection_rectangle = None
        self._hover_id = None
        self._pending_grid_fit = None
        self._pending_family_analysis = None
        self._pending_stack_selection = None
        self._view_transform = None
        self._reference_cache_key = None
        self._reference_cache_image = None
        self._reference_photo = None
        self._preview_grid_elements = None
        self._parametric_text.set("项目已切换；可重新尝试参数化。")
        self._load_grid_controls(self.session.grid_model or GridParametricModel())
        # Neutral controls when the new project has no model/stack.
        from .shared_modifiers import SharedModifierStack
        stack = SharedModifierStack.from_document(self.session.require_document())
        self._load_family_field_controls(self.session.parametric_model or stack or SharedModifierStack())
        self.mode.set(ViewMode.VECTOR.value)
        self.hide_reference.set(True)
        self._after_document_change()
        if self.session.missing_reference:
            self._status_text.set("参考图片未找到；矢量仍可编辑。请使用 文件 → 重新定位参考图片。")

    def new_project(self):
        if not self._confirm_project_transition():
            return False
        self.session.new_document()
        self._reset_project_view()
        return True

    def save_document(self):
        return self._save_project(False)

    def save_document_as(self):
        return self._save_project(True)

    def _save_project(self, save_as):
        if self.session.document is None:
            messagebox.showinfo("保存项目", "请先新建项目或导入图片。", parent=self)
            return False
        try:
            self._flush_project_edits()
            path = self.session.current_project_path
            if save_as or path is None:
                path = filedialog.asksaveasfilename(parent=self, title="另存为项目",
                    defaultextension=".pattern.json", filetypes=[("PatternDocument 项目", "*.pattern.json;*.json")])
            if not path:
                return False
            self.session.save_document(str(path))
            self.refresh_log()
            return True
        except Exception as error:
            self._log_exception("保存项目失败", error)
            messagebox.showerror("保存项目失败", str(error), parent=self)
            return False

    def open_document(self):
        path = filedialog.askopenfilename(parent=self, title="打开项目",
                                         filetypes=[("PatternDocument 项目", "*.json")])
        return self.open_project_path(path) if path else False

    def open_project_path(self, path):
        if not Path(path).is_file():
            self._handle(lambda: self.session.project_files.forget(Path(path)))
            messagebox.showwarning("项目不存在", "文件不存在，已从最近项目中移除：\n" + str(path), parent=self)
            return False
        if not self._confirm_project_transition():
            return False
        try:
            self.session.load_document(str(path))
        except Exception as error:
            self._log_exception("打开项目失败，保留当前设计", error)
            messagebox.showerror("打开项目失败", str(error), parent=self)
            return False
        self._reset_project_view()
        return True

    def _refresh_recent_projects(self):
        self._recent_menu.delete(0, "end")
        paths = self.session.project_files.recent()
        for path in paths:
            self._recent_menu.add_command(label=path, command=lambda p=path: self.open_project_path(p))
        if not paths:
            self._recent_menu.add_command(label="暂无最近项目", state="disabled")

    def relink_reference(self):
        if self.session.document is None:
            return
        path = filedialog.askopenfilename(parent=self, title="重新定位参考图片",
                                         filetypes=[("图片", "*.png;*.jpg;*.jpeg")])
        if path:
            self._handle(lambda: (self.session.relink_reference(path), self._reset_project_view()))

    def check_project_recovery(self):
        # Called once by the real entry point, not by reusable test roots.
        for path in self.session.project_files.recoveries():
            choice = ProjectChoiceDialog(self, "项目恢复", "检测到未恢复的项目数据：\n" + path.name,
                                         (("恢复", "recover"), ("放弃", "discard"))).result
            if choice == "recover":
                self._handle(lambda: (self.session.restore_recovery(path), self._reset_project_view()))
                break
            if choice == "discard":
                self._handle(lambda: self.session.project_files.discard_recovery(path))
            else:
                break

    def request_close(self):
        if not self._confirm_project_transition():
            return False
        self.session._discard_own_recovery()
        self.destroy()
        return True
