using System;
using System.Collections.Generic;
using UnityEngine;

namespace SphericalCivilization.World
{
    public sealed class SubdivisionOptions
    {
        // Zero chooses a shared boundary density from the requested cell count.
        public int EdgeSegments;
        public int SubtilesPerTile = 37;
        // Zero preserves the legacy uniform-count setting.
        public int PentagonSubtilesPerTile;
        public uint Seed = 1337;
        public int CountForSides(int sides) => sides == 5 && PentagonSubtilesPerTile != 0 ? PentagonSubtilesPerTile : SubtilesPerTile;
    }

    public sealed class OperationalTile
    {
        public int Id;
        public int[] Corners;
        public int[] BoundaryIds;
        public int[] SubtileIndices;
        public Vector3 Normal;
        public Color Color;
        public string Terrain;
    }

    public sealed class OperationalSubtile
    {
        // IDs are stable across generation order: parent ID in the high 32 bits,
        // deterministic local cell index in the low 32 bits.
        public long Id;
        public int ParentTileId;
        public int[] Vertices;
        public int[] Edges;
        public int[] Neighbors;
        public Vector3 Center;
    }

    public sealed class OperationalEdge
    {
        public int Id;
        public int Start, End;
        public int FirstSubtile, SecondSubtile;
        public int ParentBoundaryId = -1;
    }

    public sealed class RegionBoundary
    {
        public int Id;
        public int Start, End;
        public int FirstTileId, SecondTileId;
        // Ordered from Start to End, shared by both parents. Never generated twice.
        public int[] Vertices;
        public int[] Subedges;
    }

    public sealed class OperationalWorld
    {
        public readonly List<Vector3> Vertices = new();
        public readonly List<OperationalTile> Tiles = new();
        public readonly List<OperationalSubtile> Subtiles = new();
        public readonly List<OperationalEdge> Edges = new();
        public readonly List<RegionBoundary> Boundaries = new();
        public readonly Dictionary<int, OperationalTile> TilesById = new();
        public readonly Dictionary<long, int> SubtileIndicesById = new();
    }
}
