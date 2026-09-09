---
name: image-to-svg
description: Take full control of an image by converting it to an editable SVG. Use when the user wants to vectorize, recolor, restyle, simplify, or otherwise edit an image (PNG/JPG/etc.) or a vector file (PDF/AI/EPS), or replace a raster image with an SVG.
---

# Image to SVG — taking control of images

You have an MCP server (`imagetosvg`) that turns images into editable SVGs and back.
Use this loop. **Always verify visually** — render and look before declaring success.

## Tools
- `convert_image_to_svg(input_path, mode?, max_colors?)` — raster → SVG. `mode`: `auto` (default), `simple`, `layered`.
- `import_vector(input_path, page?)` — PDF/AI/EPS → SVG (paths preserved).
- `inspect_svg(svg_path)` — list addressable layers (`layer-0`, `layer-1`, …) with fill/stroke/bbox.
- `edit_svg(svg_path, operations)` — structured ops by layer id.
- `render_svg(svg_path, width?)` — rasterize to PNG so you can see the result.
- `optimize_svg(svg_path)` — clean up (keeps layer ids).

## Workflow
1. **Look** at the source image first (your own vision).
2. **Convert**: `convert_image_to_svg` for raster, or `import_vector` for PDF/AI/EPS. Inspect the returned PNG preview.
3. **Compare** preview to the original. If a flat graphic came out muddy, re-run with `mode: 'simple'`; if a rich image lost detail, use `mode: 'layered'` and/or raise `max_colors`.
4. **Inspect**: `inspect_svg` to learn the layers before editing — never hand-parse giant path strings.
5. **Edit**: use `edit_svg` for structured changes (recolor/remove/isolate/transform a layer, resize). For freeform tweaks, edit the `.svg` text directly with your normal file tools.
6. **Verify**: `render_svg` and look. Iterate 4–6 until correct.
7. **Finalize**: `optimize_svg`, then use the `.svg` in place of the original image.

## edit_svg operations
`setFill{id,color}`, `setStroke{id,color}`, `removeNode{id}`, `isolateNode{id}`,
`transform{id,translate?,scale?,rotate?}`, `setDimensions{width?,height?}`, `setAttribute{id,name,value}`.

## Notes
- EPS import needs Ghostscript on PATH; PDF and AI do not.
- Layer ids (`layer-N`) are assigned in document order and survive `optimize_svg`.
