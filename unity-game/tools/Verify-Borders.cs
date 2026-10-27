// Statement block for Pipeline `script eval_file`; checks geometry and actual URP pixels.
var globe = UnityEngine.Object.FindFirstObjectByType<SphericalCivilization.GlobePreview>();
var orbit = UnityEngine.Object.FindFirstObjectByType<SphericalCivilization.OrbitCamera>();
var camera = UnityEngine.Camera.main;
var world = UnityEngine.JsonUtility.FromJson<SphericalCivilization.ReferenceWorld>(globe.worldAsset.text);
var mesh = globe.GetComponent<UnityEngine.MeshFilter>().sharedMesh;
var renderer = globe.GetComponent<UnityEngine.MeshRenderer>();
var oldProperties = new UnityEngine.MaterialPropertyBlock();
renderer.GetPropertyBlock(oldProperties);
var oldOrientation = orbit.Orientation;
float oldDistance = orbit.distance;
int oldSelection = globe.SelectedTileId;
var oldTarget = camera.targetTexture;
var oldActive = UnityEngine.RenderTexture.active;
float oldAspect = camera.aspect;
var target = UnityEngine.RenderTexture.GetTemporary(960, 640, 24, UnityEngine.RenderTextureFormat.ARGB32);
var readback = new UnityEngine.Texture2D(960, 640, UnityEngine.TextureFormat.RGBA32, false);
void Require(bool condition, string message) { if (!condition) throw new System.Exception(message); }
string PointKey(UnityEngine.Vector3 p) => System.FormattableString.Invariant($"{p.x:F6},{p.y:F6},{p.z:F6}");
string EdgeKey(UnityEngine.Vector3 a, UnityEngine.Vector3 b)
{
    string x = PointKey(a), y = PointKey(b);
    return string.CompareOrdinal(x, y) < 0 ? x + ";" + y : y + ";" + x;
}
try
{
    Require(globe.GetComponentsInChildren<UnityEngine.Renderer>().Length == 1,
        "Borders or selection still use separate, potentially offset geometry.");
    var expected = new System.Collections.Generic.Dictionary<string, int>();
    var segments = new System.Collections.Generic.Dictionary<string, (UnityEngine.Vector3 a, UnityEngine.Vector3 b)>();
    foreach (var boundary in globe.Topology.Boundaries)
        for (int i = 0; i < boundary.Vertices.Length - 1; i++)
        {
            var a = globe.Topology.Vertices[boundary.Vertices[i]];
            var b = globe.Topology.Vertices[boundary.Vertices[i + 1]];
            string key = EdgeKey(a, b);
            expected[key] = 2;
            segments[key] = (a, b);
        }
    int expectedCount=0;
    foreach(var boundary in globe.Topology.Boundaries)
    {
        int a=globe.Topology.TilesById[boundary.FirstTileId].Corners.Length==5?globe.PentagonSubtileCount:globe.HexagonSubtileCount;
        int b=globe.Topology.TilesById[boundary.SecondTileId].Corners.Length==5?globe.PentagonSubtileCount:globe.HexagonSubtileCount;
        expectedCount+=System.Math.Min(SphericalCivilization.World.OperationalSubdivision.GetEdgeSegments(a),SphericalCivilization.World.OperationalSubdivision.GetEdgeSegments(b))+1;
    }
    Require(expected.Count == expectedCount, "The reference globe lost shared edge segments.");
    foreach (int owners in expected.Values) Require(owners == 2, "A shared edge does not have two owners.");

    var borderData = new System.Collections.Generic.List<UnityEngine.Vector4>();
    mesh.GetUVs(2, borderData);
    var positions = mesh.vertices;
    var indices = mesh.triangles;
    var drawn = new System.Collections.Generic.Dictionary<string, int>();
    for (int triangle = 0; triangle < indices.Length; triangle += 3)
    {
        var flags = borderData[indices[triangle]];
        for (int edge = 0; edge < 3; edge++)
        {
            if (flags[edge] < 0.5f) continue;
            var a = positions[indices[triangle + (edge + 1) % 3]];
            var b = positions[indices[triangle + (edge + 2) % 3]];
            string key = EdgeKey(a, b);
            Require(expected.ContainsKey(key), "A border is offset from the surface perimeter, or a fan diagonal is visible.");
            drawn[key] = drawn.TryGetValue(key, out int owners) ? owners + 1 : 1;
        }
    }
    Require(drawn.Count == expected.Count, "Some polygon borders are missing.");
    foreach (var edge in expected) Require(drawn[edge.Key] == edge.Value, "A shared border is not drawn by both neighbors.");

    // Render the very same surface with and without its border, then check darkening
    // at projected shared edges. A raised line fails this at close, oblique views.
    camera.targetTexture = target;
    camera.aspect = 1.5f;
    UnityEngine.Color32[] Render(float width)
    {
        var properties = new UnityEngine.MaterialPropertyBlock();
        renderer.GetPropertyBlock(properties);
        properties.SetFloat("_SelectedTileId", -1f);
        properties.SetFloat("_SelectedSubtileId", -1f);
        properties.SetFloat("_SubtileVisibility", 0f);
        properties.SetFloat("_BorderWidth", width);
        renderer.SetPropertyBlock(properties);
        camera.Render();
        UnityEngine.RenderTexture.active = target;
        readback.ReadPixels(new UnityEngine.Rect(0, 0, 960, 640), 0, 0);
        readback.Apply();
        return readback.GetPixels32();
    }
    var reports = new System.Collections.Generic.List<object>();
    foreach (var view in new[]
    {
        (name: "close oblique", rotation: oldOrientation, distance: 1.1f),
        (name: "middle distance", rotation: UnityEngine.Quaternion.Euler(20f, 35f, 0f), distance: 2f),
        (name: "whole globe", rotation: UnityEngine.Quaternion.Euler(20f, 35f, 0f), distance: 7f),
        (name: "close pole", rotation: UnityEngine.Quaternion.Euler(89f, -80f, 30f), distance: 1.1f)
    })
    {
        orbit.SetView(view.rotation, view.distance);
        UnityEngine.Physics.SyncTransforms();
        var plain = Render(0f);
        var bordered = Render(3f);
        int checkedSamples = 0, missed = 0;
        string missedDetail = "";
        foreach (var edge in segments.Values)
            foreach (float fraction in new[] { 0.25f, 0.5f, 0.75f })
            {
                var localPoint = UnityEngine.Vector3.Lerp(edge.a, edge.b, fraction);
                var point = globe.transform.TransformPoint(localPoint);
                var screen = camera.WorldToScreenPoint(point);
                if (screen.z <= camera.nearClipPlane || screen.x < 3f || screen.x >= 957f || screen.y < 3f || screen.y >= 637f) continue;
                var ray = new UnityEngine.Ray(camera.transform.position, point - camera.transform.position);
                // At the silhouette a geometric edge can cover less than one sample,
                // even with MSAA. Only compare seams that have a resolvable surface.
                if (UnityEngine.Vector3.Dot(globe.transform.TransformDirection(localPoint.normalized),
                        -ray.direction.normalized) < 0.1f) continue;
                if (!UnityEngine.Physics.Raycast(ray, out var hit) || hit.collider != globe.GetComponent<UnityEngine.MeshCollider>() ||
                    UnityEngine.Vector3.Distance(hit.point, point) > 0.000001f) continue;
                int bestDarkening = 0;
                for (int y = (int)screen.y - 1; y <= (int)screen.y + 1; y++)
                    for (int x = (int)screen.x - 1; x <= (int)screen.x + 1; x++)
                    {
                        int index = y * 960 + x;
                        int before = plain[index].r + plain[index].g + plain[index].b;
                        int after = bordered[index].r + bordered[index].g + bordered[index].b;
                        bestDarkening = System.Math.Max(bestDarkening, before - after);
                    }
                checkedSamples++;
                if (bestDarkening < 12) { missed++; missedDetail = $" screen={screen.x},{screen.y}, darkening={bestDarkening}"; }
            }
        Require(checkedSamples >= 3 && missed == 0,
            $"Visible borders do not align with color seams at {view.name}: {missed}/{checkedSamples} missed samples.{missedDetail}");
        reports.Add(new { view = view.name, samples = checkedSamples, missed });
    }
    globe.SelectTile(world.tiles[0].id);
    var selection = new UnityEngine.MaterialPropertyBlock();
    renderer.GetPropertyBlock(selection);
    Require(selection.GetFloat("_SelectedTileId") == world.tiles[0].id, "Selection did not reach the surface shader.");
    globe.ClearSelection();
    renderer.GetPropertyBlock(selection);
    Require(selection.GetFloat("_SelectedTileId") == -1f, "Selection was not cleared.");
    return new { sharedEdges = expected.Count, surfaceTriangles = mesh.triangles.Length / 3,
        surfaceRenderers = 1, extraBorderGeometry = false, pixelChecks = reports, selection = "PASS" };
}
finally
{
    camera.targetTexture = oldTarget;
    if (oldTarget == null) camera.ResetAspect(); else camera.aspect = oldAspect;
    UnityEngine.RenderTexture.active = oldActive;
    orbit.SetView(oldOrientation, oldDistance);
    if (oldSelection < 0) globe.ClearSelection(); else globe.SelectTile(oldSelection);
    renderer.SetPropertyBlock(oldProperties);
    UnityEngine.RenderTexture.ReleaseTemporary(target);
    UnityEngine.Object.DestroyImmediate(readback);
}
