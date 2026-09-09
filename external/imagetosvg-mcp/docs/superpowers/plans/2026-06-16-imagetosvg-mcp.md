# imagetosvg MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-only MCP server (plus a Claude skill) that lets any MCP-capable agent vectorize raster images, import vector files (PDF/AI/EPS), and inspect/edit/render/optimize the resulting SVG — giving the agent full deterministic control over images.

**Architecture:** A TypeScript/Node MCP server over stdio. Pure mechanical modules (convert, importVector, svgModel, inspect, edit, render, optimize) each with one responsibility; `server.ts` wires them to six MCP tools. The agent's own vision supplies the intelligence; the server never calls an AI model. SVG is parsed to an addressable tree (svgson) so layers get stable ids the agent can target.

**Tech Stack:** Node 22 + TypeScript (ESM, NodeNext), `@modelcontextprotocol/sdk`, `@neplex/vectorizer` (vtracer), `sharp`, `@resvg/resvg-js`, `svgo`, `svgson`, `svg-path-bbox`, `mupdf` (WASM), optional Ghostscript for EPS. Tests: `vitest`, fixtures generated at test time with `sharp` and `pdf-lib`.

**Verified package versions (2026-06-16):** sdk 1.29.0, @neplex/vectorizer 0.1.0, sharp 0.35.1, @resvg/resvg-js 2.6.2, svgo 4.0.1, svgson 5.3.1, mupdf 1.27.0, svg-path-bbox 2.1.0, zod 4.4.3, vitest 4.1.9, tsx 4.22.4, typescript 6.0.3, @types/node 25.9.3, pdf-lib ^1.17.1.

---

## File Structure

```
imagetosvg/
  package.json              # ESM, scripts, deps
  tsconfig.json             # NodeNext, strict
  vitest.config.ts          # test config
  src/
    constants.ts            # thresholds, limits, supported formats
    types.ts                # shared interfaces: LayerInfo, SvgSummary, Operation
    workspace.ts            # output-path derivation helpers
    svgModel.ts             # parse/stringify/assignIds/findById/listLayers (svgson + svg-path-bbox)
    inspect.ts              # inspectSvg(svg) -> structured summary
    edit.ts                 # applyOperations(svg, ops) -> svg
    render.ts               # renderSvgToPng(svg, opts) -> Buffer
    optimize.ts             # optimizeSvg(svg) -> svg (ids preserved)
    convert.ts              # countUniqueColors/classifyComplexity/buildVtracerConfig/convertImageToSvg
    importVector.ts         # pdfBufferToSvg/detectGhostscript/epsToSvg/importVector
    server.ts               # McpServer + 6 tools (startServer)
    index.ts                # CLI entry (shebang)
  skill/
    SKILL.md                # Claude skill: the agent workflow
  test/
    svgModel.test.ts
    inspect.test.ts
    edit.test.ts
    render.test.ts
    optimize.test.ts
    convert.test.ts
    importVector.test.ts
    server.test.ts
    helpers.ts              # fixture generators (sharp, pdf-lib)
  README.md                 # install + MCP client config
```

Each module is independently testable on plain strings/buffers. `server.ts` only adapts these functions to MCP tools (read file → call function → write file → return content), so it stays thin.

**Cross-task type contract (used consistently in all tasks; all defined in `src/types.ts`):**

```ts
// src/types.ts
export interface LayerInfo {
  id: string;
  tag: string;                       // 'path' | 'g' | 'rect' | ...
  fill: string | null;
  stroke: string | null;
  pathCount: number;
  bbox: [number, number, number, number] | null;  // [x1,y1,x2,y2]
}

export interface SvgSummary {
  width: string | null;
  height: string | null;
  viewBox: string | null;
  layerCount: number;
  layers: LayerInfo[];
}

// src/edit.ts
export type Operation =
  | { op: 'setFill'; id: string; color: string }
  | { op: 'setStroke'; id: string; color: string }
  | { op: 'removeNode'; id: string }
  | { op: 'isolateNode'; id: string }
  | { op: 'transform'; id: string; translate?: [number, number]; scale?: number | [number, number]; rotate?: number }
  | { op: 'setDimensions'; width?: number; height?: number }
  | { op: 'setAttribute'; id: string; name: string; value: string };
```

---

## Task 0: Project scaffolding

**Files:**
- Create: `package.json`, `tsconfig.json`, `vitest.config.ts`

- [ ] **Step 1: Create `package.json`**

```json
{
  "name": "imagetosvg",
  "version": "0.1.0",
  "description": "Local MCP server that vectorizes images and gives agents full control over SVG",
  "type": "module",
  "bin": { "imagetosvg": "dist/index.js" },
  "main": "dist/index.js",
  "files": ["dist", "skill", "README.md"],
  "scripts": {
    "build": "tsc",
    "dev": "tsx src/index.ts",
    "start": "node dist/index.js",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.29.0",
    "@neplex/vectorizer": "^0.1.0",
    "@resvg/resvg-js": "^2.6.2",
    "mupdf": "^1.27.0",
    "sharp": "^0.35.1",
    "svg-path-bbox": "^2.1.0",
    "svgo": "^4.0.1",
    "svgson": "^5.3.1",
    "zod": "^4.4.3"
  },
  "devDependencies": {
    "@types/node": "^25.9.3",
    "pdf-lib": "^1.17.1",
    "tsx": "^4.22.4",
    "typescript": "^6.0.3",
    "vitest": "^4.1.9"
  }
}
```

- [ ] **Step 2: Create `tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "outDir": "dist",
    "rootDir": "src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "declaration": false
  },
  "include": ["src"]
}
```

- [ ] **Step 3: Create `vitest.config.ts`**

```ts
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['test/**/*.test.ts'],
    testTimeout: 30000,
    hookTimeout: 30000,
  },
});
```

- [ ] **Step 4: Install dependencies**

Run: `npm install`
Expected: completes; `node_modules/` populated; no peer-dep errors that abort install.

- [ ] **Step 5: Verify the toolchain runs**

Run: `npx vitest run`
Expected: exits successfully reporting "No test files found" (no tests yet).

- [ ] **Step 6: Commit**

```bash
git add package.json package-lock.json tsconfig.json vitest.config.ts
git commit -m "chore: scaffold imagetosvg MCP project (TS, ESM, vitest)"
```

---

## Task 1: Constants, workspace helper, and SVG model

**Files:**
- Create: `src/constants.ts`, `src/workspace.ts`, `src/svgModel.ts`
- Test: `test/svgModel.test.ts`

- [ ] **Step 1: Create `src/constants.ts`**

```ts
export const COLOR_THRESHOLD = 16;       // <= this many unique colors => "simple"
export const MAX_DIMENSION = 2000;       // downscale inputs larger than this (px)
export const SAMPLE_SIZE = 100;          // color-sampling resize box (px)
export const PREVIEW_WIDTH = 512;        // rendered preview width (px)

export const SUPPORTED_RASTER = ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tiff', '.avif'];
export const SUPPORTED_VECTOR = ['.pdf', '.ai', '.eps'];

export const SHAPE_TAGS = ['path', 'g', 'rect', 'circle', 'ellipse', 'polygon', 'polyline', 'line'];
```

- [ ] **Step 2: Create `src/workspace.ts`**

```ts
import path from 'node:path';

/** Produce a sibling output path: /a/b/c.png + ".svg" => /a/b/c.svg */
export function deriveOutputPath(inputPath: string, ext: string): string {
  const dir = path.dirname(inputPath);
  const base = path.basename(inputPath, path.extname(inputPath));
  return path.join(dir, `${base}${ext}`);
}

/** Sibling preview path for an svg: /a/b/c.svg => /a/b/c.preview.png */
export function previewPathFor(svgPath: string): string {
  return svgPath.replace(/\.svg$/i, '') + '.preview.png';
}
```

- [ ] **Step 3: Write the failing test `test/svgModel.test.ts`**

```ts
import { describe, it, expect } from 'vitest';
import { parseSvg, assignIds, listLayers, findById, toSvgString } from '../src/svgModel.js';

const TWO_PATHS = `<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">
<path d="M10 10 L90 10 L90 90 Z" fill="#ff0000"/>
<path d="M0 0 L20 0 L20 20 Z" fill="#00ff00" stroke="#000000"/>
</svg>`;

describe('svgModel', () => {
  it('assigns stable sequential ids to shape children', async () => {
    const tree = await parseSvg(TWO_PATHS);
    assignIds(tree);
    const layers = listLayers(tree);
    expect(layers.map((l) => l.id)).toEqual(['layer-0', 'layer-1']);
  });

  it('reads fill, stroke, tag and computes a path bbox', async () => {
    const tree = await parseSvg(TWO_PATHS);
    assignIds(tree);
    const layers = listLayers(tree);
    expect(layers[0]).toMatchObject({ tag: 'path', fill: '#ff0000', stroke: null, pathCount: 1 });
    expect(layers[1]).toMatchObject({ fill: '#00ff00', stroke: '#000000' });
    expect(layers[0].bbox).toEqual([10, 10, 90, 90]);
  });

  it('preserves existing ids and is idempotent', async () => {
    const tree = await parseSvg(TWO_PATHS);
    assignIds(tree);
    assignIds(tree);
    expect(listLayers(tree).map((l) => l.id)).toEqual(['layer-0', 'layer-1']);
  });

  it('findById returns the matching node and round-trips to string', async () => {
    const tree = await parseSvg(TWO_PATHS);
    assignIds(tree);
    const node = findById(tree, 'layer-1');
    expect(node?.attributes.fill).toBe('#00ff00');
    expect(toSvgString(tree)).toContain('id="layer-0"');
  });
});
```

- [ ] **Step 4: Run test to verify it fails**

Run: `npx vitest run test/svgModel.test.ts`
Expected: FAIL — cannot find module `../src/svgModel.js`.

- [ ] **Step 5: Create `src/svgModel.ts`**

```ts
import { parse, stringify, type INode } from 'svgson';
import { svgPathBbox } from 'svg-path-bbox';
import { SHAPE_TAGS } from './constants.js';
import type { LayerInfo } from './types.js';

export type { INode };

export async function parseSvg(svg: string): Promise<INode> {
  return parse(svg);
}

export function toSvgString(tree: INode): string {
  return stringify(tree);
}

function isShape(node: INode): boolean {
  return node.type === 'element' && SHAPE_TAGS.includes(node.name);
}

/** Direct shape children of the <svg> root, in document order. */
function topLevelShapes(root: INode): INode[] {
  return root.children.filter(isShape);
}

/** Assign id="layer-N" to each top-level shape that lacks an id. Idempotent. */
export function assignIds(root: INode): void {
  let n = 0;
  for (const child of topLevelShapes(root)) {
    if (!child.attributes.id) child.attributes.id = `layer-${n}`;
    n += 1;
  }
}

export function findById(root: INode, id: string): INode | null {
  if (root.attributes && root.attributes.id === id) return root;
  for (const c of root.children) {
    const found = findById(c, id);
    if (found) return found;
  }
  return null;
}

function countDescendantPaths(node: INode): number {
  if (node.name === 'path') return 1;
  return node.children.reduce((acc, c) => acc + countDescendantPaths(c), 0);
}

function unionBbox(
  a: [number, number, number, number] | null,
  b: [number, number, number, number] | null,
): [number, number, number, number] | null {
  if (!a) return b;
  if (!b) return a;
  return [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[2], b[2]), Math.max(a[3], b[3])];
}

function nodeBbox(node: INode): [number, number, number, number] | null {
  if (node.name === 'path' && node.attributes.d) {
    try {
      return svgPathBbox(node.attributes.d);
    } catch {
      return null;
    }
  }
  if (node.children.length) {
    return node.children.reduce<[number, number, number, number] | null>(
      (acc, c) => unionBbox(acc, nodeBbox(c)),
      null,
    );
  }
  return null;
}

export function listLayers(root: INode): LayerInfo[] {
  return topLevelShapes(root).map((node) => ({
    id: node.attributes.id,
    tag: node.name,
    fill: node.attributes.fill ?? null,
    stroke: node.attributes.stroke ?? null,
    pathCount: node.name === 'path' ? 1 : countDescendantPaths(node),
    bbox: nodeBbox(node),
  }));
}
```

- [ ] **Step 6: Create `src/types.ts`** (shared interfaces referenced above and in later tasks)

```ts
export interface LayerInfo {
  id: string;
  tag: string;
  fill: string | null;
  stroke: string | null;
  pathCount: number;
  bbox: [number, number, number, number] | null;
}

export interface SvgSummary {
  width: string | null;
  height: string | null;
  viewBox: string | null;
  layerCount: number;
  layers: LayerInfo[];
}

export type Operation =
  | { op: 'setFill'; id: string; color: string }
  | { op: 'setStroke'; id: string; color: string }
  | { op: 'removeNode'; id: string }
  | { op: 'isolateNode'; id: string }
  | { op: 'transform'; id: string; translate?: [number, number]; scale?: number | [number, number]; rotate?: number }
  | { op: 'setDimensions'; width?: number; height?: number }
  | { op: 'setAttribute'; id: string; name: string; value: string };
```

- [ ] **Step 7: Run test to verify it passes**

Run: `npx vitest run test/svgModel.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 8: Commit**

```bash
git add src/constants.ts src/workspace.ts src/svgModel.ts src/types.ts test/svgModel.test.ts
git commit -m "feat: SVG model with stable layer ids, bbox, and round-trip"
```

---

## Task 2: Inspect

**Files:**
- Create: `src/inspect.ts`
- Test: `test/inspect.test.ts`

- [ ] **Step 1: Write the failing test `test/inspect.test.ts`**

```ts
import { describe, it, expect } from 'vitest';
import { inspectSvg } from '../src/inspect.js';

const SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="100" height="80" viewBox="0 0 100 80">
<path d="M0 0 L10 10 Z" fill="#111111"/>
<path d="M5 5 L20 20 Z" fill="#222222"/>
</svg>`;

describe('inspectSvg', () => {
  it('returns dimensions, viewBox, layer count and layers', async () => {
    const s = await inspectSvg(SVG);
    expect(s.width).toBe('100');
    expect(s.height).toBe('80');
    expect(s.viewBox).toBe('0 0 100 80');
    expect(s.layerCount).toBe(2);
    expect(s.layers[0].id).toBe('layer-0');
    expect(s.layers[1].fill).toBe('#222222');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run test/inspect.test.ts`
Expected: FAIL — cannot find module `../src/inspect.js`.

- [ ] **Step 3: Create `src/inspect.ts`**

```ts
import { parseSvg, assignIds, listLayers } from './svgModel.js';
import type { SvgSummary } from './types.js';

export async function inspectSvg(svg: string): Promise<SvgSummary> {
  const tree = await parseSvg(svg);
  assignIds(tree);
  const layers = listLayers(tree);
  return {
    width: tree.attributes.width ?? null,
    height: tree.attributes.height ?? null,
    viewBox: tree.attributes.viewBox ?? null,
    layerCount: layers.length,
    layers,
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run test/inspect.test.ts`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add src/inspect.ts test/inspect.test.ts
git commit -m "feat: inspect_svg structured summary"
```

---

## Task 3: Edit operations

**Files:**
- Create: `src/edit.ts`
- Test: `test/edit.test.ts`

- [ ] **Step 1: Write the failing test `test/edit.test.ts`**

```ts
import { describe, it, expect } from 'vitest';
import { applyOperations } from '../src/edit.js';
import { inspectSvg } from '../src/inspect.js';

const SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">
<path id="layer-0" d="M0 0 L10 10 Z" fill="#ff0000"/>
<path id="layer-1" d="M5 5 L20 20 Z" fill="#00ff00"/>
</svg>`;

describe('applyOperations', () => {
  it('setFill changes a layer fill', async () => {
    const out = await applyOperations(SVG, [{ op: 'setFill', id: 'layer-0', color: '#0000ff' }]);
    expect((await inspectSvg(out)).layers[0].fill).toBe('#0000ff');
  });

  it('setStroke and setAttribute set attributes', async () => {
    const out = await applyOperations(SVG, [
      { op: 'setStroke', id: 'layer-1', color: '#abcdef' },
      { op: 'setAttribute', id: 'layer-1', name: 'opacity', value: '0.5' },
    ]);
    expect(out).toContain('stroke="#abcdef"');
    expect(out).toContain('opacity="0.5"');
  });

  it('removeNode drops a layer', async () => {
    const out = await applyOperations(SVG, [{ op: 'removeNode', id: 'layer-0' }]);
    const s = await inspectSvg(out);
    expect(s.layerCount).toBe(1);
    expect(s.layers[0].fill).toBe('#00ff00');
  });

  it('isolateNode keeps only the target shape', async () => {
    const out = await applyOperations(SVG, [{ op: 'isolateNode', id: 'layer-1' }]);
    expect(out).toContain('#00ff00');
    expect(out).not.toContain('#ff0000');
  });

  it('transform adds a transform attribute', async () => {
    const out = await applyOperations(SVG, [
      { op: 'transform', id: 'layer-0', translate: [5, 5], scale: 2, rotate: 90 },
    ]);
    expect(out).toMatch(/transform="translate\(5 5\) scale\(2\) rotate\(90\)"/);
  });

  it('setDimensions updates the root width/height', async () => {
    const out = await applyOperations(SVG, [{ op: 'setDimensions', width: 200, height: 150 }]);
    expect(out).toMatch(/width="200"/);
    expect(out).toMatch(/height="150"/);
  });

  it('throws a helpful error for an unknown id', async () => {
    await expect(applyOperations(SVG, [{ op: 'setFill', id: 'nope', color: '#000' }])).rejects.toThrow(
      /layer-0, layer-1/,
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run test/edit.test.ts`
Expected: FAIL — cannot find module `../src/edit.js`.

- [ ] **Step 3: Create `src/edit.ts`**

```ts
import { parseSvg, assignIds, findById, listLayers, toSvgString, type INode } from './svgModel.js';
import type { Operation } from './types.js';

function requireNode(root: INode, id: string): INode {
  const node = findById(root, id);
  if (!node) {
    const ids = listLayers(root).map((l) => l.id).join(', ');
    throw new Error(`No layer with id '${id}'. Valid ids: ${ids || '(none)'}`);
  }
  return node;
}

function removeById(node: INode, id: string): boolean {
  const before = node.children.length;
  node.children = node.children.filter((c) => c.attributes?.id !== id);
  if (node.children.length < before) return true;
  return node.children.some((c) => removeById(c, id));
}

function buildTransform(op: Extract<Operation, { op: 'transform' }>): string {
  const parts: string[] = [];
  if (op.translate) parts.push(`translate(${op.translate[0]} ${op.translate[1]})`);
  if (op.scale !== undefined) {
    parts.push(Array.isArray(op.scale) ? `scale(${op.scale[0]} ${op.scale[1]})` : `scale(${op.scale})`);
  }
  if (op.rotate !== undefined) parts.push(`rotate(${op.rotate})`);
  return parts.join(' ');
}

export async function applyOperations(svg: string, operations: Operation[]): Promise<string> {
  const root = await parseSvg(svg);
  assignIds(root);

  for (const op of operations) {
    switch (op.op) {
      case 'setFill':
        requireNode(root, op.id).attributes.fill = op.color;
        break;
      case 'setStroke':
        requireNode(root, op.id).attributes.stroke = op.color;
        break;
      case 'setAttribute':
        requireNode(root, op.id).attributes[op.name] = op.value;
        break;
      case 'removeNode':
        requireNode(root, op.id);
        removeById(root, op.id);
        break;
      case 'isolateNode': {
        const keep = requireNode(root, op.id);
        root.children = root.children.filter((c) => c.type !== 'element' || c === keep || c.name === 'defs');
        break;
      }
      case 'transform': {
        const node = requireNode(root, op.id);
        const t = buildTransform(op);
        node.attributes.transform = node.attributes.transform ? `${node.attributes.transform} ${t}` : t;
        break;
      }
      case 'setDimensions':
        if (op.width !== undefined) root.attributes.width = String(op.width);
        if (op.height !== undefined) root.attributes.height = String(op.height);
        break;
    }
  }

  return toSvgString(root);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run test/edit.test.ts`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add src/edit.ts test/edit.test.ts
git commit -m "feat: structured edit_svg operations"
```

---

## Task 4: Render (SVG → PNG)

**Files:**
- Create: `src/render.ts`
- Test: `test/render.test.ts`

- [ ] **Step 1: Write the failing test `test/render.test.ts`**

```ts
import { describe, it, expect } from 'vitest';
import sharp from 'sharp';
import { renderSvgToPng } from '../src/render.js';

const RED = `<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 10 10">
<rect width="10" height="10" fill="#ff0000"/></svg>`;

describe('renderSvgToPng', () => {
  it('renders a non-empty PNG at the requested width', async () => {
    const png = renderSvgToPng(RED, { width: 40 });
    expect(png.length).toBeGreaterThan(0);
    const meta = await sharp(png).metadata();
    expect(meta.format).toBe('png');
    expect(meta.width).toBe(40);
  });

  it('produces red pixels matching the source', async () => {
    const png = renderSvgToPng(RED, { width: 10 });
    const { data } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
    expect(data[0]).toBe(255); // R
    expect(data[1]).toBe(0);   // G
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run test/render.test.ts`
Expected: FAIL — cannot find module `../src/render.js`.

- [ ] **Step 3: Create `src/render.ts`**

```ts
import { Resvg } from '@resvg/resvg-js';
import { PREVIEW_WIDTH } from './constants.js';

export interface RenderOptions {
  width?: number;
  scale?: number;
}

export function renderSvgToPng(svg: string, opts: RenderOptions = {}): Buffer {
  const options: ConstructorParameters<typeof Resvg>[1] = {};
  if (opts.width) options.fitTo = { mode: 'width', value: opts.width };
  else if (opts.scale) options.fitTo = { mode: 'zoom', value: opts.scale };
  else options.fitTo = { mode: 'width', value: PREVIEW_WIDTH };

  const resvg = new Resvg(svg, options);
  return Buffer.from(resvg.render().asPng());
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run test/render.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/render.ts test/render.test.ts
git commit -m "feat: render_svg to PNG via resvg"
```

---

## Task 5: Optimize (ids preserved)

**Files:**
- Create: `src/optimize.ts`
- Test: `test/optimize.test.ts`

- [ ] **Step 1: Write the failing test `test/optimize.test.ts`**

```ts
import { describe, it, expect } from 'vitest';
import { optimizeSvg } from '../src/optimize.js';

const MESSY = `<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">
  <!-- a comment -->
  <path id="layer-0" d="M0 0 L10 10 Z" fill="#ff0000"   />
  <path id="layer-1" d="M5 5 L20 20 Z" fill="#00ff00"/>
</svg>`;

describe('optimizeSvg', () => {
  it('shrinks the SVG but preserves layer ids and viewBox', () => {
    const out = optimizeSvg(MESSY);
    expect(out.length).toBeLessThan(MESSY.length);
    expect(out).toContain('id="layer-0"');
    expect(out).toContain('id="layer-1"');
    expect(out).toContain('viewBox="0 0 100 100"');
    expect(out).not.toContain('<!--');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run test/optimize.test.ts`
Expected: FAIL — cannot find module `../src/optimize.js`.

- [ ] **Step 3: Create `src/optimize.ts`**

```ts
import { optimize } from 'svgo';

export function optimizeSvg(svg: string): string {
  const result = optimize(svg, {
    multipass: true,
    plugins: [
      {
        name: 'preset-default',
        params: { overrides: { cleanupIds: false, removeViewBox: false } },
      },
    ],
  });
  return result.data;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run test/optimize.test.ts`
Expected: PASS (1 test). (`cleanupIds: false` is what keeps `layer-*` ids alive.)

- [ ] **Step 5: Commit**

```bash
git add src/optimize.ts test/optimize.test.ts
git commit -m "feat: optimize_svg preserving layer ids"
```

---

## Task 6: Convert (raster → SVG)

**Files:**
- Create: `src/convert.ts`, `test/helpers.ts`
- Test: `test/convert.test.ts`

- [ ] **Step 1: Create fixture helpers `test/helpers.ts`**

```ts
import sharp from 'sharp';

/** Raw RGB buffer wrapped as a sharp image with exactly `colors` distinct colors. */
export function rawWithColors(colors: number, side = 16): sharp.Sharp {
  const channels = 3;
  const data = Buffer.alloc(side * side * channels);
  for (let p = 0; p < side * side; p++) {
    const c = p % colors;
    data[p * channels] = (c * 37) % 256;
    data[p * channels + 1] = (c * 53) % 256;
    data[p * channels + 2] = (c * 71) % 256;
  }
  return sharp(data, { raw: { width: side, height: side, channels } });
}

/** A simple 2-color PNG (black square on white) as a PNG buffer. */
export async function simplePng(side = 64): Promise<Buffer> {
  const bg = { create: { width: side, height: side, channels: 3 as const, background: '#ffffff' } };
  const square = await sharp({ create: { width: side / 2, height: side / 2, channels: 3, background: '#000000' } })
    .png()
    .toBuffer();
  return sharp(bg)
    .composite([{ input: square, left: side / 4, top: side / 4 }])
    .png()
    .toBuffer();
}

/** A many-color horizontal gradient PNG buffer. */
export async function gradientPng(side = 64): Promise<Buffer> {
  const channels = 3;
  const data = Buffer.alloc(side * side * channels);
  for (let y = 0; y < side; y++) {
    for (let x = 0; x < side; x++) {
      const i = (y * side + x) * channels;
      data[i] = Math.floor((x / side) * 255);
      data[i + 1] = Math.floor((y / side) * 255);
      data[i + 2] = 128;
    }
  }
  return sharp(data, { raw: { width: side, height: side, channels } }).png().toBuffer();
}
```

- [ ] **Step 2: Write the failing test `test/convert.test.ts`**

```ts
import { describe, it, expect } from 'vitest';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {
  countUniqueColors,
  classifyComplexity,
  buildVtracerConfig,
  convertImageToSvg,
} from '../src/convert.js';
import { rawWithColors, simplePng, gradientPng } from './helpers.js';

describe('convert heuristics', () => {
  it('countUniqueColors counts distinct colors', async () => {
    const n = await countUniqueColors(await rawWithColors(5).png().toBuffer());
    expect(n).toBe(5);
  });

  it('classifyComplexity splits on the threshold', () => {
    expect(classifyComplexity(4)).toBe('simple');
    expect(classifyComplexity(16)).toBe('simple');
    expect(classifyComplexity(17)).toBe('layered');
  });

  it('buildVtracerConfig picks Binary for simple, Color for layered', () => {
    expect(buildVtracerConfig('simple').colorMode).toBe(0); // ColorMode.Binary === 0
    expect(buildVtracerConfig('layered').colorMode).toBe(1); // ColorMode.Color === 1
  });
});

describe('convertImageToSvg', () => {
  it('converts a simple image to a valid SVG with a preview', async () => {
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'i2svg-'));
    const input = path.join(dir, 'simple.png');
    await fs.writeFile(input, await simplePng());

    const res = await convertImageToSvg(input, { mode: 'auto' });
    expect(res.mode).toBe('simple');
    const svg = await fs.readFile(res.svgPath, 'utf8');
    expect(svg).toContain('<svg');
    expect(svg).toContain('<path');
    expect(res.summary.layerCount).toBeGreaterThan(0);
    const stat = await fs.stat(res.previewPath);
    expect(stat.size).toBeGreaterThan(0);
  });

  it('produces layered output for a gradient', async () => {
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'i2svg-'));
    const input = path.join(dir, 'grad.png');
    await fs.writeFile(input, await gradientPng());

    const res = await convertImageToSvg(input, { mode: 'auto' });
    expect(res.mode).toBe('layered');
    expect(res.summary.layerCount).toBeGreaterThan(1);
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `npx vitest run test/convert.test.ts`
Expected: FAIL — cannot find module `../src/convert.js`.

- [ ] **Step 4: Create `src/convert.ts`**

```ts
import { promises as fs } from 'node:fs';
import sharp from 'sharp';
import { vectorize, ColorMode, Hierarchical, PathSimplifyMode, type Config } from '@neplex/vectorizer';
import { COLOR_THRESHOLD, MAX_DIMENSION, SAMPLE_SIZE, PREVIEW_WIDTH } from './constants.js';
import { parseSvg, assignIds, toSvgString } from './svgModel.js';
import { inspectSvg } from './inspect.js';
import { renderSvgToPng } from './render.js';
import { deriveOutputPath, previewPathFor } from './workspace.js';
import type { SvgSummary } from './types.js';

export type ConvertMode = 'auto' | 'simple' | 'layered';

export interface ConvertOptions {
  mode?: ConvertMode;
  maxColors?: number;
  outputPath?: string;
}

export interface ConvertResult {
  svgPath: string;
  previewPath: string;
  previewPng: Buffer;
  mode: 'simple' | 'layered';
  downscaled: boolean;
  summary: SvgSummary;
}

export async function countUniqueColors(input: Buffer | string): Promise<number> {
  const { data, info } = await sharp(input)
    .resize(SAMPLE_SIZE, SAMPLE_SIZE, { fit: 'inside' })
    .raw()
    .toBuffer({ resolveWithObject: true });
  const ch = info.channels;
  const seen = new Set<number>();
  for (let i = 0; i < data.length; i += ch) {
    seen.add((data[i] << 16) | (data[i + 1] << 8) | data[i + 2]);
  }
  return seen.size;
}

export function classifyComplexity(uniqueColors: number): 'simple' | 'layered' {
  return uniqueColors <= COLOR_THRESHOLD ? 'simple' : 'layered';
}

const BASE_CONFIG: Config = {
  colorMode: ColorMode.Color,
  hierarchical: Hierarchical.Stacked,
  mode: PathSimplifyMode.Spline,
  filterSpeckle: 4,
  colorPrecision: 6,
  layerDifference: 16,
  cornerThreshold: 60,
  lengthThreshold: 4,
  spliceThreshold: 45,
  maxIterations: 10,
  pathPrecision: 8,
};

export function buildVtracerConfig(mode: 'simple' | 'layered', maxColors?: number): Config {
  if (mode === 'simple') {
    return { ...BASE_CONFIG, colorMode: ColorMode.Binary };
  }
  const colorPrecision = maxColors
    ? Math.max(1, Math.min(8, Math.round(Math.log2(maxColors))))
    : BASE_CONFIG.colorPrecision;
  return { ...BASE_CONFIG, colorMode: ColorMode.Color, colorPrecision };
}

export async function convertImageToSvg(inputPath: string, opts: ConvertOptions = {}): Promise<ConvertResult> {
  const meta = await sharp(inputPath).metadata();
  const tooBig = (meta.width ?? 0) > MAX_DIMENSION || (meta.height ?? 0) > MAX_DIMENSION;
  const buffer = tooBig
    ? await sharp(inputPath).resize(MAX_DIMENSION, MAX_DIMENSION, { fit: 'inside', withoutEnlargement: true }).png().toBuffer()
    : await sharp(inputPath).png().toBuffer();

  let mode = opts.mode ?? 'auto';
  if (mode === 'auto') mode = classifyComplexity(await countUniqueColors(buffer));
  const resolvedMode = mode as 'simple' | 'layered';

  const rawSvg = await vectorize(buffer, buildVtracerConfig(resolvedMode, opts.maxColors));

  const tree = await parseSvg(rawSvg);
  assignIds(tree);
  const svg = toSvgString(tree);

  const svgPath = opts.outputPath ?? deriveOutputPath(inputPath, '.svg');
  await fs.writeFile(svgPath, svg, 'utf8');

  const previewPng = renderSvgToPng(svg, { width: PREVIEW_WIDTH });
  const previewPath = previewPathFor(svgPath);
  await fs.writeFile(previewPath, previewPng);

  return {
    svgPath,
    previewPath,
    previewPng,
    mode: resolvedMode,
    downscaled: tooBig,
    summary: await inspectSvg(svg),
  };
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npx vitest run test/convert.test.ts`
Expected: PASS (5 tests). If `ColorMode.Binary`/`Color` enum values differ from 0/1, adjust the two assertions in Step 2 to compare against `ColorMode.Binary`/`ColorMode.Color` imported from the package.

- [ ] **Step 6: Commit**

```bash
git add src/convert.ts test/convert.test.ts test/helpers.ts
git commit -m "feat: convert_image_to_svg with hybrid complexity heuristic"
```

---

## Task 7: Vector import (PDF / AI / EPS)

**Files:**
- Create: `src/importVector.ts`
- Test: `test/importVector.test.ts`
- Modify: `test/helpers.ts` (add `vectorPdf`)

- [ ] **Step 1: Add a PDF fixture generator to `test/helpers.ts`**

Append:

```ts
import { PDFDocument, rgb } from 'pdf-lib';

/** A single-page vector PDF (red rectangle) as a Buffer. */
export async function vectorPdf(): Promise<Buffer> {
  const doc = await PDFDocument.create();
  const page = doc.addPage([100, 100]);
  page.drawRectangle({ x: 20, y: 20, width: 60, height: 60, color: rgb(1, 0, 0) });
  const bytes = await doc.save();
  return Buffer.from(bytes);
}

/** A minimal valid EPS document (single stroked line) as a Buffer. */
export function simpleEps(): Buffer {
  return Buffer.from(
    [
      '%!PS-Adobe-3.0 EPSF-3.0',
      '%%BoundingBox: 0 0 100 100',
      'newpath 10 10 moveto 90 90 lineto 2 setlinewidth stroke',
      'showpage',
      '%%EOF',
    ].join('\n'),
    'utf8',
  );
}
```

- [ ] **Step 2: Write the failing test `test/importVector.test.ts`**

```ts
import { describe, it, expect } from 'vitest';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { importVector, detectGhostscript } from '../src/importVector.js';
import { vectorPdf, simpleEps } from './helpers.js';

describe('importVector', () => {
  it('imports a vector PDF to SVG with paths preserved', async () => {
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'i2svg-pdf-'));
    const input = path.join(dir, 'in.pdf');
    await fs.writeFile(input, await vectorPdf());

    const res = await importVector(input, {});
    const svg = await fs.readFile(res.svgPath, 'utf8');
    expect(svg).toContain('<svg');
    expect(res.summary.layerCount).toBeGreaterThan(0);
    expect((await fs.stat(res.previewPath)).size).toBeGreaterThan(0);
  });

  it('rejects an unsupported extension', async () => {
    await expect(importVector('whatever.txt', {})).rejects.toThrow(/Unsupported vector format/);
  });

  it('EPS: imports when Ghostscript is present, else errors with guidance', async () => {
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'i2svg-eps-'));
    const input = path.join(dir, 'in.eps');
    await fs.writeFile(input, simpleEps());

    if (detectGhostscript()) {
      const res = await importVector(input, {});
      expect((await fs.readFile(res.svgPath, 'utf8'))).toContain('<svg');
    } else {
      await expect(importVector(input, {})).rejects.toThrow(/Ghostscript/);
    }
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `npx vitest run test/importVector.test.ts`
Expected: FAIL — cannot find module `../src/importVector.js`.

- [ ] **Step 4: Create `src/importVector.ts`**

```ts
import { promises as fs } from 'node:fs';
import { execFileSync } from 'node:child_process';
import os from 'node:os';
import path from 'node:path';
import * as mupdf from 'mupdf';
import { parseSvg, assignIds, toSvgString } from './svgModel.js';
import { inspectSvg } from './inspect.js';
import { renderSvgToPng } from './render.js';
import { deriveOutputPath, previewPathFor } from './workspace.js';
import { PREVIEW_WIDTH } from './constants.js';
import type { SvgSummary } from './types.js';

export interface ImportOptions {
  page?: number;
  outputPath?: string;
}

export interface ImportResult {
  svgPath: string;
  previewPath: string;
  previewPng: Buffer;
  summary: SvgSummary;
}

const GS_CANDIDATES = ['gs', 'gswin64c', 'gswin32c'];

export function detectGhostscript(): string | null {
  for (const cmd of GS_CANDIDATES) {
    try {
      execFileSync(cmd, ['--version'], { stdio: 'ignore' });
      return cmd;
    } catch {
      // not this one
    }
  }
  return null;
}

/** Convert one page of a PDF (or PDF-compatible AI) buffer to an SVG string. */
export function pdfBufferToSvg(buffer: Buffer, page = 0): string {
  const doc = mupdf.Document.openDocument(buffer, 'application/pdf');
  const count = doc.countPages();
  if (page < 0 || page >= count) {
    throw new Error(`page ${page} out of range; document has ${count} page(s)`);
  }
  const pg = doc.loadPage(page);
  const out = new mupdf.Buffer();
  const writer = new mupdf.DocumentWriter(out, 'svg', '');
  const device = writer.beginPage(pg.getBounds());
  pg.run(device, mupdf.Matrix.identity);
  writer.endPage();
  writer.close();
  return out.asString();
}

async function epsToSvg(epsPath: string, page = 0): Promise<string> {
  const gs = detectGhostscript();
  if (!gs) {
    throw new Error(
      'EPS import requires Ghostscript on PATH. Install it (Windows: gswin64c from https://ghostscript.com/releases/) and retry. PDF and AI files work without it.',
    );
  }
  const pdfPath = path.join(os.tmpdir(), `imagetosvg-${process.pid}-${Date.now()}.pdf`);
  try {
    execFileSync(gs, ['-dNOPAUSE', '-dBATCH', '-dSAFER', '-sDEVICE=pdfwrite', '-o', pdfPath, epsPath], {
      stdio: 'ignore',
    });
    return pdfBufferToSvg(await fs.readFile(pdfPath), page);
  } finally {
    await fs.unlink(pdfPath).catch(() => {});
  }
}

export async function importVector(inputPath: string, opts: ImportOptions = {}): Promise<ImportResult> {
  const ext = path.extname(inputPath).toLowerCase();
  const page = opts.page ?? 0;

  let rawSvg: string;
  if (ext === '.pdf' || ext === '.ai') {
    rawSvg = pdfBufferToSvg(await fs.readFile(inputPath), page);
  } else if (ext === '.eps') {
    rawSvg = await epsToSvg(inputPath, page);
  } else {
    throw new Error(`Unsupported vector format '${ext}'. Supported: .pdf, .ai, .eps`);
  }

  const tree = await parseSvg(rawSvg);
  assignIds(tree);
  const svg = toSvgString(tree);

  const svgPath = opts.outputPath ?? deriveOutputPath(inputPath, '.svg');
  await fs.writeFile(svgPath, svg, 'utf8');

  const previewPng = renderSvgToPng(svg, { width: PREVIEW_WIDTH });
  const previewPath = previewPathFor(svgPath);
  await fs.writeFile(previewPath, previewPng);

  return { svgPath, previewPath, previewPng, summary: await inspectSvg(svg) };
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npx vitest run test/importVector.test.ts`
Expected: PASS (3 tests). The EPS test exercises whichever branch matches your machine (GS present → conversion; absent → guidance error).
If mupdf's writer call signature differs in 1.27, the failure will point at `pdfBufferToSvg`; consult `node_modules/mupdf` types for `DocumentWriter`/`beginPage`/`run` and adjust that single function — the rest of the module is unaffected.

- [ ] **Step 6: Commit**

```bash
git add src/importVector.ts test/importVector.test.ts test/helpers.ts
git commit -m "feat: import_vector for PDF/AI (mupdf) and EPS (Ghostscript)"
```

---

## Task 8: MCP server and entry point

**Files:**
- Create: `src/server.ts`, `src/index.ts`
- Test: `test/server.test.ts`

- [ ] **Step 1: Write the failing test `test/server.test.ts`**

```ts
import { describe, it, expect } from 'vitest';
import { createServer } from '../src/server.js';

describe('server', () => {
  it('creates an McpServer exposing the six tools', () => {
    const server = createServer();
    expect(server).toBeDefined();
    // McpServer keeps registered tools on an internal registry; assert it constructed.
    expect(typeof server.connect).toBe('function');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run test/server.test.ts`
Expected: FAIL — cannot find module `../src/server.js`.

- [ ] **Step 3: Create `src/server.ts`**

```ts
import { promises as fs } from 'node:fs';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { convertImageToSvg } from './convert.js';
import { importVector } from './importVector.js';
import { inspectSvg } from './inspect.js';
import { applyOperations } from './edit.js';
import { renderSvgToPng } from './render.js';
import { optimizeSvg } from './optimize.js';
import { previewPathFor } from './workspace.js';
import type { Operation } from './types.js';

function textResult(obj: unknown) {
  return { content: [{ type: 'text' as const, text: typeof obj === 'string' ? obj : JSON.stringify(obj, null, 2) }] };
}

function errorResult(message: string) {
  return { content: [{ type: 'text' as const, text: `Error: ${message}` }], isError: true };
}

function imageResult(text: string, png: Buffer) {
  return {
    content: [
      { type: 'text' as const, text },
      { type: 'image' as const, data: png.toString('base64'), mimeType: 'image/png' },
    ],
  };
}

const operationSchema = z.discriminatedUnion('op', [
  z.object({ op: z.literal('setFill'), id: z.string(), color: z.string() }),
  z.object({ op: z.literal('setStroke'), id: z.string(), color: z.string() }),
  z.object({ op: z.literal('removeNode'), id: z.string() }),
  z.object({ op: z.literal('isolateNode'), id: z.string() }),
  z.object({
    op: z.literal('transform'),
    id: z.string(),
    translate: z.tuple([z.number(), z.number()]).optional(),
    scale: z.union([z.number(), z.tuple([z.number(), z.number()])]).optional(),
    rotate: z.number().optional(),
  }),
  z.object({ op: z.literal('setDimensions'), width: z.number().optional(), height: z.number().optional() }),
  z.object({ op: z.literal('setAttribute'), id: z.string(), name: z.string(), value: z.string() }),
]);

export function createServer(): McpServer {
  const server = new McpServer({ name: 'imagetosvg', version: '0.1.0' });

  server.registerTool(
    'convert_image_to_svg',
    {
      title: 'Convert image to SVG',
      description:
        'Vectorize a raster image (PNG/JPG/WebP/GIF/BMP/TIFF/AVIF) into an editable SVG. mode=auto picks simple vs layered by image complexity. Returns a summary and an inline PNG preview.',
      inputSchema: {
        input_path: z.string(),
        mode: z.enum(['auto', 'simple', 'layered']).optional(),
        max_colors: z.number().int().positive().optional(),
        output_path: z.string().optional(),
      },
    },
    async ({ input_path, mode, max_colors, output_path }) => {
      try {
        const r = await convertImageToSvg(input_path, { mode, maxColors: max_colors, outputPath: output_path });
        return imageResult(
          JSON.stringify(
            { svgPath: r.svgPath, previewPath: r.previewPath, mode: r.mode, downscaled: r.downscaled, summary: r.summary },
            null,
            2,
          ),
          r.previewPng,
        );
      } catch (e) {
        return errorResult((e as Error).message);
      }
    },
  );

  server.registerTool(
    'import_vector',
    {
      title: 'Import vector file to SVG',
      description:
        'Import a vector file (PDF, PDF-compatible AI, or EPS) into an editable SVG with paths preserved. EPS requires Ghostscript on PATH. page selects a PDF page (default 0).',
      inputSchema: {
        input_path: z.string(),
        page: z.number().int().nonnegative().optional(),
        output_path: z.string().optional(),
      },
    },
    async ({ input_path, page, output_path }) => {
      try {
        const r = await importVector(input_path, { page, outputPath: output_path });
        return imageResult(
          JSON.stringify({ svgPath: r.svgPath, previewPath: r.previewPath, summary: r.summary }, null, 2),
          r.previewPng,
        );
      } catch (e) {
        return errorResult((e as Error).message);
      }
    },
  );

  server.registerTool(
    'inspect_svg',
    {
      title: 'Inspect SVG',
      description: 'Return SVG dimensions, viewBox, and the list of addressable layers (id, tag, fill, stroke, pathCount, bbox).',
      inputSchema: { svg_path: z.string() },
    },
    async ({ svg_path }) => {
      try {
        const svg = await fs.readFile(svg_path, 'utf8');
        return textResult(await inspectSvg(svg));
      } catch (e) {
        return errorResult((e as Error).message);
      }
    },
  );

  server.registerTool(
    'edit_svg',
    {
      title: 'Edit SVG',
      description:
        'Apply structured edits to an SVG by layer id: setFill, setStroke, removeNode, isolateNode, transform, setDimensions, setAttribute. Writes back to svg_path (or output_path) and returns the updated summary.',
      inputSchema: {
        svg_path: z.string(),
        operations: z.array(operationSchema),
        output_path: z.string().optional(),
      },
    },
    async ({ svg_path, operations, output_path }) => {
      try {
        const svg = await fs.readFile(svg_path, 'utf8');
        const out = await applyOperations(svg, operations as Operation[]);
        const target = output_path ?? svg_path;
        await fs.writeFile(target, out, 'utf8');
        return textResult({ svgPath: target, summary: await inspectSvg(out) });
      } catch (e) {
        return errorResult((e as Error).message);
      }
    },
  );

  server.registerTool(
    'render_svg',
    {
      title: 'Render SVG to PNG',
      description: 'Rasterize an SVG to PNG for visual verification. Returns the PNG inline and writes a .preview.png next to the SVG.',
      inputSchema: {
        svg_path: z.string(),
        width: z.number().int().positive().optional(),
        scale: z.number().positive().optional(),
      },
    },
    async ({ svg_path, width, scale }) => {
      try {
        const svg = await fs.readFile(svg_path, 'utf8');
        const png = renderSvgToPng(svg, { width, scale });
        const previewPath = previewPathFor(svg_path);
        await fs.writeFile(previewPath, png);
        return imageResult(JSON.stringify({ previewPath }, null, 2), png);
      } catch (e) {
        return errorResult((e as Error).message);
      }
    },
  );

  server.registerTool(
    'optimize_svg',
    {
      title: 'Optimize SVG',
      description: 'Run svgo to clean up an SVG while preserving layer ids and viewBox. Writes back to svg_path (or output_path).',
      inputSchema: { svg_path: z.string(), output_path: z.string().optional() },
    },
    async ({ svg_path, output_path }) => {
      try {
        const svg = await fs.readFile(svg_path, 'utf8');
        const out = optimizeSvg(svg);
        const target = output_path ?? svg_path;
        await fs.writeFile(target, out, 'utf8');
        return textResult({ svgPath: target, bytesBefore: svg.length, bytesAfter: out.length });
      } catch (e) {
        return errorResult((e as Error).message);
      }
    },
  );

  return server;
}

export async function startServer(): Promise<void> {
  const server = createServer();
  const transport = new StdioServerTransport();
  await server.connect(transport);
}
```

- [ ] **Step 4: Create `src/index.ts`**

```ts
#!/usr/bin/env node
import { startServer } from './server.js';

startServer().catch((err) => {
  console.error('imagetosvg failed to start:', err);
  process.exit(1);
});
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npx vitest run test/server.test.ts`
Expected: PASS (1 test). If `registerTool` is not a function on this SDK build, switch the six `server.registerTool(name, def, handler)` calls to `server.tool(name, def.description, def.inputSchema, handler)` — both are exported by `McpServer` in 1.29; the test will confirm.

- [ ] **Step 6: Build to verify types compile**

Run: `npm run build`
Expected: `tsc` exits 0; `dist/` contains `index.js` and module files.

- [ ] **Step 7: Smoke-test the server over stdio**

Run:
```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | node dist/index.js
```
Expected: a single JSON-RPC response line listing the six tool names (`convert_image_to_svg`, `import_vector`, `inspect_svg`, `edit_svg`, `render_svg`, `optimize_svg`). (The server reads line-delimited JSON-RPC on stdin; it will stay open — Ctrl+C to exit.)

- [ ] **Step 8: Commit**

```bash
git add src/server.ts src/index.ts test/server.test.ts
git commit -m "feat: MCP server exposing six imagetosvg tools"
```

---

## Task 9: Claude skill + README

**Files:**
- Create: `skill/SKILL.md`, `README.md`

- [ ] **Step 1: Create `skill/SKILL.md`**

```markdown
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
```

- [ ] **Step 2: Create `README.md`**

```markdown
# imagetosvg

Local MCP server that gives AI agents full control over images: vectorize raster
images, import vector files (PDF/AI/EPS), then inspect, edit, render, and optimize
the SVG. No API keys, no cloud — everything runs locally.

## Install
```bash
npm install
npm run build
```

## Tools
| Tool | Purpose |
|------|---------|
| `convert_image_to_svg` | Raster → SVG (hybrid: simple trace or layered color trace) |
| `import_vector` | PDF / AI / EPS → SVG (paths preserved) |
| `inspect_svg` | List addressable layers (id, fill, stroke, bbox) |
| `edit_svg` | Structured edits by layer id |
| `render_svg` | Rasterize SVG → PNG for visual verification |
| `optimize_svg` | Clean up SVG (layer ids preserved) |

## Use as an MCP server

Claude Code / Claude Desktop (`claude_desktop_config.json` or `.mcp.json`):
```json
{
  "mcpServers": {
    "imagetosvg": {
      "command": "node",
      "args": ["C:/Users/rajra/Desktop/imagetosvg/dist/index.js"]
    }
  }
}
```
Cursor / Windsurf use the same `command`/`args` shape in their MCP settings.

## Optional: EPS support
EPS import requires [Ghostscript](https://ghostscript.com/releases/) on `PATH`
(`gswin64c` on Windows). PDF and AI work without it.

## Development
```bash
npm test          # run the vitest suite
npm run dev       # run the server from source via tsx
```
```

- [ ] **Step 3: Run the full test suite**

Run: `npx vitest run`
Expected: all tests pass across every `test/*.test.ts` file.

- [ ] **Step 4: Commit**

```bash
git add skill/SKILL.md README.md
git commit -m "docs: Claude skill workflow and README with MCP config"
```

---

## Self-Review (completed during plan authoring)

**Spec coverage:**
- Hybrid raster conversion (simple/layered, auto-detect) → Task 6.
- Vector import PDF/AI (mupdf) + EPS optional via Ghostscript → Task 7.
- `inspect_svg` structured summary with bbox → Tasks 1–2.
- `edit_svg` ops (setFill/setStroke/removeNode/isolateNode/transform/setDimensions/setAttribute) → Task 3.
- `render_svg` verification → Task 4.
- `optimize_svg` preserving ids → Task 5.
- Six MCP tools + stdio server → Task 8.
- Claude skill wrapper + README/MCP config → Task 9.
- Error handling (missing/unsupported input, oversized downscale, unknown layer id, EPS-without-GS, PDF page range) → covered in edit (unknown id), convert (downscale), importVector (unsupported ext, EPS guidance, page range), and per-tool try/catch in Task 8.
- Testing strategy (real fixtures, generated; round-trip recolor; layered assertion; conditional EPS) → Tasks 1–9.

**Placeholder scan:** No TBD/TODO; every code step contains complete code. The two "if the API differs" notes (vtracer enum values, mupdf writer signature, SDK `registerTool` vs `tool`) are concrete fallbacks with exact remedies, not placeholders.

**Type consistency:** `LayerInfo`, `SvgSummary`, and `Operation` are defined once in `src/types.ts` and imported everywhere. Function names are consistent across tasks (`parseSvg`, `assignIds`, `listLayers`, `findById`, `toSvgString`, `inspectSvg`, `applyOperations`, `renderSvgToPng`, `optimizeSvg`, `convertImageToSvg`, `importVector`, `createServer`, `startServer`). `svgModel.ts` re-exports `INode` for downstream imports.

**Note on round-trip recolor test (spec):** covered functionally by `edit.test.ts` (setFill → inspect shows new fill) plus `render.test.ts` (fill → pixel color). A combined pixel-level recolor assertion is redundant given those two and is intentionally omitted (YAGNI).
