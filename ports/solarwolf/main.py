"""wasmcart entry point for SolarWolf.

Upstream SolarWolf's main.py owns a `while game.handler:` loop. A wasmcart
cart cannot own the loop -- the host calls `_wc_frame()` once per frame and
expects the cart to return. So this module is the loop inversion: the setup
half of upstream `gamemain()` runs at import time, and the body of the while
loop becomes `_wc_frame()`.

Everything this module drives is upstream SolarWolf. The game's own modules
(game, gfx, snd, txt, input, and the 30-odd handlers) are byte-identical to
the upstream repo.

SolarWolf is Copyright (C) Pete Shinners and contributors, LGPL. See
lgpl.txt.
"""

import pygame

# Upstream's cli.py chdir()s into the data directory and inserts the code
# directory on sys.path before importing anything. A cart's assets are already
# the root of the (virtual) filesystem and the import hook resolves bare
# module names against assets/, which is exactly what the game modules'
# `import game` style needs.
import game
import gfx
import snd
import txt
import input
import allmodules
import players
import gamepref


SIZE = 800, 600

_started = False
_lasthandler = None
_star_timer_ms = 0


def _setup():
    """Upstream gamemain()'s setup half, up to the `while game.handler:` line."""
    global _started

    pygame.init()
    game.clock = pygame.time.Clock()

    players.load_players()
    input.load_translations()
    gamepref.load_prefs()

    # Always windowed: a cart does not own the display mode, the host does.
    gfx.initialize(SIZE, 0)
    pygame.display.set_caption('SolarWolf')

    snd.initialize()
    input.init()

    if not txt.initialize():
        raise pygame.error("Pygame Font Module Unable to Initialize")

    from gameinit import GameInit
    from gamefinish import GameFinish
    game.handler = GameInit(GameFinish(None))

    _started = True


def _wc_frame():
    """One iteration of upstream's `while game.handler:` loop."""
    global _lasthandler, _star_timer_ms

    if not _started or not game.handler:
        # Upstream falls out of the loop and quits the process. A cart has
        # nowhere to exit to, so hold on the last frame instead.
        return

    handler = game.handler
    if handler is not _lasthandler:
        _lasthandler = handler
        if hasattr(handler, 'starting'):
            handler.starting()

    # Upstream drives star-count recalculation off a 1000 ms USEREVENT timer
    # (pygame.time.set_timer). SDL timers need a background thread to tick
    # them, which a single-threaded cart does not have, so the same cadence
    # is derived from the frame clock here.
    _star_timer_ms += game.clockticks
    if _star_timer_ms >= 1000:
        _star_timer_ms = 0
        gfx.starobj.recalc_num_stars(game.clock.get_fps())

    for event in pygame.event.get():
        if event.type == pygame.USEREVENT:
            gfx.starobj.recalc_num_stars(game.clock.get_fps())
            continue
        elif event.type == pygame.ACTIVEEVENT:
            continue
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            if event.mod & pygame.KMOD_ALT:
                # No fullscreen toggle in a cart: the host owns the window.
                continue
        inputevent = input.translate(event)
        if inputevent.normalized is not None:
            inputevent = input.exclusive(
                (input.UP, input.DOWN, input.LEFT, input.RIGHT), inputevent)
            handler.input(inputevent)
        elif event.type == pygame.QUIT:
            game.handler = None
            return
        handler.event(event)

    handler.run()
    game.clockticks = game.clock.tick(40)
    gfx.update()


_setup()
