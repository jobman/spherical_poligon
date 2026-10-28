using System;
using System.IO;
using System.Text;
using UnityEngine;
using SphericalCivilization.World;

namespace SphericalCivilization.Battle
{
    [Serializable]
    public sealed class BattleSettings
    {
        public const float MinRadius = .00001f, MaxRadius = .02f;
        public float hexWorldRadius;

        public bool IsValid => !float.IsNaN(hexWorldRadius) && !float.IsInfinity(hexWorldRadius) &&
            hexWorldRadius >= MinRadius && hexWorldRadius <= MaxRadius;

        public static float ReferenceRadius(OperationalWorld world)
        {
            double area = 0;
            foreach (var tile in world.Tiles)
            {
                var origin = world.Vertices[tile.Corners[0]];
                for (int i = 1; i + 1 < tile.Corners.Length; i++)
                    area += Vector3.Cross(world.Vertices[tile.Corners[i]] - origin, world.Vertices[tile.Corners[i + 1]] - origin).magnitude * .5;
            }
            return (float)Math.Sqrt(2 * area / world.Subtiles.Count / (900 * 2.598076211353316));
        }
    }

    public static class BattleSettingsStore
    {
        public static string SettingsPath => Path.Combine(Application.persistentDataPath, "BattleSettings.json");
        public static bool TryLoad(out BattleSettings settings) => TryLoad(SettingsPath, out settings);
        public static bool TryLoad(string path, out BattleSettings settings)
        {
            settings = null;
            try
            {
                if (!File.Exists(path)) return false;
                var candidate = JsonUtility.FromJson<BattleSettings>(File.ReadAllText(path));
                if (candidate == null || !candidate.IsValid) return false;
                settings = candidate; return true;
            }
            catch (Exception e) when (e is IOException || e is UnauthorizedAccessException || e is ArgumentException) { return false; }
        }

        public static void Save(string path, BattleSettings settings)
        {
            if (settings == null || !settings.IsValid) throw new ArgumentOutOfRangeException(nameof(settings));
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
