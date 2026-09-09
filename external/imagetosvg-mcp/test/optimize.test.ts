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
