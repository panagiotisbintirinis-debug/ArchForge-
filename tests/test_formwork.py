import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from archforge.core.commands import AddEntities, CommandStack, RenameEntities
from archforge.core.model import Document, Entity
from archforge.structure.analysis.building import read_members
from archforge.structure.layout import propose_frame
from archforge.structure.marks import renumber


def _house(doc, z=0.0, level='Ground'):
    for a, b in (((0, 0), (10, 0)), ((10, 0), (10, 8)), ((10, 8), (0, 8)), ((0, 8), (0, 0)), ((5, 0), (5, 8))):
        doc.add(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'thickness': .25, 'height': 3, 'z': z, 'level': level}))


def _framed():
    doc = Document(); _house(doc)
    entities, _report = propose_frame(doc)
    CommandStack(doc).execute(AddEntities(entities))
    return doc


def test_every_member_has_its_own_mark_shared_with_the_analysis():
    doc = _framed()
    cols = [e for e in doc.entities.values() if e.kind == 'structural_column']
    beams = [e for e in doc.entities.values() if e.kind == 'structural_beam']
    assert cols and beams
    assert sorted(int(c.name[1:]) for c in cols) == list(range(1, len(cols) + 1))
    assert all(c.name.startswith('Κ') for c in cols) and all(b.name.startswith('Δ') for b in beams)
    # Κ1 is top-left in plan (reading order).
    k1 = next(c for c in cols if c.name == 'Κ1')
    assert float(k1.params['y']) == max(float(c.params['y']) for c in cols)
    members, _ = read_members(doc)
    assert {m.name for m in members.values()} == {e.name for e in cols + beams}


def test_a_column_drawn_by_hand_gets_the_next_mark_and_user_names_stay():
    doc = _framed()
    n = sum(e.kind == 'structural_column' for e in doc.entities.values())
    extra = Entity('structural_column', {'x': 2.5, 'y': 4, 'z': 0, 'width': .3, 'depth': .3, 'height': 3, 'rotation': 0,
                                         'role': 'structural', 'construction': 'reinforced_concrete', 'section': 'rectangular',
                                         'base_level': 'Ground', 'top_level': 'Unassigned'}, name='Column')
    doc.add(extra)
    assert extra.name == f'Κ{n + 1}'
    stack = CommandStack(doc)
    stack.execute(RenameEntities({extra.id: 'Κ-γωνία'}))
    assert doc.get(extra.id).name == 'Κ-γωνία'
    assert extra.id not in renumber(doc)                  # the user's name is kept
    members, _ = read_members(doc)
    assert members[extra.id].name == 'Κ-γωνία'
    stack.undo()
    assert doc.get(extra.id).name == f'Κ{n + 1}'


def test_renumber_closes_gaps_in_reading_order():
    doc = _framed()
    first = next(e for e in doc.entities.values() if e.name == 'Κ1')
    del doc.entities[first.id]
    names = renumber(doc)
    CommandStack(doc).execute(RenameEntities(names))
    cols = [e for e in doc.entities.values() if e.kind == 'structural_column']
    assert sorted(int(c.name[1:]) for c in cols) == list(range(1, len(cols) + 1))


def test_formwork_sheet_per_storey(tmp_path):
    from PySide6.QtWidgets import QApplication
    from archforge.output.formwork import export_formwork_pdf, storey_frames
    app = QApplication.instance() or QApplication([])
    doc = _framed()
    frames = storey_frames(doc)
    assert len(frames) == 1
    f = frames[0]
    assert f['columns'] and f['beams']
    assert all(b.name.startswith('Δ') for b in f['beams'])
    r = export_formwork_pdf(doc, tmp_path / 'xt.pdf')
    assert r['pages'] == 2 and (tmp_path / 'xt.pdf').stat().st_size > 2000   # θεμελίωση + οροφή


def test_formwork_needs_a_frame(tmp_path):
    from PySide6.QtWidgets import QApplication
    from archforge.output.formwork import export_formwork_pdf
    app = QApplication.instance() or QApplication([])
    doc = Document(); _house(doc)
    try:
        export_formwork_pdf(doc, tmp_path / 'x.pdf')
        assert False
    except ValueError as exc:
        assert 'Πρόταση φέροντος' in str(exc)


def test_name_is_edited_in_properties_and_menu_has_formwork(tmp_path):
    from PySide6.QtWidgets import QApplication, QLineEdit
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    _house(window.doc)
    window._no_modal_dialogs = True
    entities, _ = propose_frame(window.doc)
    window.stack.execute(AddEntities(entities))
    k1 = next(e for e in window.doc.entities.values() if e.name == 'Κ1')
    window.doc.select([k1.id]); window.refresh_inspector()
    edit = next(window.form.itemAt(i, window.form.ItemRole.FieldRole).widget() for i in range(window.form.rowCount())
                if isinstance(window.form.itemAt(i, window.form.ItemRole.FieldRole).widget(), QLineEdit))
    assert edit.text() == 'Κ1'
    window._rename_entity(k1.id, 'Κ2')                     # taken: refused
    assert window.doc.get(k1.id).name == 'Κ1'
    window._rename_entity(k1.id, 'ΚΓ1')
    assert window.doc.get(k1.id).name == 'ΚΓ1'
    labels = [a.text() for a in window._structure_menu.actions()]
    assert 'Φύλλο ξυλοτύπου (PDF)…' in labels and 'Αρίθμηση κολονών / δοκών (Κ1, Δ1 …)' in labels
    r = window._export_formwork(str(tmp_path / 'x'))
    assert r['pages'] == 2 and (tmp_path / 'x.pdf').exists()
    window._mark_clean(); window.close(); app.processEvents()


def test_tree_has_slabs_with_reinforcement_and_the_foundation():
    from archforge.structure.analysis import analyze_cached
    from archforge.ui.project_outline import project_outline
    doc = _framed()
    analyze_cached(doc)

    def walk(node):
        yield node
        for c in node["children"]:
            yield from walk(c)
    labels = [n["label"] for n in walk(project_outline(doc))]
    slab = next(l for l in labels if l.startswith("Πλάκες οροφής"))
    assert "m³" in slab
    panel = next(l for l in labels if l.startswith("Πλ1 "))
    assert "κάτω Ø" in panel and "άνω" in panel
    assert any(l.startswith("Πέδιλα (") for l in labels)
    assert any(l.startswith("Π1 (Κ") and "σχάρα Ø" in l for l in labels)
    assert any(l.startswith("Συνδετήριες δοκοί (") for l in labels)
    assert any(l.startswith("ΣΔ1 ") and "Ø" in l for l in labels)


def _with_stair():
    from archforge.architecture.stairs import solve_stair_candidates
    doc = _framed()
    _house(doc, z=3.0, level='Floor 2')
    c = solve_stair_candidates(0.0, 3.0, (2.5, 0.7), (2.5, 7.0), width=1.0, upper_floor_z=3.0, upper_slab_thickness=.18)[0]
    doc.add(Entity('stair', c.to_params(), name='Σκάλα'))
    return doc


def test_stair_well_gets_reinforcement_bands_and_a_beam_through_it_is_flagged():
    from archforge.structure.slabs import design_slabs, slabs_html
    r = design_slabs(_with_stair())
    ops = [o for p in r['panels'] for o in p['openings']]
    assert len(ops) == 1
    o = ops[0]
    assert o['slab'] == 'Πλ1'
    assert {b['side'] for b in o['bands']} == {'x0', 'x1', 'y0', 'y1'}
    for b in o['bands']:
        assert b['n'] >= 2 and b['d'] >= 12 and b['stirrups'] == 'Ø8/20' and b['length_m'] > max(o['size']) - 1e-6 or b['along'] == 'x'
    assert o['corners'] == 4
    assert 'Δ7' in o['warning']                              # the beam on y=4 runs through the well
    host = next(p for p in r['panels'] if p['mark'] == 'Πλ1')
    assert not host['ok']
    assert 'ζώνες ενίσχυσης' in slabs_html(r)


def test_well_edges_on_walls_need_no_band():
    from archforge.structure.slab_openings import openings_in_slabs, stair_openings, _supported_edges
    doc = _with_stair()
    (_stair, box, z), = stair_openings(doc)
    doc.add(Entity('wall', {'x1': box[0], 'y1': -1, 'x2': box[0], 'y2': 9, 'thickness': .2, 'height': 3, 'z': 0, 'level': 'Ground'}))
    assert 'x0' in _supported_edges(doc, box, z)


def test_footings_numbered_like_the_columns_and_foundation_sheet(tmp_path):
    from PySide6.QtWidgets import QApplication
    from archforge.output.formwork import export_formwork_pdf, foundation_of
    app = QApplication.instance() or QApplication([])
    doc = _with_stair()
    fd = foundation_of(doc)
    p1 = next(f for f in fd['footings'] if f['name'] == 'Π1')
    assert p1['column'] == 'Κ1'
    r = export_formwork_pdf(doc, tmp_path / 'x.pdf')
    assert r['pages'] == 2                                   # θεμελίωση + οροφή ισογείου


def test_strip_footings_where_pads_crowd_or_on_request(tmp_path):
    from PySide6.QtWidgets import QApplication
    from archforge.structure.analysis import analyze
    from archforge.structure.analysis.settings import get_settings
    from archforge.structure.foundation import design_foundation, foundation_html
    from archforge.output.formwork import foundation_page, Sheet
    doc = _framed()
    r = analyze(doc)
    s = get_settings(doc)
    auto = design_foundation(r['footings'], s)
    assert not auto['strips'] and len(auto['footings']) == 9          # 5 m apart: pads and ties
    s['foundation_type'] = 'strips'
    fd = design_foundation(r['footings'], s)
    assert len(fd['strips']) == 6 and not fd['footings'] and not fd['ties']
    sp = fd['strips'][0]
    assert sp['B_m'] >= 0.80 and sp['H_m'] >= 0.80 and sp['bw_m'] >= 0.40 and sp['hf_m'] >= 0.30
    assert sp['bars_top'].endswith(('Ø16', 'Ø18', 'Ø20', 'Ø22', 'Ø25')) and sp['stirrups'].startswith('Ø')
    assert sp['sigma_kPa'] <= float(s['soil_pressure']) + 1e-6
    assert 'Πεδιλοδοκοί' in foundation_html(fd)
    # Crowded pads (a weak soil makes them big): auto merges them into strips, ties only where none.
    s.update(foundation_type='auto')
    big = [dict(f, B_m=4.7) if f['x'] > 6 else dict(f) for f in r['footings']]     # east pads 4.7 m: < 0.50 m apart
    crowded = design_foundation(big, s)
    assert crowded['strips']
    covered = {frozenset(p) for sp in crowded['strips'] for p in zip(sp['members'], sp['members'][1:])}
    assert all(frozenset(t['pair']) not in covered for t in crowded['ties'])
    assert crowded['footings'] and crowded['ties']                       # the rest stay pads with ties


def test_strips_on_the_sheet_tree_and_3d(tmp_path):
    from PySide6.QtWidgets import QApplication
    from archforge.core.commands import AddEntity
    from archforge.output.formwork import export_formwork_pdf
    from archforge.structure.analysis import analyze_cached
    from archforge.ui.project_outline import project_outline
    app = QApplication.instance() or QApplication([])
    doc = _framed()
    doc.add(Entity('structural_design', {'foundation_type': 'strips'}))
    fd = analyze_cached(doc)['foundation']
    assert fd['strips']

    def walk(n):
        yield n['label']
        for c in n['children']:
            yield from walk(c)
    labels = list(walk(project_outline(doc)))
    assert any(l.startswith('Πεδιλοδοκοί (6)') for l in labels)
    assert any(l.startswith('ΠΔ1 ') and 'κορμός' in l and 'πέλμα' in l for l in labels)
    r = export_formwork_pdf(doc, tmp_path / 'p.pdf')
    assert r['pages'] == 2


def test_roof_form_from_menu_leaves_terrace_rooms_alone():
    from archforge.architecture.roof_choice import form_roofs, room_roof_command
    from archforge.assistant.understanding import read_drawing
    from archforge.core.commands import CommandStack
    doc = Document()
    # Two rooms side by side: west 6×8, east 4×4 (the east one becomes a terrace).
    for a, b in (((0, 0), (6, 0)), ((6, 0), (10, 0)), ((10, 0), (10, 4)), ((10, 4), (6, 4)), ((6, 4), (6, 8)),
                 ((6, 8), (0, 8)), ((0, 8), (0, 0)), ((6, 0), (6, 4))):
        doc.add(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'thickness': .25, 'height': 3, 'z': 0, 'level': 'Ground'}))
    rooms = read_drawing(doc)['storeys'][0]['rooms']
    east = next(r for r in rooms if min(q[0] for q in r['polygon']) > 5)
    cmd, _msg = room_roof_command(doc, east, 'terrace', z=0.0)
    CommandStack(doc).execute(cmd)
    roofs = form_roofs(doc, 'hip', 0.0)
    assert len(roofs) == 1 and roofs[0]['roof_form'] == 'hip'
    assert roofs[0]['x1'] < 6.5                                   # stops at the west room, terrace left out
    # No terrace: the whole storey as before.
    doc2 = Document()
    for e in doc.entities.values():
        if e.kind == 'wall':
            doc2.add(Entity('wall', dict(e.params)))
    assert form_roofs(doc2, 'hip', 0.0)[0]['x1'] > 9.9


def test_menu_roof_on_a_smaller_l_shaped_upper_floor():
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    from archforge.architecture.roof_choice import form_roofs
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    doc = w.doc
    doc.levels['Floor 2'] = 3.0

    def wall(a, b, z):
        doc.add(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'thickness': .25, 'height': 3, 'z': z,
                                'level': 'Ground' if z == 0 else 'Floor 2'}))
    # Ground 10×8 in two rooms; the upper floor an L over it (west 5×8 + north-east 5×4), the south-east 5×4 left open.
    for a, b in (((0, 0), (10, 0)), ((10, 0), (10, 8)), ((10, 8), (0, 8)), ((0, 8), (0, 0)), ((5, 0), (5, 8))):
        wall(a, b, 0.0)
    for a, b in (((0, 0), (5, 0)), ((5, 0), (5, 4)), ((5, 4), (10, 4)), ((10, 4), (10, 8)), ((10, 8), (0, 8)), ((0, 8), (0, 0)),
                 ((5, 4), (5, 8))):
        wall(a, b, 3.0)
    roofs = form_roofs(doc, 'hip', 3.0)
    assert len(roofs) == 2 and all(r['roof_form'] == 'hip' for r in roofs)          # per room, nothing over the open corner
    assert not any(r['x0'] > 4.5 and r['y1'] < 4.5 for r in roofs)
    w._create_pitched_roof('hip')
    assert sum(e.kind == 'pitched_roof' for e in doc.entities.values()) == 2
    assert any(e.kind == 'room_roof' for e in doc.entities.values())               # the open part below: terrace
    w._undo()
    assert not any(e.kind in ('pitched_roof', 'room_roof') for e in doc.entities.values())
    w._mark_clean(); w.close(); app.processEvents()
