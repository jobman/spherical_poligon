import pygame
import math
import asyncio
import platform
from collections import defaultdict

# Настройки окна
WIDTH, HEIGHT = 800, 600
FPS = 60

# Инициализация Pygame
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Geodesic Sphere")
clock = pygame.time.Clock()

# Класс для представления вершины
class Vertex:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def normalize(self):
        length = math.sqrt(self.x**2 + self.y**2 + self.z**2)
        if length > 0:
            self.x /= length
            self.y /= length
            self.z /= length

    def to_screen(self):
        # Простая ортографическая проекция
        scale = 200
        x = WIDTH / 2 + self.x * scale
        y = HEIGHT / 2 + self.y * scale
        return x, y

# Класс для представления грани
class Face:
    def __init__(self, vertices):
        self.vertices = vertices

# Класс для представления полигедра
class Polyhedron:
    def __init__(self):
        self.vertices = []
        self.faces = []
        self.edges = defaultdict(list)

    def add_vertex(self, vertex):
        self.vertices.append(vertex)

    def add_face(self, face):
        self.faces.append(face)
        # Обновляем ребра
        for i in range(len(face.vertices)):
            v1 = face.vertices[i]
            v2 = face.vertices[(i + 1) % len(face.vertices)]
            self.edges[v1].append(v2)
            self.edges[v2].append(v1)

# Создание икосаэдра
def create_icosahedron():
    t = (1.0 + math.sqrt(5.0)) / 2.0
    poly = Polyhedron()
    vertices = [
        Vertex(-1, t, 0), Vertex(1, t, 0), Vertex(-1, -t, 0), Vertex(1, -t, 0),
        Vertex(0, -1, t), Vertex(0, 1, t), Vertex(0, -1, -t), Vertex(0, 1, -t),
        Vertex(t, 0, -1), Vertex(t, 0, 1), Vertex(-t, 0, -1), Vertex(-t, 0, 1)
    ]
    for v in vertices:
        v.normalize()
        poly.add_vertex(v)
    
    faces = [
        [0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11],
        [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8],
        [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
        [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1]
    ]
    for f in faces:
        poly.add_face(Face([vertices[i] for i in f]))
    return poly

# Операция усечения (Truncate)
def truncate(poly):
    new_poly = Polyhedron()
    vertex_map = {}
    
    # Для каждой грани создаем новые вершины
    for face in poly.faces:
        n = len(face.vertices)
        centroid = Vertex(0, 0, 0)
        for v in face.vertices:
            centroid.x += v.x
            centroid.y += v.y
            centroid.z += v.z
        centroid.x /= n
        centroid.y /= n
        centroid.z /= n
        centroid.normalize()
        
        new_vertices = []
        for v in face.vertices:
            if v not in vertex_map:
                vertex_map[v] = Vertex(v.x, v.y, v.z)
                new_poly.add_vertex(vertex_map[v])
            new_vertices.append(vertex_map[v])
        
        # Создаем новую грань для центроида
        new_poly.add_face(Face(new_vertices))
    
    return new_poly

# Операция двойственности (Dual)
def dual(poly):
    new_poly = Polyhedron()
    
    # Центроиды граней становятся новыми вершинами
    for face in poly.faces:
        centroid = Vertex(0, 0, 0)
        n = len(face.vertices)
        for v in face.vertices:
            centroid.x += v.x
            centroid.y += v.y
            centroid.z += v.z
        centroid.x /= n
        centroid.y /= n
        centroid.z /= n
        centroid.normalize()
        new_poly.add_vertex(centroid)
    
    # Создаем новые грани на основе вершин
    for i, v in enumerate(poly.vertices):
        neighbors = poly.edges[v]
        new_face_vertices = []
        for neighbor in neighbors:
            # Находим грань, содержащую v и neighbor
            for j, face in enumerate(poly.faces):
                if v in face.vertices and neighbor in face.vertices:
                    new_face_vertices.append(new_poly.vertices[j])
        new_poly.add_face(Face(new_face_vertices))
    
    return new_poly

# Создание геодезической сферы
def create_geodesic_sphere():
    poly = create_icosahedron()
    poly = truncate(poly)  # t
    poly = dual(poly)      # d
    poly = truncate(poly)  # t
    return poly

# Рендеринг
def draw_polyhedron(screen, poly):
    screen.fill((0, 0, 0))
    for face in poly.faces:
        points = [v.to_screen() for v in face.vertices]
        pygame.draw.polygon(screen, (255, 255, 255), points, 1)

# Основной цикл
polyhedron = create_geodesic_sphere()
mouse_dragging = False
last_mouse_pos = None
rotation_x = 0
rotation_y = 0

def setup():
    pass

def update_loop():
    global mouse_dragging, last_mouse_pos, rotation_x, rotation_y
    
    # Обработка событий мыши
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            return
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Левая кнопка мыши
                mouse_dragging = True
                last_mouse_pos = event.pos
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                mouse_dragging = False
        elif event.type == pygame.MOUSEMOTION and mouse_dragging:
            dx, dy = event.pos[0] - last_mouse_pos[0], event.pos[1] - last_mouse_pos[1]
            rotation_y += dx * 0.01
            rotation_x += dy * 0.01
            last_mouse_pos = event.pos
    
    # Применение вращения
    for v in polyhedron.vertices:
        # Вращение вокруг оси Y
        x = v.x * math.cos(rotation_y) - v.z * math.sin(rotation_y)
        z = v.x * math.sin(rotation_y) + v.z * math.cos(rotation_y)
        v.x = x
        v.z = z
        # Вращение вокруг оси X
        y = v.y * math.cos(rotation_x) - v.z * math.sin(rotation_x)
        z = v.y * math.sin(rotation_x) + v.z * math.cos(rotation_x)
        v.y = y
        v.z = z
    
    draw_polyhedron(screen, polyhedron)
    pygame.display.flip()

async def main():
    setup()
    while True:
        update_loop()
        await asyncio.sleep(1.0 / FPS)

if platform.system() == "Emscripten":
    asyncio.ensure_future(main())
else:
    if __name__ == "__main__":
        asyncio.run(main())