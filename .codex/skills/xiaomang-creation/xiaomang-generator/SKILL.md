---
name: xiaomang-generator
description: 将参考分析映射到小芒造物现有 Generator 注册表，生成可编辑二维规则和 SVG；需要从分析结果生成新变体或参数化规则时使用。
---

# Xiaomang Generator

## 执行规则

- 只调用 `ppg/generators/` 注册的 Generator 和 `ppg/field_generators.py` 的统一 API；不在 UI 或本 Skill 中复制算法。
- 根据分析置信度选择已有规则，保留 `generator_id`、版本、参数默认值、Seed、Mask 和 Modifier Stack。
- 生成必须可重现：同一输入、参数和 Seed 的规则 JSON 与 SVG 哈希一致；变体只能改变明确的参数或新 Seed。
- 规则应表达位置场、尺寸场、密度场、旋转/扭曲、Mask/留白等可编辑信息，而不是逐像素贴图。
- 没有可靠匹配时输出 `needs_new_generator=true` 和建议接口，停止进入制造阶段，除非用户明确选择已有近似规则。

## 交接

写入 `editable_2d` artifact（规则 JSON、SVG、边界框、目标宽度、单位和连通性预期），并引用上游 analysis artifact 的 ID。

