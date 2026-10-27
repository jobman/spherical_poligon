# Operational subdivision

The strategic reference globe has 642 parents: 630 hexagons and 12 pentagons.
`OperationalSubdivision.Build` generates irregular clipped Voronoi cells
independently of scene objects, materials and input. The user rejected the
regular ring experiment and deferred area equalization to preserve this look.
The current generator does not enforce a 1.5 area-ratio limit.

## Cell count

`SubdivisionOptions.SubtilesPerTile` sets the exact count in hexagonal parents;
`PentagonSubtilesPerTile` independently sets the pentagons. A zero pentagon count
preserves the legacy uniform setting. Both accept 12–128; the default is 37
for both, giving 23,754 cells. The total is `630*hexagonCount + 12*pentagonCount`.
Counts 12, 24, 64 and 128 produce 7,704 / 15,408 / 41,088 / 82,176 cells.

The generator chooses shared boundary site intervals using
`round(4 * sqrt(count / 37))`, taking the smaller density of the two owners on
each parent edge, then creates the remaining sites inside the
parent. It retains the original distance-limited random sampling. If the
requested count cannot fit at that spacing, it inserts best-separated points
from a deterministic candidate pool. Updating each candidate against only the
new site keeps high-density generation practical. Interior sites never leave
the boundary guard strip constraint.

An optional nonzero `EdgeSegments` overrides the automatic boundary density
for development. The requested count must accommodate all boundary sites.
Both settings, together with the seed, define the generated map.

## Shared borders

Original corners are welded once. Each undirected strategic edge owns a
canonical `RegionBoundary`, shared by exactly two parents and created before
interiors. With `n` site intervals, boundary sites lie at `j/n`; their Voronoi
transitions are `(j + 0.5)/n`. Transitions and original endpoints are created
once in 3D. Owners consume the same vertex IDs in opposite directions.

At the default count, `n=4` and there are five subtile segments per strategic
edge: 9,600 cross-region segments in total. Changing count can change this
shared density, always for both owners at once.

A guard wider than half the maximum boundary-site spacing prevents interior
sites from changing the canonical boundary cuts on the reference world's
obtuse polygons. An unexpected boundary intersection aborts generation.

Clipping runs in double-precision tangent coordinates. Interior vertices are
lifted onto the reference triangle fan and welded. The render mesh fans each
cell around its center using the same shared perimeter endpoints. There is no
elevated line geometry.

## Identity and connectivity

- Parent IDs are the reference IDs.
- Subtile IDs pack the parent ID and deterministic local site index.
- Every operational edge has exactly two owners and reciprocal neighbors.
- Cross-region edges identify their canonical strategic boundary.
- Parents are sorted by ID; randomness is local to parent ID and world seed.

Changing count or algorithm defines a different map; old subtile IDs must not
be used to restore gameplay state in a regenerated map. There is no saved
operational gameplay state yet. Cells inherit parent terrain and color.

At 37 cells per parent, the map has 39,823 shared vertices, 63,575 shared edges
and 127,150 render triangles. Euler characteristic is 2 and the map is connected.
One combined renderer and collider display and pick the cells.

## Runtime settings

Esc > `Карта` exposes both count sliders. Dragging only changes the pending values.
`Применить` generates the topology before replacing the old one, resets selection
and preserves the camera. `Сохранить` applies and atomically stores the count
and seed in `WorldSettings.json` under `Application.persistentDataPath`.
Camera preferences stay in their separate existing file.

`GlobePreview.ApplySubdivision(hexagonCount, pentagonCount)` is available to code;
the single-count overload still applies one value to both shapes. Counts are
clamped to the supported limits; malformed or absent settings fall back to
scene defaults. The Inspector exposes `subtilesPerTile` for development.

Esc > `Подбор субтайлов` opens the [separate lab](SUBDIVISION_LAB.md), where
`BuildPreview` generates only six selected parent interiors, without a subtile
adjacency graph. It reuses the main generator and canonical parent boundaries.

Fine borders fade in between camera center distances 3.10 and 1.55. Clicks
select a subtile at visibility 0.65 or above, otherwise its parent. Parent
edge-distance equations preserve strategic outlines at distant/subpixel views.

## Validation

`tools/Verify-Subtiles.cs` checks exact counts, coverage, convexity, two edge
owners, identical reversed endpoints, reciprocal neighbors, cross-region
connectivity, all pentagons, connectedness, Euler characteristic, outward
triangles, and ray picking for every default cell. It checks reversed parent
enumeration, another seed and counts 12, 24, 64 and 128. All passed. Area ratios
are measured and reported without enforcing the deferred 1.5 limit.
Mixed pairs 128/12, 12/128 and 37/24 also passed. Preview cell coordinates matched
their equivalents in the complete globe.

`Verify-WorldSettings.cs` tests persistence through temporary files, leaving user
preferences untouched. `Verify-Borders.cs` checks canonical segments and actual
URP pixels at close oblique, middle, distant and polar views. These checks do
not operate menu UI. UI interaction and layout are checked by the user.

`Analyze-SubtileAreas.cs` exports current 3D surface-area measurements to
`Library/SubtileAreaAnalysis/`. [The earlier area report](SUBTILE_AREAS.md) and
its CSV remain explicitly marked as an archive of the rejected ring experiment.
