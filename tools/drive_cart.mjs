#!/usr/bin/env node
/*
 * drive_cart.mjs -- run a cart headlessly with a scripted input timeline.
 *
 * `wasmcart --frames N --shot out.png` proves a cart boots and renders, but
 * every screenshot it can take is of the title screen: there is no way to
 * press a button. A port is not tested until something past the menu has been
 * seen, so this drives the same CartHost the player uses and holds buttons on
 * a schedule.
 *
 *   node tools/drive_cart.mjs cart.wasc \
 *        --script "60:;90:A;200:;260:RIGHT;400:" \
 *        --shots "150:menu.png,420:play.png" \
 *        --frames 500
 *
 * --script is `frame:BUTTONS` pairs, BUTTONS being a `+`-joined list of
 * wasmcart button names (or empty to release everything). Each entry holds
 * until the next one. --shots writes a PNG at the named frames.
 *
 * This is a test harness for this repo's own ports, not a second player:
 * rendering, PNG encoding and the host all come from the wasmcart package.
 */
import { writeFileSync } from 'node:fs';
import { deflateSync } from 'node:zlib';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const WASMCART = process.env.WASMCART_REPO || resolve(HERE, '..', '..', 'wasmcart');

const { CartHost } = await import(resolve(WASMCART, 'src/CartHost.js'));
const { BUTTON } = await import(resolve(WASMCART, 'src/abi.js'));

/* PNG encoding is duplicated from wasmcart-play.js rather than imported:
 * importing it runs that module's top-level main(), which starts a SECOND
 * player on the same cart. The first version of this harness did exactly
 * that and every run was silently doubled. */
function crc32(buf) {
  let c, crc = 0xffffffff;
  for (let n = 0; n < buf.length; n++) {
    c = (crc ^ buf[n]) & 0xff;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    crc = c ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function pngChunk(type, data) {
  const out = Buffer.alloc(12 + data.length);
  out.writeUInt32BE(data.length, 0);
  out.write(type, 4);
  Buffer.from(data).copy(out, 8);
  out.writeUInt32BE(crc32(out.subarray(4, 8 + data.length)), 8 + data.length);
  return out;
}

function encodePng(rgba, width, height) {
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;
  ihdr[9] = 2;
  const raw = Buffer.alloc(height * (1 + width * 3));
  for (let y = 0; y < height; y++) {
    const row = y * (1 + width * 3);
    raw[row] = 0;
    for (let x = 0; x < width; x++) {
      const s = (y * width + x) * 4;
      const d = row + 1 + x * 3;
      // framebuffer words are little-endian XRGB: B,G,R,X
      raw[d] = rgba[s + 2];
      raw[d + 1] = rgba[s + 1];
      raw[d + 2] = rgba[s];
    }
  }
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    pngChunk('IHDR', ihdr),
    pngChunk('IDAT', deflateSync(raw)),
    pngChunk('IEND', Buffer.alloc(0)),
  ]);
}

const argv = process.argv.slice(2);
const cartPath = argv[0];
if (!cartPath) {
  console.error('usage: drive_cart.mjs <cart.wasc> [--script F:BTNS;...] '
                + '[--shots F:file.png,...] [--frames N]');
  process.exit(2);
}

const opt = { frames: 300, script: '', shots: '' };
for (let i = 1; i < argv.length; i++) {
  if (argv[i] === '--frames') opt.frames = parseInt(argv[++i], 10) || 300;
  else if (argv[i] === '--script') opt.script = argv[++i] || '';
  else if (argv[i] === '--shots') opt.shots = argv[++i] || '';
}

// frame -> button bitmask
const timeline = new Map();
for (const part of opt.script.split(';')) {
  if (!part.trim()) continue;
  const [f, btns] = part.split(':');
  let mask = 0;
  for (const name of (btns || '').split('+')) {
    const key = name.trim().toUpperCase();
    if (!key) continue;
    if (!(key in BUTTON)) {
      console.error(`unknown button: ${key}`);
      process.exit(2);
    }
    mask |= BUTTON[key];
  }
  timeline.set(parseInt(f, 10), mask);
}

// frame -> output png path
const shots = new Map();
for (const part of opt.shots.split(',')) {
  if (!part.trim()) continue;
  const idx = part.lastIndexOf(':');
  shots.set(parseInt(part.slice(0, idx), 10), part.slice(idx + 1));
}

const host = new CartHost();
await host.load(cartPath, {});

/* A pygame cart draws through GL (sdl2_wc blits the SDL surface as a texture),
 * so the pixels are in the GPU framebuffer and CartHost's 2D framebuffer stays
 * black. Reading the wrong one gives a black PNG for a cart that is rendering
 * perfectly -- the exact false negative this harness exists to avoid -- so
 * mirror what wasmcart-play does: read back GL, and use it only when it has
 * content. readPixels' origin is bottom-left, the cart's is top-left. */
const glCtx = host.getGlContext();
let glReadback = null;
if (host.usesGL && glCtx) {
  const gi = host.getInfo();
  const gw = gi.width, gh = gi.height;
  const rgba = new Uint8Array(gw * gh * 4);
  const out = new Uint8Array(gw * gh * 4);
  glReadback = () => {
    glCtx.finish();
    glCtx.readPixels(0, 0, gw, gh, glCtx.RGBA, glCtx.UNSIGNED_BYTE, rgba);
    for (let y = 0; y < gh; y++) {
      const src = (gh - 1 - y) * gw * 4, dst = y * gw * 4;
      for (let x = 0; x < gw * 4; x += 4) {
        out[dst + x] = rgba[src + x + 2];
        out[dst + x + 1] = rgba[src + x + 1];
        out[dst + x + 2] = rgba[src + x];
        out[dst + x + 3] = 255;
      }
    }
    return { framebuffer: out, width: gw, height: gh };
  };
}

const hasContent = (buf) => {
  for (let p = 0; p + 2 < buf.length; p += 4 * 64) {
    if (buf[p] > 8 || buf[p + 1] > 8 || buf[p + 2] > 8) return true;
  }
  return false;
};

let buttons = 0;
let last = null;
for (let f = 0; f < opt.frames; f++) {
  if (timeline.has(f)) buttons = timeline.get(f);
  last = host.runFrame([{ connected: true, buttons }]);
  if (glReadback) {
    const gf = glReadback();
    if (hasContent(gf.framebuffer)) last = { ...last, ...gf };
  }
  if (shots.has(f) && last) {
    const png = encodePng(last.framebuffer, last.width, last.height);
    writeFileSync(shots.get(f), png);
    console.log(`frame ${f}: wrote ${shots.get(f)}`);
  }
}
console.log(`ran ${opt.frames} frames  ${last?.width}x${last?.height}`);
