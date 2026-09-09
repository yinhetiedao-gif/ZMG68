from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

Point = tuple[float, float]


@dataclass
class PatternSettings:
    active_generator: str = "radial"
    contour_type: str = "有机形"
    element_type: str = "线条 + 圆点"
    distribution: str = "均匀"
    direction: str = "向外法线"
    count: int = 160
    length: float = 30.0
    width: float = 1.2
    dot_radius: float = 3.0
    length_random: float = 10.0
    dot_random: float = 6.0
    noise_strength: float = 10.0
    noise_scale: float = 22.0
    rotation: float = 0.0
    offset: float = 0.0
    scale: float = 1.0
    spacing: float = 0.0
    seed: int = 42
    preview_quality: str = "标准"
    units: str = "mm"
    # 内部世界坐标统一以 mm 计算；此值是当前设计输出到 3D/STL 的目标成品宽度。
    target_width_mm: float = 100.0
    field_generator: str = "halftone"
    field_element: str = "点"
    field_shape: str = "圆"
    field_spacing: float = 5.0
    dot_size: float = 2.2
    line_width: float = 0.7
    field_scale: float = 1.0
    gradient_mode: str = "径向"
    gradient_strength: float = 72.0
    field_contrast: float = 25.0
    field_threshold: float = 8.0
    feather: float = 3.0
    field_blur: float = 0.0
    field_rotation: float = 0.0
    field_noise: float = 0.0
    smooth_noise: float = 12.0
    mask_type: str = "圆形"
    reference_image: str = ""
    # Field Generator 统一扩展参数（旧项目读取时自动采用这些默认值）。
    grid_columns: int = 0
    grid_rows: int = 0
    row_spacing: float = 0.0
    column_spacing: float = 0.0
    min_size: float = 0.25
    max_size: float = 5.0
    field_density: float = 100.0
    field_offset_x: float = 0.0
    field_offset_y: float = 0.0
    image_gamma: float = 1.0
    image_levels: int = 0
    image_invert: bool = False
    mask_strength: float = 100.0
    edge_softness: float = 0.0
    gradient_curve: str = "平滑"
    gradient_center_x: float = 50.0
    gradient_center_y: float = 50.0
    random_strength: float = 0.0
    random_size: float = 0.0
    random_rotation: float = 0.0
    random_position: float = 0.0
    random_density: float = 0.0
    noise_frequency: float = 1.0
    noise_offset: float = 0.0
    noise_octaves: int = 1
    distortion_wave: float = 0.0
    distortion_twist: float = 0.0
    distortion_bend: float = 0.0
    distortion_curl: float = 0.0
    distortion_flow: float = 0.0
    attraction: float = 0.0
    repulsion: float = 0.0
    element_fill: str = "实心"
    element_aspect: float = 1.0
    three_d_thickness: float = 1.2
    three_d_quality: str = "标准"
    three_d_roundness: float = 55.0
    three_d_blend: float = 55.0
    three_d_min_feature: float = 0.8
    # 参考图重建不是像素描摹：以下参数描述从分析结果拟合出的空间规则。
    reference_rebuild_enabled: bool = False
    reference_strength: float = 100.0
    reference_structure_preservation: float = 85.0
    reference_creative_variation: float = 0.0
    reference_void_size: float = 0.0
    reference_void_rotation: float = 0.0
    reference_void_feather: float = 2.0
    reference_corner_emphasis: float = 0.0
    reference_vortex: float = 0.0
    reference_center_x: float = 50.0
    reference_center_y: float = 50.0
    reference_warp_radius: float = 48.0
    reference_corner_density: float = 0.0
    reference_size_gradient: float = 0.0
    reference_density_gradient: float = 0.0
    # 经视觉分析得到的真实元素工作单。它保存的是中心、尺寸、方向等几何特征，
    # 不是位图；参考重建可在此基础上继续由 Modifier 变化。
    reference_elements: list[dict] = field(default_factory=list)
    reference_use_extracted_elements: bool = False
    reference_match_score: float = 0.0
    reference_compare_mode: str = "重建结果"
    reference_opacity: float = 45.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict) -> "PatternSettings":
        allowed = {field.name for field in cls.__dataclass_fields__.values()}
        data = {key: value[key] for key in allowed if key in value}
        # V0.2 的项目使用“均匀分布”；V1 统一为更短的枚举值。
        if data.get("distribution") == "均匀分布": data["distribution"] = "均匀"
        return cls(**data)


@dataclass
class Project:
    settings: PatternSettings = field(default_factory=PatternSettings)
    contour: list[Point] = field(default_factory=list)
    contour_source: Literal["builtin", "imported", "drawn"] = "builtin"
    custom_element: list[Point] = field(default_factory=list)
    # 连续高度场的控制点；每点保存 x/y、delta、半径和衰减，旧项目默认为空。
    height_controls: list[dict] = field(default_factory=list)
    # 二维编辑视图状态；三维 Viewer 状态不再属于项目格式。
    view_2d: dict = field(default_factory=lambda: {"zoom": 1.0, "pan_x": 0.0, "pan_y": 0.0})
    favorite: bool = False
    name: str = "未命名纹样"
    # Stage A POC 接入正式项目时保存的可编辑二维场景快照；不保存 SVG/位图。
    reference2d_document: dict | None = None
    # Reference Reconstruction V1 的统一文档；包含真实 Element、Generator、Modifier 和 Override。
    editable_pattern_document: dict | None = None

    def to_dict(self) -> dict:
        return {
            "project_version": 7,
            "name": self.name,
            "settings": self.settings.to_dict(),
            "contour": [[round(x, 8), round(y, 8)] for x, y in self.contour],
            "contour_source": self.contour_source,
            "custom_element": [[round(x, 8), round(y, 8)] for x, y in self.custom_element],
            "height_controls": self.height_controls,
            "view_2d": self.view_2d,
            "favorite": self.favorite,
            "reference2d_document": self.reference2d_document,
            "editable_pattern_document": self.editable_pattern_document,
        }

    @classmethod
    def from_dict(cls, value: dict) -> "Project":
        contour = [(float(p[0]), float(p[1])) for p in value.get("contour", []) if len(p) >= 2]
        return cls(
            settings=PatternSettings.from_dict(value.get("settings", {})),
            contour=contour,
            contour_source=value.get("contour_source", "imported"),
            custom_element=[(float(p[0]), float(p[1])) for p in value.get("custom_element", []) if len(p) >= 2],
            height_controls=[dict(point) for point in value.get("height_controls", []) if isinstance(point, dict)],
            view_2d=dict(value.get("view_2d", {})) if isinstance(value.get("view_2d", {}), dict) else {"zoom": 1.0, "pan_x": 0.0, "pan_y": 0.0},
            favorite=bool(value.get("favorite", False)),
            name=value.get("name", "未命名纹样"),
            reference2d_document=dict(value.get("reference2d_document")) if isinstance(value.get("reference2d_document"), dict) else None,
            editable_pattern_document=dict(value.get("editable_pattern_document")) if isinstance(value.get("editable_pattern_document"), dict) else None,
        )
