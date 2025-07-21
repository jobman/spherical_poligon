import math
from collections import defaultdict
import numpy as np
from geometry import Vertex

class PolyhedronGenerator:

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

    def create_goldberg_polyhedron(self, subdivision_level):
        geodesic = self._create_icosahedron()
        for _ in range(subdivision_level):
            geodesic = self._subdivide(geodesic)

        goldberg_verts, face_centroid_map = [], {}
        for i, face in enumerate(geodesic.faces):
            c_x, c_y, c_z = sum(v.x for v in face.vertices)/3, sum(v.y for v in face.vertices)/3, sum(v.z for v in face.vertices)/3
            centroid = Vertex(c_x, c_y, c_z); centroid.normalize()
            goldberg_verts.append(centroid); face_centroid_map[i] = centroid

        vert_to_face_idx_map = defaultdict(list)
        for i, face in enumerate(geodesic.faces):
            for v in face.vertices: vert_to_face_idx_map[v].append(i)
        
        return goldberg_verts, vert_to_face_idx_map, face_centroid_map
