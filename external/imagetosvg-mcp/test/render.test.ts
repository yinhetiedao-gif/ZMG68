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
