# Κοινές οδηγίες για τους κριτές του ArchForge v5 (04/11)

Είσαι **χρήστης** με συγκεκριμένο επάγγελμα (ο ρόλος σου δίνεται χωριστά). Κρίνεις το ArchForge και την πρόταση v5
όπως θα τα έκρινε αυτός ο άνθρωπος στη δουλειά του: **ταχύτητα στη χρήση** και **εύρος πληροφορίας** που παίρνει για
τη σχεδίαση. Ο ιδιοκτήτης θέλει εφαρμόσιμα ευρήματα, όχι γενικότητες.

## Υλικό
- Repo (μόνο ανάγνωση): /home/user/ArchForge- (branch claude/busy-goodall-boaa9c = develop + PR #186).
- Η πρόταση v5 κομμάτι κομμάτι (HTML, διάβασέ την ολόκληρη): /tmp/claude-0/-home-user-ArchForge-/9191178c-86ce-57d9-8a87-bf5553d0e659/scratchpad/kritiki_v5.html
  (δημοσιευμένη: https://claude.ai/artifact/KirwiNtQqpE4zGCFfji2Be). 11 κομμάτια k0–k10: Συνολική εικόνα · Οθόνη ·
  Ταχύτητα σχεδίασης · Επιλογή & πληροφορία · Τοίχοι/τύποι · Κατασκευή · Εγκαταστάσεις · Θερμική (λ,U,θερμογέφυρες) ·
  Κάμερα/3D · Σχέδια/λίστες · Ρυθμίσεις.
- Χάρτης εντολών: docs/ui/TOOL_MAP.md · έλεγχος εντολών: docs/MENU_SMOKE_04_11.md · συμπεριφορά ArchiCAD:
  docs/specs/archicad_menu_behavior.md · docs/specs/archicad_analysis.md · docs/specs/kateythynsi_epilysis.md.
- Πραγματικό έργο του ιδιοκτήτη: tests/data/owner_111_two_storey.archforge.

## Δούλεψε με το πρόγραμμα (υποχρεωτικό)
Τρέξε το ArchForge offscreen όπως άνθρωπος, με το υπάρχον εργαλείο `scripts/user_drive/user.py` (δες `house.py`,
`core_check.py` για παραδείγματα: μενού, κλικ στην κάτοψη, μετράει βήματα, `U.notes` = τριβές). Περιβάλλον:
`cd /home/user/ArchForge- && QTWEBENGINE_DISABLE_SANDBOX=1 QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu" QT_QPA_PLATFORM=offscreen PYTHONPATH=. python <script>`
(PySide6 και βιβλιοθήκες είναι εγκατεστημένα). Κάνε 2–4 πραγματικές εργασίες του ρόλου σου (π.χ. σχεδίασε τοίχους με
ακριβές μήκος, άλλαξε τύπο, βρες U, βγάλε επιμέτρηση, βάλε κάμερα) και **μέτρα βήματα/κλικ** και τι πληροφορία
παίρνεις σε κάθε σημείο. Γράψε τα scripts σου ΜΟΝΟ στον φάκελό σου: .../scratchpad/reviews/<ρόλος>/ (όχι μέσα στο repo,
ρύθμισε `sys.path` στο /home/user/ArchForge- και /home/user/ArchForge-/scripts/user_drive). Το `user.py` γράφει
στο scripts/user_drive/out — μη σε απασχολεί, αλλά **μην αλλάξεις κανένα αρχείο του repo, μην κάνεις commit/push,
μη δημοσιεύσεις artifact**. Αν ένα script κολλήσει >3 λεπτά, σταμάτα το και συνέχισε.

## Σύγκρινε με άλλα προγράμματα (υποχρεωτικό)
Αναλύσεις βίντεο στη VideoDB (ΜΟΝΟ ανάγνωση υπαρχουσών — δεν υπάρχουν credits: ΜΗΝ καλέσεις understand_video,
create_index, upload ή οτιδήποτε νέο). Διάβασε με `get_analyzer_output(video_id, understanding_id, analyzer_name)`
(analyzer "transcript" = ομιλία, "scene" ή "ui" = τι φαίνεται στην οθόνη). Τα αποτελέσματα είναι μεγάλα: σώζονται
σε αρχείο· διάβασε όσα αφορούν τον ρόλο σου.
| Βίντεο | video_id | understanding_id | analyzers |
|---|---|---|---|
| ArchiCAD Exterior & Interior Walls (8′) | m-z-01a16c9f-92b2-7e32-a659-d9ec75c912dd | und_52ff36062a394349 (transcript, scene) · und_79d52d82f4b74404 (ui) |
| ArchiCAD 25 timelapse κατοικίας (ArchiCAD ως 5′45″, μετά Twinmotion) | m-z-01a18ba5-d58b-7401-b926-ba4043ff561c | und_73ed779f3b964a62 (ui) |
| Revit How to Draw Walls (14′) | m-z-01a16c9f-9e6e-7e33-97ef-88540d5aaf27 | und_e6a17fc3c9db4a62 (transcript, scene) |
| Allplan 2020 Quickstart Ground floor (23′) | m-z-01a16ca4-ac64-7ca1-ba16-36cc0022b9e0 | und_261f3b72652d4155 (transcript, scene) |
| SketchUp 2D Floorplan Walls (7′) | m-z-01a16c9f-a41c-74b1-8eff-bb250d12a6df | und_564a4cc9a59045e4 (transcript, scene) |
| Chief Architect Creating a Floor Plan (23′) | m-z-01a16c7c-bb0c-74f0-9fd4-26e5f3bea8bf | und_c0301407c99748a4 (transcript, scene) |
| Chief Architect Drawing Walls (3′) | m-z-01a16c7c-b281-7e71-9f43-b40ea66def00 | und_99021eec3d7c4145 (transcript, scene) |
| Home Designer Place Walls & Rooms (2′) | m-z-01a16c7c-a7fc-73e3-99a6-0c39187fc98e | und_e3e653de7c8e4994 (transcript, scene) |
| Sweet Home 3D Walls (7′) | m-z-01a16ca7-1d32-7f32-9326-be3fd5e7884b | und_9affeaf82e5047b3 (transcript, scene) |
Μπορείς επίσης WebSearch / WebFetch για επίσημα εγχειρίδια (help.graphisoft.com, help.autodesk.com, κ.λπ.) ή
YouTube (αν δεν ανοίγει το βίντεο, ψάξε περιγραφή/μεταγραφή). Γράψε **από πού** είναι κάθε σύγκριση (βίντεο + χρόνος,
ή URL). Τίποτα από μνήμης χωρίς να το πεις.

## Παραδοτέο: ένα αρχείο .../scratchpad/reviews/<ρόλος>.md, στα ελληνικά, με αυτή τη μορφή
1. **Ποιος είμαι** (1 γραμμή) και **τι έκανα** (εργασίες στο πρόγραμμα, βίντεο/πηγές που είδα).
2. **Μετρήσεις από το πρόγραμμα**: εργασία → βήματα/κλικ σήμερα → τι πληροφορία έλειπε (με αρχείο/συνάρτηση αν βρήκες αιτία).
3. **Ψήφος ανά κομμάτι k1–k10**: ΝΑΙ / ΟΧΙ / ΑΛΛΙΩΣ + μία πρόταση γιατί. Απάντησε και στις ερωτήσεις «Θέλει απόφαση» όσων σε αφορούν.
4. **Τα 5 πιο σημαντικά για τον ρόλο μου** με σειρά, το καθένα: τι, γιατί (με πηγή σύγκρισης), πόσο κερδίζει σε ταχύτητα/πληροφορία.
5. **Τι λείπει από την πρόταση v5** που ένας άνθρωπος του ρόλου μου θα ζητούσε αμέσως.
6. **Διαφωνίες** με την πρόταση (πού κάνει λάθος ή υπερβάλλει).
Μέχρι ~900 λέξεις. Στο τέλος της απάντησής σου επέστρεψε σύνοψη 10 γραμμών + τη διαδρομή του αρχείου.

## ΑΠΟΦΑΣΕΙΣ ΙΔΙΟΚΤΗΤΗ (04/11, μετά την πρόταση) — λάβε τες υπόψη
- **k1 «Χάρτης έργου μόνιμα ανοιχτός»: ο ιδιοκτήτης ΔΕΝ συμφωνεί.** Μην το προτείνεις ως έχει· αν ο ρόλος σου χρειάζεται
  γρήγορη πλοήγηση σε ορόφους/τομές/λίστες, πρότεινε άλλο τρόπο (π.χ. ανοίγει όταν τον ζητάς, πλήκτρο, μενού).
- **k4: το σημερινό εργαλείο με +/− για είδη (υλικά) και πάχη στρώσεων είναι «τέλειο για αλλαγές» και ΔΕΝ πρέπει να χαθεί
  ποτέ** (`archforge/ui/wall_details_dialog.py`: «+ Στρώση εξωτερικά/εσωτερικά», «−», υλικό και πάχος ανά στρώση·
  `archforge/ui/wall_layers_panel.py`). Ό,τι προτείνεις για τύπους τοίχου πρέπει να το κρατά και να χτίζει πάνω του.
