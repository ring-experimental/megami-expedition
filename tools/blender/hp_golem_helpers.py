"""Hi-poly geometry helpers for the Steam Golem (model_golem.py only — not shared).

Builds on common.Part / hp_helpers WITHOUT modifying them. All geometry is added to a common.Part
in the part's LOCAL (pivot-relative) space.

    Surf(keys, n, M)          smooth superellipse loft (PCHIP-interpolated sections along local z,
                              optionally re-oriented by matrix M). pt()/nrm() sample the surface,
                              so plates, bands, trims, rivets can be placed ON it.
    surf_shell(...)           closed shell of a Surf (with fan caps / poles)
    surf_plate(...)           thick plate patch lying on a Surf (theta x z range), raised by `off`
    surf_trim(...)            sweep a cross-section along a (theta, z) path on a Surf (bands, rims,
                              weld beads, edge trims)
    surf_rivets(...)          rivet rows / columns on a Surf
    rivet / bolt              tiny domed rivet (18 tris) / hex bolt head oriented along a normal
    lathe_axis(...)           surface of revolution around an arbitrary axis
    arc_plate(...)            thick cylindrical shell segment around an axis (couters, poleyns, lames)
    orient(normal, up)        euler (deg) that maps local +Z to `normal` (for Part primitives)
    LPart                     a part made of several layers with different bevel / smoothing,
                              joined into ONE object (= one bone) at build time
"""
import bisect
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from common import Part
import hp_helpers as hp

TAU = 2.0 * math.pi
D = math.radians


def linspace(a, b, n):
    """n+1 values from a to b inclusive."""
    return [a + (b - a) * i / n for i in range(n + 1)]


# ---------------------------------------------------------------------------
# Interpolation
# ---------------------------------------------------------------------------

def pchip(xs, ys):
    """Monotone cubic (PCHIP) interpolant through (xs, ys); clamps outside the range."""
    n = len(xs)
    if n == 1:
        return lambda x: ys[0]
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]
    d = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    m = [0.0] * n
    if n == 2:
        m = [d[0], d[0]]
    else:
        m[0], m[-1] = d[0], d[-1]
        for i in range(1, n - 1):
            if d[i - 1] * d[i] <= 0:
                m[i] = 0.0
            else:
                w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
                m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
        # gentle ends
        m[0] = 0.5 * d[0]
        m[-1] = 0.5 * d[-1]

    def f(x):
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]
        i = min(max(bisect.bisect_right(xs, x) - 1, 0), n - 2)
        t = (x - xs[i]) / h[i]
        t2, t3 = t * t, t * t * t
        return ((2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h[i] * m[i]
                + (-2 * t3 + 3 * t2) * ys[i + 1] + (t3 - t2) * h[i] * m[i + 1])
    return f


# ---------------------------------------------------------------------------
# Superellipse loft surface
# ---------------------------------------------------------------------------

class Surf:
    """Superellipse loft along local z.

    keys: [(z, w, d), (z, w, d, cx, cy), (z, w, d, cx, cy, n)] — width (x), depth (y), centre, exponent.
    theta convention (before M): 0 = +x, 90 = +y, 180 = -x, 270 = -y (model front when M = identity).
    M: 4x4 matrix placing the surface in part space (rotate the loft axis, translate).
    """

    def __init__(self, keys, n=2.5, M=None):
        keys = sorted(keys, key=lambda k: k[0])
        zs = [k[0] for k in keys]

        def col(i, default):
            return [k[i] if len(k) > i else default for k in keys]
        self.fw = pchip(zs, col(1, 0.0))
        self.fd = pchip(zs, col(2, 0.0))
        self.fcx = pchip(zs, col(3, 0.0))
        self.fcy = pchip(zs, col(4, 0.0))
        self.fn = pchip(zs, col(5, n))
        self.z0, self.z1 = zs[0], zs[-1]
        self.M = M if M is not None else Matrix.Identity(4)
        self.R = self.M.to_3x3()

    def raw(self, th, z):
        w = max(self.fw(z), 1e-6)
        d = max(self.fd(z), 1e-6)
        e = 2.0 / self.fn(z)
        c, s = math.cos(th), math.sin(th)
        x = self.fcx(z) + 0.5 * w * math.copysign(abs(c) ** e, c)
        y = self.fcy(z) + 0.5 * d * math.copysign(abs(s) ** e, s)
        return Vector((x, y, z))

    def frame(self, th, z, eps=1e-3):
        p = self.raw(th, z)
        t = self.raw(th + eps, z) - self.raw(th - eps, z)
        u = self.raw(th, z + eps) - self.raw(th, z - eps)
        n = t.cross(u)
        if n.length < 1e-10:
            n = Vector((math.cos(th), math.sin(th), 0.0))
        return p, n.normalized()

    def pt(self, th, z, off=0.0):
        p, n = self.frame(th, z)
        return self.M @ (p + n * off)

    def nrm(self, th, z):
        return (self.R @ self.frame(th, z)[1]).normalized()

    def centre(self, z):
        return self.M @ Vector((self.fcx(z), self.fcy(z), z))

    def is_pole(self, z):
        return self.fw(z) < 1e-4 or self.fd(z) < 1e-4


def _bridge(bm, A, B, closed):
    """Faces between two vertex rows (len 1 = pole)."""
    if len(A) == 1 and len(B) == 1:
        return
    n = max(len(A), len(B))
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        j = (i + 1) % n
        try:
            if len(A) == 1:
                bm.faces.new((A[0], B[j], B[i]))
            elif len(B) == 1:
                bm.faces.new((A[i], A[j], B[0]))
            else:
                bm.faces.new((A[i], A[j], B[j], B[i]))
        except ValueError:
            pass


def _thetas(nth, th0=None, th1=None, phase=0.0):
    if th0 is None:
        return [phase + TAU * i / nth for i in range(nth)], True
    return [th0 + (th1 - th0) * i / nth for i in range(nth + 1)], False


def surf_shell(p, mat, S, zs, nth=48, off=0.0, cap=(True, True), phase=0.0):
    """Closed shell of Surf S sampled at the z levels `zs` (ascending). Pole rings (w or d == 0)
    collapse to a vertex; open ends get a triangle-fan cap when cap[i]."""
    bm = p.bm
    ths, closed = _thetas(nth, phase=phase)
    rows, allv = [], []
    for z in zs:
        if S.is_pole(z):
            row = [bm.verts.new(S.centre(z))]
        else:
            row = [bm.verts.new(S.pt(th, z, off)) for th in ths]
        rows.append(row)
        allv += row
    for k in range(len(rows) - 1):
        _bridge(bm, rows[k], rows[k + 1], True)
    for idx, flag, flip in ((0, cap[0], True), (-1, cap[1], False)):
        row = rows[idx]
        if flag and len(row) > 2:
            c = bm.verts.new(S.centre(zs[idx]))
            allv.append(c)
            n = len(row)
            for i in range(n):
                j = (i + 1) % n
                f = (row[j], row[i], c) if flip else (row[i], row[j], c)
                try:
                    bm.faces.new(f)
                except ValueError:
                    pass
    return p._assign(allv, mat)


def surf_plate(p, mat, S, th0, th1, z0, z1, off0=0.0, off1=0.03, nth=12, nz=6, inner=True):
    """Thick plate lying on S between theta th0..th1 (radians) and z0..z1, from normal offset off0
    (bottom) to off1 (top). Full ring when th1 - th0 >= 2pi. z0 / z1 may be callables f(theta)
    (curved or V-shaped borders). inner=False skips the (hidden) bottom face (keep off0 < 0 so the
    open side is buried in the base shell)."""
    bm = p.bm
    full = abs(th1 - th0) >= TAU - 1e-6
    if full:
        ths = [th0 + TAU * i / nth for i in range(nth)]
    else:
        ths = linspace(th0, th1, nth)
    f0 = z0 if callable(z0) else (lambda th: z0)
    f1 = z1 if callable(z1) else (lambda th: z1)
    cols = [linspace(f0(th), f1(th), nz) for th in ths]
    top = [[bm.verts.new(S.pt(th, cols[i][k], off1)) for i, th in enumerate(ths)] for k in range(nz + 1)]
    bot = [[bm.verts.new(S.pt(th, cols[i][k], off0)) for i, th in enumerate(ths)] for k in range(nz + 1)]
    allv = [v for r in top + bot for v in r]
    for k in range(nz):
        _bridge(bm, top[k], top[k + 1], full)
        if inner:
            _bridge(bm, bot[k + 1], bot[k], full)
    # walls along the z0 / z1 borders
    _bridge(bm, bot[0], top[0], full)
    _bridge(bm, top[-1], bot[-1], full)
    if not full:
        colA_t = [r[0] for r in top]
        colA_b = [r[0] for r in bot]
        colB_t = [r[-1] for r in top]
        colB_b = [r[-1] for r in bot]
        _bridge(bm, colA_t, colA_b, False)
        _bridge(bm, colB_b, colB_t, False)
    return p._assign(allv, mat)


def capsule(p, mat, a, b, w, d, up=(0, 0, 1), n=3.0, seg=10, end=0.6):
    """Rounded bar from a to b: superellipse cross-section w (across) x d (along `up`), rounded
    ends bulging end*max(w,d)/2 beyond a and b (seg*8 tris). Chunky finger segments, pins, handles."""
    bm = p.bm
    a, b = Vector(a), Vector(b)
    t = b - a
    L = t.length
    t.normalize()
    u = Vector(up) - t * t.dot(Vector(up))
    if u.length < 1e-6:
        u = t.orthogonal()
    u.normalize()
    v = t.cross(u)
    r = 0.5 * max(w, d)
    e = end * r
    prof = [(-e, 0.0), (-e * 0.643, 0.766), (0.0, 1.0), (L, 1.0), (L + e * 0.643, 0.766), (L + e, 0.0)]
    ex = 2.0 / n
    rows, allv = [], []
    for ax, sc in prof:
        c = a + t * ax
        if sc <= 1e-6:
            row_ = [bm.verts.new(c)]
        else:
            row_ = []
            for i in range(seg):
                ang = TAU * i / seg + math.pi / seg
                cx, cy = math.cos(ang), math.sin(ang)
                x = 0.5 * w * sc * math.copysign(abs(cx) ** ex, cx)
                y = 0.5 * d * sc * math.copysign(abs(cy) ** ex, cy)
                row_.append(bm.verts.new(c + v * x + u * y))
        rows.append(row_)
        allv += row_
    for k in range(len(rows) - 1):
        _bridge(bm, rows[k], rows[k + 1], True)
    return p._assign(allv, mat)


def surf_trim(p, mat, S, path, profile, closed=False, cap=True):
    """Sweep a closed cross-section `profile` [(dn, dt), ...] (dn = along the surface normal,
    dt = sideways within the surface, perpendicular to the path) along `path` [(theta, z), ...]."""
    bm = p.bm
    n = len(path)
    pts = [S.pt(th, z) for th, z in path]
    nrms = [S.nrm(th, z) for th, z in path]
    rings, allv = [], []
    for i in range(n):
        if closed:
            t = pts[(i + 1) % n] - pts[i - 1]
        else:
            t = pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]
        t.normalize()
        N = nrms[i]
        B = N.cross(t).normalized()
        ring = [bm.verts.new(pts[i] + N * dn + B * dt) for dn, dt in profile]
        rings.append(ring)
        allv += ring
    m = len(profile)
    for k in range(n - 1 + (1 if closed else 0)):
        A, Bv = rings[k], rings[(k + 1) % n]
        for i in range(m):
            j = (i + 1) % m
            try:
                bm.faces.new((A[i], A[j], Bv[j], Bv[i]))
            except ValueError:
                pass
    if cap and not closed:
        for ring in (rings[0], rings[-1]):
            try:
                bm.faces.new(ring)
            except ValueError:
                pass
    return p._assign(allv, mat)


def band_profile(off, h, sink=0.02, ch=None):
    """Chamfered rectangular band cross-section (dn, dt): height h, raised `off` above the surface."""
    ch = min(off * 0.45, h * 0.25) if ch is None else ch
    if ch <= 1e-6:
        return [(-sink, -h / 2), (off, -h / 2), (off, h / 2), (-sink, h / 2)]
    return [(-sink, -h / 2), (off - ch, -h / 2), (off, -h / 2 + ch), (off, h / 2 - ch), (off - ch, h / 2),
            (-sink, h / 2)]


def round_profile(r, n=6, lift=0.0, flat=1.0):
    """Round bead cross-section (weld seams, pipes lying on a surface)."""
    return [(lift + r * math.sin(TAU * i / n) * flat, r * math.cos(TAU * i / n)) for i in range(n)]


def surf_band(p, mat, S, z, h, off, nth=48, th0=None, th1=None, sink=0.02, ch=None):
    """Raised band around S at height z (full ring unless th0/th1 given)."""
    if th0 is None:
        path = [(TAU * i / nth, z) for i in range(nth)]
        return surf_trim(p, mat, S, path, band_profile(off, h, sink, ch), closed=True)
    path = [(th0 + (th1 - th0) * i / nth, z) for i in range(nth + 1)]
    return surf_trim(p, mat, S, path, band_profile(off, h, sink, ch), closed=False)


# ---------------------------------------------------------------------------
# Small hardware
# ---------------------------------------------------------------------------

def _basis(nrm, up=(0, 0, 1)):
    z = Vector(nrm).normalized()
    u = Vector(up)
    x = u.cross(z)
    if x.length < 1e-6:
        x = Vector((1, 0, 0)).cross(z)
        if x.length < 1e-6:
            x = Vector((0, 1, 0)).cross(z)
    x.normalize()
    y = z.cross(x)
    return x, y, z


def orient(nrm, up=(0, 0, 1), spin=0.0):
    """Euler XYZ (degrees) rotating local +Z onto nrm, local +Y as close to `up` as possible."""
    x, y, z = _basis(nrm, up)
    if spin:
        c, s = math.cos(D(spin)), math.sin(D(spin))
        x, y = x * c + y * s, -x * s + y * c
    m = Matrix((x, y, z)).transposed()
    return tuple(math.degrees(a) for a in m.to_euler("XYZ"))


def rivet(p, mat, pos, nrm, r=0.02, h=0.014, seg=5, sink=0.006):
    """Domed rivet head (seg*3 tris)."""
    bm = p.bm
    x, y, n = _basis(nrm)
    pos = Vector(pos)
    base = [bm.verts.new(pos - n * sink + (x * math.cos(TAU * i / seg) + y * math.sin(TAU * i / seg)) * r)
            for i in range(seg)]
    mid = [bm.verts.new(pos + n * (h * 0.55) + (x * math.cos(TAU * i / seg) + y * math.sin(TAU * i / seg)) * r * 0.8)
           for i in range(seg)]
    top = bm.verts.new(pos + n * h)
    _bridge(bm, base, mid, True)
    _bridge(bm, mid, [top], True)
    return p._assign(base + mid + [top], mat)


def bolt(p, mat, pos, nrm, r=0.03, h=0.025, seg=6, spin=0.0, sink=0.008):
    """Hex bolt head oriented along nrm (seg*3 tris)."""
    bm = p.bm
    x, y, n = _basis(nrm)
    pos = Vector(pos)
    a0 = D(spin)

    def ring(zz, rr):
        return [bm.verts.new(pos + n * zz + (x * math.cos(a0 + TAU * i / seg) + y * math.sin(a0 + TAU * i / seg)) * rr)
                for i in range(seg)]
    b = ring(-sink, r)
    t = ring(h, r)
    c = bm.verts.new(pos + n * (h + r * 0.15))
    _bridge(bm, b, t, True)
    _bridge(bm, t, [c], True)
    return p._assign(b + t + [c], mat)


def fplace(P, N, up=(0, 0, 1), lloc=(0, 0, 0), lrot=(0, 0, 0)):
    """(loc, rot_deg) for a Part primitive placed in the surface frame at P (local z = N, local y ~ up),
    offset by lloc and rotated by lrot (deg, XYZ) inside that frame."""
    from mathutils import Euler
    x, y, z = _basis(N, up)
    B = Matrix((x, y, z)).transposed()
    loc = Vector(P) + B @ Vector(lloc)
    R = B @ Euler(tuple(D(a) for a in lrot), "XYZ").to_matrix()
    return tuple(loc), tuple(math.degrees(a) for a in R.to_euler("XYZ"))


def theta_at_x(S, z, x, lo, hi, it=40):
    """Bisection: theta in [lo, hi] (radians) where S.pt(theta, z).x == x (monotone on that range)."""
    flo = S.pt(lo, z).x - x
    for _ in range(it):
        mid = 0.5 * (lo + hi)
        fm = S.pt(mid, z).x - x
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return 0.5 * (lo + hi)


def surf_rivets(p, mat, S, pts, off=0.0, r=0.02, h=0.014, seg=5):
    """Rivets at surface params pts [(theta, z), ...] raised by off."""
    for th, z in pts:
        rivet(p, mat, S.pt(th, z, off), S.nrm(th, z), r=r, h=h, seg=seg)
    return p


def row(th0, th1, z, count, closed=False):
    """Param points along theta at height z."""
    if closed:
        return [(th0 + TAU * i / count, z) for i in range(count)]
    return [(th0 + (th1 - th0) * i / (count - 1), z) for i in range(count)]


def col(th, z0, z1, count):
    return [(th, z0 + (z1 - z0) * i / (count - 1)) for i in range(count)]


# ---------------------------------------------------------------------------
# Revolution / arcs around arbitrary axes
# ---------------------------------------------------------------------------

def lathe_axis(p, mat, center, axis, profile, seg=32, ref=None, cap=(False, False), a0=0.0, a1=360.0,
               closed=False):
    """Surface of revolution: profile [(r, h), ...] revolved around `axis` through `center`.
    r == 0 -> pole. cap: fan caps on open first/last rings. Partial when a1 - a0 < 360.
    closed=True bridges the last profile ring back to the first (solid ring cross-sections)."""
    bm = p.bm
    A = Vector(axis).normalized()
    R0 = Vector(ref) if ref is not None else A.orthogonal()
    R0 = (R0 - A * A.dot(R0)).normalized()
    R1 = A.cross(R0)
    C = Vector(center)
    full = (a1 - a0) >= 359.999
    angs = [D(a0 + (a1 - a0) * i / seg) for i in range(seg if full else seg + 1)]
    rows, allv = [], []
    for r, h in profile:
        if r <= 1e-6:
            row_ = [bm.verts.new(C + A * h)]
        else:
            row_ = [bm.verts.new(C + (R0 * math.cos(a) + R1 * math.sin(a)) * r + A * h) for a in angs]
        rows.append(row_)
        allv += row_
    for k in range(len(rows) - 1):
        _bridge(bm, rows[k], rows[k + 1], full)
    if closed:
        _bridge(bm, rows[-1], rows[0], full)
    for idx, flag in ((0, cap[0]), (-1, cap[1])):
        rw = rows[idx]
        if flag and len(rw) > 2:
            c = bm.verts.new(C + A * profile[idx][1])
            allv.append(c)
            _bridge(bm, rw, [c], full)
    return p._assign(allv, mat)


def arc_plate(p, mat, center, axis, ref, r0, r1, a0, a1, h0, h1, seg=16):
    """Thick cylindrical shell segment around `axis` through `center`: radii r0 (inner) .. r1 (outer),
    angles a0..a1 (deg, from `ref` toward axis x ref), extent h0..h1 along the axis."""
    bm = p.bm
    A = Vector(axis).normalized()
    R0 = (Vector(ref) - A * A.dot(Vector(ref))).normalized()
    R1 = A.cross(R0)
    C = Vector(center)
    full = (a1 - a0) >= 359.999
    angs = [D(a0 + (a1 - a0) * i / seg) for i in range(seg if full else seg + 1)]
    prof = [(r1, h0), (r1, h1), (r0, h1), (r0, h0)]
    rings = []
    for a in angs:
        d = R0 * math.cos(a) + R1 * math.sin(a)
        rings.append([bm.verts.new(C + d * r + A * h) for r, h in prof])
    allv = [v for r in rings for v in r]
    nr = len(rings)
    for k in range(nr - (0 if full else 1)):
        Ar, Br = rings[k], rings[(k + 1) % nr]
        for i in range(4):
            j = (i + 1) % 4
            try:
                bm.faces.new((Ar[i], Ar[j], Br[j], Br[i]))
            except ValueError:
                pass
    if not full:
        for rg in (rings[0], rings[-1]):
            try:
                bm.faces.new(rg)
            except ValueError:
                pass
    return p._assign(allv, mat)


def arc_bolts(p, mat, center, axis, ref, rad, angles, along, nrm=None, **kw):
    """Bolts on a circle (radius rad around axis, at axial offset `along`); nrm defaults to the axis."""
    A = Vector(axis).normalized()
    R0 = (Vector(ref) - A * A.dot(Vector(ref))).normalized()
    R1 = A.cross(R0)
    for a in angles:
        d = R0 * math.cos(D(a)) + R1 * math.sin(D(a))
        bolt(p, mat, Vector(center) + d * rad + A * along, nrm if nrm is not None else A, **kw)
    return p


def arc_rivets(p, mat, center, axis, ref, rad, angles, along, radial=False, **kw):
    A = Vector(axis).normalized()
    R0 = (Vector(ref) - A * A.dot(Vector(ref))).normalized()
    R1 = A.cross(R0)
    for a in angles:
        d = R0 * math.cos(D(a)) + R1 * math.sin(D(a))
        rivet(p, mat, Vector(center) + d * rad + A * along, d if radial else A, **kw)
    return p


# ---------------------------------------------------------------------------
# Layered part -> one object (one bone)
# ---------------------------------------------------------------------------

def _join(main, others):
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    objs = [main] + list(others)
    for o in objs:
        o.select_set(True)
    vl.objects.active = main
    with bpy.context.temp_override(active_object=main, object=main, selected_objects=objs,
                                   selected_editable_objects=objs):
        bpy.ops.object.join()
    return main


BEVEL_BIG = dict(width=0.018, segments=1, angle=30.0)
BEVEL_MID = dict(width=0.008, segments=1, angle=30.0)
BEVEL_ROUND = dict(width=0.035, segments=1, angle=30.0)


class LPart:
    """Named part assembled from layers that get different bevel/smoothing, joined into one object.

        lp = LPart("torso")
        base = lp.L("base", bevel=BEVEL_BIG)    # big plates
        fine = lp.L("fine")                      # already shaped hardware (bolts, bands)
        riv  = lp.L("riv", angle=180)            # fully smooth (rivets, domes)
        obj = lp.build(parent, loc=pivot)
    """

    def __init__(self, name):
        self.name = name
        self.layers = {}

    def L(self, key, bevel=None, angle=35.0):
        if key not in self.layers:
            self.layers[key] = [Part(f"{self.name}__{key}"), bevel, angle]
        return self.layers[key][0]

    def mirror_x(self):
        """Mirror every layer across local x = 0 (build the left side, mirror for the right)."""
        for p, _, _ in self.layers.values():
            bmesh.ops.scale(p.bm, vec=(-1.0, 1.0, 1.0), verts=p.bm.verts[:])
            bmesh.ops.reverse_faces(p.bm, faces=p.bm.faces[:])
        return self

    def build(self, parent, loc=(0, 0, 0)):
        objs = []
        stats = []
        for key, (p, bev, ang) in self.layers.items():
            if len(p.bm.verts) == 0:
                p.bm.free()
                continue
            o = p.build(parent, loc=loc)
            t0 = hp.obj_tris(o)
            # smooth + sharp-by-angle first, then bevel with hardened normals: a 1-segment chamfer then
            # shades like a rounded edge (flat faces keep their normals, the chamfer blends them)
            hp.smooth_obj(o, ang)
            if bev:
                hp.bevel_obj(o, **bev)
            stats.append(f"{key}:{t0}->{hp.obj_tris(o)}" if bev else f"{key}:{t0}")
            objs.append(o)
        main = objs[0]
        if len(objs) > 1:
            _join(main, objs[1:])
        main.name = self.name
        main.data.name = self.name
        print(f"[part] {self.name:10s} {hp.obj_tris(main):6d} tris   ({', '.join(stats)})")
        return main
