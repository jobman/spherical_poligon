import pygame
from pygame.locals import *
import math
import numpy as np
import config as cfg
from OpenGL.GL import *
from OpenGL.GLU import *
from render_data import RenderData
from camera import Camera
from input_handler import InputHandler
import picking

class Renderer:
    def __init__(self, render_data, game_world):
        self.render_data = render_data
        self.game_world = game_world
        self.fps = cfg.FPS

        display_flags = DOUBLEBUF | OPENGL
        if cfg.FULLSCREEN:
            display_flags |= FULLSCREEN
            info = pygame.display.Info()
            self.width, self.height = info.current_w, info.current_h
        else:
            self.width, self.height = cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT

        pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLEBUFFERS, 1)
        pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLESAMPLES, 8)
        pygame.display.set_mode((self.width, self.height), display_flags)
        pygame.display.set_caption(cfg.CAPTION)
        
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("monospace", 16)
        self.debug_mode = False

        self.camera = Camera()
        self.input_handler = InputHandler(self.camera, self, game_world)

        self.light_angle = 0

        self.init_gl()

        self.tile_vbo_verts = None
        self.tile_vbo_colors = None
        self.tile_vbo_normals = None
        self.tile_vbo_edges = None
        self.river_vbo_verts = None
        self.river_vbo_colors = None
        
        self.tile_vert_count = 0
        self.tile_edge_count = 0
        self.river_vert_count = 0

        self.prepare_vbos(render_data)

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
        glEnable(GL_NORMALIZE)
        glShadeModel(GL_SMOOTH)

    def prepare_vbos(self, render_data):
        self.tile_vert_count = len(render_data.tile_vertices)
        self.tile_edge_count = len(render_data.edge_vertices)
        self.river_vert_count = len(render_data.river_vertices)

        if self.tile_vert_count > 0:
            self.tile_vbo_verts = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self.tile_vbo_verts)
            glBufferData(GL_ARRAY_BUFFER, render_data.tile_vertices, GL_STATIC_DRAW)

            self.tile_vbo_colors = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self.tile_vbo_colors)
            glBufferData(GL_ARRAY_BUFFER, render_data.tile_colors, GL_STATIC_DRAW)

            self.tile_vbo_normals = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self.tile_vbo_normals)
            glBufferData(GL_ARRAY_BUFFER, render_data.tile_normals, GL_STATIC_DRAW)

            self.tile_vbo_edges = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self.tile_vbo_edges)
            glBufferData(GL_ARRAY_BUFFER, render_data.edge_vertices, GL_STATIC_DRAW)

        if self.river_vert_count > 0:
            self.river_vbo_verts = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self.river_vbo_verts)
            glBufferData(GL_ARRAY_BUFFER, render_data.river_vertices, GL_STATIC_DRAW)

            self.river_vbo_colors = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self.river_vbo_colors)
            glBufferData(GL_ARRAY_BUFFER, render_data.river_colors, GL_STATIC_DRAW)

    def run(self):
        running = True
        while running:
            running = self.input_handler.handle_events(pygame.event.get())
            self.update()
            self.draw()
        pygame.quit()

    def update(self):
        self.camera.update()
        self.light_angle = (self.light_angle + cfg.LIGHT_ROTATION_SPEED) % (2 * math.pi)

    def draw(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        self.camera.apply_transformations()

        if self.input_handler.click_to_process:
            x, y = self.input_handler.click_to_process
            selected_tile = picking.get_tile_at_pos(x, y, self.width, self.height, self.camera, self.game_world)
            
            for tile in self.game_world.tiles:
                tile.is_selected = False
            
            if selected_tile:
                selected_tile.is_selected = True
                print(f"Selected tile: {selected_tile.id}")
            
            self.input_handler.click_to_process = None

        lx, ly, lz = cfg.LIGHT_SOURCE_VECTOR
        rotated_lx = lx * math.cos(self.light_angle) + lz * math.sin(self.light_angle)
        rotated_lz = -lx * math.sin(self.light_angle) + lz * math.cos(self.light_angle)
        light_pos = [rotated_lx, ly, rotated_lz, 0.0]
        glLightfv(GL_LIGHT0, GL_POSITION, light_pos)
        
        ambient = cfg.AMBIENT_LIGHT
        glLightModelfv(GL_LIGHT_MODEL_AMBIENT, [ambient, ambient, ambient, 1.0])

        if self.tile_vert_count > 0:
            glEnableClientState(GL_VERTEX_ARRAY)
            glEnableClientState(GL_COLOR_ARRAY)
            glEnableClientState(GL_NORMAL_ARRAY)

            glBindBuffer(GL_ARRAY_BUFFER, self.tile_vbo_verts)
            glVertexPointer(3, GL_FLOAT, 0, None)
            glBindBuffer(GL_ARRAY_BUFFER, self.tile_vbo_colors)
            glColorPointer(3, GL_FLOAT, 0, None)
            glBindBuffer(GL_ARRAY_BUFFER, self.tile_vbo_normals)
            glNormalPointer(GL_FLOAT, 0, None)
            glDrawArrays(GL_TRIANGLES, 0, self.tile_vert_count)

            glDisable(GL_LIGHTING)
            glColor3f(0.2, 0.2, 0.2)
            glLineWidth(1.0)
            glBindBuffer(GL_ARRAY_BUFFER, self.tile_vbo_edges)
            glVertexPointer(3, GL_FLOAT, 0, None)
            glDrawArrays(GL_LINES, 0, self.tile_edge_count)
            glEnable(GL_LIGHTING)

            glDisableClientState(GL_VERTEX_ARRAY)
            glDisableClientState(GL_COLOR_ARRAY)
            glDisableClientState(GL_NORMAL_ARRAY)

        if self.river_vert_count > 0:
            glDisable(GL_LIGHTING)
            glLineWidth(4.0)
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

        self.draw_selected_tile()

        if self.debug_mode:
            self.draw_debug_info()

        pygame.display.flip()
        self.clock.tick(self.fps)

    def draw_selected_tile(self):
        glDisable(GL_LIGHTING)
        glColor3f(1.0, 0.0, 0.0) # Red
        glLineWidth(3.0)

        for tile in self.game_world.tiles:
            if tile.is_selected:
                glBegin(GL_LINE_LOOP)
                for vertex in tile.vertices:
                    v = vertex.to_np() * 1.001
                    glVertex3fv(v)
                glEnd()
        
        glEnable(GL_LIGHTING)

    def draw_debug_info(self):
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        gluOrtho2D(0, self.width, 0, self.height)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        
        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        y_offset = 10

        def render(text, x, y):
            text_surface = self.font.render(text, True, (255, 255, 255, 255))
            bg_height = text_surface.get_height() + 4
            bg_surface = pygame.Surface((self.width, bg_height), pygame.SRCALPHA)
            bg_surface.fill((20, 20, 20, 180))
            bg_surface.blit(text_surface, (5, 2))
            data = pygame.image.tostring(bg_surface, "RGBA", True)
            glWindowPos2d(x, self.height - y - bg_surface.get_height())
            glDrawPixels(bg_surface.get_width(), bg_surface.get_height(), GL_RGBA, GL_UNSIGNED_BYTE, data)
            return bg_height

        y_offset += render(f"FPS: {self.clock.get_fps():.2f}", 0, y_offset)
        y_offset += render(f"Angle X: {math.degrees(self.camera.angle_x):.2f}", 0, y_offset)
        y_offset += render(f"Angle Y: {math.degrees(self.camera.angle_y):.2f}", 0, y_offset)
        y_offset += render(f"Zoom: {self.camera.zoom:.2f}", 0, y_offset)
        y_offset += render(f"Vertices: {self.tile_vert_count}", 0, y_offset)
        y_offset += render(f"Light Angle: {math.degrees(self.light_angle):.2f}", 0, y_offset)
        
        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()