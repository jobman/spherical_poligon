import math
from collections import defaultdict
import numpy as np
from geometry import Vertex
from tile import Tile

class GameWorld:
    def __init__(self, subdivision_level=2):
        self.subdivision_level = subdivision_level
        self.tiles = []
        self.vertices = []
        self._create_goldberg_polyhedron()

        # Pre-compute numpy arrays for rendering performance
        self.original_vertices = np.array([v.to_np() for v in self.vertices])
        self.face_indices = [[self.vertices.index(v) for v in tile.vertices] for tile in self.tiles]
        self.face_colors = np.array([tile.color for tile in self.tiles])
        self.face_normals = np.array([tile.normal for tile in self.tiles])

    def _create_icosahedron(self):
        t = (1.0 + math.sqrt(5.0)) / 2.0
        verts = [
            Vertex(-1, t, 0), Vertex(1, t, 0), Vertex(-1, -t, 0), Vertex(1, -t, 0),
            Vertex(0, -1, t), Vertex(0, 1, t), Vertex(0, -1, -t), Vertex(0, 1, -t),
            Vertex(t, 0, -1), Vertex(t, 0, 1), Vertex(-t, 0, -1), Vertex(-t, 0, 1)
        ]
        for v in verts: v.normalize()

        faces_indices = [
            0, 11, 5,  0, 5, 1,  0, 1, 7,  0, 7, 10,  0, 10, 11,
            1, 5, 9,  5, 11, 4,  11, 10, 2,  10, 7, 6,  7, 1, 8,
            3, 9, 4,  3, 4, 2,  3, 2, 6,  3, 6, 8,  3, 8, 9,
            4, 9, 5,  2, 4, 11,  6, 2, 10,  8, 6, 7,  9, 8, 1
        ]
        
        class Face:
            def __init__(self, vertices):
                self.vertices = vertices

        class Polyhedron:
            def __init__(self, vertices, faces):
                self.vertices = vertices
                self.faces = faces

        return Polyhedron(verts, [Face([verts[i] for i in faces_indices[j:j+3]]) for j in range(0, len(faces_indices), 3)])

    def _subdivide(self, poly):
        new_vertices = list(poly.vertices)
        new_faces = []
        midpoint_cache = {}

        for face in poly.faces:
            v1, v2, v3 = face.vertices

            def get_midpoint(p1, p2):
                key = tuple(sorted((poly.vertices.index(p1), poly.vertices.index(p2))))
                if key in midpoint_cache:
                    return midpoint_cache[key]
                
                mid_v = Vertex((p1.x + p2.x) / 2, (p1.y + p2.y) / 2, (p1.z + p2.z) / 2)
                mid_v.normalize()
                new_vertices.append(mid_v)
                midpoint_cache[key] = mid_v
                return mid_v

            m1 = get_midpoint(v1, v2)
            m2 = get_midpoint(v2, v3)
            m3 = get_midpoint(v3, v1)

            new_faces.append(type(face)([v1, m1, m3]))
            new_faces.append(type(face)([v2, m2, m1]))
            new_faces.append(type(face)([v3, m3, m2]))
            new_faces.append(type(face)([m1, m2, m3]))

        return type(poly)(new_vertices, new_faces)

    def _create_goldberg_polyhedron(self):
        if self.subdivision_level < 1: self.subdivision_level = 1
        
        geodesic = self._create_icosahedron()
        for _ in range(self.subdivision_level):
            geodesic = self._subdivide(geodesic)

        goldberg_verts = []
        face_centroid_map = {}
        for i, face in enumerate(geodesic.faces):
            c_x = sum(v.x for v in face.vertices) / 3
            c_y = sum(v.y for v in face.vertices) / 3
            c_z = sum(v.z for v in face.vertices) / 3
            centroid = Vertex(c_x, c_y, c_z)
            centroid.normalize()
            goldberg_verts.append(centroid)
            face_centroid_map[i] = centroid

        vert_to_face_idx_map = defaultdict(list)
        for i, face in enumerate(geodesic.faces):
            for v in face.vertices:
                vert_to_face_idx_map[v].append(i)

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
            
            color = np.array([240, 220, 220]) if len(new_face_verts_sorted) == 6 else np.array([210, 210, 240])
            
            p1, p2, p3 = new_face_verts_sorted[0].to_np(), new_face_verts_sorted[1].to_np(), new_face_verts_sorted[2].to_np()
            v1, v2 = p2 - p1, p3 - p1
            face_normal = np.cross(v1, v2)
            norm = np.linalg.norm(face_normal)
            if norm != 0:
                face_normal /= norm

            self.tiles.append(Tile(tile_id_counter, new_face_verts_sorted, face_normal, color))
            tile_id_counter += 1
