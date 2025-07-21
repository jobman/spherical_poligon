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
        del state["neighbors"]
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.neighbors = []

    def is_water(self):
        return self.terrain_type in [TerrainType.OCEAN, TerrainType.COAST, TerrainType.ICE]

    @property
    def color(self):
        return np.array(self.terrain_type.value) if self.terrain_type else np.array([200, 200, 200])