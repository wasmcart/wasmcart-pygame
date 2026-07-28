"""
hello_pygame — pygame feature test for wasmcart

Tests: init, display, draw, fill, rect, circle, line, font, events, input
"""

import pygame

pygame.init()
screen = pygame.display.set_mode((640, 480))
pygame.display.set_caption("Hello wasmcart!")
clock = pygame.time.Clock()

print(f"pygame {pygame.get_sdl_version()} ready: {screen.get_size()}")

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 60, 60)
GREEN = (60, 200, 60)
BLUE = (60, 60, 255)
YELLOW = (255, 255, 60)

# Ball
ball_x, ball_y = 320.0, 240.0
ball_dx, ball_dy = 3.0, 2.0

# Test surfaces
test_surf = pygame.Surface((80, 80))
test_surf.fill(GREEN)
pygame.draw.circle(test_surf, YELLOW, (40, 40), 30)

frame_count = 0


def _wc_frame():
    global ball_x, ball_y, ball_dx, ball_dy, frame_count
    frame_count += 1

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            return

    # Input
    keys = pygame.key.get_pressed()
    if keys[pygame.K_LEFT]:
        ball_dx = -abs(ball_dx)
    if keys[pygame.K_RIGHT]:
        ball_dx = abs(ball_dx)
    if keys[pygame.K_UP]:
        ball_dy = -abs(ball_dy)
    if keys[pygame.K_DOWN]:
        ball_dy = abs(ball_dy)

    # Update
    ball_x += ball_dx
    ball_y += ball_dy
    if ball_x < 20 or ball_x > 620:
        ball_dx = -ball_dx
        ball_x += ball_dx
    if ball_y < 50 or ball_y > 430:
        ball_dy = -ball_dy
        ball_y += ball_dy

    # Draw
    screen.fill(BLACK)

    # Top bar
    pygame.draw.rect(screen, WHITE, (0, 0, 640, 40))

    # Title text (using default font)
    try:
        font = pygame.font.Font(None, 28)
        text = font.render("pygame on wasmcart", True, BLACK)
        screen.blit(text, (220, 8))
    except Exception as e:
        # Font might not work without TTF files
        pass

    # Bottom bar
    pygame.draw.rect(screen, BLUE, (0, 450, 640, 30))

    # Bouncing ball
    pygame.draw.circle(screen, RED, (int(ball_x), int(ball_y)), 20)

    # Lines
    pygame.draw.line(screen, GREEN, (10, 50), (10, 440), 2)
    pygame.draw.line(screen, GREEN, (630, 50), (630, 440), 2)

    # Blit test surface
    screen.blit(test_surf, (540, 50))

    # Rects
    pygame.draw.rect(screen, YELLOW, (20, 400, 100, 40), 2)

    pygame.display.flip()
