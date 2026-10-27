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

namespace SphericalCivilization.Editor
{
    public static class SubdivisionLabBootstrap
    {
        public const string ScenePath = "Assets/_Project/Scenes/SubdivisionLab.unity";

        [MenuItem("Spherical Civilization/Open subdivision lab")]
        public static void Open()
        {
            if (Application.isPlaying) { SceneManager.LoadScene("SubdivisionLab"); return; }
            var active = SceneManager.GetActiveScene();
            if (active.isDirty && !string.IsNullOrEmpty(active.path)) EditorSceneManager.SaveScene(active);
            if (File.Exists(ScenePath)) EditorSceneManager.OpenScene(ScenePath);
            else CreateScene();
        }

        public static string CreateScene()
        {
            if (Application.isPlaying) throw new InvalidOperationException("Create the lab scene outside Play Mode.");
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            const string root = "Assets/_Project/";
            var tree = AssetDatabase.LoadAssetAtPath<VisualTreeAsset>(root + "UI/SubdivisionLab/SubdivisionLab.uxml");
            var settings = AssetDatabase.LoadAssetAtPath<PanelSettings>(root + "Settings/CameraPanelSettings.asset");
            var world = AssetDatabase.LoadAssetAtPath<TextAsset>(root + "Data/ReferenceWorld.json");
            var shader = Shader.Find("SphericalCivilization/VertexTerrain");
            if (tree == null || settings == null || world == null || shader == null) throw new InvalidOperationException("Lab source assets are missing.");
            string materialPath = root + "Materials/SubdivisionLab.mat";
            var material = AssetDatabase.LoadAssetAtPath<Material>(materialPath);
            if (material == null) { material = new Material(shader); AssetDatabase.CreateAsset(material, materialPath); }
            material.SetFloat("_SubtileVisibility", 1); material.SetFloat("_BorderWidth", 2);
            material.SetFloat("_SelectedTileId", -1); material.SetFloat("_SelectedSubtileId", -1);
            EditorUtility.SetDirty(material);

            var cameraObject = new GameObject("Comparison camera"); cameraObject.tag = "MainCamera";
            var camera = cameraObject.AddComponent<Camera>();
            camera.transform.position = new Vector3(0, 0, -10); camera.orthographic = true; camera.orthographicSize = 2.45f;
            camera.rect = new Rect(0, 0.27f, 1, 0.6f); camera.nearClipPlane = 0.1f; camera.farClipPlane = 30;
            camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = new Color(0.025f, 0.045f, 0.065f);
            camera.allowHDR = false; camera.GetUniversalAdditionalCameraData().renderPostProcessing = false;
            cameraObject.AddComponent<AudioListener>();
            var light = new GameObject("Preview light").AddComponent<Light>(); light.type = LightType.Directional; light.intensity = 1;
            light.color = Color.white; light.transform.rotation = Quaternion.identity; RenderSettings.sun = light;
            var surface = new GameObject("Six sample tiles").AddComponent<MeshFilter>();
            surface.gameObject.AddComponent<MeshRenderer>().sharedMaterial = material;
            var ui = new GameObject("Subdivision lab"); var document = ui.AddComponent<UIDocument>();
            document.panelSettings = settings; document.visualTreeAsset = tree;
            var lab = ui.AddComponent<SubdivisionLab>(); lab.worldAsset = world; lab.previewMaterial = material;
            lab.previewSurface = surface; lab.previewCamera = camera;
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
