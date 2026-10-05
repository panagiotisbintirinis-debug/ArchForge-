# Home Designer `.calib` catalog format: what is known

This page lists what has been verified against real catalogs (`IceStone.calib`
and `CoreBackdrops.calib` from Home Designer Pro 2023). Mark anything new as
*verified* (it has been checked against a real file) or *guess*. Do not
promote a guess into ArchForge code as fact.

## Container
- A plain **SQLite 3** database. Always open it read-only:
  `sqlite3.connect("file:X?mode=ro", uri=True)`.
- `.calibz` files (Bonus*, downloaded catalogs) are **not inspected yet**,
  but are probably a compressed `.calib`.

## Tables (verified)
| Table | Meaning |
|---|---|
| `LibraryObjects` | one row per catalog item: `LibraryObjectId, Name, Type, CopyrightId, Metric, UniqueId, LibSymDataId, PlantDataId, ...` |
| `Data4LibraryObjects` | `Data` BLOB: the proprietary binary record of the item |
| `SymbolData4LibraryObjects` | `SymbolData` BLOB. For materials and backdrops it is only a tiny JSON `{"Version": 2}` |
| `LibrarySymbolData` | `symDxf, symBlock, twoDRep, drawInfo, lightData`. **Empty** in material and backdrop catalogs; probably filled for 3D symbols/furniture (guess) |
| `LibraryViews` | `LibraryView` TEXT: the folder tree as XML (`<Directory Name=…><Item Id=…/>`), stored wrapped in single quotes |
| `Keywords`, `Keywords4LibraryObjects` | search tags |
| `Copyrights` | copyright owner text (Chief Architect, IceStone, …) |
| `PlantData` + view `PlantDataView` | plant metadata: height, zones, bloom, sun and water needs, common and scientific names |

## `LibraryObjects.Type` (verified values)
- `8` = material
- `10` = backdrop

Furniture, fixture, plant and other types are **not known yet**. Report
them as `type-<n>` until a sample confirms the value.

## Material record (`Type 8`, verified on 33 items)
- The record starts with a copyright string, folder names and keywords.
- Then comes a 16-byte GUID, followed by `<uint32 len><name>`.
- 5 bytes after the name comes the base colour, in one of two revisions:
  - `R G B FF 00 00 00 FF …`: newer records
  - `FF FF R G B 00 00 00 00 00 …`: older records
- Then the texture path: `<uint32 len incl. NUL><path>`, followed by `float64 repeat_u, float64 repeat_v`.
  - The repeat values are probably inches (35.0, 14.0, 15.0 are seen). The unit is a guess and is unverified.
- Several materials share one generic texture and differ only in colour. For example, all PaperStone items use `PaperStoneBase 512.JPG`. The texture is a greyscale pattern tinted by the colour.
- The trailing floats (`1.0 1.0 1.0`, `0.12…`, `0.2…`) are probably lighting coefficients: diffuse, specular, ambient. This is a guess.

## Backdrop record (`Type 10`)
- Holds only an image path. The image is **not embedded**.

## Images
Texture and backdrop paths point at the authoring machine
(`C:\Productivity\P4\content\…`, `C:\Users\Dustin\…`). The JPGs live
somewhere else in the user's Home Designer install, and that location is
**not found yet**. Verified on the user's machine: Home Designer Pro 2023
has no loose texture JPG/PNG files. The only loose images are help files.
The images are therefore probably embedded in the large catalogs; Kohler.calib
alone is 5.1 GB. This is a guess until a sample proves it. Resolve images by file name against a user-chosen folder.
Never resolve them by the stored absolute path.

## 3D symbols (`Type 14`): VERIFIED on 2 objects (Belwith-Keeler, 2026-10-05)
Verification: we extracted `B076086 Pull 1-1/2"` and `B076087 Knob 2" X 1"`.
- Their shapes match their names: a U-shaped pull and a T-shaped bar knob.
- The knob measures 50.0 × 25.3 × 25.3 mm. The name says 2" × 1" (50.8 × 25.4 mm).
- The pull is 53.3 × 27.1 × 27.0 mm, with 4806 triangles and 2406 unique vertices.

Layout:
- `.calibz` is **not** a zip. `calib_open.py` finds the embedded SQLite image by its header and carves it out. How the wrapper stores textures is still unknown.
- `LibraryObjects.LibSymDataId` points to `LibrarySymbolData`. In that row `symDxf` and `symBlock` are NULL. `twoDRep` (8 KB) is probably the 2D plan symbol, made of float64 (x, y) pairs. This is a guess.
- The 3D model is in `SymbolData4LibraryObjects.SymbolData`, a series of records that each start with `CD AB`.
- Mesh record, seen at offset 7048 in the pull:
  ```
  +0   CD AB 74 00
  +4   B2 0B                       (record version? guess)
  +6   FF FF FF FF
  +10  uint32 N                    triangle count (4806)
  +14  10 bytes                    unknown (03 00 04 00 00 00 00 00 08 11 in the pull)
  +24  N × 162-byte triangle records
  ```
  In the knob the count sits at +10 and the data at +24 in the same way.
- Triangle record, 162 bytes:
  - **verified:** `0..71` are 9 × float64, the vertices (x, y, z) × 3, in **inches**.
  - **guess:** `72..87` are uint32 a, uint32 b, int32 -1, uint32 3 (neighbour or edge indices?).
  - **guess:** `88..135` are 6 × float64 per-vertex UV pairs (values like 514.6, 14.26).
  - **guess:** `136..151` are 2 × float64 (20.0, 20.0), a texture scale?
  - **unknown:** `152..161` are 10 bytes, possibly a material index or flags.
- Axes are not yet confirmed. In the samples the long dimension lies on X and the model is centred near the origin.
- The remaining `CD AB` records (26 in the knob, 46 in some pulls) are not yet decoded. They are probably materials and other sub-objects.
- `scripts/calib_mesh.py` scans for this layout. It keeps the largest valid count at each marker, and among the alignments that decode it keeps the one with the fewest unique vertices.

## Open questions
- Where HD stores texture JPGs locally.
- 3D symbols: test the layout on furniture and other catalogs. Decode the UV, material and other bytes of each record, the other `CD AB` records, and the axis convention.
- The `.calibz` wrapper.
