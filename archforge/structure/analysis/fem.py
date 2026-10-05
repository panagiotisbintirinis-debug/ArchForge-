"""Linear 3D frame solver (direct stiffness method, 6 DOF per node).

Solver-neutral: it knows nodes, elements, supports and nodal loads only.  The
building model (``building.py``) derives those from the Document.

Element local axes: x along the element; for a vertical element the caller
gives the direction of local y (column width direction); for any other
element local z is as close to global +Z as possible.  ``Iy`` is the second
moment about local y (bending in the local x-z plane), ``Iz`` about local z.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np


@dataclass
class Element:
    n1: int
    n2: int
    E: float          # kN/m²
    G: float          # kN/m²
    A: float          # m²
    Iy: float         # m⁴
    Iz: float         # m⁴
    J: float          # m⁴
    y_dir: Optional[Tuple[float, float, float]] = None   # local y for vertical elements
    tag: str = ""


def local_axes(p1, p2, y_dir=None):
    """Rotation matrix whose rows are the local x, y, z unit vectors in global coordinates."""
    x = np.asarray(p2, float) - np.asarray(p1, float)
    L = float(np.linalg.norm(x))
    if L < 1e-9:
        raise ValueError("zero-length element")
    x /= L
    if abs(x[2]) > 0.999:                     # vertical
        y = np.asarray(y_dir if y_dir is not None else (1.0, 0.0, 0.0), float)
        y = y - x * float(y @ x)
        y /= np.linalg.norm(y)
        z = np.cross(x, y)
    else:
        z = np.array([0.0, 0.0, 1.0]) - x * x[2]
        z /= np.linalg.norm(z)
        y = np.cross(z, x)
    return np.vstack([x, y, z]), L


def local_stiffness(e: Element, L: float):
    k = np.zeros((12, 12))
    EA, GJ = e.E * e.A / L, e.G * e.J / L
    k[0, 0] = k[6, 6] = EA
    k[0, 6] = k[6, 0] = -EA
    k[3, 3] = k[9, 9] = GJ
    k[3, 9] = k[9, 3] = -GJ
    # Bending in the x-y plane (v, θz) with Iz.
    a, b, c, d = 12 * e.E * e.Iz / L ** 3, 6 * e.E * e.Iz / L ** 2, 4 * e.E * e.Iz / L, 2 * e.E * e.Iz / L
    for i, j, v in ((1, 1, a), (1, 5, b), (1, 7, -a), (1, 11, b), (5, 5, c), (5, 7, -b), (5, 11, d),
                    (7, 7, a), (7, 11, -b), (11, 11, c)):
        k[i, j] = k[j, i] = v
    # Bending in the x-z plane (w, θy) with Iy.
    a, b, c, d = 12 * e.E * e.Iy / L ** 3, 6 * e.E * e.Iy / L ** 2, 4 * e.E * e.Iy / L, 2 * e.E * e.Iy / L
    for i, j, v in ((2, 2, a), (2, 4, -b), (2, 8, -a), (2, 10, -b), (4, 4, c), (4, 8, b), (4, 10, d),
                    (8, 8, a), (8, 10, b), (10, 10, c)):
        k[i, j] = k[j, i] = v
    return k


class Frame:
    def __init__(self, nodes: Sequence[Tuple[float, float, float]], elements: Sequence[Element],
                 supports: Dict[int, Tuple[bool, bool, bool, bool, bool, bool]]):
        self.nodes = [tuple(map(float, p)) for p in nodes]
        self.elements = list(elements)
        self.supports = dict(supports)
        n = 6 * len(self.nodes)
        K = np.zeros((n, n))
        self._T, self._k = [], []
        for e in self.elements:
            R, L = local_axes(self.nodes[e.n1], self.nodes[e.n2], e.y_dir)
            T = np.zeros((12, 12))
            for b in range(4):
                T[3 * b:3 * b + 3, 3 * b:3 * b + 3] = R
            k = local_stiffness(e, L)
            dofs = list(range(6 * e.n1, 6 * e.n1 + 6)) + list(range(6 * e.n2, 6 * e.n2 + 6))
            K[np.ix_(dofs, dofs)] += T.T @ k @ T
            self._T.append(T)
            self._k.append(k)
        fixed = {6 * nid + i for nid, mask in self.supports.items() for i, f in enumerate(mask) if f}
        self.free = np.array([i for i in range(n) if i not in fixed], dtype=int)
        self.K = K
        Kff = K[np.ix_(self.free, self.free)]
        # Unstable structure (mechanism): the free stiffness is not positive definite.
        self._Kinv = None
        if len(self.free):
            scale = np.sqrt(np.maximum(np.diag(Kff), 1e-30))
            Kn = Kff / scale[:, None] / scale[None, :]
            try:
                L = np.linalg.cholesky(Kn)
            except np.linalg.LinAlgError:
                raise np.linalg.LinAlgError("unstable structure (mechanism)") from None
            if np.min(np.diag(L)) ** 2 < 1e-12:
                raise np.linalg.LinAlgError("unstable structure (mechanism)")
            # One factorisation for every load case: Kff⁻¹ = (S Kn S)⁻¹.
            Linv = np.linalg.inv(L)
            self._Kinv = (Linv.T @ Linv) / scale[:, None] / scale[None, :]
        self._Kff = Kff

    def solve(self, loads: Dict[int, Sequence[float]]):
        """Nodal loads {node: (Fx, Fy, Fz, Mx, My, Mz)} → (displacements, element end forces in local axes)."""
        n = 6 * len(self.nodes)
        F = np.zeros(n)
        for nid, vec in loads.items():
            F[6 * nid:6 * nid + 6] += np.asarray(vec, float)
        U = np.zeros(n)
        if len(self.free):
            U[self.free] = self._Kinv @ F[self.free]
        forces = []
        for e, T, k in zip(self.elements, self._T, self._k):
            dofs = list(range(6 * e.n1, 6 * e.n1 + 6)) + list(range(6 * e.n2, 6 * e.n2 + 6))
            forces.append(k @ (T @ U[dofs]))
        reactions = self.K @ U - F
        return U.reshape(-1, 6), forces, reactions.reshape(-1, 6)


def internal(f):
    """Internal actions at both ends from local end forces (beam sign convention).

    Returns ``((N, Vy, Vz, T, My, Mz) at start, same at end)`` with N > 0 in
    tension, and My / Mz positive when the bottom (-z) / the -y side is in tension.
    """
    start = (-f[0], -f[1], -f[2], -f[3], f[4], -f[5])
    end = (f[6], f[7], f[8], f[9], -f[10], f[11])
    return start, end
