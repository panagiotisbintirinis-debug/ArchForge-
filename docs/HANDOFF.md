# ArchForge — Συνέχεια συνομιλίας (handoff)

> **Νέο chat / νέος agent: διάβασε πρώτα αυτό**, μετά `AGENTS.md` και `docs/WORKLOG.md`.
> Το αρχείο κρατά ό,τι ειπώθηκε στη συνομιλία με τον ιδιοκτήτη και δεν φαίνεται μόνο από τον κώδικα:
> - τι ζήτησε και με ποια λόγια·
> - τι αποφασίσαμε και γιατί·
> - πού σταματήσαμε.
>
> Ενημερώνεται σε κάθε commit που αλλάζει κατεύθυνση ή κλείνει στοιχείο.

Τελευταία ενημέρωση: 2026-10-05 · branch `claude/new-session-hiekda` (συνέχεια του `claude/new-session-l1o9gl`) · tests: 689 passed, 1 skipped.

---

## 1. Πώς δουλεύουμε με τον ιδιοκτήτη

- **Γλώσσα και ρυθμός:** απαντάμε **στα ελληνικά**. Ο ιδιοκτήτης δίνει στοιχεία· εκτελούνται **με τη σειρά**, ένα-ένα, με test, commit και push.
- **Branch:** κάθε chat έχει δικό του branch `claude/...`· το νέο ξεκινά από το τελευταίο (τώρα `claude/new-session-hiekda`, που περιέχει όλο το `claude/new-session-l1o9gl`). Ποτέ push στο `develop`. Ποτέ PR χωρίς ρητό αίτημα.
- **Τεκμηρίωση:** το `docs/WORKLOG.md` ενημερώνεται σε κάθε στοιχείο: πίνακας ολοκληρωμένων, ουρά, ιστορικό λαθών.
- **Δοκιμή στα Windows από τον ιδιοκτήτη:** `cd C:\Users\User\ArchForge-test` → `git pull` → `py -m pytest -q` → `py run_app.py`.
- **Αρχές προϊόντος (AGENTS.md):**
  - human-first· το Document είναι η μοναδική αλήθεια·
  - κάθε αλλαγή περνά από κοινές εντολές: `AddEntity`, `UpdateEntity`, `MoveEntities`, `RotateEntities`, με undo/redo·
  - η γεωμετρία παράγεται από το Document (derived)· regression-first tests.
- **Μηχανικές τιμές:**
  - Πάντα με πηγή και την ένδειξη «προμελέτη, προς έλεγχο μηχανικού / ηλεκτρολόγου / μηχανολόγου».
  - Ποτέ ως επαληθευμένες.
  - Ο ιδιοκτήτης: «εάν το πρόγραμμα αντλήσει στοιχεία … τα οποία είναι ευρέως αποδεκτά, τότε δεν θα υπάρχει σύγκρουση μεταξύ μηχανολόγου και προγράμματος».
  - Δηλαδή χρησιμοποιούμε ευρέως αποδεκτούς κανόνες και πρότυπα, τα δηλώνουμε ρητά και δεν μαντεύουμε.

## 2. Τι ζήτησε ο ιδιοκτήτης (με τη σειρά) και τι έγινε

| Αίτημα (περίληψη των λόγων του) | Αποτέλεσμα | Commit |
|---|---|---|
| Μελέτη των βιβλιοθηκών Home Designer (.calib) και δημιουργία skill γι' αυτό | `.claude/skills/archforge-library/`· τοπικός, read-only αναγνώστης· αποκωδικοποίηση των 3D meshes | 1f1e074 … b252e07 |
| «Αν θέλω να δώσω το ArchForge σε άλλον, πρέπει να έχει δική του βιβλιοθήκη» | Δική μας βιβλιοθήκη (asset store σε `%APPDATA%\ArchForge\library`). Τα αρχεία HD **δεν** μπαίνουν ποτέ στο repo (`.gitignore`) | 5bf53cf |
| Online αντικείμενα (CC0/CC-BY) και «από φωτογραφία», με επαλήθευση γεωμετρίας από το οπτικό αποτέλεσμα | Εισαγωγή glTF, 2D σύμβολα κάτοψης, φύλλα επαλήθευσης. «Όχι μάρκες»: η φωτογραφία είναι μόνο αναφορά, το μοντέλο είναι δικό μας | 9c63fb8 |
| Χρώμα/υφή ανά τμήμα από την παλέτα (όπως οι τοίχοι), Sculpt, **Object Modifier** συνδεδεμένος με τις Properties | ObjectModifierDialog, υλικά ανά τμήμα, sculpt modifiers | 94b252c |
| Ντουλάπια κουζίνας και ντουλάπες με την ίδια λογική (παραμετρικά) | `kitchen/cabinets.py` | 8e022cd |
| «Κάνε το tree πραγματικό, μην εμφανίζει πράγματα που δεν υπάρχουν» | Το δέντρο Έργου γεμίζει από το Document | eb4e397 |
| Εμπλουτισμός όλων των βιβλιοθηκών: βασικά πρώτα, μικρές παραλλαγές | 39 δικά μας αντικείμενα, 4 καρτέλες | bd73953 |
| Τύποι τοίχων: γυψοσανίδα, πετροκτιστά με/χωρίς μόνωση | `architecture/wall_types.py` (στρώσεις, ενδεικτικό U κατά ISO 6946) | d8fc168 |
| Υδραυλικά: σημεία, και οι σωλήνες χαράζονται μόνοι τους, ζωντανά, σε layer «Μηχανολογικά» | `mep/plumbing.py` | 9bcce22 |
| Ηλεκτρολογικά: πίνακας, πρίζες, φώτα, διακόπτες· σύνδεση βάσει φορτίων· «πλήρης αντίληψη όπως εγώ» | `mep/electrical.py` (κυκλώματα κατά ΕΛΟΤ HD 384) | 608fd9e |
| Ξύλινη στέγη με δοκούς και κεραμίδια βάσει φορτίων· «μην ξεχάσεις τα στρώματα μόνωσης» | `structure/timber_roof.py` (EN 1991-1-3 χιόνι, C24, L/300) και στρώσεις | 06a6fe3, e7b924c |
| **Διόρθωση:** «Δεν συνηθίζεται στην Ελλάδα… οι διελεύσεις ανεβαίνουν στα 2,3–2,4 m πάνω από τα σενάζ»· κουτιά διέλευσης σε μεγάλες αποστάσεις· κουτιά σύνδεσης πάνω από διακόπτες/πρίζες, ορατά στο σχέδιο | Οδεύσεις στον τοίχο στα 2,35 m· κουτιά διακλάδωσης, δαπέδου και διέλευσης | 2df35b6 |
| «Επιλογή από δάπεδο ή από τοίχο… από δάπεδο τα κουτιά 15 cm πάνω από το έδαφος… να επιλέγει την καλύτερη διαδρομή, π.χ. νησίδα κουζίνας» | Πεδίο `routing` ανά σημείο: auto/wall/floor. Στο auto, ≤60 cm από τοίχο πάει από τοίχο, αλλιώς από δάπεδο | 2df35b6 |
| Υδραυλικά ανάλογα με το υλικό: χαλκός, μονοσωλήνιο, πολυστρωματική· «να φαίνονται και οι πίνακες υδροληψίας με τη δομή τους» | Πεδίο `pipe_system` στην παροχή· πίνακες υδροληψίας σε κάτοψη και 3D | dffe8c5 |
| «Τώρα που είπα νησίδα, ξέχασες τους εξαερισμούς» | `mep/ventilation.py`: απορροφητήρας τοίχου/νησίδας Ø125, μπάνιο/WC Ø100, ευθεία στον πλησιέστερο εξωτερικό τοίχο ή από τη στέγη, `outlet` auto/wall/roof (V1) | (αυτό το commit) |
| «Μετά στήσε το AI Assistant, κατά προτίμηση μέσα στο ίδιο το πρόγραμμα και όχι εξωτερικά» | ⏳ **επόμενο** (AI1) | — |
| «Προτεραιότητα να καταστεί η συνομιλία μας ορατή από το επόμενο chat» | Αυτό το αρχείο και το `CLAUDE.md` | (αυτό το commit) |

## 3. Ουρά: τι ακολουθεί, με σειρά

1. ~~V1 Εξαερισμοί~~ ✅ (βλ. WORKLOG V1).
2. **AI1 AI Assistant μέσα στην εφαρμογή.**
   - Πάνελ στο dock «AI».
   - Ροή: πρόθεση χρήστη → προτεινόμενες ενέργειες → **οι ίδιες κοινές εντολές** (AddEntity/UpdateEntity…) → Document.
   - Επιπλέον:
     - εφαρμογή μόνο με έγκριση του χρήστη· undo με ένα βήμα·
     - provider ρυθμιζόμενος· το πρόγραμμα δουλεύει πλήρως και χωρίς AI·
     - tests που συγκρίνουν την authoritative κατάσταση χειροκίνητης και AI εκτέλεσης (AGENTS.md).
   - Υπάρχουσα βάση:
     - `architecture/design_agent.py` (`AIAssistantProposal`, `apply_ai_proposal`);
     - `orchestration/` (LangGraph, providers);
     - dock «AI» στο `ui/main_window.py` (~γρ. 1193).
3. Από το WORKLOG:
   - L8 κουφώματα· L9 κάγκελα· L10 υφές/χρώματα·
   - L7 υπόλοιπα (γωνιακά ντουλάπια, ανοιχτά ράφια, εσωτερικά ντουλάπας)·
   - R2–R7 ρεαλισμός·
   - εκκρεμότητες από τις προβολές (16, 17).

## 4. Χάρτης κώδικα (ό,τι προστέθηκε σε αυτή τη συνομιλία)

- **`archforge/library/`:**
  - Home Designer: `hd_calib.py`·
  - asset store: `assets.py`·
  - αντικείμενα και σύμβολα: `objects.py`, `plan_symbol.py`·
  - glTF: `gltf.py`·
  - γεωμετρία: `builder.py`·
  - κατάλογος: `catalog.py`, 39 δικά μας αντικείμενα με `seed_core_library`.
- **`archforge/kitchen/cabinets.py`:** παραμετρικά ντουλάπια και ντουλάπες.
- **`archforge/architecture/wall_types.py`:** συνθέσεις τοίχων.
- **`archforge/mep/plumbing.py`:**
  - Router: `_Grid` (A* σε κάναβο 20 cm, modes floor/wall) και `_grow` (δέντρο).
  - `PIPE_SYSTEMS` και πίνακες υδροληψίας.
- **`archforge/mep/electrical.py`:**
  - Κυκλώματα: `CIRCUIT_RULES`, `design_circuits`.
  - Οδεύσεις: `route_cables` (τοίχος 2,35 m / δάπεδο, κουτιά), `routing_of`, `_pull_boxes`.
- **`archforge/mep/ventilation.py`:** `exterior_walls`, `route_ventilation` (αεραγωγοί, στόμια, αναφορά), `outlet_of`.
- **`archforge/structure/timber_roof.py`:** στέγη, φορτία, προδιαστασιολόγηση, στρώσεις.
- **UI:**
  - `ui/object_modifier.py`, `ui/project_outline.py`;
  - `ui/approved_mockup_shell.py`: μενού Βιβλιοθήκη, Κουζίνα, Μηχανολογικά, Κατασκευή·
  - `ui/main_window.py`: Inspector με combos για wall_type, roof, routing, pipe_system.
- **Παράγωγα σχέδια:**
  - κάτοψη: `core/plan_scene.py` (`build_plan_frame`) με στυλ στο `ui/plan_view.py` (`_draw_primitive`)·
  - 3D: `rendering/scene.py` (`build_pbr_scene_payload`, layers `mep`, `elec` και `vent`).
- **Σχήματα Document:** `core/model.py` `SCHEMAS`, για library_object, cabinet, plumbing_point (`pipe_system`), ventilation_point (`outlet`, `airflow`), electrical_point (`routing`, `power_w`), pitched_roof, wall_type.

## 5. Χρήσιμα για τον επόμενο agent

- Νέο cloud container: `pip install -r requirements.txt pytest` και `apt-get install libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3 libnss3` (αλλιώς τα tests UI αποτυγχάνουν με libEGL).
- Πλήρης σουίτα στο cloud:
  `QT_QPA_PLATFORM=offscreen QTWEBENGINE_DISABLE_SANDBOX=1 QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu --single-process" python -m pytest -q -p no:cacheprovider`
- Το δίκτυο του cloud μπλοκάρει Poly Haven, ambientCG και Kenney. Λειτουργεί μόνο το `raw.githubusercontent.com` (Khronos glTF samples).
- Οπτική επαλήθευση: render με matplotlib ή `asset_preview.py` του skill, πριν δηλωθεί κάτι «έτοιμο».
- Τα αρχεία `.calib`, `.calibz` και `.tbdata` του Home Designer είναι αδειοδοτημένα: μόνο για τοπική μελέτη, **ποτέ** στο repo.
- Το πλήρες transcript της συνεδρίας δεν είναι στο repo. Όσα χρειάζονται για συνέχεια είναι σε αυτό το αρχείο και στο WORKLOG.
