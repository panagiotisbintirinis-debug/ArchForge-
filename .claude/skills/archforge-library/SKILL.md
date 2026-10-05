---
name: archforge-library
description: How to build, import and maintain ArchForge's object and material libraries — the `.afcatalog` catalog format, license/provenance rules, adding parametric library objects (cabinets, furniture, fixtures) as Document entities, CC0 material packs (ambientCG, Poly Haven), glTF/OBJ model import, and reading Home Designer / Chief Architect `.calib` catalogs locally for study. Use this skill whenever work in the ArchForge repo touches the Library/Βιβλιοθήκη, catalogs, materials or textures, furniture or cabinet objects, model import, Home Designer files (.calib, .calibz, .tbdata), or the user asks where library content should come from — even if they don't say "library".
---

# ArchForge library work

ArchForge is human-first: the user places library items by hand, and the
`Document` is the only design truth (see `AGENTS.md`). A library is how
users get ready-made objects and materials. It must also stay legal to ship
when ArchForge is given to other people. Almost every decision below follows
from those two facts.

## Three sources, in order of preference

1. **Parametric objects written in ArchForge code.** Examples are cabinets,
   worktops, doors, windows, stairs, railings, beds, tables, sanitary ware
   and wardrobes. Prefer them because they are project-owned, take no space,
   resize correctly from the Inspector, and get 2D and 3D from one entity.
2. **CC0 content** for materials and decorative models:
   - ambientCG and Poly Haven for PBR textures and HDRIs;
   - Poly Haven, Kenney and Quaternius for models.
   - CC-BY is acceptable only if the attribution is recorded in provenance.
   - Never use NC/ND licenses, or "free download" with no clear license.
3. **User imports** (glTF/GLB first, OBJ second) into a per-user catalog.

Home Designer / Chief Architect catalogs belong in none of these. They are
licensed content of Chief Architect and of the manufacturers named in the
`Copyrights` table. The owner may study them on their own machine, as
described in the next section. Nothing derived from them may enter the
repository or any distributed build.

## Reading Home Designer catalogs (local study only)

- Inspect a catalog with the bundled read-only script:
  `python .claude/skills/archforge-library/scripts/calib_inspect.py <file.calib> [--out x.json] [--hex]`
- To study a big catalog (furniture is 30 MB to 5 GB), first print where its
  bytes live, then cut a few objects into a small sample:
  `python .claude/skills/archforge-library/scripts/calib_sample.py <file.calib> --stats`
  `python .claude/skills/archforge-library/scripts/calib_sample.py <file.calib> --out sample.calib --count 3`
- Experimental 3D extraction, writing OBJ files to compare visually against Home Designer:
  `python .claude/skills/archforge-library/scripts/calib_mesh.py <file.calib|.calibz> --name <text> --out-dir <dir>`
- `references/calib-format.md` holds everything decoded so far, with each
  item marked verified or guess. Update that file whenever you learn
  something new from a real file. That keeps the next agent from redoing
  the reverse engineering.
- Never decode by guessing. Confirm every field against more than one
  record, and against more than one catalog when possible.
- An app-side importer must:
  - read the catalog **in place** from the user's Home Designer install;
  - write results only under the user data folder
    (`%APPDATA%\ArchForge\hd-cache\` on Windows, or
    `~/.local/share/ArchForge/hd-cache/`);
  - mark every item `provenance.source = "home-designer-calib"` and
    `redistributable: false`;
  - show that mark in the Library UI.
- Excluded from the repo by `.gitignore`: `*.calib`, `*.calibz`,
  `*.tbdata`, and `hd-cache/`. Do not attach these files to tests. Write
  tests against tiny synthetic SQLite files that the test builds itself.

## In the app (implemented)
- `archforge/library/hd_calib.py` is the catalog reader and mesh parser. The skill scripts reuse it.
- `archforge/library/assets.py` stores imported meshes in the user data folder (`ARCHFORGE_DATA` overrides it).
  - Each mesh is normalised to metres, centred on X/Y, with its base at Z=0.
  - Its id is a content hash, so importing the same object twice keeps one copy.
- `archforge/library/objects.py` derives the geometry of `library_object` entities.
  - The entity holds `x, y, z, rotation` (degrees), `width, depth, height` (metres), `uniform` (1 = keep proportions) and `asset`.
  - The mesh is the asset scaled per axis to the target size. A missing asset gives a placeholder box of that size.
- 2D plan symbols come from `archforge/library/plan_symbol.py`: the top-view outline plus lines where the height jumps.
- glTF/GLB files are read by `archforge/library/gltf.py` (Y-up converted to Z-up, base colours, display bases dropped).
- Material parts: each palette colour of an asset is part `part<i>` (with `part_names`).
  - The user's palette finish is stored in `surface_materials["part<i>"]`, exactly like wall faces.
  - `material_id` applies one finish to the whole object.
- Sculpt: the surface `body` is deformable. Sculpt centres are stored as fractions of the object's own width, depth and height (see `geometry/surface_frame.py`), so they follow moves, rotations and resizes.
- The Object Modifier (`ui/object_modifier.py`) opens from the Inspector. It edits size and lock, rotation, elevation, part materials, and the sculpt modifier list, all through the shared commands.
- UI: the **Βιβλιοθήκη** menu (place, Object Modifier, import glTF, import Home Designer), the **Έπιπλα** tab in the left panel, the `library_place` plan tool, and proportional resize in the Inspector.

## Parametric cabinets (implemented)
`archforge/kitchen/cabinets.py` defines the `cabinet` entity.
- Types: base, drawers, sink, wall, tall, wardrobe.
- Derived boxes per role: carcass, shelf, front, handle, plinth, worktop, rail.
- Panel thicknesses and gaps are constants, so resizing never distorts. The door count follows the width (60 cm per door, 50 cm in wardrobes).
- Placement through the Κουζίνα panel uses `wall_aligned` (back onto the nearest wall face, facing the room) and `snap_to_neighbours` (butt against a cabinet on the same run).
- Verify new cabinet types with sheets at several widths (3D next to the plan), as for imported objects.

## Every import is verified: geometry against the visual result
Follow `references/verification.md` for each new object, whatever its source:
- measure the size against what the object must be;
- render a verification sheet with `scripts/asset_preview.py`: 3D views, top view with the outline overlaid, and the 2D symbol;
- judge the sheet against the source;
- fix the importer or reject the item;
- log the finding in the findings table there.

Content sources and their rules are in `references/sources.md`:
- ArchForge originals, including photo-built models made with `scripts/build_model.py`. No brands; the photo is reference only.
- Khronos CC0/CC-BY models fetched with `scripts/fetch_khronos.py`.
- User glTF files.
- Home Designer catalogs.

## Catalog format

Shipped and shared libraries use `.afcatalog`, a zip containing
`manifest.json`, `models/*.glb`, `textures/`, and `thumbs/`. The full
draft spec is in `references/catalog-format.md`. Each item has a `kind`:

- `parametric` items reference an entity kind and default params;
- `material` items are PBR definitions;
- `model` items reference a glb.

Every item carries `provenance`, which the AGENTS.md truth and provenance
rules require.

## Adding a parametric library object

A library object is just a new semantic entity kind, or a preset of an
existing one, flowing through the normal pipeline. Look at `plant`
(archforge/site/plants.py) and `kitchen_part`
(archforge/kitchen/generator.py) as worked examples. The touch points are:

1. Add the schema to `SCHEMAS` in `archforge/core/model.py`, using the
   existing validators (`_finite`, `_positive`, `_nonempty`, …). Validation
   is what keeps manual and AI edits on the same contract.
2. Add a geometry function in its own module that returns
   `(vertices, triangles, roles)`. Dispatch to it from
   `_payload` in `archforge/geometry/mesh.py`. The mesh must be closed,
   because tests check `validate_mesh(...).watertight`.
3. Register surface roles in `_KIND_ROLES` in `archforge/geometry/surfaces.py`.
4. Add the 2D plan symbol as a `Primitive2D` in
   `archforge/core/plan_scene.py`, and give it active-level filtering.
5. Add rendering materials in `_MATERIALS` in
   `archforge/rendering/scene.py`, split by role if the object has
   several finishes.
6. Placement goes through the shared commands (`AddEntity` /
   `UpdateEntity` on `CommandStack`). Never mutate the Document
   directly from UI code.
7. Write the test first (regression-first). Cover:
   - schema accept and reject;
   - the watertight mesh and its bounds;
   - the plan primitive;
   - add, then undo/redo, then save/load round trip.

Dimensions are metres in the Document. Convert millimetre or inch source
data at the boundary, and say so in a comment.

## Materials from catalogs

- Map imported colour and texture into the PBR fields used by
  `materialFor` in `archforge/ui/pbr_viewport.py`: `color`, `roughness`,
  `metalness`, an optional `map`, and repeat in metres.
- A greyscale shared texture plus a colour (as in HD PaperStone) means
  *tint*: use the colour as the base colour and the image as the map.
- Never claim a material's physical properties (fire rating, strength,
  thermal values) from catalog data. Catalogs describe appearance only.

## Before finishing library work
- Run the full `pytest` suite.
- Check `git status` for any `.calib`, `.tbdata`, `hd-cache` or texture
  file that should not be committed.
- Update `docs/WORKLOG.md`, both the done table and the queue items 15
  and 15α.
