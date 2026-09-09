"""二维工作区的逻辑图层与生成器卡片。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from ..theme import COLORS


class CanvasLayers:
    """Canvas 的逻辑图层命名约定；图层分离不依赖单张合成图片。"""
    ORDER = ("background", "grid", "reference", "geometry", "selection", "brush", "guides", "overlay")

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas

    def clear(self, *layers: str) -> None:
        for layer in layers or self.ORDER:
            self.canvas.delete(f"layer:{layer}")

    @staticmethod
    def tags(layer: str, *extra: str) -> tuple[str, ...]:
        return (f"layer:{layer}", *extra)


class GeneratorShelf(ttk.Frame):
    def __init__(self, parent, cards: list[tuple[str, str]], on_select: Callable[[str], None]):
        super().__init__(parent, padding=(8, 6))
        self._buttons: dict[str, ttk.Button] = {}
        self._on_select = on_select
        ttk.Label(self, text="常用生成器", foreground=COLORS["muted"]).pack(anchor="w", pady=(0, 4))
        row = ttk.Frame(self); row.pack(fill="x")
        for key, label in cards:
            button = ttk.Button(row, text=label, style="Generator.TButton", command=lambda key=key: self.select(key))
            button.pack(side="left", padx=2, expand=True, fill="x")
            self._buttons[key] = button
        self.selected = ""

    def select(self, key: str) -> None:
        for item_key, button in self._buttons.items():
            button.configure(style="GeneratorActive.TButton" if item_key == key else "Generator.TButton")
        self.selected = key
        self._on_select(key)
