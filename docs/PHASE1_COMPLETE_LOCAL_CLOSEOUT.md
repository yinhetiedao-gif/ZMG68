# 阶段一完整工作流 — 本地收口（2026-10-10）

## 版本与授权

- 仓库ParametricPatternGenerator，分支feature/pattern-library-reuse，提交前HEAD为dd16f64aab07e894cdc09218c56a416579b45203；暂存区空，27个tracked修改、40个untracked文件先保护再分类。没有更晚收口提交。
- 原稳定backup/web-native-design-local-validated仍指向上述完整SHA，不移动。新backup/web-phase1-complete-local-validated检查时不存在，只在成功提交后创建；实际身份以Git提交及最终报告核对，不以文档HEAD占位。
- 本轮只检查、必要交叉测试、记录、本地提交与备份；没有产品代码修改、新依赖、线上配置/权限变动、旧补丁恢复、reset/clean/amend/rebase、推送或部署。
- 保护副本在work/phase1-complete-local-20261010/source-before-record/，差异在working-tree-before.patch；不删除文件、不改忽略规则。

## A/B完整提交范围

明确47个文件：A为22个实现文件，B为25个必要测试、fixture、记录及中心可复用验收工具。相互依赖，用一个完整提交保存，不拆不能运行的中间版本。

- A包含六新Cell registry/工厂/Schema/稳定ID及选择UI、目录加载/布点/旧预览状态；元素可读性；线性有限矩形的Python真实作用范围与画布控件；显式原图/单元来源与实际轮廓原型；预览/候选、大小/高度；三套高度配方/专用场隔离与原图/Fin兼容。
- 必要新生产依赖web/src/document/fabricOriginal.ts、xiaomang_pattern_lab/fabric_original.py纳入，不能只提交中心配方。其他实现文件列表：
- web/src/App.tsx
- web/src/api/fabricPreview.ts
- web/src/document/InspectorControls.tsx
- web/src/document/fabricCell.ts
- web/src/document/fabricModifiers.ts
- web/src/document/fabricPresets.ts
- web/src/document/linearSize.ts
- web/src/document/parameterSchema.ts
- web/src/geometry/Workspace2D.tsx
- web/src/geometry/gradientControls.ts
- web/src/manufacturing/FabricThreePreview.tsx
- web/src/manufacturing/ManufacturingPanel.tsx
- web/src/manufacturing/fabricTemporaryDimensions.ts
- web/src/styles.css
- xiaomang_pattern_lab/fabric_candidate.py
- xiaomang_pattern_lab/fabric_cells.py
- xiaomang_pattern_lab/fabric_plan.py
- xiaomang_pattern_lab/fabric_preview.py
- xiaomang_pattern_lab/parameter_definitions.py
- xiaomang_pattern_lab/shared_fields.py
- B包括修改的正式测试与phase1aFixture、4个新增Python测试、6个新增Web测试、5份分阶段验收报告、GATE_STATUS与本文，以及tools/center_recipe_1b_smoke.cjs / center_recipe_1b_readback.py。
- 可移植fixture由规范模型构造；中心浏览器小样内联构造并引用已追踪的basic-grid.pattern.json、gradient-grid.pattern.json。新增Python测试复用已追踪tests/test_fabric_cells_only_1a.py；不依赖个人图片或未跟踪运行资产才能运行正式测试。
- 父提交已有两步导航/旧preview兼容、基础图形/参考底图、线性/径向快捷/控制柄、请求协调/错误解析、草稿/Undo及严格制造/Exporter，完整保留，不重复开发。没有Docker/render/依赖锁/生产开关变化。

## 当前集成证据与对应版本

- 中心最终App/配方/控件源码修改早于10:29浏览器及10:31最后Web80和构建；本轮只有记录变动，没有验收后产品修改。
- 原图和Fin各完成方向→波浪→中心→方向→中心。原轮廓/孔洞、二维XY/相对大小/旋转、shape source/选中单元、output/base/placement及作用范围外效果保持。未换Pyramid/偷偷加底板，无重复高度绑定。4类共享引用copy-on-write及用户场不借用由当前测试覆盖。
- Reset/Apply一次commit/Undo；Undo/Redo/已应用草稿刷新恢复完整引用；保存失败阻止替换。未应用Layout保留，未应用快捷二维表单要求先应用/取消，不偷提交。形状或高度变化后旧结果stale、下载禁用。
- 当前3份浏览器实际STL及300条逐元素读回仍存在，文件大小与报告一致。56个POST全200；原图/Fin切换、Reset/Undo/Redo和刷新检查true。没有重新制造另一模型代替证据。
- center-default-original.stl、center-offcenter-original.stl、center-fin.stl分别61,084/61,084/40,084bytes；各100个有效组件、水密、正体积、绕序一致、Z=0、0退化。每实体完整顶点、XY/旋转/尺寸及独立采样高度吻合，真实孔保留。
- 仅图案允许有效多组件、不宣称融合整体；带Solid9点Python原图/Fin为1组件。普通STL及Grid有效/脱离拒绝引用最近原图证据，不扩为所有造型×配方矩阵。
- 实际本地运行是当前工作区FastAPI/8797、生产index-flDVYUfN.js、独立Edge/IndexedDB。收口health200、staging及既有测试导出能力，backend_commit仍UNKNOWN；新Git提交不能冒充已运行/已部署身份。

## 测试分批，不相加为全量

| 批次 | 结果 | 本轮处理 |
| --- | --- | --- |
| 当前中心最后Web | 11文件80/80 PASS | 引用，后续无产品修改 |
| 当前中心/波浪/原图Python | 34/34 PASS（含中心9） | 引用，无后续Python修改 |
| 当前生产构建 | PASS，index-flDVYUfN.js | 引用对应产物，不伪称本轮重建 |
| 本轮交叉Web | 13文件51/51 PASS | 补原生设计、底图、尺寸快捷/范围、控制柄、示例/草稿 |
| 浏览器实际交付/读回 | 当前3份文件与逐元素报告PASS | 复用并核对存在/大小/报告，不重复制造 |
| 较早99/116/84/49等批次 | 各历史记录保留 | 不累加、不宣称本轮重新全验 |

本轮在web目录执行：

```powershell
npm test -- src/App.nativeDesign.test.tsx src/App.linearSize.test.tsx src/App.examples.test.tsx src/App.draft.test.tsx src/document/nativeDesign.test.ts src/document/referenceLayer.test.ts src/document/linearSize.test.ts src/document/linearRegion.test.ts src/document/radialSize.test.ts src/geometry/gradientControls.test.tsx src/geometry/Workspace2D.wm56.test.tsx src/draft/localDraft.test.ts src/examples/catalog.test.ts --maxWorkers=2
```

没有真实产品回归，不跑Tk全量、重复六单元制造或400/5000压力。暂存前窄密钥形态扫描通过；无.env、凭据、个人文件。提交前再核对暂存内容和diff check。

## 边界及OPEN

- 数值控件松手/确认后预览。设计画布线性/径向/局部范围控制柄限频更新候选、只处理最新值；拖动与松手不提交，应用一次提交。只支持实际参数，不代表所有参数逐帧实时。
- 未应用快捷二维表单不持久化，刷新/明确切换上下文会丢弃；pending Layout沿用browser-only恢复。刷新正式文档后旧Undo历史重新开始。
- 混合追加独立图形、多选直接编辑的限制及旧非中性隐式效果堆栈不自动迁移保留。
- 原8792故障页11类型全部鼠标、刷新/草稿/目录重载、原页下载确认仍OPEN，部分最初DOM/内部状态UNKNOWN；8793/8797隔离/API证据不代替它，不因稳定引用关闭该问题。
- Dome/Ring高面数制造较慢；400圆环历史冷制造到下载22.810s，不能拿暖缓存代替。bundle>500kB、Starlette/httpx/CRLF提示、5000退化/Tk基础设施问题未在本轮关闭。
- 本批公网/Render/Linux、切片、实物、原生浏览器工具栏缩放NOT TESTED；历史Linux记录保留但不充当本批证明。不是Physical/Production标签。
- 仅逐元素高度，非单轮廓连续曲面，不支持全区域重复自定义轮廓。非法/开放/歧义/空几何仍拒绝，未repair/删面/放宽Validator。
- 分阶段记录保留其当时“未提交/未实施”的历史时态；当前完整提交范围以本收口记录及Git为准。

## C：未提交、原地保留的22个旧批脚本

以下不是正式构建/测试必要输入；部分依赖旧work资产、旧端口或旧配方语义，包含历史探查。不自动捆入当前稳定版，不声称本批重验；不删除。

- tools/gradient_handles_readback.py
- tools/gradient_handles_smoke.cjs
- tools/linear_size_readback.py
- tools/linear_size_smoke.cjs
- tools/original_shape_readback.py
- tools/original_shape_smoke.cjs
- tools/phase1a_cells_only_readback.py
- tools/phase1a_cells_only_smoke.cjs
- tools/phase1a_live_manufacture_readback.py
- tools/phase1a_live_manufacture_smoke.cjs
- tools/phase1a_local_smoke.cjs
- tools/phase1a_readback.py
- tools/two_step_native_readback.py
- tools/two_step_native_smoke.cjs
- tools/two_step_reference_probe.cjs
- tools/unit_cell_selection_readback.py
- tools/unit_range_readback.py
- tools/unit_range_ui_layout.cjs
- tools/unit_range_ui_smoke.cjs
- tools/unit_shapes_benchmark.py
- tools/wave_recipe_1b_readback.py
- tools/wave_recipe_1b_smoke.cjs

忽略的work截图/STL/日志/运行资产/源码快照、node_modules/.venv/dist及其他worktree同样保留，但不在Git稳定引用的保护范围。未修改.gitignore。

## 提交与安全取回

- 使用明确47文件列表暂存，本地消息feat: finalize phase1 shape-preserving height recipes。
- 提交成功后创建backup/web-phase1-complete-local-validated，保留旧引用；完整SHA及实际指向以最终Git核对。无空提交或历史重写。
- 以后取回时先检查状态，再在不存在的新目录使用git worktree add --detach <新目录> backup/web-phase1-complete-local-validated，不覆盖当前用户目录。本轮不实际执行回退。
- 完成后STOP；不推送、不部署、不进入新图案逻辑。
