"""Grand Carillon only — bell geometry helpers for model_grand_carillon.py.

Own module (shared helpers stay read-only). Builds on hp_beetle_helpers' world-space bmesh blocks:
geometry is added to a common.Part in WORLD coordinates and BoneBuilder moves it to the bone pivot.

    BellProfile(keys, thick)       outer radius r(z) (PCHIP through (z, r) keys) + wall thickness t(z)
    bell_pos(th, z, r)             point on a surface of revolution; th = 0 is the FRONT (-Y),
                                   th = +90 deg is +X (the model's left)
    bell_shell(p, prof, ...)       thick bell wall with an arched opening on the front
                                   (opening half-angle a(z) -> 0 at the arch top), lip band, opening
                                   edge bands, per-face material callback (verdigris streaks)
    bell_band(p, mat, prof, z, profile, th0, th1)   raised moulding following the bell surface
    surf_frame(prof, th, z, off)   (point, outward normal, tangent) on the outer surface
"""
import math

from mathutils import Vector

from hp_beetle_helpers import _face, grid_faces, grid_rows, set_mat, strip
from hp_golem_helpers import pchip

TAU = 2.0 * math.pi


def bell_pos(th, z, r):
    return Vector((r * math.sin(th), -r * math.cos(th), z))


class BellProfile:
    def __init__(self, keys, thick):
        zs = [k[0] for k in keys]
        self.z0, self.z1 = zs[0], zs[-1]
        self.fr = pchip(zs, [k[1] for k in keys])
        tz = [k[0] for k in thick]
        self.ft = pchip(tz, [k[1] for k in thick])

    def r(self, z):
        return max(0.0, self.fr(z))

    def rin(self, z):
        return max(0.0, self.fr(z) - self.ft(z))

    def slope(self, z, e=1e-3):
        return (self.r(z + e) - self.r(z - e)) / (2 * e)


def surf_frame(prof, th, z, off=0.0):
    """Point on the outer surface (+ off along the normal), outward normal, horizontal tangent."""
    r = prof.r(z)
    dr = prof.slope(z)
    radial = Vector((math.sin(th), -math.cos(th), 0.0))
    n = (radial - Vector((0, 0, dr))).normalized()
    t = Vector((math.cos(th), math.sin(th), 0.0))
    return bell_pos(th, z, r) + n * off, n, t


def bell_shell(p, prof, zs_out, zs_in, nth, open_a, mat_out, mat_in, mat_edge, outer_mat=None):
    """Thick bell wall. zs_out / zs_in: row heights (bottom = lip, top = crown pole), the inner list
    must share its first value with zs_out and should share every row that lies inside the opening.
    open_a(z) -> half-angle (rad) of the front opening at height z (0 = closed row).
    outer_mat(th, z) -> material name for an outer face (None -> mat_out)."""
    bm = p.bm

    def row(z, rr, n):
        a = open_a(z)
        return [bell_pos(a + (TAU - 2 * a) * j / n, z, rr) for j in range(n + 1)]

    O_pts = [row(z, prof.r(z), nth) for z in zs_out]
    I_pts = [row(z, prof.rin(z), nth) for z in zs_in]
    O = grid_rows(bm, O_pts)
    I = grid_rows(bm, I_pts)
    # outer faces (material per face)
    for i in range(len(zs_out) - 1):
        for j in range(nth):
            f = _face(bm, [O[i][j], O[i][j + 1], O[i + 1][j + 1], O[i + 1][j]])
            if f is None:
                continue
            m = mat_out
            if outer_mat is not None:
                a = open_a((zs_out[i] + zs_out[i + 1]) / 2)
                th = a + (TAU - 2 * a) * (j + 0.5) / nth
                m = outer_mat(th, (zs_out[i] + zs_out[i + 1]) / 2) or mat_out
            set_mat(p, [f], m)
    fi = grid_faces(bm, I)
    for f in fi:
        f.normal_flip()
    set_mat(p, fi, mat_in)
    # lip band (bottom row outer <-> inner)
    set_mat(p, strip(bm, I[0], O[0]), mat_edge)
    # opening edge bands: rows shared by both lists while the row is open
    zin = {round(z, 6): k for k, z in enumerate(zs_in)}
    edge = []
    for i in range(len(zs_out) - 1):
        za, zb = zs_out[i], zs_out[i + 1]
        ka, kb = zin.get(round(za, 6)), zin.get(round(zb, 6))
        if ka is None or kb is None:
            continue
        if open_a(za) <= 1e-6 and open_a(zb) <= 1e-6:
            continue
        for jo, ji in ((0, 0), (nth, nth)):
            f = _face(bm, [O[i][jo], O[i + 1][jo], I[kb][ji], I[ka][ji]])
            if f:
                edge.append(f)
    set_mat(p, edge, mat_edge)
    return dict(outer=O, inner=I)


def bell_band(p, mat, prof, z, profile, th0=0.0, th1=TAU, seg=48, cap=True):
    """Raised moulding following the outer bell surface. profile: [(dz, out), ...] (metres, a closed
    cross-section around height z; out = offset along the surface normal). th0..th1 (rad) range;
    a full ring when th1 - th0 >= TAU."""
    bm = p.bm
    closed = (th1 - th0) >= TAU - 1e-6
    n = seg if closed else seg + 1
    rings = []
    for k in range(n):
        th = th0 + (th1 - th0) * k / seg
        ring = []
        for dz, out in profile:
            q, nn, _ = surf_frame(prof, th, z + dz, out)
            ring.append(bm.verts.new(q))
        rings.append(ring)
    fs = []
    m = len(profile)
    for k in range(n if closed else n - 1):
        A, B = rings[k], rings[(k + 1) % n]
        for i in range(m):
            j = (i + 1) % m
            f = _face(bm, [A[i], A[j], B[j], B[i]])
            if f:
                fs.append(f)
    if cap and not closed:
        for ring, rev in ((rings[0], True), (rings[-1], False)):
            f = _face(bm, list(reversed(ring)) if rev else ring)
            if f:
                fs.append(f)
    set_mat(p, fs, mat)
    return rings


def round_section(h, out, n=6, sink=0.01):
    """Closed half-round moulding section of height h, standing `out` off the surface."""
    pts = [(-h / 2, -sink)]
    for k in range(n + 1):
        a = math.pi * k / n
        pts.append((-math.cos(a) * h / 2, math.sin(a) * out))
    pts.append((h / 2, -sink))
    return pts
