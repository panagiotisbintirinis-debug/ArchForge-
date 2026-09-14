from archforge.geometry.mesh import MeshPayload
from archforge.geometry.mesh_validation import validate_mesh

def test_closed_tetrahedron_is_watertight_and_manifold():
 m=MeshPayload(((0,0,0),(1,0,0),(0,1,0),(0,0,1)),((0,2,1),(0,1,3),(1,2,3),(2,0,3)),('x',)*4);r=validate_mesh(m)
 assert r.watertight and r.manifold and not r.findings

def test_missing_face_reports_boundary_edges():
 m=MeshPayload(((0,0,0),(1,0,0),(0,1,0),(0,0,1)),((0,2,1),(0,1,3),(1,2,3)),('x',)*3);r=validate_mesh(m)
 assert not r.watertight and r.boundary_edges==3 and any(f.code=='boundary_edges' for f in r.findings)

def test_three_faces_sharing_edge_is_nonmanifold():
 m=MeshPayload(((0,0,0),(1,0,0),(0,1,0),(0,-1,0),(0,0,1)),((0,1,2),(1,0,3),(0,1,4)),('x',)*3);r=validate_mesh(m)
 assert not r.manifold and r.nonmanifold_edges>=1

def test_same_edge_direction_detects_orientation_conflict():
 m=MeshPayload(((0,0,0),(1,0,0),(0,1,0),(0,0,1)),((0,1,2),(0,1,3)),('x','x'));r=validate_mesh(m)
 assert r.orientation_conflicts==1 and not r.manifold

def test_zero_area_triangle_is_rejected():
 m=MeshPayload(((0,0,0),(1,0,0),(2,0,0)),((0,1,2),),('x',));r=validate_mesh(m)
 assert r.degenerate_triangles==1 and not r.manifold
