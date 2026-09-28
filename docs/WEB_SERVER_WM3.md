# WM3 — FastAPI Headless Server（Alpha）

WM3 是既有 Python Engine 的 HTTP 适配层，不是新设计格式。依赖方向：`FastAPI → WM2 Web Contract DTO v1 → ManufacturingService / Evaluate → 现有 Engine`。桌面入口保持不变；服务器导入不加载 Tkinter、旧 `ppg.xiaomang_pipeline` 或 Blender。

## 启动

在仓库根使用 Pattern Lab 虚拟环境安装可选 Web 依赖：

```powershell
.\xiaomang_pattern_lab\.venv\Scripts\python.exe -m pip install -r .\xiaomang_pattern_lab\requirements-web.txt
.\xiaomang_pattern_lab\.venv\Scripts\python.exe -m xiaomang_pattern_lab.web
```

服务默认只绑定 `127.0.0.1:8765`。打开 `http://127.0.0.1:8765/docs`；`/openapi.json` 可用，但产品语义协议仍以 [WEB_CONTRACT_V1.md](WEB_CONTRACT_V1.md) 为准。桌面版仍由 `python -m xiaomang_pattern_lab.main` 启动。

## Endpoint

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/api/v1/health` | 存活与合同版本 |
| GET | `/api/v1/contract` | schema `1.0`、单位 `mm` |
| POST | `/api/v1/evaluate` | `EvaluateRequestDTO` → 最终二维毫米几何 |
| POST | `/api/v1/manufacturing/build` | 顶层 `ManufacturingBuildRequestDTO` 字段加 `document: PatternDocumentDTO`；同步构建 |
| GET | `/api/v1/manufacturing/{manufacturing_result_id}/model.stl` | 同一次构建经 Gate X 验证的 Binary STL 字节，`model/stl`、附件文件名 |

Build 的 `document_id/revision` 必须与内嵌文档一致。`manufacturing_result_id` 来自 WM2 合同；同一响应的 STL Artifact 带 ID、文件名、字节数和 SHA-256，不含本机路径。GET 只查缓存字节，不重新 Evaluate、制造或 STL 序列化。制造检查未通过返回 `manufacturing_validation_failed` (422)，不会产生可下载 Artifact。

## 资产与结果生命周期

`AssetResolver.resolve(asset_id)` 由服务器注入。默认 `NullAssetResolver` 拒绝所有外部资产；`InMemoryAssetResolver` 只供本地测试/开发预登记。没有图片上传 API，绝不把客户端传来的本机路径当服务器路径。结果缓存是进程内 Alpha 实现：最多 32 项、创建后 30 分钟过期，重启即丢失；没有数据库或跨进程共享。未找到/过期的结果返回 `artifact_not_found` (404)。

## 错误、安全与限制

所有应用错误使用 WM2 `ErrorDTO`。版本/无效 JSON → 400；文档/数值/高度/资产/制造检查 → 422；未知 Artifact → 404；过大请求 → 413；意外错误 → 500 且响应只包含通用中文信息。当前没有文档仓库，因此只是回传 revision，不伪造服务器端冲突；有持久版本时才使用 409。非有限数值和绝对本机路径由 WM2 合同拒绝。HTTP 请求体最多 2 MiB，按流累计限制；CORS 仅限本机 5173/3000 开发 Origin，未开启跨域凭据。

同步制造会占用工作线程并可能持续较久；当前只经小样实测，尚无生产超时、鉴权、速率限制或隔离式任务队列。只能用于可信本机开发，不要直接暴露公网。没有 React、Three.js、GLB、数据库、Redis、WebSocket、云存储、3MF 或 Skill Orchestrator。
