using System;
using System.Collections.Generic;
using System.Globalization;
using UnityEngine;
using UnityEngine.UIElements;

namespace SphericalCivilization
{
    [RequireComponent(typeof(UIDocument))]
    public sealed class CameraControlsPanel : MonoBehaviour
    {
        public OrbitCamera orbitCamera;
        public static bool IsMenuOpen => _active != null && _active._isOpen;
        public static bool HasKeyboardFocus => IsMenuOpen;

        private static CameraControlsPanel _active;
        private VisualElement _overlay, _mainMenu, _settingsPage, _hint;
        private Button _continueButton, _settingsButton, _backButton, _saveButton, _copyButton;
        private GlobePreview _globe;
        private VisualElement _worldPage;
        private Button _worldButton, _worldBackButton, _applyWorldButton, _saveWorldButton;
        private SliderInt _worldCount, _pentagonCount;
        private Label _pentagonValue;
        private Button _labButton;
        private Label _worldValue, _worldSummary, _worldStatus;
        private Label _status;
        private bool _isOpen, _dirty;
        private readonly List<SettingControl> _controls = new();

        private sealed class SettingControl
        {
            public Slider slider;
            public Label label;
            public Func<float> read;
            public bool time;
            public EventCallback<ChangeEvent<float>> changed;
        }

        private void OnEnable()
        {
            if (orbitCamera == null) orbitCamera = FindFirstObjectByType<OrbitCamera>();
            var root = GetComponent<UIDocument>().rootVisualElement;
            root.AddToClassList("camera-document");
            root.style.unityFontDefinition = FontDefinition.FromFont(Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf"));
            root.pickingMode = PickingMode.Ignore;
            _overlay = root.Q("menuOverlay");
            _mainMenu = root.Q("mainMenu");
            _settingsPage = root.Q("settingsPage");
            _hint = root.Q("menuHint");
            _status = root.Q<Label>("copyStatus");
            _continueButton = root.Q<Button>("continueButton");
            _settingsButton = root.Q<Button>("settingsButton");
            _backButton = root.Q<Button>("backButton");
            _saveButton = root.Q<Button>("saveButton");
            _copyButton = root.Q<Button>("copyButton");
            _globe = FindFirstObjectByType<GlobePreview>();
            _worldPage = root.Q("worldPage");
            _worldButton = root.Q<Button>("worldButton");
            _worldBackButton = root.Q<Button>("worldBackButton");
            _applyWorldButton = root.Q<Button>("applyWorldButton");
            _saveWorldButton = root.Q<Button>("saveWorldButton");
            _worldCount = root.Q<SliderInt>("subtileCountSlider");
            _pentagonCount = root.Q<SliderInt>("pentagonCountSlider");
            _pentagonValue = root.Q<Label>("pentagonCountValue");
            _labButton = root.Q<Button>("labButton");
            _worldValue = root.Q<Label>("subtileCountValue");
            _worldSummary = root.Q<Label>("worldCountSummary");
            _worldStatus = root.Q<Label>("worldStatus");
            if (_overlay == null || orbitCamera == null) return;
            _active = this;
            Bind(root, "backgroundSpeed", () => orbitCamera.BackgroundRotationSpeed, value => orbitCamera.BackgroundRotationSpeed = value);
            Bind(root, "keyboardSpeed", () => orbitCamera.KeyboardRotationSpeed, value => orbitCamera.KeyboardRotationSpeed = value);
            Bind(root, "turnSpeed", () => orbitCamera.TurnRotationSpeed, value => orbitCamera.TurnRotationSpeed = value);
            Bind(root, "scrollSpeed", () => orbitCamera.ScrollSpeed, value => orbitCamera.ScrollSpeed = value);
            Bind(root, "inertia", () => orbitCamera.RotationInertiaHalfLife, value => orbitCamera.RotationInertiaHalfLife = value, true);
            Bind(root, "scrollInertia", () => orbitCamera.ScrollInertiaHalfLife, value => orbitCamera.ScrollInertiaHalfLife = value, true);
            _continueButton.clicked += CloseMenu;
            _settingsButton.clicked += OpenSettings;
            _backButton.clicked += OpenMainMenu;
            _saveButton.clicked += SaveSettings;
            _copyButton.clicked += CopySettings;
            _worldButton.clicked += OpenWorldSettings;
            _worldBackButton.clicked += OpenMainMenu;
            _applyWorldButton.clicked += ApplyWorldSettings;
            _saveWorldButton.clicked += SaveWorldSettings;
            _worldCount.RegisterValueChangedCallback(WorldCountChanged);
            _pentagonCount.RegisterValueChangedCallback(WorldCountChanged);
            _labButton.clicked += OpenLab;
            RefreshControls();
            CloseMenu();
        }

        private void OnDisable()
        {
            CloseMenu();
            if (_active == this) _active = null;
            foreach (var control in _controls) control.slider.UnregisterValueChangedCallback(control.changed);
            _controls.Clear();
            if (_continueButton != null) _continueButton.clicked -= CloseMenu;
            if (_settingsButton != null) _settingsButton.clicked -= OpenSettings;
            if (_backButton != null) _backButton.clicked -= OpenMainMenu;
            if (_saveButton != null) _saveButton.clicked -= SaveSettings;
            if (_copyButton != null) _copyButton.clicked -= CopySettings;
            if (_worldButton != null) _worldButton.clicked -= OpenWorldSettings;
            if (_worldBackButton != null) _worldBackButton.clicked -= OpenMainMenu;
            if (_applyWorldButton != null) _applyWorldButton.clicked -= ApplyWorldSettings;
            if (_saveWorldButton != null) _saveWorldButton.clicked -= SaveWorldSettings;
            _worldCount?.UnregisterValueChangedCallback(WorldCountChanged);
            _pentagonCount?.UnregisterValueChangedCallback(WorldCountChanged);
            if (_labButton != null) _labButton.clicked -= OpenLab;
        }

        private void Bind(VisualElement root, string name, Func<float> read, Action<float> write, bool time = false)
        {
            var control = new SettingControl
            {
                slider = root.Q<Slider>(name + "Slider"), label = root.Q<Label>(name + "Value"), read = read, time = time
            };
            control.changed = change =>
            {
                write(Mathf.Round(change.newValue * 100f) / 100f);
                _dirty = true;
                RefreshControls();
            };
            control.slider.RegisterValueChangedCallback(control.changed);
            _controls.Add(control);
        }

        private void RefreshControls()
        {
            foreach (var control in _controls)
            {
                float value = control.read();
                control.slider.SetValueWithoutNotify(value);
                control.label.text = control.time && value == 0f ? "Выкл." :
                    value.ToString("F2", CultureInfo.InvariantCulture) + (control.time ? " с" : "×");
            }
            _status.text = _dirty ? "Изменения не сохранены" : "";
        }

        public static bool ContainsPointer(Vector2 screenPosition) => IsMenuOpen;

        public static void ReleaseKeyboardFocus()
        {
            _active?._overlay?.panel?.focusController.focusedElement?.Blur();
            var events = UnityEngine.EventSystems.EventSystem.current;
            if (events != null) events.SetSelectedGameObject(null);
        }

        public static void FocusControls() => _active?.OpenSettings();

        public static void HandleEscape()
        {
            if (_active == null) return;
            if (!IsMenuOpen) _active.OpenMainMenu();
            else if (_active._settingsPage.style.display == DisplayStyle.Flex || _active._worldPage.style.display == DisplayStyle.Flex) _active.OpenMainMenu();
            else _active.CloseMenu();
        }

        private void ShowMenu()
        {
            orbitCamera.CancelDrag();
            _isOpen = true;
            _overlay.style.display = DisplayStyle.Flex;
            _hint.style.display = DisplayStyle.None;
            ReleaseKeyboardFocus();
        }

        public void OpenMainMenu()
        {
            ShowMenu();
            _mainMenu.style.display = DisplayStyle.Flex;
            _settingsPage.style.display = DisplayStyle.None;
            _worldPage.style.display = DisplayStyle.None;
            _continueButton.Focus();
        }

        public void OpenSettings()
        {
            ShowMenu();
            RefreshControls();
            _mainMenu.style.display = DisplayStyle.None;
            _settingsPage.style.display = DisplayStyle.Flex;
            _worldPage.style.display = DisplayStyle.None;
            _controls[0].slider.Focus();
        }

        public void CloseMenu()
        {
            ReleaseKeyboardFocus();
            _isOpen = false;
            if (_overlay != null) _overlay.style.display = DisplayStyle.None;
            if (_hint != null) _hint.style.display = DisplayStyle.Flex;
            if (orbitCamera != null) orbitCamera.CancelDrag();
        }

        public void SaveSettings()
        {
            try
            {
                CameraSettingsStore.Save(CameraSettingsStore.SettingsPath, orbitCamera.GetSettings());
                _dirty = false;
                _status.text = "Сохранено — эти значения загрузятся при следующем запуске";
            }
            catch (Exception exception) when (exception is System.IO.IOException || exception is UnauthorizedAccessException)
            {
                _status.text = "Не удалось сохранить настройки";
                Debug.LogWarning("Не удалось сохранить настройки камеры: " + exception.Message);
            }
        }

        public void CopySettings()
        {
            GUIUtility.systemCopyBuffer = orbitCamera.GetSettingsJson();
            _status.text = "Скопировано — вставь значения в чат";
        }

        public void OpenWorldSettings()
        {
            ShowMenu();
            _mainMenu.style.display = DisplayStyle.None;
            _settingsPage.style.display = DisplayStyle.None;
            _worldPage.style.display = DisplayStyle.Flex;
            _worldCount.SetValueWithoutNotify(_globe.subtilesPerTile);
            _pentagonCount.SetValueWithoutNotify(_globe.PentagonSubtileCount);
            _worldStatus.text = "";
            RefreshWorldControls();
            _worldCount.Focus();
        }

        private void WorldCountChanged(ChangeEvent<int> change)
        {
            RefreshWorldControls();
            _worldStatus.text = !WorldCountChanged() ? "" : "Нажми «Применить», чтобы перестроить карту";
        }

        private bool WorldCountChanged() => _worldCount.value != _globe.HexagonSubtileCount || _pentagonCount.value != _globe.PentagonSubtileCount;
        private void OpenLab() => UnityEngine.SceneManagement.SceneManager.LoadScene("SubdivisionLab");

        private void RefreshWorldControls()
        {
            _worldValue.text = _worldCount.value.ToString(CultureInfo.InvariantCulture);
            _pentagonValue.text = _pentagonCount.value.ToString(CultureInfo.InvariantCulture);
            int total = 0;
            foreach (var tile in _globe.Topology.Tiles) total += tile.Corners.Length == 5 ? _pentagonCount.value : _worldCount.value;
            _worldSummary.text = $"Сейчас: {_globe.SubtileCount:N0} субтайлов во всём мире. После применения: {total:N0}.";
            _applyWorldButton.SetEnabled(WorldCountChanged());
        }

        private bool ApplyWorld()
        {
            try
            {
                if (WorldCountChanged()) _globe.ApplySubdivision(_worldCount.value, _pentagonCount.value);
                RefreshWorldControls();
                _worldStatus.text = "Карта перестроена. Значение ещё не сохранено для следующих запусков.";
                return true;
            }
            catch (Exception exception)
            {
                _worldStatus.text = "Не удалось перестроить карту";
                Debug.LogWarning("Не удалось перестроить карту: " + exception.Message);
                return false;
            }
        }

        private void ApplyWorldSettings() => ApplyWorld();

        private void SaveWorldSettings()
        {
            if (!ApplyWorld()) return;
            try
            {
                WorldSettingsStore.Save(WorldSettingsStore.SettingsPath,
                    _globe.GetWorldSettings());
                _worldStatus.text = "Сохранено — карта будет использовать это количество при следующих запусках";
            }
            catch (Exception exception) when (exception is System.IO.IOException || exception is UnauthorizedAccessException)
            {
                _worldStatus.text = "Карта применена, но сохранить настройки не удалось";
                Debug.LogWarning("Не удалось сохранить настройки карты: " + exception.Message);
            }
        }
    }
}
