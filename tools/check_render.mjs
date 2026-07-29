#!/usr/bin/env node
/*
 * check_render.mjs -- is this PNG a rendered frame, or a plausible-looking
 * blank?
 *
 * A cart that boots, returns frames and renders nothing is the standard
 * pygame-port failure, and "ran 700 frames" reports success for it just as
 * loudly as for a working game. Frame counts are not evidence. This looks at
 * the pixels.
 *
 *   node tools/check_render.mjs shot.png [--min-colors 3] [--min-ink 0.02]
 *
 * Two thresholds, both of which a blank frame fails:
 *   distinct colors  a solid fill has exactly 1
 *   ink coverage     fraction of pixels differing from the most common color
 *
 * Ink is the load-bearing check; the color floor is deliberately low. A first
 * pass required 24 colors and flagged two WORKING examples: threepy renders
 * flat-shaded polygons (4 colors) and hello_python writes solid blocks
 * straight to the framebuffer (4 colors). A gate that fails a correct frame
 * is worse than no gate, because the next person turns it off. What no
 * rendering cart can fake is ink: a frame the cart never pushed is one
 * uniform color, everywhere.
 *
 * Verified against a control: a SolarWolf build with the
 * pygame.display.update() call removed runs the same 700 frames, reports the
 * same resolution, and comes back colors=1 ink=0.00%.
 */
import { readFileSync } from 'node:fs';
import { inflateSync } from 'node:zlib';

const args = process.argv.slice(2);
const path = args[0];
if (!path) {
  console.error('usage: check_render.mjs <shot.png> [--min-colors N] [--min-ink F]');
  process.exit(2);
}
let minColors = 3;
let minInk = 0.02;
for (let i = 1; i < args.length; i++) {
  if (args[i] === '--min-colors') minColors = parseInt(args[++i], 10);
  else if (args[i] === '--min-ink') minInk = parseFloat(args[++i]);
}

/* Minimal PNG reader: only the shape this repo's own tools write --
 * 8-bit truecolor, single IDAT stream, filters 0-4. */
function decodePng(buf) {
  if (buf.readUInt32BE(0) !== 0x89504e47) throw new Error('not a PNG');
  let off = 8;
  let width = 0, height = 0, colorType = 0, bitDepth = 0;
  const idat = [];
  while (off < buf.length) {
    const len = buf.readUInt32BE(off);
    const type = buf.toString('ascii', off + 4, off + 8);
    const data = buf.subarray(off + 8, off + 8 + len);
    if (type === 'IHDR') {
      width = data.readUInt32BE(0);
      height = data.readUInt32BE(4);
      bitDepth = data[8];
      colorType = data[9];
    } else if (type === 'IDAT') {
      idat.push(data);
    } else if (type === 'IEND') break;
    off += 12 + len;
  }
  if (bitDepth !== 8 || colorType !== 2) {
    throw new Error(`unsupported PNG (depth ${bitDepth}, color type ${colorType})`);
  }
  const raw = inflateSync(Buffer.concat(idat));
  const bpp = 3;
  const stride = width * bpp;
  const out = Buffer.alloc(height * stride);
  let pos = 0;
  for (let y = 0; y < height; y++) {
    const filter = raw[pos++];
    const row = y * stride;
    const prev = row - stride;
    for (let x = 0; x < stride; x++) {
      const rawByte = raw[pos + x];
      const a = x >= bpp ? out[row + x - bpp] : 0;
      const b = y > 0 ? out[prev + x] : 0;
      const c = (x >= bpp && y > 0) ? out[prev + x - bpp] : 0;
      let v;
      switch (filter) {
        case 0: v = rawByte; break;
        case 1: v = rawByte + a; break;
        case 2: v = rawByte + b; break;
        case 3: v = rawByte + ((a + b) >> 1); break;
        case 4: {
          const p = a + b - c;
          const pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
          v = rawByte + (pa <= pb && pa <= pc ? a : pb <= pc ? b : c);
          break;
        }
        default: throw new Error(`bad filter ${filter}`);
      }
      out[row + x] = v & 0xff;
    }
    pos += stride;
  }
  return { width, height, pixels: out };
}

const { width, height, pixels } = decodePng(readFileSync(path));

const counts = new Map();
const total = width * height;
for (let i = 0; i < total; i++) {
  const p = i * 3;
  const key = (pixels[p] << 16) | (pixels[p + 1] << 8) | pixels[p + 2];
  counts.set(key, (counts.get(key) || 0) + 1);
}
let topCount = 0;
for (const n of counts.values()) if (n > topCount) topCount = n;
const ink = (total - topCount) / total;
const colors = counts.size;

const ok = colors >= minColors && ink >= minInk;
console.log(`${path}: ${width}x${height} colors=${colors} ink=${(ink * 100).toFixed(2)}% ` +
            `-> ${ok ? 'RENDERING' : 'BLANK'}`);
if (!ok) {
  console.log(`  needs colors>=${minColors} and ink>=${(minInk * 100).toFixed(2)}%`);
}
process.exit(ok ? 0 : 1);
