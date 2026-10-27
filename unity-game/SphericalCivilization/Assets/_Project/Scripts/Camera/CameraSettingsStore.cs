using System;
using System.IO;
using System.Text;
using UnityEngine;

namespace SphericalCivilization
{
    public static class CameraSettingsStore
    {
        public static string SettingsPath => Path.Combine(Application.persistentDataPath, "CameraSettings.json");

        public static bool TryLoad(string path, CameraSettings defaults, out CameraSettings settings, out string error)
        {
            settings = JsonUtility.FromJson<CameraSettings>(JsonUtility.ToJson(defaults));
            error = null;
            try
            {
                if (!File.Exists(path)) return false;
                string json = File.ReadAllText(path);
                if (string.IsNullOrWhiteSpace(json) || !json.TrimStart().StartsWith("{"))
                    throw new ArgumentException("Expected a settings JSON object.");
                JsonUtility.FromJsonOverwrite(json, settings);
                return true;
            }
            catch (Exception exception) when (exception is IOException || exception is UnauthorizedAccessException || exception is ArgumentException)
            {
                settings = defaults;
                error = exception.Message;
                return false;
            }
        }

        public static void Save(string path, CameraSettings settings)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            string temporary = path + ".tmp";
            try
            {
                File.WriteAllText(temporary, JsonUtility.ToJson(settings, true), new UTF8Encoding(false));
                if (File.Exists(path)) File.Replace(temporary, path, null);
                else File.Move(temporary, path);
            }
            finally
            {
                if (File.Exists(temporary)) File.Delete(temporary);
            }
        }
    }
}
