
import trimesh
from OpenGL.GL import *
from OpenGL.GLU import *
from PIL import Image
import numpy as np

def load_gl_texture(image):
    """Converts a PIL image to an OpenGL texture."""
    if image.mode != 'RGBA':
        image = image.convert('RGBA')

    img_data = image.tobytes("raw", "RGBA", 0, -1)
    
    texture_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    
    gluBuild2DMipmaps(GL_TEXTURE_2D, GL_RGBA, image.width, image.height, GL_RGBA, GL_UNSIGNED_BYTE, img_data)
    
    return texture_id

class Model:
    def __init__(self, file_path):
        self.mesh = None
        self.texture_id = None
        self.vbo_verts = None
        self.vbo_normals = None
        self.vbo_uvs = None
        self.ibo_faces = None
        self.face_count = 0

        self._load_model(file_path)

    def _load_model(self, file_path):
        try:
            # Use trimesh to load the scene. We use force='scene' to ensure we get a scene object.
            scene = trimesh.load(file_path, force='scene')
            # We'll take the first geometry from the scene. This is a simplification.
            # For complex scenes, you might need to iterate through scene.geometry.
            mesh_key = list(scene.geometry.keys())[0]
            self.mesh = scene.geometry[mesh_key]
        except Exception as e:
            print(f"Error loading model with trimesh: {e}")
            # As a fallback, try loading directly as a mesh
            try:
                self.mesh = trimesh.load(file_path, force='mesh')
            except Exception as e2:
                print(f"Secondary error loading as mesh: {e2}")
                return # Could not load the mesh

        # Prepare VBOs
        self.vbo_verts = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo_verts)
        glBufferData(GL_ARRAY_BUFFER, self.mesh.vertices.astype(np.float32).tobytes(), GL_STATIC_DRAW)

        self.vbo_normals = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo_normals)
        glBufferData(GL_ARRAY_BUFFER, self.mesh.vertex_normals.astype(np.float32).tobytes(), GL_STATIC_DRAW)

        if self.mesh.visual.uv is not None and len(self.mesh.visual.uv) > 0:
            self.vbo_uvs = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo_uvs)
            glBufferData(GL_ARRAY_BUFFER, self.mesh.visual.uv.astype(np.float32).tobytes(), GL_STATIC_DRAW)

        self.face_count = len(self.mesh.faces.flatten())
        self.ibo_faces = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ibo_faces)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, self.mesh.faces.flatten().astype(np.uint32).tobytes(), GL_STATIC_DRAW)


        # --- Load Texture ---
        try:
            image = None
            if hasattr(self.mesh.visual, 'material'):
                if hasattr(self.mesh.visual.material, 'baseColorTexture') and self.mesh.visual.material.baseColorTexture is not None:
                    image = self.mesh.visual.material.baseColorTexture
                elif hasattr(self.mesh.visual.material, 'image') and self.mesh.visual.material.image is not None:
                    image = self.mesh.visual.material.image

            if image is not None:
                self.texture_id = load_gl_texture(image)
            else:
                # Fallback for OBJ files that reference textures in the MTL file
                if file_path.lower().endswith('.obj'):
                    try:
                        # A bit of a hack: assume texture is in the same dir with a common name
                        from pathlib import Path
                        p = Path(file_path)
                        # Try to find a texture file in the same directory
                        for ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tga']:
                            tex_path = p.with_suffix(ext)
                            if tex_path.exists():
                                image = Image.open(tex_path)
                                self.texture_id = load_gl_texture(image)
                                break
                        if not self.texture_id:
                             # Try to find PBR_Material.png in the same directory
                            pbr_tex_path = p.parent / 'PBR_Material.png'
                            if pbr_tex_path.exists():
                                image = Image.open(pbr_tex_path)
                                self.texture_id = load_gl_texture(image)

                    except Exception as e:
                        print(f"Could not manually load texture for OBJ: {e}")

        except Exception as e:
            print(f"Could not load texture: {e}")

    def draw(self):
        if not self.mesh:
            return

        if self.texture_id and self.vbo_uvs is not None:
            glEnable(GL_TEXTURE_2D)
            glBindTexture(GL_TEXTURE_2D, self.texture_id)

        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_NORMAL_ARRAY)
        if self.texture_id and self.vbo_uvs is not None:
            glEnableClientState(GL_TEXTURE_COORD_ARRAY)

        glBindBuffer(GL_ARRAY_BUFFER, self.vbo_verts)
        glVertexPointer(3, GL_FLOAT, 0, None)

        glBindBuffer(GL_ARRAY_BUFFER, self.vbo_normals)
        glNormalPointer(GL_FLOAT, 0, None)

        if self.texture_id and self.vbo_uvs is not None:
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo_uvs)
            glTexCoordPointer(2, GL_FLOAT, 0, None)

        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ibo_faces)
        glDrawElements(GL_TRIANGLES, self.face_count, GL_UNSIGNED_INT, None)

        glDisableClientState(GL_VERTEX_ARRAY)
        glDisableClientState(GL_NORMAL_ARRAY)
        if self.texture_id and self.vbo_uvs is not None:
            glDisableClientState(GL_TEXTURE_COORD_ARRAY)
            glDisable(GL_TEXTURE_2D)

    def __del__(self):
        # Destructor to clean up OpenGL buffers
        buffers = [self.vbo_verts, self.vbo_normals, self.vbo_uvs, self.ibo_faces]
        glDeleteBuffers(len(buffers), [b for b in buffers if b is not None])
        if self.texture_id:
            glDeleteTextures(1, [self.texture_id])
