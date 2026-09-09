import path from 'node:path';

/** Produce a sibling output path: /a/b/c.png + ".svg" => /a/b/c.svg */
export function deriveOutputPath(inputPath: string, ext: string): string {
  const dir = path.dirname(inputPath);
  const base = path.basename(inputPath, path.extname(inputPath));
  return path.join(dir, `${base}${ext}`);
}

/** Sibling preview path for an svg: /a/b/c.svg => /a/b/c.preview.png */
export function previewPathFor(svgPath: string): string {
  return svgPath.replace(/\.svg$/i, '') + '.preview.png';
}
