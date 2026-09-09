# 上游能力集成记录

本阶段采用“安装并调用上游工具”的方式，不复制或重写其矢量化算法。项目外部依赖放在 `external/`，运行时通过 `ppg/upstream_svg_pipeline.py` 调用。

## 已核验的仓库

| 仓库 | 用途 | 许可证 | 运行依赖 | Windows/Codex 结论 |
| --- | --- | --- | --- | --- |
| [ujo78/imagetosvg-mcp](https://github.com/ujo78/imagetosvg-mcp) | Raster→SVG、Inspect、Edit、Render、Optimize | MIT | Node.js ≥20；npm 依赖随仓库安装，含预构建 native binaries | Node 24.19.0 下已 `npm install`、构建并通过上游 26 项测试 |
| [aeren23/image-processing-skills](https://github.com/aeren23/image-processing-skills) | 预处理、阈值、形态学、轮廓决策 Skill | MIT | SKILL.md；示例使用 OpenCV/Python | 原始 Skill 已安装到项目目录，不改写为自研 Skill |
| [linyaosky/svg-skill](https://github.com/linyaosky/svg-skill) | SVG Path/Transform/Mask/Pattern/验证规范 | MIT | `scripts/validate.sh`（需要 bash） | 原始 Skill 已安装到项目目录；Windows 可用 Git Bash/WSL 验证 |

## 安装位置

由于当前主机拒绝向全局 `C:\Users\13524\.codex\skills` 写入，Skill Installer 返回 WinError 5。本项目改用可复现的项目内安装位置：

- `external/skills/imagetosvg-mcp/`
- `external/skills/01-image-fundamentals/`
- `external/skills/02-preprocessing-decisions/`
- `external/skills/03-thresholding-strategy/`
- `external/skills/04-morphology-toolkit/`
- `external/skills/05-contour-analysis/`
- `external/skills/svg-skill/`

原始 MCP Runtime 位于 `external/imagetosvg-mcp/`，其 `package-lock.json` 已锁定依赖。安装/更新命令：

```powershell
cd external/imagetosvg-mcp
npm install
```

## 当前最小链路

```text
PNG/JPG
  → imagetosvg-mcp.convert_image_to_svg
  → SVG 文件（每个 layer-* 为可寻址真实节点）
  → imagetosvg-mcp.inspect_svg
  → EditableSVGDocument / EditableSVGElement
  → imagetosvg-mcp.edit_svg
  → imagetosvg-mcp.render_svg
  → imagetosvg-mcp.optimize_svg
```

`EditableSVGDocument.reference_visible` 与 SVG 几何文件独立；隐藏参考图不会删除或替换 SVG 元素。

## 已执行测试

- `npm test`：上游 8 个测试文件、26 个测试通过。
- `D:\steam\steamapps\common\Blender\5.2\python\bin\python.exe -m unittest tests.test_upstream_svg_pipeline -v`：4 个集成测试通过。
- 3 类图片：`test_dot_grid.png`、`test_dot_gradient.png`、`test_dot_star.png`。
- 每类均验证：转换、SVG 存在、Inspect 层数量、Render、隐藏参考标志、单层 Transform 编辑、编辑后 Render 哈希变化、Optimize 后再次 Inspect。

## 设计边界

本阶段不做 Generator 猜测、不做参数化重建、不改正式 Canvas。先确保上游 SVG 的真实节点可被稳定保存和编辑；下一阶段再把 `EditableSVGDocument` 接入 2D 编辑器。
