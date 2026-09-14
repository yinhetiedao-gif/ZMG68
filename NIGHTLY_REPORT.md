# Nightly Shared Field Report

## Gate M — 形状池与稳定随机（2026-09-11）

- 目标：让多个既有 ShapePrototype 按权重分配至同一组 PlacementSlot，同时让同一 Document + Seed 永远产生同一图案。
- 实现：新增正式 `ShapePoolEntry`、`shape_pool_enabled`、`shape_random_seed`。分配只使用 SHA-256 stable hash，不使用全局随机数或列表下标。
- 安全性：Evaluate 保持 `Source → Slot → Manual Replacement → Shape Pool → Modifier Stack → Local Override → Final Geometry`；手动替换优先，源快照不变；全零权重回退原始形状。
- UI：在既有单一可滚动参数页加入中文权重、Seed、“换一种”和重置控件；拖动权重先走只读预览，释放/确认后提交一条 Undo。
- 验证：定向 23/23 PASS；全量 189/189 PASS；self-test 6/6 PASS；100/500/1000/3000 Slot 分配均已自动验证。

## Gate L — 多选与批量编辑（2026-09-11）

- 目标：让数百至数千个真实 Element 可以一次选择、一次编辑，保持 PatternDocument 为唯一数据源。
- 实现：在既有 `selected_ids` 上增加世界坐标框选、Shift 追加、Ctrl+A、Escape 和成组拖动；不新建第二套选择/Transform 状态。
- 批量操作：形状替换/恢复、按元素自身中心缩放、相对旋转、位移、隐藏/显示；业务提交均使用一条 Undo Transaction。
- 可见性：自由元素保留 Element record，参数化模型使用 LocalOverride，Placement 模式使用 PlacementSlot；均不删除 source geometry。
- 性能：100/500/1000 Element 的选择、移动和缩放已在专项测试中执行；当前实现保持既有 SpatialIndex，不做额外 Canvas 架构重写。
- 验证：专项及 K/J/Canvas 回归 17/17 PASS；完整 unittest 184/184 PASS；固定图 self-test 6/6 PASS。

## Gate K — 非破坏式形状替换（2026-09-10）

- 目标：让单个槽位更换视觉形状，同时保留原始几何、稳定 ID、现有效果堆栈和可逆编辑。
- 实现：扩展既有 ShapePrototypeRegistry 与 ReplacementMap；新增原始 Element 持久快照，避免重复物化或保存重开后无法恢复。
- 形状：圆形、正方形、菱形、三角形、星形、线形；Path 形状使用通用 FilledRegion Canvas/SVG 链路。
- 组合：Replacement 在共享 Size/Rotation/Position/Scope 之前执行；Grid 行列、间距变化后按稳定 cell ID 继续应用。
- UI：Element 编辑页增加中文形状选择、应用替换、恢复原形和当前替换状态。
- 验证：Gate K + Placement/Gate J 定向回归 14/14 PASS；完整 unittest 177/177 PASS；固定图 self-test 6/6 PASS。

## Gate J — Modifier Scope / 基础作用范围（2026-09-10）

- 根因：效果层只能全局作用；既有 Grid Mask 的语义是控制可见性，若复用会错误隐藏未命中元素。
- 修复：新增统一 `ModifierScope`，以 0/1 influence 选择当前层结果；未命中项沿用上一层派生结果。
- 范围：全部、当前选择快照、圆形、矩形、反转；Size/Rotation/Position 共用同一数据结构。
- UI：所选效果层显示中文范围面板，连续范围参数使用动态毫米 Slider + Entry；临时预览和单次 Commit 分离。
- 兼容：旧层无 scope 时按全部元素运行；Grid 可见性 Mask、source snapshot、Local Override 和 stable layer ID 均保持。
- 验证：Gate 专项及 H/I/I-UI 回归 9/9 PASS；全量 173/173 PASS；固定图自检 6/6 PASS。

## Gate I-UI — 位置/变形参数面板产品化（2026-09-10）

- 根因：六种位置模式此前共用十一项纯 Entry，当前模式无关参数仍然可见，且缺少已选层的双向参数编辑。
- 修复：按模式重建动态参数区，统一 Slider + Numeric Entry；范围从 source bounds 推导，内部单位仍为 mm/radian/0..1。
- 交互：预览使用候选 PatternDocument 执行只读 Evaluate；不写文档、不增加 Undo，Commit 时一次性更新当前层。
- 重置：Position 层保持当前模式并只重置该层；其他 Size/Rotation/Position 层不受影响。
- 验证：专项 2/2 PASS；全量 170/170 PASS。

## Gate I — 位置与变形修饰器（2026-09-10）

- 根因：Gate H 堆栈只支持尺寸和旋转，位置变化会被迫写入源几何或另起一套生成器。
- 修复：新增统一 `PositionModifier`，按有序层对派生元素中心执行六种确定性变换；现有 source snapshot 与参考图保持只读。
- 交互：参数页提供中文模式和数值入口，位置层沿用堆栈的启停、排序、复制、删除、重置与一次性 Undo。
- 验证：Position 专项 2/2 PASS；Gate H/共享 Modifier 回归 7/7 PASS；完整测试将在提交前执行。

## Gate H — 可组合 Modifier Stack（2026-09-10）

- 根因：现有共享效果虽然按 Size/Rotation 分离，但没有用户可管理的有序层列表。
- 修复：新增显式 `modifiers` 层记录和最小管理面板；每层可启停、复制、删除、上下移、重置。
- 安全性：新列表存在时清空兼容 graph，统一由 Stack 从 source snapshot 派生；未启用新列表的旧项目路径不变。
- 验证：Gate H 2/2 PASS；共享 Field/Canvas/滚动面板专项 PASS。

## Gate G follow-up — 参数面板滚动修复（2026-09-10）

- 根因：矩阵页此前只有底部表单有局部滚动，顶部共享参数场和旋转场不在同一滚动区域，短窗口下后续控件被裁切。
- 修复：改为整页单一垂直滚动容器，移除嵌套底部滚动；增加 Tk 回归测试覆盖滚动到底部。
- 补充：滚轮事件按鼠标所在控件的祖先关系路由，只滚动左侧参数页，不抢占中央 Canvas 缩放。
- 验证：Tk 5/5 PASS（768/900/1080 高度）；全量 unittest 164/164 PASS，0 skip。

## Gate G 产品化收尾（2026-09-10）

- 新增稳定的 Field 中文显示映射、中文说明和动态参数面板；保存格式继续使用英文 stable id。
- 新增正式评估链路兼容性审计：共享 Field 的 Size/Rotation 支持状态已自动验证，Position 明确标记未接入。
- Slider/Entry 使用同一 StringVar；拖动只做预览，释放或确认时调用一次 `apply_family_fields()`，避免连续 Undo。
- Gate G 专项：3/3 PASS；全量回归：163/163 PASS，0 skip。
- 当前版本：1.6.31；未新增 Field 或 3D/素材/案例功能。

Baseline Commit: `db5fd5ba698863608e3cc92286d46877daf6366a` (`backup/gatea-stable`)

Development Branch: `feature/shared-fields-nightly-20260909-1630`

Final Commit: 以本文件所在最终提交执行 `git rev-parse HEAD` 获取

Last Known Good Commit: `4895b05cadf72e065bdbc5fe764ced923ebb1073`（Gate E；Gate F 仅兼容性检查）

## Gate A.5

- Status: PASS
- Commit: `db5fd5ba698863608e3cc92286d46877daf6366a`
- Result: PatternDocument Field Graph 正式接入 Evaluate；Ring 生效；Linear 无重复应用；Save/Load、Undo/Redo、SVG、Grid 全部通过。

## Gate B Wave

- Status: PASS
- Commit: `893cf7b063af2bcaed09db1ed4a9431e533ab533`
- Tests: Wave 专项 5/5；该 Gate 全量回归 144/144 PASS。

## Gate C Stripe

- Status: PASS
- Commit: `83bd35986f3e4189e0e37c11c8321ec9993216b4`
- Tests: Stripe 专项 4/4；该 Gate 全量回归 148/148 PASS。

## Gate D Checker

- Status: PASS
- Commit: `dc64ce0581f2301dcffc2cb781061107d26d70ce`
- Tests: Checker 专项 4/4；该 Gate 全量回归 152/152 PASS。

## Gate E Spiral

- Status: PASS
- Commit: `4895b05cadf72e065bdbc5fe764ced923ebb1073`
- Tests: Spiral 专项 4/4；该 Gate 全量回归 156/156 PASS。

## Gate F Final Regression

- Status: PASS
- Final full test count: 160
- Passed: 160
- Failed: 0
- Skipped: 0
- Evidence: `work/shared-fields-nightly-gate-f-regression.log`
- Pattern Lab self-test: 6/6 PASS；`work/shared-fields-nightly-final-self-test.log`

## Existing Features Regression

- Raster→Vector: PASS
- Selection / Drag / Scale: PASS
- Zoom / Pan: PASS
- Undo/Redo: PASS
- Save/Load: PASS
- SVG: PASS
- Grid / Radial / Free Parametric: PASS
- Linear Double Apply: PASS
- Ring / Wave / Stripe / Checker / Spiral: PASS
- Source Elements Integrity: PASS；重复 Evaluate 不改写 source geometry
- Grid structure: PASS；Rows、Columns、Spacing 未被 Field 改写

## Files Added

- `tests/test_shared_field_wave.py`
- `tests/test_shared_field_stripe.py`
- `tests/test_shared_field_checker.py`
- `tests/test_shared_field_spiral.py`
- `tests/test_shared_field_gate_f.py`

## Files Modified

- `xiaomang_pattern_lab/shared_fields.py`
- `xiaomang_pattern_lab/parametric_families.py`
- `xiaomang_pattern_lab/shared_modifiers.py`
- `xiaomang_pattern_lab/evaluation.py`
- `xiaomang_pattern_lab/ui_harness.py`
- `xiaomang_pattern_lab/README.md`
- `CHANGELOG.md`
- `GATE_STATUS.md`

## Files Deleted

- None

## Known Issues

- 当前已运行的 Pattern Lab 窗口是在开发分支切换前启动的旧进程；未强制关闭。要使用本夜间版本，请正常关闭后从 `xiaomang_pattern_lab/start_pattern_lab.ps1` 重新启动。
- UI 仍是现有实验台风格，本轮没有进行视觉重构。
- 本轮没有实现 Noise、Image、Vector、Shape、Random、Density、Field Combine 或 3D。

## Rollback Commit

```powershell
git switch --detach backup/gatea-stable
```

或使用逐 Gate 保护分支：`backup/shared-fields-gate-b`、`backup/shared-fields-gate-c`、`backup/shared-fields-gate-d`、`backup/shared-fields-gate-e`。

## Recommended Next Step

停止 Shared Field 夜间扩展，先由用户重新启动并实际操作验证；后续如继续开发，应另开新分支，不能直接把 Shape、Random、Density 或 3D 叠加到本分支。
