from __future__ import annotations

import math

import numpy as np

from .models import DotFeature, SpatialFields


def estimate_spatial_fields(features: list[DotFeature], grid_size: int = 16) -> SpatialFields:
    density = np.zeros((grid_size, grid_size), dtype=float); size = np.zeros_like(density); rotation = np.zeros_like(density); counts = np.zeros_like(density)
    points = []
    for feature in features:
        gx = min(grid_size - 1, max(0, int(feature.center_x / 100.0 * grid_size))); gy = min(grid_size - 1, max(0, int(feature.center_y / 100.0 * grid_size)))
        density[gy, gx] += 1.0; size[gy, gx] += feature.diameter; rotation[gy, gx] += feature.rotation; counts[gy, gx] += 1.0; points.append((feature.center_x, feature.center_y))
    if features:
        size = np.divide(size, counts, out=np.zeros_like(size), where=counts > 0); rotation = np.divide(rotation, counts, out=np.zeros_like(rotation), where=counts > 0); density /= max(1.0, density.max())
    nearest = []
    for index, point in enumerate(points):
        distances = [math.hypot(point[0] - other[0], point[1] - other[1]) for j, other in enumerate(points) if j != index]
        if distances: nearest.append(min(distances))
    nearest_mean = float(np.mean(nearest)) if nearest else 0.0
    spacings = np.asarray(nearest, dtype=float)
    anisotropy = float(np.std(spacings) / max(1e-6, np.mean(spacings))) if len(spacings) > 1 else 0.0
    # 可解释的全局/局部空间测量，供 Generator 候选评分和 Modifier 使用。
    points_np = np.asarray(points, dtype=float).reshape((-1, 2)) if points else np.empty((0, 2), dtype=float)
    unique_x = np.unique(np.round(points_np[:, 0], 2)) if len(points_np) else np.empty(0)
    unique_y = np.unique(np.round(points_np[:, 1], 2)) if len(points_np) else np.empty(0)
    grid_spacing = (
        float(np.median(np.diff(unique_x))) if len(points_np) > 2 and len(unique_x) > 1
        else float(np.mean(spacings)) if len(spacings) else 0.0,
        float(np.median(np.diff(unique_y))) if len(points_np) > 2 and len(unique_y) > 1
        else float(np.mean(spacings)) if len(spacings) else 0.0,
    )
    principal_direction = 0.0
    if len(points) > 2:
        covariance = np.cov(points_np, rowvar=False, bias=True)
        vector = np.linalg.eigh(np.atleast_2d(covariance))[1][:, -1]
        principal_direction = float(np.degrees(np.arctan2(vector[1], vector[0])))
    orientation_values = np.asarray([feature.rotation for feature in features], dtype=float)
    size_values = np.asarray([feature.diameter for feature in features], dtype=float)
    size_distribution = {"min": float(size_values.min()) if len(size_values) else 0.0, "max": float(size_values.max()) if len(size_values) else 0.0, "mean": float(size_values.mean()) if len(size_values) else 0.0, "std": float(size_values.std()) if len(size_values) else 0.0}
    lookup = {(round(x, 2), round(y, 2)) for x, y in points}
    radial_pairs = bilateral_pairs = 0; radial_hits = bilateral_hits = 0
    for x, y in points:
        radial_pairs += 1; radial_hits += int(any(abs((100 - x) - px) < 4 and abs((100 - y) - py) < 4 for px, py in points))
        bilateral_pairs += 1; bilateral_hits += int(any(abs((100 - x) - px) < 4 and abs(y - py) < 4 for px, py in points))
    symmetry = {"radial": radial_hits / max(1, radial_pairs), "bilateral": bilateral_hits / max(1, bilateral_pairs)}
    return SpatialFields(tuple(tuple(round(float(v), 6) for v in row) for row in density), tuple(tuple(round(float(v), 6) for v in row) for row in size), tuple(tuple(round(float(v), 6) for v in row) for row in rotation), round(nearest_mean, 6), round(anisotropy, 6), symmetry, tuple(round(float(v), 6) for v in grid_spacing), round(principal_direction, 5), round(float(orientation_values.mean()) if len(orientation_values) else 0.0, 5), round(anisotropy, 6), {key: round(value, 6) for key, value in size_distribution.items()})
