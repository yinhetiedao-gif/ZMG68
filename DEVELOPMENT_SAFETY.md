# Pattern Lab 开发安全与版本回退规范

本规范落实用户 2026-09-09 提供的开发安全要求。现在只执行 Gate 0。

## 源码、运行时与版本

仓库根为 ParametricPatternGenerator，包含实验台及其共享内核、测试和第三方源码。
Git 保留旧源码用于兼容回归，不表示恢复旧产品开发。
`.venv`、`.runtime`、node_modules、build、dist、work、备份和安装包保留在原处，
不纳入源码提交。Git bundle/ZIP 是源码备份，不是自带运行时安装包。
恢复源码后需要有效 Python+Tk、项目 requirements 和 external Node 构建产物。

没有 Git 历史时允许先初始化本地仓库，创建待验证快照；不得编造稳定提交。
只有运行、回归均通过后，才创建 `backup/stable-baseline`。
若基线有失败，使用 `backup/pre-safety-snapshot` 保护原始源码，Last Known Good 写 NONE。
已有稳定分支永不覆盖；之后另建带日期的保护分支。

## Gate 顺序

0. 保存现状、回归验证、基线与回退路径。
1. ModifierStack 基础。
2. Size 迁移。
3. Rotation 迁移。
4. Position。
5. Mask。
6. Shape Prototype / Replacement。
7. Random / Seed / Density。
8. 高级 Field。

既有模块不重复实现。每个 Gate 为“开发 → 测试 → PASS → Commit → 下一 Gate”。
诊断证据或失败快照可单独提交，但提交名称和状态必须注明 NOT VALIDATED/BLOCKED，
不更新 Last Known Good，也不进入下一 Gate。

## 每轮回归

在仓库根执行：

```powershell
git status --short --branch
git diff
git diff --cached
& .\xiaomang_pattern_lab\.venv\Scripts\python.exe -m unittest discover -s tests -v
& .\xiaomang_pattern_lab\.venv\Scripts\python.exe -m xiaomang_pattern_lab.main --self-test
```

必须记录 Import PNG/JPG、Raster→Vector、Elements 显示、Selection、Drag、Scale、
50/100/200% Zoom 和 Pan、Undo/Redo、Save/Load、SVG Export、共享参数化、旧 Grid。
无界面测试证明数据/数学行为；GUI 回调测试证明 Tk 控件链路；二者都不能冒充人工视觉验收。
Skipped、未运行或缺依赖均不得标 PASS。日志保存到每轮独立 work 子目录。
测试 Modifier 关闭后恢复 Source Geometry，源快照不被效果累乘或改写。

出现 FAIL/ERROR：DO NOT CONTINUE。记录具体测试 ID、traceback、影响范围。
不得通过删除测试、放宽断言或把失败标“旧问题”来宣称本轮全部通过。

## 提交与保护

功能分支为 `feature/*`，每个通过的 Gate 独立提交。使用本地 pre-commit 保护钩子
阻止 main/master/backup 分支提交（防误操作，不是远程服务器级权限保护）。
每轮记录 `GATE_STATUS.md`，可验证提交证据独立存档；不要用 HEAD 占位冒充真实 LKG。

禁止未经明确确认执行 `git reset --hard`、`git clean -fd`、`git branch -D`、
`git push --force`、丢弃改动的 `git restore .`、删除基线和覆盖整个项目目录。

## 回退

先 `git status`、`git diff`、`git log --oneline --decorate`，保留坏版本和用户改动。
优先 `git worktree add --detach <新的不存在的目录> <已验证提交>`，在新目录验证。
未建立 LKG 时只能恢复“原始快照”，不能宣称是正常版本。
不要在仍有未保存工程的运行目录上切换分支。

## 结束报告

Current Branch / Baseline Commit / Current Commit / Modified Files / New Files /
Deleted Files / Architecture Changes / Regression Results / Known Issues /
Last Known Good Commit / Rollback Command 必须齐全。FAIL 时写 DO NOT CONTINUE。
