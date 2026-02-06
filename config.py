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
FULLSCREEN = True
FPS = 60
CAPTION = "Spherical World"

# Colors
EDGE_COLOR = (40, 40, 40)
BACKGROUND_COLOR = (0, 0, 0)
RIVER_COLOR = np.array([60, 120, 200])

# --- Camera & Input ---
ROTATION_SENSITIVITY = 0.007
KEYBOARD_ROTATION_SPEED = 0.003
DAMPING = 0.95
ZOOM_SPEED = 0.1
ZOOM_SMOOTHING_FACTOR = 0.1
MIN_ZOOM = 0.38
MAX_ZOOM = 1.2
MIN_ZOOM_STEP = 0.02
MAX_ZOOM_STEP = 0.15
INITIAL_SCALE_FACTOR = 250

# --- World Generation ---
SUBDIVISION_LEVEL = 5
RIVER_COUNT = 150
RIVER_ELEVATION = 0.98
RIVER_BASE_WIDTH = 0.002
RIVER_WIDTH_FACTOR = 0.01
RIVER_DELTA_LENGTH_FACTOR = 1.5 # Controls the length of the river delta, proportional to its width

# --- Lighting ---
LIGHT_SOURCE_VECTOR = np.array([0.8, 0.5, -0.8])
AMBIENT_LIGHT = 0.3
LIGHT_ROTATION_SPEED = 0.0001 # Radians per frame
