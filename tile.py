class Tile:
    def __init__(self, id, vertices, normal, color):
        self.id = id
        self.vertices = vertices
        self.normal = normal
        self.color = color
        self.neighbors = []