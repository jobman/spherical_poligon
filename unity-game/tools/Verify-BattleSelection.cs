// Data and game API checks only; no UI controls or mouse/keyboard events.
var globe=UnityEngine.Object.FindFirstObjectByType<SphericalCivilization.GlobePreview>();
var orbit=UnityEngine.Object.FindFirstObjectByType<SphericalCivilization.OrbitCamera>();
var controller=globe.GetComponent<SphericalCivilization.Battle.BattlefieldController>();
var world=globe.Topology;
var oldOrientation=orbit.Orientation;float oldDistance=orbit.distance;
int oldTile=globe.SelectedTileId;long? oldCell=globe.SelectedSubtileId,oldTarget=globe.AttackTargetSubtileId;
void Require(bool value,string message){if(!value)throw new System.Exception(message);}
try
{
    globe.ClearSelection();
    Require(!controller.EnterFromSelection(),"Battle opened without a chosen pair.");
    Require(!globe.TrySetAttackTarget(world.Subtiles[0].Id),"Target accepted without a source.");
    orbit.SetView(UnityEngine.Quaternion.Euler(20,35,0),3.3f);UnityEngine.Physics.SyncTransforms();
    var camera=orbit.GetComponent<UnityEngine.Camera>();
    var ray=camera.ViewportPointToRay(new UnityEngine.Vector3(.5f,.5f));
    Require(globe.TryGetSubtile(ray,out var picked) && globe.TrySelectRay(ray),"Source ray did not select a subtile.");
    Require(globe.SelectedSubtileId==picked.Id,"Distant selection silently picked a parent tile.");
    Require(!controller.EnterFromSelection(),"Battle auto-chose a target.");

    int source=-1,target=-1;
    for(int i=0;i<world.Subtiles.Count && source<0;i++)foreach(int n in world.Subtiles[i].Neighbors)
        if(world.Subtiles[n].ParentTileId!=world.Subtiles[i].ParentTileId){source=i;target=n;break;}
    Require(source>=0,"No cross-parent pair in reference world.");
    globe.SelectSubtile(world.Subtiles[source].Id);
    Require(globe.TrySetAttackTarget(world.Subtiles[target].Id),"Cross-parent neighbor was rejected.");
    var properties=new UnityEngine.MaterialPropertyBlock();globe.GetComponent<UnityEngine.MeshRenderer>().GetPropertyBlock(properties);
    Require(properties.GetFloat("_AttackTargetSubtileId")==target,"Target highlight has the wrong region.");
    Require(controller.EnterFromSelection(),"Valid pair did not open.");
    Require(controller.Field.FirstSubtileIndex==source && controller.Field.SecondSubtileIndex==target,"Battle used a different pair.");
    controller.ExitBattle();
    Require(globe.SelectedSubtileIndex==source && globe.AttackTargetSubtileIndex==target,"Return lost the chosen pair.");

    int nonNeighbor=0;
    while(nonNeighbor==source || System.Array.IndexOf(world.Subtiles[source].Neighbors,nonNeighbor)>=0)nonNeighbor++;
    Require(!globe.TrySetAttackTarget(world.Subtiles[nonNeighbor].Id) && globe.AttackTargetSubtileIndex<0,"Non-neighbor left a stale attack target.");
    Require(!controller.EnterFromSelection(),"Invalid target launched the previous battle.");
    Require(!globe.TrySetAttackTarget(world.Subtiles[source].Id),"Self-attack was accepted.");
    Require(globe.TrySetAttackTarget(world.Subtiles[target].Id),"Failed to reselect target.");
    globe.SelectSubtile(world.Subtiles[target].Id);
    Require(globe.AttackTargetSubtileIndex<0 && !controller.EnterFromSelection(),"Changing source retained the target.");
    Require(globe.TrySetAttackTarget(world.Subtiles[source].Id),"Reverse neighbor relation was rejected.");
    Require(!globe.TrySetAttackTargetRay(new UnityEngine.Ray(new UnityEngine.Vector3(20,20,20),UnityEngine.Vector3.up)) && globe.AttackTargetSubtileIndex<0,"Empty-space click retained a target.");
    Require(globe.TrySetAttackTarget(world.Subtiles[source].Id),"Failed to prepare clear test.");
    globe.ClearSelection();Require(globe.AttackTargetSubtileIndex<0 && !controller.EnterFromSelection(),"Clear selection retained an attack.");
    globe.SelectSubtile(world.Subtiles[source].Id);globe.TrySetAttackTarget(world.Subtiles[target].Id);
    globe.Rebuild();Require(globe.SelectedSubtileIndex<0 && globe.AttackTargetSubtileIndex<0 && !controller.EnterFromSelection(),"Regeneration reused stale selection indices.");
    foreach(var message in UnityEditor.ShaderUtil.GetShaderMessages(globe.terrainMaterial.shader))Require(message.severity.ToString()!="Error",message.message);
    return new{result="PASS",explicitPair=new[]{source,target},crossParent=true,invalidTargetsBlocked=true,regenerationClearsSelection=true};
}
finally
{
    controller.ExitBattle();orbit.SetView(oldOrientation,oldDistance);
    if(oldCell.HasValue)globe.SelectSubtile(oldCell.Value);else if(oldTile>=0)globe.SelectTile(oldTile);else globe.ClearSelection();
    if(oldTarget.HasValue)globe.TrySetAttackTarget(oldTarget.Value);
}
