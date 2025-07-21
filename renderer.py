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
        self.font = pygame.font.SysFont("monospace", 16)
        self.debug_mode = False

        self.light_source = np.array([0.5, 0.7, -1])
        self.edge_color = (40, 40, 40)
        self.river_color = (60, 120, 200) # A slightly different blue

        self.angle_x, self.angle_y = 0, 0
        self.angle_x_vel, self.angle_y_vel = 0, 0
        self.damping = 0.95
        self.zoom = 1.0
        self.target_zoom = 1.0
        self.zoom_speed = 0.1
        self.zoom_smoothing_factor = 0.1
        self.rotation_sensitivity = 0.1
        self.keyboard_rotation_speed = 0.005
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
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F3:
                self.debug_mode = not self.debug_mode
        elif event.type == pygame.MOUSEBUTTONDOWN:
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
                inversion_factor = -1 if math.cos(self.angle_x) >= 0 else 1
                self.angle_y_vel -= rel_x * sensitivity * self.rotation_sensitivity * inversion_factor
                self.angle_x_vel += rel_y * sensitivity * self.rotation_sensitivity

    def update(self):
        keys = pygame.key.get_pressed()
        inversion_factor = -1 if math.cos(self.angle_x) >= 0 else 1

        if keys[pygame.K_w]:
            self.angle_x_vel += self.keyboard_rotation_speed
        if keys[pygame.K_s]:
            self.angle_x_vel -= self.keyboard_rotation_speed
        if keys[pygame.K_a]:
            self.angle_y_vel += self.keyboard_rotation_speed * inversion_factor
        if keys[pygame.K_d]:
            self.angle_y_vel -= self.keyboard_rotation_speed * inversion_factor

        self.angle_x += self.angle_x_vel
        self.angle_y += self.angle_y_vel

        # Keep angles in the [0, 2*pi] range
        two_pi = 2 * math.pi
        self.angle_x = self.angle_x % two_pi
        self.angle_y = self.angle_y % two_pi

        self.angle_x_vel *= self.damping
        self.angle_y_vel *= self.damping
        self.zoom += (self.target_zoom - self.zoom) * self.zoom_smoothing_factor

    def _draw_rivers(self, rotated_vertices, projected_points):
        river_segments = []
        for start_v, end_v in self.world.river_downstream_map.items():
            start_idx = self.world.vertex_to_index.get(start_v)
            end_idx = self.world.vertex_to_index.get(end_v)

            if start_idx is None or end_idx is None:
                continue

            # Culling: only draw if both ends of the segment are visible
            if rotated_vertices[start_idx, 2] > 0 and rotated_vertices[end_idx, 2] > 0:
                flow = self.world.river_vertex_flow.get(end_v, 1.0)
                width = int(2 + math.log(1 + flow) * 1.5)
                width = min(width, 10)
                
                p1 = projected_points[start_idx]
                p2 = projected_points[end_idx]
                depth = (rotated_vertices[start_idx, 2] + rotated_vertices[end_idx, 2]) / 2
                river_segments.append((depth, p1, p2, width))

        river_segments.sort(key=lambda x: x[0], reverse=True)

        for _, p1, p2, width in river_segments:
            pygame.draw.line(self.screen, self.river_color, p1, p2, width)

    def draw(self):
        self.screen.fill((0, 0, 0))

        # --- Create rotation matrix from user input ---
        cos_x, sin_x = math.cos(self.angle_x), math.sin(self.angle_x)
        cos_y, sin_y = math.cos(self.angle_y), math.sin(self.angle_y)
        rot_x = np.array([[1, 0, 0], [0, cos_x, -sin_x], [0, sin_x, cos_x]])
        rot_y = np.array([[cos_y, 0, sin_y], [0, 1, 0], [-sin_y, 0, cos_y]])
        rotation_matrix = rot_y @ rot_x

        # --- Rotate vertices and normals ---
        rotated_vertices = self.world.original_vertices @ rotation_matrix
        rotated_normals = self.world.face_normals @ rotation_matrix

        # --- Back-face culling ---
        visible_faces_mask = rotated_normals[:, 2] > 0
        visible_indices = np.where(visible_faces_mask)[0]

        if visible_indices.any():
            # --- Process only visible faces ---
            visible_normals = rotated_normals[visible_indices]
            visible_colors = self.world.face_colors[visible_indices]

            # --- Lighting ---
            light_source = np.array([0.3, 0.5, -0.8])
            light_source /= np.linalg.norm(light_source)
            
            intensities = np.dot(visible_normals, -light_source)
            np.clip(intensities, 0.3, 1.0, out=intensities)
            final_colors = (visible_colors * intensities[:, np.newaxis]).astype(int)
            np.clip(final_colors, 0, 255, out=final_colors)

            # --- Projection and Depth Sorting ---
            polygons_to_draw = []
            projected_points = rotated_vertices[:, :2] * (self.scale_factor * self.zoom) + np.array([self.width / 2, self.height / 2])

            for i, face_idx in enumerate(visible_indices):
                indices = self.world.face_indices[face_idx]
                depth = np.mean(rotated_vertices[indices, 2])
                projected = projected_points[indices]
                polygons_to_draw.append((depth, projected, final_colors[i]))

            polygons_to_draw.sort(key=lambda x: x[0], reverse=True)

            # --- Drawing ---
            for _, projected, color in polygons_to_draw:
                pygame.draw.polygon(self.screen, color, projected)
                pygame.draw.polygon(self.screen, self.edge_color, projected, 1)
            
            # --- Draw Rivers on top of terrain ---
            self._draw_rivers(rotated_vertices, projected_points)

        if self.debug_mode:
            self.draw_debug_info()

        pygame.display.flip()
        self.clock.tick(self.fps)

    def draw_debug_info(self):
        fps_text = f"FPS: {self.clock.get_fps():.2f}"
        angle_text_x = f"Angle X: {math.degrees(self.angle_x):.2f}"
        angle_text_y = f"Angle Y: {math.degrees(self.angle_y):.2f}"
        river_count_text = f"River Segments: {len(self.world.river_downstream_map)}"
        
        fps_surface = self.font.render(fps_text, True, (255, 255, 255))
        angle_x_surface = self.font.render(angle_text_x, True, (255, 255, 255))
        angle_y_surface = self.font.render(angle_text_y, True, (255, 255, 255))
        river_count_surface = self.font.render(river_count_text, True, (255, 255, 255))
        
        self.screen.blit(fps_surface, (10, 10))
        self.screen.blit(angle_x_surface, (10, 30))
        self.screen.blit(angle_y_surface, (10, 50))
        self.screen.blit(river_count_surface, (10, 70))
