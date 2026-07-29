/*
 * test_rumble.mjs - end-to-end check that pygame's rumble API reaches the host
 *
 * wasmcart-play is the normal way to run a cart, but it wires no rumble
 * handler, so wc_pad_has_rumble answers 0 there and every rumble() call
 * correctly returns False. That is the honest answer for a headless run and it
 * proves nothing about the wiring. This drives CartHost directly with a
 * handler attached, so the calls have somewhere to land and can be counted.
 *
 * The control matters as much as the test: run 2 attaches NO handler, and its
 * expectation is that the same cart reports no rumble and rumbles zero times.
 * If both runs looked identical the harness would be measuring nothing.
 *
 * Usage: node tools/test_rumble.mjs [path/to/rumble.wasc]
 */

import { CartHost } from '../../wasmcart/src/CartHost.js';
import { BUTTON } from '../../wasmcart/src/abi.js';

const cart = process.argv[2] || new URL('../out/rumble.wasc', import.meta.url).pathname;

/* Long enough for an effect to expire.
 *
 * Rumble durations are wall-clock: SDL expires an effect by comparing
 * SDL_GetTicks() against the deadline it recorded. A headless run has no frame
 * pacing, so ~90 frames pass in tens of milliseconds and a 200ms effect would
 * still be running when the run ends -- the stop would never be observed, and
 * the test would be asserting on a window it never reached. The frame count
 * here covers the longest effect the example fires (600ms) with room to spare. */
const FRAMES = 2000;

// The example fires on the A button's rising edge, so the pad has to release
// between presses or only the first frame counts.
function padsForFrame(frame, withPad) {
  if (!withPad) return [{ connected: false }];
  const pressA = frame >= 30 && frame < 33;
  const pressB = frame >= 50 && frame < 53;
  let buttons = 0;
  if (pressA) buttons |= BUTTON.A;
  if (pressB) buttons |= BUTTON.B;
  return [{ connected: true, name: 'Test Pad', buttons }];
}

async function run({ label, handler }) {
  const host = new CartHost();
  const calls = [];
  const logs = [];

  await host.load(cart);
  if (handler) {
    host.setRumbleHandler({
      hasRumble: () => true,
      rumble: (pad, low, high, ms) => calls.push({ pad, low, high, ms }),
      stopRumble: (pad) => calls.push({ pad, stop: true }),
    });
  }

  for (let f = 0; f < FRAMES; f++) {
    host.runFrame(padsForFrame(f, true));
    for (const e of host.debugLog.splice(0)) logs.push(e.text ?? e.message ?? String(e));
  }

  return { label, calls, logs };
}

const withHandler = await run({ label: 'rumble handler attached', handler: true });
const noHandler = await run({ label: 'CONTROL: no rumble handler', handler: false });

let failed = false;
function check(cond, msg) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${msg}`);
  if (!cond) failed = true;
}

console.log(`\n--- ${withHandler.label} ---`);
console.log(`rumble calls: ${withHandler.calls.length}`);
for (const c of withHandler.calls.slice(0, 8)) console.log('  ', JSON.stringify(c));

console.log(`\n--- ${noHandler.label} ---`);
console.log(`rumble calls: ${noHandler.calls.length}`);

console.log('');
check(withHandler.calls.length > 0,
  'pygame Joystick.rumble() reached the host through wc_pad_rumble');
check(withHandler.calls.some(c => c.low > 0.9 && c.high === 0),
  'A button produced a strong-motor-only effect (low=1.0, high=0.0)');
check(withHandler.calls.some(c => c.high > 0.5 && c.low === 0),
  'B button produced a weak-motor-only effect (low=0.0, high>0.5)');
check(withHandler.calls.every(c => c.stop || (c.low <= 1 && c.high <= 1 && c.ms > 0)),
  'every effect stayed within the ABI range (0..1 intensity, positive duration)');
check(noHandler.calls.length === 0,
  'CONTROL: with no handler wired, nothing is delivered (harness can distinguish)');
// SDL owns effect expiry: the driver arms the host for a fixed window and SDL
// calls Rumble(0,0) once the game's duration elapses, which the driver turns
// into wc_pad_rumble_stop. Without that, a short effect would run for the
// arming window instead of the duration the game asked for.
check(withHandler.calls.some(c => c.stop),
  'effect expiry reached the host as wc_pad_rumble_stop');
// The example lights its result indicator from rumble()'s return value, so the
// two runs must disagree. Identical logs would mean the cart never noticed the
// difference and the panel is decorative.
check(withHandler.logs.some(l => /-> True/.test(l)),
  'the cart saw rumble() succeed and can show it');
check(noHandler.logs.some(l => /-> False/.test(l)),
  'CONTROL: the same cart saw rumble() refused and can show that instead');

process.exit(failed ? 1 : 0);
