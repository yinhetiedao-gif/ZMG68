# Roadmap

## 当前：Xiaomang Pattern Lab Web v0.1 Alpha（2026-10-01）

- [x] Web Alpha 设计制造闭环：图片/SVG → 可编辑二维 → Layout → Field → Modifier → Mesh Validation → Three.js 预览 → Web STL 下载。
- [x] Web Alpha 实物验收：用户确认网页版 STL 已在 Bambu Studio 中切片并真机打印，成品正常。记录为用户反馈，不推断任意图案/材料均可打印。
- [x] 冻结 `web-v0.1-alpha` 与 `backup/web-v0.1-alpha-physical-validated`；本轮不开发新功能。
- [ ] 后续另行立项 Fabric：F0 架构蓝图 → F1 Fabric Base → F2 Unit Cell Library → F3 Height/Density/Orientation → F4 Image-driven Fabric → F5 Manufacturing Validation → Fabric Alpha。此处仅为计划，均未开始。
- [ ] 其他独立计划：项目完整持久化/云端产品化、3MF、自动连接/修复、最小壁厚与打印配置。Web Alpha 冻结不包含这些能力。

## 历史阶段快照：Xiaomang Pattern Lab（2026-09-23）

- [x] v0.1-alpha 制造闭环：Design → Parametric → Manufacturing2D → 3D Mesh → Validation → STL → Bambu Studio → Physical Print。
- [x] Gate T/U/U.5/V/W/X；两次实物验证 PASS（用户确认，范围见 GATE_STATUS.md）。
- [x] v0.2-M1：Manufacturing UI，将现有制造 API 接入用户操作流程；厚度、摘要、阻止错误、STL 保存均已接入。
- [x] v0.2-M2：Lightweight 3D Preview，只读显示最终制造 Mesh，支持 Orbit/Zoom/Fit/Reset、孔洞和多组件。
- [x] WM1：Headless Manufacturing Application Service；桌面 UI 已通过同一无 Tk Service 调用 T→X，未来 API 不需要复制制造编排。
- [ ] Basic Manufacturing Warnings，孤立组件、过细结构与最小壁厚提示，不自动修复。
- [x] WM2：版本化 Web Contract / DTO v1（schema_version、document_revision、资产引用、毫米报告和制造结果身份）；实现范围见 `docs/WEB_CONTRACT_V1.md`。
- [x] WM3：本机 FastAPI Headless Server v1；可用 HTTP 调 Evaluate / 制造 / 同结果 STL，仍无 Web UI；见 `docs/WEB_SERVER_WM3.md`。
- [x] WM4：React/TypeScript/Vite Web Shell，三栏布局与 WM3 Health/Contract 握手；尚无 2D 编辑或制造入口。见 `docs/WEB_SHELL_WM4.md`。
- [x] WM5：2D Viewer/Editor Foundation，打开项目 JSON、Python Evaluate、最终二维 SVG、毫米坐标视图与有限的自由源元素拖动；见 `docs/WEB_2D_WM5.md`。
- [x] WM6：现有参数化配置的网页检查器、提交一次求值、会话撤销/重做和失败回滚；只读字段与浏览器验收限制见 `docs/WEB_PARAMETRIC_WM6.md`。
- [ ] 后续 Web Prototype：图片上传、参数调整、制造、Three.js 只读 Mesh 与 STL 下载。WM5 不提前实现。
- [ ] 后续独立规划：3MF / AI / 自动连接 / 高级制造。

本段记录当时的桌面 v0.1-alpha 冻结状态；其“后续 Web Prototype”待办不代表 2026-10-01 的 Web Alpha 现状。桌面版本代码基线 d1ed14e，最终冻结提交以 v0.1-alpha tag 为准。

## 旧版小芒造物历史路线（不是当前 Pattern Lab 完成清单）

- [x] **P0：图片 STL 表面质量** — 连续 SDF、圆角厚度场、独立最终网格、四档质量和基本 STL 拓扑审计。
- [x] **P1：小芒造物 1.6 UI** — 浅灰、白色、稳重蓝色的清晰双栏工作台与中文控件状态。
- [x] **P2：点线面 Generator / 图片分析** — 可解释特征分析、半调/点阵/点线面生成、完整参数、实时预览、变体和 SVG/PNG/DXF 输出。
- [x] **P0/P2：统一参数与可访问工具栏** — 扩展 Field 参数系统、流/波/噪声场、可滚动搜索参数页和横向滚动/更多工具栏。
- [x] **P3：Blender 最小 3D Worker** — 后台 bpy、Geometry Nodes 体素融合、平滑 STL、中文状态和拓扑审计。
- [x] **3D Viewer 收缩** — 已删除自研实时 3D Canvas、相机、显示模式、预览 Mesh 与效果图入口；最终制造 Mesh/STL 后端继续保留。

- [x] **V1.0：造物工坊二维创作版** — 中文 UI、导入/手绘轮廓、多类元素、自定义 SVG、均匀/随机/渐变/曲率分布、平滑噪声、实时预览、项目/预设/Undo、SVG/PNG/DXF、构建与安装程序。
- [ ] **Phase 2：二维扩展** — 自定义 SVG 元素、叶片/水滴/尖刺等元素、高级分布与 Modifier、曲率驱动、完整 DXF 轮廓支持。
- [ ] **Phase 3：最终制造模型** — 厚度、高精度最终 Mesh、STL、基础打印检查；不引入实时 Viewer。
- [ ] **Phase 4：高级制造几何** — 全立体、厚度场、根部/末端融合与更完整的打印检查；如需显示，采用独立第三方 PreviewProvider。
- [ ] **Phase 5：打印与性能** — 网格修复、最小壁厚分析、后台任务、进度取消与性能剖析。
