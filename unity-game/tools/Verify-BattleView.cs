// Calls the game APIs directly. No UI controls or synthesized mouse/keyboard events.
var globe=UnityEngine.Object.FindFirstObjectByType<SphericalCivilization.GlobePreview>();
var orbit=UnityEngine.Object.FindFirstObjectByType<SphericalCivilization.OrbitCamera>();
var controller=globe.GetComponent<SphericalCivilization.Battle.BattlefieldController>();
var camera=orbit.GetComponent<UnityEngine.Camera>();
var oldOrientation=orbit.Orientation;float oldDistance=orbit.distance;var oldSettings=orbit.GetSettings();
int oldTile=globe.SelectedTileId;long? oldCell=globe.SelectedSubtileId;
long? oldTarget=globe.AttackTargetSubtileId;
void Require(bool value,string message){if(!value)throw new System.Exception(message);}
var reports=new System.Collections.Generic.List<object>();
try
{
    foreach(var view in new[]{(orientation:UnityEngine.Quaternion.Euler(20,35,0),distance:1.5f),
        (orientation:UnityEngine.Quaternion.Euler(89,-80,67),distance:1.3f),
        (orientation:UnityEngine.Quaternion.Euler(200,40,112),distance:1.3f)})
    {
        orbit.SetView(view.orientation,view.distance);UnityEngine.Physics.SyncTransforms();
        Require(globe.TryGetSubtile(camera.ViewportPointToRay(new UnityEngine.Vector3(.5f,.5f)),out var cell),"No subtile under the camera.");
        globe.SelectSubtile(cell.Id);
        int source=globe.SelectedSubtileIndex;
        int target=SphericalCivilization.Battle.Battlefield.ChooseNeighbor(globe.Topology,source);
        Require(globe.TrySetAttackTarget(globe.Topology.Subtiles[target].Id),"Failed to choose attack target.");
        var position=camera.transform.position;var rotation=camera.transform.rotation;
        float liveSpeed=orbit.TurnRotationSpeed;orbit.TurnRotationSpeed=1.77f;
        Require(controller.EnterFromSelection(),"Battle failed to enter.");
        Require(!camera.enabled && !globe.GetComponent<UnityEngine.MeshRenderer>().enabled,"Globe and tactical cameras overlap.");
        Require(SphericalCivilization.Battle.BattlefieldController.BlocksGlobeInput,"World camera can move during battle.");
        var field=controller.Field;var edge=globe.Topology.Edges[field.SharedEdgeId];
        Require(field.FirstSubtileIndex==source && field.SecondSubtileIndex==target,"Battle ignored the explicitly selected pair.");
        var a=camera.WorldToScreenPoint(globe.transform.TransformPoint(globe.Topology.Vertices[edge.Start]));
        var b=camera.WorldToScreenPoint(globe.transform.TransformPoint(globe.Topology.Vertices[edge.End]));
        float before=UnityEngine.Mathf.Atan2(b.y-a.y,b.x-a.x)*UnityEngine.Mathf.Rad2Deg;
        var pa=field.Project(globe.Topology.Vertices[edge.Start]);var pb=field.Project(globe.Topology.Vertices[edge.End]);
        var ta=controller.BattleCamera.WorldToScreenPoint(new UnityEngine.Vector3(pa.x,pa.y,0));
        var tb=controller.BattleCamera.WorldToScreenPoint(new UnityEngine.Vector3(pb.x,pb.y,0));
        float after=UnityEngine.Mathf.Atan2(tb.y-ta.y,tb.x-ta.x)*UnityEngine.Mathf.Rad2Deg;
        float error=UnityEngine.Mathf.Abs(UnityEngine.Mathf.DeltaAngle(before,after));
        Require(error<.02f,"Battle rotated away from its screen orientation: "+error);
        Require((camera.transform.position-position).sqrMagnitude<1e-12f,"Battle entry moved the globe camera.");
        controller.ExitBattle();
        Require(camera.enabled && globe.GetComponent<UnityEngine.MeshRenderer>().enabled && !controller.IsActive,"Failed to restore globe visibility.");
        Require((camera.transform.position-position).sqrMagnitude<1e-12f && UnityEngine.Quaternion.Angle(camera.transform.rotation,rotation)<.001f,"Return changed the globe pose.");
        Require(UnityEngine.Mathf.Abs(orbit.TurnRotationSpeed-1.77f)<.0001f,"Battle reset live unsaved camera settings.");
        Require(globe.SelectedSubtileId==cell.Id,"Battle lost the selected subtile.");
        Require(globe.AttackTargetSubtileIndex==target,"Battle lost the attack target.");
        orbit.TurnRotationSpeed=liveSpeed;
        reports.Add(new{distance=view.distance,orientationErrorDegrees=error,core=field.CoreHexCount,total=field.Hexes.Count});
    }
    var shader=controller.battlefieldMaterial.shader;
    foreach(var message in UnityEditor.ShaderUtil.GetShaderMessages(shader))Require(message.severity.ToString()!="Error",message.message);
    return new{result="PASS",views=reports,cameraAndLiveSettingsRestored=true};
}
finally
{
    controller.ExitBattle();orbit.ApplySettings(oldSettings);orbit.SetView(oldOrientation,oldDistance);
    if(oldCell.HasValue)globe.SelectSubtile(oldCell.Value);else if(oldTile>=0)globe.SelectTile(oldTile);else globe.ClearSelection();
    if(oldTarget.HasValue)globe.TrySetAttackTarget(oldTarget.Value);
}
