"""Geometry helpers for the hi-poly Lamp Wisp (model_wisp.py only).

Own module (the shared helpers stay read-only). Everything adds geometry to a common.Part in the
part's LOCAL (pivot-relative) space, like Part.box / cyl.

    ngon_outline / circle    unit cross-section outlines (rounded n-gon, circle)
    fillet_profile           round / chamfer the corners of a 2D (r, z) profile polyline
    revolve                  surface of revolution of a profile over any outline (hex lathe)
    sweep                    sweep varying 2D sections along a 3D polyline (blades, ribs, rims)
    ring_band                torus with an arbitrary cross-section (optionally a partial arc)
    gear_ring                toothed annulus (gear rim with a hole), axis = local Z
    flame                    twisted, lobed teardrop flame
    join_objects             join meshes into one object (keeps custom normals / materials)
    wn_obj                   smooth + weighted normals (flat faces stay flat, rounded corners soft)
    clearance                min vertex->surface distance + overlap test between two objects
"""
import math

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from common import _mtx
import hp_helpers as hp

TAU = 2.0 * math.pi


# ---------------------------------------------------------------------------
# Outlines / profiles
# ---------------------------------------------------------------------------

def ngon_outline(n=6, fillet=0.07, k=2, phase=0.0):
    """Unit outline (corner radius 1) of a regular n-gon whose corners are rounded with k points
    (k=2 -> chamfer).  Corners sit at phase + i*360/n.  CCW."""
    half = math.pi / n
    ap = math.cos(half)
    rho = 1.0 - fillet / ap
    pts = []
    for i in range(n):
        a = phase + TAU * i / n
        cx, cy = rho * math.cos(a), rho * math.sin(a)
        for j in range(k):
            t = a - half + 2 * half * j / (k - 1) if k > 1 else a
            pts.append((cx + fillet * math.cos(t), cy + fillet * math.sin(t)))
    return pts


def circle(n, phase=0.0):
    return [(math.cos(phase + TAU * i / n), math.sin(phase + TAU * i / n)) for i in range(n)]


def fillet_profile(pts, radius=0.004, segs=1):
    """pts: [(r, z)] or [(r, z, rad)] polyline. Interior corners get rounded with `segs` extra
    segments (segs=1 -> single chamfer).  rad per point overrides `radius` (0 = keep sharp)."""
    out = [tuple(pts[0][:2])]
    for i in range(1, len(pts) - 1):
        rad = pts[i][2] if len(pts[i]) > 2 else radius
        p0, p1, p2 = Vector(pts[i - 1][:2]), Vector(pts[i][:2]), Vector(pts[i + 1][:2])
        a, b = p0 - p1, p2 - p1
        la, lb = a.length, b.length
        if rad <= 0 or la < 1e-9 or lb < 1e-9:
            out.append(tuple(p1))
            continue
        a.normalize()
        b.normalize()
        ang = a.angle(b)
        if ang > math.radians(172):
            out.append(tuple(p1))
            continue
        d = min(rad / math.tan(ang / 2), la * 0.45, lb * 0.45)
        q0, q2 = p1 + a * d, p1 + b * d
        for s in range(segs + 1):
            t = s / segs
            q = (1 - t) ** 2 * q0 + 2 * (1 - t) * t * p1 + t * t * q2
            out.append((q.x, q.y))
    out.append(tuple(pts[-1][:2]))
    return out


# ---------------------------------------------------------------------------
# Surfaces
# ---------------------------------------------------------------------------

def revolve(p, mat, profile, outline, caps=(True, True), loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    """Profile [(r, z)] (bottom -> top, r==0 -> pole) revolved over a unit outline [(x, y)]."""
    M = _mtx(loc, rot, scale)
    bm = p.bm
    rings, allv = [], []
    for (r, z) in profile:
        if r <= 1e-7:
            v = bm.verts.new(M @ Vector((0.0, 0.0, z)))
            rings.append([v])
            allv.append(v)
        else:
            ring = [bm.verts.new(M @ Vector((r * u, r * w, z))) for (u, w) in outline]
            rings.append(ring)
            allv += ring
    n = len(outline)
    for k in range(len(rings) - 1):
        A, B = rings[k], rings[k + 1]
        if len(A) == 1 and len(B) == 1:
            continue
        for i in range(n):
            j = (i + 1) % n
            if len(A) == 1:
                bm.faces.new((A[0], B[i], B[j]))
            elif len(B) == 1:
                bm.faces.new((A[i], A[j], B[0]))
            else:
                bm.faces.new((A[i], A[j], B[j], B[i]))
    if caps[0] and len(rings[0]) > 2:
        bm.faces.new(list(reversed(rings[0])))
    if caps[1] and len(rings[-1]) > 2:
        bm.faces.new(rings[-1])
    return p._assign(allv, mat)


def _frames(P, up):
    """Parallel-transport frames (t, n, b) along polyline P."""
    n = len(P)
    tang = []
    for i in range(n):
        if i == 0:
            t = P[1] - P[0]
        elif i == n - 1:
            t = P[-1] - P[-2]
        else:
            t = (P[i + 1] - P[i]).normalized() + (P[i] - P[i - 1]).normalized()
        tang.append(t.normalized())
    upv = Vector(up)
    nrm = upv - tang[0] * upv.dot(tang[0])
    if nrm.length < 1e-5:
        nrm = tang[0].orthogonal()
    nrm.normalize()
    out = []
    for i in range(n):
        t = tang[i]
        nrm = (nrm - t * nrm.dot(t)).normalized()
        b = t.cross(nrm).normalized()
        out.append((t, nrm, b))
    return out


def sweep(p, mat, pts, sections, up=(0, 0, 1), cap=(True, True), loc=(0, 0, 0), rot=(0, 0, 0),
          scale=(1, 1, 1)):
    """Sweep 2D sections along a 3D polyline.  sections: one outline [(x, y)] (x along the frame
    normal, y along the binormal) per path point, all with the same vertex count; None -> pole.
    `up` picks the initial normal direction."""
    M = _mtx(loc, rot, scale)
    P = [Vector(q) for q in pts]
    fr = _frames(P, up)
    bm = p.bm
    rings, allv = [], []
    m = max(len(s) for s in sections if s)
    for i, (c, sec) in enumerate(zip(P, sections)):
        t, nv, bv = fr[i]
        if not sec:
            v = bm.verts.new(M @ c)
            rings.append([v])
            allv.append(v)
            continue
        ring = [bm.verts.new(M @ (c + nv * x + bv * y)) for (x, y) in sec]
        rings.append(ring)
        allv += ring
    for k in range(len(rings) - 1):
        A, B = rings[k], rings[k + 1]
        if len(A) == 1 and len(B) == 1:
            continue
        for i in range(m):
            j = (i + 1) % m
            if len(A) == 1:
                bm.faces.new((A[0], B[i], B[j]))
            elif len(B) == 1:
                bm.faces.new((A[i], A[j], B[0]))
            else:
                bm.faces.new((A[i], A[j], B[j], B[i]))
    if cap[0] and len(rings[0]) > 2:
        bm.faces.new(list(reversed(rings[0])))
    if cap[1] and len(rings[-1]) > 2:
        bm.faces.new(rings[-1])
    return p._assign(allv, mat)


def round_section(r, n=6, flat=1.0, phase=None):
    phase = math.pi / n if phase is None else phase
    return [(r * math.cos(phase + TAU * i / n), r * flat * math.sin(phase + TAU * i / n)) for i in range(n)]


def ring_band(p, mat, R, section, seg=48, arc=None, loc=(0, 0, 0), rot=(0, 0, 0), cap=True):
    """Torus-like band around local Z at radius R with cross-section [(dr, dz)] (closed loop, CCW
    seen with +dr to the right and +dz up).  arc=(a0, a1) radians -> partial band with end caps."""
    M = _mtx(loc, rot)
    bm = p.bm
    closed = arc is None
    if closed:
        angs = [TAU * i / seg for i in range(seg)]
    else:
        angs = [arc[0] + (arc[1] - arc[0]) * i / seg for i in range(seg + 1)]
    rings, allv = [], []
    for a in angs:
        ca, sa = math.cos(a), math.sin(a)
        ring = [bm.verts.new(M @ Vector(((R + dr) * ca, (R + dr) * sa, dz))) for (dr, dz) in section]
        rings.append(ring)
        allv += ring
    m = len(section)
    nr = len(rings) if closed else len(rings) - 1
    for k in range(nr):
        A, B = rings[k], rings[(k + 1) % len(rings)]
        for i in range(m):
            j = (i + 1) % m
            bm.faces.new((A[i], A[j], B[j], B[i]))
    if not closed and cap:
        bm.faces.new(rings[0])
        bm.faces.new(list(reversed(rings[-1])))
    return p._assign(allv, mat)


def gear_ring(p, mat, r_in, r_root, r_tip, teeth, thick, tip=0.36, root=0.52, loc=(0, 0, 0), rot=(0, 0, 0),
              inner_seg_per_tooth=2):
    """Toothed annulus in local XY (axis local Z), centred on z=0, `thick` along Z.
    Outer outline: 4 points per tooth.  Inner hole circle sampled with matching angles."""
    M = _mtx(loc, rot)
    pitch = TAU / teeth
    outer = []
    for i in range(teeth):
        a = pitch * i
        for (aa, rr) in ((a - pitch * root / 2, r_root), (a - pitch * tip / 2, r_tip),
                         (a + pitch * tip / 2, r_tip), (a + pitch * root / 2, r_root)):
            outer.append((aa, rr))
    bm = p.bm
    rows = []
    for z in (-thick / 2, thick / 2):
        o = [bm.verts.new(M @ Vector((rr * math.cos(aa), rr * math.sin(aa), z))) for (aa, rr) in outer]
        i_ = [bm.verts.new(M @ Vector((r_in * math.cos(aa), r_in * math.sin(aa), z))) for (aa, rr) in outer]
        rows.append((o, i_))
    (o0, i0), (o1, i1) = rows
    n = len(outer)
    for k in range(n):
        j = (k + 1) % n
        bm.faces.new((i1[k], o1[k], o1[j], i1[j]))      # top
        bm.faces.new((i0[j], o0[j], o0[k], i0[k]))      # bottom
        bm.faces.new((o0[k], o0[j], o1[j], o1[k]))      # outer wall
        bm.faces.new((i0[j], i0[k], i1[k], i1[j]))      # inner wall
    return p._assign(o0 + o1 + i0 + i1, mat)


def gear_ring_lp(p, mat, r_in, r_root, r_tip, teeth, thick, tip=0.36, root=0.52, loc=(0, 0, 0),
                 rot=(0, 0, 0)):
    """Cheaper toothed annulus (~20 tris per tooth): one n-gon per tooth on each face and one inner
    wall quad per tooth.  Axis local Z, centred on z=0."""
    M = _mtx(loc, rot)
    pitch = TAU / teeth
    bm = p.bm
    layers = []
    for z in (-thick / 2, thick / 2):
        teeth_v = []
        for i in range(teeth):
            a = pitch * i
            o = [bm.verts.new(M @ Vector((rr * math.cos(aa), rr * math.sin(aa), z))) for (aa, rr) in
                 ((a - pitch * root / 2, r_root), (a - pitch * tip / 2, r_tip),
                  (a + pitch * tip / 2, r_tip), (a + pitch * root / 2, r_root))]
            aa = a - pitch * root / 2
            iv = bm.verts.new(M @ Vector((r_in * math.cos(aa), r_in * math.sin(aa), z)))
            teeth_v.append((iv, o))
        layers.append(teeth_v)
    bot, top = layers
    allv = []
    for k in range(teeth):
        j = (k + 1) % teeth
        ib, ob = bot[k]
        it, ot = top[k]
        ibn, obn = bot[j]
        itn, otn = top[j]
        bm.faces.new([it] + ot + [otn[0], itn])                       # top n-gon
        bm.faces.new(list(reversed([ib] + ob + [obn[0], ibn])))       # bottom n-gon
        chain_b = ob + [obn[0]]
        chain_t = ot + [otn[0]]
        for m in range(4):
            bm.faces.new((chain_b[m], chain_b[m + 1], chain_t[m + 1], chain_t[m]))
        bm.faces.new((ibn, ib, it, itn))                              # inner wall
        allv += [ib, it] + ob + ot
    return p._assign(allv, mat)


def flame(p, mat, z0, z1, rmax, n_z=12, n_t=20, lobes=3, twist=0.55, amp=0.28, bend=(0.0, 0.0),
          belly=0.32, tip_pow=1.35, phase=0.0, sharp=1.0, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    """Teardrop flame along local Z from z0 (round bottom) to z1 (pointed tip). The upper part gets
    `lobes` twisting tongues (twist = turns over the height), the tip bends by `bend` (x, y)."""
    M = _mtx(loc, rot, scale)
    bm = p.bm
    H = z1 - z0
    rings, allv = [], []
    for iz in range(n_z + 1):
        h = iz / n_z
        # bottom: quarter-ellipse up to `belly`, then concave taper to the tip
        hh = 0.02 + 0.98 * h
        if hh < belly:
            f = math.sqrt(max(0.0, 1 - ((belly - hh) / belly) ** 2))
        else:
            f = ((1 - hh) / (1 - belly)) ** tip_pow
            f = max(f, 0.0)
        z = z0 + H * hh
        cx = bend[0] * h ** 2
        cy = bend[1] * h ** 2
        if iz == n_z:
            v = bm.verts.new(M @ Vector((cx, cy, z1)))
            rings.append([v])
            allv.append(v)
            continue
        if iz == 0:
            v = bm.verts.new(M @ Vector((0, 0, z0)))
            rings.append([v])
            allv.append(v)
            continue
        g = min(1.0, max(0.0, (h - 0.15) / 0.55))
        ring = []
        for it in range(n_t):
            t = TAU * it / n_t
            c = math.cos(lobes * (t - TAU * twist * h) + phase)
            if sharp != 1.0:                      # narrower ridges / wider valleys
                c = 2.0 * ((c + 1.0) / 2.0) ** sharp - 1.0
            lob = 1 + amp * g * c
            r = rmax * f * lob
            ring.append(bm.verts.new(M @ Vector((cx + r * math.cos(t), cy + r * math.sin(t), z))))
        rings.append(ring)
        allv += ring
    for k in range(len(rings) - 1):
        A, B = rings[k], rings[k + 1]
        for i in range(n_t):
            j = (i + 1) % n_t
            if len(A) == 1:
                bm.faces.new((A[0], B[i], B[j]))
            elif len(B) == 1:
                bm.faces.new((A[i], A[j], B[0]))
            else:
                bm.faces.new((A[i], A[j], B[j], B[i]))
    return p._assign(allv, mat)


def flame_radius(z, z0, z1, rmax, belly=0.32, tip_pow=1.35):
    """Un-lobed radius of `flame(...)` at height z (to place features on its surface)."""
    hh = (z - z0) / (z1 - z0)
    if hh < belly:
        return rmax * math.sqrt(max(0.0, 1 - ((belly - hh) / belly) ** 2))
    return rmax * max(0.0, (1 - hh) / (1 - belly)) ** tip_pow


def fluted(n, depth=0.045, phase=0.0):
    """Unit outline with n points alternating radius 1 / 1-depth -> n/2 flutes."""
    return [((1.0 if i % 2 == 0 else 1.0 - depth) * math.cos(phase + TAU * i / n),
             (1.0 if i % 2 == 0 else 1.0 - depth) * math.sin(phase + TAU * i / n)) for i in range(n)]


def paint_faces(p, mat, start, pred):
    """Re-assign `mat` to the faces p.bm.faces[start:] whose centre satisfies pred(centre)."""
    mi = p._mi(mat)
    p.bm.faces.ensure_lookup_table()
    for f in p.bm.faces[start:]:
        if pred(f.calc_center_median()):
            f.material_index = mi
    return p


RUNES = {   # stroke sets in a unit glyph box (x in [-0.35, 0.35], z in [-0.5, 0.5])
    "algiz": (((0, -0.5), (0, 0.5)), ((0, 0.02), (-0.3, 0.45)), ((0, 0.02), (0.3, 0.45))),
    "fehu": (((-0.18, -0.5), (-0.18, 0.5)), ((-0.18, 0.12), (0.25, 0.46)), ((-0.18, -0.18), (0.25, 0.14))),
    "tiwaz": (((0, -0.5), (0, 0.5)), ((0, 0.5), (-0.28, 0.18)), ((0, 0.5), (0.28, 0.18))),
    "sowilo": (((-0.22, 0.5), (0.18, 0.12)), ((0.18, 0.12), (-0.18, -0.12)), ((-0.18, -0.12), (0.22, -0.5))),
    "ingwaz": (((0, 0.5), (0.28, 0.0)), ((0.28, 0.0), (0, -0.5)), ((0, -0.5), (-0.28, 0.0)), ((-0.28, 0.0), (0, 0.5))),
    "kenaz": (((0.22, 0.48), (-0.2, 0.0)), ((-0.2, 0.0), (0.22, -0.48))),
}


def rune(p, mat, M, name, h=0.018, bar=0.0026):
    """Glowing rune strokes as flat quads in frame M's (x, z) plane, facing frame +y."""
    bm = p.bm
    vs = []
    for (a, b) in RUNES[name]:
        A, B = Vector((a[0] * h, 0, a[1] * h)), Vector((b[0] * h, 0, b[1] * h))
        d = (B - A).normalized()
        n = Vector((-d.z, 0, d.x)) * (bar / 2)
        A, B = A - d * bar * 0.4, B + d * bar * 0.4
        q = [bm.verts.new(M @ c) for c in (A - n, B - n, B + n, A + n)]
        f = bm.faces.new(q)
        f.normal_update()
        if (M.to_3x3() @ Vector((0, 1, 0))).dot(f.normal) < 0:
            f.normal_flip()
        vs += q
    return p._assign(vs, mat)


def build_raw(p, parent=None, loc=(0, 0, 0)):
    """Like Part.build but WITHOUT recalc_face_normals (single-sided decal quads keep the
    orientation they were built with)."""
    from common import _link, get_mat
    mesh = bpy.data.meshes.new(p.name)
    p.bm.to_mesh(mesh)
    p.bm.free()
    for mn in p.mat_names:
        mesh.materials.append(get_mat(mn))
    obj = bpy.data.objects.new(p.name, mesh)
    _link(obj)
    obj.parent = parent
    obj.location = loc
    return obj


def mirror_x(p):
    """Mirror a Part's bmesh across X (builds the right-side copy of a left-side part)."""
    bmesh.ops.scale(p.bm, vec=(-1, 1, 1), verts=p.bm.verts[:])
    bmesh.ops.reverse_faces(p.bm, faces=p.bm.faces[:])
    return p


# ---------------------------------------------------------------------------
# Objects
# ---------------------------------------------------------------------------

def join_objects(objs):
    """Join objs into objs[0] (keeps its name / transform / parent). Custom normals & materials kept."""
    target = objs[0]
    if len(objs) > 1:
        with bpy.context.temp_override(active_object=target, object=target, selected_objects=objs,
                                       selected_editable_objects=objs):
            bpy.ops.object.join()
    return target


def wn_obj(obj, angle=50.0, weight=50):
    """Smooth by angle, then weighted normals (big flat faces dominate) -> crisp hard-surface look
    with soft rounded corners."""
    hp.smooth_obj(obj, angle)
    m = obj.modifiers.new("hp_wn", "WEIGHTED_NORMAL")
    m.weight = weight
    m.keep_sharp = True
    m.mode = "FACE_AREA"
    hp.apply_modifiers(obj)
    return obj


def render_aces(filename, target, azimuth=25.0, elevation=20.0, dist_k=2.6, size=720, sun=(50.0, 35.0),
                sun_strength=3.2, exposure=0.0, bg=(0.16, 0.17, 0.2)):
    """Like hp.render_hp but with the ACES 1.3 view transform (closer to the game's three.js
    ACESFilmic tonemapping, so glow colours can be judged).  No ground; target = (centre, radius)."""
    import os
    from common import PREVIEW_DIR, _link
    scene = bpy.context.scene
    center, radius = Vector(target[0]), target[1]
    hp._wire_vcol(True)
    prev_world = hp._setup_world(bg)
    temp = []
    ld = bpy.data.lights.new("_aces_sun", "SUN")
    ld.energy = sun_strength
    ls = bpy.data.objects.new("_aces_sun", ld)
    _link(ls)
    ls.rotation_euler = (math.radians(sun[0]), 0.0, math.radians(sun[1]))
    temp.append(ls)
    az, el = math.radians(azimuth), math.radians(elevation)
    cam_pos = center + Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))) * radius * dist_k
    cd = bpy.data.cameras.new("_aces_cam")
    cam = bpy.data.objects.new("_aces_cam", cd)
    _link(cam)
    cam.location = cam_pos
    cam.rotation_euler = (center - cam_pos).to_track_quat("-Z", "Y").to_euler()
    temp.append(cam)
    prev_cam = scene.camera
    scene.camera = cam
    scene.render.engine = "BLENDER_EEVEE"
    scene.view_settings.view_transform = "ACES 1.3"
    scene.view_settings.exposure = exposure
    scene.render.resolution_x = scene.render.resolution_y = size
    out = os.path.join(PREVIEW_DIR, filename + ".png")
    scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    scene.camera = prev_cam
    scene.world = prev_world
    for o in temp:
        data = o.data
        bpy.data.objects.remove(o)
        if isinstance(data, bpy.types.Light):
            bpy.data.lights.remove(data)
        elif isinstance(data, bpy.types.Camera):
            bpy.data.cameras.remove(data)
    hp._wire_vcol(False)
    print(f"[preview] {out}")
    return out


def bvh_world(obj, keep=None):
    """BVH of obj in world space. keep(local_co) -> bool filters faces (all verts must pass)."""
    mw = obj.matrix_world
    me = obj.data
    ok = [True] * len(me.vertices) if keep is None else [bool(keep(v.co)) for v in me.vertices]
    verts = [mw @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons if all(ok[i] for i in p.vertices)]
    pts = [verts[i] for i in range(len(verts)) if ok[i]]
    return BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0), pts


def clearance(a, b, keep_a=None, keep_b=None):
    """(min vertex->surface distance between a and b, n overlapping face pairs), world space.
    keep_a / keep_b(local_co) restrict the test to part of a mesh (e.g. skip an axle that sits in
    its socket by design)."""
    ta, va = bvh_world(a, keep_a)
    tb, vb = bvh_world(b, keep_b)
    def _md(tree, pts):
        ds = [tree.find_nearest(v)[3] for v in pts]
        return min((d for d in ds if d is not None), default=9.0)
    return min(_md(tb, va), _md(ta, vb)), len(ta.overlap(tb))
