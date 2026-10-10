# 原图形状默认预览与逐元素高度 — 本地验收（2026-10-09）

## 状态、来源及兼容

- 分支 `feature/pattern-library-reuse`，HEAD `dd16f64aab07e894cdc09218c56a416579b45203` 不变。开始/结束暂存区为空，保留上一批波浪、单元、范围、选择修复和全部未跟踪成果。本记录不是已提交/上线/实物验证。
- 本轮源码保护副本：`work/original-shape-20261009/*.before`。不 reset/clean/恢复 Dot 补丁，不新增依赖，不修改 Validator、融合算法、STLExporter、标准挤出接口、生产配置或 Git 引用。
- 用独立服务 `http://127.0.0.1:8796/`、当前工作树、生产 `web/dist`、独立 Edge/IndexedDB 验收；没有清除用户草稿。仅本测试进程使用既有 `XIAOMANG_ENV=staging` / `XIAOMANG_FABRIC_STL_TEST_EXPORT=1`。自己的初次测试进程 19448 核对命令及端口后重启，最终 PID 31364。旧 8795 等服务未重启；其检查时目录没有原图 Schema，不用它证明当前功能已加载。8792 原用户页既有选择问题仍不以本轮隔离验收宣布关闭。
- 前端最后生产构建 `index-CnLfrYvr.js`；后端运行提交可靠身份 UNKNOWN（未提交工作树不能用 HEAD 当运行版本）。无公网、Linux、切片或实物验收。
- 显式 `fabric_config.shape_source=original` 配合 `original_shape={size_scale,height_mm}`；立体单元为 `unit_cell`，旧无标记但有单元保持原行为。原单元配置与原图参数各自保留，只有一个来源开关，生成方式和造型选择共用入口。
- **无 Fabric 配置**仍是既有统一厚度原图制造，默认厚度 2mm；进入②构造同 revision 的只读原图预览候选，不写正式文档或历史。首次编辑参数/选择原图/应用高度效果才提交显式配置。旧统一厚度值在此转换时保留。**已有 Fabric 配置、unit_cell 缺失/null**不全局重解释：保留旧数据，提示主动选择原图或单元。既有单元、输出、尺寸、场均不自动迁移。

## 真实数据路径及修改文件

| 文件 | 本轮适配 |
| --- | --- |
| `xiaomang_pattern_lab/fabric_original.py`（新） | `original_plan` 读取现有权威最终二维元素，经现有 ManufacturingGeometryAdapter 得到实际多部分/带孔轮廓；复用 TrimeshBackend 的单位高度挤出及有限缓存，不用包围盒替代轮廓。按元素保存 source/final ID、原锚点、世界毫米尺度，轮廓中二维变换已执行一次。 |
| `xiaomang_pattern_lab/fabric_plan.py` | 派生实例计划可携带按实例 ID 索引的真实 contour_prototypes；不是新项目格式或注册一个假普通单元。 |
| `xiaomang_pattern_lab/fabric_preview.py` | 只对显式原图来源接上述路径；原图强制跟随最终元素，保留但不使用 Area Fill 配置。设计预览仅有单位高度轮廓挤出，不运行融合、MeshValidator 或 STL。复用同一 Fabric Field 高度/比例/密度/方向消费逻辑。 |
| `xiaomang_pattern_lab/fabric_candidate.py` | 候选按各实例真实轮廓选择网格，使用同一 T×R×S；多部分保留同一元素高度及 ID，组件数按实际拓扑计。沿用 Solid/Grid 实际材料接触、融合和严格校验。 |
| `xiaomang_pattern_lab/parameter_definitions.py` | 正式新增 fabric_original/original 参数组：等比比例默认1、高度默认2mm；不是前端伪默认值。11种 Unit Cell Schema/Registry 不变。 |
| `web/src/document/fabricOriginal.ts`（新） | 显式配置编辑、旧数据识别及只读预览候选；保留当前单元档案、输出、基底、布点、其他绑定，一次 revision。 |
| `web/src/document/fabricCell.ts`、`fabricModifiers.ts` | 共用来源切换和既有消费者；切回原图不丢单元档案，原图可以绑定既有高度消费者，不重复二维 Scale/Rotation。 |
| `web/src/document/fabricPresets.ts` | 原图的方向/波浪操作走 `applyOriginalHeightRecipe`：只设置归属安全的场、Height范围及配方身份，不覆盖来源/布局/大小/输出。明确完整造型替换配方则设置 unit_cell 来源，保留原图档案。 |
| `web/src/document/parameterSchema.ts` | 接收正式原图 Schema。 |
| `web/src/App.tsx` | 共用自动预览、请求协调、commitDocument、草稿、Undo/Redo及失效；无有效原图明确引导，不造空模型。 |
| `web/src/manufacturing/ManufacturingPanel.tsx` | “保留原图形状（默认）”、图形大小%、图形高度、现有高度效果；显示实际最终元素分布，不暗中全区域重复；说明高度效果与造型替换的区别。 |
| `web/src/manufacturing/FabricThreePreview.tsx` | 复用唯一 renderer；不同真实轮廓分组、相同轮廓复用实例几何，保持相机和风格；大小/高度临时显示与制造分离。全局高度范围只算一次。 |
| `web/src/manufacturing/fabricTemporaryDimensions.ts` | 原图拖动只改局部等比倍率/均匀高度，保持锚点、孔洞及原二维变换，不改高度场结果。 |
| `web/src/api/fabricPreview.ts` | 校验来源、对应轮廓、有限坐标/索引、输出、版本及原字段；无回退假单元，不删除 Contract 校验。 |
| `tests/test_fabric_original_shape.py`（新） | 169最终轮廓、逐元素三种高度×两种输出、孔洞、多部分、Grid接触/孔洞拒绝、旧null、空/非法/密度空、真实API下载和内容指纹。 |
| `web/src/document/fabricOriginal.test.ts`（新），`App.phase1a.test.tsx`、`api/fabricPreview.test.ts`、`fabricTemporaryDimensions.test.ts`、`test/phase1aFixture.ts`、`manufacturing/outputClassification.test.tsx`、`unitCellSelection.test.tsx` | 原图候选不提交、来源切换及档案、一次历史、Undo、完整高度配方不替换、保存恢复、临时变换、严格响应格式、旧无单元兼容/布点提示。 |
| `tools/original_shape_smoke.cjs`、`tools/original_shape_readback.py`（新） | 可重复的独立真实浏览器及已下载文件读回。 |

### 单位、尺寸和输出规则

- 原图大小100%是相对**已应用最终二维轮廓**的本层倍率，绕现有元素锚点等比缩放，不改点距/中心，保留原相对大小/孔洞。二维旋转已烘入轮廓，实例原始 rotation=0，额外 Fabric Orientation 如启用仍正常叠加。
- 高度采样位置为最终元素锚点×mm_per_unit；沿方向/Wave复用原有场注册/采样/Height映射，同一元素多个轮廓部分同高。不是单个轮廓内连续曲面。
- 仅图案：无实体基底，Z=0，不要求连接底布/单组件，所有封闭正体积有效实体保留；相交时仍走原有可靠融合，不宣称穿插壳已融合。
- 图案＋基底：接触、脱离、融合、组件、水密、绕序、正体积及零退化检查保持。Grid孔洞未接触的轮廓拒绝。空、密度全部禁用或不能安全转换的轮廓拒绝，不生成只剩底板的伪成功结果。
- 指纹仍覆盖完整 DTO（来源、轮廓、尺寸、高度、输出等）；下载严格绑定当前内容/版本，不与普通结果混用。辅助对象不在最终二维输入中。

## 浏览器及实际文件证据

证据目录 `work/original-shape-20261009/`；使用13×13方块代表性样本，60×60mm画布、源原点20/40、每源单位0.5mm，已有二维Size .7–1及Rotation -10–10°，方块自身原旋转0/15/30°。这是明确固定验收输入，不宣称重放某个未提供的原用户草稿。

- 默认无Fabric配置：169真实原图轮廓实体、无底板、2mm；正式 revision仍0/字段不新增/Undo空，轻量预览通过，普通制造及浏览器STL下载通过。
- 图形大小100→120%：169锚点XY不变，实际轮廓宽深×1.2；固定高度2→3mm，真实画面变化。保留二维Modifier/原图内容。
- 方向/波浪配方：一次提交，不换Pyramid；大小120%、仅图案输出和原元素保留；单独Height世界毫米核算每个元素。
- 原图→Fin→原图、Undo/Redo、草稿保存/刷新恢复通过；类型和参数档案恢复，旧STL失效。刷新旧Undo历史不保留，沿用既有提示。
- 大小、固定高度真实鼠标分别12次move：拖动期间正式 revision未变、计算请求0，中央实际bounds变，下载禁用；松手一次提交，各一次 `/evaluate` + `/fabric/preview`，没有fusion；Undo恢复尺寸。完整最后会话45个POST，全部200，pageerror0。记录在 `browser-evidence.json`，不是固定FPS声明。
- 截图：`default-original-169.png`、`uniform-original.png`、`size120-height3.png`、`direction-original.png`、`wave-original.png`、`hole-irregular-original.png`。真实WebGL通过；glance本地CLI未安装，直接view_image检查截图，不编造工具输出。

| 浏览器实际下载 | XYZ mm | 组件 | 字节 | 读回 |
| --- | --- | --- | --- | --- |
| uniform-original.stl | 57.23850×57.72620×2.00000 | 169 | 101484 | 每元素真实轮廓顶点/XY/Z均吻合 |
| direction-original.stl | 57.88620×58.47144×5.86374 | 169 | 101484 | 每元素读回高度与独立Linear公式吻合 |
| wave-original.stl | 57.88620×58.47144×5.99239 | 169 | 101484 | 每元素读回高度与独立Wave公式吻合 |
| hole-irregular-original.stl | 32.87146×12.24745×3.00000 | 2 | 2684 | 真孔（Euler=0、实测体积126.5625mm³）和L轮廓保留，125%等比及原旋转匹配 |
| standard-original.stl | 同 uniform-original | 169 | 101484 | 老标准挤出API下载文件；bounds/体积与统一原图新路径一致 |

全部Zmin=0、水密、绕序一致、正体积、零退化面。读回逐元素检查真实下载三角面组、顶点、孔洞和独立高度计算，不能仅凭最大Z算通过。详细在 `stl-readback.json`，没有重新造替代文件/修复/删面。

## 最后测试批次（不叠加历史数量）

```powershell
# web目录
npm test -- src/document/fabricOriginal.test.ts src/document/fabricWaveRecipe.test.ts src/App.phase1a.test.tsx src/manufacturing/unitCellSelection.test.tsx src/manufacturing/outputClassification.test.tsx src/manufacturing/FabricThreePreview.test.ts src/manufacturing/fabricTemporaryDimensions.test.ts src/api/fabricPreview.test.ts --maxWorkers=2
npm run build

# repo目录
& xiaomang_pattern_lab/.venv/Scripts/python.exe -m pytest tests/test_fabric_original_shape.py tests/test_fabric_wave_recipe_1b.py tests/test_fabric_cells_only_1a.py tests/test_fabric_candidate_f5a.py tests/test_parameter_definitions_p1a.py tests/test_fabric_cells_f2.py tests/test_unit_shapes_and_linear_region.py::test_prototype_final_and_real_binary_roundtrip tests/test_unit_shapes_and_linear_region.py::test_grid_attachment_and_real_fusion tests/test_fabric_fusion_f5b.py::FusionTests::test_all_cell_types_and_fin_outward_winding tests/test_web_server_wm3.py -q

# 需既有Playwright模块位置，脚本头部有本地端口说明
node tools/original_shape_smoke.cjs
& xiaomang_pattern_lab/.venv/Scripts/python.exe -m tools.original_shape_readback
```

- Web 49/49 PASS；Python84/84 PASS，另31子测试PASS；build PASS；最后生产浏览器/下载/读回PASS。没有重复Tk全量或5000压力测试。
- 中间脚本因错误控件名/旧状态文案等待失败，改为实际控件后通过；第一份自构造输入未补标准矩形字段且残留旧transform ID，普通制造409被正确拒绝。诊断记录保留，修测试输入，不改一致性guard。新增空态代码一处属性误写被测试和tsc捕获，修为现有finalGeometry后重跑通过；不是用旧PASS掩盖。
- 警告：既有大bundle、Starlette/httpx弃用保留。

## 边界

- 只支持现有Adapter可安全转换的有效闭合轮廓；非法/开放/歧义或拓扑改变按现有规则准确拒绝。仅逐元素高度；无单轮廓连续高度曲面、全区域重复自定义轮廓或新算法。
- 设计预览不等于最终通过；测试Fabric导出仍限已授权本地/测试环境。普通无Fabric配置的统一高度输出仍保留原普通接口。
- Solid/Grid原图已做实际候选/融合/二进制读回定向测试；本轮浏览器下载侧以仅图案样本为主，未称所有基底组合均逐项网页下载。11单元数值/制造定向回归与Fin浏览器切换通过，不冒充原8792页11项鼠标重新验收。
- 用户原169项目未覆盖/替换；新独立浏览器使用固定代表性169点阵，不从不存在的工程文件猜数据。
- 本轮无公网/Linux、Bambu切片、实物打印、新冻结备份；全部新成果仍未提交。
