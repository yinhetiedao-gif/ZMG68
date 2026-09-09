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
  // mupdf objects live on the WASM heap; GC finalization is unreliable, so we
  // destroy them explicitly. try/finally also covers the error paths below.
  const doc = mupdf.Document.openDocument(buffer, 'application/pdf');
  try {
    const count = doc.countPages();
    if (page < 0 || page >= count) {
      throw new Error(`page ${page} out of range; document has ${count} page(s)`);
    }
    const pg = doc.loadPage(page);
    const out = new mupdf.Buffer();
    const writer = new mupdf.DocumentWriter(out, 'svg', '');
    try {
      const device = writer.beginPage(pg.getBounds());
      pg.run(device, mupdf.Matrix.identity);
      writer.endPage();
      writer.close();
      return out.asString();
    } finally {
      writer.destroy();
      out.destroy();
      pg.destroy();
    }
  } finally {
    doc.destroy();
  }
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
