import math
import numpy as np
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

    def rotate_world_point(self, point):
        x, y, z = point

        cos_y = math.cos(self.angle_y)
        sin_y = math.sin(self.angle_y)
        x1 = x * cos_y + z * sin_y
        y1 = y
        z1 = -x * sin_y + z * cos_y

        cos_x = math.cos(self.angle_x)
        sin_x = math.sin(self.angle_x)
        x2 = x1
        y2 = y1 * cos_x - z1 * sin_x
        z2 = y1 * sin_x + z1 * cos_x

        return np.array([x2, y2, z2], dtype=np.float32)

    def rotate_world_points(self, points):
        if len(points) == 0:
            return np.empty((0, 3), dtype=np.float32)

        cos_y = math.cos(self.angle_y)
        sin_y = math.sin(self.angle_y)
        cos_x = math.cos(self.angle_x)
        sin_x = math.sin(self.angle_x)

        x1 = points[:, 0] * cos_y + points[:, 2] * sin_y
        y1 = points[:, 1]
        z1 = -points[:, 0] * sin_y + points[:, 2] * cos_y

        y2 = y1 * cos_x - z1 * sin_x
        z2 = y1 * sin_x + z1 * cos_x

        return np.column_stack((x1, y2, z2)).astype(np.float32, copy=False)
