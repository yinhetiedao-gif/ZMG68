# Pattern Lab Web Contract v1（WM2）

本文件定义浏览器与 Python 应用服务之间的 JSON 数据边界。当前只有 Python DTO/Mapper，尚无 HTTP API。唯一持久设计数据仍是 `ppg.foundation.PatternDocument`；`PatternDocumentDTO.document` 直接复用正式项目文件的 `PatternDocument.to_dict()` 结构，读取时调用正式 schema 迁移入口和 `PatternDocument.from_dict()`。

## 版本、身份与传输

- 每个顶层 DTO 的 `schema_version` 固定为字符串 `"1.0"`，由 `CURRENT_WEB_SCHEMA_VERSION` 集中定义。读入未知版本直接返回 `invalid_schema_version`。
- `document_id` 是传输层的逻辑标识；`document_revision` 是非负整数。它们不写回 PatternDocument。写入前须核对当前 revision；旧 revision 报 `stale_revision`。WM3 才决定 HTTP 409。
- JSON 只允许 null、布尔值、整数、有限数、字符串、数组和字符串键对象。`canonical_json()` 使用 UTF-8 文本、稳定键顺序与标准 JSON；`parse_json()` 拒绝 NaN/Infinity。DTO Mapper 拒绝 Python 对象和本机绝对路径。
- 设计坐标使用文档 Canvas 的既有单位；求值结果和报告的坐标使用世界毫米。没有 `mm_per_unit` 且 Canvas 不是 `mm` 时，毫米求值明确报 `missing_mm_mapping`。Path 的 `path_data` 是元素局部 SVG 命令，`x/y/width/height/base_*` 是世界毫米；字段 `path_data_coordinate_system="element_local"` 明示这一点。

## 文档与资产

`PatternDocumentDTO`：`schema_version`、`document_id`、`document_revision`、`document`、`assets[]`。`document` 保留正式项目的 Element IDs、Groups、Transforms、Grid/其他 Parametric 元数据、Field/Composite Field、Modifier 顺序、Local Override、Shape Replacement、Random/Occupancy 与当前可持久配置。它不包含选择、Hover、鼠标、Zoom/Pan、Tab、窗口、3D 相机或滚动位置。

桌面 `reference.source_path` / ImageField `image_path` 不能直接传输。调用 `PatternDocumentDTO.from_document(..., asset_bindings={本机路径: "asset-123"})`，DTO 将路径清空，并用 `assets[]` 描述 `reference` 或 `field:<field_id>` 与资产 ID 的关系。缺失绑定直接报 `unbound_asset`；其他 metadata 中出现绝对路径会报 `local_path_forbidden`，不静默丢弃。服务端将来通过自己的资产解析器向 `to_document(asset_sources={"asset-123": 本机路径})` 注入路径；未绑定时几何仍可恢复，但图片驱动 Field 需资产解析后才能重现取样。WM2 没有上传、存储或下载接口。

```json
{
  "schema_version": "1.0",
  "document_id": "doc-123",
  "document_revision": 17,
  "document": {
    "schema_version": 1,
    "canvas": {"width": 80, "height": 50, "unit": "mm", "mm_per_unit": 1, "origin_x": 0, "origin_y": 0},
    "reference": {"source_path": "", "visible": false, "preprocessing": {}, "metadata": {}},
    "elements": [], "groups": [], "transforms": {}, "metadata": {}, "fields": [], "modifiers": []
  },
  "assets": []
}
```

## Evaluate

`EvaluateRequestDTO` 带顶层版本、身份、revision 和完整 `PatternDocumentDTO`。不设计 Patch。`EvaluateResponseDTO` 带版本、相同身份/revision、`geometry[]`、`bounds_mm` 与 `warnings[]`。Geometry 按现有最终 Element 的 `type` 区分：`circle`、`ellipse`、`rect`、`path`、`filled_region`；包含稳定 ID、世界毫米位置/尺寸/旋转、样式及必要的本地 Path 数据。浏览器无需理解 Python Element 类。

2D Bounds：`min_x/min_y/max_x/max_y/width/height/units="mm"`。旋转形状的 v1 Bounds 为保守包络，尚不是严格曲线极值。

## 验证、连通性与制造

`GeometryValidationReportDTO` Mapper 输出 `checked_count/valid_count/warning_count/error_count/issues[]`。Issue：稳定 `code`、`severity`、给人看的 `message`、可选 `element_id`、毫米 `bounds` 和 JSON metadata。`ConnectivityReportDTO` 输出总元素、组件数、孤立 ID、最大组件、无效跳过数及 `components[]`。组件带 ID、元素 ID 列表、数量和毫米 Bounds。Mesh Issue 也有 `code`，例如现有引擎的 `non_watertight`、`non_manifold_edges`、`degenerate_faces`、`multiple_components`；UI 不需解析 message。

`ManufacturingBuildRequestDTO`：版本、`document_id`、`document_revision`、正数 `height_mm`。`ManufacturingBuildResponseDTO`：版本、`manufacturing_result_id`、文档身份/revision、`status`、二维几何/连通/转换/Mesh 报告、3D Bounds、组件数、warning、artifact 列表。`status` v1 值为 `queued/running/completed/failed`；WM2 没有后台队列。3D Bounds：`min_x/min_y/min_z/max_x/max_y/max_z/size_x/size_y/size_z/units="mm"`。

`manufacturing_result_id` 是 `mfg-` + SHA-256 前 24 位，由 canonical 文档 DTO、document revision、文档 ID 和制造参数确定。同一文档状态和参数得同一逻辑 ID；不同内容即使 revision 误用也会产生不同 ID。制造响应 Mapper 还核对 Service 的 document snapshot，阻止相同 revision 的错配结果。未来 GLB、STL 和验证报告必须引用这个 ID；本轮无服务端 Mesh 缓存，也没有 GLB 导出。

```json
{
  "schema_version": "1.0",
  "document_id": "doc-123",
  "document_revision": 17,
  "height_mm": 2.0
}
```

## Artifact 与错误

`ArtifactDTO`：版本、`artifact_id`、可选 `manufacturing_result_id`、`kind`（`svg/stl/glb`）、`media_type`、纯文件名、可选 `byte_size/sha256`。`glb` 只是协议值，本轮无 GLB exporter。无本机路径或下载 URL。

`ErrorDTO`：版本、稳定 `code`、用户可读 `message`、`recoverable`、可选 JSON `details`。预留代码包括 `invalid_schema_version`、`invalid_document`、`stale_revision`、`invalid_height`、`manufacturing_validation_failed`、`artifact_not_found`、`unsupported_geometry`；具体 HTTP 状态由 WM3 定义。

当前 Python 调用顺序：`PatternDocumentDTO.from_document()` → `to_dict()` → `canonical_json()` → `parse_json()` → `PatternDocumentDTO.from_dict()` → `to_document()`；求值使用现有 `evaluate_pattern_document()`，制造使用 WM1 `ManufacturingService`，Mapper 不运行第二套 Engine。
