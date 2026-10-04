"""Semantic straight-kitchen generator for ArchForge.

Source dimensions are millimetres; generated ArchForge entities use metres.
Every panel/front/worktop remains an independent semantic kitchen_part.
"""
from typing import List
import math
from archforge.core.model import Entity

MM=0.001

def _part(run_id, role, name, x,y,z,w,d,h, rotation=0.0,
          roughness=0.5, metallic=0.0):
    return Entity("kitchen_part",{
        "x":x*MM,"y":y*MM,"z":z*MM,
        "width":w*MM,"depth":d*MM,"height":h*MM,
        "rotation":float(rotation),"role":role,"run_id":run_id,
        "roughness":float(roughness),"metallic":float(metallic),
    },name=name)

def build_straight_kitchen(run_id="Kitchen-1", total_length=3600.0,
                           num_base_modules=6,num_wall_modules=6,
                           depth_base=600.0,height_base=720.0,
                           plinth_height=100.0,plinth_recess=50.0,
                           countertop_thick=40.0,countertop_overhang=20.0,
                           backsplash_height=600.0,wall_height=720.0,
                           wall_depth=350.0,carcass_thick=18.0,
                           door_thick=18.0,door_gap=2.0,back_thick=8.0,
                           origin_x=0.0,origin_y=0.0,origin_z=0.0,rotation_deg=0.0)->List[Entity]:
    vals=(total_length,depth_base,height_base,plinth_height,countertop_thick,
          wall_height,wall_depth,carcass_thick,door_thick,back_thick)
    if any(float(v)<=0 for v in vals): raise ValueError("kitchen dimensions must be positive")
    if num_base_modules<1 or num_wall_modules<0: raise ValueError("invalid module count")
    if plinth_recess>=depth_base: raise ValueError("plinth recess must be smaller than base depth")
    out=[]
    def add(role,name,x,y,z,w,d,h,rough=.5,metal=0.0):
        out.append(_part(run_id,role,name,x,y,z,w,d,h,roughness=rough,metallic=metal))
    add("plinth","Kitchen_Plinth",0,plinth_recess,0,total_length,depth_base-plinth_recess,plinth_height,.8,.1)
    bw=total_length/num_base_modules
    if bw<=2*carcass_thick: raise ValueError("base modules are too narrow")
    zb=plinth_height
    def carcass(prefix,i,x,y,z,w,d,h):
        t=carcass_thick
        add("carcass_side",f"{prefix}_{i}_left",x,y,z,t,d,h,.6)
        add("carcass_side",f"{prefix}_{i}_right",x+w-t,y,z,t,d,h,.6)
        add("carcass_bottom",f"{prefix}_{i}_bottom",x+t,y,z,w-2*t,d,t,.6)
        add("carcass_top",f"{prefix}_{i}_top",x+t,y,z+h-t,w-2*t,d,t,.6)
        add("carcass_back",f"{prefix}_{i}_back",x+t,y+d-back_thick,z+t,w-2*t,back_thick,h-2*t,.7)
    for i in range(num_base_modules):
        x=i*bw; carcass("Base",i+1,x,0,zb,bw,depth_base,height_base)
        add("base_door",f"Base_{i+1}_Door",x+door_gap,-door_thick,zb+door_gap,
            bw-2*door_gap,door_thick,height_base-2*door_gap,.35)
        hw=min(160.0,bw*.5)
        add("handle",f"Base_{i+1}_Handle",x+(bw-hw)/2,-door_thick-20,zb+height_base-60,
            hw,15,15,.25,.85)
    zc=plinth_height+height_base
    add("countertop","Kitchen_Countertop",-5,-countertop_overhang,zc,
        total_length+10,depth_base+countertop_overhang,countertop_thick,.15,.05)
    if num_wall_modules:
        ww=total_length/num_wall_modules
        if ww<=2*carcass_thick: raise ValueError("wall modules are too narrow")
        zw=zc+countertop_thick+backsplash_height; yw=depth_base-wall_depth
        for i in range(num_wall_modules):
            x=i*ww; carcass("Wall",i+1,x,yw,zw,ww,wall_depth,wall_height)
            add("wall_door",f"Wall_{i+1}_Door",x+door_gap,yw-door_thick,zw+door_gap,
                ww-2*door_gap,door_thick,wall_height-2*door_gap,.3)
    angle=math.radians(float(rotation_deg)); ca=math.cos(angle); sa=math.sin(angle)
    for entity in out:
        p=entity.params; x=float(p["x"]); y=float(p["y"])
        p["x"]=float(origin_x)+x*ca-y*sa
        p["y"]=float(origin_y)+x*sa+y*ca
        p["z"]=float(origin_z)+float(p["z"])
        p["rotation"]=float(p.get("rotation",0.0))+angle
    return out
