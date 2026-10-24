"""Electrical measured schedule and passage alternatives; one quote/price path.

Box specifications and study quantities are explicit user inputs. Product data
remain those cited in conduit_fill; neither cost completeness nor geometric fit
certifies an installation. No market prices are supplied.
"""
from __future__ import annotations
from collections import defaultdict
import hashlib
import math

BOX_LABELS={'junction':'Κουτί διακλάδωσης','floor':'Κουτί δαπέδου','pull':'Κουτί διέλευσης','lv':'Κουτί ασθενών'}
MODES={'floor':'Δάπεδο','ceiling':'Οροφή','wall':'Περιμετρικά'}
ZONES={'floor':'δάπεδο','ceiling':'οροφή','wall':'τοίχος / κατακόρυφα','free':'εκτός ζώνης τοίχου','outdoor':'έδαφος / εξωτερικά'}
STUDY_ITEMS={'electrical.rcd','electrical.panel_enclosure','electrical.led_driver',
             'lv.cable.network','lv.cable.tv','lv.conduit.network','lv.conduit.tv','knx.bus_conduit'}


def panel(doc):
    return next((e for e in doc.entities.values() if e.kind=='electrical_point' and e.params.get('point_type')=='panel'),None)


def spec_code(code,spec):
    return code+'.spec.'+hashlib.sha256(spec.encode('utf-8')).hexdigest()[:16]


def routing_command(doc,mode,profile=None):
    from archforge.core.commands import UpdateEntities
    if mode not in MODES: raise ValueError('select floor, ceiling or wall passage')
    changes={e.id:{'routing':mode} for e in doc.entities.values() if e.kind=='electrical_point'
             and e.params.get('point_type') not in ('panel','network_rack') and e.params.get('routing','auto')!=mode}
    p=panel(doc)
    if profile and p and p.params.get('conduit_profile','conflex')!=profile: changes[p.id]={'conduit_profile':profile}
    return UpdateEntities(changes)


def apply_routing(doc,stack,mode,profile=None):
    command=routing_command(doc,mode,profile)
    if command.changes: stack.execute(command); return True
    return False


def routing_preview(doc,mode,profile=None):
    from archforge.core.model import Document
    clone=Document.from_dict(doc.to_dict())
    # Preview evaluates the shared command on a private clone. Layer locks
    # protect committed edits, not read-only alternative calculations.
    routing_command(clone,mode,profile).do(clone)
    return clone


def box_inventory(doc,cmap=None):
    from archforge.mep.electrical import route_cables_cached
    from archforge.mep.conduits import conduit_map, _key
    from archforge.mep.low_voltage import route_low_voltage_cached
    cmap=conduit_map(doc) if cmap is None else cmap
    p=panel(doc); defaults=p.params.get('electrical_box_defaults',{}) if p else {}
    overrides=p.params.get('electrical_box_specs',{}) if p else {}; nodes={}
    def location(xyz): return tuple(round(float(x),6) for x in xyz)
    def add(xyz,kind,circuits=''):
        xyz=location(xyz); key=kind+':'+','.join(f'{v:.6f}' for v in xyz)
        if key not in nodes: nodes[key]={'key':key,'kind':kind,'point':xyz,'circuits':set()}
        nodes[key]['circuits'].update(filter(None,str(circuits).split(',')))
    power=route_cables_cached(doc)['boxes']
    for x,y,z,kind,cid in power: add((x,y,z),kind,cid)
    occupied={_key(b[:3]) for b in power}
    for xyz in cmap['split_boxes']:
        if _key(xyz) not in occupied: add(xyz,'junction')
    for x,y,z,_kind,cid in route_low_voltage_cached(doc)['boxes']: add((x,y,z),'lv',cid)
    split_points={_key(xyz) for xyz in cmap['split_boxes']}
    out=[]
    for key,b in sorted(nodes.items()):
        spec=overrides.get(key,defaults.get(b['kind'],''))
        out.append({**b,'split':b['kind']!='lv' and _key(b['point']) in split_points,'circuits':sorted(b['circuits']),'spec':spec,'spec_source':'USER_INPUT' if spec else 'ENGINEER_REVIEW'})
    return out


def measured_rows(doc,result=None):
    from archforge.mep.electrical_board import analyse,_location,_walls_by_floor
    from archforge.mep.electrical import _floor_of
    from archforge.mep.conduits import conduit_map
    from archforge.mep.conduit_fill import WIRE_DIAMETERS,CONDUIT_PROFILES
    r=result if result is not None else analyse(doc); rows=[]
    for purchase in r['purchase']:
        section=purchase['mm2']; wire=WIRE_DIAMETERS.get(section); typ=wire['type'] if wire else 'τύπος από τη μελέτη'
        code=f'electrical.cable.{typ.replace(" ","_")}.{section:g}mm2' if wire else f'electrical.cable.unspecified.{section:g}mm2'
        rows.append((f'Καλώδιο αγωγός {section:g} mm² — {typ} (ανά αγωγό)'.replace('.', ','),'m',purchase['with_waste'],
                     {'code':code,'why':'Μέτρα αγωγών και επιστροφών από τις διαδρομές με την καταχωρισμένη φύρα. '
                      'Προϊόν γεωμετρικού υπολογισμού, επιβεβαίωση πριν την αγορά.',
                      'status':'ENGINEER_REVIEW','source':wire['source'] if wire else '', 'specified':bool(wire)}))
    cmap=conduit_map(doc); totals=defaultdict(float); walls=_walls_by_floor(doc)
    for piece in cmap['pieces']:
        for a,b in zip(piece['points'],piece['points'][1:]):
            floor=_floor_of(doc,min(a[2],b[2]))
            zone='outdoor' if piece['outdoor'] else _location(doc,walls.get(floor,[]),floor,a,b)[0]
            totals[(piece['profile'],piece['dn'],zone)]+=math.dist(a,b)*piece['count']
    for (profile,dn,zone),length in sorted(totals.items()):
        spec=CONDUIT_PROFILES[profile]
        rows.append((f'Σωλήνας {spec["name"]} Φ{dn} — {ZONES[zone]}','m',round(length,2),
                     {'code':f'electrical.conduit.{profile}.{dn}.{zone}', 'why':cmap['rule']+
                      ' Φυσικά μήκη όλων των σωλήνων, μαζί με παράλληλες σωληνώσεις. Ζώνη από την υπάρχουσα ταξινόμηση του πίνακα.',
                      'status':'ENGINEER_REVIEW','source':spec['source'],'specified':True}))
    groups=defaultdict(int); split_counts=defaultdict(int)
    for b in box_inventory(doc,cmap):
        key=(b['kind'],b['spec']);groups[key]+=1;split_counts[key]+=int(b['split'])
    for (kind,spec),count in sorted(groups.items()):
        base=f'electrical.box.{kind}'
        suffix=f" (περιλαμβάνει {split_counts[(kind,spec)]} θέσεις χωρισμού)" if split_counts[(kind,spec)] else ''
        rows.append((BOX_LABELS[kind]+' — '+(spec or 'μέγεθος / μοντέλο δεν ορίστηκε')+suffix,'τεμ.',count,
                     {'code':spec_code(base,spec) if spec else base+'.unspecified',
                      'why':'Κουτιά διαδρομών από το σχέδιο· χωρισμός σε υπάρχον κουτί μετριέται μία φορά. '
                      'Διαστάσεις, θύρες και καταλληλότητα επιβεβαιώνονται από τον χρήστη.',
                      'status':'ENGINEER_REVIEW','source':'Document: electrical_box_defaults / electrical_box_specs','specified':bool(spec)}))
    return rows


def finalise_rows(doc,rows):
    from archforge.mep.low_voltage import lv_points
    p=panel(doc); params=p.params if p else {}; specs=params.get('electrical_item_specs',{})
    quantities=params.get('electrical_quantity_inputs',{})
    rack=next((e for e in lv_points(doc) if e.params['point_type']=='network_rack'),None); out=[]
    for desc,unit,qty,raw in rows:
        meta=dict(raw); code=meta['code']; meta.update(base_code=code,quantity_input=meta.get('quantity_input',qty is None),requires_spec=code in STUDY_ITEMS)
        if code in STUDY_ITEMS:
            spec=specs.get(code,'')
            if not spec and code=='lv.cable.network' and rack: spec=str(rack.params.get('network_cable','')).strip()
            meta['specified']=bool(spec)
            if spec:
                desc+=' — '+spec; meta['code']=spec_code(code,spec); meta['source']='Document: user study specification'
            # Existing descriptions already identify study-specified items;
            # the schedule's unresolved column records the missing specification.
        if qty is None and code in quantities:
            qty=quantities[code]; meta['why']+=' Ποσότητα χρήστη από τη μελέτη.'
            meta['source']+='; Document: electrical_quantity_inputs'
        out.append((desc,unit,qty,meta))
    return out


def takeoff(doc):
    from archforge.quantities.materials import electrical_list
    from archforge.quantities.quote import costed
    from archforge.mep.project_pricebook import effective_prices
    from archforge.mep.conduits import conduit_map
    from archforge.mep.low_voltage import route_low_voltage_cached
    raw=electrical_list(doc); rows=costed(doc,'Ηλεκτρολογικά',raw); missing=[]; prices=effective_prices(doc)
    for item,(_,_,_,meta) in zip(rows,raw):
        reasons=[]
        if item['quantity'] is None: reasons.append('ποσότητα από μελέτη')
        if not meta.get('specified',True): reasons.append('μέγεθος / τύπος / μοντέλο')
        price=prices.get(item['code'])
        if price is None or price.material_unit_price is None: reasons.append('τιμή υλικού')
        if price is None or price.labour_unit_price is None: reasons.append('τιμή εργασίας')
        if reasons: missing.append({'code':item['code'],'description':item['description'],'reasons':reasons})
    geometry_missing=list(conduit_map(doc)['warnings'])+list(route_low_voltage_cached(doc)['warnings'])
    if panel(doc) is None and any(e.kind=='electrical_point' and e.params.get('point_type') not in
                                 ('network_rack','data_outlet','wifi_ap','tv_outlet') for e in doc.entities.values()):
        geometry_missing.append('Δεν υπάρχει ηλεκτρικός πίνακας: οι γραμμές ισχύος δεν επιμετρήθηκαν.')
    complete=bool(rows) and not missing and not geometry_missing; subtotal=round(sum(x['amount'] or 0 for x in rows),2)
    return {'rows':rows,'raw_rows':raw,'known_subtotal':subtotal,'material':round(sum(x['material'] or 0 for x in rows),2),
            'labour':round(sum(x['labour'] or 0 for x in rows),2),'total':subtotal if complete else None,
            'complete':complete,'missing':missing,'geometry_missing':geometry_missing,'engineering_status':'ENGINEER_REVIEW'}


def compare_routing(doc,profiles=None):
    return {mode:{'document':clone,**takeoff(clone)} for mode in ('floor','ceiling')
            for clone in (routing_preview(doc,mode,(profiles or {}).get(mode)),)}


def edit_price(doc,stack,code,component,value):
    from archforge.mep.project_pricebook import effective_prices,set_project_price
    from archforge.mep.trade_costing import PriceEntry
    if component not in ('material','labour'): raise ValueError('select material or labour')
    if value is not None:
        value=float(value)
        if not math.isfinite(value) or value<0: raise ValueError('Η τιμή πρέπει να είναι πεπερασμένος μη αρνητικός αριθμός.')
    old=effective_prices(doc).get(code,PriceEntry())
    return set_project_price(stack,doc,code,PriceEntry(material_unit_price=value if component=='material' else old.material_unit_price,
                                                    labour_unit_price=value if component=='labour' else old.labour_unit_price,source='user'))


def extra_rows(doc):
    """Owner-entered unmodelled accessories/work, optionally per whole-project passage."""
    p=panel(doc)
    if p is None:return []
    modes={e.params.get('routing','auto') for e in doc.entities.values() if e.kind=='electrical_point'
           and e.params.get('point_type') not in ('panel','network_rack')}
    active=next(iter(modes)) if len(modes)==1 else 'mixed';rows=[]
    for item in p.params.get('electrical_extra_items',[]):
        scope=item['mode'];qty=item['quantity'];why='Είδος / ποσότητα που καταχώρισε ο χρήστης από τη μελέτη ή προσφορά.'
        if scope!='all':
            if active in MODES and scope!=active:continue
            why+=' Μόνο για συνολική διέλευση: '+MODES[scope]+'.'
            if active not in MODES:
                qty=None;why+=' Το τρέχον έργο έχει μικτή / αυτόματη διέλευση· επιβεβαιώστε την ποσότητα.'
        rows.append((item['description'],'%s'%item['unit'],qty,{'code':'electrical.extra.'+item['id'],'extra_id':item['id'],
                     'why':why,'status':'ENGINEER_REVIEW','source':'Document: owner quotation','quantity_input':False}))
    return rows
