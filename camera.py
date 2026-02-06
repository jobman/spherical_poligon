import math
import config as cfg
from OpenGL.GL import glRotatef, glTranslatef

class Camera:
    def __init__(self):
        self.angle_x, self.angle_y = 0, 0
        self.angle_x_vel, self.angle_y_vel = 0, 0
        self.damping = cfg.DAMPING
        self.zoom = 1.0
        self.target_zoom = 1.0
        self.zoom_speed = cfg.ZOOM_SPEED
        self.zoom_smoothing_factor = cfg.ZOOM_SMOOTHING_FACTOR
        self.rotation_sensitivity = cfg.ROTATION_SENSITIVITY
        self.keyboard_rotation_speed = cfg.KEYBOARD_ROTATION_SPEED
        self.base_distance = 3.0
        self.surface_radius = 1.0

    def update(self):
        # Update camera angles and apply damping
        self.angle_x += self.angle_x_vel
        self.angle_y += self.angle_y_vel
        self.angle_x_vel *= self.damping
        self.angle_y_vel *= self.damping

        # Update zoom
        self.zoom += (self.target_zoom - self.zoom) * self.zoom_smoothing_factor

    def apply_transformations(self):
        glTranslatef(0.0, 0.0, -self.base_distance * self.zoom)
        glRotatef(math.degrees(self.angle_x), 1, 0, 0)
        glRotatef(math.degrees(self.angle_y), 0, 1, 0)

    def get_distance_to_center(self):
        return self.base_distance * self.zoom

    def get_speed_scale(self):
        return max(0.0, self.get_distance_to_center() - self.surface_radius)
