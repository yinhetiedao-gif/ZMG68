# Pattern Lab development rules

唯一活跃应用：`xiaomang_pattern_lab`（小芒图案实验室）。项目依赖的
`ppg.foundation`、集成 Adapter、tests 和 external 源码在本仓库内保留。
旧应用仅供兼容回归，不作为默认启动或新增功能对象。

每次开始先完整阅读 `DEVELOPMENT_SAFETY.md` 和 `GATE_STATUS.md`，执行
`git status --short --branch`、`git diff`、`git diff --cached`。

- 新功能仅在 `feature/*` 分支上开发。`backup/*`、main、master 禁止直接修改。
- 先保存源码快照，验证后才能将提交记作 Last Known Good。
- 每个 Gate 必须单独回归、记录、提交。FAIL/ERROR/未验证不等于 PASS。
- 任意旧功能失败，禁止下一 Gate；允许为当前 Gate 定位、修复并重测。
- 未经用户明确确认，禁止 reset --hard、clean -fd、branch -D、push --force、
  丢弃改动的 restore、删除保护分支、覆盖整个目录。
- 回退优先在新目录创建 detached worktree；不要强制切换正在使用的源码。
- 所有结构共用 Source Geometry → Modifier Stack → Local Overrides → Final Geometry。
  保护 Raster/Vector、source_elements、PatternDocument、Canvas 坐标与交互、
  Undo/Redo、Save/Load、SVG Export。不要建立第二份独立 Elements 状态。
- 发布前汇报 Current Branch、Baseline/Current Commit、变更/新增/删除文件、
  架构变化、Regression、Known Issues、Last Known Good、Rollback Command。
- 应用在运行时不要强制结束它来测试。使用独立临时测试实例。
  Windows .venv 的 Python 启动器可能产生基础 .runtime Python 子进程；
  必须核对父子关系与 pyvenv.cfg，不能把它误当作旧应用并杀掉。
