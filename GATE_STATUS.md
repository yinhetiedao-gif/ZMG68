# Gate 状态（2026-09-09）

- Current Gate: 1 — Shared Field Engine 基础 + Linear Size 迁移
- Status: PASS — 不继续 Gate 2
- Current Branch: feature/shared-field-gate1
- Pre-change Snapshot Commit: b685af304241541a21a123bf7b86f2b995266e01
- Protected Snapshot Branch: backup/pre-safety-snapshot
- Stable Baseline Commit: 本次验证提交由 backup/stable-baseline 保护（提交后创建，不覆盖）
- Last Known Good Commit: 使用 `git rev-parse backup/stable-baseline` 获取验证提交
- Current Commit: Gate 1 提交后以 `git rev-parse HEAD` 为准（状态文件不自指提交哈希）

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
