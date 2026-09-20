# PPG 维护技能说明

## 项目目标

维护“小芒造物”：面向非程序员的中文 Windows 参数化创意设计与 3D 制造平台。核心路径始终是“灵感 → 创作 → 修改 → 3D → 打印”；不能要求用户编辑代码或运行 Rhino。

## 架构

- `ppg/geometry.py`：唯一的二维几何内核。复用 Rhino 原型的等弧长采样、外法线测试、凹区安全裁剪；禁止在 UI 中复制几何算法。
- `ppg/model.py`：项目和参数数据结构。新参数须具备默认值与 `.ppg` 兼容读取方式。
- `ppg/app.py`：Tk 二维编辑 Canvas 与最终模型后台任务入口；不包含三维查看器、相机或临时 Mesh。
- `ppg/exporters.py`：SVG、PNG、DXF 输出；所有 Element 图元在这里和 Canvas 使用同一 Geometry 描述。
- `ppg/raster_print.py`：黑白图片直接转无底板 SVG/STL；黑色是实体，白色是孔洞，必须先读取连通性结果。
- `ppg/blender_worker.py`：3D 后端兼容边界。默认转发到 `ppg/native_stl.py` 的本地 SDF 网格，不要求 Blender；仅显式选择兼容后端时才提交 Blender JSON 工作单。
- `ppg/final_geometry.py`：最终制造工作单的 mm 缩放、边界计算和连续高度场；不生成临时预览网格。
- `ppg/preview_provider.py`：未来可选显示适配器的窄接口；当前必须使用无状态的 `NullPreviewProvider`，核心制造流程不得依赖它。
- `ppg/generators/`：Generator Library 注册表；新算法以 `GeneratorSpec` 注册，不能把生成规则散落进 UI。
- `ppg/field_generators.py`：点线面 / 半调 Generator 内核；返回与 Canvas/导出无关的图元，预览与 SVG/PNG/DXF 必须共享这一结果。
- `ppg/image_analysis.py`：可解释参考图分析；读取阈值、组件、紧致度、线性、网格周期、方向性和密度规律，返回置信度、分析详情和建议，低置信度必须提示新 Generator 缺失。
- `ppg/reference2d/`：Reference → Editable 2D 管线；按 importer/preprocessing/classifier/features/fields/matching/reconstruction/similarity/cache/pipeline 拆分，输出真实 DotFeature、SpatialFields、`EditablePatternDocument` 与可序列化结构化结果，并通过兼容桥接回旧 AnalysisResult/UI。点检测优先使用 distance transform + local maxima + watershed；OpenCV/scikit-image/SciPy 为可选加速，NumPy 后备保证无额外安装也能工作。
- `reference2d_poc/`：旧版 Stage A VTracer/SVG 兼容基准；仅用于轮廓/Mask 和回归验证，不作为 DOT/Pattern 识别器。正式参考重建使用 `xiaomang-reference-reconstruction` 与 `ppg/reference2d/`。
- `xiaomang_pattern_lab/recognition.py`：实验台的多尺度 Dot 识别补充层；仅把二值图证据标注或恢复为真实 PatternDocument Element，不能以文件名、fixture id 或预设数据决定结果。
- `xiaomang_pattern_lab/pattern_analyzer.py`：实验台的独立 PatternAnalyzer；输入严格为 `PatternDocument.elements`，第一版只输出 GridFitResult 与 SizeGradient 候选。低分保持 Free Element Mode。
- `xiaomang_pattern_lab/evaluation.py`：Pattern Lab Matrix V1 的唯一 Evaluate Pipeline。参数化模式严格按 Grid → Modifier → Local Override 计算；Canvas、SVG 导出和保存恢复不得自行生成另一份几何状态。
- `xiaomang_pattern_lab/placement_assignment.py`：Gate 1 的统一 Placement / Prototype / Assignment 基础层。`PlacementSlot` 同时适配导入图元和既有 Grid；`ShapePrototypeRegistry` 复用 `ElementPrototype`；Replacement/Assignment/Random 通过可选 metadata 接入，默认必须是 Circle Grid 的兼容 no-op。
- `xiaomang_pattern_lab/shared_modifiers.py`：公共参数化效果层。`SharedModifierStack` 可作用于 Imported Elements、Grid、Radial 和 Curve source；结构参数与 Size/Rotation/Mask/Local Override 效果分离，源快照必须可保存恢复。
- `xiaomang_pattern_lab/presets.py`：Gate O 本地预设边界。`ParametricPreset` 只保存可复用的 Field/Modifier/Scope/ShapePool/Random 配置，绝不承载 PatternDocument、Raster、`source_elements`、Selection 或 View State；跨几何应用必须按 source Bounds 适配世界坐标。
- `xiaomang_pattern_lab/manufacturing_geometry.py`：Gate U.5 的只读制造二维边界。它把唯一 Evaluate Pipeline 的最终面积几何转换为毫米 `Manufacturing2DGeometry`，保留明确 `evenodd` 孔洞；开放线、无效几何和嵌套 nonzero 填充歧义必须明确跳过，不得猜线宽、孔洞语义、修复或写回文档。
- `xiaomang_pattern_lab/manufacturing_backend.py`：Gate V 的唯一最小 3D 边界。`ManufacturingBackend` 只接受 `Manufacturing2DGeometry` 并生成临时 `ManufacturingMeshResult`；本地 `TrimeshBackend` 使用 Shapely + Earcut 挤出到 Z=`0..height_mm`。不得读取 UI/Canvas/Element/Grid，不得导出 STL/3MF、布尔并集、桥接、修复或启动 Viewer。
- `ImageField`（Gate P）：只读 Reference 灰度共享场；按世界坐标双线性采样并缓存派生像素，缺失图片回退中性值，不保存像素、不重新矢量化。
- `NoiseField`（Gate Q）：连续世界坐标 fBm 共享场；以稳定 Seed、尺度、偏移、八度和对比度输出 `0..1`，可复用给尺寸、旋转、位置或密度消费者，不改写源几何。
- `xiaomang_pattern_lab/family_analyzers.py`：多结构路由的 Along Curve 门禁。先以二维协方差特征值和局部邻域方向一致性确认内在一维性，再进行链路评分；规则二维晶格不得因贪心最近邻链进入 Along Curve。
- `xiaomang_pattern_lab/ui_harness.py`：所有 Tk 数值先经 `parse_int_ui_value` / `parse_float_ui_value`，Grid 控件只在实际 Grid 结构激活时可编辑；UI callback traceback 持久化到 `work/diagnostics/pattern_lab-ui.log`。
- `xiaomang_pattern_lab/element_debug.py`：实验台元素可渲染性审计。任何“空框/缺失元素”必须先检查 detected、renderable、visible filled、invalid 与 unknown 统计，再修改识别或渲染。
- `ppg/xiaomang_pipeline.py`：将项目导出接入 `.codex/skills/xiaomang-creation` 的 handoff contract；写入阶段 artifact、哈希、checkpoint，并把最终 STL 交给本地 SDF/可选 Blender 后端再审计。
- `ppg/theme.py`：奶油白、芒果橙、叶绿点缀的清晰专业界面系统；所有新面板必须复用颜色与状态样式，不能改回过度装饰的金属/霓虹界面。
- `ppg/locales/*.json`：所有用户可见文本优先从语言资源读取；默认 `zh_CN`。

## 项目内 Xiaomang Skill 系统

跨阶段制造任务使用 `.codex/skills/xiaomang-creation/` 下的本地 Skill 体系：

- `xiaomang-orchestrator`：阶段编排、checkpoint、失败停止与回滚。
- `xiaomang-reference`：参考图证据提取和可解释分析。
- `xiaomang-generator`：现有 Generator 注册表到可编辑 2D 规则的映射。
- `xiaomang-geometry`：毫米制几何清理、连通性和最小特征预检。
- `xiaomang-blender`：可选 Blender Worker 边界；默认由 `xiaomang-native` 完成本地建模和 readback。
- `xiaomang-native`：无需外部软件的 SDF 最终网格、STL 导出和拓扑审计。
- `xiaomang-manufacturing`：打印尺寸、壁厚、孔洞和组件策略预检。
- `xiaomang-stl`：最终 STL 导出门槛、修复和拓扑审计。
- `xiaomang-quality`：最终模型读回、制造质量循环和 milestone 发布。

统一交接格式位于 `.codex/skills/xiaomang-creation/references/handoff-contract.md` 及其 JSON Schema。它要求 artifact 绝对路径、SHA-256、producer、阶段状态和 checkpoint；只有 Reference → Editable 2D → Clean Geometry → 后端 readback → Manufacturing → STL → Quality 全部通过，才能交付 STL。参考图 Raster→SVG 阶段允许通过 `external/imagetosvg-mcp` 的官方 MCP 协议调用上游工具；项目只保留薄适配器，不复制上游实现、Skill 内容或依赖，并不改变 UI 或 Generator 产品方向。

## 规范

1. UI 默认使用简体中文；专业词可在 Tooltip 括注英文。
2. 内部长度以 mm 保存。单位切换不可损坏项目数值。
3. 同一 Seed、同一轮廓和参数必须严格可重现。
4. 正式产品预览只指二维编辑 Canvas：滑动中约 33ms 节流、最多 80 个图元；停止 120–140ms 后完成标准二维预览。最终后端只可由“导出 STL / 生成最终模型”触发；不得因二维参数变化生成任何 3D 临时 Mesh。`xiaomang_pattern_lab` 是例外的性能实验台：它可以使用原生 Canvas 静态图元验证 144–3,000 个对象的直接操作，但拖动期间只能更新 `InteractionState` 与交互层；严禁完整 Document clone、SVG 序列化、完整 Canvas 重建或连续 Undo。
5. 点线面 Generator 的参考图片仅用于推导可编辑密度场；不得把位图逐像素伪装成“生成”。用户可更改 Mask、渐变、Seed 和元素类型得到真正新变体。
6. Field 参数必须在 `field_generators.py` 中产生可测量效果；不得只添加 UI 滑杆。新 Generator 通过注册表和该统一 API 扩展。
7. 缓存只保存派生采样/解析数据，不能把预览对象写入项目文件。原始参考图明暗场须按路径、修改时间和模糊参数缓存；项目只保存二维平移缩放等轻量视图状态。
8. 简单闭合轮廓才可生成；对自交、零面积和不合法输入给用户中文提示，技术细节写入日志（未来加入）。
9. 图片转 STL 默认拒绝将多个黑色连通组件称作单一面料；只有用户明确确认多部件后才能输出 STL。
10. STL 最终生成使用 SDF 连续轮廓、圆角厚度场和等值面提取。质量档只影响最终建模采样，不能复用实时 Canvas 预览；导出后运行独立 STL 拓扑审计。
11. 制造模式默认只接受单一连通主体：在几何后端前清理无效、极短和过小元素；放射线需要连续根部连接；导出后检查封闭、裸边、非流形、退化面和独立组件。检查失败必须阻止最终 STL，不能静默导出。
12. 局部高度控制点必须保存到 `.ppg`，且只影响最终后端工作单；当前产品不得显示、缓存或编辑实时三维预览。
13. 当前主工作区只提供 2D 编辑与“原图 / 左右对比 / 叠加对比”。参考图重建只能保存并应用“位置、尺寸、密度、旋转、扭曲、Mask/留白、锚点”等规则参数，不能把像素复制伪装为生成结果。高密度参考图可使用 CV 元素特征工作单，稀疏/粘连图回退连续规则场。
14. 参考图的“原图 / 左右对比 / 叠加对比”必须在真实 Tk Canvas 中可见。左右对比的两个画幅分别独立等比居中，不得从同一全画布缓存裁切中心图形；合成位图由实例持有 `PhotoImage` 引用。发布前至少用 `ImageTk.getimage()` 验证左、右画幅均含可见内容。
15. 点线面 Generator 的缓存键必须可处理参考分析产生的 `reference_elements: list[dict]`；不得将含列表的 `dict.items()` 直接用于哈希。参考图应用流程必须回归“导入 → 分析 → 应用 → Canvas”，并确认无 `unhashable type: 'list'` 和 1×1 `PhotoImage`。
16. Reference2D P0 必须遵循 Image Decode → Preprocess → Classification → Feature Detection → Spatial Fields → Generator Match → Editable Geometry → Similarity 的顺序。ReferenceImage 元数据、DotFeature、SpatialFields、EditableGeometry 和匹配结果必须可 JSON 序列化；位图不得写入 GeneratedLayer。
17. Reference Reconstruction V1 只接受 DOT/HALFTONE/几何点阵：Image Decode → Preprocess → Primitive Detection → Editable Elements → Spatial Analysis → Generator/Modifier Fitting → `EditablePatternDocument`。参数拟合失败必须回退 Direct Element Mode；Reference Layer 只能持有原始图片，Geometry Layer 只能持有真实元素。VTracer/Anionex `trace` 仅用于轮廓、Mask 和开发交叉验证，不能成为点阵识别器或最终产品唯一依赖。
18. `EditablePatternDocument` 的 `base_elements`、`added_elements`、Generator、Modifier Stack 与按稳定 ID 的 Local Override 是 Reference → Editable 2D 的唯一重建输入；`elements` 为物化输出。Canvas、SVG/PNG/DXF、项目恢复与 Rebuild 禁止读取 Raster 或调用旧 Field Generator 来替代 GeometryLayer。
19. Pattern Lab 的固定 Fixture 只能是测试输入；`GridAnalyzer`、SizeGradient 拟合、参数化模式切换和 UI 不得根据文件名、fixture id 或预写参数决定结果。用户导入与 Fixture 必须共享 `PatternDocument.elements → PatternAnalyzer` 路径。
20. Pattern Lab 的参数化入口必须由 `PatternAnalyzer` 调度，而不是被 Grid 写死：只允许从当前 `PatternDocument.elements` 并行分析 Grid、Radial、Along Curve，并始终提供 `FreeParametricModel` 回退；不得读取文件名、fixture id 或预写参数。所有 ParametricModel 必须通过同一 `Evaluate → shared Modifier → Local Override → Element` 路径物化，Canvas/SVG/保存恢复不得自行生成第二套 Geometry。低分结构保持自由元素或进入自由场，绝不提示“非矩阵无法参数化”。Matrix V3 中 Grid 只负责 anchor centroid、行列、Origin 与任意两条 Basis U/V，定义为 `P(i,j)=Origin+i·BasisU+j·BasisV`；禁止绑定 Circle、屏幕 X/Y 或 Canvas 边界。拟合必须支持水平、旋转、斜向、非正交、裁切和部分缺格；方向、间距、位置、内点和占用率分项记录，尺寸相似度不得否决位置格子。ElementPrototype 独立保留 Circle、Ellipse、Rect、Polygon 与 Custom SVG Path 单元；位置完成后才能单独拟合 Linear/Radial/Elliptical Size Field，低质量尺寸拟合保留 Per-Cell Local Override。Grid、Radial、Along Curve 和 Free Parametric 都必须支持 Size/Rotation Field、Mask、稳定 Local Override、Bake、Save/Load 和单次参数操作的一条 Undo。新增 Wave、Flow、Noise、3D 或 UI 重构前，先完成多结构真实导入回归。
21. Gate V 的制造 Mesh 只可从 Gate U.5 已验证的毫米面积 Polygon 生成：XY 不得重标定，Z 必须是 `0..height_mm`，默认高度 2mm 且拒绝非有限/非正高度。孔洞必须贯穿高度；多个 Polygon 保持各自组件，相接边界在未进入专用 Union Gate 前不得自动合并。Mesh 构建必须只读、确定性并有 20×10×2、孔洞、分离/相接与真实 Pattern Lab 回归；STL/3MF、自动修复、最小壁厚和连接策略属于后续 Gate。

## 扩展 API

- **Shape API**：函数返回 `list[Point]` 的简单闭合轮廓。
- **Element API**：输入 `(start, end, style)`，通过 `element_polygon` 输出可绘制和可导出的二维图元；不要耦合 Canvas。
- **Distribution API**：输入轮廓与数量，输出均匀、随机、渐变或曲率驱动的弧长样本。
- **Modifier API**：输入基础属性、索引、总数与 RNG，输出经固定/随机/平滑噪声/渐变修饰后的属性。

## 3D 后端

小芒造物默认使用本地 SDF 连续体后端完成最终 STL，因此安装包不依赖 Blender。Blender 保留为显式兼容的最终建模后端：设置 `XIAOMANG_3D_BACKEND=blender` 或传入路径时，后台 Worker 才会使用 bpy Voxel Remesh。两种后端都必须经过独立封闭、裸边、非流形、退化面与独立组件审计。没有内建 3D Viewer；未来仅可通过 `PreviewProvider` 适配显示，显示组件不得接管业务数据或制造流程。

## 测试与发布

每次修改先运行 `python -m unittest discover -s tests -v`，再运行 `build.ps1`。至少覆盖 100/300/500/1000 元素、Seed 重现、项目往返和三种二维导出。每次正式发布更新 `CHANGELOG.md` 和版本号；保持旧 `.ppg` 可读。

安装器必须采用当前用户安装并生成带版本号的文件名。升级时不得强制终止运行中的软件：只检查即将覆盖的安装路径，提示用户保存并退出该实例；旧版、开发版和测试副本不能误拦截安装。应用本身保持单实例，避免多个进程再次锁定升级文件。发布前执行打包 EXE 的 `--self-test`。

安装目录常量只能在用户选择目录之后的安装事件中读取，不能在初始化事件中展开。构建脚本必须检查每个原生命令的退出码；测试、PyInstaller 或 Inno Setup 任一失败即停止，不能把历史安装包当作新版本交付。
