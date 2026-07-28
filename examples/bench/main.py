import pygame
import random
from os import path

img_dir = path.join(path.dirname(__file__), 'assets')

WIDTH, HEIGHT = 480, 600
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)

pygame.init()
pygame.mixer.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))

background = pygame.image.load(path.join(img_dir, 'starfield.png')).convert()
background_rect = background.get_rect()
player_img = pygame.image.load(path.join(img_dir, 'playerShip1_orange.png')).convert()
player_img = pygame.transform.scale(player_img, (50, 38))
player_img.set_colorkey(BLACK)

meteor_images = []
for name in ['meteorBrown_big1.png', 'meteorBrown_med1.png', 'meteorBrown_small1.png']:
    img = pygame.image.load(path.join(img_dir, name)).convert()
    img.set_colorkey(BLACK)
    meteor_images.append(img)

class Mob(pygame.sprite.Sprite):
    def __init__(self):
        pygame.sprite.Sprite.__init__(self)
        self.image_orig = random.choice(meteor_images)
        self.image = self.image_orig.copy()
        self.rect = self.image.get_rect()
        self.radius = int(self.rect.width * .90 / 2)
        self.rect.x = random.randrange(0, WIDTH - self.rect.width)
        self.rect.y = random.randrange(-150, -100)
        self.speedy = random.randrange(5, 20)
        self.speedx = random.randrange(-3, 3)
        self.rotation = 0
        self.rotation_speed = random.randrange(-8, 8)
        self.last_update = pygame.time.get_ticks()
    def rotate(self):
        now = pygame.time.get_ticks()
        if now - self.last_update > 50:
            self.last_update = now
            self.rotation = (self.rotation + self.rotation_speed) % 360
            new_image = pygame.transform.rotate(self.image_orig, self.rotation)
            old_center = self.rect.center
            self.image = new_image
            self.rect = self.image.get_rect()
            self.rect.center = old_center
    def update(self):
        self.rotate()
        self.rect.x += self.speedx
        self.rect.y += self.speedy
        if self.rect.top > HEIGHT + 10 or self.rect.left < -25 or self.rect.right > WIDTH + 20:
            self.rect.x = random.randrange(0, WIDTH - self.rect.width)
            self.rect.y = random.randrange(-100, -40)
            self.speedy = random.randrange(1, 8)

all_sprites = pygame.sprite.Group()
mobs = pygame.sprite.Group()
for i in range(8):
    m = Mob()
    all_sprites.add(m)
    mobs.add(m)

player_rect = player_img.get_rect()
player_rect.centerx = WIDTH / 2
player_rect.bottom = HEIGHT - 10

frame_count = 0
start_time = None

def _wc_frame():
    global frame_count, start_time
    if start_time is None:
        start_time = pygame.time.get_ticks()

    for event in pygame.event.get():
        pass

    all_sprites.update()
    screen.fill(BLACK)
    screen.blit(background, background_rect)
    all_sprites.draw(screen)
    screen.blit(player_img, player_rect)
    pygame.draw.rect(screen, GREEN, (5, 5, 100, 10))
    pygame.draw.rect(screen, WHITE, (5, 5, 100, 10), 2)
    pygame.display.flip()

    frame_count += 1
    elapsed = (pygame.time.get_ticks() - start_time) / 1000.0
    if elapsed >= 5.0 and frame_count % 300 == 0:
        fps = frame_count / elapsed
        print(f"WASMCART: {frame_count} frames in {elapsed:.2f}s = {fps:.1f} FPS")
