import pygame
import math
import numpy as np
import config as cfg

class Renderer:
    def __init__(self, world):
        self.world = world
        self.width, self.height = cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT
        self.fps = cfg.FPS
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption(cfg.CAPTION)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("monospace", 16)
        self.debug_mode = False

        self.edge_color = cfg.EDGE_COLOR

        self.angle_x, self.angle_y = 0, 0
        self.angle_x_vel, self.angle_y_vel = 0, 0
        self.damping = cfg.DAMPING
        self.zoom = 1.0
        self.target_zoom = 1.0
        self.zoom_speed = cfg.ZOOM_SPEED
        self.zoom_smoothing_factor = cfg.ZOOM_SMOOTHING_FACTOR
        self.rotation_sensitivity = cfg.ROTATION_SENSITIVITY
        self.keyboard_rotation_speed = cfg.KEYBOARD_ROTATION_SPEED
        self.scale_factor = cfg.INITIAL_SCALE_FACTOR
        self.mouse_dragging = False

        # Pre-calculate max flow for river width calculation
        if self.world.river_flow:
            self.max_flow = max(self.world.river_flow.values())
        else:
            self.max_flow = 1.0

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
                self.target_zoom = min(cfg.MAX_ZOOM, self.target_zoom + self.zoom_speed)
            elif event.button == 5:
                self.target_zoom = max(cfg.MIN_ZOOM, self.target_zoom - self.zoom_speed)
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
        keys = pygame.key.get_pressed()
        inversion_factor = -1 if math.cos(self.angle_x) >= 0 else 1

        if keys[pygame.K_w]: self.angle_x_vel += self.keyboard_rotation_speed
        if keys[pygame.K_s]: self.angle_x_vel -= self.keyboard_rotation_speed
        if keys[pygame.K_a]: self.angle_y_vel += self.keyboard_rotation_speed * inversion_factor
        if keys[pygame.K_d]: self.angle_y_vel -= self.keyboard_rotation_speed * inversion_factor

        self.angle_x += self.angle_x_vel
        self.angle_y += self.angle_y_vel

        self.angle_x %= (2 * math.pi)
        self.angle_y %= (2 * math.pi)

        self.angle_x_vel *= self.damping
        self.angle_y_vel *= self.damping
        self.zoom += (self.target_zoom - self.zoom) * self.zoom_smoothing_factor

    def draw(self):
        self.screen.fill(cfg.BACKGROUND_COLOR)

        # --- Create rotation matrix ---
        cos_x, sin_x = math.cos(self.angle_x), math.sin(self.angle_x)
        cos_y, sin_y = math.cos(self.angle_y), math.sin(self.angle_y)
        rot_x = np.array([[1, 0, 0], [0, cos_x, -sin_x], [0, sin_x, cos_x]])
        rot_y = np.array([[cos_y, 0, sin_y], [0, 1, 0], [-sin_y, 0, cos_y]])
        rotation_matrix = rot_y @ rot_x

        # --- Rotate tile vertices and normals ---
        rotated_vertices = self.world.original_vertices @ rotation_matrix
        rotated_normals = self.world.face_normals @ rotation_matrix

        # --- Back-face culling for tiles ---
        visible_faces_mask = rotated_normals[:, 2] > 0
        visible_indices = np.where(visible_faces_mask)[0]

        # Pre-calculate all projected points once
        projected_points = rotated_vertices[:, :2] * (self.scale_factor * self.zoom) + np.array([self.width / 2, self.height / 2])

        if visible_indices.any():
            # --- Process only visible faces ---
            visible_normals = rotated_normals[visible_indices]
            visible_colors = self.world.face_colors[visible_indices]

            # --- Lighting ---
            light_source = cfg.LIGHT_SOURCE_VECTOR / np.linalg.norm(cfg.LIGHT_SOURCE_VECTOR)
            
            intensities = np.dot(visible_normals, -light_source)
            np.clip(intensities, cfg.AMBIENT_LIGHT, 1.0, out=intensities)
            final_colors = (visible_colors * intensities[:, np.newaxis]).astype(int)
            np.clip(final_colors, 0, 255, out=final_colors)

            # --- Depth Sorting for Tiles ---
            polygons_to_draw = []
            for i, face_idx in enumerate(visible_indices):
                indices = self.world.face_indices[face_idx]
                if all(idx is not None and idx < len(projected_points) for idx in indices):
                    depth = np.mean(rotated_vertices[indices, 2])
                    projected = projected_points[indices]
                    polygons_to_draw.append((depth, projected, final_colors[i]))

            polygons_to_draw.sort(key=lambda x: x[0], reverse=True)

            # --- Drawing Tiles ---
            for _, projected, color in polygons_to_draw:
                pygame.draw.polygon(self.screen, color, projected)
                pygame.draw.polygon(self.screen, self.edge_color, projected, 1)

        # --- Drawing Rivers ---
        if self.world.river_paths:
            vert_to_idx = {v: i for i, v in enumerate(self.world.vertices)}
            
            for path in self.world.river_paths:
                path_indices = [vert_to_idx.get(v) for v in path]
                path_indices = [i for i in path_indices if i is not None]

                if len(path_indices) < 2:
                    continue
                
                for i in range(len(path_indices) - 1):
                    idx1 = path_indices[i]
                    idx2 = path_indices[i+1]

                    # Culling check for the segment
                    z1 = rotated_vertices[idx1][2]
                    z2 = rotated_vertices[idx2][2]
                    if z1 < 0 and z2 < 0:
                        continue

                    # Get projected points for the segment from the pre-calculated array
                    p1 = projected_points[idx1]
                    p2 = projected_points[idx2]

                    # Calculate width based on flow
                    flow = self.world.river_flow.get(path[i], 1.0)
                    
                    if self.max_flow > 0:
                        normalized_flow = flow / self.max_flow
                    else:
                        normalized_flow = 0
                    
                    width = 1 + int(4 * normalized_flow)
                    
                    pygame.draw.line(self.screen, cfg.RIVER_COLOR, p1, p2, width)

        if self.debug_mode:
            self.draw_debug_info()

        pygame.display.flip()
        self.clock.tick(self.fps)

    def draw_debug_info(self):
        fps_text = f"FPS: {self.clock.get_fps():.2f}"
        angle_text_x = f"Angle X: {math.degrees(self.angle_x):.2f}"
        angle_text_y = f"Angle Y: {math.degrees(self.angle_y):.2f}"
        vert_count_text = f"Vertices: {len(self.world.original_vertices)}"
        face_count_text = f"Faces: {len(self.world.face_indices)}"
        
        def render(text, y):
            surface = self.font.render(text, True, (255, 255, 255))
            self.screen.blit(surface, (10, y))

        render(fps_text, 10)
        render(angle_text_x, 30)
        render(angle_text_y, 50)
        render(vert_count_text, 70)
        render(face_count_text, 90)