# 真实作品综合验收与本地收口（2026-10-10）

## 结论：BLOCKED，未收口

本轮真实作品验收发现不规则SVG的路径Bounds/元素锚点错误。按照用户“发现阻塞即停止收口”的授权边界，未修改产品、未暂存/提交、未创建新稳定备份，等待批准最小修复。浏览器操作成功、HTTP200、网格校验通过，均不替代作品作用范围语义正确；不把本轮标为全部PASS。

- 实际工作区：`C:/Users/13524/Documents/Codex/2026-08-25/bw-lace-fabric-generator-plugin-bw-2/ParametricPatternGenerator`。
- 分支：`feature/pattern-library-reuse`；开始/结束HEAD均为 `4a1c799255ca71002dc4cd9bae88e38ef0fea69e`；暂存区始终为空。
- 保留全部原13个tracked修改、前批新实现/测试/fixture/记录、22个旧探查脚本。本轮只增加验收工具/记录及Gate状态，没有恢复旧补丁、清文件、reset、提交、推送、部署、新依赖或线上配置变化。
- 原 `backup/web-phase1-complete-local-validated`（4a1c799…）、`backup/web-native-design-local-validated`（dd16f64…）保留、不移动。新稳定备份：未创建；最终新提交：无。
- 本轮源码保护ZIP：`work/artwork-closeout-20261010/source-before.zip`；它是局部源码保护，不等于Git稳定引用或运行环境备份。

## 当前运行证据

复用上轮本地8800项目服务，未另启后端、未重启用户服务。独立Edge/IndexedDB context，保护用户草稿。

- 实际URL：`http://127.0.0.1:8800/`，API same-origin。
- 前端资源：`/assets/index-BeMizbJw.js`，同上轮已构建并定向验收的未提交源码产物。
- 后端进程30944：当前工作区standalone Python，项目`.venv`启动的Uvicorn `xiaomang_pattern_lab.web.app:create_app`；health运行提交仍为UNKNOWN，不能用HEAD冒充未提交运行身份。
- health：staging，preflight/final_mesh/test_export均true。沿用已有本地测试权限，没有改环境配置或Production权限。
- 本轮产品代码未发生变化，因此引用上轮Web91、补充14（重叠）、Python60+2子测试、独立导入4+5子测试、build；没有再跑无关Tk/全量回归。

## 三类作品与观察

| 类别 | 实际输入与调整 | 本轮结论 |
| --- | --- | --- |
| 规则图案 | 原生Grid48圆，80×60mm画板、非零原点5/10；调整7×9=63、间距7.5mm/错列、尺寸105%、宽扁1.15、旋转8°、尺寸随机.06/错位.12mm/seed81；Wave Size波长23mm/映射.8–1.15＋三影响区；画板85×65mm | 大小与错列形成清楚但适中的节奏，无大面积重叠。三种独立范围有inside/outside，outside完整不变；应用、Undo/Redo、刷新恢复及输出检查通过相应步骤 |
| 不规则导入 | 真SVG文件上传，5对象：圆、椭圆、圆角矩形、带孔区域、L形；保留Free，不自动排列；尺寸90%、宽扁1.05、旋转2°、同seed随机；定向放置三种影响区；画板65×45mm | 轮廓/孔仍显示，文件可下载；但可见带孔图形的中心与正式元素锚点不一致，放在可见图形上的椭圆范围没有命中，作品级范围验收FAIL |
| 3D纹理 | Grid48元素，已有Fin3.2×1.8×3mm/Pattern Points/Follow Pattern/仅单元；公共二维随机/尺寸/三影响区；Wave Height波长23mm/方向35°/2–6mm；仅单元→Solid→仅单元 | 默认和调整后的真实WebGL截图有清楚高低变化、整体布点保留、没有隐式换Pyramid或加板；模式切换正确stale、Undo/Redo/刷新恢复、文件严格几何读回通过。整体作品冻结仍被不规则案例阻塞 |

视觉观察为本轮实际截图检查，不是任意图案“美观认证”或真实用户易用性研究。参数解释、右侧字段可见；不借收口做UI微调。数值仍为确认/松手更新，未声称逐帧实时。

### 默认与调整后截图（实际浏览器）

- 规则：[默认](C:/Users/13524/Documents/Codex/2026-08-25/bw-lace-fabric-generator-plugin-bw-2/ParametricPatternGenerator/work/artwork-closeout-20261010/regular-default.png)、[调整后](C:/Users/13524/Documents/Codex/2026-08-25/bw-lace-fabric-generator-plugin-bw-2/ParametricPatternGenerator/work/artwork-closeout-20261010/regular-adjusted.png)。二维调整后在刷新恢复后拍摄，重新Fit导致缩放11.53→11.91px/mm，不伪称严格同缩放。
- 不规则：[默认](C:/Users/13524/Documents/Codex/2026-08-25/bw-lace-fabric-generator-plugin-bw-2/ParametricPatternGenerator/work/artwork-closeout-20261010/imported-default.png)、[调整与影响区](C:/Users/13524/Documents/Codex/2026-08-25/bw-lace-fabric-generator-plugin-bw-2/ParametricPatternGenerator/work/artwork-closeout-20261010/imported-adjusted-candidate.png)。后一张是明确未应用候选，不冒充正式结果；正式结果另存`imported-adjusted.png`。
- 纹理：[默认](C:/Users/13524/Documents/Codex/2026-08-25/bw-lace-fabric-generator-plugin-bw-2/ParametricPatternGenerator/work/artwork-closeout-20261010/texture-default.png)、[调整后](C:/Users/13524/Documents/Codex/2026-08-25/bw-lace-fabric-generator-plugin-bw-2/ParametricPatternGenerator/work/artwork-closeout-20261010/texture-adjusted.png)。同一持久renderer、相机保留；没有用相机缩放伪造尺寸/高度变化。

## 阻塞的真实数据链

输入：`tests/fixtures/full_design_holes.svg`内带孔路径：

```text
M 30 85 H 50 V 105 H 30 Z M 35 90 V 100 H 45 V 90 Z
```

| 核对项 | 正确路径事实 | 当前导入记录 |
| --- | --- | --- |
| native Bounds (xmin,ymin,xmax,ymax) | (30,85,50,105) | (30,35,90,105) |
| .5mm/单位下中心mm | (20,47.5) | (30,35) |
| 实际宽高mm | 10×10 | 30×35 |

- 首个错误：`ppg/foundation/svg_normalizer.py:412 _path_bounds()`只提取所有数字并按两个一组配XY，忽略`H/V`命令单坐标语义。该路径的数字被错误配成(30,85)/(50,105)/(30,35)/(90,100)/(45,90)，正好得到错误Bounds。
- `SVGNormalizer.normalize_file()` → `_filled_region_element`（349行）将错误Bounds写成x/y/width/height及base_x/base_y/base_width/base_height；这不是新影响区布尔判断造成的字段丢失。
- 现有 `region_geometry.path_subpaths()`真实解析M/L/H/V等，得到正确闭合外环/内孔；图形能画出，不等于其锚点正确。
- Python正式Size影响区按本层输入元素x/y取权重。仅启用椭圆时，范围中心(20,47.5)mm、直径14×12mm、过渡1mm；带孔元素当前锚点(29.9131,34.9856)mm。实际5个元素权重均0，尽管截图椭圆覆盖可见带孔区域。
- 验收失败：`artwork_closeout_readback.py:77`断言该范围应同时有inside和outside，实际 `('imported','ellipse',[0,0,0,0,0])`；退出1。没有换样本、改范围绕过、删除断言或把空命中说成正常视觉PASS。
- `git diff -- ppg/foundation/svg_normalizer.py`为空；`git show HEAD:...`中的同一函数与当前一致，证明该错误实现已在本轮基线中，但历史是否曾被用户触发UNKNOWN。本轮首次取得精确作品证据。
- 原技术验收检查了矢量/文件/部分尺寸，不足以证明导入锚点语义正确。以前仅在DTO x/y取透明像素不能代替真实孔位核验；本轮已按真实内环几何中心取PNG透明像素，孔仍保留，但不因此关闭锚点缺陷。

## 最小修复建议（未实施）

1. 仅在SVG已有路径规范化入口，针对已支持的路径命令复用现有`region_geometry.path_subpaths`结果计算真实Bounds；避免将H/V数值错配为XY。不新造路径引擎、不改共享Field/影响区算法。
2. 补多子路径H/V、相对h/v、孔洞与等价M/L写法的导入Bounds/center测试；用同一当前样本再做范围命中、围绕真实中心缩放/旋转、SVG/PNG/STL对照。
3. 旧保存作品可能已经持久化错误base_*。不能静默重算覆盖既有变换；旧数据处理需明确确认。首轮可限定正确新导入及明确重导入验收，旧档不自动迁移。

预期最小文件范围：`ppg/foundation/svg_normalizer.py`、对应SVG导入/Bounds定向测试；当前已有fixture及本轮验收工具复用。若需要更大的旧档修复/migration，先另报范围。当前未修改上述产品文件。

## 已下载与读回：不代替整体作品PASS

真实浏览器保存11份文件（每类SVG/PNG各一份＋5份STL），没有代用品/修复/删坏面。

| 文件 | 读回事实 |
| --- | --- |
| regular-design.svg/png | 真63矢量、85×65mm、viewBox5/10/85/65；PNG1600×1224 RGBA透明 |
| imported-design.svg/png | 真5矢量、65×45mm、viewBox10/20/65/45；PNG1600×1108 RGBA透明；真实内孔中心(20.813879,45.080575)mm alpha0 |
| texture-design.svg/png | 真48矢量、85×65mm；PNG1600×1224 RGBA透明；属于已应用二维图，不冒充3D纹理图片 |
| regular-standard.stl | 186684bytes/3732三角面；67.533407×48.291249×2mm；63组件 |
| imported-standard.stl | 10084bytes/200面；32.326788×23.186455×2mm；5组件；孔/轮廓仍在，但锚点语义错误尚未修正 |
| texture-cells-only.stl | 19284bytes/384面；60.214244×42.414375×5.999341mm；48组件，Z0 |
| texture-solid.stl | 29484bytes/588面；63.232394×46.935896×6.599341mm；1组件，Z0 |
| texture-cells-return.stl | 同仅单元字节/尺寸/体积；48组件，Z0 |

5份STL由原STLExporter读回＋严格MeshValidator，均finite/watertight/正体积/绕序一致/0退化；不自动repair。两种纹理模式Plan的XY/旋转/宽深/逐实例Height/enable保持，Solid仅Z基准+.6mm、实体基底按对应语义加入。普通二维与仅单元不强制单组件。

完整跨作品几何读回因上述inside断言停止，不能把单独文件拓扑通过当作全部逐元素/语义通过。成功子证据与阻塞一起保留。

## 本轮命令、实际结果与文件范围

```powershell
$env:PLAYWRIGHT_MODULE='C:/Users/13524/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'
node tools/artwork_closeout_smoke.cjs
& ./xiaomang_pattern_lab/.venv/Scripts/python.exe tools/artwork_closeout_readback.py
& ./xiaomang_pattern_lab/.venv/Scripts/python.exe tools/artwork_closeout_diagnose.py
```

- 最终浏览器UI操作会话：规则35POST、不规则49POST、纹理53POST，各自全部200、pageerror0、evaluate max在途1；Apply/Undo/Redo/正式文档/geometry刷新同值。纹理切输出stale、Undo/Redo、恢复正确。脚本UI状态PASS不等于作品验收PASS。
- 完整readback：FAIL退出1（不规则ellipse权重全0）。诊断脚本退出0，明确输出`BLOCKED_NO_FREEZE`及数据，不是假成功。
- 只引用此前当前产品代码测试/构建，没有重复无关全量或增加生产依赖。
- 中途验收脚本曾误等普通制造模式不存在的右侧“设计预览已就绪”文本、以及把二进制STL POST观察为JSON/在reload前未排空响应读取；只修脚本观察条件/读取时序，未改产品保护或吞pageerror，最终会话无此错误。
- 本轮新增：`tools/artwork_closeout_smoke.cjs`、`tools/artwork_closeout_readback.py`、`tools/artwork_closeout_diagnose.py`、本记录；仅修改`GATE_STATUS.md`添加BLOCKED记录。其他产品/测试/旧未提交成果本轮不改，不暂存任何文件。
- 全部截图/DTO/HTTP/文件/`blocker-evidence.json`在`work/artwork-closeout-20261010/`，运行产物按既有忽略规则留原地，不删、不加入Git。
- 本轮最终提交SHA：无新提交（HEAD仍4a1c799完整SHA见上）；新稳定备份：未创建。所有本批/前批修改及无关22旧脚本仍留工作区。
- 最终Git状态：13个tracked修改、47个untracked文件、0暂存。tracked为GATE_STATUS.md、App.tsx/App.linearSize.test.tsx/App.phase1a.test.tsx、linearSize.ts/parameterSchema.ts、localDraft.ts、Workspace2D.tsx/gradientControls.ts/styles.css、evaluation.py/parameter_definitions.py/shared_fields.py；除Gate记录外均是开工前已存在的成果。untracked包含两批产品实现/测试/Schema fixture/记录/验收工具、本轮3工具和本记录，以及22个旧工具；全部未提交，不被稳定Git引用保护。
- 剩余：curve128段近似、数值松手更新、pending与旧Undo刷新边界、混合追加/旧隐式堆栈限制、bundle/Starlette warning、旧8792原页OPEN继续保留。公网/Linux/切片/实物NOT TESTED。

停止，待用户批准上述最小锚点修复，不进入下一功能、不擅自修复或冻结。
