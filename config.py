from enum import Enum
import numpy as np

# --- Terrain ---
class TerrainType(Enum):
    # Water
    OCEAN = (30, 144, 255)
    COAST = (100, 149, 237)
    SHALLOWS = (135, 206, 250) # Not used yet
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
    PLAINS = (152, 251, 152) # Not used yet

# --- Renderer Settings ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60
CAPTION = "Spherical World"

# Colors
EDGE_COLOR = (40, 40, 40)
BACKGROUND_COLOR = (0, 0, 0)
RIVER_COLOR = np.array([60, 120, 200])

# --- Camera & Input ---
ROTATION_SENSITIVITY = 0.1
KEYBOARD_ROTATION_SPEED = 0.005
DAMPING = 0.95
ZOOM_SPEED = 0.1
ZOOM_SMOOTHING_FACTOR = 0.1
MIN_ZOOM = 0.5
MAX_ZOOM = 5.0
INITIAL_SCALE_FACTOR = 250

# --- World Generation ---
SUBDIVISION_LEVEL = 4
RIVER_COUNT = 150
RIVER_ELEVATION = 0.99
RIVER_BASE_WIDTH = 0.002
RIVER_WIDTH_FACTOR = 0.01

# --- Lighting ---
LIGHT_SOURCE_VECTOR = np.array([0.3, 0.5, -0.8])
AMBIENT_LIGHT = 0.3
