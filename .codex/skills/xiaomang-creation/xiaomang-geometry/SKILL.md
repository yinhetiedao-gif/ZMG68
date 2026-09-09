---
name: xiaomang-geometry
description: 清理和规范二维轮廓/点线面几何，统一毫米单位、修复短碎片与断连，并为本地/Blender 三维后端准备 clean geometry artifact。
---

# Xiaomang Geometry

## 检查与清理

1. 解析 editable SVG/规则 JSON，确认平面、有限坐标、闭合轮廓和非零面积。
2. 使用现有几何内核进行去重、去短段、简化、闭合、方向统一、弧长采样和外侧判断；不得在 UI 重写几何算法。
3. 按喷嘴/线宽和目标单位检查最小线宽、孔洞、间隙、重叠和连通组件；显式记录自动修复内容。
4. 输出 `clean_geometry`（SVG + JSON），包含 component 数量、边界框、总长度、最小特征和 `connected`。多组件默认阻断单一面料 STL。

清理必须幂等：对同一输入重复运行不应继续改变坐标。任何不安全修复都改为报告错误而不是猜测。
