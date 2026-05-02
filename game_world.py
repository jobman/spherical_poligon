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
        self.subtile_cache_filename = f"subtile_cache_level_{self.subdivision_level}_v{cfg.SUBTILE_CACHE_VERSION}.pkl"
        self.subtile_cache = {}
        self.tile_centers = np.empty((0, 3), dtype=np.float32)
        self.tile_center_radius_sq = np.empty(0, dtype=np.float32)
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
        submitted_tile_ids = set()

        for tile in tiles:
            if tile.subtiles:
                continue

            cached_subtiles = self.subtile_cache.get(tile.id)
            if cached_subtiles is not None:
                tile.subtiles = self._deserialize_subtiles(cached_subtiles)
                self._polish_tile_edges_with_generated_neighbors(tile)
                continue

            if tile.id in self.subtile_futures:
                continue
            if len(self.subtile_futures) >= cfg.SUBTILE_MAX_IN_FLIGHT_TASKS:
                break

            forced_edge_points = self._get_neighbor_subtile_edge_points(tile)
            if not forced_edge_points and (self.subtile_futures or submitted_tile_ids):
                continue
            if any(neighbor.id in self.subtile_futures or neighbor.id in submitted_tile_ids for neighbor in tile.neighbors):
                continue

            self._submit_subtile_task(tile, forced_edge_points)
            submitted_tile_ids.add(tile.id)

    def get_visible_tiles_for_subtiles(self, camera, aspect_ratio, limit=cfg.SUBTILE_VISIBLE_TILE_LIMIT, screen_margin=cfg.SUBTILE_SCREEN_MARGIN):
        half_fov_y = math.radians(45.0) * 0.5
        tan_half_fov_y = math.tan(half_fov_y)
        camera_distance = camera.get_distance_to_center()
        rotated_centers = camera.rotate_world_points(self.tile_centers)
        camera_space_z = rotated_centers[:, 2] - camera_distance
        safe_camera_distance = max(camera_distance, 1e-6)
        horizon_z = self.tile_center_radius_sq / safe_camera_distance
        surface_mask = rotated_centers[:, 2] >= horizon_z - cfg.SUBTILE_HORIZON_MARGIN
        front_mask = (camera_space_z < -0.05) & surface_mask
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
                    self._polish_tile_edges_with_generated_neighbors(self.tiles[tile_id])
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
            self.tile_center_radius_sq = np.empty(0, dtype=np.float32)
            return
        self.tile_centers = np.array([tile.center for tile in self.tiles], dtype=np.float32)
        self.tile_center_radius_sq = np.einsum("ij,ij->i", self.tile_centers, self.tile_centers).astype(np.float32)

    def _start_subtile_executor(self):
        worker_count = self._get_subtile_worker_count()
        print(f"Starting subtile executor with {worker_count} worker(s).")
        self.subtile_executor = ProcessPoolExecutor(max_workers=worker_count)

    def _get_subtile_worker_count(self):
        if cfg.SUBTILE_BACKGROUND_WORKERS > 0:
            return cfg.SUBTILE_BACKGROUND_WORKERS

        cpu_count = os.cpu_count() or 1
        reserved_cores = max(1, cfg.SUBTILE_RESERVED_CPU_CORES)
        usable_cores = max(1, cpu_count - reserved_cores)
        return max(1, min(usable_cores, cfg.SUBTILE_MAX_BACKGROUND_WORKERS))

    def _submit_subtile_task(self, tile, forced_edge_points=None):
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
            cfg.SUBTILE_MAX_STAGNATION,
            forced_edge_points or []
        )
        self.subtile_futures[tile.id] = future

    def _get_neighbor_subtile_edge_points(self, tile):
        forced_points = []
        for neighbor in tile.neighbors:
            if not neighbor.subtiles:
                continue

            shared_edge = self._get_shared_edge(tile, neighbor)
            if shared_edge is None:
                continue

            edge_start, edge_end = shared_edge
            forced_points.extend(
                self._get_subtile_vertices_on_edge(neighbor, edge_start, edge_end)
            )

        return self._deduplicate_points(forced_points)

    def _get_shared_edge(self, tile, neighbor):
        common_vertices = [
            vertex.to_np()
            for vertex in tile.vertices
            if vertex in neighbor.vertices
        ]
        if len(common_vertices) < 2:
            return None

        return common_vertices[0], common_vertices[1]

    def _get_subtile_vertices_on_edge(self, tile, edge_start, edge_end):
        points = []
        edge_length_sq = float(np.dot(edge_end - edge_start, edge_end - edge_start))
        if edge_length_sq <= 1e-16:
            return points

        endpoint_epsilon_sq = 1e-10
        boundary_epsilon_sq = 1e-8
        for subtile in tile.subtiles:
            for vertex in subtile.vertices:
                point = np.asarray(vertex, dtype=np.float32)
                if self._point_segment_distance_sq(point, edge_start, edge_end) > boundary_epsilon_sq:
                    continue
                if (
                    np.sum((point - edge_start) * (point - edge_start)) <= endpoint_epsilon_sq or
                    np.sum((point - edge_end) * (point - edge_end)) <= endpoint_epsilon_sq
                ):
                    continue
                points.append(point)

        return points

    def _deduplicate_points(self, points):
        deduplicated = []
        seen = set()
        for point in points:
            key = tuple(np.round(point, 7))
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(np.asarray(point, dtype=np.float32))
        return deduplicated

    def _point_segment_distance_sq(self, point, segment_start, segment_end):
        segment = segment_end - segment_start
        segment_length_sq = float(np.dot(segment, segment))
        if segment_length_sq <= 1e-16:
            return float(np.sum((point - segment_start) * (point - segment_start)))

        t = float(np.dot(point - segment_start, segment) / segment_length_sq)
        t = np.clip(t, 0.0, 1.0)
        closest = segment_start + segment * t
        return float(np.sum((point - closest) * (point - closest)))

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
            self._polish_tile_edges_with_generated_neighbors(self.tiles[tile_id])
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

    def _polish_tile_edges_with_generated_neighbors(self, tile):
        if not tile.subtiles:
            return

        changed_tiles = set()
        for neighbor in tile.neighbors:
            if not neighbor.subtiles:
                continue

            shared_edge = self._get_shared_edge(tile, neighbor)
            if shared_edge is None:
                continue

            if self._polish_shared_subtile_edge(tile, neighbor, shared_edge):
                changed_tiles.add(tile)
                changed_tiles.add(neighbor)

        for changed_tile in changed_tiles:
            changed_tile.subtile_version = getattr(changed_tile, "subtile_version", 0) + 1
            self.subtile_cache[changed_tile.id] = self._serialize_subtiles(changed_tile.subtiles)
            self.pending_cache_save_count += 1

    def _polish_shared_subtile_edge(self, tile, neighbor, shared_edge):
        edge_start, edge_end = shared_edge
        edge_points = []
        edge_points.extend(self._get_subtile_vertex_refs_on_edge(tile, edge_start, edge_end))
        edge_points.extend(self._get_subtile_vertex_refs_on_edge(neighbor, edge_start, edge_end))
        if len(edge_points) < 2:
            return False

        merge_distance = self._get_edge_polish_merge_distance(tile, neighbor)
        if merge_distance <= 0:
            return False

        parent = list(range(len(edge_points)))
        merge_distance_sq = merge_distance * merge_distance

        def find(index):
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        def union(left, right):
            left_root = find(left)
            right_root = find(right)
            if left_root != right_root:
                parent[right_root] = left_root

        for left_index in range(len(edge_points)):
            left_point = edge_points[left_index][3]
            for right_index in range(left_index + 1, len(edge_points)):
                right_point = edge_points[right_index][3]
                if np.sum((left_point - right_point) * (left_point - right_point)) <= merge_distance_sq:
                    union(left_index, right_index)

        clusters = defaultdict(list)
        for index, edge_point in enumerate(edge_points):
            clusters[find(index)].append(edge_point)

        changed = False
        for cluster in clusters.values():
            if len(cluster) < 2:
                continue

            representative = np.mean(np.asarray([item[3] for item in cluster], dtype=np.float64), axis=0).astype(np.float32)
            representative = self._closest_point_on_segment(representative, edge_start, edge_end)
            for _, subtile, vertex_index, point in cluster:
                if np.sum((point - representative) * (point - representative)) <= 1e-14:
                    continue
                subtile.vertices[vertex_index] = representative.copy()
                changed = True

        if changed:
            for changed_tile in (tile, neighbor):
                for subtile in changed_tile.subtiles:
                    subtile.vertices = self._clean_subtile_vertices(subtile.vertices)
                changed_tile.subtiles = [
                    subtile for subtile in changed_tile.subtiles
                    if len(subtile.vertices) >= 3
                ]

        return changed

    def _get_subtile_vertex_refs_on_edge(self, tile, edge_start, edge_end):
        refs = []
        endpoint_epsilon_sq = 1e-10
        boundary_epsilon_sq = 1e-8
        for subtile in tile.subtiles:
            for vertex_index, vertex in enumerate(subtile.vertices):
                point = np.asarray(vertex, dtype=np.float32)
                if self._point_segment_distance_sq(point, edge_start, edge_end) > boundary_epsilon_sq:
                    continue
                if (
                    np.sum((point - edge_start) * (point - edge_start)) <= endpoint_epsilon_sq or
                    np.sum((point - edge_end) * (point - edge_end)) <= endpoint_epsilon_sq
                ):
                    continue
                refs.append((tile, subtile, vertex_index, point))
        return refs

    def _get_edge_polish_merge_distance(self, tile, neighbor):
        edge_spacing = (
            self._get_tile_initial_edge_point_spacing(tile) +
            self._get_tile_initial_edge_point_spacing(neighbor)
        ) * 0.5
        return edge_spacing * cfg.SUBTILE_EDGE_POLISH_MERGE_SPACING_FACTOR

    def _get_tile_initial_edge_point_spacing(self, tile):
        vertices = [vertex.to_np() for vertex in tile.vertices]
        if len(vertices) < 2:
            return 0.0

        edge_lengths = [
            np.linalg.norm(vertices[(index + 1) % len(vertices)] - vertices[index])
            for index in range(len(vertices))
        ]
        average_edge_length = float(np.mean(edge_lengths))
        min_distance = average_edge_length * cfg.SUBTILE_MIN_DISTANCE_FACTOR
        return max(min_distance, average_edge_length * cfg.SUBTILE_EDGE_POINT_SPACING_FACTOR)

    def _clean_subtile_vertices(self, vertices, distance_epsilon=1e-8, collinear_epsilon=1e-10):
        cleaned = []
        for vertex in vertices:
            point = np.asarray(vertex, dtype=np.float32)
            if cleaned and np.sum((point - cleaned[-1]) * (point - cleaned[-1])) <= distance_epsilon * distance_epsilon:
                continue
            cleaned.append(point)

        if len(cleaned) > 1 and np.sum((cleaned[0] - cleaned[-1]) * (cleaned[0] - cleaned[-1])) <= distance_epsilon * distance_epsilon:
            cleaned.pop()
        if len(cleaned) < 3:
            return cleaned

        result = []
        for index, point in enumerate(cleaned):
            previous = cleaned[index - 1]
            following = cleaned[(index + 1) % len(cleaned)]
            edge_a = point - previous
            edge_b = following - point
            cross = np.linalg.norm(np.cross(edge_a, edge_b))
            if cross <= collinear_epsilon and np.dot(edge_a, edge_b) >= 0:
                continue
            result.append(point)
        return result

    def _closest_point_on_segment(self, point, segment_start, segment_end):
        segment = segment_end - segment_start
        segment_length_sq = float(np.dot(segment, segment))
        if segment_length_sq <= 1e-16:
            return np.asarray(segment_start, dtype=np.float32)

        t = float(np.dot(point - segment_start, segment) / segment_length_sq)
        t = np.clip(t, 0.0, 1.0)
        return np.asarray(segment_start + segment * t, dtype=np.float32)

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
