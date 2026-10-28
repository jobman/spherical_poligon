using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.Rendering.Universal;

namespace SphericalCivilization.Battle
{
    [DefaultExecutionOrder(-100)]
    [RequireComponent(typeof(GlobePreview))]
    public sealed class BattlefieldController : MonoBehaviour
    {
        public Material battlefieldMaterial;
        [Range(100, 5000)] public int targetCoreHexes = 900;
        public Battlefield Field { get; private set; }
        public bool IsActive => _root != null;
        public Camera BattleCamera => _battleCamera;
        public int SelectedUnit { get; private set; } = 0;
        public int EscapedUnits { get { int count = 0; if (Field != null) foreach (var unit in Field.Units) if (unit.Escaped) count++; return count; } }
        private static BattlefieldController _active;
        private static int _lastExitFrame = -1;
        public static bool BlocksGlobeInput => (_active != null && _active.IsActive) || _lastExitFrame == Time.frameCount;
        public static string ActiveHint => _active != null && _active.IsActive ?
            $"Бой · ЛКМ: выбрать фишку / идти · Перетаскивание: обзор · Колесо: масштаб\n3-й ряд за оболочкой — побег · Сбежали: {_active.EscapedUnits}/2 · Пробел / Esc — к глобусу" : null;
        public static string SelectionHint => _active == null || _active._globe.SelectedSubtileIndex < 0 ?
            "ЛКМ — выбрать свой субтайл · ПКМ — соседняя цель атаки · Esc — меню" :
            _active._globe.AttackTargetSubtileIndex < 0 ?
            "Свой субтайл: оранжевый · ПКМ по соседнему — выбрать цель атаки · Esc — меню" :
            "Свой: оранжевый · Цель: красная · Пробел — начать бой · ЛКМ / ПКМ — изменить выбор · Esc — меню";

        private GlobePreview _globe;
        private OrbitCamera _orbit;
        private Camera _worldCamera, _battleCamera;
        private GameObject _root;
        private World.OperationalWorld _source;
        private bool _cameraEnabled, _rendererEnabled;
        private Mesh _surface, _boundaries, _units;
        private MeshFilter _unitFilter;
        private MeshRenderer _surfaceRenderer;
        private Material _lineMaterial, _unitMaterial;
        private float _fitSize, _nextStep;
        private readonly Queue<int> _path = new();
        private int _movingUnit = -1, _mouseButton = -1;
        private Vector2 _press, _previous;
        private bool _dragged;

        private void OnEnable() { _globe = GetComponent<GlobePreview>(); _active = this; }
        private void OnDisable() { ExitBattle(); if (_active == this) _active = null; }

        private void Update()
        {
            if (!Application.isPlaying) return;
            var keyboard = Keyboard.current;
            if (IsActive)
            {
                if (keyboard?.escapeKey.wasPressedThisFrame == true || keyboard?.spaceKey.wasPressedThisFrame == true) { ExitBattle(); return; }
                if (_source != _globe.Topology) { ExitBattle(); return; }
                UpdateBattleInput(keyboard, Mouse.current);
                if (_movingUnit >= 0 && _path.Count > 0 && Time.unscaledTime >= _nextStep)
                {
                    int next = _path.Dequeue();
                    if (!Field.TryMoveUnit(_movingUnit, next) || Field.Units[_movingUnit].Escaped) { _path.Clear(); _movingUnit = -1; }
                    _nextStep = Time.unscaledTime + .09f; RefreshUnits();
                }
            }
            else if (!CameraControlsPanel.IsMenuOpen && keyboard?.spaceKey.wasPressedThisFrame == true)
                EnterFromSelection();
        }

        public bool EnterFromSelection()
        {
            if (_globe.Topology == null) return false;
            int first = _globe.SelectedSubtileIndex;
            int second = _globe.AttackTargetSubtileIndex;
            return first >= 0 && second >= 0 && EnterBattle(first, second);
        }

        public bool EnterBattle(int first, int second)
        {
            if (IsActive || battlefieldMaterial == null || _globe.Topology == null) return false;
            _orbit = FindFirstObjectByType<OrbitCamera>(); if (_orbit == null) return false;
            _worldCamera = _orbit.GetComponent<Camera>();
            var source = _globe.Topology;
            if (first < 0 || first >= source.Subtiles.Count || second < 0 || Array.IndexOf(source.Subtiles[first].Neighbors, second) < 0) return false;
            int side = Array.IndexOf(source.Subtiles[first].Neighbors, second);
            var edge = source.Edges[source.Subtiles[first].Edges[side]];
            var start = _globe.transform.TransformPoint(source.Vertices[edge.Start]);
            var end = _globe.transform.TransformPoint(source.Vertices[edge.End]);
            var axis = end - start;
            axis /= Mathf.Max(axis.magnitude, 1e-10f);
            var midpoint = (start + end) * .5f;
            // Probe the same projected line at a resolvable length, even when
            // the actual shared edge is much smaller than one screen pixel.
            float probe = Mathf.Max((end - start).magnitude, .01f);
            var a = _worldCamera.WorldToScreenPoint(midpoint - axis * probe);
            var b = _worldCamera.WorldToScreenPoint(midpoint + axis * probe);
            float angle = Mathf.Atan2(b.y - a.y, b.x - a.x);
            float radius = BattleSettingsStore.TryLoad(out var settings) ? settings.hexWorldRadius : 0;
            var field = Battlefield.Build(source, first, second, angle, targetCoreHexes, radius);
            _surface = BattlefieldMeshes.Surface(field); _boundaries = BattlefieldMeshes.Boundaries(field, source);
            Field = field; _source = source; _orbit.CancelDrag(); SelectedUnit = 0;
            _cameraEnabled = _worldCamera.enabled; _rendererEnabled = _globe.GetComponent<MeshRenderer>().enabled;
            _root = new GameObject("Battle preview") { hideFlags = HideFlags.DontSave };
            _lineMaterial = new Material(battlefieldMaterial) { hideFlags = HideFlags.DontSave, renderQueue = battlefieldMaterial.renderQueue + 1 };
            _unitMaterial = new Material(battlefieldMaterial) { hideFlags = HideFlags.DontSave, renderQueue = battlefieldMaterial.renderQueue + 2 };
            _surfaceRenderer = View("Hexes", _surface, battlefieldMaterial).GetComponent<MeshRenderer>();
            View("Subtile outlines", _boundaries, _lineMaterial); _unitFilter = View("Test units", null, _unitMaterial);
            RefreshUnits();
            var cameraObject = new GameObject("Battle camera"); cameraObject.transform.SetParent(_root.transform, false); cameraObject.tag = "MainCamera";
            _battleCamera = cameraObject.AddComponent<Camera>(); _battleCamera.orthographic = true;
            _battleCamera.nearClipPlane = .1f; _battleCamera.farClipPlane = 300f; _battleCamera.allowHDR = false;
            _battleCamera.clearFlags = CameraClearFlags.SolidColor; _battleCamera.backgroundColor = new Color(.025f, .037f, .05f);
            _battleCamera.GetUniversalAdditionalCameraData().renderPostProcessing = false;
            _battleCamera.transform.rotation = Quaternion.Euler(0, 0, -angle * Mathf.Rad2Deg);
            float cosine = Mathf.Cos(angle), sine = Mathf.Sin(angle);
            Vector2 min = new(float.MaxValue, float.MaxValue), max = new(float.MinValue, float.MinValue);
            foreach (var hex in field.Hexes) for (int i = 0; i < 6; i++)
            {
                var p = HexCoord.CornerPosition(hex.Coord.CornerKey(i));
                var screen = new Vector2(p.x * cosine - p.y * sine, p.x * sine + p.y * cosine);
                min = Vector2.Min(min, screen); max = Vector2.Max(max, screen);
            }
            var center = (min + max) * .5f;
            _battleCamera.transform.position = new Vector3(center.x * cosine + center.y * sine, -center.x * sine + center.y * cosine, -100);
            _fitSize = Mathf.Max((max.y - min.y) * .5f, (max.x - min.x) * .5f / Mathf.Max(.1f, _worldCamera.aspect)) * 1.12f;
            _battleCamera.orthographicSize = _fitSize;
            _worldCamera.enabled = false; _globe.GetComponent<MeshRenderer>().enabled = false;
            _mouseButton = -1; _path.Clear(); _movingUnit = -1; _active = this;
            return true;
        }

        private MeshFilter View(string name, Mesh mesh, Material material)
        {
            var go = new GameObject(name); go.transform.SetParent(_root.transform, false);
            var filter = go.AddComponent<MeshFilter>(); filter.sharedMesh = mesh; go.AddComponent<MeshRenderer>().sharedMaterial = material; return filter;
        }

        private void RefreshUnits()
        {
            if (_units != null) Destroy(_units);
            _units = BattlefieldMeshes.Units(Field, SelectedUnit); _unitFilter.sharedMesh = _units;
        }

        public void ExitBattle()
        {
            if (_root == null) return;
            _root.SetActive(false); Destroy(_root); _root = null;
            if (_surface != null) Destroy(_surface); if (_boundaries != null) Destroy(_boundaries); if (_units != null) Destroy(_units);
            if (_lineMaterial != null) Destroy(_lineMaterial); if (_unitMaterial != null) Destroy(_unitMaterial);
            if (_worldCamera != null) _worldCamera.enabled = _cameraEnabled;
            if (_globe != null) _globe.GetComponent<MeshRenderer>().enabled = _rendererEnabled;
            if (_orbit != null) _orbit.CancelDrag();
            _battleCamera = null; Field = null; _source = null; _path.Clear(); _movingUnit = -1; _mouseButton = -1;
            _lastExitFrame = Time.frameCount;
        }

        private Vector2 GroundPoint(Vector2 screen) => _battleCamera.ScreenToWorldPoint(new Vector3(screen.x, screen.y, 100));

        public bool Pick(Vector2 ground)
        {
            if (!IsActive || !Field.TryGetHex(ground, out int index)) return false;
            int unit = Field.UnitAt(index);
            if (unit >= 0) { SelectedUnit = unit; _path.Clear(); _movingUnit = -1; RefreshUnits(); }
            else if (SelectedUnit >= 0 && !Field.Units[SelectedUnit].Escaped)
            {
                _path.Clear(); foreach (int step in Field.FindPath(SelectedUnit, index)) _path.Enqueue(step);
                _movingUnit = SelectedUnit; _nextStep = Time.unscaledTime;
            }
            var properties = new MaterialPropertyBlock(); properties.SetFloat("_SelectedHex", index); _surfaceRenderer.SetPropertyBlock(properties);
            return true;
        }

        private void UpdateBattleInput(Keyboard keyboard, Mouse mouse)
        {
            if (mouse != null)
            {
                var position = mouse.position.ReadValue();
                if (_mouseButton < 0 && (mouse.leftButton.wasPressedThisFrame || mouse.rightButton.wasPressedThisFrame))
                { _mouseButton = mouse.leftButton.wasPressedThisFrame ? 0 : 1; _press = _previous = position; _dragged = false; }
                if (_mouseButton >= 0)
                {
                    if ((position - _press).sqrMagnitude > 16) _dragged = true;
                    bool held = _mouseButton == 0 ? mouse.leftButton.isPressed : mouse.rightButton.isPressed;
                    if (held && _dragged)
                    {
                        var delta = (position - _previous) * (_battleCamera.orthographicSize * 2 / Mathf.Max(1, _battleCamera.pixelHeight));
                        _battleCamera.transform.position -= _battleCamera.transform.TransformVector(new Vector3(delta.x, delta.y, 0));
                    }
                    if (!held) { if (_mouseButton == 0 && !_dragged) Pick(GroundPoint(position)); _mouseButton = -1; }
                    _previous = position;
                }
                float wheel = OrbitCamera.WheelNotches(mouse.scroll.ReadValue().y);
                if (wheel != 0)
                {
                    var before = GroundPoint(position);
                    _battleCamera.orthographicSize = Mathf.Clamp(_battleCamera.orthographicSize * Mathf.Exp(-wheel * .18f), _fitSize * .18f, _fitSize * 4);
                    var after = GroundPoint(position); var delta = before - after;
                    _battleCamera.transform.position += new Vector3(delta.x, delta.y, 0);
                }
            }
            if (keyboard != null)
            {
                var pan = new Vector2((keyboard.dKey.isPressed || keyboard.rightArrowKey.isPressed ? 1 : 0) - (keyboard.aKey.isPressed || keyboard.leftArrowKey.isPressed ? 1 : 0),
                    (keyboard.wKey.isPressed || keyboard.upArrowKey.isPressed ? 1 : 0) - (keyboard.sKey.isPressed || keyboard.downArrowKey.isPressed ? 1 : 0));
                pan = Vector2.ClampMagnitude(pan, 1) * (_battleCamera.orthographicSize * Time.unscaledDeltaTime);
                _battleCamera.transform.position += _battleCamera.transform.TransformVector(new Vector3(pan.x, pan.y, 0));
            }
        }
    }
}
