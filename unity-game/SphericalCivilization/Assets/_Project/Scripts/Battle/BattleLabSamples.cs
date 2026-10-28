using System;
using System.Collections.Generic;
using UnityEngine;
using SphericalCivilization.World;

namespace SphericalCivilization.Battle
{
    public sealed class BattleLabSample
    {
        public int First, Second;
        public string Title;
    }

    public static class BattleLabSamples
    {
        public static List<BattleLabSample> Select(OperationalWorld world, int chosenFirst = -1, int chosenSecond = -1)
        {
            var result = new List<BattleLabSample>(); var used = new HashSet<ulong>();
            ulong Key(int a, int b) => ((ulong)(uint)Math.Min(a, b) << 32) | (uint)Math.Max(a, b);
            void Add(int a, int b, string title)
            { result.Add(new BattleLabSample { First = a, Second = b, Title = title }); used.Add(Key(a, b)); }
            if (chosenFirst >= 0 && chosenFirst < world.Subtiles.Count && Array.IndexOf(world.Subtiles[chosenFirst].Neighbors, chosenSecond) >= 0)
                Add(chosenFirst, chosenSecond, "Выбранная пара");
            else
            {
                float best = -1; int a = -1, b = -1;
                foreach (var edge in world.Edges)
                {
                    var parentA = world.Subtiles[edge.FirstSubtile].ParentTileId;
                    if (parentA != world.Subtiles[edge.SecondSubtile].ParentTileId || world.TilesById[parentA].Corners.Length != 6) continue;
                    float length = (world.Vertices[edge.Start] - world.Vertices[edge.End]).sqrMagnitude;
                    if (length > best) { best = length; a = edge.FirstSubtile; b = edge.SecondSubtile; }
                }
                if (a < 0) throw new InvalidOperationException("No internal sample pair.");
                Add(a, b, "Внутри большого тайла");
            }
            float shortest = float.MaxValue; int first = -1, second = -1;
            foreach (var edge in world.Edges)
            {
                if (used.Contains(Key(edge.FirstSubtile, edge.SecondSubtile))) continue;
                float length = (world.Vertices[edge.Start] - world.Vertices[edge.End]).sqrMagnitude;
                if (length < shortest) { shortest = length; first = edge.FirstSubtile; second = edge.SecondSubtile; }
            }
            Add(first, second, "Короткая общая грань");
            float longest = -1; first = second = -1;
            foreach (var edge in world.Edges)
            {
                if (edge.ParentBoundaryId < 0 || used.Contains(Key(edge.FirstSubtile, edge.SecondSubtile))) continue;
                int parentA = world.Subtiles[edge.FirstSubtile].ParentTileId, parentB = world.Subtiles[edge.SecondSubtile].ParentTileId;
                if (world.TilesById[parentA].Corners.Length != 5 && world.TilesById[parentB].Corners.Length != 5) continue;
                float length = (world.Vertices[edge.Start] - world.Vertices[edge.End]).sqrMagnitude;
                if (length > longest) { longest = length; first = edge.FirstSubtile; second = edge.SecondSubtile; }
            }
            if (first < 0) throw new InvalidOperationException("No cross-parent sample pair.");
            Add(first, second, "Граница больших тайлов");
            return result;
        }
    }
}
