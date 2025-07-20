import pygame
import math
import numpy as np

class Renderer:
    def __init__(self, world):
        self.world = world
        self.width, self.height = 800, 600
        self.fps = 60
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Spherical World")
        self.clock = pygame.time.Clock()
        self.light_source = np.array([0.5, 0.7, -1])
        self.edge_color = (40, 40, 40)

        self.angle_x, self.angle_y = 0, 0
        self.angle_x_vel, self.angle_y_vel = 0, 0
        self.damping = 0.95
        self.zoom = 1.0
        self.target_zoom = 1.0
        self.zoom_speed = 0.1
        self.zoom_smoothing_factor = 0.1
        self.rotation_sensitivity = 0.1
        self.scale_factor = 250
        self.mouse_dragging = False

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                self.handle_input(event)

            self.update()
            self.draw()

        pygame.quit()

    def handle_input(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self.mouse_dragging = True
            elif event.button == 4:
                self.target_zoom = min(5.0, self.target_zoom + self.zoom_speed)
            elif event.button == 5:
                self.target_zoom = max(0.5, self.target_zoom - self.zoom_speed)
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.mouse_dragging = False
        elif event.type == pygame.MOUSEMOTION:
            if self.mouse_dragging:
                sensitivity = 1 / (self.scale_factor * self.zoom)
                rel_x, rel_y = event.rel
                inversion_factor = 1 if math.cos(self.angle_x) >= 0 else -1
                self.angle_y_vel -= rel_x * sensitivity * self.rotation_sensitivity * inversion_factor
                self.angle_x_vel += rel_y * sensitivity * self.rotation_sensitivity

    def update(self):
        self.angle_x += self.angle_x_vel
        self.angle_y += self.angle_y_vel
        self.angle_x_vel *= self.damping
        self.angle_y_vel *= self.damping
        self.zoom += (self.target_zoom - self.zoom) * self.zoom_smoothing_factor

    def draw(self):
        self.screen.fill((0, 0, 0))

        cos_x, sin_x = math.cos(self.angle_x), math.sin(self.angle_x)
        cos_y, sin_y = math.cos(self.angle_y), math.sin(self.angle_y)
        rot_x = np.array([[1,0,0],[0,cos_x,-sin_x],[0,sin_x,cos_x]])
        rot_y = np.array([[cos_y,0,sin_y],[0,1,0],[-sin_y,0,cos_y]])
        rotation_matrix = rot_y @ rot_x

        # --- Vectorized Operations ---
        rotated_vertices = self.world.original_vertices @ rotation_matrix
        rotated_normals = self.world.face_normals @ rotation_matrix

        # --- Culling ---
        visible_faces_mask = rotated_normals[:, 2] >= 0
        visible_indices = np.where(visible_faces_mask)[0]

        if len(visible_indices) == 0:
            pygame.display.flip()
            self.clock.tick(self.fps)
            return

        # --- Lighting for Visible Faces ---
        intensities = np.dot(rotated_normals[visible_indices], -self.light_source)
        np.clip(intensities, 0.2, 1.0, out=intensities)
        final_colors = (self.world.face_colors[visible_indices] * intensities[:, np.newaxis]).astype(int)

        # --- Projection and Depth Calculation ---
        polygons_to_draw = []
        projected_points = rotated_vertices[:, :2] * (self.scale_factor * self.zoom) + np.array([self.width / 2, self.height / 2])

        for i, face_idx in enumerate(visible_indices):
            indices = self.world.face_indices[face_idx]
            depth = np.mean(rotated_vertices[indices, 2])
            projected = projected_points[indices]
            color = final_colors[i]
            polygons_to_draw.append((depth, projected, color))

        # --- Sorting and Drawing ---
        polygons_to_draw.sort(key=lambda x: x[0], reverse=True)

        for _, projected, color in polygons_to_draw:
            pygame.draw.polygon(self.screen, color, projected)
            pygame.draw.polygon(self.screen, self.edge_color, projected, 1)

        # Draw Equator
        equator_points_3d = np.array([[math.cos(a), 0, math.sin(a)] for a in np.linspace(0, 2 * math.pi, 100)])
        rotated_equator = equator_points_3d @ rotation_matrix
        
        for i in range(len(rotated_equator) - 1):
            p1 = rotated_equator[i]
            p2 = rotated_equator[i+1]
            if p1[2] > 0 and p2[2] > 0:
                proj1 = p1[:2] * (self.scale_factor * self.zoom) + np.array([self.width / 2, self.height / 2])
                proj2 = p2[:2] * (self.scale_factor * self.zoom) + np.array([self.width / 2, self.height / 2])
                pygame.draw.line(self.screen, (100, 100, 255), proj1, proj2, 1)

        pygame.display.flip()
        self.clock.tick(self.fps)