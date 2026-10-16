"""Non-destructive structural-column / wall hosting geometry."""
import math


def _projection_interval(column_params, wall_params):
    x=float(column_params["x"]); y=float(column_params["y"])
    w=float(column_params["width"]); d=float(column_params["depth"])
    a=math.radians(float(column_params.get("rotation",0.0)))
    x1=float(wall_params["x1"]); y1=float(wall_params["y1"])
    x2=float(wall_params["x2"]); y2=float(wall_params["y2"])
    dx=x2-x1; dy=y2-y1; length=math.hypot(dx,dy)
    if length <= 1e-9:
        return None
    ux,uy=dx/length,dy/length
    ca,sa=math.cos(a),math.sin(a)
    corners=[]
    for lx,ly in ((-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)):
        corners.append((x+ca*lx-sa*ly,y+sa*lx+ca*ly))
    ss=[(px-x1)*ux+(py-y1)*uy for px,py in corners]
    # Perpendicular overlap uses the real rotated rectangular footprint.
    nx,ny=-uy,ux
    ds=[(px-x1)*nx+(py-y1)*ny for px,py in corners]
    half_t=float(wall_params["thickness"])/2.0
    if max(ds) < -half_t or min(ds) > half_t:
        return None
    lo=max(0.0,min(ss)); hi=min(length,max(ss))
    return (lo,hi) if hi > lo + 1e-9 else None


def wall_visible_intervals(wall_entity, columns):
    """Return wall-axis intervals left after embedded hosted columns are excluded."""
    wp=wall_entity.params if hasattr(wall_entity,"params") else wall_entity["params"]
    wall_id=wall_entity.id if hasattr(wall_entity,"id") else wall_entity["id"]
    length=math.hypot(float(wp["x2"])-float(wp["x1"]),float(wp["y2"])-float(wp["y1"]))
    cuts=[]
    for col in columns:
        cp=col.params if hasattr(col,"params") else col.get("params",{})
        if not bool(cp.get("embedded",False)):
            continue
        host=str(cp.get("host_wall_id",""))
        if host and host != str(wall_id):
            continue
        interval=_projection_interval(cp,wp)
        if interval is not None:
            cuts.append(interval)
    if not cuts:
        return [(0.0,length)]
    cuts.sort()
    merged=[]
    for lo,hi in cuts:
        if not merged or lo > merged[-1][1] + 1e-9:
            merged.append([lo,hi])
        else:
            merged[-1][1]=max(merged[-1][1],hi)
    visible=[]; cursor=0.0
    for lo,hi in merged:
        if lo > cursor + 1e-9: visible.append((cursor,lo))
        cursor=max(cursor,hi)
    if cursor < length - 1e-9: visible.append((cursor,length))
    return visible


def storey_member_top(doc, x, y, z, reach=0.35):
    """Top of the walls a column at (x, y) on the storey at ``z`` stands among.

    A column follows the walls it is placed on (or next to): the nearest wall of
    that storey within ``reach`` of its axis gives the top; otherwise the highest
    wall of the storey; with no walls, the next level above, else ``z + 2.70``.
    Beams sit under the same top.
    """
    z=float(z); x=float(x); y=float(y)
    walls=[e for e in doc.entities.values()
           if e.kind=="wall" and abs(float(e.params.get("z",0.0))-z)<0.05 and float(e.params.get("height",0.0))>0.0]
    best=None
    for w in walls:
        p=w.params
        x1,y1,x2,y2=(float(p[k]) for k in ("x1","y1","x2","y2"))
        dx,dy=x2-x1,y2-y1; L2=dx*dx+dy*dy
        t=0.0 if L2<=1e-12 else max(0.0,min(1.0,((x-x1)*dx+(y-y1)*dy)/L2))
        dist=math.hypot(x-(x1+t*dx),y-(y1+t*dy))-float(p.get("thickness",0.2))/2.0
        if dist<=reach and (best is None or dist<best[0]):
            best=(dist,z+float(p["height"]))
    if best is not None:
        return best[1]
    if walls:
        return max(z+float(w.params["height"]) for w in walls)
    above=sorted(float(v) for v in doc.levels.values() if float(v)>z+1e-9)
    return above[0] if above else z+2.70
