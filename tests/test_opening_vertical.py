import math
import pytest

from archforge.core.model import Document,Entity
from archforge.core.commands import CommandStack
from archforge.core.opening_vertical import OpeningVerticalEditTransaction,opening_elevation_handles


def wall():
    return Entity('wall',{'x1':0.0,'y1':0.0,'x2':6.0,'y2':0.0,'z':0.5,'height':3.0,'thickness':0.15})


def window(doc,w):
    e=Entity('window',{'offset':3.0,'width':1.2,'height':1.0,'sill':0.8},parent_id=w.id)
    doc.add(e);return e


def door(doc,w):
    e=Entity('door',{'offset':2.0,'width':0.9,'height':2.0,'sill':0.0},parent_id=w.id)
    doc.add(e);return e


def test_window_top_stretch_preserves_sill():
    d=Document();w=wall();d.add(w);e=window(d,w);s=CommandStack(d)
    tx=OpeningVerticalEditTransaction(d,s,e.id,'top');hud=tx.update(2.8)
    assert math.isclose(tx.preview['sill'],0.8)
    assert math.isclose(tx.preview['height'],1.5)
    assert math.isclose(hud['top_z'],2.8)
    tx.commit();assert math.isclose(d.get(e.id).params['height'],1.5)
    s.undo();assert math.isclose(d.get(e.id).params['height'],1.0)


def test_window_bottom_stretch_preserves_top():
    d=Document();w=wall();d.add(w);e=window(d,w);s=CommandStack(d)
    old_top=w.params['z']+e.params['sill']+e.params['height']
    tx=OpeningVerticalEditTransaction(d,s,e.id,'bottom');hud=tx.update(1.0)
    assert math.isclose(hud['top_z'],old_top)
    assert math.isclose(tx.preview['sill'],0.5)
    assert math.isclose(tx.preview['height'],1.3)


def test_door_bottom_is_fixed():
    d=Document();w=wall();d.add(w);e=door(d,w);s=CommandStack(d)
    with pytest.raises(ValueError):OpeningVerticalEditTransaction(d,s,e.id,'bottom')


def test_opening_vertical_edit_cannot_exceed_wall_top():
    d=Document();w=wall();d.add(w);e=window(d,w);s=CommandStack(d)
    tx=OpeningVerticalEditTransaction(d,s,e.id,'top')
    with pytest.raises(ValueError):tx.update(4.0)
    assert math.isclose(d.get(e.id).params['height'],1.0)


def test_window_elevation_handles_include_top_and_bottom():
    d=Document();w=wall();d.add(w);e=window(d,w)
    hs=opening_elevation_handles(d,e.id,'XZ')
    assert {h[0] for h in hs}=={'top','bottom'}
    values={h[0]:h[2] for h in hs}
    assert math.isclose(values['bottom'],1.3)
    assert math.isclose(values['top'],2.3)


def test_door_elevation_handles_only_top():
    d=Document();w=wall();d.add(w);e=door(d,w)
    hs=opening_elevation_handles(d,e.id,'XZ')
    assert [h[0] for h in hs]==['top']
    assert math.isclose(hs[0][2],2.5)
