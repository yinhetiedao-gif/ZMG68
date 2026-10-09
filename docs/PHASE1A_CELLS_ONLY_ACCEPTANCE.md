# Phase 1A 修正：仅图案单元输出 / 默认尺寸（2026-10-06）

## 范围与保护

- 分支 `feature/pattern-library-reuse`；HEAD 始终为 `b5338a9af41d25ccd191d34366115578265920bb`；暂存区为空。
- 开始时已有14个 tracked 修改和10个 untracked 文件，属于前一轮1A。逐文件复制到 `work/phase1a-no-base-20261006/pre-change/`，未覆盖、清理或恢复旧补丁。
- 请求协调、专用高度、草稿保护、配方及测试保留。没有提交、推送、部署、依赖/部署配置改动；不进入1B。
- 独立本地生产构建服务 `http://127.0.0.1:8792/`；原8791服务未关闭。仅独立测试进程沿用已有 `XIAOMANG_ENV=staging` / `XIAOMANG_FABRIC_STL_TEST_EXPORT=1`，未修改生产开关。
- 浏览器采用独立 Edge context，不覆盖用户已有浏览器草稿。

## 本次修改文件与理由（不含此前1A已有改动）

| 文件 | 修改理由 |
| --- | --- |
| `xiaomang_pattern_lab/fabric_base.py` | FabricConfig.output_mode；缺失字段兼容旧带基底行为 |
| 同目录 `fabric_preview.py`, `fabric_plan.py` | 无基底实例Z=0；布局bounds/margin继续布点；允许合法零起点 |
| 同目录 `fabric_candidate.py` | 无基底完全不调用基底几何/挤出；VALID与ATTACHED区分；空结果拒绝 |
| 同目录 `fabric_fusion.py` | 原manifold平衡树处理cells-only；按模式约束组件；模式覆盖指纹 |
| 同目录 `fabric_stl.py` | 原STLExporter；读回组件数等于实际最终结果，无基底不机械要求1 |
| 同目录 `manufacturing_service.py` | 误入原F1基底挤出接口的cells-only请求明确拒绝，不错误输出底板 |
| 同目录 `parameter_definitions.py` | 新单元基础宽深默认2→4mm，合法范围/高度默认不变 |
| `xiaomang_pattern_lab/web/app.py` | 候选/融合传递权威输出模式 |
| `web/src/document/fabricBase.ts` | 新配置默认无基底；旧配置保留；切换一次revision |
| 同目录 `fabricCell.ts` | 统一大小按原宽深比例调节，不改高度、点位、间距或场 |
| 同目录 `fabricPresets.ts` | 方向配方v2无基底、4.8×4.8mm、跟随二维；旧预设仅首次配置默认无基底，旧值不迁移 |
| `web/src/App.tsx` | 输出方式接入正常commit/Undo/失效 |
| `web/src/manufacturing/ManufacturingPanel.tsx` | 两种输出、主要大小/高度、精确宽深与基底参数在高级设置 |
| 同目录 `FabricThreePreview.tsx` | 无基底不加入底板对象，实例TRS仍来自后端计划 |
| 同目录 `FabricPreflightPanel.tsx`, `FabricFusionPanel.tsx` | 真实模式提示/组件报告，不假称连到底布或单体融合 |
| `web/src/api/fabricPreview.ts`, `fabricCandidate.ts`, `fabricFusion.ts` | 模式/请求/响应一致；只对明确cells-only接受多组件；保留stale检查 |
| `tests/test_fabric_cells_only_1a.py` | 无基底、比例、组合变换、相交、空/坏输入、缓存/开关/普通制造回归 |
| `web/src/document/fabricOutput.1a.test.ts` | 新旧模式、比例控件、Reset/草稿、严格响应解析 |
| 同目录 `fabricCell.test.ts`, `fabricPresets.test.ts`, `web/src/App.f1.test.tsx` | 测试数据跟随当前Schema默认/模式契约；既有断言保留 |
| `tools/phase1a_cells_only_smoke.cjs`, `phase1a_cells_only_readback.py` | 真实网页下载/截图，严格读回下载文件，不另建替代模型 |
| `GATE_STATUS.md`, 本文、`PHASE1A_LOCAL_ACCEPTANCE.md` | 本地证据、历史配置对照与未验收边界 |

## 生成与校验

`Final FabricInstancePlan → enabled prototype copies + final TRS → mode-specific candidate → existing manifold union → existing MeshValidator → existing STLExporter`。

- 无基底完全不生成Solid/Grid实体，不保留原0.6mm悬空偏移；单元自身底面保留。布局范围是最终二维mm bounds，不是Canvas像素。
- 无基底不要求接触基底、不要求单组件。带基底保留原接触、Grid孔洞、真实融合及单组件要求。
- 两模式仍要求有限坐标、正确绕序、封闭、正体积、零退化面、Validator无错误；无基底各manifold分量必须正体积。
- 相交用原可靠实体并集；互不相交保留全部有效实体，报告实际数量，不声称一个融合整体。不删面、不Repair、不放宽epsilon、不自动加板。
- 空或非法单元阻止导出；开关关闭仍403。导出复用已通过最终mesh，不重新制造。
- 完整DTO、模式、尺寸、revision、mesh进入现有指纹。测试同revision换模式仍拒绝旧STL；正常UI变更后旧结果立即失效。

## 新默认、统一大小与旧作品

- 新建单元Schema基础宽深 `2×2 → 4×4mm`，高度仍3mm；制造算法不乘2，读取存量值不乘2。
- 方向配方v2基础宽深 `2.4×2.4 → 4.8×4.8mm`，跟随二维相对大小；二维Scale和Fabric Scale各应用一次。
- 主大小控件改变宽度，并按原宽深比改变深度；不变更XY、rotation、height或布点间距。
- 老配置没有output_mode仍带基底，旧尺寸不静默升级。显式切换或应用/Reset新配方才更改；一次正常提交，可Undo。
- 原五套预设的显式尺寸/场行为未全面迁移，不声称拥有新版方向配方的所有归属保障。

## 三张真实截图

证据目录：`work/phase1a-no-base-20261006/`。
同一100点fixture：60×60mm、非零原点(10,20)、Pattern Points、Pyramid、方向高度2~6mm。
实际采样高度约2.0667~5.9333mm，不能把UI范围直接冒充实际网格极值。
1600×1100 viewport、Default样式、同一isometric reset视角；Fit仍按实际bounds选距离，不靠相机改变几何。

1. `before.png`：修改前配置对照（保留旧带底板配置绘制，并非启动旧源码），宽深2.4mm、板厚0.6mm。
2. `no-base.png`：同尺寸、同位置/高度，无底板，单元Z=0。
3. `no-base-large.png`：宽深4.8mm，分布更清楚，仍有间隙/高度趋势。

三份同名preview JSON逐实例核对：XY/height/rotation不变，宽深精确2倍。真实WebGL画面成功，未用API成功替代。
vision CLI本机缺失，已用现有本地图片预览逐图检查。

## 实际网页下载与严格读回

以下都是网页点击下载后的实际文件，不是另外重建的替代模型。全部Z min=0，封闭、绕序正确、正体积、零退化面，现有MeshValidator PASS。

| 文件 | XYZ mm（约） | 组件 | 三角面 | 字节 |
| --- | --- | --- | --- | --- |
| `nine.stl` | 60.4×60.4×3 | 9 | 54 | 2784 |
| `grid-base.stl` | 62×62×3.6 | 1 | 2484 | 124284 |
| `with-base.stl` | 62×62×6.5333 | 1 | 1012 | 50684 |
| `no-base-large.stl` | 62.8×62.8×5.9333 | 100 | 600 | 30084 |
| `standard.stl` | 60×60×2 | 100 | 1200 | 60084 |

无基底9/100文件仅对应单元，没有连接板、参考网格/坐标轴。100单元读回每组件高度与Preview逐一匹配。
Grid带基底使用同一九点图案，spacing5mm/line width3mm，预检/融合/下载成功；Solid带基底同一100点图案成功。
Grid孔洞拒绝继续通过自动化回归。普通二维100组件没有套用Fabric带基底单组件要求。
完整数据：`browser-evidence.json`、各`*-final.json`、`stl-readback.json`。

## 命令与结果

从`web/`运行23个受影响文件：

```powershell
npm.cmd test -- src/document/fabricOutput.1a.test.ts src/document/fabricHeight.phase1a.test.ts src/document/fabricCell.test.ts src/document/fabricBase.test.ts src/document/fabricModifiers.test.ts src/document/fabricPresets.test.ts src/document/ParameterPanel.test.tsx src/document/realSize.test.ts src/draft/localDraft.test.ts src/App.phase1a.test.tsx src/App.examples.test.tsx src/App.p2c.test.tsx src/App.f1.test.tsx src/api/fabricPreview.test.ts src/api/fabricPlan.test.ts src/api/imageAssets.test.ts src/api/manufacturingArtifacts.test.ts src/manufacturing/computeRequests.test.ts src/manufacturing/FabricFusionPanel.test.tsx src/manufacturing/FabricPreflightPanel.test.tsx src/manufacturing/useFabricPreview.test.tsx src/manufacturing/StlExportButton.test.tsx src/manufacturing/FabricThreePreview.test.ts --maxWorkers=2
npm.cmd run build
```

从仓库根目录，同一已安装解释器/依赖：

```powershell
.\xiaomang_pattern_lab\.venv\Scripts\python.exe -B -m pytest tests/test_fabric_cells_only_1a.py tests/test_fabric_base_f1.py tests/test_fabric_cells_f2.py tests/test_fabric_preview_f25.py tests/test_fabric_fields_f3.py tests/test_fabric_ranges_f35.py tests/test_fabric_candidate_f5a.py tests/test_fabric_fusion_f5b.py tests/test_fabric_stl_f5c.py tests/test_phase1a_dimensions.py tests/test_web_staging.py tests/test_stl_export_gate_x.py tests/test_manufacturing_service_wm1.py -k 'not 5000' -q --tb=short
node tools/phase1a_cells_only_smoke.cjs
.\xiaomang_pattern_lab\.venv\Scripts\python.exe -B -m tools.phase1a_cells_only_readback
git diff --check
```

浏览器脚本使用已有PLAYWRIGHT_MODULE/Edge，不安装依赖。
Web：108/108 PASS（23文件，24.64秒）；production build PASS（现有bundle警告保留）。
Python：80 PASS +34 subtests，3 deselected（5000不属本轮），17.26秒。
浏览器五个下载成功，pageerrors=[]；实际文件严格读回PASS。

覆盖已有1A：统一请求busy/入口、根级/嵌套/detail错误、旧请求排空、失败恢复；均匀模式不建场、方向专用场、共享引用复制隔离、一次Undo、配方保护/Reset、pending不偷偷Apply、例子返回/草稿恢复。
尺寸回归：mm比例1/2、旧px比例.25、非正方形、非零原点、图片资产恢复。
Area Fill无基底Solid/Grid配置都生成八个单元，mock禁止调用BaseBuilder.geometry。
px=.25在世界毫米中存在实际相交，并集为三个组件，未假装九个穿插实体。

## 失败记录与剩余限制

- 初始旧plan拒绝Z=0：仅改为拒绝负起点，不改变高度/尺度合法标准。
- 旧测试mock不含新模式/Z、旧默认仍2mm：更新真实契约/Schema，未删除断言。
- 旧px小比例发生真实相交：按实际并集组件核验，不缩小单元、不改间距。
- 首次浏览器Undo selector使用旧中英标签超时：改为实际“撤销”后通过；readback首次直接执行的模块路径/编码问题改为`-m`与UTF-8。失败运行不计PASS，产品一致性检查未移除。
- Bambu Studio GUI/切片/实物/公网Render：NOT TESTED，待用户核看。不声明断开的独立单元实际打印后自动连成面料。
- 本轮采用固定9/100点测试图，未读取或覆盖用户当前浏览器作品。
- 保留现有bundle/TestClient warning、5000退化限制；未跑无关Tk全量。
- 无基底仍保留合法基底参数用于margin/切回基底，它们不生成实体。
- 本地改动等待用户确认；无稳定Git/Physical backup，不宣布F5 CLOSED。
