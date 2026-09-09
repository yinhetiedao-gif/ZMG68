# 小芒造物主规格（当前收缩阶段）

版本：1.6.14（上游 Raster→SVG POC 已验收；安装包待在可访问构建依赖的桌面环境重新生成）  
状态：以 `Reference Image → Editable 2D Geometry` 为最高优先级。

## 产品边界

小芒造物是面向非程序员的中文二维参数化设计与制造输出工具。当前工作区只围绕真实、可编辑的二维对象展开；不提供自研实时三维查看器、相机、渲染模式或预览 Mesh。

不在本阶段开发：3D Preview/Viewer、相机轨道/平移/缩放、透视与正交视图、线框/材质/热力图、Viewport 灯光/AO/阴影、实时 3D FPS/缓存、2D 参数触发的实时 3D 更新、素材库、案例库和无关的新 Generator。

## 唯一生产链

```text
Reference Image
  → Preprocess
  → Primitive Detection
  → Editable Elements
  → Spatial Analysis
  → Generator / Modifier Fitting
  → EditablePatternDocument
  → 2D Local Editing
  → Geometry Cleanup
  → Final 3D Build
  → Manufacturing Validation
  → Validated STL Export
```

参数拟合不是元素重建的前置条件。只要 Primitive Detection 成功，必须生成可保存、选择、移动、缩放、旋转、删除、复制和分组的真实元素；拟合低分时使用 `Direct Element Mode`。

## 数据所有权

- `ReferenceLayer`：原始参考图和其元数据，只用于对照，不得充当最终几何。
- Raster→SVG 优先调用项目内安装的上游 `ujo78/imagetosvg-mcp` MCP 工具（convert/inspect/edit/render/optimize）；Python 适配器不得重复实现矢量化。
- `GeometryLayer`：只读取 `EditableElement`（DOT/ELLIPSE/LINE/SHAPE 等）的物化 `elements`。
- `EditablePatternDocument`：持久化 `canvas, reference, generator, modifiers, elements, overrides, masks, fields, metadata, base_elements, added_elements`。
- Rebuild 固定为 `base_elements + added_elements → Generator + Modifier Stack → Local Overrides → elements`，不得重新读取 Raster。
- Final Manufacturing Mesh 只由当前 `EditablePatternDocument.elements`（若存在）或兼容的二维规则工作单产生；不得从 Canvas 位图或预览网格导出。

## 3D 与显示边界

软件保留 `生成最终模型` 与 `导出 STL`。它们在后台运行二维清理、本地 SDF 或显式 Blender 兼容后端、网格修复、封闭/组件/法线/单位审计和 STL reload 验证。完成后 UI 只显示：尺寸、三角面数、组件数、Watertight 状态和制造检查结果。

`PreviewProvider` 是未来显示集成的唯一窄接口：

```text
load_model() / open_model() / update_model() / fit_view()
get_bounds() / capture_preview() / close()
```

当前必须使用无状态 `NullPreviewProvider`。任何未来第三方 Viewer 只能显示最终制造模型，禁止接管 Generator、Reference Reconstruction、Editable Geometry、Height Field、Geometry Cleanup、Manufacturing、STL 或项目状态。

## 交付门槛

1. 隐藏 ReferenceLayer 后几何仍完整存在。
2. 单元素和多元素编辑会真实改变 `EditablePatternDocument`。
3. 保存/重开不需重新分析参考图。
4. Parametric Fitting 失败仍可 Direct Element 编辑。
5. Generate Final Model / Export STL 不依赖任何 Viewer、相机或 Preview Mesh。
6. 最终 STL 必须通过 Watertight、单组件、裸边、非流形、退化面与尺寸/mm 检查。

## 开发顺序

P0 Reference → Editable 2D  
P1 EditablePatternDocument  
P2 Geometry Cleanup  
P3 Final 3D Build  
P4 Manufacturing Validation  
P5 Validated STL  
P6 Optional Third-Party Viewer（未启动）
