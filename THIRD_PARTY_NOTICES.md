# 第三方资源说明

- `ChineseSimplified.isl`：来自 [Inno Setup Chinese Simplified Translation](https://github.com/kira-96/Inno-Setup-Chinese-Simplified-Translation)，MIT License；用于将安装向导显示为简体中文。
- 构建工具：PyInstaller、Inno Setup。运行中的最终应用不要求用户安装它们。
- `vtracer==0.6.15`：来自 [visioncortex/vtracer](https://github.com/visioncortex/vtracer) 的官方 Python binding；由 `reference2d_poc` 的 Raster → Editable 2D Geometry 链路和正式 2D Canvas 使用。
- `Anionex/agent-vision-toolkit` 的 `vision-skills`：仅在开发阶段使用本地 `trace` CLI 交叉验证 PNG→SVG；不作为小芒造物最终运行时依赖。
- `external/imagetosvg-mcp`：来自 [ujo78/imagetosvg-mcp](https://github.com/ujo78/imagetosvg-mcp)，MIT License；本阶段作为本地 MCP Raster→SVG、Inspect、Edit、Render、Optimize 后端。Node.js ≥20，依赖由其 `package-lock.json` 管理，未复制或改写其实现。
- `external/skills/01-image-fundamentals`、`02-preprocessing-decisions`、`03-thresholding-strategy`、`04-morphology-toolkit`、`05-contour-analysis`：来自 [aeren23/image-processing-skills](https://github.com/aeren23/image-processing-skills)，MIT License；仅作为原始图像预处理决策 Skill。
- `external/skills/svg-skill`：来自 [linyaosky/svg-skill](https://github.com/linyaosky/svg-skill)，MIT License；用于 SVG 结构、Path、Transform 和验证规范。
