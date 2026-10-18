"""Owner 18 Oct: usable space, actual headroom cut, storage and landing guards.

Fixture design policy, not engineering approval. Uses existing shared commands
and canonical stair/railing/cabinet geometry; does not alter regulatory values.
"""
from archforge.core.commands import AddEntities
from archforge.architecture.stairs import candidate_from_params, stair_centerline, stair_opening_polygons
from archforge.geometry.regions import region_loops,point_in_polygon
from archforge.architecture.railings import default_params
from archforge.core.model import Entity


def add_under_stair_storage(doc, stack, stair_id):
    from archforge.architecture.stair_options import under_stair_command
    command,objects=under_stair_command(doc,stair_id)
    for i,e in enumerate(objects):e.id=f'{stair_id}-storage-{i}'
    stack.execute(command)
    return objects


def opening_guard_lines(stair,underside):
    c=candidate_from_params(stair.params)
    pieces=stair_opening_polygons(c,underside=underside)
    loops=region_loops(pieces,lambda x,y:any(point_in_polygon(x,y,p) for p in pieces))
    path=stair_centerline(c);end=path[-1];previous=path[-2]
    dx,dy=end[0]-previous[0],end[1]-previous[1]
    # The open end across the final flight remains an unobstructed exit.
    def exit_edge(a,b):
        return all(abs((p[0]-end[0])*dx+(p[1]-end[1])*dy)<1e-7 for p in (a,b))
    return [(a,b) for loop in loops for a,b in zip(loop,loop[1:]+loop[:1]) if not exit_edge(a,b)]


def protect_upper_opening(doc,stack,stair_id,underside):
    stair=doc.get(stair_id);lines=opening_guard_lines(stair,underside)
    # One continuous rail per open boundary chain: shared corners must not
    # accumulate duplicate posts from separate two-point rail objects.
    pending=list(lines);paths=[]
    while pending:
        start=next((i for i,(a,b) in enumerate(pending)
            if not any(all(abs(a[k]-d[k])<1e-7 for k in (0,1)) for c,d in pending)),0)
        a,b=pending.pop(start);path=[a,b]
        while True:
            following=next((i for i,(c,d) in enumerate(pending)
                if all(abs(path[-1][k]-c[k])<1e-7 for k in (0,1))),None)
            if following is None:break
            c,d=pending.pop(following);path.append(d)
        paths.append(path)
    # Existing railing defaults remain design defaults, not approved safety dimensions.
    rails=[Entity('railing',default_params('balusters',path,z=stair.params['upper_z']),
        id=f'{stair_id}-opening-guard-{i}',name='Προστατευτικό οπής σκάλας — προς έλεγχο',parent_id=stair_id)
        for i,path in enumerate(paths)]
    stack.execute(AddEntities(rails))
    return rails
