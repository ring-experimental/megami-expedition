"""Geometry / finishing helpers for props_small.py (hi-poly small interactables).

Everything here adds geometry straight into a common.Part's bmesh (like env_helpers) or post-
processes finished objects. Only used by props_small.py — shared helper modules stay untouched.

    Kit         : several Parts per prop grouped by *finish class* (bevel width, smoothing) that are
                  finished individually and joined into ONE mesh object at the end (fewer nodes and
                  draw calls in props.glb).
    grid_box    : closed box whose faces are subdivided (AO resolution, grain streaks)
    revolve     : (r, z) profile revolved around local Z — open or closed cross-section, partial
                  arcs, per-angle radius modulation (flutes / gadroons)
    sweep_band  : flat rectangular strap swept along a path lying on a surface (chest straps, trims)
    prism / ring_prism / gear : extruded 2D outlines (sign boards, plates, rune glyphs, gears)
    rivet       : small dome head oriented along a surface normal
    tint_islands: per-island colour variation multiplied into the baked AO ('Col') — plank/stave
                  variation, grain streaks
"""
import math
import random

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

from common import Part, get_mat
from env_helpers import set_mat
import hp_helpers as hp

I4 = Matrix.Identity(4)
VERBOSE = bool(__import__("os").environ.get("SML_VERBOSE"))


# ---------------------------------------------------------------------------
# matrices
# ---------------------------------------------------------------------------

def T(x=0.0, y=0.0, z=0.0):
    return Matrix.Translation(Vector((x, y, z)))


def R(axis, deg):
    return Matrix.Rotation(math.radians(deg), 4, axis)


def S(sx, sy=None, sz=None):
    sy = sx if sy is None else sy
    sz = sx if sz is None else sz
    return Matrix.Diagonal(Vector((sx, sy, sz, 1.0)))


def frame(loc, normal, spin=0.0, up=None):
    """Matrix whose local +Z points along `normal` at `loc` (spin: degrees around the normal).
    up: optional world hint for local +Y (keeps glyphs/plates upright)."""
    n = Vector(normal).normalized()
    if up is not None:
        y = Vector(up)
        y = (y - n * y.dot(n))
        if y.length < 1e-6:
            y = n.orthogonal()
        y.normalize()
        x = y.cross(n)
        M3 = Matrix((x, y, n)).transposed()
        Mr = M3.to_4x4()
    else:
        Mr = Vector((0, 0, 1)).rotation_difference(n).to_matrix().to_4x4()
    return T(*loc) @ Mr @ R("Z", spin)


# ---------------------------------------------------------------------------
# primitives
# ---------------------------------------------------------------------------

def grid_box(part, mat, size, divs=(1, 1, 1), M=I4, skip=()):
    """Closed box centred on the origin (then transformed by M); each face is a grid of
    divs = (nx, ny, nz) cells. skip: faces to omit ('-z', '+y', ...) for hidden sides."""
    sx, sy, sz = size
    return param_box(part, mat, lambda u, v, w: M @ Vector((sx * (u - 0.5), sy * (v - 0.5), sz * (w - 0.5))),
                     divs, skip)


def param_box(part, mat, fn, divs=(1, 1, 1), skip=()):
    """Topological box (closed, faces gridded by divs) whose lattice point (u, v, w) in [0, 1]^3 is
    placed at fn(u, v, w) -> Vector. Curved planks, wedge-shaped stone blocks, staves ...
    Face orientation is fixed later by Part.build (recalc normals), so fn may mirror freely."""
    nx, ny, nz = divs
    bm = part.bm
    V = {}

    def v(i, j, k):
        key = (i, j, k)
        if key not in V:
            V[key] = bm.verts.new(Vector(fn(i / nx, j / ny, k / nz)))
        return V[key]

    faces = []
    for i, tag in ((0, "-x"), (nx, "+x")):
        if tag in skip:
            continue
        for j in range(ny):
            for k in range(nz):
                q = [v(i, j, k), v(i, j + 1, k), v(i, j + 1, k + 1), v(i, j, k + 1)]
                faces.append(bm.faces.new(q[::-1] if i == 0 else q))
    for j, tag in ((0, "-y"), (ny, "+y")):
        if tag in skip:
            continue
        for i in range(nx):
            for k in range(nz):
                q = [v(i, j, k), v(i + 1, j, k), v(i + 1, j, k + 1), v(i, j, k + 1)]
                faces.append(bm.faces.new(q if j == 0 else q[::-1]))
    for k, tag in ((0, "-z"), (nz, "+z")):
        if tag in skip:
            continue
        for i in range(nx):
            for j in range(ny):
                q = [v(i, j, k), v(i + 1, j, k), v(i + 1, j + 1, k), v(i, j + 1, k)]
                faces.append(bm.faces.new(q if k == nz else q[::-1]))
    set_mat(part, faces, mat)
    return faces


def box(part, mat, size, loc=(0, 0, 0), M=I4, divs=(1, 1, 1), skip=()):
    return grid_box(part, mat, size, divs, M @ T(*loc), skip)


def revolve(part, mat, prof, seg=24, closed=False, cap0=False, cap1=False, M=I4, phase=0.0,
            arc=None, rfn=None, zfn=None):
    """Revolve a (r, z) profile around local Z.
    closed : the profile is a closed cross-section (last point connects back to the first)
    cap0/1 : fill the first / last ring with an n-gon (open profiles)
    arc    : (a0, a1) degrees -> partial revolve (open ends are NOT capped)
    rfn(theta, r, z) -> r'  /  zfn(theta, r, z) -> z' : per-angle modulation (flutes, gadroons, waves).
    r == 0 makes a pole vertex. Returns the list of rings (one list of verts per profile point)."""
    bm = part.bm
    full = arc is None
    if full:
        angs = [2 * math.pi * j / seg + phase for j in range(seg)]
    else:
        a0, a1 = math.radians(arc[0]), math.radians(arc[1])
        angs = [a0 + (a1 - a0) * j / seg for j in range(seg + 1)]
    rings = []
    for (r, z) in prof:
        if r <= 1e-7:
            rings.append([bm.verts.new(M @ Vector((0, 0, z)))])
            continue
        ring = []
        for a in angs:
            rr = rfn(a, r, z) if rfn else r
            zz = zfn(a, r, z) if zfn else z
            ring.append(bm.verts.new(M @ Vector((rr * math.cos(a), rr * math.sin(a), zz))))
        rings.append(ring)
    faces = []
    n = len(rings)
    nseg = len(angs) if full else len(angs) - 1
    pairs = [(i, i + 1) for i in range(n - 1)]
    if closed:
        pairs.append((n - 1, 0))
    for (ia, ib) in pairs:
        a, b = rings[ia], rings[ib]
        for j in range(nseg):
            k = (j + 1) % len(angs)
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                faces.append(bm.faces.new((a[0], b[k], b[j])))
            elif len(b) == 1:
                faces.append(bm.faces.new((a[j], a[k], b[0])))
            else:
                faces.append(bm.faces.new((a[j], a[k], b[k], b[j])))
    if full:
        if cap0 and len(rings[0]) > 2:
            faces.append(bm.faces.new(list(reversed(rings[0]))))
        if cap1 and len(rings[-1]) > 2:
            faces.append(bm.faces.new(rings[-1]))
    set_mat(part, faces, mat)
    return rings


def sweep_band(part, mat, pts, ups, w, t, M=I4, cap=True, base=0.0, w_end=None):
    """Rectangular strap along a path. pts: centre line ON the surface, ups: outward surface
    normals per point. The strap spans [base, base + t] along up and w across (side = tangent x up).
    w_end: optional end width (linear taper)."""
    bm = part.bm
    pts = [Vector(p) for p in pts]
    n = len(pts)
    rings = []
    for i in range(n):
        if i == 0:
            tan = pts[1] - pts[0]
        elif i == n - 1:
            tan = pts[-1] - pts[-2]
        else:
            tan = pts[i + 1] - pts[i - 1]
        tan.normalize()
        up = Vector(ups[i])
        up = (up - tan * up.dot(tan)).normalized()
        side = tan.cross(up).normalized()
        ww = w if w_end is None else w + (w_end - w) * i / (n - 1)
        c0 = pts[i] + up * base
        c1 = pts[i] + up * (base + t)
        ring = [c0 - side * ww / 2, c0 + side * ww / 2, c1 + side * ww / 2, c1 - side * ww / 2]
        rings.append([bm.verts.new(M @ p) for p in ring])
    faces = []
    for i in range(n - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(4):
            k = (j + 1) % 4
            faces.append(bm.faces.new((a[j], b[j], b[k], a[k])))
    if cap:
        faces.append(bm.faces.new(rings[0]))
        faces.append(bm.faces.new(list(reversed(rings[-1]))))
    set_mat(part, faces, mat)
    return faces


def prism(part, mat, pts2d, z0, z1, M=I4, side_mat=None, fan=False, center=(0.0, 0.0)):
    """Extrude a 2D outline (x, y; any winding) from z0 to z1 along local Z, transformed by M.
    fan=True: caps as a triangle fan around `center` (for star-shaped concave outlines: gears)."""
    bm = part.bm
    a = [bm.verts.new(M @ Vector((x, y, z0))) for x, y in pts2d]
    b = [bm.verts.new(M @ Vector((x, y, z1))) for x, y in pts2d]
    n = len(pts2d)
    caps, sides = [], []
    if fan:
        ca = bm.verts.new(M @ Vector((center[0], center[1], z0)))
        cb = bm.verts.new(M @ Vector((center[0], center[1], z1)))
        for i in range(n):
            k = (i + 1) % n
            caps.append(bm.faces.new((a[k], a[i], ca)))
            caps.append(bm.faces.new((b[i], b[k], cb)))
    else:
        caps.append(bm.faces.new(a))
        caps.append(bm.faces.new(list(reversed(b))))
    for i in range(n):
        k = (i + 1) % n
        sides.append(bm.faces.new((a[i], a[k], b[k], b[i])))
    set_mat(part, caps, mat)
    set_mat(part, sides, side_mat or mat)
    return caps + sides


def ring_prism(part, mat, outer, inner, z0, z1, M=I4, side_mat=None):
    """Extruded ring between two closed 2D loops with the same vertex count (frames, washers)."""
    bm = part.bm
    n = len(outer)
    assert len(inner) == n
    oa = [bm.verts.new(M @ Vector((x, y, z0))) for x, y in outer]
    ob = [bm.verts.new(M @ Vector((x, y, z1))) for x, y in outer]
    ia = [bm.verts.new(M @ Vector((x, y, z0))) for x, y in inner]
    ib = [bm.verts.new(M @ Vector((x, y, z1))) for x, y in inner]
    caps, sides = [], []
    for i in range(n):
        k = (i + 1) % n
        caps.append(bm.faces.new((ob[i], ob[k], ib[k], ib[i])))
        caps.append(bm.faces.new((oa[k], oa[i], ia[i], ia[k])))
        sides.append(bm.faces.new((oa[i], oa[k], ob[k], ob[i])))
        sides.append(bm.faces.new((ia[k], ia[i], ib[i], ib[k])))
    set_mat(part, caps, mat)
    set_mat(part, sides, side_mat or mat)
    return caps + sides


def loft(part, mat, loops, close_profile=False, cap_first=False, cap_last=False, M=I4, mats=None):
    """Connect closed point rings (same vertex count, 3D) ring i -> i+1 with quads (and last -> first
    when close_profile). cap_first / cap_last fill the end rings with n-gons. mats: per-band list."""
    bm = part.bm
    rings = [[bm.verts.new(M @ Vector(p)) for p in L] for L in loops]
    n = len(rings[0])
    pairs = [(i, i + 1) for i in range(len(rings) - 1)]
    if close_profile:
        pairs.append((len(rings) - 1, 0))
    out = []
    for bi, (ia, ib) in enumerate(pairs):
        a, b = rings[ia], rings[ib]
        fs = [bm.faces.new((a[j], a[(j + 1) % n], b[(j + 1) % n], b[j])) for j in range(n)]
        set_mat(part, fs, mats[bi] if mats else mat)
        out += fs
    caps = []
    if cap_first:
        caps.append(bm.faces.new(list(reversed(rings[0]))))
    if cap_last:
        caps.append(bm.faces.new(rings[-1]))
    if caps:
        set_mat(part, caps, mat)
    return out + caps


def fillet_poly(pts, r, steps=2, mask=None):
    """Round the corners of a 2D polygon (any winding). r: radius (number or per-vertex list),
    mask: per-vertex bool (False = keep sharp). Each rounded corner becomes steps+1 points."""
    n = len(pts)
    out = []
    for i in range(n):
        rr = r[i] if isinstance(r, (list, tuple)) else r
        if (mask is not None and not mask[i]) or rr <= 0:
            out.append(tuple(pts[i]))
            continue
        P = Vector(pts[i])
        A = Vector(pts[i - 1])
        B = Vector(pts[(i + 1) % n])
        e1 = (A - P)
        e2 = (B - P)
        l1, l2 = e1.length, e2.length
        e1.normalize()
        e2.normalize()
        ang = e1.angle(e2, 0.0)
        if ang < 1e-3 or ang > math.pi - 1e-3:
            out.append(tuple(pts[i]))
            continue
        half = ang / 2
        d = min(rr / math.tan(half), l1 * 0.49, l2 * 0.49)
        rr = d * math.tan(half)
        bis = (e1 + e2).normalized()
        C = P + bis * (rr / math.sin(half))
        T1 = P + e1 * d
        T2 = P + e2 * d
        v1, v2 = T1 - C, T2 - C
        a1 = math.atan2(v1.y, v1.x)
        a2 = math.atan2(v2.y, v2.x)
        da = a2 - a1
        while da > math.pi:
            da -= 2 * math.pi
        while da < -math.pi:
            da += 2 * math.pi
        for k in range(steps + 1):
            a = a1 + da * k / steps
            out.append((C.x + rr * math.cos(a), C.y + rr * math.sin(a)))
    return out


def plate(part, mat, outline, t, bev=0.003, steps=2, M=I4, bottom=True, z0=0.0):
    """Extruded 2D outline from z0 to z0 + t (local Z, then M) whose TOP edge is rounded with radius
    `bev` in `steps` segments (sides + top stay clean; cheap 'bevelled plate')."""
    outline = polygon_ccw([tuple(p) for p in outline])
    loops = [[(x, y, z0) for x, y in outline]]
    if bev > 0:
        loops.append([(x, y, z0 + t - bev) for x, y in outline])
        for k in range(1, steps + 1):
            a = (math.pi / 2) * k / steps
            off = bev * (1 - math.cos(a))
            zz = z0 + t - bev + bev * math.sin(a)
            loops.append([(x, y, zz) for x, y in offset_poly(outline, off)])
    else:
        loops.append([(x, y, z0 + t) for x, y in outline])
    return loft(part, mat, loops, cap_first=bottom, cap_last=True, M=M)


def slab(part, mat, outline, t, bev=0.004, steps=2, M=I4, z0=0.0, side_mat=None):
    """Board from z0 to z0 + t with BOTH faces' edges rounded (signs, boards seen from both sides)."""
    outline = polygon_ccw([tuple(p) for p in outline])
    loops = []
    for k in range(steps, 0, -1):
        a = (math.pi / 2) * k / steps
        loops.append([(x, y, z0 + bev - bev * math.sin(a)) for x, y in offset_poly(outline, bev * (1 - math.cos(a)))])
    loops.append([(x, y, z0 + bev) for x, y in outline])
    loops.append([(x, y, z0 + t - bev) for x, y in outline])
    for k in range(1, steps + 1):
        a = (math.pi / 2) * k / steps
        loops.append([(x, y, z0 + t - bev + bev * math.sin(a)) for x, y in offset_poly(outline, bev * (1 - math.cos(a)))])
    return loft(part, mat, loops, cap_first=True, cap_last=True, M=M)


def ring_plate(part, mat, outer, inner, z0, z1, bev=0.003, steps=2, M=I4, bev_inner=None):
    """Frame between two closed loops (same count, both CCW) from z0 to z1 with rounded top edges."""
    outer = polygon_ccw([tuple(p) for p in outer])
    inner = polygon_ccw([tuple(p) for p in inner])
    bi = bev if bev_inner is None else bev_inner
    loops = [[(x, y, z0) for x, y in outer]]
    if bev > 0:
        loops.append([(x, y, z1 - bev) for x, y in outer])
        for k in range(1, steps + 1):
            a = (math.pi / 2) * k / steps
            loops.append([(x, y, z1 - bev + bev * math.sin(a)) for x, y in offset_poly(outer, bev * (1 - math.cos(a)))])
    else:
        loops.append([(x, y, z1) for x, y in outer])
    if bi > 0:
        for k in range(steps, 0, -1):
            a = (math.pi / 2) * k / steps
            loops.append([(x, y, z1 - bi + bi * math.sin(a)) for x, y in offset_poly(inner, -bi * (1 - math.cos(a)))])
        loops.append([(x, y, z1 - bi) for x, y in inner])
    else:
        loops.append([(x, y, z1) for x, y in inner])
    loops.append([(x, y, z0) for x, y in inner])
    return loft(part, mat, loops, close_profile=True, M=M)


def sweep_profile(part, mat, pts, ups, prof, M=I4, caps=True, scale=None):
    """Sweep a closed 2D cross-section prof = [(s, u)] along a path. At each path point the frame is
    tangent / up (= ups[i], made perpendicular) / side = tangent x up; u runs along up, s along side.
    scale: optional per-point factor for the profile."""
    P = [Vector(p) for p in pts]
    n = len(P)
    rings = []
    for i in range(n):
        if i == 0:
            tan = P[1] - P[0]
        elif i == n - 1:
            tan = P[-1] - P[-2]
        else:
            tan = P[i + 1] - P[i - 1]
        tan.normalize()
        up = Vector(ups[i])
        up = (up - tan * up.dot(tan)).normalized()
        side = tan.cross(up).normalized()
        k = scale[i] if scale else 1.0
        rings.append([P[i] + side * (s * k) + up * (u * k) for (s, u) in prof])
    return loft(part, mat, rings, cap_first=caps, cap_last=caps, M=M)


def round_rect(w, h, r, steps=2, corners=(0, 0, 1, 1), u0=0.0):
    """Rectangle profile s in [-w/2, w/2], u in [u0, u0 + h] (CCW: bl, br, tr, tl); corners flags
    select which corners get a radius-r fillet (default: the two 'top' ones = outward side)."""
    pts = [(-w / 2, u0), (w / 2, u0), (w / 2, u0 + h), (-w / 2, u0 + h)]
    return fillet_poly(pts, r, steps, mask=[bool(c) for c in corners])


def plank_prof(w, h, r, grooves=(), steps=2):
    """Plank cross-section (like round_rect: s across [-w/2, w/2], u = thickness [0, h], outer = u=h)
    with rounded outer corners and V 'grain' grooves [(s, width, depth), ...] cut into the outer face."""
    pts = [(-w / 2, 0.0), (w / 2, 0.0), (w / 2, h)]
    mask = [False, False, True]
    for (s, gw, gd) in sorted(grooves, key=lambda g: -g[0]):
        pts += [(s + gw / 2, h), (s, h - gd), (s - gw / 2, h)]
        mask += [False, False, False]
    pts.append((-w / 2, h))
    mask.append(True)
    return fillet_poly(pts, r, steps, mask=mask)


def facet_gem(part, rings, M=I4, mats=("glow_cyan",), light=(-0.45, -0.55, 0.7), cuts=(0.3, -0.25), nseg=8):
    """Cut gem around local Z: rings = [(r, z, phase_deg), ...] bottom -> top (r == 0 -> pole).
    Rings with different phase are joined by zig-zag triangles (crown / pavilion facets).
    Faces are shaded by baked facet orientation: mats = (bright, mid, deep) chosen by
    dot(normal, light) > cuts[0] / < cuts[1] - emissive gems still read as faceted (and sparkle
    when spun)."""
    bm = part.bm
    L = Vector(light).normalized()
    rings_v = []
    for (r, z, ph) in rings:
        if r <= 1e-7:
            rings_v.append([bm.verts.new(M @ Vector((0, 0, z)))])
            continue
        a0 = math.radians(ph)
        rings_v.append([bm.verts.new(M @ Vector((r * math.cos(a0 + 2 * math.pi * j / nseg),
                                                  r * math.sin(a0 + 2 * math.pi * j / nseg), z)))
                        for j in range(nseg)])
    faces = []
    for i in range(len(rings_v) - 1):
        a, b = rings_v[i], rings_v[i + 1]
        if len(a) == 1:
            faces += [bm.faces.new((a[0], b[(j + 1) % nseg], b[j])) for j in range(nseg)]
        elif len(b) == 1:
            faces += [bm.faces.new((a[j], a[(j + 1) % nseg], b[0])) for j in range(nseg)]
        elif abs(rings[i][2] - rings[i + 1][2]) < 1e-6:
            faces += [bm.faces.new((a[j], a[(j + 1) % nseg], b[(j + 1) % nseg], b[j])) for j in range(nseg)]
        else:
            # rings rotated against each other: zig-zag (b[j + sh] lies between a[j] and a[j + 1])
            sh_ = 0 if rings[i + 1][2] > rings[i][2] else 1
            for j in range(nseg):
                k = (j + 1) % nseg
                bj, bk = b[(j + sh_) % nseg], b[(j + 1 + sh_) % nseg]
                faces.append(bm.faces.new((a[j], a[k], bj)))
                faces.append(bm.faces.new((bj, a[k], bk)))
    centre = M @ Vector((0, 0, (rings[0][1] + rings[-1][1]) / 2))
    Mi = M.to_3x3()
    for f in faces:
        f.normal_update()
        nrm = f.normal.copy()
        if nrm.dot(f.calc_center_median() - centre) < 0:
            nrm = -nrm
        # classify in the gem's own frame (so the pattern spins with the crystal)
        nl = (Mi.inverted_safe() @ nrm).normalized()
        d = nl.dot(L)
        m = mats[0] if (len(mats) == 1 or d > cuts[0]) else (mats[2] if (len(mats) > 2 and d < cuts[1]) else mats[1])
        set_mat(part, [f], m)
    return faces


def ribbon(part, mat, pts, normals, w, M=I4):
    """Flat strip (single-sided, faces along `normals`) of width w along a path — glowing inlays.
    Use in a Part built with recalc=False."""
    bm = part.bm
    P = [M @ Vector(p) for p in pts]
    N = [(M.to_3x3() @ Vector(nv)).normalized() for nv in normals]
    L, Rr = [], []
    for i in range(len(P)):
        t = (P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]).normalized()
        side = t.cross(N[i]).normalized()
        L.append(bm.verts.new(P[i] - side * w / 2))
        Rr.append(bm.verts.new(P[i] + side * w / 2))
    faces = [bm.faces.new((L[i], Rr[i], Rr[i + 1], L[i + 1])) for i in range(len(P) - 1)]
    set_mat(part, faces, mat)
    return faces


def catmull(pts, sub=3):
    """Catmull-Rom resample of a polyline (passes through every input point; sub samples per span)."""
    P = [Vector(p) for p in pts]
    n = len(P)
    out = []
    for i in range(n - 1):
        p0 = P[i - 1] if i > 0 else P[i] * 2 - P[i + 1]
        p1, p2 = P[i], P[i + 1]
        p3 = P[i + 2] if i + 2 < n else P[i + 1] * 2 - P[i]
        for k in range(sub):
            t = k / sub
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-1])
    return out


def circle2d(r, n, phase=0.0, cx=0.0, cy=0.0, sx=1.0, sy=1.0):
    return [(cx + r * sx * math.cos(2 * math.pi * i / n + phase), cy + r * sy * math.sin(2 * math.pi * i / n + phase))
            for i in range(n)]


def offset_poly(pts, d):
    """Inset a simple CCW polygon by d (negative d = outset); mitred corners (line intersections)."""
    n = len(pts)
    lines = []
    for i in range(n):
        p0 = Vector(pts[i])
        p1 = Vector(pts[(i + 1) % n])
        e = (p1 - p0).normalized()
        nrm = Vector((-e.y, e.x))   # inward for CCW
        lines.append((p0 + nrm * d, e))
    out = []
    for i in range(n):
        (pa, ea), (pb, eb) = lines[i - 1], lines[i]
        den = ea.x * eb.y - ea.y * eb.x
        if abs(den) < 1e-9:
            out.append(tuple(pb))
            continue
        t = ((pb.x - pa.x) * eb.y - (pb.y - pa.y) * eb.x) / den
        q = pa + ea * t
        out.append((q.x, q.y))
    return out


def polygon_ccw(pts):
    a = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
            for i in range(len(pts)))
    return pts if a > 0 else pts[::-1]


def gear_outline(r_root, r_tip, teeth, top=0.42, bottom=0.6, phase=0.0):
    """2D gear outline (CCW): trapezoid teeth. top/bottom = tooth width fraction at tip / root."""
    pts = []
    step = 2 * math.pi / teeth
    for i in range(teeth):
        a = i * step + phase
        for (f, r) in ((-bottom / 2, r_root), (-top / 2, r_tip), (top / 2, r_tip), (bottom / 2, r_root)):
            pts.append((r * math.cos(a + f * step), r * math.sin(a + f * step)))
    return pts


def gear(part, mat, r, teeth, depth, tooth=None, hole=0.0, M=I4, hub=None, spokes=0, spoke_w=None,
         rim=None, phase=0.0):
    """Gear in local XY (axis Z) from z = -depth/2 .. depth/2.
    hole > 0: open centre (ring). spokes > 0 (needs hole): wheel with `spokes` spokes, `rim` width,
    and a hub of radius `hub` (+ optional axle hole 0)."""
    tooth = tooth if tooth is not None else r * 0.16
    outline = gear_outline(r - tooth * 0.5, r + tooth * 0.5, teeth, phase=phase)
    faces = []
    if hole <= 0:
        faces += prism(part, mat, outline, -depth / 2, depth / 2, M, fan=True)
        return faces
    n = len(outline)
    if spokes:
        rim = rim if rim is not None else r * 0.22
        r_in = r - tooth * 0.5 - rim
        inner = [(r_in * math.cos(math.atan2(y, x)), r_in * math.sin(math.atan2(y, x))) for x, y in outline]
        faces += ring_prism(part, mat, outline, inner, -depth / 2, depth / 2, M)
        hub = hub if hub is not None else r * 0.25
        nh = 12
        faces += prism(part, mat, circle2d(hub, nh), -depth * 0.65, depth * 0.65, M)
        sw = spoke_w if spoke_w is not None else r * 0.14
        for k in range(spokes):
            a = 2 * math.pi * k / spokes + phase
            L = r_in - hub * 0.6
            Mk = M @ R("Z", math.degrees(a)) @ T(hub * 0.6 + L / 2 + 0.0, 0, 0)
            faces += grid_box(part, mat, (L + 0.01, sw, depth * 0.8), M=Mk)
        return faces
    inner = [(hole * math.cos(math.atan2(y, x)), hole * math.sin(math.atan2(y, x))) for x, y in outline]
    faces += ring_prism(part, mat, outline, inner, -depth / 2, depth / 2, M)
    return faces


def rivet(part, mat, loc, normal, r=0.011, h=0.006, seg=6, up=None, sink=0.002):
    """Dome rivet head standing on a surface (base sunk by `sink` so it never floats). 18 tris @ seg 6."""
    M = frame(loc, normal, up=up)
    prof = [(r, -sink), (r * 0.84, h * 0.55), (0.0, h)]
    return revolve(part, mat, prof, seg=seg, M=M, phase=math.pi / seg)


def bolt_hex(part, mat, loc, normal, r=0.016, h=0.01, up=None, sink=0.002):
    """Hex bolt head with a chamfered top."""
    M = frame(loc, normal, up=up)
    prof = [(r, -sink), (r, h * 0.7), (r * 0.8, h), (0.0, h)]
    return revolve(part, mat, prof, seg=6, cap0=True, M=M)


def tube(part, mat, pts, r, seg=8, caps=True, M=I4, radii=None):
    """Circular tube along a polyline (parallel transport), transformed by M."""
    bm = part.bm
    P = [M @ Vector(p) for p in pts]
    n = len(P)
    radii = radii or [r] * n
    tans = []
    for i in range(n):
        if i == 0:
            t = P[1] - P[0]
        elif i == n - 1:
            t = P[-1] - P[-2]
        else:
            t = (P[i + 1] - P[i]).normalized() + (P[i] - P[i - 1]).normalized()
        tans.append(t.normalized())
    nrm = tans[0].orthogonal().normalized()
    rings = []
    for i in range(n):
        if i > 0:
            ax = tans[i - 1].cross(tans[i])
            if ax.length > 1e-9:
                nrm = (Matrix.Rotation(tans[i - 1].angle(tans[i]), 3, ax.normalized()) @ nrm).normalized()
        bi = tans[i].cross(nrm)
        rings.append([bm.verts.new(P[i] + (nrm * math.cos(2 * math.pi * j / seg) +
                                           bi * math.sin(2 * math.pi * j / seg)) * radii[i])
                      for j in range(seg)])
    faces = []
    for i in range(n - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(seg):
            k = (j + 1) % seg
            faces.append(bm.faces.new((a[j], a[k], b[k], b[j])))
    if caps:
        faces.append(bm.faces.new(list(reversed(rings[0]))))
        faces.append(bm.faces.new(rings[-1]))
    set_mat(part, faces, mat)
    return faces


def blob(part, mat, r, loc=(0, 0, 0), scale=(1, 1, 1), subdiv=2, amount=0.12, seed=0, floor=None, M=I4,
         freq=1.7):
    """Smooth organic lump (icosphere + low-frequency radial noise) — stones, coin heaps."""
    rng = random.Random(seed)
    res = bmesh.ops.create_icosphere(part.bm, subdivisions=subdiv, radius=1.0, matrix=I4)
    vs = res["verts"]
    # a few random 'bumps' give a coherent low-frequency shape (not per-vertex jitter)
    bumps = [(Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))).normalized(),
              rng.uniform(-1, 1)) for _ in range(6)]
    for v in vs:
        d = v.co.normalized()
        k = 1.0
        for (bd, ba) in bumps:
            k += amount * ba * max(0.0, d.dot(bd)) ** freq
        k += rng.uniform(-amount, amount) * 0.15
        v.co = d * r * k
    Mx = M @ T(*loc) @ S(*scale)
    for v in vs:
        v.co = Mx @ v.co
        if floor is not None and v.co.z < floor:
            v.co.z = floor
    faces = list({f for v in vs for f in v.link_faces})
    set_mat(part, faces, mat)
    return faces


# ---------------------------------------------------------------------------
# Kit: Parts grouped by finish class, finished and joined into one mesh
# ---------------------------------------------------------------------------

class Kit:
    """kit = Kit("prop_chest_body")
       wood = kit.part("wood", bevel=(0.008, 2), smooth=35)
       ... add geometry ...
       obj = kit.build(parent, loc)           # one joined mesh named "prop_chest_body"
    bevel = (width, segments[, angle]) or None; smooth = angle (deg) or None; flat=True -> faceted."""

    def __init__(self, name):
        self.name = name
        self.parts = {}
        self.specs = {}

    def part(self, key, bevel=None, smooth=35.0, flat=False, wn=False, recalc=True, occluder=True, subdiv=0,
             zclamp=None):
        """recalc=False keeps the face winding exactly as authored (single-sided decals / paint).
        occluder=False: the part receives AO but does not cast it (small details on sparse surfaces would
        otherwise smear dark blotches across the interpolated vertex colours)."""
        if key not in self.parts:
            self.parts[key] = Part(f"{self.name}__{key}")
            self.specs[key] = dict(bevel=bevel, smooth=smooth, flat=flat, wn=wn, subdiv=subdiv, zclamp=zclamp)
            self.parts[key]._recalc = recalc
            self.parts[key]._occ = occluder
        return self.parts[key]

    def build_parts(self, parent=None, loc=(0, 0, 0)):
        """Build + finish every part as its own object (not joined yet): [(obj, is_occluder), ...]."""
        out = []
        for key, part in self.parts.items():
            if len(part.bm.verts) == 0:
                part.bm.free()
                continue
            occ = getattr(part, "_occ", True)
            o = part.build(parent, loc) if getattr(part, "_recalc", True) else build_raw(part, parent, loc)
            finish(o, **self.specs[key])
            if VERBOSE:
                mats = {}
                for p in o.data.polygons:
                    mn = o.data.materials[p.material_index].name
                    mats[mn] = mats.get(mn, 0) + len(p.vertices) - 2
                print(f"   [kit] {self.name}/{key}: {hp.obj_tris(o)} tris {mats}")
            out.append((o, occ))
        return out

    def join_parts(self, built):
        return join([o for o, _ in built], self.name)

    def build(self, parent=None, loc=(0, 0, 0)):
        return self.join_parts(self.build_parts(parent, loc))


def bake_parts(*built_lists, **kw):
    """hp.bake_vertex_ao over the parts of one prop (several Kits' build_parts results): every part
    receives AO, only parts flagged as occluders cast it."""
    objs = [o for bl in built_lists for (o, _) in bl]
    occ = [o for bl in built_lists for (o, c) in bl if c]
    bpy.context.view_layer.update()
    hp.bake_vertex_ao(objs=objs, occluders=occ, **kw)


def build_raw(part, parent=None, loc=(0, 0, 0)):
    """Like Part.build but WITHOUT recalculating face normals (authored winding is kept)."""
    mesh = bpy.data.meshes.new(part.name)
    part.bm.to_mesh(mesh)
    part.bm.free()
    for mn in part.mat_names:
        mesh.materials.append(get_mat(mn))
    obj = bpy.data.objects.new(part.name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = parent
    obj.location = loc
    return obj


def stroke_quads(part, mat, M, strokes, rings=(), sw=0.1, lift=0.0008, ring_seg=10):
    """Flat 'painted' strokes (2 tris each) in the XY plane of frame M (normal +Z, CCW winding):
    strokes = [((x0, y0), (x1, y1)), ...], rings = [(cx, cy, r), ...] drawn with width sw.
    Build the Part with recalc=False so the winding (and AO direction) stays +Z."""
    bm = part.bm
    faces = []
    for (p0, p1) in strokes:
        a, b = Vector(p0), Vector(p1)
        d = (b - a)
        if d.length < 1e-9:
            continue
        d.normalize()
        n = Vector((-d.y, d.x))
        a = a - d * sw * 0.45
        b = b + d * sw * 0.45
        q = [a - n * sw / 2, b - n * sw / 2, b + n * sw / 2, a + n * sw / 2]
        faces.append(bm.faces.new([bm.verts.new(M @ Vector((p.x, p.y, lift))) for p in q]))
    for (cx, cy, r) in rings:
        ro, ri = r + sw / 2, r - sw / 2
        outer = [bm.verts.new(M @ Vector((cx + ro * math.cos(2 * math.pi * i / ring_seg),
                                            cy + ro * math.sin(2 * math.pi * i / ring_seg), lift))) for i in range(ring_seg)]
        inner = [bm.verts.new(M @ Vector((cx + ri * math.cos(2 * math.pi * i / ring_seg),
                                            cy + ri * math.sin(2 * math.pi * i / ring_seg), lift))) for i in range(ring_seg)]
        for i in range(ring_seg):
            k = (i + 1) % ring_seg
            faces.append(bm.faces.new((outer[i], outer[k], inner[k], inner[i])))
    set_mat(part, faces, mat)
    return faces


def finish(o, bevel=None, smooth=35.0, flat=False, wn=False, subdiv=0, zclamp=None):
    """subdivision (Catmull-Clark) -> optional floor at z = zclamp (object space; faces lying on it are
    removed) -> bevel -> shading."""
    if subdiv:
        hp.subdivide_obj(o, levels=subdiv)
    if zclamp is not None:
        # flatten onto the floor, then drop the faces lying on it (never visible, saves ~1/3 of the tris)
        bm = bmesh.new()
        bm.from_mesh(o.data)
        for v in bm.verts:
            if v.co.z < zclamp:
                v.co.z = zclamp
        dead = [f for f in bm.faces if all(v.co.z <= zclamp + 1e-5 for v in f.verts)]
        bmesh.ops.delete(bm, geom=dead, context="FACES")
        bm.to_mesh(o.data)
        bm.free()
        o.data.update()
    if bevel:
        w, segs = bevel[0], bevel[1]
        ang = bevel[2] if len(bevel) > 2 else 30.0
        hp.bevel_obj(o, width=w, segments=segs, angle=ang)
    if flat:
        hp.flat_obj(o)
    elif wn:
        hp.weighted_normals(o)
    elif smooth is not None:
        hp.smooth_obj(o, smooth)
    return o


def join(objs, name):
    """Join mesh objects (same parent) into objs[0]; renames object + data to `name`."""
    objs = [o for o in objs if o is not None]
    if not objs:
        return None
    tgt = objs[0]
    if len(objs) > 1:
        vl = bpy.context.view_layer
        for o in vl.objects:
            o.select_set(False)
        for o in objs:
            o.select_set(True)
        vl.objects.active = tgt
        with bpy.context.temp_override(active_object=tgt, object=tgt, selected_objects=objs,
                                       selected_editable_objects=objs):
            bpy.ops.object.join()
        for o in vl.objects:
            o.select_set(False)
    tgt.name = name
    tgt.data.name = name
    return tgt


# ---------------------------------------------------------------------------
# vertex colour post-process (after hp.bake_tree_ao)
# ---------------------------------------------------------------------------

def _islands(me, face_ok):
    """Connected face islands (through shared vertices) among faces with face_ok[i]."""
    nv = len(me.vertices)
    parent = list(range(nv))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for p in me.polygons:
        if not face_ok[p.index]:
            continue
        vs = p.vertices
        r0 = find(vs[0])
        for v in vs[1:]:
            r1 = find(v)
            if r1 != r0:
                parent[r1] = r0
    return find


def tint_islands(obj, mats, lo=0.8, hi=1.0, seed=1, streak=0.0, streak_freq=9.0, axis_fn=None,
                 hue=None):
    """Multiply the 'Col' attribute per connected island of faces using materials in `mats`
    by a random factor in [lo, hi] (+ optional lengthwise grain streaks: per-vertex sine noise
    across the island's long axis). hue: optional (r, g, b) multiplier range end for warm/cool shifts."""
    me = obj.data
    if hp.AO_ATTR not in me.color_attributes:
        return
    names = [m.name if m else "" for m in me.materials]
    ok_mi = {i for i, n in enumerate(names) if n in mats}
    face_ok = [p.material_index in ok_mi for p in me.polygons]
    find = _islands(me, face_ok)
    rng = random.Random(seed)
    fac = {}
    attr = me.color_attributes[hp.AO_ATTR]
    nl = len(me.loops)
    cols = np.empty(nl * 4, dtype=np.float32)
    attr.data.foreach_get("color", cols)
    cols = cols.reshape(nl, 4)
    # island bounding boxes for streak direction
    ibox = {}
    if streak:
        for p in me.polygons:
            if not face_ok[p.index]:
                continue
            key = find(p.vertices[0])
            for vi in p.vertices:
                co = me.vertices[vi].co
                b = ibox.get(key)
                if b is None:
                    ibox[key] = [co.copy(), co.copy()]
                else:
                    b[0] = Vector(map(min, b[0], co))
                    b[1] = Vector(map(max, b[1], co))
    for p in me.polygons:
        if not face_ok[p.index]:
            continue
        key = find(p.vertices[0])
        if key not in fac:
            f = rng.uniform(lo, hi)
            if hue:
                t = rng.random()
                fac[key] = (f * (1 + (hue[0] - 1) * t), f * (1 + (hue[1] - 1) * t), f * (1 + (hue[2] - 1) * t),
                            rng.uniform(0, 100))
            else:
                fac[key] = (f, f, f, rng.uniform(0, 100))
        fr, fg, fb, ph = fac[key]
        for li in range(p.loop_start, p.loop_start + p.loop_total):
            k = 1.0
            if streak:
                co = me.vertices[me.loops[li].vertex_index].co
                b0, b1 = ibox[key]
                ext = b1 - b0
                # long axis = biggest extent; streak coordinate = the other two
                ax = max(range(3), key=lambda a: ext[a])
                u = sum(co[a] for a in range(3) if a != ax)
                k = 1.0 - streak * (0.5 + 0.5 * math.sin(u * streak_freq * 6.283 + ph)) \
                    * (0.6 + 0.4 * math.sin(co[ax] * 3.1 + ph * 1.7))
            cols[li, 0] *= fr * k
            cols[li, 1] *= fg * k
            cols[li, 2] *= fb * k
    np.clip(cols[:, :3], 0.0, 1.0, out=cols[:, :3])
    attr.data.foreach_set("color", cols.ravel())
    me.update()


def ground_grime(z0=0.0, z1=0.25, dark=0.72, warm=(1.0, 0.95, 0.88)):
    """bake_tree_ao tint: darker / warmer towards the ground (dirt splash) above the prop base."""
    def fn(p, n):
        t = min(1.0, max(0.0, (p.z - z0) / max(1e-6, z1 - z0)))
        t = t * t * (3 - 2 * t)
        k = dark + (1 - dark) * t
        return (k * (warm[0] + (1 - warm[0]) * t), k * (warm[1] + (1 - warm[1]) * t),
                k * (warm[2] + (1 - warm[2]) * t))
    return fn
