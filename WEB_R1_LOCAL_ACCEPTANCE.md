# Web-R1 本地稳定性核验（2026-10-13）

## 本地收口：用户试用确认（2026-10-13）

用户已明确确认Web-R1四项实际操作正常：二维视角往返、保存状态、制造结果失效提示、导出尺寸说明，记录为**用户本地试用PASS**。这不是独立浏览器自动化证据；下文真实桌面/500px/390px等独立验收缺口、历史预览失败/超时与其他OPEN继续保留，不用用户确认抹掉当时BLOCKED记录。公网持续429的占槽任务和根因仍为**UNKNOWN**，诊断日志不是最终修复证据。

本轮只按发布前审核批准的24文件收口：10实现、12测试、2记录；仅补这两份验收记录，不修改算法、Validator、任务槽并发或超时，不重跑历史全量。32个历史tools及全部运行产物保留，禁止纳入本次提交。用户仅授权本地提交和新备份，未授权推送、部署或重启Render。

基线与当前 HEAD：`c9ff2ce9239c27eda4c02c6e3b513c03894dfa2a`，分支 `feature/pattern-library-reuse`。
开工 tracked / index 空，32个历史 tools 未跟踪文件均保留。源码保护副本与本轮日志在忽略的 `work/web-r1-20261013/`；不是新的 Git 稳定备份。没有提交、建分支、推送、部署、依赖或环境配置修改。

## 已实现与定向证据

1. LIVE 01：App 条件卸载 Workspace2D 后，组件局部 `lastFitToken` 回到 null，同一 token 被再次 Fit。修复前测试输入 zoom=28.15、pan=(-123,47)，1200/500/390模拟画布重挂载均错误调用 Fit（默认800×600导致12.6）。这不是用户报告41.32的真实浏览器复现。修复由 App 保存已消费的 fit 请求，仍只保留一份父级 view；首次 Fit 优先取实际容器尺寸。重挂载不 Fit，新作品请求 token 与主动 Fit 仍生效。`Workspace2D.view.test.tsx`三视口、`App.webR1.test.tsx`缩放/平移/模式往返/零额外Evaluate通过。坐标函数与几何未改。
2. 候选同输入失败：原 hook `state.key === key`阻止再次计算，且没有显式重试。新增仅失败时可用的 Retry，保留原单活跃请求、最新输入合并、最后有效画面与正式结果隔离。hook故障注入和App真实格式429响应模拟确认第二次请求DTO完全相同；同帧两次Retry只发一份新请求。正式草稿、revision、Undo不变，失败时Apply禁用，取消恢复。没有假定浏览器取消等于服务器结束。
3. 保存：根据实际保存状态和待应用状态显示“正式作品已保存 · 有未应用预览”，另区分保存中/失败/更新。App测试覆盖已保存＋候选失败、Cancel与存储失败；原未应用Layout恢复测试保留，预期文案更新。不增加未应用快捷表单或Undo持久化；刷新仍开始新历史。
4. 制造结果：标准结果仍按原hook只暴露有效文件结果；失效时标注上次/当前正式revision。Fabric已保留报告的旧组件数与XYZ直接标注“上次结果 · 已失效”，与有效STL尺寸区分。只增加展示，不改缓存、校验或下载判断。测试覆盖提交后旧报告、迟到响应、新请求、候选未应用但正式revision不变时不误标失效且下载禁用。
5. 尺寸：共用只读 `OutputDimensions` 显示已应用画板mm、权威二维XY最小/最大与占用尺寸、PNG宽高像素及原裁切规则。正式二维计算未完成不把旧bounds当当前数据。非正方形60×40mm、非零原点、2mm/px、1200×800px测试通过；没有制造结果时不捏造STL XYZ。STL仍使用原有效报告，不按画板裁切。

## 历史3项预览失败：逐项状态

完整suite前缀：`P3 preview and STL remain tied to the current build`，文件 `web/src/App.p3.test.tsx`。原只读基线日志 `work/p4b-two-column-20261012/baseline-p3-results.json`；本轮完整错误/调用栈在 `history-before.json`。

| 原case title | 本轮结果 | 证据与处置 |
|---|---|---|
| sends a premature preview visit to manufacturing without starting a build | FAIL | 在:70查询已移除的“去检查并生成”；当前默认原图形状走Fabric中央设计预览，不显示旧空白普通预览导航。过时UI期望，未删除断言、恢复旧导航或改产品凑绿。 |
| enables preview/download after build without touching revision, then disables both when stale | FAIL | 在:98期待自动普通`ThreePreview`/“三维模型预览”，mock仅替换旧普通组件；当前默认原图预览使用FabricThreePreview。旧三步工作区与自动预览期望不匹配，独立测试债保留。 |
| shows download failure inline without clearing the design | 本轮未复现（PASS） | 实际404下载错误与返回二维断言通过。历史曾有多alert期望问题；一次未复现不宣布其所有场景已关闭。 |

## 历史5项P1/P2超时

原GATE只记录“两文件7/12 PASS、5 FAIL”，没有保存可逐项关联的5个完整case ID。现存 `preset-isolated.json` 实为8个SKIP，不能当失败列表或PASS。**原5项逐项映射均为UNKNOWN，不能声称全部历史根因已关闭。** 本轮运行这两个原模块的12个用例作为最小相关依赖，报告完整名称/调用栈。

本轮隔离复现4项超时：

- `pattern presets share the protected project and candidate workflow 精密错列 can become custom and still return the exact original, including pending layout, after refresh`
- 同suite：`光谱渐隐 can become custom and still return the exact original, including pending layout, after refresh`
- 同suite：`斜向潮汐 can become custom and still return the exact original, including pending layout, after refresh`
- `P2 cards use one candidate/history and protected-return pipeline coral-grains edits, cancels, applies once, restores and returns the exact original`

失败位置分别为 `App.patternPresets.test.tsx:89` / `App.patternPresetsP2.test.tsx:43` 等待Apply可用。本轮初批只出现前两项，隔离另批出现4项，具有调度敏感性，不称稳定产品故障。

只读内存诊断（不注入产品）记录候选key前缀、完整专用Field、请求顺序与200 mock响应、pending/error/result与生命周期。光谱例：原作品Evaluate#1 → 未应用Layout候选#2 → 新预设正式Evaluate#3 → 尺寸候选计时。全页role查询单次22–200ms，计时180ms实际可延后至761ms；测试期限包含创建/渲染阶段，最后候选timer在执行前被超时清理，状态为current=true、pending=true、error=null、result=false，而非几何失败或服务器429。

最小测试修正仅将Apply查询限定到真实“待应用效果操作”栏的 `within(...).getByRole`。仍是同一按钮、同一toBeEnabled断言、同一timeout、同一完整Apply/Cancel/Undo/Redo/保存流程；没有跳过、删断言、加timeout或换假返回。只读对照 `trace-scoped.log` 同一光谱例通过；最终两个模块12/12通过。该结论仅关闭本轮已复现的测试查询/调度问题，原5项的缺失case证据仍OPEN。

详细证据：`history-before.json`、`presets-diagnosis.json`、`trace-spectrum.log`、`trace-timers.log`、`trace-query-cost.log`、`trace-scoped.log`。两个诊断配置启动错误（导入路径/重复导入）保留在探查日志，不算产品测试结果。修复前新增Retry测试失败遗留的一次mock返回导致另一条fake-timer测试级联失败，不冒充额外产品缺陷；新增mockReset隔离测试，未改变断言。

## 定向批次（不相加冒充全量）

- 修复前新增复现：`repro-before.json` 3/8 PASS，3个重挂载失败＋无Retry失败＋上述mock级联失败。
- 第一处修复后：`repro-after.json` 8/8 PASS。
- 历史原模块初批：`history-before.json` 13/17 PASS，4 FAIL；没有修改旧App.p3断言。
- P1/P2隔离诊断：`presets-diagnosis.json` 8/12 PASS，4 FAIL。
- 最终主批：`targeted.json` 8文件37/37 PASS：App.webR1、OutputDimensions、Workspace2D.view、useLayoutPreview、FabricFusionPanel、P1/P2预设、App.p2c。
- 保护回归另批：`protection-regression.json` 6文件36/36 PASS：App.wm65、App.p1e、App.phase1a、StlExportButton、Workspace2D.wm56、App.draft。
- 最后仅新增测试隔离/候选保护断言补跑：`final-changed-tests.json` 16/18 PASS、2个beforeEach清理回调超时。新增beforeEach误将mockReset返回的Mock函数交给框架作为清理函数执行；改为明确无返回的代码块，不改产品/断言/timeout。`final-changed-tests-fixed.json` 同3文件18/18 PASS；两个批次与主批重叠，不相加，失败日志保留。
- `D:/npm.cmd run build` PASS，`build.log`。已有大bundle警告、Git LF/CRLF警告保留；未改依赖/构建配置/制造核心/Validator。没有运行Tk全量。

## 真实浏览器与未完成项

浏览器inventory显示原本地8806/8807/8808已“无法访问此站点”，当前公网仍c9稳定代码；未动公网草稿、参数或部署。定向绑定现有IAB tab 7（公网）再次30秒超时并重置kernel，已停止重复控制。

- 真实桌面、500px、390px缩放/平移/往返/主动Fit/刷新/返回原作：**BLOCKED**；组件模拟不是截图或鼠标证据。
- 原视角不持久化进草稿，刷新恢复/返回不同作品沿用合法首次Fit边界；本轮未新增存储格式或宣称刷新还原上次zoom。
- 真实界面保存、重试、尺寸说明、旧制造统计的显示与遮挡：**BLOCKED**。
- 本轮真实普通/Fabric制造、重新生成、下载及独立STL读回：**NOT TESTED**。上述制造/下载模拟测试不能代替文件验收，也没有拿历史文件或公网API200充数。
- 多标签草稿风险、完整项目导入导出等排除项未实施；参考路线图未取得文件正文，只依据本轮明确需求工作。
- 其余历史OPEN、Arc/Skew/通用曲线/自动毫米映射/历史迁移、切片/实物边界不变。不声明Web-R1全项PASS或可上线。STOP等待本地试用与浏览器验收。

## HTTP 429 三维阻塞补充（2026-10-13，本地受控验收）

### 定位与边界

- 实际HEAD/分支不变，开工保留前批17个正式改动，暂存区空、32历史tools不变。本轮没有恢复旧补丁或修改Render配置/服务。公网只读`GET https://zmg68-1.onrender.com/api/v1/health`为200，`backend_commit=c9ff2ce9239c27eda4c02c6e3b513c03894dfa2a`、`environment=staging`，能力含预检、最终网格和测试STL导出；未对公网发送制造请求。health不是槽空闲证据。
- 未取得可读取的Render运行日志连接，不能记录实际线上任务ID、占槽接口、开始时间、持续时间或是否仍在计算，全部UNKNOWN。仅凭用户429不能确定死锁。没有新增日志系统或公开内部进程信息。本地受控结论不等于部署修复或线上恢复。
- `xiaomang_pattern_lab/web/app.py:create_app`的`BoundedSemaphore(1)`由普通`manufacturing_build`、`fabric_design_preview`、`fabric_candidate`、`fabric_fusion`共用。非阻塞申请失败返回根级`code=staging_busy`的429。四入口均在`finally`释放，正常返回、验证错误及未捕获异常都覆盖；本轮没有改后端生产代码。Fabric STL下载和轻量Evaluate/health不占此槽。
- 实际线程池依赖`run_in_threadpool -> anyio.to_thread.run_sync`默认不abandon，计算完成前不因UI取消释放槽。当前同步线程/原生布尔计算没有安全强杀机制；真正无法结束的计算需要先取得日志，再另批评估进程隔离/终止，不能先清锁、提高并发或加超时伪装恢复。
- `computeRequests.ts:coordinateComputeRequests`已有App级共享token、同帧防重、取消等待后仍排空HTTP请求、finally与token匹配释放；本轮不改此实现。`canEditDocument/openExample/onFile/importAsset`不依赖3D computeBusy；轻量求值与本地草稿不被该锁无差别禁用。后端总CPU/线程池容量仍可能影响速度，不承诺忙碌时无延迟。

### 已复现第一处产品缺口与最小修复

默认原图形状（未显式base）的自动preview首次429后，`useFabricPreview`同key的error状态不自动重试，本来是防循环保护。但`ManufacturingPanel`更新按钮条件`base || !actionHost`排除了该默认模式，中央也没有Retry；App标题与空画面重复显示同条错误，容易表现成永久等待。没有证据表明该前端缺口就是线上长任务根因。

- `useFabricPreview.ts`只增加真实`HttpRequestError.code`保留、`serverBusy`及本页任务排空等待标记；不改单活跃/最新输入合并/最后有效画面/文档ID与序号隔离。网络失败不是几何失败，没有虚构failure_id。
- `App.tsx`中央加入当前输入“重试3D预览”，遵守computeBusy、未提交输入及hook入口双重校验；服务器仍忙则再次诚实提示，不自动重试。不触发融合、正式提交或STL生成。当前作品没有图像时可返回设计；A→B不保留A画面。
- 中央标题简短区分等待本页任务、正在生成、服务器忙碌、预览失败、旧预览失效；详细错误只显示一次。`ManufacturingPanel.tsx`在统一中央错误区已挂载时不再重复raw preview错误；独立无actionHost组件仍保留错误。最终制造的既有building/staging_busy/失败/失效/重新生成与导出保护不变。

### 定向证据与实际结果

目录`work/web-r1-429-20261013/`为ignored测试日志，不纳入Git，不是稳定备份。没有新探查脚本。

- 新增修复前：`repro-before.json`实际执行2项均FAIL、19项筛选SKIP（不是21项失败）；缺Retry按钮及缺业务码状态。修复后`repro-after.json`同2项PASS。hook中将旧beforeEach的mockReset返回值改为无返回代码块，仅测试清理语义，不加timeout或删断言。
- 最终命令：`D:/node.exe node_modules/vitest/vitest.mjs run src/App.phase1a.test.tsx src/manufacturing/useFabricPreview.test.tsx src/manufacturing/computeRequests.test.ts src/App.webR1.test.tsx src/manufacturing/FabricFusionPanel.test.tsx --maxWorkers=1 --reporter=json --outputFile=../work/web-r1-429-20261013/final-ui.json`，5文件40/40 PASS。先前hook/协调器11/11与该批重叠，不相加。
- App受控A→B：A开始fusion，B文件可打开、正式Evaluate及高度编辑可提交、draft save执行；未显示A画面，计算按钮持续禁用直到A响应排空；A迟到429被丢弃，随后只有一份最新B预览，按钮恢复。请求记录为A预览1、A融合1、B最新预览1；不以mock Renderer当真实WebGL。相同输入Retry双击仅额外1次preview，正式文档对象、revision及Undo不变；现有双击/跨入口、失败恢复/取消保护保持。
- hook受控A→B连续revision1/2/3：A排空前不请求B，A响应不展示；排空后仅B revision3请求，未积压中间输入。协调器测试保持HTTP错误/网络错误finally释放、旧任务不错误清除新锁，下载/健康/二维请求不受3D锁阻塞。
- Python命令：`xiaomang_pattern_lab/.venv/Scripts/python.exe -m unittest tests.test_web_staging tests.test_web_server_wm3.WebServerWM3Tests.test_build_download_and_stl_reload_reuse_one_result -v`，4/4 PASS，`backend.log`。正常A执行期间另四冲突入口429、B Evaluate200；A完成后实际B制造200。异常测试对4入口分别使用事件保持任务运行，期间新制造429，释放测试事件后抛RuntimeError、返回500，再由真实B制造200。日志的4份500栈是故障注入，不是线上异常。新增B Evaluate初次测试遗漏schema_version返回400；改用现有EvaluateRequestDTO后通过，未因此修改产品协议。普通10×10×2mm圆体正式STL接口下载到临时文件、独立STL reload+MeshValidator通过，缓存交付复用及GLB尺寸通过。
- 原图Fabric：`python -m pytest tests/test_fabric_original_shape.py -k api_preview_export -q`，1PASS、11DESELECTED（`fabric.log`）。新生成9原图实例、仅单元、9组件，最终校验/实际STL响应与严格读回PASS，形状来源与输出模式改动后旧文件请求拒绝。不是历史STL或浏览器点击。
- 固定单元Fabric：`python -m pytest tests/test_fabric_stl_f5c.py::FabricStlTests::test_api_flag_stale_content_namespace_and_download -q`，1/1 PASS（`fabric-unit.log`），20实例正式融合/测试导出、变更指纹/revision拒绝、生产授权禁止保持。此例没有增加独立文件读回，不扩大为所有11种单元制造通过。环境开关仅既有测试内部patch，不改运行服务或生产权限。
- `D:/npm.cmd run build` PASS（`build.log`，`index-DKaTkhO1.js`），`git diff --check`PASS；既有大bundle、LF/CRLF与Starlette测试客户端弃用warning保留，没有升级依赖。

### 当前交付边界

本轮三份产品接线（App、ManufacturingPanel、useFabricPreview）、三份测试（App.phase1a、useFabricPreview.test、test_web_staging）及两份既有记录有新增差异；与原Web-R1合计21份正式文件（16 tracked修改＋5正式新增），32历史tools全部保留，暂存为空。无提交/备份/推送/部署/服务重启。后端生产、制造几何、Validator、缓存、依赖不变。

本地受控A→B正常及失败后恢复PASS；线上长任务占槽原因/释放时间仍OPEN，实际用户本地浏览器与公网修复验收NOT TESTED，未重复此前持续超时的浏览器工具。上方前批真实制造NOT TESTED只针对当时批次，本补充普通/原图Fabric接口文件测试不倒改历史结论，也不等于浏览器下载。历史3+5、其他OPEN、Linux/切片/实物不变。STOP，等待用户本地试用及故障时段Render日志。

## Render 持续占槽：最小任务诊断接入（2026-10-13）

### 已确认与未确认

用户本轮提供真实Render日志摘要：health/import/evaluate多次200，Fabric preview至少4次429，服务关闭时有`Waiting for background tasks to complete.`，随后新服务进程启动。这支持持续忙碌和关闭时未完成请求的存在，不足以定位占槽接口、开始时间、元素/实例数量、OOM、其他会话或真正无法结束的计算。没有将摘要冒充完整日志读取，也没有公网制造或重启请求。

相关现有关系（未改变）：

| 接口 | 真正取槽时刻 | 持槽范围/本轮阶段标记 |
|---|---|---|
| POST manufacturing/build | 输入校验与结果缓存未命中后 | resolve_assets → standard_manufacture → 可选failure_snapshot → store_result |
| POST fabric/preview | 资产校验、key与缓存未命中后 | preview_evaluate_plan_prototype → cache_preview |
| POST fabric/candidate | 输入/资产校验后 | design_and_plan → candidate_geometry |
| POST fabric/fusion | 输入/资产校验后 | design_and_plan → candidate_geometry → fusion_and_validation → 可选failure_snapshot |

表内接口均有前缀`/api/v1/`。staging进程内四者共用一个BoundedSemaphore(1)，不是全局跨进程锁；普通缓存命中与Fabric预览缓存命中不占槽。普通/Fabric STL下载、health、import、evaluate没有申请此槽，仍可能竞争服务器总体CPU/内存/线程池。正常或异常离开原持槽范围后才释放；未返回的同步计算不会进入finally，所以finally存在不等于及时恢复。

执行器仍是Starlette `run_in_threadpool -> anyio.to_thread.run_sync`，本地依赖默认`abandon_on_cancel=False`。已读取本地Uvicorn `h11_impl.connection_lost`：标记disconnected而不是杀计算线程；HTTP等待超时/页面切换不会可靠终止后台工作。`server.py:shutdown/_wait_tasks_to_complete`等待`server_state.tasks`中的ASGI请求任务，日志所说background tasks不证明业务任务队列或专门BackgroundTasks。Docker现有启动命令没有新增worker、任务超时或取消参数；线上未取得精确依赖版本、shutdown timeout与平台终止事件，保持UNKNOWN。进程终止/OOM可能没有end/released日志，缺少末尾日志本身也不能判锁泄漏。

### 只增加诊断，不调整计算系统

- `xiaomang_pattern_lab/web/compute_diagnostics.py:ComputeDiagnostics.task`在原取槽位置执行同样非阻塞申请，contextmanager仅收拢原finally与记录；数据保护锁只用于短暂的日志元数据操作，不在计算期间持有。开发模式原本slot=None，仍不限制计算并发；没有新任务队列、进程池、异步后台作业或超时。
- 一行`compute_task`JSON，事件`start/stage/end/released/busy`；随机request_id/task_id、PID、recorded_at/started_at UTC、revision、哈希document_ref、source_element_count、权威已知instance_count、stage与perf_counter elapsed_ms。数量未知用null而非猜值；无单元旧plan=None用0计数，保留既有输出含义。源元素数不冒充Layout展开后的实际实例数。
- preview内部不侵入引擎，阶段是诚实的粗粒度求值/规划/原型合并标签，实例数仅在函数返回后已知；candidate/fusion则在规划完成后立即记录启用实例数。若preview卡在这一阶段，尚不能区分其内部子步骤，后续有证据才补更细日志。
- busy事件记录拒绝请求与`occupied`真实持槽任务的ID、接口、PID、开始时间、当前阶段及已运行时长；拒绝请求的task_id/start时间为空，不伪称已开始计算。记录由内部生成，不信任客户端标签。原429状态码/正文和全部API数据结构不变，未公开任务状态端点。
- `end`区分completed/error，仅记录异常类名、不记录异常正文/用户图像/文件路径/个人信息；融合捕获后返回422也明确记为error。实际release后才记released。日志处理器失败不能遗留槽或影响正在计算的任务；INFO复用Uvicorn现有logger，不改系统日志级别、Hooks、Git、环境或配置。

### 本地实际日志样例（不是Render日志）

完整原始字段保存在`work/web-compute-diagnostics-20261013/final-diagnostics.log`。以下只摘录该次实际值，任务ID缩写为可读前缀，不作为完整JSON：

```text
PID 24616，UTC 2026-10-13 03:37:39.026605：start，task 550361de…，manufacturing/build，revision 2，源元素1
03:37:39.028834：fabric/preview busy，occupied=550361de…，standard_manufacture，已运行2.90ms
03:37:39.030850：manufacturing/build busy，occupied=550361de…，已运行4.24ms
03:37:39.039819：end completed 13.67ms；released 13.74ms
随后作品B的新任务正常开始、结束、释放；A/B响应document_id分别对应原输入
```

日志不逐元素打印；没有任务运行期间的周期性心跳。长时间任务的实时持续时间由后续busy事件补充；若没有新请求，只能得到最后一条阶段日志。

### 定向测试与范围

- 命令：`xiaomang_pattern_lab/.venv/Scripts/python.exe -m unittest tests.test_web_compute_diagnostics tests.test_web_staging tests.test_web_server_wm3.WebServerWM3Tests.test_build_download_and_stl_reload_reuse_one_result -v`。最终`final-diagnostics.log` **11/11 PASS**（诊断7项、已有staging3项、普通STL1项）。子测试不是额外叠加总数。
- 覆盖四真实接口的start/stage/end/released、源/实例数和UTC/耗时；正常和异常/已处理422释放；A运行时B的两个429均关联A且无提前released；A和B依次真实小样本制造，结果分别对应作品、任务ID不覆盖；缓存命中不制造假任务；隐私、日志handler失败、开发模式原并发语义和旧可选plan全部通过。
- 制造回归：普通圆体实际STL接口/临时文件严格读回；原图Fabric另执行`python -m pytest tests/test_fabric_original_shape.py -k api_preview_export -q`，`fabric-final.log` **1PASS、11DESELECTED**。9实例最终制造/下载/读回、指纹和模式失效保护仍通过；不是浏览器下载或公网制造验收。前批前端40/40仅引用保护证据，本轮未修改前端或重跑前端构建。
- 失败批次原地保留：首轮测试在metadata加入本地路径被已有Contract安全规则拒绝、将Fabric配置送普通制造被已有边界拒绝；只换合法测试样本，不改安全规则。`final.log`一次耗时断言失败是本地Python3.12 Windows monotonic精度不足，busy仍正确关联；诊断改用项目已有同类perf_counter高精度计时，保留正耗时/顺序断言，不加等待/超时或削弱断言。后续所有重叠批次不相加。
- 仅检查本轮Python语法/运行与diff，不需要重新编译未变动的前端；既有Starlette弃用、Git换行和前批bundle warning不变。没有安装新依赖或运行Tk全量。

### 结论与后续闸门

未发现本地可复现锁泄漏；检查到的候选连通遍历耗尽有限集合，融合union层数逐次减少，没有明确无限Python循环。不过三角化/原型/原生布尔/网格验证没有可靠计算时间上限，仍可能长时间不返回。本轮未复现大型模型资源瓶颈，未辨别公网A/B/C/D类根因，不承诺新日志能自动解锁。

最小下一步是另行批准加载这份诊断版本，取同一task_id完整生命周期及Render Events/CPU/内存记录：正常长任务优先定位慢阶段和规模；同输入重复需用文档哈希＋revision/任务ID识别（不能直接认定同一浏览器会话）；任务未结束则结合PID是否仍活着与平台终止事件判断。只有确认无法结束的同步计算，才另批评估可终止进程隔离和可靠期限，不能只加HTTP超时或强行清锁。队列不是本轮必要改动。

本轮新增/修改仅app.py、compute_diagnostics.py、test_web_compute_diagnostics.py和这两份既有记录；前批Web-R1全部保留。目前24份正式改动（17tracked修改＋7正式新增）及32个历史tools，暂存区仍空，HEAD/分支不变。未提交、推送、部署、重启Render或现有本地8808；当前运行进程未加载这份新诊断，TestClient证据不能冒充其已更新。其他历史OPEN不变，STOP等待用户授权。
