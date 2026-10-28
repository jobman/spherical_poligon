using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem.UI;
using UnityEngine.Rendering.Universal;
using UnityEngine.SceneManagement;
using UnityEngine.UIElements;
using SphericalCivilization.Battle;

namespace SphericalCivilization.Editor
{
    public static class BattlefieldLabBootstrap
    {
        public const string ScenePath = "Assets/_Project/Scenes/BattlefieldLab.unity";
        [MenuItem("Spherical Civilization/Open battlefield lab")]
        public static void Open()
        {
            if (Application.isPlaying)
            {
                var globe = UnityEngine.Object.FindFirstObjectByType<GlobePreview>();
                if (globe != null) BattlefieldLab.OpenFromGlobe(globe); else SceneManager.LoadScene(BattlefieldLab.SceneName);
                return;
            }
            var active = SceneManager.GetActiveScene();
            if (active.isDirty && !string.IsNullOrEmpty(active.path)) EditorSceneManager.SaveScene(active);
            if (File.Exists(ScenePath)) EditorSceneManager.OpenScene(ScenePath); else CreateScene();
        }

        public static string CreateScene()
        {
            if (Application.isPlaying) throw new InvalidOperationException("Create the lab outside Play Mode.");
            var active = SceneManager.GetActiveScene();
            if (active.isDirty && !string.IsNullOrEmpty(active.path)) EditorSceneManager.SaveScene(active);
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            const string root = "Assets/_Project/";
            var tree = AssetDatabase.LoadAssetAtPath<VisualTreeAsset>(root + "UI/BattlefieldLab/BattlefieldLab.uxml");
            var settings = AssetDatabase.LoadAssetAtPath<PanelSettings>(root + "Settings/CameraPanelSettings.asset");
            var world = AssetDatabase.LoadAssetAtPath<TextAsset>(root + "Data/ReferenceWorld.json");
            var material = AssetDatabase.LoadAssetAtPath<Material>(root + "Materials/Battlefield.mat");
            if (tree == null || settings == null || world == null || material == null) throw new InvalidOperationException("Battle lab source assets are missing.");
            var cameraObject = new GameObject("Battle lab camera"); cameraObject.tag = "MainCamera";
            var camera = cameraObject.AddComponent<Camera>();
            camera.transform.position = new Vector3(0, 0, -1); camera.orthographic = true; camera.orthographicSize = .08f;
            camera.nearClipPlane = .1f; camera.farClipPlane = 5; camera.rect = new Rect(0, .27f, 1, .57f);
            camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = new Color(.025f, .037f, .05f);
            camera.allowHDR = false; camera.GetUniversalAdditionalCameraData().renderPostProcessing = false;
            cameraObject.AddComponent<AudioListener>();
            var ui = new GameObject("Battlefield lab"); var document = ui.AddComponent<UIDocument>();
            document.panelSettings = settings; document.visualTreeAsset = tree;
            var lab = ui.AddComponent<BattlefieldLab>(); lab.worldAsset = world; lab.previewMaterial = material; lab.previewCamera = camera;
            var events = new GameObject("UI Event System").AddComponent<EventSystem>();
            events.gameObject.AddComponent<InputSystemUIInputModule>().AssignDefaultActions();
            EditorSceneManager.SaveScene(scene, ScenePath);
            var scenes = new List<EditorBuildSettingsScene>(EditorBuildSettings.scenes);
            if (!scenes.Exists(s => s.path == ScenePath)) scenes.Add(new EditorBuildSettingsScene(ScenePath, true));
            EditorBuildSettings.scenes = scenes.ToArray(); AssetDatabase.SaveAssets();
            return ScenePath;
        }
    }
}
