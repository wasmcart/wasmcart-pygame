"""
three.py spinning cube — 3D engine running in wasmcart

Uses the three.py scene graph (Scene, Camera, Mesh, Material, Light)
with OpenGL calls going through wasmcart's GL ABI to the host GPU.
"""

import _wasmcart
# Signal to host: this is a GL cart, not 2D framebuffer
#

from core import *
from cameras import *
from geometry import *
from material import *
from lights import *
from mathutils import *

class SpinningCube(Base):

    def initialize(self):
        self.setWindowSize(640, 480)

        self.renderer = Renderer()
        self.renderer.setViewportSize(640, 480)
        self.renderer.setClearColor(0.1, 0.1, 0.2)

        self.scene = Scene()
        self.camera = PerspectiveCamera()
        self.camera.transform.setPosition(0, 1, 5)
        self.camera.transform.lookAt(0, 0, 0)

        # Spinning cube
        cubeGeo = BoxGeometry(1.5, 1.5, 1.5)
        cubeMat = SurfaceBasicMaterial(color=[0.2, 0.8, 0.3])
        self.cube = Mesh(cubeGeo, cubeMat)
        self.cube.transform.setPosition(0, 1, 0)
        self.scene.add(self.cube)

        # Second cube
        cube2Geo = BoxGeometry(0.8, 0.8, 0.8)
        cube2Mat = SurfaceBasicMaterial(color=[0.8, 0.2, 0.2])
        self.cube2 = Mesh(cube2Geo, cube2Mat)
        self.cube2.transform.setPosition(2.5, 0.5, 0)
        self.scene.add(self.cube2)

        # Third cube
        cube3Geo = BoxGeometry(0.6, 0.6, 0.6)
        cube3Mat = SurfaceBasicMaterial(color=[0.2, 0.4, 0.9])
        self.cube3 = Mesh(cube3Geo, cube3Mat)
        self.cube3.transform.setPosition(-2, 0.5, 1)
        self.scene.add(self.cube3)

        self.angle = 0
        print("three.py initialized!")

    def update(self):
        self.angle += 0.02

        self.cube.transform.rotateY(0.01, Matrix.LOCAL)
        self.cube.transform.rotateX(0.007, Matrix.LOCAL)

        self.cube2.transform.rotateY(-0.02, Matrix.LOCAL)
        self.cube2.transform.rotateZ(0.01, Matrix.LOCAL)

        self.cube3.transform.rotateX(0.015, Matrix.LOCAL)
        self.cube3.transform.rotateZ(-0.01, Matrix.LOCAL)

        self.renderer.render(self.scene, self.camera)


# Create game instance
game = SpinningCube()

def _wc_frame():
    game._wc_tick()
