// Legacy input/UI checks for the earlier always-visible panel; not an Esc-menu test.
// Do not run unless the user explicitly requests UI verification.
if (!UnityEngine.Application.isPlaying) throw new System.InvalidOperationException("Run this check in Play Mode.");
var orbit = UnityEngine.Camera.main.GetComponent<SphericalCivilization.OrbitCamera>();
var globe = UnityEngine.Object.FindFirstObjectByType<SphericalCivilization.GlobePreview>();
var document = UnityEngine.Object.FindFirstObjectByType<UnityEngine.UIElements.UIDocument>();
var root = document.rootVisualElement;
var previousMouse = UnityEngine.InputSystem.Mouse.current;
var previousKeyboard = UnityEngine.InputSystem.Keyboard.current;
bool previousMouseEnabled = previousMouse != null && previousMouse.enabled;
bool previousKeyboardEnabled = previousKeyboard != null && previousKeyboard.enabled;
var mouse = UnityEngine.InputSystem.InputSystem.AddDevice<UnityEngine.InputSystem.Mouse>("CameraVerificationMouse");
var keyboard = UnityEngine.InputSystem.InputSystem.AddDevice<UnityEngine.InputSystem.Keyboard>("CameraVerificationKeyboard");
if(previousMouseEnabled) UnityEngine.InputSystem.InputSystem.DisableDevice(previousMouse);
if(previousKeyboardEnabled) UnityEngine.InputSystem.InputSystem.DisableDevice(previousKeyboard);
var events = UnityEngine.EventSystems.EventSystem.current;
bool oldUIFocus = events.isFocused;
events.SendMessage("OnApplicationFocus",true);
var oldInputBehavior = UnityEngine.InputSystem.InputSystem.settings.editorInputBehaviorInPlayMode;
var oldBackgroundBehavior = UnityEngine.InputSystem.InputSystem.settings.backgroundBehavior;
bool oldRunInBackground = UnityEngine.Application.runInBackground;
UnityEngine.InputSystem.InputSystem.settings.editorInputBehaviorInPlayMode = UnityEngine.InputSystem.InputSettings.EditorInputBehaviorInPlayMode.AllDeviceInputAlwaysGoesToGameView;
UnityEngine.InputSystem.InputSystem.settings.backgroundBehavior = UnityEngine.InputSystem.InputSettings.BackgroundBehavior.IgnoreFocus;
UnityEngine.Application.runInBackground = true;
UnityEngine.InputSystem.InputSystem.EnableDevice(mouse);
UnityEngine.InputSystem.InputSystem.EnableDevice(keyboard);
var oldView = orbit.Orientation;
float oldDistance = orbit.distance, oldSpeed = orbit.BackgroundRotationSpeed;
float oldKeyboardSpeed = orbit.KeyboardRotationSpeed;
float oldTurnSpeed = orbit.TurnRotationSpeed;
float oldScroll = orbit.ScrollSpeed;
float oldInertia = orbit.RotationInertiaHalfLife;
float oldScrollInertia = orbit.ScrollInertiaHalfLife;
int oldSelection = globe.SelectedTileId;
var checks = new System.Collections.Generic.List<string>();
string oldClipboard = UnityEngine.GUIUtility.systemCopyBuffer;
UnityEngine.InputSystem.LowLevel.MouseState? next = null;
UnityEngine.InputSystem.LowLevel.KeyboardState? nextKeys = null;
System.Action inject = () =>
{
    if (UnityEngine.InputSystem.LowLevel.InputState.currentUpdateType == UnityEngine.InputSystem.LowLevel.InputUpdateType.Dynamic && next.HasValue)
    {
        UnityEngine.InputSystem.InputSystem.QueueStateEvent(mouse,next.Value);
        next = null;
    }
    if (UnityEngine.InputSystem.LowLevel.InputState.currentUpdateType == UnityEngine.InputSystem.LowLevel.InputUpdateType.Dynamic && nextKeys.HasValue)
    {
        UnityEngine.InputSystem.InputSystem.QueueStateEvent(keyboard,nextKeys.Value);
        nextKeys = null;
    }
};
void Require(bool value,string message) { if(!value) throw new System.Exception(message); }
UnityEngine.Vector2 ToScreen(UnityEngine.UIElements.VisualElement element)
{
    var a = UnityEngine.UIElements.RuntimePanelUtils.ScreenToPanel(root.panel,UnityEngine.Vector2.zero);
    var b = UnityEngine.UIElements.RuntimePanelUtils.ScreenToPanel(root.panel,new UnityEngine.Vector2(UnityEngine.Screen.width,UnityEngine.Screen.height));
    var p = element.worldBound.center;
    return new UnityEngine.Vector2((p.x-a.x)/(b.x-a.x)*UnityEngine.Screen.width,
        UnityEngine.Screen.height-(p.y-a.y)/(b.y-a.y)*UnityEngine.Screen.height);
}
System.Collections.IEnumerator Run()
{
    UnityEngine.InputSystem.InputSystem.onBeforeUpdate += inject;
    try
    {
        orbit.CancelDrag();
        orbit.RotationInertiaHalfLife=0.12f;
        next = new UnityEngine.InputSystem.LowLevel.MouseState { buttons=0 };
        yield return new UnityEngine.WaitForSecondsRealtime(0.15f);
        var center = new UnityEngine.Vector2(UnityEngine.Screen.width/2f,UnityEngine.Screen.height/2f);
        orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
        next = new UnityEngine.InputSystem.LowLevel.MouseState {position=center,buttons=1};
        yield return new UnityEngine.WaitForSecondsRealtime(0.15f);
        Require(orbit.DragMode==SphericalCivilization.GlobeDragMode.Surface,"Left down did not grab surface.");
        var target = center+new UnityEngine.Vector2(40f,25f);
        next = new UnityEngine.InputSystem.LowLevel.MouseState {position=target,buttons=1};
        yield return new UnityEngine.WaitForSecondsRealtime(0.15f);
        float error = UnityEngine.Vector2.Distance(UnityEngine.Camera.main.WorldToScreenPoint(orbit.GrabbedPoint),target);
        Require(error<0.5f,"Left-drag anchor error: "+error);
        checks.Add("Left surface drag passed; error pixels="+error.ToString(System.Globalization.CultureInfo.InvariantCulture));
        next = new UnityEngine.InputSystem.LowLevel.MouseState {position=target,buttons=0};
        yield return new UnityEngine.WaitForSecondsRealtime(0.15f);
        Require(orbit.DragMode==SphericalCivilization.GlobeDragMode.None,"Left release did not end drag.");

        orbit.CancelDrag();
        orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
        orbit.BackgroundRotationSpeed=1f;
        var background = new UnityEngine.Vector2(10f,UnityEngine.Screen.height/2f);
        next = new UnityEngine.InputSystem.LowLevel.MouseState {position=background,buttons=2};
        yield return new UnityEngine.WaitForSecondsRealtime(0.15f);
        Require(orbit.DragMode==SphericalCivilization.GlobeDragMode.Background,"Right down did not begin background rotation: "+orbit.DragMode);
        next = new UnityEngine.InputSystem.LowLevel.MouseState {position=background+new UnityEngine.Vector2(100f,0f),buttons=2};
        yield return new UnityEngine.WaitForSecondsRealtime(0.15f);
        Require(UnityEngine.Mathf.Abs(UnityEngine.Quaternion.Angle(UnityEngine.Quaternion.identity,orbit.Orientation)-20f)<0.1f,"Right background rotation did not match sensitivity.");
        next = new UnityEngine.InputSystem.LowLevel.MouseState {position=background,buttons=0};
        yield return new UnityEngine.WaitForSecondsRealtime(0.15f);
        checks.Add("Right background drag and release passed.");

        SphericalCivilization.CameraControlsPanel.ReleaseKeyboardFocus();
        orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
        orbit.KeyboardRotationSpeed=1f;
        nextKeys=new UnityEngine.InputSystem.LowLevel.KeyboardState(UnityEngine.InputSystem.Key.W);
        yield return new UnityEngine.WaitForSecondsRealtime(0.2f);
        Require(UnityEngine.Quaternion.Angle(UnityEngine.Quaternion.identity,orbit.Orientation)>2f,"Holding W did not rotate the camera.");
        nextKeys=new UnityEngine.InputSystem.LowLevel.KeyboardState();
        yield return new UnityEngine.WaitForSecondsRealtime(0.15f);
        var releasedView=orbit.Orientation;
        float releasedSpeed=orbit.InertiaAngularSpeed;
        yield return new UnityEngine.WaitForSecondsRealtime(0.15f);
        Require(UnityEngine.Quaternion.Angle(releasedView,orbit.Orientation)>0.1f &&
            orbit.InertiaAngularSpeed>0f && orbit.InertiaAngularSpeed<releasedSpeed,"Key release did not give a decaying coast.");
        orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
        nextKeys=new UnityEngine.InputSystem.LowLevel.KeyboardState(UnityEngine.InputSystem.Key.UpArrow);
        yield return new UnityEngine.WaitForSecondsRealtime(0.2f);
        Require(UnityEngine.Quaternion.Angle(UnityEngine.Quaternion.identity,orbit.Orientation)>2f,"Holding Up Arrow did not rotate the camera.");
        nextKeys=new UnityEngine.InputSystem.LowLevel.KeyboardState();
        yield return new UnityEngine.WaitForSecondsRealtime(0.15f);
        checks.Add("WASD and arrow-key events rotate the camera and coast with decaying velocity on release.");

        foreach(var key in new[]{UnityEngine.InputSystem.Key.Q,UnityEngine.InputSystem.Key.E})
        {
            orbit.SetView(UnityEngine.Quaternion.identity,1.1f);
            var turnFocus=orbit.FocusPoint;
            nextKeys=new UnityEngine.InputSystem.LowLevel.KeyboardState(key);
            yield return new UnityEngine.WaitForSecondsRealtime(0.2f);
            Require(UnityEngine.Quaternion.Angle(UnityEngine.Quaternion.identity,orbit.Orientation)>1f &&
                UnityEngine.Vector3.Distance(turnFocus,orbit.FocusPoint)<0.00001f,"Q/E input did not turn around the ground focus: "+key);
            Require((orbit.Orientation*UnityEngine.Vector3.right).y*(key==UnityEngine.InputSystem.Key.Q?-1f:1f)>0f,
                "Q/E input turned in the wrong direction: "+key);
            nextKeys=new UnityEngine.InputSystem.LowLevel.KeyboardState();
            yield return new UnityEngine.WaitForSecondsRealtime(0.15f);
            var turnReleased=orbit.Orientation;
            float turnVelocity=orbit.InertiaAngularSpeed;
            yield return new UnityEngine.WaitForSecondsRealtime(0.11f);
            Require(UnityEngine.Quaternion.Angle(turnReleased,orbit.Orientation)>0.01f &&
                orbit.InertiaAngularSpeed>0f && orbit.InertiaAngularSpeed<turnVelocity,"Q/E release did not coast.");
        }
        orbit.SetView(UnityEngine.Quaternion.identity,1.1f);
        nextKeys=new UnityEngine.InputSystem.LowLevel.KeyboardState(UnityEngine.InputSystem.Key.Q,UnityEngine.InputSystem.Key.E);
        yield return new UnityEngine.WaitForSecondsRealtime(0.2f);
        Require(UnityEngine.Quaternion.Angle(UnityEngine.Quaternion.identity,orbit.Orientation)<0.05f,"Q and E do not cancel each other.");
        nextKeys=new UnityEngine.InputSystem.LowLevel.KeyboardState();
        yield return new UnityEngine.WaitForSecondsRealtime(0.15f);
        checks.Add("Q/E events turn in opposite directions around the ground focus, coast on release, and cancel when held together.");

        orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
        orbit.ScrollSpeed=1f;
        orbit.ScrollInertiaHalfLife=0.11f;
        next=new UnityEngine.InputSystem.LowLevel.MouseState {position=center,scroll=new UnityEngine.Vector2(0f,1f)};
        yield return new UnityEngine.WaitForSecondsRealtime(0.25f);
        Require(3.3f-orbit.TargetDistance>0.4f,"A normalized wheel event did not give meaningful zoom.");
        float scrollReleaseDistance=orbit.distance;
        float scrollReleaseSpeed=UnityEngine.Mathf.Abs(orbit.ScrollInertiaVelocity);
        yield return new UnityEngine.WaitForSecondsRealtime(0.11f);
        Require(orbit.distance<scrollReleaseDistance && UnityEngine.Mathf.Abs(orbit.ScrollInertiaVelocity)<scrollReleaseSpeed,
            "Scrolling did not continue with decaying velocity after the wheel stopped.");
        checks.Add("A normalized wheel event zooms and coasts with decaying velocity after release.");

        orbit.CancelDrag();
        orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
        var turnSlider=UnityEngine.UIElements.UQueryExtensions.Q<UnityEngine.UIElements.Slider>(root,"turnSpeedSlider");
        turnSlider.value=1f;
        var turnPoint=ToScreen(UnityEngine.UIElements.UQueryExtensions.Q(turnSlider,"unity-dragger"));
        next=new UnityEngine.InputSystem.LowLevel.MouseState {position=turnPoint,delta=turnPoint-center};
        yield return new UnityEngine.WaitForSecondsRealtime(0.2f);
        next=new UnityEngine.InputSystem.LowLevel.MouseState {position=turnPoint,buttons=1};
        yield return new UnityEngine.WaitForSecondsRealtime(0.15f);
        next=new UnityEngine.InputSystem.LowLevel.MouseState {position=turnPoint+new UnityEngine.Vector2(50f,0f),delta=new UnityEngine.Vector2(50f,0f),buttons=1};
        yield return new UnityEngine.WaitForSecondsRealtime(0.4f);
        Require(orbit.TurnRotationSpeed>1f && orbit.KeyboardRotationSpeed==1f &&
            UnityEngine.Quaternion.Angle(UnityEngine.Quaternion.identity,orbit.Orientation)<0.05f,
            "Turn speed slider did not adjust Q/E independently without moving the world.");
        next=new UnityEngine.InputSystem.LowLevel.MouseState {position=turnPoint,buttons=0};
        yield return new UnityEngine.WaitForSecondsRealtime(0.15f);
        checks.Add("Mouse adjusts Q/E speed without affecting WASD or moving the world.");
        var slider = UnityEngine.UIElements.UQueryExtensions.Q<UnityEngine.UIElements.Slider>(root,"inertiaSlider");
        slider.value=0.12f;
        var point=ToScreen(UnityEngine.UIElements.UQueryExtensions.Q(slider,"unity-dragger"));
        next = new UnityEngine.InputSystem.LowLevel.MouseState {position=point,delta=point-center,buttons=0};
        yield return new UnityEngine.WaitForSecondsRealtime(0.2f);
        next = new UnityEngine.InputSystem.LowLevel.MouseState {position=point,buttons=1};
        yield return new UnityEngine.WaitForSecondsRealtime(0.15f);
        next = new UnityEngine.InputSystem.LowLevel.MouseState {position=point+new UnityEngine.Vector2(50f,0f),buttons=1,delta=new UnityEngine.Vector2(50f,0f)};
        yield return new UnityEngine.WaitForSecondsRealtime(0.4f);
        Require(orbit.DragMode==SphericalCivilization.GlobeDragMode.None &&
            UnityEngine.Quaternion.Angle(UnityEngine.Quaternion.identity,orbit.Orientation)<0.1f,"Slider gesture moved the globe.");
        Require(orbit.RotationInertiaHalfLife>0.12f,"Mouse did not change the inertia slider.");
        next = new UnityEngine.InputSystem.LowLevel.MouseState {position=point,buttons=0};
        yield return new UnityEngine.WaitForSecondsRealtime(0.15f);
        checks.Add("Mouse drags slider without moving the camera.");

        var zoomSlider=UnityEngine.UIElements.UQueryExtensions.Q<UnityEngine.UIElements.Slider>(root,"scrollInertiaSlider");
        var zoomPoint=ToScreen(UnityEngine.UIElements.UQueryExtensions.Q(zoomSlider,"unity-dragger"));
        next=new UnityEngine.InputSystem.LowLevel.MouseState {position=zoomPoint,delta=zoomPoint-point};
        yield return new UnityEngine.WaitForSecondsRealtime(0.2f);
        next=new UnityEngine.InputSystem.LowLevel.MouseState {position=zoomPoint,buttons=1};
        yield return new UnityEngine.WaitForSecondsRealtime(0.15f);
        next=new UnityEngine.InputSystem.LowLevel.MouseState {position=zoomPoint+new UnityEngine.Vector2(40f,0f),delta=new UnityEngine.Vector2(40f,0f),buttons=1};
        yield return new UnityEngine.WaitForSecondsRealtime(0.4f);
        Require(orbit.ScrollInertiaHalfLife>0.11f && orbit.DragMode==SphericalCivilization.GlobeDragMode.None,
            "Mouse did not adjust the scroll inertia slider safely.");
        next=new UnityEngine.InputSystem.LowLevel.MouseState {position=zoomPoint,buttons=0};
        yield return new UnityEngine.WaitForSecondsRealtime(0.15f);
        checks.Add("Mouse adjusts the scroll inertia slider independently.");

        var viewBeforeFocus=orbit.Orientation;
        slider.Focus();
        nextKeys=new UnityEngine.InputSystem.LowLevel.KeyboardState(UnityEngine.InputSystem.Key.W,UnityEngine.InputSystem.Key.Q);
        yield return new UnityEngine.WaitForSecondsRealtime(0.15f);
        Require(UnityEngine.Quaternion.Angle(viewBeforeFocus,orbit.Orientation)<0.05f,"Keyboard rotated the world while a UI control had focus.");
        nextKeys=new UnityEngine.InputSystem.LowLevel.KeyboardState();
        yield return new UnityEngine.WaitForSecondsRealtime(0.15f);
        checks.Add("UI keyboard focus blocks WASD and Q/E world navigation.");

        var copy = ToScreen(UnityEngine.UIElements.UQueryExtensions.Q<UnityEngine.UIElements.Button>(root,"copyButton"));
        next = new UnityEngine.InputSystem.LowLevel.MouseState {position=copy,delta=copy-point,buttons=0};
        yield return new UnityEngine.WaitForSecondsRealtime(0.2f);
        next = new UnityEngine.InputSystem.LowLevel.MouseState {position=copy,buttons=1};
        yield return new UnityEngine.WaitForSecondsRealtime(0.15f);
        next = new UnityEngine.InputSystem.LowLevel.MouseState {position=copy,buttons=0};
        yield return new UnityEngine.WaitForSecondsRealtime(0.15f);
        Require(UnityEngine.GUIUtility.systemCopyBuffer==orbit.GetSettingsJson(),"Mouse click did not copy current camera settings.");
        checks.Add("Mouse click on Copy writes the current settings to the clipboard.");
    }
    finally
    {
        UnityEngine.InputSystem.InputSystem.onBeforeUpdate-=inject;
        UnityEngine.InputSystem.InputSystem.QueueStateEvent(mouse,new UnityEngine.InputSystem.LowLevel.MouseState {buttons=0});
        UnityEngine.InputSystem.InputSystem.QueueStateEvent(keyboard,new UnityEngine.InputSystem.LowLevel.KeyboardState());
        orbit.CancelDrag();
        orbit.SetView(oldView,oldDistance);
        orbit.BackgroundRotationSpeed=oldSpeed;
        orbit.KeyboardRotationSpeed=oldKeyboardSpeed;
        orbit.TurnRotationSpeed=oldTurnSpeed;
        orbit.ScrollSpeed=oldScroll;
        orbit.RotationInertiaHalfLife=oldInertia;
        orbit.ScrollInertiaHalfLife=oldScrollInertia;
        var controls=document.GetComponent<SphericalCivilization.CameraControlsPanel>();
        controls.enabled=false; controls.enabled=true;
        SphericalCivilization.CameraControlsPanel.ReleaseKeyboardFocus();
        if(oldSelection>=0) globe.SelectTile(oldSelection); else globe.ClearSelection();
        UnityEngine.InputSystem.InputSystem.settings.editorInputBehaviorInPlayMode = oldInputBehavior;
        UnityEngine.InputSystem.InputSystem.settings.backgroundBehavior = oldBackgroundBehavior;
        UnityEngine.InputSystem.InputSystem.RemoveDevice(mouse);
        UnityEngine.InputSystem.InputSystem.RemoveDevice(keyboard);
        if(previousMouseEnabled) UnityEngine.InputSystem.InputSystem.EnableDevice(previousMouse);
        if(previousKeyboardEnabled) UnityEngine.InputSystem.InputSystem.EnableDevice(previousKeyboard);
        previousMouse?.MakeCurrent();
        previousKeyboard?.MakeCurrent();
        UnityEngine.Application.runInBackground = oldRunInBackground;
        events.SendMessage("OnApplicationFocus",oldUIFocus);
        UnityEngine.GUIUtility.systemCopyBuffer=oldClipboard;
    }
}
System.Collections.IEnumerator Guard()
{
    var run=Run();
    while(true)
    {
        bool more;
        try { more=run.MoveNext(); }
        catch(System.Exception e)
        {
            UnityEditor.SessionState.SetString("CameraVerification.InputResult","FAILED: "+e.Message+"; "+string.Join(" | ",checks));
            break;
        }
        if(!more)
        {
            UnityEditor.SessionState.SetString("CameraVerification.InputResult","PASSED: "+string.Join(" | ",checks));
            break;
        }
        yield return run.Current;
    }
}
UnityEditor.SessionState.SetString("CameraVerification.InputResult","RUNNING");
orbit.StartCoroutine(Guard());
return "Input verification started on Player dynamic input updates.";
