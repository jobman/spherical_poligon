// Legacy checks for the earlier always-visible panel; not a test of the Esc menu.
// Do not run UI checks unless the user explicitly requests them.
if (!UnityEngine.Application.isPlaying) throw new System.InvalidOperationException("Run this check in Play Mode.");
var camera = UnityEngine.Camera.main;
var orbit = camera.GetComponent<SphericalCivilization.OrbitCamera>();
var globe = UnityEngine.Object.FindFirstObjectByType<SphericalCivilization.GlobePreview>();
var panel = UnityEngine.Object.FindFirstObjectByType<SphericalCivilization.CameraControlsPanel>();
var root = panel.GetComponent<UnityEngine.UIElements.UIDocument>().rootVisualElement;
var oldOrientation = orbit.Orientation;
float oldDistance = orbit.distance;
var oldSettings = UnityEngine.JsonUtility.FromJson<SphericalCivilization.CameraSettings>(orbit.GetSettingsJson());
int oldSelection = globe.SelectedTileId;
var checks = new System.Collections.Generic.List<string>();
float maxAnchorError = 0f;
void Require(bool condition, string message) { if (!condition) throw new System.InvalidOperationException(message); }
void SettleZoom() { for(int i=0;i<360;i++) orbit.AdvanceZoom(1f/120f); }
var center = new UnityEngine.Vector2(UnityEngine.Screen.width*0.5f,UnityEngine.Screen.height*0.5f);
var offset = new UnityEngine.Vector2(UnityEngine.Screen.height*0.04f,UnityEngine.Screen.height*0.03f);
var background = new UnityEngine.Vector2(10f,UnityEngine.Screen.height*0.5f);
try
{
    UnityEngine.Physics.SyncTransforms();
    foreach(float d in new[]{1.1f,1.35f,2f,3.3f,7f})
    foreach(var q in new[]{UnityEngine.Quaternion.Euler(18f,30f,0f),UnityEngine.Quaternion.Euler(88f,140f,35f)})
    {
        orbit.SetView(q,d);
        Require(orbit.BeginDrag(center),"Cannot grab surface.");
        Require(orbit.DragMode==SphericalCivilization.GlobeDragMode.Surface,"Surface press chose background mode.");
        var anchor=orbit.GrabbedPoint;
        foreach(var target in new[]{center+offset,center-offset,center})
        {
            orbit.DragTo(target);
            float error=UnityEngine.Vector2.Distance(camera.WorldToScreenPoint(anchor),target);
            maxAnchorError=UnityEngine.Mathf.Max(maxAnchorError,error);
            Require(error<0.75f,"Surface anchor slipped by "+error+" pixels at distance "+d);
        }
        orbit.CancelDrag();
    }
    checks.Add("Surface grabbing stays anchored across five distances, both near poles and with automatic tilt.");

    orbit.BackgroundRotationSpeed=1f;
    orbit.SetView(UnityEngine.Quaternion.Euler(89f,0f,0f),3.3f);
    orbit.BeginDrag(background,false);
    orbit.DragTo(background+new UnityEngine.Vector2(0f,-10f));
    Require((orbit.Orientation*UnityEngine.Vector3.forward).z<0f,"Background drag stopped at the north pole.");
    var crossed=orbit.Orientation;
    orbit.DragTo(background+new UnityEngine.Vector2(0f,-1810f));
    Require(UnityEngine.Quaternion.Angle(crossed,orbit.Orientation)<0.05f,"Background drag could not complete a full turn.");
    orbit.CancelDrag();
    orbit.SetView(UnityEngine.Quaternion.Euler(-89f,0f,0f),3.3f);
    orbit.BeginDrag(background,false);
    orbit.DragTo(background+new UnityEngine.Vector2(0f,10f));
    Require((orbit.Orientation*UnityEngine.Vector3.forward).z<0f,"Background drag stopped at the south pole.");
    orbit.CancelDrag();
    checks.Add("Background drag crosses both poles and completes full rotations.");

    orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
    orbit.KeyboardRotationSpeed=1f;
    orbit.TurnRotationSpeed=1f;
    for(int i=0;i<30;i++) orbit.RotateKeyboard(UnityEngine.Vector2.up,UnityEngine.Vector2.zero,1f/30f);
    var at30=orbit.Orientation;
    orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
    for(int i=0;i<120;i++) orbit.RotateKeyboard(UnityEngine.Vector2.up,UnityEngine.Vector2.zero,1f/120f);
    Require(UnityEngine.Quaternion.Angle(at30,orbit.Orientation)<0.05f,"Keyboard rotation depends on frame rate.");
    orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
    orbit.RotateKeyboard(UnityEngine.Vector2.zero,UnityEngine.Vector2.up,1f);
    Require(UnityEngine.Quaternion.Angle(at30,orbit.Orientation)<0.05f,"Arrows and WASD differ.");
    orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
    orbit.RotateKeyboard(UnityEngine.Vector2.up,UnityEngine.Vector2.up,1f);
    Require(UnityEngine.Quaternion.Angle(at30,orbit.Orientation)<0.05f,"Holding both key sets doubles the speed.");
    orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
    orbit.RotateKeyboard(UnityEngine.Vector2.up,UnityEngine.Vector2.right,1f);
    Require(UnityEngine.Mathf.Abs(UnityEngine.Quaternion.Angle(UnityEngine.Quaternion.identity,orbit.Orientation)-60f)<0.05f,
        "Diagonal movement accelerates rotation.");
    orbit.KeyboardRotationSpeed=0.5f;
    orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
    orbit.RotateKeyboard(UnityEngine.Vector2.up,UnityEngine.Vector2.zero,1f);
    float slow=UnityEngine.Quaternion.Angle(UnityEngine.Quaternion.identity,orbit.Orientation);
    orbit.KeyboardRotationSpeed=2f;
    orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
    orbit.RotateKeyboard(UnityEngine.Vector2.zero,UnityEngine.Vector2.up,1f);
    Require(UnityEngine.Mathf.Abs(UnityEngine.Quaternion.Angle(UnityEngine.Quaternion.identity,orbit.Orientation)/slow-4f)<0.02f,
        "The shared keyboard speed control does not affect both key sets.");
    orbit.KeyboardRotationSpeed=1f;
    foreach(float d in new[]{1.1f,1.35f,3.3f,7f})
    {
        orbit.SetView(UnityEngine.Quaternion.identity,d);
        float actualRadius=camera.transform.position.magnitude;
        Require(UnityEngine.Mathf.Abs(orbit.KeyboardDegreesPerSecond-60f*actualRadius/3.3f)<0.001f,
            "Keyboard speed is not linear in actual center distance.");
        orbit.RotateKeyboard(UnityEngine.Vector2.up,UnityEngine.Vector2.zero,0.25f);
        float angle=UnityEngine.Quaternion.Angle(UnityEngine.Quaternion.identity,orbit.Orientation);
        Require(UnityEngine.Mathf.Abs(angle-60f*d/3.3f*0.25f)<0.05f,"Rotation used surface height instead of center distance.");
    }
    orbit.SetView(UnityEngine.Quaternion.Euler(89f,0f,0f),3.3f);
    orbit.RotateKeyboard(UnityEngine.Vector2.up,UnityEngine.Vector2.zero,0.2f);
    Require((orbit.Orientation*UnityEngine.Vector3.forward).z<0f,"Keyboard stopped at the pole.");
    checks.Add("WASD and arrows share one speed, scale linearly with center distance, avoid overlap/diagonal acceleration and cross poles independently of frame rate.");

    foreach(float d in new[]{1.1f,1.35f,3.3f,7f})
    {
        var initial=UnityEngine.Quaternion.Euler(88f,140f,35f);
        orbit.SetView(initial,d);
        var focus=orbit.FocusPoint;
        float tilt=orbit.GroundTiltDegrees;
        orbit.RotateKeyboard(UnityEngine.Vector2.zero,UnityEngine.Vector2.zero,0.25f,1f);
        Require(UnityEngine.Vector3.Distance(focus,orbit.FocusPoint)<0.000001f,
            "Q/E moved the focused ground point.");
        Require(UnityEngine.Mathf.Abs(orbit.GroundTiltDegrees-tilt)<0.00001f && orbit.distance==d,
            "Q/E changed tilt or zoom.");
        Require(UnityEngine.Mathf.Abs(UnityEngine.Quaternion.Angle(initial,orbit.Orientation)-orbit.KeyboardDegreesPerSecond*0.25f)<0.05f,
            "Q/E do not share the accepted keyboard speed law.");
        orbit.RotateKeyboard(UnityEngine.Vector2.zero,UnityEngine.Vector2.zero,0.25f,-1f);
        Require(UnityEngine.Quaternion.Angle(initial,orbit.Orientation)<0.05f,"Q/E do not rotate in opposite directions.");
    }
    orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
    for(int i=0;i<30;i++) orbit.RotateKeyboard(UnityEngine.Vector2.up,UnityEngine.Vector2.zero,1f/30f,1f);
    var combined=orbit.Orientation;
    Require(UnityEngine.Mathf.Abs(UnityEngine.Quaternion.Angle(UnityEngine.Quaternion.identity,combined)-60f)<0.05f,
        "Combining Q/E with WASD accelerates rotation.");
    orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
    for(int i=0;i<120;i++) orbit.RotateKeyboard(UnityEngine.Vector2.up,UnityEngine.Vector2.zero,1f/120f,1f);
    Require(UnityEngine.Quaternion.Angle(combined,orbit.Orientation)<0.05f,"Combined Q/E rotation depends on frame rate.");
    orbit.RotationInertiaHalfLife=0.11f;
    orbit.SetView(UnityEngine.Quaternion.identity,1.1f);
    orbit.RotateKeyboard(UnityEngine.Vector2.zero,UnityEngine.Vector2.zero,0.1f,1f);
    var turnFocus=orbit.FocusPoint;
    float turnSpeed=orbit.InertiaAngularSpeed;
    orbit.AdvanceInertia(0.11f);
    Require(UnityEngine.Mathf.Abs(orbit.InertiaAngularSpeed-turnSpeed*0.5f)<0.001f &&
        UnityEngine.Vector3.Distance(turnFocus,orbit.FocusPoint)<0.000001f,"Q/E inertia did not retain its pivot and half-life.");
    checks.Add("Q/E turn around the focused ground point, preserve zoom/tilt, combine with WASD and share speed, frame independence and inertia.");

    orbit.ScrollSpeed=1f;
    orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
    orbit.ApplyScroll(1f,center);
    float farStep=3.3f-orbit.TargetDistance;
    Require(farStep>0.4f && farStep<0.6f,"One normalized wheel notch is too weak or too strong: "+farStep);
    Require(orbit.distance==3.3f,"Zoom skipped smoothing.");
    orbit.AdvanceZoom(1f/60f);
    Require(orbit.distance<3.3f && orbit.distance>orbit.TargetDistance,"Zoom is not smoothly approaching its target.");
    SettleZoom();
    Require(UnityEngine.Mathf.Abs(orbit.distance-orbit.TargetDistance)<0.0001f,"Zoom did not settle.");
    orbit.SetView(UnityEngine.Quaternion.identity,1.35f);
    orbit.ApplyScroll(1f,center);
    Require(1.35f-orbit.TargetDistance<farStep*0.2f,"Zoom did not slow down near the surface.");
    orbit.ScrollSpeed=5f;
    orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
    orbit.ApplyScroll(1f,center);
    Require(3.3f-orbit.TargetDistance>farStep*2f,"Zoom speed slider has insufficient effect.");
    orbit.ApplyScroll(100000f,center); SettleZoom();
    Require(UnityEngine.Mathf.Abs(orbit.distance-SphericalCivilization.OrbitCamera.MinDistance)<0.0001f,"Zoom minimum failed.");
    orbit.ApplyScroll(-100000f,center); SettleZoom();
    Require(UnityEngine.Mathf.Abs(orbit.distance-SphericalCivilization.OrbitCamera.MaxDistance)<0.0001f,"Zoom maximum failed.");
    checks.Add("A normalized wheel notch gives useful height-dependent zoom, smooth motion, stronger speed settings and safe limits.");

    var qBase=UnityEngine.Quaternion.Euler(18f,30f,0f);
    float lastTilt=-1f;
    foreach(float d in new[]{7f,3.3f,2.4f,2f,1.5f,1.2f,1.1f})
    {
        orbit.SetView(qBase,d);
        Require(orbit.GroundTiltDegrees>=lastTilt,"Tilt is not increasing smoothly toward the ground.");
        lastTilt=orbit.GroundTiltDegrees;
        var focusPixel=(UnityEngine.Vector2)camera.WorldToScreenPoint(orbit.FocusPoint);
        Require(UnityEngine.Vector2.Distance(focusPixel,center)<0.1f,"Automatic tilt lost the ground focus point.");
        Require(UnityEngine.Mathf.Abs(camera.transform.position.magnitude-d)<0.0001f,"Automatic tilt changed camera altitude.");
    }
    Require(UnityEngine.Mathf.Abs(lastTilt-50f)<0.05f,"Near-ground tilt is incorrect.");
    orbit.SetView(qBase,7f);
    Require(orbit.GroundTiltDegrees<0.01f,"Distant globe view is tilted.");
    checks.Add("Zoom tilts from nadir to 50 degrees while keeping the same ground focus and altitude.");

    orbit.SetView(qBase,1.35f);
    globe.SelectTile(0);
    orbit.BeginDrag(center); orbit.DragTo(center+offset); orbit.EndDrag(center+offset);
    Require(globe.SelectedTileId==0,"Dragging changed tile selection.");
    orbit.BeginDrag(center); orbit.EndDrag(center);
    Require(globe.SelectedTileId>=0,"Short click did not select terrain.");
    checks.Add("Selection still distinguishes clicks from drags at an oblique view.");

    var card=UnityEngine.UIElements.UQueryExtensions.Q(root,"cameraPanel");
    var a=UnityEngine.UIElements.RuntimePanelUtils.ScreenToPanel(root.panel,UnityEngine.Vector2.zero);
    var b=UnityEngine.UIElements.RuntimePanelUtils.ScreenToPanel(root.panel,new UnityEngine.Vector2(UnityEngine.Screen.width,UnityEngine.Screen.height));
    var p=card.worldBound.center;
    var uiPoint=new UnityEngine.Vector2((p.x-a.x)/(b.x-a.x)*UnityEngine.Screen.width,
        UnityEngine.Screen.height-(p.y-a.y)/(b.y-a.y)*UnityEngine.Screen.height);
    orbit.SetView(qBase,3.3f);
    Require(!orbit.BeginDrag(uiPoint) && !orbit.ApplyScroll(1f,uiPoint),"UI does not block camera pointer input.");
    Require(orbit.TargetDistance==3.3f,"UI wheel input changed zoom.");
    checks.Add("Camera panel blocks world drag and zoom.");

    orbit.ScrollSpeed=1f;
    orbit.ScrollInertiaHalfLife=0.11f;
    orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
    orbit.ApplyScroll(1f,center);
    float scrollVelocity=orbit.ScrollInertiaVelocity;
    float remaining=orbit.distance-orbit.TargetDistance;
    orbit.AdvanceZoom(0.11f);
    Require(UnityEngine.Mathf.Abs(orbit.ScrollInertiaVelocity-scrollVelocity*0.5f)<0.0001f &&
        UnityEngine.Mathf.Abs(orbit.distance-orbit.TargetDistance-remaining*0.5f)<0.0001f,
        "Scroll velocity did not halve in 0.11 seconds.");
    float oneZoomStep=orbit.distance;
    orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
    orbit.ApplyScroll(1f,center);
    for(int i=0;i<11;i++) orbit.AdvanceZoom(0.01f);
    Require(UnityEngine.Mathf.Abs(orbit.distance-oneZoomStep)<0.00001f,"Scroll inertia depends on frame rate.");
    orbit.ApplyScroll(-1f,center);
    Require(orbit.ScrollInertiaVelocity>0f,"Reverse scrolling did not reverse the zoom.");
    orbit.BeginDrag(center,false);
    Require(orbit.ScrollInertiaVelocity==0f && orbit.TargetDistance==orbit.distance,"New grab did not stop scroll inertia.");
    orbit.CancelDrag();
    orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
    orbit.ApplyScroll(1f,center);
    Require(!orbit.ApplyScroll(1f,uiPoint) && orbit.ScrollInertiaVelocity==0f,"UI wheel input did not stop pending zoom.");
    orbit.ScrollInertiaHalfLife=0f;
    orbit.ApplyScroll(1f,center);
    Require(orbit.distance==orbit.TargetDistance && !orbit.AdvanceZoom(0.1f),"Zero scroll inertia was not immediate.");
    orbit.SetView(qBase,1.35f);
    var zoomGrabPosition=center+offset;
    orbit.BeginDrag(zoomGrabPosition,false);
    var zoomAnchor=orbit.GrabbedPoint;
    orbit.ApplyScroll(1f,zoomGrabPosition);
    Require(UnityEngine.Vector2.Distance(camera.WorldToScreenPoint(zoomAnchor),zoomGrabPosition)<0.75f,
        "Instant zoom lost the grabbed surface point.");
    orbit.CancelDrag();
    orbit.ScrollInertiaHalfLife=0.11f;
    orbit.ApplyScroll(1f,center);
    orbit.SendMessage("OnApplicationFocus",false);
    Require(orbit.ScrollInertiaVelocity==0f,"Focus loss did not stop scroll inertia.");
    checks.Add("Scroll velocity halves in 0.11 seconds independently of frame rate, reverses correctly, stops on grab/UI/focus loss and supports zero inertia.");

    orbit.RotationInertiaHalfLife=0.12f;
    orbit.KeyboardRotationSpeed=1f;
    orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
    orbit.RotateKeyboard(UnityEngine.Vector2.up,UnityEngine.Vector2.zero,0.1f);
    var released=orbit.Orientation;
    Require(orbit.AdvanceInertia(0.12f),"Keyboard release did not coast.");
    Require(UnityEngine.Mathf.Abs(orbit.InertiaAngularSpeed-30f)<0.01f,"Inertia did not halve velocity in the selected time.");
    Require(UnityEngine.Quaternion.Angle(released,orbit.Orientation)>1f,"Momentum did not continue rotation.");
    var oneStep=orbit.Orientation;
    orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
    orbit.RotateKeyboard(UnityEngine.Vector2.up,UnityEngine.Vector2.zero,0.1f);
    for(int i=0;i<12;i++) orbit.AdvanceInertia(0.01f);
    Require(UnityEngine.Quaternion.Angle(oneStep,orbit.Orientation)<0.05f,"Inertia displacement depends on frame rate.");
    Require(UnityEngine.Mathf.Abs(orbit.InertiaAngularSpeed-30f)<0.01f,"Inertia damping depends on frame rate.");
    for(int i=0;i<180;i++) orbit.AdvanceInertia(1f/60f);
    Require(orbit.InertiaAngularSpeed==0f,"Inertia did not stop.");
    orbit.RotationInertiaHalfLife=0f;
    orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
    orbit.RotateKeyboard(UnityEngine.Vector2.up,UnityEngine.Vector2.zero,0.1f);
    released=orbit.Orientation;
    Require(!orbit.AdvanceInertia(0.1f) && orbit.InertiaAngularSpeed==0f &&
        UnityEngine.Quaternion.Angle(released,orbit.Orientation)<0.01f,"Zero inertia did not stop immediately.");
    checks.Add("Keyboard momentum continues on release, halves at the chosen time, is frame-rate independent, settles and can be disabled.");

    orbit.RotationInertiaHalfLife=0.12f;
    foreach(var press in new[]{center,background})
    {
        orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
        orbit.BeginDrag(press,false);
        orbit.DragTo(press+new UnityEngine.Vector2(20f,10f),1f/60f);
        orbit.EndDrag(press+new UnityEngine.Vector2(20f,10f));
        Require(orbit.InertiaAngularSpeed>0.1f,"Mouse drag did not transfer angular momentum.");
        released=orbit.Orientation;
        orbit.AdvanceInertia(0.05f);
        Require(UnityEngine.Quaternion.Angle(released,orbit.Orientation)>0.05f,"Mouse release did not coast.");
        orbit.BeginDrag(center,false);
        Require(orbit.InertiaAngularSpeed==0f && !orbit.AdvanceInertia(0.1f),"New grab did not stop the coast.");
        orbit.CancelDrag();
    }
    orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
    orbit.BeginDrag(background,false);
    var stoppedPointer=background+new UnityEngine.Vector2(30f,0f);
    orbit.DragTo(stoppedPointer,1f/60f);
    for(int i=0;i<30;i++) orbit.DragTo(stoppedPointer,1f/60f);
    orbit.EndDrag(stoppedPointer);
    Require(orbit.InertiaAngularSpeed<0.02f,"Pausing the mouse launched stale momentum.");
    orbit.RotateKeyboard(UnityEngine.Vector2.up,UnityEngine.Vector2.zero,0.1f);
    Require(!orbit.BeginDrag(uiPoint) && orbit.InertiaAngularSpeed==0f,"UI interaction did not stop inertia.");
    orbit.RotateKeyboard(UnityEngine.Vector2.up,UnityEngine.Vector2.zero,0.1f);
    orbit.SendMessage("OnApplicationFocus",false);
    Require(orbit.InertiaAngularSpeed==0f,"Focus loss did not stop inertia.");
    checks.Add("Both mouse modes coast, a new grab or UI stops momentum, a paused pointer does not fling and focus loss is safe.");

    orbit.BackgroundRotationSpeed=oldSettings.backgroundRotationSpeed;
    orbit.KeyboardRotationSpeed=oldSettings.keyboardRotationSpeed;
    orbit.ScrollSpeed=oldSettings.scrollSpeed;
    var inertiaSlider=UnityEngine.UIElements.UQueryExtensions.Q<UnityEngine.UIElements.Slider>(root,"inertiaSlider");
    var scrollSlider=UnityEngine.UIElements.UQueryExtensions.Q<UnityEngine.UIElements.Slider>(root,"scrollInertiaSlider");
    var turnSlider=UnityEngine.UIElements.UQueryExtensions.Q<UnityEngine.UIElements.Slider>(root,"turnSpeedSlider");
    Require(UnityEngine.UIElements.UQueryExtensions.Query<UnityEngine.UIElements.Slider>(root).ToList().Count==3,"Expected turn speed and two inertia sliders.");
    turnSlider.value=2f;
    Require(orbit.TurnRotationSpeed==2f,"Turn speed slider is not bound.");
    orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
    orbit.RotateKeyboard(UnityEngine.Vector2.zero,UnityEngine.Vector2.zero,0.25f,1f);
    Require(UnityEngine.Mathf.Abs(UnityEngine.Quaternion.Angle(UnityEngine.Quaternion.identity,orbit.Orientation)-30f)<0.05f,
        "Turn speed slider did not double Q/E speed.");
    orbit.SetView(UnityEngine.Quaternion.identity,3.3f);
    orbit.RotateKeyboard(UnityEngine.Vector2.up,UnityEngine.Vector2.zero,0.25f);
    Require(UnityEngine.Mathf.Abs(UnityEngine.Quaternion.Angle(UnityEngine.Quaternion.identity,orbit.Orientation)-15f)<0.05f,
        "Turn speed slider affected WASD.");
    inertiaSlider.value=0.3f;
    Require(UnityEngine.Mathf.Approximately(orbit.RotationInertiaHalfLife,0.3f),"Inertia slider is not bound.");
    scrollSlider.value=0.24f;
    Require(UnityEngine.Mathf.Approximately(orbit.ScrollInertiaHalfLife,0.24f),"Scroll inertia slider is not bound.");
    Require(orbit.BackgroundRotationSpeed==oldSettings.backgroundRotationSpeed &&
        orbit.KeyboardRotationSpeed==oldSettings.keyboardRotationSpeed && orbit.ScrollSpeed==oldSettings.scrollSpeed,
        "Inertia slider changed the accepted speeds.");
    string clipboard=UnityEngine.GUIUtility.systemCopyBuffer;
    try
    {
        var button=UnityEngine.UIElements.UQueryExtensions.Q<UnityEngine.UIElements.Button>(root,"copyButton");
        button.Focus();
        using(var submit=UnityEngine.UIElements.NavigationSubmitEvent.GetPooled()) button.SendEvent(submit);
        var copied=UnityEngine.JsonUtility.FromJson<SphericalCivilization.CameraSettings>(UnityEngine.GUIUtility.systemCopyBuffer);
        Require(copied.turnRotationSpeed==2f && copied.rotationInertiaHalfLife==0.3f && copied.scrollInertiaHalfLife==0.24f && copied.keyboardRotationSpeed==oldSettings.keyboardRotationSpeed &&
            copied.backgroundRotationSpeed==oldSettings.backgroundRotationSpeed && copied.scrollSpeed==oldSettings.scrollSpeed,
            "Clipboard did not copy inertia and the frozen speed profile.");
    }
    finally { UnityEngine.GUIUtility.systemCopyBuffer=clipboard; }
    checks.Add("Turn speed slider changes Q/E independently of WASD; both inertia sliders and Copy export the current profile.");
    return new{Passed=checks.Count,Checks=checks,MaxAnchorErrorPixels=maxAnchorError};
}
finally
{
    orbit.CancelDrag(); orbit.SetView(oldOrientation,oldDistance);
    orbit.BackgroundRotationSpeed=oldSettings.backgroundRotationSpeed;
    orbit.KeyboardRotationSpeed=oldSettings.keyboardRotationSpeed;
    orbit.TurnRotationSpeed=oldSettings.turnRotationSpeed;
    orbit.ScrollSpeed=oldSettings.scrollSpeed;
    orbit.RotationInertiaHalfLife=oldSettings.rotationInertiaHalfLife;
    orbit.ScrollInertiaHalfLife=oldSettings.scrollInertiaHalfLife;
    panel.enabled=false; panel.enabled=true;
    SphericalCivilization.CameraControlsPanel.ReleaseKeyboardFocus();
    if(oldSelection>=0) globe.SelectTile(oldSelection); else globe.ClearSelection();
}
