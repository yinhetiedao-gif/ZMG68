---
name: xiaomang-reference
description: 解析 PNG/JPG/SVG 参考图，提取轮廓、点线面、密度与方向规律，产出可解释的分析 JSON；参考图导入、分析或重建请求时使用。
---

# Xiaomang Reference

## 目标

把参考图当作“生成规则的证据”，不是最终几何。保留原始文件只读副本，记录路径、尺寸、色彩空间和 SHA-256。

## 输出

使用现有 `ppg/image_analysis.py` 生成 `reference_analysis`：阈值、黑色覆盖率、连通组件、紧致度/线性比例、方向性、网格周期、径向密度、元素候选和置信度。明确给出主体轮廓、基础元素、排列/渐变规律以及推荐 Generator；低置信度必须标记 `needs_new_generator=true`。

分析结果不得包含“已复制像素”的承诺，也不得覆盖原图。只有通过 schema 校验的分析 artifact 才能交给 Generator。

