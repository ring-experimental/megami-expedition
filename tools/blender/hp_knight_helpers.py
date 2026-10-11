"""Hi-poly geometry helpers for the Clockwork Knight (model_knight.py only).

Builds on common.py / char_helpers.py / hp_helpers.py WITHOUT modifying them. Everything adds
geometry to a common.Part in the part's LOCAL (pivot-relative) space.

    piece() / merge(p, q, bevel=(w, segs[, angle]))   build a primitive in its own temp Part, bevel
                                                      only that piece, then append it to Part p
    Stack(rows)                                       vertical stack of super-elliptic sections
                                                      (smooth monotone interpolation in z) -> ring()/pt()
    loft_rings(p, mat, rings, band_mats=...)          loft through explicit 3D rings (poles allowed)
    revolve(p, mat, [(r, z), ...], seg, M)            surface of revolution (open, closed or with poles)
    grid_shell(p, mat, G, t, ...)                     thick plate from a grid of surface points
    gear(p, mat, r, teeth, thick, ...)                toothed disc / ring (axis = local Z of M)
    rivet(p, mat, pos, nrm)                           small dome rivet
    fist(...)                                         armoured fist wrapped around a channel axis
    finish_obj(obj, angle)                            smooth by angle + weighted normals
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from common import Part, _mtx
import hp_helpers as hp

TAU = 2 * math.pi


# ---------------------------------------------------------------------------
# Matrices
# ---------------------------------------------------------------------------

def M_(loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    return _mtx(loc, rot, scale)


def frame(pos, nrm, up=(0, 0, 1)):
    """4x4 matrix at pos whose local +Z is nrm (local +Y roughly toward `up`)."""
    n = Vector(nrm).normalized()
    u = Vector(up)
    if abs(n.dot(u.normalized())) > 0.98:
        u = Vector((0, 1, 0)) if abs(n.y) < 0.9 else Vector((1, 0, 0))
    x = u.cross(n).normalized()
    y = n.cross(x).normalized()
    m = Matrix((x, y, n)).transposed().to_4x4()
    m.translation = Vector(pos)
    return m


def basis(x, y, z, pos=(0, 0, 0)):
    """4x4 matrix from explicit axis vectors."""
    m = Matrix((Vector(x), Vector(y), Vector(z))).transposed().to_4x4()
    m.translation = Vector(pos)
    return m


# ---------------------------------------------------------------------------
# Pieces: per-primitive bevel, then merge into the part
# ---------------------------------------------------------------------------

def piece():
    return Part("_pc")


def bevel_bm(bm, width, segs=2, angle=30.0, profile=0.5, outer_only=None):
    """Bevel edges sharper than `angle`. outer_only=None -> automatic: if any face of the piece is tagged
    (grid_shell marks its OUTER surface), only edges touching a tagged face are bevelled (the hidden
    inner rim of a plate costs no triangles)."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    lim = math.radians(angle)
    if outer_only is None:
        outer_only = any(f.tag for f in bm.faces)
    edges = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim
             and (not outer_only or any(f.tag for f in e.link_faces))]
    if not edges:
        return
    bmesh.ops.bevel(bm, geom=edges, offset=width, offset_type="OFFSET", segments=segs, profile=profile,
                    affect="EDGES", clamp_overlap=True, material=-1, miter_outer="SHARP")


def merge(p, q, bevel=None, M=None):
    """Append temp Part q into Part p (materials remapped). bevel=(width, segs[, angle])."""
    if bevel:
        bevel_bm(q.bm, bevel[0], bevel[1], bevel[2] if len(bevel) > 2 else 30.0)
    for f in q.bm.faces:
        f.tag = False
    vmap = {}
    for v in q.bm.verts:
        vmap[v] = p.bm.verts.new((M @ v.co) if M is not None else v.co.copy())
    for f in q.bm.faces:
        try:
            nf = p.bm.faces.new([vmap[v] for v in f.verts])
        except ValueError:
            continue
        nf.material_index = p._mi(q.mat_names[f.material_index])
    q.bm.free()
    return p


def rbox(p, mat, size, loc=(0, 0, 0), rot=(0, 0, 0), r=0.01, segs=2, M=None):
    """Rounded (bevelled) box."""
    q = piece()
    q.box(mat, size=size, loc=loc, rot=rot)
    return merge(p, q, bevel=(r, segs, 30.0), M=M)


# ---------------------------------------------------------------------------
# Curves / interpolation
# ---------------------------------------------------------------------------

def se(a, rx, ry, e=2.0):
    c, s = math.cos(a), math.sin(a)
    return (rx * math.copysign(abs(c) ** (2.0 / e), c), ry * math.copysign(abs(s) ** (2.0 / e), s))


def pchip(xs, ys, x):
    """Monotone cubic interpolation (Fritsch-Carlson). xs ascending."""
    n = len(xs)
    if n == 1:
        return ys[0]
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]
    d = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    m = [0.0] * n
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
        else:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    k = 0
    while k < n - 2 and x > xs[k + 1]:
        k += 1
    t = (x - xs[k]) / h[k]
    t2, t3 = t * t, t * t * t
    return ((2 * t3 - 3 * t2 + 1) * ys[k] + (t3 - 2 * t2 + t) * h[k] * m[k]
            + (-2 * t3 + 3 * t2) * ys[k + 1] + (t3 - t2) * h[k] * m[k + 1])


def lerp(a, b, t):
    return a + (b - a) * t


def smooth01(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def bez(pts, n):
    """Sample a polyline/Bezier-ish smooth curve through control points with Catmull-Rom (n points)."""
    P = [Vector(q) for q in pts]
    out = []
    m = len(P) - 1
    for i in range(n):
        u = i / (n - 1) * m
        k = min(int(u), m - 1)
        t = u - k
        p0 = P[max(k - 1, 0)]
        p1, p2 = P[k], P[k + 1]
        p3 = P[min(k + 2, m)]
        t2, t3 = t * t, t * t * t
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    return out


# ---------------------------------------------------------------------------
# Stack of super-elliptic sections
# ---------------------------------------------------------------------------

class Stack:
    """rows: [(z, w, d[, cy[, keel[, cx]]]), ...] ascending z. w/d = full width (X) / depth (Y),
    cy/cx = section centre offset, keel = forward (-Y) ridge height at the front centre line."""

    def __init__(self, rows, e=2.4, keel_w=0.55, back_keel=False):
        self.zs = [r[0] for r in rows]
        self.cols = [[r[i] if len(r) > i else 0.0 for r in rows] for i in range(1, 6)]
        self.e = e
        self.keel_w = keel_w
        self.back_keel = back_keel

    def at(self, z):
        return [pchip(self.zs, c, z) for c in self.cols]

    def pt(self, a, z, off=0.0, keel_scale=1.0):
        w, d, cy, k, cx = self.at(z)
        x, y = se(a, max(w / 2 + off, 1e-4), max(d / 2 + off, 1e-4), self.e)
        if k:
            da = abs(((a + math.pi / 2 + math.pi) % TAU) - math.pi)   # angular distance to the front
            if da < self.keel_w:
                y -= k * keel_scale * (1 - da / self.keel_w) ** 2
            if self.back_keel:
                db = abs(((a - math.pi / 2 + math.pi) % TAU) - math.pi)
                if db < self.keel_w:
                    y += k * keel_scale * (1 - db / self.keel_w) ** 2
        return Vector((cx + x, cy + y, z))

    def ring(self, z, n, off=0.0, a0=-math.pi / 2):
        return [self.pt(a0 + TAU * i / n, z, off) for i in range(n)]

    def loft(self, p, mat, zs, n, off=0.0, caps=(True, True), band_mats=None, M=None):
        rings = [self.ring(z, n, off) for z in zs]
        if M is not None:
            rings = [[M @ v for v in r] for r in rings]
        return loft_rings(p, mat, rings, caps=caps, band_mats=band_mats)


def front_angle(t, span):
    """Angle on a Stack ring for parameter t in [-1, 1] across +-span radians around the front (-Y).
    t = -1 -> character's right (-X), t = +1 -> left (+X)."""
    return -math.pi / 2 + t * span


def back_angle(t, span):
    """t=-1 -> right (-X) ... t=+1 -> left (+X), around the back (+Y)."""
    return math.pi / 2 - t * span


# ---------------------------------------------------------------------------
# Lofts / revolves
# ---------------------------------------------------------------------------

def loft_rings(p, mat, rings, caps=(True, True), band_mats=None, closed=True):
    """Loft through explicit rings of 3D points (all same length, or length 1 = pole).
    band_mats: {band_index: mat} overrides the material of band k (between ring k and k+1).
    closed=False -> open strips (rings are polylines)."""
    bm = p.bm
    mi = p._mi(mat)
    R = [[bm.verts.new(Vector(v)) for v in ring] for ring in rings]
    for k in range(len(R) - 1):
        A, B = R[k], R[k + 1]
        bmi = p._mi(band_mats[k]) if band_mats and k in band_mats else mi
        if len(A) == 1 and len(B) == 1:
            continue
        n = max(len(A), len(B))
        rng = range(n) if closed else range(n - 1)
        for i in rng:
            j = (i + 1) % n
            if len(A) == 1:
                f = bm.faces.new((A[0], B[i], B[j]))
            elif len(B) == 1:
                f = bm.faces.new((A[i], A[j], B[0]))
            else:
                f = bm.faces.new((A[i], A[j], B[j], B[i]))
            f.material_index = bmi
    if closed:
        if caps[0] and len(R[0]) > 2:
            bm.faces.new(list(reversed(R[0]))).material_index = mi
        if caps[1] and len(R[-1]) > 2:
            bm.faces.new(R[-1]).material_index = mi
    return p


def revolve(p, mat, prof, seg=16, M=None, closed=False, phase=0.0, caps=True, band_mats=None):
    """Surface of revolution of prof [(r, z), ...] around local Z (r <= 1e-5 -> pole).
    closed=True also bridges the last profile point back to the first (torus-like solids)."""
    M = M if M is not None else Matrix.Identity(4)
    rings = []
    for (r, z) in prof:
        if r <= 1e-5:
            rings.append([M @ Vector((0, 0, z))])
        else:
            rings.append([M @ Vector((r * math.cos(TAU * i / seg + phase), r * math.sin(TAU * i / seg + phase), z))
                          for i in range(seg)])
    if closed:
        rings.append(rings[0])
        bm = p.bm
        mi = p._mi(mat)
        R = [[bm.verts.new(v) for v in ring] for ring in rings[:-1]]
        R.append(R[0])
        for k in range(len(R) - 1):
            A, B = R[k], R[k + 1]
            bmi = p._mi(band_mats[k]) if band_mats and k in band_mats else mi
            for i in range(seg):
                j = (i + 1) % seg
                bm.faces.new((A[i], A[j], B[j], B[i])).material_index = bmi
        return p
    return loft_rings(p, mat, rings, caps=(caps, caps), band_mats=band_mats)


def ring_rr(p, mat, R, w, t, seg=24, M=None, rr=0.35, csteps=1):
    """Flat ring (washer / key bow) of mean radius R, radial width w, thickness t (along local Z),
    rounded-rectangle cross-section (corner radius rr * min(w, t))."""
    c = rr * min(w, t)
    hw, ht = w / 2, t / 2
    prof = []
    corners = [(R + hw - c, ht - c, 0), (R - hw + c, ht - c, 90), (R - hw + c, -ht + c, 180), (R + hw - c, -ht + c, 270)]
    for (cx, cz, a0) in corners:
        for s in range(csteps + 1):
            a = math.radians(a0 + 90 * s / csteps)
            prof.append((cx + c * math.cos(a), cz + c * math.sin(a)))
    return revolve(p, mat, prof, seg=seg, M=M, closed=True)


# ---------------------------------------------------------------------------
# Thick plates from a grid of surface points
# ---------------------------------------------------------------------------

def grid_shell(p, mat, G, t, closed_u=False, inward=None, face_mat=None, rim=True, inner=True):
    """G[i][j]: rows i (along v), columns j (along u) of OUTER surface points (Vectors).
    A row of length 1 is a pole (first/last row only, needs closed_u).
    t: thickness (float or f(i, j)); the inner surface is offset toward `inward` (a point, default:
    centroid of G) -> solid closed plate. face_mat(i, j) -> material of cell (i, j) (optional).
    inner=False skips the inner surface (plates lying on a body: only the outer face + rim are visible)."""
    bm = p.bm
    mi = p._mi(mat)
    nr = len(G)
    allp = [v for row in G for v in row]
    cen = Vector(inward) if inward is not None else sum(allp, Vector()) / len(allp)

    def g(i, j):
        row = G[i]
        if len(row) == 1:
            return row[0]
        n = len(row)
        if closed_u:
            return row[j % n]
        return row[max(0, min(n - 1, j))]

    normals = []
    for i in range(nr):
        row = G[i]
        nrow = []
        if len(row) == 1:
            adj = G[1] if i == 0 else G[-2]
            c = sum(adj, Vector()) / len(adj)
            nrow.append((row[0] - c).normalized() if (row[0] - c).length > 1e-6 else Vector((0, 0, 1)))
            normals.append(nrow)
            continue
        n = len(row)
        for j in range(n):
            if closed_u:
                du = g(i, j + 1) - g(i, j - 1)
            else:
                du = g(i, min(j + 1, n - 1)) - g(i, max(j - 1, 0))
            i0, i1 = max(i - 1, 0), min(i + 1, nr - 1)
            a = G[i0][0] if len(G[i0]) == 1 else g(i0, j)
            b = G[i1][0] if len(G[i1]) == 1 else g(i1, j)
            dv = b - a
            nn = du.cross(dv)
            nrow.append(nn.normalized() if nn.length > 1e-9 else Vector((0, 0, 1)))
        normals.append(nrow)
    # orientation: normals should point away from `cen`
    s = 0.0
    for i in range(nr):
        for j, v in enumerate(G[i]):
            s += normals[i][j].dot(v - cen)
    sign = 1.0 if s >= 0 else -1.0

    def th(i, j):
        return t(i, j) if callable(t) else t

    O, I = [], []
    for i in range(nr):
        orow, irow = [], []
        for j, v in enumerate(G[i]):
            orow.append(bm.verts.new(v))
            irow.append(bm.verts.new(v - normals[i][j] * sign * th(i, j)))
        O.append(orow)
        I.append(irow)

    def fm(i, j):
        return p._mi(face_mat(i, j)) if face_mat else mi

    def quad(a, b, c, d, m, outer=False):
        try:
            f = bm.faces.new((a, b, c, d))
            f.material_index = m
            f.tag = outer
        except ValueError:
            pass

    def tri(a, b, c, m, outer=False):
        try:
            f = bm.faces.new((a, b, c))
            f.material_index = m
            f.tag = outer
        except ValueError:
            pass

    for i in range(nr - 1):
        A, B = O[i], O[i + 1]
        Ai, Bi = I[i], I[i + 1]
        n = max(len(A), len(B))
        rng = range(n) if closed_u else range(n - 1)
        for j in rng:
            k = (j + 1) % n
            m = fm(i, j)
            if len(A) == 1:
                tri(A[0], B[j], B[k], m, True)
                if inner:
                    tri(Ai[0], Bi[k], Bi[j], m)
            elif len(B) == 1:
                tri(A[j], A[k], B[0], m, True)
                if inner:
                    tri(Ai[k], Ai[j], Bi[0], m)
            else:
                quad(A[j], A[k], B[k], B[j], m, True)
                if inner:
                    quad(Ai[k], Ai[j], Bi[j], Bi[k], m)
    if rim:
        for i in (0, nr - 1):
            if len(O[i]) == 1:
                continue
            n = len(O[i])
            rng = range(n) if closed_u else range(n - 1)
            for j in rng:
                k = (j + 1) % n
                quad(O[i][j], O[i][k], I[i][k], I[i][j], mi)
        if not closed_u:
            for j in (0, -1):
                for i in range(nr - 1):
                    quad(O[i][j], O[i + 1][j], I[i + 1][j], I[i][j], mi)
    return p


def stack_grid(stack, us, zs_fn, off=0.0, ang_fn=None, extra=None):
    """Grid on a Stack surface. us: parameters (e.g. -1..1), zs_fn(u) -> list of z (same length for
    every u), ang_fn(u) -> angle. extra(u, z, P) -> displaced point (optional)."""
    cols = []
    for u in us:
        a = ang_fn(u)
        col = []
        for z in zs_fn(u):
            P = stack.pt(a, z, off)
            if extra:
                P = extra(u, z, P)
            col.append(P)
        cols.append(col)
    nrow = len(cols[0])
    return [[cols[j][i] for j in range(len(cols))] for i in range(nrow)]


def lin(a, b, n):
    return [a + (b - a) * i / (n - 1) for i in range(n)]


# ---------------------------------------------------------------------------
# Small parts
# ---------------------------------------------------------------------------

def rivet(p, mat, pos, nrm, r=0.011, h=0.007, seg=5):
    M = frame(pos, nrm)
    revolve(p, mat, [(r, -0.003), (r * 0.8, h * 0.55), (0, h)], seg=seg, M=M, caps=False)
    return p


def gear(p, mat, r, teeth, thick, depth=None, hole=0.0, tip=0.42, root=0.58, M=None, bevel=None,
         hub=None, hub_mat=None, spokes=0, spoke_w=None, web=None, back=True, arc=None, two_sided=False,
         inner_wall=True):
    """Toothed disc in local XY (axis Z) centred at z=0 (transformed by M).
    hole > 0 -> ring with a central hole of that radius (optional spokes / hub / thin web).
    bevel=(w, segs) chamfers the teeth (costs tris). back=False: no -Z face / inner wall (gear mounted
    on a surface). arc=(a0, a1) radians: only the teeth whose centre lies in the arc (open sector,
    closed with end faces) -> e.g. a half gear crest."""
    M = M if M is not None else Matrix.Identity(4)
    depth = r * 0.16 if depth is None else depth
    rr = r - depth
    ri = hole if hole > 0 else rr * 0.55
    pitch = TAU / teeth
    outline = []
    idx = range(teeth)
    if arc is not None:
        idx = [i for i in range(teeth) if arc[0] <= pitch * i <= arc[1]]
    for i in idx:
        a = pitch * i
        for (rad, da) in ((rr, -root / 2), (r, -tip / 2), (r, tip / 2), (rr, root / 2)):
            outline.append((rad, a + da * pitch))
    if arc is not None:
        a_s, a_e = outline[0][1] - (1 - root) * pitch / 2, outline[-1][1] + (1 - root) * pitch / 2
        outline = [(rr, a_s)] + outline + [(rr, a_e)]
    q = piece()
    bm = q.bm
    mi = q._mi(mat)
    ht = thick / 2
    Ot = [bm.verts.new(M @ Vector((rad * math.cos(a), rad * math.sin(a), ht))) for rad, a in outline]
    Ob = [bm.verts.new(M @ Vector((rad * math.cos(a), rad * math.sin(a), -ht))) for rad, a in outline]
    It = [bm.verts.new(M @ Vector((ri * math.cos(a), ri * math.sin(a), ht))) for _, a in outline]
    Ib = [bm.verts.new(M @ Vector((ri * math.cos(a), ri * math.sin(a), -ht))) for _, a in outline]
    n = len(outline)
    closed = arc is None
    rng = range(n) if closed else range(n - 1)

    def F(vs, outer=True):
        f = bm.faces.new(vs)
        f.material_index = mi
        f.tag = outer
    # only the +Z (front) faces are tagged -> a bevel rounds the front edges only
    for k in rng:
        l = (k + 1) % n
        F((Ot[k], Ot[l], It[l], It[k]))
        if back:
            F((Ob[l], Ob[k], Ib[k], Ib[l]), outer=two_sided)
        F((Ob[k], Ob[l], Ot[l], Ot[k]), outer=False)
        if hole > 0 and inner_wall and (back or not closed):
            F((Ib[l], Ib[k], It[k], It[l]), outer=False)
    if not closed:
        F((It[0], Ot[0], Ob[0], Ib[0]), outer=False)
        F((Ot[-1], It[-1], Ib[-1], Ob[-1]), outer=False)
    elif hole <= 0:
        F(It)
        if back:
            F(list(reversed(Ib)), outer=False)
    merge(p, q, bevel=bevel)
    hm = hub_mat or mat
    if hole > 0 and spokes:
        sw = spoke_w or ri * 0.35
        for s in range(spokes):
            a = TAU * s / spokes + pitch / 2
            q = piece()
            q.box(mat, size=(ri * 1.05, sw, thick * 0.7), loc=(ri * 0.5 * math.cos(a), ri * 0.5 * math.sin(a), 0),
                  rot=(0, 0, math.degrees(a)))
            merge(p, q, M=M)
    if hole > 0 and web:
        revolve(p, mat, [(0, -web / 2), (ri * 1.02, -web / 2), (ri * 1.02, web / 2), (0, web / 2)],
                seg=max(12, teeth * 2), M=M)
    if hub:
        hr, hh = hub
        revolve(p, hm, [(0, -hh / 2), (hr, -hh / 2), (hr, hh / 2 - hr * 0.25), (hr * 0.7, hh / 2), (0, hh / 2)],
                seg=10, M=M)
    return p


def tube_pts(p, mat, pts, r, seg=6, cap=True, flat=1.0, up=(0, 0, 1)):
    """char_helpers.tube equivalent that accepts Vectors and per-point radius lists."""
    from char_helpers import tube
    return tube(p, mat, [tuple(v) for v in pts], r, seg=seg, cap=cap, flat=flat, up=up)


def edge_roll(p, mat, pts, r=0.008, seg=6, closed=False):
    """Rolled armour edge: a thin tube along points (closed loop optional)."""
    P = [Vector(v) for v in pts]
    if closed:
        P = P + [P[0], P[1]]
    from char_helpers import tube
    if closed:
        # tube with overlapping ends (cheap way to close the loop)
        return tube(p, mat, [tuple(v) for v in P[:-1]], r, seg=seg, cap=False)
    return tube(p, mat, [tuple(v) for v in P], r, seg=seg, cap=True)


def fist(p, mat_f, mat_k, S, axis, open_dir, r_in=0.03, fw=0.024, spread=0.030, n_f=4, arc=(-140, 150),
         knuckles=True, seg=6, flat=0.62, steps=6):
    """Armoured fist: n_f finger segments stacked along `axis` (index first, at +axis end), each a
    C-shaped tube wrapping around the channel line through S (inner radius r_in). The C is open toward
    `open_dir` (the palm / hand-back side). arc = start/end angle (deg) measured from open_dir around
    axis. Finger cross-sections are flattened along the axis (flat) so neighbouring fingers stay
    separate (grooves between them). Adds a knuckle plate (mat_k) on the first knuckle of each finger."""
    ax = Vector(axis).normalized()
    od = Vector(open_dir)
    od = (od - ax * od.dot(ax)).normalized()
    side = ax.cross(od)
    rc = r_in + fw
    for f in range(n_f):
        off = ((n_f - 1) / 2 - f) * spread
        c = Vector(S) + ax * off
        pts = []
        for s in range(steps):
            a = math.radians(arc[0] + (arc[1] - arc[0]) * s / (steps - 1))
            pts.append(c + (od * math.cos(a) + side * math.sin(a)) * rc)
        w = fw * (0.9 if f == n_f - 1 else 1.0)
        tube_pts(p, mat_f, pts, [w * 0.9] + [w] * (steps - 2) + [w * 0.8], seg=seg, flat=flat, up=tuple(ax))
        if knuckles:
            a = math.radians(arc[0] + (arc[1] - arc[0]) * 0.2)
            kd = (od * math.cos(a) + side * math.sin(a))
            kp = c + kd * (rc + fw * 0.75)
            q = piece()
            q.box(mat_k, size=(spread * 0.85, fw * 1.5, fw * 0.55))
            merge(p, q, M=basis(ax, kd.cross(ax), kd, kp))
    return p


# ---------------------------------------------------------------------------
# Finishing
# ---------------------------------------------------------------------------

def finish_obj(obj, angle=40.0, wn=True):
    """Smooth shading + sharp edges by angle, then weighted normals (flat faces stay flat)."""
    hp.smooth_obj(obj, angle=angle)
    if wn and obj.type == "MESH" and len(obj.data.polygons):
        m = obj.modifiers.new("hp_wn", "WEIGHTED_NORMAL")
        m.weight = 50
        m.keep_sharp = True
        m.mode = "FACE_AREA"
        hp.apply_modifiers(obj)
    return obj


def mirror_x(pts):
    return [Vector((-v.x, v.y, v.z)) for v in pts]
