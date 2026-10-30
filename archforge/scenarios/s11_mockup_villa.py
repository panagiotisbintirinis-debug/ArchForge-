"""Mockup villa: inferred furniture-relative dimensions, NOT a measured/surveyed building.

Reuses the common UI scenario builder and S06 circulation/stair arrangement. The
reference is the two-storey 3D mockup, not a construction document. See NOTES.
"""
from copy import deepcopy
from archforge.scenarios.builder import build_spec
from archforge.scenarios.s06_diorofo import SPEC as BASE

KEY = '11'
NAME = 'S11_mockup_villa'
TITLE = 'Κατοικία mockup — πέτρα, βεράντες, πέργκολα και πισίνα'
SPEC = deepcopy(BASE)
# Inferred design scale: library double bed 160×200 cm; compare several furniture
# objects, not screen pixels along perspective axes. Approximate main block 15×10 m.
for st in SPEC['storeys'].values():
    st['outline'] = [(x*1.25,y) for x,y in st['outline']]
    st['walls'] = [((a[0]*1.25,a[1]),(b[0]*1.25,b[1]),t) for a,b,t in st['walls']]
    st['openings'] = [(k,x*1.25,y,w,*rest) for k,x,y,w,*rest in st['openings']]
    st['rooms'] = {k:(x*1.25,y) for k,(x,y) in st['rooms'].items()}
    st['furniture'] = [(k,x*1.25,y,r) for k,x,y,r in st['furniture']]
    if st.get('kitchen'): st['kitchen'] = (st['kitchen'][0]*1.25,st['kitchen'][1])
    st['baths'] = [((p[0]*1.25,p[1]),kind) for p,kind in st.get('baths',())]
    st['height'] = 3.0
SPEC['storeys']['Floor 1']['furniture'] = [
    (name,1.5 if name == 'Διπλό κρεβάτι 160×200' and y == 1.1 else x,
     3.2 if name == 'Μονό κρεβάτι 90×200' else y,turn)
    for name,x,y,turn in SPEC['storeys']['Floor 1']['furniture']]
SPEC['stairs'] = []
# Give the U stair a continuous upper landing, not a stair through a bedroom wall.
st = SPEC['storeys']['Floor 1']
st['walls'] = [((10.0 if a[0] == 11.875 else a[0],a[1]),
                (10.0 if b[0] == 11.875 else b[0],b[1]),t) for a,b,t in st['walls']]
SPEC['roof'] = 'flat'
SPEC['pergolas'] = [('timber',(0.4,-3.6),(7.8,-0.4))]
SPEC['pools'] = [{'x':10.5,'y':-8.,'length':8.,'width':4.,'plant_x':19.,'plant_y':-8.}]
SPEC['storeys']['Ground']['furniture'] += [
    ('Τραπέζι κήπου 4θέσιο',3.8,-2.,0),('Ξαπλώστρα',8.,-4.6,90),
    ('Ξαπλώστρα',11.,-4.6,90),('Ομπρέλα κήπου Ø250',14.,-4.6,0),
    ('Ελιά σε γλάστρα',-2.,2.,0),('Ελιά σε γλάστρα',17.,8.,0)]
# Sliding-looking floor-height glazing and access to the upper balcony.
SPEC['storeys']['Floor 1']['openings'] = [
    ('door',x,y,1.4) if k == 'window' and y == 0 and x in (3.75,12.125) else (k,x,y,w,*rest)
    for k,x,y,w,*rest in SPEC['storeys']['Floor 1']['openings']]
OWNER_PENDING = ()
FINDINGS = []
NOTES = '''Σχέδιο επίδειξης, όχι αποτύπωση ή τεχνικά πιστοποιημένη μελέτη.
Αναφορά: η διώροφη εικόνα 3D του mockup ArchForge (30/10/2026).
Οδηγός αναλογιών: διπλό κρεβάτι βιβλιοθήκης 1,60×2,00 m, καναπές και τραπέζι.
Κυρίως όγκος περίπου 15×10 m, στάθμες 0/+3 m, πισίνα 8×4 m, οικόπεδο 28×30 m.
Αυτές είναι επιλεγμένες διαστάσεις σχεδιασμού κατόπιν εκτίμησης, όχι μετρήσεις της εικόνας.
Η αθέατη κάτοψη, η σκάλα και οι χώροι υπηρεσίας αποτελούν σχεδιαστικές παραδοχές·
η κυκλοφορία βασίζεται στο κοινό δείγμα S06. Η εικόνα δεν καθορίζει μοναδική κάτοψη.
Οι αυτόματοι υπολογισμοί/προεπιλογές του προγράμματος δεν αποτελούν υπογεγραμμένη
μελέτη στατικών/ΗΜ/πισίνας. Κάθε FAIL της πύλης παραμένει εμφανές στην αναφορά.
'''


def build(window):
    s = build_spec(window,KEY,TITLE,SPEC)
    from archforge.core.commands import UpdateEntity, DeleteEntities
    from archforge.ui.layers_panel import set_workspace
    set_workspace(window,"arch",announce=False)
    s.level("Ground")
    s.stair((10.7,7.1),(14.5,7.1),layout="u")
    from archforge.ui.slab_tools import place_balcony
    s.level('Floor 1')
    s.step('Μπαλκόνι νότια, από το κοινό εργαλείο',lambda:place_balcony(window,[(0,0),(15,0),(15,-1.8),(0,-1.8)]))
    s.level('Ground')
    s.step('Πλακόστρωτη βεράντα',lambda:place_balcony(window,[(-.4,0),(15.4,0),(15.4,-4.),(-.4,-4.)]))
    s.step('Ελεύθερη πρόσβαση βεράντας',lambda:s.stack.execute(DeleteEntities([
        e.id for e in s.doc.entities.values() if e.kind=='railing' and abs(float(e.params.get('z',0))) < .01])))
    s.step('Έδαφος οικοπέδου',window._create_terrain)
    terrain = next(e for e in s.doc.entities.values() if e.kind=='terrain')
    s.step('Όρια οικοπέδου',lambda:s.stack.execute(UpdateEntity(terrain.id,{'x0':-6.,'y0':-14.,'x1':22.,'y1':16.,'elevation':-.18})))
    for a,b in [((-5,-13),(21,-13)),((21,-13),(21,15)),((21,15),(-5,15)),((-5,15),(-5,-8))]:
        s.wall(a,b,.25,height=.8)
    for e in list(s.doc.entities.values()):
        if e.kind=='wall' and float(e.params.get('thickness',0)) >= .24:
            s.step('Πέτρα πρόσοψης '+e.name,lambda eid=e.id:s.stack.execute(UpdateEntity(eid,{'material_id':'limestone_light'})))
    return s
