import pygame
from pygame.locals import *
from game_world import GameWorld
from renderer import Renderer
import config as cfg

if __name__ == "__main__":
    pygame.init()
    game_world = GameWorld(subdivision_level=cfg.SUBDIVISION_LEVEL)
    renderer = Renderer(game_world)
    renderer.run()