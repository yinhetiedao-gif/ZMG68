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

  it('transform composes with an existing transform attribute', async () => {
    const withTransform = `<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">
<path id="layer-0" d="M0 0 L10 10 Z" fill="#ff0000" transform="rotate(10)"/>
</svg>`;
    const out = await applyOperations(withTransform, [
      { op: 'transform', id: 'layer-0', translate: [5, 5] },
    ]);
    expect(out).toMatch(/transform="rotate\(10\) translate\(5 5\)"/);
  });

  it('isolateNode keeps <defs> alongside the target', async () => {
    const withDefs = `<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">
<defs><linearGradient id="g"/></defs>
<path id="layer-0" d="M0 0 L10 10 Z" fill="#ff0000"/>
<path id="layer-1" d="M5 5 L20 20 Z" fill="#00ff00"/>
</svg>`;
    const out = await applyOperations(withDefs, [{ op: 'isolateNode', id: 'layer-1' }]);
    expect(out).toContain('<defs>');
    expect(out).toContain('#00ff00');
    expect(out).not.toContain('#ff0000');
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
