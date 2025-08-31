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

    def _get_river_paths(self):
        """
        Reconstructs river paths from the downstream map.
        Returns a list of paths, where each path is a list of Vertex objects.
        """
        paths = []
        # Find sources (vertices that are not a destination for any other vertex)
        sources = {v for v in self.downstream_map if v not in self.downstream_map.values()}
        
        for source in sources:
            path = [source]
            current_vertex = source
            # Follow the downstream map to build the path
            while current_vertex in self.downstream_map:
                current_vertex = self.downstream_map[current_vertex]
                path.append(current_vertex)
            
            if len(path) > 1:
                paths.append(path)
        return paths

    def generate_rivers(self, num_rivers=cfg.RIVER_COUNT):
        self._classify_vertices()
        sources = self._find_inland_sources(num_rivers)
        if not sources:
            print("No suitable river sources found.")
            return [], {}
        print(f"Generating river network from {len(sources)} sources...")
        self._build_flow_network(sources)
        self._calculate_flow()
        print("Extracting river paths...")
        paths = self._get_river_paths()
        return paths, self.vertex_flow