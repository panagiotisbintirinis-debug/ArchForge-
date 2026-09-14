from archforge.core.model import Document,Entity
from archforge.architecture.intent import infer_architecture,ArchitectureDefaults


def _rectangle():
 d=Document()
 for a,b in [((0,0),(5,0)),((5,0),(5,4)),((5,4),(0,4)),((0,4),(0,0))]:
  d.add(Entity('wall',{'x1':a[0],'y1':a[1],'x2':b[0],'y2':b[1],'z':0,'height':2.8,'thickness':.2}))
 return d


def test_four_walls_infer_editable_house_elements():
 d=_rectangle();r=infer_architecture(d)
 assert len(r.room_signatures)==1
 kinds=[d.get(i).kind for i in r.created_ids]
 assert set(kinds)=={'room_foundation','room_floor','room_ceiling','room_roof'}
 assert all(not d.get(i).locked for i in r.created_ids)


def test_inference_is_idempotent_not_duplicate_magic():
 d=_rectangle();a=infer_architecture(d);b=infer_architecture(d)
 assert len(a.created_ids)==4 and b.created_ids==()


def test_user_can_disable_automatic_assumptions():
 d=_rectangle();r=infer_architecture(d,ArchitectureDefaults(auto_roof=False,auto_foundation=False))
 assert {d.get(i).kind for i in r.created_ids}=={'room_floor','room_ceiling'}


def test_generated_elements_depend_on_semantic_walls():
 d=_rectangle();r=infer_architecture(d);walls=[e.id for e in d.entities.values() if e.kind=='wall']
 for derived in r.created_ids:
  assert all(derived in d.dependencies.get(w,set()) for w in walls)


def test_roof_is_an_assumption_not_a_project_mode():
 d=_rectangle();r=infer_architecture(d);roof=next(d.get(i) for i in r.created_ids if d.get(i).kind=='room_roof')
 assert roof.params['roof_type']=='auto'
 d.update(roof.id,{'roof_type':'flat'})
 assert d.get(roof.id).params['roof_type']=='flat'


def test_intent_survives_save_roundtrip():
 d=_rectangle();infer_architecture(d);d2=Document.from_dict(d.to_dict())
 assert len([e for e in d2.entities.values() if e.kind.startswith('room_')])==4
 assert d2.to_dict()['format']==7
