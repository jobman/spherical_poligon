import pygame
from game_world import GameWorld
from renderer import Renderer

if __name__ == "__main__":
    pygame.init()
    game_world = GameWorld(subdivision_level=3)
    renderer = Renderer(game_world)
    renderer.run()