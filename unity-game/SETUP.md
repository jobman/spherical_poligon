# Local setup

Status: Editor installed, Unity project created, official Pipeline connected, and
the first strategic-globe preview verified.

## Installed and verified

- Official Codex plugin: `unity@unity-agent-plugin`, version `0.1.8-beta`.
- Unity CLI: `1.0.0-beta.14`.
- Unity ID sign-in and active Unity Personal license.
- Unity Editor: `6000.3.27f1`, under `D:\Tools\Unity\Editors`.
- Unity project: `D:\Projects\spherical_poligon\unity-game\SphericalCivilization`.
- Template: `com.unity.template.urp-blank` (Universal 3D / URP).
- URP `17.3.0`; Input System `1.20.1` (provided by the template).
- Official `com.unity.pipeline` package `0.9.1-exp.1`.
- Pipeline connected to this project's Editor on localhost; `state: ready`.
- No Unity Cloud project or new Git repository was created.

## First scene

Open `Assets/_Project/Scenes/Globe.unity` and press Play.
Left- or right-drag grabs the globe surface when the gesture begins on a tile;
starting on empty space rotates the camera freely. A short left click selects a
tile. The wheel zooms. Background rotation, shared keyboard speed and wheel speed
default to the accepted 1.00 multipliers. Esc opens a menu with `Продолжить` and
`Настройки`. Settings contain sliders for all four speed multipliers and adjust
rotation and scroll inertia separately, with half-lives of
0.00–1.00 seconds (both default to the accepted 0.11). Zero disables the selected
inertia. Copy exports both half-lives and the saved speeds.
All rotation modes pass through both poles. Changes apply immediately;
`Сохранить` writes them as defaults for the next Play session or game launch.
The preview requests a 60 FPS limit.
Q/E turn around the focused ground point, retaining zoom and ground tilt. They
share the keyboard speed law and rotation inertia, work together with WASD or
arrows, and respect UI keyboard focus. Combined input is normalized.
The Q/E speed slider has its own multiplier, 0.10–5.00 with accepted default 2.64;
WASD/arrows retain their saved multiplier. Copy exports `turnRotationSpeed` too.

The menu is hidden at startup and blocks camera input while open. Esc returns
from settings to the main menu, then closes it; `Продолжить` closes it directly.
Opening the menu stops dragging and both kinds of inertia. All six settings are
saved atomically to `CameraSettings.json` under `Application.persistentDataPath`.
Startup loads the file over the scene defaults, preserves missing-field defaults,
and sanitizes invalid numeric values. Without a saved file the accepted profile
is 1.00 / 1.00 / 2.64 / 1.00 / 0.11 / 0.11.

The globe imports the original cached world: 642 tiles rendered as one terrain
operational mesh generated from irregular Voronoi cells. The 642 parents contain
23,754 subtiles at the default count of 37 per parent. There are 9,600 cross-region operational
edges along 1,920 canonical parent boundaries. Polygon borders and selection are part of the same
terrain shader pass, with pixel-based width and no radial offsets, separate line
mesh or LineRenderer. This prevents parallax at close, oblique camera angles.
Triangle vertices carry barycentric coordinates and edge data, so fan diagonals
remain invisible. Subtile borders fade in on approach, and near clicks select a
subtile. Parent edge equations keep strategic outlines consistent even when
fine fan triangles become subpixel. Esc > `Карта` adjusts the exact count per
parent type from 12 to 128, independently for hexagons and pentagons. `Применить` regenerates once and clears selection;
`Сохранить` also persists the count and seed to `WorldSettings.json` for the next
Play/application launch. The camera view is retained. The user rejected the
regular ring pattern and deferred the 1.5 area-ratio requirement; the earlier
ring measurements in `docs/SUBTILE_AREAS.md` are historical.

The separate `SubdivisionLab` scene is available through Esc > `Подбор субтайлов`
or the Editor menu `Spherical Civilization > Open subdivision lab`. It shows
three real examples of each shape at the same scale and regenerates only six
interiors when either slider changes. Save/Copy/Apply to globe use independent
hexagon and pentagon counts. `docs/SUBDIVISION_LAB.md` describes the workflow.
Both scenes are enabled in Build Settings, with Globe still the default first scene.
Tactical combat remains a future milestone. The terrain generator still
lives in the Python prototype.

The scene uses a directional sun, URP HDR, ACES tonemapping, subtle bloom, and a
vignette. Its materials, volume profile, scene, and build-scene list were created
through Unity APIs in the live Editor.

## Checks completed

- Esc menu implementation: compilation and data-only save/load checks passed.
  The user checks menu interaction and layout; no UI automation or UI captures
  were run. The older UI checks below describe the previous always-visible panel.
- Unity C# compilation: zero errors and warnings.
- Pipeline C# execution and camera PNG capture work.
- Play mode advances: server-side frame-count wait returned `met: true`.
- Ray selection returned the correct ID for all 642 cells.
- Camera-center selection, URP, HDR, post-processing and volume layer mask passed.
- Shader diagnostic check passed; Editor console reported no errors or warnings.
- All operational edges have two owners and reciprocal neighbors. Parent
  coverage, connectedness, Euler characteristic 2, pentagon regions and all
  23,754 ray picks passed, including counts 12, 24, 64, 128 and another seed.
  Polygon convexity and the exact requested count per parent are checked.
- Independent counts passed for pairs 128/12, 12/128 and 37/24. Sample geometry
  matched the full globe, including boundaries. Legacy settings migrate to both
  new counts. Lab geometry generation and triangle orientation passed at mixed
  counts; preview updates measured about 35–60 ms locally. Menu controls remain
  for the user to check; only the sample terrain was captured.
- All 9,600 default parent boundary segments use identical endpoints on both sides.
  One renderer draws terrain, borders and selection. URP pixel comparisons
  passed at four zoom/orientation combinations, including close oblique and
  polar views. Frame/console checks and camera captures exclude menu UI.
- Surface-grab projection error was below 0.004 pixels at five zoom distances,
  including near a pole and with the new ground tilt.
- Unlimited background rotation, shared keyboard speed, frame-rate
  independence, click versus drag selection, normalized wheel units, zoom
  damping and limits, UI blocking, both inertia sliders and Copy passed
  `tools/Verify-Camera.cs` in the live Player.
- Tilt increases from 0 to 50 degrees on approach while keeping the same ground
  focus centered and preserving the requested radial altitude.
- UI Toolkit panel captured in the Game view, including Cyrillic text.
- Dynamic Input System events verified left-button surface dragging,
  right-button background rotation, WASD and arrow-key navigation and coasting,
  Q/E turning in both directions, its independent speed slider, momentum after
  release and UI focus blocking,
  one normalized wheel event, mouse dragging of the actual UI slider,
  keyboard focus isolation, and Copy writing the current values to the clipboard.
  The scene includes EventSystem with InputSystemUIInputModule for UI routing.
- Keyboard, mouse and scroll momentum decay after release. The chosen half-life halves
  velocity, the analytical integration is independent of frame rate, zero
  disables inertia, and new grabs, UI interactions and focus loss stop it.
- Mouse velocity is sampled from actual orbit rotation, filtered over 0.035
  seconds and bounded at 360 degrees/second for coasting. An idle held pointer
  clears stale velocity. Held keyboard input retains the accepted speed law.
- Reference export: 12 pentagons, 630 hexagons, 1,920 shared edges with two owners,
  connected and reciprocal adjacency, and Euler characteristic 2.

Captures are in the project's ignored `Assets/.artifacts/` directory.

The Input System is configured with `UniformAcrossAllPlatforms`: one wheel
notch is 1 rather than Windows' native 120. Zoom now uses these units and scales
with height above the unit sphere. The old `0.0015 * delta` formula was too weak
with normalized input. Python's adaptive zoom and surface-distance speed scaling
were used as initial reference; keyboard rotation now uses center distance:
`degreesPerSecond = 60 * keyboardRotationSpeed * distance / 3.3`.
WASD and arrows are aliases and share one saved multiplier; combined and diagonal inputs
are normalized. No surface-radius subtraction or altitude clamp is applied to
keyboard rotation. The old serialized WASD setting migrates to the shared field.
Python sources remain unchanged. The close limit is
1.10 radii, near Python's 1.104 limit. Zoom uses an exponential approach with
velocity half-life 0.11 seconds, matching rotation. Its remaining target distance and
speed halve together, independently of frame rate. Total wheel displacement
still follows the accepted height-dependent step. Zoom respects both distance
limits, reverses immediately on opposite wheel input, and stops on a new grab,
UI interaction or focus loss. Tilt begins below 1.4 radii of height and peaks
at 50 degrees.

## Helpers

- `tools/Check-Setup.ps1` reports plugin, CLI, license, Editor and project status.
- `tools/Open-Unity.ps1` opens this project.
- `tools/Install-Editor.ps1` can reuse the verified local installer and verifies
  the installed Editor without attempting duplicate registration.
- `tools/Create-Project.ps1` creates a URP project and installs Pipeline; it
  refuses to overwrite an existing incomplete directory.
- `tools/export_reference_world.py` exports an existing local Python cache
  without starting GameWorld or modifying its source or cache.
- `tools/Verify-Globe.cs` runs through Pipeline `script eval_file`.
- `tools/Verify-Settings.cs` checks persistence and validation using temporary
  files; it does not open UI or alter the user's saved preferences.
- `tools/Verify-Borders.cs` checks shared-edge geometry and actual URP rendering
  with borders enabled/disabled, restoring the view and selection afterward.
- `tools/Verify-Subtiles.cs` checks operational topology, coverage, determinism,
  3D area ratios, different densities and ray picking without operating UI controls.
- `tools/Analyze-SubtileAreas.cs` measures rendered 3D surface areas, global
  statistics and within-parent max/min ratios, saving JSON under `Library/`.
- `tools/Verify-WorldSettings.cs` checks world-count persistence with temporary
  files without touching the user's saved preferences or UI.
- `tools/Verify-Camera.cs` uses the same command in Play Mode, after UI layout
  has had a frame to complete. It restores the camera and clipboard state.
- `tools/Verify-CameraInput.cs` checks mouse and keyboard events on actual Player input
  updates. Read the asynchronous result with Pipeline C# execution:
  `UnityEditor.SessionState.GetString("CameraVerification.InputResult", "MISSING")`.
  It temporarily allows background input and restores the previous settings.
  It uses temporary virtual mouse/keyboard devices, disabling and then restoring
  the previous Unity input devices so physical input cannot overwrite test events.
  It also restores UI focus and the clipboard. UI steps wait for real time so
  Toolkit can dispatch events when Editor auto-ticking advances Player frames
  faster than panel updates.
  Slider dragging allows 0.4 seconds for UI dispatch independently of the Player
  frame counter; synthetic pointer movement includes a hover before each press.

For unattended verification, temporarily enable `editor.playmode
set_run_in_background`; wait for `UnityEngine.Time.frameCount` to change before
checking UI geometry. Restore the previous background setting afterward. A
reload can leave the unfocused Player paused before its first UI layout.
If frames remain at 1 with background execution and auto-ticking enabled, restore
the Editor window if minimized. The Pipeline focus command may focus its dock
without restoring the native Windows window.
After recompiling scripts during Play, restart Play Mode before checking UI
input: the uGUI/UI Toolkit bridge can lose its panel raycasters on domain reload.

New Codex sessions load the installed plugin automatically. Relevant skills can
also be read from its verified installed path reported by `codex plugin list`.
The current Pipeline package does not contain the older hidden `unity-pipeline`
skill path referenced by the plugin; live command schemas were used instead.

## Installation issue resolved

The installer initially failed writing `UserInfo.dll` under the system-drive
temporary directory. Installation succeeded after free space on C increased.
The Editor itself is on D. A verified installer remains at
`D:\Tools\Unity\Downloads\UnitySetup64-6000.3.27f1.exe`.

The Windows UI automation runtime could not initialize during setup. It was not
needed after installation: Editor control and captures use the official CLI and
Pipeline. No Windows security prompts were automated or bypassed.

The Python prototype's source and existing working-tree changes are preserved.
