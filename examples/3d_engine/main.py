import _wasmcart
#

import pygame as pg
import moderngl as mgl
import sys
from model import *
from camera import Camera
from light import Light
from mesh import Mesh
from scene import Scene
from scene_renderer import SceneRenderer


class GraphicsEngine:
    def __init__(self, win_size=(800, 600)):
        pg.init()
        self.WIN_SIZE = win_size
        # Need a display surface for pygame.image.load().convert()
        pg.display.set_mode(self.WIN_SIZE)
        self.ctx = mgl.create_context()
        self.ctx.enable(flags=mgl.DEPTH_TEST | mgl.CULL_FACE)
        self.clock = pg.time.Clock()
        self.time = 0
        self.delta_time = 0
        self.light = Light()
        self.camera = Camera(self)
        self.mesh = Mesh(self)
        self.scene = Scene(self)
        self.scene_renderer = SceneRenderer(self)
        print("3D Engine initialized!")

    def check_events(self):
        for event in pg.event.get():
            if event.type == pg.QUIT or (event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE):
                return

    def render(self):
        self.ctx.clear(color=(0.08, 0.16, 0.18))
        self.scene_renderer.render()

    def get_time(self):
        self.time = pg.time.get_ticks() * 0.001


app = GraphicsEngine()

def _wc_frame():
    app.get_time()
    app.check_events()
    app.camera.update()
    app.render()
    app.delta_time = 16
