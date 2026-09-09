---
name: xiaomang-creation
description: 小芒造物的参考图到可编辑二维、清理几何、本地/Blender 建模和已验证 STL 的总编排 Skill。用户要求完整制造链、批量检查或跨阶段交接时使用。
---

# 小芒造物 Skill 系统

这是项目自己的流程入口，不是第三方 Skill 的合并包。它把一次运行拆成可恢复的阶段，并用统一 handoff contract 传递文件、参数、单位、验证结果和错误。

## 触发与边界

- 当用户要求“参考图/参数 → SVG 或可编辑 2D → 清理 → 三维后端 → STL”、生成最终模型、制造检查或跨阶段恢复时触发。
- 仅 UI 设计、普通图片导出或新增 Generator 时，不强行触发完整制造链。
- 本轮只复用已有 Generator 注册表；缺少匹配规则时报告缺口，不在本 Skill 中偷偷新增算法。
- UI 不直接导入 `bpy`。默认使用本地 SDF 后端；只有显式选择 Blender 兼容模式时，才通过 `ppg/blender_worker.py` 的 JSON 工作单边界调用。

## 调用顺序

1. 读取 `references/handoff-contract.md` 和 `references/handoff_contract.schema.json`。
2. `xiaomang-reference` 保留原图并输出可解释的参考分析。
3. `xiaomang-reference-reconstruction` 对 DOT/HALFTONE/几何点阵执行检测优先的 EditablePatternDocument 重建；拟合失败时保留 Direct Element Mode。
4. `xiaomang-generator` 将分析映射到现有 Generator 和可编辑规则。
4. `xiaomang-geometry` 把规则清理为毫米制、可连接的二维几何。
5. `xiaomang-manufacturing` 在进入 Blender 前执行尺寸、最小特征、连通性和打印约束预检。
6. `xiaomang-native`（默认）或用户明确选择的 `xiaomang-blender` 将通过预检的清理结果构建并读回最终制造网格事实；当前没有实时三维预览阶段。
7. `xiaomang-stl` 仅从通过验证的后端结果导出 STL。
8. `xiaomang-quality` 执行最终网格读回、拓扑审计和制造里程碑；失败则阻止交付。

每一步都更新同一个 contract，写入 checkpoint；下游只消费上游 `status=passed` 的 artifact。任何失败都保留工作目录和报告，不能用旧结果冒充成功。

`scripts/validate_handoff.py` 提供无第三方依赖的本地门禁，可在 Worker 或 CI 导出前校验 contract。

## 产物

最少产物为：原始参考图、analysis JSON、可编辑 SVG/规则 JSON、clean geometry JSON/SVG、后端 job/readback JSON、STL、质量报告和制造报告。每个产物必须有绝对路径、SHA-256、生成阶段和状态。

## 失败与恢复

优先从最近一个通过的 checkpoint 重跑；不要覆盖原始参考图、用户项目或已交付 STL。若修复会改变设计规则，创建新的 `run_id` 和变体，而不是修改旧运行记录。
