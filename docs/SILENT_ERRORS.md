# Σιωπηλά λάθη (λίστα εργασιών Α3) — απογραφή

> Απογραφή του **Astra** (28/10/2026, στατικός έλεγχος του branch `claude/wonderful-pasteur-ejxzix`, χωρίς
> `core/commands.py`). Τα «τι θα έβλεπε ο χρήστης» λένε τι **μπορεί** να συμβεί αν προκύψει η εξαίρεση, όχι λάθη
> που αναπαράχθηκαν· όποιο αναπαραχθεί γράφεται εδώ ως ΕΠΑΛΗΘΕΥΤΗΚΕ. Διαδρομές από `archforge/`, γραμμή = το `except`.
> Δεν χαρακτηρίστηκαν σιωπηλά όσα επιστρέφουν διαγνωστικό ή προειδοποιούν αργότερα (`AICommandError`,
> `GeometryIssue`, αναφορά φόρτωσης έργου, `structure/analysis/building.py:365`).

**Κατηγορίες:** **Α** χάνεται δουλειά/ρύθμιση του χρήστη · **Β** λάθος ή ελλιπές αποτέλεσμα χωρίς προειδοποίηση ·
**Γ** αθώο (προαιρετικό, καθάρισμα, εναλλακτική κωδικοποίηση).

## Α — χάνονται δεδομένα (όλα διορθώθηκαν 28/10)

| Σημείο | Τι συνέβαινε | Κατάσταση |
|---|---|---|
| `quantities/price_book.py:24` | Κομμένος τιμοκατάλογος (διακοπή ρεύματος, OneDrive/antivirus) → διαβαζόταν ως άδειος → με την επόμενη τιμή **έμεναν 1 από 50 τιμές**. Και η εγγραφή δεν ήταν ασφαλής (μισό αρχείο). | **ΕΠΑΛΗΘΕΥΤΗΚΕ** με εκτέλεση → διορθώθηκε: αντίγραφο `.broken-…` πριν από κάθε εγγραφή, ειδοποίηση, `atomic_write`· αν δεν διαβάζεται καθόλου, δεν γράφεται τίποτα |
| `ui/autosave.py:43` | Κατεστραμμένο `settings.json` → `{}` → με την επόμενη ρύθμιση **χάνονταν όλες οι άλλες** (και τα υλικά του χρήστη). | **ΕΠΑΛΗΘΕΥΤΗΚΕ** → ίδια διόρθωση (`persistence.read_user_json`) |
| `rendering/user_materials.py:263` | Υλικά από το ίδιο `settings.json`: ίδια απώλεια. | Καλύπτεται από την παραπάνω (το παλιό αρχείο κρατιέται πριν γραφτεί) |
| `ui/toolbar_custom.py:58` | Κατεστραμμένες προσαρμογές ribbon/ποντικιού → προεπιλογές → χάνονταν με την επόμενη αποθήκευση. | Διορθώθηκε: κρατιούνται στο `custom/prefs_broken`, ειδοποίηση |
| `ui/autosave.py:143` | Αποτυχία εγγραφής ανάκτησης (π.χ. γεμάτος δίσκος) χωρίς μήνυμα· το «Αυτόματη αποθήκευση» είχε ήδη φανεί. | Διορθώθηκε: η επόμενη αποθήκευση λέει «η προηγούμενη απέτυχε (αιτία)» και ξαναδοκιμάζει |

Τεστ: `tests/test_user_data_files_kept.py`, `tests/test_ui_autosave_recovery.py` (2 νέα).

## Β — λάθος/ελλιπές αποτέλεσμα χωρίς προειδοποίηση

**Μηχανισμός (28/10):** `archforge/core/notices.py` — `not_computed(code, μήνυμα, στοιχείο, exc)` στο σημείο,
`collecting()` σε ό,τι τρέχει ο χρήστης (προσφορά: `quote()["not_computed"]` → «ΕΛΛΙΠΕΣ» στην καρτέλα
Επαγγέλματα· Ολοκλήρωση κτιρίου: «ΕΛΛΙΠΕΣ» στο βήμα), και για όλα τα άλλα η **γραμμή κατάστασης** μετά από
κάθε ενέργεια («Δεν υπολογίστηκε: …»). Μορφή = το ίδιο `Issue` με τη γεωμετρία (`GeometryIssue`).

**Έκλεισαν 28/10 (✓):** `construction/shell.py:102` · `construction/earthworks.py:77, 89` · `quantities/takeoff.py:112`
· `output/formwork.py:59, 282` · `construction/drywall.py:189` · `architecture/roof_need.py:41, 122, 150` (και: με
άγνωστη κάλυψη **δεν προστίθεται ούτε αφαιρείται στέγη**) · `architecture/storey_slabs.py:477` ·
`architecture/stairs.py:402, 422` · `scenarios/gate.py:213, 321` (ό,τι δεν ελέγχθηκε δεν γράφεται πια «ελεύθερο»).
**Εισαγωγή (✓):** `project/underlay.py:43, 116` και `site/survey.py:58, 72, 130` (γραμμές που δεν διαβάστηκαν
μετριούνται, ένα μήνυμα ανά αρχείο με παράδειγμα γραμμής) · `site/plateaus.py:85, 132` · `site/terrain.py:94` ·
`ui/building_from_underlay.py:134, 150` · `ui/drawing_set_import.py:479, 483, 580` — η αναφορά «Σύνολο σχεδίων»
γράφει «ΕΛΛΙΠΗΣ ΕΙΣΑΓΩΓΗ — δεν διαβάστηκαν: …».
**Τοίχοι, ανοίγματα, διαστάσεις (✓):** `architecture/dimension_reference.py:49` · `architecture/dimensions.py:89, 199,
204` · `architecture/joinery.py:288` · `architecture/railings.py:567` · `architecture/wall_edit.py:160`.
**Εξετάστηκαν και μένουν (λόγος):** `architecture/openings.py:113, 169` και `architecture/wall_edit.py:365` τρέχουν σε
κάθε κίνηση του ποντικιού (εύρεση τοίχου / προεπισκόπηση)· τοίχος που δεν προβάλλεται (μηδενικό μήκος) δεν μπορεί να
φιλοξενήσει άνοιγμα, και η εντολή μετακίνησης τοίχου λέει πια ό,τι δεν ελέγχθηκε (`wall_edit.py:160`) ·
`architecture/railings.py:586`: κρατά έγκυρη θέση για κρυφό κάγκελο, το 567 το λέει.
**Η/Μ, φωτισμός (✓):** `mep/conduits.py:53` · `mep/electrical.py:176` · `mep/heating_layout.py:88` · `mep/lighting.py:66`
· `ui/lighting_system.py:205` · `ui/lighting_panel.py:48` · `library/lighting.py:110` · `ui/plumbing_tab.py:132`.
Μένει: `ui/lighting_mep_bridge.py:50` (μεταβατικό `ModuleNotFoundError`· το `mep/lighting.py` υπάρχει, δεν εκτελείται).
**Κάτοψη, 3D (✓):** `core/plan_scene.py:544, 845` (και: αποτυχία δεν αποθηκεύεται πια ως «κανένας τοίχος»), `890` ·
`core/interaction.py:638` (άγνωστοι χώροι: δεν μπαίνει στο έδαφος) · `core/layers.py:113` · `rendering/scene.py:579` ·
`kinematics/authoring.py:72` · `ui/plan_view.py:34, 944`. Μένουν (κάθε κίνηση ποντικιού: κούμπωμα/επιλογή):
`core/snapping.py:270`, `core/interaction.py:151`, `ui/plan_view.py:187`.
**Βιβλιοθήκη, υλικά, Ιδιότητες (✓):** `library/assets.py:139` · `ui/library_instance_integration.py:62` ·
`ui/material_library.py:100` · `ui/material_object_integration.py:19` (άγνωστο τμήμα: **το υλικό δεν εφαρμόζεται**
σε όλο το αντικείμενο), `49` (η κάρτα γράφει «δεν διαβάστηκε», όχι «προεπιλογή»), `307` · `ui/material_properties.py:45`
· `ui/light_properties.py:142, 161` (μήνυμα για μη αριθμό / εκτός ορίων) · `ui/object_preview.py:84` ·
`ui/mouse_menus.py:473` · `ui/layout_assist.py:252` · `ui/stair_dialog.py:52` (η αιτία μέσα στην προεπισκόπηση),
`287` (γραμμή στη φόρμα). Μένει: `ui/stair_dialog.py:86` (ζωγραφική· το λέει το `railings.py:567`).
**Δέντρο έργου, βοηθός, ενημερώσεις (✓):** `ui/project_outline.py:51, 93, 118, 161, 378` ·
`assistant/understanding.py:107` · `updates.py:39, 53` («ο έλεγχος απέτυχε» αντί για «έχεις την τελευταία έκδοση»).

**Όλα τα Β εξετάστηκαν (28/10).** Ό,τι σημειώνεται «μένει» έχει τον λόγο του δίπλα.

**Η αρχική ομαδοποίηση του Astra (για αναφορά):** ποσότητες · στέγες/πλάκες/σκάλες · εισαγωγή · πύλη (1) ·
τοίχοι/ανοίγματα · Η/Μ · κάτοψη/3D (2) · βιβλιοθήκη/υλικά · δέντρο έργου/ενημερώσεις (3).

## Γ — αθώα (μένουν)

`architecture/stair_options.py:48, 64` · `architecture/wall_dims.py:94` · `core/model.py:1167, 1189` ·
`core/interaction.py:1206, 1217` · `geometry/picking.py:102` · `geometry/sculpt.py:124` · `library/bundled_lights.py:28, 41`
· `library/gltf.py:92, 105` · `library/thumbnail.py:43` · `output/section_cut.py:148` ·
`project/persistence.py:62, 68, 192, 279, 321, 348` · `rendering/user_materials.py:98, 121, 442` · `scenarios/render3d.py:57`
· `site/survey.py:306` · `ui/autosave.py:158` · `ui/drywall_tools.py:195` · `ui/slab_tools.py:293` ·
`ui/fixture_controls.py:51` · `ui/indication.py:30` · `ui/library_drag.py:41` · `ui/library_icons.py:52` ·
`ui/library_instance_integration.py:51` · `ui/lighting_system.py:253` · `ui/material_codes.py:267` ·
`ui/material_object_integration.py:170` · `ui/pattern_swatch.py:90` · `ui/pbr_viewport.py:2428` ·
`ui/project_outline.py:126` · `ui/start_page.py:36, 48, 54` · `ui/underlay_tools.py:98` · `ui/updates_ui.py:65` ·
`ui/wall_edit_3d.py:103, 146, 378`.
