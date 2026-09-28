# Gate 状态（2026-09-19）

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
