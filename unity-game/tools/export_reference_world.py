"""Export an existing prototype cache without running or changing GameWorld.

Only use this with a cache produced by this local project: pickle is not an
interchange format for files obtained from third parties.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import pickle
import sys


def export_world(cache_path: Path, output_path: Path) -> dict:
    prototype_path = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(prototype_path))

    with cache_path.open("rb") as cache_file:
        world = pickle.load(cache_file)

    tiles = world["tiles"]
    by_id = {tile.id: tile for tile in tiles}
    if len(by_id) != len(tiles):
        raise ValueError("Tile IDs are not unique.")

    vertex_count_histogram = Counter(len(tile.vertices) for tile in tiles)
    if vertex_count_histogram[5] != 12:
        raise ValueError("The reference sphere must have twelve pentagons.")
    if set(vertex_count_histogram) - {5, 6}:
        raise ValueError("Unexpected strategic cell polygon.")

    # Tile.__getstate__ deliberately omits neighbors. Reconstruct adjacency from
    # shared polygon edges without instantiating GameWorld or writing its caches.
    edge_owners = {}
    vertex_keys = set()
    neighbors = {tile.id: set() for tile in tiles}
    for tile in tiles:
        points = [tuple(float(value) for value in vertex.to_np()) for vertex in tile.vertices]
        vertex_keys.update(points)
        for start, end in zip(points, points[1:] + points[:1]):
            edge = tuple(sorted((start, end)))
            edge_owners.setdefault(edge, []).append(tile.id)
    for edge, owners in edge_owners.items():
        if len(owners) != 2:
            raise ValueError(f"A sphere edge must have exactly two owners: {edge}.")
        left, right = owners
        neighbors[left].add(right)
        neighbors[right].add(left)

    if len(vertex_keys) - len(edge_owners) + len(tiles) != 2:
        raise ValueError("The sphere does not satisfy Euler's formula.")
    for tile in tiles:
        if len(neighbors[tile.id]) != len(tile.vertices):
            raise ValueError(f"Unexpected neighbor count at tile {tile.id}.")

    visited = set()
    pending = [tiles[0].id]
    while pending:
        tile_id = pending.pop()
        if tile_id in visited:
            continue
        visited.add(tile_id)
        pending.extend(neighbors[tile_id])
    if len(visited) != len(tiles):
        raise ValueError("The reference sphere's neighbor graph is disconnected.")

    def vector(values):
        return {axis: float(value) for axis, value in zip("xyz", values)}

    data = {
        "schemaVersion": 1,
        "sourceCache": cache_path.name,
        "tiles": [
            {
                "id": int(tile.id),
                "center": vector(tile.center),
                "normal": vector(tile.normal),
                "vertices": [vector(vertex.to_np()) for vertex in tile.vertices],
                "color": {
                    channel: float(value) / 255.0
                    for channel, value in zip("rgb", tile.color)
                },
                "terrain": tile.terrain_type.name if tile.terrain_type else "UNKNOWN",
                "neighbors": sorted(neighbors[tile.id]),
            }
            for tile in sorted(tiles, key=lambda item: item.id)
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    return {
        "output": str(output_path),
        "tiles": len(tiles),
        "pentagons": vertex_count_histogram[5],
        "hexagons": vertex_count_histogram[6],
        "connected": True,
        "reciprocalNeighbors": True,
        "sharedEdges": len(edge_owners),
        "eulerCharacteristic": 2,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    print(json.dumps(export_world(options.cache.resolve(), options.output.resolve()), indent=2))
