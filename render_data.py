
import numpy as np
from dataclasses import dataclass, field

@dataclass
class RenderData:
    tile_vertices: np.ndarray = field(default_factory=lambda: np.array([]))
    tile_colors: np.ndarray = field(default_factory=lambda: np.array([]))
    tile_normals: np.ndarray = field(default_factory=lambda: np.array([]))
    edge_vertices: np.ndarray = field(default_factory=lambda: np.array([]))
    river_vertices: np.ndarray = field(default_factory=lambda: np.array([]))
    river_colors: np.ndarray = field(default_factory=lambda: np.array([]))
