// Statement block for the official Pipeline `script eval_file` command.
var globe = UnityEngine.Object.FindFirstObjectByType<SphericalCivilization.GlobePreview>();
if (globe == null || globe.TileCount != 642 || globe.Topology == null || globe.TriangleCount != globe.Topology.Edges.Count * 2)
    throw new System.Exception("The reference globe did not rebuild correctly.");
var data = UnityEngine.JsonUtility.FromJson<SphericalCivilization.ReferenceWorld>(globe.worldAsset.text);
UnityEngine.Physics.SyncTransforms();
var failures = new System.Collections.Generic.List<int>();
foreach (var tile in data.tiles)
{
    var radial = tile.center.normalized;
    if (!globe.TrySelectRay(new UnityEngine.Ray(radial * 2f, -radial)) ||
        globe.SelectedTileId != tile.id)
        failures.Add(tile.id);
}
if (failures.Count != 0)
    throw new System.Exception("Incorrect cell picking: " + string.Join(",", failures));

var camera = UnityEngine.Camera.main;
if (camera == null || !globe.TrySelectRay(camera.ViewportPointToRay(new UnityEngine.Vector3(0.5f, 0.5f, 0f))))
    throw new System.Exception("The camera cannot pick the visible center of the globe.");
var pipeline = UnityEngine.Rendering.GraphicsSettings.currentRenderPipeline as
    UnityEngine.Rendering.Universal.UniversalRenderPipelineAsset;
var cameraData = camera.GetComponent<UnityEngine.Rendering.Universal.UniversalAdditionalCameraData>();
var volume = UnityEngine.Object.FindFirstObjectByType<UnityEngine.Rendering.Volume>();
if (pipeline == null || !pipeline.supportsHDR || !cameraData.renderPostProcessing ||
    volume?.sharedProfile == null || (cameraData.volumeLayerMask.value & (1 << volume.gameObject.layer)) == 0)
    throw new System.Exception("The URP visual baseline is incomplete.");
foreach (var message in UnityEditor.ShaderUtil.GetShaderMessages(globe.terrainMaterial.shader))
    if (message.severity.ToString() == "Error") throw new System.Exception(message.message);

return new
{
    tiles = globe.TileCount,
    triangles = globe.TriangleCount,
    cellsPickedCorrectly = data.tiles.Length,
    selectedCenterTile = globe.SelectedTileId,
    urp = true,
    hdr = pipeline.supportsHDR,
    postProcessing = cameraData.renderPostProcessing,
    playing = UnityEngine.Application.isPlaying,
    frameCount = UnityEngine.Time.frameCount
};
