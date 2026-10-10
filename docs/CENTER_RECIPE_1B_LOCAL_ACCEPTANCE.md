# 1B 中心隆起与原图兼容 — 本地验收（2026-10-10）

## 状态与授权边界

- 分支 `feature/pattern-library-reuse`，HEAD `dd16f64aab07e894cdc09218c56a416579b45203`。当前成果未提交，不是该HEAD已包含的实现。开始暂存区为空，27个tracked修改及所有既有untracked成果保留。
- 修改前5份源码副本：`work/center-height-1b-20261010/source-before/`。未reset/clean/恢复旧补丁/提交/推送/部署/修改生产配置/增加依赖。没有开展第四套配方。
- 独立本地生产页面 `http://127.0.0.1:8797/`；当前工作树 `.venv`、FastAPI factory、`web/dist`，服务PID27464。仅该测试进程沿用既有 `XIAOMANG_ENV=staging` / `XIAOMANG_FABRIC_STL_TEST_EXPORT=1`。没有杀用户应用或覆盖用户草稿。
- 独立Edge/IndexedDB会话，真实WebGL，前端产物 `index-flDVYUfN.js`。健康信息后端运行提交为UNKNOWN，未以未提交工作树HEAD冒充运行身份。不是公网/Linux/切片/实物验收，未创建Physical备份。

## 实际复用与最小修改

| 文件 | 修改与复用 |
| --- | --- |
| `web/src/document/fabricModifiers.ts` | 现有version1高度归属映射增加ring，复用引用扫描/copy-on-write/一次派生revision；`centerHeightDefaults`、`setCenterFabricHeight`使用正式Ring/Height Schema。首次明确中心及范围保存在现有owner metadata的`center_defaults`，Reset和再次进入不重新取变化后的bounds。 |
| `web/src/document/fabricPresets.ts` | `center-height`v1；共用`applyFabricHeightRecipe`，三套主要高度方案只管理height及自己的field；保持现有造型、原图倍率、输出/base/placement/其他效果。旧明确造型替换预设及其函数保留，不自动迁移历史文档。 |
| `web/src/App.tsx` | 三套高度配方共用现有保存保护、一次commit、pending Layout保留、快捷表单边界；中心参数回调沿用正常编辑、自动轻量预览与旧结果失效。 |
| `web/src/manufacturing/ManufacturingPanel.tsx` | 中心配方/Reset/高度模式入口；中心X/Y、影响半径、最低/最高高度；范围控件由实际ring_width Schema换算为半宽，不创建另一套参数。明确松手/确认更新与范围外最低高度语义。 |
| `web/src/test/phase1aFixture.ts`、`web/src/App.phase1a.test.tsx` | Ring目录、中心save failure/commit/Reset/Undo及pending Layout连接测试。 |
| `web/src/document/fabricCenterRecipe.test.ts` | 11个新增用例：原图/单元保持、4类共享引用隔离、稳定默认及Reset/draft、三套切换、非法输入。 |
| `tests/test_fabric_center_recipe_1b.py` | 9个新增数值/变换/模式/孔洞/宽窄偏心用例；调用既有Python核心，没有修改生产算法。 |
| `tools/center_recipe_1b_smoke.cjs`、`tools/center_recipe_1b_readback.py` | 真实生产浏览器/HTTP/下载、实际文件严格读回，逐元素完整顶点、XY/旋转/相对尺寸/高度/孔洞检查。不生成替代STL，不repair。 |
| 本文及`GATE_STATUS.md` | 最小本地证据与限制记录。 |

## 算法和参数语义

- 原有 `shared_fields.py:RingField.evaluate`：`max(0,1-abs(distance-radius)/(ring_width/2))**falloff`，支持invert。已有正式Schema允许radius=0。
- 本配方固定radius=0、falloff=1、invert=false：`value=max(0,1-distance/R)`，R=ring_width/2。真实数值测试R20mm：中心1、10mm处0.5、边界20mm和范围外25mm处0。
- Height消费者仍使用 `min_height_mm+(max_height_mm-min_height_mm)*value`。边界/外围最低高度，不删图案；逐元素采样，不生成单轮廓内部连续曲面。
- 默认中心是最终二维几何毫米bounds中点，R是半对角线；仅无bounds时沿用既有canvas/mm映射作为回退。初始化后保存明确参数，后续编辑不跟随相机、求值变化或单位比例再次缩放。
- 配方身份、version1、units mm、scope(height/owned_height_field)、field ID/type/full parameters、Height绑定及范围、确定性seed=null存于现有metadata。完整Fabric配置和二维图案继续在同一PatternDocument内。没有隐藏图片、第二项目格式或新算法。
- 原图保留真实最终轮廓/孔洞，使用已确认的逐元素原型与高度链；单元使用已有最终实例计划。仅图案Z=0，允许真实有效多组件；带基底保留连接/融合和组件要求。

## 四种视觉与尺寸证据

同一100元素规则点阵，含1个真实孔洞、已应用二维Size/Rotation；Canvas 120×80源单位，原点20/40，mm_per_unit=0.5。仅图案、原图倍率100%、默认实体显示样式、同一相机视角。实际最终bounds不机械等于canvas60×40mm。

| 截图（均在`work/center-height-1b-20261010/`） | 中心mm | 影响半径mm | 高度范围mm | 实际实例高度mm | 观察 |
| --- | --- | --- | --- | --- | --- |
| `center-default-original.png` | 40.270416 / 41 | 34.731044 | 2–6 | 2.236761–5.610276 | 中心较高，向外降低；保留100实例 |
| `center-broad-original.png` | 同上 | 55 | 2–6 | 3.623614–5.753900 | 外围抬高，坡更缓 |
| `center-narrow-original.png` | 同上 | 11 | 2–6 | 2–4.769499 | 中部少数较高，范围外保持2mm |
| `center-offcenter-original.png` | 26.270416 / 47 | 23 | 2–6 | 2–5.779058 | 峰位置向左上移，原有元素点位不移动 |

- 离散点阵没有中心样本，最高实例不强行等于6mm；逐项用实际实例坐标检查。
- `center-fin.png`：Fin2×1mm、跟随二维相对大小、100实例；Height同一Ring，XY/旋转/尺寸继承与该Fin的关高度基准一致。截图直接读取核验；本机vision skill的glance CLI未安装，未伪报其调用结果。

## 状态、请求与三套切换

- 同一独立浏览器完成：方向→波浪→中心→方向→中心，分别在原图与Fin模式验证。造型来源/单元/原图倍率/输出/base/placement/二维elements/modifiers/transforms保持；每类型专用field ID复用，无重复层。原有用户二维场不借用。
- 每次数值确认或配方应用1revision/1evaluate/1preview，未提交输入不修改revision；参数动作0fusion。最终成功会话56个POST全200，其中3次fusion及3次真实STL下载。按钮状态/下载stale保护保留；不据此宣称历史429或原8792页面已经关闭。
- Reset恢复首次保存的中心/范围及2–6mm，1commit；Undo恢复编辑前完整图，Redo恢复Reset，未重排/换造型。刷新恢复完整DTO/引用/效果，旧Undo历史重新开始；未应用Layout保留测试通过，未应用快捷二维表单仍须先应用/取消。
- 4类共享引用（二维modifier、其他Fabric消费者、Composite、legacy）copy-on-write；原共享场及消费者不修改。save失败阻止配方替换；未改变请求槽/429解析/序号/旧响应逻辑。

## 真实下载与严格读回

| 浏览器实际文件 | bytes / triangles | XYZ mm | 组件 |
| --- | --- | --- | --- |
| `center-default-original.stl` | 61,084 / 1,220 | 56.954643×39.062065×5.610276 | 100 |
| `center-offcenter-original.stl` | 61,084 / 1,220 | 56.954643×39.062065×5.779058 | 100 |
| `center-fin.stl` | 40,084 / 800 | 55.866170×37.756287×5.610276 | 100 |

- 全部实际下载HTTP200、文件存在，既有STLExporter读取并通过MeshValidator：水密、有限、绕序一致、正体积、0退化面，底部Z=0。
- 每100个实体逐项验证完整原型变换顶点/轮廓与实际STL一致（容差1e-5mm），逐项Height独立用PythonRing在世界锚点求值对照；每个三角面恰好归属一个实例。原图hole组件Euler=0，真实孔保留；不是只看整个模型maxZ。
- Python9点Solid带基底原图/Fin严格读回为1组件，仅图案为9组件，height/XY/scale/rotation一致；本轮带基底浏览器下载未重新执行。Grid连接与普通STL复用此前有效原图验收及本轮原图回归，不扩展成所有模式单组件约束。

## 定向测试及真实限制

- 最终Web：`npm test -- src/document/fabricCenterRecipe.test.ts src/document/fabricWaveRecipe.test.ts src/document/fabricOriginal.test.ts src/document/fabricModifiers.test.ts src/document/fabricPresets.test.ts src/App.phase1a.test.tsx src/manufacturing/outputClassification.test.tsx src/manufacturing/unitCellSelection.test.tsx src/manufacturing/computeRequests.test.ts src/manufacturing/FabricFusionPanel.test.tsx src/manufacturing/FabricPreflightPanel.test.tsx`：11文件、80/80 PASS。先前35/37批与此重叠，不累加。
- Python：`.venv/Scripts/python.exe -m pytest tests/test_fabric_center_recipe_1b.py tests/test_fabric_wave_recipe_1b.py tests/test_fabric_original_shape.py -q`：34/34 PASS，包含新增9；没有跑无关Tk全量。
- `npm run build` PASS，同一浏览器产物index-flDVYUfN.js；既有bundle较大warning不处理。`git diff --check` PASS，CRLF提示保留。
- 实际下载读回：进程级PYTHONPATH设置为项目目录后，`.venv/Scripts/python.exe tools/center_recipe_1b_readback.py` PASS。仅进程环境，不改部署配置。直接脚本初次缺少PYTHONPATH报ModuleNotFoundError，未安装新依赖。
- 浏览器中间失败如实记录：固定fixture把rect的rx/ry带进FilledRegion导致422（只修验收样本）；测试fill先于控件focus恢复精度导致字符串追加，修脚本先真实click/focus再fill并校验数值；首次测试漏context/center Reset selector及TS includes窄类型已修正。没有据此改几何算法、阈值、删除面或自动repair。
- 复用前两套历史有效视觉/制造证据：`docs/WAVE_RECIPE_1B_LOCAL_ACCEPTANCE.md`及`docs/ORIGINAL_SHAPE_LOCAL_ACCEPTANCE.md`；本轮只补中心和三套形状兼容证据。历史旧非中性隐式效果不自动迁移，混合独立图形追加、未应用快捷表单刷新与Undo历史边界保持原样。
- 本轮范围内：**1B本地验收完成**。未提交/未上线；公网、Linux/Render、切片、实物NOT TESTED，不宣布Physical/F5 CLOSED。不实施第四配方，停止等待用户确认。
