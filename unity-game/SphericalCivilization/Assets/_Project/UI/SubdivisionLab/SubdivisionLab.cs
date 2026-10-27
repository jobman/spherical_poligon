using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UIElements;
using SphericalCivilization.World;

namespace SphericalCivilization
{
    [RequireComponent(typeof(UIDocument))]
    public sealed class SubdivisionLab : MonoBehaviour
    {
        public TextAsset worldAsset;
        public Material previewMaterial;
        public MeshFilter previewSurface;
        public Camera previewCamera;
        public int HexagonCount { get; private set; } = 37;
        public int PentagonCount { get; private set; } = 37;
        public uint Seed { get; private set; } = 1337;
        public OperationalWorld Preview { get; private set; }
        public int[] SampleIds { get; private set; }
        public double LastGenerationMilliseconds { get; private set; }

        private ReferenceWorld _source;
        private Mesh _mesh;
        private SliderInt _hexSlider, _pentSlider;
        private Label _hexValue, _pentValue, _status;
        private Button _copy, _save, _apply;
        private IVisualElementScheduledItem _pending;

        private void OnEnable()
        {
            _source = JsonUtility.FromJson<ReferenceWorld>(worldAsset.text);
            var hexagons = _source.tiles.Where(t => t.vertices.Length == 6).OrderBy(t => t.id).ToArray();
            var pentagons = _source.tiles.Where(t => t.vertices.Length == 5).OrderBy(t => t.id).ToArray();
            SampleIds = new[] { hexagons[0].id, hexagons[hexagons.Length / 3].id, hexagons[hexagons.Length * 2 / 3].id,
                pentagons[0].id, pentagons[pentagons.Length / 3].id, pentagons[pentagons.Length * 2 / 3].id };
            if (!WorldSettingsStore.TryLoad(out var settings)) settings = new WorldSettings();
            settings.Normalize();
            Seed = settings.seed;
            var root = GetComponent<UIDocument>().rootVisualElement;
            root.AddToClassList("lab-document");
            root.style.unityFontDefinition = FontDefinition.FromFont(Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf"));
            root.pickingMode = PickingMode.Ignore;
            _hexSlider = root.Q<SliderInt>("hexSlider"); _pentSlider = root.Q<SliderInt>("pentSlider");
            _hexValue = root.Q<Label>("hexValue"); _pentValue = root.Q<Label>("pentValue"); _status = root.Q<Label>("labStatus");
            _copy = root.Q<Button>("copyLabButton"); _save = root.Q<Button>("saveLabButton"); _apply = root.Q<Button>("applyLabButton");
            _hexSlider.RegisterValueChangedCallback(CountChanged); _pentSlider.RegisterValueChangedCallback(CountChanged);
            _copy.clicked += CopyValues; _save.clicked += SaveValues; _apply.clicked += ApplyToGlobe;
            SetCounts(settings.hexagonSubtilesPerTile, settings.pentagonSubtilesPerTile);
        }

        private void OnDisable()
        {
            _pending?.Pause();
            _hexSlider?.UnregisterValueChangedCallback(CountChanged); _pentSlider?.UnregisterValueChangedCallback(CountChanged);
            if (_copy != null) _copy.clicked -= CopyValues;
            if (_save != null) _save.clicked -= SaveValues;
            if (_apply != null) _apply.clicked -= ApplyToGlobe;
            ClearMesh();
        }

        private void LateUpdate()
        {
            previewCamera.rect = new Rect(0f, 0.27f, 1f, 0.60f);
            float aspect = (float)Math.Max(1, previewCamera.pixelWidth) / Math.Max(1, previewCamera.pixelHeight);
            previewCamera.orthographicSize = Mathf.Max(2.45f, 3.9f / aspect);
        }

        private void CountChanged(ChangeEvent<int> change)
        {
            _hexValue.text = _hexSlider.value.ToString(); _pentValue.text = _pentSlider.value.ToString();
            _status.text = "Обновление примеров…";
            _pending?.Pause();
            _pending = GetComponent<UIDocument>().rootVisualElement.schedule.Execute(() =>
            {
                try
                {
                    SetCounts(_hexSlider.value, _pentSlider.value);
                    _status.text = $"Всего на глобусе: {630 * HexagonCount + 12 * PentagonCount:N0} субтайлов. Не сохранено.";
                }
                catch (Exception exception) { _status.text = "Не удалось построить примеры"; Debug.LogException(exception); }
            }).StartingIn(100);
        }

        public void SetCounts(int hexagons, int pentagons)
        {
            hexagons = Mathf.Clamp(hexagons, OperationalSubdivision.MinSubtilesPerTile, OperationalSubdivision.MaxSubtilesPerTile);
            pentagons = Mathf.Clamp(pentagons, OperationalSubdivision.MinSubtilesPerTile, OperationalSubdivision.MaxSubtilesPerTile);
            var watch = System.Diagnostics.Stopwatch.StartNew();
            var next = OperationalSubdivision.BuildPreview(_source, SampleIds, new SubdivisionOptions
                { SubtilesPerTile = hexagons, PentagonSubtilesPerTile = pentagons, Seed = Seed });
            var mesh = CreateSampleMesh(next);
            ClearMesh(); _mesh = mesh; previewSurface.sharedMesh = mesh; Preview = next;
            HexagonCount = hexagons; PentagonCount = pentagons;
            _hexSlider.SetValueWithoutNotify(hexagons); _pentSlider.SetValueWithoutNotify(pentagons);
            _hexValue.text = hexagons.ToString(); _pentValue.text = pentagons.ToString();
            LastGenerationMilliseconds = watch.Elapsed.TotalMilliseconds;
        }

        public WorldSettings GetSettings() => new()
        {
            subtilesPerTile = HexagonCount, hexagonSubtilesPerTile = HexagonCount,
            pentagonSubtilesPerTile = PentagonCount, seed = Seed
        };

        private void FlushPending()
        {
            _pending?.Pause();
            if (_hexSlider.value != HexagonCount || _pentSlider.value != PentagonCount) SetCounts(_hexSlider.value, _pentSlider.value);
        }

        private void CopyValues()
        {
            FlushPending(); GUIUtility.systemCopyBuffer = JsonUtility.ToJson(GetSettings(), true);
            _status.text = "Значения скопированы — можно вставить их в чат.";
        }

        private bool Save()
        {
            try
            {
                FlushPending(); WorldSettingsStore.Save(WorldSettingsStore.SettingsPath, GetSettings());
                _status.text = "Сохранено. Основной мир загрузит эти два значения при следующем запуске.";
                return true;
            }
            catch (Exception exception) { _status.text = "Не удалось сохранить настройки"; Debug.LogWarning(exception.Message); return false; }
        }

        private void SaveValues() => Save();
        private void ApplyToGlobe() { if (Save()) SceneManager.LoadScene("Globe"); }

        private Mesh CreateSampleMesh(OperationalWorld map)
        {
            var positions = new List<Vector3>(); var normals = new List<Vector3>(); var colors = new List<Color>();
            var triangles = new List<int>(); var barycentrics = new List<Vector3>(); var borders = new List<Vector4>(); var regions = new List<Vector4>();
            var distancesA = new List<Vector3>(); var distancesB = new List<Vector3>();
            float radius = 0f;
            foreach (int id in SampleIds)
            {
                var tile = map.TilesById[id]; var center = Mean(tile.Corners, map);
                foreach (int corner in tile.Corners) radius = Mathf.Max(radius, (map.Vertices[corner] - center).magnitude);
            }
            for (int sample = 0; sample < SampleIds.Length; sample++)
            {
                var tile = map.TilesById[SampleIds[sample]]; var center = Mean(tile.Corners, map);
                var u = Vector3.ProjectOnPlane(map.Vertices[tile.Corners[0]] - center, tile.Normal).normalized;
                var v = Vector3.Cross(tile.Normal, u).normalized;
                var offset = new Vector3((sample % 3 - 1) * 2.7f, sample < 3 ? 1.3f : -1.3f, 0f);
                var edgeStarts = new Vector3[tile.Corners.Length]; var edgeNormals = new Vector3[tile.Corners.Length];
                for (int side = 0; side < tile.Corners.Length; side++)
                {
                    edgeStarts[side] = map.Vertices[tile.Corners[side]];
                    edgeNormals[side] = Vector3.Cross(tile.Normal, map.Vertices[tile.Corners[(side + 1) % tile.Corners.Length]] - edgeStarts[side]).normalized;
                }
                foreach (int index in tile.SubtileIndices)
                {
                    var cell = map.Subtiles[index];
                    float variation = 0.94f + ((uint)cell.Id * 2654435761u % 101) / 100f * 0.12f;
                    var color = (sample < 3 ? new Color(0.28f, 0.58f, 0.76f) : new Color(0.32f, 0.69f, 0.56f)).linear * variation;
                    for (int side = 0; side < cell.Vertices.Length; side++)
                    {
                        // Reverse the projected CCW perimeter to face the camera at -Z.
                        Add(cell.Center, Vector3.right); Add(map.Vertices[cell.Vertices[(side + 1) % cell.Vertices.Length]], Vector3.up);
                        Add(map.Vertices[cell.Vertices[side]], Vector3.forward);
                    }
                    void Add(Vector3 p, Vector3 barycentric)
                    {
                        var delta = p - center;
                        positions.Add(new Vector3(Vector3.Dot(delta, u) / radius, Vector3.Dot(delta, v) / radius, 0f) + offset);
                        normals.Add(Vector3.back); colors.Add(color); triangles.Add(triangles.Count); barycentrics.Add(barycentric);
                        borders.Add(new Vector4(1, 0, 0, tile.Id)); regions.Add(new Vector4(0, 0, 0, index));
                        var a = Vector3.one * 100000f; var b = a;
                        for (int edge = 0; edge < tile.Corners.Length; edge++)
                        {
                            float distance = Mathf.Max(0f, Vector3.Dot(p - edgeStarts[edge], edgeNormals[edge]));
                            if (edge < 3) a[edge] = distance; else b[edge - 3] = distance;
                        }
                        distancesA.Add(a); distancesB.Add(b);
                    }
                }
            }
            var mesh = new Mesh { name = "Subtile comparison samples", hideFlags = HideFlags.DontSave,
                indexFormat = positions.Count > 65535 ? UnityEngine.Rendering.IndexFormat.UInt32 : UnityEngine.Rendering.IndexFormat.UInt16 };
            mesh.SetVertices(positions); mesh.SetNormals(normals); mesh.SetColors(colors); mesh.SetUVs(0, barycentrics);
            mesh.SetUVs(1, borders); mesh.SetUVs(2, regions); mesh.SetUVs(3, distancesA); mesh.SetUVs(4, distancesB);
            mesh.SetTriangles(triangles, 0); mesh.RecalculateBounds();
            return mesh;
        }

        private static Vector3 Mean(int[] corners, OperationalWorld map)
        { var center = Vector3.zero; foreach (int id in corners) center += map.Vertices[id]; return center / corners.Length; }

        private void ClearMesh()
        {
            if (_mesh == null) return;
            if (previewSurface != null) previewSurface.sharedMesh = null;
            if (Application.isPlaying) Destroy(_mesh); else DestroyImmediate(_mesh);
            _mesh = null;
        }
    }
}
