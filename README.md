# Xiaomang Pattern Lab / 小芒图案实验室（当前活跃项目）

## v0.2-M1 — 软件内制造工作流

顶部“制造”按钮打开独立制造窗口。用户可设置唯一制造参数“厚度（mm）”，点击“检查并生成”后查看二维几何、连通组件、制造转换和 Mesh 摘要；只有 Gate W 无错误时才能通过系统保存对话框导出 Binary STL。多组件会明确警告但不自动连接，也不阻止合法导出。

该窗口只编排既有 `PatternDocument → Evaluate → T → U → U.5 → V → W → X` 链路。检查、生成和导出均为临时派生操作，不修改工程、不增加 Undo、不改变 Dirty。设计或厚度变化后必须重新检查。技术详情保存在窗口详情区和现有日志中。本阶段没有 3D Viewer、自动修复、Union、桥接或新制造算法。

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
