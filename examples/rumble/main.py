"""
rumble - gamepad rumble on wasmcart, through the upstream pygame API

Press A or B to fire a rumble effect. A is a short strong pulse (low-frequency
motor), B is a longer light buzz (high-frequency motor). The screen shows what
the pad reports and what the last call returned.

The code below is ordinary pygame-ce. There is nothing wasmcart-specific in
the rumble path: pygame.joystick.Joystick.rumble() reaches SDL's joystick
driver, which on wasmcart is backed by the wc_pad_rumble host import.

Rumble capability is per-DEVICE, so this asks (get_rumble / the return value of
rumble()) rather than assuming. On a keyboard-only setup, or a headless run
with no pad wired up, rumble() returns False and the game says so instead of
pretending an effect played.
"""

import pygame

pygame.init()
pygame.joystick.init()

SCREEN_W, SCREEN_H = 640, 480
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("wasmcart rumble")
clock = pygame.time.Clock()

BLACK = (12, 14, 22)
WHITE = (240, 240, 245)
GREY = (120, 126, 140)
GREEN = (70, 210, 120)
RED = (235, 80, 80)
BLUE = (80, 150, 255)
AMBER = (250, 190, 70)


def _log(msg):
    """Mirror to the host debug log.

    A still screenshot cannot show that a rumble call happened at all, let
    alone what it returned, so the interesting moments go to the log where a
    headless run can assert on them."""
    try:
        import _wasmcart
        _wasmcart.log(msg)
    except Exception:
        print(msg)


class _NoFont:
    """Stand-in when no font can be loaded at all.

    Renders nothing, so a caller does not have to branch. Everything this
    example needs to communicate is ALSO drawn as shapes, because a screen made
    only of text goes completely blank when the font is missing -- which reads
    as a dead cart rather than a missing font."""

    def render(self, text, antialias, color):
        return pygame.Surface((0, 0), pygame.SRCALPHA)


def _load_font(size):
    """Load the default font, or report that there is none.

    Every form of this call currently raises "can't access resource on
    platform" in a packed cart, including an explicit path to the .ttf that IS
    in the archive. That is a pygame text problem, not a rumble one, and it
    affects the other examples here the same way -- so this reports it and
    carries on rather than failing. The status panel this example draws is
    shapes, so the screen stays readable with no font at all."""
    errs = []
    for path in ("stdlib/pygame/freesansbold.ttf", "freesansbold.ttf"):
        try:
            return pygame.font.Font(path, size)
        except Exception as e:
            errs.append(f"{path}: {type(e).__name__}: {e}")
    try:
        return pygame.font.Font(None, size)
    except Exception as e:
        errs.append(f"None: {type(e).__name__}: {e}")
    _log(f"rumble: font load failed: {errs}")
    return _NoFont()


font = _load_font(26)
big = _load_font(40)
have_font = not isinstance(font, _NoFont)
_log_font = f"rumble: font loaded={have_font}"

# Pads are opened per frame, not once at import.
#
# Import runs during wc_init, before the host has written a single frame of pad
# state, so joystick.get_count() is 0 there no matter what is plugged in. That
# is not a wasmcart quirk to work around: enumerating once at startup misses
# every pad connected later, and hot-plug is exactly what JOYDEVICEADDED is
# for. Re-scanning each frame is the same thing an upstream pygame game does,
# just written without an event loop.
pads = {}
open_errors = []


def sync_pads():
    """Open pads that have appeared, drop ones that have gone.

    get_count() is positional on wasmcart: pad slot 2 connected alone still
    reports a count of 3, with the empty slots failing to open. Skipping those
    keeps SDL device index and wasmcart pad id in agreement, which matters
    because rumble is keyed by pad id."""
    seen = set()
    for i in range(pygame.joystick.get_count()):
        seen.add(i)
        if i in pads:
            continue
        try:
            j = pygame.joystick.Joystick(i)
            j.init()
            pads[i] = j
        except pygame.error as e:
            msg = f"pad {i}: {e}"
            if msg not in open_errors:
                open_errors.append(msg)
    for gone in [i for i in pads if i not in seen]:
        del pads[gone]


def describe(joy):
    """Report what this pad says about itself, without assuming rumble."""
    try:
        name = joy.get_name()
    except Exception:
        name = "?"
    # get_rumble() is pygame-ce 2.5+; older builds only learn from rumble()'s
    # return value, so treat a missing method as "unknown" rather than "no".
    if hasattr(joy, "get_rumble"):
        try:
            has = "yes" if joy.get_rumble() else "no"
        except Exception:
            has = "?"
    else:
        has = "?"
    return name, has


last_result = None
last_action = "none"
frame = 0

# Edge-detect so holding the button fires one effect rather than sixty a
# second. A held button restarting the effect every frame would also mask the
# duration argument entirely, since the effect would never be allowed to end.
prev_pressed = {}


# The effect currently believed to be running, for the meters. Tracked here
# rather than read back from pygame because there is no API to ask a joystick
# what it is playing; this mirrors what was asked for, and only while rumble()
# said yes.
active_until = 0
active_span = 1
active_level = (0.0, 0.0)

# Whether the one-shot startup effect has already run.
demoed = False


def fire(joy, low, high, duration, label):
    global last_result, last_action, active_until, active_span, active_level
    last_action = label
    try:
        last_result = joy.rumble(low, high, duration)
    except Exception as e:
        last_result = f"error: {e}"
    if last_result is True:
        active_until = pygame.time.get_ticks() + duration
        active_span = duration
        active_level = (low, high)
    _log(f"rumble: {label} -> {last_result}")


def draw_status_panel():
    """Draw the whole state of the demo without using a single glyph.

    Four pad lamps, one live-motor meter per motor, a result light, and a
    heartbeat. Between them these answer the questions the text would: is a pad
    open, did the last rumble call succeed, is an effect running right now, and
    is the loop still alive."""
    dim = (40, 44, 56)

    # Pad lamps. Green = opened. Red = the host reports the slot connected but
    # opening it failed, which is a real problem worth seeing. Dim = empty.
    lamp_y = 150
    for slot in range(4):
        x = 60 + slot * 70
        if slot in pads:
            colour = GREEN
        elif slot < pygame.joystick.get_count():
            colour = RED
        else:
            colour = dim
        pygame.draw.circle(screen, colour, (x, lamp_y), 22)
        pygame.draw.circle(screen, GREY, (x, lamp_y), 22, 2)

    # Motor meters. These track the effect that is actually running rather than
    # the last call, so a 600ms buzz visibly drains over its duration and a
    # refused call never fills them at all.
    now = pygame.time.get_ticks()
    for i, (label_y, motor) in enumerate(((250, 'low'), (300, 'high'))):
        pygame.draw.rect(screen, dim, (60, label_y, 400, 32))
        remaining = 0.0
        level = 0.0
        if active_until > now and active_level[i] > 0:
            remaining = (active_until - now) / max(active_span, 1)
            level = active_level[i]
        w = int(400 * level * min(remaining, 1.0))
        if w > 0:
            pygame.draw.rect(screen, BLUE if motor == 'low' else AMBER,
                             (60, label_y, w, 32))
        pygame.draw.rect(screen, GREY, (60, label_y, 400, 32), 2)

    # Result light for the most recent rumble() return value.
    if last_result is True:
        col = GREEN
    elif last_result is False:
        col = RED
    elif last_result is None:
        col = dim
    else:
        col = AMBER
    pygame.draw.rect(screen, col, (500, 250, 82, 82))
    pygame.draw.rect(screen, GREY, (500, 250, 82, 82), 2)

    # Heartbeat: a still screenshot cannot otherwise show the loop is running.
    pygame.draw.circle(screen, WHITE if (frame // 15) % 2 else dim,
                       (SCREEN_W - 48, SCREEN_H - 48), 10)


def _wc_frame():
    global frame, last_result, last_action
    frame += 1

    # event.get() drives SDL_JoystickUpdate, which is what refreshes button
    # state AND expires a finished rumble effect. Pump it before reading.
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            return

    if frame == 1:
        _log(_log_font)

    before = set(pads)
    sync_pads()
    if set(pads) != before:
        _log(f"rumble: pads now {sorted(pads)} "
             f"(get_count={pygame.joystick.get_count()}) errors={open_errors}")

    for idx, joy in sorted(pads.items()):
        try:
            a = joy.get_button(0)
            b = joy.get_button(1)
        except Exception:
            continue
        was_a, was_b = prev_pressed.get(idx, (0, 0))
        if a and not was_a:
            fire(joy, 1.0, 0.0, 200, f"pad {idx}: strong 200ms")
        elif b and not was_b:
            fire(joy, 0.0, 0.6, 600, f"pad {idx}: light 600ms")
        prev_pressed[idx] = (a, b)

    # Keyboard fallback so the example is exercisable without a pad attached.
    keys = pygame.key.get_pressed()
    if keys[pygame.K_SPACE] and 0 in pads:
        fire(pads[0], 0.8, 0.8, 250, "pad 0: both motors 250ms")

    # Fire once, unprompted, shortly after the first pad opens.
    #
    # A headless capture presses nothing, so without this every screenshot
    # shows the idle state and says nothing about whether rumble works. This
    # exercises the real path -- and on a pad without motors it correctly comes
    # back False and lights the result red, which is also worth seeing.
    global demoed
    if not demoed and 0 in pads and frame > 5:
        demoed = True
        fire(pads[0], 0.7, 0.4, 1500, "startup demo: both motors 1500ms")

    screen.fill(BLACK)

    title = big.render("wasmcart rumble", True, WHITE)
    screen.blit(title, (24, 24))

    sub = font.render(
        "pygame.joystick.Joystick.rumble(low, high, duration_ms)", True, GREY)
    screen.blit(sub, (24, 72))

    y = 120
    count_col = GREEN if pads else AMBER
    screen.blit(font.render(
        f"joystick.get_count(): {pygame.joystick.get_count()}   opened: {len(pads)}",
        True, count_col), (24, y))
    y += 34

    if not pads:
        screen.blit(font.render(
            "No pad opened. Rumble needs a connected pad.", True, AMBER),
            (24, y))
        y += 30
        screen.blit(font.render(
            "The joystick subsystem is up either way (no SDL error).",
            True, GREY), (24, y))
        y += 40
        if open_errors:
            for msg in open_errors[:3]:
                screen.blit(font.render(msg, True, RED), (24, y))
                y += 26
    else:
        for idx, joy in sorted(pads.items()):
            name, has = describe(joy)
            col = GREEN if has == "yes" else (AMBER if has == "?" else GREY)
            screen.blit(font.render(
                f"pad {idx}: {name}   rumble: {has}   "
                f"axes {joy.get_numaxes()} buttons {joy.get_numbuttons()} "
                f"hats {joy.get_numhats()}",
                True, col), (24, y))
            y += 30
        y += 10

    screen.blit(font.render(f"last call: {last_action}", True, WHITE), (24, y))
    y += 30
    if last_result is True:
        screen.blit(font.render("returned: True (motors driven)", True, GREEN),
                    (24, y))
    elif last_result is False:
        screen.blit(font.render(
            "returned: False (pad reports no rumble)", True, RED), (24, y))
    elif last_result is None:
        screen.blit(font.render("returned: -", True, GREY), (24, y))
    else:
        screen.blit(font.render(f"returned: {last_result}", True, RED), (24, y))
    y += 50

    # Status panel drawn as shapes, not text.
    #
    # Everything above depends on a working font, and font loading currently
    # fails in a packed cart. Without this the whole screen would be an empty
    # border, which looks exactly like a cart that booted and died. These
    # indicators carry the same information and cannot go blank.
    draw_status_panel()

    screen.blit(font.render("A = strong pulse    B = light buzz    "
                            "SPACE = both motors", True, BLUE), (24, y))

    # A frame counter proves the loop is live even when nothing else moves,
    # which a still screenshot otherwise cannot show.
    screen.blit(font.render(f"frame {frame}", True, GREY), (SCREEN_W - 140, SCREEN_H - 40))

    pygame.draw.rect(screen, GREY, (16, 16, SCREEN_W - 32, SCREEN_H - 32), 2)

    pygame.display.flip()
