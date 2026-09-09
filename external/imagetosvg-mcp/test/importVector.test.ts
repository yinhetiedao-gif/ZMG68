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
