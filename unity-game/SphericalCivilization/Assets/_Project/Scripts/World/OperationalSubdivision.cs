using System;
using System.Collections.Generic;
using UnityEngine;

namespace SphericalCivilization.World
{
    public static class OperationalSubdivision
    {
        public const int MinSubtilesPerTile = 12;
        public const int MaxSubtilesPerTile = 128;

        public static int GetEdgeSegments(int count) => Mathf.Clamp(Mathf.RoundToInt(4f * Mathf.Sqrt(count / 37f)), 1, 16);
        private const double Epsilon = 1e-8;
        private const float WeldTolerance = 0.000001f;

        private readonly struct Point
        {
            public readonly double X, Y;
            public Point(double x, double y) { X = x; Y = y; }
            public double LengthSquared => X * X + Y * Y;
            public static Point operator +(Point a, Point b) => new(a.X + b.X, a.Y + b.Y);
            public static Point operator -(Point a, Point b) => new(a.X - b.X, a.Y - b.Y);
            public static Point operator *(Point a, double b) => new(a.X * b, a.Y * b);
            public static double Dot(Point a, Point b) => a.X * b.X + a.Y * b.Y;
            public static double Cross(Point a, Point b) => a.X * b.Y - a.Y * b.X;
        }

        private readonly struct EdgeKey : IEquatable<EdgeKey>, IComparable<EdgeKey>
        {
            public readonly int A, B;
            public EdgeKey(int a, int b) { A = Math.Min(a, b); B = Math.Max(a, b); }
            public bool Equals(EdgeKey other) => A == other.A && B == other.B;
            public override bool Equals(object obj) => obj is EdgeKey other && Equals(other);
            public override int GetHashCode() => unchecked(A * 397 ^ B);
            public int CompareTo(EdgeKey other) { int c = A.CompareTo(other.A); return c != 0 ? c : B.CompareTo(other.B); }
        }

        private sealed class VertexRegistry
        {
            private readonly OperationalWorld _world;
            private readonly Dictionary<(int, int, int), List<int>> _buckets = new();
            public VertexRegistry(OperationalWorld world) => _world = world;
            public int Add(Vector3 position)
            {
                int x = Mathf.FloorToInt(position.x / WeldTolerance), y = Mathf.FloorToInt(position.y / WeldTolerance), z = Mathf.FloorToInt(position.z / WeldTolerance);
                int best = -1;
                for (int dx = -1; dx <= 1; dx++)
                for (int dy = -1; dy <= 1; dy++)
                for (int dz = -1; dz <= 1; dz++)
                    if (_buckets.TryGetValue((x + dx, y + dy, z + dz), out var candidates))
                        foreach (int index in candidates)
                            if ((_world.Vertices[index] - position).sqrMagnitude <= WeldTolerance * WeldTolerance && (best < 0 || index < best)) best = index;
                if (best >= 0) return best;
                int id = _world.Vertices.Count;
                _world.Vertices.Add(position);
                if (!_buckets.TryGetValue((x, y, z), out var bucket)) _buckets[(x, y, z)] = bucket = new List<int>();
                bucket.Add(id);
                return id;
            }
        }

        private sealed class Face
        {
            public OperationalTile Tile;
            public Vector3 Origin, U, V;
            public Point[] Polygon;
            public Point Project(Vector3 p)
            {
                // Retain precision when orienting small polygons on the globe.
                double x = (double)p.x - Origin.x, y = (double)p.y - Origin.y, z = (double)p.z - Origin.z;
                return new Point(x * U.x + y * U.y + z * U.z, x * V.x + y * V.y + z * V.z);
            }
        }

        private struct RandomSequence
        {
            private uint _state;
            public RandomSequence(uint seed) => _state = seed == 0 ? 0x6d2b79f5u : seed;
            public double Next()
            {
                _state ^= _state << 13; _state ^= _state >> 17; _state ^= _state << 5;
                return _state / 4294967296.0;
            }
        }

        public static OperationalWorld Build(ReferenceWorld source, SubdivisionOptions options = null)
            => BuildInternal(source, options, null);

        // Render-only subset: keeps the full world's canonical parent borders,
        // generates only these interiors, and does not build an adjacency graph.
        public static OperationalWorld BuildPreview(ReferenceWorld source, IReadOnlyList<int> tileIds, SubdivisionOptions options = null)
        {
            if (tileIds == null || tileIds.Count == 0) throw new ArgumentException("Preview needs sample tiles.");
            return BuildInternal(source, options, new HashSet<int>(tileIds));
        }

        private static OperationalWorld BuildInternal(ReferenceWorld source, SubdivisionOptions options, HashSet<int> previewIds)
        {
            if (source?.schemaVersion != 1 || source.tiles == null) throw new ArgumentException("Unsupported reference world.");
            options ??= new SubdivisionOptions();
            if (options.EdgeSegments < 0 || options.EdgeSegments > 16 || options.SubtilesPerTile < MinSubtilesPerTile || options.SubtilesPerTile > MaxSubtilesPerTile ||
                options.CountForSides(5) < MinSubtilesPerTile || options.CountForSides(5) > MaxSubtilesPerTile)
                throw new ArgumentOutOfRangeException(nameof(options));
            var world = new OperationalWorld();
            var registry = new VertexRegistry(world);
            var references = new List<ReferenceTile>(source.tiles);
            references.Sort((a, b) => a.id.CompareTo(b.id));
            var faces = new List<Face>();
            var parentEdges = new Dictionary<EdgeKey, List<int>>();
            foreach (var reference in references)
            {
                if (reference.id < 0 || reference.vertices == null || reference.vertices.Length < 3 || world.TilesById.ContainsKey(reference.id))
                    throw new ArgumentException("Invalid or duplicate parent tile.");
                var tile = new OperationalTile { Id = reference.id, Normal = reference.center.normalized,
                    Color = reference.color.Linear, Terrain = reference.terrain, Corners = new int[reference.vertices.Length] };
                for (int i = 0; i < tile.Corners.Length; i++) tile.Corners[i] = registry.Add(reference.vertices[i]);
                var face = new Face { Tile = tile, Origin = reference.center };
                face.U = Vector3.ProjectOnPlane(world.Vertices[tile.Corners[0]] - face.Origin, tile.Normal).normalized;
                face.V = Vector3.Cross(tile.Normal, face.U).normalized;
                face.Polygon = ProjectCorners(face, world);
                if (SignedArea(face.Polygon) < 0)
                {
                    Array.Reverse(tile.Corners);
                    face.Polygon = ProjectCorners(face, world);
                }
                if (SignedArea(face.Polygon) <= Epsilon) throw new ArgumentException("Degenerate parent tile.");
                tile.BoundaryIds = new int[tile.Corners.Length];
                world.Tiles.Add(tile); world.TilesById.Add(tile.Id, tile); faces.Add(face);
                for (int i = 0; i < tile.Corners.Length; i++)
                {
                    var key = new EdgeKey(tile.Corners[i], tile.Corners[(i + 1) % tile.Corners.Length]);
                    if (!parentEdges.TryGetValue(key, out var owners)) parentEdges[key] = owners = new List<int>();
                    owners.Add(tile.Id);
                }
            }

            var parentKeys = new List<EdgeKey>(parentEdges.Keys); parentKeys.Sort();
            var boundaryIds = new Dictionary<EdgeKey, int>();
            foreach (var key in parentKeys)
            {
                var owners = parentEdges[key];
                if (owners.Count != 2) throw new ArgumentException("The parent globe must be closed: every edge needs two owners.");
                int segments = options.EdgeSegments != 0 ? options.EdgeSegments : Math.Min(
                    GetEdgeSegments(options.CountForSides(world.TilesById[owners[0]].Corners.Length)),
                    GetEdgeSegments(options.CountForSides(world.TilesById[owners[1]].Corners.Length)));
                var boundary = new RegionBoundary { Id = world.Boundaries.Count, Start = key.A, End = key.B,
                    FirstTileId = owners[0], SecondTileId = owners[1], Vertices = new int[segments + 2] };
                boundary.Vertices[0] = key.A; boundary.Vertices[boundary.Vertices.Length - 1] = key.B;
                for (int step = 0; step < segments; step++)
                    boundary.Vertices[step + 1] = registry.Add(Vector3.Lerp(world.Vertices[key.A], world.Vertices[key.B], (step + 0.5f) / segments));
                world.Boundaries.Add(boundary); boundaryIds.Add(key, boundary.Id);
            }
            foreach (var face in faces)
            {
                for (int i = 0; i < face.Tile.Corners.Length; i++)
                    face.Tile.BoundaryIds[i] = boundaryIds[new EdgeKey(face.Tile.Corners[i], face.Tile.Corners[(i + 1) % face.Tile.Corners.Length])];
                if (previewIds == null || previewIds.Contains(face.Tile.Id))
                    GenerateFace(face, world, registry, options, options.CountForSides(face.Tile.Corners.Length));
            }
            if (previewIds == null) Connect(world);
            else foreach (int id in previewIds)
                if (!world.TilesById.ContainsKey(id)) throw new ArgumentException($"Unknown preview tile {id}.");
            return world;
        }

        private static Point[] ProjectCorners(Face face, OperationalWorld world)
        {
            var points = new Point[face.Tile.Corners.Length];
            for (int i = 0; i < points.Length; i++) points[i] = face.Project(world.Vertices[face.Tile.Corners[i]]);
            return points;
        }

        private static double SignedArea(IReadOnlyList<Point> points)
        {
            double area = 0;
            for (int i = 0; i < points.Count; i++) area += Point.Cross(points[i], points[(i + 1) % points.Count]);
            return area * 0.5;
        }

        private static void GenerateFace(Face face, OperationalWorld world, VertexRegistry registry, SubdivisionOptions options, int targetCount)
        {
            var seeds = new List<Point>();
            double averageEdge = 0, guard = 0, minX = double.MaxValue, minY = double.MaxValue, maxX = double.MinValue, maxY = double.MinValue;
            for (int i = 0; i < face.Polygon.Length; i++)
            {
                var a = face.Polygon[i]; var b = face.Polygon[(i + 1) % face.Polygon.Length];
                int segments = world.Boundaries[face.Tile.BoundaryIds[i]].Vertices.Length - 2;
                double length = Math.Sqrt((b - a).LengthSquared); averageEdge += length; guard = Math.Max(guard, length / segments * 0.55);
                minX = Math.Min(minX, a.X); maxX = Math.Max(maxX, a.X); minY = Math.Min(minY, a.Y); maxY = Math.Max(maxY, a.Y);
                for (int step = 0; step < segments; step++) seeds.Add(a + (b - a) * ((double)step / segments));
            }
            if (seeds.Count > targetCount)
                throw new ArgumentException("Requested cell count is smaller than the shared boundary site count.");
            averageEdge /= face.Polygon.Length;
            double spacing = averageEdge * 0.28 * Math.Sqrt(37.0 / targetCount);
            var random = new RandomSequence(unchecked(options.Seed ^ ((uint)face.Tile.Id * 0x9e3779b9u) ^ 0x85ebca6bu));
            Point Candidate() => new(minX + random.Next() * (maxX - minX), minY + random.Next() * (maxY - minY));
            bool InsideGuard(Point candidate)
            {
                for (int edge = 0; edge < face.Polygon.Length; edge++)
                {
                    var a = face.Polygon[edge]; var delta = face.Polygon[(edge + 1) % face.Polygon.Length] - a;
                    if (Point.Cross(delta, candidate - a) / Math.Sqrt(delta.LengthSquared) < guard) return false;
                }
                return true;
            }
            double NearestDistanceSquared(Point candidate)
            {
                double nearest = double.MaxValue;
                foreach (var other in seeds) nearest = Math.Min(nearest, (candidate - other).LengthSquared);
                return nearest;
            }
            // Keep the original Poisson-style sampling and irregular Voronoi
            // appearance. Stop at the requested count instead of a random total.
            for (int attempt = 0; attempt < 2048 && seeds.Count < targetCount; attempt++)
            {
                var candidate = attempt == 0 ? new Point(0, 0) : Candidate();
                if (InsideGuard(candidate) && NearestDistanceSquared(candidate) >= spacing * spacing) seeds.Add(candidate);
            }
            // If spacing saturation occurs, add the best-separated remaining
            // candidates. The guard stays fixed so shared edge cuts cannot move.
            var candidates = new List<Point>(); var distances = new List<double>();
            if (seeds.Count < targetCount)
            {
                for (int attempt = 0; attempt < 2048; attempt++)
                {
                    var candidate = Candidate();
                    if (!InsideGuard(candidate)) continue;
                    candidates.Add(candidate); distances.Add(NearestDistanceSquared(candidate));
                }
            }
            while (seeds.Count < targetCount)
            {
                int bestIndex = -1; double bestDistance = -1;
                for (int i = 0; i < candidates.Count; i++)
                    if (distances[i] > bestDistance) { bestIndex = i; bestDistance = distances[i]; }
                if (bestDistance <= WeldTolerance * WeldTolerance * 16)
                    throw new InvalidOperationException($"Cannot fit the requested subtile count in parent {face.Tile.Id}.");
                var best = candidates[bestIndex];
                seeds.Add(best);
                // Update against only the new seed, rather than rescanning all
                // seeds for every candidate on each insertion at high density.
                for (int i = 0; i < candidates.Count; i++)
                    distances[i] = Math.Min(distances[i], (candidates[i] - best).LengthSquared);
            }

            var indices = new List<int>(seeds.Count);
            for (int site = 0; site < seeds.Count; site++)
            {
                var polygon = new List<Point>(face.Polygon); var scratch = new List<Point>(16);
                for (int other = 0; other < seeds.Count && polygon.Count >= 3; other++)
                {
                    if (other == site) continue;
                    Clip(polygon, scratch, seeds[other] - seeds[site], (seeds[other].LengthSquared - seeds[site].LengthSquared) * 0.5);
                    (polygon, scratch) = (scratch, polygon);
                }
                if (polygon.Count < 3 || SignedArea(polygon) <= 1e-14) throw new InvalidOperationException("An operational cell collapsed.");
                var vertices = new List<int>();
                foreach (var point in polygon)
                {
                    int vertex = ResolveVertex(face, point, world, registry);
                    if (vertices.Count == 0 || vertices[vertices.Count - 1] != vertex) vertices.Add(vertex);
                }
                if (vertices.Count > 1 && vertices[0] == vertices[vertices.Count - 1]) vertices.RemoveAt(vertices.Count - 1);
                if (vertices.Count < 3) throw new InvalidOperationException("An operational cell collapsed during vertex welding.");
                Vector3 center = Vector3.zero;
                foreach (int vertex in vertices) center += world.Vertices[vertex];
                var cell = new OperationalSubtile { Id = ((long)face.Tile.Id << 32) | (uint)site, ParentTileId = face.Tile.Id,
                    Vertices = vertices.ToArray(), Center = center / vertices.Count };
                int index = world.Subtiles.Count;
                world.SubtileIndicesById.Add(cell.Id, index); world.Subtiles.Add(cell); indices.Add(index);
            }
            face.Tile.SubtileIndices = indices.ToArray();
        }

        private static void Clip(List<Point> input, List<Point> output, Point normal, double limit)
        {
            output.Clear();
            var previous = input[input.Count - 1]; double previousDistance = Point.Dot(normal, previous) - limit;
            foreach (var current in input)
            {
                double distance = Point.Dot(normal, current) - limit;
                bool inside = distance <= 1e-14, previousInside = previousDistance <= 1e-14;
                if (inside != previousInside) output.Add(previous + (current - previous) * (previousDistance / (previousDistance - distance)));
                if (inside) output.Add(current);
                previous = current; previousDistance = distance;
            }
        }

        private static int ResolveVertex(Face face, Point point, OperationalWorld world, VertexRegistry registry)
        {
            for (int edge = 0; edge < face.Polygon.Length; edge++)
            {
                var a = face.Polygon[edge]; var delta = face.Polygon[(edge + 1) % face.Polygon.Length] - a;
                double t = Point.Dot(point - a, delta) / delta.LengthSquared;
                if (t < -Epsilon || t > 1 + Epsilon || Math.Abs(Point.Cross(delta, point - a)) / Math.Sqrt(delta.LengthSquared) > Epsilon) continue;
                var boundary = world.Boundaries[face.Tile.BoundaryIds[edge]];
                int segments = boundary.Vertices.Length - 2;
                if (face.Tile.Corners[edge] != boundary.Start) t = 1 - t;
                int cut = 0; double best = Math.Abs(t);
                for (int step = 0; step < segments; step++)
                {
                    double error = Math.Abs(t - (step + 0.5) / segments);
                    if (error < best) { best = error; cut = step + 1; }
                }
                if (Math.Abs(t - 1) < best) { best = Math.Abs(t - 1); cut = segments + 1; }
                if (best * Math.Sqrt(delta.LengthSquared) > WeldTolerance * 2)
                    throw new InvalidOperationException("An interior Voronoi site changed a canonical parent boundary.");
                return boundary.Vertices[cut];
            }
            var origin = face.Polygon[0];
            for (int i = 1; i < face.Polygon.Length - 1; i++)
            {
                var b = face.Polygon[i] - origin; var c = face.Polygon[i + 1] - origin; var p = point - origin;
                double determinant = Point.Cross(b, c);
                double u = Point.Cross(p, c) / determinant, v = Point.Cross(b, p) / determinant;
                if (u < -Epsilon || v < -Epsilon || u + v > 1 + Epsilon) continue;
                return registry.Add(world.Vertices[face.Tile.Corners[0]] * (float)(1 - u - v) +
                    world.Vertices[face.Tile.Corners[i]] * (float)u + world.Vertices[face.Tile.Corners[i + 1]] * (float)v);
            }
            throw new InvalidOperationException("An operational vertex escaped its parent polygon.");
        }

        private static void Connect(OperationalWorld world)
        {
            var boundarySegments = new Dictionary<EdgeKey, int>();
            foreach (var boundary in world.Boundaries)
            {
                boundary.Subedges = new int[boundary.Vertices.Length - 1];
                for (int i = 0; i < boundary.Vertices.Length - 1; i++) boundarySegments.Add(new EdgeKey(boundary.Vertices[i], boundary.Vertices[i + 1]), boundary.Id);
            }
            var owners = new Dictionary<EdgeKey, List<(int cell, int side)>>();
            for (int index = 0; index < world.Subtiles.Count; index++)
            {
                var cell = world.Subtiles[index]; cell.Edges = new int[cell.Vertices.Length]; cell.Neighbors = new int[cell.Vertices.Length];
                for (int side = 0; side < cell.Vertices.Length; side++)
                {
                    var key = new EdgeKey(cell.Vertices[side], cell.Vertices[(side + 1) % cell.Vertices.Length]);
                    if (key.A == key.B) throw new InvalidOperationException("Zero-length operational edge.");
                    if (!owners.TryGetValue(key, out var list)) owners[key] = list = new List<(int, int)>();
                    list.Add((index, side));
                }
            }
            var keys = new List<EdgeKey>(owners.Keys); keys.Sort();
            var edgeIds = new Dictionary<EdgeKey, int>();
            foreach (var key in keys)
            {
                var list = owners[key];
                if (list.Count != 2) throw new InvalidOperationException($"Operational edge {key.A}-{key.B} has {list.Count} owners; possible crack or T-junction.");
                var first = list[0]; var second = list[1];
                int parentBoundary = boundarySegments.TryGetValue(key, out int boundaryId) ? boundaryId : -1;
                bool crosses = world.Subtiles[first.cell].ParentTileId != world.Subtiles[second.cell].ParentTileId;
                if (crosses != (parentBoundary >= 0)) throw new InvalidOperationException("Invalid inter-region operational adjacency.");
                int id = world.Edges.Count;
                world.Edges.Add(new OperationalEdge { Id = id, Start = key.A, End = key.B,
                    FirstSubtile = first.cell, SecondSubtile = second.cell, ParentBoundaryId = parentBoundary });
                edgeIds.Add(key, id);
                world.Subtiles[first.cell].Edges[first.side] = id; world.Subtiles[second.cell].Edges[second.side] = id;
                world.Subtiles[first.cell].Neighbors[first.side] = second.cell; world.Subtiles[second.cell].Neighbors[second.side] = first.cell;
            }
            foreach (var boundary in world.Boundaries)
                for (int i = 0; i < boundary.Subedges.Length; i++)
                    boundary.Subedges[i] = edgeIds[new EdgeKey(boundary.Vertices[i], boundary.Vertices[i + 1])];
        }
    }
}
