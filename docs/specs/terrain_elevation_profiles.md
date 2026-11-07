# Terrain elevation profiles — first working version

Owner request, 4 November 2026, issue #187: sections through an existing site
with large elevation changes; any number of section lines, any direction; protect
source measurements and edit the design through the common model.

## Human workflow

1. Create/import the terrain using the existing site tools.
2. Draw a section line in the plan using the existing Section tool.
3. In the section drawing, press **Elevation profile…**. The button has the
   stable control id `terrain.profile.open`; no main/menu or mouse-menu
   reorganization is part of this change.
4. Select any saved section and terrain. **New section in plan** returns to the
   existing draw-line workflow. Section entities remain in the Document; there
   is no separate terrain copy or stored profile cache for each section.
5. Green source records are read-only in this editor. Blue points are explicit
   design controls. The table separates source/target Z, current model Z and
   absolute model Z when a project datum is available. A source/model mismatch
   already present in the terrain is highlighted, not silently reconciled.
6. Double click the plot to add a design point. Drag a blue point to preview,
   release to commit, or Esc to cancel. Numeric distance and model Z use the
   same command path. A rejected edit changes nothing. An unchanged edit adds
   no empty Undo step. Deleting a blue point is one Undo too.
7. **Average grade** sets a target endpoint from the preceding source/design
   record: `target_z = previous_z + grade_percent / 100 * distance`.
   It does not claim constant slope along the interpolated curve.

Distances are measured from the viewed end of the saved section. Reversing the
section reverses stationing; stored terrain/control X/Y coordinates stay intact.
Profiles are clipped to the finite section and the selected terrain's extent.
Values outside the terrain are not extrapolated.

## Shared model and source constraints

- The existing `section_line`, `output.section_cut.frame`, terrain height field,
  mesh generators, `UpdateEntity` and `CommandStack` are reused.
- Design records live only in the terrain's `params.profile_controls`:
  `{id, x, y, z, provenance: DESIGN_DEFAULT}`. An id survives moves, Undo/Redo,
  save/load and reading the same point from intersecting sections.
- Existing `points` and `levels` are treated as source constraints, regardless
  of whether they were imported or entered manually. Their records are never
  changed by this tool. New controls cannot occupy the same plan location.
- The existing `_point_height` local interpolation supplies a correction on top
  of the current terrain. Corrections are zero at every source anchor, including
  anchors outside the viewed section. All design endpoints are evaluated against
  the same unmodified underlying field, so other design endpoints stay pinned.
- Fixed elevation-region interiors are protected. Change the region using its
  existing editor instead of silently overriding it with a profile control.
  Current green-roof minimum-ground constraints are retained.
- The influence radius follows the existing terrain interpolation setting
  (`profile_radius` if explicitly supplied, otherwise `blend_radius`). The
  inherited minimum 0.5 m is an algorithm/design limit, not an engineering rule.
- The mesh retains its existing base grid and includes design coordinates;
  numerical coincidences are merged within the model tolerance without moving
  stored data. Survey coordinates do not create an expensive Cartesian cross grid.
- Visible plan/3D/section views derive from the changed terrain. The profile
  editor subscribes to the shared stack and detaches when destroyed. An ordinary
  section line may be deleted without deleting the physical terrain edits.

## Explicit limits

The brown line is a **sampled model height field**, not evidence of unmeasured
ground between survey records. It is not an independent survey or a geotechnical
approval. Vertical faces, overhangs and a general breakline/retaining-wall design
model are not implemented by this editor. Existing terrain regions/walls keep
their existing behavior; this feature does not certify their geometry or sizing.

The architectural section drawing shows the actual building/pool excavation
cuts. The profile shows the terrain field, including its reference height under
those cutouts. Do not present it as the boundary of the excavated solid.

Absolute Z is `model_z + altitude_ref`, using the existing project setting.
Absent/zero unconfirmed datum is shown as unset; the editor does not invent a
geographic datum. User-entered/source values retain their original precision.

The new editor's labels are English. Localization PR #185 remains a separate
branch; this feature neither duplicates its translation service nor merges it.
The new control and its dialog labels must be included in the final UI inventory.

## Evidence

`tests/test_terrain_profiles.py` uses explicitly synthetic fixtures. It checks
field/source separation, clipping and reversal, cross-section propagation,
stable control identity, rejection, Undo/Redo and save/load, mean-grade targets,
mesh watertightness and near-coincident grid lines, bounded grid growth with a
400-point fixture, 41 saved sections, actual Qt drag/preview/Esc, and the real
SectionPanel button -> editor -> terrain -> PBR/section drawing path.

The first five new tests failed before the module existed. Additional regressions
failed before the empty-Undo and degenerate-mesh fixes. The final focused group
passed 67 tests; one existing browser test skipped without Node/Playwright/Chromium.
Compile and diff checks passed. The full local suite and independent PR CI must
be assessed separately. An offscreen Qt preview is not an owner's Windows test.
