"""Wall-hosted MEP coordinate adapter.

Wall remains authoritative. This module derives world placement from semantic
wall parameters and never mutates wall geometry.
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
import math


@dataclass(frozen=True)
class WallCoordinateFrame:
    x1: float; y1: float; z: float
    x2: float; y2: float
    height: float; thickness: float; length: float
    ux: float; uy: float; nx: float; ny: float

    @classmethod
    def from_wall_params(cls, params: Dict[str, Any]) -> "WallCoordinateFrame":
        x1=float(params["x1"]); y1=float(params["y1"]); z=float(params.get("z",0.0))
        x2=float(params["x2"]); y2=float(params["y2"])
        height=float(params["height"]); thickness=float(params["thickness"])
        dx=x2-x1; dy=y2-y1; length=math.hypot(dx,dy)
        if length <= 1e-9:
            raise ValueError("degenerate wall axis")
        ux=dx/length; uy=dy/length
        return cls(x1,y1,z,x2,y2,height,thickness,length,ux,uy,-uy,ux)

    def local_to_world(self,s:float,d:float,h:float)->Tuple[float,float,float]:
        return (self.x1+self.ux*s+self.nx*d,
                self.y1+self.uy*s+self.ny*d,
                self.z+h)

    def world_to_local(self,x:float,y:float,z:float)->Tuple[float,float,float]:
        dx=x-self.x1; dy=y-self.y1
        return (dx*self.ux+dy*self.uy, dx*self.nx+dy*self.ny, z-self.z)

    def resolve_surface_offset(self,surface_role:str,embed_depth:float=0.0,
                               clearance:float=0.0,normal_offset:float=0.0)->float:
        if embed_depth < 0 or clearance < 0:
            raise ValueError("embed_depth and clearance must be non-negative")
        role=str(surface_role).lower().strip()
        half=self.thickness/2.0
        if role=="positive_face":
            return half-embed_depth+clearance+normal_offset
        if role=="negative_face":
            return -half+embed_depth-clearance+normal_offset
        if role=="centerline":
            return normal_offset
        raise ValueError(f"unknown wall surface role: {surface_role}")


class MEPWallMountResolver:
    @staticmethod
    def evaluate_mount(wall_entity:Dict[str,Any], mount_params:Dict[str,Any],
                       part_params:Dict[str,Any])->Dict[str,Any]:
        frame=WallCoordinateFrame.from_wall_params(wall_entity["params"])
        u=float(mount_params.get("surface_u",0.0))
        if not 0.0 <= u <= 1.0:
            raise ValueError("surface_u must be between 0 and 1")
        s=u*frame.length
        h=float(mount_params.get("elevation",0.0))
        if not 0.0 <= h <= frame.height:
            raise ValueError("MEP elevation lies outside wall height")
        embed=float(mount_params.get("embed_depth",0.0))
        clearance=float(mount_params.get("clearance",0.0))
        normal=float(mount_params.get("normal_offset",0.0))
        d=frame.resolve_surface_offset(mount_params.get("surface_role","positive_face"),
                                       embed,clearance,normal)
        x,y,z=frame.local_to_world(s,d,h)
        wall_yaw=math.atan2(frame.uy,frame.ux)
        local_rot=float(part_params.get("rotation",0.0))
        yaw=wall_yaw+local_rot
        return {"world_x":x,"world_y":y,"world_z":z,
                "rotation_rad":yaw,"rotation_deg":math.degrees(yaw),
                "local_s":s,"local_d":d,"local_h":h}

    @staticmethod
    def derive_penetration_void(wall_entity:Dict[str,Any],part_entity:Dict[str,Any],
                                mount_params:Dict[str,Any])->Optional[Dict[str,Any]]:
        embed=float(mount_params.get("embed_depth",0.0))
        if embed <= 0.0:
            return None
        resolved=MEPWallMountResolver.evaluate_mount(
            wall_entity,mount_params,part_entity["params"])
        p=part_entity["params"]
        return {"host_id":wall_entity["id"],"source_part_id":part_entity["id"],
                "void_type":"mep_penetration","surface_u":float(mount_params["surface_u"]),
                "local_s":resolved["local_s"],"local_h":resolved["local_h"],
                "width":float(p.get("width",0.0)),"height":float(p.get("height",0.0)),
                "depth":embed,"required_clearance":float(mount_params.get("clearance",0.0))}
