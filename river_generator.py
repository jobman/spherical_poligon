
import random
from collections import defaultdict
import numpy as np
from geometry import Vertex

class RiverGenerator:
    def __init__(self, vertices, vert_to_tiles, vert_neighbors):
        self.world_vertices = vertices
        self.vert_to_tiles = vert_to_tiles
        self.vert_neighbors = vert_neighbors
        
        self.vertex_terrain = {}
        self.downstream_map = {}
        self.vertex_flow = defaultdict(float)

    def _classify_vertices(self):
        for vertex in self.world_vertices:
            is_sea = any(tile.is_water() for tile in self.vert_to_tiles[vertex])
            self.vertex_terrain[vertex] = 'sea' if is_sea else 'land'

    def _find_inland_sources(self, num_rivers):
        candidates = []
        for vertex in self.world_vertices:
            if self.vertex_terrain[vertex] == 'land':
                if all(self.vertex_terrain[n] == 'land' for n in self.vert_neighbors[vertex]):
                    avg_height = sum(t.height for t in self.vert_to_tiles[vertex]) / len(self.vert_to_tiles[vertex])
                    if avg_height > 0.6:
                        candidates.append(vertex)
        
        if not candidates:
            candidates = [v for v in self.world_vertices if self.vertex_terrain[v] == 'land' and all(self.vertex_terrain[n] == 'land' for n in self.vert_neighbors[v])]

        return random.sample(candidates, min(num_rivers, len(candidates)))

    def _build_flow_network(self, sources):
        river_vertices = set()
        for source in sources:
            if source in river_vertices: continue
            
            current_vertex = source
            path = [current_vertex]
            river_vertices.add(current_vertex)

            for _ in range(200):
                if current_vertex in self.downstream_map: break

                neighbors = self.vert_neighbors[current_vertex]
                valid_neighbors = [n for n in neighbors if n not in path]

                sea_neighbors = [n for n in valid_neighbors if self.vertex_terrain[n] == 'sea']
                if sea_neighbors:
                    next_vertex = random.choice(sea_neighbors)
                    self.downstream_map[current_vertex] = next_vertex
                    break

                if not valid_neighbors: break
                
                next_vertex = random.choice(valid_neighbors)
                self.downstream_map[current_vertex] = next_vertex
                river_vertices.add(next_vertex)
                path.append(next_vertex)
                current_vertex = next_vertex

    def _calculate_flow(self):
        in_degree = defaultdict(int)
        all_river_verts = set(self.downstream_map.keys()) | set(self.downstream_map.values())

        for u, v in self.downstream_map.items():
            in_degree[v] += 1

        queue = [v for v in all_river_verts if in_degree[v] == 0]
        for v in queue:
            self.vertex_flow[v] = 1.0

        head = 0
        while head < len(queue):
            u = queue[head]; head += 1
            v = self.downstream_map.get(u)
            if v:
                self.vertex_flow[v] += self.vertex_flow[u]
                in_degree[v] -= 1
                if in_degree[v] == 0: queue.append(v)

    def _create_river_geometry(self):
        river_verts = []
        river_faces = []
        river_normals = []
        vert_map = {}

        def get_or_add_vert(v_pos):
            key = tuple(round(c, 5) for c in v_pos)
            if key in vert_map:
                return vert_map[key]
            idx = len(river_verts)
            river_verts.append(Vertex(v_pos[0], v_pos[1], v_pos[2]))
            vert_map[key] = idx
            return idx

        max_flow = max(self.vertex_flow.values()) if self.vertex_flow else 1.0

        for u, v in self.downstream_map.items():
            flow = self.vertex_flow.get(v, 1.0)
            # Remapped width for better visual scaling
            width = 0.002 + (0.01 * (flow / max_flow))

            u_pos, v_pos = u.to_np(), v.to_np()
            
            # The normal of the sphere surface at the midpoint of the segment
            up_vec = (u_pos + v_pos) / 2
            up_vec /= np.linalg.norm(up_vec)
            
            flow_dir = v_pos - u_pos
            flow_dir /= np.linalg.norm(flow_dir)
            
            # A vector pointing to the side of the river
            side_vec = np.cross(up_vec, flow_dir)
            side_vec /= np.linalg.norm(side_vec)

            # Define the 4 corners of the river quad
            p1 = u_pos - side_vec * width / 2
            p2 = u_pos + side_vec * width / 2
            p3 = v_pos + side_vec * width / 2
            p4 = v_pos - side_vec * width / 2

            # Project corners back onto the sphere and slightly elevate them
            elevation = 0.99
            p1 = p1 / np.linalg.norm(p1) * elevation
            p2 = p2 / np.linalg.norm(p2) * elevation
            p3 = p3 / np.linalg.norm(p3) * elevation
            p4 = p4 / np.linalg.norm(p4) * elevation

            idx1, idx2, idx3, idx4 = get_or_add_vert(p1), get_or_add_vert(p2), get_or_add_vert(p3), get_or_add_vert(p4)

            # Create two triangles from the quad with the correct winding order (CCW)
            face1 = [idx1, idx2, idx3]
            face2 = [idx1, idx3, idx4]
            river_faces.extend([face1, face2])

            # The normal should be the same as the surface normal
            normal1 = np.cross(p3 - p1, p2 - p1)
            normal1 /= np.linalg.norm(normal1)
            
            normal2 = np.cross(p4 - p1, p3 - p1)
            normal2 /= np.linalg.norm(normal2)

            river_normals.extend([normal1, normal2])

        return river_verts, river_faces, np.array(river_normals)

    def generate_rivers(self, num_rivers=75):
        self._classify_vertices()
        sources = self._find_inland_sources(num_rivers)
        
        print(f"Generating river network from {len(sources)} sources...")
        self._build_flow_network(sources)
        self._calculate_flow()
        
        print("Creating river 3D geometry...")
        return self._create_river_geometry()
