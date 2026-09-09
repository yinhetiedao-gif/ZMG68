---
name: xiaomang-native
description: 无需安装 Blender 时，为小芒造物执行本地 SDF 最终网格、STL 导出与拓扑审计。
---

# Xiaomang Native

## 适用范围

当用户需要从当前可编辑二维图元生成最终三维模型或 STL，且不希望安装/启动 Blender 时使用。它是小芒造物的默认本地制造后端；Blender 仅作为显式兼容选项，不得成为 UI 的安装前提。

## 工作流

1. 接收已经清理过的二维图元工作单，单位统一为 mm，并保留 Seed、质量档、基础厚度、圆润程度和有机融合参数。
2. 将点、线、面栅格化为质量档对应的高分辨率实体 Mask；用连续 SDF、圆角厚度场和 Marching Tetrahedra 重新构建封闭体，不直接导出低面数预览网格。
3. 独立检查 STL 的封闭性、裸边、非流形边、退化面和独立组件；失败时阻止交付并返回中文原因。

## 交接

运行时实现位于 `ppg/native_stl.py`。`run_blender_job` 这个兼容命名的接口会在默认配置下转发到本后端，以保持已有项目和 handoff contract 兼容。只有设置 `XIAOMANG_3D_BACKEND=blender` 或显式传入 Blender 路径时才走兼容后端。

## 质量门槛

- 多个互不连接组件默认拒绝作为单一面料导出；只有用户明确允许多部件时才放行。
- 所有最终尺寸、厚度和审计结果写入现有 handoff contract，并保留 checkpoint 以便回滚。
- 修改后运行 `python -m unittest discover -s tests -v`、打包自检和至少一次无 Blender 的本地 STL 回归。
