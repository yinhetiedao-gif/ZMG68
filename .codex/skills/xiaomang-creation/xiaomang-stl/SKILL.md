---
name: xiaomang-stl
description: 从通过制造预检和本地/Blender 后端读回的最终模型导出、修复并审计 STL；用户点击生成/导出 STL 或要求可打印文件时使用。
---

# Xiaomang STL

## 导出门槛

只有 `clean_geometry`、后端 readback 和 `manufacturing_preflight` 均为 `passed` 才能导出。默认使用 `xiaomang-native` 的最终高质量 SDF 流程；显式兼容时才使用 Blender Worker，绝不直接拿实时预览网格或旧 STL。

## 审计

导出后记录格式、三角面数、边界框、法线方向、Naked Edge、Non-manifold、退化面、自交风险、Disconnected Components、Watertight 和最小壁厚。可安全修复的法线/退化面自动修复后重新审计；无法安全修复则阻断并返回报告。

成功时写入 `stl_output` artifact（绝对路径、SHA-256、质量档、单位、来源 run_id）和用户可读的中文结果。
