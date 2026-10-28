using System;
using System.IO;
using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.UIElements;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem.UI;

namespace SphericalCivilization.Editor
{
    public static class ProjectBootstrap
    {
        private const string Root = "Assets/_Project";

        [MenuItem("Spherical Civilization/Create globe preview")]
        public static void CreateFromMenu() => CreateGlobeScene();

        public static string CreateGlobeScene()
        {
            var world = AssetDatabase.LoadAssetAtPath<TextAsset>(Root + "/Data/ReferenceWorld.json");
            if (world == null) throw new InvalidOperationException("Export the reference world first.");
            var terrainShader = Shader.Find("SphericalCivilization/VertexTerrain");
            if (terrainShader == null)
                throw new InvalidOperationException("Required URP shaders are missing.");

            foreach (var directory in new[] { "/Materials", "/Scenes", "/Settings" })
                Directory.CreateDirectory(Root + directory);
            AssetDatabase.Refresh();
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            QualitySettings.SetQualityLevel(QualitySettings.names.Length - 1, true);
            var pipeline = GraphicsSettings.currentRenderPipeline as UniversalRenderPipelineAsset;
            if (pipeline == null) throw new InvalidOperationException("URP must be active.");
            pipeline.supportsHDR = true;

            var globe = new GameObject("Strategic globe").AddComponent<GlobePreview>();
            globe.worldAsset = world;
            globe.terrainMaterial = MaterialAsset("Terrain", terrainShader, Color.white);
            globe.Rebuild();

            var cameraObject = new GameObject("Main Camera");
            cameraObject.tag = "MainCamera";
            var camera = cameraObject.AddComponent<Camera>();
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = new Color(0.018f, 0.035f, 0.06f);
            camera.fieldOfView = 45f;
            camera.nearClipPlane = 0.03f;
            camera.farClipPlane = 50f;
            camera.allowHDR = true;
            var cameraData = camera.GetUniversalAdditionalCameraData();
            cameraData.renderPostProcessing = true;
            cameraData.volumeLayerMask = 1;
            cameraObject.AddComponent<AudioListener>();
            var orbit = cameraObject.AddComponent<OrbitCamera>();
            orbit.ApplyView();
            EnsureCameraControls(orbit);
            BattlefieldBootstrap.Install(globe);

            var sun = new GameObject("Sun").AddComponent<Light>();
            sun.type = LightType.Directional;
            sun.intensity = 1.15f;
            sun.color = new Color(1f, 0.97f, 0.9f);
            sun.shadows = LightShadows.Soft;
            sun.transform.rotation = Quaternion.Euler(38f, -45f, 0f);
            RenderSettings.sun = sun;

            var volume = new GameObject("Global post-processing").AddComponent<Volume>();
            volume.isGlobal = true;
            var profilePath = Root + "/Settings/WorldVolume.asset";
            var profile = AssetDatabase.LoadAssetAtPath<VolumeProfile>(profilePath);
            if (profile == null)
            {
                profile = ScriptableObject.CreateInstance<VolumeProfile>();
                AssetDatabase.CreateAsset(profile, profilePath);
            }
            if (!profile.TryGet<Tonemapping>(out var tone)) tone = profile.Add<Tonemapping>();
            tone.mode.Override(TonemappingMode.ACES);
            if (!profile.TryGet<Bloom>(out var bloom)) bloom = profile.Add<Bloom>();
            bloom.intensity.Override(0.5f);
            bloom.threshold.Override(0.9f);
            if (!profile.TryGet<Vignette>(out var vignette)) vignette = profile.Add<Vignette>();
            vignette.intensity.Override(0.18f);
            volume.sharedProfile = profile;
            EditorUtility.SetDirty(profile);
            EditorUtility.SetDirty(pipeline);
            EditorSettings.serializationMode = SerializationMode.ForceText;
            PlayerSettings.productName = "Spherical Civilization";
            var scenePath = Root + "/Scenes/Globe.unity";
            EditorSceneManager.SaveScene(scene, scenePath);
            var scenes = new List<EditorBuildSettingsScene>(EditorBuildSettings.scenes);
            scenes.RemoveAll(s => s.path == scenePath); scenes.Insert(0, new EditorBuildSettingsScene(scenePath, true));
            EditorBuildSettings.scenes = scenes.ToArray();
            AssetDatabase.SaveAssets();
            SceneView.lastActiveSceneView?.LookAt(Vector3.zero, Quaternion.Euler(20f, 35f, 0f), 2f);
            return $"Saved {scenePath}: {globe.TileCount} tiles, {globe.TriangleCount} triangles.";
        }

        public static string EnsureCameraControls(OrbitCamera orbit = null)
        {
            if (Application.isPlaying) throw new InvalidOperationException("Install camera controls outside Play Mode.");
            if (orbit == null) orbit = UnityEngine.Object.FindFirstObjectByType<OrbitCamera>();
            if (orbit == null) throw new InvalidOperationException("Open the strategic globe scene first.");
            var uiPath = Root + "/UI/CameraControls/";
            var tree = AssetDatabase.LoadAssetAtPath<VisualTreeAsset>(uiPath + "CameraControls.uxml");
            var theme = AssetDatabase.LoadAssetAtPath<ThemeStyleSheet>(uiPath + "CameraTheme.tss");
            if (tree == null || theme == null) throw new InvalidOperationException("Camera UI assets are missing.");
            var settingsPath = Root + "/Settings/CameraPanelSettings.asset";
            var settings = AssetDatabase.LoadAssetAtPath<PanelSettings>(settingsPath);
            if (settings == null)
            {
                settings = ScriptableObject.CreateInstance<PanelSettings>();
                AssetDatabase.CreateAsset(settings, settingsPath);
            }
            settings.themeStyleSheet = theme;
            settings.scaleMode = PanelScaleMode.ScaleWithScreenSize;
            settings.referenceResolution = new Vector2Int(1280, 720);
            settings.screenMatchMode = PanelScreenMatchMode.MatchWidthOrHeight;
            settings.match = 0.5f;
            settings.sortingOrder = 10;
            EditorUtility.SetDirty(settings);
            var panel = UnityEngine.Object.FindFirstObjectByType<CameraControlsPanel>();
            var panelObject = panel != null ? panel.gameObject : new GameObject("Camera controls");
            var document = panelObject.GetComponent<UIDocument>();
            if (document == null) document = panelObject.AddComponent<UIDocument>();
            document.panelSettings = settings;
            document.visualTreeAsset = tree;
            if (panel == null) panel = panelObject.AddComponent<CameraControlsPanel>();
            panel.orbitCamera = orbit;
            var events = UnityEngine.Object.FindFirstObjectByType<EventSystem>();
            if (events == null) events = new GameObject("UI Event System").AddComponent<EventSystem>();
            if (events.GetComponent<InputSystemUIInputModule>() == null)
                events.gameObject.AddComponent<InputSystemUIInputModule>().AssignDefaultActions();
            EditorUtility.SetDirty(panel);
            EditorSceneManager.MarkSceneDirty(orbit.gameObject.scene);
            AssetDatabase.SaveAssets();
            return "Camera controls installed.";
        }

        private static Material MaterialAsset(string name, Shader shader, Color color)
        {
            var path = Root + "/Materials/" + name + ".mat";
            var material = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (material == null)
            {
                material = new Material(shader) { name = name };
                AssetDatabase.CreateAsset(material, path);
            }
            if (material.HasProperty("_BaseColor")) material.SetColor("_BaseColor", color);
            EditorUtility.SetDirty(material);
            return material;
        }
    }
}
