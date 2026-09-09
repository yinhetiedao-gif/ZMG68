import { promises as fs } from 'node:fs';
import sharp from 'sharp';
import { vectorize, ColorMode, Hierarchical, PathSimplifyMode, type Config } from '@neplex/vectorizer';
import { COLOR_THRESHOLD, MAX_DIMENSION, SAMPLE_SIZE, PREVIEW_WIDTH } from './constants.js';
import { parseSvg, assignIds, toSvgString } from './svgModel.js';
import { inspectSvg } from './inspect.js';
import { renderSvgToPng } from './render.js';
import { deriveOutputPath, previewPathFor } from './workspace.js';
import type { SvgSummary } from './types.js';

export type ConvertMode = 'auto' | 'simple' | 'layered';

export interface ConvertOptions {
  mode?: ConvertMode;
  maxColors?: number;
  outputPath?: string;
}

export interface ConvertResult {
  svgPath: string;
  previewPath: string;
  previewPng: Buffer;
  mode: 'simple' | 'layered';
  downscaled: boolean;
  summary: SvgSummary;
}

export async function countUniqueColors(input: Buffer | string): Promise<number> {
  const { data, info } = await sharp(input)
    .resize(SAMPLE_SIZE, SAMPLE_SIZE, { fit: 'inside', withoutEnlargement: true, kernel: 'nearest' })
    .raw()
    .toBuffer({ resolveWithObject: true });
  const ch = info.channels;
  const seen = new Set<number>();
  // Alpha is intentionally ignored: this is a complexity heuristic over RGB,
  // not an exact distinct-pixel count.
  for (let i = 0; i < data.length; i += ch) {
    seen.add((data[i] << 16) | (data[i + 1] << 8) | data[i + 2]);
  }
  return seen.size;
}

export function classifyComplexity(uniqueColors: number): 'simple' | 'layered' {
  return uniqueColors <= COLOR_THRESHOLD ? 'simple' : 'layered';
}

const BASE_CONFIG: Config = {
  colorMode: ColorMode.Color,
  hierarchical: Hierarchical.Stacked,
  mode: PathSimplifyMode.Spline,
  filterSpeckle: 4,
  colorPrecision: 8,
  layerDifference: 16,
  cornerThreshold: 60,
  lengthThreshold: 4,
  spliceThreshold: 45,
  maxIterations: 10,
  pathPrecision: 8,
};

export function buildVtracerConfig(mode: 'simple' | 'layered', maxColors?: number): Config {
  if (mode === 'simple') {
    return { ...BASE_CONFIG, colorMode: ColorMode.Binary };
  }
  const colorPrecision = maxColors
    ? Math.max(1, Math.min(8, Math.round(Math.log2(maxColors))))
    : BASE_CONFIG.colorPrecision;
  return { ...BASE_CONFIG, colorMode: ColorMode.Color, colorPrecision };
}

export async function convertImageToSvg(inputPath: string, opts: ConvertOptions = {}): Promise<ConvertResult> {
  const meta = await sharp(inputPath).metadata();
  const tooBig = (meta.width ?? 0) > MAX_DIMENSION || (meta.height ?? 0) > MAX_DIMENSION;
  const buffer = tooBig
    ? await sharp(inputPath).resize(MAX_DIMENSION, MAX_DIMENSION, { fit: 'inside', withoutEnlargement: true }).png().toBuffer()
    : await sharp(inputPath).png().toBuffer();

  let mode = opts.mode ?? 'auto';
  if (mode === 'auto') mode = classifyComplexity(await countUniqueColors(buffer));
  const resolvedMode = mode as 'simple' | 'layered';

  const rawSvg = await vectorize(buffer, buildVtracerConfig(resolvedMode, opts.maxColors));

  const tree = await parseSvg(rawSvg);
  assignIds(tree);
  const svg = toSvgString(tree);

  const svgPath = opts.outputPath ?? deriveOutputPath(inputPath, '.svg');
  await fs.writeFile(svgPath, svg, 'utf8');

  const previewPng = renderSvgToPng(svg, { width: PREVIEW_WIDTH });
  const previewPath = previewPathFor(svgPath);
  await fs.writeFile(previewPath, previewPng);

  return {
    svgPath,
    previewPath,
    previewPng,
    mode: resolvedMode,
    downscaled: tooBig,
    summary: await inspectSvg(svg),
  };
}
