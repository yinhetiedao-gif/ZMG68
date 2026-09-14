# 更新记录

## 1.6.39 — Gate M：形状池与确定性随机（2026-09-11）

### Added

- 新增统一 `ShapePoolEntry`：只保存 `prototype_id`、`weight` 与 `enabled`，继续复用 Gate K 的 ShapePrototypeRegistry，不建立第二套形状或元素系统。
- 形状池以 `shape_random_seed + PlacementSlot.slot_id + "shape_assignment"` 的 SHA-256 稳定哈希分配；保存、重开、缩放、遍历顺序变化后结果一致。
- 左侧参数页增加中文“形状池”面板：可启用圆形、正方形、菱形、三角形、星形、线形，调权重，填写 Seed，并使用“换一种”或“恢复默认”。
- 手动 ReplacementMap 优先于形状池。清除手动替换后，槽位会重新显示该 Seed 对应的随机形状。

### Compatibility

- 旧 PatternDocument 未包含 Gate M metadata 时形状池默认关闭，视觉结果保持不变。
- 形状池始终为派生 Geometry；不改写 `source_elements`，不引入 Density、位置/尺寸/旋转随机或其他 Generator。

### Verification

- Gate M + Gate K/L/Placement 定向回归：23/23 PASS。
- 完整 unittest：189/189 PASS。
- Pattern Lab 固定测试图自检：6/6 PASS。

## 1.6.38 — Gate L：多选与批量编辑（2026-09-11）

### Added

- 复用现有 `selected_id + selected_ids` 作为唯一选择状态，新增 Shift 点击切换、空白区域框选、Shift + 框选追加、Ctrl+A 全选和 Escape 清空。
- 框选始终通过 Canvas 的世界坐标变换判断 Element 中心，Zoom/Pan 后保持准确。
- 多选集合可整体拖动；拖动只保留瞬态预览，鼠标释放后一次提交为一条 Undo。
- 形状替换和恢复原形支持多选批量操作；一次操作只写入一条 ReplacementMap 事务。
- 增加批量缩放、相对旋转、位移、隐藏选中与显示全部；隐藏不删除 Element 或 Placement source snapshot。
- Element 编辑页增加中文批量编辑区、选择数量提示和无选择时的禁用状态。

### Verification

- Gate L 专项及 Gate K/J/Canvas 定向回归：17/17 PASS。
- 完整 unittest：184/184 PASS。
- Pattern Lab 固定测试图自检：6/6 PASS。

## 1.6.37 — Gate K：非破坏式形状替换（2026-09-10）

### Added

- 新增单元素形状替换，内置圆形、正方形、菱形、三角形、星形和线形；所有形状按现有 PlacementSlot 边界自动适配。
- 替换关系保存于 PatternDocument 的 Placement Assignment metadata；原始 Element 快照保持不变，恢复原形只删除对应映射。
- 形状替换位于结构生成之后、Size/Rotation/Position/Scope 等共享效果层之前，Grid 参数变化后仍保留稳定 ID 对应的替换。
- Element 编辑页增加中文形状选择、应用替换、恢复原形和当前形状状态。

### Compatibility

- 旧项目没有 ReplacementMap 或 source snapshot 时继续按原始形状加载。
- 星形、菱形、三角形和线形复用通用 FilledRegion 渲染与 SVG Path 导出，不增加 Canvas 专用分支。

### Verification

- Gate K 与 Placement/Gate J 定向回归：14/14 PASS。
- 完整 unittest：177/177 PASS。
- Pattern Lab 固定测试图自检：6/6 PASS。

## 1.6.36 — Gate J：Modifier Scope / 基础作用范围（2026-09-10）

### Added

- 为 Size、Rotation、Position 效果层增加统一 `ModifierScope`，支持全部元素、当前选择、圆形区域、矩形区域和反转。
- Scope 只决定当前层是否影响 Element；未命中的元素保留上一层结果，不会被隐藏，也不会写回 `source_elements`。
- 左侧效果堆栈增加中文作用范围面板；圆形/矩形参数使用世界坐标毫米和 Slider + Numeric Entry。
- 当前选择以稳定 Element ID 快照保存；可通过“使用当前选择”明确更新，不会因后续选择变化而静默改变。
- Scope 参数拖动使用只读临时 Evaluate，释放后一次提交；切换、反转和范围更新支持 Undo/Redo。

### Compatibility

- Gate J 之前没有 `scope` 字段的效果层自动按“全部元素”加载，视觉结果保持不变。
- 旧 Grid 可见性 Mask 保持独立兼容路径，没有被 Scope 替换或改变语义。

### Verification

- Gate J + Gate H/I/I-UI 定向回归：9/9 PASS。
- 完整 unittest：173/173 PASS。
- Pattern Lab 固定测试图自检：6/6 PASS。

## 1.6.35 — Gate I-UI：位置/变形面板产品化（2026-09-10）

### Improved

- 位置/变形面板按当前模式动态显示有效参数，不再同时展示全部输入项。
- 连续参数统一为 Slider + Numeric Entry；强度/衰减以百分比显示，相位以角度显示，内部 schema 和英文 stable id 不变。
- 偏移、中心、半径、幅度和波长范围根据当前 source geometry bounds 动态计算。
- Slider 拖动走只读临时 Evaluate；释放后只提交一条 Undo。模式切换和同模式重置均可 Undo/Redo。
- 选中 Position 层时自动同步参数；现有堆栈启停、排序、复制、删除与其他 Modifier 行为保持不变。

### Verification

- Gate I-UI 专项：2/2 PASS。
- 完整 unittest：170/170 PASS。

## 1.6.34 — Gate I：位置与变形修饰器（2026-09-10）

### Added

- 新增有序 `PositionModifier` 层：整体偏移、吸引、排斥、径向推出、扭转和波形位移。
- 位置层与现有 Size/Rotation 层共用 Modifier Stack；仅改变派生 Element，保留 source geometry 不变。
- 参数页增加位置/变形层的中文模式与数值入口，支持与堆栈同样的启用、排序、复制、删除和重置操作。

### Verification

- Gate I 定向测试：2/2 PASS；位置层 Save/Load、Undo/Redo、确定性和源元素完整性通过。
- Gate H/共享 Modifier 回归：7/7 PASS。

## 1.6.33 — Gate H：可组合效果堆栈（2026-09-10）

### Added

- 新增有序 Size/Rotation Modifier Stack；每层支持启用/停用、上移、下移、复制、删除和重置。
- 堆栈从 source geometry 重新评估，支持 Wave → Size + Spiral → Rotation 等组合，保存/重开保留顺序与状态。
- 左侧参数页增加最小堆栈管理面板；现有单层 Field 控件和旧项目兼容层保持不变。

### Verification

- Gate H 定向测试：2/2 PASS。
- 既有共享 Field、Canvas 和滚动面板回归保持通过。

## 1.6.32 — 参数面板统一滚动修复（2026-09-10）

### Fixed

- 规则矩阵页改为单一垂直滚动容器，尺寸场、旋转场、网格、渐变和掩膜参数均可访问。
- 移除仅滚动底部网格表单的嵌套滚动布局，避免窗口较矮时后续功能被裁切或看似消失。
- 保留现有 Slider/Entry 绑定、实时预览和一次性提交行为。
- 左侧参数页的鼠标滚轮仅在指针位于该页及其子控件时生效，中央 Canvas 滚轮缩放保持不变。

### Verification

- Tk 界面回归：5/5 PASS（含 768/900/1080 高度）。
- 全量 unittest：164/164 PASS，0 skip。

## 1.6.31 — Shared Field Gate G：中文参数面板与兼容性审计（2026-09-10）

### Added

- 新增 `field_ui.py`：内部稳定 ID 与中文显示名称、说明、旋转方式映射完全分离。
- 新增 `field_compatibility.py`：通过正式 `evaluate_pattern_document()` 对 Size/Rotation/Position 进行兼容性审计。
- 共享参数场面板升级为按当前 Field 动态显示相关参数，并提供 Slider + 数值框双向输入。
- 增加作用强度、合理单位范围、反转 Checkbox、参数预览与释放时单次提交。

### Compatibility

- 未新增 Field；PatternDocument 内部仍使用 `constant`、`wave` 等稳定英文 ID。
- `radial` / `attractor` 明确标记为旧 Size 兼容层，Position 当前明确不支持，不再假装已接通。
- 全量回归 163/163 PASS；共享 Field 兼容性审计 3/3 PASS。

## 1.6.30 — Shared Field Gate E：SpiralField（2026-09-09）

### Added

- 新增 `SpiralField`，基于世界坐标极角、归一化半径、圈数、相位、方向、衰减和反转输出标量。
- Spiral 复用通用 Size/Rotation Modifier，支持 Grid、Save/Load、Undo/Redo 和 source safety。
- 新增方向、相位、中心、圈数、衰减、Document Evaluate 与确定性测试。

### Scope

- 本 Gate 未修改 Raster、GridAnalyzer、Canvas 交互或旧 `ppg`；不新增 Noise、Image、Vector、Shape、Random、Density 或 3D。

## 1.6.29 — Shared Field Gate D：CheckerField（2026-09-09）

### Added

- 新增 `CheckerField`，以世界坐标格宽、格高、旋转、偏移和反转输出交替 0～1 标量。
- Checker 复用通用 Size/Rotation Modifier，支持 Grid、Save/Load 和 Undo/Redo。
- 新增相邻单元交替、旋转、偏移、反转、Document Evaluate 与 source safety 测试。

### Scope

- 本 Gate 未修改 Raster、GridAnalyzer、Canvas 交互或旧 `ppg`；Spiral 仍待后续独立 Gate。

## 1.6.28 — Shared Field Gate C：StripeField（2026-09-09）

### Added

- 新增 `StripeField`，支持世界坐标角度、周期、相位、占空比、平滑度和反转。
- Stripe 继续复用通用 Size/Rotation Modifier，不创建专用效果类。
- 共享参数场控件补充占空比、平滑度及通用场参数；旧项目参数保持兼容。
- 新增 Stripe 的周期、角度、相位、占空比、Size/Rotation、Grid、Save/Load 与 Undo/Redo 测试。

### Scope

- 本 Gate 未修改 Raster、GridAnalyzer、Canvas 交互或旧 `ppg`；Checker、Spiral 仍待后续独立 Gate。

## 1.6.27 — Shared Field Gate B：WaveField（2026-09-09）

### Added

- 新增可复用 `WaveField`，按世界坐标、角度、波长、相位、振幅、偏移和反转输出确定性 0～1 标量。
- `SharedFieldEngine` 新增通用 `RotationModifier`；Wave 可复用现有 Size/Rotation 消费路径。
- 共享参数场面板加入 Wave 选择和基础波形参数；Grid 与导入 Elements 共用同一 Evaluate 入口。
- 新增 Wave 的周期、角度、边界、Round-trip、Grid、UI、Undo/Redo、Save/Load 和 source safety 测试。

### Scope

- 本 Gate 未修改 Raster、GridAnalyzer、Canvas 交互或旧 `ppg`；Stripe、Checker、Spiral 仍待后续独立 Gate。

## 1.6.26 — Shared Field Gate A.5：Integration Bridge（2026-09-09）

### Added

- `evaluate_pattern_document()` 现在从 `PatternDocument.fields[] / modifiers[]`
  重建并执行 `SharedFieldEngine`；Ring/Linear 图在保存、重开、Grid 生成和非 UI
  评估路径中真正生效。
- 兼容 `SharedModifierStack` 增加 post-field 模式，声明式 Size Field 消费后只再
  应用旋转、掩膜和 Local Override，避免重复缩放。
- 既有共享参数场面板加入 Ring 模式及环宽/反转控制；旧模式 JSON 保持兼容。
- 新增 Gate A.5 集成测试：文档图、Grid+Ring、Linear 不重复、Save/Load、SVG 物化。

### Scope

- 不新增 Wave、Stripe、Checker、Spiral，也不修改 Raster、Canvas Direct
  Manipulation、Grid 专用 SizeGradient 或已弃用的 `ppg/field_generators.py`。

## 1.6.25 — Shared Field Gate A：RingField（2026-09-09）

### Added

- 新增 `RingField`：以世界坐标计算环带影响值，支持 `center_x`、`center_y`、`radius`、`ring_width`、`falloff` 与 `invert`。
- `FieldRegistry` / `SharedFieldEngine.from_dict()` 支持 `type: "ring"`；现有 `SizeModifier` 可直接引用 RingField。
- 新增 RingField 的峰值、边界、Falloff、Invert、尺寸 Modifier、源数据不变和 JSON 往返测试。

### Scope

- 本 Gate 未新增 Wave、Stripe、Checker、Spiral、Position/Rotation 接入或 Field UI；旧 Raster、Vector、Grid、Canvas、保存和导出逻辑未重构。

## 1.6.24 — Shared Field Engine Gate 1（2026-09-09）

### Added

- 新增 `SharedFieldEngine`、`FieldRegistry`、`FieldContext`、`ConstantField`、`LinearField`、`FieldMapping` 与 `SizeModifier`。场只输出标准化标量，Modifier 才消费数据。
- `PatternDocument` 向后兼容增加 `fields[]` / `modifiers[]` 声明式持久化记录；旧工程缺少这些键时照常读取。

### Changed

- 既有 Linear X/Y Size 通过兼容适配层迁移到 Shared Field Engine，视觉与旧公式、SVG 输出、Tk Canvas 图元坐标保持一致。
- “应用参数场”首次使用更新入口时会捕获原始元素快照，修复反复应用时可能在已缩放结果上累乘的问题。
- Pattern Lab 窗口销毁前取消性能/交互定时回调，避免测试或关闭窗口后出现残留 Tcl 回调错误。

### Deliberately deferred

- 不包含 Radial、Elliptical、Attractor、Position、Mask、Random、组合场、Field Handle 或新的 Field UI；这些属于后续独立 Gate。

## 1.6.23 — 结构路由与 Grid 输入稳定性（2026-09-08）

### Fixed

- Along Curve 分析增加二维内在维度门禁（协方差特征值、局部方向一致性）；规则二维矩阵不再因最近邻贪心链被误判为沿曲线。
- Grid 参数控件统一经过整数/有限浮点解析，拒绝隐式截断和 `nan/inf`；Grid 控件在非 Grid 结构激活时禁用，避免编辑器显示与实际模型不一致。
- UI 回调与 Grid 交互预览现在记录完整 traceback 至 `work/diagnostics/pattern_lab-ui.log`，不再吞掉 TypeError/ValueError。
- 共享参数场按钮可用于 Grid 结构；Grid 继续负责位置结构，共享层负责尺寸/旋转效果。

### Verified

- 规则 12×12 矩阵路由至 Grid，Along Curve 候选为空；圆点、斜向晶格、放射、沿曲线、共享修饰与 Placement 回归测试通过。

## 1.6.22 — Shared Parametric Modifier Stack（2026-09-08）

### Added

- 新增 `SharedModifierStack`，将 Geometry Source 与参数化效果分离。导入 Elements、Grid、Radial 和沿曲线模型都可以共享 Size Field、Rotation Field、Mask 与 Local Override。
- 新增 `PatternLabSession.activate_shared_modifiers()`、`update_shared_modifiers()` 与 `deactivate_shared_modifiers()`；导入图片无需先通过 GridAnalyzer 即可使用公共参数化效果。
- 保存时保留源元素快照，避免反复调整时在已评估结果上累乘；Save/Load 后会从源快照重新评估。

### Compatibility

- Grid 仍负责 rows、columns、spacing、Basis、rotation 和 origin；共享效果层不会覆盖或清空 Grid 结构参数。
- 旧项目没有共享效果元数据时完全沿用旧 Evaluate 路径。

### Verified

- Shared Modifier 专项 3 项、Placement Gate 1 及核心回归合计 53 项通过。

## 1.6.21 — Unified Placement / Prototype / Assignment 基础层（2026-09-08）

### Added

- 新增无 UI 的 `PlacementSlot`、`ImportedElementSlotProvider` 与 `GridSlotProvider`。导入元素和现有 `GridParametricModel` 共享同一套位置槽位抽象；Grid Provider 只适配既有 Grid，不复制 GridAnalyzer。
- 新增 `ShapePrototypeRegistry`、`ReplacementMap`、`AssignmentSettings` 与 `RandomSettings`，复用现有 `ElementPrototype` 类型，支持后续单元形状替换、策略分配和稳定 Seed 随机。
- 新增 `AssignmentEngine` 与可选的 `PlacementAssignmentState` 元数据。默认关闭时是严格兼容的 no-op；开启后替换只作用于 Evaluate 结果，源 `PatternDocument.elements` 不被破坏，支持保存/恢复。

### Fixed

- `grid_model_from_document()` 现在同时读取新的通用 `model` 载荷以及历史 `grid` / `parametric_model` 载荷，避免模型载荷丢失。
- Pattern Lab 运行依赖补齐 NumPy，覆盖 Reference2D 和制造检查代码的实际导入需求。

### Verified

- Placement/Assignment Gate 1 测试 7 项通过；Grid V1/V2/V3、Canvas、Faithful Mapping、Multi-family 和保存恢复核心回归通过。
- 完整测试仍有 3 项旧 Phase 1 UI/Pillow 兼容失败，未将其伪报为通过。

## 1.6.20 — Pattern Lab Multi-Family Parametric Analysis（2026-09-07）

### Changed

- “尝试参数化”不再等同于“尝试规则矩阵”。`PatternAnalyzer` 现在只读取当前 `PatternDocument.elements`，并并行比较 Grid、Radial 与 Along Curve 三类结构；文件名、固定测试图名称和预设均不参与判断。
- `PatternDocument → ParametricModel → shared Modifier → Local Override → evaluated Elements` 成为统一计算路径。原有 `GridParametricModel` 完整保留，成为结构候选之一。

### Added

- 新增 `RadialParametricModel`、`AlongCurveParametricModel` 与 `FreeParametricModel`，分别用于共同中心的角度序列、沿连续路径的元素序列，以及无可靠整体结构时的场参数化。
- 新增 Size Field（Constant / Linear X / Linear Y / Radial / Attractor）与 Rotation Field（Constant / Face Center / Tangential / Attractor）；放射、曲线与自由参数化共用它们，并继续使用已有 Mask 与稳定 Local Override。
- “尝试参数化”会显示 Grid / 放射 / 沿曲线置信度，按最高可靠候选提供转换；没有可靠候选时明确给出“进入自由参数化”，不会再把图案归为“无法参数化”。
- 新增自动化覆盖：圆环放射点、弧线、S 曲线、完全不规则元素、Free Field、Local Override、Save/Load 以及 Grid 回归。

### Fixed

- 修复沿曲线模型在连续等长分段中错误将后续采样夹回第一段的问题。
- 修复自由参数化元数据在重新打开工程后未被 Evaluate 路径识别，导致 Local Override 未物化的问题。

### Verified

- 38 项 Pattern Lab 核心回归通过：保真映射、Canvas 直接编辑、通用二维晶格 V3、Grid V1/V2、用户 PNG 导入、多结构参数化与保存恢复均通过。

## 1.6.19 — Pattern Lab General 2D Lattice / Matrix V3（2026-09-07）

### Changed

- `GridAnalyzer` 从“按屏幕 X/Y 聚类”升级为通用二维晶格拟合：仅从真实 Element 的 centroid 建立 KNN 邻域、方向直方图、两个基础向量与稳健整数格坐标，使用 `P(row,column) = Origin + column·BasisU + row·BasisV`。
- `GridParametricModel` 可持久化显式 `Basis U / Basis V`；旧项目继续由 `spacing + rotation` 推导正交基向量，兼容旧矩阵工程。
- 尺寸场与位置格子彻底拆分。Grid 成立仅由方向、间距、位置残差、内点率与占用率决定；尺寸变化、裁切与画布白边不再否决格子。

### Added

- 支持水平、旋转、斜向、非正交、长方形、带大边距、少量缺失／裁切单元的二维格子；缺失单元继续保存为 `visible=false` Local Override。
- `SizeFieldAnalyzer` 在位置拟合后独立尝试 Constant、线性、中心到边缘、Radial 与 Elliptical Radial；无法可靠解释时保留每格尺寸 Override，不破坏位置参数化。
- 矩阵面板新增 Basis U/V 分量、Radial/Elliptical 尺寸场、X/Y 半径和衰减；分析结果会显示基向量、方向/间距/位置分数、内点率与占用率。
- 新增真实 PNG 斜向椭圆尺寸场矩阵、缺格、Custom SVG 斜向路径矩阵以及显式基向量 Save/Load/Local Override 回归。

### Fixed

- 修复候选方向配对时复用上一对 U/V 临时变量的问题；该错误会使部分水平尺寸渐变矩阵错误选择对角线基向量并出现 9×21 而非 9×13 的结果。

### Verified

- Matrix V1/V2 全部回归通过；新增 Matrix V3 专项 3/3 通过，覆盖非正交基向量、强二维尺寸变化、缺失单元、路径原型与持久化。

## 1.6.18 — Pattern Lab Matrix Parameterization V2（2026-08-29）

### Changed

- 矩阵定义从“圆点阵”升级为“二维格子上的重复单元”：`GridParametricModel` 只保存行列、U/V 间距、旋转和原点；新 `ElementPrototype` 保存 Circle、Ellipse、Rect、Polygon 或 Custom Path 单元。
- `GridAnalyzer` 改为 `ElementAnchor` 位置优先拟合。所有可见 Circle、Ellipse、Rect、Path 与 FilledRegion 都提供中心锚点；单元尺寸、尺寸渐变和画布白边不再参与 Grid 是否成立的判断。
- 引入 OccupancyMap、内点率、占用率与位置残差。少量缺格不会使矩阵失败，缺失格继续通过 `visible=false` Local Override 保存。

### Added

- 新增 `CirclePrototype`、`EllipsePrototype`、`RectPrototype`、`PolygonPrototype` 与 `CustomPathPrototype`；未知闭合 SVG Path 保真保存为 CustomPath，不会生成圆点替代物。
- 新增严格 / 标准 / 宽松三档分析容差，以及候选数、内点数、行列、基向角、U/V 间距、残差、占用率、形状聚类比例和失败原因的 Matrix Analysis Debug。
- 新增真实 PNG 导入回归：星形 Y 尺寸渐变、菱形 Y 尺寸渐变、大边距 8×20、少量缺格和 17°旋转矩阵；新增真实 SVG Path 矩阵原型保存/生成验证。

### Verified

- Pattern Lab 核心回归 34/34 通过，包含保真映射、Canvas 直接编辑、Save/Load、Matrix V1 与 Matrix V2。
- 所有 V2 实际 PNG 用例均通过 `PatternLabSession.import_image()` 而非固定 Fixture 特殊路径；Grid 参数重建保留 FilledRegion/CustomPath 原型与 Local Override。

## 1.6.17 — Pattern Lab Matrix Parametric V1（2026-08-29）

### Changed

- 矩阵参数化收敛到唯一 Evaluate Pipeline：`PatternDocument → GridParametricModel → Size / Mask Modifier → Local Override → active Elements`。Canvas 不保存第二套 Geometry State；Free Mode 保持原始独立 Element。
- GridAnalyzer 仍只读取 Element 的真实空间数据，现可识别非方阵、整体旋转，并容忍少量缺失逻辑单元。缺失单元写入 `visible=false` Local Override，转换后不会被自动补成黑点。
- Grid 模式的多选移动、缩放、旋转和删除均以单条 Undo Transaction 写入 Local Override；整体重建后仍按稳定 Grid ID 保留。

### Added

- 新增非破坏 `MaskModifier`：矩形、圆形和已序列化 Imported Path 三种形状；关闭 Mask 会立即恢复基础 Grid。
- 新增明确的“烘焙为自由元素”操作：先 Evaluate 当前模型，再解除参数化关系，保留所有当前 Geometry 供后续自由编辑。
- 新增 5 类真实用户 PNG 导入回归：12×12、8×18、15°旋转、尺寸渐变、缺少单元矩阵；不经固定 Fixture 选择器。

### Verified

- Matrix V1 专项测试覆盖 Evaluate、Mask、Local Override 比例缩放、缺失单元、Bake、Save/Reload、批量局部编辑与真实用户导入。
- Tk Canvas 冒烟：通过“尝试参数化 → 转换 → 圆形 Mask → 烘焙”真实 UI 调用；144 格中 16 格可见，烘焙后返回 Free Mode。

## 1.6.16 — Pattern Lab Halftone 显示与用户导入 Grid 拟合（2026-08-29）

### Fixed

- 修复 `star_halftone` 的空 Bounding Box：根因是上游 tracer 把一部分小圆输出为闭合 cubic Path，而 Canvas 将语义 Path 降级成了包围盒轮廓。SVGNormalizer 现会恢复符合形状阈值的 Circle/Ellipse；仍为 Path 的闭合黑色区域也会绘制为真实实心多边形。
- 修复中文用户文件名经 Node imagetosvg-mcp 子进程时被 Windows 默认 GBK 解码破坏的问题；MCP JSON stdio 现在明确使用 UTF-8。

### Added

- 新增 `MultiScaleDotRecognizer`：按 small / medium / large 自适应分带、合并去重，并把检测结果写入真实 Element metadata。参数化语义导入可恢复 tracer 未语义化的 dot；保真映射只添加 dot hint，不破坏 FilledRegion。
- 新增 `Element Debug`：显示元素完整数据及 detected/renderable/visible-filled/invalid/unknown 审计统计，供定位 Detection、Normalization 或 Rendering 问题。
- 新增独立 `PatternAnalyzer / GridAnalyzer / GridFitResult / SizeGradientAnalyzer`。输入仅为 `PatternDocument.elements`，可测量旋转、行列、间距、尺寸、偏移、残差与 Fit Score；支持 Horizontal、Vertical、Center→Edge、Edge→Center 四种可靠尺寸梯度。
- UI 增加“尝试参数化 → 转换为参数化矩阵”两步流程。低置信度图案继续保留自由元素；规则参数只在确认转换后控制当前导入的 Geometry。

### Verified

- `star_halftone`：63/63 元素可渲染、可见且实心，0 无效几何、0 未知 Primitive。
- 新增用户路径回归：以中文文件名通过真实 PNG 导入，规则点阵可测得 12×12 与 24 mm 间距、转换/重建/Local Override/保存恢复均通过；渐变 Halftone 的未支持对角尺寸场保留 Per-Element Override，不伪造 Modifier；稀疏星形保持自由元素模式。

## 1.6.15 — Pattern Lab 直接编辑性能与规则矩阵验证（2026-08-29）

### Changed

- `xiaomang_pattern_lab` 的 Circle/Ellipse/Rect 改为原生 Canvas 静态层；指针移动不再重建完整 Canvas、重新渲染 SVG 位图、更新整个 Document 或连续写入 Undo/SVG。
- 新增独立 `InteractionState`：按下时仅保存起始几何，拖动中以 Tk `after_idle` 合帧更新交互层，松开后才一次性提交 PatternDocument、生成一条 Undo Transaction、序列化 SVG。Inspector 拖动中限频约 15 Hz。
- 新增缓存 Bounding Box `SpatialIndex` 边界，当前实现可替换；Canvas 代码不再直接依赖反复读取 Document 的逐路径命中测试。
- 新增实验性 `GridParametricModel`、`SizeGradientModifier`、`LocalOverride` 与基于真实 X/Y 空间聚类的规则矩阵识别。局部移动/缩放在 Grid 重建、保存、重新打开后保留。

### Verified

- 新增 13 项 Pattern Lab/FOUNDATION 0 回归，包括 9×16 非平方规则矩阵识别、Center→Edge 尺寸渐变、Local Override 跨参数更新与保存恢复，以及 144/500/1,000/3,000 Element 下的瞬态拖动、缩放、Pan/Zoom 坐标与参数预览基准；3,000 Element 下 240 次瞬态指针更新不改 Document、不序列化 SVG、只在最终提交写入一条 Undo/SVG。
- 旧 FOUNDATION 0、Canvas 坐标变换、矢量化/保存恢复回归保持通过。

## 1.6.13 — 移除实时三维查看器，收紧最终制造链（2026-08-28）

### Removed

- 完整删除自研 `ppg/three_d_preview.py`、3D Preview Tab、临时 Preview Mesh Renderer、相机轨道/平移/缩放、透视/顶/正/侧视图、显示模式、材质/线框/热力图、Viewport 灯光/AO/阴影、预览缓存与相关交互测试。
- 删除“渲染效果图”及 `run_blender_render` / `run_native_render` 路径；二维参数变动不再触发任何三维重建。
- 从 `.ppg` 新版本格式移除三维相机、显示模式、三维选择和局部 Brush 状态；旧项目保留可读，未知旧字段会被安全忽略。

### Changed

- 新增 `ppg/final_geometry.py`，将二维工作单缩放、边界与高度场限定为最终制造模型输入；不再生成临时三维网格。
- 新增 `ppg/preview_provider.py` 的 `PreviewProvider` / `NullPreviewProvider`。当前实现无界面、无状态；未来第三方显示只能消费最终制造 Mesh，核心编辑、清理、验证和 STL 不依赖它。
- `EditablePatternDocument.elements` 现在是 Final 3D Build 的优先输入，经 `document_to_primitives()` 转为毫米制造工作单；Direct Element Mode 和 Parametric Mode 的本地编辑都能进入同一条最终 STL 链。
- 制造 handoff 的质量报告改为最终网格审计，不再伪造或要求多视角 Viewer 证据。

### Verified

- 删除旧 Viewer/效果图回归；新增 `NullPreviewProvider` 无状态、EditablePatternDocument 作为最终制造输入，以及高度场直接进入无 Blender 封闭 STL 的回归。
- 保留并回归 2D Canvas、Reference → Editable 2D、项目保存/恢复、Geometry Cleanup、最终 STL reload 与拓扑审计。

## 1.6.12 — EditablePatternDocument 重建内核（2026-08-28）

### Changed

- 参考重建正式改为 `base_elements + added_elements → Base Generator + Modifier Stack → Local Overrides → materialized elements`；Rebuild、Canvas 和 SVG/PNG/DXF 导出只消费当前真实元素，绝不以参考位图或旧 Field Generator 充当重建结果。
- 规则拟合只把已经有确定性公式的 Grid/Radial 设为 Parametric Mode；Spiral/Wave/Flow 仅保留候选评分，低分或未实现规则会明确进入 Direct Element Mode。
- 规则面板补齐尺寸、密度、旋转、圆形 Mask 和 Simple Warp；局部移动、尺寸、旋转、删除、复制、分组通过稳定 ID 作为 Local Override 保存，并会在 Rebuild 后重新叠加。

### Verified

- 新增 Rebuild 与 Modifier Stack 回归：局部修改跨 Rebuild 保留；删除/复制跨 Rebuild 保留；Direct Mode 不依赖 Generator；Grid 规则修改后保留局部偏移；导出、保存/恢复均只使用物化元素。
- VTracer POC 在绑定不可用时使用确定性检测 SVG 回退，仅为 SVG/轮廓验证提供兼容性，正式 DOT 重建不依赖该运行时。

## 1.6.11 — Reference Reconstruction 与可编辑元素模式（2026-08-28）

### Added

- 新增 `xiaomang-reference-reconstruction` Skill 和 `EditablePatternDocument`，固定字段为 canvas、reference、generator、modifiers、elements、overrides、masks、fields、metadata。
- 重构点阵识别为“检测优先”：预处理 → Primitive Detection → Editable Elements → Spatial Analysis → Generator/Modifier Fitting；参数拟合低分时保留 Direct Element Mode。
- 粘连圆点加入 distance transform、local maxima 和 watershed/Voronoi 分区；新增六组确定性 PNG 测试图与检测调试图导出。
- Canvas 支持真实元素的单点选择、Shift 多选、Ctrl+A 全选、Ctrl+D 复制、拖动、尺寸修改、删除和项目 JSON 持久化。

### Removed

- 删除案例与素材 Tab、按钮、浏览/搜索/分类/收藏/下载入口、示例数据和相关状态；保留参考图、轮廓、自由绘制、SVG、2D、3D 与 STL 功能。

### Verified

- 全量自动测试覆盖 38 项；包括 `test_touching_dots.png` 的粘连圆点分离、Direct Element fallback、批量 Override、保存/恢复和真实 Canvas 回归。
- 修复 1.6.11 后续字段统计回归：空间字段先规范化点坐标数组，参考图导入不会再因 `TypeError` 中断；修订安装包已重新自检。

## 1.6.10 — Reference2D Stage A 接入正式 Canvas（2026-08-28）

### Added

- 将已验证的 `reference2d_poc/` 接入现有 2D Canvas：官方 VTracer Python binding → SVG Parser → Primitive Recognizer → Dot Primitive Recovery → Document2D。
- 新增 `ReferenceLayer` / `GeometryLayer` 严格分层及可保存 `Document2D`；GeometryLayer 仅保存真实 `DotObject`，Canvas 支持点选、半径编辑、移动和删除。
- 应用打包收集 VTracer `0.6.15` 运行时；关闭/删除源图后，项目文件仍可恢复 GeometryLayer，不会重新分析图片。

### Verified

- 固定点阵 PNG 在直接 VTracer 管线和 Anionex `trace` 交叉验证中均得到 12 条 SVG 路径、12 个可编辑 DOT、0 个拒绝对象。
- Stage B 参数推断仍明确暂停；本版仅完成 Stage A 的正式 Canvas 接入。

## 1.6.9 — Reference → Editable 2D P0 架构落地（2026-08-28）

### Added

- 新增项目内 `ppg/reference2d/` 模块：导入元数据、预处理、分类、连通组件/点特征检测、密度/尺寸/旋转场估计、Generator/Modifier 匹配、Editable 2D 场景和 IoU/Dice 评估。
- PNG/JPG/WEBP/TIFF/BMP 参考图现在可保留像素尺寸、DPI、色彩空间、透明通道与目标物理尺寸；WEBP 已加入文件选择器。
- 点阵/半调分析入口接入结构化 Reference2D 结果，同时兼容旧版 `AnalysisResult` 字段；生成点对象与 Mask 独立于源位图，可序列化后继续编辑。

### Verified

- 新增 P0 回归：WEBP 点阵 → 真实 DotFeature → EditableGeometry → SpatialFields → Generator Match → Dice/IoU，并验证结果可 JSON 序列化。
- 保留并继续通过真实 Tk 的导入、应用分析、左右对比回归；缓存列表错误与 1×1 Canvas 防护仍在 1.6.8 修复基础上生效。

## 1.6.8 — 参考分析应用后 2D 预览恢复（2026-08-28）

### Fixed

- 修复导入参考图并点击“应用分析”后 2D 视图清空的根因：包含 `reference_elements` 列表的 `PatternSettings` 不能直接作为字段缓存键，旧逻辑抛出 `unhashable type: 'list'` 后清除 Canvas。现在使用稳定 JSON 快照作为缓存键，字段生成器、原图和左右对比均能继续绘制。
- 增加 Canvas 布局就绪保护：Tk 首次映射或切换面板短暂报告 1×1 时不再提交永久 1×1 `PhotoImage`，待布局完成后自动重绘；退出时取消延迟回调，避免 Tcl 残留命令。

### Verified

- 新增真实 Tk 流程回归：导入 PNG → 应用分析 → 进入点线面 Generator → 左右对比，验证真实 `PhotoImage` 尺寸、Canvas 图层、左右黑色图元和无 `unhashable` 错误。

## 1.6.7 — 参考图左右对比完整画幅回归（2026-08-28）

### Fixed

- 修复“左右对比”把同一张全画布图片从中线裁成两半的问题：左栏现在直接从导入的 PNG/JPG 独立等比居中绘制，右栏显示完整参数化构图，不会再将位于中心的原图或生成图切断。
- 继续保留统一 RGBA 合成和实例级 `PhotoImage` 引用，避免参考图遮挡生成图或被 Tk 垃圾回收后变为空白。

### Verified

- 新增真实 Tk Canvas / `ImageTk.getimage()` 回归：生成一张含中央黑圆的参考图，验证左右栏各自都有完整黑色图形且 Canvas 只提交一个合成图层。

## 1.6.6 — 本地 3D/STL 后端与参考图链路修复（2026-08-27）

### Added

- 新增项目 Skill `xiaomang-native`，使用本地 SDF + Marching Tetrahedra 生成封闭 STL 与白底黑体效果图，不要求安装 Blender。
- 默认制造和效果图路径改为本地后端；Blender 保留为显式兼容选项，旧接口继续可回滚。
- 新增无 Blender 的 STL、效果图和拓扑审计自动测试。

### Fixed

- 导入参考图的 Canvas 图层继续保留独立 `PhotoImage` 引用，并加入真实 Tk Canvas image-item 回归检查。

## 1.6.5 — 黑白 3D 效果图与渲染回归测试（2026-08-27）

### Fixed

- Blender 独立效果图改为白色背景、黑色实体，材质改用 Principled BSDF 节点并固定 Standard 色彩管理。
- 新增渲染像素回归测试，防止再次输出深色背景或橙色模型。

## 1.6.4 — 参考图 2D 显示修复（2026-08-27）

### Fixed

- 导入 PNG/JPG 后立即建立 Reference Layer，即使暂不应用分析结果也会显示原图。
- 2D 普通 Generator 和点线面 Generator 均支持参考图显示；图片保持原始宽高比并居中适配设计区域。
- 持久保存 `ImageTk.PhotoImage` 引用，避免 Tk Canvas 因垃圾回收出现空白图片。
- 参考图缓存按路径、修改时间、缩放尺寸和透明度失效，窗口调整和对比模式切换可稳定刷新。

## 1.6.3 — Xiaomang Skill 体系（2026-08-27）

### Added

- 创建项目内 `xiaomang-creation` 及八个职责单一的子 Skill：编排、参考分析、Generator 映射、几何清理、Blender Worker、制造预检、STL 导出和质量审计。
- 新增统一 `handoff-contract.md` 与 `handoff_contract.schema.json`，固定 Reference → Editable 2D → Clean Geometry → Blender → Validated STL 的交接字段、状态门槛、artifact SHA-256 和 checkpoint 回滚语义。
- 新增 `tests/test_xiaomang_skills.py`，覆盖 Skill frontmatter、contract schema、阶段字段和第三方能力边界声明。
- 将“导出 STL”接入 `ppg/xiaomang_pipeline.py`：运行时写入 handoff artifact、SHA-256、checkpoint 和阶段状态，只有 Blender readback、制造预检与质量审计通过才交付 STL。

### Notes

- 本轮没有新增 UI、Generator 或第三方运行时代码；仅把公开项目的 Bridge、reference-first、readback、多视角 milestone、quality loop 和 export domain 原则转化为小芒造物自己的流程约束。

## 1.6.2 — 2026-08-27

### Fixed

- 回退到 1.6 的浅灰/白色/稳重蓝双栏工作台，恢复左侧参数、右侧大预览的操作节奏。
- 修复参考图分析后默认进入“重建结果”导致原图不可见的问题；应用分析结果后自动打开左右对比，且参考图层与生成几何层保持分离。
- 修复 2D/3D 切换后的预览画布引用，导入参考图生成的点线面规则现在会同步到三维预览。

## 1.7.0 — 2026-08-27

### Added

- 产品正式更名为“小芒造物”，统一安装器、可执行文件、标题、单实例提示与中文语言资源。
- 新增芒果小猫轻量 Canvas 吉祥物和奶油/芒果/叶绿设计系统；不加载外部图片，保持安装包离线可用。
- 参考图分析新增真实组件特征提取（中心、尺寸、方向、形态、区域），高密度参考图可直接生成可编辑元素工作单；过稀/粘连图自动回退连续规则场。
- 3D 视图新增线框/网格/打印检查/高度热力图显示别名、选区交互与局部元素属性覆盖；新增 Blender 后台效果图渲染入口。

### Fixed

- 修复参考重建在中心留白和角点密度叠加后过度稀疏的问题，并保持 Seed 可复现。
- 构建与安装脚本统一输出 `小芒造物-安装程序-1.7.0.exe`，避免继续打包旧产品名。
- 主工作台重构为“一级导航｜中央 2D/大型编辑｜右侧常驻 3D”三栏布局；新增可复用 ToolButton、IconButton、ParameterControl、NavigationRail、GeneratorShelf 与 Canvas 图层命名约定。

## 1.6.1 — 2026-08-27

### Added

- 预览区新增固定、始终可见的“2D 设计 / 3D 预览”切换；`1`、`2` 快捷键可切换，二维缩放/平移与三维相机/显示模式分别保存到 `.ppg` 项目。
- 点线面参考重建新增可编辑的 Generator + Modifier Stack：参考强度、结构保留、创意变化、中心留白及旋转/过渡、角点强调、中心涡旋，以及“重建结果 / 原图 / 左右对比 / 叠加对比”。
- 增加 196、500、1,000、3,000、5,000 图元压力回归测试，并增加“旋转中心留白 + 角点尺寸 + 涡旋”参考重建回归测试。

### Changed

- 预览改为四级管线：滑动中 33ms 节流的轻量工作单；停下 120–140ms 后完整 2D；进入三维或停下后按三维质量生成；最终 Blender 制造模型只在导出 STL 时启动。
- 大量二维元素不再逐个创建 Canvas 图元，改为一次性临时位图批量绘制；参考图明暗场按路径、修改时间和模糊参数缓存，避免拖动参数反复读取原始图片。
- 参考分析不再只有“明暗映射”描述：结果会明确输出位置、尺寸、密度、旋转和扭曲规律；低置信度仍会诚实提示 Generator 缺失。

## 1.6.0 — 2026-08-27

### Added

- 主界面新增“生成三维模型”“二维视图”和“导出 STL”。用户在软件内完成保存路径选择后即可得到通过制造审计的 STL，不需要手动打开 Blender。
- 新增软件内实时三维 Canvas 视图：透视/顶/正/侧视图、左键旋转、中键平移、滚轮缩放、双击聚焦、恢复视角，以及实体、光滑、线框、网格、厚度热力图和四档预览质量。
- 新增连续局部高度场：增加、降低、平滑、恢复和高度控制点会保存到 PPG 项目，实时改变三维预览，并传入 Blender 最终 STL 工作单。
- 新增高度场预览/Blender 回归测试和三维 UI 冒烟测试。

### Changed

- 所有新增三维与 STL 主操作均使用简体中文；旧“Blender 生成 STL”入口保留为兼容别名。

## 1.5.3 — 2026-08-26

### Fixed

- 修复 Blender 5.2 在节点式 `Volume to Mesh` 收尾时可能生成大量微型封闭岛的问题。最终制造模型改为原生 `Voxel Remesh` 隐式融合，再执行焊接、平滑、法线统一、三角化与独立 STL 审计。
- 新增真实“根部脊环 + 放射线 + 节点”制造回归测试；连通放射图案现在验证为单一封闭主体，断开图元仍会被阻止导出。
- 最终模型检查报告明确标记为非实时预览的制造模型，并如实记录实际 Blender 后端。
- 修复安装器在初始化阶段读取安装目录常量导致的运行时错误；占用检查现在在用户确认安装目录后执行。发布脚本也会在测试、应用打包或安装器编译失败时立即停止，绝不回退误报旧安装包。

## 1.5.2 — 2026-08-26

### Fixed

- 修复安装器在安装目录尚未初始化时读取 `{app}` 而导致的运行时错误；占用检测现改在用户确认安装目录后执行。
- 3D 最终模型加入二维制造清理：删除无效、极短和过小源元素，并按最小结构宽度规范化线宽。
- 放射线结构在 3D 生成时自动补连续根部脊环，避免每根放射线变成独立 STL 碎片。
- 独立 STL 审计新增连通组件、漂浮组件和最小边长度统计。默认单件制造模式发现多个组件时阻止输出并删除无效 STL。
- 修复 Blender 5.2 网格检查兼容性；实际后台 Blender 回归测试覆盖“单一封闭主体”和“阻止断开碎片”。

## 1.5.1 — 2026-08-26

### Fixed

- 修复升级安装容易被同名旧版、开发版或测试副本误拦截的问题：安装器现在仅检查即将被覆盖的当前安装路径，并以中文提示安全退出，不会强制结束可能未保存的设计工作。
- 增加单实例保护，后续不会再启动多个造物工坊进程导致升级冲突。
- 安装包文件名包含版本号，避免用户误运行缓存中的旧安装程序。

## 1.5.0 — 2026-08-26

### Added

- 统一 Field Generator 参数系统：横/纵数量、行列距、最小/最大尺寸、密度、X/Y 偏移、Gamma、Levels、反相、Mask 强度、边缘柔化、渐变中心/曲线、独立随机、分形 Smooth Noise，以及 Wave/Twist/Bend/Curl/Flow/吸引/排斥。
- 点线面新增菱形、六边形、水滴、叶片、胶囊、空心/描边和长宽比；参数实际影响预览与二维导出。
- 启用流场、波场、噪声场 Generator；它们遵循同一可扩展 Generator API。
- 点线面参数页改为可垂直滚动，并提供参数名称搜索。
- 顶部操作区支持左右箭头、横向滚轮、Shift+滚轮、触控板滚动、拖动与“更多”菜单，窄窗口下全部操作仍可访问。
- 新增 `FEATURE_STATUS.md`，明确 Working / Partial / Not Implemented 状态。

### Fixed

- 图片视觉分析的推荐尺寸现在同时映射到最小/最大尺寸，不再只写入已废弃的单一点大小参数。

## 1.4.1 — 2026-08-26

### Fixed

- 安装器固定采用当前用户模式，避免在管理员上下文下被自动改为“所有用户安装”而导致安装位置、权限或旧安装记录冲突。
- 重新执行完整安装冒烟测试：复制、卸载信息注册及安装后 EXE 自检均通过。

## 1.4.0 — 2026-08-26

### Added

- Blender 成为参数化纹样的主要 3D / STL 后端；自动检测本机 Blender 5.2 LTS 并以隐藏后台进程运行。
- 新增独立 `Blender Worker`：JSON 工作单 → bpy 基础几何 → Geometry Nodes Mesh-to-Volume / Volume-to-Mesh 有机融合 → 平滑、法线统一、三角化 → STL。
- 工具栏新增“Blender 生成 STL”；无需人工打开 Blender，支持厚度、圆润程度、有机融合和四档质量，并输出中文检查报告。
- 增加真实 Blender 端到端自动测试，验证 Worker 导出的 STL 为封闭网格、裸边为 0。

## 1.3.0 — 2026-08-26

### Added

- 实装点线面视觉分析：自动阈值、组件紧致度/线性、规则网格周期、方向性、径向与明暗密度检测，并以中文展示可解释结果和置信度。
- 实装独立点线面 Generator 内核：半调点阵、规则点阵、渐变点阵、点线面构成、轮廓遮罩、网格变形，支持参考明暗但不逐像素复制原图。
- 新增完整的点阵参数面板、实时预览、六个可选变体、PPG 项目保存及 SVG/PNG/DXF 导出。
- 新增合成点阵分析、生成可重现性和点线面三格式导出的自动测试。

### Changed

- UI 回归浅灰/白色/稳重蓝色的专业工作台，移除银蓝液态金属的高装饰视觉方向。

## 1.2.1 — 2026-08-26

### Fixed

- 安装包改为当前用户免管理员安装，修复默认写入 Program Files 导致普通用户无法安装的问题。
- 快捷方式改为可选安装任务；修复安装完成页仍显示旧产品名称的问题。

## 1.2.0 — 2026-08-26

### Added

- 高质量 STL 最终管线：连续 SDF 轮廓、圆角厚度场、Marching Tetrahedra 等值面提取。
- 草稿 / 标准 / 精细 / 超精细质量档，以及圆润程度、有机融合参数。
- 二进制 STL 独立拓扑审计：三角面、裸边、非流形边和退化面。
- Liquid Metal / Silver Blue 中文界面设计系统。
- 可注册 Generator Library 与诚实的本地图片视觉分析初判。

### Fixed

- 修复早期像素块直接挤出导致的阶梯边缘与粗糙表面。
- 修复最终厚度场顶部/底部边界，确保测试 STL 通过封闭性审计。

## 1.1.0 — 2026-08-26

### Added

- 主工具栏新增“图片转 SVG / STL”一键工作流。
- 黑白图片自动生成无底板 SVG、封闭 STL、预览图、参数公式和连通性检测。
- 断开黑色组件默认不导出 STL，需由用户明确确认多部件输出。

## 1.0.0 — 2026-08-26

### Added

- 正式模块化 PPG 项目与独立 Windows 构建脚本。
- 新增三角形、矩形、叶片、水滴、珠子及自定义 SVG 元素。
- 新增随机、渐变、曲率分布，旋转、偏移、缩放与最小间距。
- 简体中文 UI、语言资源架构、中文 Tooltip。
- 内置轮廓、自由绘制、SVG/DXF 轮廓导入。
- 平滑噪声、预览质量、缓存、自动保存、PPG 项目/预设、撤销/重做。
- SVG、PNG、DXF 导出、自动测试与 Inno Setup 安装脚本。

### Changed

- 从单文件“Radial Pattern Generator”升级为面向设计者的“参数化纹样生成器”。
- 保留并迁移 Rhino 原型的外法线和凹区安全裁剪逻辑到独立几何模块。

### Known Issues

- SVG 导入目前针对单个 polygon/polyline 或简单 path；复杂贝塞尔、多子路径需预处理。
- 3D、STL、厚度场和打印检查尚未进入稳定版本。
# 1.6.14 — 上游 Raster→Editable SVG 最小集成（2026-08-28）

- 安装原始 `ujo78/imagetosvg-mcp`、`aeren23/image-processing-skills` 与 `linyaosky/svg-skill` 到项目外部目录。
- 新增 `ppg/upstream_svg_pipeline.py`：通过 MCP stdio 调用 `convert_image_to_svg`、`inspect_svg`、`edit_svg`、`render_svg`、`optimize_svg`，不重复实现矢量化。
- 三类点阵图片集成回归通过：144 层规则点阵、渐变半调和星形 Mask 均可转换、检查、单层编辑、重新渲染和优化。
- 正式 Canvas 尚未切换到上游链路，下一阶段在 POC 稳定后接入。
