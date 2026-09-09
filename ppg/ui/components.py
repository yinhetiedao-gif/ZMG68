"""基础可复用控件：工具按钮、图标按钮和可输入的参数滑杆。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from ..theme import COLORS


class ToolButton(ttk.Button):
    """统一顶部操作按钮，支持运行时的 loading / success / error 反馈。"""
    def __init__(self, parent, *, text: str, command: Callable[[], None] | None = None, primary: bool = False, **kwargs):
        self._base_text = text
        super().__init__(parent, text=text, command=command, style="Action.TButton" if primary else "Toolbar.TButton", **kwargs)

    def feedback(self, state: str = "default") -> None:
        labels = {"default": self._base_text, "loading": "处理中…", "success": "已完成 ✓", "error": "操作失败 !"}
        self.configure(text=labels.get(state, self._base_text), state="disabled" if state == "loading" else "normal")
        if state in ("success", "error"):
            self.after(1500, lambda: self.feedback("default"))


class IconButton(ttk.Button):
    """没有外部图标依赖的紧凑文字图标按钮。"""
    def __init__(self, parent, icon: str, label: str, command: Callable[[], None], **kwargs):
        super().__init__(parent, text=icon, command=command, width=3, style="Icon.TButton", **kwargs)
        self._tooltip = label
        self.bind("<Enter>", lambda _e: self.configure(style="IconActive.TButton"), add=True)
        self.bind("<Leave>", lambda _e: self.configure(style="Icon.TButton"), add=True)


class ParameterControl(ttk.Frame):
    """“名称 + 滑杆 + 数字输入 + 单位 + 重置”的统一参数控件。"""
    def __init__(self, parent, *, label: str, variable: tk.Variable, lower: float, upper: float, resolution: float,
                 suffix: str = "", on_change: Callable[[], None] | None = None, default: str | None = None):
        super().__init__(parent)
        self.variable, self.default, self._on_change = variable, str(default if default is not None else variable.get()), on_change
        header = ttk.Frame(self); header.pack(fill="x")
        ttk.Label(header, text=label).pack(side="left")
        self.entry = ttk.Entry(header, textvariable=variable, width=7, justify="right")
        self.entry.pack(side="right")
        if suffix:
            ttk.Label(header, text=suffix, foreground=COLORS["muted"], width=3).pack(side="right", padx=(3, 0))
        self.reset = ttk.Button(header, text="↺", width=3, command=self.reset_value, style="Icon.TButton")
        self.reset.pack(side="right", padx=(4, 0))
        self.scale = tk.Scale(self, from_=lower, to=upper, resolution=resolution, showvalue=False, orient="horizontal",
                              variable=variable, command=lambda _v: self.changed(), highlightthickness=0,
                              bg=COLORS["surface_2"], fg=COLORS["silver"], troughcolor=COLORS["line"],
                              activebackground=COLORS["mango"], highlightbackground=COLORS["surface"])
        self.scale.pack(fill="x", pady=(1, 0))
        self.entry.bind("<Return>", lambda _e: self.changed())
        self.entry.bind("<FocusOut>", lambda _e: self.changed())

    def changed(self) -> None:
        if self._on_change:
            self._on_change()

    def reset_value(self) -> None:
        self.variable.set(self.default)
        self.changed()
