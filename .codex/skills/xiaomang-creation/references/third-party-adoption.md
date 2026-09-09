# 第三方经验采纳边界

本文件记录“学习原则”而非复制实现。第三方代码、插件清单、命令协议和产品方向均不进入小芒造物运行时。

## 采纳

- **bestmaa/codex-blender**：本地 HTTP/结构化 JSON Bridge、先检查场景再编辑、保存/渲染/导出和明确的本地进程边界。小芒造物对应 `ppg/blender_worker.py`，UI 只提交工作单。
- **powerhouse90/Blender-Superskill**：reference-first；建模前先拆解参考和锚点，连接处做近景检查，并采用 inspect → repair → 再验证，而不是一键“看起来像”。
- **nodecue/blender-node-skills**：Geometry Nodes 的节点/Socket 版本意识、构建后 readback、只保留必要节点以及失败自修复。小芒造物要求写入 `blender_readback`，不把执行返回值当作事实。
- **jithinolickal/blender**：先简单分解再参数化、曲面函数使用平滑过渡、顶/正/侧/透视多视角验证，以及每次修改前保存 milestone。
- **RobLe3/cc-blender-skill**：按职责拆分可链式 Skill、由协调层管理优先级和 handoff、质量细化循环、把 STL 当独立 export domain 并设置打印门槛。

## 明确拒绝

- 不复制任何第三方仓库的代码、插件 manifest、MCP 端口、命令名或许可证文本到产品。
- 不把外部 MCP/Blender UI 当作用户操作前提；小芒造物继续使用自己的后台 Worker 和中文 UI。
- 不采用“任意图片都能完美转 3D”、只看单一角度、只增三角面数或跳过拓扑/打印检查的做法。
- 不因参考图而改变产品定位，不把第三方 Skill 变成新的 UI 或 Generator。

