# imagetosvg-mcp

[![CI](https://github.com/ujo78/imagetosvg-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/ujo78/imagetosvg-mcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Node](https://img.shields.io/badge/node-%3E%3D20-brightgreen.svg)](https://nodejs.org)

A local [Model Context Protocol](https://modelcontextprotocol.io) server that gives
AI agents **full control over images** — vectorize a raster image, import a vector
file (PDF/AI/EPS), then inspect, edit, render, and optimize the SVG. No API keys,
no cloud; everything runs locally.

The idea: an SVG is just text, and the agent is already the intelligence. So this
server only does what an agent *can't* do on its own — turn pixels into editable
paths and render SVG back to a picture for visual verification — plus a set of
structured edit operations for the parts of SVG editing that are tedious by hand.
The agent does the rest with its own file tools.

## Why

Agents normally treat an image as opaque pixels they can't change. Convert it to
SVG and the agent can recolor a logo, delete a layer, resize, restyle, or simplify
it — then render the result and *see* whether the edit worked, all deterministically.

## Tools

| Tool | Purpose |
|------|---------|
| `convert_image_to_svg` | Raster → SVG (hybrid: clean trace for simple graphics, layered color trace for complex ones) |
| `import_vector` | PDF / AI / EPS → SVG (paths preserved, no tracing) |
| `inspect_svg` | List addressable layers (id, tag, fill, stroke, bbox) without parsing path strings |
| `edit_svg` | Structured edits by layer id (recolor, remove, isolate, transform, resize, set attribute) |
| `render_svg` | Rasterize SVG → PNG so the agent can verify visually |
| `optimize_svg` | Clean up with svgo while preserving layer ids and viewBox |

Supported raster inputs: PNG, JPG, WebP, GIF, BMP, TIFF, AVIF.
Supported vector inputs: PDF, PDF-compatible AI, and EPS (EPS requires Ghostscript).

## Install

```bash
git clone https://github.com/ujo78/imagetosvg-mcp.git
cd imagetosvg-mcp
npm install        # builds automatically (prepare hook)
```

Requires Node.js >= 20. All native dependencies ship prebuilt binaries — no system
toolchain required.

## Connect it to an agent

### Claude Code

User scope (available in every project):

```bash
claude mcp add -s user imagetosvg -- node "/absolute/path/to/imagetosvg-mcp/dist/index.js"
```

Or per-project, commit a `.mcp.json` at the repo root:

```json
{
  "mcpServers": {
    "imagetosvg": {
      "command": "node",
      "args": ["/absolute/path/to/imagetosvg-mcp/dist/index.js"]
    }
  }
}
```

### Claude Desktop / Cursor / Windsurf

Add the same block to the client's MCP config (`claude_desktop_config.json` for
Claude Desktop; the MCP settings panel for Cursor/Windsurf). Use an absolute path
to `dist/index.js`.

> On Windows, use forward slashes in the path, e.g.
> `C:/Users/you/imagetosvg-mcp/dist/index.js`.

## The workflow

The bundled [Claude skill](./skill/SKILL.md) teaches agents this loop:

1. **Look** at the source image.
2. **Convert** (`convert_image_to_svg`) or **import** (`import_vector`); check the returned PNG preview.
3. **Compare** preview to the original; re-convert with a different `mode`/`max_colors` if needed.
4. **Inspect** (`inspect_svg`) to learn the layers.
5. **Edit** with `edit_svg` (structured) or the agent's own file tools (freeform).
6. **Verify** with `render_svg` and look. Iterate.
7. **Finalize** with `optimize_svg` and use the `.svg` in place of the image.

## edit_svg operations

`setFill{id,color}`, `setStroke{id,color}`, `removeNode{id}`, `isolateNode{id}`,
`transform{id,translate?,scale?,rotate?}`, `setDimensions{width?,height?}`,
`setAttribute{id,name,value}`. Layer ids (`layer-N`) are assigned in document
order and survive `optimize_svg`.

## Optional: EPS support

EPS import requires [Ghostscript](https://ghostscript.com/releases/) on `PATH`
(`gswin64c` on Windows). PDF and AI work without it; if Ghostscript is missing,
`import_vector` returns a clear error for EPS only.

## Development

```bash
npm run dev        # run the server from source via tsx
npm run typecheck  # tsc --noEmit
npm test           # vitest
npm run build      # tsc -> dist/
```

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the full guide.

## How it works

- **Hybrid conversion:** a unique-color heuristic classifies an image as *simple*
  (vtracer binary trace → clean paths) or *layered* (vtracer color trace → stacked,
  individually addressable color layers). Override with `mode` / `max_colors`.
- **Vector import:** PDF/AI go through [`mupdf`](https://www.npmjs.com/package/mupdf)
  (WASM, no system deps) with paths preserved; EPS is converted via Ghostscript when
  available.
- **Stack:** TypeScript (ESM) · `@modelcontextprotocol/sdk` · `@neplex/vectorizer`
  (vtracer) · `sharp` · `@resvg/resvg-js` · `svgo` · `svgson`.

## License

[MIT](./LICENSE) © Rakshit Raj
