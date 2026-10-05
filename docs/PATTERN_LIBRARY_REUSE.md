# 小芒图案库：现成工程复用交付

## 版本与保护

- 工作分支：`feature/pattern-library-reuse`。
- 接入基线 / Last Known Good：`85c6ad05205362c4c65c04593b6f2a02d8966723`。
- 保护引用：`backup/pre-pattern-library-20261005`，未覆盖旧稳定引用。
- 发布目标：已有 Render **Staging** 服务 `https://zmg68-1.onrender.com/`，绑定
  `feature/staging-render-deployment`。不创建服务、购买套餐、修改域名或覆盖生产站。
- 主项目原工作区开始时干净，新增工作在功能分支；原版工程另行克隆运行。

安全回退先保留当前改动，再使用新的不存在的目录：

```powershell
git worktree add --detach ../pattern-library-rollback-20261005 85c6ad05205362c4c65c04593b6f2a02d8966723
```

不 reset/clean/force push。公网回退需对部署分支正常提交 revert，而非修改历史。

## 实际取得的源码与复用边界

主源码：`https://github.com/catchspider2002/svelte-svg-patterns`，固定提交
`803e30bfde106cf094581aabfc80ced2062c5ab7`，MIT，版权声明全文保留。
原工程为 Svelte 3 / Sapper 0.29 / Rollup 2，锁文件 v2。没有改框架、升级全部依赖
或重新实现图案算法。330款 `_index.js` 数据和 package-lock 与上游 SHA256 一致。

复用：原画廊、搜索/筛选/排序、图案选择、颜色选择、比例/线宽/间距/位置/角度控件、
实时 SVG 背景预览、随机/Reset、复制 SVG/CSS、PNG 导出。
必要修正：原 SVG 单瓦片下载不包含预览角度/位移，现下载原编辑器已有的 live SVG，
采用用户导出宽高；仍使用原 SVG 定义，没有第二套图案生成器。

参考源码 `https://github.com/zengxb723-a11y/parametric-form-studio` 已下载，提交
`f07b3831d5e2a245c6f61d61199df075d09987a9` 只有7个已打包文件，没有源模块、
package.json 或可核验 LICENSE；未反编译、未复制其 bundle，也未依赖它交付。

没有图案库到 PatternDocument 的自动转换。SVG/PNG 是设计产物，不代表可打印认证。
原网站制造、STL、Fabric 仍按既有流程工作。

## 修改 / 新增 / 删除文件范围

- 新增 `external/pattern-library/`：独立上游源码和完整许可证；`UPSTREAM.md` 固定来源，
  `_zh.js` 汉化；Nav/Logo/Footer/StickyFooter/template 去除推广跟踪、增加返回入口。
  server 只为原 Sapper 静态导出提供 `/patterns`，没有个人服务 API。
- `build-static.cjs` 使用 **原 Sapper exporter**，导出全部330路由并逐页检查；生成
  MIT/第三方许可文件。原 Node/Sapper 服务和 node_modules 不进入运行时镜像。
- 删除旧推广/Newsletter/Pro 路由、广告文件、旧第三方验证文件、未使用推广组件及
  Service Worker；原 Service Worker 会清理整个 origin 的缓存，不用于本次接入。
- `web/src/App.tsx` / `styles.css`：原网站增加新标签页入口，不替换编辑器。
  `App.test.tsx` 验证 href/target/rel；`vite.config.ts` 独立 `/patterns` 开发代理。
- `xiaomang_pattern_lab/web/app.py`：可选静态挂载，位于 React SPA fallback 前；
  缺少配置不影响原网站，配置路径不存在时明确失败，未知文件不落入 React 页面。
- Dockerfile / .dockerignore / .gitignore：独立 Svelte multi-stage build，忽略生成产物；
  原 React、vectorizer、Python 部署流程保留。render.yaml 不变。
- `tests/test_pattern_library_serving.py`、`scripts/smoke_pattern_library.cjs`：隔离路由、
  浏览器真实导出及普通 STL 回归。README / GATE_STATUS / 本文记录状态。

## 已验证的构建与启动

在仓库根，先按原流程构建 React。图案库单独构建：

```powershell
Set-Location external/pattern-library
npm ci --ignore-scripts
node build-static.cjs
Set-Location ../..
$env:XIAOMANG_PATTERN_LIBRARY_DIST = (Resolve-Path external/pattern-library/__sapper__/export/patterns).Path
$env:XIAOMANG_WEB_DIST = (Resolve-Path web/dist).Path
$env:XIAOMANG_ENV = 'staging'
& .\xiaomang_pattern_lab\.venv\Scripts\python.exe -m uvicorn xiaomang_pattern_lab.web.app:create_app --factory --host 127.0.0.1 --port 8777
```

实际本地验证：`http://127.0.0.1:8777/patterns/`。8777是本次独立测试端口，未杀旧服务器。
生产 Docker 自动构建并配置挂载，使用现有 PORT / API / health；不需要 Vite 或新 Node 服务。
原本地 Vite 流程保持，模块代理使用已有 `XIAOMANG_STAGING_API_TARGET`（默认8766）。

`--ignore-scripts` 避免原离线图片工具的 Puppeteer 下载和 sharp 安装脚本；它们不是站点
构建/导出依赖。原版首次安装卡在 Chromium 下载后，只终止已确认的该安装子进程；
使用 `PUPPETEER_SKIP_DOWNLOAD=1` 安装并跑通原版 build、真实 SVG/PNG 导出。

## 实际测试

- 原版 Sapper production build、画廊与SVG/PNG下载：PASS。
- 新模块所有330个图案静态路由、资源和法律声明生成：PASS。
- 原 React Web：**189/189 PASS**；`npm run build -- --mode staging` PASS。
- Python静态挂载、部署、普通制造API：**16 PASS**。
- Edge真实流程：画廊330款、搜索、waves-1 / circles-1 / diamonds-14 选择；
  scale=3、angle=35及可用间距参数修改；480×320 SVG/PNG实际下载并打开。
  SVG包含当前 scale/angle；PNG有图案；SVG/PNG逐像素比较差异0。
  直接刷新资源、返回画廊、390px手机端SVG下载 PASS。
- 原网站新标签页入口、返回入口 PASS；无外部推广请求、HTTP错误、致命JS错误。
- 原网站圆点例子真实标准制造和STL下载200；文件34284 bytes /684 triangles，
  原 STLExporter 读回 + MeshValidator：40×40×2mm、9组件、watertight、正体积、零退化面。
  初次使用 trimesh.split 的读回脚本因本机缺 graph engine 失败，改用项目已有 Validator，
  未改产物、未安装新依赖。
- 构建中发现并修复的接入错误：遗漏画廊配色常量、许可文件被误导出成路由目录；
  浏览器发现旧作者远程字体请求，改为已有本地字体。修复后全部重跑通过。
- 本地 Docker build：**未执行**（无 Docker CLI）；公网 Docker build/Live与浏览器验收
  在本次发布后单独验证，不将源代码 push 视为部署成功。
- 上游 `npm test`：未执行，原脚本引用不存在的 cy:run；使用现有 Playwright runtime，
  无新测试框架。未跑无关 Tk/算法全量，不声称全产品人工验收。

## Render Staging 实际验收

- 普通 fast-forward 同步、普通 push 到现有 `feature/staging-render-deployment`；
  Render 自动部署功能提交 `2b512b16361b4976b3e35e18080f7666311d630c`，Dashboard
  确认 Live，实际 Docker build/deploy约2分11秒；未修改套餐、账户权限、域名或生产服务。
- 实际公网模块：`https://zmg68-1.onrender.com/patterns/`。原网站仍在同一 origin `/`。
  health返回相同 backend_commit、staging；既有 Fabric 能力开关保留。
- 独立 Edge context实际全流程 PASS：330图案、搜索、三类图案参数/预览、6个SVG/PNG
  下载文件、直接刷新、手机端SVG、新标签页入口、返回原网站标准制造和STL。
  图案像素对照差异0；无致命JS、HTTP错误、外部推广/作者服务请求。
- 公网STL下载200、34284 bytes、684 triangles；原Exporter/Validator读回40×40×2mm、
  9组件、watertight、正体积、零退化面。普通制造允许多组件，不施加Fabric融合单组件要求。
- 公网首次Smoke读到上游SSR20款占位图案即断言失败；源码确认完整数据随后fetch。
  只让测试等待330款数据加载，未改产品算法；本地和公网复跑均通过。
- 测试原始报告/截图/导出文件留在未提交运行目录
  `work/pattern-library-public/`，本地对照在 `work/pattern-library-smoke/`。
- 本次只完成图案库交付；未替代F5-C切片、Linux代表性Fabric样本和实物验收，
  不将普通STL回归当作 Fabric 最终制造 PASS。

## 已知限制

- 上游依赖老旧，npm audit 有24个告警（含1 critical）；omit=dev 仍有4个告警。
  没有全量升级或宣称安全审计通过。新模块线上只运行静态 HTML/JS/CSS，旧 Node HTTP
  中间件与构建依赖不进入运行时；浏览器包和未来升级仍需独立安全维护。
- 原图案英文名称保留，主要中文操作可用，搜索提示可使用英文名称。
- 原 UI/编辑功能不是每一款图案都逐项人工验证；全部330路由构建通过，3种不同类别实测。
- 刷新保留资源/路由，不新增项目存储能力；图案库当前参数遵循原工程行为。
- React旧 bundle size与上游编译 warning 保留；不扩大范围做整站重构。
- 本次不能证明所有导出 SVG 均可被原制造入口无损转换；需按原导入与制造检查流程。
