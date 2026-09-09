---
name: xiaomang-blender
description: 当用户明确选择 Blender 兼容后端时，通过小芒造物 Blender Worker 在后台构建、检查和读回参数化模型；默认制造流程使用 xiaomang-native，不要求 Blender。
---

# Xiaomang Blender

## 边界

只接受已通过 `clean_geometry` 的 JSON 工作单。仅当用户或开发配置明确选择 Blender 兼容后端时，使用 `ppg/blender_worker.py` 查找 Blender、启动后台进程并传参；UI 不导入 `bpy`，不要求用户手动操作 Blender。没有 Blender 时应转回 `xiaomang-native`，而不是阻断普通 STL 导出。

## 建模与读回

- 先保存 Blender checkpoint，再构建主体、线/面、厚度、圆润和有机融合参数。
- 优先使用项目选定的连续体素/隐式融合与适当平滑；质量档改变最终采样精度，不把 Canvas 预览当 STL 来源。
- 若使用 Geometry Nodes，按当前 Blender 版本验证节点标识和 socket；构建后必须读回节点树、对象、尺寸、面数和 modifier 状态，不能只相信执行返回值。
- 输出 `blender_job`、`blender_readback` 和最终网格审计证据；读回不一致时进入 repair，不得继续导出。不得创建或驱动实时 3D Viewer。

## 失败处理

Blender 不可用、工作单不合法、生成超时或读回不一致时，保留日志和 checkpoint，返回可重跑错误码。
