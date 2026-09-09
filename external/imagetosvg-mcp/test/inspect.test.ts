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
