"""Export unpriced surface/material records; never approve a scenario or a design.

Owner 18 Oct 2026: review all projects, retain joint warnings, omit prices.
Uses the same takeoff/material lists and native plan widget as the application.
"""
from __future__ import annotations
import argparse, hashlib, json, math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/residential_scenarios'
OUT = ROOT / 'docs/scenarios/residential_review'

def entity_map(data):
    return {e['id']: e for e in json.loads(json.dumps(data))['entities']}

def table(headers, rows):
    def cell(x):
        return str(x).replace('|', '/').replace('\n', ' ')
    return ['| ' + ' | '.join(map(cell, headers)) + ' |',
            '| ' + ' | '.join('---' for _ in headers) + ' |'] + [
            '| ' + ' | '.join(map(cell, row)) + ' |' for row in rows]

def export(spec, output=OUT):
    from archforge.project.persistence import load_project
    from archforge.structure.analysis import analyze_cached
    from archforge.quantities.materials import all_lists
    from archforge.quantities.quote import row_meta
    from archforge.quantities.takeoff import take_off
    path = (ROOT/'docs/scenarios/foundation_review/S01_strip_comparison.archforge'
            if spec['id'] == 'S01' else FIXTURES/spec['file'])
    loaded = load_project(path)
    if not loaded.ok:
        raise ValueError(loaded.message())
    doc = loaded.doc
    original = entity_map(doc.to_dict())
    # Reopen the persisted file independently. Loading may reorder hosts/children.
    again = load_project(path)
    assert again.ok and entity_map(again.doc.to_dict()) == original
    takeoff = take_off(doc)
    result = analyze_cached(doc)
    if result.get('error'):
        raise ValueError(result['error'])
    sheets = all_lists(doc)
    assert any(s[0] == 'Φέρων' for s in sheets), 'Fresh structural takeoff missing'
    count = 0
    for _name, _title, rows, _notes in sheets:
        for row in rows:
            q = row[2]
            assert q is None or (math.isfinite(float(q)) and float(q) >= 0), row
            count += 1
    for key, total in takeoff['totals'].items():
        assert abs(total - round(sum(r[key] for r in takeoff['rooms']), 2)) < .011
    kinds = Counter(e.kind for e in doc.entities.values())
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    lines = [f"# {spec['id']} — {spec['name']}", '', '**Κατάσταση: ΓΙΑ ΕΛΕΓΧΟ — όχι πλήρης έγκριση.**', '',
             'Απόφαση ιδιοκτήτη 18/10/2026: επιφάνειες και υλικά ανά εργασία χωρίς τιμές. Οι έξι επισημάνσεις κόμβων του S01 παραμένουν ανοιχτές, χωρίς να σταματούν την καταγραφή των υπολοίπων. Ο ιδιοκτήτης θα ελέγξει κάθε σχέδιο χωριστά.', '',
             f'Αρχείο: `{path.relative_to(ROOT)}`.', f'SHA-256: `{source_hash}`.', '',
             'Οι τιμές/εργατικά/ΦΠΑ παραλείπονται. Οι ποσότητες είναι έξοδος των υπαρχουσών μεθόδων του συγκεκριμένου δοκιμαστικού μοντέλου· δεν αποτελούν επαληθευμένη παραγγελία ή μελέτη. Δεν αθροίζονται επικαλυπτόμενες ενότητες. Όγκοι μελών δεν είναι καθαρή ένωση στερεών στις διασταυρώσεις.', '',
             '## Επιφάνειες ανά όροφο και χώρο', '']
    lines += table(['Όροφος','Χώρος','Δάπεδο m²','Τοίχοι m² μείον ανοίγματα','Οροφή m²','Ανοίγματα m²'],
                   [(r['storey'],r['name'],r['floor_m2'],r['walls_m2'],r['ceiling_m2'],r['openings_m2']) for r in takeoff['rooms']])
    lines += ['', 'Η οροφή της επιμέτρησης χρησιμοποιεί το καθαρό οριζόντιο εμβαδόν, όχι την κεκλιμένη επιφάνεια στέγης. Η κατανομή φινιρισμάτων και το ύψος πλακιδίων υγρών χώρων ακολουθούν τους υπάρχοντες κανόνες της μηχανής και παραμένουν προς έλεγχο.', '',
              '## Υλικά και ποσότητες ανά εργασία']
    for name, _title, rows, notes in sheets:
        lines += ['', '### ' + name, '']
        lines += table(['Υλικό / εργασία','Μονάδα','Ποσότητα','Κατάσταση'], [
            (desc, unit, 'Από μελέτη / άγνωστο' if qty is None else f'{float(qty):g}',
             meta.get('status','Υπάρχουσα επιμέτρηση — προς έλεγχο'))
            for desc, unit, qty, meta in (row_meta(row) for row in rows)])
        lines += ['', *[str(n) for n in notes if not any(w in str(n).lower() for w in ('τιμή','τιμές','price'))]]
    # Generic floor objects are not covered by the canonical slab material list.
    generic = [e for e in doc.entities.values() if e.kind == 'floor']
    if generic:
        lines += ['', '## Γενικά αντικείμενα δαπέδου — ξεχωριστή γεωμετρική καταγραφή', '',
                  'Δεν έχουν αποδοθεί αυθαίρετα σε σκυρόδεμα. Οι παρακάτω επιφάνειες/όγκοι είναι μικτά γεωμετρικά μεγέθη του αντικειμένου, πριν από τυχόν πραγματικές οπές ή επικαλύψεις. Δεν προστίθενται στα καθαρά εμβαδά χώρων.']
        rows=[]
        for e in generic:
            pts=e.params['points']; a=abs(sum(pts[i][0]*pts[(i+1)%len(pts)][1]-pts[(i+1)%len(pts)][0]*pts[i][1] for i in range(len(pts)))/2)
            t=float(e.params['thickness'])
            rows.append((e.name,e.params['z'],round(a,2),t,round(a*t,3),'Υλικό / οπές προς έλεγχο'))
        lines += ['', *table(['Αντικείμενο','z m','Μικτό m²','Πάχος m','Μικτός όγκος m³','Κατάσταση'], rows)]
    issues=[]
    if kinds['box']:
        issues.append(f"{kinds['box']} γενικά κουτιά με ονόματα επίπλων: δεν θεωρούνται πραγματικά έπιπλα ή είδη υγιεινής για παραγγελία.")
    if not kinds['stair'] and spec['storeys'] > 1:
        issues.append('Δεν υπάρχει πραγματική οντότητα σκάλας. Η πρόσβαση ορόφων και οι οπές πλακών παραμένουν ανοιχτές.')
    if not kinds['door'] or not kinds['window']:
        issues.append('Λείπουν πραγματικές πόρτες ή/και παράθυρα: τα καθαρά εμβαδά τοίχων και οι ποσότητες κουφωμάτων δεν είναι πλήρη.')
    if generic:
        issues.append('Τα γενικά δάπεδα χρειάζονται έλεγχο πραγματικών οπών, υλικού και μετατροπής στο κοινό σύστημα πλακών.')
    issues += ['Θέρμανση/HVAC και άγνωστοι οπλισμοί/ξυλότυποι παραμένουν προς μελέτη.',
               'Δεν έχει ολοκληρωθεί χειροκίνητος έλεγχος κάθε κάτοψης/3D και όλων των ενεργειών UI για αυτό το σχέδιο.']
    lines += ['', '## Ανοιχτά ευρήματα', '', *['- '+x for x in issues], '', '### Προειδοποιήσεις στατικού υπολογισμού — διατηρούνται', '',
              *['- '+str(w) for w in result.get('warnings',[])]]
    report=output/f"{spec['id']}_SURFACES_MATERIALS.md";report.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source_hash
    return {'id':spec['id'],'file':str(path.relative_to(ROOT)),'rooms':len(takeoff['rooms']),
            'floor_m2':takeoff['totals']['floor_m2'],'sections':len(sheets),'rows':count,'report':str(report.relative_to(ROOT)),
            'open':issues,'warning_count':len(result.get('warnings',[]))}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--scenario');args=parser.parse_args()
    specs=json.loads((FIXTURES/'manifest.json').read_text())
    results=[]
    for spec in specs:
        if args.scenario and spec['id']!=args.scenario:continue
        result=export(spec);results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
    lines=['# Σχέδια για έλεγχο — επιφάνειες και υλικά', '',
           '18/10/2026: χωρίς προσφορά/τιμές. Τα σχέδια παραδίδονται για διαδοχικό ανθρώπινο έλεγχο, όχι ως όλα εγκεκριμένα. Οι προειδοποιήσεις παραμένουν ορατές.', '']
    lines += table(['Σχέδιο','Χώροι','Δάπεδα χώρων m²','Ενότητες εργασιών','Γραμμές υλικών','Προειδοποιήσεις'],
                   [(r['id'],r['rooms'],r['floor_m2'],r['sections'],r['rows'],r['warning_count']) for r in results])
    lines += ['', *[f"- {r['id']}: [{Path(r['file']).name}]({Path('../../..')/r['file']}) · [{Path(r['report']).name}]({Path(r['report']).name})" for r in results]]
    lines += ['', '## Κάτοψεις για αρχική επισκόπηση', '', '![Πραγματικές ισόγειες κάτοψεις](plans-overview.png)', '', 'Πλήρεις λήψεις ανά επίπεδο στον φάκελο `plans/`. Δεν αντικαθιστούν τον έλεγχο του αρχείου από τον ιδιοκτήτη.']
    (OUT/'INDEX.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
if __name__=='__main__':main()
