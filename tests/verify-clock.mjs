#!/usr/bin/env node
// Verifies that game time follows the host's frame clock (wc_time):
// pygame.time.get_ticks(), Clock.tick()/get_time(), time.monotonic(),
// time.perf_counter() and time.time() all read the same clock, and that
// clock is the host's.
//
// Runs tests/clock (a probe cart) through wasmcart's public CartHost API:
//   1. deterministic, stepMs 16.667 (seed 7), twice: constant step, the two
//      runs bit-identical, the 1200 ms splash hands off at 1200 ms.
//   2. deterministic, stepMs 8.333 (a 120 Hz host): half the step, and the
//      splash still hands off at 1200 ms of game time (twice the frames).
//   3. real clock, 40 ms between frames: tick() reports the real gap and the
//      splash hands off after ~1200 ms of real time.
// Runs 1 and 3 are each the other's control: a constant cannot pass 3 and a
// wall clock cannot pass 1. The 0.2.x engine (one fixed 16.667 ms step per
// frame) fails runs 2 and 3:
//
//   node tests/verify-clock.mjs                 # engine: out/cart.wasm
//   node tests/verify-clock.mjs old/cart.wasm   # control: must FAIL
import { existsSync, mkdirSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '..');
const WASMCART_REPO = resolve(process.env.WASMCART_REPO || join(REPO, '..', 'wasmcart'));
if (!existsSync(join(WASMCART_REPO, 'src', 'CartHost.js'))) {
  console.error(`wasmcart checkout not found at ${WASMCART_REPO} (set WASMCART_REPO)`);
  process.exit(2);
}
const { CartHost } = await import(join(WASMCART_REPO, 'src', 'CartHost.js'));

const enginePath = resolve(process.argv[2] || join(REPO, 'out', 'cart.wasm'));
if (!existsSync(enginePath)) {
  console.error(`engine wasm not found: ${enginePath} (run build_full.sh)`);
  process.exit(2);
}

// Packed under out/ (gitignored), never /tmp.
const work = join(REPO, 'out', 'verify-clock');
mkdirSync(work, { recursive: true });
const cartPath = join(work, 'clock.wasc');
execFileSync('bash', [join(REPO, 'pack_game.sh'), join(HERE, 'clock'), cartPath, 'clock-verify'], {
  stdio: 'ignore',
  env: { ...process.env, CART_WASM: enginePath, CART_VERSION: '0.0.0' },
});

const pads = [{ connected: true, buttons: 0 }];
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

function parse(lines) {
  const frames = [];
  let handoff = null;
  for (const { text } of lines) {
    const f = text.split(' ');
    if (f[0] === 'CLK') {
      frames.push({
        n: +f[1], ticks: +f[2], tick: +f[3], getTime: +f[4], mono: +f[5],
        perf: +f[6], wall: +f[7], hostT: +f[8], hostDt: +f[9], state: f[10], raw: text,
      });
    } else if (f[0] === 'HANDOFF') {
      handoff = { n: +f[1], ticks: +f[2] };
    }
  }
  return { frames, handoff };
}

async function run(options, count, gapMs) {
  const quietError = console.error;
  console.error = () => {};
  const lines = [];
  try {
    const cart = new CartHost();
    await cart.load(cartPath, options);
    cart.drainDebugEvents();
    for (let i = 0; i < count; i++) {
      if (gapMs) await wait(gapMs);
      cart.runFrame(pads);
      lines.push(...cart.drainDebugEvents().log);
    }
    cart.dispose?.();
  } finally {
    console.error = quietError;
  }
  return parse(lines);
}

const fails = [];
const check = (ok, msg) => { console.log(`${ok ? 'ok  ' : 'FAIL'} ${msg}`); if (!ok) fails.push(msg); };
const deltas = (xs, key) => xs.slice(1).map((s, i) => s[key] - xs[i][key]);
const near = (a, b, eps) => Math.abs(a - b) <= eps;
const show = (xs) => xs.slice(0, 8).map((x) => +x.toFixed(3)).join(' ');

function checkConsistent(r, label) {
  // Every clock a game can read agrees with get_ticks within a millisecond
  // (get_ticks is the integer floor of the same value).
  check(r.frames.length > 0 && r.frames.every((s) =>
    near(s.mono, s.perf, 1e-6) && s.mono >= s.ticks && s.mono - s.ticks < 1 &&
    near(s.mono, s.hostT, 1e-6)),
    `${label}: get_ticks, monotonic, perf_counter and wc_time.time_ms are one clock`);
  const wallVsMono = deltas(r.frames, 'wall').map((d, i) => d - deltas(r.frames, 'mono')[i]);
  check(wallVsMono.every((d) => Math.abs(d) < 0.01),
    `${label}: time.time() advances with game time`);
  check(r.frames.slice(1).every((s) => s.tick === s.getTime),
    `${label}: Clock.get_time() equals Clock.tick()'s return`);
}

// 1. deterministic 16.667 ms, twice
const STEP = 1000 / 60;
const d1 = await run({ deterministic: { seed: 7 } }, 100, 0);
const d1b = await run({ deterministic: { seed: 7 } }, 100, 0);
console.log('--- deterministic, stepMs 16.667 (seed 7) ---');
console.log('monotonic deltas', show(deltas(d1.frames, 'mono')));
console.log('tick()          ', show(d1.frames.slice(1).map((s) => s.tick)));
check(d1.frames.length === 100, `cart logged every frame (${d1.frames.length}/100)`);
check(deltas(d1.frames, 'mono').every((d) => near(d, STEP, 1e-6)),
  'monotonic advances exactly 16.667 ms per frame');
check(d1.frames.slice(1).every((s) => s.tick === 16 || s.tick === 17),
  'Clock.tick() returns 16 or 17 every frame');
checkConsistent(d1, 'seeded');
// time.time() carries a wall-clock origin (field 7); every other field must
// match exactly.
const strip = (r) => r.frames.map((s) => s.raw.split(' ').filter((_, i) => i !== 7).join(' '));
check(JSON.stringify(strip(d1)) === JSON.stringify(strip(d1b)),
  'two seeded runs are bit-identical (every field except the calendar origin)');
check(d1.handoff && near(d1.handoff.ticks, 1200, 17) && d1.handoff.n === Math.ceil(1200 / STEP),
  `splash hands off at 1200 ms game time (frame ${d1.handoff?.n}, ticks ${d1.handoff?.ticks})`);

// 2. deterministic 8.333 ms: a 120 Hz host
const STEP2 = 1000 / 120;
const d2 = await run({ deterministic: { seed: 7, stepMs: STEP2 } }, 200, 0);
console.log('--- deterministic, stepMs 8.333 (120 Hz) ---');
console.log('monotonic deltas', show(deltas(d2.frames, 'mono')));
console.log('tick()          ', show(d2.frames.slice(1).map((s) => s.tick)));
check(deltas(d2.frames, 'mono').every((d) => near(d, STEP2, 1e-6)),
  'monotonic advances exactly 8.333 ms per frame');
check(d2.frames.slice(1).every((s) => s.tick === 8 || s.tick === 9),
  'Clock.tick() returns 8 or 9 every frame');
checkConsistent(d2, 'seeded 120 Hz');
check(d2.handoff && near(d2.handoff.ticks, 1200, 9) && d2.handoff.n === Math.ceil(1200 / STEP2),
  `splash hands off at 1200 ms game time, twice the frames (frame ${d2.handoff?.n}, ticks ${d2.handoff?.ticks})`);

// 3. real clock, 40 ms between frames
const real = await run({}, 45, 40);
console.log('--- real clock, 40 ms between frames ---');
console.log('monotonic deltas', show(deltas(real.frames, 'mono')));
console.log('tick()          ', show(real.frames.slice(1).map((s) => s.tick)));
const later = real.frames.slice(2);
check(later.every((s) => s.tick >= 35 && s.tick <= 250),
  'Clock.tick() reports the real gap (35..250 ms; the host clamp is 250)');
check(deltas(real.frames.slice(1), 'mono').every((d) => d >= 35 && d <= 250),
  'monotonic deltas report the real gap');
checkConsistent(real, 'real');
check(real.handoff && real.handoff.ticks >= 1200 && real.handoff.n >= 20 && real.handoff.n <= 34,
  `splash hands off after ~1200 ms of real time (frame ${real.handoff?.n}, ticks ${real.handoff?.ticks})`);
check(Math.abs(later[later.length - 1].tick - d1.frames[40].tick) > 10,
  'real and seeded clocks disagree, so the value is the host clock and not a constant');

rmSync(work, { recursive: true, force: true });
console.log(fails.length ? `\n${fails.length} FAILED` : '\nall clock checks passed');
process.exit(fails.length ? 1 : 0);
