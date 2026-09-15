import pytest

def test_orbit_camera_math():
    try:
        from archforge.ui.viewport_3d import OrbitCamera
    except ModuleNotFoundError:
        pytest.skip("PySide6 not installed in headless test environment")

    cam = OrbitCamera(cx=0.0, cy=0.0, cz=0.0, distance=10.0, yaw=0.0, pitch=0.0)
    w, h = 800, 600
    proj = cam.project((0.0, 0.0, 0.0), w, h)
    assert proj is not None
    sx, sy, depth = proj
    assert abs(sx - 400.0) < 1e-3
    assert abs(sy - 300.0) < 1e-3
    assert abs(depth - 10.0) < 1e-3

    origin, direction = cam.unproject_ray(400.0, 300.0, w, h)
    assert abs(origin[0] - 0.0) < 1e-3
    assert abs(origin[1] - (-10.0)) < 1e-3
    assert abs(direction[0] - 0.0) < 1e-3
    assert abs(direction[1] - 1.0) < 1e-3
