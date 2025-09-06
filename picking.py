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
