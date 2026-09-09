import { Resvg } from '@resvg/resvg-js';
import { PREVIEW_WIDTH } from './constants.js';

export interface RenderOptions {
  width?: number;
  scale?: number;
}

export function renderSvgToPng(svg: string, opts: RenderOptions = {}): Buffer {
  const options: ConstructorParameters<typeof Resvg>[1] = {};
  if (opts.width) options.fitTo = { mode: 'width', value: opts.width };
  else if (opts.scale) options.fitTo = { mode: 'zoom', value: opts.scale };
  else options.fitTo = { mode: 'width', value: PREVIEW_WIDTH };

  const resvg = new Resvg(svg, options);
  return Buffer.from(resvg.render().asPng());
}
