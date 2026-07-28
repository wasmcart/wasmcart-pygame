# static methods to load and compile OpenGL shader programs
from OpenGL.GL import *

import pygame # for loading images / texture data

class OpenGLUtils(object):

    @staticmethod
    def _fixup_gles3(code, is_fragment):
        """Patch desktop GLSL for GLES3 / WebGL2 compatibility."""
        # texture2D → texture
        code = code.replace('texture2D(', 'texture(')
        # C-style array init → separate assignments
        import re
        # Fix: Light lightArray[4] = {light0, light1, light2, light3};
        code = re.sub(
            r'Light\s+lightArray\[4\]\s*=\s*\{(\w+),\s*(\w+),\s*(\w+),\s*(\w+)\};',
            r'Light lightArray[4];\nlightArray[0] = \1;\nlightArray[1] = \2;\nlightArray[2] = \3;\nlightArray[3] = \4;',
            code)
        if is_fragment:
            # Add fragColor output declaration after precision
            code = 'out vec4 fragColor;\n' + code
        return code

    @staticmethod
    def initializeShader(shaderCode, shaderType):

        is_fragment = (shaderType == GL_FRAGMENT_SHADER)
        shaderCode = OpenGLUtils._fixup_gles3(shaderCode, is_fragment)
        # GLES3 / WebGL2 compatible
        shaderCode = '#version 300 es\nprecision mediump float;\n' + shaderCode
        
        # create empty shader object and return reference value
        shaderID = glCreateShader(shaderType)
        # stores the source code in the shader
        glShaderSource(shaderID, shaderCode)
        # compiles source code previously stored in the shader object
        glCompileShader(shaderID)

        # queries whether shader compile was successful
        compileSuccess = glGetShaderiv(shaderID, GL_COMPILE_STATUS)
        if not compileSuccess:
            errorMessage = glGetShaderInfoLog(shaderID)
            glDeleteShader(shaderID)
            kind = "FRAG" if is_fragment else "VERT"
            print(f"[GL] shader {shaderID} compile FAILED:\n{errorMessage}\n\nFull source:\n{shaderCode[:500]}")
            # TODO: parse str(errorMessage) for better printing
            raise Exception(errorMessage)  
            
        # compilation was successful; return shader reference value
        return shaderID

    @staticmethod
    def initializeShaderFromCode(vertexShaderCode, fragmentShaderCode):
        
        vertexShaderID   = OpenGLUtils.initializeShader(vertexShaderCode,   GL_VERTEX_SHADER)
        fragmentShaderID = OpenGLUtils.initializeShader(fragmentShaderCode, GL_FRAGMENT_SHADER)
    
        programID = glCreateProgram()
        glAttachShader(programID, vertexShaderID)
        glAttachShader(programID, fragmentShaderID)
        glLinkProgram(programID)

        linkSuccess = glGetProgramiv(programID, GL_LINK_STATUS)
        if not linkSuccess:
            errorMessage = glGetProgramInfoLog(programID)
            print(f"[GL] program {programID} link FAILED:\n{errorMessage}")

        return programID

    """
    @staticmethod
    def initializeShaderFromFiles(vertexShaderFileName, fragmentShaderFileName):

        vertexShaderFile = open(vertexShaderFileName, mode='r')
        vertexShaderCode = vertexShaderFile.read()
        vertexShaderFile.close()

        fragmentShaderFile = open(fragmentShaderFileName, mode='r')
        fragmentShaderCode = fragmentShaderFile.read()
        fragmentShaderFile.close()
        
        return OpenGLUtils.initializeShaderFromCode(vertexShaderCode, fragmentShaderCode)
    """
    
    @staticmethod
    def initializeTexture(imageFileName):
        # load image from file
        surface = pygame.image.load(imageFileName)
        return OpenGLUtils.initializeSurface(surface)
        
    @staticmethod
    def initializeSurface(surface):
        # transfer image to string buffer
        textureData = pygame.image.tostring(surface, "RGBA", 1)
        width = surface.get_width()
        height = surface.get_height()
        # glEnable(GL_TEXTURE_2D)
        texid = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, texid)

        # send image data to texture buffer
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height,
                     0, GL_RGBA, GL_UNSIGNED_BYTE, textureData)
                     
        # generate a mipmap for use with 2d textures
        glGenerateMipmap(GL_TEXTURE_2D)
        
        # default: use smooth interpolated color sampling when textures magnified
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        # use the mip map filter rather than standard filter
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
        
        return texid

    @staticmethod
    def updateSurface(surface, textureID):
        textureData = pygame.image.tostring(surface, "RGBA", 1)
        width = surface.get_width()
        height = surface.get_height() 
        glBindTexture(GL_TEXTURE_2D, textureID)
        # send image data to texture buffer
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height,
                     0, GL_RGBA, GL_UNSIGNED_BYTE, textureData)
                     