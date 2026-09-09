export interface LayerInfo {
  id: string;
  tag: string;
  fill: string | null;
  stroke: string | null;
  pathCount: number;
  bbox: [number, number, number, number] | null;
}

export interface SvgSummary {
  width: string | null;
  height: string | null;
  viewBox: string | null;
  layerCount: number;
  layers: LayerInfo[];
}

export type Operation =
  | { op: 'setFill'; id: string; color: string }
  | { op: 'setStroke'; id: string; color: string }
  | { op: 'removeNode'; id: string }
  | { op: 'isolateNode'; id: string }
  | { op: 'transform'; id: string; translate?: [number, number]; scale?: number | [number, number]; rotate?: number }
  | { op: 'setDimensions'; width?: number; height?: number }
  | { op: 'setAttribute'; id: string; name: string; value: string };
