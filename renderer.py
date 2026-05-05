import pygame
from pygame.locals import *
import math
import time
import numpy as np
import config as cfg
from OpenGL.GL import *
from OpenGL.GLU import *
from render_data import RenderData
from camera import Camera
from input_handler import InputHandler
import picking
from model import Model

class Renderer:
    def __init__(self, render_data, game_world):
        self.render_data = render_data
        self.game_world = game_world
        self.fps = cfg.FPS
        self.models = {}

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
        self.selected_tile = None
        self.selected_subtile = None
        self.selected_unit = None
        self.battle_mode = False
        self.active_battle_subtile = None
        self.active_battle_rotation = 0.0
        self.battle_pan = np.array([0.0, 0.0], dtype=np.float32)
        self.battle_zoom = 1.0
        self.selected_battle_hex_index = None
        self.battle_field_vbos = None
        self.battle_field_vbo_key = None

        self.light_angle = 0

        self.init_gl()

        self.tile_vbo_verts = None
        self.tile_vbo_colors = None
        self.tile_vbo_normals = None
        self.tile_vbo_edges = None
        self.river_vbo_verts = None
        self.river_vbo_colors = None
        self.subtile_edge_vbos = {}
        self.subtile_point_vbos = {}
        
        self.tile_vert_count = 0
        self.tile_edge_count = 0
        self.river_vert_count = 0

        self.prepare_vbos(render_data)
        if cfg.SUBTILE_PREPARE_ALL_VBOS_ON_START:
            self.prepare_all_subtile_vbos()
        self.load_model("unit", "assets/textured_primal_warior/textured_primal_warior.obj")

    def load_model(self, name, file_path):
        self.models[name] = Model(file_path)

    def init_gl(self):
        glViewport(0, 0, self.width, self.height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, (self.width / self.height), 0.1, 50.0)
        glMatrixMode(GL_MODELVIEW)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_MULTISAMPLE)
        glEnable(GL_CULL_FACE)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        glEnable(GL_NORMALIZE) # Switched back from RESCALE for robustness
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

    def prepare_all_subtile_vbos(self):
        start_time = time.perf_counter()
        tiles_with_subtiles = [tile for tile in self.game_world.tiles if tile.subtiles]
        total_tiles = len(tiles_with_subtiles)
        if total_tiles == 0:
            print("Subtile VBO prebuild skipped: no generated subtiles are loaded.")
            return

        print(f"Prebuilding subtile edge VBOs for {total_tiles} tiles...")
        prepared_count = 0
        edge_vertex_count = 0
        progress_step = max(1, int(cfg.SUBTILE_PREPARE_VBO_PROGRESS_STEP))
        for tile in tiles_with_subtiles:
            prepared_vbo = self._get_subtile_edge_vbo(tile)
            if prepared_vbo is not None:
                _, edge_count = prepared_vbo
                edge_vertex_count += edge_count
            prepared_count += 1

            if prepared_count % progress_step == 0 or prepared_count == total_tiles:
                elapsed = time.perf_counter() - start_time
                print(
                    f"Subtile VBO prebuild: {prepared_count}/{total_tiles} tiles, "
                    f"{edge_vertex_count} edge vertices in {elapsed:.2f}s."
                )

        elapsed = time.perf_counter() - start_time
        print(
            f"Subtile VBO prebuild complete: {prepared_count} tiles, "
            f"{edge_vertex_count} edge vertices, total time {elapsed:.2f}s."
        )

    def run_frame(self):
        running = self.input_handler.handle_events(pygame.event.get())
        self.update()
        self.draw()
        return running

    def update(self):
        if self.battle_mode:
            return

        self.camera.update()
        self.light_angle = (self.light_angle + cfg.LIGHT_ROTATION_SPEED) % (2 * math.pi)

    def draw(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        if self.battle_mode:
            self.draw_battle_field()
            pygame.display.flip()
            self.clock.tick(self.fps)
            return

        self.camera.apply_transformations()

        if self.input_handler.click_to_process:
            x, y = self.input_handler.click_to_process
            clicked_tile = None
            clicked_subtile = None
            if self._should_pick_subtile():
                clicked_tile, clicked_subtile = picking.get_subtile_at_pos(
                    x,
                    y,
                    self.width,
                    self.height,
                    self.camera,
                    self.game_world
                )
                if clicked_tile is not None and clicked_subtile is None:
                    self.game_world.ensure_subtiles_generated([clicked_tile])
                    clicked_tile, clicked_subtile = picking.get_subtile_at_pos(
                        x,
                        y,
                        self.width,
                        self.height,
                        self.camera,
                        self.game_world
                    )
            else:
                clicked_tile = picking.get_tile_at_pos(x, y, self.width, self.height, self.camera, self.game_world)
            self.input_handler.click_to_process = None

            if clicked_subtile is not None:
                self.selected_tile = clicked_tile
                self.selected_subtile = clicked_subtile
            elif clicked_tile:
                self.selected_subtile = None
                if self.selected_unit:
                    if self.selected_unit.move_to(clicked_tile):
                        self.selected_unit = None # Deselect after moving
                    else:
                        # If the clicked tile is not a valid move, check if it has a unit to select
                        if clicked_tile.unit:
                            self.selected_unit = clicked_tile.unit
                        else:
                            self.selected_unit = None # Deselect if clicking on empty tile
                elif clicked_tile.unit:
                    self.selected_unit = clicked_tile.unit
                
                self.selected_tile = clicked_tile

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

        self.draw_subtiles()
        self.draw_selected_tile()
        self.draw_units()
        self.draw_possible_moves()
        self.draw_ui()

        if self.debug_mode:
            self.draw_debug_info()

        pygame.display.flip()
        self.clock.tick(self.fps)

    def toggle_battle_mode(self):
        if self.battle_mode:
            self.battle_mode = False
            self.active_battle_subtile = None
            self.battle_field_vbo_key = None
            return

        if self.selected_tile is None or self.selected_subtile is None:
            return

        self.active_battle_subtile = self.selected_subtile
        self.active_battle_subtile.ensure_battle_field()
        self.active_battle_rotation = self._get_screen_aligned_subtile_rotation(self.selected_tile, self.selected_subtile)
        self.battle_pan = np.array([0.0, 0.0], dtype=np.float32)
        self.battle_zoom = 1.0
        self.selected_battle_hex_index = None
        self.battle_field_vbo_key = None
        self.game_world.persist_tile_subtiles(self.selected_tile)
        self.battle_mode = True

    def handle_battle_mouse_down(self, event):
        if event.button == 1:
            self.input_handler.mouse_dragging = True
            self.input_handler.mouse_down_pos = event.pos
        elif event.button == 4:
            self.adjust_battle_zoom(cfg.BATTLE_FIELD_ZOOM_STEP, event.pos)
        elif event.button == 5:
            self.adjust_battle_zoom(1.0 / cfg.BATTLE_FIELD_ZOOM_STEP, event.pos)

    def handle_battle_mouse_up(self, event):
        if event.button != 1:
            return

        if self.input_handler.mouse_down_pos:
            dist_sq = (
                (event.pos[0] - self.input_handler.mouse_down_pos[0]) ** 2 +
                (event.pos[1] - self.input_handler.mouse_down_pos[1]) ** 2
            )
            if dist_sq < 10:
                self.select_battle_hex_at_pos(event.pos)
        self.input_handler.mouse_dragging = False
        self.input_handler.mouse_down_pos = None

    def handle_battle_mouse_motion(self, event):
        if not self.input_handler.mouse_dragging:
            return

        aspect = self.width / self.height if self.height else 1.0
        rel_x, rel_y = event.rel
        self.battle_pan += np.array([
            (rel_x / max(self.width, 1)) * 2.0 * aspect,
            (-rel_y / max(self.height, 1)) * 2.0,
        ], dtype=np.float32) * cfg.BATTLE_FIELD_PAN_SPEED
        self.battle_field_vbo_key = None

    def adjust_battle_zoom(self, factor, mouse_pos=None):
        old_zoom = self.battle_zoom
        new_zoom = float(np.clip(old_zoom * factor, cfg.BATTLE_FIELD_MIN_ZOOM, cfg.BATTLE_FIELD_MAX_ZOOM))
        if abs(new_zoom - old_zoom) <= 1e-8:
            return

        if mouse_pos is not None:
            before = self._screen_to_battle_world(mouse_pos)
            self.battle_zoom = new_zoom
            after = self._screen_to_battle_world(mouse_pos)
            self.battle_pan += (after - before) * new_zoom
        else:
            self.battle_zoom = new_zoom
        self.battle_field_vbo_key = None

    def select_battle_hex_at_pos(self, mouse_pos):
        battle_field = self.active_battle_subtile.battle_field if self.active_battle_subtile else None
        if not battle_field:
            return

        world_point = self._screen_to_battle_world(mouse_pos)
        hexes = battle_field.get("hexes", [])
        for index, hex_polygon in enumerate(hexes):
            polygon = [np.asarray(point, dtype=np.float32) for point in hex_polygon]
            if self._battle_point_in_polygon(world_point, polygon):
                self.selected_battle_hex_index = index
                self.battle_field_vbo_key = None
                return
        self.selected_battle_hex_index = None
        self.battle_field_vbo_key = None

    def draw_battle_field(self):
        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_CULL_FACE)
        background = np.asarray(cfg.BATTLE_FIELD_BACKGROUND_COLOR, dtype=np.float32) / 255.0
        glClearColor(float(background[0]), float(background[1]), float(background[2]), 1.0)
        glClear(GL_COLOR_BUFFER_BIT)

        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        aspect = self.width / self.height if self.height else 1.0
        glOrtho(-aspect, aspect, -1.0, 1.0, -1.0, 1.0)

        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        battle_field = self.active_battle_subtile.battle_field if self.active_battle_subtile else None
        if battle_field:
            self._draw_battle_field_geometry(battle_field, aspect)

        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

        glEnable(GL_CULL_FACE)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glClearColor(
            cfg.BACKGROUND_COLOR[0] / 255.0,
            cfg.BACKGROUND_COLOR[1] / 255.0,
            cfg.BACKGROUND_COLOR[2] / 255.0,
            1.0
        )

    def _draw_battle_field_geometry(self, battle_field, aspect):
        polygon = [np.asarray(point, dtype=np.float32) for point in battle_field.get("polygon", [])]
        hexes = battle_field.get("hexes", [])
        if len(polygon) < 3:
            return

        transform = self._make_battle_field_transform(polygon, aspect)
        render_data = self._get_battle_field_render_data(battle_field, polygon, hexes, transform)
        self._draw_battle_field_render_data(render_data)

    def _get_battle_field_render_data(self, battle_field, polygon, hexes, transform):
        key = (
            id(battle_field),
            self.selected_battle_hex_index,
            round(float(self.battle_pan[0]), 6),
            round(float(self.battle_pan[1]), 6),
            round(float(self.battle_zoom), 6),
            round(float(self.active_battle_rotation), 6),
            self.width,
            self.height,
        )
        if self.battle_field_vbos is not None and self.battle_field_vbo_key == key:
            return self.battle_field_vbos

        render_data = self._build_battle_field_render_data(polygon, hexes, transform)
        self._upload_battle_field_render_data(render_data)
        self.battle_field_vbo_key = key
        return self.battle_field_vbos

    def _build_battle_field_render_data(self, polygon, hexes, transform):
        fill_color = np.asarray(cfg.BATTLE_FIELD_HEX_COLOR, dtype=np.float32) / 255.0
        selected_fill_color = np.asarray(cfg.BATTLE_FIELD_SELECTED_HEX_COLOR, dtype=np.float32) / 255.0
        edge_color = np.asarray(cfg.BATTLE_FIELD_HEX_EDGE_COLOR, dtype=np.float32) / 255.0
        boundary_color = np.asarray(cfg.BATTLE_FIELD_BOUNDARY_COLOR, dtype=np.float32) / 255.0
        fill_vertices = []
        fill_colors = []
        line_vertices = []
        line_colors = []
        boundary_vertices = []
        boundary_colors = []

        for hex_index, hex_polygon in enumerate(hexes):
            if len(hex_polygon) < 3:
                continue
            color = selected_fill_color if hex_index == self.selected_battle_hex_index else fill_color
            transformed_hex = [transform(point) for point in hex_polygon]
            for index in range(1, len(transformed_hex) - 1):
                fill_vertices.extend([transformed_hex[0], transformed_hex[index], transformed_hex[index + 1]])
                fill_colors.extend([color, color, color])
        
            for index in range(len(transformed_hex)):
                line_vertices.extend([transformed_hex[index], transformed_hex[(index + 1) % len(transformed_hex)]])
                line_colors.extend([edge_color, edge_color])

        transformed_boundary = [transform(point) for point in polygon]
        for index in range(len(transformed_boundary)):
            boundary_vertices.extend([
                transformed_boundary[index],
                transformed_boundary[(index + 1) % len(transformed_boundary)]
            ])
            boundary_colors.extend([boundary_color, boundary_color])

        return {
            "fill_vertices": np.asarray(fill_vertices, dtype=np.float32),
            "fill_colors": np.asarray(fill_colors, dtype=np.float32),
            "line_vertices": np.asarray(line_vertices, dtype=np.float32),
            "line_colors": np.asarray(line_colors, dtype=np.float32),
            "boundary_vertices": np.asarray(boundary_vertices, dtype=np.float32),
            "boundary_colors": np.asarray(boundary_colors, dtype=np.float32),
        }

    def _upload_battle_field_render_data(self, render_data):
        if self.battle_field_vbos is None:
            self.battle_field_vbos = {
                "fill_vertices": glGenBuffers(1),
                "fill_colors": glGenBuffers(1),
                "line_vertices": glGenBuffers(1),
                "line_colors": glGenBuffers(1),
                "boundary_vertices": glGenBuffers(1),
                "boundary_colors": glGenBuffers(1),
                "fill_count": 0,
                "line_count": 0,
                "boundary_count": 0,
            }

        for key in ("fill_vertices", "fill_colors", "line_vertices", "line_colors", "boundary_vertices", "boundary_colors"):
            glBindBuffer(GL_ARRAY_BUFFER, self.battle_field_vbos[key])
            glBufferData(GL_ARRAY_BUFFER, render_data[key], GL_DYNAMIC_DRAW)

        self.battle_field_vbos["fill_count"] = len(render_data["fill_vertices"])
        self.battle_field_vbos["line_count"] = len(render_data["line_vertices"])
        self.battle_field_vbos["boundary_count"] = len(render_data["boundary_vertices"])

    def _draw_battle_field_render_data(self, render_data):
        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_COLOR_ARRAY)

        if render_data["fill_count"] > 0:
            glBindBuffer(GL_ARRAY_BUFFER, render_data["fill_vertices"])
            glVertexPointer(2, GL_FLOAT, 0, None)
            glBindBuffer(GL_ARRAY_BUFFER, render_data["fill_colors"])
            glColorPointer(3, GL_FLOAT, 0, None)
            glDrawArrays(GL_TRIANGLES, 0, render_data["fill_count"])

        if render_data["line_count"] > 0:
            glLineWidth(1.0)
            glBindBuffer(GL_ARRAY_BUFFER, render_data["line_vertices"])
            glVertexPointer(2, GL_FLOAT, 0, None)
            glBindBuffer(GL_ARRAY_BUFFER, render_data["line_colors"])
            glColorPointer(3, GL_FLOAT, 0, None)
            glDrawArrays(GL_LINES, 0, render_data["line_count"])

        if render_data["boundary_count"] > 0:
            glLineWidth(3.0)
            glBindBuffer(GL_ARRAY_BUFFER, render_data["boundary_vertices"])
            glVertexPointer(2, GL_FLOAT, 0, None)
            glBindBuffer(GL_ARRAY_BUFFER, render_data["boundary_colors"])
            glColorPointer(3, GL_FLOAT, 0, None)
            glDrawArrays(GL_LINES, 0, render_data["boundary_count"])

        glDisableClientState(GL_COLOR_ARRAY)
        glDisableClientState(GL_VERTEX_ARRAY)

    def _make_battle_field_transform(self, polygon, aspect):
        polygon_array = np.asarray(polygon, dtype=np.float32)
        min_bounds = polygon_array.min(axis=0)
        max_bounds = polygon_array.max(axis=0)
        center = (min_bounds + max_bounds) * 0.5
        size = np.maximum(max_bounds - min_bounds, 1e-8)
        scale_x = (2.0 * aspect * cfg.BATTLE_FIELD_VIEW_SCALE) / float(size[0])
        scale_y = (2.0 * cfg.BATTLE_FIELD_VIEW_SCALE) / float(size[1])
        scale = min(scale_x, scale_y)
        self._battle_transform_center = center
        self._battle_transform_scale = scale

        def transform(point):
            point = np.asarray(point, dtype=np.float32)
            local = (point - center) * scale
            cos_angle = math.cos(self.active_battle_rotation)
            sin_angle = math.sin(self.active_battle_rotation)
            rotated = np.array([
                local[0] * cos_angle - local[1] * sin_angle,
                local[0] * sin_angle + local[1] * cos_angle,
            ], dtype=np.float32)
            return rotated * self.battle_zoom + self.battle_pan

        return transform

    def _screen_to_battle_world(self, mouse_pos):
        aspect = self.width / self.height if self.height else 1.0
        ndc = np.array([
            (mouse_pos[0] / max(self.width, 1)) * 2.0 * aspect - aspect,
            1.0 - (mouse_pos[1] / max(self.height, 1)) * 2.0,
        ], dtype=np.float32)
        local = (ndc - self.battle_pan) / max(self.battle_zoom, 1e-8)
        cos_angle = math.cos(-self.active_battle_rotation)
        sin_angle = math.sin(-self.active_battle_rotation)
        unrotated = np.array([
            local[0] * cos_angle - local[1] * sin_angle,
            local[0] * sin_angle + local[1] * cos_angle,
        ], dtype=np.float32)
        return unrotated / max(getattr(self, "_battle_transform_scale", 1.0), 1e-8) + getattr(
            self,
            "_battle_transform_center",
            np.array([0.0, 0.0], dtype=np.float32)
        )

    def _battle_point_in_polygon(self, point, polygon):
        if len(polygon) < 3:
            return False

        inside = False
        j = len(polygon) - 1
        for i in range(len(polygon)):
            pi = polygon[i]
            pj = polygon[j]
            intersects = ((pi[1] > point[1]) != (pj[1] > point[1])) and (
                point[0] < (pj[0] - pi[0]) * (point[1] - pi[1]) / ((pj[1] - pi[1]) + 1e-12) + pi[0]
            )
            if intersects:
                inside = not inside
            j = i
        return inside

    def _get_screen_aligned_subtile_rotation(self, tile, subtile):
        if tile is None or subtile is None or len(subtile.vertices) < 2:
            return 0.0

        world_direction = self._get_subtile_primary_direction_world(subtile)
        screen_direction = self._project_world_direction_to_screen(world_direction)
        local_direction = self._get_battle_field_primary_direction_local(subtile)
        if screen_direction is None or local_direction is None:
            return 0.0

        screen_angle = math.atan2(screen_direction[1], screen_direction[0])
        local_angle = math.atan2(local_direction[1], local_direction[0])
        return screen_angle - local_angle

    def _get_subtile_primary_direction_world(self, subtile):
        vertices = [np.asarray(vertex, dtype=np.float32) for vertex in subtile.vertices]
        center = np.mean(vertices, axis=0)
        best_direction = None
        best_distance_sq = -1.0
        for vertex in vertices:
            direction = vertex - center
            distance_sq = float(np.dot(direction, direction))
            if distance_sq > best_distance_sq:
                best_distance_sq = distance_sq
                best_direction = direction

        if best_direction is None or np.linalg.norm(best_direction) <= 1e-8:
            return None
        return best_direction

    def _project_world_direction_to_screen(self, direction):
        if direction is None:
            return None

        rotation_x = np.array([
            [1, 0, 0],
            [0, math.cos(self.camera.angle_x), -math.sin(self.camera.angle_x)],
            [0, math.sin(self.camera.angle_x), math.cos(self.camera.angle_x)]
        ], dtype=np.float32)
        rotation_y = np.array([
            [math.cos(self.camera.angle_y), 0, math.sin(self.camera.angle_y)],
            [0, 1, 0],
            [-math.sin(self.camera.angle_y), 0, math.cos(self.camera.angle_y)]
        ], dtype=np.float32)
        rotated_direction = rotation_x @ (rotation_y @ np.asarray(direction, dtype=np.float32))
        screen_direction = np.array([rotated_direction[0], rotated_direction[1]], dtype=np.float32)
        norm = np.linalg.norm(screen_direction)
        if norm <= 1e-8:
            return None
        return screen_direction / norm

    def _get_battle_field_primary_direction_local(self, subtile):
        battle_field = subtile.battle_field
        if not battle_field:
            return None

        polygon = [np.asarray(point, dtype=np.float32) for point in battle_field.get("polygon", [])]
        if len(polygon) < 2:
            return None

        center = np.mean(np.asarray(polygon, dtype=np.float32), axis=0)
        best_direction = None
        best_distance_sq = -1.0
        for point in polygon:
            direction = point - center
            distance_sq = float(np.dot(direction, direction))
            if distance_sq > best_distance_sq:
                best_distance_sq = distance_sq
                best_direction = direction

        if best_direction is None or np.linalg.norm(best_direction) <= 1e-8:
            return None
        return best_direction

    def draw_selected_tile(self):
        if self.selected_subtile is not None:
            glDisable(GL_LIGHTING)
            glColor3f(1.0, 1.0, 0.0)
            glLineWidth(3.0)

            glBegin(GL_LINE_LOOP)
            for vertex in self.selected_subtile.vertices:
                glVertex3fv(np.asarray(vertex, dtype=np.float32) * 1.0035)
            glEnd()

            glEnable(GL_LIGHTING)
        elif self.selected_tile:
            glDisable(GL_LIGHTING)
            glColor3f(1.0, 1.0, 0.0) # Yellow
            glLineWidth(3.0)

            glBegin(GL_LINE_LOOP)
            for vertex in self.selected_tile.vertices:
                v = vertex.to_np() * 1.001
                glVertex3fv(v)
            glEnd()
            
            glEnable(GL_LIGHTING)

    def draw_subtiles(self):
        should_render_subtiles = self._should_render_subtiles()
        if not should_render_subtiles and not cfg.SUBTILE_DEBUG_DRAW_POINTS:
            return

        aspect_ratio = self.width / self.height if self.height else 1.0
        visible_tiles = self.game_world.get_visible_tiles_for_subtiles(self.camera, aspect_ratio)
        if not visible_tiles:
            return

        if should_render_subtiles:
            self.game_world.ensure_subtiles_generated(visible_tiles)

        visible_subtile_vbos = [
            (tile, prepared_vbo)
            for tile in visible_tiles
            if (prepared_vbo := self._get_subtile_edge_vbo(tile)) is not None
        ]
        subtile_alpha = self._get_subtile_edge_alpha()
        if (not visible_subtile_vbos or subtile_alpha <= 0.0) and not cfg.SUBTILE_DEBUG_DRAW_POINTS:
            return

        glDisable(GL_LIGHTING)
        glEnable(GL_DEPTH_TEST)

        if visible_subtile_vbos and subtile_alpha > 0.0:
            glLineWidth(1.2)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glEnableClientState(GL_VERTEX_ARRAY)
            for tile, (edge_vbo, edge_count) in visible_subtile_vbos:
                edge_color = self._get_subtile_edge_color(tile)
                glColor4f(float(edge_color[0]), float(edge_color[1]), float(edge_color[2]), float(subtile_alpha))
                glBindBuffer(GL_ARRAY_BUFFER, edge_vbo)
                glVertexPointer(3, GL_FLOAT, 0, None)
                glDrawArrays(GL_LINES, 0, edge_count)
            glDisableClientState(GL_VERTEX_ARRAY)
            glDisable(GL_BLEND)

        if cfg.SUBTILE_DEBUG_DRAW_POINTS:
            self._draw_subtile_debug_points(visible_tiles)

        glEnable(GL_LIGHTING)

    def _should_render_subtiles(self):
        if cfg.SUBTILE_RENDER_ALWAYS:
            return True

        reveal_zoom = cfg.MIN_ZOOM + cfg.SUBTILE_VISIBILITY_MARGIN
        return self.camera.zoom <= reveal_zoom

    def _get_subtile_edge_alpha(self):
        zoom_range = cfg.MAX_ZOOM - cfg.MIN_ZOOM
        if zoom_range <= 1e-8:
            return 1.0

        zoom_t = (self.camera.zoom - cfg.MIN_ZOOM) / zoom_range
        fade_start = float(np.clip(cfg.SUBTILE_FADE_START_FRACTION, 0.0, 1.0))
        fade_end = float(np.clip(cfg.SUBTILE_FADE_END_FRACTION, fade_start + 1e-6, 1.0))
        if zoom_t <= fade_start:
            return 1.0
        if zoom_t >= fade_end:
            return 0.0

        fade_t = (zoom_t - fade_start) / (fade_end - fade_start)
        return float(1.0 - fade_t)

    def _should_pick_subtile(self):
        return self._should_render_subtiles() and self._get_subtile_edge_alpha() >= cfg.SUBTILE_PICK_FULL_VISIBILITY_ALPHA

    def _get_subtile_edge_vbo(self, tile):
        if not tile.subtiles:
            return None

        cached_vbo = self.subtile_edge_vbos.get(tile.id)
        subtile_count = len(tile.subtiles)
        subtile_version = getattr(tile, "subtile_version", 0)
        if cached_vbo is not None and cached_vbo[2] == subtile_count and cached_vbo[3] == subtile_version:
            return cached_vbo[0], cached_vbo[1]

        edge_vertices = []
        seen_edges = set()

        for subtile in tile.subtiles:
            if len(subtile.vertices) < 2:
                continue
            for index in range(len(subtile.vertices)):
                raw_start = subtile.vertices[index]
                raw_end = subtile.vertices[(index + 1) % len(subtile.vertices)]
                if self._is_tile_boundary_edge(tile, raw_start, raw_end):
                    continue

                start = raw_start * 1.0025
                end = raw_end * 1.0025
                if np.sum((start - end) * (start - end)) <= 1e-12:
                    continue
                edge_key = self._subtile_edge_key(start, end)
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)
                edge_vertices.extend([start, end])

        edge_array = np.array(edge_vertices, dtype=np.float32)
        edge_count = len(edge_array)
        if edge_count == 0:
            return None

        edge_vbo = cached_vbo[0] if cached_vbo is not None else glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, edge_vbo)
        glBufferData(GL_ARRAY_BUFFER, edge_array, GL_STATIC_DRAW)
        self.subtile_edge_vbos[tile.id] = (edge_vbo, edge_count, subtile_count, subtile_version)
        return edge_vbo, edge_count

    def _get_subtile_edge_color(self, tile):
        base_color = np.asarray(tile.color, dtype=np.float32) / 255.0
        darken_factor = float(np.clip(cfg.SUBTILE_EDGE_COLOR_DARKEN_FACTOR, 0.0, 1.0))
        return np.clip(base_color * darken_factor, 0.0, 1.0)

    def _draw_subtile_debug_points(self, visible_tiles):
        visible_point_vbos = [
            prepared_vbo
            for tile in visible_tiles
            if (prepared_vbo := self._get_subtile_point_vbo(tile)) is not None
        ]
        if not visible_point_vbos:
            return

        point_color = np.asarray(cfg.SUBTILE_DEBUG_POINT_COLOR, dtype=np.float32) / 255.0
        glColor3f(float(point_color[0]), float(point_color[1]), float(point_color[2]))
        glPointSize(float(cfg.SUBTILE_DEBUG_POINT_SIZE))
        glEnableClientState(GL_VERTEX_ARRAY)
        for point_vbo, point_count in visible_point_vbos:
            glBindBuffer(GL_ARRAY_BUFFER, point_vbo)
            glVertexPointer(3, GL_FLOAT, 0, None)
            glDrawArrays(GL_POINTS, 0, point_count)
        glDisableClientState(GL_VERTEX_ARRAY)
        glPointSize(1.0)

    def _get_subtile_point_vbo(self, tile):
        if not tile.subtiles:
            return None

        cached_vbo = self.subtile_point_vbos.get(tile.id)
        point_source = getattr(tile, "subtile_seed_points", [])
        if not point_source:
            return None

        subtile_count = len(tile.subtiles)
        seed_count = len(point_source)
        subtile_version = getattr(tile, "subtile_version", 0)
        if (
            cached_vbo is not None and
            cached_vbo[2] == subtile_count and
            cached_vbo[3] == subtile_version and
            cached_vbo[4] == seed_count
        ):
            return cached_vbo[0], cached_vbo[1]

        point_vertices = []
        seen_points = set()
        for raw_point in point_source:
            point = raw_point * 1.003
            key = tuple(np.round(point, 6))
            if key in seen_points:
                continue
            seen_points.add(key)
            point_vertices.append(point)

        point_array = np.array(point_vertices, dtype=np.float32)
        point_count = len(point_array)
        if point_count == 0:
            return None

        point_vbo = cached_vbo[0] if cached_vbo is not None else glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, point_vbo)
        glBufferData(GL_ARRAY_BUFFER, point_array, GL_STATIC_DRAW)
        self.subtile_point_vbos[tile.id] = (point_vbo, point_count, subtile_count, subtile_version, seed_count)
        return point_vbo, point_count

    def _subtile_edge_key(self, start, end):
        a = tuple(np.round(start, 6))
        b = tuple(np.round(end, 6))
        return (a, b) if a <= b else (b, a)

    def _is_tile_boundary_edge(self, tile, start, end):
        boundary_epsilon_sq = 1e-8
        tile_vertices = [vertex.to_np() for vertex in tile.vertices]

        for index in range(len(tile_vertices)):
            segment_start = tile_vertices[index]
            segment_end = tile_vertices[(index + 1) % len(tile_vertices)]
            if (
                self._point_segment_distance_sq(start, segment_start, segment_end) <= boundary_epsilon_sq and
                self._point_segment_distance_sq(end, segment_start, segment_end) <= boundary_epsilon_sq
            ):
                return True

        return False

    def _point_segment_distance_sq(self, point, segment_start, segment_end):
        segment = segment_end - segment_start
        segment_length_sq = float(np.dot(segment, segment))
        if segment_length_sq <= 1e-16:
            return float(np.sum((point - segment_start) * (point - segment_start)))

        t = float(np.dot(point - segment_start, segment) / segment_length_sq)
        t = np.clip(t, 0.0, 1.0)
        closest = segment_start + segment * t
        return float(np.sum((point - closest) * (point - closest)))

    def draw_units(self):
        unit_model = self.models.get("unit")
        if not unit_model or not unit_model.mesh:
            return

        glColor3f(1.0, 1.0, 1.0)

        for unit in self.game_world.units:
            glPushMatrix()

            # -- Align model to tile normal --
            target_up = unit.tile.normal
            model_up = np.array([0.0, 1.0, 0.0])
            
            target_up_norm = np.linalg.norm(target_up)
            if target_up_norm > 1e-6:
                target_up = target_up / target_up_norm

            axis = np.cross(model_up, target_up)
            axis_norm = np.linalg.norm(axis)
            
            angle_rad = np.arccos(np.clip(np.dot(model_up, target_up), -1.0, 1.0))
            angle_deg = np.degrees(angle_rad)

            # -- Calculate position to place base of the model on the tile --
            scale = 0.02
            model_base_y = unit_model.mesh.bounds[0][1]
            offset_distance = -model_base_y * scale
            offset_vector = target_up * offset_distance
            position = unit.tile.center + offset_vector

            # -- Apply transformations --
            glTranslatef(position[0], position[1], position[2])

            if axis_norm > 1e-6:
                axis = axis / axis_norm
                glRotatef(angle_deg, axis[0], axis[1], axis[2])

            glScalef(scale, scale, scale)

            if unit == self.selected_unit:
                glMaterialfv(GL_FRONT, GL_EMISSION, [0.6, 0.3, 0.0, 1.0])
            else:
                glMaterialfv(GL_FRONT, GL_EMISSION, [0.0, 0.0, 0.0, 1.0])

            unit_model.draw()
            glPopMatrix()

        glMaterialfv(GL_FRONT, GL_EMISSION, [0.0, 0.0, 0.0, 1.0])

    def draw_possible_moves(self):
        if self.selected_unit:
            glDisable(GL_LIGHTING)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glColor4f(0.0, 1.0, 0.0, 0.5) # Semi-transparent green

            for neighbor in self.selected_unit.tile.neighbors:
                if not neighbor.unit:
                    glBegin(GL_TRIANGLE_FAN)
                    glVertex3fv(neighbor.center * 1.002)
                    for vertex in neighbor.vertices:
                        glVertex3fv(vertex.to_np() * 1.002)
                    glVertex3fv(neighbor.vertices[0].to_np() * 1.002)
                    glEnd()

            glDisable(GL_BLEND)
            glEnable(GL_LIGHTING)

    def draw_ui(self):
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

        panel_height = 100
        bg_surface = pygame.Surface((self.width, panel_height), pygame.SRCALPHA)
        bg_surface.fill((20, 20, 20, 180))
        
        if self.selected_tile:
            tile = self.selected_tile
            
            def render_text(text, x, y):
                text_surface = self.font.render(text, True, (255, 255, 255, 255))
                bg_surface.blit(text_surface, (x, y))
                return text_surface.get_height()

            y_offset = 10
            x_offset = 10
            y_offset += render_text(f"Selected Tile: {tile.id}", x_offset, y_offset)
            y_offset += render_text(f"Terrain: {tile.terrain_type.name}", x_offset, y_offset)
            y_offset += render_text(f"Height: {tile.height:.4f}", x_offset, y_offset)
            y_offset += render_text(f"Normal: ({tile.normal[0]:.2f}, {tile.normal[1]:.2f}, {tile.normal[2]:.2f})", x_offset, y_offset)
            y_offset += render_text(f"Neighbors: {len(tile.neighbors)}", x_offset, y_offset)

        data = pygame.image.tostring(bg_surface, "RGBA", True)
        glWindowPos2d(0, 0)
        glDrawPixels(self.width, panel_height, GL_RGBA, GL_UNSIGNED_BYTE, data)

        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()

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
