"""Physical conduit pieces from geometric fill (owner 24/10/2026).

Outside insulated wire diameters and minimum product bores come from cited
manufacturer tables in conduit_fill. The owner selected 30% as a project
setting, not a verified code limit. Every pipe has its own assigned lines.
Pulling and bends remain separate engineering review, not extra empty pipes.
"""
from __future__ import annotations
import math

SIZES=(16,20,25,32,40,50)
OUTDOOR_MIN=50  # Existing underground study choice; not a verified code clause.
OUTDOOR_SIZES=(50,63)
RULE=('Γεωμετρική πλήρωση από εξωτερικές ονομαστικές διαμέτρους μονωμένων αγωγών Nexans H07V-U/R '
      'και εσωτερικές διαμέτρους επιλεγμένων σωλήνων KOUVIDIS. Προεπιλογή ορίου έργου 30% κατόπιν επιλογής ιδιοκτήτη '
      '(24/10/2026), ρυθμιζόμενο· όχι επαληθευμένη κανονιστική απαίτηση. Καμπύλες/έλξη/θερμική '
      'ομαδοποίηση/καταλληλότητα προϊόντος προς έλεγχο. Κάθε σωλήνας έχει δικές του γραμμές.')


def fill(dn, conductors):
    """Geometric area fraction for the default calculation profile; no copper-area shortcut."""
    from archforge.mep.conduit_fill import CONDUIT_PROFILES,wire_bundle,geometric_fill
    wires=wire_bundle(conductors)
    bore=CONDUIT_PROFILES['conflex']['bores'].get(dn)
    return geometric_fill(bore,wires) if bore and wires is not None else math.inf


def size_for(conductors, bends=0, outdoor=False):
    """Smallest diameter under the owner's 30% setting and existing study size range.

    Bends are reviewed independently: a second pipe cannot fix a bend problem.
    """
    from archforge.mep.conduit_fill import CONDUIT_PROFILES,DEFAULT_LIMIT,DEFAULT_MAX_DN,wire_bundle,geometric_fill
    wires=wire_bundle(conductors)
    if wires is None:return None
    profile=CONDUIT_PROFILES['geonflex' if outdoor else 'conflex']
    candidates=[dn for dn,bore in sorted(profile['bores'].items())
                if (outdoor or dn<=DEFAULT_MAX_DN) and geometric_fill(bore,wires)<=DEFAULT_LIMIT+1e-12]
    return candidates[0] if candidates else None


def _outdoor(doc, p):
    """A conduit point in the ground outside the building: not in a room, not in a wall, at floor level."""
    from archforge.mep.electrical import _floor_of
    from archforge.mep.heating_layout import _inside
    floor = _floor_of(doc, p[2])
    if p[2] - floor > 0.5:
        return False
    try:
        # Measurement queries must not create or migrate persistent room IDs.
        from archforge.architecture.topology import room_faces
        faces = room_faces(doc, z=floor)
    except Exception as exc:                              # noqa: BLE001 — said: unknown rooms ≠ outdoors
        from archforge.core.notices import not_computed
        not_computed("conduits.rooms", f"Σωληνώσεις: δεν αναγνωρίστηκαν οι χώροι του ορόφου {floor:+.2f} — η διαδρομή "
                     "μπορεί να θεωρηθεί εξωτερική/υπόγεια", exc=exc)
        faces = []
    if any(_inside(f.polygon, p[0], p[1]) for f in faces):
        return False
    for w in doc.entities.values():
        if w.kind == "wall" and abs(float(w.params.get("z", 0.0)) - floor) < 0.05:
            q = w.params
            ax, ay, bx, by = (float(q[k]) for k in ("x1", "y1", "x2", "y2"))
            L2 = (bx - ax) ** 2 + (by - ay) ** 2 or 1.0
            t = max(0.0, min(1.0, ((p[0] - ax) * (bx - ax) + (p[1] - ay) * (by - ay)) / L2))
            if math.hypot(ax + (bx - ax) * t - p[0], ay + (by - ay) * t - p[1]) <= float(q["thickness"]) / 2 + 0.25:
                return False
    return True


def _key(p):
    return (round(p[0], 3), round(p[1], 3), round(p[2], 3))


def pulling_review(points, *, label=''):
    """Measured route geometry, not a pulling-force or replaceability certificate.

    Model polylines have no installed bend radii, friction data, pulling-force
    limits or confirmed access. No undocumented length/angle threshold turns
    this into a pass. Repeated and collinear router vertices add no bend.
    """
    vectors=[];length=0.
    for a,b in zip(points,points[1:]):
        vector=tuple(float(y)-float(x) for x,y in zip(a,b))
        distance=math.sqrt(sum(v*v for v in vector))
        length+=distance
        if distance>0:vectors.append(tuple(v/distance for v in vector))
    angles=[]
    for a,b in zip(vectors,vectors[1:]):
        dot=max(-1.,min(1.,sum(x*y for x,y in zip(a,b))))
        cross=(a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
        angle=math.degrees(math.atan2(math.sqrt(sum(v*v for v in cross)),dot))
        if angle>1e-7:angles.append(angle)  # floating point noise only, not an installation limit
    total=sum(angles)
    summary=(f'{label+": " if label else ""}{length:.2f} m · {len(angles)} αλλαγές διεύθυνσης '
             f'· άθροισμα {total:g}° — έλξη/αντικατάσταση προς έλεγχο. '
             'Δεν έχουν επαληθευτεί ακτίνες καμπυλών, τριβές/όρια έλξης και πρόσβαση στα άκρα/κουτιά. '
             'Η πλήρωση δεν πιστοποιεί εύκολη αντικατάσταση.')
    return {'length_m':length,'turn_angles_deg':angles,'total_turn_deg':total,
            'bend_radii_m':None,'accessibility_verified':False,
            'replacement_status':'ENGINEER_REVIEW','summary':summary}


def conduit_map(doc, route=None):
    """One row per real pipe piece, with its own conductors and geometric fill."""
    from collections import Counter
    from archforge.mep.electrical import electrical_points, mount_z, route_cables_cached
    from archforge.mep.electrical_board import conductors, switch_leg
    from archforge.mep.knx import dimming_of, control_system
    from archforge.mep.conduit_fill import (CONDUIT_PROFILES, DEFAULT_LIMIT, DEFAULT_MAX_DN,
                                           WIRE_DIAMETERS, allocate, wire_bundle, geometric_fill)
    route = route if route is not None else route_cables_cached(doc)
    points = {e.id:e for e in electrical_points(doc)}
    panel = next((e for e in points.values() if e.params['point_type']=='panel'), None)
    params = panel.params if panel is not None else {}
    limit = float(params.get('conduit_fill_limit', DEFAULT_LIMIT))
    profile_id = str(params.get('conduit_profile', 'conflex'))
    max_dn = int(params.get('conduit_max_dn', DEFAULT_MAX_DN))
    if profile_id not in CONDUIT_PROFILES or profile_id=='geonflex':
        raise ValueError('select a supported indoor conduit profile')
    circuits = {c['id']:c for c in route['circuits']}
    sections, edges_of = {}, {}
    for cid, circuit in circuits.items():
        dali = any(dimming_of(points[i].params)=='dali2' for i in circuit['points'] if i in points)
        sections[cid] = dict(Counter(s for _,_,s in conductors(circuit,dali)))
    for a,b,group,cid in route['runs']:
        if group=='switch' or cid not in circuits:
            continue
        edge=tuple(sorted((_key(a),_key(b))))
        if edge[0]!=edge[1]:edges_of.setdefault(cid,set()).add(edge)
    if control_system(doc)!='knx':
        light_circuit = {pid:c for c in route['circuits'] if c['group']=='lighting' for pid in c['points']}
        switch_circuit = {link['switch']:next((light_circuit[i] for i in link['lights'] if i in light_circuit),None)
                          for link in route['switch_links']}
        from archforge.mep.electrical_routes import TRAVELLER
        for a,b,sid in route.get('switch_runs',[]):
            circuit=switch_circuit.get(sid[len(TRAVELLER):] if sid.startswith(TRAVELLER) else sid)
            if circuit is None:continue
            cid=f'switch:{sid}'
            sections[cid]=dict(Counter(s for _,_,s in switch_leg(float(circuit['cable_mm2']))))
            edge=tuple(sorted((_key(a),_key(b))))
            if edge[0]!=edge[1]:edges_of.setdefault(cid,set()).add(edge)
    diameters={cid:wire_bundle(counts) for cid,counts in sections.items()}
    unsupported={cid for cid in edges_of if diameters[cid] is None}
    on_edge={}
    for cid,edges in edges_of.items():
        if cid in unsupported:continue
        for edge in edges:on_edge.setdefault(edge,set()).add(cid)
    allocation_cache, bundles, all_optimal = {}, {}, True
    for edge, active in sorted(on_edge.items()):
        midpoint=tuple((a+b)/2 for a,b in zip(*edge))
        outdoor=_outdoor(doc,midpoint)
        selected='geonflex' if outdoor else profile_id
        profile=CONDUIT_PROFILES[selected]
        options={dn:bore for dn,bore in profile['bores'].items() if not outdoor or dn>=OUTDOOR_MIN}
        maximum=max(options) if outdoor else max_dn
        cache_key=(selected,tuple(sorted(active)),maximum)
        if cache_key not in allocation_cache:
            allocation_cache[cache_key]=allocate({cid:diameters[cid] for cid in sorted(active)},
                                                 options,limit=limit,max_dn=maximum)
        result=allocation_cache[cache_key]
        unsupported.update(result['unsupported']);all_optimal=all_optimal and result['optimal_count']
        for pipe in result['pipes']:
            key=(selected,pipe['dn'],tuple(pipe['lines']))
            bundle=bundles.setdefault(key,{'edges':set(),'pipe':pipe,'profile':selected,'outdoor':outdoor})
            bundle['edges'].add(edge)
    edge_bundles={}
    for key,bundle in bundles.items():
        for edge in bundle['edges']:edge_bundles.setdefault(edge,set()).add(key)
    signatures={}
    for edge,keys in edge_bundles.items():
        for node in edge:signatures.setdefault(node,set()).add(frozenset(keys))
    # A change in pipe contents/size needs a junction. Parallel pipes that
    # simply continue together do not create a box at every router grid node.
    boundaries={node for node,values in signatures.items() if len(values)>1}
    boxes={_key((x,y,z)):kind for x,y,z,kind,_cid in route['boxes']}
    split=set()
    def name_of(node):
        if node in boxes:
            return {'junction':'κουτί διακλάδωσης','pull':'κουτί διέλευσης','floor':'κουτί δαπέδου'}.get(boxes[node],'κουτί')
        if panel is not None and math.dist(node,(float(panel.params['x']),float(panel.params['y']),mount_z(doc,panel.params)))<.3:
            return 'πίνακας'
        near=[(math.dist(node,(float(e.params['x']),float(e.params['y']),mount_z(doc,e.params))),e)
              for e in points.values()]
        distance,e=min(near,key=lambda item:item[0]) if near else (math.inf,None)
        if e is not None and distance<.6:return e.name or e.params['point_type']
        split.add(node);return 'κουτί διακλάδωσης σωληνώσεων'
    pieces, review, n = [], [], 0
    for key,bundle in sorted(bundles.items()):
        adjacency={}
        for a,b in bundle['edges']:
            adjacency.setdefault(a,set()).add(b);adjacency.setdefault(b,set()).add(a)
        remaining=set(adjacency)
        while remaining:
            seed=min(remaining);component={seed};queue=[seed];remaining.remove(seed)
            while queue:
                node=queue.pop()
                for other in adjacency[node]:
                    if other in remaining:remaining.remove(other);component.add(other);queue.append(other)
            n+=1;part=0
            cut={v for v in component if len(adjacency[v])!=2 or v in boxes or v in boundaries}
            if not cut:cut={min(component)}
            seen=set()
            for start in sorted(cut):
                for nxt in sorted(adjacency[start]):
                    edge=tuple(sorted((start,nxt)))
                    if edge in seen:continue
                    chain=[start,nxt];previous,current=start,nxt;seen.add(edge)
                    while current not in cut:
                        following=next(v for v in adjacency[current] if v!=previous)
                        seen.add(tuple(sorted((current,following))))
                        previous,current=current,following;chain.append(current)
                    part+=1
                    pipe=bundle['pipe'];line_ids=pipe['lines'];wire_counts={}
                    for cid in line_ids:
                        for section,count in sections[cid].items():wire_counts[section]=wire_counts.get(section,0)+count
                    pulling=pulling_review(chain,label=f'Σ{n}.{part}')
                    bends=len(pulling['turn_angles_deg'])
                    selected=bundle['profile'];profile=CONDUIT_PROFILES[selected]
                    piece={'id':f'Σ{n}.{part}','conduit':f'Σ{n}','from':name_of(chain[0]),'to':name_of(chain[-1]),
                           'a':chain[0],'b':chain[-1],'points':chain,
                           'length_m':round(sum(math.dist(a,b) for a,b in zip(chain,chain[1:])),2),
                           'dn':pipe['dn'],'inner_mm':pipe['inner_mm'],'profile':selected,'profile_name':profile['name'],
                           'profile_source':profile['source'],'count':1,'bends':bends,'outdoor':bundle['outdoor'],
                           'fill':geometric_fill(pipe['inner_mm'],pipe['diameters']),'fill_limit':limit,
                           'diameters':dict(pipe['diameters']),'wire_counts':wire_counts,'line_ids':list(line_ids),
                           'lines':[cid if cid in circuits else 'επιστροφή διακόπτη' for cid in line_ids],
                           'conductors':' + '.join(f'{count}×{section:g}'.replace('.',',') for section,count in sorted(wire_counts.items())),
                           'wire_sources':{s:WIRE_DIAMETERS[s]['source'] for s in wire_counts},
                           'pulling':pulling,'status':'ENGINEER_REVIEW'}
                    pieces.append(piece)
                    review.append(pulling['summary'])
    by_size={}
    for p in pieces:by_size[p['dn']]=round(by_size.get(p['dn'],0)+p['length_m'],2)
    warnings=[f'{cid}: λείπει τεκμηριωμένη διάμετρος ή η γραμμή δεν χωρά στη μέγιστη επιλεγμένη διάμετρο'
              for cid in sorted(unsupported)]
    return {'pieces':pieces,'by_size':dict(sorted(by_size.items())),'conduits':n,'warnings':warnings,
            'unsupported':sorted(unsupported),'review':review,'rule':RULE+f' Ενεργό όριο έργου: {limit*100:g}%.','fill_limit':limit,
            'profile':profile_id,'max_dn':max_dn,'packing_optimal_per_segment':all_optimal,
            'split_boxes':sorted(split),'outdoor_m':round(sum(p['length_m'] for p in pieces if p['outdoor']),2)}
