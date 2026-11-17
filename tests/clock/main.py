"""Clock probe for tests/verify-clock.mjs.

Logs one line per frame with every clock a game can read, so the test can
check they agree with each other and with the host's wc_time:

  CLK <n> <get_ticks> <tick> <get_time> <monotonic_ms> <perf_ms> <time_ms>
      <host_time_ms> <host_delta_ms> <state>

and a SolarWolf-style timed handoff: the 'splash' state waits 1200 ms of
game time (get_ticks), then hands off to 'menu', logged once as HANDOFF.
A red square moves 120 px per second, scaled by Clock.tick's return value.
"""
import time

import _wasmcart
import pygame

pygame.init()
screen = pygame.display.set_mode((320, 240))
clock = pygame.time.Clock()

SPLASH_MS = 1200
SPEED_PX_PER_S = 120.0

n = 0
state = 'splash'
start = pygame.time.get_ticks()
x = 0.0


def _wc_frame():
    global n, state, x
    for _event in pygame.event.get():
        pass
    dt = clock.tick(60)
    now = pygame.time.get_ticks()
    if state == 'splash' and now - start >= SPLASH_MS:
        state = 'menu'
        _wasmcart.log(f'HANDOFF {n} {now}')
    x += SPEED_PX_PER_S * dt / 1000.0
    host_t, host_dt, _frame = _wasmcart.get_time()
    _wasmcart.log(
        f'CLK {n} {now} {dt} {clock.get_time()} '
        f'{time.monotonic() * 1000:.6f} {time.perf_counter() * 1000:.6f} '
        f'{time.time() * 1000:.3f} {host_t:.6f} {host_dt:.6f} {state}')
    screen.fill((0, 0, 40) if state == 'splash' else (0, 40, 0))
    pygame.draw.rect(screen, (230, 40, 40), (int(x) % 320, 100, 16, 16))
    pygame.display.flip()
    n += 1
