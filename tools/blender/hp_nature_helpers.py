"""Geometry helpers for the hi-poly nature props (props_nature.py only).

    sweep()          smooth tube along a Catmull-Rom spline (lobed cross-sections -> root buttresses)
    remesh_obj()     voxel union of overlapping closed parts (trunk + roots + limbs -> filleted forks)
    blob_mesh()      union of ellipsoid "puffs" -> voxel remesh -> smooth -> decimate (canopies, bushes, moss)
    puff_cloud()     sub-puffs scattered over bigger puffs (cauliflower / cloud foliage)
    leaf_shingles()  oblate, upturned leaf-clump discs laid over puffs (overhanging leafy lips)
    cloud_pad()      cloud-pruned foliage pad (+ flatten_under() post hook for flat undersides)
    boulder()        sheared box with every corner / edge knocked off by jittered planar cuts
    bm_split()       split a chunk along a plane (strata layers, cracks)
    bevel_pieces()   per-piece refine + bevel, merged into one Part; finish_hard() = weighted normals
    moss_clumps()    flattened mini-puffs ray-cast onto flat rock tops (clumpy moss cushions)
    find_plateau()   ray-cast grid -> centre / radius of a rock's flat top
    blend_normals()  custom normals pulled toward ellipsoid centres (soft stylized foliage shading)
    bake_parts()     per-mesh vertex AO + tint (occluded by every mesh of the prop)
    mul_vcol()       extra per-vertex colour multiplier (edge wear, lichen ...)

Shared helper modules stay untouched; everything nature-specific lives here.
"""
import math
import random

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector, noise
from mathutils.bvhtree import BVHTree

from common import Part, get_mat, _link  # noqa: F401
import hp_helpers as hp


# ---------------------------------------------------------------------------
# math utils
# ---------------------------------------------------------------------------

def smoothstep(a, b, x):
    if b == a:
        return 1.0 if x >= b else 0.0
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def lerp3(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def catmull(pts, n_per=4):
    """Catmull-Rom spline through pts (Vectors). Returns (points, param) with param in [0, len-1]."""
    pts = [Vector(p) for p in pts]
    if len(pts) == 2:
        out = [pts[0].lerp(pts[1], k / n_per) for k in range(n_per + 1)]
        return out, [k / n_per for k in range(n_per + 1)]
    P = [pts[0] + (pts[0] - pts[1])] + pts + [pts[-1] + (pts[-1] - pts[-2])]
    out, prm = [], []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n_per):
            t = k / n_per
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
            prm.append(i - 1 + t)
    out.append(pts[-1])
    prm.append(len(pts) - 1)
    return out, prm


def interp_list(vals, x):
    """Piecewise-linear lookup of vals at fractional index x."""
    i = int(math.floor(x))
    if i >= len(vals) - 1:
        return vals[-1]
    if i < 0:
        return vals[0]
    t = x - i
    return vals[i] * (1 - t) + vals[i + 1] * t


# ---------------------------------------------------------------------------
# sweeps (trunks, branches, roots, stems)
# ---------------------------------------------------------------------------

def sweep(part, mat, ctrl, radii, seg=12, n_per=4, section=None, cap_start=False, cap_end=True,
          tip=False, twist=0.0, phase=0.0):
    """Tube along a Catmull-Rom spline through ctrl points. radii: one per ctrl point.
    section(u, theta) -> radius multiplier (u = 0..1 along the tube) for lobed / irregular
    cross-sections. tip=True closes the end into a single pole vertex (pointed twig / root tip).
    twist: total radians the cross-section rotates along the tube."""
    pts, prm = catmull(ctrl, n_per)
    n = len(pts)
    tans = []
    for i in range(n):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[i + 1] - pts[i - 1]
        tans.append(t.normalized())
    t0 = tans[0]
    ref = Vector((0, 1, 0)) if abs(t0.y) < 0.9 else Vector((1, 0, 0))
    nrm = ref.cross(t0).normalized()
    bm = part.bm
    mi = part._mi(mat)
    rings = []
    last = n - 1 if tip else n
    for i in range(n):
        if i > 0:
            ax = tans[i - 1].cross(tans[i])
            if ax.length > 1e-9:
                ang = tans[i - 1].angle(tans[i])
                nrm = (Matrix.Rotation(ang, 3, ax.normalized()) @ nrm).normalized()
        if i >= last:
            break
        bi = tans[i].cross(nrm)
        u = prm[i] / (len(ctrl) - 1)
        r = interp_list(radii, prm[i])
        ring = []
        for j in range(seg):
            a = 2 * math.pi * j / seg + phase + twist * u
            k = section(u, a - twist * u) if section else 1.0
            p = pts[i] + (nrm * math.cos(a) + bi * math.sin(a)) * r * k
            ring.append(bm.verts.new(p))
        rings.append(ring)
    faces = []
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(seg):
            k = (j + 1) % seg
            faces.append(bm.faces.new((a[j], a[k], b[k], b[j])))
    if tip:
        pole = bm.verts.new(pts[-1])
        a = rings[-1]
        for j in range(seg):
            faces.append(bm.faces.new((a[j], a[(j + 1) % seg], pole)))
    elif cap_end:
        faces.append(bm.faces.new(rings[-1]))
    if cap_start:
        faces.append(bm.faces.new(list(reversed(rings[0]))))
    for f in faces:
        f.material_index = mi
        f.smooth = True
    return rings


# ---------------------------------------------------------------------------
# blob unions (foliage)
# ---------------------------------------------------------------------------

def puff_cloud(main, n_sub=7, sub_r=(0.28, 0.42), seed=0, min_z=-0.35, embed=0.78, others=None,
               skip_inside=0.92, golden=True):
    """Scatter small puffs over the surface of each main puff (cloud / cauliflower foliage).
    main: [(center, radius, scale3)]; returns a list of extra puffs in the same format.
    min_z: skip directions pointing further down than this (keeps undersides calmer)."""
    rng = random.Random(seed)
    others = main if others is None else others
    out = []
    for (c, r, sc) in main:
        c = Vector(c)
        cnt = 0
        tries = n_sub * 4
        off = rng.random() * 10
        for i in range(tries):
            if cnt >= n_sub:
                break
            # fibonacci-ish direction with jitter
            k = (i + off) / tries
            z = 1 - 2 * k
            if z < min_z:
                continue
            rr = math.sqrt(max(0.0, 1 - z * z))
            a = i * math.pi * (3 - math.sqrt(5)) + off
            d = Vector((rr * math.cos(a), rr * math.sin(a), z))
            d = (d + Vector((rng.uniform(-.25, .25), rng.uniform(-.25, .25), rng.uniform(-.15, .15)))).normalized()
            p = c + Vector((d.x * r * sc[0], d.y * r * sc[1], d.z * r * sc[2])) * embed
            # skip points buried inside another main puff
            buried = False
            for (c2, r2, sc2) in others:
                if Vector(c2) == c:
                    continue
                q = p - Vector(c2)
                q = Vector((q.x / sc2[0], q.y / sc2[1], q.z / sc2[2]))
                if q.length < r2 * skip_inside:
                    buried = True
                    break
            if buried:
                continue
            sr = rng.uniform(*sub_r) * r
            out.append((p, sr, (1.0, 1.0, rng.uniform(0.82, 0.95))))
            cnt += 1
    return out


def leaf_shingles(main, n_sub=10, size=(0.42, 0.55), flat=(0.38, 0.5), seed=0, min_z=-0.5, embed=0.9,
                  tilt=0.35, others=None, skip_inside=0.9, max_z=1.0):
    """Oblate leaf-clump discs laid over each main puff like shingles (short axis ~ outward normal,
    tipped upward by `tilt` so the lower lips overhang and catch a shadow). Returns puffs with a 4th
    element (rotation quaternion) for blob_mesh."""
    rng = random.Random(seed)
    others = main if others is None else others
    out = []
    zax = Vector((0, 0, 1))
    for (c, r, sc) in main:
        c = Vector(c)
        cnt = 0
        tries = n_sub * 4
        off = rng.random() * 10
        for i in range(tries):
            if cnt >= n_sub:
                break
            k = (i + off) / tries
            z = 1 - 2 * (k % 1.0)
            if z < min_z or z > max_z:
                continue
            rr = math.sqrt(max(0.0, 1 - z * z))
            a = i * math.pi * (3 - math.sqrt(5)) + off
            d = Vector((rr * math.cos(a), rr * math.sin(a), z))
            d = (d + Vector((rng.uniform(-.2, .2), rng.uniform(-.2, .2), rng.uniform(-.12, .12)))).normalized()
            p = c + Vector((d.x * r * sc[0], d.y * r * sc[1], d.z * r * sc[2])) * embed
            buried = False
            for (c2, r2, sc2) in others:
                if Vector(c2) == c:
                    continue
                q = p - Vector(c2)
                q = Vector((q.x / sc2[0], q.y / sc2[1], q.z / sc2[2]))
                if q.length < r2 * skip_inside:
                    buried = True
                    break
            if buried:
                continue
            nrm = (d + Vector((0, 0, tilt))).normalized()
            q = zax.rotation_difference(nrm)
            q = q @ Quaternion(zax, rng.uniform(0, math.tau))
            sr = rng.uniform(*size) * r
            out.append((p, sr, (1.0, rng.uniform(0.8, 1.0), rng.uniform(*flat)), q))
            cnt += 1
    return out


def blob_mesh(name, puffs, mat, voxel=0.07, target_tris=3000, smooth=(0.6, 3), parent=None, clip_z=None,
              ico=3, disp=None, post=None):
    """Union of ellipsoid puffs [(center, radius, scale3)] -> voxel remesh -> smooth -> decimate.
    clip_z: delete everything below this z and close the hole (flat bottom on the ground).
    disp: (strength, noise_scale, seed) cloud-noise displacement before smoothing."""
    p = Part(name)
    p._mi(mat)
    for pf in puffs:
        c, r, sc = pf[0], pf[1], pf[2]
        rot = pf[3] if len(pf) > 3 else None
        bmesh.ops.create_icosphere(p.bm, subdivisions=ico, radius=r,
                                   matrix=Matrix.LocRotScale(Vector(c), rot, Vector(sc)))
    obj = p.build(parent)
    m = obj.modifiers.new("nat_remesh", "REMESH")
    m.mode = "VOXEL"
    m.voxel_size = voxel
    m.adaptivity = 0.0
    m.use_smooth_shade = True
    tex = None
    if disp:
        tex = bpy.data.textures.new(f"nat_disp_{name}", "CLOUDS")
        tex.noise_scale = disp[1]
        tex.noise_depth = 1
        d = obj.modifiers.new("nat_disp", "DISPLACE")
        d.texture = tex
        d.strength = disp[0]
        d.mid_level = 0.5
        d.texture_coords = "LOCAL"
    if smooth:
        s = obj.modifiers.new("nat_smooth", "SMOOTH")
        s.factor = smooth[0]
        s.iterations = smooth[1]
    hp.apply_modifiers(obj)
    if tex:
        bpy.data.textures.remove(tex)
    if clip_z is not None:
        clip_below(obj, clip_z)
    if post:
        post(obj)
        obj.data.update()
    decimate_to(obj, target_tris)
    return obj


def cloud_pad(c, R, n=6, seed=0, dome=(0.42, 0.52), ring=0.56, zs=0.62, lift=0.1):
    """Cloud-pruned foliage pad: a centre dome plus a ring of overlapping flattened domes."""
    rng = random.Random(seed)
    c = Vector(c)
    out = [(c + Vector((0, 0, lift * R)), R * 0.56, (1.0, 1.0, zs))]
    ph = rng.random() * math.tau
    for k in range(n):
        a = ph + math.tau * k / n + rng.uniform(-0.25, 0.25)
        rr = R * ring * rng.uniform(0.9, 1.1)
        p = c + Vector((math.cos(a) * rr, math.sin(a) * rr, R * rng.uniform(-0.08, 0.06)))
        out.append((p, R * rng.uniform(*dome), (1.0, rng.uniform(0.85, 1.0), zs * rng.uniform(0.9, 1.1))))
    return out


def flatten_under(pads, k=0.18, soft=0.25):
    """post-hook for blob_mesh: squash everything below each pad's underside plane (z = c.z - k*R)
    toward that plane -> flat-bottomed cloud pads with a softly rounded rim."""
    def f(obj):
        for v in obj.data.vertices:
            p = v.co
            best = min(pads, key=lambda pr: ((p.x - pr[0][0]) ** 2 + (p.y - pr[0][1]) ** 2) / pr[1] ** 2
                       + ((p.z - pr[0][2]) / pr[1]) ** 2 * 4)
            zb = best[0][2] - k * best[1]
            if p.z < zb:
                v.co.z = zb + (p.z - zb) * soft
    return f


def remesh_obj(obj, voxel=0.03, smooth=(0.5, 4), target_tris=1200, clip_z=None):
    """Voxel-remesh an object made of overlapping closed parts (trunk + roots + limbs) into one
    seamless surface (smoothing fillets the forks), then decimate to the budget."""
    m = obj.modifiers.new("nat_remesh", "REMESH")
    m.mode = "VOXEL"
    m.voxel_size = voxel
    m.adaptivity = 0.0
    m.use_smooth_shade = True
    if smooth:
        s = obj.modifiers.new("nat_smooth", "SMOOTH")
        s.factor = smooth[0]
        s.iterations = smooth[1]
    hp.apply_modifiers(obj)
    if clip_z is not None:
        clip_below(obj, clip_z)
    decimate_to(obj, target_tris)
    return obj


def clip_below(obj, z):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=(0, 0, z), plane_no=(0, 0, 1), clear_inner=True)
    edges = [e for e in bm.edges if e.is_boundary]
    if edges:
        bmesh.ops.holes_fill(bm, edges=edges, sides=0)
        # triangulate the cap so it doesn't become one giant ngon
        caps = [f for f in bm.faces if abs(f.normal.z + 1) < 1e-3 and len(f.verts) > 4]
        if caps:
            bmesh.ops.triangulate(bm, faces=caps)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def decimate_to(obj, target_tris):
    tris = hp.obj_tris(obj)
    if tris > target_tris:
        m = obj.modifiers.new("nat_decimate", "DECIMATE")
        m.decimate_type = "COLLAPSE"
        m.ratio = target_tris / tris
        m.use_collapse_triangulate = True
        hp.apply_modifiers(obj)
    return obj


def blend_normals(obj, centers, weight=0.5, falloff=3.0):
    """Custom split normals = lerp(surface normal, ellipsoid normal of the nearest centres, weight).
    centers: [(center, radius, scale3)]. Gives foliage the soft 'one big shape' shading of
    stylized trees while the silhouette keeps its puffs."""
    me = obj.data
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    if "sharp_edge" in me.attributes:
        me.attributes.remove(me.attributes["sharp_edge"])
    if "sharp_face" in me.attributes:
        me.attributes.remove(me.attributes["sharp_face"])
    me.update()
    cs = [(Vector(c), r, Vector(sc)) for (c, r, sc) in centers]
    out = []
    for v in me.vertices:
        p = v.co
        acc = Vector((0, 0, 0))
        ws = []
        for (c, r, sc) in cs:
            q = p - c
            qs = Vector((q.x / sc.x, q.y / sc.y, q.z / sc.z))
            d = qs.length - r
            ws.append(math.exp(-falloff * d / max(r, 1e-3)))
        tot = sum(ws) or 1.0
        for w, (c, r, sc) in zip(ws, cs):
            q = p - c
            g = Vector((q.x / (sc.x * sc.x), q.y / (sc.y * sc.y), q.z / (sc.z * sc.z)))
            if g.length > 1e-6:
                acc += g.normalized() * (w / tot)
        if acc.length < 1e-6:
            acc = v.normal.copy()
        n = (v.normal * (1 - weight) + acc.normalized() * weight).normalized()
        out.append(n)
    me.normals_split_custom_set_from_vertices(out)
    me.update()
    return obj


# ---------------------------------------------------------------------------
# chiselled rock chunks
# ---------------------------------------------------------------------------

def bm_fill_boundary(bm):
    edges = [e for e in bm.edges if e.is_boundary]
    if edges:
        bmesh.ops.holes_fill(bm, edges=edges, sides=0)


def bm_cut(bm, co, no, keep="inner"):
    """Bisect with plane (co, no) and keep the side behind the normal ('inner') or in front ('outer');
    the opening is closed with an n-gon (planar cut face)."""
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=Vector(co), plane_no=Vector(no),
                           clear_outer=(keep == "inner"), clear_inner=(keep == "outer"))
    bm_fill_boundary(bm)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def refine_planar(bm, max_len=0.3, passes=3):
    """Triangulate n-gons and split long edges (shape-preserving) so flat faces get interior vertices
    for vertex AO / colour variation. Run BEFORE bevelling (bevel only hits real creases)."""
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
    for _ in range(passes):
        long_e = [e for e in bm.edges if e.calc_length() > max_len and
                  (len(e.link_faces) != 2 or e.calc_face_angle(1.0) < math.radians(0.5))]
        if not long_e:
            break
        bmesh.ops.subdivide_edges(bm, edges=long_e, cuts=1, use_grid_fill=False)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3], quad_method="BEAUTY",
                              ngon_method="BEAUTY")
    flat = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(1.0) < math.radians(0.5)]
    bmesh.ops.beautify_fill(bm, faces=bm.faces[:], edges=flat, use_restrict_tag=False)
    return bm


def boulder(size, seed, corner=(0.16, 0.34), edge=(0.08, 0.22), bottom_k=0.45, chips=4,
            chip_depth=(0.03, 0.07), shear=0.12, jitter=0.3, top_cut=None, skip_top_corners=False,
            top_k=1.0):
    """Chiselled boulder: a (sheared) box whose 8 corners and 12 edges are all knocked off by jittered
    planar cuts -> chunky facets, no long box edges left, plateau on top. Depths are fractions of the
    chunk's extent along each cut normal; cuts on the buried bottom side are scaled by bottom_k."""
    rng = random.Random(seed)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Diagonal((size[0], size[1], size[2], 1.0)))
    sh = Matrix.Identity(4)
    sh[0][2] = rng.uniform(-shear, shear)
    sh[1][2] = rng.uniform(-shear, shear)
    sh[0][1] = rng.uniform(-shear, shear) * 0.5
    bmesh.ops.transform(bm, matrix=sh, verts=bm.verts[:])
    plan = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                if skip_top_corners and sz > 0:
                    continue
                d = Vector((sx / size[0], sy / size[1], sz / size[2]))
                plan.append((d, corner, -1 if sz < 0 else 1))
    for ax in range(3):
        for s1 in (-1, 1):
            for s2 in (-1, 1):
                d = [0.0, 0.0, 0.0]
                o = [i for i in range(3) if i != ax]
                d[o[0]] = s1 / size[o[0]]
                d[o[1]] = s2 / size[o[1]]
                plan.append((Vector(d), edge, -1 if d[2] < 0 else (1 if d[2] > 0 else 0)))
    rng.shuffle(plan)
    for d, rngd, low in plan:
        d = d.normalized() + Vector((rng.uniform(-jitter, jitter), rng.uniform(-jitter, jitter),
                                     rng.uniform(-jitter, jitter) * 0.6))
        d.normalize()
        dots = [v.co.dot(d) for v in bm.verts]
        hi, lo = max(dots), min(dots)
        frac = rng.uniform(*rngd) * (bottom_k if low < 0 else (top_k if low > 0 else 1.0))
        bm_cut(bm, d * (hi - (hi - lo) * frac), d, keep="inner")
    if top_cut:
        d = Vector(top_cut[0]).normalized()
        dots = [v.co.dot(d) for v in bm.verts]
        hi, lo = max(dots), min(dots)
        bm_cut(bm, d * (hi - (hi - lo) * top_cut[1]), d, keep="inner")
    for i in range(chips):
        d = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.1, 1))).normalized()
        dots = [v.co.dot(d) for v in bm.verts]
        hi, lo = max(dots), min(dots)
        bm_cut(bm, d * (hi - (hi - lo) * rng.uniform(*chip_depth)), d, keep="inner")
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(2.0), verts=bm.verts[:], edges=bm.edges[:])
    return bm


def find_plateau(bvh, xmin, xmax, ymin, ymax, min_nz=0.85, step=0.08, band=0.25, ztop=20.0):
    """Centre (x, y) and rough radius of the flat top region: ray-cast a grid downward, keep hits
    with normal.z >= min_nz lying within `band` of the highest such hit."""
    hits = []
    x = xmin
    while x <= xmax:
        y = ymin
        while y <= ymax:
            loc, nrm, _, _ = bvh.ray_cast(Vector((x, y, ztop)), Vector((0, 0, -1)), 100.0)
            if loc is not None and nrm.z >= min_nz:
                hits.append(loc)
            y += step
        x += step
    if not hits:
        return None
    zmax = max(h.z for h in hits)
    top = [h for h in hits if h.z > zmax - band]
    cx = sum(h.x for h in top) / len(top)
    cy = sum(h.y for h in top) / len(top)
    r = math.sqrt(len(top) * step * step / math.pi)
    return (cx, cy), r


def obj_append(part, obj, mat_map=None):
    """Copy an object's mesh (world transform applied) into a Part, keeping per-face materials."""
    me = obj.data
    mw = obj.matrix_world
    names = [m.name if m else "" for m in me.materials]
    mis = [part._mi((mat_map or {}).get(nm, nm)) for nm in names] or [0]
    bm = part.bm
    vs = [bm.verts.new(mw @ v.co) for v in me.vertices]
    for p in me.polygons:
        try:
            f = bm.faces.new([vs[i] for i in p.vertices])
        except ValueError:
            continue
        f.material_index = mis[p.material_index] if p.material_index < len(mis) else mis[0]
        f.smooth = True


def bevel_pieces(name, pieces, refine=0.4, angle=28):
    """pieces: [(bmesh, mat, matrix_or_None, bevel_width, bevel_segments)]. Each piece is refined,
    bevelled on its own (so pebbles can get a cheap chamfer and hero chunks a round bevel), then all
    are merged into ONE Part (returned, not built). Finish the built object with finish_hard()."""
    out = Part(name)
    for i, (bm, mat, M, width, seg) in enumerate(pieces):
        b = bm.copy()
        if M is not None:
            bmesh.ops.transform(b, matrix=M, verts=b.verts[:])
        if refine:
            refine_planar(b, max_len=refine)
        tp = Part(f"_tmp_{name}_{i}")
        bm_append(tp, b, mat)
        b.free()
        o = tp.build()
        hp.smooth_obj(o, angle=angle)
        if width > 0 and seg > 0:
            hp.bevel_obj(o, width=width, segments=seg, angle=angle, harden=False)
        obj_append(out, o)
        me = o.data
        bpy.data.objects.remove(o)
        bpy.data.meshes.remove(me)
    return out


def finish_hard(obj, angle=50):
    """Smooth across bevel segments, keep remaining creases sharp, face-area weighted normals so the
    big planar faces stay flat and the bevels carry the curvature (= 'harden normals')."""
    hp.smooth_obj(obj, angle=angle, keep_existing_sharp=False)
    m = obj.modifiers.new("nat_wn", "WEIGHTED_NORMAL")
    m.weight = 50
    m.keep_sharp = True
    m.mode = "FACE_AREA"
    hp.apply_modifiers(obj)
    return obj


def bm_split(bm, co, no):
    """Split a chunk along a plane -> (behind, in_front) as two closed bmeshes."""
    a = bm.copy()
    b = bm.copy()
    bm_cut(a, co, no, keep="inner")
    bm_cut(b, co, no, keep="outer")
    return a, b


def bm_transform(bm, M):
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts[:])
    return bm


def bm_append(dst_part, src, mat, M=None):
    """Copy a bmesh into a Part (optionally transformed) with material `mat`."""
    mi = dst_part._mi(mat)
    dst = dst_part.bm
    vmap = {}
    for v in src.verts:
        vmap[v] = dst.verts.new(M @ v.co if M is not None else v.co.copy())
    for f in src.faces:
        try:
            nf = dst.faces.new([vmap[v] for v in f.verts])
        except ValueError:
            continue
        nf.material_index = mi
        nf.smooth = True
    return dst_part


# ---------------------------------------------------------------------------
# moss cushions
# ---------------------------------------------------------------------------

def world_bvh(objs):
    verts, polys = [], []
    for o in objs:
        mw = o.matrix_world
        base = len(verts)
        verts.extend(mw @ v.co for v in o.data.vertices)
        polys.extend(tuple(base + i for i in p.vertices) for p in o.data.polygons)
    return BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)


def moss_clumps(bvh, center, radius, seed=0, n=14, size=(0.12, 0.2), flat=(0.4, 0.55), min_nz=0.7,
                lift=0.25, ztop=20.0):
    """Clumpy moss: flattened mini-puffs ray-cast onto the flat-enough surface around `center`
    (bigger in the middle, smaller toward the rim). Returns puffs (with rotation) for blob_mesh."""
    rng = random.Random(seed)
    out = []
    zax = Vector((0, 0, 1))
    for i in range(n * 8):
        if len(out) >= n:
            break
        rr = radius * math.sqrt(rng.random())
        a = rng.uniform(0, math.tau)
        x, y = center[0] + math.cos(a) * rr, center[1] + math.sin(a) * rr
        loc, nrm, _, _ = bvh.ray_cast(Vector((x, y, ztop)), Vector((0, 0, -1)), 100.0)
        if loc is None or nrm.z < min_nz:
            continue
        r = rng.uniform(*size) * (1.2 - 0.5 * rr / radius)
        fz = rng.uniform(*flat)
        q = zax.rotation_difference(nrm) @ Quaternion(zax, rng.uniform(0, math.tau))
        out.append((loc + nrm * r * fz * lift, r, (1.0, rng.uniform(0.75, 1.0), fz), q))
    return out


# ---------------------------------------------------------------------------
# vertex colours
# ---------------------------------------------------------------------------

def bake_parts(root, jobs, samples=40, ground=0.0):
    """jobs: [(mesh_obj, dict(distance=, strength=, floor=, tint=...)), ...]. Every mesh of the
    prop occludes; each job may use its own AO distance / tint. Meshes not listed get a default."""
    allm = hp.tree_meshes(root)
    bpy.context.view_layer.update()
    done = set()
    for obj, kw in jobs:
        k = dict(samples=samples, ground=ground)
        k.update(kw)
        hp.bake_vertex_ao(objs=[obj], occluders=allm, **k)
        done.add(obj.name)
    rest = [o for o in allm if o.name not in done]
    if rest:
        hp.bake_vertex_ao(objs=rest, occluders=allm, samples=samples, ground=ground, distance=0.5)


def mul_vcol(obj, fn, skip_prefixes=hp.NO_AO_PREFIXES):
    """Multiply the 'Col' attribute by fn(vertex_index, co_world, normal_world) -> (r, g, b) per vertex."""
    me = obj.data
    attr = me.color_attributes.get(hp.AO_ATTR)
    if attr is None:
        return
    mw = obj.matrix_world
    nm = mw.to_3x3().inverted_safe().transposed()
    vals = np.ones((len(me.vertices), 3), dtype=np.float32)
    for v in me.vertices:
        vals[v.index] = fn(v.index, mw @ v.co, (nm @ v.normal).normalized())
    nl = len(me.loops)
    loop_v = np.empty(nl, dtype=np.int64)
    me.loops.foreach_get("vertex_index", loop_v)
    cols = np.empty(nl * 4, dtype=np.float32)
    attr.data.foreach_get("color", cols)
    cols = cols.reshape(nl, 4)
    mult = vals[loop_v]
    skip = set()
    for i, m in enumerate(me.materials):
        if m and any(m.name.startswith(s) for s in skip_prefixes):
            skip.add(i)
    if skip:
        for p in me.polygons:
            if p.material_index in skip:
                mult[p.loop_start:p.loop_start + p.loop_total] = 1.0
    cols[:, :3] = np.clip(cols[:, :3] * mult, 0.0, 1.0)
    attr.data.foreach_set("color", cols.ravel())


def convexity(obj):
    """Per-vertex convexity (>0 convex edge, <0 concave) from neighbour directions."""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    out = np.zeros(len(bm.verts), dtype=np.float32)
    for v in bm.verts:
        n = v.normal
        acc, cnt = 0.0, 0
        for e in v.link_edges:
            o = e.other_vert(v)
            d = v.co - o.co
            if d.length > 1e-6:
                acc += n.dot(d.normalized())
                cnt += 1
        out[v.index] = acc / max(cnt, 1)
    bm.free()
    return out

