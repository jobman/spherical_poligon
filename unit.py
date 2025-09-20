class Unit:
    def __init__(self, tile, owner):
        self.tile = tile
        self.owner = owner
        self.tile.unit = self

    def move_to(self, new_tile):
        if new_tile in self.tile.neighbors and not new_tile.unit:
            self.tile.unit = None
            self.tile = new_tile
            new_tile.unit = self
            return True
        return False
