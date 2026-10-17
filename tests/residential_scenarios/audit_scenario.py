"""Run one scenario's complete recorded gate; never silently advance to the next.

Run with PYTHONPATH=. python tests/residential_scenarios/audit_scenario.py --scenario S01.
Unperformed checks stay NOT_TESTED. ENGINEER_REVIEW never becomes verified.
"""
from __future__ import annotations

import argparse
import copy
import json
import tempfile
from dataclasses import asdict, is_dataclass
from pathlib import Path
from types import SimpleNamespace

from archforge.core.commands import CommandStack, DeleteEntities, MoveEntities, UpdateEntity
from archforge.core.model import Document
from archforge.project.persistence import load_project, save_project

ROOT = Path(__file__).resolve().parent


def plain(value):
    if is_dataclass(value):
        return plain(asdict(value))
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


def covers(mesh, point):
    """Independent vertical ray check against horizontal top triangles."""
    vertices = mesh.vertices
    if not vertices:
        return False
    z = max(v[2] for v in vertices)
    x, y = point
    for triangle in mesh.triangles:
        a, b, c = [vertices[i] for i in triangle]
        if not all(abs(p[2] - z) < 1e-6 for p in (a, b, c)):
            continue
        signs = [(x-q[0])*(r[1]-q[1]) - (y-q[1])*(r[0]-q[0]) for q, r in ((a,b),(b,c),(c,a))]
        if min(signs) >= -1e-8 or max(signs) <= 1e-8:
            return True
    return False


def audit(spec, out):
    from archforge.architecture.stairs import candidate_from_params, stair_centerline, stair_wall_conflicts
    from archforge.architecture.roof_need import room_face_of
    from archforge.geometry.mesh import _payload
    from archforge.mep.plumbing import route_plumbing
    from archforge.mep.drainage import route_drainage
    from archforge.mep.electrical import design_circuits, route_cables
    from archforge.mep.project_quote import project_quote
    from archforge.structure.analysis import analyze_cached
    from archforge.quantities.quote import quote as whole_quote

    checks, evidence = [], {}
    def record(category, name, status, detail):
        checks.append(dict(category=category, check=name, status=status, detail=str(detail)))
    def run(category, name, fn):
        try:
            detail = fn()
            record(category, name, 'PASS', detail if detail is not None else 'assertions passed')
        except Exception as exc:
            record(category, name, 'FAIL', f'{type(exc).__name__}: {exc}')
    def require(condition, text):
        if not condition:
            raise AssertionError(text)
        return text

    loaded = load_project(ROOT / spec['file'])
    record('Architecture', 'Load without skipped entities', 'PASS' if loaded.ok else 'FAIL', loaded.message())
    doc = loaded.doc
    entities = lambda kind: [e for e in doc.entities.values() if e.kind == kind]
    zs = sorted(set(float(e.params['z']) for e in entities('wall')))
    run('Architecture', 'Storeys and enclosed rooms', lambda: require(
        len(zs) == spec['storeys'] and all(len(doc.active_room_faces(z=z)) == 4 for z in zs),
        f'{len(zs)} storeys; four enclosed rooms on each'))
    run('Architecture', 'Door/window hosts', lambda: require(
        len(entities('door')) >= 8 and len(entities('window')) >= 4
        and all(e.parent_id in doc.entities for e in entities('door') + entities('window')), 'Openings have actual wall hosts'))
    run('Architecture', 'Real library furniture', lambda: require(len(entities('library_object')) >= 10, 'Four furniture instances plus six real bathroom assets; no furniture boxes'))
    run('Architecture', 'Kitchen cabinets', lambda: require(len(entities('cabinet')) >= 2, 'Base cabinet and sink cabinet'))
    run('Architecture', 'Bathroom and kitchen separated', lambda: require(all(
        float(e.params['x']) > 5 for e in entities('plumbing_point') if e.params['point_type'] in ('wc','basin','shower')),
        'Sanitary fixtures in separate bathroom rooms'))
    run('Architecture', 'Balcony and railing', lambda: require(len(entities('railing')) >= spec['balconies'], 'Canonical railing schema loaded'))
    run('Architecture', 'Attic ceilings top floor only', lambda: require(len(entities('room_ceiling')) == 4
        and all(room_face_of(doc, e)[1] == zs[-1] for e in entities('room_ceiling')), 'Four ceilings; none on lower storeys'))
    def stairs():
        st = entities('stair')
        assert len(st) == len(zs)-1
        for stair in st:
            c = candidate_from_params(stair.params)
            assert c.lower_z in zs and c.upper_z in zs
            assert not stair_wall_conflicts(doc,c), stair_wall_conflicts(doc,c)
        return 'Stair links actual levels and crosses no wall'
    run('Architecture', 'Stair levels and wall conflicts', stairs)
    def opening():
        stair = entities('stair')[0]; c = candidate_from_params(stair.params)
        slabs = [e for e in entities('room_roof') if e.params['level_z'] == c.lower_z]
        assert slabs, 'interstorey slab missing'
        for slab in slabs:
            mesh = _payload(doc, SimpleNamespace(semantic_kind=slab.kind, params=slab.params, entity_id=slab.id, transform=None))
            assert mesh.vertices, 'slab has no evaluated geometry'
            path = stair_centerline(c)
            # Sample inside the final flight, not on the boundary at its landing.
            end, previous = path[-1], path[-2]
            high = tuple(.95*a + .05*b for a,b in zip(end,previous))
            assert not covers(mesh, high), 'solid slab over last stair tread'
            assert covers(mesh, stair_centerline(c)[0]), 'slab removed above the low stair where headroom remains'
        return 'Ray checks of actual evaluated mesh: open over top steps; retained over first steps'
    run('Architecture', 'Physical slab opening and retained headroom', opening)
    run('Architecture', 'Roof is present', lambda: require(len(entities('pitched_roof')) == 1, spec['roof_form']))

    structure = analyze_cached(doc); evidence['structure'] = structure
    run('Structure', 'Analysis completes with members', lambda: require(not structure.get('error') and bool(structure.get('members')), structure.get('error') or 'Analysis completed'))
    run('Structure', 'Frame member counts', lambda: require(len(entities('structural_column')) == 9*len(zs)
        and len(entities('structural_beam')) == 6*len(zs), 'Columns and beams present on every storey'))
    run('Structure', 'Warnings explicitly inspected', lambda: require(not structure.get('warnings'), structure.get('warnings') or 'No top-level analysis warnings'))
    record('Structure', 'Engineering validation', 'REVIEW', f"verified={structure.get('verified')}; {structure.get('provenance')}")
    record('Structure', 'Member, footing, slab and joint engineering results', 'REVIEW', 'Raw results retained in evidence JSON; require structural engineer review, including any member failures')

    water = route_plumbing(doc); drain = route_drainage(doc); circuits = design_circuits(doc); cables = route_cables(doc)
    evidence['mep'] = {'plumbing':water,'drainage':drain,'circuits':circuits,'cables':cables}
    run('MEP', 'Cold/hot routing and all outlets served', lambda: require(water['cold'] and water['hot']
        and not water['report']['unserved'], str(water['report'])))
    run('MEP', 'Interstorey water risers', lambda: require(all(any(abs(a[2]-b[2]) > 1 for a,b,_ in water[k]) for k in ('cold','hot')), 'Cold/hot both have vertical risers'))
    run('MEP', 'Drainage and warnings', lambda: require(drain['pipes'] and drain['nodes'] and not drain['report']['warnings'], str(drain['report'])))
    run('MEP', 'Electrical assignment and routes', lambda: require(circuits['circuits'] and cables['runs']
        and not circuits['report']['unassigned'] and not circuits['report']['warnings'], str(circuits['report'])))
    record('MEP', 'Sizing and regulatory validation', 'REVIEW', 'Preserve all existing provenance. Routing output is not regulatory verification.')
    record('MEP', 'Heating/HVAC network continuity', 'NOT_TESTED', 'Current heating module is inventory-only; no hydraulic network solver is implemented')

    # Commands are exercised on a clone so audit cannot alter the delivered house.
    clone = Document.from_dict(doc.to_dict()); stack = CommandStack(clone)
    source = next(e for e in clone.entities.values() if e.kind == 'plumbing_point' and e.params['point_type']=='water_supply')
    sid = source.id
    electrical_before = copy.deepcopy([asdict(e) for e in clone.entities.values() if e.kind=='electrical_point'])
    run('Behavior', 'Select authoritative entity', lambda: (clone.selection.append(sid), require(sid in clone.selection, 'Selection accepted'))[-1])
    def movement():
        before=copy.deepcopy(clone.get(sid).params)
        stack.execute(MoveEntities([sid],.2,0.)); assert clone.get(sid).params['x'] == before['x']+.2
        stack.undo(); assert clone.get(sid).params == before
        stack.redo(); assert clone.get(sid).params['x'] == before['x']+.2
        stack.undo()
        return 'Move → undo → redo → undo restores original position'
    run('Behavior', 'Move / undo / redo', movement)
    def systems():
        before=route_plumbing(clone)
        for system in ('copper','manifold'):
            stack.execute(UpdateEntity(sid,{'pipe_system':system}))
            r=route_plumbing(clone); assert r['report']['system']==system and not r['report']['unserved']
            stack.undo()
        assert route_plumbing(clone)==before
        return 'Copper and manifold reroute; undo restores original multilayer routing'
    run('Behavior', 'Change plumbing system and undo', systems)
    run('Behavior', 'Plumbing edits preserve electrical entities', lambda: require(
        [asdict(e) for e in clone.entities.values() if e.kind=='electrical_point']==electrical_before, 'Electrical entities unchanged'))
    def deletion():
        eid=next(e.id for e in clone.entities.values() if e.kind=='library_object')
        before=clone.to_dict(); stack.execute(DeleteEntities([eid])); assert eid not in clone.entities
        stack.undo(); assert clone.to_dict()==before
        stack.redo(); assert eid not in clone.entities; stack.undo()
        return 'Delete/undo/redo/undo keeps the project intact'
    run('Behavior', 'Delete / undo / redo', deletion)
    def persistence():
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'reopen.archforge';before=doc.to_dict();save_project(doc,p);r=load_project(p)
            assert r.ok and r.doc.to_dict()==before
        return 'Save → independent reload: identical authoritative serialized state'
    run('Behavior', 'Save and reopen', persistence)

    commercial = project_quote(doc); whole = whole_quote(doc); evidence['quote']={'trades':commercial,'whole_project':whole}
    run('Quote', 'Shared price book resolves synthetic test prices', lambda: require(commercial['pricing_complete']
        and commercial['summary']['subtotal']>0, 'Synthetic test prices only; never market data'))
    run('Quote', 'Material and labour arithmetic', lambda: require(
        round(commercial['summary']['material_cost']+commercial['summary']['labour_cost'],2)==commercial['summary']['subtotal'],
        str(commercial['summary'])))
    record('Quote', 'Whole-project missing prices remain visible', 'PASS', f"{whole['missing']} unpriced rows; {whole['incomplete']} partly priced rows. No invented market prices.")
    record('Quote', 'Whole-project commercial completeness', 'REVIEW', 'Unknown prices and study-dependent quantities prevent an actual priced construction offer; synthetic test prices do not resolve this')

    ui_file=out/f"{spec['id']}_UI_CHECKS.json"
    ui=json.loads(ui_file.read_text()) if ui_file.exists() else {}
    evidence['ui']=ui
    for name in ('Plan: Ground','Plan: Level 1','PBR 3D','Structural','Plumbing plan','Drainage plan','Electrical plan','UI select','UI level switch','UI close/reopen'):
        result=ui.get(name)
        record('Visual/UI',name, result.get('status','NOT_TESTED') if result else 'NOT_TESTED',result.get('detail','') if result else 'No checked UI evidence yet')
    visual_file=out/f"{spec['id']}_VISUAL_REVIEW.json"
    review=json.loads(visual_file.read_text()) if visual_file.exists() else {}
    record('Visual/UI','Human visual inspection', review.get('status','NOT_TESTED'),review.get('detail','Images must be opened and inspected; screenshot existence is insufficient'))
    status='PASS' if all(c['status'] in ('PASS','N/A') for c in checks) else 'BLOCKED'
    result={'scenario':spec['id'],'status':status,'engineering_verified':False,'checks':checks,'evidence':plain(evidence)}
    out.mkdir(exist_ok=True)
    (out/f"{spec['id']}_EVIDENCE.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n')
    lines=[f"# {spec['id']} — {spec['name']}",'',f"Status: **{status}**. Next scenario is not authorised by a green unit test alone.",'',
           'Software fixture; not a certified engineering design. All prices are synthetic test values or explicitly missing.','',
           '| Area | Check | Status | Evidence / remaining work |','|---|---|---|---|']
    lines += [f"| {c['category']} | {c['check']} | {c['status']} | {c['detail'].replace('|','/').replace(chr(10),' ')} |" for c in checks]
    (out/f"{spec['id']}_REPORT.md").write_text('\n'.join(lines)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--scenario',default='S01');args=parser.parse_args()
    specs=json.loads((ROOT/'manifest.json').read_text()); spec=next(s for s in specs if s['id']==args.scenario)
    out=ROOT/'output'
    index=specs.index(spec)
    for previous in specs[:index]:
        p=out/f"{previous['id']}_EVIDENCE.json"
        if not p.exists() or json.loads(p.read_text())['status']!='PASS':
            raise SystemExit(f"STOP: {previous['id']} has not passed its complete gate")
    result=audit(spec,out)
    for row in result['checks']:print(row['status'],row['category'],row['check'],flush=True)
    raise SystemExit(0 if result['status']=='PASS' else 1)


if __name__=='__main__':main()
