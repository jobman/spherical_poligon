from enum import Enum
import numpy as np

class TerrainType(Enum):
    # Water
    OCEAN = (30, 144, 255)
    COAST = (100, 149, 237)
    SHALLOWS = (135, 206, 250)
    ICE = (240, 248, 255)
    
    # Land
    GRASSLAND = (34, 139, 34)
    FOREST = (0, 100, 0)
    HILLS = (139, 137, 112)
    MOUNTAINS = (105, 105, 105)
    DESERT = (244, 164, 96)
    SAVANNA = (218, 165, 32)
    TUNDRA = (135, 142, 150)
    SNOW = (255, 250, 250)
    PLAINS = (152, 251, 152)

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

    @property
    def color(self):
        return np.array(self.terrain_type.value) if self.terrain_type else np.array([200, 200, 200])