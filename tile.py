
import numpy as np
from config import TerrainType

class Tile:
    def __init__(self, id, vertices, normal):
        self.id = id
        self.vertices = vertices
        self.normal = normal
        self.terrain_type = None
        self.height = 0.0
        self.neighbors = []

    def __getstate__(self):
        state = self.__dict__.copy()
        # Don't pickle neighbors, it's rebuilt
        if 'neighbors' in state:
            del state['neighbors']
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.neighbors = []

    def is_water(self):
        return self.terrain_type in [TerrainType.OCEAN, TerrainType.COAST, TerrainType.ICE]

    @property
    def color(self):
        return np.array(self.terrain_type.value) if self.terrain_type else np.array([200, 200, 200])

    @property
    def center(self):
        return np.mean([v.to_np() for v in self.vertices], axis=0)
        
    def __repr__(self):
        return f"Tile({self.id}, terrain={self.terrain_type.name if self.terrain_type else 'None'}, height={self.height:.2f})"
        
    def __lt__(self, other):
        return self.height < other.height
        
    def __eq__(self, other):
        return isinstance(other, Tile) and self.id == other.id

    def __hash__(self):
        return hash(self.id)
