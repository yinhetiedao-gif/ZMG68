import sharp from 'sharp';
import { PDFDocument, rgb } from 'pdf-lib';

/** Raw RGB buffer wrapped as a sharp image with exactly `colors` distinct colors. */
export function rawWithColors(colors: number, side = 16): sharp.Sharp {
  const channels = 3;
  const data = Buffer.alloc(side * side * channels);
  for (let p = 0; p < side * side; p++) {
    const c = p % colors;
    data[p * channels] = (c * 37) % 256;
    data[p * channels + 1] = (c * 53) % 256;
    data[p * channels + 2] = (c * 71) % 256;
  }
  return sharp(data, { raw: { width: side, height: side, channels } });
}

/** A simple 2-color PNG (black square on white) as a PNG buffer. */
export async function simplePng(side = 64): Promise<Buffer> {
  const bg = { create: { width: side, height: side, channels: 3 as const, background: '#ffffff' } };
  const square = await sharp({ create: { width: side / 2, height: side / 2, channels: 3, background: '#000000' } })
    .png()
    .toBuffer();
  return sharp(bg)
    .composite([{ input: square, left: side / 4, top: side / 4 }])
    .png()
    .toBuffer();
}

/** A many-color horizontal gradient PNG buffer. */
export async function gradientPng(side = 64): Promise<Buffer> {
  const channels = 3;
  const data = Buffer.alloc(side * side * channels);
  for (let y = 0; y < side; y++) {
    for (let x = 0; x < side; x++) {
      const i = (y * side + x) * channels;
      data[i] = Math.floor((x / side) * 255);
      data[i + 1] = Math.floor((y / side) * 255);
      data[i + 2] = 128;
    }
  }
  return sharp(data, { raw: { width: side, height: side, channels } }).png().toBuffer();
}

/** A single-page vector PDF (red rectangle) as a Buffer. */
export async function vectorPdf(): Promise<Buffer> {
  const doc = await PDFDocument.create();
  const page = doc.addPage([100, 100]);
  page.drawRectangle({ x: 20, y: 20, width: 60, height: 60, color: rgb(1, 0, 0) });
  const bytes = await doc.save();
  return Buffer.from(bytes);
}

/** A minimal valid EPS document (single stroked line) as a Buffer. */
export function simpleEps(): Buffer {
  return Buffer.from(
    [
      '%!PS-Adobe-3.0 EPSF-3.0',
      '%%BoundingBox: 0 0 100 100',
      'newpath 10 10 moveto 90 90 lineto 2 setlinewidth stroke',
      'showpage',
      '%%EOF',
    ].join('\n'),
    'utf8',
  );
}
