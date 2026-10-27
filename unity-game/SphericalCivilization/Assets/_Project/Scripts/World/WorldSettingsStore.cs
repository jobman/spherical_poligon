using System;
using System.IO;
using System.Text;
using UnityEngine;
using SphericalCivilization.World;

namespace SphericalCivilization
{
    [Serializable]
    public sealed class WorldSettings
    {
        public int subtilesPerTile = 37;
        public int hexagonSubtilesPerTile;
        public int pentagonSubtilesPerTile;
        public uint seed = 1337;

        public void Normalize()
        {
            subtilesPerTile = Mathf.Clamp(subtilesPerTile, OperationalSubdivision.MinSubtilesPerTile, OperationalSubdivision.MaxSubtilesPerTile);
            hexagonSubtilesPerTile = hexagonSubtilesPerTile == 0 ? subtilesPerTile : Mathf.Clamp(hexagonSubtilesPerTile, OperationalSubdivision.MinSubtilesPerTile, OperationalSubdivision.MaxSubtilesPerTile);
            pentagonSubtilesPerTile = pentagonSubtilesPerTile == 0 ? subtilesPerTile : Mathf.Clamp(pentagonSubtilesPerTile, OperationalSubdivision.MinSubtilesPerTile, OperationalSubdivision.MaxSubtilesPerTile);
        }
    }

    public static class WorldSettingsStore
    {
        public static string SettingsPath => Path.Combine(Application.persistentDataPath, "WorldSettings.json");

        public static bool TryLoad(out WorldSettings settings) => TryLoad(SettingsPath, out settings);

        public static bool TryLoad(string path, out WorldSettings settings)
        {
            settings = new WorldSettings();
            try
            {
                if (!File.Exists(path)) return false;
                string json = File.ReadAllText(path);
                if (string.IsNullOrWhiteSpace(json) || !json.TrimStart().StartsWith("{")) return false;
                JsonUtility.FromJsonOverwrite(json, settings);
                settings.Normalize();
                return true;
            }
            catch (Exception exception) when (exception is IOException || exception is UnauthorizedAccessException || exception is ArgumentException)
            {
                settings = new WorldSettings();
                return false;
            }
        }

        public static void Save(string path, WorldSettings settings)
        {
            if (settings.subtilesPerTile < OperationalSubdivision.MinSubtilesPerTile || settings.subtilesPerTile > OperationalSubdivision.MaxSubtilesPerTile)
                throw new ArgumentOutOfRangeException(nameof(settings));
            settings.Normalize();
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            string temporary = path + ".tmp";
            try
            {
                File.WriteAllText(temporary, JsonUtility.ToJson(settings, true), new UTF8Encoding(false));
                if (File.Exists(path)) File.Replace(temporary, path, null); else File.Move(temporary, path);
            }
            finally { if (File.Exists(temporary)) File.Delete(temporary); }
        }
    }
}
