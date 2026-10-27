# Project brief

Build a strategy prototype inspired by Civilization, using a spherical world
with three connected map scales. Terrain is 3D; units and buildings may initially
use sprites to reduce content-production work.

## Initial technical choices

- Windows desktop first.
- Unity 6.3 LTS, initially 6000.3.27f1.
- Universal Render Pipeline (URP), using Unity's actual Universal 3D template.
- C# for Unity-side systems; the Python generator remains a reference and can
  export data while migration is in progress.
- Official Unity plugin for Codex, Unity CLI, and Unity Pipeline for Editor access.
- Existing parent Git repository; no remote publication or nested repository.
- Local single-player prototype; no accounts, ads, purchases, or backend packages.

## Map model

1. Strategic: an icosahedron-derived dual mesh with mostly hexagonal cells and
   twelve pentagons. Store explicit cell IDs, neighbors, and shared edges.
2. Operational: subdivide regions while consuming the same canonical boundary
   on each side of a shared edge. Store connectivity across regional borders.
3. Tactical: create a local hex grid from the active campaign area, then apply
   battle results back to campaign state.

## First milestones

1. Install and verify the official tooling; create a clean URP project.
2. Verify compilation, live Editor commands, camera capture, and an advancing
   Play-mode session.
3. Display the tiled sphere with orbit/zoom and cell selection.
4. Operational subdivision implemented for all 642 regions, with canonical
   shared boundaries and cross-region adjacency; see `SUBTILE_TOPOLOGY.md`.
5. Open one tactical field and return to the globe.

Do not attempt the entire game or full generator migration in one change.
