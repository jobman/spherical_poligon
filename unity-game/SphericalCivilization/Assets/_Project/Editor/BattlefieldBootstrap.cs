using System;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using SphericalCivilization.Battle;

namespace SphericalCivilization.Editor
{
    public static class BattlefieldBootstrap
    {
        public static void Install(GlobePreview globe)
        {
            if (Application.isPlaying) throw new InvalidOperationException("Install the battle preview outside Play Mode.");
            var shader = Shader.Find("SphericalCivilization/Battlefield");
            if (shader == null) throw new InvalidOperationException("Battlefield shader is missing.");
            const string path = "Assets/_Project/Materials/Battlefield.mat";
            var material = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (material == null) { material = new Material(shader); AssetDatabase.CreateAsset(material, path); }
            var controller = globe.GetComponent<BattlefieldController>();
            if (controller == null) controller = globe.gameObject.AddComponent<BattlefieldController>();
            controller.battlefieldMaterial = material;
            EditorUtility.SetDirty(controller); EditorSceneManager.MarkSceneDirty(globe.gameObject.scene);
            AssetDatabase.SaveAssets();
        }
    }
}
