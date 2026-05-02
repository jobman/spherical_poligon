import math
import tkinter as tk
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

import config as cfg

try:
    from scipy.spatial import Voronoi
except ImportError:
    Voronoi = None


WINDOW_WIDTH = 1180
WINDOW_HEIGHT = 820
LOG_HEIGHT = 9


@dataclass
class DebugStep:
    title: str
    message: str
    seed_points: list = field(default_factory=list)
    saved_points: list = field(default_factory=list)
    cells: list = field(default_factory=list)
    candidate_points: list = field(default_factory=list)
    lines: list = field(default_factory=list)
    highlight_polygon: list | None = None
    highlight_point: np.ndarray | None = None


class SubtileDebugRecorder:
    def __init__(self, mode, tile_count=4, voronoi_backend="step"):
        self.mode = mode
        self.voronoi_backend = voronoi_backend
        self.tile_count = max(1, int(tile_count))
        if self.mode == "single":
            self.tile_count = 1

        self.tile_polygons = self._make_tile_polygons(self.tile_count)
        self.tile_seed_points = [[] for _ in self.tile_polygons]
        self.tile_saved_points = [[] for _ in self.tile_polygons]
        self.tile_cells = [[] for _ in self.tile_polygons]
        self.steps = []

    def build(self):
        self._record(
            "Start",
            f"Mode: {'1 tile' if self.mode == 'single' else f'{self.tile_count} adjacent tiles'}, backend={self.voronoi_backend}",
        )

        for tile_index, polygon in enumerate(self.tile_polygons):
            forced_edge_vertices = []
            for source_tile_index in range(tile_index):
                forced_edge_vertices.extend(
                    self._get_shared_edge_cell_vertices(source_tile_index, tile_index)
                )

            self._generate_tile(tile_index, polygon, forced_edge_vertices)

        self._polish_all_shared_edges()
        self._record("Done", "All requested tiles are generated.")
        return self.steps

    def _generate_tile(self, tile_index, polygon, forced_edge_vertices):
        vertex_count = len(polygon)
        edge_lengths = [
            np.linalg.norm(polygon[(i + 1) % vertex_count] - polygon[i])
            for i in range(vertex_count)
        ]
        average_edge_length = float(np.mean(edge_lengths))
        min_distance = average_edge_length * cfg.SUBTILE_MIN_DISTANCE_FACTOR
        edge_spacing = max(min_distance, average_edge_length * cfg.SUBTILE_EDGE_POINT_SPACING_FACTOR)

        self._record(
            f"Tile {tile_index}: setup",
            f"avg_edge={average_edge_length:.3f}, min_distance={min_distance:.3f}, edge_spacing={edge_spacing:.3f}",
        )

        seed_points = []
        for point in polygon:
            seed_points.append(point.copy())
            self.tile_seed_points[tile_index] = list(seed_points)
            self._record(
                f"Tile {tile_index}: vertex seed",
                f"Added tile vertex seed at {self._format_point(point)}.",
                highlight_point=point,
            )

        forced_seed_points = self._project_forced_edge_vertices(tile_index, polygon, forced_edge_vertices, min_distance)
        for point in forced_seed_points:
            seed_points.append(point)
            self.tile_seed_points[tile_index] = list(seed_points)
            self._record(
                f"Tile {tile_index}: forced edge seed",
                f"Reconstructed seed from neighbor boundary at {self._format_point(point)}.",
                highlight_point=point,
            )

        for point in self._generate_edge_points(polygon, edge_spacing, min_distance, seed_points):
            seed_points.append(point)
            self.tile_seed_points[tile_index] = list(seed_points)
            self._record(
                f"Tile {tile_index}: edge seed",
                f"Added automatic edge seed at {self._format_point(point)}.",
                highlight_point=point,
            )

        for point in self._generate_interior_points(tile_index, polygon, seed_points, min_distance):
            seed_points.append(point)
            self.tile_seed_points[tile_index] = list(seed_points)
            self._record(
                f"Tile {tile_index}: interior seed",
                f"Accepted interior seed at {self._format_point(point)}.",
                highlight_point=point,
            )

        if self.voronoi_backend == "fast":
            self._generate_fast_voronoi_cells(tile_index, polygon, seed_points)
            return

        self._generate_step_voronoi_cells(tile_index, polygon, seed_points)

    def _generate_step_voronoi_cells(self, tile_index, polygon, seed_points):
        cells = []
        for seed_index, seed in enumerate(seed_points):
            cell = [point.copy() for point in polygon]
            self._record(
                f"Tile {tile_index}: Voronoi cell {seed_index}",
                f"Start cell from tile boundary for seed {seed_index}.",
                highlight_polygon=cell,
                highlight_point=seed,
            )

            for other_index, other in enumerate(seed_points):
                if other_index == seed_index:
                    continue

                mid_point = (seed + other) * 0.5
                normal = other - seed
                line = self._make_debug_bisector_line(mid_point, normal, polygon)
                self._record(
                    f"Tile {tile_index}: clip cell {seed_index}",
                    f"Clip against seed {other_index}: bisector through {self._format_point(mid_point)}.",
                    lines=[line] if line is not None else [],
                    highlight_polygon=cell,
                    highlight_point=seed,
                )

                cell = self._clip_polygon_with_half_plane(cell, mid_point, normal)
                if len(cell) < 3:
                    self._record(
                        f"Tile {tile_index}: cell discarded",
                        f"Cell for seed {seed_index} collapsed after clipping against seed {other_index}.",
                        highlight_point=seed,
                    )
                    break

                self._record(
                    f"Tile {tile_index}: cell clipped",
                    f"Cell for seed {seed_index} now has {len(cell)} vertices.",
                    highlight_polygon=cell,
                    highlight_point=seed,
                )

            if len(cell) >= 3:
                cell = self._clean_polygon_vertices(cell)
                cells.append(cell)
                self._save_cell_points(tile_index, cell)
                self.tile_cells[tile_index] = list(cells)
                self._record(
                    f"Tile {tile_index}: cell ready",
                    f"Stored subtile polygon for seed {seed_index} with {len(cell)} vertices.",
                    highlight_polygon=cell,
                    highlight_point=seed,
                )

        self.tile_seed_points[tile_index] = seed_points
        cells = self._polish_tile_cells(tile_index, polygon, cells)
        self.tile_cells[tile_index] = cells
        self._record(f"Tile {tile_index}: complete", f"Generated {len(cells)} subtiles.")

    def _generate_fast_voronoi_cells(self, tile_index, polygon, seed_points):
        if Voronoi is None:
            self._record(
                f"Tile {tile_index}: fast Voronoi unavailable",
                "SciPy is not installed, falling back to step-by-step clipping.",
            )
            self._generate_step_voronoi_cells(tile_index, polygon, seed_points)
            return

        if len(seed_points) < 4:
            self._record(
                f"Tile {tile_index}: fast Voronoi skipped",
                "Need at least 4 seed points for scipy.spatial.Voronoi; falling back to clipping.",
            )
            self._generate_step_voronoi_cells(tile_index, polygon, seed_points)
            return

        points = np.asarray(seed_points, dtype=np.float64)
        self._record(
            f"Tile {tile_index}: fast Voronoi",
            f"Building Voronoi diagram for {len(points)} seeds with scipy.spatial.Voronoi.",
            candidate_points=seed_points,
        )

        try:
            voronoi = Voronoi(points)
            neighbor_indices = self._voronoi_neighbor_indices(voronoi, len(seed_points))
        except Exception as exc:
            self._record(
                f"Tile {tile_index}: fast Voronoi failed",
                f"{exc}; falling back to step-by-step clipping.",
            )
            self._generate_step_voronoi_cells(tile_index, polygon, seed_points)
            return

        cells = []
        for seed_index, seed in enumerate(seed_points):
            clipped_cell = [point.copy() for point in polygon]
            for other_index in neighbor_indices[seed_index]:
                other = seed_points[other_index]
                mid_point = (seed + other) * 0.5
                normal = other - seed
                clipped_cell = self._clip_polygon_with_half_plane(clipped_cell, mid_point, normal)
                if len(clipped_cell) < 3:
                    break

            if len(clipped_cell) < 3:
                self._record(
                    f"Tile {tile_index}: fast cell skipped",
                    f"Fast cell for seed {seed_index} collapsed after tile-boundary clipping.",
                    highlight_point=seed_points[seed_index],
                )
                continue

            clipped_cell = self._clean_polygon_vertices(clipped_cell)
            cells.append(clipped_cell)
            self._save_cell_points(tile_index, clipped_cell)
            self.tile_cells[tile_index] = list(cells)
            self._record(
                f"Tile {tile_index}: fast cell ready",
                f"Stored scipy Voronoi cell for seed {seed_index} with {len(clipped_cell)} vertices.",
                highlight_polygon=clipped_cell,
                highlight_point=seed_points[seed_index],
            )

        self.tile_seed_points[tile_index] = seed_points
        cells = self._polish_tile_cells(tile_index, polygon, cells)
        self.tile_cells[tile_index] = cells
        self._record(f"Tile {tile_index}: complete", f"Generated {len(cells)} fast Voronoi subtiles.")

    def _project_forced_edge_vertices(self, tile_index, polygon, forced_edge_vertices, min_distance):
        if not forced_edge_vertices:
            return []

        self._record(
            f"Tile {tile_index}: forced input",
            f"Received {len(forced_edge_vertices)} neighbor boundary vertices.",
            candidate_points=forced_edge_vertices,
        )

        forced_by_edge = {}
        for point in forced_edge_vertices:
            edge_location = self._find_polygon_boundary_location(point, polygon)
            if edge_location is None:
                self._record(
                    f"Tile {tile_index}: forced skipped",
                    f"Neighbor point {self._format_point(point)} is not on this tile boundary.",
                    highlight_point=point,
                )
                continue

            edge_index, edge_t, closest_point = edge_location
            if edge_t <= 1e-5 or edge_t >= 1.0 - 1e-5:
                continue
            forced_by_edge.setdefault(edge_index, []).append((edge_t, closest_point))
            self._record(
                f"Tile {tile_index}: forced boundary",
                f"Accepted neighbor boundary vertex on edge {edge_index}, t={edge_t:.3f}.",
                highlight_point=closest_point,
            )

        forced_seed_points = []
        min_distance_to_vertex = min_distance * 0.45
        for edge_index, edge_vertices in forced_by_edge.items():
            edge_start = polygon[edge_index]
            edge_end = polygon[(edge_index + 1) % len(polygon)]
            previous_seed = edge_start

            for _, boundary_vertex in sorted(edge_vertices, key=lambda item: item[0]):
                seed_point = boundary_vertex * 2.0 - previous_seed
                self._record(
                    f"Tile {tile_index}: reconstruct forced seed",
                    f"boundary={self._format_point(boundary_vertex)}, previous_seed={self._format_point(previous_seed)} -> seed={self._format_point(seed_point)}",
                    lines=[(previous_seed, seed_point)],
                    highlight_point=seed_point,
                )

                if not self._is_point_on_segment_2d(seed_point, edge_start, edge_end):
                    self._record(
                        f"Tile {tile_index}: forced seed rejected",
                        "Reconstructed seed would be outside the shared edge segment.",
                        highlight_point=seed_point,
                    )
                    continue

                previous_seed = seed_point
                if not self._is_far_enough(seed_point, polygon, min_distance_to_vertex):
                    continue
                if not self._is_far_enough(seed_point, forced_seed_points, min_distance * 0.25):
                    continue
                forced_seed_points.append(seed_point)

        return forced_seed_points

    def _generate_edge_points(self, polygon, edge_spacing, min_distance, existing_points):
        edge_points = []
        blocked_points = list(existing_points)

        for edge_index in range(len(polygon)):
            start = polygon[edge_index]
            end = polygon[(edge_index + 1) % len(polygon)]
            edge_length = np.linalg.norm(end - start)
            segment_count = max(1, int(np.floor(edge_length / edge_spacing)))
            self._record(
                "Edge seed scan",
                f"Edge {edge_index}: length={edge_length:.3f}, segment_count={segment_count}.",
                lines=[(start, end)],
            )

            for step in range(1, segment_count):
                t = step / segment_count
                point = start * (1.0 - t) + end * t
                nearest_sq = self._nearest_distance_sq(point, blocked_points + edge_points)
                accepted = nearest_sq >= (min_distance * 0.98) ** 2
                self._record(
                    "Edge candidate",
                    f"Candidate edge point t={t:.3f} at {self._format_point(point)}: {'accepted' if accepted else 'rejected'}.",
                    highlight_point=point,
                )
                if accepted:
                    edge_points.append(point)

        return edge_points

    def _generate_interior_points(self, tile_index, polygon, existing_points, min_distance):
        rng = np.random.default_rng(tile_index)
        interior_points = []
        all_points = list(existing_points)
        polygon_array = np.asarray(polygon, dtype=np.float64)
        min_bounds = polygon_array.min(axis=0)
        max_bounds = polygon_array.max(axis=0)
        stagnation = 0
        min_distance_sq = min_distance * min_distance
        all_points_array = np.asarray(all_points, dtype=np.float64).reshape(-1, 2)
        max_points = min(cfg.SUBTILE_MAX_INTERIOR_POINTS, 18)
        batch_size = min(cfg.SUBTILE_CANDIDATE_BATCH_SIZE, 32)
        max_stagnation = min(cfg.SUBTILE_MAX_STAGNATION, 12)

        while len(interior_points) < max_points and stagnation < max_stagnation:
            candidates = np.column_stack((
                rng.uniform(float(min_bounds[0]), float(max_bounds[0]), batch_size),
                rng.uniform(float(min_bounds[1]), float(max_bounds[1]), batch_size),
            ))
            inside_mask = self._points_in_polygon(candidates, polygon_array)
            candidates = candidates[inside_mask]
            self._record(
                f"Tile {tile_index}: interior batch",
                f"Generated {batch_size} candidates, {len(candidates)} are inside the polygon.",
                candidate_points=[np.asarray(point, dtype=np.float32) for point in candidates],
            )

            best_candidate = None
            best_distance = -1.0
            if len(candidates) > 0:
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
                self._record(
                    f"Tile {tile_index}: interior rejected",
                    f"No valid candidate in this batch. stagnation={stagnation}/{max_stagnation}.",
                )
                continue

            best_candidate = np.asarray(best_candidate, dtype=np.float32)
            interior_points.append(best_candidate)
            all_points.append(best_candidate)
            all_points_array = np.vstack((all_points_array, best_candidate))
            stagnation = 0
            self._record(
                f"Tile {tile_index}: interior selected",
                f"Selected best candidate at {self._format_point(best_candidate)}, nearest_dist={math.sqrt(best_distance):.3f}.",
                highlight_point=best_candidate,
            )

        return interior_points

    def _get_shared_edge_cell_vertices(self, source_tile_index, target_tile_index):
        source = self.tile_polygons[source_tile_index]
        target = self.tile_polygons[target_tile_index]
        shared_edge = self._get_shared_edge_between_polygons(source, target)
        if shared_edge is None:
            return []

        edge_start, edge_end = shared_edge
        points = []
        for cell in self.tile_cells[source_tile_index]:
            for point in cell:
                if self._point_segment_distance_sq_2d(point, edge_start, edge_end) <= 1e-8:
                    if np.sum((point - edge_start) * (point - edge_start)) <= 1e-10:
                        continue
                    if np.sum((point - edge_end) * (point - edge_end)) <= 1e-10:
                        continue
                    points.append(point)

        deduplicated = []
        seen = set()
        for point in points:
            key = tuple(np.round(point, 6))
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(point)

        self._record(
            f"Tiles {source_tile_index}->{target_tile_index}: shared boundary",
            f"Collected {len(deduplicated)} subtile vertices from the already generated neighbor edge.",
            candidate_points=deduplicated,
        )
        return deduplicated

    def _polish_all_shared_edges(self):
        changed_pairs = 0
        before_count = sum(len(points) for points in self.tile_saved_points)

        for tile_index in range(len(self.tile_polygons)):
            for neighbor_index in range(tile_index + 1, len(self.tile_polygons)):
                shared_edge = self._get_shared_edge_between_polygons(
                    self.tile_polygons[tile_index],
                    self.tile_polygons[neighbor_index]
                )
                if shared_edge is None:
                    continue
                if self._polish_shared_edge(tile_index, neighbor_index, shared_edge):
                    changed_pairs += 1

        for tile_index in range(len(self.tile_cells)):
            self.tile_saved_points[tile_index] = []
            for cell in self.tile_cells[tile_index]:
                self._save_cell_points(tile_index, cell)

        after_count = sum(len(points) for points in self.tile_saved_points)
        threshold = self._polygon_average_edge_length(self.tile_polygons[0]) * cfg.SUBTILE_EDGE_POINT_SPACING_FACTOR * cfg.SUBTILE_EDGE_POLISH_MERGE_SPACING_FACTOR
        self._record(
            "Global edge polish",
            f"Merged shared-edge vertices closer than {threshold:.4f} ({cfg.SUBTILE_EDGE_POLISH_MERGE_SPACING_FACTOR:.2f} initial edge spacing). pairs_changed={changed_pairs}, saved_points {before_count}->{after_count}.",
        )

    def _polish_shared_edge(self, tile_index, neighbor_index, shared_edge):
        edge_start, edge_end = shared_edge
        refs = []
        refs.extend(self._get_cell_vertex_refs_on_edge(tile_index, edge_start, edge_end))
        refs.extend(self._get_cell_vertex_refs_on_edge(neighbor_index, edge_start, edge_end))
        if len(refs) < 2:
            return False

        edge_spacing = self._polygon_average_edge_length(self.tile_polygons[tile_index]) * cfg.SUBTILE_EDGE_POINT_SPACING_FACTOR
        merge_distance = edge_spacing * cfg.SUBTILE_EDGE_POLISH_MERGE_SPACING_FACTOR
        merge_distance_sq = merge_distance * merge_distance
        parent = list(range(len(refs)))

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

        for left_index in range(len(refs)):
            for right_index in range(left_index + 1, len(refs)):
                if np.sum((refs[left_index][3] - refs[right_index][3]) ** 2) <= merge_distance_sq:
                    union(left_index, right_index)

        clusters = {}
        for index, ref in enumerate(refs):
            clusters.setdefault(find(index), []).append(ref)

        changed = False
        for cluster in clusters.values():
            if len(cluster) < 2:
                continue
            representative = np.mean(np.asarray([ref[3] for ref in cluster], dtype=np.float64), axis=0).astype(np.float32)
            representative = self._closest_point_on_segment_2d(representative, edge_start, edge_end)
            for ref_tile_index, cell_index, vertex_index, point in cluster:
                if np.sum((point - representative) ** 2) <= 1e-14:
                    continue
                self.tile_cells[ref_tile_index][cell_index][vertex_index] = representative.copy()
                changed = True

        if changed:
            for changed_tile_index in (tile_index, neighbor_index):
                cleaned_cells = []
                for cell in self.tile_cells[changed_tile_index]:
                    cleaned = self._clean_polygon_vertices(cell)
                    if len(cleaned) >= 3:
                        cleaned_cells.append(cleaned)
                self.tile_cells[changed_tile_index] = cleaned_cells

        return changed

    def _get_cell_vertex_refs_on_edge(self, tile_index, edge_start, edge_end):
        refs = []
        endpoint_epsilon_sq = 1e-10
        boundary_epsilon_sq = 1e-8
        for cell_index, cell in enumerate(self.tile_cells[tile_index]):
            for vertex_index, point in enumerate(cell):
                if self._point_segment_distance_sq_2d(point, edge_start, edge_end) > boundary_epsilon_sq:
                    continue
                if (
                    np.sum((point - edge_start) ** 2) <= endpoint_epsilon_sq or
                    np.sum((point - edge_end) ** 2) <= endpoint_epsilon_sq
                ):
                    continue
                refs.append((tile_index, cell_index, vertex_index, point))
        return refs

    def _get_shared_edge_between_polygons(self, source, target):
        shared = []
        for point in source:
            if any(np.sum((point - target_point) * (point - target_point)) <= 1e-10 for target_point in target):
                shared.append(point)
        if len(shared) < 2:
            return None
        return shared[0], shared[1]

    def _save_cell_points(self, tile_index, cell):
        for point in cell:
            if self._contains_point(self.tile_saved_points[tile_index], point, epsilon=1e-7):
                continue
            self.tile_saved_points[tile_index].append(np.asarray(point, dtype=np.float32))

    def _contains_point(self, points, point, epsilon=1e-7):
        return any(np.sum((point - existing) * (point - existing)) <= epsilon * epsilon for existing in points)

    def _polish_tile_cells(self, tile_index, polygon, cells):
        side_length = self._polygon_average_edge_length(polygon)
        merge_distance = side_length * cfg.SUBTILE_POLISH_MERGE_DISTANCE_FACTOR
        before_count = sum(len(cell) for cell in cells)
        polished_cells = self._merge_nearby_cell_vertices(cells, polygon, merge_distance)
        after_count = sum(len(cell) for cell in polished_cells)

        self.tile_cells[tile_index] = polished_cells
        self.tile_saved_points[tile_index] = []
        for cell in polished_cells:
            self._save_cell_points(tile_index, cell)

        self._record(
            f"Tile {tile_index}: polish",
            f"Merged vertices closer than {merge_distance:.4f} ({cfg.SUBTILE_POLISH_MERGE_DISTANCE_FACTOR:.2f} tile side). vertices {before_count}->{after_count}.",
        )
        return polished_cells

    def _merge_nearby_cell_vertices(self, cells, boundary_polygon, merge_distance):
        if merge_distance <= 0 or not cells:
            return cells

        points = []
        for cell in cells:
            points.extend(cell)
        if not points:
            return cells

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
            if any(self._find_polygon_boundary_location(point, boundary_polygon, merge_distance * 0.25) is not None for point in cluster_points):
                representative = self._nearest_boundary_point(representative, boundary_polygon)
            representatives[root] = representative

        polished_cells = []
        point_index = 0
        for cell in cells:
            polished_cell = []
            for _ in cell:
                polished_cell.append(representatives[find(point_index)])
                point_index += 1

            polished_cell = self._clean_polygon_vertices(polished_cell)
            if len(polished_cell) >= 3:
                polished_cells.append(polished_cell)

        return polished_cells

    def _polygon_average_edge_length(self, polygon):
        return float(np.mean([
            np.linalg.norm(polygon[(index + 1) % len(polygon)] - polygon[index])
            for index in range(len(polygon))
        ]))

    def _polygon_area(self, polygon):
        return abs(self._polygon_signed_area(polygon))

    def _record(self, title, message, seed_points=None, saved_points=None, cells=None, candidate_points=None, lines=None, highlight_polygon=None, highlight_point=None):
        self.steps.append(DebugStep(
            title=title,
            message=message,
            seed_points=[list(points) for points in self.tile_seed_points] if seed_points is None else seed_points,
            saved_points=[list(points) for points in self.tile_saved_points] if saved_points is None else saved_points,
            cells=[list(polygons) for polygons in self.tile_cells] if cells is None else cells,
            candidate_points=candidate_points or [],
            lines=lines or [],
            highlight_polygon=highlight_polygon,
            highlight_point=highlight_point,
        ))

    def _make_tile_polygons(self, tile_count):
        polygons = []
        radius = 1.0
        half_width = math.sqrt(3.0) * 0.5 * radius
        half_height = radius * 0.5
        for q, r in self._make_hex_axial_coords(tile_count):
            center_x = math.sqrt(3.0) * radius * (q + r * 0.5)
            center_y = 1.5 * radius * r
            polygons.append([
                np.array([center_x + half_width, center_y + half_height], dtype=np.float32),
                np.array([center_x, center_y + radius], dtype=np.float32),
                np.array([center_x - half_width, center_y + half_height], dtype=np.float32),
                np.array([center_x - half_width, center_y - half_height], dtype=np.float32),
                np.array([center_x, center_y - radius], dtype=np.float32),
                np.array([center_x + half_width, center_y - half_height], dtype=np.float32),
            ])
        return polygons

    def _make_hex_axial_coords(self, tile_count):
        if tile_count <= 0:
            return []

        coords = [(0, 0)]
        directions = [
            (1, 0),
            (1, -1),
            (0, -1),
            (-1, 0),
            (-1, 1),
            (0, 1),
        ]
        radius = 1
        while len(coords) < tile_count:
            q = -radius
            r = radius
            for direction_q, direction_r in directions:
                for _ in range(radius):
                    if len(coords) >= tile_count:
                        return coords
                    coords.append((q, r))
                    q += direction_q
                    r += direction_r
            radius += 1
        return coords

    def _make_debug_bisector_line(self, mid_point, normal, polygon):
        direction = np.array([-normal[1], normal[0]], dtype=np.float32)
        norm = np.linalg.norm(direction)
        if norm <= 1e-8:
            return None
        direction /= norm
        span = max(2.0, float(np.ptp(np.asarray(polygon), axis=0).max()) * 2.0)
        return mid_point - direction * span, mid_point + direction * span

    def _voronoi_neighbor_indices(self, voronoi, point_count):
        neighbors = [set() for _ in range(point_count)]
        for point_a, point_b in voronoi.ridge_points:
            neighbors[int(point_a)].add(int(point_b))
            neighbors[int(point_b)].add(int(point_a))
        return [sorted(indices) for indices in neighbors]

    def _clip_polygon_to_convex_boundary(self, polygon, boundary):
        clipped = [np.asarray(point, dtype=np.float32) for point in polygon]
        orientation = self._polygon_signed_area(boundary)
        for index in range(len(boundary)):
            start = boundary[index]
            end = boundary[(index + 1) % len(boundary)]
            clipped = self._clip_polygon_to_boundary_edge(clipped, start, end, orientation)
            if len(clipped) < 3:
                return []
        return self._constrain_polygon_to_boundary(clipped, boundary)

    def _clip_polygon_to_boundary_edge(self, polygon, edge_start, edge_end, boundary_orientation):
        if not polygon:
            return []

        clipped = []
        previous = polygon[-1]
        previous_inside = self._is_inside_boundary_edge(previous, edge_start, edge_end, boundary_orientation)

        for current in polygon:
            current_inside = self._is_inside_boundary_edge(current, edge_start, edge_end, boundary_orientation)

            if current_inside != previous_inside:
                intersection = self._line_boundary_intersection(previous, current, edge_start, edge_end)
                if intersection is not None:
                    clipped.append(intersection)

            if current_inside:
                clipped.append(current)

            previous = current
            previous_inside = current_inside

        return self._remove_duplicate_polygon_vertices(clipped)

    def _is_inside_boundary_edge(self, point, edge_start, edge_end, boundary_orientation):
        edge = edge_end - edge_start
        relative = point - edge_start
        cross = edge[0] * relative[1] - edge[1] * relative[0]
        if boundary_orientation >= 0:
            return cross >= -1e-6
        return cross <= 1e-6

    def _line_boundary_intersection(self, start, end, edge_start, edge_end):
        direction = end - start
        edge = edge_end - edge_start
        denominator = direction[0] * edge[1] - direction[1] * edge[0]
        if abs(denominator) < 1e-8:
            return None

        relative = edge_start - start
        t = (relative[0] * edge[1] - relative[1] * edge[0]) / denominator
        t = np.clip(t, 0.0, 1.0)
        return start + direction * t

    def _constrain_polygon_to_boundary(self, polygon, boundary):
        constrained = []
        for point in polygon:
            if self._is_inside_convex_polygon(point, boundary):
                constrained.append(point)
            else:
                constrained.append(self._nearest_boundary_point(point, boundary))
        return self._remove_duplicate_polygon_vertices(constrained)

    def _is_inside_convex_polygon(self, point, boundary):
        orientation = self._polygon_signed_area(boundary)
        for index in range(len(boundary)):
            start = boundary[index]
            end = boundary[(index + 1) % len(boundary)]
            if not self._is_inside_boundary_edge(point, start, end, orientation):
                return False
        return True

    def _nearest_boundary_point(self, point, boundary):
        nearest_point = None
        nearest_distance_sq = float("inf")
        for index in range(len(boundary)):
            start = boundary[index]
            end = boundary[(index + 1) % len(boundary)]
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

    def _polygon_signed_area(self, polygon):
        area = 0.0
        for index, point in enumerate(polygon):
            next_point = polygon[(index + 1) % len(polygon)]
            area += float(point[0] * next_point[1] - next_point[0] * point[1])
        return area * 0.5

    def _clip_polygon_with_half_plane(self, polygon, line_point, line_normal):
        if not polygon:
            return []

        clipped = []
        previous = polygon[-1]
        previous_inside = np.dot(previous - line_point, line_normal) <= 1e-6

        for current in polygon:
            current_inside = np.dot(current - line_point, line_normal) <= 1e-6
            if current_inside != previous_inside:
                intersection = self._line_half_plane_intersection(previous, current, line_point, line_normal)
                if intersection is not None:
                    clipped.append(intersection)
            if current_inside:
                clipped.append(current)
            previous = current
            previous_inside = current_inside

        return self._remove_duplicate_polygon_vertices(clipped)

    def _line_half_plane_intersection(self, start, end, line_point, line_normal):
        direction = end - start
        denominator = np.dot(direction, line_normal)
        if abs(denominator) < 1e-8:
            return None
        t = np.dot(line_point - start, line_normal) / denominator
        t = np.clip(t, 0.0, 1.0)
        return start + direction * t

    def _remove_duplicate_polygon_vertices(self, polygon, distance_epsilon=1e-8):
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

    def _find_polygon_boundary_location(self, point, polygon, distance_epsilon=1e-6):
        for index in range(len(polygon)):
            start = polygon[index]
            end = polygon[(index + 1) % len(polygon)]
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

    def _is_far_enough(self, point, others, min_distance):
        return self._nearest_distance_sq(point, others) >= min_distance * min_distance

    def _nearest_distance_sq(self, point, others):
        if not others:
            return float("inf")
        other_points = np.asarray(others, dtype=np.float64)
        offsets = other_points - point
        return float(np.min(np.sum(offsets * offsets, axis=1)))

    def _points_in_polygon(self, points, polygon):
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

    def _format_point(self, point):
        return f"({point[0]:.3f}, {point[1]:.3f})"


class SubtileStepDebugApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Subtile step debugger")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.steps = []
        self.step_index = 0
        self.mode_frame = None
        self.canvas = None
        self.log = None
        self.status = None
        self.tile_polygons = []
        self.bounds = None
        self.view_scale = 1.0
        self.view_offset = np.array([0.0, 0.0], dtype=np.float32)
        self.drag_start = None
        self.drag_total = 0.0
        self.measure_points = []
        self.measure_label = None
        self.tile_count_var = tk.StringVar(value="4")
        self.voronoi_backend_var = tk.StringVar(value="step")
        self._show_mode_selector()

    def run(self):
        self.root.mainloop()

    def _show_mode_selector(self):
        self.mode_frame = tk.Frame(self.root, padx=24, pady=24)
        self.mode_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(self.mode_frame, text="Subtile Step Debugger", font=("Segoe UI", 20, "bold")).pack(pady=(80, 16))
        tk.Label(self.mode_frame, text="Choose a mode, then use Left/Right arrows to move one generation step at a time.").pack(pady=(0, 24))

        tk.Button(self.mode_frame, text="1 tile", width=24, command=lambda: self._start("single")).pack(pady=8)

        row = tk.Frame(self.mode_frame)
        row.pack(pady=8)
        tk.Label(row, text="Adjacent tiles:").pack(side=tk.LEFT, padx=(0, 8))
        tk.Entry(row, textvariable=self.tile_count_var, width=6).pack(side=tk.LEFT)
        tk.Button(row, text="N tiles", width=16, command=lambda: self._start("multi")).pack(side=tk.LEFT, padx=8)

        backend_frame = tk.LabelFrame(self.mode_frame, text="Voronoi backend", padx=12, pady=8)
        backend_frame.pack(pady=(20, 8))
        tk.Radiobutton(
            backend_frame,
            text="Step clipping: slow, every bisector is visible",
            variable=self.voronoi_backend_var,
            value="step",
        ).pack(anchor="w")
        tk.Radiobutton(
            backend_frame,
            text="Fast Voronoi: scipy.spatial.Voronoi, global cells",
            variable=self.voronoi_backend_var,
            value="fast",
        ).pack(anchor="w")

        tk.Label(
            self.mode_frame,
            text="Keys: Right/Left = next/previous step, Home/End = start/end.",
            fg="#555555",
        ).pack(pady=(24, 0))

    def _start(self, mode):
        try:
            tile_count = int(self.tile_count_var.get())
        except ValueError:
            tile_count = 4

        recorder = SubtileDebugRecorder(mode, tile_count, self.voronoi_backend_var.get())
        self.steps = recorder.build()
        self.tile_polygons = recorder.tile_polygons
        self.bounds = self._calculate_bounds(self.tile_polygons)
        self.view_scale = 1.0
        self.view_offset = np.array([0.0, 0.0], dtype=np.float32)
        self.drag_start = None
        self.drag_total = 0.0
        self.measure_points = []
        self.step_index = 0

        self.mode_frame.destroy()
        self._build_debug_ui()
        self._draw_current_step()

    def _build_debug_ui(self):
        toolbar = tk.Frame(self.root, padx=8, pady=6)
        toolbar.pack(fill=tk.X)
        tk.Button(toolbar, text="<", width=4, command=self._previous_step).pack(side=tk.LEFT)
        tk.Button(toolbar, text=">", width=4, command=self._next_step).pack(side=tk.LEFT, padx=(4, 12))
        self.status = tk.Label(toolbar, anchor="w")
        self.status.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.measure_label = tk.Label(toolbar, text="Distance: click two points", anchor="e")
        self.measure_label.pack(side=tk.RIGHT, padx=(12, 0))

        self.canvas = tk.Canvas(self.root, bg="#f7f7f3", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.log = tk.Text(self.root, height=LOG_HEIGHT, wrap=tk.WORD, font=("Consolas", 10))
        self.log.pack(fill=tk.X)

        self.root.bind("<Right>", lambda _event: self._next_step())
        self.root.bind("<Left>", lambda _event: self._previous_step())
        self.root.bind("<Home>", lambda _event: self._set_step(0))
        self.root.bind("<End>", lambda _event: self._set_step(len(self.steps) - 1))
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Button-4>", self._on_mouse_wheel)
        self.canvas.bind("<Button-5>", self._on_mouse_wheel)
        self.canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self.canvas.bind("<B1-Motion>", self._on_drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_end)

    def _next_step(self):
        self._set_step(min(len(self.steps) - 1, self.step_index + 1))

    def _previous_step(self):
        self._set_step(max(0, self.step_index - 1))

    def _set_step(self, index):
        if index == self.step_index:
            return
        self.step_index = index
        self._draw_current_step()

    def _draw_current_step(self):
        step = self.steps[self.step_index]
        self.canvas.delete("all")
        self.status.config(text=f"Step {self.step_index + 1}/{len(self.steps)}: {step.title}")
        self.canvas.create_text(
            12,
            12,
            anchor="nw",
            text="blue: created seed points   green: saved subtile vertices   gray: current candidates",
            fill="#333333",
            font=("Segoe UI", 10),
        )

        for tile_index, polygon in enumerate(self.tile_polygons):
            self._draw_polygon(polygon, fill="#fafafa", outline="#222222", width=2)
            center = np.mean(np.asarray(polygon), axis=0)
            self._draw_text(center, str(tile_index), fill="#666666")

        for cells in step.cells:
            for cell in cells:
                self._draw_polygon(cell, fill="#d7ecff", outline="#4f86b8", width=1)

        if step.highlight_polygon is not None:
            self._draw_polygon(step.highlight_polygon, fill="#ffe8a3", outline="#d89000", width=3)

        for line_start, line_end in step.lines:
            self._draw_line(line_start, line_end, fill="#a43bd1", width=2, dash=(5, 4))

        for tile_points in step.saved_points:
            for point in tile_points:
                self._draw_saved_point(point)

        for tile_points in step.seed_points:
            for point in tile_points:
                self._draw_point(point, radius=4, fill="#1f77b4", outline="#0c3d66")

        for point in step.candidate_points:
            self._draw_point(point, radius=3, fill="#cccccc", outline="#666666")

        if step.highlight_point is not None:
            self._draw_point(step.highlight_point, radius=7, fill="#ff3b30", outline="#8a130d")

        self._draw_measurement()
        self._update_log()

    def _on_mouse_wheel(self, event):
        if getattr(event, "num", None) == 4 or getattr(event, "delta", 0) > 0:
            factor = 1.12
        else:
            factor = 1.0 / 1.12

        old_scale = self.view_scale
        new_scale = float(np.clip(old_scale * factor, 0.35, 12.0))
        if abs(new_scale - old_scale) <= 1e-9:
            return

        mouse = np.array([event.x, event.y], dtype=np.float32)
        self.view_offset = mouse - (mouse - self.view_offset) * (new_scale / old_scale)
        self.view_scale = new_scale
        self._draw_current_step()

    def _on_drag_start(self, event):
        self.drag_start = np.array([event.x, event.y], dtype=np.float32)
        self.drag_total = 0.0

    def _on_drag_move(self, event):
        if self.drag_start is None:
            return
        current = np.array([event.x, event.y], dtype=np.float32)
        delta = current - self.drag_start
        self.drag_total += float(np.linalg.norm(delta))
        self.view_offset += delta
        self.drag_start = current
        self._draw_current_step()

    def _on_drag_end(self, event):
        if self.drag_total <= 4.0:
            self._try_select_measure_point(event.x, event.y)
        self.drag_start = None
        self.drag_total = 0.0

    def _try_select_measure_point(self, screen_x, screen_y):
        step = self.steps[self.step_index]
        points = self._current_measure_points(step)
        if not points:
            return

        click = np.array([screen_x, screen_y], dtype=np.float32)
        nearest_point = None
        nearest_distance = float("inf")
        for point in points:
            point_screen = np.asarray(self._world_to_screen(point), dtype=np.float32)
            distance = float(np.linalg.norm(point_screen - click))
            if distance < nearest_distance:
                nearest_distance = distance
                nearest_point = point

        if nearest_point is None or nearest_distance > 12.0:
            return

        nearest_point = np.asarray(nearest_point, dtype=np.float32)
        if len(self.measure_points) == 2:
            self.measure_points = []
        self.measure_points.append(nearest_point)
        self._update_measure_label()
        self._draw_current_step()

    def _current_measure_points(self, step):
        points = []
        for point_groups in (step.seed_points, step.saved_points):
            for tile_points in point_groups:
                points.extend(tile_points)
        points.extend(step.candidate_points)
        if step.highlight_point is not None:
            points.append(step.highlight_point)

        deduplicated = []
        seen = set()
        for point in points:
            key = tuple(np.round(point, 7))
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(np.asarray(point, dtype=np.float32))
        return deduplicated

    def _update_measure_label(self):
        if self.measure_label is None:
            return
        if len(self.measure_points) < 2:
            self.measure_label.config(text=f"Distance: point {len(self.measure_points)}/2")
            return

        distance = float(np.linalg.norm(self.measure_points[1] - self.measure_points[0]))
        side_length = self._tile_side_length()
        relative = distance / side_length if side_length > 1e-8 else 0.0
        self.measure_label.config(text=f"Distance: {distance:.4f} = {relative:.4f} tile sides")

    def _tile_side_length(self):
        if not self.tile_polygons:
            return 1.0
        polygon = self.tile_polygons[0]
        lengths = [
            float(np.linalg.norm(polygon[(index + 1) % len(polygon)] - polygon[index]))
            for index in range(len(polygon))
        ]
        return float(np.mean(lengths))

    def _draw_measurement(self):
        if not self.measure_points:
            return
        for point in self.measure_points:
            x, y = self._world_to_screen(point)
            radius = 10
            self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, outline="#ff3b30", width=3)
        if len(self.measure_points) == 2:
            self._draw_line(self.measure_points[0], self.measure_points[1], fill="#ff3b30", width=2)
            midpoint = (self.measure_points[0] + self.measure_points[1]) * 0.5
            distance = float(np.linalg.norm(self.measure_points[1] - self.measure_points[0]))
            side_length = self._tile_side_length()
            relative = distance / side_length if side_length > 1e-8 else 0.0
            self._draw_text(midpoint, f"{distance:.3f} / {relative:.3f}s", fill="#b00000")

    def _update_log(self):
        start = max(0, self.step_index - LOG_HEIGHT + 2)
        visible_steps = self.steps[start:self.step_index + 1]
        text = "\n".join(
            f"{start + offset + 1:04d} | {step.title}: {step.message}"
            for offset, step in enumerate(visible_steps)
        )
        self.log.config(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.insert(tk.END, text)
        self.log.config(state=tk.NORMAL)

    def _calculate_bounds(self, polygons):
        points = np.asarray([point for polygon in polygons for point in polygon], dtype=np.float32)
        min_xy = points.min(axis=0)
        max_xy = points.max(axis=0)
        padding = np.array([0.2, 0.2], dtype=np.float32)
        return min_xy - padding, max_xy + padding

    def _world_to_screen(self, point):
        canvas_width = max(1, self.canvas.winfo_width())
        canvas_height = max(1, self.canvas.winfo_height())
        min_xy, max_xy = self.bounds
        world_size = max_xy - min_xy
        scale = min((canvas_width - 80) / world_size[0], (canvas_height - 80) / world_size[1])
        offset_x = (canvas_width - world_size[0] * scale) * 0.5
        offset_y = (canvas_height - world_size[1] * scale) * 0.5
        x = offset_x + (point[0] - min_xy[0]) * scale
        y = canvas_height - (offset_y + (point[1] - min_xy[1]) * scale)
        screen_point = np.array([x, y], dtype=np.float32)
        screen_center = np.array([canvas_width * 0.5, canvas_height * 0.5], dtype=np.float32)
        transformed = screen_center + (screen_point - screen_center) * self.view_scale + self.view_offset
        return transformed[0], transformed[1]

    def _draw_polygon(self, polygon, fill, outline, width):
        coords = []
        for point in polygon:
            coords.extend(self._world_to_screen(point))
        self.canvas.create_polygon(coords, fill=fill, outline=outline, width=width)

    def _draw_line(self, start, end, fill, width=1, dash=None):
        x1, y1 = self._world_to_screen(start)
        x2, y2 = self._world_to_screen(end)
        self.canvas.create_line(x1, y1, x2, y2, fill=fill, width=width, dash=dash)

    def _draw_point(self, point, radius, fill, outline):
        x, y = self._world_to_screen(point)
        self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=fill, outline=outline)

    def _draw_saved_point(self, point):
        x, y = self._world_to_screen(point)
        radius = 4
        self.canvas.create_rectangle(x - radius, y - radius, x + radius, y + radius, fill="#2ca02c", outline="#145214")

    def _draw_text(self, point, text, fill):
        x, y = self._world_to_screen(point)
        self.canvas.create_text(x, y, text=text, fill=fill, font=("Segoe UI", 14, "bold"))


if __name__ == "__main__":
    SubtileStepDebugApp().run()
