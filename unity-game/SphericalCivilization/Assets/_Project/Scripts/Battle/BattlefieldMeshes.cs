using System.Collections.Generic;
using UnityEngine;
using SphericalCivilization.World;

namespace SphericalCivilization.Battle
{
    public static class BattlefieldMeshes
    {
        private sealed class Builder
        {
            private readonly List<Vector3> _positions = new();
            private readonly List<Color> _colors = new();
            private readonly List<Vector3> _barycentrics = new();
            private readonly List<Vector2> _cells = new();
            private readonly List<int> _triangles = new();
            public void Triangle(Vector2 a, Vector2 b, Vector2 c, Color ca, Color cb, Color cc, float z, int cell = -2)
            {
                Add(a, ca, Vector3.right); Add(b, cb, Vector3.up); Add(c, cc, Vector3.forward);
                void Add(Vector2 p, Color color, Vector3 barycentric)
                {
                    _positions.Add(new Vector3(p.x, p.y, z)); _colors.Add(color); _barycentrics.Add(barycentric);
                    _cells.Add(new Vector2(cell >= 0 ? 1 : 0, cell)); _triangles.Add(_triangles.Count);
                }
            }
            public Mesh Finish(string name)
            {
                var mesh = new Mesh { name = name, hideFlags = HideFlags.DontSave,
                    indexFormat = _positions.Count > 65535 ? UnityEngine.Rendering.IndexFormat.UInt32 : UnityEngine.Rendering.IndexFormat.UInt16 };
                mesh.SetVertices(_positions); mesh.SetColors(_colors); mesh.SetUVs(0, _barycentrics); mesh.SetUVs(1, _cells);
                mesh.SetTriangles(_triangles, 0); mesh.RecalculateBounds(); return mesh;
            }
        }

        public static Mesh Surface(Battlefield field)
        {
            var mesh = new Builder();
            for (int index = 0; index < field.Hexes.Count; index++)
            {
                var hex = field.Hexes[index];
                Color color = hex.RetreatRow > 0 ? new Color(.12f, .19f, .17f) :
                    hex.SourceSubtileIndex == field.FirstSubtileIndex ? new Color(.19f, .29f, .35f) :
                    hex.SourceSubtileIndex == field.SecondSubtileIndex ? new Color(.26f, .31f, .22f) : new Color(.21f, .27f, .25f);
                float coverage = Mathf.SmoothStep(0, 1, hex.Coverage);
                if (hex.RetreatRow == 0) color *= .65f + .35f * coverage;
                color = color.linear;
                Color Fade(float alpha) { var c = color; c.a = alpha; return c; }
                for (int side = 0; side < 6; side++)
                {
                    var a = hex.Coord.CornerKey(side); var b = hex.Coord.CornerKey((side + 1) % 6);
                    mesh.Triangle(hex.Coord.Center, HexCoord.CornerPosition(b), HexCoord.CornerPosition(a),
                        Fade(Battlefield.Opacity(hex.RetreatRow)), Fade(field.CornerOpacity[b]), Fade(field.CornerOpacity[a]), 0, index);
                }
            }
            return mesh.Finish("Battle hex surface");
        }

        public static Mesh Boundaries(Battlefield field, OperationalWorld world)
        {
            var mesh = new Builder(); var seen = new HashSet<int>();
            var hullColor = new Color(.86f, .91f, .8f).linear;
            hullColor.a = 1;
            for (int i = 0; i < field.PlayableBoundary.Length; i++)
            {
                var start = field.PlayableBoundary[i]; var end = field.PlayableBoundary[(i + 1) % field.PlayableBoundary.Length];
                var normal = new Vector2(-(end - start).y, (end - start).x).normalized * .11f;
                mesh.Triangle(start - normal, end - normal, end + normal, hullColor, hullColor, hullColor, -.02f);
                mesh.Triangle(start - normal, end + normal, start + normal, hullColor, hullColor, hullColor, -.02f);
            }
            foreach (var region in field.Regions)
            foreach (int id in world.Subtiles[region.SubtileIndex].Edges)
            {
                if (!seen.Add(id)) continue;
                var edge = world.Edges[id];
                bool first = edge.FirstSubtile == field.FirstSubtileIndex || edge.SecondSubtile == field.FirstSubtileIndex;
                bool second = edge.FirstSubtile == field.SecondSubtileIndex || edge.SecondSubtile == field.SecondSubtileIndex;
                var color = first && second ? new Color(.96f, .9f, .62f) : first ? new Color(.4f, .77f, .95f) : second ? new Color(.93f, .74f, .36f) : new Color(.6f, .7f, .62f);
                color = color.linear;
                var a = field.Project(world.Vertices[edge.Start]); var b = field.Project(world.Vertices[edge.End]);
                int steps = Mathf.Max(1, Mathf.CeilToInt((b - a).magnitude / .4f));
                var normal = new Vector2(-(b - a).y, (b - a).x).normalized * (first || second ? .07f : .08f);
                for (int step = 0; step < steps; step++)
                {
                    var start = Vector2.Lerp(a, b, (float)step / steps); var end = Vector2.Lerp(a, b, (float)(step + 1) / steps);
                    var ca = color; var cb = color;
                    ca.a = first || second ? 1f : field.OpacityAt(start);
                    cb.a = first || second ? 1f : field.OpacityAt(end);
                    if (ca.a <= 0 && cb.a <= 0) continue;
                    mesh.Triangle(start - normal, end - normal, end + normal, ca, cb, cb, -.02f);
                    mesh.Triangle(start - normal, end + normal, start + normal, ca, cb, ca, -.02f);
                }
            }
            return mesh.Finish("Battle geographic boundaries");
        }

        public static Mesh Units(Battlefield field, int selectedUnit)
        {
            var mesh = new Builder();
            for (int i = 0; i < field.Units.Count; i++)
            {
                var unit = field.Units[i]; if (unit.Escaped) continue;
                var center = field.Hexes[unit.HexIndex].Coord.Center;
                Disc(center, i == selectedUnit ? .52f : .45f, i == selectedUnit ? new Color(.98f, .95f, .75f) : new Color(.07f, .09f, .1f), -.05f);
                Disc(center, .32f, unit.Side == 0 ? new Color(.25f, .8f, 1f) : new Color(1f, .55f, .2f), -.06f);
            }
            return mesh.Finish("Battle test units");
            void Disc(Vector2 center, float radius, Color color, float z)
            {
                color = color.linear;
                for (int side = 0; side < 20; side++)
                {
                    float a = side * Mathf.PI * .1f, b = (side + 1) * Mathf.PI * .1f;
                    mesh.Triangle(center, center + new Vector2(Mathf.Cos(b), Mathf.Sin(b)) * radius,
                        center + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * radius, color, color, color, z);
                }
            }
        }
    }
}
