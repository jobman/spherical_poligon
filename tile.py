import math
import numpy as np
from dataclasses import dataclass
from collections import defaultdict
import config as cfg
from config import TerrainType
from geometry import Vertex

try:
    from scipy.spatial import Voronoi
except ImportError:
    Voronoi = None

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
    max_stagnation,
    forced_edge_points=None
):
    vertices = [Vertex(*coords) for coords in vertex_coords]
    tile = Tile(tile_id, vertices, np.asarray(normal, dtype=np.float32))
    tile.generate_subtiles(
        min_distance_factor=min_distance_factor,
        edge_spacing_factor=edge_spacing_factor,
        max_interior_points=max_interior_points,
        candidate_batch_size=candidate_batch_size,
        max_stagnation=max_stagnation,
        forced_edge_points=forced_edge_points
    )
    return tile_id, {
        "subtiles": [
            [np.asarray(vertex, dtype=np.float32) for vertex in subtile.vertices]
            for subtile in tile.subtiles
        ],
        "seed_points": [
            np.asarray(point, dtype=np.float32)
            for point in tile.subtile_seed_points
        ],
    }

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
        self.subtile_seed_points = []

    def __getstate__(self):
        state = self.__dict__.copy()
        # Don't pickle neighbors, it's rebuilt
        if 'neighbors' in state:
            del state['neighbors']
        if 'subtiles' in state:
            del state['subtiles']
        if 'subtile_seed_points' in state:
            del state['subtile_seed_points']
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.neighbors = []
        self.unit = None
        self.is_selected = False
        self.subtiles = []
        self.subtile_seed_points = []
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
        max_stagnation=12,
        forced_edge_points=None
    ):
        vertex_count = len(self.vertices)
        if vertex_count < 3:
            self.subtiles = []
            self.subtile_seed_points = []
            return

        polygon_2d, basis_origin, basis_u, basis_v = self._project_polygon_to_2d()
        edge_lengths = [
            np.linalg.norm(polygon_2d[(i + 1) % vertex_count] - polygon_2d[i])
            for i in range(vertex_count)
        ]
        average_edge_length = float(np.mean(edge_lengths))

        min_distance = average_edge_length * min_distance_factor
        seed_points = []
        seed_display_points = []

        # Stage 1: place points on the tile vertices.
        for vertex_index, vertex in enumerate(polygon_2d):
            seed_points.append(vertex.copy())
            seed_display_points.append(self.vertices[vertex_index].to_np().copy())

        # Stage 2: place canonical points on tile edges. These are derived from
        # the real 3D edge, so adjacent tiles get identical boundary seeds.
        edge_seed_points, edge_seed_display_points = self._generate_canonical_edge_points(
            polygon_2d,
            basis_origin,
            basis_u,
            basis_v,
            edge_spacing_factor,
            min_distance_factor,
            min_distance,
            seed_points
        )
        seed_points.extend(edge_seed_points)
        seed_display_points.extend(edge_seed_display_points)

        # Stage 3: place points only inside the tile with a distance threshold.
        interior_seed_points = self._generate_interior_points(
            polygon_2d,
            seed_points,
            min_distance,
            max_interior_points,
            candidate_batch_size,
            max_stagnation
        )
        seed_points.extend(interior_seed_points)
        seed_display_points.extend(
            basis_origin + basis_u * point[0] + basis_v * point[1]
            for point in interior_seed_points
        )

        subtile_cells = self._build_voronoi_cells(seed_points, polygon_2d)

        merge_distance = average_edge_length * cfg.SUBTILE_POLISH_MERGE_DISTANCE_FACTOR
        subtile_cells = self._polish_subtile_cells(subtile_cells, polygon_2d, merge_distance)

        subtiles = []
        for cell, color in subtile_cells:
            polygon_3d = [
                self._polygon_point_to_3d(point, polygon_2d, basis_origin, basis_u, basis_v)
                for point in cell
            ]
            subtiles.append(SubTile(polygon_3d, color))

        self.subtiles = subtiles
        self.subtile_seed_points = seed_display_points

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

    def _project_point_to_2d(self, point_3d, basis_origin, basis_u, basis_v):
        offset = np.asarray(point_3d, dtype=np.float32) - basis_origin
        return np.array([np.dot(offset, basis_u), np.dot(offset, basis_v)], dtype=np.float32)

    def _polygon_point_to_3d(self, point_2d, polygon_2d, basis_origin, basis_u, basis_v):
        edge_location = self._find_polygon_boundary_location(point_2d, polygon_2d, distance_epsilon=1e-5)
        if edge_location is not None:
            edge_index, edge_t, _ = edge_location
            start_3d = self.vertices[edge_index].to_np()
            end_3d = self.vertices[(edge_index + 1) % len(self.vertices)].to_np()
            return np.asarray(start_3d * (1.0 - edge_t) + end_3d * edge_t, dtype=np.float32)

        return np.asarray(basis_origin + basis_u * point_2d[0] + basis_v * point_2d[1], dtype=np.float32)

    def _generate_canonical_edge_points(
        self,
        polygon_2d,
        basis_origin,
        basis_u,
        basis_v,
        edge_spacing_factor,
        min_distance_factor,
        min_distance,
        existing_points
    ):
        edge_points = []
        edge_display_points = []
        blocked_points = list(existing_points)
        vertex_count = len(self.vertices)

        for edge_index in range(vertex_count):
            start_3d = self.vertices[edge_index].to_np()
            end_3d = self.vertices[(edge_index + 1) % vertex_count].to_np()
            edge_length = float(np.linalg.norm(end_3d - start_3d))
            if edge_length <= 1e-8:
                continue

            edge_spacing = max(
                edge_length * min_distance_factor,
                edge_length * edge_spacing_factor
            )
            segment_count = max(1, int(np.floor(edge_length / edge_spacing)))
            edge_start_2d = polygon_2d[edge_index]
            edge_end_2d = polygon_2d[(edge_index + 1) % vertex_count]

            for step in range(1, segment_count):
                t = step / segment_count
                point_3d = start_3d * (1.0 - t) + end_3d * t
                point_2d = self._project_point_to_2d(point_3d, basis_origin, basis_u, basis_v)
                point_2d = self._closest_point_on_segment_2d(point_2d, edge_start_2d, edge_end_2d)
                if self._is_far_enough(point_2d, blocked_points + edge_points, min_distance * 0.98):
                    edge_points.append(point_2d)
                    edge_display_points.append(np.asarray(point_3d, dtype=np.float32))

        return edge_points, edge_display_points

    def _project_forced_edge_points_to_2d(
        self,
        forced_edge_points,
        basis_origin,
        basis_u,
        basis_v,
        polygon_2d,
        min_distance
    ):
        if not forced_edge_points:
            return []

        forced_edge_vertices = {}
        boundary_epsilon = 1e-6
        for raw_point in forced_edge_points:
            point_3d = np.asarray(raw_point, dtype=np.float32)
            offset = point_3d - basis_origin
            point_2d = np.array([np.dot(offset, basis_u), np.dot(offset, basis_v)], dtype=np.float32)
            edge_location = self._find_polygon_boundary_location(point_2d, polygon_2d, boundary_epsilon)
            if edge_location is None:
                continue

            edge_index, edge_t, closest_point = edge_location
            if edge_t <= 1e-5 or edge_t >= 1.0 - 1e-5:
                continue
            forced_edge_vertices.setdefault(edge_index, []).append((edge_t, closest_point))

        forced_seed_points = []
        min_distance_to_vertex = min_distance * 0.45
        for edge_index, edge_vertices in forced_edge_vertices.items():
            edge_start = polygon_2d[edge_index]
            edge_end = polygon_2d[(edge_index + 1) % len(polygon_2d)]
            previous_seed = edge_start

            for _, boundary_vertex in sorted(edge_vertices, key=lambda item: item[0]):
                seed_point = boundary_vertex * 2.0 - previous_seed
                if not self._is_point_on_segment_2d(seed_point, edge_start, edge_end):
                    continue
                previous_seed = seed_point
                if not self._is_far_enough(seed_point, polygon_2d, min_distance_to_vertex):
                    continue
                if not self._is_far_enough(seed_point, forced_seed_points, min_distance * 0.25):
                    continue
                forced_seed_points.append(seed_point)

        return forced_seed_points

    def _generate_edge_points(self, polygon_2d, edge_spacing, min_distance, existing_points=None):
        edge_points = []
        vertex_count = len(polygon_2d)
        blocked_points = list(existing_points) if existing_points is not None else list(polygon_2d)

        for i in range(vertex_count):
            start = polygon_2d[i]
            end = polygon_2d[(i + 1) % vertex_count]
            edge_length = np.linalg.norm(end - start)
            segment_count = max(1, int(np.floor(edge_length / edge_spacing)))

            for step in range(1, segment_count):
                t = step / segment_count
                point = start * (1.0 - t) + end * t
                if self._is_far_enough(point, blocked_points + edge_points, min_distance * 0.98):
                    edge_points.append(point)

        return edge_points

    def _is_on_polygon_boundary(self, point, polygon_2d, distance_epsilon=1e-6):
        return self._find_polygon_boundary_location(point, polygon_2d, distance_epsilon) is not None

    def _find_polygon_boundary_location(self, point, polygon_2d, distance_epsilon=1e-6):
        for index in range(len(polygon_2d)):
            start = polygon_2d[index]
            end = polygon_2d[(index + 1) % len(polygon_2d)]
            segment = end - start
            segment_length_sq = float(np.dot(segment, segment))
            if segment_length_sq <= 1e-16:
                continue
            t = float(np.dot(point - start, segment) / segment_length_sq)
            t = np.clip(t, 0.0, 1.0)
            closest = start + segment * t
            if float(np.sum((point - closest) * (point - closest))) <= distance_epsilon * distance_epsilon:
                return index, t, closest.astype(np.float32)
        return None

    def _is_point_on_segment_2d(self, point, segment_start, segment_end, distance_epsilon=1e-6):
        return self._point_segment_distance_sq_2d(point, segment_start, segment_end) <= distance_epsilon * distance_epsilon

    def _point_segment_distance_sq_2d(self, point, segment_start, segment_end):
        segment = segment_end - segment_start
        segment_length_sq = float(np.dot(segment, segment))
        if segment_length_sq <= 1e-16:
            return float(np.sum((point - segment_start) * (point - segment_start)))

        t = float(np.dot(point - segment_start, segment) / segment_length_sq)
        t = np.clip(t, 0.0, 1.0)
        closest = segment_start + segment * t
        return float(np.sum((point - closest) * (point - closest)))

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

    def _build_voronoi_cells(self, seed_points, boundary_polygon):
        neighbor_indices = self._get_voronoi_neighbor_indices(seed_points)
        if neighbor_indices is None:
            return self._build_voronoi_cells_by_full_clipping(seed_points, boundary_polygon)

        subtile_cells = []
        for point_index, seed in enumerate(seed_points):
            cell = [point.copy() for point in boundary_polygon]
            for other_index in neighbor_indices[point_index]:
                other = seed_points[other_index]
                mid_point = (seed + other) * 0.5
                normal = other - seed
                cell = self._clip_polygon_with_half_plane(cell, mid_point, normal)
                if len(cell) < 3:
                    break

            cell = self._clean_polygon_vertices(cell)
            if len(cell) >= 3:
                subtile_cells.append((cell, self._get_subtile_color(point_index)))

        return subtile_cells

    def _build_voronoi_cells_by_full_clipping(self, seed_points, boundary_polygon):
        subtile_cells = []
        for point_index, seed in enumerate(seed_points):
            cell = self._build_voronoi_cell(point_index, seed, seed_points, boundary_polygon)
            if len(cell) < 3:
                continue

            subtile_cells.append((cell, self._get_subtile_color(point_index)))

        return subtile_cells

    def _get_voronoi_neighbor_indices(self, seed_points):
        if Voronoi is None or len(seed_points) < 4:
            return None

        points = np.asarray(seed_points, dtype=np.float64)
        if points.ndim != 2 or points.shape[1] != 2 or not np.isfinite(points).all():
            return None

        try:
            voronoi = Voronoi(points)
        except Exception:
            return None

        neighbors = [set() for _ in range(len(seed_points))]
        for point_a, point_b in voronoi.ridge_points:
            neighbors[int(point_a)].add(int(point_b))
            neighbors[int(point_b)].add(int(point_a))

        return [sorted(indices) for indices in neighbors]

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

    def _polish_subtile_cells(self, subtile_cells, boundary_polygon, merge_distance):
        if merge_distance <= 0 or not subtile_cells:
            return subtile_cells

        points = []
        for cell, _ in subtile_cells:
            points.extend(cell)
        if not points:
            return subtile_cells

        parent = list(range(len(points)))
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

        for left_index in range(len(points)):
            left = points[left_index]
            for right_index in range(left_index + 1, len(points)):
                right = points[right_index]
                if np.sum((left - right) * (left - right)) <= merge_distance_sq:
                    union(left_index, right_index)

        clusters = {}
        for index, point in enumerate(points):
            clusters.setdefault(find(index), []).append(point)

        representatives = {}
        for root, cluster_points in clusters.items():
            representative = np.mean(np.asarray(cluster_points, dtype=np.float64), axis=0).astype(np.float32)
            if any(self._is_on_polygon_boundary(point, boundary_polygon, merge_distance * 0.25) for point in cluster_points):
                representative = self._nearest_polygon_boundary_point(representative, boundary_polygon)
            representatives[root] = representative

        polished_cells = []
        point_index = 0
        for cell, color in subtile_cells:
            polished_cell = []
            for _ in cell:
                polished_cell.append(representatives[find(point_index)])
                point_index += 1

            polished_cell = self._clean_polygon_vertices(polished_cell)
            if len(polished_cell) >= 3:
                polished_cells.append((polished_cell, color))

        return polished_cells

    def _polygon_area_2d(self, polygon):
        return abs(self._polygon_area_signed_2d(polygon))

    def _polygon_area_signed_2d(self, polygon):
        area = 0.0
        for index, point in enumerate(polygon):
            next_point = polygon[(index + 1) % len(polygon)]
            area += float(point[0] * next_point[1] - next_point[0] * point[1])
        return area * 0.5

    def _nearest_polygon_boundary_point(self, point, polygon):
        nearest_point = None
        nearest_distance_sq = float("inf")
        for index in range(len(polygon)):
            start = polygon[index]
            end = polygon[(index + 1) % len(polygon)]
            candidate = self._closest_point_on_segment_2d(point, start, end)
            distance_sq = float(np.sum((point - candidate) * (point - candidate)))
            if distance_sq < nearest_distance_sq:
                nearest_distance_sq = distance_sq
                nearest_point = candidate
        return np.asarray(nearest_point, dtype=np.float32)

    def _closest_point_on_segment_2d(self, point, segment_start, segment_end):
        segment = segment_end - segment_start
        segment_length_sq = float(np.dot(segment, segment))
        if segment_length_sq <= 1e-16:
            return np.asarray(segment_start, dtype=np.float32)

        t = float(np.dot(point - segment_start, segment) / segment_length_sq)
        t = np.clip(t, 0.0, 1.0)
        return np.asarray(segment_start + segment * t, dtype=np.float32)

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
