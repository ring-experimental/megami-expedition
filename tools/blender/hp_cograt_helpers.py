"""Geometry helpers for the hi-poly Cog Rat (model_cograt.py). Own module — builds on common.Part
without modifying any shared helper.

Everything is modelled in WORLD coordinates (metres, Z up, model faces -Y) and moved to its pivot by
`build_world` at the end, so pivots / joints can be tweaked without touching the geometry code.

    Profile(keys)                     smooth (Catmull-Rom) interpolation of cross-section params along Y
    grid(p, rings, mat_fn, ...)       quad grid surface between rings (closed in U, optional poles)
    lathe_m(p, prof, seg, M, ...)     surface of revolution with a material per profile span
    frame(origin, axis, up)           4x4 matrix whose local Z = axis (for lathes, gears, rivets)
    rivet(p, mat, pos, nrm, r, ...)   small dome head sunk into a surface
    gear(p, mat, M, r, ...)           chamfer-free gear wheel with optional spokes + hub hole
    capsule(p, mat, a, b, r, ...)     rounded tube segment
    build_world(p, parent, pivot, parent_pivot)
    check_closed(obj)                 report open edges (helps spot missing caps / flipped islands)
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from common import Part, get_mat  # noqa: F401


# ---------------------------------------------------------------------------
# Profiles / interpolation
# ---------------------------------------------------------------------------

def _cr(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)


class Profile:
    """keys: [(s, v0, v1, ...), ...] sorted by s. at(s) -> tuple of interpolated values
    (Catmull-Rom through the keys, clamped at the ends)."""

    def __init__(self, keys):
        self.keys = sorted((tuple(k) for k in keys), key=lambda k: k[0])
        self.s = [k[0] for k in self.keys]

    def at(self, s):
        ks = self.keys
        if s <= self.s[0]:
            return ks[0][1:]
        if s >= self.s[-1]:
            return ks[-1][1:]
        i = 0
        while i < len(ks) - 2 and s > self.s[i + 1]:
            i += 1
        s0, s1 = self.s[i], self.s[i + 1]
        t = (s - s0) / (s1 - s0)
        k0 = ks[max(0, i - 1)]
        k1, k2 = ks[i], ks[i + 1]
        k3 = ks[min(len(ks) - 1, i + 2)]
        return tuple(_cr(k0[j], k1[j], k2[j], k3[j], t) for j in range(1, len(k1)))


def spow(x, e):
    return math.copysign(abs(x) ** e, x)


def super_pt(hw, ht, hb, n=2.0, th=0.0):
    """Point on a superellipse-ish section in the (u=x, v=z) plane. th=0 -> +X, 90deg -> up.
    ht = extent upward, hb = extent downward. n=2 ellipse, n>2 boxier."""
    c, s = math.cos(th), math.sin(th)
    e = 2.0 / n
    u = hw * spow(c, e)
    v = (ht if s >= 0 else hb) * spow(s, e)
    return u, v


# ---------------------------------------------------------------------------
# Frames / transforms
# ---------------------------------------------------------------------------

def frame(origin, axis, up=(0, 0, 1)):
    """Matrix with local Z along `axis`, local Y roughly toward `up`, translation `origin`."""
    z = Vector(axis).normalized()
    upv = Vector(up)
    if abs(z.dot(upv.normalized())) > 0.98:
        upv = Vector((0, 1, 0)) if abs(z.y) < 0.9 else Vector((1, 0, 0))
    x = upv.cross(z).normalized()
    y = z.cross(x).normalized()
    m = Matrix.Identity(4)
    for r in range(3):
        m[r][0], m[r][1], m[r][2] = x[r], y[r], z[r]
        m[r][3] = origin[r]
    return m


# ---------------------------------------------------------------------------
# Surfaces
# ---------------------------------------------------------------------------

def grid(p, rings, mat_fn, close_u=True, start_pole=None, end_pole=None, pole_mat=None):
    """Quad grid between consecutive rings (lists of Vector, same length).
    mat_fn(i, j) -> material for the face between ring i..i+1, column j..j+1.
    start_pole / end_pole: optional Vector closing the surface with a triangle fan."""
    bm = p.bm
    vr = [[bm.verts.new(v) for v in ring] for ring in rings]
    n = len(rings[0])
    ncol = n if close_u else n - 1
    for i in range(len(vr) - 1):
        A, B = vr[i], vr[i + 1]
        for j in range(ncol):
            k = (j + 1) % n
            f = bm.faces.new((A[j], A[k], B[k], B[j]))
            f.material_index = p._mi(mat_fn(i, j))
    if start_pole is not None:
        pv = bm.verts.new(Vector(start_pole))
        for j in range(ncol):
            k = (j + 1) % n
            f = bm.faces.new((pv, vr[0][k], vr[0][j]))
            f.material_index = p._mi(pole_mat or mat_fn(0, j))
    if end_pole is not None:
        pv = bm.verts.new(Vector(end_pole))
        for j in range(ncol):
            k = (j + 1) % n
            f = bm.faces.new((vr[-1][j], vr[-1][k], pv))
            f.material_index = p._mi(pole_mat or mat_fn(len(vr) - 2, j))
    return vr


def lathe_m(p, prof, seg, M=None, phase=None, close_top=True, close_bottom=True):
    """Surface of revolution around local Z of matrix M.
    prof: [(r, z, mat), ...] bottom -> top; `mat` colours the span from this point to the next.
    r == 0 -> pole vertex. Open ends with r > 0 are capped (n-gon) unless close_* is False
    (leave an end open only where it is buried inside another surface — saves the n-gon cap;
    Part.build still orients a shell with one hidden opening correctly)."""
    M = M or Matrix.Identity(4)
    if phase is None:
        phase = math.pi / seg
    bm = p.bm
    rings = []
    for (r, z, _m) in prof:
        if r <= 1e-7:
            rings.append([bm.verts.new(M @ Vector((0, 0, z)))])
        else:
            rings.append([bm.verts.new(M @ Vector((r * math.cos(2 * math.pi * k / seg + phase),
                                                   r * math.sin(2 * math.pi * k / seg + phase), z)))
                          for k in range(seg)])
    for i in range(len(rings) - 1):
        A, B = rings[i], rings[i + 1]
        mi = p._mi(prof[i][2])
        for k in range(seg):
            k2 = (k + 1) % seg
            if len(A) == 1 and len(B) == 1:
                break
            if len(A) == 1:
                f = bm.faces.new((A[0], B[k], B[k2]))
            elif len(B) == 1:
                f = bm.faces.new((A[k], A[k2], B[0]))
            else:
                f = bm.faces.new((A[k], A[k2], B[k2], B[k]))
            f.material_index = mi
    if close_bottom and len(rings[0]) > 2:
        f = bm.faces.new(list(reversed(rings[0])))
        f.material_index = p._mi(prof[0][2])
    if close_top and len(rings[-1]) > 2:
        f = bm.faces.new(rings[-1])
        f.material_index = p._mi(prof[-2][2] if len(prof) > 1 else prof[-1][2])
    return rings


def rivet(p, mat, pos, nrm, r=0.008, h=None, seg=6, sink=None):
    """Dome-headed rivet sitting on a surface at pos with normal nrm (~22 tris at seg=6)."""
    h = r * 0.6 if h is None else h
    sink = r * 0.6 if sink is None else sink
    M = frame(Vector(pos), Vector(nrm))
    lathe_m(p, [(r, -sink, mat), (r * 0.92, h * 0.45, mat), (0.0, h, mat)], seg, M, close_bottom=True)


def capsule(p, mat, a, b, r, r2=None, seg=12, rings=3):
    """Rounded tube from a to b (hemispherical ends). r2: radius at b (tapered)."""
    a, b = Vector(a), Vector(b)
    r2 = r if r2 is None else r2
    d = b - a
    L = d.length
    M = frame(a, d)
    prof = []
    for i in range(rings):                       # bottom hemisphere
        t = (i / rings) * math.pi / 2
        prof.append((r * math.sin(t), -r * math.cos(t), mat))
    prof.append((r, 0.0, mat))
    prof.append((r2, L, mat))
    for i in range(1, rings + 1):                # top hemisphere
        t = (i / rings) * math.pi / 2
        prof.append((r2 * math.cos(t), L + r2 * math.sin(t), mat))
    prof[0] = (0.0, -r, mat)
    return lathe_m(p, prof, seg, M)


def gear(p, mat, M, r, thick, teeth=10, depth=None, hole=0.0, seg_per_tooth=4, tip=0.42, root=0.5,
         spokes=0, spoke_w=None, hub=None, chamfer=0.0, two_sided=False, bottom=True):
    """Gear wheel in the local XY plane of M (axis = local Z), centred on z=0.
    bottom=False leaves the -Z face open (gear lying on a surface: the face is never seen).
    hole>0 : the wheel is a toothed ring with inner radius `hole`; spokes>0 adds that many spokes
    and a hub (radius `hub`) bridging to the centre. chamfer>0 bevels the tooth faces' outer edges
    (adds one ring of verts top & bottom)."""
    depth = r * 0.18 if depth is None else depth
    rr = r - depth
    pitch = 2 * math.pi / teeth
    outline = []
    for i in range(teeth):
        a = pitch * i
        outline += [(rr, a - pitch * root / 2), (r, a - pitch * tip / 2), (r, a + pitch * tip / 2),
                    (rr, a + pitch * root / 2)]
    bm = p.bm
    mi = p._mi(mat)
    hz = thick / 2

    def P(rad, ang, z):
        return M @ Vector((rad * math.cos(ang), rad * math.sin(ang), z))

    n = len(outline)
    if chamfer > 0:
        outer_lo = [bm.verts.new(P(rad, ang, -hz + chamfer)) for (rad, ang) in outline]
        outer_hi = [bm.verts.new(P(rad, ang, hz - chamfer)) for (rad, ang) in outline]
        top = [bm.verts.new(P(rad - chamfer, ang, hz)) for (rad, ang) in outline]
        bot = [bm.verts.new(P(rad - chamfer, ang, -hz)) for (rad, ang) in outline]
        side_rings = [bot, outer_lo, outer_hi, top]
    else:
        top = [bm.verts.new(P(rad, ang, hz)) for (rad, ang) in outline]
        bot = [bm.verts.new(P(rad, ang, -hz)) for (rad, ang) in outline]
        side_rings = [bot, top]
    for A, B in zip(side_rings[:-1], side_rings[1:]):
        for k in range(n):
            k2 = (k + 1) % n
            bm.faces.new((A[k], A[k2], B[k2], B[k])).material_index = mi
    inner_r = hole if hole > 0 else rr * 0.0
    if hole > 0:
        # ring faces between outline and inner circle (one inner vert per outline vert)
        it = [bm.verts.new(P(hole, ang, hz)) for (_, ang) in outline]
        ib = [bm.verts.new(P(hole, ang, -hz)) for (_, ang) in outline]
        for k in range(n):
            k2 = (k + 1) % n
            bm.faces.new((top[k], top[k2], it[k2], it[k])).material_index = mi
            bm.faces.new((bot[k2], bot[k], ib[k], ib[k2])).material_index = mi
            bm.faces.new((it[k], it[k2], ib[k2], ib[k])).material_index = mi
        if spokes:
            sw = spoke_w or hole * 0.35
            hub = hub or hole * 0.35
            for s in range(spokes):
                a = 2 * math.pi * s / spokes + pitch / 2
                L = hole - hub + 0.004
                mid = (hub + hole) / 2
                box_m = M @ Matrix.Rotation(a, 4, "Z") @ Matrix.Translation((mid, 0, 0)) @ \
                    Matrix.Diagonal((L, sw, thick * 0.8, 1.0))
                r_ = bmesh.ops.create_cube(bm, size=1.0, matrix=box_m)
                for f in {f for v in r_["verts"] for f in v.link_faces}:
                    f.material_index = mi
            lathe_m(p, [(0.0, -thick * 0.65, mat), (hub, -thick * 0.65, mat), (hub, thick * 0.7, mat),
                        (0.0, thick * 1.1, mat)], 10, M)
    else:
        # faces: tooth quads + an inner vertex ring (2 per tooth) so no long fan triangles reach the
        # centre (vertex AO / smooth normals would otherwise show a "sunburst")
        ri = rr * 0.55

        def ringed(face_ring, z, flip):
            inner = []
            for t in range(teeth):
                inner.append(bm.verts.new(P(ri, outline[4 * t][1], z)))
                inner.append(bm.verts.new(P(ri, outline[4 * t + 3][1], z)))
            cv = bm.verts.new(P(0, 0, z))
            fl = []
            for t in range(teeth):
                o = [face_ring[(4 * t + q) % n] for q in range(5)]
                i0, i3, i0n = inner[2 * t], inner[2 * t + 1], inner[(2 * t + 2) % (2 * teeth)]
                fl += [(o[0], o[1], o[2], o[3]), (i0, i3, o[3], o[0]), (i3, i0n, o[4], o[3]),
                       (cv, i0, i3), (cv, i3, i0n)]
            for f in fl:
                bm.faces.new(tuple(reversed(f)) if flip else f).material_index = mi
        ringed(top, hz, False)
        if two_sided:
            ringed(bot, -hz, True)
        elif bottom:
            cb = bm.verts.new(P(0, 0, -hz))
            for k in range(n):
                k2 = (k + 1) % n
                bm.faces.new((bot[k2], bot[k], cb)).material_index = mi
    return p


def torus_m(p, mat, M, R, r, seg=24, seg2=8, squash=1.0):
    """Torus in local XY of M (axis local Z). squash scales the tube along local Z."""
    bm = p.bm
    mi = p._mi(mat)
    rings = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        ring = []
        for j in range(seg2):
            b = 2 * math.pi * j / seg2
            d = R + r * math.cos(b)
            ring.append(bm.verts.new(M @ Vector((d * math.cos(a), d * math.sin(a), r * math.sin(b) * squash))))
        rings.append(ring)
    for i in range(seg):
        A, B = rings[i], rings[(i + 1) % seg]
        for j in range(seg2):
            k = (j + 1) % seg2
            bm.faces.new((A[j], B[j], B[k], A[k])).material_index = mi
    return p


def sweep(p, mat, pts, prof, closed_path=False, up=(0, 0, 1), cap=True):
    """Sweep a closed 2D profile [(u, v), ...] along a polyline (u along the side normal,
    v along the 'up'-derived binormal). Profile is scaled by nothing — give it in metres.
    prof may also be a function i -> profile list (per point)."""
    P = [Vector(q) for q in pts]
    n = len(P)
    tang = []
    for i in range(n):
        if closed_path:
            t = (P[(i + 1) % n] - P[i]).normalized() + (P[i] - P[i - 1]).normalized()
        elif i == 0:
            t = P[1] - P[0]
        elif i == n - 1:
            t = P[-1] - P[-2]
        else:
            t = (P[i + 1] - P[i]).normalized() + (P[i] - P[i - 1]).normalized()
        tang.append(t.normalized())
    bm = p.bm
    mi = p._mi(mat)
    rings = []
    upv = Vector(up)
    for i in range(n):
        t = tang[i]
        side = t.cross(upv)
        if side.length < 1e-5:
            side = t.cross(Vector((1, 0, 0)))
        side.normalize()
        b = side.cross(t).normalized()
        pr = prof(i) if callable(prof) else prof
        rings.append([bm.verts.new(P[i] + side * u + b * v) for (u, v) in pr])
    m = len(rings[0])
    segs = n if closed_path else n - 1
    for i in range(segs):
        A, B = rings[i], rings[(i + 1) % n]
        for k in range(m):
            k2 = (k + 1) % m
            bm.faces.new((A[k], A[k2], B[k2], B[k])).material_index = mi
    if cap and not closed_path:
        bm.faces.new(list(reversed(rings[0]))).material_index = mi
        bm.faces.new(rings[-1]).material_index = mi
    return rings


def rounded_rect(w, h, r, n=3):
    """Closed 2D outline (u, v) of a rounded rectangle centred at 0 (counter-clockwise)."""
    r = min(r, w / 2 - 1e-5, h / 2 - 1e-5)
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180),
                       (w / 2 - r, -h / 2 + r, 270)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def tint_skin(skin, fn, attr_name="Col"):
    """Multiply the baked vertex colour of a skinned mesh per corner: fn(co, mat_name, bone) -> factor
    (co in world space = skin space after rig_from_parts; bone = vertex group with the largest weight)."""
    import numpy as np
    me = skin.data
    attr = me.color_attributes[attr_name]
    names = {g.index: g.name for g in skin.vertex_groups}
    vbone = []
    for v in me.vertices:
        best, bw = None, -1.0
        for ge in v.groups:
            if ge.weight > bw:
                best, bw = names.get(ge.group), ge.weight
        vbone.append(best)
    mats = [m.name if m else "" for m in me.materials]
    cols = np.empty(len(me.loops) * 4, dtype=np.float32)
    attr.data.foreach_get("color", cols)
    cols = cols.reshape(-1, 4)
    for poly in me.polygons:
        mn = mats[poly.material_index]
        for li in range(poly.loop_start, poly.loop_start + poly.loop_total):
            vi = me.loops[li].vertex_index
            f = fn(me.vertices[vi].co, mn, vbone[vi])
            if f != 1.0:
                cols[li, :3] *= f
    attr.data.foreach_set("color", np.clip(cols, 0.0, 1.0).ravel())


# ---------------------------------------------------------------------------
# Build / checks
# ---------------------------------------------------------------------------

class SPart(Part):
    """Part with per-primitive smoothing groups:

        with p.soft(65):            # faces created inside get their own auto-smooth angle
            capsule(p, ...)

    build_world() first smooths the whole part by angle (hp_helpers.smooth_obj, base angle) and then
    re-evaluates the edges INSIDE each group with the group's angle — low-segment cylinders, struts,
    tori read round while profile corners (caps, chamfers > angle) stay crisp."""

    def __init__(self, name):
        super().__init__(name)
        self.groups = []

    class _Grp:
        def __init__(self, part, angle):
            self.part, self.angle = part, angle

        def __enter__(self):
            self.before = len(self.part.bm.faces)       # faces are only ever appended while building
            return self

        def __exit__(self, *exc):
            self.part.groups.append((range(self.before, len(self.part.bm.faces)), self.angle))
            return False

    def soft(self, angle=65.0):
        return SPart._Grp(self, angle)


def _apply_groups(obj, groups_idx):
    import numpy as np
    me = obj.data
    if not groups_idx:
        return
    if "sharp_edge" not in me.attributes:
        me.attributes.new("sharp_edge", "BOOLEAN", "EDGE")
    sharp = np.zeros(len(me.edges), dtype=bool)
    me.attributes["sharp_edge"].data.foreach_get("value", sharp)
    ek_idx = {e.key: e.index for e in me.edges}
    adj = {}
    for poly in me.polygons:
        for ek in poly.edge_keys:
            adj.setdefault(ek, []).append(poly.index)
    for fset, ang in groups_idx:
        lim = math.radians(ang)
        for ek, ps in adj.items():
            if len(ps) == 2 and ps[0] in fset and ps[1] in fset:
                n1, n2 = me.polygons[ps[0]].normal, me.polygons[ps[1]].normal
                sharp[ek_idx[ek]] = n1.angle(n2, 0.0) > lim
    me.attributes["sharp_edge"].data.foreach_set("value", sharp)
    me.update()


def build_world(p, parent, pivot, parent_pivot=(0, 0, 0), smooth_angle=34.0):
    """Build a Part modelled in world space with its origin (bone head) at `pivot` (world), then smooth
    it by angle (+ SPart smoothing groups)."""
    import hp_helpers as hp
    off = -Vector(pivot)
    bmesh.ops.translate(p.bm, vec=off, verts=p.bm.verts[:])
    groups_idx = [(set(rng), ang) for rng, ang in getattr(p, "groups", [])]
    obj = p.build(parent, loc=tuple(Vector(pivot) - Vector(parent_pivot)))
    hp.smooth_obj(obj, angle=smooth_angle)
    _apply_groups(obj, groups_idx)
    return obj


def check_closed(obj):
    """Print the number of boundary (open) edges and non-manifold edges of a mesh object."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    open_e = sum(1 for e in bm.edges if e.is_boundary)
    nonman = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
    tris = sum(len(f.verts) - 2 for f in bm.faces)
    bm.free()
    print(f"[check] {obj.name:10s} tris {tris:5d}  open edges {open_e:4d}  non-manifold {nonman}")
    return open_e
