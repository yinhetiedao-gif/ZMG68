"""Read-only lightweight preview of an existing ManufacturingMeshResult.

This is deliberately a view, not a mesh pipeline.  It keeps an immutable
render copy of the final manufacturing vertices/faces and never exposes a
write-back path to the source mesh, PatternDocument, or STL exporter.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from time import perf_counter
import tkinter as tk
from tkinter import ttk
from typing import Callable

import numpy as np
from PIL import Image, ImageDraw, ImageTk

from .manufacturing_backend import ManufacturingMeshResult


@dataclass(frozen=True)
class MeshPreviewModel:
    vertices: np.ndarray
    faces: np.ndarray
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]]
    component_count: int
    source_vertex_count: int
    source_face_count: int

    @classmethod
    def from_manufacturing_result(cls, result: ManufacturingMeshResult) -> "MeshPreviewModel":
        vertices = np.asarray(result.mesh.vertices, dtype=float).copy()
        faces = np.asarray(result.mesh.faces, dtype=np.int64).copy()
        if vertices.ndim != 2 or vertices.shape[1] != 3 or not np.isfinite(vertices).all():
            raise ValueError("Preview 需要有限的三维 Mesh 顶点。")
        if faces.ndim != 2 or faces.shape[1] != 3 or len(faces) == 0:
            raise ValueError("Preview 需要有效的三角面 Mesh。")
        if np.any(faces < 0) or np.any(faces >= len(vertices)):
            raise ValueError("Preview Mesh 含有无效三角面索引。")
        vertices.setflags(write=False); faces.setflags(write=False)
        return cls(
            vertices, faces, result.bounds, int(result.component_count),
            int(result.vertex_count), int(result.face_count),
        )

    @property
    def size(self) -> tuple[float, float, float]:
        lower, upper = self.bounds
        return tuple(float(upper[index] - lower[index]) for index in range(3))

    @property
    def center(self) -> np.ndarray:
        return (np.asarray(self.bounds[0], dtype=float) + np.asarray(self.bounds[1], dtype=float)) * 0.5


@dataclass
class PreviewCamera:
    azimuth: float = 45.0
    elevation: float = 28.0
    zoom: float = 1.0

    def orbit(self, dx: float, dy: float) -> None:
        self.azimuth = (self.azimuth + float(dx) * 0.45) % 360.0
        self.elevation = max(-85.0, min(85.0, self.elevation - float(dy) * 0.35))

    def zoom_by(self, factor: float) -> None:
        if not math.isfinite(factor) or factor <= 0:
            return
        self.zoom = max(0.12, min(12.0, self.zoom * factor))

    def fit(self) -> None:
        self.zoom = 1.0

    def reset(self) -> None:
        self.azimuth, self.elevation, self.zoom = 45.0, 28.0, 1.0


@dataclass(frozen=True)
class PreviewRenderResult:
    image: Image.Image
    rendered_face_count: int
    duration_ms: float


class MeshSoftwareRenderer:
    """Small painter-style renderer for inspection, never manufacturing."""

    background = (248, 249, 251)

    def render(self, model: MeshPreviewModel, camera: PreviewCamera, width: int, height: int) -> PreviewRenderResult:
        started = perf_counter()
        width, height = max(64, int(width)), max(64, int(height))
        image = Image.new("RGB", (width, height), self.background)
        draw = ImageDraw.Draw(image)
        relative = model.vertices - model.center
        right, up, view = self._camera_basis(camera)
        screen_x = relative @ right
        screen_y = relative @ up
        depth = relative @ view
        radius = max(float(np.linalg.norm(relative, axis=1).max(initial=1.0)), 1e-9)
        scale = 0.82 * min(width, height) / (2.0 * radius) * camera.zoom
        points = np.column_stack((width * 0.5 + screen_x * scale, height * 0.5 - screen_y * scale))
        triangles = points[model.faces]
        face_depth = depth[model.faces].mean(axis=1)
        order = np.argsort(face_depth)
        rotated = np.column_stack((screen_x, screen_y, depth))
        tri3 = rotated[model.faces]
        normals = np.cross(tri3[:, 1] - tri3[:, 0], tri3[:, 2] - tri3[:, 0])
        norm = np.linalg.norm(normals, axis=1)
        visible_norm = np.divide(np.abs(normals[:, 2]), norm, out=np.zeros_like(norm), where=norm > 1e-12)
        for face_index in order:
            triangle = triangles[face_index]
            if not np.isfinite(triangle).all():
                continue
            shade = int(85 + 135 * visible_norm[face_index])
            fill = (max(28, shade - 18), max(35, shade - 8), min(235, shade + 8))
            draw.polygon([tuple(point) for point in triangle], fill=fill, outline=(45, 55, 66))
        self._draw_axes(draw, right, up, width, height)
        return PreviewRenderResult(image, len(model.faces), (perf_counter() - started) * 1000.0)

    @staticmethod
    def _camera_basis(camera: PreviewCamera) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        azimuth, elevation = math.radians(camera.azimuth), math.radians(camera.elevation)
        right = np.asarray((-math.sin(azimuth), math.cos(azimuth), 0.0))
        up = np.asarray((-math.cos(azimuth) * math.sin(elevation),
                         -math.sin(azimuth) * math.sin(elevation), math.cos(elevation)))
        view = np.asarray((math.cos(azimuth) * math.cos(elevation),
                           math.sin(azimuth) * math.cos(elevation), math.sin(elevation)))
        return right, up, view

    @staticmethod
    def _draw_axes(draw: ImageDraw.ImageDraw, right: np.ndarray, up: np.ndarray, width: int, height: int) -> None:
        origin = np.asarray((44.0, float(height - 42)))
        for axis, color, label in (
            (np.asarray((1.0, 0.0, 0.0)), (190, 65, 65), "X"),
            (np.asarray((0.0, 1.0, 0.0)), (55, 145, 80), "Y"),
            (np.asarray((0.0, 0.0, 1.0)), (55, 95, 190), "Z"),
        ):
            end = origin + np.asarray((axis @ right, -(axis @ up))) * 28.0
            draw.line((tuple(origin), tuple(end)), fill=color, width=3)
            draw.text(tuple(end + 2), label, fill=color)


class MeshPreviewDialog(tk.Toplevel):
    """Tk view of one immutable preview model with orbit/zoom/fit/reset only."""

    def __init__(self, parent, model: MeshPreviewModel, *, is_stale: Callable[[], bool], on_close=None):
        super().__init__(parent)
        self.model, self.is_stale, self.on_close = model, is_stale, on_close
        self.camera = PreviewCamera(); self.renderer = MeshSoftwareRenderer()
        self._photo: ImageTk.PhotoImage | None = None
        self._render_after: str | None = None
        self._stale_after: str | None = None
        self._drag_origin: tuple[int, int] | None = None
        self._forced_stale = False
        self.status_var = tk.StringVar(value="✓ 当前制造 Mesh（Z 向上）")
        size = model.size
        self.summary_var = tk.StringVar(value=(
            "X %.2f mm    Y %.2f mm    Z %.2f mm    Components %d" %
            (size[0], size[1], size[2], model.component_count)
        ))
        self.performance_var = tk.StringVar(value="等待渲染…")
        self.title("制造 3D 预览 / Manufacturing Preview")
        self.geometry("780x620"); self.minsize(520, 420); self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._build(); self._schedule_render(); self._poll_stale()

    def _build(self) -> None:
        root = ttk.Frame(self, padding=10); root.pack(fill="both", expand=True)
        top = ttk.Frame(root); top.pack(fill="x")
        ttk.Label(top, textvariable=self.status_var, font=("Microsoft YaHei UI", 10, "bold")).pack(side="left")
        ttk.Button(top, text="重置视角", command=self.reset_view).pack(side="right")
        ttk.Button(top, text="适合窗口", command=self.fit_view).pack(side="right", padx=6)
        ttk.Label(root, textvariable=self.summary_var).pack(anchor="w", pady=(5, 5))
        self.canvas = tk.Canvas(root, background="#f8f9fb", highlightthickness=1, highlightbackground="#aeb8c5")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _event: self._schedule_render())
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", lambda _event: setattr(self, "_drag_origin", None))
        self.canvas.bind("<MouseWheel>", self._wheel)
        ttk.Label(root, text="左键拖动旋转；滚轮缩放。预览只读取最终 Mesh，不参与 STL 导出。",
                  foreground="#44515e").pack(anchor="w", pady=(6, 0))
        ttk.Label(root, textvariable=self.performance_var, foreground="#66717d").pack(anchor="w")

    def _press(self, event: tk.Event) -> None:
        self._drag_origin = (event.x, event.y)

    def _drag(self, event: tk.Event) -> None:
        if self._drag_origin is None:
            return
        old_x, old_y = self._drag_origin
        self.camera.orbit(event.x - old_x, event.y - old_y)
        self._drag_origin = (event.x, event.y)
        self._schedule_render()

    def _wheel(self, event: tk.Event):
        self.camera.zoom_by(1.12 if event.delta > 0 else 1 / 1.12)
        self._schedule_render()
        return "break"

    def fit_view(self) -> None:
        self.camera.fit(); self._schedule_render()

    def reset_view(self) -> None:
        self.camera.reset(); self._schedule_render()

    def mark_stale(self, message: str = "设计或厚度已修改，请重新生成制造模型。") -> None:
        self._forced_stale = True
        self.status_var.set("⚠ " + message)

    def _poll_stale(self) -> None:
        try:
            if self._forced_stale or self.is_stale():
                self.mark_stale()
            self._stale_after = self.after(350, self._poll_stale)
        except tk.TclError:
            self._stale_after = None

    def _schedule_render(self) -> None:
        if self._render_after is None:
            self._render_after = self.after_idle(self._render)

    def _render(self) -> None:
        self._render_after = None
        width, height = max(64, self.canvas.winfo_width()), max(64, self.canvas.winfo_height())
        result = self.renderer.render(self.model, self.camera, width, height)
        self._photo = ImageTk.PhotoImage(result.image)
        self.canvas.delete("preview")
        self.canvas.create_image(0, 0, image=self._photo, anchor="nw", tags=("preview",))
        self.performance_var.set("Preview：%d faces，%.1f ms（正式 STL Mesh 未改变）" % (
            result.rendered_face_count, result.duration_ms,
        ))

    def close(self) -> None:
        for callback in (self._render_after, self._stale_after):
            if callback:
                try: self.after_cancel(callback)
                except tk.TclError: pass
        if self.on_close:
            self.on_close()
        self.destroy()
