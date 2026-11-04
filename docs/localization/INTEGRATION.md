# English interface and mockup integration

Owner, 4 November 2026: English throughout the application, language selection,
Greek available, additional languages later. This work lives on the separate
`codex/english-interface` branch. Do not merge it as a completed English release.

## Current scope and remaining work

The initial implementation supplies a local JSON catalog service, English as its
default, persistent language preference, explicit live Qt label bindings, and the
Settings language selector. The semantic property-field labels and the parameter
labels in `ui/object_properties.py` use the catalogs. The raw property registry,
parameter ids, numeric values, commands and Document serialization stay intact.

**The rest of the legacy interface is not yet translated.** Existing menus,
toolbar/mouse labels, help, messages, reports, other property editors, built-in
library labels, and web overlays require context-specific migration. The selector
currently changes the migrated controls only. Do not call partial catalog coverage
a complete application translation. A source scan is a candidate list, not proof
that each string is user-facing, and not proof that every displayed string is found.

## Concurrent work: Claude's menu inventory

Read Claude's current menu work before connecting legacy actions. Latest document
reviewed for this checkpoint:

- Branch: `claude/youthful-fermat-ia4gem`
- Commit: `55ab149434295993ba654dde394deae3368af68d`
- [docs/specs/archicad_menus.md](https://github.com/panagiotisbintirinis-debug/ArchForge-/blob/55ab149434295993ba654dde394deae3368af68d/docs/specs/archicad_menus.md)

That document compares functions and proposed behaviors. It is not a final
machine-readable inventory of implemented commands, stable ids and approved labels.
Its proposed commands are not treated as implemented features here. No menu-map,
mockup layout or command placement is rewritten in this branch. The existing
path readers in `main_menus`, `toolbar_custom` and `mouse_menus` use a preserved
source-label alias for translated actions; copied/popup labels use the display text.

The integration contract is:

1. Claude's approved inventory owns grouping, placement and behavior.
2. Each command/control has a stable id separate from its displayed label and path.
3. Each display role has a translation key: label, tooltip, help, error, placeholder.
4. A move to another menu keeps the same command id and translation keys.
5. Bind the original QAction/widget. Keep callback, data, shortcuts, checked state,
   undo behavior and saved customization ids. Never create a replacement command
   because its label changed.
6. Audit the existing text-derived paths in `toolbar_custom`, `mouse_menus`,
   `main_menus`, `layout2`, `shortcuts` and `task_icons` before translating their
   existing QActions. Their current paths are still Greek and must remain resolvable.
7. Re-read live develop and the latest inventory; validate the combined result
   before proposing an integration. The owner reviews before merge.

Inventory input for the shared audit tool is an array or an object with `items`:

```json
{"items": [{"id": "project.save", "label_key": "command.save", "path": "Project / File"}]}
```

`path` is descriptive, never the identifier. `tooltip_key` is optional and is
validated when present. The tool rejects missing source keys and duplicate ids.
`ui.language.bind_inventory(actions_by_id, items)` validates the entire mapping
before binding the original live QActions/QMenus. It does not create, move or
replace commands. Existing source paths remain compatibility aliases, separate
from both the new stable id and the translated display text.

## Translation rules

- English (`en.json`) is the canonical text catalog. Keys describe the meaning,
  e.g. `property.door.width`, not the current menu position or Greek label.
- Greek (`el.json`) is a translation catalog. Additional valid `code.json` files
  with `code`, `native_name`, and `messages` appear in the selector automatically
  at the next launch. Missing entries in a partial language fall back to English.
- Do not translate by replacing Greek substrings across widget text or files.
  A saved project name, note, material code, supplier name or imported object is
  user data, even if it happens to equal a catalog label.
- Translate the template first, then interpolate values once. Keep each named
  placeholder and its format spec unchanged; validation rejects mismatches.
- Keep `mm`, `m`, `kW`, technical identifiers, decimal precision, regulatory
  provenance, and country/units settings independent of interface language.
- Existing project names/annotations stay verbatim. Translate built-in catalog
  descriptions at display time, while keeping asset/material ids unchanged.
- Bind static controls with `ui.language.bind`. Recompute dynamic text through
  `localization.text` as part of its existing document refresh. A language callback
  must not rebuild an editor and discard an unfinished human edit.
- Use separate keys where Greek has several meanings. The following are reviewed
  terminology choices for this project, not a claim of regulatory verification.

| Context | English |
|---|---|
| Πλάκα: structural element | Slab |
| Δάπεδο: room surface/finish | Floor |
| Όροφος | Storey |
| Στάθμη: vertical coordinate | Elevation |
| Ξυλότυπος | Formwork |
| Δοκός / κολόνα | Beam / column |
| Ρίχτι / πάτημα σκάλας | Riser / tread |
| Ποδιά παραθύρου | Window sill |
| Έλξη / κάνναβος | Snapping / grid |
| Σύνθεση τοίχου | Wall assembly |
| Υπόβαθρο σχεδίου | Drawing underlay |

## Verification

```bash
python scripts/toolbox/localization_audit.py --inventory menu_inventory.json
python scripts/toolbox/localization_audit.py --scan --json
QT_QPA_PLATFORM=offscreen python -m pytest -q tests/test_localization.py
```

The audit reads only. Catalog structure, keys and placeholders can pass while
legacy text is still Greek. Full completion also needs every display role mapped,
English/Greek command-path equivalence, project text/save/undo preservation, 2D and
web-overlay checks, clipped-label inspection, and the owner's Windows review.
Windows packaging explicitly includes `archforge/localization/catalogs`.
