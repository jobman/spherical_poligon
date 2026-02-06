import pygame
from pygame.locals import *
import math
import numpy as np
import config as cfg

class InputHandler:
    def __init__(self, camera, renderer, game_world):
        self.camera = camera
        self.renderer = renderer
        self.game_world = game_world
        self.mouse_dragging = False
        self.click_to_process = None
        self.mouse_down_pos = None
        self.camera.surface_radius = self._estimate_surface_radius(game_world)

    def _estimate_surface_radius(self, game_world):
        if game_world.tiles:
            return float(np.linalg.norm(game_world.tiles[0].center))
        return 1.0

    def handle_events(self, events):
        for event in events:
            if event.type == pygame.QUIT:
                return False # Signal to quit
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return False # Signal to quit

            self.handle_mouse_input(event)
        
        self.handle_keyboard_input(pygame.key.get_pressed())
        return True # Signal to continue

    def handle_keyboard_input(self, keys):
        inversion_factor = -1 if math.cos(self.camera.angle_x) < 0 else 1
        speed_scale = self.camera.get_speed_scale()
        if keys[pygame.K_w]: self.camera.angle_x_vel += self.camera.keyboard_rotation_speed * speed_scale
        if keys[pygame.K_s]: self.camera.angle_x_vel -= self.camera.keyboard_rotation_speed * speed_scale
        if keys[pygame.K_a]: self.camera.angle_y_vel += self.camera.keyboard_rotation_speed * speed_scale * inversion_factor
        if keys[pygame.K_d]: self.camera.angle_y_vel -= self.camera.keyboard_rotation_speed * speed_scale * inversion_factor

    def handle_mouse_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F3:
                self.renderer.debug_mode = not self.renderer.debug_mode
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self.mouse_dragging = True
                self.mouse_down_pos = event.pos
            elif event.button == 4: # Zoom in
                zoom_range = cfg.MAX_ZOOM - cfg.MIN_ZOOM
                current_zoom_ratio = (self.camera.target_zoom - cfg.MIN_ZOOM) / zoom_range if zoom_range != 0 else 0
                zoom_step = cfg.MIN_ZOOM_STEP + current_zoom_ratio * (cfg.MAX_ZOOM_STEP - cfg.MIN_ZOOM_STEP)
                self.camera.target_zoom = max(cfg.MIN_ZOOM, self.camera.target_zoom - zoom_step)
            elif event.button == 5: # Zoom out
                zoom_range = cfg.MAX_ZOOM - cfg.MIN_ZOOM
                current_zoom_ratio = (self.camera.target_zoom - cfg.MIN_ZOOM) / zoom_range if zoom_range != 0 else 0
                zoom_step = cfg.MIN_ZOOM_STEP + current_zoom_ratio * (cfg.MAX_ZOOM_STEP - cfg.MIN_ZOOM_STEP)
                self.camera.target_zoom = min(cfg.MAX_ZOOM, self.camera.target_zoom + zoom_step)
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1 and self.mouse_down_pos:
                dist_sq = (event.pos[0] - self.mouse_down_pos[0])**2 + (event.pos[1] - self.mouse_down_pos[1])**2
                if dist_sq < 10: # Click threshold
                    self.click_to_process = event.pos
                self.mouse_dragging = False
                self.mouse_down_pos = None
        elif event.type == pygame.MOUSEMOTION:
            if self.mouse_dragging:
                inversion_factor = -1 if math.cos(self.camera.angle_x) < 0 else 1
                speed_scale = self.camera.get_speed_scale()
                rel_x, rel_y = event.rel
                self.camera.angle_y_vel += rel_x * self.camera.rotation_sensitivity * 0.01 * speed_scale * inversion_factor
                self.camera.angle_x_vel += rel_y * self.camera.rotation_sensitivity * 0.01 * speed_scale
