from __future__ import annotations

"""确定性的 DOT/HALFTONE 检测。

优先使用 OpenCV/scipy/scikit-image（若运行时存在），否则使用 NumPy 的
等价实现。关键点是：粘连圆点不再被一个 connected component 吞掉，而是
通过 distance transform + local maxima + watershed/Voronoi 分区拆开。
"""

from collections import deque
import math
from typing import Any

import numpy as np

from .models import DotFeature


def _components(mask: np.ndarray, min_area: int, limit: int) -> list[list[tuple[int, int]]]:
    """8 邻域组件；保留纯 NumPy/Python 后备，避免强制安装 CV 库。"""
    height, width = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    result: list[list[tuple[int, int]]] = []
    for y, x in zip(*np.where(mask & ~seen)):
        if seen[y, x]:
            continue
        queue = deque([(int(y), int(x))]); seen[y, x] = True; pixels = []
        while queue:
            yy, xx = queue.popleft(); pixels.append((yy, xx))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if not dx and not dy:
                        continue
                    ny, nx = yy + dy, xx + dx
                    if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True; queue.append((ny, nx))
        if len(pixels) >= max(1, int(min_area)):
            result.append(pixels)
            if len(result) >= limit:
                break
    return result


def _distance_transform(mask: np.ndarray) -> np.ndarray:
    """返回前景到背景的距离；scipy 不可用时采用两遍 chamfer 距离。"""
    try:
        from scipy import ndimage  # type: ignore
        return np.asarray(ndimage.distance_transform_edt(mask), dtype=float)
    except Exception:
        inf = 1e9; distance = np.where(mask, inf, 0.0).astype(float); diagonal = math.sqrt(2.0)
        for y in range(mask.shape[0]):
            for x in range(mask.shape[1]):
                if not mask[y, x]: continue
                value = distance[y, x]
                if y: value = min(value, distance[y - 1, x] + 1.0)
                if x: value = min(value, distance[y, x - 1] + 1.0)
                if y and x: value = min(value, distance[y - 1, x - 1] + diagonal)
                if y and x + 1 < mask.shape[1]: value = min(value, distance[y - 1, x + 1] + diagonal)
                distance[y, x] = value
        for y in range(mask.shape[0] - 1, -1, -1):
            for x in range(mask.shape[1] - 1, -1, -1):
                if not mask[y, x]: continue
                value = distance[y, x]
                if y + 1 < mask.shape[0]: value = min(value, distance[y + 1, x] + 1.0)
                if x + 1 < mask.shape[1]: value = min(value, distance[y, x + 1] + 1.0)
                if y + 1 < mask.shape[0] and x + 1 < mask.shape[1]: value = min(value, distance[y + 1, x + 1] + diagonal)
                if y + 1 < mask.shape[0] and x: value = min(value, distance[y + 1, x - 1] + diagonal)
                distance[y, x] = value
        return distance


def _local_maxima(distance: np.ndarray, component_mask: np.ndarray, min_distance: float) -> list[tuple[int, int]]:
    ys, xs = np.where(component_mask)
    if not len(xs): return []
    candidates = [(float(distance[y, x]), int(y), int(x)) for y, x in zip(ys, xs) if distance[y, x] > 0]
    candidates.sort(reverse=True); peaks: list[tuple[int, int]] = []
    for value, y, x in candidates:
        if value < 1.25: break
        # 真正的局部峰值：圆形内部的平坦区域只保留一个中心，
        # 避免把每个高距离像素误当作一个 DOT。
        neighbourhood = distance[max(0, y-2):y+3, max(0, x-2):x+3]
        if float(neighbourhood.max()) > value + 1e-6:
            continue
        if all(math.hypot(x - px, y - py) >= min_distance for py, px in peaks): peaks.append((y, x))
    return peaks


def _watershed_split(component: list[tuple[int, int]], distance: np.ndarray) -> list[list[tuple[int, int]]]:
    ys = np.asarray([p[0] for p in component], dtype=int); xs = np.asarray([p[1] for p in component], dtype=int)
    component_mask = np.zeros_like(distance, dtype=bool); component_mask[ys, xs] = True
    maximum = float(distance[component_mask].max()) if np.any(component_mask) else 0.0
    # 55% of the largest radius prevents noise maxima, while allowing two touching dots.
    peaks = _local_maxima(distance, component_mask, max(2.0, maximum * 0.72))
    if len(peaks) < 2: return [component]
    width = int(xs.max() - xs.min() + 1); height = int(ys.max() - ys.min() + 1)
    # Very elongated components are lines, not a row of dots; do not split them here.
    if max(width / max(1, height), height / max(1, width)) > 3.8: return [component]
    peak_array = np.asarray([(x, y) for y, x in peaks], dtype=float); points = np.column_stack((xs.astype(float), ys.astype(float)))
    distances = ((points[:, None, :] - peak_array[None, :, :]) ** 2).sum(axis=2); labels = np.argmin(distances, axis=1)
    regions = []
    for label in range(len(peaks)):
        region = [(int(y), int(x)) for (y, x), assigned in zip(component, labels) if int(assigned) == label]
        if len(region) >= 3: regions.append(region)
    return regions or [component]


def _feature_from_pixels(pixels: list[tuple[int, int]], width: int, height: int, index: int) -> DotFeature:
    ys = np.asarray([p[0] for p in pixels], dtype=float); xs = np.asarray([p[1] for p in pixels], dtype=float)
    min_x, max_x, min_y, max_y = xs.min(), xs.max(), ys.min(), ys.max(); box_width, box_height = max_x - min_x + 1.0, max_y - min_y + 1.0
    centered = np.column_stack((xs - xs.mean(), ys - ys.mean())); covariance = np.cov(centered, rowvar=False, bias=True) if len(pixels) > 2 else np.eye(2)
    eigenvalues, eigenvectors = np.linalg.eigh(np.atleast_2d(covariance)); major = max(float(eigenvalues[-1]), 0.0); minor = max(float(eigenvalues[0]), 0.0); vector = eigenvectors[:, -1]
    rotation = float(np.degrees(np.arctan2(vector[1], vector[0]))) if major > 1e-6 and major - minor > .15 else 0.0
    points = set(pixels); boundary = 0
    for yy, xx in pixels: boundary += sum((yy + dy, xx + dx) not in points for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)))
    circularity = float(min(1.0, 4.0 * np.pi * len(pixels) / max(1.0, boundary * boundary * 1.15))); eccentricity = float(np.sqrt(max(0.0, 1.0 - minor / max(major, 1e-6)))); aspect = box_width / max(1.0, box_height)
    if aspect > 2.5 or aspect < 0.4: element_type = "line"
    elif circularity > 0.20: element_type = "dot"
    else: element_type = "shape"
    cx, cy = float(xs.mean()), float(ys.mean()); region = ("left" if cx < width * .33 else "right" if cx > width * .67 else "center") + "_" + ("top" if cy < height * .33 else "bottom" if cy > height * .67 else "middle")
    confidence = max(0.05, min(1.0, .45 + circularity * .35 + min(1.0, len(pixels) / 120.0) * .2))
    return DotFeature(id=index, center_x=round(cx / max(1, width - 1) * 100.0, 5), center_y=round(cy / max(1, height - 1) * 100.0, 5), radius_x=round(box_width / max(1, width) * 50.0, 5), radius_y=round(box_height / max(1, height) * 50.0, 5), diameter=round((box_width + box_height) / max(1, min(width, height)) * 100.0, 5), area=float(len(pixels)), bounding_box=tuple(round(v, 5) for v in (min_x / width * 100, min_y / height * 100, max_x / width * 100, max_y / height * 100)), circularity=round(circularity, 5), eccentricity=round(eccentricity, 5), rotation=round(rotation, 4), confidence=round(confidence, 5), region_id=region, element_type=element_type)


def detect_dot_features(mask: np.ndarray, min_area: int = 3, limit: int = 2000, debug: dict[str, Any] | None = None) -> list[DotFeature]:
    """检测 DOT/HALFTONE，并公开开发调试图层。"""
    mask = np.asarray(mask, dtype=bool); distance = _distance_transform(mask); components = _components(mask, min_area, max(limit * 2, limit)); regions: list[list[tuple[int, int]]] = []; all_peaks: list[tuple[int, int]] = []
    for component in components:
        split = _watershed_split(component, distance); regions.extend(split)
        if len(split) > 1:
            ys = np.asarray([p[0] for p in component]); xs = np.asarray([p[1] for p in component]); local = np.zeros_like(mask); local[ys, xs] = True; all_peaks.extend(_local_maxima(distance, local, max(2.0, float(distance[local].max()) * .72)))
    regions = regions[:limit]; features = [_feature_from_pixels(region, mask.shape[1], mask.shape[0], index) for index, region in enumerate(regions, 1)]
    if debug is not None:
        labels = np.zeros(mask.shape, dtype=np.int32)
        for index, region in enumerate(regions, 1):
            yy, xx = zip(*region); labels[np.asarray(yy), np.asarray(xx)] = index
        debug.update({"distance_transform": distance, "local_maxima": all_peaks, "watershed_labels": labels, "components": components})
    return features
