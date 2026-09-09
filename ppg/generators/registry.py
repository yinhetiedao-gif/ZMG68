"""可持续扩展的 Generator Library 注册表。"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class GeneratorSpec:
    key: str
    name_zh: str
    category: str
    available: bool
    description: str
    apply: Callable | None = field(default=None, compare=False)


class GeneratorRegistry:
    def __init__(self): self._items: dict[str, GeneratorSpec] = {}
    def register(self, spec: GeneratorSpec) -> None: self._items[spec.key] = spec
    def get(self, key: str) -> GeneratorSpec | None: return self._items.get(key)
    def all(self) -> list[GeneratorSpec]: return list(self._items.values())


def default_registry() -> GeneratorRegistry:
    registry = GeneratorRegistry()
    registry.register(GeneratorSpec("radial", "放射纹样", "结构", True, "沿闭合轮廓生成向外或向内的参数化元素。"))
    registry.register(GeneratorSpec("halftone", "半调点阵", "点线面", True, "用连续明暗场控制点、线或面尺寸；支持参考明暗、径向、线性和波纹渐变。"))
    registry.register(GeneratorSpec("dot_matrix", "规则点阵", "点线面", True, "可编辑网格、点形、间距、Mask、旋转和可复现噪声。"))
    registry.register(GeneratorSpec("gradient_dots", "渐变点阵", "点线面", True, "根据渐变场或参考明暗生成尺寸连续变化的点阵。"))
    registry.register(GeneratorSpec("point_line_plane", "点线面构成", "点线面", True, "以统一的密度场混合点、线和面，生成新的构图变体。"))
    registry.register(GeneratorSpec("shape_mask", "轮廓遮罩", "点线面", True, "将点线面生成规则限制在圆、星形、心形或圆角矩形 Mask 内。"))
    registry.register(GeneratorSpec("grid_distortion", "网格变形", "点线面", True, "在可控平滑噪声下扭曲规则网格，保持 Seed 可重现。"))
    registry.register(GeneratorSpec("flow_field", "流场", "点线面", True, "用连续噪声场控制线元素方向和位置。"))
    registry.register(GeneratorSpec("wave_field", "波场", "点线面", True, "使用波形位置与方向调制生成可编辑波场。"))
    registry.register(GeneratorSpec("noise_field", "噪声场", "点线面", True, "用分形平滑噪声控制元素尺寸、密度和构图。"))
    registry.register(GeneratorSpec("raster_lace", "黑白图转打印", "打印", True, "黑白图片转 SVG 与圆角平滑无底板 STL。"))
    for key,name,category in (("voronoi","Voronoi","结构"),("particle","粒子场","场"),("reaction_diffusion","反应扩散","生长"),("branch","分枝 / L-System","生长"),("ripple","波纹","场"),("honeycomb","蜂窝","结构"),("weave","织物","结构"),("coral","珊瑚生长","生长")):
        registry.register(GeneratorSpec(key,name,category,False,"已预留统一 Generator API；需要新增算法模块后启用。"))
    return registry
