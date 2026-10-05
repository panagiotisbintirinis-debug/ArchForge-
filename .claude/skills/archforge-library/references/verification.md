# Verifying library objects: geometry against the visual result

Every object entering the library passes this loop, whatever its source (Home Designer catalog, online CC0/CC-BY model, photo-built original). Numbers alone miss problems that pictures show, and pictures alone miss wrong scale. Check both.

## The loop
1. **Import or build** the object into the asset store (`ARCHFORGE_DATA` selects the store).
   - Use a scratch store while experimenting.
   - The asset gets its 2D plan symbol automatically (`archforge/library/plan_symbol.py`).
2. **Measure.** Compare the size (W × D × H, cm) with what the object must be:
   - a name or code that states dimensions (`Knob 2" X 1"`, `B2442`);
   - the expected range for its category (`fetch_khronos.py` holds a table);
   - real-world norms: seat height 42–48 cm, table 72–76 cm, worktop 90 cm, door 200–210 cm.
3. **Look.** Run `scripts/asset_preview.py <asset> --expect W,D,H --out sheet.png` and read the image. The sheet has two rows:
   - three shaded 3D views;
   - a top view of the mesh, the same top view with the plan outline drawn in red, and the 2D symbol alone.
4. **Judge** the sheet against the source: the photo, the catalog thumbnail, or the object's name.
   - Is it the object it claims to be, and the right way up?
   - Is it the right size, with nothing extra?
   - Does the red outline sit on the mesh edge?
   - Do the inner lines of the symbol mark real height changes (seat and back, cushions, arms)?
5. **Fix or reject.**
   - Fix the importer when the problem is generic.
   - Reject the item when the problem is in the source file.
   - Record the finding below, so the next agent does not repeat it.

## Findings so far (2026-10-05)
| Source | Problem seen | Resolution |
|---|---|---|
| Khronos `Lantern` | 25.7 m tall street light | Wrong scale in the source; size check flags it. Not curated. |
| Khronos `TrafficCone` | Two cones on a 2.4 m display plate, plus a floating demo bulb | Plate removed by `drop_ground_planes`. The bulb stays, so the item is rejected and not curated. |
| Khronos `LightsPunctualLamp` | Flagged as a "desk lamp" at 186 cm | Our category was wrong: it is a floor lamp. Category fixed. |
| Khronos `GlamVelvetSofa` | Rendered black | Its colour comes from a base-colour texture; we now multiply in the texture's average colour. |
| Khronos `SheenWoodLeatherSofa` | Grey | WebP/KTX textures are not read; the colour is missing, the geometry is fine. |
| Plan symbol | Jagged raster outline; noisy step-lines on curved backs | Douglas–Peucker 1.6 cells; inner lines shorter than 10 cells dropped. |
| HD catalog meshes | Parts of grouped sets come out at local origins | Each part is imported as a separate item; placement inside the group is not decoded. |
