from __future__ import annotations

"""确定性的 Generator / Modifier Fitting。

这里只做可解释的几何测量和候选打分。它永远不能阻断 Stage A：分数不足时
返回 Direct Element Mode，已检测的元素依然完整存在。
"""

import math
import numpy as np

from .models import ClassificationResult, DotFeature, SpatialFields


def _median_step(values: np.ndarray, fallback: float = 1.0) -> float:
    values = np.unique(np.round(values.astype(float), 6))
    differences = np.diff(np.sort(values))
    differences = differences[differences > 1e-5]
    return float(np.median(differences)) if len(differences) else float(fallback)


def _radial_score(features: list[DotFeature]) -> float:
    if len(features) < 4:
        return 0.0
    points = np.asarray([(item.center_x, item.center_y) for item in features], dtype=float)
    center = points.mean(axis=0)
    radii = np.linalg.norm(points - center, axis=1)
    return float(max(0.0, min(1.0, 1.0 - np.std(radii) / max(1e-6, np.mean(radii)))))


def _grid_score(features: list[DotFeature], fields: SpatialFields) -> float:
    if len(features) < 6:
        return 0.0
    points = np.asarray([(item.center_x, item.center_y) for item in features], dtype=float)
    xs, ys = np.unique(np.round(points[:, 0], 1)), np.unique(np.round(points[:, 1], 1))
    occupancy = len(points) / max(1, len(xs) * len(ys))
    return float(max(0.0, min(1.0, .55 * occupancy + .45 * math.exp(-fields.spacing_anisotropy))))


def _grid_definition(features: list[DotFeature]) -> tuple[dict, dict[str, dict[str, float]]]:
    points = np.asarray([(item.center_x, item.center_y) for item in features], dtype=float)
    origin_x, origin_y = float(points[:, 0].min()), float(points[:, 1].min())
    spacing_x, spacing_y = _median_step(points[:, 0]), _median_step(points[:, 1])
    bindings = {
        f"element-{index:04d}": {"u": float((item.center_x - origin_x) / spacing_x), "v": float((item.center_y - origin_y) / spacing_y)}
        for index, item in enumerate(features, 1)
    }
    return {
        "origin_x": origin_x, "origin_y": origin_y,
        "spacing_x": spacing_x, "spacing_y": spacing_y,
        "scale_x": 1.0, "scale_y": 1.0,
        "columns": int(round((points[:, 0].max() - origin_x) / spacing_x)) + 1,
        "rows": int(round((points[:, 1].max() - origin_y) / spacing_y)) + 1,
    }, bindings


def _radial_definition(features: list[DotFeature]) -> tuple[dict, dict[str, dict[str, float]]]:
    points = np.asarray([(item.center_x, item.center_y) for item in features], dtype=float)
    center_x, center_y = float(points[:, 0].mean()), float(points[:, 1].mean())
    bindings = {}
    for index, item in enumerate(features, 1):
        dx, dy = item.center_x - center_x, item.center_y - center_y
        bindings[f"element-{index:04d}"] = {"radius": float(math.hypot(dx, dy)), "angle": float(math.degrees(math.atan2(dy, dx)))}
    return {"center_x": center_x, "center_y": center_y, "radius_scale": 1.0, "rotation": 0.0}, bindings


def _modifier_stack(features: list[DotFeature], fields: SpatialFields) -> tuple[dict, ...]:
    sizes = np.asarray([item.diameter for item in features], dtype=float)
    size_variation = float(sizes.std() / max(1e-6, sizes.mean())) if len(sizes) else 0.0
    # 初始值为零：检测出的真实元素就是初始几何，修改器在用户调整后才改变规则。
    return (
        {"name": "SizeGradient", "parameters": {"enabled": False, "axis": "y", "strength": 0.0, "inferred_variation": round(size_variation, 6)}},
        {"name": "DensityField", "parameters": {"enabled": False, "axis": "y", "strength": 0.0, "inferred_anisotropy": round(fields.spacing_anisotropy, 6)}},
        {"name": "RotationField", "parameters": {"enabled": False, "axis": "y", "strength": 0.0, "inferred_angle": round(fields.local_orientation_mean, 6)}},
        {"name": "SimpleWarp", "parameters": {"enabled": False, "axis": "x", "amplitude": 0.0, "frequency": 1.0, "inferred_distortion": round(fields.position_distortion, 6)}},
        {"name": "Mask", "parameters": {"enabled": False, "shape": "circle", "center_x": 50.0, "center_y": 50.0, "radius": 50.0, "feather": 0.0}},
    )


def fit_generator(features: list[DotFeature], fields: SpatialFields, threshold: float = .48) -> tuple[dict, tuple[dict, ...], dict[str, float]]:
    """计算候选分数并返回可 Rebuild 的规则参数和稳定元素绑定。"""
    scores = {
        "regular_grid": _grid_score(features, fields),
        "radial": max(fields.symmetry.get("radial", 0.0), _radial_score(features)),
        # 这些仅是候选评分，用于提示后续扩展；V1 不把它们伪装为已实现的基础模型。
        "spiral": max(0.0, min(1.0, fields.symmetry.get("radial", 0.0) * .7 + fields.spacing_anisotropy * .2)),
        "wave": max(0.0, min(1.0, (1.0 - fields.spacing_anisotropy) * .45 + (1.0 if any(abs(f.rotation) > 10 for f in features) else 0.0) * .25)),
        "flow": max(0.0, min(1.0, fields.spacing_anisotropy * .65 + (1.0 if any(f.element_type == "line" for f in features) else 0.0) * .35)),
    }
    base, score = max(scores.items(), key=lambda item: item[1]) if scores else (None, 0.0)
    # V1 只把真正已有 Rebuild 公式的 Grid/Radial 提升为 Parametric Mode。
    if score < threshold or base not in {"regular_grid", "radial"}:
        generator = {"mode": "direct", "base": None, "score": round(float(score), 6), "threshold": threshold, "candidates": scores}
        return generator, (), scores
    parameters, bindings = _grid_definition(features) if base == "regular_grid" else _radial_definition(features)
    generator = {
        "mode": "parametric", "base": base, "score": round(float(score), 6), "threshold": threshold,
        "candidates": scores, "parameters": parameters, "bindings": bindings,
    }
    return generator, _modifier_stack(features, fields), scores


def match_generator(classification: ClassificationResult, fields: SpatialFields, legacy_generator: str | None, features: list[DotFeature] | None = None) -> tuple[dict, tuple[dict, ...]]:
    """兼容旧 UI 读取字段，但不允许旧建议覆盖数学拟合的 mode。"""
    detected = list(features or [])
    if not detected:
        detected = [DotFeature(0, 50, 50, 1, 1, 2, 1, (49, 49, 51, 51), .5, 0, 0, classification.confidence, "center_middle")]
    generator, modifiers, _ = fit_generator(detected, fields, threshold=.48)
    if generator["mode"] == "direct":
        generator["suggested_base"] = (legacy_generator if classification.primary_type != "DOT" else ("halftone" if "GRADIENT" in classification.secondary_types else "dot_matrix")) or "shape_mask"
        generator["base_generator"] = generator["suggested_base"]
    else:
        generator["base_generator"] = "halftone" if classification.primary_type == "DOT" and "GRADIENT" in classification.secondary_types else "dot_matrix"
    return generator, modifiers
