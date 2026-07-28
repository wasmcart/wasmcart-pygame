import pygame
import sys
import time

from core import Input

class Base(object):

    def __init__(self):
        pygame.init()
        self.screenSize = (640, 640)
        self.clock = pygame.time.Clock()
        self.deltaTime = 0
        self.input = Input()
        self.running = True
        self._initialized = False

    def setWindowTitle(self, text):
        pass  # wasmcart host handles title

    def setWindowSize(self, width, height):
        self.screenSize = (width, height)

    def initialize(self):
        pass

    def update(self):
        pass

    def run(self):
        """Not used in wasmcart — use _wc_frame instead"""
        self.initialize()
        while self.running:
            self.input.update()
            if self.input.quit():
                self.running = False
            self.deltaTime = self.clock.get_time() / 1000.0
            self.update()
            pygame.display.flip()
            self.clock.tick(60)
        pygame.quit()

    def _wc_tick(self):
        """Called each frame by wasmcart"""
        if not self._initialized:
            self.initialize()
            self._initialized = True

        self.input.update()
        if self.input.quit():
            self.running = False
            return

        self.deltaTime = 1.0 / 60.0
        self.update()
