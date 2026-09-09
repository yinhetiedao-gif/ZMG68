"""左侧一级导航。"""
from __future__ import annotations

from tkinter import ttk
from typing import Callable

from ..theme import COLORS


class NavigationRail(ttk.Frame):
    def __init__(self, parent, items: list[tuple[str, str]], on_change: Callable[[str], None]):
        super().__init__(parent, padding=(8, 12))
        self._buttons: dict[str, ttk.Button] = {}
        self._on_change = on_change
        for key, label in items:
            button = ttk.Button(self, text=label, style="Nav.TButton", command=lambda key=key: self.select(key))
            button.pack(fill="x", pady=3)
            self._buttons[key] = button
        self.selected = ""

    def select(self, key: str) -> None:
        if key not in self._buttons:
            return
        for item_key, button in self._buttons.items():
            button.configure(style="NavActive.TButton" if item_key == key else "Nav.TButton")
        self.selected = key
        self._on_change(key)


def brand_hint(parent) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=(8, 12))
    ttk.Separator(frame).pack(fill="x", pady=(0, 10))
    ttk.Label(frame, text="嗨！我是小芒～", foreground=COLORS["orange"], font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w")
    ttk.Label(frame, text="选择左侧模块，开始设计吧。", foreground=COLORS["muted"], wraplength=180).pack(anchor="w", pady=(3, 0))
    return frame
