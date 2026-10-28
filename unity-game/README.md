# Spherical Civilization — Unity prototype

Unity workspace for the spherical strategy game. The Python prototype in the
parent directory remains the reference implementation during migration.

## Layout

- `SphericalCivilization/` — Unity project (created by the official Unity CLI).
- `docs/PROJECT_BRIEF.md` — game direction and initial development boundaries.
- `SETUP.md` — local setup, verification status, and ways to resume development.
- `tools/` — project-specific development scripts.

## Direction

The game has three geographic scales: a tiled globe, regional subtiles with
matching shared borders, and local tactical hex grids. The initial visual target
is simple 3D terrain with sprite units and buildings.

The initial platform is Windows desktop. Rendering uses URP. World topology and
simulation should remain separate from Unity presentation code.

## Run the first globe preview

1. Open `SphericalCivilization/` in Unity `6000.3.27f1`.
2. Open `Assets/_Project/Scenes/Globe.unity` and press Play.
3. Drag with either left or right mouse button. A press on the globe grabs its
   surface; a press on empty space starts free camera rotation. The mode stays
   fixed until release. A short left click selects a tile; dragging preserves
   the selection. Scroll the mouse wheel to zoom.
4. Press Esc for the menu, then choose `Настройки` to adjust the camera.
   `Сохранить` stores the current values as defaults for future launches.

Mouse dragging, WASD and arrows rotate freely through both poles. Keyboard
navigation slows down toward the center, is independent of frame rate and does
not accelerate on diagonals. The menu blocks camera input and stops inertia.
Esc opens the menu, returns from settings to the main menu, then closes it.
`Продолжить` also closes the menu. Tab navigates controls while the menu is open.

Q and E turn the camera around the focused ground point, preserving zoom and
automatic tilt. They combine with WASD/arrows, use the same distance-dependent
speed scaling and rotation inertia, and are blocked while UI controls have
keyboard focus. Combined navigation input is normalized.
The Q/E turn-speed slider adjusts its own multiplier from 0.10× to 5.00×,
defaulting to the accepted 2.64×. WASD/arrows retain their accepted speed. Copy includes
`turnRotationSpeed` alongside the speed profile and inertia settings.

Settings include background mouse rotation, shared WASD/arrow speed, Q/E turn
speed, wheel zoom speed, and the two inertia half-lives. Speed multipliers range
from 0.10× to 5.00×. Initial defaults are 1.00× for mouse, WASD/arrows and wheel,
and 2.64× for Q/E. Surface grabbing follows the cursor directly while held.

The camera panel adjusts rotation and zoom inertia separately. Both default to
the accepted 0.11-second velocity half-life, with a range of 0.00–1.00 seconds.
Rotation and zoom continue after input stops, with their velocity halving every
0.11 seconds. Zero disables the corresponding inertia. New grabs or clicks and
loss of focus stop both motions; interacting with the UI stops pending zoom.
Pausing the mouse before release avoids a stale fling. During surface grabbing,
inertia never displaces the point from the cursor.

Keyboard angular speed is `60 * keyboardRotationSpeed * distance / 3.3` degrees
per second. `distance` is the camera's actual distance from the globe center,
including with automatic tilt. At multiplier 1.00, distances 1.10, 3.30 and 6.60
give 20, 60 and 120 degrees per second. Holding both key sets or moving diagonally
does not increase speed.

Wheel zoom uses Unity Input System's normalized wheel units. One notch at 1.00
changes target height above the surface by about 20%. The camera coasts toward
that target with the selected zoom half-life, preserving the total zoom step.
Distant travel is faster and close adjustment is finer.
The camera stays between 1.10 and 7.00 globe radii from the center. Below a height
of 1.40 radii it gradually tilts from a straight-down globe view toward a 50-degree
oblique view, keeping the ground focus in the center of the screen.
`Скопировать` copies all six current values as JSON for pasting into the chat.
Changes apply immediately and remain active when returning to the game.
`Сохранить` writes `CameraSettings.json` under Unity's `Application.persistentDataPath`;
the camera loads it on the next Play session or application launch. Saved values
override scene defaults. A partial file preserves defaults for missing fields;
an unreadable file falls back to scene defaults. Unsaved changes last for the
current session. Only the small `Esc — меню` hint is visible during gameplay.

The preview imports the existing 642-cell Python world, including its terrain
colors. Tile borders and selection are drawn by the terrain shader on the same
surface, so they stay aligned with color seams even at the closest oblique view.
Borders have a stable pixel width; internal triangulation edges remain hidden.
The globe needs one mesh renderer and no elevated line geometry. The generator
itself and campaign game rules have not yet been ported. The
runtime requests a 60 FPS frame-rate limit.

Operational subdivision now creates 23,754 irregular Voronoi subtiles inside the 642
parent regions. Neighbors share the same canonical boundary vertices and have
reciprocal links across parent borders, including pentagons. Fine borders fade
in as the camera approaches; left-click selects a subtile at any distance.
Right-click chooses an adjacent attack target. Subtiles currently inherit parent terrain and color.
Esc > `Карта` sets separate exact counts of 12–128 subtiles for hexagons and
pentagons (both default to 37). `Применить` regenerates the map once; `Сохранить` also stores the counts for
future launches in `WorldSettings.json`, separately from camera preferences.
Regeneration clears selection and preserves the camera view. The rejected ring
experiment is archived in [the statistical report](docs/SUBTILE_AREAS.md).
The user deferred the 1.5 area-ratio limit to preserve the irregular appearance.
See [the subdivision model](docs/SUBTILE_TOPOLOGY.md) for generation and validation.

**Esc > `Подбор субтайлов`** opens a separate lab scene with three hexagonal and
three pentagonal examples, shown at the same scale. Two independent sliders
update only these six samples. Copy exports the chosen values; Save stores them;
Apply to globe saves and opens the main world with those counts. The Editor menu
`Spherical Civilization > Open subdivision lab` also opens it. See
[the lab guide](docs/SUBDIVISION_LAB.md). Development and previews run inside the
Unity Editor; standalone executable builds are deferred at the user's request.

In the globe scene, **left-click** chooses your subtile (orange), **right-click**
chooses an adjacent attack target (red), and **Space** opens a test battlefield
on exactly that pair. Invalid targets and changing the source clear the target;
there is no automatic pair selection. The playable area is the convex hull around
both subtiles, including the filled gaps between them. It uses the same hex size,
with exactly three retreat
rows and fading surrounding subtile outlines. Two test tokens can be selected
and moved with the left mouse button; reaching row 3 marks one as escaped.
Drag/WASD pans and the wheel zooms. Space/Esc returns to the unchanged globe
view. Entry preserves the screen orientation of the shared boundary, including
after Q/E turns and near poles. See [the tactical preview](docs/BATTLEFIELD.md).

Esc > `Подбор поля боя` opens the separate `BattlefieldLab` scene with three
neighboring subtile pairs at a common geographic scale. One size slider updates
all examples. Save writes a fixed hex radius to `BattleSettings.json`; each new
battle reads it immediately. Returning without saving leaves battle settings
unchanged. See [the battle lab](docs/BATTLEFIELD_LAB.md).
These are test tokens; combat resolution and campaign armies remain future work.

## Development

Open the `SphericalCivilization` project in the Editor version recorded in its
`ProjectSettings/ProjectVersion.txt`. Use the official Unity plugin for Codex,
Unity CLI, and the Unity Pipeline package to interact with the Editor.

See [SETUP.md](SETUP.md) for setup and verification details. The migration of the
three map scales is incremental.

`Spherical Civilization > Create globe preview` rebuilds the scene through Unity
APIs. The helper `tools/Verify-Globe.cs` is a statement block for Pipeline's
`script eval_file` command and checks cell picking and the URP baseline.
`tools/Verify-Borders.cs` checks the 9,600 default canonical segments along 1,920 parent
boundaries, excludes fan diagonals,
and compares actual URP pixels with borders enabled and disabled at four views,
including minimum-distance oblique views and a pole. It restores the view and
selection afterward.
`tools/Verify-Subtiles.cs` checks the whole operational topology, coverage, 3D area ratios and
picking, deterministic IDs, another seed and alternative densities without UI input.
`tools/Verify-Settings.cs` checks saving, replacement, loading, missing fields,
damaged files and numeric limits using temporary files, without exercising UI
controls or changing user preferences. Menu interactions and layout are left to
the user to check. The legacy `Verify-Camera.cs` and `Verify-CameraInput.cs`
include checks for the previous always-visible panel and are not current menu tests.
