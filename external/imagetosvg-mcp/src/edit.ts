import { parseSvg, assignIds, findById, listLayers, toSvgString, type INode } from './svgModel.js';
import type { Operation } from './types.js';

function requireNode(root: INode, id: string): INode {
  const node = findById(root, id);
  if (!node) {
    const ids = listLayers(root).map((l) => l.id).join(', ');
    throw new Error(`No layer with id '${id}'. Valid ids: ${ids || '(none)'}`);
  }
  return node;
}

function removeById(node: INode, id: string): boolean {
  const before = node.children.length;
  node.children = node.children.filter((c) => c.attributes?.id !== id);
  if (node.children.length < before) return true;
  return node.children.some((c) => removeById(c, id));
}

function buildTransform(op: Extract<Operation, { op: 'transform' }>): string {
  const parts: string[] = [];
  if (op.translate) parts.push(`translate(${op.translate[0]} ${op.translate[1]})`);
  if (op.scale !== undefined) {
    parts.push(Array.isArray(op.scale) ? `scale(${op.scale[0]} ${op.scale[1]})` : `scale(${op.scale})`);
  }
  if (op.rotate !== undefined) parts.push(`rotate(${op.rotate})`);
  return parts.join(' ');
}

export async function applyOperations(svg: string, operations: Operation[]): Promise<string> {
  const root = await parseSvg(svg);
  assignIds(root);

  for (const op of operations) {
    switch (op.op) {
      case 'setFill':
        requireNode(root, op.id).attributes.fill = op.color;
        break;
      case 'setStroke':
        requireNode(root, op.id).attributes.stroke = op.color;
        break;
      case 'setAttribute':
        requireNode(root, op.id).attributes[op.name] = op.value;
        break;
      case 'removeNode':
        requireNode(root, op.id);
        removeById(root, op.id);
        break;
      case 'isolateNode': {
        const keep = requireNode(root, op.id);
        root.children = root.children.filter((c) => c.type !== 'element' || c === keep || c.name === 'defs');
        break;
      }
      case 'transform': {
        const node = requireNode(root, op.id);
        const t = buildTransform(op);
        node.attributes.transform = node.attributes.transform ? `${node.attributes.transform} ${t}` : t;
        break;
      }
      case 'setDimensions':
        if (op.width !== undefined) root.attributes.width = String(op.width);
        if (op.height !== undefined) root.attributes.height = String(op.height);
        break;
    }
  }

  return toSvgString(root);
}
