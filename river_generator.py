import random
from collections import defaultdict
import numpy as np
from geometry import Vertex
import config as cfg

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

    def _create_continuous_river_geometry(self):
        river_verts = []
        river_faces = []
        river_normals = []

        # 1. Reconstruct full river paths
        paths = []
        sources = {v for v in self.downstream_map if v not in self.downstream_map.values()}
        for source in sources:
            path = [source]
            curr = source
            while curr in self.downstream_map:
                curr = self.downstream_map[curr]
                path.append(curr)
            if len(path) > 1: paths.append(path)

        max_flow = max(self.vertex_flow.values()) if self.vertex_flow else 1.0
        elevation = cfg.RIVER_ELEVATION

        for path in paths:
            path_strip_indices = []
            for i, v_node in enumerate(path):
                # 2. Calculate smoothed tangent
                v_pos = v_node.to_np()
                if i == 0:
                    tangent = (path[i+1].to_np() - v_pos)
                elif i == len(path) - 1:
                    tangent = (v_pos - path[i-1].to_np())
                else:
                    vec_in = v_pos - path[i-1].to_np()
                    vec_out = path[i+1].to_np() - v_pos
                    tangent = (vec_in / np.linalg.norm(vec_in) + vec_out / np.linalg.norm(vec_out)) / 2
                if (norm := np.linalg.norm(tangent)) > 0: tangent /= norm

                # 3. Create side vector and quad vertices
                up_vec = v_pos / np.linalg.norm(v_pos)
                side_vec = np.cross(tangent, up_vec)
                if (norm := np.linalg.norm(side_vec)) > 0: side_vec /= norm
                
                flow = self.vertex_flow.get(v_node, 1.0)
                width = cfg.RIVER_BASE_WIDTH + (cfg.RIVER_WIDTH_FACTOR * (flow / max_flow))

                v_left_pos = v_pos - side_vec * width / 2
                v_right_pos = v_pos + side_vec * width / 2

                v_left_pos = v_left_pos / np.linalg.norm(v_left_pos) * elevation
                v_right_pos = v_right_pos / np.linalg.norm(v_right_pos) * elevation

                left_idx = len(river_verts)
                river_verts.append(Vertex(*v_left_pos))
                right_idx = len(river_verts)
                river_verts.append(Vertex(*v_right_pos))
                path_strip_indices.append((left_idx, right_idx))

            # 4. Create faces from the strip
            for i in range(len(path_strip_indices) - 1):
                l1, r1 = path_strip_indices[i]
                l2, r2 = path_strip_indices[i+1]
                
                face1 = [l1, r1, r2]
                face2 = [l1, r2, l2]
                river_faces.extend([face1, face2])

                v_l1, v_r1, v_r2, v_l2 = river_verts[l1].to_np(), river_verts[r1].to_np(), river_verts[r2].to_np(), river_verts[l2].to_np()
                normal1 = np.cross(v_r1 - v_l1, v_r2 - v_l1)
                normal2 = np.cross(v_r2 - v_l1, v_l2 - v_l1)
                if (n1_norm := np.linalg.norm(normal1)) > 0: normal1 /= n1_norm
                if (n2_norm := np.linalg.norm(normal2)) > 0: normal2 /= n2_norm
                river_normals.extend([normal1, normal2])

            # 5. Create river delta trapezoid at the mouth
            if len(path) > 1 and self.vertex_terrain.get(path[-1]) == 'sea':
                last_left_idx, last_right_idx = path_strip_indices[-1]
                v_left_start = river_verts[last_left_idx]
                v_right_start = river_verts[last_right_idx]

                v_mouth_node = path[-1]
                v_before_node = path[-2]
                v_mouth_pos = v_mouth_node.to_np()

                flow_direction = v_mouth_pos - v_before_node.to_np()
                if (norm := np.linalg.norm(flow_direction)) > 0: flow_direction /= norm

                up_vec = v_mouth_pos / np.linalg.norm(v_mouth_pos)
                side_vec = np.cross(flow_direction, up_vec)
                if (norm := np.linalg.norm(side_vec)) > 0: side_vec /= norm

                flow = self.vertex_flow.get(v_mouth_node, 1.0)
                width = cfg.RIVER_BASE_WIDTH + (cfg.RIVER_WIDTH_FACTOR * (flow / max_flow))
                delta_length = width * cfg.RIVER_DELTA_LENGTH_FACTOR * 1.25

                angle = np.pi / 3 
                cos_angle = np.cos(angle)
                sin_angle = np.sin(angle)

                left_delta_dir = cos_angle * flow_direction + sin_angle * side_vec
                right_delta_dir = cos_angle * flow_direction - sin_angle * side_vec
                
                v_left_end_pos = v_left_start.to_np() + left_delta_dir * delta_length
                v_right_end_pos = v_right_start.to_np() + right_delta_dir * delta_length
                
                # Set elevation to river level to prevent deltas from being "sunken"
                v_left_end_pos = v_left_end_pos / np.linalg.norm(v_left_end_pos) * elevation
                v_right_end_pos = v_right_end_pos / np.linalg.norm(v_right_end_pos) * elevation

                left_end_idx = len(river_verts)
                river_verts.append(Vertex(*v_left_end_pos))
                right_end_idx = len(river_verts)
                river_verts.append(Vertex(*v_right_end_pos))

                face1 = [last_left_idx, last_right_idx, right_end_idx]
                face2 = [last_left_idx, right_end_idx, left_end_idx]
                river_faces.extend([face1, face2])

                # Calculate normals based on face centroid to ensure they point outwards
                v_ls_pos = v_left_start.to_np()
                v_rs_pos = v_right_start.to_np()

                centroid1 = (v_ls_pos + v_rs_pos + v_right_end_pos) / 3.0
                normal1 = centroid1 / np.linalg.norm(centroid1)

                centroid2 = (v_ls_pos + v_right_end_pos + v_left_end_pos) / 3.0
                normal2 = centroid2 / np.linalg.norm(centroid2)
                
                river_normals.extend([normal1, normal2])

        return river_verts, river_faces, np.array(river_normals)

    def generate_rivers(self, num_rivers=cfg.RIVER_COUNT):
        self._classify_vertices()
        sources = self._find_inland_sources(num_rivers)
        print(f"Generating river network from {len(sources)} sources...")
        self._build_flow_network(sources)
        self._calculate_flow()
        print("Creating continuous river 3D geometry...")
        return self._create_continuous_river_geometry()
