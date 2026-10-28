using System;
using System.Collections.Generic;
using UnityEngine;
using SphericalCivilization.World;

namespace SphericalCivilization.Battle
{
    public readonly struct HexCoord : IEquatable<HexCoord>
    {
        public readonly int Q, R;
        public HexCoord(int q, int r) { Q = q; R = r; }
        public bool Equals(HexCoord other) => Q == other.Q && R == other.R;
        public override bool Equals(object obj) => obj is HexCoord other && Equals(other);
        public override int GetHashCode() => unchecked(Q * 397 ^ R);
        public static HexCoord operator +(HexCoord a, HexCoord b) => new(a.Q + b.Q, a.R + b.R);
        public static readonly HexCoord[] Directions = { new(1, 0), new(0, 1), new(-1, 1), new(-1, 0), new(0, -1), new(1, -1) };
        public Vector2 Center => new(Mathf.Sqrt(3) * (Q + R * 0.5f), R * 1.5f);
        private static readonly Vector2Int[] CornerOffsets = { new(1, 1), new(0, 2), new(-1, 1), new(-1, -1), new(0, -2), new(1, -1) };
        public Vector2Int CornerKey(int corner)
        {
            return new Vector2Int(2 * Q + R, 3 * R) + CornerOffsets[corner];
        }
        public static Vector2 CornerPosition(Vector2Int key) => new(key.x * Mathf.Sqrt(3) * 0.5f, key.y * 0.5f);
        public static HexCoord At(Vector2 p)
        {
            float r = p.y / 1.5f, q = p.x / Mathf.Sqrt(3) - r * 0.5f, s = -q - r;
            int iq = Mathf.RoundToInt(q), ir = Mathf.RoundToInt(r), iss = Mathf.RoundToInt(s);
            float dq = Mathf.Abs(iq - q), dr = Mathf.Abs(ir - r), ds = Mathf.Abs(iss - s);
            if (dq > dr && dq > ds) iq = -ir - iss; else if (dr > ds) ir = -iq - iss;
            return new HexCoord(iq, ir);
        }
    }

    public sealed class BattleHex
    {
        public HexCoord Coord;
        public int RetreatRow;
        public int SourceSubtileIndex;
        public float Coverage;
        public int[] Neighbors;
        public bool IsEscape => RetreatRow == Battlefield.RetreatRows;
    }

    public sealed class BattleUnit
    {
        public int HexIndex;
        public int Side;
        public bool Escaped;
    }

    public sealed class BattleRegion
    {
        public int SubtileIndex;
        public Vector2[] Polygon;
        public Color Color;
    }

    public sealed class Battlefield
    {
        public const int RetreatRows = 3;
        public readonly List<BattleHex> Hexes = new();
        public readonly Dictionary<HexCoord, int> Indices = new();
        public readonly List<BattleRegion> Regions = new();
        public readonly List<BattleUnit> Units = new();
        public readonly Dictionary<Vector2Int, float> CornerOpacity = new();
        public int FirstSubtileIndex, SecondSubtileIndex, SharedEdgeId;
        public Vector3 Origin, AxisX, AxisY, Normal;
        public float WorldHexRadius;
        public float ScreenAngle;
        public Bounds Bounds;
        public int CoreHexCount;
        public Vector2[] PlayableBoundary;
        public Vector2 Project(Vector3 position)
        { var d = position - Origin; return new Vector2(Vector3.Dot(d, AxisX), Vector3.Dot(d, AxisY)) / WorldHexRadius; }

        public static int ChooseNeighbor(OperationalWorld world, int index)
        {
            if (world == null || index < 0 || index >= world.Subtiles.Count) return -1;
            float best = -1; int chosen = -1;
            var cell = world.Subtiles[index];
            for (int i = 0; i < cell.Edges.Length; i++)
            {
                var edge = world.Edges[cell.Edges[i]];
                float length = (world.Vertices[edge.Start] - world.Vertices[edge.End]).sqrMagnitude;
                if (length > best) { best = length; chosen = cell.Neighbors[i]; }
            }
            return chosen;
        }

        public static Battlefield Build(OperationalWorld world, int first, int second, float sharedEdgeScreenAngle, int targetCoreHexes = 900, float hexWorldRadius = 0)
        {
            if (world == null || first < 0 || second < 0 || first >= world.Subtiles.Count || second >= world.Subtiles.Count || first == second)
                throw new ArgumentException("Battle needs two distinct neighboring subtiles.");
            var a = world.Subtiles[first]; var b = world.Subtiles[second];
            int side = Array.IndexOf(a.Neighbors, second);
            if (side < 0) throw new ArgumentException("Battle subtiles must share an edge.");
            var field = new Battlefield { FirstSubtileIndex = first, SecondSubtileIndex = second, SharedEdgeId = a.Edges[side], Origin = (a.Center + b.Center) * 0.5f };
            field.Normal = (world.TilesById[a.ParentTileId].Normal + world.TilesById[b.ParentTileId].Normal).normalized;
            var shared = world.Edges[field.SharedEdgeId];
            var u = Vector3.ProjectOnPlane(world.Vertices[shared.End] - world.Vertices[shared.Start], field.Normal);
            // Some valid welded subtile edges are shorter than Unity's default
            // Vector3.Normalize threshold. Do not erase their direction.
            float edgeLength = u.magnitude;
            if (edgeLength < 1e-10f) throw new InvalidOperationException("Collapsed shared battle edge.");
            u /= edgeLength;
            var v = Vector3.Cross(field.Normal, u).normalized;
            // The lattice belongs to geography. Camera roll rotates only the
            // view, never the tactical cell IDs or their contents.
            field.AxisX = u; field.AxisY = v; field.ScreenAngle = sharedEdgeScreenAngle;
            field.WorldHexRadius = 1f;
            Vector2[] Polygon(int index)
            {
                var vertices = world.Subtiles[index].Vertices;
                var result = new Vector2[vertices.Length];
                for (int i = 0; i < result.Length; i++) result[i] = field.Project(world.Vertices[vertices[i]]);
                if (SignedArea(result) < 0) Array.Reverse(result);
                return result;
            }
            double area = SignedArea(Polygon(first)) + SignedArea(Polygon(second));
            if (area <= 1e-12) throw new InvalidOperationException("Degenerate battle area.");
            if (float.IsNaN(hexWorldRadius) || float.IsInfinity(hexWorldRadius) || hexWorldRadius < 0)
                throw new ArgumentOutOfRangeException(nameof(hexWorldRadius));
            field.WorldHexRadius = hexWorldRadius > 0 ? hexWorldRadius : (float)Math.Sqrt(area / (Mathf.Clamp(targetCoreHexes, 100, 5000) * 2.598076211353316));

            var coreA = Polygon(first); var coreB = Polygon(second);
            var points = new List<Vector2>(coreA); points.AddRange(coreB);
            field.PlayableBoundary = ConvexHull(points);
            if (SignedArea(field.PlayableBoundary) / 2.598076211353316 > 18000)
                throw new InvalidOperationException("Слишком мелкие гексы для этой пары. Увеличь размер гекса.");
            Vector2 min = field.PlayableBoundary[0], max = min;
            foreach (var p in field.PlayableBoundary) { min = Vector2.Min(min, p); max = Vector2.Max(max, p); }

            // Gather geography over the whole hull and retreat band. A hull can
            // bridge cells farther than three operational-neighbor hops away.
            float padding = (RetreatRows + 1) * Mathf.Sqrt(3) + 2;
            var contextMin = min - Vector2.one * padding; var contextMax = max + Vector2.one * padding;
            var visitedRegions = new HashSet<int> { first, second };
            var regionQueue = new Queue<int>(); regionQueue.Enqueue(first); regionQueue.Enqueue(second);
            while (regionQueue.Count > 0)
            {
                int index = regionQueue.Dequeue();
                var polygon = index == first ? coreA : index == second ? coreB : Polygon(index);
                Vector2 regionMin = polygon[0], regionMax = regionMin;
                foreach (var p in polygon) { regionMin = Vector2.Min(regionMin, p); regionMax = Vector2.Max(regionMax, p); }
                if (regionMax.x < contextMin.x || regionMin.x > contextMax.x || regionMax.y < contextMin.y || regionMin.y > contextMax.y) continue;
                field.Regions.Add(new BattleRegion { SubtileIndex = index, Polygon = polygon, Color = world.TilesById[world.Subtiles[index].ParentTileId].Color });
                foreach (int next in world.Subtiles[index].Neighbors)
                    if (visitedRegions.Add(next)) regionQueue.Enqueue(next);
            }
            int Owner(Vector2 point)
            { foreach (var region in field.Regions) if (Contains(region.Polygon, point)) return region.SubtileIndex; return -1; }
            int minR = Mathf.FloorToInt((min.y - 1) / 1.5f) - 1, maxR = Mathf.CeilToInt((max.y + 1) / 1.5f) + 1;
            var queue = new Queue<int>();
            for (int r = minR; r <= maxR; r++)
            {
                int minQ = Mathf.FloorToInt((min.x - 1) / Mathf.Sqrt(3) - r * 0.5f) - 1;
                int maxQ = Mathf.CeilToInt((max.x + 1) / Mathf.Sqrt(3) - r * 0.5f) + 1;
                for (int q = minQ; q <= maxQ; q++)
                {
                    var coord = new HexCoord(q, r); var hex = PolygonOf(coord);
                    double playableArea = Math.Abs(SignedArea(Clip(hex, field.PlayableBoundary)));
                    if (playableArea <= 0.000001) continue;
                    double areaA = Math.Abs(SignedArea(Clip(hex, coreA))), areaB = Math.Abs(SignedArea(Clip(hex, coreB)));
                    int owner = areaA + areaB > 0.000001 ? areaA >= areaB ? first : second : Owner(coord.Center);
                    int index = field.Add(coord, 0, owner, Mathf.Clamp01((float)(playableArea / 2.598076211353316)));
                    queue.Enqueue(index);
                }
            }
            field.CoreHexCount = field.Hexes.Count;
            if (field.CoreHexCount == 0 || field.CoreHexCount > 20000) throw new InvalidOperationException("Invalid battle hex count.");
            while (queue.Count > 0)
            {
                var hex = field.Hexes[queue.Dequeue()];
                if (hex.RetreatRow == RetreatRows) continue;
                foreach (var direction in HexCoord.Directions)
                {
                    var next = hex.Coord + direction;
                    if (field.Indices.ContainsKey(next)) continue;
                    queue.Enqueue(field.Add(next, hex.RetreatRow + 1, Owner(next.Center), 1f));
                }
            }
            var cornerSums = new Dictionary<Vector2Int, (float sum, int count)>();
            Vector2 boundsMin = new(float.MaxValue, float.MaxValue), boundsMax = new(float.MinValue, float.MinValue);
            foreach (var hex in field.Hexes)
            {
                hex.Neighbors = new int[6];
                for (int i = 0; i < 6; i++)
                {
                    hex.Neighbors[i] = field.Indices.TryGetValue(hex.Coord + HexCoord.Directions[i], out int neighbor) ? neighbor : -1;
                    var key = hex.Coord.CornerKey(i); cornerSums.TryGetValue(key, out var sum);
                    cornerSums[key] = (sum.sum + Opacity(hex.RetreatRow), sum.count + 1);
                    var p = HexCoord.CornerPosition(key); boundsMin = Vector2.Min(boundsMin, p); boundsMax = Vector2.Max(boundsMax, p);
                }
            }
            foreach (var item in cornerSums) field.CornerOpacity[item.Key] = item.Value.count < 3 ? 0 : item.Value.sum / 3f;
            field.Bounds = new Bounds((Vector3)((boundsMin + boundsMax) * 0.5f), new Vector3(boundsMax.x - boundsMin.x, boundsMax.y - boundsMin.y, 1));
            for (int team = 0; team < 2; team++)
            {
                int source = team == 0 ? first : second, best = -1; float bestScore = float.MaxValue;
                var center = field.Project(world.Subtiles[source].Center);
                var sourcePolygon = team == 0 ? coreA : coreB;
                for (int i = 0; i < field.CoreHexCount; i++)
                {
                    var hex = field.Hexes[i];
                    if (hex.SourceSubtileIndex != source || hex.Coverage < .98f || !Contains(sourcePolygon, hex.Coord.Center)) continue;
                    float score = (hex.Coord.Center - center).sqrMagnitude;
                    if (score < bestScore) { best = i; bestScore = score; }
                }
                // At very coarse settings a narrow source polygon may not
                // contain a hex center. Still place the token on its nearest
                // available core cell rather than preventing battle entry.
                if (best < 0)
                    for (int i = 0; i < field.CoreHexCount; i++)
                    {
                        if (field.UnitAt(i) >= 0) continue;
                        var hex = field.Hexes[i];
                        float score = (hex.Coord.Center - center).sqrMagnitude + (hex.SourceSubtileIndex == source ? 0 : 1000000);
                        if (score < bestScore) { best = i; bestScore = score; }
                    }
                if (best < 0) throw new InvalidOperationException("Cannot place test units on the battle area.");
                field.Units.Add(new BattleUnit { HexIndex = best, Side = team });
            }
            return field;
        }

        private int Add(HexCoord coord, int row, int source, float coverage)
        { int id = Hexes.Count; Indices.Add(coord, id); Hexes.Add(new BattleHex { Coord = coord, RetreatRow = row, SourceSubtileIndex = source, Coverage = coverage }); return id; }

        public static float Opacity(int row) => row == 0 ? 1f : row == 1 ? .58f : row == 2 ? .25f : .06f;
        public bool TryGetHex(Vector2 point, out int index) => Indices.TryGetValue(HexCoord.At(point), out index);
        public bool IsEscapeCell(HexCoord coord) => Indices.TryGetValue(coord, out int id) && Hexes[id].IsEscape;
        public int UnitAt(int hexIndex)
        { for (int i = 0; i < Units.Count; i++) if (!Units[i].Escaped && Units[i].HexIndex == hexIndex) return i; return -1; }

        public bool TryMoveUnit(int unitIndex, int destination)
        {
            if (unitIndex < 0 || unitIndex >= Units.Count || destination < 0 || destination >= Hexes.Count) return false;
            var unit = Units[unitIndex];
            if (unit.Escaped || UnitAt(destination) >= 0 || Array.IndexOf(Hexes[unit.HexIndex].Neighbors, destination) < 0) return false;
            unit.HexIndex = destination;
            if (Hexes[destination].IsEscape) unit.Escaped = true;
            return true;
        }

        public List<int> FindPath(int unitIndex, int destination)
        {
            var result = new List<int>();
            if (unitIndex < 0 || unitIndex >= Units.Count || Units[unitIndex].Escaped || destination < 0 || destination >= Hexes.Count) return result;
            int start = Units[unitIndex].HexIndex;
            var previous = new int[Hexes.Count]; Array.Fill(previous, -1); previous[start] = start;
            var queue = new Queue<int>(); queue.Enqueue(start);
            while (queue.Count > 0)
            {
                int current = queue.Dequeue(); if (current == destination) break;
                if (current != start && Hexes[current].IsEscape) continue;
                foreach (int next in Hexes[current].Neighbors)
                    if (next >= 0 && previous[next] < 0 && UnitAt(next) < 0) { previous[next] = current; queue.Enqueue(next); }
            }
            if (previous[destination] < 0) return result;
            for (int current = destination; current != start; current = previous[current]) result.Add(current);
            result.Reverse(); return result;
        }

        public float OpacityAt(Vector2 p)
        {
            if (!TryGetHex(p, out int index)) return 0;
            var hex = Hexes[index]; var center = hex.Coord.Center;
            for (int i = 0; i < 6; i++)
            {
                var keyA = hex.Coord.CornerKey(i); var keyB = hex.Coord.CornerKey((i + 1) % 6);
                var a = HexCoord.CornerPosition(keyA) - center; var b = HexCoord.CornerPosition(keyB) - center; var d = p - center;
                float determinant = Cross(a, b), u = Cross(d, b) / determinant, v = Cross(a, d) / determinant;
                if (u >= -.0001f && v >= -.0001f && u + v <= 1.0001f)
                    return Mathf.Clamp01(Opacity(hex.RetreatRow) * (1 - u - v) + CornerOpacity[keyA] * u + CornerOpacity[keyB] * v);
            }
            return 0;
        }

        public static Vector2[] PolygonOf(HexCoord coord)
        { var points = new Vector2[6]; for (int i = 0; i < 6; i++) points[i] = HexCoord.CornerPosition(coord.CornerKey(i)); return points; }
        public static float Cross(Vector2 a, Vector2 b) => a.x * b.y - a.y * b.x;
        public static Vector2[] ConvexHull(IReadOnlyList<Vector2> points)
        {
            var sorted = new List<Vector2>(points);
            sorted.Sort((a, b) => a.x == b.x ? a.y.CompareTo(b.y) : a.x.CompareTo(b.x));
            for (int i = sorted.Count - 1; i > 0; i--) if (sorted[i].Equals(sorted[i - 1])) sorted.RemoveAt(i);
            if (sorted.Count < 3) throw new ArgumentException("A battle hull needs at least three distinct points.");
            var hull = new List<Vector2>();
            foreach (var point in sorted)
            {
                while (hull.Count >= 2 && Turn(hull[hull.Count - 2], hull[hull.Count - 1], point) <= 0) hull.RemoveAt(hull.Count - 1);
                hull.Add(point);
            }
            int lowerCount = hull.Count;
            for (int i = sorted.Count - 2; i >= 0; i--)
            {
                while (hull.Count > lowerCount && Turn(hull[hull.Count - 2], hull[hull.Count - 1], sorted[i]) <= 0) hull.RemoveAt(hull.Count - 1);
                hull.Add(sorted[i]);
            }
            hull.RemoveAt(hull.Count - 1);
            if (hull.Count < 3) throw new ArgumentException("A battle hull must have positive area.");
            return hull.ToArray();
            static double Turn(Vector2 a, Vector2 b, Vector2 c) =>
                ((double)b.x - a.x) * ((double)c.y - a.y) - ((double)b.y - a.y) * ((double)c.x - a.x);
        }
        public static double SignedArea(IReadOnlyList<Vector2> polygon)
        { double area = 0; for (int i = 0; i < polygon.Count; i++) { var a = polygon[i]; var b = polygon[(i + 1) % polygon.Count]; area += (double)a.x * b.y - (double)a.y * b.x; } return area * .5; }
        public static bool Contains(IReadOnlyList<Vector2> polygon, Vector2 point)
        { for (int i = 0; i < polygon.Count; i++) if (Cross(polygon[(i + 1) % polygon.Count] - polygon[i], point - polygon[i]) < -.00001f) return false; return true; }
        private static List<Vector2> Clip(IReadOnlyList<Vector2> polygon, Vector2[] boundary)
        {
            var input = new List<Vector2>(polygon); var output = new List<Vector2>();
            for (int side = 0; side < boundary.Length && input.Count > 0; side++)
            {
                output.Clear(); var a = boundary[side]; var edge = boundary[(side + 1) % boundary.Length] - a;
                var previous = input[input.Count - 1]; float before = Cross(edge, previous - a);
                foreach (var current in input)
                {
                    float distance = Cross(edge, current - a);
                    if ((distance >= 0) != (before >= 0)) output.Add(previous + (current - previous) * (before / (before - distance)));
                    if (distance >= 0) output.Add(current);
                    previous = current; before = distance;
                }
                (input, output) = (output, input);
            }
            return input;
        }
    }
}
