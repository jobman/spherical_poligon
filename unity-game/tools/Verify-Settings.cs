// Data-only persistence checks; does not open menus or exercise UI controls.
var orbit = UnityEngine.Object.FindFirstObjectByType<SphericalCivilization.OrbitCamera>();
var original = orbit.GetSettings();
string directory = System.IO.Path.GetFullPath(System.IO.Path.Combine(UnityEngine.Application.dataPath,
    "../Library/SettingsVerification-" + System.Guid.NewGuid().ToString("N")));
string path = System.IO.Path.Combine(directory, "CameraSettings.json");
void Require(bool condition, string message) { if (!condition) throw new System.Exception(message); }
try
{
    Require(!SphericalCivilization.CameraSettingsStore.TryLoad(path, original, out var missing, out var missingError) && missingError == null,
        "Missing preferences must use defaults without an error.");
    Require(missing.turnRotationSpeed == original.turnRotationSpeed, "Missing file discarded defaults.");
    var chosen = UnityEngine.JsonUtility.FromJson<SphericalCivilization.CameraSettings>(UnityEngine.JsonUtility.ToJson(original));
    chosen.turnRotationSpeed = 3.27f;
    chosen.backgroundRotationSpeed = 1.23f;
    chosen.keyboardRotationSpeed = 1.75f;
    chosen.scrollSpeed = 2.1f;
    chosen.rotationInertiaHalfLife = 0.17f;
    chosen.scrollInertiaHalfLife = 0.26f;
    SphericalCivilization.CameraSettingsStore.Save(path, chosen);
    Require(SphericalCivilization.CameraSettingsStore.TryLoad(path, original, out var loaded, out var error) && error == null,
        "Saved preferences could not be read.");
    Require(UnityEngine.JsonUtility.ToJson(chosen) == UnityEngine.JsonUtility.ToJson(loaded), "Saved values changed during reload.");
    chosen.turnRotationSpeed = 2.64f;
    SphericalCivilization.CameraSettingsStore.Save(path, chosen);
    Require(SphericalCivilization.CameraSettingsStore.TryLoad(path, original, out loaded, out error) && loaded.turnRotationSpeed == 2.64f &&
        !System.IO.File.Exists(path + ".tmp"), "Atomic replacement did not save the new defaults.");
    orbit.ApplySettings(loaded);
    Require(orbit.TurnRotationSpeed == 2.64f && orbit.KeyboardRotationSpeed == 1.75f && orbit.ScrollInertiaHalfLife == 0.26f,
        "Loaded preferences were not applied to the camera.");
    System.IO.File.WriteAllText(path, "{\"turnRotationSpeed\": 4.12}");
    Require(SphericalCivilization.CameraSettingsStore.TryLoad(path, original, out loaded, out error) &&
        loaded.turnRotationSpeed == 4.12f && loaded.scrollSpeed == original.scrollSpeed && loaded.rotationInertiaHalfLife == original.rotationInertiaHalfLife,
        "A partial settings file lost defaults for missing fields.");
    System.IO.File.WriteAllText(path, "broken");
    Require(!SphericalCivilization.CameraSettingsStore.TryLoad(path, original, out loaded, out error) && error != null &&
        loaded.turnRotationSpeed == original.turnRotationSpeed, "A damaged settings file did not fall back safely.");
    orbit.ApplySettings(original);
    orbit.ApplySettings(new SphericalCivilization.CameraSettings
    {
        backgroundRotationSpeed = -20f, keyboardRotationSpeed = 100f, turnRotationSpeed = float.NaN,
        scrollSpeed = float.PositiveInfinity, rotationInertiaHalfLife = -1f, scrollInertiaHalfLife = 20f
    });
    Require(orbit.BackgroundRotationSpeed == 0.1f && orbit.KeyboardRotationSpeed == 5f &&
        orbit.TurnRotationSpeed == original.turnRotationSpeed && orbit.ScrollSpeed == original.scrollSpeed &&
        orbit.RotationInertiaHalfLife == 0f && orbit.ScrollInertiaHalfLife == 1f, "Invalid settings were not sanitized.");
    return new { result = "PASS", checks = new[] { "missing file", "save/load all six values", "atomic overwrite", "apply saved preferences",
        "missing-field defaults", "damaged-file fallback", "safe numeric limits" }, actualUserSettingsChanged = false };
}
finally
{
    orbit.ApplySettings(original);
    if (System.IO.File.Exists(path)) System.IO.File.Delete(path);
    if (System.IO.File.Exists(path + ".tmp")) System.IO.File.Delete(path + ".tmp");
    if (System.IO.Directory.Exists(directory)) System.IO.Directory.Delete(directory);
}
