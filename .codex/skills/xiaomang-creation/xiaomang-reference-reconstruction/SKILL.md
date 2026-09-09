---
name: xiaomang-reference-reconstruction
description: 将限定范围的 DOT、HALFTONE 与几何点阵参考图重建为真实可编辑二维元素；检测优先，参数化拟合失败时自动保留 Direct Element Mode。
---

# 小芒造物 Reference Reconstruction

## 适用范围

V1 只处理 Circle、Ellipse、Dot Matrix、Halftone、Size/Density Gradient、Mask、Rotation 和 Simple Warp。任意照片、复杂插画和未知视觉类型必须明确标记为低置信度，不得伪装成已完成的参数化重建。

## 两阶段管线

```
Reference → Preprocess → Primitive Detection → Editable Elements
          → Spatial Analysis → Generator/Modifier Fitting → Editable Pattern Document
```

Stage A（检测与真实元素）独立于 Stage B（规则拟合）。只要检测到元素，就必须输出 `EditablePatternDocument`；拟合分数低于阈值时使用 `generator.mode=direct`，不能丢弃元素或只显示 bitmap。

## 检测约束

- 灰度、去噪、阈值化后使用 connected components 取得候选区域。
- 粘连 DOT 必须使用 distance transform + local maxima + watershed/Voronoi 分区；禁止仅以一个连通组件作为最终圆点。
- 每个元素保存 `id, primitive_type, x, y, width, height, radius, rotation, opacity, enabled, group_id, source, confidence`。
- OpenCV、scikit-image、SciPy 存在时可作为加速后端；运行时不可用时使用项目内 NumPy 确定性后备，不能阻断导入。

## 文档与图层

`EditablePatternDocument` 的固定字段为 `canvas, reference, generator, modifiers, elements, overrides, masks, fields, metadata`；实现还必须持久化 `base_elements`（检测基线）和 `added_elements`（用户复制/新增）。Reference Layer 只保留原图元数据；Geometry Layer、Canvas、导出器只消费当前物化的真实 `elements`。Rebuild 固定为 `base_elements + added_elements → Base Generator + Modifier Stack → Local Overrides → elements`，禁止在 Rebuild 时重新读取 Raster。元素支持点选、框选、移动、缩放、旋转、删除、复制和分组，Override 使用稳定的元素 ID。

## Debug Visualization

开发验证可通过 `ppg.reference2d.debug_visualization.render_debug` 输出原图、检测框、中心点、半径和 watershed 层。调试数组不得写入项目文档或导出几何。

## 验收门槛

隐藏 Reference Layer 后，元素仍可见并可编辑；单点修改只影响该元素；框选批量操作、Undo/Redo、保存/恢复、规则 Rebuild 后 Local Override 保留必须通过自动化测试。未达到门槛不得将 Reference → Editable 2D 标记为完成。
