# Αναφορά διασταύρωσης: κάθε bot συνεχίζει το έργο άλλου bot

Bot: **100** · βήματα: **0** · στοιχεία που έφτιαξαν: **0** · χωρίς κανένα εύρημα: **0** · ομάδες ευρημάτων: **1**

Κτίρια: Γ σχήμα 11 · διώροφη 20 · κατάστημα + κατοικία 18 · με υπόγειο 18 · μονοκατοικία 17 · πολυκατοικία 16

Το bot ανοίγει από το μενού το αποθηκευμένο έργο άλλου bot, ελέγχει ότι άνοιξε ίδιο με το αρχείο (ίδια στοιχεία, έγκυρα, χωρίς ορφανά, χωρίς «μη αποθηκευμένο»), ότι άνοιγμα → αποθήκευση δεν αλλάζει τίποτα κρυφά, και συνεχίζει: διορθώσεις, υλικά, έπιπλα, Η/Μ, εξωτερικοί χώροι, έξοδοι, αναιρέσεις. Εργαλείο: `scripts/user_drive/bots.py`.

| # | Είδος | Bot | Εύρημα | Πού (βήμα) | Αιτία | Κώδικας | Πρώτο bot |
|---|---|---|---|---|---|---|---|
| 1 | διακοπή bot | 100 | ProjectFileError: Δεν βρέθηκε το αρχείο «apo_allon.archforge». | εκκίνηση | προς διερεύνηση | e01b991 | 8 |

## Λεπτομέρειες (εξαιρέσεις / καταρρεύσεις)

### 1. ProjectFileError: Δεν βρέθηκε το αρχείο «apo_allon.archforge».

```
Traceback (most recent call last):
  File "/home/user/ArchForge-/scripts/user_drive/bots.py", line 1242, in run_cross
    written = _file_snapshot(src)
  File "/home/user/ArchForge-/scripts/user_drive/bots.py", line 1226, in _file_snapshot
    doc = load_project(path).doc
          ~~~~~~~~~~~~^^^^^^
  File "/home/user/ArchForge-/archforge/project/persistence.py", line 294, in load_project
    return load_project_data(read_project_json(path), path)
                             ~~~~~~~~~~~~~~~~~^^^^^^
  File "/home/user/ArchForge-/archforge/project/persistence.py", line 257, in read_project_json
    raise ProjectFileError(f'Δεν βρέθηκε το αρχείο «{os.path.basename(path)}».') from None
archforge.project.persistence.ProjectFileError: Δεν βρέθηκε το αρχείο «apo_allon.archforge».

```

