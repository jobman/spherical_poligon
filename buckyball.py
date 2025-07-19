import pygame
import math
from collections import defaultdict
import numpy as np

# --- Constants ---
WIDTH, HEIGHT = 800, 600
FPS = 60
BLACK = (0, 0, 0)
PENTAGON_COLOR = np.array([210, 210, 240])
HEXAGON_COLOR = np.array([240, 220, 220])
EDGE_COLOR = (40, 40, 40)
LIGHT_SOURCE = np.array([0.5, 0.7, -1])

# --- Pygame Setup ---
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Goldberg Polyhedron")
clock = pygame.time.Clock()

# --- Geometry Classes ---
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

class Face:
    def __init__(self, vertices):
        self.vertices = vertices

class Polyhedron:
    def __init__(self, vertices, faces):
        self.vertices = vertices
        self.faces = faces

# --- Geometry Generation ---
def create_icosahedron():
    t = (1.0 + math.sqrt(5.0)) / 2.0
    verts = [
        Vertex(-1, t, 0), Vertex(1, t, 0), Vertex(-1, -t, 0), Vertex(1, -t, 0),
        Vertex(0, -1, t), Vertex(0, 1, t), Vertex(0, -1, -t), Vertex(0, 1, -t),
        Vertex(t, 0, -1), Vertex(t, 0, 1), Vertex(-t, 0, -1), Vertex(-t, 0, 1)
    ]
    for v in verts: v.normalize()

    faces_indices = [
        0, 11, 5,  0, 5, 1,  0, 1, 7,  0, 7, 10,  0, 10, 11,
        1, 5, 9,  5, 11, 4,  11, 10, 2,  10, 7, 6,  7, 1, 8,
        3, 9, 4,  3, 4, 2,  3, 2, 6,  3, 6, 8,  3, 8, 9,
        4, 9, 5,  2, 4, 11,  6, 2, 10,  8, 6, 7,  9, 8, 1
    ]
    return Polyhedron(verts, [Face([verts[i] for i in faces_indices[j:j+3]]) for j in range(0, len(faces_indices), 3)])

def subdivide(poly):
    """Subdivides each triangular face of a polyhedron into 4 smaller triangles."""
    new_vertices = list(poly.vertices)
    new_faces = []
    midpoint_cache = {}

    for face in poly.faces:
        v1, v2, v3 = face.vertices

        def get_midpoint(p1, p2):
            key = tuple(sorted((poly.vertices.index(p1), poly.vertices.index(p2))))
            if key in midpoint_cache:
                return midpoint_cache[key]
            
            mid_v = Vertex((p1.x + p2.x) / 2, (p1.y + p2.y) / 2, (p1.z + p2.z) / 2)
            mid_v.normalize()
            new_vertices.append(mid_v)
            midpoint_cache[key] = mid_v
            return mid_v

        m1 = get_midpoint(v1, v2)
        m2 = get_midpoint(v2, v3)
        m3 = get_midpoint(v3, v1)

        new_faces.append(Face([v1, m1, m3]))
        new_faces.append(Face([v2, m2, m1]))
        new_faces.append(Face([v3, m3, m2]))
        new_faces.append(Face([m1, m2, m3]))

    return Polyhedron(new_vertices, new_faces)

def create_goldberg_polyhedron(subdivision_level=1):
    """Creates a Goldberg polyhedron by taking the dual of a subdivided icosahedron."""
    if subdivision_level < 1: subdivision_level = 1
    
    # 1. Create a subdivided icosahedron (geodesic sphere)
    geodesic = create_icosahedron()
    for _ in range(subdivision_level):
        geodesic = subdivide(geodesic)

    # 2. The vertices of the Goldberg are the centroids of the geodesic's faces
    goldberg_verts = []
    face_centroid_map = {}
    for i, face in enumerate(geodesic.faces):
        c_x = sum(v.x for v in face.vertices) / 3
        c_y = sum(v.y for v in face.vertices) / 3
        c_z = sum(v.z for v in face.vertices) / 3
        centroid = Vertex(c_x, c_y, c_z)
        centroid.normalize()
        goldberg_verts.append(centroid)
        face_centroid_map[i] = centroid

    # 3. The faces of the Goldberg correspond to the vertices of the geodesic
    goldberg_faces = []
    vert_to_face_idx_map = defaultdict(list)
    for i, face in enumerate(geodesic.faces):
        for v in face.vertices:
            vert_to_face_idx_map[v].append(i)

    for geo_vert, face_indices in vert_to_face_idx_map.items():
        new_face_verts_unsorted = [face_centroid_map[i] for i in face_indices]
        
        # Sort the new vertices by angle around the original geodesic vertex
        normal = geo_vert.to_np()
        u_axis = np.cross(normal, [0, 1, 0])
        if np.linalg.norm(u_axis) < 1e-5: u_axis = np.cross(normal, [1, 0, 0])
        u_axis /= np.linalg.norm(u_axis)
        v_axis = np.cross(normal, u_axis)

        def get_angle(v):
            p_vec = v.to_np()
            return math.atan2(np.dot(p_vec, v_axis), np.dot(p_vec, u_axis))

        new_face_verts_sorted = sorted(new_face_verts_unsorted, key=get_angle)
        goldberg_faces.append(Face(new_face_verts_sorted))

    return Polyhedron(goldberg_verts, goldberg_faces)

# --- Optimized Main Loop ---
# subdivision_level=1 -> Buckyball, 2 -> 260 faces, 3 -> 980 faces
polyhedron = create_goldberg_polyhedron(subdivision_level=2)
angle_x, angle_y = 0, 0
mouse_dragging = False

# --- Pre-computation ---
original_vertices = np.array([v.to_np() for v in polyhedron.vertices])
face_indices = [[polyhedron.vertices.index(v) for v in face.vertices] for face in polyhedron.faces]
face_colors = np.array([HEXAGON_COLOR if len(face.vertices) == 6 else PENTAGON_COLOR for face in polyhedron.faces])

# Pre-calculate face normals (relative to the object)
face_normals = []
for indices in face_indices:
    if len(indices) < 3:
        face_normals.append(np.array([0,0,0]))
        continue
    p1, p2, p3 = original_vertices[indices[0]], original_vertices[indices[1]], original_vertices[indices[2]]
    v1, v2 = p2 - p1, p3 - p1
    normal = np.cross(v1, v2)
    norm = np.linalg.norm(normal)
    if norm == 0:
        face_normals.append(np.array([0,0,0]))
    else:
        face_normals.append(normal / norm)
face_normals = np.array(face_normals)


def main():
    global angle_x, angle_y, mouse_dragging

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            elif event.type == pygame.MOUSEBUTTONDOWN: mouse_dragging = True
            elif event.type == pygame.MOUSEBUTTONUP: mouse_dragging = False
            elif event.type == pygame.MOUSEMOTION:
                if mouse_dragging:
                    rel_x, rel_y = event.rel
                    angle_y -= rel_x * 0.005
                    angle_x += rel_y * 0.005

        screen.fill(BLACK)

        # --- Rotation ---
        cos_x, sin_x = math.cos(angle_x), math.sin(angle_x)
        cos_y, sin_y = math.cos(angle_y), math.sin(angle_y)
        rot_x = np.array([[1,0,0],[0,cos_x,-sin_x],[0,sin_x,cos_x]])
        rot_y = np.array([[cos_y,0,sin_y],[0,1,0],[-sin_y,0,cos_y]])
        rotation_matrix = rot_y @ rot_x

        # --- Vectorized Operations ---
        rotated_vertices = original_vertices @ rotation_matrix
        rotated_normals = face_normals @ rotation_matrix

        # --- Culling ---
        visible_faces_mask = rotated_normals[:, 2] >= 0
        visible_indices = np.where(visible_faces_mask)[0]

        # If no faces are visible, just update the screen and continue
        if len(visible_indices) == 0:
            pygame.display.flip()
            clock.tick(FPS)
            continue

        # --- Lighting for Visible Faces ---
        intensities = np.dot(rotated_normals[visible_indices], -LIGHT_SOURCE)
        np.clip(intensities, 0.2, 1.0, out=intensities)
        final_colors = (face_colors[visible_indices] * intensities[:, np.newaxis]).astype(int)

        # --- Projection and Depth Calculation ---
        polygons_to_draw = []
        projected_points = rotated_vertices[:, :2] * 250 + np.array([WIDTH / 2, HEIGHT / 2])

        for i, face_idx in enumerate(visible_indices):
            indices = face_indices[face_idx]
            depth = np.mean(rotated_vertices[indices, 2])
            projected = projected_points[indices]
            color = final_colors[i]
            polygons_to_draw.append((depth, projected, color))

        # --- Sorting and Drawing ---
        polygons_to_draw.sort(key=lambda x: x[0], reverse=True)

        for _, projected, color in polygons_to_draw:
            pygame.draw.polygon(screen, color, projected)
            pygame.draw.polygon(screen, EDGE_COLOR, projected, 1)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()