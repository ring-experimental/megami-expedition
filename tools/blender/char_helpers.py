"""Extra geometry helpers for the character / enemy model scripts (model_*.py).

Builds on common.py (which must not be edited). All helpers add geometry to a
common.Part in the part's LOCAL (pivot-relative) space, like Part.box/cyl/...

    loft(p, mat, sections, shape=8)      stacked cross-sections (torsos, boots, skirts, hats)
    lathe(p, mat, [(r, z), ...], seg=8)  surface of revolution around local Z (loft shortcut)
    tube(p, mat, points, r, seg=6)       swept tube along a polyline (tails, horns, braids)
    tbox(p, mat, z0, z1, s0, s1, ...)    tapered box / frustum
    prism(p, mat, outline_yz, ...)       extruded flat outline (blades, axe heads, wings)
    finish(name)                         report tris, export GLB, render front/side/back previews
"""
import math

import bpy
from mathutils import Vector

from common import Part, get_mat, export_glb, render_preview, _mtx  # noqa: F401


def _section_pts(w, d, shape, chamfer, phase):
    """Cross-section points (counter-clockwise, XY plane) of width w (X) and depth d (Y)."""
    hw, hd = w / 2.0, d / 2.0
    if isinstance(shape, (list, tuple)):          # custom unit outline [(u, v), ...] scaled by (w, d)
        return [(u * w, v * d) for (u, v) in shape]
    if shape == "rect":
        return [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)]
    if shape == "oct":
        cx, cy = hw * chamfer, hd * chamfer
        return [(-hw + cx, -hd), (hw - cx, -hd), (hw, -hd + cy), (hw, hd - cy),
                (hw - cx, hd), (-hw + cx, hd), (-hw, hd - cy), (-hw, -hd + cy)]
    n = int(shape)
    return [(hw * math.cos(2 * math.pi * i / n + phase), hd * math.sin(2 * math.pi * i / n + phase))
            for i in range(n)]


def loft(p, mat, sections, shape=8, chamfer=0.35, phase=None, cap=(True, True),
         loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    """Loft through cross-sections stacked along local Z.

    sections: [(z, w, d), ...] or [(z, w, d, cx, cy), ...]; w or d == 0 collapses to a pole.
    shape: "rect", "oct" (chamfered rect) or an int n (ellipse with n segments).
    """
    if phase is None:
        phase = (math.pi / int(shape)) if isinstance(shape, int) else 0.0
    M = _mtx(loc, rot, scale)
    bm = p.bm
    rings, allv = [], []
    for s in sections:
        z, w, d = s[0], s[1], s[2]
        cx, cy = (s[3], s[4]) if len(s) >= 5 else (0.0, 0.0)
        if w <= 1e-6 or d <= 1e-6:
            v = bm.verts.new(M @ Vector((cx, cy, z)))
            rings.append([v])
            allv.append(v)
            continue
        ring = [bm.verts.new(M @ Vector((cx + x, cy + y, z)))
                for (x, y) in _section_pts(w, d, shape, chamfer, phase)]
        rings.append(ring)
        allv += ring
    for k in range(len(rings) - 1):
        A, B = rings[k], rings[k + 1]
        if len(A) == 1 and len(B) == 1:
            continue
        n = max(len(A), len(B))
        for i in range(n):
            j = (i + 1) % n
            if len(A) == 1:
                bm.faces.new((A[0], B[j], B[i]))
            elif len(B) == 1:
                bm.faces.new((A[i], A[j], B[0]))
            else:
                bm.faces.new((A[i], A[j], B[j], B[i]))
    if cap[0] and len(rings[0]) > 2:
        bm.faces.new(list(reversed(rings[0])))
    if cap[1] and len(rings[-1]) > 2:
        bm.faces.new(rings[-1])
    return p._assign(allv, mat)


def lathe(p, mat, profile, seg=8, **kw):
    """Surface of revolution around local Z. profile: [(r, z), ...] bottom -> top. r==0 -> pole."""
    return loft(p, mat, [(z, 2 * r, 2 * r) for (r, z) in profile], shape=seg, **kw)


def tube(p, mat, pts, r, seg=6, cap=True, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1),
         up=(0, 0, 1), flat=1.0):
    """Tube swept along a polyline. r: scalar or per-point list (0 -> pointed end).
    flat < 1 squashes the cross-section along the 'up'-derived binormal (ribbon-like)."""
    M = _mtx(loc, rot, scale)
    P = [Vector(q) for q in pts]
    n = len(P)
    rs = list(r) if isinstance(r, (list, tuple)) else [r] * n
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
    nrm = tang[0].cross(upv)
    if nrm.length < 1e-4:
        nrm = tang[0].cross(Vector((1, 0, 0)))
    nrm.normalize()
    bm = p.bm
    rings, allv = [], []
    for i in range(n):
        t = tang[i]
        nrm = (nrm - t * nrm.dot(t)).normalized()
        b = t.cross(nrm).normalized()
        if rs[i] <= 1e-6:
            v = bm.verts.new(M @ P[i])
            rings.append([v])
            allv.append(v)
            continue
        ring = []
        for k in range(seg):
            a = 2 * math.pi * k / seg + math.pi / seg
            off = (nrm * math.cos(a) + b * math.sin(a) * flat) * rs[i]
            ring.append(bm.verts.new(M @ (P[i] + off)))
        rings.append(ring)
        allv += ring
    for k in range(n - 1):
        A, B = rings[k], rings[k + 1]
        for i in range(seg):
            j = (i + 1) % seg
            if len(A) == 1:
                bm.faces.new((A[0], B[i], B[j]))
            elif len(B) == 1:
                bm.faces.new((A[i], A[j], B[0]))
            else:
                bm.faces.new((A[i], A[j], B[j], B[i]))
    if cap:
        if len(rings[0]) > 2:
            bm.faces.new(list(reversed(rings[0])))
        if len(rings[-1]) > 2:
            bm.faces.new(rings[-1])
    return p._assign(allv, mat)


def gem(p, mat, r, up, down=None, seg=4, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), mid=0.0):
    """Cheap bipyramid crystal / bead along local Z: equator radius r, tips at +up and -down.
    mid > 0 inserts a straight band of that height at the equator."""
    down = up if down is None else down
    secs = [(-down - mid / 2, 0, 0), (-mid / 2, 2 * r, 2 * r)]
    if mid > 0:
        secs.append((mid / 2, 2 * r, 2 * r))
    secs.append((up + mid / 2, 0, 0))
    return loft(p, mat, secs, shape=seg, loc=loc, rot=rot, scale=scale)


def tbox(p, mat, z0, z1, s0, s1=None, c0=(0, 0), c1=None, loc=(0, 0, 0), rot=(0, 0, 0)):
    """Tapered box: bottom rect at z0 (size s0=(w,d), centre c0), top rect at z1 (size s1, centre c1)."""
    s1 = s0 if s1 is None else s1
    c1 = c0 if c1 is None else c1
    return loft(p, mat, [(z0, s0[0], s0[1], c0[0], c0[1]), (z1, s1[0], s1[1], c1[0], c1[1])],
                shape="rect", loc=loc, rot=rot)


def prism(p, mat, outline, thick, loc=(0, 0, 0), rot=(0, 0, 0), axis="x"):
    """Extrude a flat outline. axis='x': outline is [(y, z), ...] extruded along X by thick
    (scalar or per-point list, centred). axis='y': outline [(x, z)], extruded along Y.
    axis='z': outline [(x, y)], extruded along Z. Outline must be convex or star-shaped
    around its first point is NOT required: the caps are n-gons (keep outlines convex-ish)."""
    th = list(thick) if isinstance(thick, (list, tuple)) else [thick] * len(outline)
    verts = []
    for sgn in (-1, 1):
        for (a, b), t in zip(outline, th):
            h = sgn * t / 2.0
            if axis == "x":
                verts.append((h, a, b))
            elif axis == "y":
                verts.append((a, h, b))
            else:
                verts.append((a, b, h))
    n = len(outline)
    M = _mtx(loc, rot)
    verts = [tuple(M @ Vector(v)) for v in verts]
    faces = [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    return p.poly(mat, verts, faces)


def render_view(filename, center, radius, azimuth=20.0, elevation=10.0, size=512):
    """Close-up workbench render framed on an explicit world-space centre/radius
    (same look as common.render_preview). Writes previews/<filename>.png."""
    import os
    from common import PREVIEW_DIR, _link
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    scene = bpy.context.scene
    center = Vector(center)
    az, el = math.radians(azimuth), math.radians(elevation)
    cam_pos = center + Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el),
                               math.sin(el))) * radius * 2.8
    cam_data = bpy.data.cameras.new("closeup_cam")
    cam_data.lens = 50
    cam = bpy.data.objects.new("closeup_cam", cam_data)
    _link(cam)
    cam.location = cam_pos
    cam.rotation_euler = (center - cam_pos).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_cavity = True
    scene.display.shading.show_object_outline = True
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    out = os.path.join(PREVIEW_DIR, filename + ".png")
    scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam)
    return out


def sgear(p, mat, r, teeth=8, depth=None, thick=0.05, loc=(0, 0, 0), rot=(0, 0, 0), tip=0.32, root=0.55):
    """Cheap gear: a single star-outline prism in local XY (axis = local Z). ~16*teeth tris.
    r = outer (tip) radius, depth = tooth height (default r*0.22)."""
    depth = r * 0.22 if depth is None else depth
    rr = r - depth
    pitch = 2 * math.pi / teeth
    pts = []
    for i in range(teeth):
        a = pitch * i
        pts += [(rr * math.cos(a - pitch * root / 2), rr * math.sin(a - pitch * root / 2)),
                (r * math.cos(a - pitch * tip / 2), r * math.sin(a - pitch * tip / 2)),
                (r * math.cos(a + pitch * tip / 2), r * math.sin(a + pitch * tip / 2)),
                (rr * math.cos(a + pitch * root / 2), rr * math.sin(a + pitch * root / 2))]
    return prism(p, mat, pts, thick, loc=loc, rot=rot, axis="z")


def tri_report():
    total = 0
    rows = []
    for o in bpy.context.scene.objects:
        if o.type == "MESH":
            t = sum(len(poly.vertices) - 2 for poly in o.data.polygons)
            rows.append((o.name, t))
            total += t
    for name, t in sorted(rows, key=lambda r: -r[1]):
        print(f"[tris] {name:14s} {t}")
    print(f"[tris] TOTAL {total}")
    return total


def finish(name, views=(("", 35, 18), ("_front", 0, 5), ("_side", 90, 8), ("_back", 205, 20)), budget=3000):
    total = tri_report()
    if total > budget:
        print(f"[WARN] {name}: {total} tris exceeds budget {budget}")
    export_glb(name)
    # Workbench can't show emission: brighten glow_* viewport colours for the previews only
    # (runs after the export, so the GLB keeps the real material values).
    for m in bpy.data.materials:
        if m.name.startswith("glow_"):
            c = m.diffuse_color
            m.diffuse_color = (c[0] * 0.35 + 0.65, c[1] * 0.35 + 0.65, c[2] * 0.35 + 0.65, 1.0)
    for suffix, az, el in views:
        render_preview(name + suffix, azimuth=az, elevation=el)
    return total
