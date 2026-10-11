"""Brass Beetle only — geometry / rig / AO helpers for the hi-poly model (model_beetle.py).

Own module (shared helpers common.py / char_helpers.py / hp_helpers.py ... stay read-only).
All builders add geometry to a common.Part in WORLD coordinates; `BoneBuilder` shifts the
finished pieces to the bone pivot, applies smoothing / bevels per piece and joins them into
the single rigid part object that rig_from_parts() later turns into a bone.

    sp(v, e)                         signed power (superellipse sections)
    frame(z, x_hint) / mtx(...)      orthonormal frame / 4x4 placement from an axis
    grid_rows / grid_faces / strip   parametric quad grids (poles collapse to one vertex)
    thick_patch(p, fo, fi, us, vs)   closed solid from an outer + inner parametric surface
    sweep(p, mat, pts, r, ...)       tube along a polyline (parallel transport or 'up' frame,
                                     elliptic sections, closed loops, pointed ends)
    catmull(pts, n)                  smooth a control polyline
    dome / ball / disc / lathe_m     small oriented primitives (rivets, bolts, caps)
    gear_ring(p, mat, M, ...)        toothed ring gear with spokes + hub (axis = frame Z)
    BoneBuilder                      pieces -> one rigid part object per bone
    bake_ao_open(skin, ...)          vertex AO that keeps the bay under the elytra lit
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

import hp_helpers as hp
from common import Part


# ---------------------------------------------------------------------------------------
# math
# ---------------------------------------------------------------------------------------
def sp(v, e):
    """signed power"""
    return math.copysign(abs(v) ** e, v)


def smoothstep(e0, e1, x):
    if e0 == e1:
        return 1.0 if x >= e1 else 0.0
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def frame(z_axis, x_hint=(1, 0, 0)):
    """3x3 rotation whose columns are (x, y, z) with z = z_axis and x as close to x_hint as possible."""
    z = Vector(z_axis).normalized()
    x = Vector(x_hint)
    x = x - z * x.dot(z)
    if x.length < 1e-6:
        x = z.orthogonal()
    x.normalize()
    y = z.cross(x)
    return Matrix((x, y, z)).transposed()


def mtx(loc, z_axis=(0, 0, 1), x_hint=(1, 0, 0), scale=(1, 1, 1)):
    if isinstance(scale, (int, float)):
        scale = (scale, scale, scale)
    R = frame(z_axis, x_hint).to_4x4()
    S = Matrix.Diagonal((scale[0], scale[1], scale[2], 1.0))
    return Matrix.Translation(Vector(loc)) @ R @ S


def catmull(pts, n_per=4, closed=False):
    """Catmull-Rom resample of a control polyline (n_per samples per segment)."""
    P = [Vector(p) for p in pts]
    out = []
    m = len(P)
    segs = m if closed else m - 1
    for i in range(segs):
        p0 = P[(i - 1) % m] if (closed or i > 0) else P[0] * 2 - P[1]
        p1 = P[i]
        p2 = P[(i + 1) % m]
        p3 = P[(i + 2) % m] if (closed or i + 2 < m) else P[-1] * 2 - P[-2]
        for k in range(n_per):
            t = k / n_per
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    if not closed:
        out.append(P[-1].copy())
    return out


def resample(pts, n):
    """Resample a polyline to n points evenly spaced by arc length."""
    P = [Vector(p) for p in pts]
    d = [0.0]
    for i in range(1, len(P)):
        d.append(d[-1] + (P[i] - P[i - 1]).length)
    L = d[-1]
    out = []
    j = 0
    for k in range(n):
        s = L * k / (n - 1)
        while j < len(P) - 2 and d[j + 1] < s:
            j += 1
        seg = d[j + 1] - d[j]
        t = 0.0 if seg < 1e-9 else (s - d[j]) / seg
        out.append(P[j].lerp(P[j + 1], max(0.0, min(1.0, t))))
    return out


# ---------------------------------------------------------------------------------------
# bmesh building blocks
# ---------------------------------------------------------------------------------------
def _face(bm, vs):
    u = []
    for v in vs:
        if v not in u:
            u.append(v)
    if len(u) < 3:
        return None
    try:
        return bm.faces.new(u)
    except ValueError:
        return None


def set_mat(p, faces, mat):
    mi = p._mi(mat)
    for f in faces:
        if f is not None:
            f.material_index = mi
    return faces


def grid_rows(bm, pts2d, eps=1e-7):
    """pts2d: rows of Vectors -> rows of BMVerts. A row whose points all coincide becomes a pole
    (one shared vertex)."""
    rows = []
    for row in pts2d:
        if all((q - row[0]).length < eps for q in row):
            v = bm.verts.new(row[0])
            rows.append([v] * len(row))
        else:
            rows.append([bm.verts.new(q) for q in row])
    return rows


def grid_faces(bm, rows, close_u=False, close_v=False):
    out = []
    nu, nv = len(rows), len(rows[0])
    for i in range(nu if close_u else nu - 1):
        A, B = rows[i], rows[(i + 1) % nu]
        for j in range(nv if close_v else nv - 1):
            k = (j + 1) % nv
            f = _face(bm, [A[j], A[k], B[k], B[j]])
            if f:
                out.append(f)
    return out


def strip(bm, a, b, closed=False):
    out = []
    n = len(a)
    for i in range(n if closed else n - 1):
        j = (i + 1) % n
        f = _face(bm, [a[i], a[j], b[j], b[i]])
        if f:
            out.append(f)
    return out


def boundary_loop(rows):
    """Boundary vertex loop of a grid (row 0 -> last column -> last row reversed -> column 0 up)."""
    nu, nv = len(rows), len(rows[0])
    loop = list(rows[0])
    loop += [rows[i][nv - 1] for i in range(1, nu)]
    loop += [rows[nu - 1][j] for j in range(nv - 2, -1, -1)]
    loop += [rows[i][0] for i in range(nu - 2, 0, -1)]
    # collapse consecutive duplicates (poles)
    out = []
    for v in loop:
        if not out or out[-1] is not v:
            out.append(v)
    if len(out) > 1 and out[0] is out[-1]:
        out.pop()
    return out


def boundary_idx(nu, nv):
    """(i, j) index pairs of boundary_loop (before pole collapsing)."""
    idx = [(0, j) for j in range(nv)]
    idx += [(i, nv - 1) for i in range(1, nu)]
    idx += [(nu - 1, j) for j in range(nv - 2, -1, -1)]
    idx += [(i, 0) for i in range(nu - 2, 0, -1)]
    return idx


def _loop_with_params(rows, us, vs):
    """Boundary loop of a grid + perimeter parameter (0..4) of every loop vertex (poles collapsed)."""
    nu, nv = len(us), len(vs)
    u0, u1, v0, v1 = us[0], us[-1], vs[0], vs[-1]

    def nu_(u):
        return (u - u0) / (u1 - u0)

    def nv_(v):
        return (v - v0) / (v1 - v0)
    seq = [((0, j), nv_(vs[j])) for j in range(nv)]
    seq += [((i, nv - 1), 1 + nu_(us[i])) for i in range(1, nu)]
    seq += [((nu - 1, j), 2 + (1 - nv_(vs[j]))) for j in range(nv - 2, -1, -1)]
    seq += [((i, 0), 3 + (1 - nu_(us[i]))) for i in range(nu - 2, 0, -1)]
    verts, params = [], []
    for (i, j), t in seq:
        v = rows[i][j]
        if verts and verts[-1] is v:
            continue
        verts.append(v)
        params.append(t)
    if len(verts) > 1 and verts[0] is verts[-1]:
        verts.pop()
        params.pop()
    return verts, params


def zipper(bm, a, pa, b, pb, period=4.0):
    """Closed triangle/quad band between two vertex loops with different counts, matched by a
    monotone loop parameter (pa, pb in [0, period))."""
    n, m = len(a), len(b)
    pa = list(pa) + [pa[0] + period]
    pb = list(pb) + [pb[0] + period]
    i = j = 0
    out = []
    while i < n or j < m:
        if i < n and (j >= m or pa[i + 1] <= pb[j + 1]):
            f = _face(bm, [a[i % n], a[(i + 1) % n], b[j % m]])
            i += 1
        else:
            f = _face(bm, [a[i % n], b[(j + 1) % m], b[j % m]])
            j += 1
        if f:
            out.append(f)
    return out


def thick_patch(p, fo, fi, us, vs, mat_out, mat_in=None, mat_edge=None, us_in=None, vs_in=None,
                depth=None, outer_mat=None):
    """Closed solid between an outer surface fo(u, v) and an inner surface fi(u, v).
    us / vs: outer grid samples; us_in / vs_in: (coarser) inner grid samples with the same first and
    last values. The rim band between both boundary loops is zipped by perimeter parameter.
    depth(u, v) -> metres pushed from the outer surface toward the inner one (grooves > 0, beads < 0).
    outer_mat(u0, u1, v0, v1) -> material name (or None = mat_out) per outer face (groove inlays).
    Returns dict(outer=rows, inner=rows, bvh=BVH of the outer surface for conform())."""
    bm = p.bm
    mat_in = mat_in or mat_out
    mat_edge = mat_edge or mat_in
    vs_in = vs_in or vs
    us_in = us_in or us

    def outer_pt(u, v):
        o = fo(u, v)
        if depth is not None:
            d = depth(u, v)
            if abs(d) > 1e-7:
                n = fi(u, v) - o
                if n.length > 1e-8:
                    o = o + n.normalized() * d
        return o

    O = grid_rows(bm, [[outer_pt(u, v) for v in vs] for u in us])
    if outer_mat is None:
        set_mat(p, grid_faces(bm, O), mat_out)
    else:
        for i in range(len(us) - 1):
            for j in range(len(vs) - 1):
                f = _face(bm, [O[i][j], O[i][j + 1], O[i + 1][j + 1], O[i + 1][j]])
                if f:
                    set_mat(p, [f], outer_mat(us[i], us[i + 1], vs[j], vs[j + 1]) or mat_out)
    I = grid_rows(bm, [[fi(u, v) for v in vs_in] for u in us_in])
    set_mat(p, grid_faces(bm, I), mat_in)
    la, pa = _loop_with_params(O, us, vs)
    lb, pb = _loop_with_params(I, us_in, vs_in)
    set_mat(p, zipper(bm, la, pa, lb, pb), mat_edge)
    tb = bmesh.new()
    T = grid_rows(tb, [[v.co.copy() for v in row] for row in O])
    grid_faces(tb, T)
    bvh = BVHTree.FromBMesh(tb)
    tb.free()
    return dict(outer=O, inner=I, bvh=bvh)


def sweep(p, mat, pts, r, seg=8, closed=False, cap=True, up=None, fx=1.0, fy=1.0, phase=None,
          mats=None, shape=None):
    """Tube along a polyline. r: scalar or per-point list (0 -> pointed end / pole).
    up: None -> parallel-transport frames; a vector -> section 'N' axis = up projected on the
    section plane (stable orientation, needed for flattened sections). fx scales the section along
    N, fy along B = T x N (scalar or per-point list). mats: optional per-segment material list.
    shape: optional custom cross-section [(a, b), ...] (unit-ish coords along N and B) instead of a
    circle with `seg` points (e.g. faceted lens / keel sections for armour plates).
    Returns list of rings."""
    bm = p.bm
    if shape is not None:
        seg = len(shape)
    P = [Vector(q) for q in pts]
    n = len(P)
    rs = list(r) if isinstance(r, (list, tuple)) else [r] * n
    fxs = list(fx) if isinstance(fx, (list, tuple)) else [fx] * n
    fys = list(fy) if isinstance(fy, (list, tuple)) else [fy] * n
    T = []
    for i in range(n):
        if closed:
            t = (P[(i + 1) % n] - P[i]).normalized() + (P[i] - P[i - 1]).normalized()
        elif i == 0:
            t = P[1] - P[0]
        elif i == n - 1:
            t = P[-1] - P[-2]
        else:
            t = (P[i + 1] - P[i]).normalized() + (P[i] - P[i - 1]).normalized()
        T.append(t.normalized())
    Ns = []
    if up is not None:
        U = Vector(up)
        prev = None
        for i in range(n):
            nn = U - T[i] * U.dot(T[i])
            if nn.length < 1e-5:
                nn = prev if prev is not None else T[i].orthogonal()
            nn.normalize()
            Ns.append(nn)
            prev = nn
    else:
        nn = T[0].orthogonal().normalized()
        Ns.append(nn)
        for i in range(1, n):
            q = T[i - 1].rotation_difference(T[i])
            nn = q @ Ns[-1]
            nn = (nn - T[i] * nn.dot(T[i])).normalized()
            Ns.append(nn)
    ph = (math.pi / seg) if phase is None else phase
    rings = []
    for i in range(n):
        if rs[i] <= 1e-7:
            rings.append([bm.verts.new(P[i])])
            continue
        Nn, Bn = Ns[i], T[i].cross(Ns[i]).normalized()
        ring = []
        for k in range(seg):
            if shape is not None:
                ca, sa = shape[k]
            else:
                a = 2 * math.pi * k / seg + ph
                ca, sa = math.cos(a), math.sin(a)
            ring.append(bm.verts.new(P[i] + (Nn * ca * fxs[i] + Bn * sa * fys[i]) * rs[i]))
        rings.append(ring)
    faces_by_seg = []
    for k in range(n if closed else n - 1):
        A, B = rings[k], rings[(k + 1) % n]
        fs = []
        if len(A) == 1 and len(B) == 1:
            faces_by_seg.append(fs)
            continue
        for i in range(seg):
            j = (i + 1) % seg
            if len(A) == 1:
                f = _face(bm, [A[0], B[i], B[j]])
            elif len(B) == 1:
                f = _face(bm, [A[i], A[j], B[0]])
            else:
                f = _face(bm, [A[i], A[j], B[j], B[i]])
            if f:
                fs.append(f)
        faces_by_seg.append(fs)
    allf = [f for fs in faces_by_seg for f in fs]
    if cap and not closed:
        if len(rings[0]) > 2:
            f = _face(bm, list(reversed(rings[0])))
            if f:
                allf.append(f)
                faces_by_seg[0].append(f)
        if len(rings[-1]) > 2:
            f = _face(bm, rings[-1])
            if f:
                allf.append(f)
                faces_by_seg[-1].append(f)
    if mats:
        for k, fs in enumerate(faces_by_seg):
            set_mat(p, fs, mats[min(k, len(mats) - 1)])
    else:
        set_mat(p, allf, mat)
    return rings


def lathe_m(p, mat, profile, M, seg=12, cap=(True, True)):
    """Surface of revolution around the local Z of matrix M. profile [(r, z), ...]; r == 0 -> pole."""
    bm = p.bm
    rings = []
    for (r, z) in profile:
        if r <= 1e-7:
            rings.append([bm.verts.new(M @ Vector((0, 0, z)))])
        else:
            rings.append([bm.verts.new(M @ Vector((r * math.cos(2 * math.pi * k / seg),
                                                   r * math.sin(2 * math.pi * k / seg), z)))
                          for k in range(seg)])
    fs = []
    for k in range(len(rings) - 1):
        A, B = rings[k], rings[k + 1]
        for i in range(seg):
            j = (i + 1) % seg
            if len(A) == 1:
                f = _face(bm, [A[0], B[j], B[i]])
            elif len(B) == 1:
                f = _face(bm, [A[i], A[j], B[0]])
            else:
                f = _face(bm, [A[i], A[j], B[j], B[i]])
            if f:
                fs.append(f)
    if cap[0] and len(rings[0]) > 2:
        fs.append(_face(bm, list(reversed(rings[0]))))
    if cap[1] and len(rings[-1]) > 2:
        fs.append(_face(bm, rings[-1]))
    set_mat(p, fs, mat)
    return rings


def mark(*parts):
    """Remember the current vertex count of each Part (start of a decal)."""
    return [(p, len(p.bm.verts)) for p in parts]


def conform(marks, bvh, M, normal=None, reach=0.15):
    """Bend every vertex created since `marks` onto the surface in `bvh`: a vertex at local (x, y, z)
    of frame M is moved to (surface hit below M@(x, y, 0)) + normal * z. M must be unscaled."""
    Mi = M.inverted()
    n = (M.to_3x3() @ Vector((0, 0, 1))).normalized() if normal is None else Vector(normal).normalized()
    for p, n0 in marks:
        bm = p.bm
        bm.verts.ensure_lookup_table()
        for v in bm.verts[n0:]:
            loc = Mi @ v.co
            base = M @ Vector((loc.x, loc.y, 0.0))
            hit, _, _, _ = bvh.ray_cast(base + n * reach, -n, reach * 2)
            if hit is None:
                continue
            v.co = hit + n * loc.z


def dome(p, mat, loc, normal, r, h=None, seg=6, sink=0.003, x_hint=(1, 0, 0)):
    """Rivet head: low dome on a surface point (base sunk by `sink`), ~4*seg tris."""
    h = r * 0.6 if h is None else h
    M = mtx(loc, normal, x_hint)
    prof = [(r, -sink), (r * 0.93, h * 0.45), (r * 0.55, h * 0.88), (0.0, h)]
    return lathe_m(p, mat, prof, M, seg=seg, cap=(False, False))


def bolt(p, mat, loc, normal, r, h, sink=0.004, seg=6, x_hint=(1, 0, 0)):
    """Hex bolt head with a chamfered top."""
    M = mtx(loc, normal, x_hint)
    return lathe_m(p, mat, [(r, -sink), (r, h * 0.7), (r * 0.78, h), (0.0, h)], M, seg=seg,
                   cap=(True, False))


def ball(p, mat, loc, r, seg=12, rings=8, scale=(1, 1, 1), z_axis=(0, 0, 1), x_hint=(1, 0, 0)):
    M = mtx(loc, z_axis, x_hint, scale)
    res = bmesh.ops.create_uvsphere(p.bm, u_segments=seg, v_segments=rings, radius=r, matrix=M)
    fs = {f for v in res["verts"] for f in v.link_faces}
    set_mat(p, list(fs), mat)
    return res["verts"]


def disc(p, mat, M, r, h, seg=16, r_top=None, bevel=0.0):
    """Cylinder disc along local Z of M from z=0 to z=h (optional chamfer on the top edge)."""
    r_top = r if r_top is None else r_top
    prof = [(0.0, 0.0), (r, 0.0)]
    if bevel > 0:
        prof += [(r, h - bevel), (r_top - bevel, h)]
    else:
        prof += [(r_top, h)]
    prof.append((0.0, h))
    return lathe_m(p, mat, prof, M, seg=seg, cap=(False, False))


def torus_m(p, mat, M, R, r, seg=16, seg2=6, phase=0.0):
    bm = p.bm
    rings = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        ring = []
        for j in range(seg2):
            b = 2 * math.pi * j / seg2 + phase
            d = R + r * math.cos(b)
            ring.append(bm.verts.new(M @ Vector((d * math.cos(a), d * math.sin(a), r * math.sin(b)))))
        rings.append(ring)
    fs = []
    for i in range(seg):
        A, B = rings[i], rings[(i + 1) % seg]
        for j in range(seg2):
            k = (j + 1) % seg2
            fs.append(_face(bm, [A[j], A[k], B[k], B[j]]))
    set_mat(p, fs, mat)
    return rings


def gear_ring(p, mat, M, r_tip, r_root, teeth, thick, r_hole=0.0, spokes=0, hub=0.0, hub_h=None,
              spoke_w=None, tip=0.36, root=0.56, mat_hub=None, bottom=True, hub_seg=None):
    """Toothed gear in the local XY plane of M (axis = local Z, from z=0 to z=thick).
    r_hole > 0 -> ring gear with `spokes` spokes and a hub of radius `hub`."""
    bm = p.bm
    pitch = 2 * math.pi / teeth
    outline = []
    for i in range(teeth):
        a = pitch * i
        outline += [(r_root, a - pitch * root / 2), (r_tip, a - pitch * tip / 2),
                    (r_tip, a + pitch * tip / 2), (r_root, a + pitch * root / 2)]
    fs = []

    def pt(r, a, z):
        return M @ Vector((r * math.cos(a), r * math.sin(a), z))
    top = [bm.verts.new(pt(r, a, thick)) for (r, a) in outline]
    bot = [bm.verts.new(pt(r, a, 0.0)) for (r, a) in outline]
    n = len(outline)
    fs += strip(bm, bot, top, closed=True)        # outer wall
    if r_hole > 0:
        itop = [bm.verts.new(pt(r_hole, a, thick)) for (_, a) in outline]
        ibot = [bm.verts.new(pt(r_hole, a, 0.0)) for (_, a) in outline]
        fs += strip(bm, top, itop, closed=True)
        if bottom:
            fs += strip(bm, ibot, bot, closed=True)
        fs += strip(bm, itop, ibot, closed=True)  # inner wall
    else:
        fs.append(_face(bm, top))
        if bottom:
            fs.append(_face(bm, list(reversed(bot))))
    set_mat(p, fs, mat)
    if r_hole > 0 and spokes:
        sw = spoke_w or r_hole * 0.28
        for k in range(spokes):
            a = 2 * math.pi * k / spokes + pitch * 0.5
            c = Vector((math.cos(a), math.sin(a), 0)) * ((r_hole + hub) * 0.5)
            L = r_hole - hub + 0.004
            Rm = M @ Matrix.Translation(c) @ Matrix.Rotation(a, 4, "Z")
            res = bmesh.ops.create_cube(bm, size=1.0, matrix=Rm @ Matrix.Diagonal((L, sw, thick * 0.8, 1))
                                        @ Matrix.Translation((0, 0, 0.5)))
            set_mat(p, list({f for v in res["verts"] for f in v.link_faces}), mat)
    if hub > 0:
        hh = thick * 1.3 if hub_h is None else hub_h
        lathe_m(p, mat_hub or mat, [(hub, -0.001), (hub, hh), (hub * 0.55, hh + 0.003),
                                     (0.0, hh + 0.003)], M, seg=hub_seg or max(8, teeth), cap=(False, False))
    return p


def box_m(p, mat, M, size):
    res = bmesh.ops.create_cube(p.bm, size=1.0, matrix=M @ Matrix.Diagonal((size[0], size[1], size[2], 1)))
    set_mat(p, list({f for v in res["verts"] for f in v.link_faces}), mat)
    return res["verts"]


# ---------------------------------------------------------------------------------------
# Bone assembly
# ---------------------------------------------------------------------------------------
def join_objects(objs, name):
    main = objs[0]
    if len(objs) > 1:
        vl = bpy.context.view_layer
        for o in vl.objects:
            o.select_set(False)
        for o in objs:
            o.select_set(True)
        vl.objects.active = main
        with bpy.context.temp_override(active_object=main, object=main, selected_objects=objs,
                                       selected_editable_objects=objs):
            bpy.ops.object.join()
    main.name = name
    main.data.name = name
    return main


class BoneBuilder:
    """Collect geometry pieces (in WORLD coordinates) for one rigid part / bone.

        bb = BoneBuilder("body", pivot)
        p = bb.piece(smooth=35)                       # hard-surface piece
        q = bb.piece(smooth=80)                       # round piece (tubes, balls)
        r = bb.piece(smooth=30, bevel=dict(width=0.004, segments=2))
        obj = bb.build(parent_obj, parent_pivot)
    """

    def __init__(self, name, pivot):
        self.name = name
        self.pivot = Vector(pivot)
        self.pieces = []

    def piece(self, smooth=35.0, bevel=None, subdiv=0):
        p = Part(f"{self.name}__{len(self.pieces)}")
        self.pieces.append((p, dict(smooth=smooth, bevel=bevel, subdiv=subdiv)))
        return p

    def build(self, parent_obj=None, parent_pivot=(0, 0, 0)):
        objs = []
        for p, o in self.pieces:
            if not len(p.bm.verts):
                p.bm.free()
                continue
            bmesh.ops.remove_doubles(p.bm, verts=p.bm.verts[:], dist=1e-6)
            bmesh.ops.translate(p.bm, vec=-self.pivot, verts=p.bm.verts[:])
            ob = p.build(parent_obj, loc=tuple(self.pivot - Vector(parent_pivot)))
            if o["subdiv"]:
                hp.subdivide_obj(ob, levels=o["subdiv"])
            hp.smooth_obj(ob, o["smooth"])
            if o["bevel"]:
                hp.bevel_obj(ob, **o["bevel"])
            objs.append(ob)
        print(f"[bone] {self.name:10s} " + " ".join(f"{hp.obj_tris(o)}" for o in objs)
              + f" = {sum(hp.obj_tris(o) for o in objs)}")
        return join_objects(objs, self.name)


# ---------------------------------------------------------------------------------------
# Vertex AO with the machinery bay lit
# ---------------------------------------------------------------------------------------
def _read_col(me):
    a = me.color_attributes[hp.AO_ATTR]
    arr = np.empty(len(me.loops) * 4, dtype=np.float32)
    a.data.foreach_get("color", arr)
    return arr.reshape(-1, 4)


def bake_ao_open(skin, hide_groups=("shell_L", "shell_R"), lo=0.62, hi=0.32, **kw):
    """Two AO passes on the skinned mesh (rest pose):
       A: everything occludes (closed elytra)          -> normal look
       B: the elytra (vertex groups hide_groups) removed -> look when the shells are open
    Corners that A finds nearly enclosed (AO < lo .. hi) blend toward B, so the bay that is only
    ever seen with the shells open (gear core, folded wings) is not baked pitch black."""
    me = skin.data
    hp.bake_vertex_ao(objs=[skin], **kw)
    A = _read_col(me)
    # occluder copy without the shells
    tmp_me = me.copy()
    tmp = bpy.data.objects.new("_ao_noshell", tmp_me)
    bpy.context.scene.collection.objects.link(tmp)
    tmp.matrix_world = skin.matrix_world.copy()
    gi = [skin.vertex_groups[g].index for g in hide_groups if g in skin.vertex_groups]
    bm = bmesh.new()
    bm.from_mesh(tmp_me)
    dl = bm.verts.layers.deform.active
    kill = []
    if dl is not None:
        for v in bm.verts:
            w = sum(v[dl].get(g, 0.0) for g in gi)
            if w > 0.5:
                kill.append(v)
    bmesh.ops.delete(bm, geom=kill, context="VERTS")
    bm.to_mesh(tmp_me)
    bm.free()
    hp.bake_vertex_ao(objs=[skin], occluders=[tmp], **kw)
    B = _read_col(me)
    bpy.data.objects.remove(tmp)
    bpy.data.meshes.remove(tmp_me)
    lum = A[:, :3].mean(axis=1)
    t = np.clip((lo - lum) / (lo - hi), 0.0, 1.0)
    t = t * t * (3 - 2 * t)
    C = A.copy()
    C[:, :3] = A[:, :3] * (1 - t[:, None]) + B[:, :3] * t[:, None]
    me.color_attributes[hp.AO_ATTR].data.foreach_set("color", C.ravel())
    print(f"[ao] open-bay blend on {int((t > 0.01).sum())} / {len(t)} corners")
