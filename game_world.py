import math
from collections import defaultdict
import numpy as np
from geometry import Vertex
from tile import Tile
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

    def _assign_terrain_and_heights(self):
        print("Assigning terrain and heights...")
        land_noise = PerlinNoise(octaves=8, seed=1)
        height_noise = PerlinNoise(octaves=12, seed=2)

        for tile in self.tiles:
            tile_center = np.mean([v.to_np() for v in tile.vertices], axis=0)
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