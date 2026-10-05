# Where library content comes from

## 1. ArchForge originals (preferred, shippable)
- **Parametric generators in code**, for cabinets, wardrobes, doors, windows, stairs and railings. They resize without distortion.
- **Photo-built models** with `scripts/build_model.py`:
  - The agent looks at a reference photo, writes a spec of simple solids in cm, builds it, and runs the verification loop (`verification.md`) against the photo.
  - The result is our own model, with provenance `archforge-original` and licence `project`. It can be shared freely.
  - The photo is **reference only**. Do not store it, ship it, or use it as a texture.
  - Use **generic names**, never brands: "lounge armchair", not a manufacturer's product name.
  - Do not make exact replicas of distinctive designer pieces that may be protected as registered designs. Model the generic type.
  - Get dimensions from the photo's proportions, anchored to one known size (seat height 45 cm, door 210 cm, worktop 90 cm). Record that anchor in the spec.

## 2. Online models with an open licence (shippable with attribution)
- Reachable from the agent sandbox: **`raw.githubusercontent.com`** only.
  - Blocked by the environment's network policy: Poly Haven, ambientCG, Kenney, Sketchfab.
  - On the owner's PC these sites work, and the same rules apply.
- `scripts/fetch_khronos.py` pulls curated furniture from KhronosGroup/glTF-Sample-Assets.
  - Each model's `metadata.json` lists SPDX licences. Only CC0-1.0 and CC-BY-4.0 are accepted (Khronos legal marks are ignored).
  - Artists are stored in `provenance.attribution`. CC-BY requires showing that attribution wherever the item ships.
- Never accept NC/ND licences, "free download" without a licence, or editorial-only content.

## 3. User files (local, not shipped)
- **Menu Βιβλιοθήκη → Εισαγωγή μοντέλου glTF/GLB…**
  - Provenance is `user-file`, with `redistributable: false`.
  - Display bases (flat floor plates) are removed automatically.

## 4. Home Designer catalogs (local study and use only)
- See SKILL.md and `calib-format.md`.
- Provenance is `home-designer-calib`, with `redistributable: false`.

## Next: cabinets and wardrobes (owner request, 2026-10-05)
Build kitchen cabinets and wardrobes with the same loop, but **parametric**: width, height, doors, drawers and shelves come from parameters (`kitchen_part` / WORKLOG 13α), not from a fixed mesh.
- Each generator gets verification sheets for several sizes, and the 2D symbol comes from the same geometry.
- HD cabinet parameters decoded from `Data` (code, size, material, drawers) should map onto these generators.
