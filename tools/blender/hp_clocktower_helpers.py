"""Geometry kit for the stopped clock tower (props_clocktower.py) (hi-poly).

Everything adds geometry straight into a common.Part's bmesh (like env_helpers) but takes an explicit
4x4 matrix M instead of loc/rot so whole facades can be modeled once in a *face-local frame* and
stamped onto the four sides of the tower:

    face frame (see frame_side):  local x = along the facade (viewer's right),
                                  local y = INTO the wall (outward = -y), local z = up,
                                  origin on the wall plane.

Per-vertex tint: parts made with new_part() carry a float vertex layer 'clk_tint' (default 0). It is
exported nowhere — props_clocktower multiplies (1 + tint) into the baked AO colours and then removes
the attribute (per-stone colour variation without textures).
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from common import Part, get_mat, _link
from env_helpers import set_mat, mtx

I4 = Matrix.Identity(4)
TINT = "clk_tint"
WARM = "clk_warm"


# ---------------------------------------------------------------------------
# parts / frames
# ---------------------------------------------------------------------------

def new_part(name):
    p = Part(name)
    p.bm.verts.layers.float.new(TINT)
    p.bm.verts.layers.float.new(WARM)
    return p


def build_part(p, parent=None, recalc=True):
    """Like Part.build but recalc_face_normals is optional (open decal geometry keeps its winding)."""
    mesh = bpy.data.meshes.new(p.name)
    if recalc:
        bmesh.ops.recalc_face_normals(p.bm, faces=p.bm.faces[:])
    p.bm.to_mesh(mesh)
    p.bm.free()
    for mn in p.mat_names:
        mesh.materials.append(get_mat(mn))
    obj = bpy.data.objects.new(p.name, mesh)
    _link(obj)
    obj.parent = parent
    return obj


def frame_side(k, hw=0.0, z=0.0):
    """Face-local frame of side k (0 = front -Y, 1 = +X, 2 = back +Y, 3 = -X), origin on the wall
    plane at distance hw from the axis, height z."""
    return Matrix.Rotation(math.radians(90 * k), 4, "Z") @ Matrix.Translation((0, -hw, z))


def T(x=0.0, y=0.0, z=0.0):
    return Matrix.Translation((x, y, z))


def R(axis, deg):
    return Matrix.Rotation(math.radians(deg), 4, axis)


def S(x, y=None, z=None):
    y = x if y is None else y
    z = x if z is None else z
    return Matrix.Diagonal((x, y, z, 1.0))


# Matrix that maps a primitive built around +Z (gears, lathes, discs) onto the facade normal:
# local +Z -> -Y (pointing out of the wall towards the viewer).
FACE_OUT = Matrix.Rotation(math.radians(90), 4, "X")


def island(verts):
    seen = set(v for v in verts if v.is_valid)
    stack = list(seen)
    while stack:
        v = stack.pop()
        for e in v.link_edges:
            o = e.other_vert(v)
            if o not in seen:
                seen.add(o)
                stack.append(o)
    return seen


def set_tint(p, verts, val):
    """val = brightness offset, or (brightness, warmth) — warmth > 0 pushes red up / blue down."""
    lay = p.bm.verts.layers.float.get(TINT)
    if lay is None:
        return
    warm = None
    if isinstance(val, (tuple, list)):
        val, warm = val
    lw = p.bm.verts.layers.float.get(WARM) if warm is not None else None
    for v in verts:
        v[lay] = val
        if lw is not None:
            v[lw] = warm


def _faces_of(verts):
    return list({f for v in verts for f in v.link_faces})


# ---------------------------------------------------------------------------
# primitives (all take a matrix M)
# ---------------------------------------------------------------------------

def cbox(p, mat, size, loc=(0, 0, 0), M=I4, rot=(0, 0, 0), bev=0.0, seg=1, prof=0.5, tint=None):
    """Box (size = full extents) with optional per-primitive bevel (bmesh, world units)."""
    Mx = M @ mtx(loc, rot, size)
    r = bmesh.ops.create_cube(p.bm, size=1.0, matrix=Mx)
    vs = r["verts"]
    set_mat(p, _faces_of(vs), mat)
    if bev > 0:
        es = list({e for v in vs for e in v.link_edges})
        res = bmesh.ops.bevel(p.bm, geom=vs + es, offset=bev, offset_type="OFFSET", segments=seg,
                              profile=prof, affect="EDGES", clamp_overlap=True)
        vs = list(res["verts"])
    isl = island(vs)
    if tint is not None:
        set_tint(p, isl, tint)
    return isl


def box_xyz(p, mat, x0, x1, y0, y1, z0, z1, M=I4, bev=0.0, seg=1, tint=None, prof=0.5):
    return cbox(p, mat, (x1 - x0, y1 - y0, z1 - z0), loc=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2),
                M=M, bev=bev, seg=seg, tint=tint, prof=prof)


def _inset(pts, d):
    """Inset a CCW polygon [(x, z)] by distance d (mitred offset along vertex bisectors)."""
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2 = Vector(pts[i - 1]), Vector(pts[i]), Vector(pts[(i + 1) % n])
        e0 = (p1 - p0).normalized()
        e1 = (p2 - p1).normalized()
        n0 = Vector((-e0.y, e0.x))           # inward normal for CCW
        n1 = Vector((-e1.y, e1.x))
        b = n0 + n1
        if b.length < 1e-6:
            b = n0
        b.normalize()
        c = max(0.35, b.dot(n0))
        q = p1 + b * (d / c)
        out.append((q.x, q.y))
    return out


def chamfer_prism(p, mat, pts, y0, y1, ch, M=I4, back=False, tint=None, side_mat=None):
    """Stone/plate cut from a 2D outline pts=[(x, z)]: front face at y0 (outward) inset by `ch` with a
    45 deg chamfer ring, straight sides back to y1. No back face unless back=True (wall-embedded).
    About half the triangles of a full bevel, with the same highlight on the visible edges."""
    pts = list(pts)
    if _signed_area(pts) < 0:
        pts.reverse()
    bm = p.bm
    ins = _inset(pts, ch)
    f = [bm.verts.new(M @ Vector((x, y0, z))) for x, z in ins]
    m = [bm.verts.new(M @ Vector((x, y0 + ch, z))) for x, z in pts]
    b = [bm.verts.new(M @ Vector((x, y1, z))) for x, z in pts]
    n = len(pts)
    faces = [bm.faces.new(f)]
    sides = []
    for i in range(n):
        j = (i + 1) % n
        faces.append(bm.faces.new((m[i], m[j], f[j], f[i])))
        sides.append(bm.faces.new((b[i], b[j], m[j], m[i])))
    if back:
        faces.append(bm.faces.new(list(reversed(b))))
    set_mat(p, faces, mat)
    set_mat(p, sides, side_mat or mat)
    if tint is not None:
        set_tint(p, f + m + b, tint)
    return f + m + b


def fbox(p, mat, x0, x1, y0, y1, z0, z1, ch, M=I4, back=False, tint=None):
    """Box whose front face (local -y, at y0) has chamfered edges; sides run back to y1 (y0 < y1)."""
    c = min(ch, (x1 - x0) * 0.3, (z1 - z0) * 0.3, (y1 - y0) * 0.8)
    return chamfer_prism(p, mat, [(x0, z0), (x1, z0), (x1, z1), (x0, z1)], y0, y1, c, M=M, back=back, tint=tint)


def bevel_island(p, verts, bev, seg=1, prof=0.5):
    vs = [v for v in island(verts)]
    es = list({e for v in vs for e in v.link_edges})
    res = bmesh.ops.bevel(p.bm, geom=vs + es, offset=bev, offset_type="OFFSET", segments=seg,
                          profile=prof, affect="EDGES", clamp_overlap=True)
    return island(list(res["verts"]) or vs)


def _signed_area(pts):
    a = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        a += x0 * y1 - x1 * y0
    return a / 2


def prism(p, mat, pts, y0, y1, M=I4, side_mat=None, bev=0.0, seg=1, tint=None, cap_back=True):
    """Extrude a 2D polygon pts=[(x, z)] (local facade plane) between y0 (front, outward) and y1 (back).
    Works for concave outlines (Blender polyfill triangulates the caps)."""
    pts = list(pts)
    if _signed_area(pts) < 0:
        pts.reverse()
    bm = p.bm
    a = [bm.verts.new(M @ Vector((x, y0, z))) for x, z in pts]
    b = [bm.verts.new(M @ Vector((x, y1, z))) for x, z in pts]
    n = len(pts)
    caps = [bm.faces.new(a)]          # CCW seen from -y -> normal -y
    if cap_back:
        caps.append(bm.faces.new(list(reversed(b))))
    sides = [bm.faces.new((a[i], b[i], b[(i + 1) % n], a[(i + 1) % n])) for i in range(n)]
    set_mat(p, caps, mat)
    set_mat(p, sides, side_mat or mat)
    vs = a + b
    if bev > 0:
        vs = list(bevel_island(p, vs, bev, seg))
    if tint is not None:
        set_tint(p, island(vs), tint)
    return vs


def prism_x(p, mat, pts, x0, x1, M=I4, bev=0.0, seg=1, tint=None):
    """Extrude a 2D profile pts=[(y, z)] along local x from x0 to x1 (consoles, brackets)."""
    pts = list(pts)
    if _signed_area(pts) < 0:
        pts.reverse()
    bm = p.bm
    a = [bm.verts.new(M @ Vector((x0, y, z))) for y, z in pts]
    b = [bm.verts.new(M @ Vector((x1, y, z))) for y, z in pts]
    n = len(pts)
    faces = [bm.faces.new(list(reversed(a))), bm.faces.new(b)]
    faces += [bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i])) for i in range(n)]
    set_mat(p, faces, mat)
    vs = a + b
    if bev > 0:
        vs = list(bevel_island(p, vs, bev, seg))
    if tint is not None:
        set_tint(p, island(vs), tint)
    return vs


def lathe_m(p, mat, prof, seg=16, M=I4, phase=0.0, cap0=True, cap1=True, mats=None, tints=None, closed=False):
    """Revolve [(z, r)] around local Z (r == 0 -> pole). mats: optional material per profile span.
    Outward normal = right of the travel direction in the (r, z) half plane (go up the outside).
    closed=True joins the last profile point back to the first (ring sections, no caps)."""
    bm = p.bm
    rings = []
    for z, r in prof:
        if r <= 1e-6:
            rings.append([bm.verts.new(M @ Vector((0, 0, z)))])
        else:
            rings.append([bm.verts.new(M @ Vector((r * math.cos(2 * math.pi * j / seg + phase),
                                                   r * math.sin(2 * math.pi * j / seg + phase), z)))
                          for j in range(seg)])
    by_mat = {}
    spans = [(i, i + 1) for i in range(len(rings) - 1)]
    if closed:
        spans.append((len(rings) - 1, 0))
        cap0 = cap1 = False
    for i, i2 in spans:
        a, b = rings[i], rings[i2]
        m = mats[min(i, len(mats) - 1)] if mats else mat
        for j in range(seg):
            k = (j + 1) % seg
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                f = bm.faces.new((a[0], b[k], b[j]))
            elif len(b) == 1:
                f = bm.faces.new((a[j], a[k], b[0]))
            else:
                f = bm.faces.new((a[j], a[k], b[k], b[j]))
            by_mat.setdefault(m, []).append(f)
    if cap0 and len(rings[0]) > 1:
        by_mat.setdefault(mat, []).append(bm.faces.new(list(reversed(rings[0]))))
    if cap1 and len(rings[-1]) > 1:
        by_mat.setdefault(mats[-1] if mats else mat, []).append(bm.faces.new(rings[-1]))
    for m, fs in by_mat.items():
        set_mat(p, fs, m)
    if tints:
        for ring, t in zip(rings, tints):
            set_tint(p, ring, t)
    return rings


def rlathe(p, mat, prof, hx=0.0, hy=None, M=I4, cap0=True, cap1=True, mats=None, tints=None):
    """Rectangular 'lathe': prof = [(z, out)] swept around the rectangle (hx+out, hy+out) with mitered
    corners (string courses, cornices, plinths, the bell-cast roof)."""
    hy = hx if hy is None else hy
    bm = p.bm
    rings = []
    for z, o in prof:
        X, Y = hx + o, hy + o
        if X <= 1e-6 and Y <= 1e-6:
            rings.append([bm.verts.new(M @ Vector((0, 0, z)))])
        else:
            rings.append([bm.verts.new(M @ Vector(c)) for c in ((X, -Y, z), (X, Y, z), (-X, Y, z), (-X, -Y, z))])
    by_mat = {}
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        m = mats[i] if mats else mat
        for j in range(4):
            k = (j + 1) % 4
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                f = bm.faces.new((a[0], b[k], b[j]))
            elif len(b) == 1:
                f = bm.faces.new((a[j], a[k], b[0]))
            else:
                f = bm.faces.new((a[j], a[k], b[k], b[j]))
            by_mat.setdefault(m, []).append(f)
    if cap0 and len(rings[0]) > 1:
        by_mat.setdefault(mat, []).append(bm.faces.new(list(reversed(rings[0]))))
    if cap1 and len(rings[-1]) > 1:
        by_mat.setdefault(mats[-1] if mats else mat, []).append(bm.faces.new(rings[-1]))
    for m, fs in by_mat.items():
        set_mat(p, fs, m)
    if tints:
        for ring, t in zip(rings, tints):
            set_tint(p, ring, t)
    return rings


def mold_run(p, mat, prof, x0, x1, M=I4, miter0=False, miter1=False, tint=None):
    """Molding along local x on a facade: prof = [(z, out)] (out = distance in front of the wall,
    i.e. local y = -out). Mitered ends follow a 45 deg corner (x shifted by out); butt ends are capped."""
    bm = p.bm
    a, b = [], []
    for z, o in prof:
        xa = x0 - o if miter0 else x0
        xb = x1 + o if miter1 else x1
        a.append(bm.verts.new(M @ Vector((xa, -o, z))))
        b.append(bm.verts.new(M @ Vector((xb, -o, z))))
    n = len(prof)
    faces = []
    for i in range(n - 1):
        faces.append(bm.faces.new((a[i], b[i], b[i + 1], a[i + 1])))
    # close back (wall side) + caps
    faces.append(bm.faces.new((a[-1], b[-1], b[0], a[0])))
    faces.append(bm.faces.new(a))
    faces.append(bm.faces.new(list(reversed(b))))
    set_mat(p, faces, mat)
    # make caps/sides consistently outward
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    if tint is not None:
        set_tint(p, a + b, tint)
    return a + b


def torus_m(p, mat, R_, r, seg=24, seg2=8, M=I4, phase=0.0, arc=None, caps=True, scale_minor=(1.0, 1.0)):
    """Torus in local XY (axis Z). arc=(a0, a1) degrees for an open arc (capped ends)."""
    bm = p.bm
    rings = []
    closed = arc is None
    n = seg if closed else seg + 1
    for i in range(n):
        if closed:
            a = 2 * math.pi * i / seg
        else:
            a = math.radians(arc[0] + (arc[1] - arc[0]) * i / seg)
        ring = []
        for j in range(seg2):
            b = 2 * math.pi * j / seg2 + phase
            d = R_ + r * scale_minor[0] * math.cos(b)
            ring.append(bm.verts.new(M @ Vector((d * math.cos(a), d * math.sin(a), r * scale_minor[1] * math.sin(b)))))
        rings.append(ring)
    faces = []
    for i in range(seg if closed else seg):
        A, B = rings[i], rings[(i + 1) % n]
        for j in range(seg2):
            k = (j + 1) % seg2
            faces.append(bm.faces.new((A[j], B[j], B[k], A[k])))
    if not closed and caps:
        faces.append(bm.faces.new(list(reversed(rings[0]))))
        faces.append(bm.faces.new(rings[-1]))
    set_mat(p, faces, mat)
    return rings


def tube(p, mat, pts, r=0.1, seg=8, M=I4, radii=None, cap0=True, cap1=True):
    """Circle swept along a polyline (parallel transport)."""
    pts = [M @ Vector(q) for q in pts]
    n = len(pts)
    radii = radii or [r] * n
    tans = []
    for i in range(n):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = (pts[i + 1] - pts[i]).normalized() + (pts[i] - pts[i - 1]).normalized()
        tans.append(t.normalized())
    t0 = tans[0]
    ref = Vector((0, 1, 0)) if abs(t0.y) < 0.9 else Vector((1, 0, 0))
    nrm = ref.cross(t0).normalized()
    bm = p.bm
    rings = []
    for i in range(n):
        if i > 0:
            ax = tans[i - 1].cross(tans[i])
            if ax.length > 1e-9:
                nrm = (Matrix.Rotation(tans[i - 1].angle(tans[i]), 3, ax.normalized()) @ nrm).normalized()
        bi = tans[i].cross(nrm)
        ring = []
        for j in range(seg):
            a = 2 * math.pi * j / seg + math.pi / seg
            off = nrm * math.cos(a) + bi * math.sin(a)
            ring.append(bm.verts.new(pts[i] + off * radii[i]))
        rings.append(ring)
    faces = []
    for i in range(n - 1):
        A, B = rings[i], rings[i + 1]
        for j in range(seg):
            k2 = (j + 1) % seg
            faces.append(bm.faces.new((A[j], A[k2], B[k2], B[j])))
    if cap0:
        faces.append(bm.faces.new(list(reversed(rings[0]))))
    if cap1:
        faces.append(bm.faces.new(rings[-1]))
    set_mat(p, faces, mat)
    return rings


def bend_pts(p0, corner, p1, r, n=6):
    """Rounded polyline corner: straight from p0 to corner to p1 with an arc of radius r."""
    p0, c, p1 = Vector(p0), Vector(corner), Vector(p1)
    d0 = (c - p0).normalized()
    d1 = (p1 - c).normalized()
    ang = d0.angle(d1)
    if ang < 1e-4:
        return [tuple(c)]
    t = r * math.tan(ang / 2)
    a = c - d0 * t
    b = c + d1 * t
    out = []
    for i in range(n + 1):
        u = i / n
        # quadratic bezier approximates the arc well for 90 deg
        q = a * (1 - u) ** 2 + c * 2 * u * (1 - u) + b * u * u
        out.append(tuple(q))
    return out


def gear(p, mat, r_root, r_tip, teeth, th, r_in=0.0, M=I4, ht=0.17, hb=0.28, back=True, inner=True,
         phase=0.0):
    """Gear in local XY plane, axis Z, thickness th centred on z=0. Trapezoid teeth (4 outline points
    per tooth). r_in > 0 -> annulus (rim), else solid disc (centre fan)."""
    bm = p.bm
    P = 2 * math.pi / teeth
    outline = []
    for i in range(teeth):
        a = P * i + phase
        for ang, rr in ((a - hb * P, r_root), (a - ht * P, r_tip), (a + ht * P, r_tip), (a + hb * P, r_root)):
            outline.append((ang, rr))
    zf, zb = th / 2, -th / 2
    of = [bm.verts.new(M @ Vector((rr * math.cos(a), rr * math.sin(a), zf))) for a, rr in outline]
    ob = [bm.verts.new(M @ Vector((rr * math.cos(a), rr * math.sin(a), zb))) for a, rr in outline]
    n = len(outline)
    faces = []
    if r_in > 0:
        inf = [bm.verts.new(M @ Vector((r_in * math.cos(a), r_in * math.sin(a), zf))) for a, _ in outline]
        inb = [bm.verts.new(M @ Vector((r_in * math.cos(a), r_in * math.sin(a), zb))) for a, _ in outline]
        for j in range(n):
            k = (j + 1) % n
            faces.append(bm.faces.new((of[j], of[k], inf[k], inf[j])))          # front (+z)
            if back:
                faces.append(bm.faces.new((inb[j], inb[k], ob[k], ob[j])))      # back (-z)
            if inner:
                faces.append(bm.faces.new((inf[j], inf[k], inb[k], inb[j])))    # bore (faces the axis)
    else:
        cf = bm.verts.new(M @ Vector((0, 0, zf)))
        cb = bm.verts.new(M @ Vector((0, 0, zb)))
        for j in range(n):
            k = (j + 1) % n
            faces.append(bm.faces.new((cf, of[j], of[k])))
            if back:
                faces.append(bm.faces.new((cb, ob[k], ob[j])))
    for j in range(n):
        k = (j + 1) % n
        faces.append(bm.faces.new((of[j], ob[j], ob[k], of[k])))
    set_mat(p, faces, mat)
    return of + ob


def gear_wheel(p, mat, r, teeth, th, M=I4, tooth=None, rim=0.17, spokes=5, hub=0.2, hub_mat=None,
               spoke_mat=None, phase=0.0, back=True):
    """Spoked gear wheel (rim + teeth, bar spokes, chamfered hub boss) in local XY, axis Z."""
    tooth = tooth or r * 0.14
    r_in = r * (1 - rim)
    gear(p, mat, r, r + tooth, teeth, th, r_in=r_in, M=M, phase=phase, back=back)
    hr = r * hub
    for i in range(spokes):
        a = 2 * math.pi * i / spokes + phase + math.pi / teeth
        mid = (hr + r_in) / 2 * 0.98
        L = r_in - hr * 0.6
        cbox(p, spoke_mat or mat, (L, r * 0.09, th * 0.62),
             loc=(math.cos(a) * mid, math.sin(a) * mid, 0), M=M, rot=(0, 0, math.degrees(a)))
    lathe_m(p, hub_mat or mat, [(-th * 0.75, hr), (th * 0.6, hr), (th * 0.85, hr * 0.75),
                                (th * 1.0, hr * 0.3), (th * 1.0, 0.0)], seg=10, M=M, cap0=False)


def disc(p, mat, r, y, M=I4, seg=48, r_in=0.0, a0=0.0, a1=360.0):
    """Flat (decal) disc / annulus / sector facing -y in the facade plane at depth y (single-sided)."""
    bm = p.bm
    full = abs(a1 - a0) >= 359.999
    n = seg if full else seg + 1
    angs = [math.radians(a0 + (a1 - a0) * i / seg) for i in range(n)]
    outer = [bm.verts.new(M @ Vector((r * math.sin(a), y, r * math.cos(a)))) for a in angs]
    faces = []
    if r_in > 0:
        inner = [bm.verts.new(M @ Vector((r_in * math.sin(a), y, r_in * math.cos(a)))) for a in angs]
        rng = range(seg) if full else range(seg)
        for j in rng:
            k = (j + 1) % n
            # clockwise angle param (sin, cos) -> winding chosen so the normal points -y
            faces.append(bm.faces.new((inner[j], inner[k], outer[k], outer[j])))
    else:
        c = bm.verts.new(M @ Vector((0, y, 0)))
        for j in range(seg):
            k = (j + 1) % n
            faces.append(bm.faces.new((c, outer[j], outer[k])))
    _orient(faces, M, Vector((0, -1, 0)))
    set_mat(p, faces, mat)
    return faces


def _orient(faces, M, want_local):
    """Flip faces whose normal disagrees with the desired (local) direction."""
    w = (M.to_3x3() @ want_local).normalized()
    for f in faces:
        f.normal_update()
        if f.normal.dot(w) < 0:
            f.normal_flip()


def bar2d(p, mat, a, b, w, y, M=I4):
    """Decal strip from 2D point a to b (facade x, z) of width w at depth y, facing -y."""
    a, b = Vector(a), Vector(b)
    d = (b - a)
    if d.length < 1e-6:
        return None
    d.normalize()
    nrm = Vector((-d.y, d.x)) * (w / 2)
    q = [a + nrm, a - nrm, b - nrm, b + nrm]
    bm = p.bm
    vs = [bm.verts.new(M @ Vector((c.x, y, c.y))) for c in q]
    f = bm.faces.new(vs)
    _orient([f], M, Vector((0, -1, 0)))
    set_mat(p, [f], mat)
    return f


def poly2d(p, mat, pts, y, M=I4):
    """Single-sided flat polygon in the facade plane at depth y, facing -y."""
    bm = p.bm
    vs = [bm.verts.new(M @ Vector((x, y, z))) for x, z in pts]
    f = bm.faces.new(vs)
    _orient([f], M, Vector((0, -1, 0)))
    set_mat(p, [f], mat)
    return f


def arch_outline(cx, z0, w, zs, n=10, close_bottom=True):
    """Round-arch opening outline (x, z): sill z0, jambs to spring zs, semicircle of radius w/2."""
    r = w / 2
    pts = [(cx - r, z0), (cx + r, z0)] if close_bottom else []
    for i in range(n + 1):
        a = math.pi * i / n
        pts.append((cx + r * math.cos(a), zs + r * math.sin(a)))
    return pts


def notched_wall(x0, x1, z0, z1, openings, n=10):
    """Polygon (x, z) of a wall band [x0,x1]x[z0,z1] with round-arched notches cut up from its bottom
    edge: openings = [(cx, w, zs)] (sill = z0, spring zs, radius w/2), sorted by cx."""
    pts = [(x0, z0)]
    for cx, w, zs in sorted(openings):
        r = w / 2
        pts.append((cx - r, z0))
        pts.append((cx - r, zs))
        for i in range(1, n):
            a = math.pi - math.pi * i / n
            pts.append((cx + r * math.cos(a), zs + r * math.sin(a)))
        pts.append((cx + r, zs))
        pts.append((cx + r, z0))
    pts += [(x1, z0), (x1, z1), (x0, z1)]
    return pts


def leaf_quad(p, mat, base, direction, normal, size, fold=0.25):
    """Ivy leaf: 4-vertex folded diamond (2 tris), single-sided, facing `normal`."""
    base, d, nrm = Vector(base), Vector(direction).normalized(), Vector(normal).normalized()
    side = d.cross(nrm).normalized()
    L, W = size, size * 0.7
    tip = base + d * L
    mid = base + d * (L * 0.45)
    l = mid + side * (W / 2) - nrm * (W * fold * 0.5)
    r = mid - side * (W / 2) - nrm * (W * fold * 0.5)
    bm = p.bm
    vb, vr, vt, vl = (bm.verts.new(c) for c in (base, r, tip, l))
    f = bm.faces.new((vb, vr, vt, vl))
    f.normal_update()
    if f.normal.dot(nrm) < 0:
        f.normal_flip()
    set_mat(p, [f], mat)
    return f


def hand_outline(kind):
    """Ornate clock-hand outline (x, z), pointing +z, pivot at the origin."""
    def circ(cx, cz, r, a0, a1, n):
        return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                 cz + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
    if kind == "hour":
        # counterweight disc tail, tapered shaft, broad spade sweeping into a point
        right = [(0.0, -0.272)]
        right += circ(0, -0.20, 0.072, -90, 62, 9)[1:]
        right += [(0.024, -0.135), (0.030, -0.08), (0.042, 0.0), (0.032, 0.40), (0.040, 0.452), (0.075, 0.458),
                  (0.105, 0.475), (0.130, 0.508), (0.140, 0.555), (0.130, 0.605), (0.104, 0.652), (0.072, 0.702),
                  (0.040, 0.755), (0.016, 0.81), (0.0, 0.86)]
    else:
        right = [(0.0, -0.34)]
        right += circ(0, -0.28, 0.06, -90, 62, 9)[1:]
        right += [(0.020, -0.21), (0.026, -0.12), (0.030, 0.0), (0.018, 0.88), (0.030, 0.905), (0.052, 0.93),
                  (0.064, 0.965), (0.055, 1.0), (0.036, 1.04), (0.018, 1.08), (0.0, 1.21)]
    left = [(-x, z) for x, z in reversed(right[1:-1])]
    return right + left


def glyph_bars(ch, H):
    """Roman numeral glyph strokes (u right, v up), centred horizontally, baseline v=0."""
    if ch == "I":
        return 0.045, [((0, 0), (0, H))]
    if ch == "V":
        hw = 0.058
        return 0.12, [((-hw, H), (0, 0)), ((hw, H), (0, 0))]
    if ch == "X":
        hw = 0.058
        return 0.12, [((-hw, 0), (hw, H)), ((hw, 0), (-hw, H))]
    raise ValueError(ch)


def numeral(p, mat, text, center, up, H, w, y, M=I4, gap=0.012):
    """Roman numeral on the dial: glyph baseline centred on `center` (x, z), glyph 'up' = `up` (unit
    2D vector), strokes width w, decal at depth y."""
    glyphs = [glyph_bars(c, H) for c in text]
    total = sum(g[0] for g in glyphs) + gap * (len(glyphs) - 1)
    up = Vector(up).normalized()
    right = Vector((up.y, -up.x))
    c0 = Vector(center)
    u = -total / 2
    for adv, bars in glyphs:
        cu = u + adv / 2
        for (a, b) in bars:
            pa = c0 + right * (cu + a[0]) + up * a[1]
            pb = c0 + right * (cu + b[0]) + up * b[1]
            bar2d(p, mat, pa, pb, w, y, M)
        # serifs (thin caps top and bottom)
        u += adv + gap
    # top / bottom serif rules spanning the numeral
    for v in (0.0, H):
        pa = c0 + right * (-total / 2 - 0.012) + up * v
        pb = c0 + right * (total / 2 + 0.012) + up * v
        bar2d(p, mat, pa, pb, w * 0.45, y - 0.001, M)
