# imagetosvg — MCP server + Claude skill for agent-controlled image vectorization

**Date:** 2026-06-16
**Status:** Design approved, pending spec review

## Purpose

Give AI agents complete control over images by turning a raster image into an
editable SVG. The agent reads an image, converts it to SVG, inspects and edits
the SVG with deterministic tools, visually verifies the result, and then uses
the SVG in place of the original image.

The core insight that shapes the whole design: **an SVG is just text, and the
agent is already the intelligence.** The server therefore does only what an agent
*cannot* do on its own — vectorize a raster and rasterize an SVG for visual
verification — plus a focused set of structured edit operations for the parts of
SVG editing that are tedious to do by hand. Everything else (freeform edits) is
left to the host agent's own file-editing tools.

## Goals

- Convert any raster image to SVG with a hybrid strategy (auto-detect complexity).
- Import vector source formats (PDF, PDF-compatible AI; EPS when Ghostscript is
  available) into editable SVG with paths preserved (no tracing).
- Let the agent inspect SVG structure without parsing huge path strings.
- Provide structured, high-value edit operations (recolor / remove / isolate /
  transform a layer; set dimensions/attributes).
- Provide a visual feedback loop: render SVG back to PNG so the agent can confirm.
- Work locally, deterministically, with no API keys and no system dependencies.
- Be portable across MCP-capable agents (Claude Code/Desktop, Cursor, Windsurf),
  with a thin Claude skill that teaches the workflow.

## Non-goals (v1, YAGNI)

- Vision/AI passes (semantic naming, AI redraw). Local-only by decision.
- Animation, SVG→SVG restyling beyond the listed ops, batch directory processing,
  GUI.

### Known limitations of vector import

- **EPS** requires Ghostscript on PATH. Without it, `import_vector` returns a
  clear error with install guidance rather than failing silently — the default
  no-system-dependency install still works for everything else.
- **Legacy `.ai`** files that are not PDF-compatible are unsupported (modern
  Illustrator files are PDF-compatible and work).
- Imported vectors are extracted as-is; the heavy `convert`/trace heuristic does
  not apply to them.

## Decisions (from brainstorming)

| Decision | Choice |
|----------|--------|
| Image scope / conversion | Hybrid: auto-detect; simple→clean trace, complex→layered trace |
| Vector import | PDF + PDF-compatible AI via mupdf (no deps); EPS optional/graceful via Ghostscript if present |
| Delivery | MCP server (engine) + thin Claude skill (workflow) |
| Engine | Local-only, deterministic (no vision model, no API key) |
| Stack | TypeScript / Node (prebuilt native binaries; no system deps) |
| Editing model | Approach A — thin mechanical server + focused structured edit ops; freeform edits via host file tools |

## Architecture

TypeScript/Node MCP server over stdio.

```
imagetosvg/
  src/
    server.ts          # MCP server, tool registration (@modelcontextprotocol/sdk)
    convert.ts         # raster→SVG: sharp preprocess + complexity heuristic + @neplex/vectorizer
    importVector.ts    # PDF/AI→SVG via mupdf (vectors preserved); EPS via Ghostscript if on PATH
    svgModel.ts        # parse SVG → addressable tree, assign stable layer/group ids
    inspect.ts         # tree → structured JSON summary
    edit.ts            # structured edit operations on the tree
    render.ts          # SVG→PNG via resvg-js (visual verification)
    optimize.ts        # svgo pass
  skill/               # Claude skill wrapper (workflow instructions)
  test/fixtures/       # real sample images (flat icon + a photo)
```

### Dependencies

- `@modelcontextprotocol/sdk` — MCP server (stdio transport).
- `@neplex/vectorizer` — vtracer binding (raster→SVG). Rust-compiled core.
- `mupdf` — WASM PDF/AI engine; converts a page to SVG with vectors preserved.
  No system dependencies, cross-platform.
- `sharp` — decode, downscale, color quantization preprocessing.
- `resvg-js` — SVG→PNG rendering for verification.
- `svgo` — SVG optimization.
- SVG parsing: a lightweight XML parser (`@xmldom/xmldom` or `svgson`) for the
  addressable tree in `svgModel.ts`. Final choice made during implementation.

All chosen for prebuilt binaries / no system dependencies on Windows.
**Ghostscript** is an *optional external tool* (not an npm dep): detected on PATH
at runtime and used only for EPS import; absence is handled gracefully.

## MCP tools (interface)

| Tool | Input | Output |
|------|-------|--------|
| `convert_image_to_svg` | `input_path`, `mode?` (auto\|simple\|layered), `max_colors?`, `output_path?` | svg path + layer summary + rendered preview PNG path |
| `import_vector` | `input_path` (PDF/AI/EPS), `page?`, `output_path?` | svg path (vectors preserved) + layer summary + rendered preview PNG path |
| `inspect_svg` | `svg_path` | JSON: dimensions, viewBox, list of layers/groups `{id, color, pathCount, bbox}` |
| `edit_svg` | `svg_path`, `operations[]` | applies ops in order, returns updated summary |
| `render_svg` | `svg_path`, `width?` / `scale?` | PNG preview path the agent can view |
| `optimize_svg` | `svg_path` | cleaned SVG |

### `edit_svg` operations

`setFill` / `setStroke` (by layer id), `removeNode`, `isolateNode` (keep only one
layer), `transform` (translate / scale / rotate a group), `setDimensions`,
`setAttribute`. Operations target stable ids assigned by `svgModel.ts`. Freeform
edits beyond these are done with the host agent's normal file-edit tools.

## Hybrid conversion logic

1. `sharp` decodes the input; if larger than a max dimension, downscale (and
   report it).
2. A heuristic counts unique colors + edge density to classify simple vs complex.
3. **Simple** → low-color/binary vtracer trace → clean, editable paths.
4. **Complex** → color-mode vtracer trace with a capped cluster count → stacked
   color-layer groups (lower fidelity, but each layer is addressable/editable).
5. `mode` can override the heuristic (`simple` | `layered`); `max_colors` caps
   cluster count.

There are two ingestion paths into the editing pipeline:
- **Raster** (`convert_image_to_svg`) → trace via vtracer (above).
- **Vector** (`import_vector`) → extract existing paths via mupdf (PDF/AI) or
  Ghostscript (EPS) → SVG with vectors preserved, no tracing. For multi-page
  PDFs, `page` selects the page (default: first).

Both paths produce an SVG that flows identically into `inspect`/`edit`/`render`/
`optimize`.

## Agent workflow (taught by the skill)

1. View the source image (agent vision).
2. `convert_image_to_svg` → SVG + preview PNG.
3. View the preview, compare to original; re-convert with a different
   `mode`/`max_colors` if fidelity is off.
4. `inspect_svg` to learn the layer/group structure.
5. Edit: `edit_svg` for structured ops; host file tools for freeform tweaks.
6. `render_svg` to verify; iterate 4–6 until correct.
7. `optimize_svg`, then use the `.svg` in place of the original image.

## Error handling

- Missing/unsupported input → clear, actionable error listing supported formats.
- Oversized image → enforce max dimension, downscale, report it in the result.
- EPS import without Ghostscript on PATH → clear error with install guidance.
- Encrypted/corrupt PDF, or legacy non-PDF `.ai` → clear error, no partial output.
- `page` out of range for a PDF → error naming the available page count.
- Edit targeting a non-existent layer id → error naming the valid ids; never
  write a partial/corrupt file (parse-validate before write).
- vtracer/resvg failures surfaced with context, not swallowed.

## Testing

Real fixtures, no mocking of the conversion/render engines.

- **Unit:** complexity heuristic picks the expected mode; each `edit_svg` op
  produces the expected tree change; `inspect_svg` parses a known SVG correctly.
- **Integration:**
  - Convert a flat-icon fixture → assert valid SVG + small layer count +
    non-empty PNG render.
  - Convert a photo fixture → assert layered output.
  - Import a small vector PDF fixture → assert SVG produced with paths preserved
    (path count > 0, non-empty PNG render).
  - EPS import test runs only when Ghostscript is detected; otherwise it asserts
    the graceful error path. (skipped/conditional in CI without GS)
  - Round-trip: recolor a layer via `edit_svg`, render, assert the pixel color
    changed.

## Open implementation details (resolved during build, not blocking)

- Exact SVG parser library (`@xmldom/xmldom` vs `svgson`).
- Specific vtracer parameter presets for simple vs layered modes.
- Max image dimension and default `max_colors` values.
- Session workspace directory convention for intermediate PNG/SVG files.
- Exact mupdf SVG-export call and how AI files are opened as PDF.
- Ghostscript detection method and the EPS→SVG invocation (e.g. `eps2svg`/`-sDEVICE`).
