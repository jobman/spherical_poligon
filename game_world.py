import math
from collections import defaultdict
import numpy as np
from geometry import Vertex
from tile import Tile, TerrainType
import pickle
import os
from perlin_noise import PerlinNoise
import random
from river_generator import RiverGenerator

class GameWorld:
    def __init__(self, subdivision_level=4):
        self.subdivision_level = subdivision_level
        self.tiles = []
        self.vertices = [] # Tile vertices
        self.vert_to_tiles = defaultdict(list)
        self.vert_neighbors = defaultdict(list)

        # Unified geometry for rendering
        self.original_vertices = np.array([])
        self.face_indices = []
        self.face_colors = np.array([])
        self.face_normals = np.array([])

        cache_filename = f"world_cache_level_{self.subdivision_level}.pkl"

        if os.path.exists(cache_filename):
            print(f"Loading world from cache: {cache_filename}")
            with open(cache_filename, 'rb') as f:
                data = pickle.load(f)
                self.__dict__.update(data)
        else:
            print("Generating new world geometry...")
            self._create_goldberg_polyhedron()
            self._generate_terrain()
            self._build_vertex_neighbors()
            river_verts, river_faces, river_normals = self._generate_rivers()
            self._combine_geometry(river_verts, river_faces, river_normals)

            print(f"Saving world to cache: {cache_filename}")
            # Don't save transient data like vert_to_tiles
            transient_data = {"vert_to_tiles": self.vert_to_tiles, "vert_neighbors": self.vert_neighbors}
            del self.vert_to_tiles
            del self.vert_neighbors
            with open(cache_filename, 'wb') as f:
                pickle.dump(self.__dict__, f)
            # Restore transient data
            self.vert_to_tiles = transient_data["vert_to_tiles"]
            self.vert_neighbors = transient_data["vert_neighbors"]

    def _combine_geometry(self, river_verts, river_faces, river_normals):
        print("Combining tile and river geometry...")
        tile_vertices_np = np.array([v.to_np() for v in self.vertices])
        river_vertices_np = np.array([v.to_np() for v in river_verts])

        # Combine vertices
        self.original_vertices = np.vstack([tile_vertices_np, river_vertices_np])
        
        # Combine faces (adjusting indices for rivers)
        tile_faces = [[self.vertices.index(v) for v in tile.vertices] for tile in self.tiles]
        river_faces_adjusted = (np.array(river_faces) + len(self.vertices)).tolist()
        self.face_indices = tile_faces + river_faces_adjusted

        # Combine colors
        tile_colors = np.array([tile.color for tile in self.tiles])
        river_color = np.array([60, 120, 200]) # Same as in renderer
        river_colors = np.tile(river_color, (len(river_faces), 1))
        self.face_colors = np.vstack([tile_colors, river_colors])

        # Combine normals
        tile_normals = np.array([tile.normal for tile in self.tiles])
        self.face_normals = np.vstack([tile_normals, river_normals])

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

    def _generate_rivers(self, num_rivers=150):
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

    def _create_icosahedron(self):
        t = (1.0 + math.sqrt(5.0)) / 2.0
        verts = [Vertex(-1,t,0), Vertex(1,t,0), Vertex(-1,-t,0), Vertex(1,-t,0), Vertex(0,-1,t), Vertex(0,1,t), Vertex(0,-1,-t), Vertex(0,1,-t), Vertex(t,0,-1), Vertex(t,0,1), Vertex(-t,0,-1), Vertex(-t,0,1)]
        for v in verts: v.normalize()
        faces_indices = [0,11,5,0,5,1,0,1,7,0,7,10,0,10,11,1,5,9,5,11,4,11,10,2,10,7,6,7,1,8,3,9,4,3,4,2,3,2,6,3,6,8,3,8,9,4,9,5,2,4,11,6,2,10,8,6,7,9,8,1]
        class Face: 
            def __init__(self, vertices): self.vertices = vertices
        class Polyhedron: 
            def __init__(self, vertices, faces): self.vertices, self.faces = vertices, faces
        return Polyhedron(verts, [Face([verts[i] for i in faces_indices[j:j+3]]) for j in range(0, len(faces_indices), 3)])

    def _subdivide(self, poly):
        new_vertices = list(poly.vertices)
        new_faces = []
        midpoint_cache = {}
        vert_map = {v: i for i, v in enumerate(poly.vertices)}
        def get_midpoint(p1, p2):
            key = tuple(sorted((vert_map[p1], vert_map[p2])))
            if key in midpoint_cache: return midpoint_cache[key]
            mid_v = Vertex((p1.x + p2.x) / 2, (p1.y + p2.y) / 2, (p1.z + p2.z) / 2); mid_v.normalize()
            new_vertices.append(mid_v)
            midpoint_cache[key] = mid_v
            return mid_v
        for face in poly.faces:
            v1, v2, v3 = face.vertices
            m1, m2, m3 = get_midpoint(v1, v2), get_midpoint(v2, v3), get_midpoint(v3, v1)
            new_faces.extend([type(face)([v1, m1, m3]), type(face)([v2, m2, m1]), type(face)([v3, m3, m2]), type(face)([m1, m2, m3])])
        return type(poly)(new_vertices, new_faces)

    def _create_goldberg_polyhedron(self):
        geodesic = self._create_icosahedron()
        for _ in range(self.subdivision_level):
            geodesic = self._subdivide(geodesic)

        goldberg_verts, face_centroid_map = [], {}
        for i, face in enumerate(geodesic.faces):
            c_x, c_y, c_z = sum(v.x for v in face.vertices)/3, sum(v.y for v in face.vertices)/3, sum(v.z for v in face.vertices)/3
            centroid = Vertex(c_x, c_y, c_z); centroid.normalize()
            goldberg_verts.append(centroid); face_centroid_map[i] = centroid

        vert_to_face_idx_map = defaultdict(list)
        for i, face in enumerate(geodesic.faces):
            for v in face.vertices: vert_to_face_idx_map[v].append(i)

        self.vertices = goldberg_verts
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
