using System;
using System.Collections.Generic;
using UnityEngine;
using SphericalCivilization.World;

namespace SphericalCivilization
{
    [ExecuteAlways]
    [RequireComponent(typeof(MeshFilter), typeof(MeshRenderer), typeof(MeshCollider))]
    public sealed class GlobePreview : MonoBehaviour
    {
        public TextAsset worldAsset;
        public Material terrainMaterial;
        [Range(OperationalSubdivision.MinSubtilesPerTile, OperationalSubdivision.MaxSubtilesPerTile)] public int subtilesPerTile = 37;
        [Tooltip("Zero uses the legacy count for both tile shapes.")]
        [Range(0, OperationalSubdivision.MaxSubtilesPerTile)] public int pentagonSubtilesPerTile;
        public uint subdivisionSeed = 1337;
        public int HexagonSubtileCount => subtilesPerTile;
        public int PentagonSubtileCount => pentagonSubtilesPerTile == 0 ? subtilesPerTile : pentagonSubtilesPerTile;
        public int edgeSubdivisions => OperationalSubdivision.GetEdgeSegments(subtilesPerTile);

        public int TileCount => _topology?.Tiles.Count ?? 0;
        public int SubtileCount => _topology?.Subtiles.Count ?? 0;
        public int SelectedTileId { get; private set; } = -1;
        public int SelectedSubtileIndex { get; private set; } = -1;
        public long? SelectedSubtileId => SelectedSubtileIndex >= 0 ? _topology.Subtiles[SelectedSubtileIndex].Id : null;
        public int AttackTargetSubtileIndex { get; private set; } = -1;
        public long? AttackTargetSubtileId => AttackTargetSubtileIndex >= 0 ? _topology.Subtiles[AttackTargetSubtileIndex].Id : null;
        public int TriangleCount => _triangleSubtiles.Count;
        public OperationalWorld Topology => _topology;
        public float SubtileVisibility => _visibility;

        private OperationalWorld _topology;
        private Mesh _surface;
        private MaterialPropertyBlock _properties;
        private float _visibility = -1f;
        private readonly List<int> _triangleSubtiles = new();
        private static readonly int SelectedTileProperty = Shader.PropertyToID("_SelectedTileId");
        private static readonly int SelectedSubtileProperty = Shader.PropertyToID("_SelectedSubtileId");
        private static readonly int AttackTargetProperty = Shader.PropertyToID("_AttackTargetSubtileId");
        private static readonly int SubtileVisibilityProperty = Shader.PropertyToID("_SubtileVisibility");

        private void OnEnable()
        {
            if (Application.isPlaying && WorldSettingsStore.TryLoad(out var settings))
            {
                subtilesPerTile = settings.hexagonSubtilesPerTile;
                pentagonSubtilesPerTile = settings.pentagonSubtilesPerTile;
                subdivisionSeed = settings.seed;
            }
            if (worldAsset != null && terrainMaterial != null) Rebuild();
        }

        private void OnDisable() => ClearGenerated();
        private void LateUpdate() => UpdateVisibility();

        public void Rebuild() => ApplySubdivision(HexagonSubtileCount, PentagonSubtileCount);

        public void ApplySubdivision(int count) => ApplySubdivision(count, count);

        public WorldSettings GetWorldSettings() => new()
        {
            subtilesPerTile = HexagonSubtileCount, hexagonSubtilesPerTile = HexagonSubtileCount,
            pentagonSubtilesPerTile = PentagonSubtileCount, seed = subdivisionSeed
        };

        public void ApplySubdivision(int count, int pentagonCount)
        {
            count = Mathf.Clamp(count, OperationalSubdivision.MinSubtilesPerTile, OperationalSubdivision.MaxSubtilesPerTile);
            pentagonCount = Mathf.Clamp(pentagonCount, OperationalSubdivision.MinSubtilesPerTile, OperationalSubdivision.MaxSubtilesPerTile);
            var reference = JsonUtility.FromJson<ReferenceWorld>(worldAsset.text);
            var next = OperationalSubdivision.Build(reference, new SubdivisionOptions
            { SubtilesPerTile = count, PentagonSubtilesPerTile = pentagonCount, Seed = subdivisionSeed });
            ClearGenerated();
            _topology = next;
            subtilesPerTile = count;
            pentagonSubtilesPerTile = pentagonCount;
            var vertices = new List<Vector3>();
            var normals = new List<Vector3>();
            var colors = new List<Color>();
            var triangles = new List<int>();
            var barycentrics = new List<Vector3>();
            var borders = new List<Vector4>();
            var regions = new List<Vector4>();
            var parentDistancesA = new List<Vector3>();
            var parentDistancesB = new List<Vector3>();
            var planes = new Dictionary<int, (Vector3[] starts, Vector3[] normals)>();
            foreach (var tile in _topology.Tiles)
            {
                var starts = new Vector3[tile.Corners.Length];
                var edgeNormals = new Vector3[tile.Corners.Length];
                for (int side = 0; side < tile.Corners.Length; side++)
                {
                    starts[side] = _topology.Vertices[tile.Corners[side]];
                    var end = _topology.Vertices[tile.Corners[(side + 1) % tile.Corners.Length]];
                    edgeNormals[side] = Vector3.Cross(tile.Normal, end - starts[side]).normalized;
                }
                planes.Add(tile.Id, (starts, edgeNormals));
            }
            for (int cellIndex = 0; cellIndex < _topology.Subtiles.Count; cellIndex++)
            {
                var cell = _topology.Subtiles[cellIndex];
                var parent = _topology.TilesById[cell.ParentTileId];
                var plane = planes[parent.Id];
                for (int side = 0; side < cell.Vertices.Length; side++)
                {
                    var a = cell.Center;
                    var b = _topology.Vertices[cell.Vertices[side]];
                    var c = _topology.Vertices[cell.Vertices[(side + 1) % cell.Vertices.Length]];
                    if (Vector3.Dot(Vector3.Cross(b - a, c - a), parent.Normal) < 0f) (b, c) = (c, b);
                    int first = vertices.Count;
                    vertices.Add(a); vertices.Add(b); vertices.Add(c);
                    barycentrics.Add(Vector3.right); barycentrics.Add(Vector3.up); barycentrics.Add(Vector3.forward);
                    bool parentBoundary = _topology.Edges[cell.Edges[side]].ParentBoundaryId >= 0;
                    for (int corner = 0; corner < 3; corner++)
                    {
                        normals.Add(parent.Normal); colors.Add(parent.Color);
                        borders.Add(new Vector4(1f, 0f, 0f, parent.Id));
                        regions.Add(new Vector4(parentBoundary ? 1f : 0f, 0f, 0f, cellIndex));
                        var position = corner == 0 ? a : corner == 1 ? b : c;
                        var distancesA = Vector3.one * 100000f;
                        var distancesB = Vector3.one * 100000f;
                        for (int edge = 0; edge < plane.starts.Length; edge++)
                        {
                            float distance = Vector3.Dot(position - plane.starts[edge], plane.normals[edge]);
                            distance = distance < 0.0000001f ? 0f : distance;
                            if (edge < 3) distancesA[edge] = distance; else distancesB[edge - 3] = distance;
                        }
                        parentDistancesA.Add(distancesA); parentDistancesB.Add(distancesB);
                    }
                    triangles.Add(first); triangles.Add(first + 1); triangles.Add(first + 2);
                    _triangleSubtiles.Add(cellIndex);
                }
            }
            _surface = new Mesh
            {
                name = "Operational globe", hideFlags = HideFlags.DontSave,
                indexFormat = vertices.Count > ushort.MaxValue ?
                    UnityEngine.Rendering.IndexFormat.UInt32 : UnityEngine.Rendering.IndexFormat.UInt16
            };
            _surface.SetVertices(vertices); _surface.SetNormals(normals); _surface.SetColors(colors);
            _surface.SetUVs(0, barycentrics); _surface.SetUVs(1, borders); _surface.SetUVs(2, regions);
            _surface.SetUVs(3, parentDistancesA); _surface.SetUVs(4, parentDistancesB);
            _surface.SetTriangles(triangles, 0); _surface.RecalculateBounds();
            GetComponent<MeshFilter>().sharedMesh = _surface;
            GetComponent<MeshRenderer>().sharedMaterial = terrainMaterial;
            GetComponent<MeshCollider>().sharedMesh = _surface;
            SelectedTileId = SelectedSubtileIndex = -1;
            _visibility = -1f;
            UpdateVisibility();
        }

        public bool TrySelectRay(Ray ray)
        {
            if (!TryGetSubtile(ray, out var cell)) return false;
            SelectSubtile(cell.Id);
            return true;
        }

        public bool TrySetAttackTargetRay(Ray ray)
        {
            if (TryGetSubtile(ray, out var cell)) return TrySetAttackTarget(cell.Id);
            ClearAttackTarget();
            return false;
        }

        public bool TrySetAttackTarget(long id)
        {
            if (_topology == null || SelectedSubtileIndex < 0 ||
                !_topology.SubtileIndicesById.TryGetValue(id, out int index) ||
                Array.IndexOf(_topology.Subtiles[SelectedSubtileIndex].Neighbors, index) < 0)
            {
                ClearAttackTarget();
                return false;
            }
            AttackTargetSubtileIndex = index;
            UpdateProperties();
            return true;
        }

        public void ClearAttackTarget()
        {
            AttackTargetSubtileIndex = -1;
            UpdateProperties();
        }

        public bool TryGetSubtile(Ray ray, out OperationalSubtile cell)
        {
            cell = null;
            if (!GetComponent<MeshCollider>().Raycast(ray, out var hit, 100f) ||
                hit.triangleIndex < 0 || hit.triangleIndex >= _triangleSubtiles.Count) return false;
            int index = _triangleSubtiles[hit.triangleIndex];
            cell = _topology.Subtiles[index];
            return true;
        }

        public void SelectTile(int id)
        {
            if (_topology == null || !_topology.TilesById.ContainsKey(id)) throw new ArgumentOutOfRangeException(nameof(id));
            SelectedTileId = id;
            SelectedSubtileIndex = -1;
            AttackTargetSubtileIndex = -1;
            UpdateProperties();
        }

        public void SelectSubtile(long id)
        {
            if (_topology == null || !_topology.SubtileIndicesById.TryGetValue(id, out int index)) throw new ArgumentOutOfRangeException(nameof(id));
            SelectedSubtileIndex = index;
            SelectedTileId = _topology.Subtiles[index].ParentTileId;
            AttackTargetSubtileIndex = -1;
            UpdateProperties();
        }

        public void ClearSelection()
        {
            SelectedTileId = SelectedSubtileIndex = -1;
            AttackTargetSubtileIndex = -1;
            UpdateProperties();
        }

        private void UpdateVisibility()
        {
            var camera = Camera.main;
            float distance = camera != null ? Vector3.Distance(camera.transform.position, transform.position) : 3.3f;
            float visibility = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(3.1f, 1.55f, distance));
            if (Mathf.Abs(visibility - _visibility) < 0.001f) return;
            _visibility = visibility;
            UpdateProperties();
        }

        private void UpdateProperties()
        {
            var renderer = GetComponent<MeshRenderer>();
            _properties ??= new MaterialPropertyBlock();
            renderer.GetPropertyBlock(_properties);
            _properties.SetFloat(SelectedTileProperty, SelectedTileId);
            _properties.SetFloat(SelectedSubtileProperty, SelectedSubtileIndex);
            _properties.SetFloat(AttackTargetProperty, AttackTargetSubtileIndex);
            _properties.SetFloat(SubtileVisibilityProperty, Mathf.Max(0f, _visibility));
            renderer.SetPropertyBlock(_properties);
        }

        private void ClearGenerated()
        {
            if (_surface != null)
            {
                GetComponent<MeshFilter>().sharedMesh = null;
                GetComponent<MeshCollider>().sharedMesh = null;
                if (Application.isPlaying) Destroy(_surface); else DestroyImmediate(_surface);
            }
            _surface = null;
            _topology = null;
            SelectedTileId = SelectedSubtileIndex = AttackTargetSubtileIndex = -1;
            _triangleSubtiles.Clear();
        }
    }
}
