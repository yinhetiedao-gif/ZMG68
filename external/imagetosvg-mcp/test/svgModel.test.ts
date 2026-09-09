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
