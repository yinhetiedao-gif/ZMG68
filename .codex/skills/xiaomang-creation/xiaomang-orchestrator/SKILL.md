---
name: xiaomang-orchestrator
description: 编排小芒造物 Reference → Editable 2D → Clean Geometry → 本地/Blender → Validated STL 的分阶段工作流，管理前置条件、handoff、checkpoint 和失败回滚。
---

# Xiaomang Orchestrator

## 何时使用

用户要求从参考图或当前项目一路生成可打印 STL、重新跑某个阶段、查看制造链状态，或需要跨 Skill 的一致交接时使用。

## 执行规则

1. 创建 `run_id`，读取并校验统一 contract；确认输入路径存在、单位为 mm、输出目录可写。
2. 按 `xiaomang-reference → xiaomang-generator → xiaomang-geometry → xiaomang-manufacturing → xiaomang-native（默认）/ xiaomang-blender（兼容的最终建模） → xiaomang-stl → xiaomang-quality` 顺序调用；不得插入实时 3D Viewer 或预览网格阶段。
3. 每阶段完成后写 checkpoint 和 artifact 哈希；下游只能读取上游通过的 artifact。
4. 失败时停止链路并给出中文错误、失败阶段和可重跑 checkpoint；不静默降级、不复用历史 STL。
5. 支持从最后通过阶段继续，或从任一 checkpoint 创建新的变体运行。

## 不负责

不实现图像算法、二维几何、后端细节或 UI；这些由专用 Skill 和现有 `ppg` 模块负责。
