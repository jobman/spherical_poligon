
import numpy as np
from queue import PriorityQueue

def get_common_vertices(tile1, tile2):
    return list(set(tile1.vertices) & set(tile2.vertices))

def distance_to(tile1, tile2):
    return np.linalg.norm(tile1.center - tile2.center)

def get_path_to(start_tile, target_tile, max_depth=10):
    q = PriorityQueue()
    q.put((0, [start_tile]))
    visited = {start_tile}
    
    while not q.empty():
        cost, path = q.get()
        current = path[-1]
        
        if current == target_tile:
            return path
        
        if len(path) > max_depth:
            continue
        
        for neighbor in current.neighbors:
            if neighbor not in visited:
                visited.add(neighbor)
                new_cost = len(path) + distance_to(current, neighbor)
                new_path = path + [neighbor]
                q.put((new_cost, new_path))
                
    return None

def get_neighbors_within_distance(start_tile, distance):
    neighbors_in_range = []
    q = [start_tile]
    visited = {start_tile}
    
    while q:
        current = q.pop(0)
        if distance_to(start_tile, current) <= distance:
            if current != start_tile:
                neighbors_in_range.append(current)
            
            for neighbor in current.neighbors:
                if neighbor not in visited:
                    visited.add(neighbor)
                    q.append(neighbor)
                    
    return neighbors_in_range

def get_geodesic_distance_to(tile1, tile2):
    dot_product = np.dot(tile1.center, tile2.center)
    dot_product = np.clip(dot_product, -1.0, 1.0)
    angle = np.arccos(dot_product)
    return angle
