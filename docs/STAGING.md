# 临时公网测试站

仅供短时外部验收；没有认证，知道链接的人都能访问。测试完成后立即关闭，不上传敏感图片。

在项目根目录准备 Python 依赖、`web/` 的 `npm ci`，并从 [Cloudflare 官方下载页](https://developers.cloudflare.com/tunnel/downloads/) 安装 `cloudflared`。启动：

```powershell
& .\scripts\start_staging.ps1 -PythonExe 'C:\path\to\python.exe' -CloudflaredExe 'C:\path\to\cloudflared.exe'
```

脚本将构建 staging 版 React，以隐藏进程启动 loopback FastAPI `8766`、Vite production preview `5175`，通过同源 `/api` 代理，并用 Cloudflare Quick Tunnel 输出唯一 `https://*.trycloudflare.com` 地址。端口可由 `-ApiPort`、`-WebPort` 改；前端代理目标由 `XIAOMANG_STAGING_API_TARGET` 传入。构建时强制清空 `VITE_API_BASE_URL`，所以公网浏览器不访问本机 localhost。测试站标有 `TEST / STAGING`。

停止：

```powershell
& .\scripts\stop_staging.ps1
```

脚本只停止自己记录且命令行匹配的三个进程。日志和 PID 文件位于未跟踪的 `work/staging/`；临时 URL、令牌、快照不提交。若启动失败，先查看该目录日志，检查端口是否被占用及 Python/npm/cloudflared 是否可运行。电脑关机、服务停止或 Tunnel 断开后 URL 即失效。

公网端保留 8 MiB 上传、2 MiB JSON 请求限制；制造/设计预览一次只允许一个重任务。`XIAOMANG_STAGING=1` 禁用 API 文档页面，开发 failure snapshot 在脚本中关闭。Fabric 最终 STL 仍未开放。普通 STL 只通过现有制造 API 下载。
