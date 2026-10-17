# S01 — Aegean Courtyard Duplex

Status: **BLOCKED**. Next scenario is not authorised by a green unit test alone.

Software fixture; not a certified engineering design. All prices are synthetic test values or explicitly missing.

| Area | Check | Status | Evidence / remaining work |
|---|---|---|---|
| Architecture | Load without skipped entities | PASS | Φορτώθηκαν 103 στοιχεία. |
| Architecture | Storeys and enclosed rooms | PASS | 2 storeys; four enclosed rooms on each |
| Architecture | Door/window hosts | PASS | Openings have actual wall hosts |
| Architecture | Real library furniture | PASS | Four furniture instances plus six real bathroom assets; no furniture boxes |
| Architecture | Kitchen cabinets | PASS | Base cabinet and sink cabinet |
| Architecture | Bathroom and kitchen separated | PASS | Sanitary fixtures in separate bathroom rooms |
| Architecture | Balcony and railing | PASS | Canonical railing schema loaded |
| Architecture | Attic ceilings top floor only | PASS | Four ceilings; none on lower storeys |
| Architecture | Stair levels and wall conflicts | PASS | Stair links actual levels and crosses no wall |
| Architecture | Physical slab opening and retained headroom | PASS | Ray checks of actual evaluated mesh: open over top steps; retained over first steps |
| Architecture | Roof is present | PASS | gable |
| Structure | Analysis completes with members | PASS | Analysis completed |
| Structure | Frame member counts | PASS | Columns and beams present on every storey |
| Structure | Warnings explicitly inspected | FAIL | AssertionError: ['Κόμβος Κ11 / Y (z=5.70 m, κορυφή): ΣMRc/ΣMRb=1.11 < 1.30 — μη επαληθευμένο κριτήριο· η εφαρμογή του και τυχόν εξαιρέσεις θέλουν έλεγχο μηχανικού. Δεν αποτελεί επιβεβαιωμένη αστοχία ή εντολή αλλαγής διατομών.', 'Κόμβος Κ13 / X (z=5.70 m, κορυφή): ΣMRc/ΣMRb=1.12 < 1.30 — μη επαληθευμένο κριτήριο· η εφαρμογή του και τυχόν εξαιρέσεις θέλουν έλεγχο μηχανικού. Δεν αποτελεί επιβεβαιωμένη αστοχία ή εντολή αλλαγής διατομών.', 'Κόμβος Κ14 / X (z=5.70 m, κορυφή): ΣMRc/ΣMRb=0.95 < 1.30 — μη επαληθευμένο κριτήριο· η εφαρμογή του και τυχόν εξαιρέσεις θέλουν έλεγχο μηχανικού. Δεν αποτελεί επιβεβαιωμένη αστοχία ή εντολή αλλαγής διατομών.', 'Κόμβος Κ14 / Y (z=5.70 m, κορυφή): ΣMRc/ΣMRb=1.24 < 1.30 — μη επαληθευμένο κριτήριο· η εφαρμογή του και τυχόν εξαιρέσεις θέλουν έλεγχο μηχανικού. Δεν αποτελεί επιβεβαιωμένη αστοχία ή εντολή αλλαγής διατομών.', 'Κόμβος Κ15 / X (z=5.70 m, κορυφή): ΣMRc/ΣMRb=1.12 < 1.30 — μη επαληθευμένο κριτήριο· η εφαρμογή του και τυχόν εξαιρέσεις θέλουν έλεγχο μηχανικού. Δεν αποτελεί επιβεβαιωμένη αστοχία ή εντολή αλλαγής διατομών.', 'Κόμβος Κ17 / Y (z=5.70 m, κορυφή): ΣMRc/ΣMRb=1.11 < 1.30 — μη επαληθευμένο κριτήριο· η εφαρμογή του και τυχόν εξαιρέσεις θέλουν έλεγχο μηχανικού. Δεν αποτελεί επιβεβαιωμένη αστοχία ή εντολή αλλαγής διατομών.'] |
| Structure | Engineering validation | REVIEW | verified=False; ΜΗ ΕΠΑΛΗΘΕΥΜΕΝΟ — ΟΧΙ ΓΙΑ ΜΕΛΕΤΗ: ο υπολογισμός στατικών δεν έχει συγκριθεί με λυμένα παραδείγματα ή με μελέτη μηχανικού και οι τιμές κανονισμών του δεν έχουν διασταυρωθεί με το κείμενο. Ενδεικτική προμελέτη μόνο. Προμελέτη φέροντος οργανισμού: EN 1990/1991-1-1, EN 1992-1-1, EN 1993-1-1, EN 1998-1 με Ελληνικό Εθνικό Προσάρτημα (ζώνες 0,16/0,24/0,36 g), ισοδύναμη στατική μέθοδος, ΚΠΜ — χωρίς ικανοτικό σχεδιασμό, κόμβους, θεμελίωση σε βάθος, πυροπροστασία· δεν αντικαθιστά τη στατική μελέτη αδειοδοτημένου μηχανικού |
| Structure | Member, footing, slab and joint engineering results | REVIEW | Raw results retained in evidence JSON; require structural engineer review, including any member failures |
| Structure | Capacity-joint flags explicitly recorded | FAIL | 6 meets=False results; roof/top-storey flags: 6. Do not resize members or waive a rule without verified engineering inputs/provenance. This is a software-reported flag, not a confirmed code violation. |
| MEP | Cold/hot routing and all outlets served | PASS | {'cold_m': 37.65, 'hot_m': 16.1, 'unserved': [], 'system': 'multilayer', 'system_label': 'Πολυστρωματική (PEX-Al-PEX), διακλαδώσεις', 'provenance': 'Προμελέτη διάταξης: κανόνες χάραξης & τυπικές διατομές ανά πλήθος εκροών — όχι υδραυλικός υπολογισμός (EN 806-3), προς έλεγχο από μηχανολόγο'} |
| MEP | Interstorey water risers | PASS | Cold/hot both have vertical risers |
| MEP | Drainage and warnings | PASS | {'warnings': [], 'auto': ['Στήλη αποχέτευσης (αυτόματα) στον τοίχο κοντά στα WC: (6.00, 7.72)', 'Σιφώνι δαπέδου (αυτόματα) στο Λουτρό', 'Φρεάτιο (αυτόματα) 1 m έξω από τον πλησιέστερο εξωτερικό τοίχο: (5.76, 9.00)', 'Σιφώνι δαπέδου (αυτόματα) στο Λουτρό'], 'length_by_dn': {100: 6.8, 50: 9.2, 40: 2.6}, 'depth_m': {3.0: 0.18, 0.0: 0.24}, 'provenance': 'Προμελέτη αποχέτευσης: EN 12056-2 (σύστημα I, μονάδες εκροής, Qww = 0,5·√ΣDU), κλάδοι Φ40/50/100 (λεκάνη Φ100), κλίση 2 %, στήλη Φ100 έως 4 l/s αλλιώς Φ125 (μαζί τα όμβρια αν πέφτουν μέσα), γέμισμα δαπέδου έως 20 cm, πέραν τσιμεντοκονία, αερισμός, φρεάτιο — προς έλεγχο από μηχανολόγο'} |
| MEP | Electrical assignment and routes | PASS | {'unassigned': [], 'warnings': [], 'provenance': 'Προμελέτη κυκλωμάτων με κανόνες του προγράμματος ΜΗ ΕΠΑΛΗΘΕΥΜΕΝΟΥΣ (φωτισμός 10A/1,5mm² ≤10 σημεία, πρίζες 16A/2,5mm² ≤6, αποκλειστικές γραμμές) — είχαν γραφτεί κατά το αποσυρμένο ΕΛΟΤ HD 384· ισχύει το ΕΛΟΤ HD 60364. Δεν είναι τεχνική απαίτηση· προς έλεγχο από ηλεκτρολόγο μηχανικό'} |
| MEP | Sizing and regulatory validation | REVIEW | Preserve all existing provenance. Routing output is not regulatory verification. |
| MEP | Heating/HVAC network continuity | NOT_TESTED | Current heating module is inventory-only; no hydraulic network solver is implemented |
| Behavior | Select authoritative entity | PASS | Selection accepted |
| Behavior | Move / undo / redo | PASS | Move → undo → redo → undo restores original position |
| Behavior | Change plumbing system and undo | PASS | Copper and manifold reroute; undo restores original multilayer routing |
| Behavior | Plumbing edits preserve electrical entities | PASS | Electrical entities unchanged |
| Behavior | Delete / undo / redo | PASS | Delete/undo/redo/undo keeps the project intact |
| Behavior | Save and reopen | PASS | Save → independent reload: identical authoritative serialized state |
| Quote | Shared price book resolves synthetic test prices | PASS | Synthetic test prices only; never market data |
| Quote | Material and labour arithmetic | PASS | {'currency': 'EUR', 'material_cost': 60.75, 'labour_cost': 60.75, 'subtotal': 121.5, 'complete_priced_subtotal': 121.5, 'by_category': {'Σημεία': 14.0, 'Σωληνώσεις': 107.5}, 'by_trade': {'plumbing': 121.5}, 'unpriced_codes': [], 'missing_price_codes': [], 'partial_price_codes': [], 'complete': True} |
| Quote | Whole-project missing prices remain visible | PASS | 58 unpriced rows; 0 partly priced rows. No invented market prices. |
| Quote | Whole-project commercial completeness | REVIEW | Unknown prices and study-dependent quantities prevent an actual priced construction offer; synthetic test prices do not resolve this |
| Visual/UI | Plan: Ground | PASS | S01_01_plan.png — real Qt plan widget |
| Visual/UI | Plan: Level 1 | PASS | S01_01b_upper_plan.png |
| Visual/UI | PBR 3D | PASS | S01_02_3d.png — Actual WebGL viewport frame |
| Visual/UI | Structural | PASS | S01_03_structural.png — Actual WebGL viewport frame |
| Visual/UI | Plumbing plan | PASS | S01_04_plumbing.png — actual layer visibility controls |
| Visual/UI | Drainage plan | PASS | S01_05_drainage.png — actual layer visibility controls |
| Visual/UI | Electrical plan | PASS | S01_06_electrical.png — actual layer visibility controls |
| Visual/UI | UI select | PASS | Actual double click in the plan on the sofa |
| Visual/UI | UI level switch | PASS | Floor selector changed work plane; no entity was removed |
| Visual/UI | UI close/reopen | PASS | Saved project; closed real window; fresh MainWindow opened file via checked-open path |
| Visual/UI | Human visual inspection | PASS | Opened and visually inspected the actual ground/upper plans, exterior PBR, dollhouse interior, Structural, plumbing, drainage and electrical images. Railing, upper/lower stair symbols, slabs/physical opening, bathroom assets and routes are visible. Plumbing label overlap fixed; drainage labels collision-managed and external manhole fits in capture. Images document software fixtures and are not engineering approval. |
