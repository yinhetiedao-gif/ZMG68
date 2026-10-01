# Gate 状态（2026-10-01）

## F2.5 Fabric 预览稳定化与布点方式（2026-10-01）

- 状态：**实现与定向验证完成；全量 Python 回归未正常退出，因此 F2.5 尚未验收 PASS、尚未提交或建立最终稳定备份**。开发分支 `feature/f2-5-fabric-stabilization`；F2 稳定点 `backup/f2-unit-cell-library-final` 保持不变。当前修改不进入 F3。
- 新预览 API 直接由最终二维几何建立 `FabricInstancePlan`，复用单个 Unit Cell 原型和浏览器 `InstancedMesh`；预览不调用 Fabric 完整制造、Boolean、Mesh Validation、GLB/STL。`Area Fill` 保留规则采样；`Pattern Points` 对每个有效最终元素取世界毫米坐标的代表点，真实 169 方块 JPG 得到 169 个实例。预览最多均匀显示 5000 个实例，超限只简化显示，不回写布点参数。
- 浏览器实测 169 方块项目：100 / 400 / 1024 / 5041 总布点均可请求独立预览；修正采样前 5041 的预览只显示 2521，现已增加回归确保显示 5000 / 5041。浏览器单原型实例创建：100=10.0 ms、400=9.9 ms、1024=11.1 ms；5041 的旧采样结果为 2521=10.9 ms，新 5000 显示量尚未在重启后端的浏览器复测。浏览器致命 Console error 0。Fabric STL 按钮禁用且说明尚未开放；普通制造/STL 路径保持。
- 同机单次 profiler：真实 169 项目原完整 Fabric 制造前置路径 2777.5 ms（基底构建+挤出 1105.9 ms、Mesh Validation 1491.0 ms 为主要耗时），独立预览 311.9 ms（含首次原型/求值）；此前另一次机器负载下测得 7538.4 ms 对 540.4 ms。用户报告的 111 秒失败现场未提供，**不能声称已复现或根治**。100/400/1000/5000 计划构建约 0.17/0.47/1.06/5.72 ms，序列化约 0.22/0.60/1.36/6.81 ms。
- 169 JPG 的 Shared Field 制造矩阵（无 Field、Constant、Linear、Wave、Ring、Stripe、Checker、Spiral、Noise）9/9 在统一安全参数下通过；未复现用户原退化面，公共根因仍待失败快照。F1/F2/F2.5 Python 定向 16/16 PASS；普通 Web 制造、STL 与 169 Field 矩阵定向 12/12 PASS；Web 112/112 PASS、构建 PASS，固定图案 6/6 PASS。全量 Python 两次均在既有 Tk `Variable.__del__` 非主线程清理异常处失去正常退出能力，第二次停在 `test_web_pattern_structure_wm65` 测试期间，人工中断 exit 1。按安全规范不把该结果记为全量 PASS。
- F2.5 补充（Final Geometry 映射）：Pattern Points 以既有 `final_geometry()` 的可见最终元素作为唯一布点输入；XY 取最终中心，X/Y 尺寸比对 evaluator 的稳定前置源尺寸，Z 旋转取最终角度。每个预览实例携带 source/final ID、XY 比例、角度、启用状态和基准单元尺寸；浏览器对共享原型仅应用一次平移/旋转/非均匀缩放。缺失可靠基准尺寸时以 1 倍显示并统计，不猜比例；隐藏元素已被最终几何过滤，不产生实例。此数据仅作派生预览，不回写 PatternDocument，也不进入最终 Fabric STL。
- 补充验证：真实 169 方块 JPG 的 Wave Size + Spiral Rotation + Wave Position 组合逐实例对齐最终二维 XY/尺寸比/角度，169/169 匹配；20 元素 Position 偏移、Density 可见性和 Area Fill 回归通过。独立测试浏览器加载该 JPG，3D 设计预览显示 169 个共享原型实例（evaluate 18.3 ms、plan 309.7 ms、HTTP 往返 391.5 ms、浏览器实例创建 8.1 ms，单次本机测量）。F1/F2/F2.5 与 169 Field 制造定向 Python 19/19 PASS，Web 113/113 PASS、TypeScript/Vite build PASS。既有 Tk 全量退出问题仍未解决，F2.5 整体状态保持未验收；不提交最终稳定备份或进入 F3。
- Revision mismatch 修正：用户看到的统一“文档不匹配”实际上是 8765 端口的旧 FastAPI 响应实例缺少 `scale_x/scale_y`；诊断请求的 document ID 与 revision 16 在请求、后端接收和响应中全部相同，`placement_mode=pattern_points`。只重启该端口的 Pattern Lab FastAPI 后，同一诊断请求返回新版实例字段。前端现在分别提示真正的 ID/revision 不匹配与过旧/不完整响应；同 revision 的重复请求和旧 revision 晚到均按请求序号/Abort 丢弃，不关闭任何校验。真实 169 方块 JPG 在当前网页使用 Size/Rotation/Position 后，Pattern Points 预览 169/169 就绪，3D 视图显示 169 个共享原型实例；revision 16 的 169 组合用例由 Python 定向测试验证。Fabric 定向 Python 5/5、Web 116/116、构建 PASS；F2.5 整体仍受既有 Tk 全量退出问题阻塞。

## 169 方块图片的 Shared Field 制造对照（2026-10-01）

- 状态：**已建立真实 JPG 回归并完成安全参数对照；用户遇到的退化面失败尚未复现，根因未确认**。本轮不进入 F3/F4，不修改任何 Field、Manufacturing Adapter、挤出算法或 MeshValidator 阈值。
- 用户提供的 343×344 JPG 固定为 `tests/fixtures/field_manufacturing_matrix_169.jpg`（SHA-256 `941D82D277E16F6BD2D123339DFEF1181CA8DB64C281D3C0A8273ABF7F2A8F3F`）。现有 Raster → SVG → Faithful Mapping 导入产生 169 个独立 `filled_region`；Web 导入会给此类图片设置尚未确认的临时 `1 mm / SVG unit` 映射，本回归使用相同映射。
- 同一份导入文档依次测试无 Field、Constant、Linear、Wave、Ring、Stripe、Checker、Spiral、Noise；有 Field 时统一使用 Size Modifier `min_output=0.8, max_output=1.0, strength=1`，厚度 2 mm。9/9 均通过 Evaluate、Gate T、Connectivity、Adapter、Extrusion、Mesh Validation；每项均为 169 个可转换元素、0 跳过、0 退化三角面、0 Mesh 错误。最小三角面面积在 0.116–0.182 mm²。原始轮廓中的方块由闭合曲线表达，单个区域预览采样含大量共线点，但在此安全参数范围内未造成制造失败。新回归连同现有 U.5/V/W 制造测试为 31/31 PASS；未因仅增加测试/记录再运行受既有 Tk teardown 问题影响的全量套件。
- 这只能否定“该图片配任一 Shared Field 必然失败”，**不能证明用户会话里的参数组合、其他 Modifier、Fabric 配置或原失败 Mesh 没有问题**。仍需当次 `failure_id`/快照（包括 active Fields/Modifiers、manufacturing parameters 和 validation summary）才能定位第一个失败阶段与对应元素/三角面。未据此猜测根因或进行轮廓清理。

## Web 项目文件入口收敛与制造失败编号（2026-10-01）

- 状态：**定向功能验证通过；完整 Python 回归未验证 PASS**。起点 `bd7f8ab`，预变更保护引用 `backup/pre-web-session-only`。不更新 Last Known Good，不进入新 Fabric Gate。
- 普通 Web 界面移除“打开本地项目”及空白页 JSON 项目入口；PNG/JPG/SVG 导入、会话内 PatternDocument、设计/制造/预览/STL 流程保留。`.pattern.json` 文件输入只在 Vitest 的 `test` 模式挂载，供已有固定工程测试使用；生产构建不提供项目文件入口。原本没有普通用户的项目导出按钮。
- 开发模式 `XIAOMANG_DEV_MANUFACTURING_SNAPSHOTS=1` 下，制造验证失败自动保存原请求快照到 `work/manufacturing-failures/`；快照内容、文件名、服务日志与失败响应中的 `failure_id` 一致。默认模式不保存、不返回 `failure_id`；快照写入失败不覆盖原制造错误。未修改 MeshValidator 或制造算法。
- 验证：Web 110/110 PASS、TypeScript/Vite build PASS；制造快照 + Web API + F1/F2 定向 Python 26/26 PASS；固定图案 6/6 PASS。完整 Python 回归再次在既有 Tk `Variable.__del__` 非主线程清理阶段反复出现 `main thread is not in main loop`，未正常退出，测试进程人工中断为 exit 1。因此本变更**不能宣称全量 PASS**；Tk 生命周期问题仍需独立处理。

## 制造失败快照（2026-10-01）

- 状态：**调试能力已通过自动测试；原始退化面根因仍待失败工程复现**。起点 `b9e71fa`，预变更保护引用 `backup/pre-manufacturing-failure-snapshot`。本轮未进入 F3/F4，未调整 MeshValidator 阈值，也未修复或删除坏三角面。
- Web `/manufacturing/build` 对 Gate T/Gate W 制造验证失败及 Fabric Base 配置失败，在显式设置 `XIAOMANG_DEV_MANUFACTURING_SNAPSHOTS=1` 后写入 `work/manufacturing-failures/`。默认不写；文件名含 UTC 时间和随机 ID，不覆盖。快照包含实际请求 DTO、revision、厚度、Fabric 配置、启用 Field/Modifier、错误码及验证摘要；敏感键值脱敏，不存本机绝对路径或浏览器临时状态。快照 I/O 失败不覆盖原 HTTP 错误。
- 当前浏览器连接无法读取仍开着的失败页面；未获得当次 `.pattern.json`，没有据此猜测导致退化面的元素或参数。后续必须用用户保存的失败工程单独定位 face index、面积、顶点和来源。
- 验证：新增快照定向测试 4/4 PASS；制造/API/F1/F2 定向 26/26 PASS；固定图案 self-test 6/6 PASS；独立 Tk smoke 2/2 PASS。第一次完整 Python 回归（追加第 4 条测试前）384/384 PASS、exit 0；最终代码的第二次全量运行遇到既有 Tk `Variable.__del__` 非主线程清理风暴，无法正常退出，人工中断为 exit 1。因此**本轮 full regression 未验证 PASS，不更新 Last Known Good、不进入下一功能 Gate**。该退出问题不属于本轮 Web 快照代码路径，但本轮未做基线对照证明。

## F2 Fabric Unit Cell Library MVP（2026-10-01）

- 状态：**PASS（软件设计预览，不是最终 Fabric 制造）**。起点 `f03c3cd` / `backup/f1-fabric-base-final`；独立分支 `feature/f2-unit-cell-library`，事前源码快照 `backup/pre-f2-unit-cell-library`。Web Alpha 与 F1 稳定引用不覆盖。
- 在现有 `fabric_config` 下增加可选 `unit_cell` 和 `placement`；单元原型由 Registry/Factory 生成。FabricPlanner 在最终二维制造边界的基底范围内产生稳定 ID 的规则布点计划，固定高度/大小/方向，局部单元 Z=0，实例 Z=基底顶面。
- API 将计划作为同一 `manufacturing_result_id` 下的只读 `/fabric-plan` 提供给 Web；Three.js 使用一份原型几何的 `InstancedMesh` 显示。F1 基底的正式 GLB/STL、Mesh Validation 及其结果 ID/缓存策略不改变。没有单元配置时该接口返回 204。
- **制造边界**：F2 单元只是设计预览，不在正式 STL/GLB 基底网格里，也没有 Boolean 融合或实体连接保证；Grid Base 网孔上方的单元尚未验证 XY 接触与实物可制造。界面明确显示“导出基底 STL”。不声明完成最终 Fabric 面料打印。
- Python 全回归 381/381 PASS，F1+F2 定向 13/13 PASS；50×40 mm / 5 mm 间距为 80 实例；100×100 mm / 5 mm 间距为 400 实例，单原型计划约 1.4–2.1 ms（本机多次测量）。真实浏览器带孔图案中圆柱 36 实例、鳍片 9 实例及鳍片 400 实例可见；400 实例请求到制造状态就绪约 301 ms，切入预览到实例状态可见约 14 ms（单次本机测量，不是标准化帧率）。Fatal Console error 0。Web 107/107 PASS、npm build PASS、固定图案 6/6 PASS。

## F1 Fabric Base MVP（2026-10-01）

- 状态：**PASS（软件验证，未作 Fabric Base 实物打印）**。F0 文档基线 `01bff18`；F1 独立分支 `feature/f1-fabric-base`，Web Alpha 冻结标签和保护分支不变。
- 在原 PatternDocument 元数据中增加可选版本化 `fabric_config`。无配置时沿用原制造路径；有配置时，在原有 Evaluate、二维几何校验与制造边界转换之后，由无 UI 依赖的 `FabricBaseBuilder` 生成 Solid 或 Grid 基底，再进入原有 Mesh Validator、GLB 预览和 STL 导出。
- F1 基底取最终二维制造几何的轴对齐外接矩形，使用 mm；Solid 填满矩形，Grid 生成相连的横纵条带。它不沿源轮廓裁切，也不保留源图孔洞或融合原元素。厚度须与制造请求一致；非法/非有限参数被拒绝。基底尚无独立实物打印证明。
- 定向 Python 12/12 PASS；完整 Python 回归 374/374 PASS（exit 0）；固定图案 6/6 PASS；Web 104/104 PASS、TypeScript/Vite 构建 PASS。并行负载下 Web 旧 P1-E 测试曾单次超时，隔离及全套顺序重跑均 PASS。浏览器在独立测试端口导入带孔 fixture，Solid/Grid 都得到封闭且单组件的 30×30×0.6 mm 模型，Grid 预览可见网孔，切换类型使旧结果 stale；HTTP STL 请求 200，自动化读回 STL/GLB 均封闭。备份将在提交后建立。

## Xiaomang Pattern Lab Web v0.1 Alpha — 实物验证冻结（2026-10-01）

- 状态：**PASS（用户报告的 Web Alpha 实物打印验收）**。产品代码基线 `b035c3f` / `backup/perf1-manufacturing-final`；本轮仅更新四份文档，不修改功能、制造算法或打包产物。最终冻结提交由 `web-v0.1-alpha` 标签和 `backup/web-v0.1-alpha-physical-validated` 分支共同保护。
- 用户确认已在网页版完成：图片/SVG 导入 → 可编辑二维与参数化设计 → Layout → Field → Modifier → 制造检查/网格验证 → 同一制造结果的 Three.js 预览与 STL 下载 → Bambu Studio → 切片 → 真机打印；实物正常。因此记录 `Web Alpha Physical Validation = PASS`。这是用户完成的实物验证，不冒充代理操作打印机、独立计量或任意图案/材料的制造保证；尚无此次打印的照片、测量公差及打印配置证据。
- 当前 Web Alpha 已接入：图片/SVG 导入、二维编辑、布局/参数场/效果堆栈、会话内 Undo/Redo、Web 制造、Mesh Validation、只读 Three.js 预览与 STL 下载。Python Engine 保持设计和制造计算权威；Web 预览不重新生成制造几何。
- 边界：这是本机运行的 Alpha，不等于已部署的商业网站或新安装包。网页项目保存/云端同步、3MF、自动连接/修复、最小壁厚保证、Fabric 系统仍未完成。先冻结此版本，不进入 F0 或 Fabric 实现。
- 冻结复验：Web 101/101 PASS、TypeScript/Vite build PASS；Python full regression 368/368 PASS（exit 0，日志 `work/web-v0.1-alpha-freeze/python-full.log`）、固定图案 6/6 PASS、Tk smoke 2/2 PASS。全部产品代码未改；仅文档提交后创建上述 tag 与保护分支，不重打包。

## PERF-1 — Web「检查并生成」耗时优化（2026-09-30）

- 状态：PASS。基线 `847a911`，保护分支 `backup/pre-perf1-manufacturing`。本轮不改变制造几何或验证门槛，不进入 Fabric。
- 真实阶段测量显示：169 元素图案旧版暖机 build/store 约 522–540 ms，其中 Mesh Validation 约 195–227 ms，提前 STL 导出约 190–197 ms（包含重复 Mesh Validation）。优化后首次约 281–333 ms；阶段约为 evaluate 1 ms、二维验证 0.2 ms、连通性 5–7 ms、adapter 7–10 ms、extrusion 57–67 ms、Mesh Validation 199–227 ms，STL/GLB 准备均为 0。Mesh Validation 是剩余最大必要耗时，未跳过。简单矩形暖机由约 4.7 ms 降至约 2.9–3.8 ms；实物打印图案由约 13–14 ms 降至约 7.8–10.5 ms。首次简单模型可能因三角剖分依赖首次加载额外耗时，未将其算作算法退化。
- 一次 build 只求值、Gate T 验证、连通性分析、制造几何适配、extrusion、Gate W 验证各一次。`/manufacturing/build` 不再预制 STL、GLB、哈希或重复验证；下载 STL / 请求 GLB 时才从同一已缓存且验证过的 Mesh 懒生成，各 artifact 单次缓存。
- 相同完整 Document DTO + revision + thickness 命中进程内带 TTL 的结果缓存，直接复用 `manufacturing_result_id`；以完整 DTO 参与键值，避免 revision 不变但内容不同误命中。169 元素 HTTP 实测首请求 395.57 ms、同请求再次 17.16 ms。进程重启/TTL/容量淘汰后重新生成；并发的首次相同请求尚未做 single-flight 合并。
- Web 构建期间显示阶段说明与实际已耗时间；不伪造后端实时阶段进度。CPU 密集文档解析与 build 在 FastAPI threadpool，artifact 路由为同步 threadpool，不阻塞事件循环。
- 真实打印图案导出的新 STL 与既有物理验证样本字节一致（5484 B，SHA-256 `1d846c4bf8f8086862ae1efce578ef60fba5582043fbbea6ec84496ef062f7e3`）；bounds/组件/封闭性不变。Web 101/101 PASS、build PASS、Python full regression 368/368 PASS（exit 0）、固定图案 6/6 PASS。既有 Tk `ThemeChanged` 清理提示仍可出现，但不导致测试失败。

## Web STL 导出入口补全（2026-09-30）

- 状态：PASS。基线 `b663866` / `backup/p3-web-alpha-final`，预变更快照 `backup/pre-web-stl-entry`。本轮仅调整 Web UI 入口和共用下载控件，Python 制造算法、API、STL 文件内容均未修改。
- 制造报告下方现在明确显示“3D 预览”与“导出 STL”；3D 预览页保留“导出 STL”。两个页面共用同一个下载控件，继续调用既有 `/api/v1/manufacturing/{result_id}/model.stl`。项目名作为下载文件名，不泄露服务器路径。
- 只有当前结果存在、状态为 ready/warning、未过期且 Mesh 检查无错误时可导出。无结果、生成中、失败、stale 或 Mesh 检查错误时按钮禁用并显示简短原因；下载期间结果变旧则不会触发浏览器保存。
- 定向 Web 101/101 PASS、TypeScript/Vite build PASS；既有 Python GLB/STL 读回 3/3 PASS。真实浏览器：已打印三星项目在制造页直接导出、带孔工程在 3D 预览页导出，均只有一次 STL 请求、浏览器错误 0；三星下载 STL 读回约 `57.2169 × 19.8992 × 2.0000 mm`、3 组件、封闭且有效。证据位于忽略的 `work/p3_browser_smoke.cjs`、`work/p3-real-pattern.stl`；未运行无关完整 Python 回归。
- 完成后独立提交并建立新保护分支，不覆盖 `backup/p3-web-alpha-final`。安全回退点仍为 `backup/p3-web-alpha-final`，优先用新 worktree 检出。

## P3 Web 3D Preview + STL Download（2026-09-30）

- 状态：PASS。基线 `9221754` / `backup/p2-web-manufacturing-final`；开发分支 `feature/p3-web-alpha`，预变更备份 `backup/pre-p3-web-alpha`。本 Gate 不进入 Fabric，也不宣布完成真实 Web 打印验收。
- `POST /api/v1/manufacturing/build` 从同一份已验证的 `ManufacturingMeshResult` 生成并缓存正式二进制 STL 和只读 GLB 预览。新增 `GET /api/v1/manufacturing/{result_id}/preview.glb`；原 `GET .../model.stl` 保持。GLB 导出不重新 build、不修复或修改正式 Mesh。缓存结果随服务进程重启或 TTL 过期失效，需重新生成。
- Web 使用 Three.js 仅加载 GLB 进行显示、旋转、缩放、适合窗口、重置视角，Z 轴为制造厚度方向。下载仅从当前 `manufacturing_result_id` 调用 Python STL 路由；项目名被清理为安全的下载文件名。不在 React 生成或编辑制造几何。
- 文档身份/修订号或厚度变化时预览与下载立即 stale；异步下载在真正触发保存前再次核对当前结果。错误在预览区内联显示，不清空二维设计 Canvas。
- 实测：真实打印图案约 `57.2169 × 19.8992 × 2.0000 mm`、3 组件、制造验证 watertight；带孔 fixture 为 `20 × 20 × 2 mm`、1 组件，GLB 与重新加载的 STL 均保留孔。浏览器实际执行真实工程和带孔工程的导入、build、预览加载、适合窗口/重置、旋转/缩放、同 ID 下载与厚度 stale；浏览器致命 Console 错误 0。证据脚本及截图位于 `work/p3_browser_smoke.cjs`、`work/p3-real-pattern-preview.png`、`work/p3-hole-preview.png`；该目录为忽略的本机验收产物。
- 自动化：Python 制造/API/GLB 相关 16/16 PASS；Web 93/93 PASS；TypeScript/Vite build PASS。视觉截图检查的 `vision-skills/glance` CLI 在本机不可用，因此不声称人工像素级视觉验收；GLB/STL 拓扑及实际浏览器行为已有自动验证。真实 Web 下载后的 Bambu Studio 切片与实物打印尚待用户进行，不将 P3 等同于 Web Alpha 物理冻结。
- 提交后创建 `backup/p3-web-alpha-final`；安全回退点 `backup/p2-web-manufacturing-final`，通过新 worktree 检出，不强制 reset。

## P2 Web Manufacturing（2026-09-30）

- 状态：PASS。基线 `7778062` / `backup/web-parameter-range-audit-final` 已包含并提交全局滑杆范围优化，工作区开始时干净；本 Gate 独立分支 `feature/p2-web-manufacturing`，预变更备份 `backup/pre-p2-web-manufacturing`。未进入 P3。
- Web 制造模式复用既有 `POST /api/v1/manufacturing/build` 与 Python `ManufacturingService`；React 仅提交当前 PatternDocumentDTO、revision、厚度，展示几何检查、连通性、转换、Mesh 封闭性、组件、XYZ 尺寸及警告。3D Preview 仍禁用，没有 STL 下载按钮或新制造算法。
- 制造结果为浏览器派生状态，不写回 PatternDocument、revision、Undo 或 Canvas。构建中可显示状态；文档身份/修订号或厚度变化立即将旧结果标为 stale，不再展示其 result ID 和报告；晚到响应被取消/忽略。非法厚度在前端阻止；后端验证失败时展示具体问题，设计画布保持可用。
- 真实浏览器：独立新版后端 `127.0.0.1:8766`、Vite `127.0.0.1:5174`，通过文件输入载入已实际打印的 `work/physical-validation-02/physical_validation_02_real_pattern.pattern.json`。一次制造请求，结果尺寸约 `57.22 × 19.90 × 2.00 mm`、独立组件 3、Mesh watertight；修改厚度后旧结果显示 stale，设计 revision 保持 0、返回设计仍显示 3 个元素，浏览器致命错误 0。证据：`work/p2_browser_smoke.cjs` 与 `work/p2-manufacturing-real-pattern.png`。
- 验证：Web 88/88 PASS、TypeScript/Vite build PASS、Python WM3/WM1 制造相关 13/13 PASS；无关 Python 全量回归未运行。提交后建立 `backup/p2-web-manufacturing-final`。安全回退点：`backup/web-parameter-range-audit-final`；通过新 worktree 检出，不执行强制 reset。

## Web 全局 Parameter Range Audit（2026-09-30）

- 状态：PASS。审计当前 Python 参数目录的 Layout（Free/Grid/Radial/Curve）、8 种可编辑 Field、Size/Rotation/Position Modifier 与 Element Transform，共 91 项定义；其中 82 项数值参数，81 项提供推荐滑杆范围。Shape Replacement 为选项控件，无数值滑杆；Image/Composite Field 仍为既有只读类型。
- Python Schema 为每项增加 `slider_min/slider_max/slider_step`，与原 `min/max/step` 分离；React 通用 ParameterPanel 读取 Schema。旧合同的数值控件改由同一通用渲染器兼容显示，元素变换在新版合同中也直接使用 Python Schema。未修改几何算法、文档格式或合法数值范围。
- 推荐范围：正向距离/宽度/周期为 0–300 或 1–300 mm，坐标/有向位移为 -300–300 mm；普通角度 -180–180°，放射起止角 0–360°；比例/强度 0–1，衰减 0.01–1；尺寸倍率 0–3；行列 1–100，数量 1–200，螺旋圈数 0–10，相位 -10–10，对比度 0.01–3。保留原有更宽的数字输入合法范围。
- 特例：随机种子仅显示整数输入，不提供不实用的大范围滑杆。超出推荐范围的旧值继续在数字框显示，滑杆仅停在边界并提示“超出推荐调节范围”；重置仍使用 Schema 默认值。
- 验证：Web 83/83 PASS；Python 参数合同定向 4/4 PASS；`npm run build` PASS。Web 既有单次提交/Undo 测试保持通过；本轮未运行无关 Python 全量回归。

## Web 滑杆常用范围调整（2026-09-30）

- 正向毫米参数的常用拖动范围为 1–300 mm；数字输入与 Python Schema 的合法 min/max 保持原值。已有值超出滑杆范围时，只将滑杆手柄显示在边界，数字框和 Document 保留真实值。坐标、角度、比例和计数范围不变。
- 滑杆移动仅改浏览器暂存值，释放时沿用原单次提交；定向参数控件测试 7/7 PASS，`npm run build` PASS。未修改 Field 算法或 Python 代码。

## Web P1-E — 参数化交互打磨（2026-09-30）

- 状态：PASS；基线 `e5c906c` / `backup/p1d-modifier-stack-final`，开发分支 `feature/p1e-parametric-interaction`。仅调整 Web 交互，Python 算法、合同和项目数据模型未修改；停止在 P1-E。
- Inspector 固定为 Layout → Field → Modifiers → Element，四区可折叠。移除 revision/evaluateStatus 作为整个 Inspector 的 React key，保留展开状态、控件实例和滚动位置；切换选中元素时展开 Element。
- 通用参数控件读取 Python Schema.default 提供数值/布尔/选项重置，不为各效果写默认值表。已应用参数重置、滑杆释放各走原单条 Undo / revision+1 / 单次 Evaluate；暂存布局仍遵守 P1-B 的“应用布局”边界，草稿恢复默认不会自行重新排列图案。原始元素尺寸/位置没有 Schema 默认值，故不伪造 Element Reset。
- `ParameterInteraction` 只保存浏览器数值草稿和 pending 状态，提交前不修改文档、不调用 Python。错误回滚或本地校验失败时在绘制前同步有效值；失败后可再次修改、重置、撤销，同值重试不会被旧 committedRef 忽略。底部显示 Ready / Editing / Evaluating / Error，旧几何在求值及失败期间保留。
- Ctrl+Z、Ctrl+Y、Ctrl+Shift+Z 复用原会话历史；不截获输入框或可编辑文本内的快捷键。求值成功后按 final ID 保留选择，已消失元素清除选择；窗口尺寸和 Evaluate 变化不会自动 Fit，导入或显式 Fit 才调整视角。
- 验证：Web 81/81 PASS；TypeScript/Vite build PASS；Python Schema/Field/Modifier 相关 8/8 PASS。按本轮限定范围未重复无关 Python 全量、固定图或 Tk 回归。
- 浏览器：独立 Edge 会话在 `http://127.0.0.1:5174` 加载真实 144 元素矩阵工程及实物打印三星工程；Field/Modifier 参数、真实鼠标滑杆（按下/移动零 Evaluate，松开一次）、Reset/Undo/Redo、启停、折叠、Zoom/Pan、选择保持和注入 422 后重试均 PASS；无非预期 Console error、无 favicon 404。截图及可复现脚本：`work/p1e-matrix-144.png`、`work/p1e-printed-pattern.png`、`work/p1e_browser_smoke.cjs`。模拟的 422 为错误恢复测试，不是产品失败。
- 性能观察：滑动阶段无后端请求、没有明显拖动停顿；单次 Evaluate 往返最大约 0.69～1.05 秒（144 元素）及 0.05～0.23 秒（三星），较慢一次与 build/test 同时运行。此为本机观测，不承诺固定 FPS 或服务延迟。
- 修改：App、InspectorControls、ParameterPanel、Workspace2D、样式、index.html 和对应测试；新增 InspectorSection、ParameterInteraction、favicon.svg、App.p1e.test.tsx。无文件删除、无新参数化算法。提交后建立 `backup/p1e-parametric-interaction-final`；安全回退参考 `git worktree add --detach ../PatternLab-P1D-Recovery backup/p1d-modifier-stack-final`（目标须不存在，运行环境另配）。

## Web P1-D — 效果堆栈接入（2026-09-30）

- 状态：PASS；仅接入现有 Python 效果算法，未进入 P1-E。Web 可在现有场图中新增、删除、启停尺寸/旋转效果层，绑定任一已有场，并通过 Python 参数 Schema 编辑其参数；现有有序堆栈增加位置/变形层及模式相关参数编辑。已有选中元素的形状替换入口归入效果区，仍使用原 Placement 替换数据，不伪装为新的有序算法层。
- 求值边界：场驱动尺寸/旋转层依 `PatternDocument.modifiers` 顺序执行，位置层依已有 `SharedModifierStack` 执行；两个既有阶段之间不支持跨组拖拽排序。React 只修改 DTO，最终几何由 Python Evaluate 生成；同一 Wave 场可同时绑定尺寸和旋转层。随机/占用未扩展。
- 编辑边界：新增、删除、启停、字段绑定、参数修改各提交一次，产生一条 Undo；滑杆移动只更新暂态值，松开才提交一次、修订号加一、Evaluate 一次。位置层首次启用保存原始元素快照，后续编辑不覆盖源数据。
- 验证：Web Vitest 77/77 PASS，TypeScript/Vite build PASS，Python 新增及 Schema 定向 5/5 PASS，完整 Python unittest 361/361 PASS（退出码 0），固定图 6/6 PASS，Tk smoke 2/2 PASS。真实 Edge 浏览器加载实物验证工程（3 元素），新增旋转/位置层、位置 X 滑杆 +10 mm、Undo 恢复均通过；滑动阶段零次 Evaluate，松开一次；致命浏览器错误 0。
- 已知非阻塞项：Vite 开发服务器请求缺失 `favicon.ico` 返回 404；完整 Python 回归仍可能打印 Tk `ThemeChanged` 销毁警告，但没有 `main thread is not in main loop` 或 `Tcl_AsyncDelete`，进程正常退出。详细入口与源码回退点以本 Gate 提交及 `backup/p1d-modifier-stack-final` 为准。

## P1-C 冻结复验（2026-09-30）

- 在进入 P1-D 前重新执行：Field/Schema 定向 6/6、Web 74/74、前端 build、完整 Python 359/359，均 PASS 且完整回归退出码 0；既有 `backup/p1c-field-system-final` 指向已修复 Tk 测试清理的稳定提交。未修改 P1-C Field 算法。

## Tk Variable 测试清理修复 / P1-C 最终验收（2026-09-30）

- 状态：PASS。P1-B 与 P1-C 在相同 Python、依赖、测试资产及完整命令下都可复现 Tk 销毁后的 `main thread is not in main loop` / `Tcl_AsyncDelete`，因此不是 P1-C Field 功能引入。
- 根因：若干 Tk 测试虽已销毁窗口，但 `tkinter.Variable` 仍留在循环引用中；后续 FastAPI `TestClient` 的工作线程触发垃圾回收时，变量析构错误地在非 Tk 主线程执行。
- 修复只涉及测试生命周期：Gate0、Modifier Scope、Multi-selection、Noise 四个 Tk 测试模块在 `tearDownModule` 阶段调用共用 `tests/tk_lifecycle.py`，明确只在主线程执行 `gc.collect()`。没有跳过测试、关闭 GC、吞掉 Tk 异常，也没有改产品 UI、参数化、PatternDocument 或 Web Field 代码。
- 已知五模块触发组合在最终代码上连续 3 次通过（各 20/20，退出码 0，两个致命错误均 0）；P1-C Field + 参数合同定向 6/6 PASS；完整 Python unittest 359/359 PASS，退出码 0、致命错误 0；固定图自检 6/6 PASS；Tk smoke 2/2 PASS。证据保存在 `work/tk_lifecycle_final_combo_{1,2,3}.log`、`work/tk_lifecycle_p1c_targeted.log`、`work/tk_lifecycle_full_final.log`、`work/tk_lifecycle_self_test.log`、`work/tk_lifecycle_tk_smoke.log`。
- P1-C 原功能提交为 `732c9ad`；本次独立提交后建立 `backup/p1c-field-system-final` 指向最终验收提交。完成后停止，不进入 P1-D。

## Web P1-C — 参数场编辑与现有效果层绑定（2026-09-30）

- 最终状态：PASS。下方 Tk 致命退出描述为修复前的历史阻塞记录；上方独立测试生命周期修复与完整回归已解除该阻塞。
- 范围：Web 复用 Python Parameter Definition Schema 展示、新建、编辑、启停和删除现有 SharedField；在已有尺寸/旋转效果层中可选择驱动场。React 不计算 Field，Canvas 使用 Python Evaluate 返回的几何。Composite 和 Image 保持只读且文档数据不丢；没有新增效果层或布局/Field 算法。
- 当前可新建：Constant、Linear（角度 0°/90° 对应 X/Y）、Ring、Wave、Stripe、Checker、Spiral、Noise。旧版 Radial/Attractor 仅属于遗留尺寸效果模式，不是独立 SharedField，故本轮未虚构该类型。未配置尺寸/旋转效果层的导入工程中，新建 Field 本身不会改变几何；效果层新增属于后续阶段。
- 验证：Web Vitest 74/74 PASS，TypeScript/Vite build PASS，Python 相关定向 78/78 PASS，固定六图 6/6 PASS。实际 Edge 浏览器加载 `work/physical-validation-02/physical_validation_02_real_pattern.pattern.json`：新增 Noise 场提交一次，滑杆移动零次请求、释放一次提交；将既有 Size 效果层从 Wave 绑定到 Noise 后，三元素宽度由 `[10,16,22]` 改为约 `[14.93,13.65,13.66]`；停用 Noise 后均恢复 16；浏览器致命错误 0。测试使用独立 8766 新源码后端，不停止现有 8765 服务。
- Python 完整 `unittest discover` 已尝试，但既有 Tk 对象销毁时持续报告 `main thread is not in main loop`，最终 `Tcl_AsyncDelete: async handler deleted by the wrong thread`，进程退出码 1。此问题在 P1-C 前的 P0/WM6.7 等记录中已有，不得将完整 Python 回归记为 PASS；本轮只确认受影响的 Field/Evaluate/Web 服务测试通过。停止在 P1-C，不进入 P1-D。

## Web P1-B — 非破坏性布局工作流（2026-09-29）

- 状态：PASS。P1-A 的真实浏览器 Schema 验收先通过；随后仅调整 Web 布局交互，Python PatternAnalyzer 和 Grid/Radial/Curve 算法未修改。
- 导入图片/无结构工程默认为 Free，保持原始位置；自动分析只显示推荐。左侧选择 Grid/Radial/Curve 时，由现有 Python `prepare-pattern` 返回独立提案；右侧复用 P1-A Generic ParameterPanel 暂存参数。仅点击“应用布局”才提交一次文档修订并求值一次；取消不修改文档。切回 Free 时复用既有 `bake`，不在 React 实现布局数学。
- Web 单测 72/72 PASS、TypeScript/Vite build PASS。实际 Edge 浏览器通过文件输入加载实物验证工程和 144 点 PNG：Free 默认显示，三种布局选择均不触发 Evaluate，应用各触发一次；暂存的 Grid 行数修改不提前提交，Free 应用另触发一次；浏览器无致命 Console 错误。全量 Python 回归不属于本轮范围，未运行。

## Web P0 — 固定设计工作区（2026-09-29）

- 状态：PASS。使用现有文件入口加载 `work/physical-validation-02/physical_validation_02_real_pattern.pattern.json` 完成真实 Web UI 验收；本轮仅补验证与记录，不改产品代码，不进入 P1。
- 仅调整 Web 样式：页面固定为视口高度，body/root 不整体滚动；左右栏独立纵向滚动，中央 Canvas 与底部模式栏留在固定工作区。旧版已把参数配置放入右侧 Inspector，当前没有大型参数化弹窗；本轮仅删除已无用途的旧弹窗样式，保留必要的毫米映射小弹窗。不修改参数化算法、文档或 Python Engine。
- Web 新增布局合同测试，Vitest 65/65 PASS，TypeScript/Vite build PASS，固定图自检 6/6 PASS。真实浏览器以 1440px 宽、768/900/1080 高视口检查：页面滚动量 0、Canvas 与模式栏位置稳定；768 高度下左栏 scrollHeight 953 > clientHeight 644，滚轮使左栏 scrollTop 从 0 增至约 309，body 保持 0；浏览器 error 日志为空。
- 最终 UI 验收：在 1440×768 浏览器视口中，该项目显示 3 个实心星形及 Grid、Wave Field、Size Modifier 控件；左栏 scrollTop 0→280.6、右栏 0→982.9，body 始终 0，顶栏 top=0、Canvas top=128、底部模式栏 top=696 均未移动。画布 Zoom 14.12→16.94 px/mm，空白区拖动使 SVG 平移量增加约 (40,30)px，元素仍为 3 个。右栏“最小输出”0.625→0.7 后 revision 0→1、元素仍为 3 个且无浏览器 error 日志。
- 最终回归：Web 受影响测试 18/18 PASS、TypeScript/Vite build PASS、Tk smoke 2/2 PASS。此前 Python 全量回归因 Tk Variable 析构异常持续输出而中断；该异常在本轮 P0 开始前已有记录，本轮未修改 Python 代码，也未将全量回归标为 PASS。

## Web 参数化体验对齐 Desktop（2026-09-29）

- 桌面 `try_parametric` 仅分析并暂存推荐；`convert_pending_grid` 显式转换推荐 family；`enter_free_parametric` 保留元素位置；`bake_to_free_elements` 物化后移除结构模型。Web 已按这四种语义拆开，不再通过点击 Grid/Radial/Curve/Free 调用手动排布。
- Web family 按钮只选择候选，当前结构另行显示；自动分析只提示推荐。新 `/api/v1/pattern-action` 薄路由复用桌面 `PatternLabSession` 的转换、Free、烘焙方法，不改 PatternAnalyzer 或参数化算法；旧 `/prepare-pattern` 保留兼容但本页不再触发。
- 定向 Python 14/14 PASS（包含真实 PNG 导入结果与桌面 Session 文档逐项相等、Grid/Radial/Curve、Free 保位、烘焙、失败拒绝）；Web Vitest 64/64 PASS；TypeScript/Vite build PASS；固定图自检 6/6 PASS。完整 Python 回归已启动，但 Tk 对象销毁报错连续输出、约 150 秒仍未收尾，已中断，不能标为 PASS；未执行桌面/Web 并排人工 GUI 测试。现有运行中 Web 服务未被强制停止，需更新服务进程才能使用新路由；当前不是新完整 LKG。

## WM6.7 — Recognition 与 Layout 分离、手动转换（2026-09-29）

- 基线 `ee07ab6`，保护引用 `backup/pre-wm6-7-recognition-layout`；未修改 PatternAnalyzer、Grid/Radial/Curve 参数化算法或其他产品功能。
- Recognition 只推荐：现有结构模型匹配时直接应用；未匹配时 Python 以既有参数化模型准备手动布局，先返回独立提案和只读预览。用户取消不改文档，确认后前端只提交一次并求值一次。
- Free 保留原位置并可在已加载文档中使用。Grid 手动参数为行列/间距/中心；Radial 为中心/半径/数量/角度偏移；Curve 为沿现有模型的直线初始路径、数量与元素尺寸。Radial Layout 不等于 Radial Field。
- 验证：Web Vitest 67/67 PASS、TypeScript/Vite build PASS、Python Web/导入定向 13/13 PASS、固定图自检 6/6 PASS。全量 Python 回归在持续输出 Tk 对象销毁异常时再次无法收尾，已中断，状态为未验证；没有人工浏览器验证。本提交不宣称为新的完整 LKG。

## WM6.6 — Web 图案结构可用性与推荐分离（2026-09-29）

- 基线 `8284a5c`，保护引用 `backup/pre-wm6-6-pattern-availability`；仅调整 Web 图案结构桥接和对应测试，不修改 PatternAnalyzer 算法或新增 family。
- 有有效可编辑几何时 Grid/Radial/Curve 可尝试应用；Free 对已求值的文档始终可用。Analyze 仅返回当前文档身份、推荐 family、置信度和 matched/no_match 状态，不再担任功能解锁器。
- 导入求值成功后立即分析；编辑提交、Undo/Redo 或结构应用后先标记 stale，再在求值成功后 400ms 防抖分析。过期请求被取消，stale/analyzing 不禁用结构按钮；无法拟合时由 Python apply 返回明确错误。
- 验证：Web Vitest 62/62 PASS，TypeScript/Vite build PASS；Python 相关定向 16/16 PASS（包括旧导入、多结构分析和新低置信度/空文档回归）；固定图案自检 6/6 PASS。全量 Python 回归曾启动，但在持续输出 Tk 对象清理异常后未能收尾，已中断，不能标记 PASS；未执行人工浏览器操作。

## WM5.6 — Web 编辑时元素可见性修复（2026-09-29）

- 范围仅 Web 编辑 Bug：直接拖动时由浏览器临时写入 SVG 位移，最终 Evaluate 可能在同一 React 批次返回，React 未观察到临时属性，导致旧位移残留、最终几何被二次平移甚至移出视野。现在在提交后的 layout 阶段显式协调该属性；求值成功/失败后都清理临时位移。
- Evaluate 响应在替换上一帧前拒绝非正几何尺寸与重复 final ID；数字输入的空白中间态不再把滑杆显示为 0。编辑请求加载中继续保留上一帧；失败继续保留上一帧并回滚项目。
- 验证记录见 `work/wm5-6/edit-visibility-report.md`；未修改 Python 几何算法、导入流程、Grid 或制造链。
- Web Vitest 51/51 PASS、TypeScript/Vite Build PASS、Python Full Regression 339/339 PASS、固定图 6/6、Tk Smoke 2/2。实际浏览器打开 144 元素工程，宽度 9→12mm 与直接拖动后始终显示 144 个实心元素，revision 各加一，拖动临时 transform 已清除。现有浏览器后台为未重启的旧 WM3 进程，不含 WM5.5 图片上传端点；新版源码的 PNG 导入及编辑经真实 Python TestClient 回归通过。

## WM5.5 增量 — Web 图片 / SVG 导入（2026-09-29）

- 从已通过的 WM6 代码基线增量实现，未回退 WM6；后端增加 `POST /api/v1/assets` 与 `POST /api/v1/import`，前端增加按钮与拖放入口。
- PNG/JPG 使用既有 BinaryThresholdImageProcessingAdapter、ImageToSVGVectorizationAdapter 与 FaithfulMappingAdapter；SVG 使用既有 SVGNormalizer。网页不包含矢量化或 SVG 解析算法。
- Alpha 临时资产仅在服务进程内保存；8 MiB、32 项、30 分钟 TTL；不向前端回传本机绝对路径。导入结果为真实 Element DTO，隐藏原图仍可求值。
- 未确认物理尺寸的图案以 1 原始单位 = 1 mm 临时显示并显著提示；不应将该值视为打印尺寸确认。
- 专项测试覆盖规则/渐变/星形点阵 PNG、JPG、带孔 SVG、无效类型/超限/丢失/过期资产、Evaluate；浏览器规则点阵 PNG 实际显示 144 个实心元素，浏览器 error 日志 0。前端 41/41、TypeScript build PASS；Python 完整回归 338/338、固定六图 6/6、Tk Smoke 2/2 PASS。

## WM6 — Web Parametric Controls MVP（2026-09-28）

- Status: PASS — 前端核心、真实打印工程浏览器导入与修改/撤销、回归测试均通过；144 点在自动化导入测试通过，尚未测量浏览器 FPS。
- 现有 PatternDocumentDTO 由 `web/src/document/editor.ts` 集中不可变编辑；右侧 Transform/Grid/Field/Modifier/Shape 控件不实现 Python Evaluate 算法。图像与组合场只读，未知/派生数据保留。
- 滑杆 pointermove 不提交；pointerup 一次 revision/Evaluate/Undo。Undo/Redo 各求值一次；失败保留上次有效画布并回滚文档/历史。窄屏检查器不再被隐藏。
- Web Vitest 38/38、TypeScript build PASS、Python Full Regression 335/335、Fixed Pattern 6/6、Tk Smoke 2/2 PASS。真实浏览器在线/Contract v1.0、小屏检查器可访问；实物打印三星工程导入后显示三颗实心黑星，参数改变第一颗的 path scale 10→14.4，Undo 恢复 10；浏览器捕获的 error 级控制台日志为空。未采集 FPS。详见 `docs/WEB_PARAMETRIC_WM6.md`。

## WM5 — Web 2D Viewer / Editor Foundation（2026-09-28）

- Status: PASS — 正式 PatternDocument JSON → WM2 DTO → WM3 Evaluate → SVG 最终二维几何。前端不实现 Python 的 Field、Modifier、Grid 或 Evaluate。
- 支持五种当前合同几何、evenodd 孔洞、毫米 World↔Screen 变换、Fit/Zoom/Pan、单选与检查器；自由源元素精确 ID/坐标映射才允许拖动。pointermove 不发请求，pointerup 一次 revision/求值；取消不提交。
- 真实浏览器验收：144 点项目显示 144 个黑色实心元素、可选可拖；打印三星项目显示三块实心 FilledRegion；方孔样例白色孔洞正确，缩放和平移可用，console error 0。144 点未测量稳定 FPS；不能据此声称大规模性能已达标。
- Frontend Vitest 25/25、TypeScript build PASS；Python Full Regression 335/335、Fixed Pattern 6/6、Tk Smoke 2/2 PASS。WM4 后端合同与桌面链路保持不变。
- 限制：本地路径资产不上传，ImageField 等依赖资产的视觉结果可能不完整；旧 SVG 单位要求用户输入毫米比例；网页尚无保存、Undo、参数面板、制造或 STL 下载。

## WM4 — React Web Shell（2026-09-28）

- Status: PASS — 独立 `web/` React 19 / TypeScript / Vite 8 前端；三栏布局、底部模式导航、禁用未实现入口。
- `web/src/api/client.ts` 统一调用 WM3 `/api/v1/health` 与 `/api/v1/contract`，校验 `schema_version=1.0`、`units=mm`；离线仍显示页面，合同不匹配明确报错。开发 URL 来自 `VITE_API_BASE_URL`。
- 浏览器 UI 状态独立于 PatternDocument：当前仅模式、侧栏/检查器开关及未来选择/缩放/平移的暂存字段；没有设计数据写回。
- Frontend tests 7/7、`npm run build` PASS（TypeScript 0 error）；本机 WM3 + Vite Browser Smoke：在线、Contract v1.0、三栏布局、模式切换正常，console error 0。Python Full Regression 335/335 PASS（255.820秒）、Fixed Pattern 6/6 PASS、Tk Smoke 2/2 PASS。
- 范围：无导入、2D 绘制/编辑、Undo、制造 UI、Three.js、STL 下载、数据库、登录或云；Tk 桌面版保持原样。

## WM3 — FastAPI Headless Server v1（2026-09-28）

- Status: PASS — WM3 专项8/8；WM3+WM2+WM1+M1/M2+T/U/U.5/V/W/X 联合92/92；最终 Full Regression 335/335（216.496秒）；Fixed Pattern 6/6；Tk Smoke 2/2。
- 真实打印类型经 TestClient Build 保持 57.2169×19.8992×2mm、3 组件与 Watertight；下载 STL 读回等价。测试进程内观测：打印 Build 约 14～16ms；Circle Build 约 11～195ms（首次运行/环境抖动）；Evaluate 约 2ms；STL 响应约 1～2ms。数据只代表小样、本机，不是生产性能承诺。
- 另以真实 Uvicorn 本机进程验证 `GET /health` 返回 200。当前 PowerShell 默认代理访问 localhost 返回 502；`curl.exe --noproxy '*'` 可正常连接。这是本机代理环境，不是 API 健康检查失败。
- HTTP Adapter 已接 WM2 Contract 与 WM1 ManufacturingService；端点为 Health、Contract、Evaluate、同步 Build、按结果 ID 下载同一份 Binary STL。Gate X `export_bytes()` 在同一最终 Mesh 上重复 Gate W 校验，不重新建模。
- Alpha Store 上限32项、TTL30分钟；服务器重启即失效。资产仅由服务器端 resolver 提供，默认不解析；无上传接口。请求体限制2 MiB，本机开发 CORS 白名单，统一中文 ErrorDTO。
- 运行 `python -m xiaomang_pattern_lab.web` 只绑定 127.0.0.1:8765；`/docs` 和 `/openapi.json` 可用。桌面依赖未强制引入 FastAPI；没有 React、GLB、数据库、队列、鉴权或公网安全保证。

## WM2 — Versioned Web Contract / DTO v1（2026-09-28）

- Status: PASS — WM2 专项10/10、WM2+WM1+M1/M2+T/U/U.5/V/W/X联合84/84、Full Regression 327/327 PASS（188.986秒）、Fixed Pattern 6/6、Tk Smoke 2/2 PASS。日志位于 `work/wm2-web-contract-v1/`。
- `xiaomang_pattern_lab.contracts` 定义唯一 `"1.0"` Web schema、Document/Evaluate/Manufacturing/Artifact/Error DTO、毫米 Bounds 和 Engine Report Mappers；没有 HTTP 或新持久设计模型。
- `PatternDocumentDTO.document` 复用正式 `PatternDocument.to_dict()/from_dict()` 与项目迁移入口；document ID/revision 属于传输层。参考图和 Image Field 路径使用显式 asset_id 绑定，避免本机路径泄露。
- `manufacturing_result_id` 由 canonical 文档状态、revision 和高度生成，Service snapshot 必须与响应文档匹配；响应不携带 Trimesh、Shapely 或 Tk 对象。
- 限制：资产上传/解析、真正 revision 存储与 HTTP 冲突、GLB、服务器缓存均属于后续 WM；Image Field 必须重新绑定真实资产才可重现取样。详见 `docs/WEB_CONTRACT_V1.md`。

## WM1 — Headless Application Service Extraction（2026-09-28）

- Status: PASS — 制造业务编排已从 Tk 窗口抽到 `xiaomang_pattern_lab.manufacturing_service.ManufacturingService`；依赖方向固定为 `Desktop UI / future API → Application Service → existing T/U/U.5/V/W/X engine`。
- Service：`build()`、`is_current()`、`export_stl()` 无 Tk、Canvas、Dialog、MessageBox 或预览依赖；`ManufacturingServiceResult` 提供既有报告、内部 Mesh、制造 Bounds、组件数和 warning。旧 `ManufacturingWorkflow` 名称仅作为同一类的兼容别名，不存在第二条制造链。
- Desktop：`ManufacturingDialog` 已改为调用 `ManufacturingService`；M2 `MeshPreviewDialog` 仍只消费 Service 返回的同一份 `ManufacturingMeshResult`，不进入 Service。
- Headless：Fresh Process 导入 Service 不加载 `tkinter`，也不加载废弃的 `ppg.xiaomang_pipeline`。工程保存/读取 → Build → Gate W → Binary STL → Reload 已在无 Tk 测试中通过。
- 真实图案：Grid + 3 star + WaveField + SizeModifier 保持 57.2169×19.8992×2mm、3 个组件、Watertight；STL 读回 Bounds、体积和组件等价；Document、source、revision、saved revision、Dirty 和 Undo 保持不变。
- 验证：WM1+M1+M2 定向21/21、T/U/U.5/V/W/X+WM1+M1+M2 联合74/74、Full Regression 317/317 PASS（179.662秒）、Fixed Pattern 6/6、Tk Smoke 2/2 PASS。日志位于 `work/wm1-headless-services/`。
- 范围：没有 FastAPI、REST、React、TypeScript、Three.js、GLB、数据库、云存储、用户系统或 Skill Orchestrator；不激活旧 PPG/Blender/legacy STL 制造路径。

## v0.2-M2 — Lightweight Manufacturing 3D Preview（2026-09-28）

- Status: PASS — 只读轻量预览消费 M1 已生成的同一份 `ManufacturingMeshResult`；没有读取 PatternDocument、重新建模、修复、Union、移动组件或介入 STL Pipeline。
- UI：制造检查通过后启用“3D 预览”；初始 45°/28° 斜视角，Z 向上，支持左键 Orbit、滚轮 Zoom、适合窗口与重置视角，并显示 XYZ 毫米尺寸和组件数。无有效 Mesh 时按钮禁用。
- Renderer：使用既有 NumPy + Pillow 的只读软件投影副本，未增加依赖；正式 Mesh 顶点/三角面不变，STL 始终直接读取原 `ManufacturingMeshResult`。20×10×2mm、贯穿孔和多组件均已视觉/数据验证。
- 状态：厚度或设计变化会将旧预览标记 stale；重新“检查并生成”会关闭旧窗口并以新制造 Mesh 打开。Orbit/Zoom/窗口尺寸变化不会重跑 Evaluate、制造适配、挤出或 Mesh 校验。
- 真实图案：Physical Validation 02 类型保持57.2169×19.8992×2mm和3个独立组件；预览前后 Binary STL SHA-256 一致。500圆/30,000面完整预览约135ms（800×600，本机观测），未降采样。
- 验证：M2专项10/10、M1+M2+T/U/U.5/V/W/X联合70/70、Full Regression 313/313 PASS（170.734秒）、Fixed Pattern 6/6、Tk Smoke 2/2 PASS。渲染图及日志位于 `work/v0.2-m2-3d-preview/`。
- 范围：没有3D编辑、实时参数化3D、材质、Boolean、Repair、3MF、壁厚、自动连接或M3制造风险分析。Windows Computer Use 原生应用接口在本会话不可用，因此真实鼠标视觉交互以 Tk 回调自动化加静态渲染人工检查覆盖，不声称完成外部GUI自动点击。

## v0.2-M1 — Integrated Manufacturing Workflow UI（2026-09-28）

- 基线：v0.1-alpha / bb76f299f29f09cf9a7e2b3bb3d9dbd244e5a90b；预备备份 `backup/pre-v0.2-m1`；开发分支 `feature/v0.2-m1-manufacturing-ui`。
- UI：顶部“制造”按钮打开独立窗口，提供2.0mm默认厚度、检查并生成、Geometry/Connectivity/Manufacturing/Mesh摘要、详情和导出 STL。状态同时使用符号和文字，不依赖颜色。
- 架构：`ManufacturingWorkflow` 仅编排现有 session 的 Gate T/U/U.5/V/W/X API。制造结果只驻留于窗口；设计或厚度变化使结果失效。UI未实现几何、网格或STL算法。
- 安全：无效厚度与 Gate T/W error 均阻止导出；多组件只警告；Gate X 导出前仍复验 Gate W。检查/生成/导出前后 PatternDocument、revision、saved_revision、Dirty、Undo 一致。
- 实物类型回归：Grid + 内置Star + WaveField + SizeModifier 通过真实 Tk 制造窗口导出；读回为57.2169×19.8992×2mm、watertight、3组件，与 Physical Validation 02 一致。
- 自动测试：新增7项核心/Tk测试；与T/U/U.5/V/W/X联合60/60 PASS；Full Regression 303/303 PASS（186.282秒）；Fixed Pattern 6/6 PASS；Tk Smoke 2/2 PASS（6.274秒）。日志位于 `work/v0.2-m1-manufacturing-ui/`。
- 明确未做：3D Viewer、OpenGL、相机、3MF、修复、Union、桥接、壁厚、新Field/Modifier和v0.2-M2。

## v0.1-alpha — Physical Manufacturing Validated Freeze（2026-09-23）

- 制造闭环：**PHYSICALLY VALIDATED** — Design → Parametric → Manufacturing2D → 3D Mesh → Validation → STL → Bambu Studio → Physical Print。
- 起始 HEAD / 产品代码：d1ed14ed6e92fcacffb4f660e0332a57a5936121；起始工作区干净；分支 feature/gate-x-stl。
- 本次仅更新 GATE_STATUS.md / ROADMAP.md / CHANGELOG.md / README.md。以下历史 Gate 的“尚未开始”均指当时状态，不覆盖本节当前结论。
- Physical Validation 01：20×10×2mm 校准块，Bambu Studio、Slice、Physical Print、Physical Dimensions 全部 PASS，证据来源为用户反馈。文件 work/gate-x-stl/gate_x_20x10x2_test.stl；SHA-256 `75c193b090b50283f3f96264c381968c44542b67fa851c811baa778390a6b77f`。
- Physical Validation 02：真实 Grid + 内置 star + WaveField + SizeModifier，3 个名义尺寸10/16/22mm星形；实物整体目标57.216907×19.899187×2mm。用户先确认导入/显示尺寸，再确认打印成型，并在冻结请求中确认切片和实物尺寸 PASS。未提供独立测量数值、照片、喷嘴/材料/打印参数，不声称代理完成实物测试。
- PV02 自动化：T error=0；U component=3、isolated=3（预期）；U.5 converted=3、skipped=0；V 60顶点/108面；W watertight、非流形/退化/边界边均0；X 5484字节 Binary STL、读回保持3组件及尺寸。项目保存/重开等价，source integrity PASS。
- PV02 文件：work/physical-validation-02/physical_validation_02_real_pattern.stl；SHA-256 `1d846c4bf8f8086862ae1efce578ef60fba5582043fbbea6ec84496ef062f7e3`。工程、SVG、完整逐项数据和日志位于同目录（本机工作产物，Git不包含）。
- 范围限制：验证限于两件样件；三星为独立试件，不是连通面料。尚无最小壁厚、自动修复/连接、3MF、集成3D预览、打印配置或生产Web UI保证。
- 冻结测试：T/U/U.5/V/W/X 53/53 PASS；Full Regression 296/296 PASS（189.199秒，无skip）；Fixed Pattern 6/6 PASS；Tk Smoke 2/2 PASS（6.716秒）。本轮日志：work/alpha-freeze/{targeted.log,full.stderr.log,self-test.log,tk.log}。
- 冻结引用：文档提交后创建 v0.1-alpha 标签与 backup/v0.1-alpha-physical-validated，二者必须指向同一最终冻结提交；创建前已确认同名引用不存在，禁止覆盖。使用 `git rev-parse 'v0.1-alpha^{commit}'` 获取最终提交。
- 安全回退（仓库根，新目录必须不存在）：`git worktree add --detach ../PatternLab-v0.1-alpha-recovery v0.1-alpha`。保留当前目录；运行时需重新配置。
- 完成冻结后 STOP，不进入 v0.2。

## Gate X — Validated Binary STL Export（2026-09-20）

- Status: PASS — 完成后停止。仅完成 Gate W 通过 Mesh 的 Binary STL 序列化与读回验证；未进入 3MF、自动修复、3D Viewer、连接器、壁厚、打印机配置或新的制造算法。
- 数据流：`ManufacturingMeshResult → MeshValidator → error 阻止 / warning 允许 → STLExporter → Binary STL`。任何 Gate W error 会在创建目标文件前抛出 `STLExportBlockedError`；多个独立组件仅写入 `multiple_disconnected_components` warning，不会自动桥接或合并。
- 单位与写入：STL 无单位元数据；本项目将顶点数值原样以毫米解释，报告中固定 `units_assumption="mm"`，不执行 mm/m/inch/pixel 缩放。默认拒绝覆盖已有文件；只有显式 `overwrite=True` 才可替换。Binary STL 通过 Trimesh 序列化，原 Mesh 不被修改。
- 读回：STL 原生不保存共享顶点索引；读回验证仅对新加载副本以完全相同的坐标重建索引，从而让 Gate W 正确检测文件拓扑。这不改变 STL 字节、不修改源 Mesh，也不是 tolerance merge 或自动修复。
- 验证：Gate X 专项 6/6 PASS；与 Gate T/U/U.5/V/W 联合 53/53 PASS；完整 unittest 296/296 PASS（236.914 秒）；固定图自检 6/6 PASS；真实 Tk 冒烟 2/2 PASS。Rectangle 20×10×2mm、贯穿 Hole、多组件、无效 Mesh 阻止、只读/覆盖策略与真实 Pattern Lab 全链路均已覆盖。日志：`work/gate-x-stl/`。
- 手工切片文件：`work/gate-x-stl/gate_x_20x10x2_test.stl`，Binary STL 684 bytes，读回 Bounds 为 `(0,0,0)..(20,10,2)`。尚未在 Bambu Studio / OrcaSlicer GUI 中实际切片；需用户手工确认尺寸、Hole 和 Slice 结果。

## Gate W-Core — Minimum Manufacturing Mesh Validation（2026-09-20）

- Status: PASS — 完成后停止。只读取 Gate V 的 `ManufacturingMeshResult / Mesh` 并生成 `MeshValidationReport`；不进入 STL/3MF、自动修复、3D Viewer、连接器、壁厚或打印机配置。
- 数据流：`Manufacturing2DGeometry → ManufacturingBackend → ManufacturingMeshResult → MeshValidator → MeshValidationReport`。`MeshValidator` 不读取 PatternDocument、Element、Grid、Field、Modifier、Canvas 或 SVG，不会调用任何 Trimesh repair/process API。
- 检查：有限坐标、拓扑 Watertight、boundary edge、non-manifold edge、显式 mm² 面积阈值（默认 `1e-12`）的退化三角面，以及按共享面边统计的 Mesh 拓扑组件。多组件是 warning/事实，绝不默认认定错误；它与 Gate U 的二维 touch/overlap 结论不同。
- 验证：Gate W 专项 9/9 PASS；与 Gate T/U/U.5/V 联合 47/47 PASS；完整 unittest 290/290 PASS（181.661 秒）；固定图自检 6/6 PASS；真实 Tk 冒烟 2/2 PASS。500 个独立圆的真实挤出 Mesh 为 16,000 顶点 / 30,000 面 / 500 个拓扑组件，验证约 599.593ms；没有发生 Mesh、PatternDocument、Undo 或 dirty 修改。日志：`work/gate-w-core/full-regression-final.stderr.log`、`self-test-final.log`、`tk-smoke-final.log`、`performance-500-elements.log`。

## Gate V-MVP — Minimum Manufacturing Extrusion Backend（2026-09-20）

- Status: PASS — 完成后停止。仅建立 `Manufacturing2DGeometry → ManufacturingBackend → derived Mesh`；尚未引入 STL/3MF、3D Viewer、全局 Union/修复/桥接或制造检查 Gate W。
- 后端边界：新增 `ManufacturingBackend` 抽象与本地 `TrimeshBackend`。后端只接受毫米单位的 `Manufacturing2DGeometry`，不会读取 Element、Canvas、UI、Field、Grid、项目状态或 SVG；`PatternLabSession.build_manufacturing_mesh()` 先复用 U.5 的只读转换，再交给后端。
- Mesh 结果：`ManufacturingMeshResult` 返回 Mesh、XYZ Bounds、顶点数、面数、组件数、高度、后端名、封闭状态与 warning；XY 原样保持 mm，Z 固定为 `0..height_mm`。默认高度为 2mm；零、负数、NaN 与 Infinity 会被拒绝。
- 三角化：使用 Shapely Polygon（含 holes）和 `trimesh.creation.extrude_polygon(..., engine="earcut")`；`trimesh`、`shapely`、`mapbox-earcut` 为 Gate V 可替换后端的实现依赖。孔洞贯穿整个高度；多个 Polygon 分别挤出、不会桥接或 Boolean Union；相接边界也不被本 Gate 静默合并。
- 安全限制：U.5 对嵌套且不是 `evenodd` 的非零填充环明确以 `ambiguous_nonzero_fill` 跳过，绝不猜测孔洞语义。没有可挤出面积几何、非 mm 输入或无效 Polygon 会给出明确错误。
- Packaging：规格文件已声明 Gate V 的运行时依赖，但本 Gate 不重新构建或验证 EXE；须在 Gate V 所有回归完成后再决定是否进行新的 PACK 验证。
- 验证：Gate V 专项 9/9 PASS；与 Gate T/U/U.5 专项合计 38/38 PASS；完整 unittest 281/281 PASS（176.084 秒）；固定图自检 6/6 PASS；真实 Tk 冒烟 2/2 PASS。日志：`work/gate-v-mvp/full-regression-final.stderr.log`、`self-test-final.log`、`tk-smoke-final.log`。

## Gate U.5 — Manufacturing Geometry Adapter（2026-09-19）

- Status: PASS — 历史 Gate 完成后停止；其后 Gate V 已通过，W / X 仍未开始。
- 数据流：`PatternDocument → existing evaluate pipeline → Final Geometry → ManufacturingGeometryAdapter → Manufacturing2DGeometry`。制造几何是临时 Derived Data；不保存、不烘焙、不修改 `PatternDocument`、`source_elements`、Final Geometry、dirty、Undo 或 SVG。
- 模型：`Manufacturing2DGeometry(units="mm", polygons, bounds)` 由 `ManufacturingPolygon(source_element_id, outer, holes)` 构成，并配套 `ManufacturingConversionReport` / `ManufacturingSkip`；后续 3D 后端只应消费此模型，不应回读 Grid、Field、Canvas 或 UI 状态。
- 单位与近似：只输出毫米；Canvas 为 `mm` 或有 `mm_per_unit` 时按世界坐标转换，缺失映射时明确跳过且不猜测尺寸。Circle/Ellipse 用统一 `curve_tolerance_mm=0.05` 的自适应折线近似（包含基准方向点以保持轴向切线接触）；闭合 Path 复用同一曲线采样尺度。
- 面积与孔洞：支持 Circle、Ellipse、Rect、FilledRegion、明确闭合的填充 Path、replacement shape 与多子路径；`fill-rule=evenodd` 保留 Outer Contour + Holes。没有明确面积语义的开放 Line/Path 以 `unsupported_open_geometry` 跳过，绝不猜线宽。Gate T 无效几何以 `skipped_invalid` 跳过。
- Gate U 拓扑保护：转换后以空间哈希候选筛选比较最终设计几何和制造几何的连接关系；切线圆、接触矩形/替换形状若因近似导致连通变化，会在 `topology_changed_element_ids` 与 warning 中明确报告，不会静默继续。500 个彼此分离圆的转换实测约 0.0405 秒。
- 验证：Gate U.5 专项现为 12/12 PASS（新增歧义 nonzero 嵌套环明确跳过）；Gate V 联合 T/U/U.5 专项 38/38 PASS，完整 unittest 281/281 PASS；固定图自检 6/6 PASS；真实 Tk 冒烟 2/2 PASS。日志：`work/gate-v-mvp/full-regression-final.stderr.log`、`self-test-final.log`、`tk-smoke-final.log`。
- 明确延后：make_valid、global union、自动闭合/桥接、孤岛删除、Hole repair、Extrude、Mesh、STL/3MF、3D Viewer。

## Gate U-Core — Connected Components + Isolated Elements（2026-09-19）

- Status: PASS — 历史 Gate 完成后停止；其后 U.5 与 V 已通过，W / X 仍未开始。
- 数据流：`PatternDocument → existing evaluate pipeline → Final Geometry → ConnectivityAnalyzer → ConnectivityReport`。结果为派生分析数据，不保存到项目，不会改变 `PatternDocument`、`source_elements`、Final Geometry、Modifier、Grid、形状分配、dirty 或 Undo。
- 连接定义：仅最终实心几何实际重叠或边界接触（`distance <= epsilon`）时建立 Edge；有正间距的临近图元仍是断开状态。隐藏/Occupancy 排除的元素不参与分析。
- 算法：局部最终几何查询适配为多边形；空间哈希先筛选可能相交的 Bounds，随后以边界相交/接触及包含进行精确判断，最后以并查集生成 Connected Components。报告包含组件、孤立 Element、最大组件尺寸、候选/实际连接对数量与跳过无效数量。
- Gate T 兼容：任何严重无效最终几何会跳过并计入 `skipped_invalid_count`，不会伪造连接关系或阻断其余有效元素分析。
- 验证：Gate U 专项 8/8 PASS（分离、重叠、相切、三连一孤立、100 元素连通链、无效跳过、最终 Grid 只读、形状替换后 FilledRegion）；与 Gate T 专项合计 17/17 PASS；完整 unittest 260/260 PASS；固定图自检 6/6 PASS；真实 Tk 冒烟 2/2 PASS。日志：`work/gate-u-core/full-regression.stderr.log`、`self-test-final.log`、`tk-smoke-final.stderr.log`。
- 明确延后：Near Connection、Gap Distance、邻居统计、连接强度、PatternGraph 可视化、自动 Connector/桥接、ManufacturingGeometryAdapter、3D、STL。

## Gate T-Core — Minimum 2D Manufacturing Geometry Validation（2026-09-19）

- Status: PASS — 历史 Gate 完成后停止；其后 U、U.5 与 V 已通过，W / X 仍未开始。
- 数据流：`PatternDocument → existing evaluate pipeline → Final Geometry → GeometryValidator → GeometryValidationReport`。校验始终读取 Evaluate 产生的瞬态最终元素；不烘焙、不修复、不写回 `PatternDocument`、`source_elements`、Modifier 或 Undo 历史。
- 检查范围：跳过隐藏元素；检查 NaN/Infinity 与非法几何、epsilon 退化尺寸/面积/开放线长度、实心区域的显式闭合轮廓，以及闭合 FilledRegion / Filled Path 的自相交。合法开放线只检查退化，不会因未闭合被误报。
- 报告：`GeometryValidationIssue(issue_type, severity, element_id, message, bounds, metadata)` 与 `GeometryValidationReport(checked_count, valid_count, warning_count, error_count, issues)`；当前 Gate 只产生安全的 `error`，为后续制造 UI 预留 `warning`。
- 验证：Gate T 定向 9/9 PASS（普通/退化圆、非法坐标、普通/未闭合/近零面积 FilledRegion、Bow-tie 自交、开放线及参数化网格的只读验证）；完整 unittest 252/252 PASS；固定图自检 6/6 PASS；真实 Tk 冒烟 2/2 PASS。日志：`work/gate-t-core/full-regression.stderr.log`、`self-test-final.log`、`tk-smoke-final.log`。
- 明确延后：元素重叠、重复件、最小壁厚、最小孔、连接性 PatternGraph、自动修复、2D→3D、STL 和任何新 UI。

## Gate S — Project Workflow Completion（2026-09-19）

- Status: PASS — 历史 Gate 完成后停止；其后 T、U、U.5 与 V 已通过，W / X 仍未开始。
- 项目会话：既有 `PatternLabSession` 扩展 `current_project_path`、派生名称、单调 `revision` 与 `saved_revision`；`PatternDocument` 仍是唯一设计数据模型。选择、缩放、平移不写 dirty；Undo/Redo 回到保存 revision 会准确清除 dirty。
- 文件流程：文件菜单/快捷键支持新建、打开、最近项目（最多 10 条）、保存、另存为、重新定位参考图片和退出。新建、打开、导入替换、关闭使用同一保存/不保存/取消判断；打开先读取、迁移、验证和重建候选，失败不替换当前设计。
- 持久化：`storage.atomic_write_json` 在目标同目录写唯一临时文件，flush/fsync、回读及 PatternDocument 验证后才 `os.replace`。集中 `migrate_pattern_payload` 为 schema 1 的旧文件补可选默认值，拒绝未知未来版本，不无故升级格式。
- 恢复：最近项目和恢复副本使用 `ppg.runtime_paths.user_data_root()` 下的 `projects/`，不写源码或 EXE `_internal`。真实修改停止 2 秒后写独立恢复副本，永不覆盖正式文件；异常退出后可恢复/放弃，正常退出清理本实例副本。多实例/工作区隔离，运行中的实例不会被误提示恢复。
- 参考图片：路径丢失时仍载入并显示矢量 Geometry，提示重新定位；ImageField 保持中性值安全降级。项目与 Preset 存储严格隔离。
- 验证：Gate S 专项 27/27 PASS（含真实 Tk 回调、保存错误注入、异常子进程恢复）；完整 unittest 243/243 PASS；固定图自检 6/6 PASS。日志：`work/gate-s-project-workflow/targeted-final.log`、`full-regression-final.log`、`self-test-final.log`。
- 基线：`2df02e3` / `backup/gate-r-final`；Gate S 的最新提交与稳定备份均位于 `backup/gate-s-final`。

## Gate R — Field Combine / 组合共享参数场（2026-09-16）

- Status: PASS
- 数据模型：`CompositeField(id, input_a_field_id, input_b_field_id, operator, mix)` 通过既有 `FieldRegistry` 与 `SharedFieldEngine` 递归求值；支持 Add、Multiply、Min、Max、Blend，输出统一钳制为 `0..1`。
- 安全性：结构 DFS 拒绝自身与间接循环；被组合场依赖的输入不允许删除；丢失输入以中性 `0.5` 安全降级，避免坏预设/工程阻断载入。
- UI：左侧单一滚动参数页新增中文“组合场”，可将当前尺寸场加入输入列表、选择输入 A/B、相加/相乘/最小/最大/混合与 Blend Slider + Entry；写入唯一 `PatternDocument.fields/modifiers` 图，不创建第二套 Engine 或 Geometry。
- 持久化：Project、Preset 和 SVG 都继续通过唯一 Evaluate 管线；Preset 保留完整 Field ID 图，应用后不会将组合场输入错误重映射。
- 验证：Gate R 定向 6/6 PASS；完整 unittest 216/216 PASS；固定图 self-test 6/6 PASS。日志：`work/gate-r-field-combine/full-regression-final2.log`、`work/gate-r-field-combine/self-test-final2.log`。

Gate S/T/U/V 尚未开始。Gate U 在制造路线中指真正的二维几何 Connectivity PatternGraph（nodes/edges/components），不等同于现有 SharedField 图。

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
