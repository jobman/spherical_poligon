import math
import numpy as np

class Vertex:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = float(x), float(y), float(z)
        self._hash = None

    def to_np(self):
        return np.array([self.x, self.y, self.z])

    def normalize(self):
        length = math.sqrt(self.x**2 + self.y**2 + self.z**2)
        if length > 0:
            self.x /= length
            self.y /= length
            self.z /= length
        self._hash = None # Invalidate hash after normalization

    def __hash__(self):
        if self._hash is None:
            self._hash = hash((round(self.x, 5), round(self.y, 5), round(self.z, 5)))
        return self._hash

    def __eq__(self, other):
        return isinstance(other, Vertex) and \
               round(self.x, 5) == round(other.x, 5) and \
               round(self.y, 5) == round(other.y, 5) and \
               round(self.z, 5) == round(other.z, 5)
