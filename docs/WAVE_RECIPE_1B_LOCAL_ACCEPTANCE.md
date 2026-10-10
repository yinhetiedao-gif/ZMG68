# 1B 波浪起伏完整配方 — 本地实施与验收（2026-10-09）

## 状态与授权边界

- 实际分支 `feature/pattern-library-reuse`，开始及结束 HEAD 均为 `dd16f64aab07e894cdc09218c56a416579b45203`。新功能未提交，不是该 HEAD 已包含的成果。
- 开始暂存区为空，已有16个tracked修改和前序测试/验收脚本未跟踪；全部保留。上一批单元/范围/目录选择尚未本地提交，8792原用户页鼠标确认仍OPEN，不以本轮独立浏览器代替其收口。
- 源文件修改前副本在 `work/wave-recipe-1b-20261009/*.before`。没有reset/clean、恢复旧Dot补丁、创建/移动备份、push、部署、生产配置修改、新依赖或新Python生产算法。
- 本轮检查时8792/8793均没有监听。独立测试服务为 `http://127.0.0.1:8795/`，运行当前工作树 `xiaomang_pattern_lab.web.app:create_app`、生产 `web/dist`。只给该测试进程使用现有local staging/test-export能力，不改文件配置。进程12124，后端运行提交可靠身份仍UNKNOWN；生产JS为 `index-COZVmRCr.js`。
- 独立Edge浏览器上下文/独立IndexedDB，无用户原草稿覆盖。不是公网、Linux或实物验收。

## 最小实现与复用路径

| 文件 | 本轮修改 |
| --- | --- |
| `web/src/document/fabricModifiers.ts` | 现有高度专用场归属扩展为向后兼容的linear/wave ID映射；共用引用扫描和copy-on-write；新增Wave高度参数Schema验证/一次派生提交，不计算波浪算法。 |
| `web/src/document/fabricPresets.ts` | 新增 `waveFabricRecipe`、`applyWaveFabricRecipe`；复用当前Fabric配置、字段创建、高度绑定和正常DTO；旧五套预设保持原样。 |
| `web/src/App.tsx` | 既有save-before-replacement/commitDocument接入Wave；保留pending Layout；未应用二维尺寸表单不因切换工作区被删除，配方应用时提示先处理该表单，不偷应用或覆盖。 |
| `web/src/manufacturing/ManufacturingPanel.tsx` | 原方案区新增“波浪起伏”，应用前说明单元/布点变化；主控件波长/方向/最低/最高，相位/幅度/偏移/反转高级；Reset和恢复后的方案显示。 |
| `web/src/test/phase1aFixture.ts`、`web/src/App.phase1a.test.tsx` | Wave定义测试fixture及真实App连接/失败保护/Undo/slider/pending Layout/shortcut保护测试。 |
| `web/src/document/fabricWaveRecipe.test.ts` | 完整配方、用户场不借用、共享引用隔离、稳定ID、Reset/Undo/Redo/IndexedDB/legacy兼容/单位与参数拒绝。 |
| `tests/test_fabric_wave_recipe_1b.py` | 现有Python权威Wave→Plan→Candidate→Fusion→Exporter及不同单位、位置/尺寸/旋转、带/不带基底定向回归。 |
| `tools/wave_recipe_1b_smoke.cjs`、`tools/wave_recipe_1b_readback.py` | 独立实际浏览器操作/下载证据与实际交付文件读回；不生成替代STL。 |
| 本文、`GATE_STATUS.md` | 本轮真实证据与边界。 |

真正算法路径仍是：`shared_fields.WaveField` → `fabric_field_modifiers.apply_fabric_field_modifiers` → 现有 `FabricInstancePlan` → 现有候选/融合/严格校验 → `STLExporter`。预览与最终制造分离，Three.js不成为制造真值。

## 配方及参数语义

- ID `wave-height`，version 1，units mm；管理 `unit_cell / placement / height / owned_wave_field`。
- 默认方锥4.8×4.8×3mm、Follow Pattern、Pattern Points，保留用户二维相对尺寸/位置/旋转。选择方案但不应用时不新增场/不提交；应用前明确显示上述变化。
- 完整Wave参数：`wavelength=36mm, angle=0°, phase=0 radians, amplitude=1, offset=0, invert=false`；高度2–6mm；无随机算法，`random_seed=null`。
- `output_mode / base / scale / density / orientation / source / layout / 2d_modifiers` 保留当前选择和引用。现有legacy Fabric缺output_mode仍按带基底行为；仅新建Fabric配置默认cells_only，不强制Solid底板。base为范围/可选实体配置，不等于本轮偷偷生成实体基底。
- `web_fabric_recipe`记录配方身份、版本、作用范围和绑定/参数；实际当前配置与场图仍在原PatternDocument/FabricConfig中，走现有serializer/IndexedDB，不创建第二套项目格式。
- 波长是世界mm，不是频率或像素长度；Fabric在最终 `x_mm/y_mm` 采样，不重复乘mm_per_unit。相位按弧度，方向按度；场沿世界原点投影，没有算法不存在的“中心”控件，不随镜头改变。
- 实际Wave为 `offset + amplitude/2*(sin(2π*projection/wavelength + phase)+1)` 后clamp/invert；Height映射至min/max。本说明只描述现有Python语义，React不实现它。
- 数值/滑杆沿用ParameterInteraction：松手或确认后一次commit和权威自动预览，不宣称拖动逐帧实时，不跑最终制造。

## 归属、Reset和作品保护

- `web_fabric_height_effect` version仍1，兼容历史 `field_id`，可选 `field_ids.linear/wave` 保存独立ID；切换方向/波浪/均匀可复用各自ID，不按类型借用户场，不每次预览新增。
- 复用 `fieldReferencedOutside`：其他二维modifier、Fabric消费者（包括disabled）、Composite或legacy引用时复制隔离；原场及引用保留，编辑新owned场。四种共享关系均测试。
- Apply/Reset先保存当前草稿，失败保留作品并提示；正常一次commit、一条Undo。Reset恢复受管单元/布点/完整Wave与高度范围，仍保留当前输出/基底和范围外效果，不删除其他对象使用的场。
- pending Layout保留且不应用，之后正常Apply仍保留Wave图。未应用二维尺寸快捷表单在模式切换后保留；配方按钮拒绝替换并指引先应用/取消。其刷新持久化和Undo历史边界仍未扩展。
- Reset/Undo/Redo/刷新恢复实际完整文档一致；刷新后Undo为空且已有提示，不新增历史持久化。

## 真实浏览器与视觉证据

固定输入：10×10点阵；60×60mm画布、源坐标原点(20,40)、0.5mm/源单位，对应世界原点(10,20)mm；最终二维圆形bounds为58×58mm，点距6mm；方锥宽深4.8mm；仅单元Z=0。区分画布、二维bounds和成品bounds，不机械等同。

同一默认视角/当前实体显示风格（无视觉重构）截图实际有WebGL模型，已查看：

| 方案 | 波长mm / 方向deg / 高度范围mm | 实际采样高度mm | 截图 |
| --- | --- | --- | --- |
| 默认 | 36 / 0 / 2–6 | 2.120615–5.879385 | `work/wave-recipe-1b-20261009/default-wave.png` |
| 长波缓起伏 | 120 / 0 / 2–6 | 3.283264–5.997259 | `work/wave-recipe-1b-20261009/long-wave.png` |
| 短波多排起伏 | 18 / 0 / 2–6 | 2.030384–5.285575 | `work/wave-recipe-1b-20261009/short-wave.png` |
| 斜向波浪 | 36 / 45 / 2–6 | 2.012449–5.995373 | `work/wave-recipe-1b-20261009/diagonal-wave.png` |

观察：默认周期高低行清楚，长波为单个缓坡/波峰，短波多排，斜向呈斜向波带。离散单元采样不保证命中连续曲线的理论极值，未伪称连续实体曲面或无采样限制。

已有二维渐变组合：使用当前 `gradient-grid.pattern.json` 的正式Linear→Size/Rotation图，尺寸0.6–1、旋转−15°–15°；加Wave前后每实例x/y/rotation/scale_x/y/cell_width/depth完全一致，只增加所选高度；用户场及modifier原样保留。截图 `combined-wave.png`、完整document/preview JSON和数值断言在同目录。Python另覆盖2D Position offset及0.5/2mm比例、非正方形/非零原点。

实际指针记录：波长slider12次mouse move，拖动0revision/0请求，松手1revision、1 `/evaluate` 和1 `/fabric/preview`（全部200），没有最终融合/STL请求。复用一冲突计算协调、旧响应/结果失效保护；相关自动测试包括staging_busy真实格式和draining guard。

浏览器Reset、一次Undo/Redo、草稿保存/刷新、刷新后Wave方案和控件恢复、修改后旧下载禁用均PASS；完整 `browser-evidence.json` 和五份document/preview JSON为证据。

## 实际下载与STL读回

网页真正点击“生成最终模型”与“下载测试 Fabric STL”，最终网格/下载HTTP200，文件存在。调用现有Exporter读回同一文件，未另造模型：

| 文件 | 大小 / 三角面 | XYZ mm | 模式与校验 |
| --- | --- | --- | --- |
| `default-wave.stl` | 30,084 bytes / 600 | 58.800001×58.800001×5.879385 | 仅单元，100组件、Z=0、水密、正体积、绕序一致、0退化 |
| `short-wave.stl` | 30,084 bytes / 600 | 58.800001×58.800001×5.285575 | 同上 |

每单元实际面组的XY中心/宽深/高度与相应preview实例逐项匹配；文件bounds与服务端final报告误差≤1e-5mm。无基底100独立实体不是“已经连接成整体”，多组件warning保留。

9实例带Solid/仅单元、默认/18mm斜向变体定向Python制造读回：分别1/9组件，严格校验全部通过。带基底波浪的本轮浏览器下载、Wave+Grid实物连接未执行；不把代码测试冒充浏览器或物理验收。

## 定向命令及结果

在repo/web：

```powershell
npm test -- src/document/fabricWaveRecipe.test.ts src/document/fabricHeight.phase1a.test.ts src/document/fabricPresets.test.ts src/App.phase1a.test.tsx src/manufacturing/computeRequests.test.ts src/App.linearSize.test.tsx src/document/radialSize.test.ts src/draft/localDraft.test.ts src/api/manufacturingFailure.test.ts src/manufacturing/FabricPreflightPanel.test.tsx src/manufacturing/FabricFusionPanel.test.tsx src/manufacturing/useFabricPreview.test.tsx --maxWorkers=2
npm run build
```

最终Web12文件67/67 PASS；build PASS。前面的32/46/67批次包含重叠，不累加。`web-targeted.log`、`build.log` 保存在本轮work目录。

在repo（现有环境，不安装依赖）：

```powershell
$env:PYTHONPATH='.'
& xiaomang_pattern_lab/.venv/Scripts/python.exe -m pytest -q tests/test_fabric_wave_recipe_1b.py tests/test_fabric_cells_only_1a.py tests/test_fabric_fields_f3.py
$env:PLAYWRIGHT_MODULE='<现有bundled Playwright模块>'
node tools/wave_recipe_1b_smoke.cjs
& xiaomang_pattern_lab/.venv/Scripts/python.exe tools/wave_recipe_1b_readback.py
```

Python最终35 PASS另13个subtests（其中新增Wave13用例），非Tk全量。实际browser/readback PASS；日志和原始报告留在work。`git diff --check` PASS。

早期验收脚本错误保留说明：首次脚本用getByText精确匹配带展开箭头的“高度效果”超时，改用真实已有输入定位（无需改产品）；首版读回用trimesh.split要求未安装的graph engine，改为对本固定分离小样的实际面组只读核对，不安装依赖/改网格/Repair，原MeshValidator仍核对拓扑100组件。最终数据均来自真实交付文件。

## 限制与停止

- 旧五套预设未整体迁移，旧Wave Textile仍不等于本完整配方；本轮新增专用入口，不宣称其遗留共享行为已修复。
- 未应用二维快捷输入刷新不恢复；旧Undo不持久化，现有提示保留。独立基础图形混合追加、旧非中性隐式堆栈迁移、5000退化/Tk问题等不在本轮关闭。
- 前端大bundle warning、Starlette/httpx弃用warning保留；没有用升级依赖消除。可选glance CLI未安装，截图用内置像素查看核验，不伪报CLI或额外视觉测试。
- 本轮不重跑全部历史验收；普通制造/无基底/变换/输出授权由受影响回归覆盖，不声明所有旧功能重新人工验收。
- 公网、Linux/Render、切片、实物打印全部NOT TESTED。未开放Production权限、未建Physical backup、未声明F5-C全面PASS。
- 中心隆起、有机扰动、中心秩序、流场波纹未实施。停止，等待用户试用；无提交、推送、部署。
