# Gate 状态（2026-09-15）

## PACK-1 — Windows EXE Packaging（2026-09-16）

- Status: PASS
- 入口：`xiaomang_pattern_lab.main`；PyInstaller 6.22.2 `onedir`，规格文件 `xiaomang_pattern_lab.spec`，构建脚本 `xiaomang_pattern_lab/build_pattern_lab.ps1`。
- 验证：Debug/Release EXE 均在源码目录之外执行固定图 self-test 6/6；Release GUI 在中文且含空格工作区路径下稳定启动。日志：`work/pack-1-*.log`。
- 输出：`%USERPROFILE%\Desktop\XiaomangPatternLabBuild\release\XiaomangPatternLab\XiaomangPatternLab.exe`。本 Gate 不包含安装器、更新器、登录或授权。

## Gate Q — Noise Field / 有机噪声共享参数场（2026-09-15）

- Status: PASS
- 数据模型：`NoiseField(id, scale, strength, seed, offset_x/y, octaves, contrast, invert)` 为世界坐标连续标量；稳定整数混合与 fBm 插值不依赖 Python 随机哈希或元素遍历顺序。
- 接入：FieldRegistry / SharedFieldEngine 复用既有声明式图；尺寸、旋转、通用位置和密度消费者统一按 `field_id` 引用，不改写 `source_elements`。
- UI：参数化效果新增“有机噪声”中文 Slider + Entry 与 Seed 换一个；没有有效 Reference 的纯几何项目不再尝试读取空图片路径。
- 验证：Gate Q + Shared Field 定向 24/24 PASS；完整 unittest 210/210 PASS（225.537 秒）；固定图 self-test 6/6 PASS。日志：`work/gate-q-noise/full-regression.log`、`work/gate-q-noise/self-test.log`。

Gate R 暂未开始；只有 Gate Q 的完整回归与自检通过后，才允许进入 Field Combine。

## Gate P — Image Field / 图片驱动共享参数场（2026-09-14）

- Status: PASS
- 数据模型：新增 `ImageField(id, image_path, contrast, black_point, white_point, invert, out_of_bounds)`，仅输出归一化灰度标量；`PatternDocument` 仍是唯一 Source of Truth，源元素与 Reference 均只读。
- 采样：按 `FieldContext.bounds` 将世界坐标映射到图像，使用双线性插值；支持 Clamp/Zero 超界、黑场/白场重映射、对比度与反转。Pillow 像素缓存按绝对路径、mtime_ns、文件大小失效。
- 接入：`FieldRegistry`、统一 `SharedFieldEngine`、既有 Size Modifier、Grid/导入元素和 SVG/Save/Load 均复用同一 Evaluate 路径；不触发 Raster→SVG 或分析器。
- UI/预设：参数化效果面板新增“图片场”中文控件；缺失图片输出中性值并保持可编辑。Preset 只保存参数，应用时绑定目标文档的当前 Reference，不保存像素。
- 验证：Gate P 专项 3/3 PASS；完整 unittest 205/205 PASS；固定图 self-test 6/6 PASS。日志：`work/gate-p-full-regression.log`、`work/gate-p-self-test.log`。

Gate R 暂缓：当前仓库尚未完成并验证 Gate Q NoiseField，不能跳过前置条件直接实现 Field Combine。

## Gate O — Parametric Preset System（2026-09-14）

- Status: PASS
- 数据模型：新增独立、版本化的 `ParametricPreset(schema_version, name, fields, modifiers, shared_modifier_stack, shape_pool, assignment_settings, random_settings, source_bounds, metadata)`；严格不是 `PatternDocument` 的序列化副本。
- 存储：`PatternLabSession.workspace / presets/*.preset.json`，与 Project JSON、Raster、源码和用户当前选择状态隔离；支持保存、应用、复制、重命名、删除以及重启后发现。
- 安全边界：预设不保存 `source_elements`、Slots、ReplacementMap、Local Overrides、Raster、Selection 或 Zoom/Pan。应用只替换效果配置，保留目标 Geometry 的源快照、结构模型、局部编辑及手动替换。
- 适配：保存时记录源 Geometry Bounds；应用时中心坐标按归一化位置、长度/半径/位移按 X/Y/平均比例映射到目标 Bounds。Seed、角度、强度、权重与 Occupancy 不变。
- 兼容：未来未知 Modifier 自动跳过并记录 Warning；Selected Scope 不携带旧 Element ID，安全恢复为空范围。一次应用仅一条 Undo，Save/Load/SVG 继续使用既有 Evaluate Pipeline。
- UI：单一左侧滚动页增加中文“参数预设”列表与保存/应用/复制/重命名/删除；双击可应用。
- 验证：Gate O 核心、UI、持久化、尺度适配、未知层容错 6/6 PASS；与 Gate H/J/M/N 定向回归 21/21 PASS；完整 unittest 202/202 PASS（227.279 秒）；固定图 self-test 6/6 PASS。证据：`work/gate-o-preset/`；Gate P 未开始。

## Gate N — Random Transform + Density / Occupancy（2026-09-14）

- Status: PASS
- 数据模型：扩展既有 `RandomSettings`，保存 `seed`、`size_random`、`rotation_random`、`position_jitter_x/y`、`occupancy` 与复用的 `ModifierScope`；旧 `position_jitter` 仍可回读为统一 X/Y 扰动。
- 确定性：SHA-256(`seed|slot_id|channel`) 分离 `size`、`rotation`、`offset_x`、`offset_y`、`occupancy`；形状池保留独立 `shape_random_seed`，变化互不重洗。
- Evaluate：`Source/Structure → Manual + Shape Pool → Random Transform + Occupancy → Shared Modifier Stack → Local Override → Final Geometry`。
- UI：单一左侧滚动页新增中文随机与密度面板，支持 Seed、换一个、Slider + Entry 及 All/Selected/Circle/Rectangle/Invert Scope。
- SVG：`visible=False` 元素不再写入导出 SVG；项目 JSON 仍保存完整状态。
- 验证：Gate N + J/K/L/M 定向 29/29 PASS；完整 unittest 196/196 PASS；固定图 self-test 6/6 PASS。
- Gate O（Preset）未开始。

## Gate M.1 — Shape Pool Scope（2026-09-14）

- Status: PASS
- 数据模型：在既有 Placement Assignment metadata 新增 `shape_pool_scope: ModifierScope`；历史项目缺失该字段时等价于 All。
- 作用范围：全部元素、当前选择稳定 ID 快照、圆形、矩形与反转；Scope 根据当前 PlacementSlot 世界坐标判断，因而 Grid 重建后仍正确。
- 优先级：`Manual Replacement > Scoped Shape Pool > Original Shape`；范围外的元素保留原形，局部手动替换不受范围或 Seed 改变影响。
- UI：形状池面板增加中文范围子区与世界坐标/mm Slider + Entry；参数拖动仅预览，释放后提交一条 Undo。
- 验证：Scope 核心和 Tk UI 定向 7/7 PASS；完整 unittest 191/191 PASS；固定图 self-test 6/6 PASS。
- Gate N（Density / Occupancy）未开始。

## Gate M — Shape Pool + Deterministic Random（2026-09-11）

- Status: PASS
- 数据模型：`ShapePoolEntry(prototype_id, weight, enabled)`、`shape_pool_enabled`、`shape_random_seed` 均保存于既有 Placement Assignment metadata；旧项目默认关闭且不变。
- 确定性：使用 SHA-256(`seed|slot_id|shape_assignment`)；不依赖全局 `random()` 或 Element 遍历顺序。导入 Element 使用稳定 Element ID，Grid 使用 `grid:r{row}:c{column}`。
- 优先级：`Manual Replacement > Shape Pool Assignment > Original Shape`；清除手动替换会重新显示对应的随机形状。
- UI：规则矩阵页的单一滚动容器新增中文形状池，支持圆/方/菱形/三角/星/线、启用、权重 Slider + Entry、Seed、“换一种”与“恢复默认”。
- 验证：Gate M + K/L/Placement 定向 23/23 PASS；完整 unittest 189/189 PASS；固定图 self-test 6/6 PASS。3,000 Slot 分配性能已验证。
- Gate N（Density / Occupancy）未开始。

## Gate L — Multi Selection & Batch Editing（2026-09-11）

- Status: PASS
- 选择架构：继续由 `PatternLabSession.selected_id + selected_ids` 作为唯一来源；未建立第二个 SelectionSystem。
- 交互：Shift 点击切换、空白处世界坐标框选、Shift 框选追加、Ctrl+A 可见 Element 全选、Escape 清空。
- 批量：替换/恢复形状、缩放、相对旋转、位移、隐藏选中与显示全部；每项业务操作仅一条 Undo。
- Canvas：多选时绘制轻量单项边框和整体边界；成组拖动只变更瞬态 InteractionState，释放后一次 Commit。
- 持久化：形状映射、变换和可见性随现有 PatternDocument / Local Override / PlacementSlot 保存；选择集合不保存。
- 验证：Gate L + K/J/Canvas 定向 17/17 PASS；完整 unittest 184/184 PASS；固定图自检 6/6 PASS。
- Gate M（Shape Pool + Seed Random）未开始。

## Gate K — Shape Replacement / 形状替换（2026-09-10）

- Status: PASS
- ShapePrototype：circle、square、diamond、triangle、star、line；复杂形状统一输出闭合 FilledRegion。
- PlacementSlot 继续负责位置、尺寸和旋转；ReplacementMap 只保存 `element_id → prototype_id`，不覆盖源 Element。
- 原始 Element 快照随 Placement Assignment metadata 保存；恢复原形、Save/Load 和多次 Evaluate 后均可追溯。
- Evaluate 顺序：结构源 → Shape Replacement → Size/Rotation/Position + Scope → Local Override → Final Geometry。
- Element 编辑页提供中文形状下拉、应用替换、恢复原形；替换和恢复各产生一条 Undo。
- Gate K + Placement/Gate J 定向回归 14/14 PASS；完整 unittest 177/177 PASS；固定图自检 6/6 PASS。
- Gate L（多选/批量编辑）已通过；Gate M（Shape Pool + Seed Random）未开始。

## Gate J — Modifier Scope / 基础作用范围（2026-09-10）

- Status: PASS
- 统一 `ModifierScope` 已接入 Size、Rotation、Position 三类有序效果层；没有建立三套独立 Mask 逻辑。
- Scope 模式：All、Selected、Circle、Rectangle；Invert 适用于四种模式。
- Selected 保存稳定 Element ID 快照；Circle/Rectangle 使用 PatternDocument 世界坐标/mm。
- 未命中范围的 Element 保留前一层结果，不隐藏、不删除、不写回 source geometry。
- 旧效果层缺少 scope 字段时自动等价于 All，开发前视觉结果保持不变；旧 Grid visibility Mask 未改动。
- Preview 不写 PatternDocument/Undo；切换、反转和 Commit 均为正常单条 Undo。
- Gate J + Gate H/I/I-UI 定向 9/9 PASS；完整 unittest 173/173 PASS；固定图自检 6/6 PASS。
- Gate K（Shape Replacement）尚未开始。

## Gate I-UI — 位置/变形参数面板产品化（2026-09-10）

- Status: PASS
- 六种 Position 模式使用动态参数区；只呈现当前算法真正读取的参数。
- Slider 与 Numeric Entry 双向共享变量；拖动只读预览不写 PatternDocument，释放后一次提交一条 Undo。
- 模式切换为一条可撤销参数更新；Reset 只恢复当前 Position 层且保留当前模式。
- source geometry、stable type/id、Modifier Stack 与 Geometry Evaluate 算法未变。
- Gate I-UI 专项 2/2 PASS；完整 unittest 170/170 PASS。
- Gate J（Mask / Scope）尚未开始。

## Gate I — Position / Deformation Modifier（2026-09-10）

- Status: PASS（核心与最小中文参数入口已接入）
- `PositionModifier` 通过显式堆栈层对派生 Element 中心进行偏移/吸引/排斥/径向推出/扭转/波形位移；不写回 `source_elements`。
- Position 层可启用/停用、复制、删除、上下移动、重置；层顺序和参数保存到 PatternDocument metadata。
- 定向测试 2/2 PASS；Gate H 与共享 Modifier 回归 7/7 PASS；完整回归以本 Gate 提交时结果为准。
- Gate J（Mask / Scope）尚未开始。

## Gate H — 可组合 Modifier Stack（2026-09-10）

- Status: PASS（核心与 UI 管理面板已接入）
- `SharedModifierStack.modifiers` 提供稳定的有序 Size/Rotation 层；旧 `size_field/rotation_field` 兼容路径继续保留。
- 每层支持启用/停用、复制、删除、上下移动、重置；Evaluate 始终从 source snapshot 派生，不写回 source。
- Save/Load 保留层顺序、enabled 状态和参数；旧文档没有新列表时按原兼容逻辑加载。
- Gate H 定向测试 2/2 PASS；已有 UI/共享 Field 回归 PASS。

## Gate G follow-up — 参数面板滚动修复（2026-09-10）

- Status: PASS
- 规则矩阵页的共享参数、旋转、网格、渐变和掩膜控件统一进入单一垂直滚动容器。
- 参数页子控件滚轮已通过祖先判断路由，中央 Canvas 的缩放事件保持独立。
- Tk 界面回归 5/5 PASS（768/900/1080 高度）；全量 unittest 164/164 PASS，0 skip。
- 未修改 PatternDocument、Raster→SVG、Grid 分析、Canvas 操作或 Undo/Redo 业务逻辑。

## Gate G — Shared Field UI & Compatibility（2026-09-10）

- Status: PASS
- 兼容性审计通过正式 `PatternDocument → evaluate_pattern_document() → Final Geometry`：3/3 PASS。
- Field × Modifier 结果：`constant/linear_x/linear_y/ring/wave/stripe/checker/spiral` 支持 Size + Rotation；`radial/attractor` 仅支持 legacy Size；Position 当前明确 unsupported。
- UI 内部 ID 保持不变，显示名称/说明改为中文；参数按 Field 动态显示，Slider 与数值框共享变量并在释放时提交一次。
- 全量 unittest：163/163 PASS，0 skip。
- 新增文件：`field_ui.py`、`field_compatibility.py`、`tests/test_field_compatibility.py`。
- 本 Gate 未新增 Field、Generator、3D、素材库或 UI 主题重构。

- Current Gate: F — Final Compatibility
- Status: PASS — 不自动进入 Wave Gate B
- Current Branch: feature/shared-fields-nightly-20260909-1630
- Pre-change Snapshot Commit: b685af304241541a21a123bf7b86f2b995266e01
- Protected Snapshot Branch: backup/pre-safety-snapshot
- Stable Baseline Commit: 本次验证提交由 backup/stable-baseline 保护（提交后创建，不覆盖）
- Last Known Good Commit: 使用 `git rev-parse backup/stable-baseline` 获取验证提交
- Current Commit: A.5 验证提交后以 `git rev-parse HEAD` 为准（状态文件不自指提交哈希）

## Gate A.5 完成记录（2026-09-09）

- `evaluate_pattern_document()` 新增文档声明式 Field Graph 适配：
  `PatternDocument → SharedFieldEngine → SharedModifierStack post-field → Final Elements`。
- Ring/Linear 尺寸场在图存在时只消费一次；旧 Linear 输出、源 Geometry 与 SVG 保持兼容。
- Ring 接入既有共享参数场控件（Ring、环宽、反转），未引入新的 Generator 或独立 UI 系统。
- Gate A.5 定向测试：6/6 PASS；Gate A/Ring、Gate 1、SharedModifier 专项合计 33/33 PASS。
- 变更文件：`evaluation.py`、`shared_modifiers.py`、`parametric_families.py`、
  `ui_harness.py`、`tests/test_shared_field_integration.py` 及本记录文档。
- 全量回归：138/138 PASS，0 skip，188.949 秒；证据 `work/shared-field-integration-gatea5-regression.log`。
- Pattern Lab self-test：6/6 PASS；证据 `work/shared-field-integration-gatea5-self-test.log`。

## Gate B 完成记录（2026-09-09）

- 新增 `WaveField` 与通用 `RotationModifier`，保持 Field 只输出标量、Modifier 负责解释的架构。
- Wave 已通过正式 Document Evaluate、Size/Rotation、Grid、UI、Save/Load、Undo/Redo 和 source safety。
- Gate B 定向测试：5/5 PASS；与 Gate A.5/共享字段专项合计 39/39 PASS。
- 全量回归：144/144 PASS，0 skip，159.502 秒；证据 `work/shared-fields-nightly-gate-b-regression.log`。
- 当前 Last Known Good：待本 Gate 提交后以 `git rev-parse HEAD` 记录；不得在此之前进入 Gate C。

## Gate C 完成记录（2026-09-09）

- 新增 `StripeField`：周期、角度、相位、占空比、平滑度与反转均使用世界坐标并输出 0～1 标量。
- Stripe 通过现有 Size/Rotation Modifier、Document Evaluate、Grid、Save/Load、Undo/Redo 和 source safety。
- Gate C 定向测试：4/4 PASS；与前序共享字段专项合计 43/43 PASS。
- 全量回归：148/148 PASS，0 skip，152.819 秒；证据 `work/shared-fields-nightly-gate-c-regression.log`。
- 当前 Last Known Good：待本 Gate 提交后以 `git rev-parse HEAD` 记录；不得在此之前进入 Gate D。

## Gate D 完成记录（2026-09-09）

- 新增 `CheckerField`：格宽、格高、旋转、偏移和反转均使用世界坐标，输出确定性 0～1 标量。
- Checker 通过通用 Size/Rotation Modifier、Document Evaluate、Grid、Save/Load、Undo/Redo 与 source safety。
- Gate D 定向测试：4/4 PASS；与前序共享字段专项合计 47/47 PASS。
- 全量回归：152/152 PASS，0 skip，197.783 秒；证据 `work/shared-fields-nightly-gate-d-regression.log`。
- 当前 Last Known Good：待本 Gate 提交后以 `git rev-parse HEAD` 记录；不得在此之前进入 Gate E。

## Gate E 完成记录（2026-09-09）

- 新增 `SpiralField`：极角、归一化半径、圈数、相位、方向、衰减和反转均使用世界坐标。
- Spiral 通过通用 Size/Rotation Modifier、Document Evaluate、Grid、Save/Load、Undo/Redo 与 source safety。
- Gate E 定向测试：4/4 PASS；与前序共享字段专项合计 51/51 PASS。
- 全量回归：160/160 PASS，0 skip，157.041 秒；证据 `work/shared-fields-nightly-gate-e-regression.log`。
- 当前 Last Known Good：待本 Gate 提交后以 `git rev-parse HEAD` 记录；Gate F 只允许做兼容性检查。

## Gate F 完成记录（2026-09-09）

- 无字段旧文档兼容：PASS。
- 所有 Field 重复 Evaluate、Disable All、source integrity、Save/Load、SVG 物化和 Grid 结构保持：PASS。
- 最终全量回归：160/160 PASS，0 skip，169.507 秒；证据 `work/shared-fields-nightly-gate-f-regression.log`。
- Pattern Lab self-test：6/6 PASS；证据 `work/shared-fields-nightly-final-self-test.log`。
- 本轮停止，不继续开发 Noise、Image、Vector、Shape、Random、Density、Field Combine 或 3D。

## Gate 1 完成记录（2026-09-09）

- `SharedFieldEngine` 已建立；`ConstantField`、`LinearField` 的 `evaluate(element, context)`
  只产生 `0.0～1.0` 标量，不改写 source geometry。
- `FieldRegistry` 以稳定 `field_id` 管理场；`FieldMapping` 已支持 output、invert、clamp、strength、falloff 和 remap curve；本 Gate 只接入 Size。
- 旧的 Linear X/Y Size 通过兼容层调用新引擎；旧项目仍使用原 payload，无需 schema migration。
- `PatternDocument.fields[]` / `modifiers[]` 已以 JSON 图记录 Linear Size 场和 Modifier 引用，保存/重开保持。
- 修复“首次从既有应用按钮更新共享效果”未捕获 source snapshot 的累乘缺陷；停用可恢复 source。
- 修复 Pattern Lab 销毁时未取消性能 refresh timer 的 Tcl 回调残留。
- Regression：全量 unittest 127/127 PASS，0 skip，156.839 秒；Pattern Lab self-test 6/6 PASS。
- 证据：`work/shared-field-gate1/final-regression.log`、`final-self-test.log`、`focused-final.log`。
- Deliberately deferred：Radial/Elliptical/Attractor/Random、Rotation/Position 接入、Handle、Field UI、组合场；未经新 Gate 不得继续。

## Gate A 完成记录（2026-09-09）

- 变更：只新增 `RingField` 与 Gate A 测试，并把 Ring 纳入既有 `FieldRegistry` 反序列化；没有建立第二套 Engine。
- RingField 输出规范化 `0.0～1.0`，使用元素世界坐标；峰值在 `radius`，支持全宽 `ring_width`、Falloff 和 Invert。
- 现有 `SizeModifier` 直接消费 RingField，source geometry、Canvas 和现有 Modifier 不被永久修改。
- Gate A 定向测试：27/27 PASS。
- 完整回归：132/132 PASS，0 skip，257.831 秒；证据 `work/shared-field-ring-gatea-regression.log`。
- Pattern Lab 自检：6/6 PASS；证据 `work/shared-field-ring-gatea-self-test.log`。
- 当前用户运行中的窗口未被强制关闭或重启；RingField Gate 在源码中独立验证。

## Regression

### 2026-09-09 基线修复后复验（当前有效）

- 全量 unittest：108/108 PASS，0 skip，191.715 秒。
- Pattern Lab self-test：6/6 PASS。
- 证据：`work/shared-field-gate1/baseline-regression.log`、`baseline-self-test.log`。
- 仅更新 tests/test_phase1.py：Pillow 像素枚举改用已安装版本支持的 getdata；
  导入后检查真实 EditablePatternDocument 及项目持久化 payload；另外主动填入旧
  reference_elements 列表继续验证非哈希列表缓存场景。未降低像素、编辑或保存断言。
- 未修改或启动旧版产品供用户使用；独立测试窗口退出，用户现有应用不关闭。
- 下表和 Known Issues 是先前失败记录，不代表本次状态。

| 检查 | 结果 | 证据范围 |
| --- | --- | --- |
| 既有全量 unittest discover | FAIL | 106 项：103 PASS，1 FAIL，2 ERROR；225.028 秒 |
| 新增 Modifier 源数据恢复契约 | PASS | 1 项，多次修改后关闭效果，数据恢复且源快照不变 |
| 新增真实 Tk 回调 smoke | PASS | 1 项，窗口初始化、PNG/JPG 实际导入、隐藏原图后 144 图元、选中/位置编辑、Undo/Redo、Grid 变为 120 元素、SVG、保存恢复 |
| Pattern Lab self-test | PASS | 六类固定图实际转换、可编辑数据与序列化检查 |
| Drag/Scale、Zoom/Pan | PASS（无界面） | 既有 direct manipulation / performance 测试；不声称本轮做了人工鼠标视觉验收 |
| 自由参数化 / Grid / 导入 / SVG | PASS（自动化范围） | 既有测试及新增 Tk 回调测试；不能抵消全量失败 |

既有全量测试启动时不包含本轮随后新增的两个测试文件；两个新增文件分别运行通过。
共实际执行 108 个 unittest 用例：105 PASS、1 FAIL、2 ERROR，另有 self-test 六图。

## Known Issues

1. `test_phase1.PhaseOneTests.test_reference2d_poc_is_connected_to_canvas_and_project`：
   tests/test_phase1.py:267，`Image.get_flattened_data` 不存在（AttributeError）。
2. `test_phase1.PhaseOneTests.test_reference_image_side_by_side_uses_two_complete_canvas_panes`：
   tests/test_phase1.py:195，调用同一缺失 Pillow API。
3. `test_phase1.PhaseOneTests.test_reference_analysis_apply_updates_field_canvas_after_editable_elements`：
   tests/test_phase1.py:235，reference_elements 数量为 0，期望大于 0。

这些历史失败已按上面的复验记录解决；Gate 1 回归没有已知失败。

## Changes

- Modified Files: .gitignore、xiaomang_pattern_lab/README.md。
- New Files: AGENTS.md、DEVELOPMENT_SAFETY.md、GATE_STATUS.md、.githooks/pre-commit、
  .gitattributes、tests/test_modifier_safety_contract.py、tests/test_gate0_tk_smoke.py。
- Deleted Files: NONE。
- Architecture Changes: NONE；未修改 Raster/Vector、Canvas、PatternDocument 或参数化业务。
- Local Git: 新建仓库；本地提交身份 Pattern Lab Automation <pattern-lab@localhost>；
  未设置远程、未推送；本地 core.hooksPath=.githooks。
- Runtime: 保留现有 .venv/.runtime 和外部依赖、构建物、旧安装包。

## Evidence and rollback

原始日志在 `work/safety-gate0/`：full-regression.log、modifier-contract.log、
tk-smoke.log、self-test.log；日志为本机生成物。源码 Git bundle 在 `backups/`。

源码快照回退（新目录必须不存在；保留当前开发目录）：

```powershell
git worktree add --detach ..\PatternLab-Recovery-Gate0 b685af304241541a21a123bf7b86f2b995266e01
```

此提交是待验证原始快照，包含上述已有失败，不能称为最后正常版本。
worktree 不包含被忽略的运行时与 node_modules，运行需要按 README 配置依赖。
不要执行 reset --hard、clean、branch -D 或覆盖现有目录。
