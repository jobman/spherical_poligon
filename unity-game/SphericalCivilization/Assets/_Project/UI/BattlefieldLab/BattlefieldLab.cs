using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.SceneManagement;
using UnityEngine.UIElements;
using SphericalCivilization.World;

namespace SphericalCivilization.Battle
{
    [RequireComponent(typeof(UIDocument))]
    public sealed class BattlefieldLab : MonoBehaviour
    {
        public const string SceneName = "BattlefieldLab";
        public TextAsset worldAsset;
        public Material previewMaterial;
        public Camera previewCamera;
        public OperationalWorld World { get; private set; }
        public List<BattleLabSample> Samples { get; private set; }
        public IReadOnlyList<Battlefield> Fields => _fields;
        public int SizePercent { get; private set; } = 100;
        public float ReferenceRadius { get; private set; }
        public bool IsReady => _fields.Count == 3;
        public double LastGenerationMilliseconds { get; private set; }

        private static OperationalWorld _nextWorld;
        private static int _nextFirst = -1, _nextSecond = -1;
        private SliderInt _slider;
        private Label _value, _status;
        private Button _save, _back;
        private readonly Label[] _titles = new Label[3], _counts = new Label[3];
        private IVisualElementScheduledItem _pending;
        private Material _lineMaterial, _unitMaterial;
        private readonly List<Battlefield> _fields = new();
        private readonly List<GameObject> _roots = new();
        private readonly List<Mesh> _meshes = new();
        private readonly List<Vector3> _centers = new();
        private float _halfWidth, _halfHeight;

        public static void OpenFromGlobe(GlobePreview globe)
        {
            _nextWorld = globe.Topology; _nextFirst = globe.SelectedSubtileIndex; _nextSecond = globe.AttackTargetSubtileIndex;
            SceneManager.LoadScene(SceneName);
        }

        private void OnEnable()
        {
            if (!Application.isPlaying) return;
            Application.targetFrameRate = 60;
            var root = GetComponent<UIDocument>().rootVisualElement;
            root.AddToClassList("battle-lab-document"); root.pickingMode = PickingMode.Ignore;
            root.style.unityFontDefinition = FontDefinition.FromFont(Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf"));
            _slider = root.Q<SliderInt>("hexSizeSlider"); _value = root.Q<Label>("hexSizeValue"); _status = root.Q<Label>("battleLabStatus");
            _save = root.Q<Button>("saveBattleSizeButton"); _back = root.Q<Button>("backToGlobeButton");
            for (int i = 0; i < 3; i++) { _titles[i] = root.Q<Label>("sampleTitle" + i); _counts[i] = root.Q<Label>("sampleCount" + i); }
            _slider.RegisterValueChangedCallback(SizeChanged); _save.clicked += SaveValues; _back.clicked += BackToGlobe;
            _save.SetEnabled(false); _slider.SetEnabled(false);
            StartCoroutine(Initialize());
        }

        private IEnumerator Initialize()
        {
            yield return null;
            try
            {
                if (_nextWorld != null) World = _nextWorld;
                else
                {
                    if (!WorldSettingsStore.TryLoad(out var settings)) settings = new WorldSettings();
                    settings.Normalize();
                    World = OperationalSubdivision.Build(JsonUtility.FromJson<ReferenceWorld>(worldAsset.text), new SubdivisionOptions
                    { SubtilesPerTile = settings.hexagonSubtilesPerTile, PentagonSubtilesPerTile = settings.pentagonSubtilesPerTile, Seed = settings.seed });
                }
                Samples = BattleLabSamples.Select(World, _nextFirst, _nextSecond);
                _nextWorld = null; _nextFirst = _nextSecond = -1;
                ReferenceRadius = BattleSettings.ReferenceRadius(World);
                bool loaded = BattleSettingsStore.TryLoad(out var saved);
                int percent = loaded ? Mathf.RoundToInt(saved.hexWorldRadius / ReferenceRadius * 100) : 100;
                _slider.lowValue = Math.Min(30, percent); _slider.highValue = Math.Max(300, percent);
                _lineMaterial = new Material(previewMaterial) { hideFlags = HideFlags.DontSave, renderQueue = previewMaterial.renderQueue + 1 };
                _unitMaterial = new Material(previewMaterial) { hideFlags = HideFlags.DontSave, renderQueue = previewMaterial.renderQueue + 2 };
                foreach (var sample in Samples)
                {
                    var largest = Battlefield.Build(World, sample.First, sample.Second, 0, hexWorldRadius: ReferenceRadius * _slider.highValue / 100);
                    var center = GeographicCenter(largest);
                    _halfWidth = Mathf.Max(_halfWidth, Mathf.Abs(largest.Bounds.min.x * largest.WorldHexRadius - center.x), Mathf.Abs(largest.Bounds.max.x * largest.WorldHexRadius - center.x));
                    _halfHeight = Mathf.Max(_halfHeight, Mathf.Abs(largest.Bounds.min.y * largest.WorldHexRadius - center.y), Mathf.Abs(largest.Bounds.max.y * largest.WorldHexRadius - center.y));
                }
                SetSizePercent(percent);
                _save.SetEnabled(true); _slider.SetEnabled(true);
                _status.text = loaded ? "Загружен сохранённый размер. Можно подобрать другой." : "Предпросмотр. Размер пока не сохранён.";
            }
            catch (Exception e) { _status.text = "Не удалось подготовить примеры: " + e.Message; Debug.LogException(e); }
        }

        private void SizeChanged(ChangeEvent<int> change)
        {
            _value.text = change.newValue + "%"; _status.text = "Обновление примеров…";
            _pending?.Pause();
            _pending = GetComponent<UIDocument>().rootVisualElement.schedule.Execute(() =>
            {
                try { SetSizePercent(_slider.value); }
                catch (Exception e) { _slider.SetValueWithoutNotify(SizePercent); _value.text = SizePercent + "%"; _status.text = e.Message; }
            }).StartingIn(100);
        }

        public void SetSizePercent(int percent)
        {
            if (World == null) throw new InvalidOperationException("Lab world is not ready.");
            percent = Mathf.Clamp(percent, _slider.lowValue, _slider.highValue);
            var watch = System.Diagnostics.Stopwatch.StartNew();
            var fields = new List<Battlefield>(); var roots = new List<GameObject>(); var meshes = new List<Mesh>();
            try
            {
                foreach (var sample in Samples)
                {
                    var field = Battlefield.Build(World, sample.First, sample.Second, 0, hexWorldRadius: ReferenceRadius * percent / 100);
                    fields.Add(field);
                    var root = new GameObject(sample.Title) { hideFlags = HideFlags.DontSave }; roots.Add(root);
                    root.transform.localScale = Vector3.one * field.WorldHexRadius;
                    Draw("Hexes", BattlefieldMeshes.Surface(field), previewMaterial, root);
                    Draw("Boundaries", BattlefieldMeshes.Boundaries(field, World), _lineMaterial, root);
                    Draw("Test units", BattlefieldMeshes.Units(field, 0), _unitMaterial, root);
                }
            }
            catch { foreach (var root in roots) Destroy(root); foreach (var mesh in meshes) Destroy(mesh); throw; }
            ClearPreviews(); _fields.AddRange(fields); _roots.AddRange(roots); _meshes.AddRange(meshes);
            for (int i = 0; i < fields.Count; i++)
            {
                _centers.Add(GeographicCenter(fields[i])); _titles[i].text = Samples[i].Title;
                _counts[i].text = $"{fields[i].CoreHexCount:N0} гексов поля\n+ {fields[i].Hexes.Count - fields[i].CoreHexCount:N0} во внешних рядах";
            }
            SizePercent = percent; _slider.SetValueWithoutNotify(percent); _value.text = percent + "%";
            _status.text = "Предпросмотр. Не сохранено."; LastGenerationMilliseconds = watch.Elapsed.TotalMilliseconds;
            UpdateLayout();
            void Draw(string name, Mesh mesh, Material material, GameObject parent)
            {
                meshes.Add(mesh); var go = new GameObject(name); go.transform.SetParent(parent.transform, false);
                go.AddComponent<MeshFilter>().sharedMesh = mesh; go.AddComponent<MeshRenderer>().sharedMaterial = material;
            }
        }

        public BattleSettings GetSettings() => new() { hexWorldRadius = ReferenceRadius * SizePercent / 100 };
        public void SaveSettings(string path)
        {
            _pending?.Pause();
            if (_slider.value != SizePercent) SetSizePercent(_slider.value);
            BattleSettingsStore.Save(path, GetSettings());
            _status.text = "Сохранено. Новые бои используют этот размер.";
        }
        private void SaveValues()
        { try { SaveSettings(BattleSettingsStore.SettingsPath); } catch (Exception e) { _status.text = "Не удалось сохранить: " + e.Message; } }
        private void BackToGlobe() => SceneManager.LoadScene("Globe");
        private void Update() { if (Keyboard.current?.escapeKey.wasPressedThisFrame == true) BackToGlobe(); }
        private void LateUpdate() { if (IsReady) UpdateLayout(); }
        private void UpdateLayout()
        {
            previewCamera.rect = new Rect(0, .27f, 1, .57f);
            float aspect = (float)Math.Max(1, previewCamera.pixelWidth) / Math.Max(1, previewCamera.pixelHeight);
            previewCamera.orthographicSize = Mathf.Max(_halfHeight * 1.3f, _halfWidth * 3.4f / aspect);
            float spacing = previewCamera.orthographicSize * 2 * aspect / 3;
            for (int i = 0; i < _roots.Count; i++) _roots[i].transform.position = new Vector3((i - 1) * spacing, 0, 0) - _centers[i];
        }
        private static Vector3 GeographicCenter(Battlefield field)
        {
            Vector2 min = field.PlayableBoundary[0], max = min;
            foreach (var p in field.PlayableBoundary) { min = Vector2.Min(min, p); max = Vector2.Max(max, p); }
            return (Vector3)((min + max) * (.5f * field.WorldHexRadius));
        }
        private void ClearPreviews()
        {
            foreach (var root in _roots) { root.SetActive(false); Destroy(root); }
            foreach (var mesh in _meshes) Destroy(mesh);
            _roots.Clear(); _meshes.Clear(); _fields.Clear(); _centers.Clear();
        }
        private void OnDisable()
        {
            StopAllCoroutines(); _pending?.Pause(); _slider?.UnregisterValueChangedCallback(SizeChanged);
            if (_save != null) _save.clicked -= SaveValues; if (_back != null) _back.clicked -= BackToGlobe;
            ClearPreviews(); if (_lineMaterial != null) Destroy(_lineMaterial); if (_unitMaterial != null) Destroy(_unitMaterial);
            World = null;
        }
    }
}
