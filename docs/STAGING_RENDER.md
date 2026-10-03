# Render 单服务临时测试站

本部署仅用于外部 UI/UX 与功能检查，不是 Production。只运行一个 Docker Web Service、一个 Uvicorn worker；上传资产与制造结果保存在进程内/临时目录，重启、过期或多实例间不会保留。Fabric 最终 STL 仍未开放。不要上传敏感图片。

## 容器

仓库根目录的 `Dockerfile` 用 Node 构建 React 和现有 `imagetosvg-mcp`，最终 Python 容器只带运行所需模块、Node 矢量化运行时和 `web/dist`。FastAPI 同源提供 `/api/*` 与 SPA；`/api/v1/health` 是 Render health check。容器读取 `PORT` 并监听 `0.0.0.0`。`XIAOMANG_ENV=staging` 关闭 API 文档、限制并发制造/预览任务；失败快照默认关闭。前端只在 staging build 显示 STAGING，不写死公网域名。

本机有 Docker 时，在仓库根目录构建并单独启动测试容器：

```powershell
docker build -t xiaomang-pattern-lab:staging .
docker run --rm -p 127.0.0.1:10000:10000 -e PORT=10000 xiaomang-pattern-lab:staging
```

然后检查 `/`、`/design`、`/api/v1/health`、PNG/JPG/SVG 导入及普通 STL 下载。不要把 Docker 本机 smoke 当成 Render 公网验收。

## Render 授权与部署

1. 将当前提交推送到用户授权的 GitHub 仓库。此仓库当前没有配置 Git remote，需由用户选择仓库与访问权限；不要在此文档填写凭据。
2. 在 [Render Dashboard](https://dashboard.render.com/) 登录，选择 **New → Blueprint**，授权 Render 读取该 GitHub 仓库并选中仓库。根目录的 `render.yaml` 声明一个 Docker Web Service、单实例、health check 和非秘密环境变量。也可选 **New → Web Service → GitHub 仓库 → Docker**，沿用相同设置。
3. 在创建界面核对计划及可能费用后由用户点击部署。不要添加域名、持久盘、数据库或额外服务。
4. 部署成功后记录实际 `https://…onrender.com` URL。逐项从公网确认首页、health、PNG/JPG/SVG 上传、2D 求值、Layout、Field、Modifier、Pattern Points、Fabric 预览、普通二维制造及 STL 下载；Network 中不应有 localhost 请求。

若 Build 失败，先查看 Render 的构建日志，不要修改几何算法或跳过上传/制造验收来宣称上线。制造任务受平台实例资源和 HTTP 超时约束；本轮不引入任务队列。部署后服务重启将清空内存中的资产与 `manufacturing_result_id`，需重新导入/生成。
