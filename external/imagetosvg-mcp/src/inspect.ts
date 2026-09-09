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
