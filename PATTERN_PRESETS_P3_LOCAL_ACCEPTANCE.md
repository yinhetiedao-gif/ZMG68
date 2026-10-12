# P3 本地实施记录（未完成验收）

基线：`1a8d28de800471074c47bc773fc942876cd2d56a`。
本轮不提交、不备份、不推送、不部署。历史 OPEN 不变。

## 数字织格：实现部分完成

新增双绑定适配：专用 Checker 同时驱动受管 Size 与 Rotation；记录两个 Modifier 和 Field 的归属。重复编辑复用 ID；外部消费者触发专用场隔离并同步重绑；跨旧预设切换停用受管旋转。原始元素不因本适配改写。

默认新图案为 10×10 矩形，间距 5.2 mm，矩形 3.8×1.5 mm；Size 0.86–1.06，Rotation 0–90°。Checker 偏移从首次实际中心初始化并保存。

实际执行证据：

- 定向 Vitest：P1/P2/P3 核心三文件，共 24/24 PASS。
- Python 定向测试：1 PASS，验证默认交替、双格组合、斜向采样、XY 保持和重复求值。
- TypeScript 检查及 Vite 构建成功；现有大 chunk 提示仍存在。
- 正式 fixture 与缩略 SVG 由 Python 引擎实际输出，含 100 个矩形；不等于浏览器视觉验收。
- 日志及中间 DTO 留在 `work/pattern-presets-p3-20261011/`。

## 验收阻塞

两次独立 Playwright Edge 启动均在页面建立前失败（crashpad named pipe 错误）。随后尝试通过可用 Computer Use 读取既有 Edge 窗口，工具返回 `Computer Use was not approved to use Microsoft Edge`。没有继续绕过限制或操作用户现有草稿。

因此以下项目 **未验证，不标 PASS**：真实浏览器默认/变体截图、界面 Apply/Cancel/Undo/Redo/刷新/返回原作品、实际 SVG/透明 PNG 下载读回、普通 STL/Fabric STL 下载读回及制造核对。

现有 UI 测试中固定“6套”的标题断言还需在后续允许继续时适配新增数量并执行；不能将核心测试视为完整 UI 回归。

## 浏览器补验（2026-10-11，仍 BLOCKED）

以上阻塞段保留为最初实施时的历史记录，不代表后续所有项目都未执行。本次没有修改产品代码，没有重跑既有测试或构建，没有提交、备份、推送或部署。

- 复用先前已取得的本地 IAB / `http://127.0.0.1:8804/` 证据：默认及格子尺寸 10.4 mm 候选截图；同一 Checker `field-1` 驱动 Size 和 Rotation；候选不增加 Undo，Cancel 恢复默认；真实 SVG 60×60 mm、100 个矢量矩形、50 个 0° / 50 个 90°及两组实际尺寸；真实透明 PNG 1600×1600 / RGBA。实际下载文件与截图位于 `work/pattern-presets-p3-20261011/browser-recovery/`。这些项目本轮未重复测试。
- 现有会话恢复后完成第二变体：格子尺寸 5.2 mm，交替角度 45°，尺寸对比 0.36（映射 0.78–1.14）；候选画布包含 100 元素。保存 `variant2-45deg.jpg`，但此次截图为窄视口，仅作为参数和可见局部画面证据，不宣称完整桌面视觉通过。
- 实际 Apply 后，100 个 `g[data-element-id]` 的 ID/图形 DOM 数组与候选逐项完全一致。Apply 前 Undo 禁用，Apply 后启用；通过按钮键盘 Enter 激活一次 Undo，几何数组与默认逐项一致、Undo 禁用/Redo 启用；Redo 恢复第二变体全部几何及 Size/Rotation 参数。这证明本次 Apply 只产生一条历史记录。最初鼠标 Undo 点击未观察到状态变化，因此鼠标激活本身不标 PASS。
- 随后再次从选择器点击“编辑数字织格”，浏览器控制返回 `Input.dispatchMouseEvent` 超时。按用户要求立即停止自动控制，没有绕过工具、重启服务、清除草稿或继续自动操作；该点击后的页面最终状态 UNKNOWN。
- 仍未完成：Reset、已应用配置刷新恢复、返回原作品、P1/P2 跨预设 Rotation 清理、普通 STL 与 Fabric STL 的真实下载及几何读回。两个 STL 尚未取得，不能以既有单元测试、预览或 API 结果替代。历史 OPEN 保持；本批完整结论仍为 BLOCKED，未改成限定样本 PASS。

## 用户手动试用确认与文件查找（2026-10-11）

- 用户明确确认“P3数字织格实际使用正常”，因此**用户手动试用：PASS**。这是用户报告的实际使用结果，独立于前述自动浏览器证据；用户本条未逐项提供 Reset、刷新恢复、返回原作品、跨预设 Rotation 清理等操作记录，不把这些独立证据改成已取得，也不宣称全项通过。
- HEAD 仍为 `1a8d28de800471074c47bc773fc942876cd2d56a`，分支仍为 `feature/pattern-library-reuse`；本次未改产品代码、重跑已通过测试、操作浏览器、提交、备份、推送或部署，全部既有修改和历史 OPEN 保留。
- 实际查找范围：已知浏览器下载目录 `F:/GPT下载`、Windows Downloads 与桌面顶层，以及本批 `work/pattern-presets-p3-20261011/`（递归）。本批 work 无 STL；已知下载目录中的 Fabric STL 最后修改于 2026-10-09，最近的标准 STL 为 2026-10-11 的旧带孔回归样本。未找到可确认属于数字织格本轮操作的普通/Fabric STL，不以旧文件或其他项目文件代替本批样本。未知的其他下载位置不宣称已查遍。
- **数字织格制造读回：BLOCKED / 实际文件缺失。** 尚无法对本轮真实输出核对 XY、旋转、尺寸、Z/逐元素高度、封闭性、正体积和退化面。需提供两个实际下载 STL 的文件或准确路径，并说明对应设计参数、厚度/高度、形状来源与输出模式，才可完成对应文件核验。
- 旋涡鳞纹保持 NOT STARTED；已有 Spiral / Size / Rotation 双绑定接线可作为后续基础，但本次未开始实现。待制造检查有有效文件证据后，再报告数字织格限定样本验收结论并确认下一项范围。

## 数字织格正式后端制造与文件读回（2026-10-11，限定样本 PASS）

本段更新制造结论；前述文件缺失 / BLOCKED 是此前查找阶段的真实历史，不删除、不冒充当时已通过。本次按用户新授权使用现有正式后端入口生成新文件，没有重试此前超时的浏览器自动化。

### 同一份已应用设计与制造参数

- 输入为已有可移植 fixture：`tests/fixtures/pattern_presets/digital-weave.pattern.json`；HEAD 仍为 `1a8d28de800471074c47bc773fc942876cd2d56a`。fixture 和产品文件未修改。
- 60×60 mm 画板，10×10 矩形 Grid；中心从 (6.6, 6.6) 到 (53.4, 53.4) mm，间距 5.2 mm；基础矩形 3.8×1.5 mm。Checker 宽高 5.2 mm、角度 0°、偏移约 (4, 4) mm；同一 `field-1` 同时绑定 `size-1` 与 `rotation-1`。
- 正式求值得到 100 个矩形：50 个采样 0，尺寸 3.268×1.290 mm、旋转 0°；50 个采样 1，尺寸 4.028×1.590 mm、旋转 90°。逐元素中心保持，水平/垂直相邻交替。
- fixture 的原始 `elements` 仍有旧 9 圆点快照；此次没有以该数组制造或替换 fixture，而是由现有 Grid / Evaluate 正式生成最终 100 个矩形。
- Standard：`POST /api/v1/manufacturing/build`，厚度 2 mm；`GET /api/v1/manufacturing/{id}/model.stl` 获取实际 binary STL。
- Fabric：仅在请求 DTO 的 metadata 增加 `fabric_config`，`shape_source=original`、`output_mode=cells_only`、`original_shape.size_scale=1`、均匀高度 2 mm、Pattern Points、无 Fabric 高度场。存储的未使用 Solid 参数厚 0.6 mm / margin 0 不生成底板，单元 Z 从 0 开始。`POST /api/v1/fabric/fusion` 后，以同一输入 `POST /api/v1/fabric/{id}/model.stl` 获取已校验结果；不重新融合不同模型、不走普通 STL 替代 Fabric。
- 两份请求保留相同 document ID / revision 0、二维源/配置/引用；移除 Fabric 输出配置后 DTO 完全一致。两个 `/api/v1/evaluate` 响应的最终 geometry 与 bounds 完全相同。完整请求指纹因输出配置不同而不同，这是预期行为，不冒充完整 DTO 同一指纹。
- 使用隔离的 FastAPI `TestClient(create_app())` 调用真实注册路由、制造服务和现有 STLExporter，无 mock、无 Validator 绕过、无 Repair。只在验收子进程设置既有本地测试权限 `XIAOMANG_ENV=staging`、`XIAOMANG_FABRIC_STL_TEST_EXPORT=1`；未修改配置文件、用户运行服务或生产权限。所有请求串行，未调整后端并发限制。

### 实际交付与独立磁盘读回

输出目录：`work/pattern-presets-p3-20261011/final-stl-acceptance/`。该目录为本轮新生成的忽略运行产物，不纳入 Git 提交。

| 文件 | 制造 / 文件接口 | 实际尺寸 XYZ（mm） | 组件 / 三角面 | 水密 / 绕序 / 体积 / 退化面 | 结论 |
| --- | --- | --- | --- | --- | --- |
| `digital-grid-standard.stl` | 200 / 200 | 50.0680003×50.8280015×2 | 100 / 1200 | 水密、绕序一致、1062.0238018 mm³、0 | PASS |
| `digital-grid-fabric.stl` | 200 / 200 | 50.0680003×50.8280015×2 | 100 / 1200 | 水密、绕序一致、1062.0238018 mm³、0 | PASS |

- 两份文件实际存在，均为 60,084 bytes；从磁盘通过 `STLExporter.reload_as_mesh_result` 独立读回，不用响应摘要代替文件检查。默认 MeshValidator：有限坐标、水密、边界边 0、非流形边 0、退化面 0、错误 0。多组件 warning 是实际输出事实，未强制单组件。
- Bounds 均为 `[4.96600008, 4.58599997, 0]` 至 `[55.03400040, 55.41400146, 2]` mm。画板 60×60 mm 不等于图案制造 Bounds；没有整张 60×60 mm 底板。
- 对 100 个组件分别匹配源元素 ID，检查中心、8 个真实轮廓顶点、局部宽深、0° / 90°长轴旋转、Z=0..2、封闭性、绕序及正体积；全部匹配。对权威最终轮廓的最大顶点误差 `0.0000026330145 mm`，小于读回比较容差 `0.00001 mm`；此容差仅用于 STL float32 比对，未改变几何 Validator 阈值。逐元素记录保留在两个 `*-readback.json`。
- 两个 STL 的对应顶点差为 0，忽略面/顶点存储顺序后的三角几何完全相同；字节 SHA 不同，实际差别为面/顶点和相应法线记录顺序，不是位置、尺寸、旋转或高度变化。均匀高度、相同最终轮廓且无底板时，两条路径本就应生成相同形状。
- 文件 SHA256：Standard `d1d9198f763dd13f0eea78dec5f486daf40f3e040165035a1522734992695c6c`；Fabric `179bdadbb7438ee732d953dbd5d61d7288a43457f4cff009a6c9286842987a22`。
- 证据：`standard-source.json`、`fabric-source.json`、`evaluated-design.json`、`api-requests-responses.json`、两个制造结果 JSON、两个逐组件读回 JSON、`artifact-comparison.json`、`evidence.json`。它们保存真实请求、结果 ID、指纹、文件 hash 和制造/读回事实，不保存 STL base64。
- 执行：现有 `.venv/Scripts/python.exe work/pattern-presets-p3-20261011/final-stl-acceptance.py` 首次正式制造及文件获取全部成功；读回脚本调用可选图分组引擎时因未安装该引擎中断，记录于 `failure.json`。仅修改忽略的验收脚本为无依赖邻接分组，再以 `--readback-only` 对原文件核验通过，未重新制造、未安装依赖。`inspect-final-stls.py` 补充二进制三角记录对照通过。没有重复定向产品测试、构建或全量回归。

**本轮结论：数字织格制造读回 = 限定样本 PASS（正式后端文件制造及独立读回）。** 用户手动试用 PASS 保持；本段不是浏览器 STL 点击下载、公网、Linux、切片或实物验收。此前尚未取得的独立 Reset、刷新恢复、返回原作品、P1/P2 Rotation 清理等操作证据仍按原状态保留；历史 OPEN 不变。未修改产品代码、未提交、未备份、未推送、未部署；旋涡鳞纹仍未开始。

## 旋涡鳞纹（2026-10-12）：已实现；完整浏览器验收 BLOCKED

本节依据数字织格限定样本制造通过后的新授权实施，不重写数字织格，不提交/备份/push/deploy。实际 HEAD 仍为 `1a8d28de800471074c47bc773fc942876cd2d56a` / `feature/pattern-library-reuse`。改动前源码保护在 `work/vortex-scales-20261012/source-before.zip`，Git、所有原成果和旧运行产物保持。

### 复用与真实参数

- 复用 `presetDualBinding.ts` 已有双绑定/归属扫描、`linearSize` 的专用场和候选、现有 SpiralField / FieldMapping / SizeModifier / RotationModifier，以及同一 App 草稿保护、提交、Undo 与请求协调器。没有新算法、依赖、公共 DTO 或预设系统。
- `patternPresets.ts` 接入 `vortex-scales`：60×60 mm，12×12 真椭圆 Grid、间距 4.6 mm、椭圆 3.4×1.6 mm、XY 中心不变。Spiral 完整配置：中心 (30,30) 世界单位、turns=3、phase=.15、direction=1、falloff=1、invert=false。中心依据首次实际 Bounds / mm_per_unit 初始化，保存 native anchor，不按原始数组第一个旧圆点猜中心。应用当前作品不替换其轮廓/Layout/画板/Fabric。
- 一个专用 Spiral 同时绑定 Size .74–1.04 / bell 与 Rotation 0–180° / linear。螺旋密度是现有 `turns`（按源范围对角线归一化），不是固定毫米波长；phase 以一个周期为1，可在高级区使用现有合法范围。主面板为密度、相位、尺寸上下限。相位推荐滑杆采用 .01 步长 / 0..1，修正浏览器把真实 .15 显示成 .2 的不一致，未改 Python Schema 范围或算法。
- 高级中心、方向、衰减和旋转映射仍通过 Generic ParameterPanel 编辑；数字织格仍使用原Checker默认参数和原双绑定。与其他6套的旋转清理复用原ID，切回数字织格更新同一受管旋转而不叠加。精密错列仍只能明确创建/编辑自己的 Grid，不为本轮放开覆盖导入作品。
- 真实引擎缩略图 `web/src/document/patternPresetThumbnails/vortex-scales.svg` 来自正式可移植 fixture 的 Python Evaluate，实际包含144个椭圆；缩略图不是主编辑器下载验收，也不冒充透明PNG。

### 中心、方向与相位接缝

- Python 数值覆盖默认 (3,.15,+1)、宽疏 (1.6,.45,+1)、反向密集 (5,.15,-1)：144个真实采样、尺寸bell及线性旋转逐项正确、XY不变、重复求值确定；非零原点、非正方形、.5 mm映射及Adapter世界坐标通过。
- 默认12×12为偶数阵列，没有元素正好落在极坐标奇点；最近中心距离约3.252691 mm。默认与宽疏实际画面显示协调的鳞纹旋转，未观察到明显相位断带，不等于所有采样/所有轮廓视觉通过。
- 使用相位边界两侧真实Spiral采样验证：bell尺寸两侧一致，默认0/180°旋转对椭圆/矩形具有180°外形等价。对不对称L轮廓，线性旋转不具备此等价，测试明确证明边界轮廓不同；已有高级bell旋转映射可令两侧返回相同角度，数值对照通过，不新增算法或自动修改用户场。
- UI显示上述边界并保留高级映射选择。**不对称轮廓默认线性映射不承诺无缝**；高级bell在任意实际作品上的浏览器视觉仍待验收。本轮未调整成新的场算法，不对异常/复杂轮廓作无依据PASS。

### 自动化验收（分批，不累加）

- 首批核心：`D:/node.exe node_modules/vitest/vitest.mjs run src/document/patternPresetsP3.test.ts src/document/patternPresets.test.ts src/document/patternPresetsP2.test.ts`，3文件28/28 PASS。包括新配方、同一双绑定、重复更新、Reset、JSON恢复、共享用户场/Fabric保护、跨类型受管层及毫米初始化。
- App流程：`... run src/App.patternPresets.test.tsx src/App.patternPresetsP2.test.tsx --maxWorkers=1`，2文件12/12 PASS。复用原候选/Cancel/一次Apply/Undo/Redo/Reset/刷新/返回原作品/保存失败流程；只将旧“6套”选择器改为真实目录数量，增加旋涡案例，没有删断言。
- 浏览器发现相位滑杆/说明不一致后补最小显示修改及断言；最后 `... run src/document/patternPresetsP3.test.ts src/App.patternPresetsP2.test.tsx --maxWorkers=1`，2文件12/12 PASS。与前批重叠，不称合计全量。
- `xiaomang_pattern_lab/.venv/Scripts/python.exe -m pytest tests/test_pattern_presets_p3.py -q`：6/6 PASS，数字织格旧定向用例保留并通过。
- 最终 `npm.cmd run build` PASS，加载产物 `index-B0XFdbRS.js`（首次产物 `index-B9oJnIk8.js` 已重载更新）；既有大chunk、Starlette/httpx warnings保留，无升级依赖。`git diff --check` PASS。未跑无关Tk全量。

### 实际浏览器证据与阻塞

- 独立本地8805 / 当前工作区FastAPI＋production dist，测试导出只在该隔离子进程启用，未重启/操作旧8802/8804服务或用户草稿，未改变线上配置。
- 先创建单矩形原生作品，再真实创建旋涡；见 `default.jpg` 与 `variant1-wide.jpg`。第一份默认真实画面和主参数、第二份1.6/.45宽疏候选均为实际浏览器截图。`default-before-label-adjustment.jpg`保留初次观察，不当最终UI截图。
- 真实候选修改保持144元素且正式revision0；Undo始终禁用。Cancel后144个DOM几何数组与默认逐项完全一致，无正式提交。首次刷新后恢复144元素、同一配置及有效返回入口，旧Undo不保留；不等于已应用变体刷新流程。
- 请求记录 `browser-requests.jsonl` / `request-summary.json`：7次Evaluate（1次原作品、6次旋涡配置）、均200，所有旋涡revision0；最多1个计算在途，0次最终制造。6次旋涡中包括默认/恢复/重新编辑、合并后的1.6/.45候选及取消后的默认候选，不按每个输入排队。静态资源8次304为合法缓存响应，不当接口失败或全200。
- 重新编辑一次鼠标调用报 `Input.dispatchMouseEvent` 超时，但随后实际DOM确认已经进入编辑器；不把工具成功与实际页面变化混为一谈。第二次编辑使用键盘语义操作仍报 `Input.dispatchKeyEvent` 超时，随后读取状态报 `Emulation.setFocusEmulationEnabled` 超时。之后停止UI自动控制，没有重启浏览器、绕过权限或另启正常页冒充此流程通过。该动作后的最终页面状态UNKNOWN。
- **浏览器剩余BLOCKED**：第三张5/.15/-1反向密集截图、实际高级顺逆/中心编辑、Apply/Undo/Redo/Reset完整浏览器链、已应用变体刷新/返回原作品及与全部7套的实际界面切换；这些功能的相应核心/App测试已通过，但不替代独立浏览器证据。主编辑器SVG/透明PNG实际下载与读回本轮未取得，保持NOT TESTED，不用缩略SVG或数字织格旧文件代替。
- `glance`可选CLI未安装；上述视觉结论来自实际截图观察，不宣称额外CLI自动视觉核验通过。所有已取得截图/DOM数组与操作结果保存在 `browser-evidence.json`。

### 正式后端实际STL文件制造与读回：限定样本PASS

- 新文件在 `work/vortex-scales-20261012/manufacturing/`：`vortex-scales-standard.stl`（普通2mm）与 `vortex-scales-fabric.stl`（保留原图形状、cells_only、size_scale1、均匀2mm、无基底）。取相同已应用默认fixture和最终144椭圆，两个正式Evaluate geometry / Bounds一致；只有Fabric请求加输出配置。
- 使用真实注册FastAPI TestClient / Standard制造服务和Fabric fusion，再从各自正式STL接口获得binary内容并实际保存；所有6请求200，没有mock、跳过Validator、重造替代STL、Repair或删除几何。只在验收子进程启用已有本地测试权限，不扩大Production开放。
- 两份均406,484 bytes / 8128三角面 / 144有效封闭组件，XYZ `53.322025299×54.129195690×2 mm`，Z0..2，正体积 `1064.977844322 mm³`、绕序一致、有限坐标、水密、边界/非流形/退化面均0。多组件warning符合仅图案模式，不冒称融合成一个实体。
- 独立从磁盘读回，144组件逐个匹配元素ID、中心、实际Adapter轮廓顶点、椭圆长轴端点和旋转、局部宽深、逐元素Z和正体积，全部PASS；最大顶点误差 `.000002649625 mm`，小于只用于float32读回比较的 `.00001 mm`，生产Validator阈值未改。两条路径对应顶点差0；二进制排序可以不同，不要求文件hash相同。
- `manufacture-readback.py` exit0，实际请求/身份/参数/指纹在 `api-requests-responses.json`，两个 `*-readback.json`保存144条组件核对，`evidence.json`保存摘要。这是**正式后端文件制造PASS**，不是浏览器下载、公网、Linux、切片、实物PASS。

### 本轮修改及停止边界

产品接线：`patternPresets.ts`、`PatternPresetPicker.tsx`、`App.tsx`。定向测试：现有`patternPresetsP3.test.ts`、`tests/test_pattern_presets_p3.py`及2个App预设测试；新增可移植vortex fixture和真实缩略SVG。本记录与Gate摘要更新；忽略work中的源码快照、截图、STL、日志和临时验收脚本不作为新生产代码。

本轮未改`editor.ts`、`linearSize.ts`和`presetDualBinding.ts`的既有数字织格成果，未修改制造算法/Validator/依赖/生产权限。完整旋涡验收仍BLOCKED，未冻结P3、未创建稳定引用；所有历史OPEN、未应用快捷/旧Undo刷新边界、一份返回上下文、旧隐式堆栈限制保留。本批公网/Linux/切片/实物NOT TESTED。STOP，等待补齐实际浏览器/输出证据或用户试用授权。

## 旋涡最小剩余输出补验（2026-10-12，服务端输出限定样本PASS）

本段只补文件证据，前述“SVG/PNG未取得”保留为当时的历史记录。本次没有调用任何浏览器控制工具，没有修改产品代码/算法、重新求值、重新制造STL、重跑已通过测试或构建；没有提交、创建备份、推送或部署。HEAD仍为`1a8d28de800471074c47bc773fc942876cd2d56a`。

### 输入与输出来源

- 直接读取本批`manufacturing/standard-source.json`及`manufacturing/evaluated-design.json`：正式默认旋涡`preset-vortex-scales`、revision0、144个椭圆；与此前已通过的两份STL使用相同已应用二维结果。没有导出fixture原始9圆点数组、缩略图或候选变体，也没有重新运行Evaluate。
- 复用主编辑器现有`web/src/geometry/designExport.tsx`的`designSvg`及`designPng`，由Node加载并执行；SVG继续使用同一`geometryShape`，尺寸及画板裁切沿用正式函数。**这是服务端执行现有Web输出适配器，不是浏览器点击下载，也不是新增FastAPI导出接口。**
- `designPng`需要浏览器Image/canvas接口；本次仅在忽略的验收脚本中桥接到已随运行环境提供的`@napi-rs/canvas`，SVG解码使用已提供的sharp/libvips，仍把同一份完整SVG绘入透明画布、按原函数输出PNG。没有安装/修改项目依赖，没有手工重画144个图形。服务端解码/绘图库不同于浏览器，因此不把该文件检查当作浏览器Image/Canvas/下载交付已验证。
- 初次服务端native SVG解码固有分辨率过低，读回中心误差超过阈值；调整验收解码分辨率后，额外带孔非零viewBox样本又暴露该native解码器的坐标兼容问题。保留两次原文件及具体失败记录，最终所有样本一致使用已有sharp/libvips解码同一SVG，再交给原`designPng`画布/序列化流程。只改忽略验收环境，未修改产品函数或降低核验阈值；这些服务端绘图库问题不宣称为浏览器/产品缺陷已修复。

### 实际文件与独立读回

最终目录：`work/vortex-scales-20261012/export-readback/server-svg-raster/`。

| 文件/项目 | 实际读回 | 本轮结论 |
| --- | --- | --- |
| `vortex-scales.svg` | 29,141 bytes，60×60mm、viewBox `0 0 60 60`、144个真正的ellipse矢量、无嵌入image | 服务端文件输出PASS |
| SVG逐元素 | 144个ID、中心、rx/ry及绕同一中心的旋转与保存的权威geometry逐项一致，数值解析最大误差0 | PASS |
| `vortex-scales.png` | 133,421 bytes、1600×1600、RGBA、alpha0..255、四边透明；阈值128的8邻域连通图形恰好144个 | 服务端文件输出PASS |
| PNG逐元素 | 144个连通图形逐个匹配权威中心、宽深与长轴角度；最大中心误差0.00373623mm、矩估计宽深误差0.01721175mm、180°等价旋转误差0.205585° | PASS，仅栅格对照，非制造Validator阈值 |
| 默认孔洞 | 当前144元素都是椭圆，没有孔洞 | N/A，不虚构旋涡默认含孔样本 |
| 独立孔洞对照 | 复用已有P1`imported-effect.json`保存的正式结果，5元素、非零viewBox `10 20 60 40`；另输出`existing-hole-control.svg/png` | 本输出链的已测带孔对照PASS；不是旋涡变体或历史缺失原作品 |
| 孔洞语义 | path保留`fill-rule="evenodd"`及多个闭合子路径；1600×1067 RGBA PNG中孔中心alpha0、外环实体采样alpha255 | PASS，不扩大到未测Arc/Skew/通用曲线等OPEN |

SVG SHA256：`8bd3887af1316009010f87ef967d25aad0f6718612ec3171ada38927b42245ba`；PNG SHA256：`649fdd83d68c35fceadec22d14791c8db4e598004e38d6e58cac6a91dd108b09`。

执行记录：`D:/node.exe work/vortex-scales-20261012/export-readback/export-files.mjs`最终exit0；现有`.venv/Scripts/python.exe work/vortex-scales-20261012/export-readback/read-files.py`最终exit0。后者独立从磁盘解析XML/PNG，不请求服务或重新求值，保存144条矢量及144条栅格读回记录。首次读回因验收环境无SciPy停止，随后仅改忽略脚本用标准库8邻域分组；没有安装依赖。`generation-evidence.json`、`readback.json`记录文件路径/hash/输入身份与全部数据；两次native解码失败的文件在父目录及`hires/`保留，诊断分别为`initial-raster-readback-failure.json`、`native-hole-control-failure.json`。

### 当前逐项状态

| 项目 | 当前状态与证据边界 |
| --- | --- |
| 核心、定向测试、构建 | PASS，直接复用前次证据，本次未重跑 |
| 普通/Fabric STL制造及读回 | 限定样本PASS，原文件/证据不变，本次未重做 |
| SVG及透明PNG文件输出/读回 | 服务端执行正式Web输出适配器：限定样本PASS；不是浏览器下载PASS |
| 默认及宽疏浏览器截图、候选与Cancel | 保留已取得的限定证据 |
| 反向密集变体及剩余顺逆/中心视觉 | 用户待确认；Python既有数值测试PASS不代替视觉 |
| 完整浏览器Apply/Undo/Redo/Reset、已应用变体刷新/返回、跨7套切换 | 独立证据未取得，保留待用户试用；已有自动化测试结论不扩大 |
| 旋涡用户试用确认 | 用户于本地收口前审核明确确认操作正常：用户手动试用PASS；未提供逐项独立操作证据，不替代其余待验收项目 |
| 浏览器SVG/PNG点击下载 | NOT TESTED，未重试超时工具 |
| 本批公网、Linux、切片、实物 | NOT TESTED；历史OPEN不变 |

本次唯一非运行产物修改为本验收记录。完整浏览器/用户视觉验收仍未关闭，等待用户试用反馈；不开始其他功能。

## P3两套本地收口前审核（2026-10-12，仅审核，等待提交授权）

### 当前状态与用户确认

- 工作区：`C:/Users/13524/Documents/Codex/2026-08-25/bw-lace-fabric-generator-plugin-bw-2/ParametricPatternGenerator`；分支`feature/pattern-library-reuse`；完整HEAD`1a8d28de800471074c47bc773fc942876cd2d56a`，与本轮基线一致。暂存区为空，8个已跟踪修改、40个未跟踪文件（8个P3正式新增＋32个历史探查脚本），没有删除文件。本轮只有本记录与Gate摘要的审核/用户确认补充，没有产品改动。
- 用户本轮明确确认数字织格、旋涡鳞纹本地操作正常：**两套用户手动试用PASS**。这是用户报告的实际操作结果，不等于取得每项独立录屏、鼠标激活、Reset、变体刷新/返回或跨全部预设切换证据。前述自动控制超时及历史BLOCKED事实保留，不能把试用确认反写为当时已通过。
- 保留现有worktree，不切换、不清理；暂存、提交、备份创建、push/deploy均未执行。`git branch --list backup/web-pattern-presets-p3-local-validated`无结果，建议名称当前不存在，**本轮仅检查、未创建**。

### 实现与证据核对

- `patternPresets.ts:58` / `openPatternPreset`：完整Checker/Spiral参数、首次初始化中心/偏移与native anchor、毫米比例一次换算、同配方读取/Reset；`createPatternPreset:220`使用正式Grid生成10×10矩形或12×12椭圆，不在JS重写场算法。`patternPresetCandidate:180`仍是候选组装，不分别产生历史提交。
- `presetDualBinding.ts:9/18/39`：`dualOwner`记录Size与Rotation ID；`assertDualSafe`明确拒绝旧非中性隐式旋转/后置位置语义；`applyDualBinding`把两个消费者绑定同一专用场、复用旋转ID，专用场被外部使用时由现有尺寸候选复制并同步重绑两层。
- `editor.ts:13`及`linearSize.ts:189`：引用扫描仅排除自身两个受管消费者/归属metadata，不排除用户独立Modifier、其他Field或Fabric引用；旧单消费者调用兼容。`linearSize.ts:223`保留旋转归属供跨预设复用。没有更改公共DTO或第二套持久化。
- `patternPresets.ts` / `preparePresetSwitch`：离开双绑定预设时只停用受管旋转、把受管Size映射恢复下一配方所需语义，不删除共享场。返回双绑定复用已有旋转ID；切到精密错列仍需明确创建新作品，不授权覆盖导入Layout。Reset作用于声明的受管参数，未改原图/Fabric/其他用户效果。
- `App.tsx:713/1233/1321/1330`：应用当前作品明确提示全图旋转；同一候选/ParameterInteraction/高级旋转面板/Reset入口；返回作品仍取真实有效上下文（`canReturnBeforeProject:899`），不依赖预设身份。本批没有改草稿、请求协调器或制造服务。
- `PatternPresetPicker.tsx`真实导入两份新增SVG。两份正式fixture与此前各自保存的`standard-source.json`完整一致；JSON使用当前schema_version1.0、field-1分别被受管Size和Rotation引用。原始9圆点数组是Grid输入快照，不以其代替最终100/144几何，正式求值链已有测试与制造证据覆盖。
- 静态XML对照：缩略图分别100个rect、144个ellipse、无嵌入image；ID、中心、宽深和旋转与保存的权威Evaluate数组匹配。沿用foundation缩略导出8位小数，最大位置/半径舍入误差4.996875e-9、旋转/中心舍入误差4.750547e-9，未改导出精度或Validator。初次审核以1e-9作完全匹配断言过严，核查`svg_exporter.py:_number`的已有8位格式后按其固有舍入边界核对；不是新的产品回归。
- 四份现有STL存在且SHA256与原`evidence.json`一致：数字织格两份各60,084bytes、旋涡两份各406,484bytes。只校核文件身份/保存结果，未重做制造或几何读回；原100/144组件、Z0..2、水密/正体积/零退化等限定PASS不扩大。
- 全部已跟踪差异均属于P3接线、测试或记录；新增正式文件均属于同阶段。`git diff --quiet HEAD -- web/package.json web/package-lock.json xiaomang_pattern_lab/requirements.txt xiaomang_pattern_lab ppg/foundation web/src/model`返回0：无新依赖、Python算法/制造链/Validator、公共model或生产配置改动。未恢复旧补丁。
- 复用已有测试：数字织格核心24/24历史日志`digital-core-final.log`；旋涡核心3文件28/28、App2文件12/12、最后相位/说明调整后2文件12/12及Python6/6、最终构建成功，按原批次记录，不累加重叠用例。本轮未重跑产品测试/构建；部分旋涡原始stdout在会话工具结果中，详细命令和覆盖范围已在前节记录，未虚构不存在的独立日志文件。最终`git diff --check`无错误，既有LF/CRLF提示不改变验收结论。

### 建议提交白名单：准确16文件（本轮未暂存）

产品实现/真实缩略图8份：

```text
web/src/App.tsx
web/src/document/PatternPresetPicker.tsx
web/src/document/editor.ts
web/src/document/linearSize.ts
web/src/document/patternPresets.ts
web/src/document/presetDualBinding.ts
web/src/document/patternPresetThumbnails/digital-weave.svg
web/src/document/patternPresetThumbnails/vortex-scales.svg
```

必要测试/可移植fixture6份：

```text
web/src/App.patternPresets.test.tsx
web/src/App.patternPresetsP2.test.tsx
web/src/document/patternPresetsP3.test.ts
tests/test_pattern_presets_p3.py
tests/fixtures/pattern_presets/digital-weave.pattern.json
tests/fixtures/pattern_presets/vortex-scales.pattern.json
```

真实验收及摘要2份：

```text
PATTERN_PRESETS_P3_LOCAL_ACCEPTANCE.md
GATE_STATUS.md
```

这些文件相互依赖，不建议只提交旋涡最后几份。`presetDualBinding.ts`及两份fixture必须纳入，否则引入的模块/可移植测试不完整。测试模块内显式`__main__`缩略生成辅助仅手动运行，常规pytest不自动写fixture；本审核未调用它。

### 明确排除：32个历史未跟踪探查脚本，全部原地保留

```text
tools/artwork_closeout_diagnose.py
tools/artwork_closeout_readback.py
tools/artwork_closeout_smoke.cjs
tools/field_size_readback.py
tools/field_size_smoke.cjs
tools/full_design_readback.py
tools/full_design_smoke.cjs
tools/gradient_handles_readback.py
tools/gradient_handles_smoke.cjs
tools/linear_size_readback.py
tools/linear_size_smoke.cjs
tools/original_shape_readback.py
tools/original_shape_smoke.cjs
tools/pattern_presets_readback.py
tools/pattern_presets_smoke.cjs
tools/phase1a_cells_only_readback.py
tools/phase1a_cells_only_smoke.cjs
tools/phase1a_live_manufacture_readback.py
tools/phase1a_live_manufacture_smoke.cjs
tools/phase1a_local_smoke.cjs
tools/phase1a_readback.py
tools/svg_final_acceptance_readback.py
tools/two_step_native_readback.py
tools/two_step_native_smoke.cjs
tools/two_step_reference_probe.cjs
tools/unit_cell_selection_readback.py
tools/unit_range_readback.py
tools/unit_range_ui_layout.cjs
tools/unit_range_ui_smoke.cjs
tools/unit_shapes_benchmark.py
tools/wave_recipe_1b_readback.py
tools/wave_recipe_1b_smoke.cjs
```

另外排除既有忽略运行目录：`work/pattern-presets-p3-20261011/`、`work/vortex-scales-20261012/`及其他work（截图、STL、PNG/SVG下载、日志、临时探针、源码快照）；`web/dist/`、node_modules、Python运行时/缓存、旧backups等继续按现有规则处理，不修改.gitignore、不删除。真实缩略SVG与测试fixture属于上面的正式16文件，不与运行输出混淆。忽略的验收证据不会随源码提交自动备份；它们继续保留本机路径，本记录不宣称Git包含运行产物。

### 剩余风险与收口建议

- 本地用户试用及已测制造/二维输出限定PASS支持准备本地提交，但不等于完整独立浏览器矩阵PASS。旋涡反向视觉、任意不对称轮廓的相位连续性、剩余Reset/刷新/返回/跨全部预设的独立界面证据继续保持未取得；不自动复跑超时浏览器。
- 默认椭圆/矩形的180°外形等价不能推广到不对称SVG；高级bell旋转仅数值验证，任意作品的视觉/制造仍需逐样本验收。棋盘采样点可能同相位，需手动调整格子尺寸/偏移，不自动重排作品。
- 两个双绑定预设的旋转是全图，尺寸局部区不限制旋转；界面已明确提示。旧非中性堆栈/后置位置场会准确拒绝，不自动迁移。数值松手/确认后更新、未应用表单/旧Undo刷新边界、单份返回上下文、其他历史OPEN及既有warnings不变。
- 旋涡SVG/PNG本次服务端适配器读回PASS不是浏览器下载证明；服务端Canvas/SVG解码器的两次验收环境失败及最终准确输出均保留。源码没有因此引入新生产绘图库。
- 本批公网、Linux、切片、实物未验收；不创建Physical/Production标签。建议稳定备份名`backup/web-pattern-presets-p3-local-validated`，当前不存在，仅在用户后续明确授权、16文件提交核对成功后创建。现有稳定引用不移动。

**审核结论：建议按16文件白名单等待用户批准本地收口；本轮未发现新增产品阻塞，未实施新功能或修复。**

## 当前结论

数字织格、旋涡鳞纹用户手动试用PASS；数字织格此前候选/应用/Undo/Redo/SVG/PNG限定证据保持有效，正式后端普通/Fabric STL文件制造读回限定样本PASS。旋涡定向测试/构建/代表性正式后端STL读回PASS，默认与宽疏浏览器截图及Cancel已取得，服务端SVG/透明PNG真实文件输出及读回限定样本PASS。两套的未取得独立浏览器证据不因总体用户确认改为PASS；旋涡反向视觉、浏览器下载和剩余完整交互仍按各自边界保留。审核建议16文件白名单，等待用户批准提交/备份。本轮无提交/新稳定引用/push/deploy；两套均不宣称全项、公网、Linux或实物通过，全部旧修改/工具/历史OPEN保留，STOP。
