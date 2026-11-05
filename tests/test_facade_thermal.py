"""Θερμική εικόνα όψης ανά υλικό (ιδιοκτήτης 05/11: «κολόνες, πλάκες, σενάζ έχουν άλλο χρωματισμό… μπλεντ… βάσει
υλικών και λ»)."""
import numpy as np
import pytest

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.mep import facade_thermal as F


def _wall(with_frame=True):
    doc = Document(); st = CommandStack(doc)
    w = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 6, 'y2': 0, 'z': 0, 'height': 3.0, 'thickness': 0.27,
                        'wall_type': 'brick_double_insulated'})
    st.execute(AddEntity(w))
    if with_frame:
        st.execute(AddEntity(Entity('structural_column', {'x': 3.0, 'y': 0.0, 'z': 0.0, 'width': 0.4, 'depth': 0.4,
                                                          'height': 3.0, 'rotation': 0.0, 'role': 'structural',
                                                          'construction': 'reinforced_concrete', 'base_level': 'Ground'})))
        st.execute(AddEntity(Entity('structural_beam', {'x1': 0, 'y1': 0, 'x2': 6, 'y2': 0, 'z': 2.5, 'width': 0.25,
                                                        'height': 0.5, 'role': 'structural',
                                                        'construction': 'reinforced_concrete', 'level': 'Ground',
                                                        'section': 'rectangular'})))
    return doc, st, w


def test_a_plain_wall_is_exactly_the_one_dimensional_answer():
    from archforge.architecture.wall_types import indicative_u
    doc, _st, w = _wall(with_frame=False)
    r = F.facade(doc, w.id)
    u = indicative_u('brick_double_insulated', doc)
    expect = r['theta_e'] + u * 0.04 * (r['theta_i'] - r['theta_e'])
    assert np.allclose(r['theta'], expect, atol=1e-4) and r['one_d'] == pytest.approx(expect)
    assert r['watts'] == pytest.approx(u * 6 * 3.0 * (r['theta_i'] - r['theta_e']), rel=0.02)


def test_the_concrete_frame_shows_warmer_with_a_soft_edge_and_etics_hides_it():
    doc, _st, w = _wall()
    r = F.facade(doc, w.id)
    th, kind = r['theta'], r['kind']
    assert r['u']['column'] > 5 * r['u']['masonry']                  # the core insulation stops at the frame
    assert th[kind == 1].mean() > th[kind == 0].mean() + 1.0
    row = th[th.shape[0] // 2]                                          # across the column at mid-height
    c = int(3.0 / F.H)
    edge = row[c - 8:c - 3]                                             # just outside the column: a gradient
    assert np.all(np.diff(edge) > 0)                                    # blended, not a step
    etics = [F.layer(doc, 'cement_plaster', 0.01, 'finish'), F.layer(doc, 'eps', 0.08, 'insulation')] + r['layers']
    p = F.facade(doc, w.id, layers=etics)
    contrast = lambda x: x['theta'][x['kind'] == 1].mean() - x['theta'][x['kind'] == 0].mean()
    assert contrast(p) < contrast(r) / 5 and p['watts'] < r['watts'] / 2
    rgb = F.to_rgb(r['theta'], r['theta_e'], float(th.max()), 'rainbow')
    assert rgb.shape == th.shape + (3,) and rgb.dtype == np.uint8


def test_a_wall_without_layers_is_refused_not_guessed():
    doc, st, w = _wall(with_frame=False)
    from archforge.core.commands import UpdateEntity
    st.execute(UpdateEntity(w.id, {'wall_type': 'generic'}))
    with pytest.raises(ValueError):
        F.facade(doc, w.id)
