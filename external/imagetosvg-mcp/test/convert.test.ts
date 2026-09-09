import { describe, it, expect } from 'vitest';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { ColorMode } from '@neplex/vectorizer';
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
    expect(buildVtracerConfig('simple').colorMode).toBe(ColorMode.Binary);
    expect(buildVtracerConfig('layered').colorMode).toBe(ColorMode.Color);
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
