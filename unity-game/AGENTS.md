# Unity game workspace

Work on the Unity version inside this directory. The existing Python/Pygame
prototype in the parent directory is reference material; do not change it as
part of Unity work. Installed development tools may live outside the repository.

## Product direction

- A Civilization-inspired strategy game with three map scales.
- Strategic: a spherical world tiled with polygons, including pentagons.
- Operational: subtiles with identical boundaries across neighboring parent tiles.
- Tactical: a local hexagonal battlefield derived from the campaign geography.
- Start with simple 3D terrain and sprite units/buildings.
- Initial development target: Windows desktop. No monetization or online services
  are needed for the prototype.

## Tooling

- Use the official `unity@unity-agent-plugin` plugin. Read its relevant skills
  before running Unity CLI, package, rendering, or UI tasks.
- Use a supported Unity 6 LTS Editor and the URP template.
- Drive the open Editor through the official Unity CLI and `com.unity.pipeline`.
- Pass the full Unity project path on every command that targets the Editor.
- Read command schemas from the connected Editor rather than assuming names.
- Create scenes, prefabs and assets through Unity APIs; do not hand-author their YAML.
- Install packages through the official package tools, not manual manifest edits.
- Keep generated caches, downloads, logs, credentials and local settings out of Git.
- Do not create a nested Git repository or publish anything without a user request.
- Use the parent repository's existing shell instructions, including RTK.
- Work and run previews only inside the Unity Editor. Do not build standalone
  executables unless the user explicitly requests a build again.

## Architecture

- Keep world topology and game state independent of rendering and scene objects.
- Give tiles, subtiles and shared edges stable identifiers.
- A shared edge owns one canonical boundary consumed by both neighboring tiles.
- Neighbor relations must be reciprocal, including across parent-tile borders.
- Group rendered terrain into chunks; avoid one scene object per small cell.
- Generate tactical fields only when needed.
- Preserve the original generator as a reference during incremental migration.

## Verification

- The user handles UI checks and will report issues. Do not manually exercise
  UI controls, run synthetic mouse/keyboard UI checks, or capture screenshots
  solely to verify UI changes unless explicitly requested. For camera setting
  updates, use compilation and data checks only; do not run UI verification suites.
- Check Unity compilation and the Editor console after changes.
- For topology changes, verify cell counts, edge sharing, reciprocal neighbors,
  connectedness and polygon orientation.
- For rendering changes, verify visuals with an actual camera capture. Entering Play mode alone does not
  prove that frames are advancing.
- Keep README.md and SETUP.md accurate, including anything that remains unverified.
