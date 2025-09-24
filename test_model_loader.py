
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import trimesh
import numpy as np

# --- Camera Settings ---
CAMERA_YAW = -30.0
CAMERA_PITCH = 30.0
CAMERA_DISTANCE = 5.0
LAST_MOUSE_POS = None
IS_ROTATING = False

from PIL import Image

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
    
    # Build mipmaps
    gluBuild2DMipmaps(GL_TEXTURE_2D, GL_RGBA, image.width, image.height, GL_RGBA, GL_UNSIGNED_BYTE, img_data)
    
    return texture_id

def main():
    global CAMERA_YAW, CAMERA_PITCH, CAMERA_DISTANCE, LAST_MOUSE_POS, IS_ROTATING

    pygame.init()
    display = (1200, 800)
    pygame.display.set_mode(display, DOUBLEBUF | OPENGL)
    pygame.display.set_caption("Model Viewer (Textured)")

    # --- Load Model ---
    try:
        scene = trimesh.load('assets/textured_primal_warior/textured_primal_warior.obj', force='scene')
        mesh = scene.geometry[list(scene.geometry.keys())[0]]
    except Exception as e:
        print(f"Error loading model: {e}")
        print("Please ensure 'trimesh' and its dependencies are installed: pip install trimesh[easy]")
        return

    # --- Load Texture ---
    texture_id = None
    try:
        image = None
        # The model can have different material types. We check for the texture in the most common places.
        if hasattr(mesh.visual, 'material'):
            # Case 1: PBR material with a base color texture
            if hasattr(mesh.visual.material, 'baseColorTexture') and mesh.visual.material.baseColorTexture is not None:
                print("Found texture in PBR material.")
                image = mesh.visual.material.baseColorTexture
            # Case 2: Simple material with a texture image
            elif hasattr(mesh.visual.material, 'image') and mesh.visual.material.image is not None:
                print("Found texture in Simple material.")
                image = mesh.visual.material.image

        if image is not None:
            texture_id = load_gl_texture(image)
        else:
            print("Model has no embedded texture, falling back to manual load.")
            image = Image.open('assets/textured_primal_warior/PBR_Material.png')
            texture_id = load_gl_texture(image)
            
    except Exception as e:
        print(f"Could not load texture: {e}")

    # --- OpenGL Setup ---
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glLightfv(GL_LIGHT0, GL_POSITION, [0, 1, 1, 0])
    glLightfv(GL_LIGHT0, GL_DIFFUSE, [1, 1, 1, 1])
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
    # Set base color to white to allow texture to show fully
    glColor4f(1.0, 1.0, 1.0, 1.0)


    glMatrixMode(GL_PROJECTION)
    gluPerspective(45, (display[0] / display[1]), 0.1, 50.0)

    glMatrixMode(GL_MODELVIEW)

    model_center = mesh.bounds.mean(axis=0)
    
    clock = pygame.time.Clock()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    IS_ROTATING = True
                    LAST_MOUSE_POS = pygame.mouse.get_pos()
                elif event.button == 4:
                    CAMERA_DISTANCE = max(1.0, CAMERA_DISTANCE - 0.5)
                elif event.button == 5:
                    CAMERA_DISTANCE += 0.5
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    IS_ROTATING = False
            elif event.type == pygame.MOUSEMOTION:
                if IS_ROTATING:
                    x, y = pygame.mouse.get_pos()
                    dx, dy = x - LAST_MOUSE_POS[0], y - LAST_MOUSE_POS[1]
                    CAMERA_YAW += dx * 0.5
                    CAMERA_PITCH += dy * 0.5
                    CAMERA_PITCH = max(-89, min(89, CAMERA_PITCH))
                    LAST_MOUSE_POS = (x, y)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        
        # --- Camera Transformation ---
        glTranslatef(0.0, 0.0, -CAMERA_DISTANCE)
        glRotatef(CAMERA_PITCH, 1, 0, 0)
        glRotatef(CAMERA_YAW, 0, 1, 0)

        # --- Center and Render Model ---
        glTranslate(-model_center[0], -model_center[1], -model_center[2])
        
        # --- Render the mesh ---
        if texture_id and mesh.visual.uv is not None:
            glEnable(GL_TEXTURE_2D)
            glBindTexture(GL_TEXTURE_2D, texture_id)
        
        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_NORMAL_ARRAY)
        if texture_id and mesh.visual.uv is not None:
            glEnableClientState(GL_TEXTURE_COORD_ARRAY)

        glVertexPointer(3, GL_FLOAT, 0, mesh.vertices)
        glNormalPointer(GL_FLOAT, 0, mesh.vertex_normals)
        if texture_id and mesh.visual.uv is not None:
            glTexCoordPointer(2, GL_FLOAT, 0, mesh.visual.uv)

        glDrawElements(GL_TRIANGLES, len(mesh.faces.flatten()), GL_UNSIGNED_INT, mesh.faces.flatten())

        glDisableClientState(GL_VERTEX_ARRAY)
        glDisableClientState(GL_NORMAL_ARRAY)
        if texture_id and mesh.visual.uv is not None:
            glDisableClientState(GL_TEXTURE_COORD_ARRAY)
            glDisable(GL_TEXTURE_2D)

        pygame.display.flip()
        clock.tick(60)

if __name__ == '__main__':
    main()
