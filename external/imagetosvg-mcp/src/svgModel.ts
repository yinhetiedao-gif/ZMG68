import { parse, stringify, type INode } from 'svgson';
import { svgPathBbox } from 'svg-path-bbox';
import { SHAPE_TAGS } from './constants.js';
import type { LayerInfo } from './types.js';

export type { INode };

export async function parseSvg(svg: string): Promise<INode> {
  return parse(svg);
}

export function toSvgString(tree: INode): string {
  return stringify(tree);
}

function isShape(node: INode): boolean {
  return node.type === 'element' && SHAPE_TAGS.includes(node.name);
}

/** Direct shape children of the <svg> root, in document order. */
function topLevelShapes(root: INode): INode[] {
  return root.children.filter(isShape);
}

/** Assign id="layer-N" to each top-level shape that lacks an id. Idempotent. */
export function assignIds(root: INode): void {
  let n = 0;
  for (const child of topLevelShapes(root)) {
    if (!child.attributes.id) child.attributes.id = `layer-${n}`;
    n += 1;
  }
}

export function findById(root: INode, id: string): INode | null {
  if (root.attributes && root.attributes.id === id) return root;
  for (const c of root.children) {
    const found = findById(c, id);
    if (found) return found;
  }
  return null;
}

function countDescendantPaths(node: INode): number {
  if (node.name === 'path') return 1;
  return node.children.reduce((acc, c) => acc + countDescendantPaths(c), 0);
}

function unionBbox(
  a: [number, number, number, number] | null,
  b: [number, number, number, number] | null,
): [number, number, number, number] | null {
  if (!a) return b;
  if (!b) return a;
  return [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[2], b[2]), Math.max(a[3], b[3])];
}

function nodeBbox(node: INode): [number, number, number, number] | null {
  if (node.name === 'path' && node.attributes.d) {
    try {
      return svgPathBbox(node.attributes.d);
    } catch {
      return null;
    }
  }
  if (node.children.length) {
    return node.children.reduce<[number, number, number, number] | null>(
      (acc, c) => unionBbox(acc, nodeBbox(c)),
      null,
    );
  }
  return null;
}

export function listLayers(root: INode): LayerInfo[] {
  return topLevelShapes(root).map((node) => ({
    id: node.attributes.id,
    tag: node.name,
    fill: node.attributes.fill ?? null,
    stroke: node.attributes.stroke ?? null,
    pathCount: node.name === 'path' ? 1 : countDescendantPaths(node),
    bbox: nodeBbox(node),
  }));
}
