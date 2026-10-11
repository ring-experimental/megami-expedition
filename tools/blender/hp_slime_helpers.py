"""Helpers for the hi-poly Boiler Jelly (model_slime.py) — own module, builds on common / hp_helpers
without modifying them.

    revolve(p, mat, prof, seg, closed=False, M=None)   surface of revolution around local Z (open or closed
                                                       cross-section, r == 0 -> pole), optional 4x4 transform
    disc(p, mat, r, z, seg, M)                         flat n-gon (fan) facing +Z
    arc_strip(p, mat, r0, r1, a0, a1, z, seg, M)       flat ring sector facing +Z (dial zones)
    flat_quad(p, mat, cx, cy, w, h, ang, z, M)         flat rectangle facing +Z, rotated by ang (dial ticks)
    frame(normal, up)                                  4x4 rotation: local +Z -> normal, local +Y -> ~up
    orient(n)                                          euler (deg) turning +Z onto n (for Part.cyl/sphere rot=)
    xform(p, M)                                        transform everything accumulated in a Part so far
    build_comp(p, ...)                                 build a Part as a loose component object
    join(objs, name, pivot)                            join components into one object, origin at pivot
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from common import Part, _link  # noqa: F401


def _M(M):
    return Matrix.Identity(4) if M is None else M


def revolve(p, mat, prof, seg=24, closed=False, M=None, phase=0.0, cap0=False, cap1=False):
    """Revolve profile [(r, z), ...] around local Z. closed=True joins last -> first section
    (torus-like cross-sections). r <= 1e-6 makes a pole. cap0/cap1 put n-gon caps on open ends."""
    M = _M(M)
    bm = p.bm
    rings = []
    allv = []
    for (r, z) in prof:
        if r <= 1e-6:
            v = bm.verts.new(M @ Vector((0.0, 0.0, z)))
            rings.append([v])
            allv.append(v)
            continue
        ring = [bm.verts.new(M @ Vector((r * math.cos(2 * math.pi * i / seg + phase),
                                         r * math.sin(2 * math.pi * i / seg + phase), z)))
                for i in range(seg)]
        rings.append(ring)
        allv += ring
    n = len(rings)
    pairs = [(k, k + 1) for k in range(n - 1)]
    if closed:
        pairs.append((n - 1, 0))
    for a, b in pairs:
        A, B = rings[a], rings[b]
        if len(A) == 1 and len(B) == 1:
            continue
        for i in range(seg):
            j = (i + 1) % seg
            if len(A) == 1:
                bm.faces.new((A[0], B[i], B[j]))
            elif len(B) == 1:
                bm.faces.new((A[i], A[j], B[0]))
            else:
                bm.faces.new((A[i], A[j], B[j], B[i]))
    if cap0 and len(rings[0]) > 2:
        bm.faces.new(list(reversed(rings[0])))
    if cap1 and len(rings[-1]) > 2:
        bm.faces.new(rings[-1])
    return p._assign(allv, mat)


def disc(p, mat, r, z=0.0, seg=24, M=None, cx=0.0, cy=0.0, fan=False):
    """Flat disc facing +Z. fan=True adds a centre vertex (triangle fan, seg tris) so vertex colours
    can vary from the centre to the rim; otherwise a single n-gon."""
    M = _M(M)
    vs = [p.bm.verts.new(M @ Vector((cx + r * math.cos(2 * math.pi * i / seg),
                                     cy + r * math.sin(2 * math.pi * i / seg), z))) for i in range(seg)]
    if fan:
        c = p.bm.verts.new(M @ Vector((cx, cy, z)))
        for i in range(seg):
            p.bm.faces.new((c, vs[i], vs[(i + 1) % seg]))
        vs.append(c)
    else:
        p.bm.faces.new(vs)
    return p._assign(vs, mat)


def radial_colour(obj, centre, axis, radius, edge=0.78, start=0.55):
    """'Col' for a dial-like decal: 1 in the middle, fading to `edge` at `radius` from the axis
    (fakes the soft shadow of a surrounding bezel without needing interior vertices for AO rays)."""
    import numpy as np
    me = obj.data
    if "Col" in me.color_attributes:
        me.color_attributes.remove(me.color_attributes["Col"])
    attr = me.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
    C, A = Vector(centre), Vector(axis).normalized()
    vals = np.ones((len(me.vertices), 4), dtype=np.float32)
    for v in me.vertices:
        d = obj.matrix_world @ v.co - C
        r = (d - A * d.dot(A)).length / radius
        t = max(0.0, min(1.0, (r - start) / (1.0 - start)))
        g = 1.0 - (1.0 - edge) * t * t
        vals[v.index, :3] = g
    lv = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get("vertex_index", lv)
    attr.data.foreach_set("color", vals[lv].ravel())
    me.color_attributes.active_color = attr
    me.color_attributes.render_color_index = me.color_attributes.find("Col")


def arc_strip(p, mat, r0, r1, a0, a1, z=0.0, seg=8, M=None):
    """Flat ring sector between radii r0 < r1 and angles a0 -> a1 (radians, CCW from +X)."""
    M = _M(M)
    inner, outer = [], []
    for i in range(seg + 1):
        a = a0 + (a1 - a0) * i / seg
        inner.append(p.bm.verts.new(M @ Vector((r0 * math.cos(a), r0 * math.sin(a), z))))
        outer.append(p.bm.verts.new(M @ Vector((r1 * math.cos(a), r1 * math.sin(a), z))))
    for i in range(seg):
        f = (inner[i], outer[i], outer[i + 1], inner[i + 1])
        if a1 < a0:
            f = tuple(reversed(f))
        p.bm.faces.new(f)
    return p._assign(inner + outer, mat)


def flat_quad(p, mat, cx, cy, w, h, ang=0.0, z=0.0, M=None):
    """Rectangle w (along the rotated x) x h (along the rotated y) centred at (cx, cy), facing +Z."""
    M = _M(M)
    ca, sa = math.cos(ang), math.sin(ang)
    pts = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    vs = [p.bm.verts.new(M @ Vector((cx + x * ca - y * sa, cy + x * sa + y * ca, z))) for (x, y) in pts]
    p.bm.faces.new(vs)
    return p._assign(vs, mat)


def flat_poly(p, mat, pts, z=0.0, thick=0.0, M=None):
    """Flat polygon [(x, y), ...] (CCW, convex) facing +Z; thick > 0 extrudes it downward (-Z)."""
    M = _M(M)
    top = [p.bm.verts.new(M @ Vector((x, y, z))) for (x, y) in pts]
    p.bm.faces.new(top)
    allv = list(top)
    if thick > 0:
        bot = [p.bm.verts.new(M @ Vector((x, y, z - thick))) for (x, y) in pts]
        p.bm.faces.new(list(reversed(bot)))
        n = len(pts)
        for i in range(n):
            j = (i + 1) % n
            p.bm.faces.new((bot[i], bot[j], top[j], top[i]))
        allv += bot
    return p._assign(allv, mat)


def frame(normal, up=(0, 0, 1), origin=(0, 0, 0)):
    """4x4 matrix whose local +Z points along `normal` and local +Y towards `up` (orthogonalised)."""
    z = Vector(normal).normalized()
    u = Vector(up)
    y = (u - z * u.dot(z))
    if y.length < 1e-6:
        y = Vector((0, 1, 0)) - z * z.y
    y.normalize()
    x = y.cross(z)
    R = Matrix((x, y, z)).transposed().to_4x4()
    return Matrix.Translation(Vector(origin)) @ R


def orient(n):
    """Euler angles (degrees, XYZ) that rotate +Z onto direction n (for Part primitives' rot=)."""
    q = Vector((0, 0, 1)).rotation_difference(Vector(n).normalized())
    e = q.to_euler("XYZ")
    return tuple(math.degrees(a) for a in e)


def xform(p, M):
    bmesh.ops.transform(p.bm, matrix=M, verts=p.bm.verts[:])
    return p


def build_comp(p):
    """Build a Part as a loose top-level object at the origin (world coords == model coords)."""
    return p.build(None, loc=(0, 0, 0))


def join(objs, name, pivot=(0, 0, 0)):
    """Join mesh objects (keeps materials, sharp edges, custom normals and the 'Col' attribute) into
    one object called `name` whose origin sits at `pivot` (geometry stays where it is in the world)."""
    objs = [o for o in objs if o is not None]
    tgt = objs[0]
    if len(objs) > 1:
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = tgt
        with bpy.context.temp_override(active_object=tgt, object=tgt, selected_objects=objs,
                                       selected_editable_objects=objs):
            bpy.ops.object.join()
    pv = Vector(pivot)
    tgt.data.transform(Matrix.Translation(-pv))
    tgt.location = pv
    tgt.name = name
    tgt.data.name = name
    return tgt


def orient_sheet(obj, direction, mats=None):
    """Flip faces (optionally only those with a material in `mats`) whose normal points against
    `direction`. Part.build's recalc_face_normals can't tell the outside of an open sheet (dial
    discs, decals), and a flipped sheet would also wreck its AO (rays shot into the backing)."""
    me = obj.data
    names = [m.name if m else "" for m in me.materials]
    d = Vector(direction).normalized()
    bm = bmesh.new()
    bm.from_mesh(me)
    flip = [f for f in bm.faces if (mats is None or names[f.material_index] in mats) and f.normal.dot(d) < 0]
    if flip:
        bmesh.ops.reverse_faces(bm, faces=flip)
        bm.to_mesh(me)
    bm.free()
    me.update()
    return len(flip)


def tris(obj):
    return sum(len(f.vertices) - 2 for f in obj.data.polygons)
