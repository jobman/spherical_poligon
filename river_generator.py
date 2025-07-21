import random
from collections import defaultdict

class RiverGenerator:
    def __init__(self, vertices, vert_to_tiles, vert_neighbors):
        self.vertices = vertices
        self.vert_to_tiles = vert_to_tiles
        self.vert_neighbors = vert_neighbors
        
        self.vertex_terrain = {}  # 'land' or 'sea'
        self.downstream_map = {}  # Maps a vertex to the one it flows into
        self.vertex_flow = defaultdict(float)

    def _classify_vertices(self):
        """Classify each vertex as either 'land' or 'sea'."""
        for vertex in self.vertices:
            is_sea = any(tile.is_water() for tile in self.vert_to_tiles[vertex])
            self.vertex_terrain[vertex] = 'sea' if is_sea else 'land'

    def _find_inland_sources(self, num_rivers):
        """Find potential river sources on high-ground, inland vertices."""
        candidates = []
        for vertex in self.vertices:
            if self.vertex_terrain[vertex] == 'land':
                is_inland = all(self.vertex_terrain[neighbor] == 'land' for neighbor in self.vert_neighbors[vertex])
                if is_inland:
                    avg_height = sum(t.height for t in self.vert_to_tiles[vertex]) / len(self.vert_to_tiles[vertex])
                    if avg_height > 0.6:  # Prioritize mountains/hills
                        candidates.append(vertex)
        
        if not candidates:  # Fallback if no high ground found
            candidates = [v for v in self.vertices if self.vertex_terrain[v] == 'land' and all(self.vertex_terrain[n] == 'land' for n in self.vert_neighbors[v])]

        return random.sample(candidates, min(num_rivers, len(candidates)))

    def _build_flow_network(self, sources):
        """Trace paths from sources to build the downstream_map."""
        river_vertices = set()
        for source in sources:
            if source in river_vertices:
                continue

            current_vertex = source
            path = [current_vertex]
            river_vertices.add(current_vertex)

            for _ in range(200):  # Max river length
                if current_vertex in self.downstream_map:
                    break

                neighbors = self.vert_neighbors[current_vertex]
                valid_neighbors = [n for n in neighbors if n not in path] # Avoid loops in a single path

                sea_neighbors = [n for n in valid_neighbors if self.vertex_terrain[n] == 'sea']
                if sea_neighbors:
                    next_vertex = random.choice(sea_neighbors)
                    self.downstream_map[current_vertex] = next_vertex
                    break  # River ends

                if not valid_neighbors:
                    break # Dead end

                next_vertex = random.choice(valid_neighbors)
                self.downstream_map[current_vertex] = next_vertex
                river_vertices.add(next_vertex)
                path.append(next_vertex)
                current_vertex = next_vertex

    def _calculate_flow(self):
        """Calculate flow volume for each vertex in the river network using topological sort."""
        in_degree = defaultdict(int)
        all_river_verts = set(self.downstream_map.keys()) | set(self.downstream_map.values())

        for u, v in self.downstream_map.items():
            in_degree[v] += 1

        queue = [v for v in all_river_verts if in_degree[v] == 0]
        for v in queue:
            self.vertex_flow[v] = 1.0  # Initial flow for sources

        head = 0
        while head < len(queue):
            u = queue[head]
            head += 1

            v = self.downstream_map.get(u)
            if v:
                self.vertex_flow[v] += self.vertex_flow[u]
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)
        
        print(f"Calculated flow for {len(self.vertex_flow)} river vertices.")

    def generate_rivers(self, num_rivers=75):
        """Main method to generate all rivers and their flow."""
        self._classify_vertices()
        sources = self._find_inland_sources(num_rivers)
        
        print(f"Generating river network from {len(sources)} sources...")
        self._build_flow_network(sources)
        self._calculate_flow()

        return self.downstream_map, self.vertex_flow