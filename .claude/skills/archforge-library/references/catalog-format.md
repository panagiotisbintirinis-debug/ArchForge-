# ArchForge catalog format (`.afcatalog`), draft v0

A catalog is a **zip** file. It can be shared on its own and added to an
install without changing ArchForge code.

```
kitchen-basics.afcatalog
├── manifest.json
├── models/      *.glb         (glTF binary, metres, Z-up, origin at the insertion point on the floor)
├── textures/    *.jpg|*.png   (≤ 2048 px; 1K preferred)
└── thumbs/      *.png         (256×256)
```

## manifest.json
```json
{
  "format": "archforge-catalog",
  "version": 0,
  "id": "archforge.core.kitchen",
  "title": {"el": "Κουζίνα – βασικά", "en": "Kitchen basics"},
  "redistributable": true,
  "items": [
    {
      "id": "base-cabinet-600",
      "kind": "parametric",
      "entity": "kitchen_part",
      "defaults": {"width": 0.6, "depth": 0.6, "height": 0.72, "role": "base"},
      "category": ["Κουζίνα", "Ντουλάπια βάσης"],
      "keywords": ["cabinet", "ντουλάπι"],
      "thumbnail": "thumbs/base-cabinet-600.png",
      "provenance": {"source": "archforge", "license": "project", "author": "ArchForge"}
    },
    {
      "id": "oak-floor",
      "kind": "material",
      "pbr": {"color": "#a4784f", "roughness": 0.6, "metalness": 0.0,
              "map": "textures/oak_diff_1k.jpg", "normalMap": "textures/oak_nor_1k.jpg",
              "repeat_m": [1.2, 1.2]},
      "category": ["Υλικά", "Ξύλο"],
      "provenance": {"source": "https://ambientcg.com/view?id=WoodFloor041", "license": "CC0-1.0"}
    },
    {
      "id": "armchair-01",
      "kind": "model",
      "model": "models/armchair-01.glb",
      "bbox_m": [0.82, 0.78, 0.9],
      "category": ["Έπιπλα", "Σαλόνι"],
      "provenance": {"source": "https://polyhaven.com/a/…", "license": "CC0-1.0", "author": "…"}
    }
  ]
}
```

## Item kinds
- `parametric` creates a normal Document entity through the shared commands
  (`AddEntity`). This is the preferred kind, because it is editable,
  undoable, has a 2D symbol, and gets 3D from the same entity.
- `material` is a PBR definition that can be applied to a surface role or
  an entity.
- `model` is a static mesh. When placed, it becomes a Document entity that
  holds the catalog reference, position, rotation and scale. The mesh is a
  derived view, so it is not copied into the Document.

## Rules
- Every item carries `provenance.source` and `provenance.license`.
- A catalog may set `"redistributable": true` only when **every** item
  license allows redistribution (CC0, CC-BY with attribution recorded, or
  project-owned).
- Local study catalogs built from Home Designer use
  `"redistributable": false` and `"source": "home-designer-calib"`. They
  live only in the user data folder (see SKILL.md).
