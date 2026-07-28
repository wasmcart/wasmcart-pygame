"""
hello_python — proof-of-concept: CPython running inside a wasmcart

Draws a bouncing ball using _wasmcart.fill_rect() directly.
No pygame — just proves CPython + .wasc asset loading works.
"""

import _wasmcart
import colors  # tests relative import from assets/colors.py

# Ball state
ball_x = 160.0
ball_y = 120.0
ball_dx = 2.0
ball_dy = 1.5
BALL_SIZE = 10

_wasmcart.log("hello_python main.py loaded!")


def _wc_frame():
    """Called once per frame by cart_shim."""
    global ball_x, ball_y, ball_dx, ball_dy

    # Get input
    pad = _wasmcart.get_pad(0)
    if pad:
        buttons, lx, ly, rx, ry, lt, rt, connected = pad
        # D-pad
        if buttons & 0x0400:  # LEFT
            ball_dx = -abs(ball_dx)
        if buttons & 0x0800:  # RIGHT
            ball_dx = abs(ball_dx)
        if buttons & 0x0100:  # UP
            ball_dy = -abs(ball_dy)
        if buttons & 0x0200:  # DOWN
            ball_dy = abs(ball_dy)

    # Update
    ball_x += ball_dx
    ball_y += ball_dy

    if ball_x < 0 or ball_x + BALL_SIZE > 320:
        ball_dx = -ball_dx
        ball_x += ball_dx
    if ball_y < 0 or ball_y + BALL_SIZE > 240:
        ball_dy = -ball_dy
        ball_y += ball_dy

    # Draw
    _wasmcart.clear(colors.BLUE)

    # Ball — big and bright
    _wasmcart.fill_rect(int(ball_x) - 20, int(ball_y) - 20, 40, 40, colors.RED)

    # White bar across the top
    _wasmcart.fill_rect(0, 0, 320, 20, colors.WHITE)

    # Green bar across the bottom
    _wasmcart.fill_rect(0, 220, 320, 20, colors.GREEN)
