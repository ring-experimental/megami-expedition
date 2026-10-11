"""Extra geometry helpers for environment models (props / arena).

Builds on common.Part (adds geometry straight into part.bm). Kept separate from
common.py so the character pipeline is untouched.

All helpers take material *names* (palette names or custom names registered with
get_mat(name, hex=...) before the Part is built).
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from common import Part, get_mat, empty, _mtx  # noqa: F401  (re-exported for convenience)


# ---------------------------------------------------------------------------
# small utils
# ---------------------------------------------------------------------------

def mtx(loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    """4x4 matrix from loc / rot (degrees, XYZ euler) / scale."""
    return _mtx(loc, rot, scale)


def set_mat(part, faces, mat):
    mi = part._mi(mat)
    for f in faces:
        f.material_index = mi
        f.smooth = False


class Xform:
    """Context manager: every vertex added to `part` inside the block is transformed by M.

        with Xform(p, mtx((0, -2, 10), (0, 0, 90))):
            p.box(...)   # modeled in the local frame
    Nested blocks compose (inner first)."""

    # NOTE: bmesh ops free temporary verts (e.g. cylinder cap centers) and later allocations
    # reuse those slots, so "verts after index n" is NOT reliable. Instead, pre-existing verts are
    # stamped with the nesting depth in a temporary int layer; new verts have the default 0.
    _LAYER = "_xform_stamp"

    def __init__(self, part, M):
        self.part = part
        self.M = M

    def __enter__(self):
        bm = self.part.bm
        lay = bm.verts.layers.int.get(self._LAYER) or bm.verts.layers.int.new(self._LAYER)
        self.depth = getattr(self.part, "_xform_depth", 0) + 1
        self.part._xform_depth = self.depth
        for v in bm.verts:
            if v[lay] == 0:
                v[lay] = self.depth
        return self

    def __exit__(self, *exc):
        bm = self.part.bm
        lay = bm.verts.layers.int.get(self._LAYER)
        for v in bm.verts:
            s = v[lay]
            if s == 0:
                v.co = self.M @ v.co
            elif s == self.depth:
                v[lay] = 0
        self.part._xform_depth = self.depth - 1
        if self.depth == 1:
            bm.verts.layers.int.remove(lay)
        return False


def box_m(part, mat, M):
    """Unit cube transformed by an arbitrary matrix."""
    r = bmesh.ops.create_cube(part.bm, size=1.0, matrix=M)
    return part._assign(r["verts"], mat)


# ---------------------------------------------------------------------------
# organic
# ---------------------------------------------------------------------------

def jitter_ico(part, mat, r=1.0, subdiv=2, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1),
               amount=0.18, seed=0, floor=None, top_mat=None, top_thresh=0.7,
               bottom_mat=None, bottom_thresh=-0.35):
    """Faceted blob: icosphere with deterministic radial + tangential jitter.
    NOTE Blender 5.x: subdiv=1 is a plain icosahedron (20 tris), subdiv=2 -> 80 tris.
    floor: clamp vertices below this world z (flat base that sits on the ground).
    top_mat / bottom_mat: material for faces whose normal.z is above top_thresh / below
    bottom_thresh (moss caps on rocks, darker undersides on foliage)."""
    rng = random.Random(seed)
    res = bmesh.ops.create_icosphere(part.bm, subdivisions=subdiv, radius=r,
                                     matrix=Matrix.Identity(4))
    vs = res["verts"]
    for v in vs:
        k = 1.0 + rng.uniform(-amount, amount)
        t = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * amount * 0.3 * r
        v.co = v.co * k + t
    M = mtx(loc, rot, scale)
    for v in vs:
        v.co = M @ v.co
    if floor is not None:
        for v in vs:
            if v.co.z < floor:
                v.co.z = floor
    part._assign(vs, mat)
    if top_mat or bottom_mat:
        faces = {f for v in vs for f in v.link_faces}
        top, bot = [], []
        for f in faces:
            f.normal_update()
            if top_mat and f.normal.z > top_thresh:
                top.append(f)
            elif bottom_mat and f.normal.z < bottom_thresh:
                bot.append(f)
        if top:
            set_mat(part, top, top_mat)
        if bot:
            set_mat(part, bot, bottom_mat)
    return vs


# ---------------------------------------------------------------------------
# tubes / revolves / extrusions
# ---------------------------------------------------------------------------

def tube_path(part, mat, pts, r=0.1, seg=8, radii=None, cap_start=True, cap_end=True,
              jag=0.0, seed=0, phase=None):
    """Sweep a circle along a polyline (parallel-transport frames).
    Use several points along bends. jag>0 makes the end ring jagged (broken pipe)."""
    pts = [Vector(p) for p in pts]
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
    ph = (math.pi / seg) if phase is None else phase
    rng = random.Random(seed)
    rings = []
    bm = part.bm
    for i in range(n):
        if i > 0:
            ax = tans[i - 1].cross(tans[i])
            if ax.length > 1e-9:
                ang = tans[i - 1].angle(tans[i])
                nrm = (Matrix.Rotation(ang, 3, ax.normalized()) @ nrm).normalized()
        bi = tans[i].cross(nrm)
        ring = []
        for j in range(seg):
            a = 2 * math.pi * j / seg + ph
            p = pts[i] + (nrm * math.cos(a) + bi * math.sin(a)) * radii[i]
            if jag and i == n - 1:
                p = p + tans[i] * rng.uniform(-jag, jag)
            ring.append(bm.verts.new(p))
        rings.append(ring)
    faces = []
    for i in range(n - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(seg):
            k = (j + 1) % seg
            faces.append(bm.faces.new((a[j], a[k], b[k], b[j])))
    if cap_start:
        faces.append(bm.faces.new(list(reversed(rings[0]))))
    if cap_end:
        faces.append(bm.faces.new(rings[-1]))
    set_mat(part, faces, mat)
    return rings


def arc_pts(center, radius, a0, a1, n, plane="XZ"):
    """Points on a circular arc (degrees, inclusive), plane XZ (default), XY or YZ."""
    cx, cy, cz = center
    out = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        c, s = math.cos(a) * radius, math.sin(a) * radius
        if plane == "XZ":
            out.append((cx + c, cy, cz + s))
        elif plane == "XY":
            out.append((cx + c, cy + s, cz))
        else:
            out.append((cx, cy + c, cz + s))
    return out


def hollow_tube(part, mat, r_out, r_in, h, seg=12, loc=(0, 0, 0), rot=(0, 0, 0), mat_in=None):
    """Thick-walled open pipe along local Z, centered on loc (closed manifold)."""
    M = mtx(loc, rot)
    bm = part.bm

    def ring(r, z):
        return [bm.verts.new(M @ Vector((r * math.cos(2 * math.pi * j / seg),
                                         r * math.sin(2 * math.pi * j / seg), z)))
                for j in range(seg)]

    o0, o1 = ring(r_out, -h / 2), ring(r_out, h / 2)
    i0, i1 = ring(r_in, -h / 2), ring(r_in, h / 2)
    outer, inner = [], []
    for j in range(seg):
        k = (j + 1) % seg
        outer.append(bm.faces.new((o0[j], o0[k], o1[k], o1[j])))
        inner.append(bm.faces.new((i0[j], i1[j], i1[k], i0[k])))
        outer.append(bm.faces.new((o1[j], o1[k], i1[k], i1[j])))
        outer.append(bm.faces.new((o0[j], i0[j], i0[k], o0[k])))
    set_mat(part, outer, mat)
    set_mat(part, inner, mat_in or mat)


def lathe(part, mat, profile, seg=12, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1),
          mat_alt=None, alt_every=1, cap_mat=None, cap_bottom=True, cap_top=True, phase=0.0):
    """Revolve a (z, r) profile (bottom -> top) around local Z. r == 0 -> pole vertex.
    mat_alt: alternate side material every `alt_every` segments (gores / staves)."""
    M = mtx(loc, rot, scale)
    bm = part.bm
    rings = []
    for z, r in profile:
        if r <= 1e-6:
            rings.append([bm.verts.new(M @ Vector((0, 0, z)))])
        else:
            rings.append([bm.verts.new(M @ Vector((r * math.cos(2 * math.pi * j / seg + phase),
                                                   r * math.sin(2 * math.pi * j / seg + phase), z)))
                          for j in range(seg)])
    main, alt, caps = [], [], []
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(seg):
            k = (j + 1) % seg
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                f = bm.faces.new((a[0], b[j], b[k])[::-1])
            elif len(b) == 1:
                f = bm.faces.new((a[j], a[k], b[0]))
            else:
                f = bm.faces.new((a[j], a[k], b[k], b[j]))
            (alt if (mat_alt and (j // alt_every) % 2 == 1) else main).append(f)
    if cap_bottom and len(rings[0]) > 1:
        caps.append(bm.faces.new(list(reversed(rings[0]))))
    if cap_top and len(rings[-1]) > 1:
        caps.append(bm.faces.new(rings[-1]))
    set_mat(part, main, mat)
    if alt:
        set_mat(part, alt, mat_alt)
    if caps:
        set_mat(part, caps, cap_mat or mat)
    return rings


def extrude_profile(part, mat, pts, depth, axis="Y", loc=(0, 0, 0), rot=(0, 0, 0), side_mat=None):
    """Prism from a 2D polygon. axis X: pts are (y, z); axis Y: (x, z); axis Z: (x, y).
    Centered on loc along the axis."""
    M = mtx(loc, rot)
    bm = part.bm

    def P(u, v, d):
        if axis == "X":
            return Vector((d, u, v))
        if axis == "Y":
            return Vector((u, d, v))
        return Vector((u, v, d))

    a = [bm.verts.new(M @ P(u, v, -depth / 2)) for u, v in pts]
    b = [bm.verts.new(M @ P(u, v, depth / 2)) for u, v in pts]
    caps = [bm.faces.new(a), bm.faces.new(list(reversed(b)))]
    sides = []
    n = len(pts)
    for i in range(n):
        k = (i + 1) % n
        sides.append(bm.faces.new((a[i], b[i], b[k], a[k])))
    set_mat(part, caps, mat)
    set_mat(part, sides, side_mat or mat)


def half_cyl_x(part, mat, r, length, seg=6, loc=(0, 0, 0), scale_z=1.0, side_mat=None):
    """Half cylinder along X, flat face down at loc.z, arch spanning y in [-r, r]."""
    pts = [(r * math.cos(math.pi * i / seg), r * math.sin(math.pi * i / seg) * scale_z)
           for i in range(seg + 1)]
    extrude_profile(part, mat, pts[::-1], length, axis="X", loc=loc, side_mat=side_mat)


# ---------------------------------------------------------------------------
# crystals / mechanical bits
# ---------------------------------------------------------------------------

def shard(part, mat, r=0.2, h=1.0, tip=0.3, seg=6, base=0.8, loc=(0, 0, 0), rot=(0, 0, 0), spin=0.0):
    """Crystal: n-gon prism from local z=0 (radius r*base) to z=h (radius r) + pointed tip."""
    M = mtx(loc, rot)
    bm = part.bm
    s0 = math.radians(spin)
    b = [bm.verts.new(M @ Vector((r * base * math.cos(2 * math.pi * j / seg + s0),
                                  r * base * math.sin(2 * math.pi * j / seg + s0), 0)))
         for j in range(seg)]
    t = [bm.verts.new(M @ Vector((r * math.cos(2 * math.pi * j / seg + s0),
                                  r * math.sin(2 * math.pi * j / seg + s0), h)))
         for j in range(seg)]
    apex = bm.verts.new(M @ Vector((0, 0, h + tip)))
    faces = [bm.faces.new(list(reversed(b)))]
    for j in range(seg):
        k = (j + 1) % seg
        faces.append(bm.faces.new((b[j], b[k], t[k], t[j])))
        faces.append(bm.faces.new((t[j], t[k], apex)))
    set_mat(part, faces, mat)


def bipyramid(part, mat, r=0.2, up=0.4, down=0.3, seg=6, loc=(0, 0, 0), rot=(0, 0, 0)):
    """Floating gem: ring of `seg` verts with an apex above and below."""
    M = mtx(loc, rot)
    bm = part.bm
    ring = [bm.verts.new(M @ Vector((r * math.cos(2 * math.pi * j / seg), r * math.sin(2 * math.pi * j / seg), 0)))
            for j in range(seg)]
    top = bm.verts.new(M @ Vector((0, 0, up)))
    bot = bm.verts.new(M @ Vector((0, 0, -down)))
    faces = []
    for j in range(seg):
        k = (j + 1) % seg
        faces.append(bm.faces.new((ring[j], ring[k], top)))
        faces.append(bm.faces.new((ring[k], ring[j], bot)))
    set_mat(part, faces, mat)


def wheel(part, mat, R=0.2, r=0.025, spokes=4, loc=(0, 0, 0), rot=(0, 0, 0), seg=10, hub_mat=None):
    """Valve wheel in local XY plane (axis local Z)."""
    with Xform(part, mtx(loc, rot)):
        part.torus(mat, R=R, r=r, seg=seg, seg2=4)
        for i in range(spokes):
            a = 180.0 * i / spokes
            box_m(part, mat, mtx((0, 0, 0), (0, 0, a), (2 * R, r * 1.3, r * 1.3)))
        part.cyl(hub_mat or mat, r=r * 2.2, h=r * 3, seg=6)


# ---------------------------------------------------------------------------
# scene utils
# ---------------------------------------------------------------------------

def mesh_tris(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons) if obj.type == "MESH" else 0


def tree_tris(obj):
    return mesh_tris(obj) + sum(mesh_tris(c) for c in obj.children_recursive)


def tree_bbox(obj):
    """World-space bbox of all mesh descendants (call view_layer.update() first)."""
    mins = Vector((1e9, 1e9, 1e9))
    maxs = Vector((-1e9, -1e9, -1e9))
    objs = [obj] + list(obj.children_recursive)
    for o in objs:
        if o.type != "MESH":
            continue
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            mins = Vector(map(min, mins, w))
            maxs = Vector(map(max, maxs, w))
    return mins, maxs


def preview_ground(radius, z=-0.01, name="_preview_ground"):
    """Thin ground disc for previews only (never exported)."""
    get_mat("_preview_ground", hex="#7d8f6a", roughness=1.0)
    p = Part(name)
    p.cyl("_preview_ground", r=radius, h=0.02, seg=32, loc=(0, 0, z - 0.01))
    return p.build()
