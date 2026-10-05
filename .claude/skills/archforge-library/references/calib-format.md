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

## Open questions
- Where HD stores texture JPGs locally.
- Furniture/3D object geometry: which table holds it and whether it can be decoded.
- The `.calibz` wrapper.
