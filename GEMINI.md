# Gemini CLI Context: Spherical Polygon Game

This document provides context for the Gemini CLI to understand and assist with the development of this project.

## Project Overview

This is a Python-based strategy game prototype that renders a spherical world. The core technologies used are:

*   **Python:** The primary programming language.
*   **Pygame:** Used for rendering the 2D projection of the 3D world and handling user input.
*   **NumPy:** Extensively used for 3D graphics calculations, vector operations, and matrix transformations.

The project generates a planet-like sphere procedurally. Key features include:

*   **Polyhedron-based Sphere:** The world geometry is based on a subdivided icosahedron (a type of Goldberg polyhedron) to create a sphere with relatively uniform hexagonal and pentagonal tiles.
*   **Procedural Terrain:** Terrain features like land, oceans, mountains, and different biomes are generated using Perlin noise.
*   **River Generation:** A system for generating river networks that flow from high elevations towards the sea.
*   **World Caching:** To speed up load times, the complex generated world geometry is cached to a `.pkl` file (`world_cache_level_*.pkl`). The cache is invalidated if the subdivision level in `config.py` is changed.
*   **3D Rendering:** A custom 3D renderer is implemented to project the spherical world onto the 2D screen, including back-face culling and basic lighting.
*   **User Interaction:** The camera can be rotated using the mouse or WASD keys, and zoomed with the mouse wheel. A debug overlay can be toggled with the F3 key.

## Building and Running

The project is intended to be run within a Python virtual environment.

1.  **Setup (if not already done):**
    *   Create a virtual environment: `python -m venv .venv`
    *   Activate it: `call .venv\Scripts\activate.bat`
    *   Install dependencies: `pip install pygame numpy perlin-noise` (based on imports)

2.  **Running the Application:**
    *   The simplest way to run the application is to execute the `run.bat` script.
    *   Alternatively, activate the virtual environment and run the main script directly: `python main.py`

## Development Conventions

*   **Configuration:** Project settings such as screen resolution, world generation parameters, and colors are centralized in `config.py`.
*   **Modularity:** The code is organized into distinct modules:
    *   `main.py`: The main application entry point.
    *   `game_world.py`: Handles the logic for generating and managing the world state.
    *   `renderer.py`: Contains the Pygame-based rendering engine.
    *   `geometry.py`: Defines the `Vertex` class and related geometric utilities.
    *   `polyhedron_generator.py`: Logic for creating the base icosahedron and subdividing it.
    *   `tile.py`: Defines the `Tile` class, representing a single polygon on the sphere.
    *   `river_generator.py`: Contains the logic for creating river paths.
*   **State:** The application state is managed primarily within the `GameWorld` and `Renderer` classes. The generated world data is owned by the `GameWorld` instance.
*   **Caching:** Be aware of the `world_cache_level_*.pkl` files. Deleting these files will force a full regeneration of the world on the next run, which can be useful for testing changes to the world generation algorithms.
