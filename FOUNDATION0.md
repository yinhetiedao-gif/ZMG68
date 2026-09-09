# FOUNDATION 0 — 可编辑二维矢量核心

本目录的当前基础链是无界面的：

`Raster Image → ImageProcessingAdapter → VectorizationAdapter → SVGNormalizer → PatternDocument → SVG / JSON`

`PatternDocument` 是核心内部格式。参考图只记录在 `Reference` 中，默认隐藏；图形只存在于 `Elements` 中。核心不导入、也不依赖任何 MCP、CLI、UI、Generator、3D 或制造模块。

## 可替换边界

- `ImageProcessingAdapter`：输入预处理实现。
- `VectorizationAdapter`：栅格转 SVG 引擎实现。
- `SVGNormalizer`：将 SVG 原生形状和可靠可恢复路径变为 `CircleElement`、`EllipseElement`、`RectElement` 或 `PathElement`。

当前应用适配器 `ImageToSVGVectorizationAdapter` 在边界外调用安装在 `external/imagetosvg-mcp` 的 `ujo78/imagetosvg-mcp`。更换为本地 CLI、WASM 或其他服务时，不需要修改 `PatternDocument`、`SVGNormalizer` 或调用方的编辑逻辑。

## 坐标

坐标使用 SVG user units，元素的 `x/y` 是视觉中心，`width/height` 是视觉尺寸。`Canvas.mm_per_unit` 是可选映射，预留给后续制造尺寸；FOUNDATION 0 不进行毫米建模。

## 自动验收

```powershell
& 'C:\Users\13524\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_foundation0 -v
```

该测试会针对规则点阵、渐变点阵、星形遮罩点阵、密集点阵、简单几何图案执行：PNG→SVG→PatternDocument，移动/缩放/复制/删除，SVG 重读，以及 JSON 保存/恢复。生成的可检查产物位于 `work/foundation0/`。
