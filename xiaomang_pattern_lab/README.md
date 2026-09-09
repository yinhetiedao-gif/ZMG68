# Xiaomang Pattern Lab / 小芒图案实验室

## 开发安全与当前 Gate

开发前必须读取仓库根的 `AGENTS.md`、`DEVELOPMENT_SAFETY.md`、`GATE_STATUS.md`。
源码已纳入本地 Git；新功能仅在 feature/*，保护快照不可覆盖。
Gate 0 已完成并由 `backup/stable-baseline` 保护；当前只执行 Shared Field Engine 的 Gate 1。
测试通过前不得继续下一 Gate。Git 备份不包含 .venv/.runtime/node_modules。
独立回退目录需安装 requirements 和构建 external/imagetosvg-mcp（锁文件已纳入 Git）。

启用本地分支保护钩子：`git config core.hooksPath .githooks`。
全量检查：`.\xiaomang_pattern_lab\.venv\Scripts\python.exe -m unittest discover -s tests -v`
（在仓库根运行）。日志和已知失败见 `GATE_STATUS.md`。

这是一个可删除的技术验证项目，不是正式版小芒造物。它验证的唯一闭环是：

`PNG/JPG → 预处理 Adapter → Vectorization Adapter → SVGNormalizer → PatternDocument → 编辑 → SVG / JSON`

## 转换模式

实验台将“图片能否还原”为几何与“图片能否参数化解释”分开处理：

- **保真映射（默认）**：`Raster Image → Binary Mask → Filled Vector Geometry → Editable 2D Geometry`。黑色像素被保留为闭合实心区域；复杂连通的点、线、面会成为 `FilledRegionElement`，而不会被强行拆成 Circle、Line 或 Generator。导出的区域始终使用 `fill="#000000"` 与 `stroke="none"`，隐藏原图后仍显示完整黑色 Geometry。
- **参数化识别**：保留原有的 Circle／Ellipse／Rect 恢复与 Grid 测试链路，供规则点阵进一步分析。它是增强路线，不是保真映射成功的前提。

两条路线都写入同一个 `PatternDocument`，所以都能继续使用选择、移动、缩放、旋转、复制、删除、Shift 多选、保存／重新打开与 SVG 导出。保真区域还可在自由元素模式下执行布尔并集／差集；“局部解构（Analyze Selected Region）”仍是后续阶段，不会改变当前保真结果。

## 分层

```text
ppg.foundation/                    # Xiaomang Core Engine：无 UI、无 MCP 直接依赖
  PatternDocument / SVGNormalizer / SVG Export / Persistence
  ImageProcessingAdapter / VectorizationAdapter

xiaomang_pattern_lab/session.py    # UI 无关的实验编排与真实 Element 操作
xiaomang_pattern_lab/ui_harness.py # 可删除的 Tk UI Test Harness
xiaomang_pattern_lab/adapters.py   # 预处理与 SVG 预览的可替换实现
xiaomang_pattern_lab/faithful_mapping.py # 保真映射编排 Adapter
xiaomang_pattern_lab/recognition.py # 多尺度 dot 恢复；只从二值图标注/恢复真实 Element
xiaomang_pattern_lab/pattern_analyzer.py # 只读取 PatternDocument.elements 的 Grid / Radial / Along Curve 候选分析
xiaomang_pattern_lab/parametric_families.py # Radial / Along Curve / Free Parametric Model 与共享 Size / Rotation Field
xiaomang_pattern_lab/evaluation.py # 唯一 Evaluate Pipeline：任一 ParametricModel → Modifier → Local Override → Element
xiaomang_pattern_lab/placement_assignment.py # PlacementSlot → Prototype Registry → Assignment / Replacement（Gate 1）
xiaomang_pattern_lab/shared_modifiers.py # Geometry Source 之上的公共 Size/Rotation/Mask/Override 效果层
xiaomang_pattern_lab/shared_fields.py # Gate 1 纯 Scalar Field / Registry / Mapping / Size Consumer
xiaomang_pattern_lab/element_debug.py # Element、可渲染性与实心填充统计
xiaomang_pattern_lab/verification.py # 六图无界面验收和量化指标
```

### Unified Placement / Prototype / Assignment（Gate 1）

当前新增的是可选、无 UI 的基础层，不会替换已稳定的 Raster→SVG、Canvas 或 GridAnalyzer：

`ImportedElementSlotProvider / GridSlotProvider → PlacementSlot → ElementPrototype → AssignmentEngine → Elements`

导入图元和现有 Grid cell 都使用稳定 `slot_id`；`ShapePrototypeRegistry` 复用既有 Circle、Ellipse、Rect、Polygon、CustomPath 原型；`ReplacementMap` 只改变 Evaluate 结果，源图元仍保留，因此可以恢复。默认 `enabled=false`、无替换、随机关闭时，Circle Grid 输出与旧路径逐项一致。状态写入 `PatternDocument.metadata`，可 Save/Load。下一阶段再在此层上增加多形状池、规则分配与 UI 控件。

### Shared Parametric Modifier Stack

“自由参数化”不再是 Grid 识别失败后的互斥模式，而是可叠加在任意 Geometry Source 上的公共效果层：

`Imported Elements / Grid / Radial / Curve → SharedModifierStack → Shape Assignment → Local Override → Final Elements`

Grid 继续只负责行列、间距、Basis、旋转和 Origin；导入图片即使没有可靠 Grid，也可以直接应用 Size Field、Rotation Field、Mask 和 Local Override。提取 Grid 后，已有共享效果状态不会被清除。源元素快照写入 metadata，防止连续调整在前一次结果上累乘，并支持 Save/Load。

Core Engine 的任何模块都不会导入 Tk、Pillow、MCP、CLI 或第三方 Skill。具体的 `ImageToSVGVectorizationAdapter` 位于 `ppg.integrations`，实验台的 SVG 预览也使用独立 Adapter；两者均不属于 Core Engine。

### Shared Field Engine — Gate 1

Gate 1 将既有 **Linear X / Linear Y Size** 迁移到同一套可替换的共享参数场内核，
没有增加第二套元素或画布状态：

`Source Geometry → FieldContext（世界坐标/mm）→ SharedFieldEngine → SizeModifier → 既有 Rotation/Mask → Local Override → Final Elements → Canvas`

- `ConstantField` 与 `LinearField` 都只输出规范化 `0.0～1.0` 标量，绝不永久修改 `source_elements`。
- `FieldRegistry` 以稳定 `field_id` 管理对象；一个场可被多个 Modifier 引用，且每次 Evaluate 对同一场只计算一次。
- `FieldMapping` 负责输出范围、反转、钳制、强度、指数 Falloff 与 Linear/Ease/Bell/Step 曲线；Size 的 neutral 值为 `1.0`，所以强度为零不会让图元消失。
- `PatternDocument.fields[]` 与 `PatternDocument.modifiers[]` 保存 JSON 兼容的声明式图；旧工程没有这些字段时仍可读取。Gate 1 只写入 Linear Size 图，Rotation、Position、Radial、Attractor 和 UI Handle 留待后续 Gate。
- 已有“应用参数场”控件仍可用，但首次应用现在会捕获源快照；重复应用、Undo/Redo、Save/Load 和停用效果都不会累乘尺寸。

### Shared Field Engine — Gate A: RingField

Gate A 只新增 `RingField`，不新增平行参数化系统。它按元素的世界坐标计算
“距离指定半径越近，值越高”的环形标量：中心、半径、环宽、Falloff 和 Invert
都以可序列化字段保存，输出始终为 `0.0～1.0`。已有 `SizeModifier` 可以直接消费
它；RingField 不修改 source geometry，也不操作 Canvas。Wave、Stripe、Checker、Spiral
及新的 Field UI 刻意留在后续独立 Gate。

### Shared Field Integration — Gate A.5

Gate A.5 将 `PatternDocument.fields[] / modifiers[]` 接回唯一的
`evaluate_pattern_document()` 入口：`PatternDocument field graph → SharedFieldEngine
→ SharedModifierStack（Rotation / Mask / Local Override）→ Final Elements → Canvas`。
因此保存后直接读取文档、Grid 生成和导出都真正消费 Ring/Linear 图，而不是只把
图作为元数据保存。已迁移的 Size Field 只执行一次，避免兼容栈与声明式图重复缩放；
旧 Linear X/Y 的输出和 SVG 保持字节级兼容。Ring 现在也可从“参数化效果”面板选择，
并提供中心、半径、环宽与反转参数。Gate A.5 不新增 Wave、Stripe、Checker 或 Spiral。

## 启动实验台

```powershell
.\start_pattern_lab.ps1
```

启动脚本自动查找/验证项目运行时、创建 `.venv`、安装 `requirements.txt` 并进行导入自检；运行失败的完整错误写入 `work\diagnostics\last-launch-error.txt`。可先运行 `./diagnose_pattern_lab.ps1` 查看环境诊断。

实验窗口只提供：PNG/JPG 导入、二值预处理、矢量化、原图/矢量/叠加切换、隐藏原图验证、点击选择、直接拖动移动、选框四角缩放、X/Y 标尺、50%/100%/200% 等比例缩放、鼠标中键平移、Inspector 数值编辑、撤销/重做、复制、删除、导出 SVG、保存/重新打开 PatternDocument 与转换日志。Canvas 的所有交互均通过统一的 `screenToWorld()` / `worldToScreen()` 变换，PatternDocument 是唯一几何数据源。

本轮增加了两个只用于验证的基础能力：

- **Canvas Direct Manipulation**：Circle/Ellipse/Rect 以原生 Canvas 静态图元显示。`pointermove` 只写入 `InteractionState`，通过 Tk `after_idle` 合帧更新选中项和控制点；鼠标松开后才一次性提交 PatternDocument、写入 1 条 Undo、序列化 SVG。左侧 Inspector 在拖动中限频约 15 Hz。
- **规则矩阵测试**：可从真实 Element 的 X/Y 聚类、行列占用率和位置误差推断 Grid，不通过元素数量猜测。`GridParametricModel + SizeGradientModifier + MaskModifier + LocalOverride` 会物化为真实 Element；参数重建不会覆盖局部移动和缩放。当前只包含规则矩阵与这两种 Modifier，不包含其他 Generator。

### 导入图片的参数化尝试

固定测试图和用户导入 PNG/JPG 现在共享同一条路径：

`Image → SVGNormalizer → PatternDocument.elements → PatternAnalyzer → GridFitResult → 用户确认 → GridParametricModel`

系统不会读取文件名、fixture id 或预写的行列参数。点击“尝试参数化”只测量当前 `PatternDocument.elements`：若得到可靠 Grid，会显示行/列、间距、旋转、残差、缺失单元数和 Fit Score；用户再点击“转换为参数化矩阵”后，左侧矩阵参数才控制当前导入图的 Geometry。低分图案会明确保持“自由元素”模式，不丢失任何元素。

### Multi-Family Parametric Analysis：结构或自由场

点击“尝试参数化”会同时检查当前真实 Elements 的三种结构，而不是把所有图片强行塞进矩阵：

`Elements → PatternAnalyzer → Grid / Radial / Along Curve / Free fallback → ParametricModel → shared Modifier → Local Override → Evaluate`

- **Grid / Matrix**：继续使用 Matrix V3 的二维晶格、任意 ElementPrototype、缺格、斜向 Basis 与独立尺寸场。
- **Radial / 放射**：通过共同中心、半径、角度覆盖与角度步长识别圆环/放射序列，得到数量、中心、半径、起止角与单元尺寸。
- **Along Curve / 沿曲线**：通过真实 element center 的邻接关系和连续间距排序成 polyline，得到路径、元素数量、间距与沿路径旋转。
- **Free Parametric / 自由参数化**：若没有候选达到可靠阈值，系统保留原始可编辑 Elements，并允许它们共用 Size Field、Rotation Field、Mask 和逐元素 Local Override；“未识别出生成结构”不再等于“不能参数化”。

共享 Size Field 支持 Constant、Linear X、Linear Y、Radial、Attractor；Rotation Field 支持 Constant、Face Center、Tangential、Attractor。三类结构和自由场都能继续使用 Canvas 拖动、缩放、旋转、删除、Undo/Redo、保存/重开和 SVG 导出。Grid 专用行列/Basis 面板仅在转换为规则矩阵时启用。

### Matrix Parametric V3：通用二维晶格

当前唯一的参数化闭环是：

`用户 PNG/JPG → SVG / Editable Elements → PatternAnalyzer → 用户确认 → GridParametricModel → Modifier → Local Override → Evaluate → 保存 / SVG`

- **FREE MODE**：`PatternDocument.elements` 是独立可编辑的原始 Geometry；参数化失败绝不会阻止继续移动、缩放、旋转、删除或复制。
- **Grid 与单元形状分离**：Grid 只定义 `rows / columns / origin / Basis U / Basis V`，并遵循 `P(row,column)=Origin+column·BasisU+row·BasisV`；`ElementPrototype` 才定义单元形状。Circle、Ellipse、Rect、闭合 Polygon 和任意闭合 SVG Path 都可成为原型。无法命名的闭合 Path 会保留为 `CustomPathPrototype`，绝不退化为 Circle。
- **通用 2D Lattice Fit**：KNN 邻域、方向直方图与稳健整数格坐标拟合任意两条不共线基向量。因此水平、旋转、斜向、非正交、部分裁切、缺格和大 Margin 都可进入同一 Grid 流程；不再要求元素拥有相同 X/Y，也不根据画布边界判断矩阵。
- **尺寸场完全独立**：位置格子只看 centroid。完成位置拟合后才尝试 Horizontal、Vertical、Center/Edge、Radial 或 Elliptical Radial Size Field；拟合不足时每格的原始尺寸作为 Local Override 保留，绝不使 Grid 失败。
- **PARAMETRIC MODE**：`evaluation.evaluate_pattern_document(document)` 是唯一计算入口。它按 `Grid + ElementPrototype → Size / Mask Modifier → Local Override` 生成当前 Element；Canvas 只渲染这一结果，不保留第二套 Geometry State。
- **位置优先拟合**：`ElementAnchor` 从每个可见 Element 提取 centroid、bounding box、area、rotation 与 source type。GridAnalyzer 只基于 centroid 位置拟合，尺寸变化不会使 Halftone / Gradient Matrix 失去 Grid；Canvas 边距也不参与拟合。
- **分析容差与诊断**：严格 / 标准 / 宽松三档分别控制位置容差、允许缺格比例和内点率。无论成功或失败，界面均显示候选数、内点数、行列、U/V 基向角、间距、位置残差、占用率、形状聚类比例和 Grid Fit Score；失败会标明具体门槛。
- **Mask Modifier**：可使用矩形、圆形或已序列化的导入路径多边形控制格点可见性；关闭后立即恢复基础 Grid。掩膜使用世界坐标（mm），不会修改源图或源 Element。
- **缺失单元**：GridAnalyzer 以 OccupancyMap 允许少量缺点。识别到的逻辑空格会保存为 `visible=false` 的 Local Override，因此转换后不会自动补成黑色单元。
- **Bake**：点击“烘焙为自由元素”后会先 Evaluate 一次，再解除参数化关系；生成的当前 Geometry 可继续复制、布尔编辑和独立修改。

Grid Element 的 ID 按行列稳定生成（例如 `grid:r3:c5`；旧项目的 `grid-r3-c5` 会在读取时自动迁移）。局部缩放保存为比例：若基础宽度从 10 mm 改为 12 mm，一个 0.8 的局部缩放会得到 9.6 mm，而不是丢失人工调整。无法完整解释的源尺寸会继续保留为 Per-Cell Local Override。

导入后右侧 **Element Debug** 会显示 `Detected Element Count`、`Renderable Element Count`、`Visible Filled Element Count`、无效几何和未知 Primitive 数，并显示选中元素的 id、type、位置、尺寸、radius、fill、stroke、visible、confidence 与 source。小/中/大圆点由多尺度识别合并；当 SVG tracer 把圆点输出为闭合 cubic path 时，系统会恢复 Circle/Ellipse。未达到圆形置信度的闭合黑色 Path 仍以真实实心区域绘制，绝不显示为空 Bounding Box。

右侧“性能 Debug”显示 Element 数、FPS/帧耗时、静态层/交互层渲染次数、Document Commit、Undo、SVG 序列化和命中测试计数。拖动一个元素不应增加静态层重建或 SVG 序列化计数；只在松开时各增加一次必要提交。

## 无界面验收

```powershell
& 'C:\Users\13524\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m xiaomang_pattern_lab.main --self-test
```

固定集覆盖：规则点阵、大小渐变点阵、星形 Halftone、高密度点阵、扭曲点阵、混合尺寸点阵。输出报告在 `work/pattern_lab/acceptance/pattern-lab-report.json`，包括检测数、元素类型、位置误差、尺寸误差、可编辑元素数、转换时间与 SVG/保存往返结果。

此外，`tests/test_faithful_mapping.py` 覆盖复杂连通黑色结构的保真映射，验证 SVG 和 `FilledRegionElement` 均为实心填充、移动／缩放／复制／保存恢复有效，并确认多选后的布尔并集／差集是实际 `PatternDocument` 编辑而非 Canvas 临时绘制。

## 当前范围

不包含正式 UI、3D、STL、素材库、案例库、渲染系统或大量 Generator。当前参数化能力仅为可审计的 `GridParametricModel`、`RadialParametricModel`、`AlongCurveParametricModel` 与 `FreeParametricModel`，它们始终产出真实 Element，而不是替代 Raster → SVG → PatternDocument 管线。自动化覆盖 Matrix V3、圆环放射点、弧线、S 曲线、自由场、Local Override 与 Save/Load；只有固定集和用户路径的导入回归稳定通过后，才应把 Core Engine 接回正式产品。
