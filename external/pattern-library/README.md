# 小芒图案库

基于 MIT 开源 [svelte-svg-patterns](https://github.com/catchspider2002/svelte-svg-patterns)
固定版本的独立 Svelte/Sapper 模块。保留现成330款图案、画廊、参数控件、实时预览和 SVG/PNG 导出。

```sh
npm ci --ignore-scripts
npm run export
```

输出 `__sapper__/export/patterns`，由原网站的 FastAPI 同源挂载到 `/patterns/`。
不替换原编辑器、Fabric 或制造/STL 功能；图案库没有自动制造转换通道。

主仓库 `docs/PATTERN_LIBRARY_REUSE.md` 记录已验证启动、测试、集成和回退方式。
来源与必要改动见 [UPSTREAM.md](UPSTREAM.md)。原完整 MIT 版权声明见 [LICENSE.md](LICENSE.md)；
发布产物同时附带第三方许可文件。旧作者的离线源码生成工具未纳入本模块，避免重新引入推广/跟踪。
