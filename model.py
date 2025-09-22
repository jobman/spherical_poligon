import trimesh
import numpy as np
from OpenGL.GL import *
import pygame

class Model:
    def __init__(self, file_path):
        self.vbo_verts = None
        self.vbo_normals = None
        self.vbo_texcoords = None
        self.ebo_indices = None
        self.texture_id = None
        self.index_count = 0

        self._load_and_prepare_model(file_path)

    def _load_and_prepare_model(self, file_path):
        # Use trimesh to load the model. It can handle various formats including GLB.
        # We force it to return a scene, which we can then process.
        scene = trimesh.load(file_path, force='scene')

        # Combine all meshes in the scene into a single mesh object.
        # This simplifies rendering as we only have to deal with one set of buffers.
        if len(scene.geometry) > 1:
            mesh = trimesh.util.concatenate(scene.geometry.values())
        else:
            mesh = next(iter(scene.geometry.values()))

        # --- Extract data from Trimesh ---
        vertices = np.array(mesh.vertices, dtype=np.float32)
        faces = np.array(mesh.faces, dtype=np.uint32)
        normals = np.array(mesh.vertex_normals, dtype=np.float32)
        
        # Store index count for drawing
        self.index_count = len(faces.flatten())

        # --- Prepare OpenGL Buffers ---
        # Vertex Buffer Object (VBO) for positions
        self.vbo_verts = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo_verts)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

        # VBO for normals
        self.vbo_normals = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo_normals)
        glBufferData(GL_ARRAY_BUFFER, normals.nbytes, normals, GL_STATIC_DRAW)

        # Element Buffer Object (EBO) for indices
        self.ebo_indices = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo_indices)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, faces.nbytes, faces, GL_STATIC_DRAW)

        # --- Handle Textures ---
        if hasattr(mesh.visual, 'material') and hasattr(mesh.visual.material, 'image'):
            uv = np.array(mesh.visual.uv, dtype=np.float32)
            
            # VBO for texture coordinates
            self.vbo_texcoords = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo_texcoords)
            glBufferData(GL_ARRAY_BUFFER, uv.nbytes, uv, GL_STATIC_DRAW)

            # Load texture image using Pygame
            image = mesh.visual.material.image
            
            # Convert PIL image from trimesh to a format Pygame can use
            mode = image.mode
            size = image.size
            data = image.tobytes()

            py_image = pygame.image.fromstring(data, size, mode)
            
            # Flip the image vertically because OpenGL's texture coordinates are flipped
            # compared to most image formats.
            py_image = pygame.transform.flip(py_image, False, True)

            texture_data = pygame.image.tostring(py_image, "RGBA", 1)
            width, height = py_image.get_size()

            # Create OpenGL texture
            self.texture_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self.texture_id)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
            gluBuild2DMipmaps(GL_TEXTURE_2D, GL_RGBA, width, height, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)

    def draw(self):
        # Enable client states for arrays
        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_NORMAL_ARRAY)

        # Bind vertex buffer
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo_verts)
        glVertexPointer(3, GL_FLOAT, 0, None)

        # Bind normal buffer
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo_normals)
        glNormalPointer(GL_FLOAT, 0, None)

        # Handle texture if it exists
        if self.vbo_texcoords and self.texture_id:
            glEnableClientState(GL_TEXTURE_COORD_ARRAY)
            glEnable(GL_TEXTURE_2D)
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo_texcoords)
            glTexCoordPointer(2, GL_FLOAT, 0, None)
            glBindTexture(GL_TEXTURE_2D, self.texture_id)

        # Bind element buffer and draw
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo_indices)
        glDrawElements(GL_TRIANGLES, self.index_count, GL_UNSIGNED_INT, None)

        # Disable client states and texture
        glDisableClientState(GL_VERTEX_ARRAY)
        glDisableClientState(GL_NORMAL_ARRAY)
        
        if self.vbo_texcoords and self.texture_id:
            glDisableClientState(GL_TEXTURE_COORD_ARRAY)
            glDisable(GL_TEXTURE_2D)