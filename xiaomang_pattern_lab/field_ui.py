"""Stable UI metadata for shared parameter fields.

Internal field ids are part of the project schema and must never be translated
in saved documents.  This module owns the user-facing Chinese labels,
descriptions and semantic ranges used by the Tk harness.
"""
from __future__ import annotations

FIELD_DISPLAY_NAMES = {
    "constant": "固定场",
    "linear_x": "X方向渐变",
    "linear_y": "Y方向渐变",
    "radial": "放射场",
    "attractor": "吸引场",
    "ring": "环形场",
    "wave": "波浪场",
    "stripe": "条纹场",
    "checker": "棋盘场",
    "spiral": "螺旋场",
    "image": "图片场",
    "noise": "有机噪声",
    "composite": "组合场",
}

FIELD_DESCRIPTIONS = {
    "constant": "所有元素使用相同影响值。",
    "linear_x": "参数从左向右连续变化。",
    "linear_y": "参数从上向下连续变化。",
    "radial": "从中心向外围产生渐变。",
    "attractor": "根据元素与控制点的距离产生变化。",
    "ring": "在指定圆环附近产生最强影响。",
    "wave": "按周期波形重复改变参数。",
    "stripe": "产生重复条带区域。",
    "checker": "产生二维交替区域。",
    "spiral": "围绕指定中心产生螺旋规律。",
    "image": "读取当前参考图灰度，驱动尺寸等参数连续变化。",
    "noise": "以世界坐标产生连续有机起伏；尺度越大，变化区域越大。",
    "composite": "将两个已有参数场以加法、相乘、最小、最大或混合方式组合。",
}

ROTATION_DISPLAY_NAMES = {
    "constant": "固定角度",
    "face_center": "朝向中心",
    "tangential": "切线方向",
    "attractor": "朝向吸引点",
}

ROTATION_DESCRIPTIONS = {
    "constant": "所有元素使用同一个旋转角度。",
    "face_center": "元素朝向旋转场中心。",
    "tangential": "元素沿中心圆周切线方向旋转。",
    "attractor": "元素朝向吸引控制点。",
}

FIELD_ORDER = tuple(FIELD_DISPLAY_NAMES)

def field_label(field_id: str) -> str:
    return FIELD_DISPLAY_NAMES.get(str(field_id), str(field_id))

def field_description(field_id: str) -> str:
    return FIELD_DESCRIPTIONS.get(str(field_id), "当前参数场没有可用说明。")

def rotation_label(mode: str) -> str:
    return ROTATION_DISPLAY_NAMES.get(str(mode), str(mode))

def rotation_description(mode: str) -> str:
    return ROTATION_DESCRIPTIONS.get(str(mode), "当前旋转方式没有可用说明。")
