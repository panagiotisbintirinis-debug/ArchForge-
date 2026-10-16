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

## 3D symbols: VERIFIED (2026-10-05)
Verified on Belwith-Keeler handles (`Type 14`, 5 objects) and on `Living Room 03` from `BonusGroupedLivingRooms` (`Type 19`, a grouped object).

| Object | Extracted size | Matches |
|---|---|---|
| Knob 2" × 1" | 50.0 × 25.3 × 25.3 mm | the name |
| Pull 3-3/4" (96 mm) | 110 mm long | 96 mm between holes plus the ends |
| Living room sofa | 2.03 × 0.81 × 0.87 m | a sofa |

The other living-room parts are a round rug (0.91 m), a leaning mirror (2.10 m), an orb vase, a stretch vase and stacked books. All are recognisable when rendered. **Z is up**, and units are **inches**.

### Containers
- `.calibz` is **not** a zip. `calib_open.py` finds the embedded SQLite image by its header and carves it out. Where the wrapper keeps textures is still unknown.
- The 3D data is in `SymbolData4LibraryObjects.SymbolData`. For each object, `LibrarySymbolData.twoDRep` probably holds the 2D plan symbol. That is a guess.
- `SymbolData` is a series of records, each starting with `CD AB <uint16 type>`. Types seen:
  - `0x74`: **mesh**, decoded below.
  - `0x61`: placed sub-object, carrying a catalog path string such as `Bonus Living Room Items:Accessories/Orb Vase` or `Sofa/Sofa`. Probably holds its transform; not decoded.
  - `0x30`: 124 in the living room, each starting with a 16-byte GUID. Probably materials.
  - `0x1f`, `0x28`, `0x22`, `0x23`: unknown.

### Mesh record `CD AB 74 00`
```
+0   CD AB 74 00
+4   uint16 version            B2 0B (Belwith), AF 08 (Bonus living room)
+6   FF FF FF FF
+10  uint32 P                  polygon count
+14  P polygon records, back to back, variable length:
       uint16 n                vertex count (3, 4, 5, ... seen)
       uint16 flags            (0x0000, 0x1000, 0x100a ... seen; meaning unknown)
       uint32 index            0, 1, 2 ... (surface/material index? guess)
       uint16 ?
       n × 3 float64           vertices x, y, z in inches          VERIFIED
       n × int32               neighbouring polygon per edge, -1 = open edge   (guess, fits values)
       uint32 k                UV count: n (Belwith) or 0 (living room)   VERIFIED as a length
       k × 2 float64           UV pairs (guess)
       2 float64               20.0, 20.0 in Belwith (texture scale? guess)
```
- Walking these lengths exactly consumes every mesh record completely: 4806 of 4806 polygons in the pull, and every polygon of the 6 complete living-room meshes.
- The Belwith "162-byte stride" is just this layout with n = 3 and k = 3.
- Mesh coordinates are **local to each part**. Placement inside grouped objects is not decoded yet; it probably lives in the `0x61` records.
- `scripts/calib_mesh.py` implements this parser. It writes one OBJ object per mesh record and flags truncated or undecodable records as INCOMPLETE.

### Grouped cabinet sets (`BonusGroupedIslands`, `Island 06`, verified 2026-10-05)
- `SymbolData` (48 KB) holds only:
  - one `0x61` sub-object `Seating:Chairs/Side Chairs/Low-back`;
  - its mesh, a bar stool of 46 × 50 × 105 cm, parsed completely;
  - small `0x30`, `0x1f` and `0x28` records. These contain ±1.0 and π/2 values, so they are probably transforms or curve primitives (guess).
- **The cabinets are not meshes.** They are stored **parametrically** in `Data4LibraryObjects.Data` (60 KB):
  - each base cabinet carries its code (`BCB2442L`, `B2442R`), size text (`24x24x42"`) and material (`material - Yellow Cedar`);
  - each also lists its parts: `drawer 20 1/2x7 1/2"`, `hidden hinge`, `drawer glide`, and several `Filler 2 5/8x42"`.
  - The blob uses its own `CD AB` record types (`0x0132` ×44, `0x013e`, `0x0107`, `0x7b`, `0x72`, `0x0f`, `0x6d`). Not decoded.
- Consequence for ArchForge: HD cabinets should map to **ArchForge parametric cabinets** (WORKLOG 13α, `kitchen_part`), not to static meshes. That fits the human-first, parametric product rule.

## Open questions
- Where HD stores texture JPGs locally.
- 3D symbols: decode the transforms of the sub-objects (`0x61`?), the materials, the UVs and the texture images.
- Parametric cabinet records in `Data`: width, depth and height, position, door and drawer layout, material.
- The `.calibz` wrapper.
