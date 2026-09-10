# Nightly Shared Field Report

## Gate G follow-up — 参数面板滚动修复（2026-09-10）

- 根因：矩阵页此前只有底部表单有局部滚动，顶部共享参数场和旋转场不在同一滚动区域，短窗口下后续控件被裁切。
- 修复：改为整页单一垂直滚动容器，移除嵌套底部滚动；增加 Tk 回归测试覆盖滚动到底部。
- 验证：Tk 5/5 PASS；全量 unittest 164/164 PASS，0 skip。

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
