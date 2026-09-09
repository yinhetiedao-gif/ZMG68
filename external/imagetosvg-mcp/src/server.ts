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
        return errorResult(e instanceof Error ? e.message : String(e));
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
        return errorResult(e instanceof Error ? e.message : String(e));
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
        return errorResult(e instanceof Error ? e.message : String(e));
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
        return errorResult(e instanceof Error ? e.message : String(e));
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
        return errorResult(e instanceof Error ? e.message : String(e));
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
        return textResult({ svgPath: target, bytesBefore: Buffer.byteLength(svg), bytesAfter: Buffer.byteLength(out) });
      } catch (e) {
        return errorResult(e instanceof Error ? e.message : String(e));
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
