import math
import numpy as np
from dataclasses import dataclass
from config import TerrainType
from geometry import Vertex

@dataclass
class SubTile:
    vertices: list
    color: np.ndarray

def generate_serialized_subtiles_for_tile(
    tile_id,
    vertex_coords,
    normal,
    min_distance_factor,
    edge_spacing_factor,
    max_interior_points,
    candidate_batch_size,
    max_stagnation
):
    vertices = [Vertex(*coords) for coords in vertex_coords]
    tile = Tile(tile_id, vertices, np.asarray(normal, dtype=np.float32))
    tile.generate_subtiles(
        min_distance_factor=min_distance_factor,
        edge_spacing_factor=edge_spacing_factor,
        max_interior_points=max_interior_points,
        candidate_batch_size=candidate_batch_size,
        max_stagnation=max_stagnation
    )
    return tile_id, [
        [np.asarray(vertex, dtype=np.float32) for vertex in subtile.vertices]
        for subtile in tile.subtiles
    ]

class Tile:
    def __init__(self, id, vertices, normal):
        self.id = id
        self.vertices = vertices
        self.normal = normal
        self._center = np.mean([v.to_np() for v in self.vertices], axis=0).astype(np.float32)
        self.terrain_type = None
        self.height = 0.0
        self.neighbors = []
        self.is_selected = False
        self.unit = None
        self.subtiles = []

    def __getstate__(self):
        state = self.__dict__.copy()
        # Don't pickle neighbors, it's rebuilt
        if 'neighbors' in state:
            del state['neighbors']
        if 'subtiles' in state:
            del state['subtiles']
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.neighbors = []
        self.unit = None
        self.is_selected = False
        self.subtiles = []
        self._center = np.mean([v.to_np() for v in self.vertices], axis=0).astype(np.float32)

    def is_water(self):
        return self.terrain_type in [TerrainType.OCEAN, TerrainType.COAST, TerrainType.ICE]

    @property
    def color(self):
        return np.array(self.terrain_type.value) if self.terrain_type else np.array([200, 200, 200])

    @property
    def center(self):
        return self._center

    def generate_subtiles(
        self,
        min_distance_factor=0.55,
        edge_spacing_factor=0.9,
        max_interior_points=18,
        candidate_batch_size=24,
        max_stagnation=12
    ):
        vertex_count = len(self.vertices)
        if vertex_count < 3:
            self.subtiles = []
            return

        polygon_2d, basis_origin, basis_u, basis_v = self._project_polygon_to_2d()
        edge_lengths = [
            np.linalg.norm(polygon_2d[(i + 1) % vertex_count] - polygon_2d[i])
            for i in range(vertex_count)
        ]
        average_edge_length = float(np.mean(edge_lengths))

        min_distance = average_edge_length * min_distance_factor
        edge_spacing = max(min_distance, average_edge_length * edge_spacing_factor)

        seed_points = []

        # Stage 1: place points on the tile vertices.
        for vertex in polygon_2d:
            seed_points.append(vertex.copy())

        # Stage 2: place points only on tile edges.
        seed_points.extend(self._generate_edge_points(polygon_2d, edge_spacing, min_distance))

        # Stage 3: place points only inside the tile with a distance threshold.
        seed_points.extend(
            self._generate_interior_points(
                polygon_2d,
                seed_points,
                min_distance,
                max_interior_points,
                candidate_batch_size,
                max_stagnation
            )
        )

        subtiles = []
        for point_index, seed in enumerate(seed_points):
            cell = self._build_voronoi_cell(point_index, seed, seed_points, polygon_2d)
            if len(cell) < 3:
                continue

            polygon_3d = [basis_origin + basis_u * point[0] + basis_v * point[1] for point in cell]
            subtiles.append(SubTile(polygon_3d, self._get_subtile_color(point_index)))

        self.subtiles = subtiles

    def _project_polygon_to_2d(self):
        center = self.center
        normal = self.normal / np.linalg.norm(self.normal)

        basis_u = self.vertices[0].to_np() - center
        basis_u -= normal * np.dot(basis_u, normal)
        if np.linalg.norm(basis_u) < 1e-8:
            fallback = np.array([1.0, 0.0, 0.0])
            if abs(np.dot(fallback, normal)) > 0.9:
                fallback = np.array([0.0, 1.0, 0.0])
            basis_u = np.cross(normal, fallback)
        basis_u /= np.linalg.norm(basis_u)

        basis_v = np.cross(normal, basis_u)
        basis_v /= np.linalg.norm(basis_v)

        polygon_2d = []
        for vertex in self.vertices:
            offset = vertex.to_np() - center
            polygon_2d.append(np.array([np.dot(offset, basis_u), np.dot(offset, basis_v)], dtype=np.float32))

        return polygon_2d, center, basis_u, basis_v

    def _generate_edge_points(self, polygon_2d, edge_spacing, min_distance):
        edge_points = []
        vertex_count = len(polygon_2d)

        for i in range(vertex_count):
            start = polygon_2d[i]
            end = polygon_2d[(i + 1) % vertex_count]
            edge_length = np.linalg.norm(end - start)
            segment_count = max(1, int(np.floor(edge_length / edge_spacing)))

            for step in range(1, segment_count):
                t = step / segment_count
                point = start * (1.0 - t) + end * t
                if self._is_far_enough(point, polygon_2d + edge_points, min_distance * 0.98):
                    edge_points.append(point)

        return edge_points

    def _generate_interior_points(
        self,
        polygon_2d,
        existing_points,
        min_distance,
        max_interior_points,
        candidate_batch_size,
        max_stagnation
    ):
        rng = np.random.default_rng(self.id)
        interior_points = []
        all_points = list(existing_points)
        polygon_array = np.asarray(polygon_2d, dtype=np.float64)
        min_bounds = polygon_array.min(axis=0)
        max_bounds = polygon_array.max(axis=0)

        if (
            polygon_array.ndim != 2 or
            polygon_array.shape[1] != 2 or
            not np.isfinite(min_bounds).all() or
            not np.isfinite(max_bounds).all()
        ):
            return interior_points

        min_x = float(min_bounds[0])
        min_y = float(min_bounds[1])
        max_x = float(max_bounds[0])
        max_y = float(max_bounds[1])

        if max_x - min_x < 1e-8 or max_y - min_y < 1e-8:
            return interior_points

        stagnation = 0
        min_distance_sq = min_distance * min_distance
        all_points_array = np.asarray(all_points, dtype=np.float64).reshape(-1, 2)
        while len(interior_points) < max_interior_points and stagnation < max_stagnation:
            best_candidate = None
            best_distance = -1.0

            candidates = np.column_stack((
                rng.uniform(min_x, max_x, candidate_batch_size),
                rng.uniform(min_y, max_y, candidate_batch_size),
            ))
            inside_mask = self._points_in_polygon(candidates, polygon_array)
            candidates = candidates[inside_mask]

            if len(candidates) > 0:
                if len(all_points_array) == 0:
                    nearest_distance_sq = np.full(len(candidates), float("inf"), dtype=np.float64)
                else:
                    offsets = candidates[:, None, :] - all_points_array[None, :, :]
                    nearest_distance_sq = np.min(np.sum(offsets * offsets, axis=2), axis=1)
                valid_mask = nearest_distance_sq >= min_distance_sq

                if np.any(valid_mask):
                    valid_candidates = candidates[valid_mask]
                    valid_distances = nearest_distance_sq[valid_mask]
                    best_index = int(np.argmax(valid_distances))
                    best_distance = float(valid_distances[best_index])
                    best_candidate = valid_candidates[best_index]

            if best_candidate is None:
                stagnation += 1
                continue

            interior_points.append(best_candidate)
            all_points.append(best_candidate)
            all_points_array = np.vstack((all_points_array, best_candidate))
            stagnation = 0

        return interior_points

    def _build_voronoi_cell(self, seed_index, seed, all_points, boundary_polygon):
        cell = [point.copy() for point in boundary_polygon]

        for other_index, other in enumerate(all_points):
            if other_index == seed_index:
                continue

            mid_point = (seed + other) * 0.5
            normal = other - seed
            cell = self._clip_polygon_with_half_plane(cell, mid_point, normal)
            if len(cell) < 3:
                return []

        return self._clean_polygon_vertices(cell)

    def _clip_polygon_with_half_plane(self, polygon, line_point, line_normal):
        if not polygon:
            return []

        clipped = []
        previous = polygon[-1]
        previous_inside = self._is_inside_half_plane(previous, line_point, line_normal)

        for current in polygon:
            current_inside = self._is_inside_half_plane(current, line_point, line_normal)

            if current_inside != previous_inside:
                intersection = self._line_half_plane_intersection(previous, current, line_point, line_normal)
                if intersection is not None:
                    clipped.append(intersection)

            if current_inside:
                clipped.append(current)

            previous = current
            previous_inside = current_inside

        return self._remove_duplicate_polygon_vertices(clipped)

    def _remove_duplicate_polygon_vertices(self, polygon, distance_epsilon=1e-8):
        if len(polygon) < 2:
            return polygon

        cleaned = []
        for point in polygon:
            if cleaned and np.sum((point - cleaned[-1]) * (point - cleaned[-1])) <= distance_epsilon * distance_epsilon:
                continue
            cleaned.append(point)

        if len(cleaned) > 1 and np.sum((cleaned[0] - cleaned[-1]) * (cleaned[0] - cleaned[-1])) <= distance_epsilon * distance_epsilon:
            cleaned.pop()

        return cleaned

    def _clean_polygon_vertices(self, polygon, distance_epsilon=1e-8, collinear_epsilon=1e-10):
        cleaned = self._remove_duplicate_polygon_vertices(polygon, distance_epsilon)
        if len(cleaned) < 3:
            return cleaned

        result = []
        for index, point in enumerate(cleaned):
            previous = cleaned[index - 1]
            following = cleaned[(index + 1) % len(cleaned)]
            edge_a = point - previous
            edge_b = following - point
            cross = edge_a[0] * edge_b[1] - edge_a[1] * edge_b[0]
            if abs(cross) <= collinear_epsilon and np.dot(edge_a, edge_b) >= 0:
                continue
            result.append(point)

        return result

    def _is_inside_half_plane(self, point, line_point, line_normal):
        return np.dot(point - line_point, line_normal) <= 1e-6

    def _line_half_plane_intersection(self, start, end, line_point, line_normal):
        direction = end - start
        denominator = np.dot(direction, line_normal)
        if abs(denominator) < 1e-8:
            return None

        t = np.dot(line_point - start, line_normal) / denominator
        t = np.clip(t, 0.0, 1.0)
        return start + direction * t

    def _point_in_polygon(self, point, polygon):
        inside = False
        j = len(polygon) - 1

        for i in range(len(polygon)):
            pi = polygon[i]
            pj = polygon[j]
            intersects = ((pi[1] > point[1]) != (pj[1] > point[1])) and (
                point[0] < (pj[0] - pi[0]) * (point[1] - pi[1]) / ((pj[1] - pi[1]) + 1e-12) + pi[0]
            )
            if intersects:
                inside = not inside
            j = i

        return inside

    def _points_in_polygon(self, points, polygon):
        if len(points) == 0:
            return np.zeros(0, dtype=bool)

        inside = np.zeros(len(points), dtype=bool)
        j = len(polygon) - 1

        for i in range(len(polygon)):
            pi = polygon[i]
            pj = polygon[j]
            intersects = ((pi[1] > points[:, 1]) != (pj[1] > points[:, 1])) & (
                points[:, 0] < (pj[0] - pi[0]) * (points[:, 1] - pi[1]) / ((pj[1] - pi[1]) + 1e-12) + pi[0]
            )
            inside ^= intersects
            j = i

        return inside

    def _is_far_enough(self, point, others, min_distance):
        return self._nearest_distance_sq(point, others) >= min_distance * min_distance

    def _nearest_distance(self, point, others):
        nearest_distance_sq = self._nearest_distance_sq(point, others)
        if not np.isfinite(nearest_distance_sq):
            return nearest_distance_sq
        return math.sqrt(nearest_distance_sq)

    def _nearest_distance_sq(self, point, others):
        if not others:
            return float("inf")
        other_points = np.asarray(others, dtype=np.float64)
        offsets = other_points - point
        return float(np.min(np.sum(offsets * offsets, axis=1)))

    def _get_subtile_color(self, point_index):
        base_color = self.color.astype(np.float32)
        noise_bucket = (self.id * 97 + point_index * 13) % 11
        brightness_shift = (noise_bucket - 5) * 0.03
        return np.clip(base_color * (1.0 + brightness_shift), 0, 255)
        
    def __repr__(self):
        return f"Tile({self.id}, terrain={self.terrain_type.name if self.terrain_type else 'None'}, height={self.height:.2f})"
        
    def __lt__(self, other):
        return self.height < other.height
        
    def __eq__(self, other):
        return isinstance(other, Tile) and self.id == other.id

    def __hash__(self):
        return hash(self.id)
