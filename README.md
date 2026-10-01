# Xiaomang Pattern Lab / 小芒图案实验室（当前活跃项目）

## Web 用户流程与制造失败调试

普通用户的 Web 流程是：导入 PNG/JPG（或已有 SVG）→ 参数化设计 → Fabric/制造 → 3D 预览 → STL。
界面不提供 `.pattern.json` 的导入/导出或项目文件保存。PatternDocument 仍是会话中的内部设计事实；
现有 JSON 读取器只保留给自动测试注入固定工程，不在开发或正式用户界面显示。

默认**关闭**。需要复现制造检查失败时，在启动 Web 后端的同一个 PowerShell 会话中设置
`$env:XIAOMANG_DEV_MANUFACTURING_SNAPSHOTS = '1'`，然后按现有方式启动后端。
Gate T / Gate W 等制造失败会把本次实际提交的 PatternDocumentDTO、厚度、Fabric 配置、
启用的 Field/Modifier、错误码和验证摘要写入被 Git 忽略的
`work/manufacturing-failures/`；每次生成独立文件，不覆盖旧记录。敏感键值会脱敏，
本地绝对路径被 Web Contract 拒绝，快照不含浏览器临时交互状态。它不修复 Mesh，
也不降低校验标准。失败响应、开发 UI 和日志使用同一个 `failure_id` 对应快照文件名；
生产环境默认不生成或返回该 ID。调试后移除该环境变量并重启后端即可关闭。

快照仅覆盖**后端收到并处理的制造请求**，不会要求用户保存工程文件。
当前那次退化面失败尚无原始请求快照，不能凭后续功能反推其根因。

## F2 — Unit Cell Library + Uniform Instance MVP

制造页的 Fabric Base 可附加 Cylinder、Cone、Pyramid、DoubleTower 或 Fin 单元，并设置统一宽、深、高及规则布点间距。Python 以毫米生成一份单元原型和派生 `FabricInstancePlan`；每个单元固定方向、固定比例，底部 Z 等于基底顶面。Three.js 用共享几何实例显示阵列，不逐个制造或布尔合并。

**重要：F2 单元仅为设计预览，不属于当前制造网格和 STL。** 现有 STL、Mesh Validation 与 GLB 仍只针对 F1 基底；界面把下载按钮标为“导出基底 STL”。单元与网格基底的 XY 接触、融合、可打印性尚未经验证，不能把此预览当成最终 Fabric 模型。F3 的高度/密度/方向 Field、F5 的融合与制造验证均未实现。

## F1 — Fabric Base MVP（增量功能）

制造页可选“标准二维挤出”“Solid Base”或“Grid Base”。Fabric 配置作为可选 `fabric_config` 存于原 PatternDocument；缺失时沿用 Web Alpha 制造行为。Solid/Grid 从最终二维制造几何的**轴对齐外接矩形**（世界坐标 mm）生成基底，网格条带先合并再挤出；厚度、边距和网格间距/线宽由 Python 校验。生成结果继续使用原有 Mesh Validation、同一 `manufacturing_result_id` 的 3D 预览与 STL 下载。

F1 **不是**沿原图轮廓裁剪基底：Solid 会填满外接矩形（包括原图孔洞），Grid 只保留自身网孔；也未将原二维元素与基底融合。制造前必须核对实际尺寸与连接方式。本阶段没有 Unit Cell、Height/Density/Orientation 或真实 Fabric 打印验证。Web Alpha 冻结标签仍指向原稳定版本，不随 F1 改动。

## Web v0.1 Alpha — 已完成实物验证（2026-10-01）

当前 Web Alpha 已形成可用闭环：图片/SVG 导入 → 可编辑二维图案 → Layout、Field、Modifier 参数化设计 → 制造检查与网格验证 → Three.js 只读 3D 预览 → 下载 STL。用户确认已将网页版下载的 STL 导入 Bambu Studio、切片并完成真机打印，实物正常；因此本次 Web Alpha 实物验收记录为 **PASS（依据用户反馈）**。

当前已接入图片/SVG 导入、二维编辑、Free/Grid/Radial/Curve 布局、参数场与效果堆栈、会话内撤销/重做、Web 制造、Mesh Validation、3D 预览和 STL 下载。制造与导出仍由 Python Engine 完成，浏览器不计算制造网格。相同设计及厚度可以复用当前进程中的制造结果；STL/GLB 从同一已验证 Mesh 按需生成。

这仍是本机 Alpha，不是已部署网站或新安装包。浏览器内尚无完整项目保存/云同步；3MF、自动连接、自动网格修复、最小壁厚保证和 Fabric 系统未完成。图片导入后的临时毫米映射须在制造前由用户核对。本次用户未提供实物照片、测量公差或打印配置，故不声称独立实测或保证所有图案都可打印。

源码版本以 `web-v0.1-alpha` 标签和 `backup/web-v0.1-alpha-physical-validated` 分支为准；二者应指向同一份文档冻结提交。标签不包含 `.venv`、`node_modules`、本机 `work` 产物或可执行安装包。下方 WM 和桌面 v0.1-alpha 段落保留为各阶段的历史记录，其中“当时尚未实现”的表述不代表当前 Web Alpha 状态。

## WM5.6 — Web 元素编辑可见性修复

移动、拖动、宽高和旋转编辑会在求值期间保留上一帧。拖动预览结束时清除临时 SVG 位移，避免最终几何被重复平移；无效尺寸或重复 ID 的响应不会覆盖有效画面。输入框中的空白草稿不会立即提交。详细验证见 [WM5.6 记录](work/wm5-6/edit-visibility-report.md)。

## WM5.5 增量 — Web 图片 / SVG 导入

当前网页增加“导入 PNG / JPG”“导入 SVG”和画布拖放。浏览器只上传文件；本机 Python 后端使用现有预处理、矢量化、SVG 归一化链路生成独立的 PatternDocument 元素，再经 Evaluate 显示。临时资产仅在本机进程保留 30 分钟，上限 32 个、每个 8 MiB；无数据库或云存储。导入后默认按 1 原始单位 = 1 mm **临时显示**，这不是经确认的制造尺寸。工程制造前须核对比例。WM6 编辑能力未回退。

## WM6 — Web 参数化控件与会话撤销

网页右侧检查器现可编辑已有自由源元素、矩阵结构、常用参数场与效果层，并通过现有 Python Evaluate 更新最终二维几何。滑杆松手才提交一次；支持会话内撤销/重做和失败时保留上次有效画面。组合场及图片场暂只读，部分派生元素不可反向编辑；网页尚无项目保存。范围、测试与限制见 [WEB_PARAMETRIC_WM6.md](docs/WEB_PARAMETRIC_WM6.md)。

## WM5 — Web 二维查看与基础编辑

网页现可打开现有 PatternDocument JSON，经 WM3 `/api/v1/evaluate` 显示最终二维几何。支持适合窗口、缩放、平移、单选和检查器；仅能对可确定映射回自由源元素的对象直接拖动，松开时提交一次并重新求值。参数化派生元素保持只读。旧 SVG 单位项目必须由用户明确填写毫米比例。运行方式、验证和限制见 [WEB_2D_WM5.md](docs/WEB_2D_WM5.md)。桌面程序及制造链未改动。

## WM4 — React Web 工作区基础版

新增独立 `web/` 前端，提供三栏工作区、模式导航，以及 WM3 后端在线状态和 v1.0/mm 协议握手。该阶段尚不支持在网页中导入、编辑或制造；WM5 已补充项目打开与基础二维编辑。桌面 Tkinter 版本保持原样。安装、运行和范围见 [WEB_SHELL_WM4.md](docs/WEB_SHELL_WM4.md)。

## WM3 — 本机 Headless API（Alpha）

现可通过 FastAPI 调用现有 WM2 Contract、二维 Evaluate 与制造 Service，并按同一次制造结果 ID 下载 Binary STL。开发服务器仅绑定本机；不包含网页 UI、账号或云存储。启动、接口和安全边界见 [WEB_SERVER_WM3.md](docs/WEB_SERVER_WM3.md)。桌面程序入口未变。

## WM2 — Web Contract / DTO v1

新增版本化 JSON 协议层，供浏览器与现有 Python 应用服务交换 PatternDocument、二维求值几何、制造验证和 STL 产物信息。唯一设计事实仍是正式 PatternDocument 项目格式；协议仅负责传输。详细字段、毫米坐标、revision、资产引用与错误码见 [WEB_CONTRACT_V1.md](docs/WEB_CONTRACT_V1.md)。WM3 已加入本机服务器；WM4 仅提供不编辑文档的浏览器工作区外壳。

## WM1 — Headless Manufacturing Application Service

当前桌面制造窗口不再自行组织制造步骤，而是调用无 Tk 依赖的 `ManufacturingService`。唯一主链保持 `PatternDocument → Evaluate → Gate T → Gate U → U.5 → Gate V → Gate W → Gate X`；桌面 UI 和未来 API 将复用同一业务服务。服务返回同一份制造 Mesh 给桌面预览和 STL 导出，操作仍为只读 Derived Operation，不改变工程、Undo 或 Dirty。

本阶段只完成服务层抽离；尚未加入 FastAPI、REST、React、TypeScript、Three.js、GLB、云端项目或 Skill Orchestrator。旧 `ppg/xiaomang_pipeline.py` 不属于当前 Web/制造入口。

## v0.2-M2 — 只读制造 3D 预览

在制造窗口完成“检查并生成”后，可点击“3D 预览”查看即将导出 STL 的同一份最终制造 Mesh。窗口支持左键旋转、滚轮缩放、适合窗口与重置视角，并显示 X/Y/Z 毫米尺寸和组件数。Z 始终为厚度方向；孔洞、多组件和真实空间位置不会被预览自动修复、合并或重新排列。

预览只持有不可写渲染副本，不回读 PatternDocument，不介入 STL Pipeline，不产生 Undo 或 Dirty。修改二维设计或厚度后旧预览会失效，需重新“检查并生成”。本阶段不是3D编辑器，也没有实时参数化3D、Boolean、Mesh Repair、3MF或壁厚分析。

## v0.2-M1 — 软件内制造工作流

顶部“制造”按钮打开独立制造窗口。用户可设置唯一制造参数“厚度（mm）”，点击“检查并生成”后查看二维几何、连通组件、制造转换和 Mesh 摘要；只有 Gate W 无错误时才能通过系统保存对话框导出 Binary STL。多组件会明确警告但不自动连接，也不阻止合法导出。

该窗口只编排既有 `PatternDocument → Evaluate → T → U → U.5 → V → W → X` 链路。检查、生成和导出均为临时派生操作，不修改工程、不增加 Undo、不改变 Dirty。设计或厚度变化后必须重新检查。技术详情保存在窗口详情区和现有日志中。M2 已增加只读制造 Mesh 预览，但仍没有3D编辑、自动修复、Union、桥接或新制造算法。

开发启动后：完成二维设计 → 点击“制造” → 输入厚度 → “检查并生成” → 阅读摘要 → “导出 STL”。

## v0.1-alpha — Physical Manufacturing Validated Freeze（2026-09-23）

End-to-end manufacturing pipeline: **PHYSICALLY VALIDATED**。

`Design → Parametric → Manufacturing2D → 3D Mesh → Validation → STL → Bambu Studio → Physical Print`

代码基线：`d1ed14e`；最终冻结版本以 `v0.1-alpha` 标签与
`backup/v0.1-alpha-physical-validated` 分支指向的提交为准。本次只更新发布文档，不新增功能、不重新打包。

### 已完成（当前 Pattern Lab）

- Image / Geometry input、可编辑二维元素及参数化设计。
- PatternDocument 项目工作流、Field / Modifier 系统。
- Geometry Validation、Connectivity Analysis、Manufacturing2DGeometry。
- Extrusion、Mesh Validation、Validated Binary STL Export。
- 两次实物制造验收：20×10×2mm 校准块；Grid + Wave Field + Size Modifier 三星试件。

### 尚未实现／不属于本次发布

- production-ready Web UI、integrated 3D preview、3MF。
- automatic mesh repair、minimum wall thickness、printer/material profiles。
- automatic connectors、AI design assistant。
- 面向普通用户的完整一键制造 UI 尚待产品化；已验证的制造能力主要通过现有内部 API/验证流程调用。

两次 Bambu Studio 导入、切片、打印和尺寸 PASS 均依据用户反馈（第二次在本次冻结请求中确认尺寸）；不是代理操作打印机或独立计量。未提供打印配置、实物照片或测量公差，因此不推广为任意图案/材料的打印保证。第二次为三个独立星形，不是连通面料。

验收与测试记录见 [GATE_STATUS.md](GATE_STATUS.md)，下一阶段仅为计划，见 [ROADMAP.md](ROADMAP.md)。
源码标签不包含被 Git 忽略的 `.venv`、`.runtime`、`work`、build/dist 或本机依赖，也不等于新的安装包。

安全回退：在仓库根执行 `git worktree add --detach ../PatternLab-v0.1-alpha-recovery v0.1-alpha`。
目标目录必须不存在；新目录需按项目说明配置运行时。不要覆盖当前工作区或使用强制 reset。

唯一当前入口为 `xiaomang_pattern_lab.main`；使用说明见
[Pattern Lab README](xiaomang_pattern_lab/README.md)。Gate S 补齐文件菜单、保存点、
未保存确认、最近项目、独立恢复副本及参考图重定位。其后 T～X 已完成上述制造后端；本次没有修改 PACK-1 打包系统。
阶段验证与回退点见 [GATE_STATUS.md](GATE_STATUS.md)。

以下为旧版小芒造物历史文档，不代表当前实验室新增了对应功能。

# 小芒造物 · AI 参数化创意设计与 3D 制造（历史）

面向非程序员设计师的 Windows 参数化设计软件。打开程序、导入参考图或选择轮廓、调节参数、实时查看并导出；不需要 Rhino 或编程环境。

当前版本：**1.6.14**。本轮新增上游 `imagetosvg-mcp` 最小集成：参考图先转换为真实 SVG 层，再进入可编辑二维链路；默认仍无需安装 Blender。

上游集成说明、许可证、依赖和回归证据见 [EXTERNAL_SKILLS.md](EXTERNAL_SKILLS.md)。

### 项目内 Skill 编排（新增）

制造链现在有独立的 `.codex/skills/xiaomang-creation/` 体系，并已接入程序内 `ppg/xiaomang_pipeline.py`。点击“导出 STL”时，软件会按“参考/规则 → Generator → 几何清理 → 制造预检 → 本地 SDF（或显式 Blender 兼容后端）→ STL → 质量审计”写入同一份 handoff contract（含 artifact 哈希、单位、状态、验证和 checkpoint），失败会停止并支持从最近通过阶段恢复；参考图矢量化 POC 通过项目内 `external/imagetosvg-mcp` 调用上游 MCP，详见 [EXTERNAL_SKILLS.md](EXTERNAL_SKILLS.md)。

主工作台以中央大型可编辑 2D 画布为重点。参数控件支持滑杆、数字输入、单位显示和单项重置，生成器卡片可直接切换规则；最终三维模型在后台独立构建，界面只显示制造结果与审计状态。

## 当前版本：Phase 1

- 简体中文 UI 与中英文语言资源架构
- 内置圆形、椭圆、圆角矩形、星形、多边形、心形、有机形、波浪形
- SVG/DXF 轮廓导入与自由绘制、自动简化和闭合
- 直线、圆点、直线+圆点、三角形、矩形、叶片、水滴、珠子和自定义 SVG 元素
- 均匀、随机、渐变、曲率分布；旋转、偏移、缩放与最小间距
- 外法线/内法线/朝向中心/远离中心
- Seed 可复现的普通随机与环形平滑噪声
- 二维预览：拖动时轻量交互、停止后标准完整 2D；仅“生成最终模型 / 导出 STL”调用最终制造后端
- SVG、PNG、DXF 导出；PPG 项目与预设；撤销/重做；自动恢复副本

## 安装与使用

优先运行 `installer-output/小芒造物-安装程序-<版本号>.exe`。安装包固定安装到当前用户的本地应用目录，不需要管理员权限。若 Windows 因文件未签名弹出保护提示，请在确认文件来自本项目后选择“更多信息 → 仍要运行”。若只拿到单文件版，双击 `dist/小芒造物/小芒造物.exe` 即可，不需要安装 Python。

升级前请先保存项目并完全退出当前安装版本的“小芒造物”。安装器只检测即将被覆盖的安装目录；旧版、开发版或测试副本不会阻止安装，也不会被安装器强制关闭。

若旧安装器曾显示 `An attempt was made to expand the "app" constant before it was initialized`，请不要再运行该旧文件；该问题已在 **1.5.3** 安装包修复。

1. 首次打开会显示一个有机“海胆”示例。
2. 在左侧选择内置轮廓，或点击“导入轮廓”“自由绘制”。
3. 选择外围元素，调整数量、长度、随机、平滑噪声与 Seed。
4. 使用“保存预设”保存喜欢的方案，或“保存”保存 `.ppg` 项目。
5. 导出 SVG、PNG 或 DXF。

## 2D 导出

- **SVG**：黑色矢量轮廓、线和圆点，适合继续编辑或进入切片流程。
- **PNG**：2000×2000 黑白预览。
- **DXF**：`GEN_BaseCurve`、`GEN_RadialLines` 与 `GEN_EndDots` 图层，可直接导入 Rhino。

## 一键图片转 SVG / STL

点击顶部的“图片转 SVG / STL”，选择黑白图片后填写成品宽度和打印厚度即可。黑色自动变为实体，白色自动变为孔洞；生成的是 **无底板** STL。

软件会同时输出：`图案.svg`、`图案.stl`、黑白预览、参数公式说明和连通性检测。若图片中存在多个互不连接的黑色区域，默认只输出 SVG 和检测报告；界面会明确询问是否将其作为多个独立打印部件导出 STL。

对于 0.4 mm 喷嘴，建议线条、连接与孔洞至少为 0.8 mm，厚度使用 0.8–1.2 mm。

### 表面质量与最终模型

图片转换会在输出前询问：

- **最终模型质量**：草稿、标准、精细、超精细。最终 STL 会重新建模，绝不直接拿 Canvas 预览导出。
- **圆润程度**：从结构清晰到液态圆润，控制连续距离场的轮廓柔化和圆角厚度场。
- **有机融合**：从边界明确到自然融合，控制主体边缘的圆角过渡。

最终管线使用“二维欧氏距离场 → 圆角连续厚度场 → Marching Tetrahedra”等值面提取。它取代了早期的逐像素方块挤出；导出后会进行 STL 三角面、裸边、非流形边与退化面的独立拓扑审计。完整的自交/最小壁厚/任意 3D 厚度场分析将在 3D 工作室阶段加入。

## AI 视觉分析与生成器库

顶部的“AI 视觉分析”现在提供本地、可解释的点线面分析：它会读取灰阶明暗、自动阈值、黑色覆盖率、连通组件数量、组件紧致度/线性比例、网格周期、方向性和径向变化。结果会明确显示主体轮廓、基础元素、排列方式、密度和尺寸变化、渐变方式、推荐 Generator 和初始参数。没有可靠匹配时会明确提示当前生成器库不足；不会假装已经完美反向还原参考图。

分析后选择“应用”会进入“点线面 / 半调”面板，立即生成一张由规则和参数产生的新图。分析结果会归纳为 Generator + Modifier Stack：位置场、尺寸场、密度场、旋转/涡旋、中心留白、角点强调和 Mask；它们都可继续编辑，不会逐像素复制原图。预览区可切换“重建结果 / 原图 / 左右对比 / 叠加对比”，用于判断规律匹配度。你可以改为圆形、星形、心形、圆角矩形 Mask，或切换径向、线性、波纹渐变，再用“生成变体”挑选新的可编辑方案。

导入 PNG/JPG 后会立即建立 Reference Layer 和 Geometry Layer；图片保持宽高比、居中适配设计区域，原图、左右对比和叠加模式仍可切换。Geometry Layer 只保存真实可编辑元素，不依赖位图或 Generator 重绘。

### Reference2D 可编辑重建

点阵/半调/几何图片会经过 `ppg/reference2d/` 的本地管线：Image Decode → Preprocess → Primitive Detection → Editable Elements → Spatial Analysis → Generator/Modifier Fitting → EditablePatternDocument。检测使用连通组件，并对粘连圆点使用 distance transform + local maxima + watershed/Voronoi 分区；OpenCV、scikit-image、SciPy 可作为加速依赖，干净安装缺少它们时自动使用 NumPy 后备。参数拟合失败时仍保留 Direct Element Mode。

对 DOT/HALFTONE 参考图，Stage A 已接入正式 2D Canvas：`EditablePatternDocument` 保存每个元素的 ID、位置、尺寸、旋转、置信度和来源。文档同时保存检测得到的 `base_elements`、用户新增元素、`Base Generator + Modifier Stack` 以及按稳定 ID 记录的 `Local Overrides`；当前 `elements` 是每次 Rebuild 后真正绘制、选择与导出的物化几何。导入后可在“可编辑检测元素”面板或画布中选中、框选、修改尺寸与旋转、拖动、Delete 删除、Ctrl+D 复制、Ctrl+G 分组；项目保存对象 JSON，重新打开不需要重新分析源图片。参数化规则只支持 Grid/Radial、尺寸/密度/旋转场、圆形 Mask 与简单 Warp；分数不足时保持 Direct Element Mode。VTracer 仅保留在独立 POC 的 SVG/轮廓验证路径，不作为点阵识别器。

当前已启用：半调点阵、规则点阵、渐变点阵、点线面构成、轮廓遮罩和网格变形。它们统一提供点大小、点间距、线宽、整体缩放、渐变强度、对比度、阈值、Feather、模糊、旋转、噪声、Smooth Noise、Seed、Mask、点/线/面、圆/方/三角和实时预览，并可导出 SVG、PNG、DXF。

当前扩展后的 Field Generator 还提供横/纵数量、行/列距、最小/最大尺寸、密度、X/Y 偏移、Gamma、Levels、反相、Mask 强度、边缘柔化、渐变中心/曲线、独立随机、Noise Frequency/Offset/Octaves、Wave/Twist/Bend/Curl/Flow/吸引/排斥，以及菱形、六边形、水滴、叶片、胶囊、空心和描边。参数页支持垂直滚动和名称搜索。

顶部工具栏支持左右箭头、鼠标滚轮、Shift+滚轮、触控板滚动、拖动和“更多”菜单；任何窗口宽度下均可访问全部功能。

详见 [功能状态](FEATURE_STATUS.md)，其中明确区分已可用、部分实现和待实现功能。

界面已回归为浅灰、白色面板和稳重蓝色操作色，优先保障预览与参数阅读的清晰度。

## 最终 3D 与 STL

当前版本没有自研 3D Viewer、相机、材质、线框或实时预览 Mesh。点击 **“生成最终模型”** 或 **“导出 STL”** 后，软件在后台独立构建最终制造网格；完成时显示尺寸、三角面数、组件数、封闭状态和制造检查结果。二维编辑状态不会自动触发三维重建。

## 预览性能基准（1.6.3）

以下为本机的纯 Generator 工作单时间；Canvas 使用批量临时位图提交，大量元素不会逐一创建 Canvas 项。交互时始终限制在 80 个图元，500 元素标准预览约 9 ms，满足参数拖动的流畅反馈目标。3,000 / 5,000 元素用于完整预览与压力测试，不承诺 60 FPS。

| 图元规模 | 生成时间 | 估算工作单帧率 |
| --- | ---: | ---: |
| 196 | 3.6 ms | 280 FPS |
| 500 | 9.1 ms | 110 FPS |
| 1,000 | 18.2 ms | 55 FPS |
| 3,000 | 54.2 ms | 18 FPS |
| 5,000 | 93.9 ms | 11 FPS |

在“随机与制造”页可直接调整基础厚度、圆润程度、有机融合、最小结构宽度和最终模型质量。已保存的高度控制数据只会作用于最终 STL 工作单，不再驱动一个实时三维画面。

点击 **“导出 STL”** 后只需选择保存路径。软件会在后台自动执行二维制造清理、最终三维重建、体素融合、网格修复、封闭性与独立组件检查，再直接保存 STL；不需要用户打开或操作 Blender。

- 点、线、面图元会转为平滑基础体；默认最终制造阶段使用本地连续 SDF + Marching Tetrahedra 进行有机融合，无需安装 Blender。需要兼容旧流程时可显式启用 Blender Worker。
- 可设置基础厚度、圆润程度、有机融合、最小结构宽度，以及草稿 / 标准 / 精细 / 超精细质量。
- 最终建模会先清理无效、过小与过短二维元素；放射线结构会生成连续根部脊环。导出后从已落盘 STL 独立检查封闭、裸边、非流形、退化面、独立组件与最小边长。单件模式发现多个组件时不输出 STL。
- 最终导出独立 STL，并生成同目录的 handoff/检查报告；报告包含实际后端、二维清理结果、顶点/三角面数和拓扑审计结果。

安装包不再要求 Blender；默认本地后端可直接生成 STL。Blender 仅作为可选兼容后端，不安装也不影响普通使用。未来如需第三方模型显示，只会通过 `PreviewProvider` 显示最终制造网格，不会重新耦合到编辑或导出流程。

## 常见问题

**导入失败**：请确保 SVG/DXF 是一个简单闭合轮廓。复杂多对象 SVG 请先转为单一 polygon/polyline 或简单 path。

**图形忽然很密**：降低数量，或先选择“快速”预览。

**如何重复生成同一图案**：保持全部参数和随机种子不变。

## 开发构建

在 PowerShell 运行：

```powershell
.\build.ps1
```

它会先运行自动测试，再生成单文件 EXE。安装程序使用 Inno Setup，安装后运行：

```powershell
.\build-installer.ps1
```

构建脚本使用项目内 `build-tools/pyinstaller-local`，避免旧缓存权限异常；首次构建若目录为空，会从 PyPI 安装 PyInstaller（需要网络）。最终发布前请确认生成了 `dist/小芒造物/小芒造物.exe`，再编译 Inno Setup 安装器。
