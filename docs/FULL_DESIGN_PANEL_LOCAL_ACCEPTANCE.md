# 主编辑器完整图案控制面板：本地验收（2026-10-10）

## 实际版本与授权边界

- 工作区 `ParametricPatternGenerator`，分支 `feature/pattern-library-reuse`；开始/结束HEAD均为 `4a1c799255ca71002dc4cd9bae88e38ef0fea69e`。本批及此前通用尺寸入口成果均未提交，暂存区保持空。
- 开始时7个tracked修改、前批通用尺寸测试/记录/工具及22个旧探查脚本已存在，保留全部；未reset/clean、切分支、恢复旧补丁、提交、推送、部署、安装生产依赖或更改线上配置。
- 实现前源码快照 `work/full-design-panel-20261010/source-before.zip`。原稳定引用 `backup/web-phase1-complete-local-validated` 和 `backup/web-native-design-local-validated` 不移动；它们不包含本轮未提交成果。
- 三张参考截图没有随本条请求提供，参考算法/范围/组合规则不可由截图推断。本轮采用下述明确的小芒语义，不声称等价复刻参考站。
- 本轮实际验收为独立Edge会话、独立IndexedDB、当前生产构建与本地FastAPI `http://127.0.0.1:8800/`；最终前端产物 `index-BeMizbJw.js`。不清用户草稿，不将独立页面通过当作旧8792故障页已关闭。
- 后端为当前工作区 `xiaomang_pattern_lab.web.app:create_app`，Python由该项目 `.venv` 启动；其standalone子进程30944来源已核对。测试STL仅该本地进程沿用 `XIAOMANG_ENV=staging`、`XIAOMANG_FABRIC_STL_TEST_EXPORT=1`，没有改配置文件或生产权限。

## 开工映射与实际接线

| 清单 | 复用 / 最小补充 | 文件与入口 |
| --- | --- | --- |
| 行列密度、横纵间距 | 原Grid模型/Schema，补公共面板和主控间距接线 | `DesignPanelControls.tsx:9`、`designControls.ts:24/32`，调用原 `editor.updateGrid` |
| 单元尺寸、宽扁、基础旋转 | 原元素模型、最终几何管线；补源层非累积变换 | `design_controls.py:18 apply_design_controls`、`evaluation.py:101 _evaluate_shared_layers` |
| 错列 | 最小Grid适用计算，原basis_u向量半格偏移 | 同上，不替换Layout算法 |
| 随机 | 复用既有 `placement_assignment.deterministic_unit`，稳定源/seed/ID；补公共配置接线 | 同上；`DesignPanelControls.tsx`完整随机动作 |
| 场、逻辑强度/反转 | 原SharedFieldEngine、Size/FieldMapping、Python Schema、专用引用检查 | `linearSize.ts:66/104/151`，`SizeModifier`及原引用隔离 |
| 径向中心 | 原径向快捷与旧控制柄，保持独立语义 | `radialSize.ts`、`gradientControls.ts`，本轮只回归 |
| 三种影响区 | 补最小消费者局部权重，不改共享场 | `influence_areas.py InfluenceArea`、`shared_fields.py:848/988/1034` |
| 区域控制柄 | 原Workspace2D/pointer/world转换，增加辅助overlay | `influenceControls.tsx:5/17/38`、`Workspace2D.tsx` |
| 画板/单位/网格 | 原Canvas/mm_per_unit、同一候选和IndexedDB UI状态 | `designControls.ts:32`、`DesignPanelControls.tsx`、`localDraft.ts` |
| 主编辑器SVG/透明PNG | 同一已应用Python几何 + 原 `geometryShape`，最小输出适配 | `designExport.tsx:8/19/33`、`App.tsx exportDesign` |
| 保存/应用/撤销/请求 | 沿用原commitDocument、history、persistDraft、useDocumentPreview与共享槽 | `App.tsx applyLinearSize`；未创建第二个候选调度器 |

## 完整功能清单及实际语义

以下“完成并验收”限本轮相应自动化/浏览器/文件范围，不表示全参数矩阵、线上或实物通过。

| 功能 | 状态 | 实际规则与证据 |
| --- | --- | --- |
| 阵列密度 | 完成并验收 | 密度明确为行×列；没有第二个矛盾密度状态。浏览器3×3→4×5实际20元素；原Grid限制继续生效 |
| 基础间距 | 完成并验收 | 主控同时写横/纵；两轴可随后独立覆盖；重新打开主控显示两轴几何平均。实际12mm主控+纵10mm |
| 水平/垂直间距 | 完成并验收 | 中心点距离，以mm显示/按源比例回写；不与图形大小联动 |
| 错列排列 | 完成并验收 | Grid奇数行沿横basis_u偏移半格；旋转Grid数值测试通过。自由导入只显示规则说明，不自动重排 |
| 单元尺寸 | 完成并验收 | 100%相对结构源，合法1–500%；只改图形自身尺寸；候选每次从正式稳定输入计算 |
| 宽扁比例 | 完成并验收 | .1–10，宽×sqrt(aspect)、深÷sqrt(aspect)，面积保持；圆变真实椭圆，轮廓/孔洞保留，圆角同步缩放 |
| 基础旋转 | 完成并验收 | 原锚点周围附加±360°；不旋转整个文档、不重复累加 |
| 尺寸随机 | 完成并验收 | ±比例，0–.8；复用稳定hash，刷新/求值/制造不重抽 |
| 随机错位 | 完成并验收 | 各源轴独立±距离，UI为mm，回写一次native转换；不改变文档毫米映射 |
| 完整随机 | 完成并验收 | 用户动作选新seed；只改声明形状/随机参数，进入候选，Apply一条Undo；不换图、底图、单位或输出模式 |
| 逻辑强度 | 完成并验收 | 原FieldMapping strength混合本层factor与1；strength0不影响之前结果 |
| 反转渐变 | 完成并验收 | 原mapping.invert反转采样，不镜像作品、不改共享Field；浏览器Wave反转与权威结果一致 |
| 当前模式专属参数 | 完成并验收（代表性覆盖） | 共用真实目录，10个已有标量类型；Wave/Stripe等引用前批真实采样。本轮Wave18mm，采样.15431–.99609；没有十套硬编码表单 |
| 径向中心水平/垂直 | 已实现，本轮定向自动化回归通过 | 原径向快捷仍独立，不把Ring当径向峰；本批未另重复径向专门鼠标截图 |
| 直线轴 | 完成并验收 | 到有限轴的两侧距离，圆头带状域；位置/方向/长度/宽度/过渡真实参与Python计算，不冒充沿线Field方向 |
| 椭圆轴 | 完成并验收 | 填充旋转椭圆，真实中心/长短直径/旋转/过渡；不是圆形Ring |
| 曲线轴 | 完成并验收（最小曲线语义） | 二次Bezier起点/一个控制点/终点，真实距离/宽度/过渡；固定128段近似，不是完整矢量编辑器 |
| 最多3区、选择/调整/启停/删除 | 完成并验收 | 稳定area ID、同一候选、Schema校验；第4项disabled，禁用/删除/Cancel/Reset/刷新验证 |
| 影响区组合 | 完成并验收 | 启用区权重取max，顺序无关；无区/全停用为本层中性；范围外直接跳过本层；不将Field置0 |
| 显示网格 | 完成并验收 | 5mm辅助显示，与画板线/底图独立；切换无几何commit/revision/制造失效；不进入任何作品文件 |
| mm/cm/px | 完成并验收 | mm/cm仅表示；像素项目依据实际mm_per_unit，非像素项目明确96DPI=25.4/96mm表示。独立PNG像素分辨率不改模型尺寸 |
| 画板宽度/高度 | 完成并验收 | 独立正宽高、保留origin；60×40→70×45mm不拉伸、不重排或删除元素。Grid仅通过显式行列/间距编辑，不随画板自动铺满 |
| 主编辑器SVG | 完成并验收 | 真圆/椭圆/矩形/path及孔洞，mm尺寸+世界viewBox，画板clip；非PNG嵌入，不用/patterns/ |
| 主编辑器透明PNG | 完成并验收 | 同一SVG栅格化RGBA透明背景；独立宽64–8192px，按画板比例算高（≤8192px、≤32MP）；不是截图 |

### 随机、层顺序和旧数据

- `web_design_controls` v1是PatternDocument metadata中的小型可选配置，不新建格式/Engine。旧文档无此key时完全不启用公共变换。
- 计算顺序为既有结构/placement assignment → 本批公共源变换 → 原共享场/尺寸/旋转/位置层 → 既有局部结果。范围在当前Size层输入中心取权重，保留之前所有效果。
- seed是0–2147483647整数；同seed+stable element ID+channel确定size/offset_x/offset_y/rotation。完整随机UI只生成新seed和声明范围内的参数，正式Apply仍一次提交。
- 原有用户场/其他Size层/Fabric消费者不被删；专用ID/引用隔离仍由原editor机制处理。Type切换不累积自己的Size，范围不改共享Field本体。
- 老线性全图/矩形、径向快捷、旧正式作品配置保持兼容；不迁移旧非中性隐式堆栈，不假定其他效果不存在。

## 交互、保存与候选边界

- 公共参数和尺寸场沿同一draft/候选hook。公共参数单独编辑不创建Field或Size。待应用范围、大小、随机都不写正式revision/Undo/自动草稿。
- Apply先用现有IndexedDB保护正式作品；失败保留作品和候选。保存期间再次校验source/proposal key。成功完整配置一次commit，浏览器逐次记录1正式evaluate/1Undo。
- Cancel丢候选而非回写旧快照。Reset只重置面板声明配置：公共shape/random默认、当前正式Grid/画板、当前Field真实默认和mapping、已有area类型/ID的默认范围；仍需Apply。用户源图/其他场/Fabric不被清空。
- 数值输入确认/slider松手后自动预览；画布控制柄拖动可合并权威请求。一次拖动8/8/24个moves，实际line/ellipse/curve分别1/1/4次evaluate，0正式commit/制造。最后会话最多1个evaluate在途；没有积压每个事件。
- 显示单位/网格/PNG分辨率在现有IndexedDB UI state中保存，不是制造几何。清洁公共表单关闭/Apply不产生文档commit、既有导出仍有效。
- 已应用公共值/scopes/Field引用/seed恢复后与刷新前geometry完全相同。未应用快捷表单不承诺刷新恢复，界面说明边界；旧Undo history刷新后重新开始。
- 临时参数或未应用Layout存在时禁当前作品导出/制造；不偷偷Apply Layout。设计→制造保留有效正式输入，②仍为原中央3D+右栏制造系统。
- 辅助标记/参考底图不成为elements、Bounds、Fabric/STL。真实SVG导入5个对象+独立PNG底图验证，无自由重排，导出没有底图；孔中心PNG alpha=0。

## 当前生产构建的真实浏览器与文件证据

命令（仓库根，既有Playwright模块；不安装依赖）：

```powershell
$env:PLAYWRIGHT_MODULE='C:/Users/13524/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'
$env:FULL_DESIGN_ORIGIN='http://127.0.0.1:8800'
node tools/full_design_smoke.cjs
& ./xiaomang_pattern_lab/.venv/Scripts/python.exe tools/full_design_readback.py
```

- 最终浏览器PASS，65个POST全200、0pageerror，WebGL真实模型可见；不是仅API返回或菜单存在。构建资源 `index-BeMizbJw.js`。
- 同一非零origin20/40、source120×80、.5mm/源单位项目，从9圆Grid到4×5，公共size120%、aspect1.25、rotation12°、seed42、size random.2、jitter.2mm、spacing12/10mm+stagger；随后Wave Size+三影响区→SVG/PNG→标准制造→保形Wave高度→Fabric STL。
- 六个公共/各独立影响区/组合/画板候选结果与再次Python求值逐项一致；组合案例20个元素中12个在所有影响区外，与关闭该Size层的结果完整一致。
- `design.svg` 4783字节、20真实矢量；`design.png` 61681字节，1600×1067，RGBA alpha0–255。
- `board.svg` 同20真实矢量、70×45mm/world viewBox；`board.png` 57027字节，1600×1029；画板前后geometry完全相同。
- `imported.svg/png`真实5对象（圆/椭圆/圆角矩形/带孔区域/L路径），SVG真实孔，PNG1600×1067孔中心透明；参考底图和所有aux不在文件中。

| 文件 | 实际字节/三角面 | 实际XYZ mm | 读回结论 |
| --- | --- | --- | --- |
| standard.stl | 46484 / 928 | 56.2923975×32.3415852×2 | 每元素XY/自身轴宽深/rotation/高度与正式2D一致 |
| fabric.stl | 46484 / 928 | 56.2923975×32.3415852×5.8880482 | 保留原轮廓、20计划实例全部顶点及逐元素Wave高度一致 |

两份实际下载文件经既有STLExporter读回/MeshValidator：20有效组件、Z=0、封闭、绕序一致、正体积、零退化面。仅图案允许多组件，不宣称融合为整体。固定Unit Cell的Pattern Points只继承一次尺度、用户Height保持3mm另有9实例Python数值与真实binary STL严格测试。

截图/交互/HTTP/DTO/文件位于忽略的 `work/full-design-panel-20261010/`：

- `public-controls.png`、`area-line.png`、`area-ellipse.png`、`area-curve.png`、`areas-dragged.png`、`artboard.png`、`manufacturing.png`、`imported-design.png`。
- `browser-evidence.json`含实际请求和鼠标拖动记录；`readback.json`含权威几何、范围外、采样、PNG透明度、STL与性能结果。无录屏文件，不伪造附件。
- 截图检查发现显式“适合窗口”原先仍按正式bounds取景；已改为当前候选bounds，仅用户主动点击取景，普通调参不自动重置相机。

## 测试批次（不相加为全量）

1. 最终相关Web19文件91/91 PASS：App.fullDesign/document.fullDesign、fieldSize/App.fieldSize、linearSize/App.linearSize/linearRegion/radialSize、gradientControls/view、nativeDesign/App.nativeDesign/referenceLayer、localDraft/realSize、fabricPresets/fabricCenterRecipe、computeRequests/useFabricPreview/useManufacturing。
2. 仅测试补充（无产品修改）后：`npm test -- src/document/fullDesign.test.tsx src/App.fullDesign.test.tsx src/App.fieldSize.test.tsx`，3文件14/14 PASS，含invalid feather/NaN/coincident curve及完整Reset；与91重叠，不能相加。
3. Python定向：`& ./xiaomang_pattern_lab/.venv/Scripts/python.exe -m pytest tests/test_full_design_panel.py tests/test_field_size_shortcut.py tests/test_web_svg_grid_p0.py tests/test_web_server_wm3.py tests/test_fabric_original_shape.py tests/test_fabric_cells_only_1a.py -q`，60/60 PASS、2子测试PASS；含本批9新测试，2条既有弃用warning。
4. 本轮较早独立PNG/JPG/SVG API导入回归：`... -m pytest tests/test_web_import_wm55.py -q`，4/4、5子测试PASS；没有借新的浏览器SVG案例冒充PNG矢量化全覆盖。
5. `npm run build` PASS；87modules，JS1298.66kB/gzip363.02kB，CSS32.68kB。既有>500kB warning保留；不为本任务升级依赖/重构打包。`git diff --check`通过。
6. 上述真实browser脚本与文件readback最终PASS；不重跑无关Tk全量，不写Python/Web“全量PASS”。

中途失败准确记录：shell默认python不可用、第一次误找根`.venv`，改用实际项目解释器；早期catalog/mock兼容及JSON编码、脚本filechooser/关闭观察时序修正见运行过程。最后一次浏览器脚本在进入制造同帧发起final请求，被原共享busy入口正确拒绝（没有制造POST，只有轻量preview200），超时；脚本按真实顺序等待自动preview释放后再点击，随后完整65POST/下载PASS。没有删除busy保护或放宽几何断言/Validator。实际文件input上传链通过，浏览器原生文件选择弹窗本轮未验收。

## 实际性能与限制

- Python authority、三影响区（含128段curve）、3次同配置：100元素8.58–9.53ms，400元素32.80–44.86ms，1000元素79.69–81.61ms。仅Python evaluate测量，不是FPS或浏览器端到端制造性能。
- 20元素真实交互请求按最新输入合并；没有反复5000实例压力制造。较大画布所有参数的浏览器FPS/完整制造矩阵未做。
- 曲线范围是明确的128段近似；极窄/极高曲率边界误差未做全面精度Gate，不宣称精确连续曲线距离。最大3区、单二次Bezier满足本轮最小曲线编辑，不包含多段自由矢量绘图。
- 原图轮廓路径/孔洞通过真实SVG/PNG与代表性STL；SVG/PNG画板裁切不反向裁剪制造，可能与STL整体范围不同，UI已说明。
- 初次空白项目需先导入/添加图形再打开控制面板；没有借本轮重做欢迎页。混合追加独立图形限制、旧隐式效果堆栈不自动迁移、旧8792原故障页鼠标OPEN仍保留。
- Image/Distance源资产、10类型采样与引用保护引用前批有效记录；本批没有再逐类型做所有制造×恢复矩阵。Composite无快捷Schema，本入口未实现复杂图编辑，原高级图保留。
- 本轮公网/Render/Linux、切片、实物NOT TESTED；历史Linux结果不代替本批。不声称网站已发布、物理可打印认证或整个F5已闭环。
- 所有新源码/fixture/测试/文档保留未提交；work中的截图/STL/日志是本地证据，不被现有Git备份引用保护。停止，不进入其他功能。
