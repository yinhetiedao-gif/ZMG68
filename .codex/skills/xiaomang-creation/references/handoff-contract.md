# Xiaomang Handoff Contract v1.0

所有阶段共享一个 JSON envelope，文件名建议为 `handoff.<run_id>.json`。详细字段约束见同目录 `handoff_contract.schema.json`。

## Envelope

```json
{
  "contract": "xiaomang.handoff",
  "version": "1.0",
  "run_id": "2026-08-27T120000Z-abc123",
  "created_at": "2026-08-27T12:00:00Z",
  "source": {"kind": "reference_image", "path": "C:/.../reference.png", "sha256": "..."},
  "intent": {"operation": "reference_to_stl", "target_width_mm": 100.0, "allow_multi_component": false},
  "stages": {
    "reference": {"status": "passed", "artifact_ids": ["a-analysis"]},
    "generator": {"status": "passed", "artifact_ids": ["a-editable"]},
    "geometry": {"status": "passed", "artifact_ids": ["a-clean"]},
    "manufacturing": {"status": "passed", "artifact_ids": ["a-preflight"]},
    "blender": {"status": "passed", "artifact_ids": ["a-readback"]},
    "stl": {"status": "passed", "artifact_ids": ["a-stl"]},
    "quality": {"status": "passed", "artifact_ids": ["a-report"]}
  },
  "parameters": {"units": "mm", "seed": 1, "quality": "standard"},
  "artifacts": [{"id": "a-stl", "kind": "stl", "path": "C:/.../model.stl", "sha256": "...", "producer": "xiaomang-stl", "status": "passed"}],
  "validation": {"passed": true, "checks": []},
  "errors": [],
  "rollback": {"checkpoint": "C:/.../checkpoints/geometry.json", "reversible": true}
}
```

## 不变量

- 所有路径为绝对路径；长度、厚度、间隙和边界框使用 mm。
- `run_id`、artifact `id`、生成器版本和 Seed 必须可追溯；artifact 必须有 SHA-256 和 producer。
- 阶段状态只能是 `pending`、`running`、`passed` 或 `failed`；只有上游 `passed` 才能启动下游。
- 原始参考图只读保存；可编辑 2D 必须是规则/矢量产物，不得以位图冒充参数化结果。
- `blender` 阶段是历史兼容字段，实际 producer 可为 `xiaomang-native` 或 `xiaomang-blender`；默认使用本地 SDF readback。兼容模式下，`stl` 只有在 Blender 读回、制造预检和质量审计通过时才可标记 `passed`。
- 失败不删除输入或 checkpoint；修复产生新 artifact，旧 artifact 保留以支持回滚。

## 阶段 payload 约定

`reference_analysis`、`editable_2d`、`clean_geometry`、`blender_job`、`blender_readback`、`manufacturing_preflight`、`stl_output`、`quality_report` 均放在 envelope 的 `payload` 下；字段可扩展，但不得改变上述 envelope 和状态语义。
