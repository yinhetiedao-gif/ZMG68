# 小芒造物｜功能状态（1.6.44）

> 当前唯一活跃项目为 `xiaomang_pattern_lab`（小芒图案实验室）。下表大部分为旧版/历史状态；
> 新实验室当前的实际阶段状态以 `GATE_STATUS.md` 为准。

| Pattern Lab Gate S：项目工作流 | ✅ PASS | 文件菜单、新建/打开/保存/另存为、标题 dirty 标记、Undo 保存点、最近项目、独立恢复副本、原子保存、集中迁移和参考图重定位已通过 27 项专项测试；Gate T 及之后尚未开始。 |

| 功能 | 状态 | 说明 |
| --- | --- | --- |
| 旧 Reference Reconstruction：Raster → EditablePatternDocument | ⚠ Legacy | 保留用于兼容既有项目和回滚；新上游 POC 不再以自研 CV/Generator 猜测作为唯一入口。 |
| EditablePatternDocument Rebuild | ✅ Working | `base_elements + added_elements → Base Generator + Modifier Stack → Local Overrides → elements`。Rebuild、导出、保存/恢复均不重新读取 Raster；删除、复制、移动、尺寸、旋转和分组均按稳定元素 ID 保存。 |
| 放射纹样、SVG/PNG/DXF | ✅ Working | 已可编辑、保存、导出。 |
| 点线面 / 半调 Generator | ✅ Working | 支持网格、图像映射、渐变、随机、分形噪声、变形与多种元素；大规模预览采用批量 Canvas 位图，参考分析应用后缓存键可安全处理元素工作单。 |
| 参考图空间规则重建 | ✅ Working | V1 以确定性测量分析位置、尺寸、密度、旋转和扭曲；仅在 Grid/Radial 拟合可靠时启用 Parametric Mode，提供 Size/Density/Rotation/Mask/Warp Modifier。其他情况保持可编辑 Direct Element Mode，不复制位图。 |
| 原图 / 重建对比 | ✅ Working | 支持重建结果、原图、左右对比与叠加对比，透明度可调；左右栏各自完整等比居中，不裁断中心图片。 |
| 二维实时预览 | ✅ Working | 33ms 交互节流、120–140ms 标准重建；只更新可编辑 2D Canvas，绝不触发临时三维网格。 |
| 自研 3D 实时预览 | 🗑️ Removed | 3D Tab、Viewer、相机、渲染模式、预览 Mesh 缓存、局部三维交互和效果图入口已从运行链删除，避免干扰核心二维重建。 |
| 流场 / 波场 / 噪声场 | ✅ Working | 通过统一 Field Generator API 生成，参数实时生效。 |
| 顶部横向滚动与更多菜单 | ✅ Working | 箭头、滚轮、Shift+滚轮、触控板滚动和“更多”均可访问操作。 |
| 本地后台 STL（默认） | ✅ Working | 无需 Blender；二维最小特征清理、连续 SDF 圆角厚度场、Marching Tetrahedra、修复及独立 STL 封闭/组件审计均实际测试。断开组件默认阻止导出。 |
| Blender 后台 STL（兼容） | ✅ Optional | 仅显式设置兼容后端时启用；不再是安装和运行前提。 |
| Xiaomang Skill 运行时编排 | ✅ Working | “导出 STL”已接入 handoff contract：记录规则快照、Generator、几何清理、制造预检、本地/Blender readback、STL 与质量审计；每阶段写入 SHA-256 和 checkpoint。 |
| 最终模型后台生成 | ✅ Working | 只从当前 EditablePatternDocument 的物化元素（兼容项目则从二维规则工作单）构建最终制造 Mesh，完成后显示尺寸、面数、组件与审计状态。 |
| Height / Thickness 最终工作单 | ✅ Basic Working | 厚度、圆润、有机融合与已保存的高度控制只在最终制造后端生效；不再存在局部三维 Brush 或实时画面。 |
| 参考图真实元素提取 | ✅ Working | DOT/HALFTONE/几何点阵使用确定性检测；粘连圆点通过距离变换 + 局部峰值 + watershed 分离。PNG/JPG/WEBP 导入后立即建立 ReferenceLayer 与 GeometryLayer，调试图可输出检测框、中心、半径和分区。 |
| 小芒造物 1.6 UI | ✅ Working | 回归浅灰、白色、稳重蓝色双栏工作台，中文界面优先。 |
| 自定义 SVG 作为点线面单元 | ⚠ Partial | 已支持外围放射元素；Field Generator 的重复 SVG 单元待实现。 |
| 自交、最小壁厚、完整打印检查 | ⚠ Partial | 已检查封闭、裸边、非流形、退化面、独立组件和最小边长度；自交、材料相关最小壁厚与实际切片机验证仍待补充。 |
| 上游 Raster → Editable SVG | ✅ POC | 已安装原始 `ujo78/imagetosvg-mcp`、`aeren23/image-processing-skills`、`linyaosky/svg-skill`；三类点阵图完成转换、Inspect、单层 Edit、Render、Optimize 回归。正式 Canvas 接入在下一阶段。 |
| Pattern Lab 直接编辑性能 | ✅ Working | 静态 Canvas 图元与瞬态 `InteractionState` 分离：拖动不重建完整画布、不更新 PatternDocument、不连续序列化 SVG/写 Undo；释放时一次性提交。性能 Debug 显示真实计数与帧耗时。 |
| Pattern Lab 矩阵参数化 V2 | ✅ Working | `evaluate_pattern_document()` 统一执行 `Grid + ElementPrototype → Size/Mask Modifier → Local Override`。Grid 位置拟合只读取所有真实 Element 的 anchor centroid，不绑定 Circle 或 Canvas 边界；支持 Circle、Ellipse、Rect、FilledRegion/Custom SVG Path 的重复单元、非方阵、大边距、旋转、少量缺格、Size Gradient、Bake 与保存恢复。 |
| Pattern Lab 通用二维晶格 V3 | ✅ Working | 使用 `P(i,j)=Origin+i·BasisU+j·BasisV` 从所有 Element centroid 拟合任意方向的二维格子；支持旋转、斜向、非正交、裁切／部分缺失和强尺寸变化。位置结构与尺寸场独立评分；显式 Basis U/V、Radial/Elliptical Size Field、Local Override 与保存恢复均已回归。 |
| Pattern Lab 多结构 + 自由场参数化 | ✅ Working | `PatternAnalyzer` 并行比较 Grid、Radial 与 Along Curve；可靠候选转换为对应 `ParametricModel`，低分图案进入 `FreeParametricModel`。所有路径共用真实 Element、Mask、Size/Rotation Field、Local Override、Evaluate、SVG 导出与 Save/Load。 |
| Placement / Prototype / Assignment 基础层 | ✅ Gate 1 + M.1 | `PlacementSlot` 将导入元素与既有 Grid 统一为空间槽位；`ShapePrototypeRegistry` 复用现有 `ElementPrototype`；`ReplacementMap`、Assignment/Random 设置和 `AssignmentEngine` 通过可选 metadata 接入。默认关闭时 Circle Grid 保持原始稳定 ID 与几何；替换不破坏源 Elements。Gate M 以 SHA-256 stable hash 按 Slot 分配；Gate M.1 将既有 `ModifierScope` 复用于形状池，支持全部、选择快照、圆形、矩形和反转，范围外保持原形、手动替换优先。 |
| 随机变换与密度 | ✅ Gate N | 在同一 Placement Assignment metadata 的 `RandomSettings` 中持久化独立 Seed、Size、Rotation、X/Y Jitter、Occupancy 与 Scope。随机由稳定 `slot_id + channel` 哈希得出，未命中 Scope 不变；0% 隐藏、100% 全可见。Shape Pool Seed 独立，调变换不会重新分配形状；隐藏元素不导出 SVG，但保留于项目 JSON。 |
| 参数预设 | ✅ Gate O | 独立、版本化的本地 `ParametricPreset` 保存效果配置而非 Project：Fields、Modifier Stack/顺序、Scope、Shape Pool、Random/Density 与 Seed 可跨图案应用。预设保存在 Pattern Lab 工作区 `presets/`，不保存 Raster、源元素、选择、视图、手动替换或局部覆盖；应用时按照当前源 Geometry Bounds 适配世界坐标参数，并保持目标 Geometry 非破坏式。 |
| 图片驱动参数场 | ✅ Gate P | `ImageField` 将当前 Reference 灰度映射为共享 `0..1` 标量，支持黑白反转、对比度、黑/白场阈值、超界策略与按文件时间缓存；可驱动既有 Size Modifier，缺失图片安全回退，不保存像素。 |
| 有机噪声参数场 | ✅ Gate Q | `NoiseField` 在世界坐标/mm 生成连续、Seed 可复现的 fBm 标量；可由尺寸、旋转、通用位置与密度消费者共享，保留 Source Geometry，纯几何项目无原图时安全运行。 |
| Shared Parametric Modifier Stack | ✅ Working | `SharedModifierStack` 将 Geometry Source 与 Size Field、Rotation Field、Mask、Local Override 分离；Gate H 增加有序 Size/Rotation 层列表，支持启停、复制、删除、上下移、重置以及 Save/Load。导入 Elements 无需先识别 Grid 即可使用；Grid/Radial/Curve 作为结构源时也可叠加同一效果层。旧工程无此 metadata 时保持兼容。 |
| Position / Deformation Modifier | ✅ Gate I | 有序堆栈位置层支持整体偏移、吸引、排斥、径向推出、扭转和波形位移；只修改派生几何，保留 source Elements。支持中文参数入口、启停、排序、复制、删除、重置及 Save/Load；Mask / Scope 仍待 Gate J。 |
| Position / Deformation UI | ✅ Gate I-UI | 六种位置模式按需显示参数，并使用 Slider + Numeric Entry。范围根据 source bounds 与参数语义设置；拖动仅临时预览、释放一次提交，模式切换和同模式 Reset 均支持 Undo/Redo。内部英文 ID、mm/radian/0..1 schema 不变。 |
| Modifier Scope / Mask | ✅ Gate J | Size、Rotation、Position 共用同一个 `ModifierScope`；支持全部、选择快照、圆形、矩形和反转。Scope 在每层 Evaluate 前按 Element 中心判定，未命中元素保留上一层结果；旧层缺少 scope 时等价于全部。UI 使用中文和毫米 Slider/Entry，支持预览、Undo/Redo、Save/Load 与 SVG。 |
| Shape Replacement / 形状替换 | ✅ Gate K | 单个 PlacementSlot 可非破坏式替换为圆形、正方形、菱形、三角形、星形或线形；默认 Fit Bounds。ReplacementMap 与原始 Element 快照写入 PatternDocument metadata，恢复、Undo/Redo、Save/Load、Grid 重建和 SVG 导出均保留一致性。当前不含批量替换、随机形状池和自定义 SVG。 |
| Multi Selection / 批量编辑 | ✅ Gate L | 复用 `selected_ids` 实现 Shift 点击、世界坐标框选、Shift 追加、Ctrl+A 与 Escape；可批量替换/恢复形状、缩放、相对旋转、位移和非破坏式隐藏。多选拖动仅在释放时写一次事务；选择状态本身不写入项目。 |
| Pattern Lab 结构路由与输入稳定性 | ✅ Working | Along Curve 先通过二维内在维度门禁，避免规则二维 Grid 被贪心最近邻链误判；Grid 数值统一严格解析，非 Grid 模式禁用 Grid 控件，UI 回调完整 traceback 写入 diagnostics。 |
| Pattern Lab Halftone Element Debug | ✅ Working | 多尺度 small/medium/large Dot 识别会恢复/标注真实元素。显示 detected、renderable、visible filled、invalid 和 unknown 统计；闭合黑色语义 Path 以实心几何渲染，不再显示为空 Bounding Box。 |
