using UnityEngine;
using UnityEngine.InputSystem;

namespace SphericalCivilization
{
    public enum GlobeDragMode { None, Surface, Background }

    [System.Serializable]
    public sealed class CameraSettings
    {
        public float backgroundRotationSpeed;
        public float keyboardRotationSpeed;
        public float turnRotationSpeed;
        public float scrollSpeed;
        public float rotationInertiaHalfLife;
        public float scrollInertiaHalfLife;
    }

    [ExecuteAlways]
    [RequireComponent(typeof(Camera))]
    public sealed class OrbitCamera : MonoBehaviour
    {
        public const float MinSpeed = 0.1f;
        public const float MaxSpeed = 5f;
        public const float GlobeRadius = 1f;
        public const float MinDistance = 1.1f;
        public const float MaxDistance = 7f;
        public const float MaxGroundTilt = 50f;
        private const float KeyboardReferenceDistance = 3.3f;
        public const float MaxInertiaHalfLife = 1f;

        public float distance = 3.3f;
        public float yaw = 30f;
        public float pitch = 18f;
        [SerializeField, Range(MinSpeed, MaxSpeed)] private float backgroundRotationSpeed = 1f;
        [UnityEngine.Serialization.FormerlySerializedAs("wasdRotationSpeed")]
        [SerializeField, Range(MinSpeed, MaxSpeed)] private float keyboardRotationSpeed = 1f;
        [SerializeField, Range(MinSpeed, MaxSpeed)] private float turnRotationSpeed = 2.64f;
        [SerializeField, Range(MinSpeed, MaxSpeed)] private float scrollSpeed = 1f;
        [SerializeField, Range(0f, MaxInertiaHalfLife)] private float rotationInertiaHalfLife = 0.11f;
        [SerializeField, Range(0f, MaxInertiaHalfLife)] private float scrollInertiaHalfLife = 0.11f;
        [SerializeField] private Quaternion orbitRotation;
        [SerializeField] private bool orientationInitialized;

        public float BackgroundRotationSpeed
        {
            get => backgroundRotationSpeed;
            set => backgroundRotationSpeed = Mathf.Clamp(value, MinSpeed, MaxSpeed);
        }
        public float KeyboardRotationSpeed
        {
            get => keyboardRotationSpeed;
            set => keyboardRotationSpeed = Mathf.Clamp(value, MinSpeed, MaxSpeed);
        }
        public float TurnRotationSpeed
        {
            get => turnRotationSpeed;
            set => turnRotationSpeed = Mathf.Clamp(value, MinSpeed, MaxSpeed);
        }
        public float ScrollSpeed
        {
            get => scrollSpeed;
            set => scrollSpeed = Mathf.Clamp(value, MinSpeed, MaxSpeed);
        }
        public float RotationInertiaHalfLife
        {
            get => rotationInertiaHalfLife;
            set
            {
                rotationInertiaHalfLife = Mathf.Clamp(value, 0f, MaxInertiaHalfLife);
                if (rotationInertiaHalfLife == 0f) StopInertia();
            }
        }
        public float InertiaAngularSpeed => _angularVelocity.magnitude;
        public float ScrollInertiaHalfLife
        {
            get => scrollInertiaHalfLife;
            set
            {
                scrollInertiaHalfLife = Mathf.Clamp(value, 0f, MaxInertiaHalfLife);
                if (scrollInertiaHalfLife == 0f) StopScrollInertia();
            }
        }
        public float ScrollInertiaVelocity => ScrollInertiaHalfLife > 0f ?
            Mathf.Log(2f) / ScrollInertiaHalfLife * (_targetDistance - distance) : 0f;
        public GlobeDragMode DragMode { get; private set; }
        public Quaternion Orientation => orbitRotation;
        public Vector3 GrabbedPoint => _grabbedPoint;
        public float TargetDistance => _targetDistance;
        public float HeightAboveSurface => distance - GlobeRadius;
        public float KeyboardDegreesPerSecond => 60f * KeyboardRotationSpeed * distance / KeyboardReferenceDistance;
        public float TurnDegreesPerSecond => 60f * TurnRotationSpeed * distance / KeyboardReferenceDistance;
        public float GroundTiltDegrees => TiltAtDistance(distance);
        public Vector3 FocusPoint => Center + orbitRotation * (Vector3.back * GlobeRadius);

        private Camera _camera;
        private GlobePreview _globe;
        private Vector2 _pressPosition;
        private Vector2 _previousPosition;
        private Vector3 _grabbedPoint;
        private float _grabRadius;
        private float _targetDistance;
        private bool _moved;
        private bool _selectOnClick;
        private bool _pointerStartedOnUI;
        private int _mouseButton = -1;
        private Vector3 _angularVelocity;
        private Vector3 Center => _globe != null ? _globe.transform.position : Vector3.zero;

        private void OnEnable()
        {
            _camera = GetComponent<Camera>();
            _globe = FindFirstObjectByType<GlobePreview>();
            if (Application.isPlaying)
            {
                Application.targetFrameRate = 60;
                if (CameraSettingsStore.TryLoad(CameraSettingsStore.SettingsPath, GetSettings(), out var saved, out var error))
                    ApplySettings(saved);
                else if (error != null) Debug.LogWarning("Не удалось загрузить настройки камеры: " + error);
            }
            if (!orientationInitialized) ApplyView();
            else SetView(orbitRotation, distance);
        }

        private void OnDisable() => CancelDrag();
        private void OnApplicationFocus(bool focused)
        {
            if (!focused) CancelDrag();
        }

        private void Update()
        {
            if (!Application.isPlaying) return;
            if (Keyboard.current?.escapeKey.wasPressedThisFrame == true)
            {
                CameraControlsPanel.HandleEscape();
                return;
            }
            if (CameraControlsPanel.IsMenuOpen)
            {
                CancelDrag();
                return;
            }
            var mouse = Mouse.current;
            if (mouse != null) UpdatePointer(mouse);
            bool keyboardDriven = false;
            if (DragMode == GlobeDragMode.None && !_pointerStartedOnUI && !CameraControlsPanel.HasKeyboardFocus)
                keyboardDriven = UpdateKeyboard(Keyboard.current, Time.unscaledDeltaTime);
            if (_pointerStartedOnUI || CameraControlsPanel.HasKeyboardFocus) StopInertia();
            else if (!keyboardDriven && DragMode == GlobeDragMode.None) AdvanceInertia(Time.unscaledDeltaTime);

            if (AdvanceZoom(Time.unscaledDeltaTime) && mouse != null &&
                _mouseButton >= 0 && DragMode == GlobeDragMode.Surface)
                FollowSurface(mouse.position.ReadValue());
        }

        private void UpdatePointer(Mouse mouse)
        {
            var position = mouse.position.ReadValue();
            if (!mouse.leftButton.isPressed && !mouse.rightButton.isPressed)
                _pointerStartedOnUI = false;

            if (_mouseButton < 0 && (mouse.leftButton.wasPressedThisFrame || mouse.rightButton.wasPressedThisFrame))
            {
                _pointerStartedOnUI = CameraControlsPanel.ContainsPointer(position);
                if (_pointerStartedOnUI)
                {
                    StopInertia();
                    StopScrollInertia();
                }
                if (!_pointerStartedOnUI && BeginDrag(position, mouse.leftButton.wasPressedThisFrame))
                    _mouseButton = mouse.leftButton.wasPressedThisFrame ? 0 : 1;
            }
            if (_mouseButton >= 0)
            {
                bool pressed = _mouseButton == 0 ? mouse.leftButton.isPressed : mouse.rightButton.isPressed;
                if (pressed) DragTo(position);
                else EndDrag(position);
            }
            float scroll = mouse.scroll.ReadValue().y;
            if (scroll != 0f && !_pointerStartedOnUI) ApplyScroll(scroll, position);
        }

        private bool UpdateKeyboard(Keyboard keyboard, float seconds)
        {
            if (keyboard == null) return false;
            var wasd = new Vector2(
                (keyboard.dKey.isPressed ? 1f : 0f) - (keyboard.aKey.isPressed ? 1f : 0f),
                (keyboard.wKey.isPressed ? 1f : 0f) - (keyboard.sKey.isPressed ? 1f : 0f));
            var arrows = new Vector2(
                (keyboard.rightArrowKey.isPressed ? 1f : 0f) - (keyboard.leftArrowKey.isPressed ? 1f : 0f),
                (keyboard.upArrowKey.isPressed ? 1f : 0f) - (keyboard.downArrowKey.isPressed ? 1f : 0f));
            float turn = (keyboard.eKey.isPressed ? 1f : 0f) - (keyboard.qKey.isPressed ? 1f : 0f);
            return RotateKeyboard(wasd, arrows, seconds, turn);
        }

        public bool RotateKeyboard(Vector2 wasd, Vector2 arrows, float seconds, float turn = 0f)
        {
            if (seconds <= 0f) return false;
            var movement = Vector2.ClampMagnitude(wasd + arrows, 1f);
            var input = Vector3.ClampMagnitude(new Vector3(movement.y, -movement.x, Mathf.Clamp(turn, -1f, 1f)), 1f);
            if (input.sqrMagnitude == 0f) return false;
            var velocity = Vector3.Scale(input, new Vector3(KeyboardDegreesPerSecond, KeyboardDegreesPerSecond, TurnDegreesPerSecond));
            _angularVelocity = orbitRotation * velocity;
            orbitRotation *= Quaternion.AngleAxis(velocity.magnitude * seconds, velocity.normalized);
            PlaceCamera();
            return true;
        }

        public bool BeginDrag(Vector2 position, bool selectOnClick = true)
        {
            if (CameraControlsPanel.ContainsPointer(position))
            {
                StopInertia();
                StopScrollInertia();
                return false;
            }
            CancelDrag();
            CameraControlsPanel.ReleaseKeyboardFocus();
            if (_globe == null) _globe = FindFirstObjectByType<GlobePreview>();
            _pressPosition = _previousPosition = position;
            _moved = false;
            _selectOnClick = selectOnClick;
            DragMode = GlobeDragMode.Background;
            if (_globe != null && _globe.GetComponent<MeshCollider>().Raycast(_camera.ScreenPointToRay(position), out var hit, 100f))
            {
                DragMode = GlobeDragMode.Surface;
                _grabbedPoint = hit.point;
                _grabRadius = Vector3.Distance(hit.point, Center);
            }
            return true;
        }

        public void DragTo(Vector2 position, float seconds = -1f)
        {
            if (DragMode == GlobeDragMode.None) return;
            if (!_moved && (position - _pressPosition).sqrMagnitude < 16f) return;
            _moved = true;
            var before = orbitRotation;
            if (DragMode == GlobeDragMode.Surface) FollowSurface(position);
            else RotateFree((position - _previousPosition) * (0.2f * BackgroundRotationSpeed));
            float elapsed = seconds < 0f ? Time.unscaledDeltaTime : seconds;
            if (position == _previousPosition)
                _angularVelocity *= Mathf.Exp(-Mathf.Max(0f, elapsed) / 0.035f);
            else RecordMouseVelocity(before, elapsed);
            _previousPosition = position;
        }

        public void EndDrag(Vector2 position)
        {
            if (DragMode == GlobeDragMode.None) return;
            if (position != _previousPosition) DragTo(position);
            if (!_moved && _selectOnClick && _globe != null && !CameraControlsPanel.ContainsPointer(position))
                _globe.TrySelectRay(_camera.ScreenPointToRay(position));
            if (!_moved) StopInertia();
            ResetGesture();
        }

        public void CancelDrag()
        {
            ResetGesture();
            StopInertia();
            StopScrollInertia();
        }

        private void ResetGesture()
        {
            DragMode = GlobeDragMode.None;
            _mouseButton = -1;
            _pointerStartedOnUI = false;
        }

        public void StopInertia() => _angularVelocity = Vector3.zero;
        public void StopScrollInertia() => _targetDistance = distance;

        public bool AdvanceInertia(float seconds)
        {
            if (DragMode != GlobeDragMode.None || seconds <= 0f) return false;
            if (RotationInertiaHalfLife <= 0f || _angularVelocity.sqrMagnitude < 0.0004f)
            {
                StopInertia();
                return false;
            }
            float decayRate = Mathf.Log(2f) / RotationInertiaHalfLife;
            float decay = Mathf.Exp(-decayRate * seconds);
            var displacement = _angularVelocity * ((1f - decay) / decayRate);
            orbitRotation = Quaternion.AngleAxis(displacement.magnitude, displacement.normalized) * orbitRotation;
            _angularVelocity *= decay;
            PlaceCamera();
            return true;
        }

        private void RecordMouseVelocity(Quaternion before, float seconds)
        {
            if (seconds <= 0f) return;
            var delta = orbitRotation * Quaternion.Inverse(before);
            delta.ToAngleAxis(out float angle, out var axis);
            if (angle > 180f) angle -= 360f;
            var velocity = Mathf.Abs(angle) < 0.001f ? Vector3.zero : axis * (angle / seconds);
            velocity = Vector3.ClampMagnitude(velocity, 360f);
            _angularVelocity = Vector3.Lerp(_angularVelocity, velocity, 1f - Mathf.Exp(-seconds / 0.035f));
        }

        public static float WheelNotches(float delta)
        {
            if (InputSystem.settings.scrollDeltaBehavior == InputSettings.ScrollDeltaBehavior.UniformAcrossAllPlatforms)
                return delta;
            bool windows = Application.platform == RuntimePlatform.WindowsEditor ||
                           Application.platform == RuntimePlatform.WindowsPlayer;
            return delta / (windows ? 120f : 1f);
        }

        public bool ApplyScroll(float delta, Vector2 position)
        {
            if (CameraControlsPanel.ContainsPointer(position))
            {
                StopScrollInertia();
                return false;
            }
            float height = _targetDistance - GlobeRadius;
            float exponent = Mathf.Clamp(-WheelNotches(delta) * 0.22f * ScrollSpeed, -10f, 10f);
            _targetDistance = GlobeRadius + Mathf.Clamp(height * Mathf.Exp(exponent),
                MinDistance - GlobeRadius, MaxDistance - GlobeRadius);
            if (ScrollInertiaHalfLife == 0f)
            {
                distance = _targetDistance;
                PlaceCamera();
                if (DragMode == GlobeDragMode.Surface) FollowSurface(position);
            }
            return true;
        }

        public bool AdvanceZoom(float seconds)
        {
            if (seconds <= 0f || distance == _targetDistance) return false;
            float decay = ScrollInertiaHalfLife > 0f ? Mathf.Exp(-Mathf.Log(2f) * seconds / ScrollInertiaHalfLife) : 0f;
            distance = _targetDistance + (distance - _targetDistance) * decay;
            if (Mathf.Abs(distance - _targetDistance) < 0.00001f)
            {
                distance = _targetDistance;
            }
            PlaceCamera();
            return true;
        }

        public void ApplyView() => SetView(Quaternion.Euler(pitch, yaw, 0f), distance);

        public void SetView(Quaternion orientation, float viewDistance)
        {
            StopInertia();
            orbitRotation = orientation.normalized;
            orientationInitialized = true;
            distance = _targetDistance = Mathf.Clamp(viewDistance, MinDistance, MaxDistance);
            PlaceCamera();
        }

        public CameraSettings GetSettings() => new CameraSettings
        {
            backgroundRotationSpeed = BackgroundRotationSpeed,
            keyboardRotationSpeed = KeyboardRotationSpeed,
            turnRotationSpeed = TurnRotationSpeed,
            scrollSpeed = ScrollSpeed,
            rotationInertiaHalfLife = RotationInertiaHalfLife,
            scrollInertiaHalfLife = ScrollInertiaHalfLife
        };

        public void ApplySettings(CameraSettings settings)
        {
            if (settings == null) return;
            BackgroundRotationSpeed = SafeSetting(settings.backgroundRotationSpeed, BackgroundRotationSpeed, MinSpeed, MaxSpeed);
            KeyboardRotationSpeed = SafeSetting(settings.keyboardRotationSpeed, KeyboardRotationSpeed, MinSpeed, MaxSpeed);
            TurnRotationSpeed = SafeSetting(settings.turnRotationSpeed, TurnRotationSpeed, MinSpeed, MaxSpeed);
            ScrollSpeed = SafeSetting(settings.scrollSpeed, ScrollSpeed, MinSpeed, MaxSpeed);
            RotationInertiaHalfLife = SafeSetting(settings.rotationInertiaHalfLife, RotationInertiaHalfLife, 0f, MaxInertiaHalfLife);
            ScrollInertiaHalfLife = SafeSetting(settings.scrollInertiaHalfLife, ScrollInertiaHalfLife, 0f, MaxInertiaHalfLife);
        }

        private static float SafeSetting(float value, float fallback, float minimum, float maximum) =>
            float.IsNaN(value) || float.IsInfinity(value) ? fallback : Mathf.Clamp(value, minimum, maximum);

        public string GetSettingsJson() => System.FormattableString.Invariant($@"{{
    ""backgroundRotationSpeed"": {BackgroundRotationSpeed:F2},
    ""keyboardRotationSpeed"": {KeyboardRotationSpeed:F2},
    ""turnRotationSpeed"": {TurnRotationSpeed:F2},
    ""scrollSpeed"": {ScrollSpeed:F2},
    ""rotationInertiaHalfLife"": {RotationInertiaHalfLife:F2},
    ""scrollInertiaHalfLife"": {ScrollInertiaHalfLife:F2}
}}");

        private void RotateFree(Vector2 degrees)
        {
            if (degrees.sqrMagnitude == 0f) return;
            var axis = new Vector3(-degrees.y, degrees.x, 0f);
            orbitRotation = orbitRotation * Quaternion.AngleAxis(axis.magnitude, axis.normalized);
            PlaceCamera();
        }

        private void FollowSurface(Vector2 position)
        {
            var ray = _camera.ScreenPointToRay(position);
            var origin = ray.origin - Center;
            float b = Vector3.Dot(origin, ray.direction);
            float discriminant = b * b - (origin.sqrMagnitude - _grabRadius * _grabRadius);
            float near = discriminant >= 0f ? -b - Mathf.Sqrt(discriminant) : -1f;
            Vector3 underPointer;
            if (near >= 0f)
                underPointer = (origin + ray.direction * near).normalized;
            else
            {
                var outward = (transform.position - Center).normalized;
                var radial = Vector3.ProjectOnPlane(ray.direction, outward).normalized;
                float horizon = Mathf.Clamp01(_grabRadius / distance);
                underPointer = radial * Mathf.Sqrt(1f - horizon * horizon) + outward * horizon;
            }
            orbitRotation = Quaternion.FromToRotation(underPointer, (_grabbedPoint - Center).normalized) * orbitRotation;
            PlaceCamera();
        }

        private static float TiltAtDistance(float viewDistance)
        {
            float height = Mathf.Max(viewDistance - GlobeRadius, MinDistance - GlobeRadius);
            float fraction = 1f - Mathf.InverseLerp(Mathf.Log(MinDistance - GlobeRadius),
                Mathf.Log(1.4f), Mathf.Log(height));
            return MaxGroundTilt * Mathf.SmoothStep(0f, 1f, fraction);
        }

        private void PlaceCamera()
        {
            orbitRotation = orbitRotation.normalized;
            var view = orbitRotation * Quaternion.Euler(-GroundTiltDegrees, 0f, 0f);
            float cosine = Mathf.Cos(GroundTiltDegrees * Mathf.Deg2Rad);
            float range = -GlobeRadius * cosine +
                          Mathf.Sqrt(distance * distance - GlobeRadius * GlobeRadius * (1f - cosine * cosine));
            transform.SetPositionAndRotation(FocusPoint + view * (Vector3.back * range), view);
            pitch = Mathf.DeltaAngle(0f, orbitRotation.eulerAngles.x);
            yaw = orbitRotation.eulerAngles.y;
        }
    }
}
