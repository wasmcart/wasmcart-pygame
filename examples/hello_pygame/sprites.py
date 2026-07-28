"""
sprites.py — Demonstrates loading sprites from .wasc assets

This module is imported by main.py to show that relative imports
work through the wasc import hook.
"""

import pygame


def draw_info(screen, x, y, ball_dx, ball_dy):
    """Draw debug info text"""
    font = pygame.font.Font(None, 24)
    info = f"pos: ({int(x)}, {int(y)})  vel: ({ball_dx:.1f}, {ball_dy:.1f})"
    text = font.render(info, True, (180, 180, 180))
    screen.blit(text, (10, 460))
