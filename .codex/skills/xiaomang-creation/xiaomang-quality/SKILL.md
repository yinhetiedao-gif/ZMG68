---
name: xiaomang-quality
description: 对小芒造物结果执行参考对照、本地/Blender 最终网格检查修复、STL 拓扑审计和制造里程碑发布；最终交付前或反馈质量问题时使用。
---

# Xiaomang Quality

## Quality Loop

1. 冻结当前 run 和 baseline，记录参数、Seed、软件/Blender 版本。
2. 检查参考分析与 editable 2D 的轮廓/密度规律，再检查清理几何的连通性。
3. 读取对象、modifier、节点（如有）和最终网格统计；发现问题时只改一个主要参数或一个修复步骤，重新读回。
5. 最后运行 STL 拓扑与打印审计，生成 milestone 报告；所有门槛通过才将 run 标记 `released`。

报告区分“规则匹配”“几何有效”“打印可行”和“审美质量”，不把单一截图当作制造证明。
