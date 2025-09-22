import pygame
from game_world import GameWorld
from renderer import Renderer
import config as cfg

if __name__ == "__main__":
    pygame.init()

    # 1. Create the world
    game_world = GameWorld(subdivision_level=cfg.SUBDIVISION_LEVEL)

    # 2. Get the data for rendering
    render_data = game_world.get_render_data()

    # 3. Create the renderer with the data
    renderer = Renderer(render_data, game_world)
    
    # 4. Run the main loop
    running = True
    while running:
        running = renderer.run_frame()
    
    pygame.quit()