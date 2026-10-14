"""Fewer columns with the same adequacy; columns follow the walls they land on."""
from archforge.core.commands import AddEntity, CommandStack, CreateRoomFloors
from archforge.core.model import Document, Entity

C = dict(z=0.0, height=3.0, rotation=0.0, role='structural', construction='reinforced_concrete',
         section='rectangular', base_level='Ground', top_level='Unassigned')
B = dict(z=2.5, width=.25, height=.5, role='structural', construction='reinforced_concrete',
         section='rectangular', level='Ground')


def _box(st, w, d, h=3.0, z=0.0):
    for s in [(0, 0, w, 0), (w, 0, w, d), (w, d, 0, d), (0, d, 0, 0)]:
        st.execute(AddEntity(Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': z,
                                             'height': h, 'thickness': 0.25})))


def _frame(xs=(0, 3.5, 7, 10.5)):
    doc = Document(); st = CommandStack(doc)
    _box(st, xs[-1], 5)
    st.execute(CreateRoomFloors([f.signature for f in doc.active_room_faces()]))
    for x in xs:
        for y in (0, 5):
            st.execute(AddEntity(Entity('structural_column', dict(C, x=x, y=y, width=.25, depth=.25))))
    for a, b in zip(xs, xs[1:]):
        for y in (0, 5):
            st.execute(AddEntity(Entity('structural_beam', dict(B, x1=a, y1=y, x2=b, y2=y))))
    for x in xs:
        st.execute(AddEntity(Entity('structural_beam', dict(B, x1=x, y1=0, x2=x, y2=5))))
    return doc, st


def _count(doc, kind='structural_column'):
    return sum(e.kind == kind for e in doc.entities.values())


def test_columns_in_a_straight_line_go_and_everything_still_passes_one_undo():
    from archforge.structure.reduce_columns import reduce_columns
    doc, st = _frame()
    out = reduce_columns(doc, st)
    assert _count(doc) < 8 and out['removed']
    assert all(m.get('ok', True) for m in out['result']['members'].values())
    # the joined beams span the old two bays; corners are kept
    assert {(e.params['x'], e.params['y']) for e in doc.entities.values() if e.kind == 'structural_column'} >= {
        (0, 0), (0, 5), (10.5, 0), (10.5, 5)}
    st.undo()
    assert _count(doc) == 8 and _count(doc, 'structural_beam') == 10


def test_a_removal_that_needs_a_beam_longer_than_the_limit_is_refused():
    from archforge.structure.reduce_columns import reduce_columns
    doc, st = _frame(xs=(0, 6, 12))
    out = reduce_columns(doc, st)
    assert _count(doc) == 6 and not out['removed']


def test_a_failing_column_in_a_wall_grows_along_the_wall_not_across():
    from archforge.structure.analysis import _resize_rc, wall_axis
    from archforge.structure.analysis.building import read_members
    doc = Document(); st = CommandStack(doc)
    _box(st, 6, 4)
    col = Entity('structural_column', dict(C, x=3.0, y=0.0, width=.25, depth=.25))
    st.execute(AddEntity(col))
    m = read_members(doc)[0][col.id]
    assert wall_axis(doc, m) == 'b'                       # wall along x, width along x
    size = _resize_rc(m, {}, lambda b, h: {'ok': b >= 0.60}, 'column', 'b')
    assert size == (0.6, 0.25)


def test_column_height_follows_the_wall_it_lands_on_not_a_fixed_2_70():
    from archforge.core.interaction import StructuralColumnPlaceTransaction
    from archforge.structure.column_wall import storey_member_top
    doc = Document(); st = CommandStack(doc)
    _box(st, 6, 4, h=3.2)
    doc.levels['Ημιόροφος'] = 1.40                          # split level above: not the column top
    assert abs(storey_member_top(doc, 3.0, 0.0, 0.0) - 3.2) < 1e-9
    tx = StructuralColumnPlaceTransaction(doc, st, 3.0, 0.05, z=0.0, height=1.4, follow_walls=True)
    assert abs(tx.preview['height'] - 3.2) < 1e-9
    empty = Document()
    assert abs(storey_member_top(empty, 0, 0, 0.0) - 2.70) < 1e-9
