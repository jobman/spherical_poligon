import numpy as np
from collections import defaultdict

class SpatialHashGrid:
    def __init__(self, tiles, cell_size=0.1):
        self.cell_size = cell_size
        self.grid = defaultdict(list)
        if tiles:
            for tile in tiles:
                self.insert(tile)

    def _hash(self, point):
        return tuple(np.floor(point / self.cell_size).astype(int))

    def insert(self, tile):
        key = self._hash(tile.center)
        self.grid[key].append(tile)

    def query(self, point):
        center_key = self._hash(point)
        candidate_tiles = set() # Use a set to avoid duplicates
        
        # Query the 3x3x3 cube of cells around the point's cell
        for i in range(-1, 2):
            for j in range(-1, 2):
                for k in range(-1, 2):
                    key = (center_key[0] + i, center_key[1] + j, center_key[2] + k)
                    # No need to check if key in grid, defaultdict handles it
                    candidate_tiles.update(self.grid[key])
        
        return list(candidate_tiles)
