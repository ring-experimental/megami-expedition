"""Arena-only helpers (hi-poly): flush floor geometry built from chamfered pieces,
per-vertex tint plumbing, mesh joining and game-camera EEVEE previews.

Everything adds geometry straight into a common.Part (part.bm / part.mat_names) — winding is built
explicitly (open shells!), so use build_obj() (no recalc_face_normals) instead of Part.build().

Floor pieces follow one rule: their top surface is at z_top (<= 0) and every chamfer/groove goes
DOWN from there, so the walkable surface never rises above z = 0.
"""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector, noise

from common import PREVIEW_DIR, _link, get_mat
from env_helpers import set_mat
import hp_helpers as hp

TINT = "_tint"
TAU = 2 * math.pi


def P(r, a, z=0.0):
    return Vector((r * math.cos(a), r * math.sin(a), z))


# ---------------------------------------------------------------------------
# tint layer (per-vertex colour multiplier applied after the AO bake)
# ---------------------------------------------------------------------------

def _tlay(part):
    bm = part.bm
    return bm.verts.layers.float_color.get(TINT) or bm.verts.layers.float_color.new(TINT)


def part(name):
    """common.Part with the _tint layer created up-front (adding a bmesh layer later would invalidate
    live BMVert references)."""
    from common import Part
    p = Part(name)
    _tlay(p)
    return p


def set_tint(part, verts, rgb):
    lay = _tlay(part)
    c = (rgb[0], rgb[1], rgb[2], 1.0)
    for v in verts:
        v[lay] = c


def build_obj(part, parent=None, loc=(0, 0, 0), recalc=False):
    """Part -> object WITHOUT the normal recalculation of Part.build (our open shells are wound
    explicitly). Every vertex gets a _tint value (white unless set)."""
    bm = part.bm
    lay = _tlay(part)
    for v in bm.verts:
        if v[lay][3] < 0.5:
            v[lay] = (1.0, 1.0, 1.0, 1.0)
    if recalc:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(part.name)
    bm.to_mesh(me)
    bm.free()
    for mn in part.mat_names:
        me.materials.append(get_mat(mn))
    obj = bpy.data.objects.new(part.name, me)
    _link(obj)
    obj.parent = parent
    obj.location = loc
    return obj


def join(objs, name):
    """Join meshes into objs[0] (keeps its parent / transform); returns the joined object."""
    objs = [o for o in objs if o is not None]
    target = objs[0]
    if len(objs) > 1:
        with bpy.context.temp_override(active_object=target, object=target,
                                       selected_objects=objs, selected_editable_objects=objs):
            bpy.ops.object.join()
    target.name = name
    target.data.name = name
    return target


def apply_tint(objs):
    """Multiply the baked 'Col' attribute by the _tint point attribute, then drop _tint."""
    for o in objs:
        if o.type != "MESH":
            continue
        me = o.data
        if TINT not in me.color_attributes:
            continue
        t = me.color_attributes[TINT]
        if hp.AO_ATTR in me.color_attributes:
            col = me.color_attributes[hp.AO_ATTR]
            nv, nl = len(me.vertices), len(me.loops)
            tv = np.empty(nv * 4, np.float32)
            t.data.foreach_get("color", tv)
            tv = tv.reshape(-1, 4)
            cv = np.empty(nl * 4, np.float32)
            col.data.foreach_get("color", cv)
            cv = cv.reshape(-1, 4)
            lv = np.empty(nl, np.int64)
            me.loops.foreach_get("vertex_index", lv)
            cv[:, :3] = np.clip(cv[:, :3] * tv[lv, :3], 0.0, 1.0)
            col.data.foreach_set("color", cv.ravel())
        me.color_attributes.remove(me.color_attributes[TINT])
        if hp.AO_ATTR in me.color_attributes:
            me.color_attributes.active_color = me.color_attributes[hp.AO_ATTR]
            me.color_attributes.render_color_index = me.color_attributes.find(hp.AO_ATTR)


# ---------------------------------------------------------------------------
# 2D polygon utils
# ---------------------------------------------------------------------------

def offset_loop(pts, dist, max_miter=2.5):
    """Offset a closed CCW 2D polygon; dist > 0 = outward. Miter joints (clamped)."""
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2 = Vector(pts[i - 1]), Vector(pts[i]), Vector(pts[(i + 1) % n])
        e1 = (p1 - p0).normalized()
        e2 = (p2 - p1).normalized()
        n1 = Vector((e1.y, -e1.x))
        n2 = Vector((e2.y, -e2.x))
        m = n1 + n2
        if m.length < 1e-6:
            m = n1
        m.normalize()
        k = 1.0 / max(m.dot(n1), 1.0 / max_miter)
        q = p1 + m * dist * k
        out.append((q.x, q.y))
    return out


# ---------------------------------------------------------------------------
# flush floor pieces
# ---------------------------------------------------------------------------
# chamfer profile: list of (t_xy, t_z) from the top edge (0, 0) to the cell boundary (1, 1)
PROF2 = ((0.42, 0.16), (1.0, 1.0))      # rounded-ish 2-facet chamfer
PROF1 = ((1.0, 1.0),)                   # plain 45 deg chamfer


def _quad_strip(bm, loop_a, loop_b, closed=True):
    """faces (u, u', v', v) between two parallel loops (loop_b = next ring outward/down).
    For a CCW loop this gives outward-facing normals."""
    faces = []
    n = len(loop_a)
    rng = range(n) if closed else range(n - 1)
    for m in rng:
        k = (m + 1) % n
        faces.append(bm.faces.new((loop_a[m], loop_b[m], loop_b[k], loop_a[k])))
    return faces


def slab(part, mat, r0, r1, a0, a1, z=0.0, w=0.045, d=0.045, prof=PROF2, arc_cell=0.4, rad_cell=0.7,
         tint=None, z_extra=None, a0o=None, a1o=None):
    """Annular-sector paving stone: flat top at z, chamfered border going DOWN to z-d at the cell
    boundary (r0..r1, a0..a1 radians). Neighbouring slabs form V-grooves. Open bottom.
    z_extra: optional extra vertical wall depth below the chamfer (for raised-gap pieces)."""
    bm = part.bm
    a0o = a0 if a0o is None else a0o      # angles of the side edges at r1 (slanted cuts / cracks)
    a1o = a1 if a1o is None else a1o
    n_arc = max(2, int(round((max(a1 - a0, a1o - a0o)) * (r0 + r1) * 0.5 / arc_cell)))
    n_rad = max(1, int(round((r1 - r0) / rad_cell)))

    def A0(r):
        return a0 + (a0o - a0) * (r - r0) / (r1 - r0)

    def A1(r):
        return a1 + (a1o - a1) * (r - r0) / (r1 - r0)

    def top_ra(i, j):
        r = r0 + w + (r1 - r0 - 2 * w) * i / n_rad
        da = w / r
        lo, hi = A0(r), A1(r)
        a = lo + da + (hi - lo - 2 * da) * j / n_arc
        return r, a

    grid = [[bm.verts.new(P(*top_ra(i, j), z)) for j in range(n_arc + 1)] for i in range(n_rad + 1)]
    faces = []
    for i in range(n_rad):
        for j in range(n_arc):
            faces.append(bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1])))
    border = ([(i, 0) for i in range(0, n_rad + 1)] + [(n_rad, j) for j in range(1, n_arc + 1)] +
              [(i, n_arc) for i in range(n_rad - 1, -1, -1)] + [(0, j) for j in range(n_arc - 1, 0, -1)])
    loops = [[grid[i][j] for (i, j) in border]]
    for (txy, tz) in prof:
        lp = []
        for (i, j) in border:
            rt, at = top_ra(i, j)
            rb = r0 if i == 0 else (r1 if i == n_rad else rt)
            ab = A0(rb) if j == 0 else (A1(rb) if j == n_arc else at)
            lp.append(bm.verts.new(P(rt + (rb - rt) * txy, at + (ab - at) * txy, z - d * tz)))
        loops.append(lp)
    if z_extra:
        loops.append([bm.verts.new((v.co.x, v.co.y, z - d - z_extra)) for v in loops[-1]])
    for k in range(len(loops) - 1):
        faces += _quad_strip(bm, loops[k], loops[k + 1])
    set_mat(part, faces, mat)
    allv = [v for row in grid for v in row] + [v for lp in loops[1:] for v in lp]
    if tint:
        set_tint(part, allv, tint)
    return allv


def ring(part, mat, r0, r1, seg, z=0.0, w=0.03, d=0.04, prof=PROF1, n_rad=1, phase=0.0, tint=None,
         wall=None):
    """Full annulus inlay: flat top at z between r0+w .. r1-w, chamfers down to z-d at r0 / r1.
    wall: extra vertical drop below the chamfers (e.g. pieces standing in a deeper recess)."""
    bm = part.bm
    angs = [phase + TAU * j / seg for j in range(seg)]
    rows = [[bm.verts.new(P(r0 + w + (r1 - r0 - 2 * w) * i / n_rad, a, z)) for a in angs] for i in range(n_rad + 1)]
    faces = []
    for i in range(n_rad):
        a, b = rows[i], rows[i + 1]
        for j in range(seg):
            k = (j + 1) % seg
            faces.append(bm.faces.new((a[j], b[j], b[k], a[k])))
    # outer chamfer (CCW loop -> outward)
    outer = [rows[-1]]
    inner = [list(reversed(rows[0]))]
    for (txy, tz) in prof:
        outer.append([bm.verts.new(P(r1 - w + w * txy, a, z - d * tz)) for a in angs])
        inner.append(list(reversed([bm.verts.new(P(r0 + w - w * txy, a, z - d * tz)) for a in angs])))
    if wall:
        outer.append([bm.verts.new((v.co.x, v.co.y, z - d - wall)) for v in outer[-1]])
        inner.append([bm.verts.new((v.co.x, v.co.y, z - d - wall)) for v in inner[-1]])
    for L in (outer, inner):
        for k in range(len(L) - 1):
            faces += _quad_strip(bm, L[k], L[k + 1])
    set_mat(part, faces, mat)
    if tint:
        set_tint(part, [v for r_ in rows for v in r_] + [v for L in (outer[1:] + inner[1:]) for v in L], tint)
    return faces


def plate(part, mat, outline, z=0.0, w=0.02, d=0.02, prof=PROF1, z_bot=None, side_mat=None, tint=None):
    """Polygon inlay: outline = CCW 2D points of the cell boundary. Top (inset by w) at z, chamfer down
    to z-d at the outline, optional vertical wall down to z_bot. Top is one n-gon (fine for convex /
    mildly concave shapes)."""
    bm = part.bm
    loops = [[bm.verts.new((x, y, z)) for x, y in offset_loop(outline, -w)]] if w > 0 else \
        [[bm.verts.new((x, y, z)) for x, y in outline]]
    if w > 0:
        for (txy, tz) in prof:
            loops.append([bm.verts.new((x, y, z - d * tz)) for x, y in offset_loop(outline, -w * (1 - txy))])
    if z_bot is not None:
        loops.append([bm.verts.new((v.co.x, v.co.y, z_bot)) for v in loops[-1]])
    top = bm.faces.new(loops[0])
    sides = []
    for k in range(len(loops) - 1):
        sides += _quad_strip(bm, loops[k], loops[k + 1])
    set_mat(part, [top], mat)
    set_mat(part, sides, side_mat or mat)
    allv = [v for L in loops for v in L]
    if tint:
        set_tint(part, allv, tint)
    return top, sides, allv


def band(part, mat, angs, r_in, r_out_list, z=0.0, w=0.025, d=0.03, prof=PROF1, wall=None):
    """Flush annular band with an arbitrary (e.g. toothed) outer edge. angs: increasing angles of the
    outline points (closed loop), r_out_list: matching outer radii. Inner edge is a circle r_in."""
    bm = part.bm
    n = len(angs)
    outer_cell = [(r * math.cos(a), r * math.sin(a)) for a, r in zip(angs, r_out_list)]
    inner_top = [bm.verts.new(P(r_in + w, a, z)) for a in angs]
    outer_top = [bm.verts.new((x, y, z)) for x, y in offset_loop(outer_cell, -w)]
    faces = []
    for j in range(n):
        k = (j + 1) % n
        faces.append(bm.faces.new((inner_top[j], outer_top[j], outer_top[k], inner_top[k])))
    outer = [outer_top]
    inner = [list(reversed(inner_top))]
    for (txy, tz) in prof:
        outer.append([bm.verts.new((x, y, z - d * tz)) for x, y in offset_loop(outer_cell, -w * (1 - txy))])
        inner.append(list(reversed([bm.verts.new(P(r_in + w - w * txy, a, z - d * tz)) for a in angs])))
    if wall:
        outer.append([bm.verts.new((v.co.x, v.co.y, z - d - wall)) for v in outer[-1]])
        inner.append([bm.verts.new((v.co.x, v.co.y, z - d - wall)) for v in inner[-1]])
    for L in (outer, inner):
        for k in range(len(L) - 1):
            faces += _quad_strip(bm, L[k], L[k + 1])
    set_mat(part, faces, mat)
    return faces


def disc_grid(part, mat, r0, r1, z, seg, n_rad, phase=0.0, center=False):
    """Flat upward-facing annulus/disc made of quads (dense enough for vertex AO)."""
    bm = part.bm
    angs = [phase + TAU * j / seg for j in range(seg)]
    rows = [[bm.verts.new(P(r0 + (r1 - r0) * i / n_rad, a, z)) for a in angs] for i in range(n_rad + 1)]
    faces = []
    for i in range(n_rad):
        a, b = rows[i], rows[i + 1]
        for j in range(seg):
            k = (j + 1) % seg
            faces.append(bm.faces.new((a[j], b[j], b[k], a[k])))
    if center:
        c = bm.verts.new((0, 0, z))
        for j in range(seg):
            k = (j + 1) % seg
            faces.append(bm.faces.new((c, rows[0][j], rows[0][k])))
    set_mat(part, faces, mat)
    return rows


def wall_ring(part, mat, r, z0, z1, seg, inward=False):
    """Vertical cylinder wall (no caps) from z0 (bottom) to z1, normals outward (or inward)."""
    bm = part.bm
    lo = [bm.verts.new(P(r, TAU * j / seg, z0)) for j in range(seg)]
    hi = [bm.verts.new(P(r, TAU * j / seg, z1)) for j in range(seg)]
    faces = []
    for j in range(seg):
        k = (j + 1) % seg
        f = (lo[j], lo[k], hi[k], hi[j])
        faces.append(bm.faces.new(f[::-1] if inward else f))
    set_mat(part, faces, mat)
    return faces


def stroke(part, mat, p0, p1, width, z_top, z_bot):
    """Thin raised bar between two 2D points (top + 4 sides, open bottom)."""
    bm = part.bm
    a, b = Vector(p0), Vector(p1)
    t = (b - a)
    if t.length < 1e-6:
        return []
    t.normalize()
    nrm = Vector((-t.y, t.x)) * (width / 2)
    a = a - t * (width * 0.35)
    b = b + t * (width * 0.35)
    outline = [a - nrm, b - nrm, b + nrm, a + nrm]   # CCW
    top = [bm.verts.new((p.x, p.y, z_top)) for p in outline]
    bot = [bm.verts.new((p.x, p.y, z_bot)) for p in outline]
    faces = [bm.faces.new(top)] + _quad_strip(bm, top, bot)
    set_mat(part, faces, mat)
    return faces


def lathe_rz(part, mats, prof, seg, M=None, phase=0.0, closed_ring=True):
    """Revolve an (r, z) polyline around local Z. Orientation rule: walking the profile with the solid
    on the LEFT in the (r right, z up) plane... i.e. up the outside, inward across the top, down the
    inside -> outward normals. mats: one material or a list per profile segment."""
    bm = part.bm
    M = M or Matrix.Identity(4)
    rings = []
    for r, z in prof:
        if r <= 1e-6:
            rings.append([bm.verts.new(M @ Vector((0, 0, z)))])
        else:
            rings.append([bm.verts.new(M @ Vector((r * math.cos(TAU * j / seg + phase),
                                                   r * math.sin(TAU * j / seg + phase), z))) for j in range(seg)])
    out = []
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        fs = []
        for j in range(seg):
            k = (j + 1) % seg
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                fs.append(bm.faces.new((a[0], b[k], b[j])))
            elif len(b) == 1:
                fs.append(bm.faces.new((a[j], a[k], b[0])))
            else:
                fs.append(bm.faces.new((a[j], a[k], b[k], b[j])))
        m = mats[i] if isinstance(mats, (list, tuple)) else mats
        set_mat(part, fs, m)
        out.append(fs)
    return rings, out


def prism(part, mat, outline, z_top, z_bot, bottom=True, M=None, side_mat=None):
    """Closed prism from a CCW 2D outline (optionally transformed by M)."""
    bm = part.bm
    M = M or Matrix.Identity(4)
    top = [bm.verts.new(M @ Vector((x, y, z_top))) for x, y in outline]
    bot = [bm.verts.new(M @ Vector((x, y, z_bot))) for x, y in outline]
    faces = [bm.faces.new(top)]
    if bottom:
        faces.append(bm.faces.new(list(reversed(bot))))
    sides = _quad_strip(bm, top, bot)
    set_mat(part, faces, mat)
    set_mat(part, sides, side_mat or mat)
    return top + bot


# ---------------------------------------------------------------------------
# procedural noise displacement (rock) with a falloff weight
# ---------------------------------------------------------------------------

def noise_displace(obj, strength=0.4, scale=0.5, weight=None, seed=0, octaves=4, along="normal"):
    me = obj.data
    me.update()
    off = Vector((seed * 13.17, seed * 7.31, seed * 3.77))
    for v in me.vertices:
        p = v.co
        w = weight(p) if weight else 1.0
        if w <= 0:
            continue
        n = noise.fractal(p * scale + off, 0.6, 2.0, octaves, noise_basis="PERLIN_ORIGINAL")
        dirv = v.normal if along == "normal" else Vector((p.x, p.y, 0)).normalized()
        v.co = p + dirv * (n * strength * w)
    me.update()


# ---------------------------------------------------------------------------
# previews that mimic the in-game battle cameras
# ---------------------------------------------------------------------------

def three_to_blender(v):
    """three.js (x, y, z) Y-up -> Blender (x, -z, y)."""
    return Vector((v[0], -v[2], v[1]))


def add_dummies(positions, name="_preview_dummy"):
    """Capsule stand-ins for units (preview only; call AFTER export). positions: Blender (x, y, h)."""
    from common import Part
    get_mat("_dummy", hex="#d8d2c4", roughness=0.6)
    objs = []
    for i, (x, y, h) in enumerate(positions):
        p = Part(f"{name}{i}")
        r = 0.32 * h / 1.75
        p.cyl("_dummy", r=r, h=h * 0.62, seg=16, loc=(0, 0, h * 0.31))
        p.sphere("_dummy", r=r * 0.95, seg=16, rings=8, loc=(0, 0, h * 0.62 + r * 0.7))
        o = p.build(None, loc=(x, y, 0))
        hp.smooth_obj(o, 60)
        objs.append(o)
    hp.fill_vertex_color(objs)
    return objs


def render_cam(filename, cam_loc, look_at, fov_v=50.0, res=(1280, 720), sun=(40.0, -40.6), sun_strength=3.0,
               bg=(0.62, 0.48, 0.48), sky=(0.95, 0.84, 0.78), sky_strength=0.85, exposure=0.0, cull=True,
               samples=32, ground=None):
    """EEVEE still from an explicit camera (three.js-like vertical FOV, 16:9). Sun default = the
    battle key light (three.js position (-12, 22, 14)). cull=True turns on backface culling so
    inverted normals show up as holes."""
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    scene = bpy.context.scene
    temp = []
    hp._wire_vcol(True)
    prev_world = hp._setup_world(bg, sky=sky, strength=sky_strength)
    culled = []
    if cull:
        for m in bpy.data.materials:
            if not m.use_backface_culling:
                m.use_backface_culling = True
                culled.append(m)
    if ground is not None:
        me = bpy.data.meshes.new("_preview_ground")
        bm = bmesh.new()
        bmesh.ops.create_circle(bm, cap_ends=True, segments=64, radius=200)
        bm.to_mesh(me)
        bm.free()
        gmat = bpy.data.materials.get("_preview_ground_mat") or bpy.data.materials.new("_preview_ground_mat")
        me.materials.append(gmat)
        g = bpy.data.objects.new("_preview_ground", me)
        _link(g)
        g.location = (0, 0, ground)
        temp.append(g)
    ld = bpy.data.lights.new("_preview_sun", "SUN")
    ld.energy = sun_strength
    ld.angle = math.radians(2.0)
    ls = bpy.data.objects.new("_preview_sun", ld)
    _link(ls)
    ls.rotation_euler = (math.radians(sun[0]), 0.0, math.radians(sun[1]))
    temp.append(ls)
    cd = bpy.data.cameras.new("_preview_cam")
    cd.sensor_fit = "VERTICAL"
    cd.angle_y = math.radians(fov_v)
    cd.clip_start = 0.1
    cd.clip_end = 2000
    cam = bpy.data.objects.new("_preview_cam", cd)
    _link(cam)
    cam.location = Vector(cam_loc)
    cam.rotation_euler = (Vector(look_at) - Vector(cam_loc)).to_track_quat("-Z", "Y").to_euler()
    temp.append(cam)
    prev_cam = scene.camera
    scene.camera = cam
    scene.render.engine = "BLENDER_EEVEE"
    try:
        scene.eevee.taa_render_samples = samples
        scene.eevee.use_shadows = True
    except Exception:
        pass
    try:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.exposure = exposure
    except Exception:
        pass
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.film_transparent = False
    out = os.path.join(PREVIEW_DIR, filename + ".png")
    scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    scene.camera = prev_cam
    scene.world = prev_world
    for o in temp:
        data = o.data
        bpy.data.objects.remove(o)
        if data is not None and data.users == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Light):
                bpy.data.lights.remove(data)
            elif isinstance(data, bpy.types.Camera):
                bpy.data.cameras.remove(data)
    for m in culled:
        m.use_backface_culling = False
    hp._wire_vcol(False)
    print(f"[preview] {out}")
    return out


def tint_by(obj, fn):
    """Multiply the object's _tint point attribute by fn(co, normal) -> (r, g, b)."""
    me = obj.data
    if TINT not in me.color_attributes:
        return
    a = me.color_attributes[TINT]
    if a.domain != "POINT":
        return
    vals = np.empty(len(me.vertices) * 4, np.float32)
    a.data.foreach_get("color", vals)
    vals = vals.reshape(-1, 4)
    for v in me.vertices:
        r, g, b = fn(v.co, v.normal)
        vals[v.index, 0] *= r
        vals[v.index, 1] *= g
        vals[v.index, 2] *= b
    a.data.foreach_set("color", vals.ravel())


def curved_panel(part, mat, M, r_in, r_out, a0, a1, z0, z1, n=4):
    """Closed cylindrical-shell patch around local Z (angles in radians), e.g. a plate hugging a column."""
    bm = part.bm
    angs = [a0 + (a1 - a0) * i / n for i in range(n + 1)]

    def row(r, z):
        return [bm.verts.new(M @ P(r, a, z)) for a in angs]
    ob, ot, ib, it = row(r_out, z0), row(r_out, z1), row(r_in, z0), row(r_in, z1)
    faces = []
    for i in range(n):
        faces.append(bm.faces.new((ob[i], ob[i + 1], ot[i + 1], ot[i])))
        faces.append(bm.faces.new((it[i], it[i + 1], ib[i + 1], ib[i])))
        faces.append(bm.faces.new((ot[i], ot[i + 1], it[i + 1], it[i])))
        faces.append(bm.faces.new((ib[i], ib[i + 1], ob[i + 1], ob[i])))
    faces.append(bm.faces.new((ob[0], ot[0], it[0], ib[0])))
    faces.append(bm.faces.new((ob[n], ib[n], it[n], ot[n])))
    set_mat(part, faces, mat)
    return faces


def rock_spike(part, mat, top, top_r, length, seg=7, rings=4, seed=0, jitter=0.22, lean=(0.0, 0.0)):
    """Faceted downward rock stalactite: jittered rings from radius top_r at `top` narrowing to a point
    `length` below (lean = xy drift of the tip). Top ring left open (embed it in the rock)."""
    import random as _r
    rnd = _r.Random(seed)
    bm = part.bm
    top = Vector(top)
    rows = []
    for i in range(rings):
        t = i / rings
        rr = top_r * (1 - t) ** 0.85
        c = top + Vector((lean[0] * t * t, lean[1] * t * t, -length * t))
        ph = rnd.uniform(0, TAU)
        rows.append([bm.verts.new(c + Vector((math.cos(TAU * j / seg + ph * 0.15) * rr * rnd.uniform(1 - jitter, 1 + jitter),
                                              math.sin(TAU * j / seg + ph * 0.15) * rr * rnd.uniform(1 - jitter, 1 + jitter),
                                              rnd.uniform(-0.12, 0.12) * length / rings)))
                     for j in range(seg)])
    tip = bm.verts.new(top + Vector((lean[0], lean[1], -length)))
    faces = []
    for i in range(rings - 1):
        a, b = rows[i], rows[i + 1]
        for j in range(seg):
            k = (j + 1) % seg
            faces.append(bm.faces.new((a[k], a[j], b[j], b[k])))
    last = rows[-1]
    for j in range(seg):
        k = (j + 1) % seg
        faces.append(bm.faces.new((last[k], last[j], tip)))
    set_mat(part, faces, mat)
    return faces
