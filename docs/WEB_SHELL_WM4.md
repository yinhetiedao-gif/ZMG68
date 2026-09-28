# WM4 — React Web Shell

WM4 是与 Tkinter 桌面版并存的 Web 工作区基础版，不是可用的 Web 设计编辑器。Python 的 PatternDocument 和制造 Service 仍是唯一设计/制造事实来源；前端只负责展示空白工作区与检查 WM3 服务兼容性。

## 运行

先按 [WM3 说明](WEB_SERVER_WM3.md)安装可选 Web 依赖并启动本机后端：

```powershell
.\xiaomang_pattern_lab\.venv\Scripts\python.exe -m xiaomang_pattern_lab.web
```

在另一个终端启动前端：

```powershell
cd web
npm ci
Copy-Item .env.example .env.development
npm run dev
```

浏览器访问 `http://127.0.0.1:5173/`。`web/.env.example` 提供本机开发样例；实际 `web/.env.development` 属于本机配置，不提交。构建其他环境时显式设置 `VITE_API_BASE_URL`；不要在代码中写死部署地址。离线时界面仍可打开，但顶部会显示 Offline。

## 工作区边界

- Top Bar：名称、Untitled 项目占位、Backend Online/Offline、Contract v1.0。
- Left Sidebar：Image/SVG/Shapes 与 Grid/Radial/Curve/Free。均为禁用占位，不会伪造导入或设计结果。
- Center：空白二维工作区提示。Bottom Modes 可切换设计/制造/三维预览，但后两者明确显示“即将开放”。
- Right Inspector：No selection，尚无真实 Element 或编辑控件。
- API 请求只在 `web/src/api/` 发出。启动时先请求 `/api/v1/health` 再请求 `/api/v1/contract`，同时验证 health 的合同版本、`schema_version=1.0` 与 `units=mm`；不兼容显示错误，不静默继续。
- `web/src/state/browserState.ts` 只定义 selection、hover、zoom、pan、sidebar、inspector、activeMode 等浏览器交互状态，不包含 PatternDocumentDTO，也不持久化设计数据。

## 验证

```powershell
cd web
npm run test
npm run build
```

WM4 浏览器烟测使用本机 WM3 + Vite：三栏正常、Backend Online、Contract v1.0、底部模式可切换、无致命 Console Error。Python 原回归、固定测试图与 Tk 冒烟仍需分别运行。WM4 不包含图片上传、2D Geometry、拖拽编辑、制造 UI、Three.js、STL 下载、登录或云服务。
