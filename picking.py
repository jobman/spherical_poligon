import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *

def get_ray(x, y, width, height, camera):
    viewport = glGetIntegerv(GL_VIEWPORT)
    modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
    projection = glGetDoublev(GL_PROJECTION_MATRIX)

    win_x, win_y = float(x), float(viewport[3] - y)

    near = gluUnProject(win_x, win_y, 0.0, modelview, projection, viewport)
    far = gluUnProject(win_x, win_y, 1.0, modelview, projection, viewport)

    ray_dir = np.array(far) - np.array(near)
    ray_dir /= np.linalg.norm(ray_dir)

    return np.array(near), ray_dir

def ray_sphere_intersection(ray_origin, ray_dir, sphere_radius=1.0):
    oc = ray_origin # Sphere is at origin
    a = np.dot(ray_dir, ray_dir)
    b = 2.0 * np.dot(oc, ray_dir)
    c = np.dot(oc, oc) - sphere_radius**2
    discriminant = b**2 - 4*a*c
    if discriminant < 0:
        return None
    else:
        t = (-b - np.sqrt(discriminant)) / (2.0 * a)
        if t < 0: # Intersection is behind the camera
             t = (-b + np.sqrt(discriminant)) / (2.0 * a)
             if t < 0:
                return None
        return ray_origin + t * ray_dir

def get_tile_at_pos(x, y, width, height, camera, game_world):
    ray_origin, ray_dir = get_ray(x, y, width, height, camera)
    
    intersection_point = ray_sphere_intersection(ray_origin, ray_dir)

    if intersection_point is None:
        return None

    candidate_tiles = game_world.spatial_hash_grid.query(intersection_point)

    if not candidate_tiles:
        return None

    closest_tile = None
    min_dist_sq = float('inf')

    for tile in candidate_tiles:
        dist_sq = np.sum((tile.center - intersection_point)**2)
        if dist_sq < min_dist_sq:
            min_dist_sq = dist_sq
            closest_tile = tile
            
    return closest_tile

def get_subtile_at_pos(x, y, width, height, camera, game_world):
    ray_origin, ray_dir = get_ray(x, y, width, height, camera)
    tile = get_tile_at_ray(ray_origin, ray_dir, game_world)
    if tile is None or not tile.subtiles:
        return tile, None

    hit_point = _ray_tile_plane_intersection(ray_origin, ray_dir, tile)
    if hit_point is None:
        return tile, None

    basis_origin, basis_u, basis_v = _make_tile_projection_basis(tile)
    point_2d = _project_point_to_2d(hit_point, basis_origin, basis_u, basis_v)

    for subtile in tile.subtiles:
        subtile_polygon_2d = [
            _project_point_to_2d(vertex, basis_origin, basis_u, basis_v)
            for vertex in subtile.vertices
        ]
        if _point_in_polygon_2d(point_2d, subtile_polygon_2d):
            return tile, subtile

    closest_subtile = _get_closest_subtile_by_center(hit_point, tile.subtiles)
    return tile, closest_subtile

def get_tile_at_ray(ray_origin, ray_dir, game_world):
    intersection_point = ray_sphere_intersection(ray_origin, ray_dir)
    if intersection_point is None:
        return None

    candidate_tiles = game_world.spatial_hash_grid.query(intersection_point)
    if not candidate_tiles:
        return None

    closest_tile = None
    min_dist_sq = float('inf')

    for tile in candidate_tiles:
        dist_sq = np.sum((tile.center - intersection_point)**2)
        if dist_sq < min_dist_sq:
            min_dist_sq = dist_sq
            closest_tile = tile

    return closest_tile

def _ray_tile_plane_intersection(ray_origin, ray_dir, tile):
    normal = tile.normal
    denominator = float(np.dot(ray_dir, normal))
    if abs(denominator) <= 1e-8:
        return None

    t = float(np.dot(tile.center - ray_origin, normal) / denominator)
    if t < 0:
        return None

    return ray_origin + ray_dir * t

def _make_tile_projection_basis(tile):
    center = tile.center
    normal = tile.normal / np.linalg.norm(tile.normal)
    basis_u = tile.vertices[0].to_np() - center
    basis_u -= normal * np.dot(basis_u, normal)
    if np.linalg.norm(basis_u) < 1e-8:
        fallback = np.array([1.0, 0.0, 0.0])
        if abs(np.dot(fallback, normal)) > 0.9:
            fallback = np.array([0.0, 1.0, 0.0])
        basis_u = np.cross(normal, fallback)
    basis_u /= np.linalg.norm(basis_u)
    basis_v = np.cross(normal, basis_u)
    basis_v /= np.linalg.norm(basis_v)
    return center, basis_u, basis_v

def _project_point_to_2d(point, basis_origin, basis_u, basis_v):
    offset = np.asarray(point, dtype=np.float32) - basis_origin
    return np.array([np.dot(offset, basis_u), np.dot(offset, basis_v)], dtype=np.float32)

def _point_in_polygon_2d(point, polygon):
    if len(polygon) < 3:
        return False

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

def _get_closest_subtile_by_center(point, subtiles):
    closest_subtile = None
    min_dist_sq = float("inf")
    for subtile in subtiles:
        if not subtile.vertices:
            continue
        center = np.mean(np.asarray(subtile.vertices, dtype=np.float32), axis=0)
        dist_sq = float(np.sum((center - point) ** 2))
        if dist_sq < min_dist_sq:
            min_dist_sq = dist_sq
            closest_subtile = subtile
    return closest_subtile
