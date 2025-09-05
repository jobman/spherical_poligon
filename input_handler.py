import pygame
from pygame.locals import *

class InputHandler:
    def __init__(self, camera, renderer):
        self.camera = camera
        self.renderer = renderer
        self.mouse_dragging = False

    def handle_events(self, events):
        for event in events:
            if event.type == pygame.QUIT:
                return False # Signal to quit
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return False # Signal to quit

            self.handle_keyboard_input(pygame.key.get_pressed())
            self.handle_mouse_input(event)
        return True # Signal to continue

    def handle_keyboard_input(self, keys):
        if keys[pygame.K_w]: self.camera.angle_x_vel += self.camera.keyboard_rotation_speed
        if keys[pygame.K_s]: self.camera.angle_x_vel -= self.camera.keyboard_rotation_speed
        if keys[pygame.K_a]: self.camera.angle_y_vel += self.camera.keyboard_rotation_speed
        if keys[pygame.K_d]: self.camera.angle_y_vel -= self.camera.keyboard_rotation_speed

    def handle_mouse_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F3:
                self.renderer.debug_mode = not self.renderer.debug_mode
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self.mouse_dragging = True
            elif event.button == 4: # Zoom in
                self.camera.target_zoom = max(0.5, self.camera.target_zoom - self.camera.zoom_speed)
            elif event.button == 5: # Zoom out
                self.camera.target_zoom = min(5.0, self.camera.target_zoom + self.camera.zoom_speed)
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.mouse_dragging = False
        elif event.type == pygame.MOUSEMOTION:
            if self.mouse_dragging:
                rel_x, rel_y = event.rel
                self.camera.angle_y_vel += rel_x * self.camera.rotation_sensitivity * 0.01
                self.camera.angle_x_vel += rel_y * self.camera.rotation_sensitivity * 0.01