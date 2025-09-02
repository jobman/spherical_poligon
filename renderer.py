
import pygame
from pygame.locals import *
import math
import numpy as np
import config as cfg
from OpenGL.GL import *
from OpenGL.GLU import *

class Renderer:
    def __init__(self, world):
        self.world = world
        self.width, self.height = cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT
        self.fps = cfg.FPS

        # --- Anti-aliasing (MSAA) ---
        pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLEBUFFERS, 1)
        pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLESAMPLES, 4) # 4x MSAA
        
        # Set up Pygame display with OpenGL
        pygame.display.set_mode((self.width, self.height), DOUBLEBUF | OPENGL)
        pygame.display.set_caption(cfg.CAPTION)
        
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("monospace", 16)
        self.debug_mode = False

        # --- Camera & Input ---
        self.angle_x, self.angle_y = 0, 0
        self.angle_x_vel, self.angle_y_vel = 0, 0
        self.damping = cfg.DAMPING
        self.zoom = 1.0
        self.target_zoom = 1.0
        self.zoom_speed = cfg.ZOOM_SPEED
        self.zoom_smoothing_factor = cfg.ZOOM_SMOOTHING_FACTOR
        self.rotation_sensitivity = cfg.ROTATION_SENSITIVITY
        self.keyboard_rotation_speed = cfg.KEYBOARD_ROTATION_SPEED
        self.mouse_dragging = False

        # --- Lighting ---
        self.light_angle = 0

        # --- OpenGL Setup ---
        self.init_gl()

        # --- VBOs ---
        self.tile_vbo_verts = None
        self.tile_vbo_colors = None
        self.tile_vbo_normals = None
        self.tile_vbo_edges = None
        self.river_vbo_verts = None
        self.river_vbo_colors = None
        
        self.tile_vert_count = 0
        self.tile_edge_count = 0
        self.river_vert_count = 0

        self.prepare_vbos()

    def init_gl(self):
        glViewport(0, 0, self.width, self.height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, (self.width / self.height), 0.1, 50.0)
        glMatrixMode(GL_MODELVIEW)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_MULTISAMPLE)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        glEnable(GL_NORMALIZE) # Important for scaling
        glShadeModel(GL_SMOOTH)

    def prepare_vbos(self):
        # 1. Prepare Tile Data
        tile_vertices = []
        tile_colors = []
        tile_normals = []
        edge_vertices = []

        for i, tile in enumerate(self.world.tiles):
            if len(tile.vertices) < 3: continue

            # We create a fan of triangles from the polygon for rendering
            v0 = tile.vertices[0].to_np()
            normal = tile.normal
            color = tile.color / 255.0 # Normalize color for OpenGL

            for j in range(1, len(tile.vertices) - 1):
                v1 = tile.vertices[j].to_np()
                v2 = tile.vertices[j + 1].to_np()
                
                tile_vertices.extend([v0, v1, v2])
                tile_normals.extend([normal, normal, normal])
                tile_colors.extend([color, color, color])

            # Prepare edge data
            for j in range(len(tile.vertices)):
                v_start = tile.vertices[j].to_np()
                v_end = tile.vertices[(j + 1) % len(tile.vertices)].to_np()
                edge_vertices.extend([v_start, v_end])

        self.tile_vert_count = len(tile_vertices)
        self.tile_edge_count = len(edge_vertices)

        # Create VBOs for tiles
        if self.tile_vert_count > 0:
            self.tile_vbo_verts = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self.tile_vbo_verts)
            glBufferData(GL_ARRAY_BUFFER, np.array(tile_vertices, dtype=np.float32), GL_STATIC_DRAW)

            self.tile_vbo_colors = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self.tile_vbo_colors)
            glBufferData(GL_ARRAY_BUFFER, np.array(tile_colors, dtype=np.float32), GL_STATIC_DRAW)

            self.tile_vbo_normals = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self.tile_vbo_normals)
            glBufferData(GL_ARRAY_BUFFER, np.array(tile_normals, dtype=np.float32), GL_STATIC_DRAW)

            self.tile_vbo_edges = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self.tile_vbo_edges)
            glBufferData(GL_ARRAY_BUFFER, np.array(edge_vertices, dtype=np.float32), GL_STATIC_DRAW)

        # 2. Prepare River Data
        river_vertices = []
        river_colors = []
        if self.world.river_paths:
            max_flow = max(self.world.river_flow.values()) if self.world.river_flow else 1.0
            base_color = cfg.RIVER_COLOR / 255.0
            
            for path in self.world.river_paths:
                if len(path) < 2: continue
                for i in range(len(path) - 1):
                    v1 = path[i]
                    v2 = path[i+1]
                    river_vertices.extend([v1.to_np(), v2.to_np()])
                    river_colors.extend([base_color, base_color]) # Simple uniform color for now

        self.river_vert_count = len(river_vertices)
        if self.river_vert_count > 0:
            self.river_vbo_verts = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self.river_vbo_verts)
            glBufferData(GL_ARRAY_BUFFER, np.array(river_vertices, dtype=np.float32), GL_STATIC_DRAW)

            self.river_vbo_colors = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self.river_vbo_colors)
            glBufferData(GL_ARRAY_BUFFER, np.array(river_colors, dtype=np.float32), GL_STATIC_DRAW)


    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                self.handle_input(event)

            self.update()
            self.draw()

        pygame.quit()

    def handle_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F3:
                self.debug_mode = not self.debug_mode
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self.mouse_dragging = True
            elif event.button == 4: # Zoom in
                self.target_zoom = max(0.5, self.target_zoom - self.zoom_speed)
            elif event.button == 5: # Zoom out
                self.target_zoom = min(5.0, self.target_zoom + self.zoom_speed)
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.mouse_dragging = False
        elif event.type == pygame.MOUSEMOTION:
            if self.mouse_dragging:
                rel_x, rel_y = event.rel
                self.angle_y_vel += rel_x * self.rotation_sensitivity * 0.01
                self.angle_x_vel += rel_y * self.rotation_sensitivity * 0.01

    def update(self):
        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]: self.angle_x_vel += self.keyboard_rotation_speed
        if keys[pygame.K_s]: self.angle_x_vel -= self.keyboard_rotation_speed
        if keys[pygame.K_a]: self.angle_y_vel += self.keyboard_rotation_speed
        if keys[pygame.K_d]: self.angle_y_vel -= self.keyboard_rotation_speed

        # Update camera angles and apply damping
        self.angle_x += self.angle_x_vel
        self.angle_y += self.angle_y_vel
        self.angle_x_vel *= self.damping
        self.angle_y_vel *= self.damping

        # Update zoom
        self.zoom += (self.target_zoom - self.zoom) * self.zoom_smoothing_factor

        # Update light rotation
        self.light_angle = (self.light_angle + cfg.LIGHT_ROTATION_SPEED) % (2 * math.pi)


    def draw(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        # --- Camera Transformations ---
        glTranslatef(0.0, 0.0, -3 * self.zoom) # Zoom
        glRotatef(math.degrees(self.angle_x), 1, 0, 0)
        glRotatef(math.degrees(self.angle_y), 0, 1, 0)

        # --- Lighting ---
        # Smoothly rotate the light source around the Y-axis
        lx, ly, lz = cfg.LIGHT_SOURCE_VECTOR
        rotated_lx = lx * math.cos(self.light_angle) + lz * math.sin(self.light_angle)
        rotated_lz = -lx * math.sin(self.light_angle) + lz * math.cos(self.light_angle)
        light_pos = [rotated_lx, ly, rotated_lz, 0.0]
        glLightfv(GL_LIGHT0, GL_POSITION, light_pos)
        
        ambient = cfg.AMBIENT_LIGHT
        glLightModelfv(GL_LIGHT_MODEL_AMBIENT, [ambient, ambient, ambient, 1.0])

        # --- Draw Tiles ---
        if self.tile_vert_count > 0:
            glEnableClientState(GL_VERTEX_ARRAY)
            glEnableClientState(GL_COLOR_ARRAY)
            glEnableClientState(GL_NORMAL_ARRAY)

            # Draw filled polygons
            glBindBuffer(GL_ARRAY_BUFFER, self.tile_vbo_verts)
            glVertexPointer(3, GL_FLOAT, 0, None)
            glBindBuffer(GL_ARRAY_BUFFER, self.tile_vbo_colors)
            glColorPointer(3, GL_FLOAT, 0, None)
            glBindBuffer(GL_ARRAY_BUFFER, self.tile_vbo_normals)
            glNormalPointer(GL_FLOAT, 0, None)
            glDrawArrays(GL_TRIANGLES, 0, self.tile_vert_count)

            # Draw edges
            glDisable(GL_LIGHTING)
            glColor3f(0.2, 0.2, 0.2) # Dark edges
            glLineWidth(1.0)
            glBindBuffer(GL_ARRAY_BUFFER, self.tile_vbo_edges)
            glVertexPointer(3, GL_FLOAT, 0, None)
            glDrawArrays(GL_LINES, 0, self.tile_edge_count)
            glEnable(GL_LIGHTING)

            glDisableClientState(GL_VERTEX_ARRAY)
            glDisableClientState(GL_COLOR_ARRAY)
            glDisableClientState(GL_NORMAL_ARRAY)

        # --- Draw Rivers ---
        if self.river_vert_count > 0:
            glDisable(GL_LIGHTING)
            glLineWidth(2.0) # Make rivers a bit thicker
            glEnableClientState(GL_VERTEX_ARRAY)
            glEnableClientState(GL_COLOR_ARRAY)

            glBindBuffer(GL_ARRAY_BUFFER, self.river_vbo_verts)
            glVertexPointer(3, GL_FLOAT, 0, None)
            glBindBuffer(GL_ARRAY_BUFFER, self.river_vbo_colors)
            glColorPointer(3, GL_FLOAT, 0, None)
            glDrawArrays(GL_LINES, 0, self.river_vert_count)

            glDisableClientState(GL_VERTEX_ARRAY)
            glDisableClientState(GL_COLOR_ARRAY)
            glEnable(GL_LIGHTING)

        if self.debug_mode:
            self.draw_debug_info()

        pygame.display.flip()
        self.clock.tick(self.fps)

    def draw_debug_info(self):
        # Switch to 2D orthographic mode
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        gluOrtho2D(0, self.width, 0, self.height)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        
        # Disable 3D features we don't need for 2D UI
        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND) # Enable blending for transparency
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        y_offset = 10

        def render(text, x, y):
            # 1. Render the text with a white color
            text_surface = self.font.render(text, True, (255, 255, 255, 255))
            
            # 2. Create a semi-transparent background surface
            bg_height = text_surface.get_height() + 4
            bg_surface = pygame.Surface((self.width, bg_height), pygame.SRCALPHA)
            bg_surface.fill((20, 20, 20, 180)) # Dark, semi-transparent background

            # 3. Blit the text onto our background
            bg_surface.blit(text_surface, (5, 2)) # Add some padding

            # 4. Convert to OpenGL texture format and draw
            data = pygame.image.tostring(bg_surface, "RGBA", True)
            glWindowPos2d(x, self.height - y - bg_surface.get_height())
            glDrawPixels(bg_surface.get_width(), bg_surface.get_height(), GL_RGBA, GL_UNSIGNED_BYTE, data)
            
            return bg_height

        # Render each line of debug info and update the y_offset
        y_offset += render(f"FPS: {self.clock.get_fps():.2f}", 0, y_offset)
        y_offset += render(f"Angle X: {math.degrees(self.angle_x):.2f}", 0, y_offset)
        y_offset += render(f"Angle Y: {math.degrees(self.angle_y):.2f}", 0, y_offset)
        y_offset += render(f"Zoom: {self.zoom:.2f}", 0, y_offset)
        y_offset += render(f"Vertices: {self.tile_vert_count}", 0, y_offset)
        y_offset += render(f"Light Angle: {math.degrees(self.light_angle):.2f}", 0, y_offset)
        
        # Restore previous OpenGL state
        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()
