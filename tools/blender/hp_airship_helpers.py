"""Geometry helpers for the hi-poly airship (props_airship.py) — adds geometry straight into a
common.Part's bmesh (part-local coordinates), like env_helpers / char_helpers.

    Track(part)                      context manager: collect the verts created inside the block
    mark_bevel(part, verts, angle)   flag sharp edges of those verts for a WEIGHT-limited bevel
    add_grid(part, rows, mat, ...)   quad grid / tube / fan from rows of 3D points (rows of 1 = pole)
    revolve_y(part, mat, prof, ...)  surface of revolution around an axis parallel to Y
    revolve_m(part, mat, prof, M)    surface of revolution around local Z, transformed by M
    sweep(part, mat, pts, shape, ..) sweep an arbitrary 2D cross-section along a polyline
    round_corners(pts, r, n)         fillet the corners of a polyline (for frames / rails)
    bezier2 / bezier3 / coons        curve & patch utilities for fins and blades
    join_objects(objs, name)         join meshes (keeps custom normals) — headless safe
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from env_helpers import set_mat

BW_LAYER = "bevel_weight_edge"


# ---------------------------------------------------------------------------
# bookkeeping
# ---------------------------------------------------------------------------

class Track:
    """with Track(part) as t: ...  -> t.idx = indices of the verts created inside the block (robust
    against bmesh ops freeing / reusing temporary verts, same stamping trick as env_helpers.Xform).
    NOTE Blender 5.x: adding/removing a bmesh custom-data layer invalidates every Python BMVert
    reference, so only indices survive the block."""
    _LAYER = "_air_track"

    def __init__(self, part):
        self.part = part
        self.idx = []

    def __enter__(self):
        bm = self.part.bm
        lay = bm.verts.layers.int.get(self._LAYER) or bm.verts.layers.int.new(self._LAYER)
        for v in bm.verts:
            v[lay] = 1
        return self

    def __exit__(self, *exc):
        bm = self.part.bm
        lay = bm.verts.layers.int.get(self._LAYER)
        bm.verts.index_update()
        self.idx = [v.index for v in bm.verts if v[lay] == 0]
        bm.verts.layers.int.remove(lay)
        return False


def mark_bevel(part, idx, angle=30.0, weight=1.0):
    """Give every edge between two of the verts `idx` (indices, see Track) whose face angle exceeds
    `angle` a bevel weight (use hp.bevel_obj(obj, limit='WEIGHT') after building)."""
    bm = part.bm
    lay = bm.edges.layers.float.get(BW_LAYER) or bm.edges.layers.float.new(BW_LAYER)
    bm.verts.ensure_lookup_table()
    verts = [bm.verts[i] for i in idx]
    faces = list({f for v in verts for f in v.link_faces})
    if faces:
        bmesh.ops.recalc_face_normals(bm, faces=faces)
    bm.normal_update()
    vs = set(verts)
    th = math.radians(angle)
    for e in {e for v in verts for e in v.link_edges}:
        if e.verts[0] in vs and e.verts[1] in vs and len(e.link_faces) == 2:
            try:
                a = e.calc_face_angle()
            except ValueError:
                continue
            if a > th:
                e[lay] = weight


# ---------------------------------------------------------------------------
# grids / revolves / sweeps
# ---------------------------------------------------------------------------

def add_grid(part, rows, mat, closed_u=False, closed_v=False, mat_fn=None, cap0=None, cap1=None):
    """rows: list (v) of lists (u) of 3D points with equal length; a row of length 1 is a pole.
    closed_u: rows are loops. closed_v: last row connects back to the first.
    mat_fn(i, j) -> material name for the face between rows i/i+1 and columns j/j+1 (None = mat).
    cap0 / cap1: material name -> n-gon cap on the first / last row."""
    bm = part.bm
    vr = [[bm.verts.new(Vector(p)) for p in row] for row in rows]
    groups = {}
    nv = len(vr)
    for i in range(nv if closed_v else nv - 1):
        A, B = vr[i], vr[(i + 1) % nv]
        if len(A) == 1 and len(B) == 1:
            continue
        n = max(len(A), len(B))
        for j in range(n if closed_u else n - 1):
            k = (j + 1) % n
            if len(A) == 1:
                f = bm.faces.new((A[0], B[k], B[j]))
            elif len(B) == 1:
                f = bm.faces.new((A[j], A[k], B[0]))
            else:
                f = bm.faces.new((A[j], A[k], B[k], B[j]))
            m = (mat_fn(i, j) if mat_fn else None) or mat
            groups.setdefault(m, []).append(f)
    if cap0 and len(vr[0]) > 2:
        groups.setdefault(cap0, []).append(bm.faces.new(list(reversed(vr[0]))))
    if cap1 and len(vr[-1]) > 2:
        groups.setdefault(cap1, []).append(bm.faces.new(vr[-1]))
    for m, fs in groups.items():
        set_mat(part, fs, m)
    return vr


def revolve_y(part, mat, prof, seg=32, cx=0.0, cz=0.0, closed=False, theta0=0.0, mat_fn=None,
              rfun=None, cap0=None, cap1=None):
    """Revolve a (y, r) profile around the axis x=cx, z=cz (parallel to Y).
    theta measured from -Z (bottom) toward +X.  rfun(i, j, theta, r) -> r' lets the caller modulate
    the radius per vertex (gores / creases). closed=True: profile is a closed loop (ring shapes)."""
    rows = []
    for i, (y, r) in enumerate(prof):
        if r <= 1e-7:
            rows.append([(cx, y, cz)])
            continue
        row = []
        for j in range(seg):
            th = theta0 + 2 * math.pi * j / seg
            rr = rfun(i, j, th, r) if rfun else r
            row.append((cx + rr * math.sin(th), y, cz - rr * math.cos(th)))
        rows.append(row)
    return add_grid(part, rows, mat, closed_u=True, closed_v=closed, mat_fn=mat_fn, cap0=cap0, cap1=cap1)


def revolve_m(part, mat, prof, seg=16, M=None, closed=False, phase=0.0, mat_fn=None, cap0=None, cap1=None):
    """Revolve an (h, r) profile around local Z, then transform by matrix M."""
    M = M or Matrix.Identity(4)
    rows = []
    for (h, r) in prof:
        if r <= 1e-7:
            rows.append([tuple(M @ Vector((0, 0, h)))])
            continue
        rows.append([tuple(M @ Vector((r * math.cos(phase + 2 * math.pi * j / seg),
                                       r * math.sin(phase + 2 * math.pi * j / seg), h)))
                     for j in range(seg)])
    return add_grid(part, rows, mat, closed_u=True, closed_v=closed, mat_fn=mat_fn, cap0=cap0, cap1=cap1)


def frames_along(pts, up=(0, 0, 1), mode="transport", closed=False):
    """Frames (tangent, normal, binormal) along a polyline.
    mode 'transport': parallel transport (no twist; start normal from `up`).
    mode 'up'       : normal = `up` made perpendicular to the tangent (stable for rails / beams that
                      never run parallel to `up`; required for closed loops)."""
    P = [Vector(p) for p in pts]
    n = len(P)
    tans = []
    for i in range(n):
        if closed:
            t = (P[(i + 1) % n] - P[i]).normalized() + (P[i] - P[i - 1]).normalized()
        elif i == 0:
            t = P[1] - P[0]
        elif i == n - 1:
            t = P[-1] - P[-2]
        else:
            t = (P[i + 1] - P[i]).normalized() + (P[i] - P[i - 1]).normalized()
        tans.append(t.normalized())
    upv = Vector(up)
    out = []
    if mode == "up":
        for i in range(n):
            t = tans[i]
            nrm = upv - t * upv.dot(t)
            if nrm.length < 1e-6:
                nrm = Vector((1, 0, 0)) - t * t.x
            nrm.normalize()
            out.append((t, nrm, t.cross(nrm)))
        return P, out
    nrm = upv - tans[0] * upv.dot(tans[0])
    if nrm.length < 1e-5:
        nrm = Vector((1, 0, 0)) - tans[0] * tans[0].x
    nrm.normalize()
    for i in range(n):
        if i > 0:
            ax = tans[i - 1].cross(tans[i])
            if ax.length > 1e-9:
                ang = tans[i - 1].angle(tans[i])
                nrm = (Matrix.Rotation(ang, 3, ax.normalized()) @ nrm)
        nrm = (nrm - tans[i] * nrm.dot(tans[i])).normalized()
        out.append((tans[i], nrm, tans[i].cross(nrm)))
    return P, out


def sweep(part, mat, pts, shape, scale=None, up=(0, 0, 1), closed_shape=True, cap=True, mat_fn=None,
          miter=True, mode="transport", closed_path=False):
    """Sweep a 2D cross-section `shape` [(a, b), ...] (a along the frame normal, b along the binormal)
    along polyline pts. scale: per-point factor (float or (sa, sb)). miter=True widens the section at
    bends (1/cos(half angle)) so tubes keep their thickness through corners.
    closed_path=True: the polyline is a loop (use mode='up')."""
    P, fr = frames_along(pts, up, mode=mode, closed=closed_path)
    n = len(P)
    rows = []
    for i in range(n):
        t, nn, bb = fr[i]
        s = 1.0 if scale is None else scale[i]
        sa, sb = (s, s) if isinstance(s, (int, float)) else s
        k = 1.0
        inner = closed_path or 0 < i < n - 1
        if miter and inner:
            d0 = (P[i] - P[i - 1]).normalized()
            d1 = (P[(i + 1) % n] - P[i]).normalized()
            c = max(0.35, math.cos(d0.angle(d1) / 2)) if (d0.length > 0 and d1.length > 0) else 1.0
            k = 1.0 / c
        row = []
        for (a, b) in shape:
            off = nn * (a * sa) + bb * (b * sb)
            if k > 1.0001:
                # stretch only the component lying in the bend plane
                bend = d1 - d0
                if bend.length > 1e-6:
                    bend = (bend - t * bend.dot(t)).normalized()
                    comp = off.dot(bend)
                    off = off + bend * comp * (k - 1.0)
            row.append(tuple(P[i] + off))
        rows.append(row)
    capm = mat if (cap and not closed_path) else None
    return add_grid(part, rows, mat, closed_u=closed_shape, closed_v=closed_path, mat_fn=mat_fn,
                    cap0=capm, cap1=capm)


def sweep_custom(part, mat, centers, normals, binormals, shape, cap=True, mat_fn=None):
    """Sweep with explicit per-point frames (e.g. straps lying on a curved surface)."""
    rows = []
    for c, nn, bb in zip(centers, normals, binormals):
        c, nn, bb = Vector(c), Vector(nn), Vector(bb)
        rows.append([tuple(c + nn * a + bb * b) for (a, b) in shape])
    capm = mat if cap else None
    return add_grid(part, rows, mat, closed_u=True, mat_fn=mat_fn, cap0=capm, cap1=capm)


def orient(c, n, up=(0, 0, 1)):
    """4x4 matrix: origin c, local Z -> n, local X horizontal-ish (up x n)."""
    n = Vector(n).normalized()
    upv = Vector(up)
    x = upv.cross(n)
    if x.length < 1e-5:
        x = Vector((0, 1, 0)).cross(n)
        if x.length < 1e-5:
            x = Vector((1, 0, 0)).cross(n)
    x.normalize()
    y = n.cross(x).normalized()
    M = Matrix((x, y, n)).transposed().to_4x4()
    M.translation = Vector(c)
    return M


def gear(part, mat, r=0.2, teeth=12, thick=0.05, depth=None, hole=0.0, loc=(0, 0, 0), tip=0.42, root=0.58):
    """Gear disc in local XY (axis Z), trapezoid teeth, one closed prism (star n-gon caps)."""
    depth = r * 0.2 if depth is None else depth
    rr = r - depth
    pitch = 2 * math.pi / teeth
    pts = []
    for i in range(teeth):
        a = pitch * i
        pts += [(rr * math.cos(a - pitch * root / 2), rr * math.sin(a - pitch * root / 2)),
                (r * math.cos(a - pitch * tip / 2), r * math.sin(a - pitch * tip / 2)),
                (r * math.cos(a + pitch * tip / 2), r * math.sin(a + pitch * tip / 2)),
                (rr * math.cos(a + pitch * root / 2), rr * math.sin(a + pitch * root / 2))]
    lx, ly, lz = loc
    rows = [[(lx + x, ly + y, lz - thick / 2) for (x, y) in pts], [(lx + x, ly + y, lz + thick / 2) for (x, y) in pts]]
    return add_grid(part, rows, mat, closed_u=True, cap0=mat, cap1=mat)


def circle_shape(r, seg, phase=None):
    ph = math.pi / seg if phase is None else phase
    return [(r * math.cos(2 * math.pi * j / seg + ph), r * math.sin(2 * math.pi * j / seg + ph)) for j in range(seg)]


def rrect_shape(w, h, r, n=2):
    """Rounded rectangle (w along a, h along b), corner radius r, n segments per corner."""
    out = []
    cs = [(w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180),
          (w / 2 - r, -h / 2 + r, 270)]
    for cx, cy, a0 in cs:
        for k in range(n + 1):
            a = math.radians(a0 + 90.0 * k / n)
            out.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return out


def tube(part, mat, pts, r, seg=8, cap=True, radii=None, up=(0, 0, 1), mat_fn=None):
    """Round tube along a polyline (mitred at bends). radii: optional per-point scale factors."""
    return sweep(part, mat, pts, circle_shape(r, seg), scale=radii, up=up, cap=cap, mat_fn=mat_fn)


def round_corners(pts, radius, n=3, closed=False, min_turn=25.0):
    """Replace every interior corner turning more than `min_turn` degrees by an n-segment arc
    (quadratic Bezier fillet). Gentle bends are kept as they are."""
    P = [Vector(p) for p in pts]
    m = len(P)
    out = []
    cos_lim = -math.cos(math.radians(min_turn))
    for i in range(m):
        if not closed and (i == 0 or i == m - 1):
            out.append(P[i])
            continue
        a, b, c = P[i - 1], P[i], P[(i + 1) % m]
        d0, d1 = (a - b), (c - b)
        r = min(radius, d0.length * 0.45, d1.length * 0.45)
        if d0.length < 1e-6 or d1.length < 1e-6 or d0.normalized().dot(d1.normalized()) < cos_lim:
            out.append(b)
            continue
        p0 = b + d0.normalized() * r
        p2 = b + d1.normalized() * r
        for k in range(n + 1):
            t = k / n
            out.append(p0 * (1 - t) ** 2 + b * 2 * t * (1 - t) + p2 * t * t)
    return [tuple(p) for p in out]


def resample(pts, step):
    """Resample a polyline at ~constant spacing (keeps end points)."""
    P = [Vector(p) for p in pts]
    L = [0.0]
    for i in range(1, len(P)):
        L.append(L[-1] + (P[i] - P[i - 1]).length)
    total = L[-1]
    n = max(1, int(round(total / step)))
    out = []
    j = 0
    for k in range(n + 1):
        s = total * k / n
        while j < len(P) - 2 and L[j + 1] < s:
            j += 1
        seg = L[j + 1] - L[j]
        t = 0.0 if seg < 1e-9 else (s - L[j]) / seg
        out.append(tuple(P[j].lerp(P[j + 1], t)))
    return out


def stack_decal(part, mat, outline, center, stack, surf):
    """Raised plate following a curved surface (emblems on the envelope).
    outline: [(u, v), ...] star-shaped around `center` (u, v). stack: [(scale, height), ...] loops from
    the bottom (negative height = embedded) to the top; closed with a pole at both ends.
    surf(u, v, h) -> 3D point on the surface offset by h along its normal."""
    cu, cv = center
    rows = [[tuple(surf(cu, cv, stack[0][1]))]]
    for s, h in stack:
        rows.append([tuple(surf(cu + (u - cu) * s, cv + (v - cv) * s, h)) for (u, v) in outline])
    rows.append([tuple(surf(cu, cv, stack[-1][1]))])
    return add_grid(part, rows, mat, closed_u=True)


def gear_outline(r, teeth, depth, tip=0.42, root=0.58):
    rr = r - depth
    pitch = 2 * math.pi / teeth
    pts = []
    for i in range(teeth):
        a = pitch * i
        pts += [(rr * math.cos(a - pitch * root / 2), rr * math.sin(a - pitch * root / 2)),
                (r * math.cos(a - pitch * tip / 2), r * math.sin(a - pitch * tip / 2)),
                (r * math.cos(a + pitch * tip / 2), r * math.sin(a + pitch * tip / 2)),
                (rr * math.cos(a + pitch * root / 2), rr * math.sin(a + pitch * root / 2))]
    return pts


# ---------------------------------------------------------------------------
# curves & patches (2D or 3D Vectors)
# ---------------------------------------------------------------------------

def bezier2(p0, p1, p2, t):
    p0, p1, p2 = Vector(p0), Vector(p1), Vector(p2)
    return p0 * (1 - t) ** 2 + p1 * (2 * t * (1 - t)) + p2 * (t * t)


def bezier3(p0, p1, p2, p3, t):
    p0, p1, p2, p3 = Vector(p0), Vector(p1), Vector(p2), Vector(p3)
    u = 1 - t
    return p0 * u ** 3 + p1 * (3 * u * u * t) + p2 * (3 * u * t * t) + p3 * t ** 3


def coons(bottom, top, left, right):
    """Bilinear Coons patch from 4 boundary functions s -> Vector (s in [0, 1]).
    bottom(u) / top(u) run along u (v=0 / v=1); left(v) / right(v) along v (u=0 / u=1)."""
    b0, b1, t0, t1 = bottom(0.0), bottom(1.0), top(0.0), top(1.0)

    def P(u, v):
        return ((bottom(u) * (1 - v) + top(u) * v) + (left(v) * (1 - u) + right(v) * u)
                - (b0 * ((1 - u) * (1 - v)) + b1 * (u * (1 - v)) + t0 * ((1 - u) * v) + t1 * (u * v)))
    return P


def smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------------------
# objects
# ---------------------------------------------------------------------------

def join_objects(objs, name):
    """Join mesh objects into the first one (keeps custom normals / attributes) and rename it."""
    objs = [o for o in objs if o is not None]
    if len(objs) > 1:
        with bpy.context.temp_override(active_object=objs[0], object=objs[0], selected_objects=objs,
                                       selected_editable_objects=objs):
            bpy.ops.object.join()
    o = objs[0]
    o.name = name
    o.data.name = name
    return o
