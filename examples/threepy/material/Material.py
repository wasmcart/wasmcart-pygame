from OpenGL.GL import *
from core import OpenGLUtils, Uniform

class Material(object):

    def __init__(self, vertexShaderCode, fragmentShaderCode, uniforms=None, name="Material"):

        self.shaderProgramID = OpenGLUtils.initializeShaderFromCode(vertexShaderCode, fragmentShaderCode)
        self.name = name

        # DEBUG
        # print("Initializing Shader Program #", self.shaderProgramID, "for material:", self.name)

        # TODO: use the UniformList class here. This will require rethinking how textureNumber is set.
        self.uniformList = {}

        if uniforms is not None:
            for uniform in uniforms:
                self.setUniform(uniform[0], uniform[1], uniform[2])
        
        # render settings

        # options: GL_POINTS, GL_LINE_STRIP, GL_LINE_LOOP, GL_TRIANGLES
        self.drawStyle = GL_TRIANGLES
        
        # customize draw style GL_POINTS
        self.pointSize = 8
        
        # customize draw style GL_LINE_*
        self.lineWidth = 4
        
        # customize draw style GL_TRIANGLES
        # GL_FILL (0x1B02) not in GLES3 as a constant but used for tracking
        self.fillStyle  = 0x1B02
        # which sides of triangles should be rendered?
        self.renderFront = True
        self.renderBack  = True
        
        self.additiveBlending = False
        
        self.linearFiltering = True
            
    # type:  float, vec2, vec3, vec4, bool(0 or 1), sampler2D, mat4
    # name:  name of attribute variable in shader
    # value: array of values
    def setUniform(self, type, name, value):
        self.uniformList[name] = Uniform(type, name, value)


    def updateRenderSettings(self):
        # glPointSize not in GLES3 (set via gl_PointSize in vertex shader)
        try: glPointSize(self.pointSize)
        except: pass
        glLineWidth(self.lineWidth)
        
        # enable meshes to cull front or back faces
        if self.renderFront and self.renderBack:
            glDisable(GL_CULL_FACE)
        else:
            glEnable(GL_CULL_FACE)
            if not self.renderFront:
                glCullFace(GL_FRONT)
            if not self.renderBack:
                glCullFace(GL_BACK)
        
        # glPolygonMode not in GLES3 — triangles always filled
        pass
        
        # use additive blending or normal blending (default)
        if self.additiveBlending:
            # additive
            glBlendFunc(GL_ONE, GL_ONE)
        else: 
            # normal blending
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            
        # for textures, use linear filtering (default) or nearest filtering (pixelize)
        if self.linearFiltering:
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        else:
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            
