import math
import numpy as np

class Vertex:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = float(x), float(y), float(z)

    def to_np(self):
        return np.array([self.x, self.y, self.z])

    def normalize(self):
        length = math.sqrt(self.x**2 + self.y**2 + self.z**2)
        if length > 0:
            self.x /= length
            self.y /= length
            self.z /= length

    def __hash__(self):
        return hash((round(self.x, 5), round(self.y, 5), round(self.z, 5)))

    def __eq__(self, other):
        return hash(self) == hash(other)