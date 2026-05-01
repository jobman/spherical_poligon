import math
from collections import defaultdict
import numpy as np
from concurrent.futures import ProcessPoolExecutor
from geometry import Vertex
from tile import Tile, generate_serialized_subtiles_for_tile
from config import TerrainType
import pickle
import os
from perlin_noise import PerlinNoise
from river_generator import RiverGenerator
import config as cfg
from polyhedron_generator import PolyhedronGenerator
from render_data import RenderData
from spatial_hash_grid import SpatialHashGrid
from unit import Unit

class GameWorld:
    def __init__(self, subdivision_level=cfg.SUBDIVISION_LEVEL):
        self.subdivision_level = subdivision_level
        self.tiles = []
        self.vertices = [] # Tile vertices, also used for river graph
        self.units = []
        self.vert_to_tiles = defaultdict(list)
        self.vert_neighbors = defaultdict(list)
        self.river_paths = []
        self.river_flow = {}
        self.spatial_hash_grid = None
        self.subtile_cache_filename = f"subtile_cache_level_{self.subdivision_level}.pkl"
        self.subtile_cache = {}
        self.tile_centers = np.empty((0, 3), dtype=np.float32)
        self.pending_cache_save_count = 0
        self.subtile_executor = None
        self.subtile_futures = {}

        # For testing, create one unit
        # This line needs to be placed after tiles are initialized and the world is loaded/generated.
        # The original replace string had `self.load_or_generate_world()` which is not in the current file.
        # The instruction implies adding it in the constructor, so it's placed here as a placeholder.
        # A separate edit would be needed to add the `add_unit` method and place this call correctly.
        # self.add_unit(self.tiles[0], owner=None) # For testing

        cache_filename = f"world_cache_level_{self.subdivision_level}.pkl"

        if os.path.exists(cache_filename):
            print(f"Loading world from cache: {cache_filename}")
            with open(cache_filename, 'rb') as f:
                data = pickle.load(f)
                self.__dict__.update(data)
            self._build_neighbor_graph()
            self._build_vertex_neighbors()
        else:
            print("Generating new world geometry...")
            self._create_geometry()
            self._generate_terrain()
            self._build_vertex_neighbors()
            self.river_paths, self.river_flow = self._generate_rivers()

            print(f"Saving world to cache: {cache_filename}")
            transient_data = {"vert_to_tiles": self.vert_to_tiles}
            del self.vert_to_tiles
            with open(cache_filename, 'wb') as f:
                pickle.dump(self.__dict__, f)
            self.vert_to_tiles = transient_data["vert_to_tiles"]

        self._load_subtile_cache()
        self._build_tile_centers()
        self._start_subtile_executor()

        print(f"World created with {len(self.tiles)} tiles.")

        print("Building spatial hash grid...")
        self.spatial_hash_grid = SpatialHashGrid(self.tiles)

        self.add_unit(self.tiles[0], owner=None)

    def add_unit(self, tile, owner):
        unit = Unit(tile, owner)
        self.units.append(unit)

    def get_render_data(self):
        tile_vertices, tile_colors, tile_normals, edge_vertices = [], [], [], []

        for tile in self.tiles:
            if len(tile.vertices) < 3: continue
            v0 = tile.vertices[0].to_np()
            normal = tile.normal
            color = tile.color / 255.0

            for j in range(1, len(tile.vertices) - 1):
                v1 = tile.vertices[j].to_np()
                v2 = tile.vertices[j + 1].to_np()
                tile_vertices.extend([v0, v1, v2])
                tile_normals.extend([normal, normal, normal])
                tile_colors.extend([color, color, color])

            for j in range(len(tile.vertices)):
                v_start = tile.vertices[j].to_np()
                v_end = tile.vertices[(j + 1) % len(tile.vertices)].to_np()
                edge_vertices.extend([v_start, v_end])

        river_vertices, river_colors = [], []
        if self.river_paths:
            base_color = cfg.RIVER_COLOR / 255.0
            for path in self.river_paths:
                if len(path) < 2: continue
                for i in range(len(path) - 1):
                    v1 = path[i]
                    v2 = path[i+1]
                    river_vertices.extend([v1.to_np(), v2.to_np()])
                    river_colors.extend([base_color, base_color])

        return RenderData(
            tile_vertices=np.array(tile_vertices, dtype=np.float32),
            tile_colors=np.array(tile_colors, dtype=np.float32),
            tile_normals=np.array(tile_normals, dtype=np.float32),
            edge_vertices=np.array(edge_vertices, dtype=np.float32),
            subtile_vertices=np.array([], dtype=np.float32),
            subtile_colors=np.array([], dtype=np.float32),
            subtile_edge_vertices=np.array([], dtype=np.float32),
            river_vertices=np.array(river_vertices, dtype=np.float32),
            river_colors=np.array(river_colors, dtype=np.float32)
        )

    def _generate_terrain(self):
        self._build_neighbor_graph()
        self._assign_terrain_and_heights()

    def _build_neighbor_graph(self):
        print("Building tile neighbor graph...")
        self.vert_to_tiles.clear()
        for tile in self.tiles:
            for v in tile.vertices:
                self.vert_to_tiles[v].append(tile)

        for tile in self.tiles:
            tile.neighbors = []
            for v in tile.vertices:
                for neighbor in self.vert_to_tiles[v]:
                    if neighbor != tile and neighbor not in tile.neighbors:
                        tile.neighbors.append(neighbor)

    def _build_vertex_neighbors(self):
        print("Building vertex neighbor graph...")
        vert_neighbors_sets = defaultdict(set)
        for tile in self.tiles:
            for i in range(len(tile.vertices)):
                v1 = tile.vertices[i]
                v2 = tile.vertices[(i + 1) % len(tile.vertices)]
                vert_neighbors_sets[v1].add(v2)
                vert_neighbors_sets[v2].add(v1)
        self.vert_neighbors = {v: list(neighbors) for v, neighbors in vert_neighbors_sets.items()}

    def _generate_rivers(self, num_rivers=cfg.RIVER_COUNT):
        print(f"Generating rivers...")
        river_gen = RiverGenerator(self.vertices, self.vert_to_tiles, self.vert_neighbors)
        return river_gen.generate_rivers(num_rivers)

    def ensure_subtiles_generated(self, tiles):
        self._collect_completed_subtile_tasks()

        for tile in tiles:
            if tile.subtiles:
                continue

            cached_subtiles = self.subtile_cache.get(tile.id)
            if cached_subtiles is not None:
                tile.subtiles = self._deserialize_subtiles(cached_subtiles)
                continue

            if tile.id in self.subtile_futures:
                continue
            if len(self.subtile_futures) >= cfg.SUBTILE_MAX_IN_FLIGHT_TASKS:
                break
            self._submit_subtile_task(tile)

    def get_visible_tiles_for_subtiles(self, camera, aspect_ratio, limit=cfg.SUBTILE_VISIBLE_TILE_LIMIT, screen_margin=cfg.SUBTILE_SCREEN_MARGIN):
        half_fov_y = math.radians(45.0) * 0.5
        tan_half_fov_y = math.tan(half_fov_y)
        camera_distance = camera.get_distance_to_center()
        rotated_centers = camera.rotate_world_points(self.tile_centers)
        camera_space_z = rotated_centers[:, 2] - camera_distance
        front_mask = camera_space_z < -0.05
        if not np.any(front_mask):
            return []

        candidate_indices = np.flatnonzero(front_mask)
        candidate_centers = rotated_centers[candidate_indices]
        candidate_z = camera_space_z[candidate_indices]

        projected_half_height = -candidate_z * tan_half_fov_y
        projected_half_width = projected_half_height * aspect_ratio
        projection_mask = (projected_half_height > 1e-6) & (projected_half_width > 1e-6)
        if not np.any(projection_mask):
            return []

        candidate_indices = candidate_indices[projection_mask]
        candidate_centers = candidate_centers[projection_mask]
        candidate_z = candidate_z[projection_mask]
        projected_half_height = projected_half_height[projection_mask]
        projected_half_width = projected_half_width[projection_mask]

        ndc_x = candidate_centers[:, 0] / projected_half_width
        ndc_y = candidate_centers[:, 1] / projected_half_height
        screen_mask = (np.abs(ndc_x) <= screen_margin) & (np.abs(ndc_y) <= screen_margin)
        if not np.any(screen_mask):
            return []

        candidate_indices = candidate_indices[screen_mask]
        candidate_z = candidate_z[screen_mask]
        ndc_x = ndc_x[screen_mask]
        ndc_y = ndc_y[screen_mask]

        screen_distance_sq = ndc_x * ndc_x + ndc_y * ndc_y
        order = np.lexsort((-candidate_z, screen_distance_sq))
        selected_indices = candidate_indices[order[:limit]]
        return [self.tiles[int(index)] for index in selected_indices]

    def _load_subtile_cache(self):
        if not os.path.exists(self.subtile_cache_filename):
            return

        try:
            with open(self.subtile_cache_filename, 'rb') as f:
                cache_data = pickle.load(f)
        except Exception as exc:
            print(f"Could not load subtile cache: {exc}")
            return

        if not isinstance(cache_data, dict):
            return

        self.subtile_cache = cache_data

    def _save_subtile_cache(self):
        try:
            with open(self.subtile_cache_filename, 'wb') as f:
                pickle.dump(self.subtile_cache, f)
        except Exception as exc:
            print(f"Could not save subtile cache: {exc}")

    def flush_subtile_cache(self):
        self._collect_completed_subtile_tasks()
        if self.pending_cache_save_count > 0:
            self._save_subtile_cache()
            self.pending_cache_save_count = 0

    def shutdown(self):
        if self.subtile_executor is not None:
            remaining_futures = list(self.subtile_futures.values())
            for future in remaining_futures:
                try:
                    tile_id, serialized_subtiles = future.result()
                    self.subtile_cache[tile_id] = serialized_subtiles
                    self.tiles[tile_id].subtiles = self._deserialize_subtiles(serialized_subtiles)
                    self.pending_cache_save_count += 1
                except Exception as exc:
                    print(f"Could not finish subtile task during shutdown: {exc}")
            self.subtile_futures.clear()
            self.subtile_executor.shutdown(wait=True, cancel_futures=False)
            self.subtile_executor = None
        self.flush_subtile_cache()

    def _build_tile_centers(self):
        if not self.tiles:
            self.tile_centers = np.empty((0, 3), dtype=np.float32)
            return
        self.tile_centers = np.array([tile.center for tile in self.tiles], dtype=np.float32)

    def _start_subtile_executor(self):
        self.subtile_executor = ProcessPoolExecutor(max_workers=cfg.SUBTILE_BACKGROUND_WORKERS)

    def _submit_subtile_task(self, tile):
        if self.subtile_executor is None:
            return

        future = self.subtile_executor.submit(
            generate_serialized_subtiles_for_tile,
            tile.id,
            [vertex.to_np() for vertex in tile.vertices],
            tile.normal,
            cfg.SUBTILE_MIN_DISTANCE_FACTOR,
            cfg.SUBTILE_EDGE_POINT_SPACING_FACTOR,
            cfg.SUBTILE_MAX_INTERIOR_POINTS,
            cfg.SUBTILE_CANDIDATE_BATCH_SIZE,
            cfg.SUBTILE_MAX_STAGNATION
        )
        self.subtile_futures[tile.id] = future

    def _collect_completed_subtile_tasks(self):
        if not self.subtile_futures:
            return

        completed_tile_ids = []
        for tile_id, future in self.subtile_futures.items():
            if not future.done():
                continue
            completed_tile_ids.append(tile_id)
            try:
                _, serialized_subtiles = future.result()
            except Exception as exc:
                print(f"Could not generate subtiles for tile {tile_id}: {exc}")
                continue

            self.subtile_cache[tile_id] = serialized_subtiles
            self.tiles[tile_id].subtiles = self._deserialize_subtiles(serialized_subtiles)
            self.pending_cache_save_count += 1

        for tile_id in completed_tile_ids:
            self.subtile_futures.pop(tile_id, None)

    def _serialize_subtiles(self, subtiles):
        serialized = []
        for subtile in subtiles:
            serialized.append([
                np.asarray(vertex, dtype=np.float32)
                for vertex in subtile.vertices
            ])
        return serialized

    def _deserialize_subtiles(self, serialized_subtiles):
        from tile import SubTile

        return [
            SubTile(
                vertices=[np.asarray(vertex, dtype=np.float32) for vertex in polygon],
                color=np.array([0, 0, 0], dtype=np.float32)
            )
            for polygon in serialized_subtiles
        ]

    def _assign_terrain_and_heights(self):
        print("Assigning terrain and heights...")
        land_noise = PerlinNoise(octaves=8, seed=1)
        height_noise = PerlinNoise(octaves=12, seed=2)

        for tile in self.tiles:
            tile_center = tile.center
            is_land = land_noise((tile_center * 0.5).tolist()) > 0.05
            lat = math.asin(tile_center[1]) * 180 / math.pi

            if is_land:
                tile.height = (height_noise((tile_center * 2.0).tolist()) + 1) / 2
                if abs(lat) > 75: tile.terrain_type = TerrainType.SNOW
                elif abs(lat) > 60: tile.terrain_type = TerrainType.TUNDRA
                elif tile.height > 0.8: tile.terrain_type = TerrainType.MOUNTAINS
                elif tile.height > 0.6: tile.terrain_type = TerrainType.HILLS
                elif abs(lat) > 45: tile.terrain_type = TerrainType.FOREST
                elif abs(lat) > 30: tile.terrain_type = TerrainType.GRASSLAND
                elif abs(lat) > 15: tile.terrain_type = TerrainType.SAVANNA
                else: tile.terrain_type = TerrainType.DESERT
            else:
                tile.height = 0
                if abs(lat) > 80: tile.terrain_type = TerrainType.ICE
                else:
                    is_coastal = any(n.height > 0 for n in tile.neighbors)
                    if is_coastal: tile.terrain_type = TerrainType.COAST
                    else: tile.terrain_type = TerrainType.OCEAN

    def _create_geometry(self):
        poly_gen = PolyhedronGenerator()
        self.vertices, vert_to_face_idx_map, face_centroid_map = poly_gen.create_goldberg_polyhedron(self.subdivision_level)

        tile_id_counter = 0
        for geo_vert, face_indices in vert_to_face_idx_map.items():
            new_face_verts_unsorted = [face_centroid_map[i] for i in face_indices]
            normal = geo_vert.to_np()
            u_axis = np.cross(normal, [0, 1, 0])
            if np.linalg.norm(u_axis) < 1e-5: u_axis = np.cross(normal, [1, 0, 0])
            u_axis /= np.linalg.norm(u_axis)
            v_axis = np.cross(normal, u_axis)
            def get_angle(v): 
                p_vec = v.to_np()
                return math.atan2(np.dot(p_vec, v_axis), np.dot(p_vec, u_axis))
            new_face_verts_sorted = sorted(new_face_verts_unsorted, key=get_angle)
            
            p1, p2, p3 = new_face_verts_sorted[0].to_np(), new_face_verts_sorted[1].to_np(), new_face_verts_sorted[2].to_np()
            v1, v2 = p2 - p1, p3 - p1
            face_normal = np.cross(v1, v2)
            if (norm := np.linalg.norm(face_normal)) != 0: face_normal /= norm

            self.tiles.append(Tile(tile_id_counter, new_face_verts_sorted, face_normal))
            tile_id_counter += 1
