# Phase 1A：右侧制造检查器 / 中央实时3D（2026-10-06，本地验收）

## 状态与范围

- Branch：`feature/pattern-library-reuse`。
- Baseline / final Git HEAD：`b5338a9af41d25ccd191d34366115578265920bb`，未提交。
- 开始时已有44个修改/未跟踪文件，复制保护于 `work/phase1a-manufacture-layout-20261006/pre-change/`；其余原受版本控制文件可由HEAD只读对照。没有清理、回退、恢复叫停补丁或修改暂存区。
- 保留前两轮1A和cells-only改动，本轮生产代码仅改Web；没有改Python几何、并发限制、依赖、部署配置或生产开关。
- 独立本地production smoke：`http://127.0.0.1:8792/`，已有测试STL权限；未重启/终止用户8791服务。独立Edge会话不覆盖用户草稿。
- 最终浏览器实际加载 `/assets/index-CzZA6WYv.js`；未提交、推送、部署或进入1B。

## 修改文件与连接

| 文件 | 本轮修改理由 |
| --- | --- |
| `web/src/App.tsx` | 一份制造表单进入右检查器；②/③共享持续挂载的Fabric画面；临时尺寸、自动预览、即时入口校验及未提交输入保护 |
| `web/src/document/ParameterInteraction.tsx` | 现有draft机制增加同步pending及显示回调；取消/提交/外部同步清除临时值，保持单次提交 |
| `web/src/document/ParameterPanel.tsx` | 复用Generic Renderer，增加可选onDraft，不建立新表单体系 |
| `web/src/manufacturing/fabricTemporaryDimensions.ts`（新增） | 仅显示层对权威最终尺寸施加基础宽深/固定高度的比值；保留XY、旋转、enabled、相对尺寸和Z基准，不写DTO或制造Mesh |
| 同目录 `useFabricPreview.ts` | 180ms合并、同步single-flight、等待取消任务实际排空；自动只处理最新提交DTO；保留上次有效画面和接受该画面的DTO |
| 同目录 `FabricThreePreview.tsx` | 同一个renderer/OrbitControls；仅原型/基底/数量变化重建共享几何，其余更新实例矩阵与颜色；首次或主动Fit才取景 |
| 同目录 `ManufacturingPanel.tsx` | 预设、输出、单元、高度、布点、高级绑定/尺寸分组；操作区portal到右底部；沿用预检/制造/导出状态 |
| 同目录 `FabricPreflightPanel.tsx`, `FabricFusionPanel.tsx` | 输入一致性处理入口校验；最终生成/下载按钮在固定操作区；下载交付前再次检查pending/stale |
| 同目录 `PreviewPanel.tsx` | App中不再复制STL按钮，普通最终模型继续原ThreePreview；移除按preview ID重挂载Fabric画面 |
| `web/src/styles.css` | 中央占满、右栏独立滚动、footer正常布局不覆盖参数、窄输入框/可折叠标题；左栏保留 |
| `web/src/App.f1.test.tsx`, `App.phase1a.test.tsx` | 新布局/单次提交/模式保留/Undo/入口保护回归；旧待提交文本查询改为指定状态区 |
| `web/src/manufacturing/useFabricPreview.test.tsx`, `fabricTemporaryDimensions.test.ts`（后者新增） | 同帧去重、失败重试、旧响应、latest-only、保留画面、Z0/.6和倍率各一次 |
| `tools/phase1a_live_manufacture_smoke.cjs`, `phase1a_live_manufacture_readback.py`（新增） | 实际生产页面、鼠标拖动录像、HTTP记录、实际下载后严格读回；不重新构造替代导出模型 |
| 本文与 `GATE_STATUS.md` | 本地证据、失败记录和未执行边界 |

## 布局和交互

- 中央显示设计预览，**不是制造通过状态**。实例数量、真实XYZ、Fit/Reset及三个原显示风格保留。
- 右栏只有一份表单，独立滚动；固定右底部 `生成最终模型` / `下载测试 Fabric STL`。普通二维仍为 `检查并生成` / `导出 STL`。
- 独立预检可选；直接最终生成仍由原服务器执行候选/预检/融合/严格校验。
- 有单元配置且二维求值ready，进入②自动调用已有轻量预览，当前缓存ready则复用。无单元明确提示在右侧选择；API失败显示实际错误。
- **拖动即时显示**：主要单元大小（维持宽深比）、均匀固定高度。只更新权威实例/原型TRS，不改相机比例或点距。
- **松手/确认自动更新**：方向角、Height范围、布点、原型、高级场等。React不重新实现Field算法；仅提交后的现有API计算。
- 高度场开启时固定基础高度不冒充最终高度的即时控制。高级/复杂draft明确显示“松手后自动更新”。
- 主尺寸drag过程中0次evaluate、0次preview、0次final；每次松手1次文档提交、1次evaluate、1次preview、0次final。Undo还原该次提交，Redo恢复。
- 同一个App协调器保护四个冲突CPU入口。取消UI等待仍等真实HTTP计算排空。下载、health和诊断不被无差别锁住。
- 复杂输入测试：方向模式请求被隔离浏览器延迟交付期间提交45°、90°，只发初始和最终90°两个预览，不发45°预览；旧响应不覆盖最新设计。
- pending Layout没有被自动Apply；未提交参数禁止最终生成/导出，处理函数和下载交付前均校验，不只是按钮disabled。

## 真实浏览器证据

目录：`work/phase1a-manufacture-layout-20261006/`。

- `layout-before-drag.png`, `layout-after-drag.png`：同输入/视角，实际宽深2.4→4.2mm，高度3→5mm。自动鼠标实际落点是4.2，未伪报目标4.8。
- `live-size-height.webm`：通过真实canvas.captureStream/MediaRecorder录制的**中央画面**，不是整页视频；配套JSON记录同时证明拖动期间无请求及生成按钮禁用。
- `height-map.png`：方向高度90°、2..6mm，真实WebGL彩色渐变；样式切换不改DTO、不发计算，不重建renderer。
- `camera-before-mode-switch.png`, `camera-after-mode-switch.png`：实际鼠标旋转后②→③→②，canvas节点相同，renderer初始化计数始终1。Orbit damping按180个实际渲染帧稳定后，提供的pixel_diff比较总差异0.01%（抗锯齿/残余阻尼），未重置相机。
- `layout-final.png`：右栏滚动到底，中央画布bounding box不变、页面scrollY=0。
- 1280×720 / 1440×900 / 1920×1080：无横向页面溢出，footer处于窗口内且是独立布局区域，不覆盖滚动内容。
- `browser-evidence.json`：100/400/1000真实运行的完整请求、状态、性能；`browser-evidence-100.json`：最终构建再验100实例/颜色/下载，记录自身asset身份。两者无pageerror，实际成功POST均200。
- 最大计算请求等待响应头数量为1；100实例时最大HTTP**传输**数量2（上一响应body尚传输、服务器计算已完成）。不把传输重叠误报为同时CPU计算，未提高后端并发。

### 性能：不冒充FPS或完全无延迟

固定输入：60×60mm，原点(10,20)，Pattern Points，Pyramid 2.4×2.4×3，cells-only；同一鼠标10步输入。表中端到端包括原二维求值、180ms合并、网络/浏览器及自动化等待。

| 实例 | 进入②到ready | 松手大小到ready | 松手高度到ready | 最后一次显示矩阵更新 |
| ---: | ---: | ---: | ---: | ---: |
| 100，三规格同轮 | 617ms | 722ms | 1363ms | 0.2/0.2ms |
| 400 | 925ms | 1292ms | 2217ms | 0.3/0.4ms |
| 1000 | 4550ms | 7411ms | 10732ms | 0.4/0.7ms |
| 100，最终构建再验 | 526ms | 667ms | 1344ms | 0.1/0.3ms |

1000轻量preview内部evaluate约126..135ms、plan约9..25ms、serialization约4..6ms；它不代表整个编辑校准耗时。**1000实例的整体松手校准仍明显慢，原因尚未独立定位，不宣称流畅度或FPS达标**。临时画面保持可见，无事件队列积压或最终融合。

## 实际下载与STL读回

按钮真实触发下载，文件存在，然后直接读回这些文件；不是用同参数重建另一份模型替代。

| 文件 | 实际组件 | XYZ mm（float32读回） | 字节 |
| --- | ---: | --- | ---: |
| `cells-only.stl` | 100 | 62.20×62.20×5.933333 | 30084 |
| `with-base.stl` | 1 | 62.20×62.20×6.533333 | 57884 |
| `standard.stl` | 100 | 60×60×2 | 60084 |

- 全部finite、绕序一致、水密、正体积、零退化面、现有MeshValidator PASS。
- cells-only底部Z=0，只有100个独立封闭单元，不存在整张底板；实际bounds与preview及final report相符（1e-5mm）；各组件高度排序与权威plan匹配。
- Solid模式保留0.6mm基底，最终单组件；模式切换立即使旧下载失效，再生成后下载。
- 普通二维允许原100独立组件，未误套Fabric带基底的单组件要求。
- `stl-readback.json`保存完整结果。Grid实体/孔洞/接触规则由下面Python定向回归覆盖，**本轮未新增Grid浏览器下载验收**。
- 源图范围60mm、单元footprint形成62.2mm成品范围，各自语义正确，不机械要求宽高相同。

## 测试命令及结果

在`web/`：

```powershell
npm.cmd test -- src/App.phase1a.test.tsx src/App.f1.test.tsx src/App.p2.test.tsx src/App.p2d.test.tsx src/App.p2c.test.tsx src/App.examples.test.tsx src/App.p0-layout.test.tsx src/document/ParameterPanel.test.tsx src/document/fabricHeight.phase1a.test.ts src/document/fabricOutput.1a.test.ts src/document/fabricPresets.test.ts src/manufacturing/useFabricPreview.test.tsx src/manufacturing/fabricTemporaryDimensions.test.ts src/manufacturing/FabricThreePreview.test.ts src/manufacturing/FabricFusionPanel.test.tsx src/manufacturing/FabricPreflightPanel.test.tsx src/manufacturing/computeRequests.test.ts --maxWorkers=2
npm.cmd test -- src/App.phase1a.test.tsx src/manufacturing/FabricThreePreview.test.ts src/manufacturing/fabricTemporaryDimensions.test.ts --maxWorkers=2
npm.cmd run build
```

第一条17文件87/87 PASS；最终显示颜色/状态提示微调后第二条12/12 PASS；build PASS（最终index-CzZA6WYv.js）。历史第一次命令还含不存在的requestErrors.test.ts筛选，实际Vitest执行仍是同17文件；错误解析真正由computeRequests.test.ts覆盖，不伪造额外文件通过。

仓库根：

```powershell
.\xiaomang_pattern_lab\.venv\Scripts\python.exe -B -m pytest -q tests/test_fabric_cells_only_1a.py tests/test_phase1a_dimensions.py tests/test_web_manufacturing_perf1.py tests/test_fabric_stl_f5c.py -k 'not 5000 and not basic_fin_and_1000'
.\xiaomang_pattern_lab\.venv\Scripts\python.exe -B -m pytest -q tests/test_fabric_base_f1.py tests/test_fabric_candidate_f5a.py -k 'grid or solid'
$env:PLAYWRIGHT_MODULE='C:/Users/13524/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'
node tools/phase1a_live_manufacture_smoke.cjs
$env:PHASE1A_COUNTS='100'
node tools/phase1a_live_manufacture_smoke.cjs
.\xiaomang_pattern_lab\.venv\Scripts\python.exe -B -m tools.phase1a_live_manufacture_readback
git diff --check
```

Python15 PASS/3 deselected；Grid/Solid4 PASS+2 subtests/13 deselected。此轮没有更改Python核心，不执行5000或无关Tk全量。浏览器及最终下载读回PASS；diff whitespace check PASS、暂存区空。

### 失败记录（不隐藏）

- 最初旧测试有同名“待提交”查询、旧按钮名，以及允许同时两次preview的旧假设；已保留原功能断言并改为准确状态区/新名称/等待旧计算排空再请求新版本，新增single-flight/latest-only回归。
- 浏览器脚本曾用不存在的“角度”定位，实际Linear Schema标签“方向角度”，修正测试定位，无参数/引擎改动。
- 最初把requestfinished之前body传输计为CPU重叠；现分别记录响应头前计算与传输，保留真实传输峰值2，不修改并发策略。
- 相机PNG二进制比较在Orbit阻尼未完成时失败；修为等待真实帧、像素对照并记录0.01%，不是放宽几何标准。
- 读回脚本直接按文件执行无法导入包；改为已验证的`python -m tools...`，不改依赖或生产代码。

## 限制与停止

- 全部是本地证据，公网/Render NOT TESTED，未改变测试导出授权。
- Bambu Studio、切片、实物、手机 NOT TESTED。未声称Fabric physical PASS。
- 1000实例权威校准慢；后续性能定位需另批范围，未新增算法或降低质量。
- 既有bundle>500kB warning、TestClient弃用warning保留；JSDOM不具WebGL产生getContext提示，视觉依据真实Edge而非单元测试。
- 前阶段5000退化限制未处理，Validator保持严格。
- 未建立新stable backup、未提交/推送/部署、不进入1B。等待用户检查效果。
