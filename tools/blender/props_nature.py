"""Nature props: aether crystals, boulders, trees, bush  (hi-poly).

Builders for props.glb (assembled by model_props.py). Each builder returns the prop's top-level
object named exactly as in ASSET_SPEC.md, origin at its base centre on the ground (z = 0).

Form language
    trees / bush : smooth spline trunks with root buttresses, cloud-like foliage built as a union of
                   puffs (voxel remesh -> decimate), custom normals blended toward the clump centres
                   (soft stylized shading) + vertex AO / colour gradient (light warm top, cool dark inside)
    rocks        : boxes chiselled by random planes (big planar faces), split / stacked into strata,
                   bevelled + hardened normals, soft moss cushions draped over the tops
    crystal      : faceted quartz shards (flat) with emissive facet / edge-glint materials on a
                   chiselled rock, brass harvesting clamp + half-buried gear

Test this group alone (no props.glb export):
    blender -b --factory-startup -P tools/blender/model_props.py -- --group=nature --previews [--back] [--only=prop_x]
Test export to a scratch dir:  ... -- --group=nature --out=<dir>
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: E402,F401,F403
from env_helpers import *  # noqa: E402,F401,F403
from env_helpers import Xform, mtx, box_m, set_mat  # noqa: E402,F401
from mathutils import Matrix, Vector, noise  # noqa: E402,F401
import hp_helpers as hp  # noqa: E402,F401
import hp_nature_helpers as nh  # noqa: E402
from hp_nature_helpers import smoothstep, lerp, lerp3  # noqa: E402


def setup_mats():
    """Group-specific materials ('nat_*', emissive 'glow_nat_*'). Base colours are the LIGHTEST tone
    of each surface: the baked vertex colour (AO x gradient) only darkens / shifts them."""
    get_mat("nat_bark", hex="#8a6446", roughness=0.9)
    get_mat("nat_bark_dark", hex="#6a4a36", roughness=0.9)
    get_mat("nat_leaf_teal", hex="#66b08c", roughness=0.85)
    get_mat("nat_leaf_autumn", hex="#f7b24a", roughness=0.85)
    get_mat("nat_leaf_bush", hex="#86c27a", roughness=0.85)
    get_mat("nat_rock", hex="#c0b49e", roughness=0.92)
    get_mat("nat_rock_dark", hex="#968d80", roughness=0.92)
    get_mat("nat_moss", hex="#7fa24c", roughness=0.95)
    # crystal facets: deep body facets + bright edge glints (glow_cyan / glow_violet are the main facets)
    get_mat("glow_nat_cyan_deep", hex="#0f86b8", emission="#0f86b8", strength=2.2)
    get_mat("glow_nat_cyan_hi", hex="#d9ffff", emission="#d9ffff", strength=7.0)
    get_mat("glow_nat_violet_deep", hex="#5a2fb0", emission="#5a2fb0", strength=2.2)
    get_mat("glow_nat_violet_hi", hex="#f0dcff", emission="#f0dcff", strength=7.0)


# ---------------------------------------------------------------------------
# shared bits
# ---------------------------------------------------------------------------

def _finish_foliage(obj, centers, weight=0.55, falloff=3.0):
    nh.blend_normals(obj, centers, weight=weight, falloff=falloff)
    return obj


def _canopy_tint(zlo, zhi, shadow, light, mott=0.12, seed=0, pads=None, local=0.0, mid=None):
    """Vertical gradient (cool dark bottom -> warm light top) mixed with an up-facing term, low-freq
    mottling, optional per-clump colour (pads=[(center, radius, rgb)]). Multipliers are LINEAR
    (0.3 linear ~ 0.58 sRGB), so shadows need small values."""
    off = Vector((seed * 7.3, seed * 3.1, seed * 1.7))

    def f(p, n):
        h = smoothstep(zlo, zhi, p.z)
        up = 0.5 + 0.5 * n.z
        t = (1 - local) * h + local * up
        t = smoothstep(0.0, 1.0, min(1.0, t * (0.75 + 0.5 * up)))
        if mid is None:
            c = lerp3(shadow, light, t)
        elif t < 0.5:
            c = lerp3(shadow, mid, t * 2)
        else:
            c = lerp3(mid, light, t * 2 - 1)
        m = 1.0 + mott * noise.noise(p * 1.3 + off)
        c = (c[0] * m, c[1] * m, c[2] * m)
        if pads:
            ws, cols = [], []
            for (pc, pr, pcol) in pads:
                d = (p - Vector(pc)).length / pr
                ws.append(math.exp(-3.0 * d))
                cols.append(pcol)
            tot = sum(ws)
            pc = [sum(w * col[i] for w, col in zip(ws, cols)) / tot for i in range(3)]
            c = (c[0] * pc[0], c[1] * pc[1], c[2] * pc[2])
        return c
    return f


def _bark_tint(z_lo=0.0, z_hi=2.5, base=(0.55, 0.6, 0.5), top=(1.0, 0.97, 0.92), moss=0.55, seed=0):
    """Bark: darker damp base -> lighter top, painterly vertical streaks (grooves), a mossy green
    tinge on the up-facing root flare."""
    off = seed * 13.1

    def f(p, n):
        t = smoothstep(z_lo, z_hi, p.z)
        c = lerp3(base, top, t)
        th = math.atan2(p.y, p.x)
        st = noise.noise(Vector((math.cos(th) * 3.2 + off, math.sin(th) * 3.2, p.z * 0.4)))
        st2 = noise.noise(Vector((math.cos(th) * 6.0, math.sin(th) * 6.0 + off, p.z * 1.2)))
        k = 1.0 - 0.3 * smoothstep(0.0, 0.4, st) - 0.18 * smoothstep(0.15, 0.55, st2)
        mz = moss * (1 - smoothstep(0.1, 0.7, p.z)) * smoothstep(0.1, 0.6, n.z)
        g = (1.0 - 0.35 * mz, 1.0 + 0.05 * mz, 1.0 - 0.55 * mz)
        return (c[0] * k * g[0], c[1] * k * g[1], c[2] * k * g[2])
    return f


def _wood(name, src_part, root, extra=(), voxel=0.028, target=1150, smooth=(0.5, 3)):
    """Union trunk + roots + limbs into one seamless remeshed surface (filleted forks), then merge in
    the un-remeshed extras (stems, pods) -> ONE mesh object named `name` under root."""
    src = src_part.build()
    nh.remesh_obj(src, voxel=voxel, smooth=smooth, target_tris=target, clip_z=-0.3)
    objs = [src] + [e.build() for e in extra]
    out = Part(name)
    for o in objs:
        nh.obj_append(out, o)
        me = o.data
        bpy.data.objects.remove(o)
        bpy.data.meshes.remove(me)
    obj = out.build(root)
    hp.smooth_obj(obj, angle=80)
    return obj


def _pod(part, mat, top, length=0.34, r=0.085, seg=6):
    """Glowing aether seed pod hanging from `top` (teardrop, tip down)."""
    prof = [(0.0, 0.0), (-0.05, r * 0.55), (-0.12, r * 0.95), (-0.2, r), (-0.27, r * 0.7),
            (-length, 0.0)]
    lathe(part, mat, prof, seg=seg, loc=top, cap_bottom=False, cap_top=False)


# ---------------------------------------------------------------------------
# prop_tree — lush round teal crown, flared buttress roots, glowing aether pods
# ---------------------------------------------------------------------------

def _roots(part, mat, n, r_trunk, reach=1.0, seed=0, phase=0.0, z0=0.5, sink=-0.22, seg=7, thick=0.6):
    """Surface roots: thick tapered sweeps leaving the trunk flare, hugging the ground and diving in."""
    rng = random.Random(seed)
    for i in range(n):
        a = phase + 2 * math.pi * i / n + rng.uniform(-0.2, 0.2)
        d = Vector((math.cos(a), math.sin(a), 0.0))
        side = Vector((-d.y, d.x, 0.0)) * rng.uniform(-0.1, 0.1)
        L = reach * rng.uniform(0.8, 1.15)
        r0 = r_trunk * thick * rng.uniform(0.9, 1.1)
        ctrl = [d * r_trunk * 0.3 + Vector((0, 0, z0)),
                d * (r_trunk * 0.85) + Vector((0, 0, z0 * 0.38)),
                d * (r_trunk + L * 0.5) + side + Vector((0, 0, 0.0)),
                d * (r_trunk + L) + side * 2 + Vector((0, 0, sink))]
        nh.sweep(part, mat, ctrl, [r0, r0 * 0.8, r0 * 0.48, r0 * 0.2], seg=seg, n_per=2,
                 tip=True, twist=0.2, cap_start=True)


def build_tree():
    root = empty("prop_tree", size=0.5)
    w = Part("prop_tree_wood_src")

    def trunk_sec(u, a):
        lob = max(0.0, math.cos(5 * (a + 0.4))) ** 1.4
        k = 0.55 * (1 - smoothstep(0.0, 0.22, u)) ** 2.0
        return 1 + k * lob + 0.035 * math.sin(3 * a + u * 9) + 0.035 * math.sin(7 * a + 2.0 * u)

    nh.sweep(w, "nat_bark", [(0, 0, -0.25), (0.02, 0.0, 0.3), (0.12, -0.04, 1.0), (0.1, 0.02, 1.7),
                             (0.02, 0.02, 2.3), (0.0, 0.02, 2.9)],
             [0.42, 0.33, 0.27, 0.245, 0.225, 0.17], seg=20, n_per=3, section=trunk_sec, twist=0.7,
             cap_end=True, cap_start=True)
    _roots(w, "nat_bark", 5, 0.36, reach=0.6, seed=3, phase=0.4 - 0.15, z0=0.5)
    limbs = [
        ([(0.05, 0.0, 2.1), (0.45, -0.15, 2.62), (0.95, -0.3, 3.1)], [0.15, 0.11, 0.075]),
        ([(0.0, 0.03, 2.25), (-0.42, 0.2, 2.8), (-0.88, 0.36, 3.25)], [0.15, 0.1, 0.07]),
        ([(0.05, 0.04, 2.4), (0.14, 0.45, 2.95), (0.26, 0.85, 3.4)], [0.12, 0.08, 0.05]),
        ([(0.09, 0.0, 1.8), (0.5, 0.42, 2.15), (0.98, 0.9, 2.38)], [0.08, 0.058, 0.035]),
        ([(0.06, 0.0, 2.0), (-0.45, -0.44, 2.28), (-0.92, -0.88, 2.44)], [0.075, 0.055, 0.032]),
    ]
    for ctrl, rad in limbs:
        nh.sweep(w, "nat_bark", ctrl, rad, seg=10, n_per=3, tip=True, twist=0.4, cap_start=True)

    main = [  # (center, radius, scale): a core + four drooping side lobes + crown + two shoulders
        ((0.0, 0.0, 3.75), 1.05, (1.05, 1.0, 0.8)),
        ((0.1, 0.05, 4.4), 1.05, (1.05, 1.0, 0.85)),
        ((1.3, -0.3, 3.45), 0.92, (1.0, 1.0, 0.82)),
        ((-1.25, 0.35, 3.6), 0.95, (1.0, 1.0, 0.82)),
        ((0.25, 1.2, 3.5), 0.88, (1.0, 1.0, 0.82)),
        ((-0.4, -1.15, 3.62), 0.85, (1.0, 1.0, 0.82)),
        ((1.0, 0.95, 4.05), 0.62, (1.0, 1.0, 0.9)),
        ((-1.0, -0.75, 4.15), 0.6, (1.0, 1.0, 0.9)),
    ]
    subs = nh.puff_cloud(main, n_sub=4, sub_r=(0.4, 0.5), seed=7, min_z=-0.2, embed=0.78)
    sh = nh.leaf_shingles(main, n_sub=12, size=(0.36, 0.48), flat=(0.36, 0.48), seed=8, min_z=-0.55,
                          embed=0.93, tilt=0.4)
    # two small leaf tufts on the low side branches break up the crown's underside
    tufts = [((1.04, 0.95, 2.46), 0.36, (1.05, 1.0, 0.85)), ((-0.98, -0.93, 2.52), 0.33, (1.05, 1.0, 0.85))]
    sh += nh.leaf_shingles(tufts, n_sub=6, size=(0.5, 0.62), flat=(0.4, 0.5), seed=9, min_z=-0.3,
                           embed=0.9, tilt=0.4, others=tufts)
    canopy = nh.blob_mesh("prop_tree_canopy", main + subs + tufts + sh, "nat_leaf_teal", voxel=0.05,
                          target_tris=3200, smooth=(0.3, 1), parent=root)
    _finish_foliage(canopy, main + tufts, weight=0.45, falloff=4.0)

    # aether pods hanging under the crown
    bvh = nh.world_bvh([canopy])
    pods = Part("_prop_tree_pods")
    for (x, y) in ((0.95, -0.75), (-1.15, -0.25), (0.15, -1.1), (-0.55, 1.0)):
        loc, _, _, _ = bvh.ray_cast(Vector((x, y, 0.5)), Vector((0, 0, 1)), 10.0)
        if loc is None:
            continue
        top = loc + Vector((0, 0, 0.1))
        nh.sweep(pods, "nat_bark", [top + Vector((0, 0, 0.1)), top - Vector((0, 0, 0.17))], [0.016, 0.012],
                 seg=4, n_per=1, cap_end=False)
        _pod(pods, "glow_cyan", tuple(top - Vector((0, 0, 0.15))), length=0.26, r=0.07)
    trunk = _wood("prop_tree_trunk", w, root, extra=[pods], voxel=0.026, target=1150)

    nh.bake_parts(root, [
        (canopy, dict(distance=1.0, strength=0.9, floor=0.25,
                      tint=_canopy_tint(2.3, 5.4, (0.08, 0.17, 0.36), (1.0, 0.98, 0.9), seed=1, local=0.45,
                                        mid=(0.41, 0.61, 0.75)))),
        (trunk, dict(distance=0.8, strength=0.8, floor=0.3, tint=_bark_tint(seed=1))),
    ])
    return root


# ---------------------------------------------------------------------------
# prop_tree_b — gnarled autumn tree with cloud-pruned leaf pads on twisting limbs
# ---------------------------------------------------------------------------

def build_tree_b():
    root = empty("prop_tree_b", size=0.5)
    w = Part("prop_tree_b_wood_src")

    def trunk_sec(u, a):
        lob = max(0.0, math.cos(4 * (a + 1.1))) ** 1.4
        k = 0.5 * (1 - smoothstep(0.0, 0.3, u)) ** 2.0
        return 1 + k * lob + 0.06 * math.sin(2 * a + u * 11)

    nh.sweep(w, "nat_bark_dark", [(0, 0, -0.25), (0.0, 0.0, 0.3), (0.14, 0.06, 0.85), (0.06, 0.0, 1.35),
                                  (0.05, 0.02, 1.6)],
             [0.38, 0.3, 0.25, 0.23, 0.2], seg=16, n_per=3, section=trunk_sec, twist=1.2, cap_end=True,
             cap_start=True)
    _roots(w, "nat_bark_dark", 4, 0.33, reach=0.55, seed=13, phase=1.1 - 0.1, z0=0.45)
    pads = [  # center, radius, scale
        ((1.3, -0.1, 2.95), 1.0, (1.15, 1.0, 0.45)),
        ((-0.95, 0.2, 3.45), 0.95, (1.1, 1.05, 0.45)),
        ((0.2, 0.62, 4.0), 0.8, (1.05, 1.0, 0.5)),
        ((0.42, -0.95, 2.45), 0.58, (1.1, 1.0, 0.52)),
    ]
    limbs = [
        ([(0.07, 0.0, 1.25), (0.5, -0.05, 1.7), (0.78, -0.22, 2.3), (1.2, -0.1, 2.8)], [0.17, 0.13, 0.1, 0.07]),
        ([(0.0, 0.02, 1.3), (-0.38, 0.02, 1.95), (-0.6, 0.25, 2.65), (-0.88, 0.2, 3.3)], [0.17, 0.13, 0.09, 0.06]),
        ([(0.05, 0.05, 1.45), (0.3, 0.3, 2.15), (0.06, 0.5, 2.95), (0.24, 0.62, 3.85)], [0.14, 0.11, 0.08, 0.055]),
        ([(0.45, -0.1, 1.8), (0.55, -0.55, 2.15), (0.45, -0.9, 2.4)], [0.08, 0.06, 0.04]),
        ([(-0.32, 0.1, 2.0), (-0.75, -0.3, 2.5), (-1.0, -0.55, 2.75)], [0.06, 0.045, 0.03]),
    ]
    for ctrl, rad in limbs:
        nh.sweep(w, "nat_bark_dark", ctrl, rad, seg=10, n_per=3, tip=True, twist=0.6, cap_start=True)
    extra = [((-1.0, -0.6, 2.8), 0.42, (1.1, 1.0, 0.58))]
    # cloud-pruned pads: a centre dome + ring of domes each, flat undersides, crisp per-dome shading
    pad_defs = [(c, r * 1.05) for (c, r, _) in pads] + [(extra[0][0], 0.5)]
    domes = []
    rim = []
    for i, (c, R) in enumerate(pad_defs):
        domes += nh.cloud_pad(c, R, n=6 if R > 0.7 else 5, seed=30 + i, zs=0.74, lift=0.14)
        # leafy scalloped rim: small upturned leaf clumps around each pad's edge
        rim += nh.leaf_shingles([(c, R * 0.86, (1.0, 1.0, 0.36))], n_sub=12 if R > 0.7 else 8,
                                size=(0.24, 0.32), flat=(0.4, 0.5), seed=50 + i, min_z=-0.5, max_z=0.45,
                                embed=0.98, tilt=0.35, others=[])
    canopy = nh.blob_mesh("prop_tree_b_canopy", domes + rim, "nat_leaf_autumn", voxel=0.045, target_tris=3500,
                          smooth=(0.3, 1), parent=root, post=nh.flatten_under(pad_defs, k=0.2))
    _finish_foliage(canopy, domes + [x[:3] for x in rim], weight=0.7, falloff=8.0)
    trunk = _wood("prop_tree_b_trunk", w, root, voxel=0.024, target=1400)

    pad_cols = [
        (pads[0][0], 1.4, (1.0, 0.6, 0.62)),    # red-orange
        (pads[1][0], 1.4, (1.0, 0.98, 0.9)),    # gold
        (pads[2][0], 1.2, (1.0, 0.8, 0.7)),     # orange
        (pads[3][0], 0.9, (0.92, 0.48, 0.55)),  # deep red
        (extra[0][0], 0.8, (1.0, 0.82, 0.75)),
    ]
    nh.bake_parts(root, [
        (canopy, dict(distance=0.9, strength=0.9, floor=0.25,
                      tint=_canopy_tint(2.1, 4.6, (0.17, 0.05, 0.12), (1.0, 1.0, 1.0), seed=2, pads=pad_cols,
                                        local=0.55, mid=(0.74, 0.42, 0.4)))),
        (trunk, dict(distance=0.8, strength=0.8, floor=0.3, tint=_bark_tint(z_hi=2.2, seed=2))),
    ])
    return root


# ---------------------------------------------------------------------------
# prop_bush — soft clumped bush with glowing violet berries
# ---------------------------------------------------------------------------

def build_bush():
    root = empty("prop_bush", size=0.5)
    main = [  # a crown of distinct leaf clumps around a core
        ((0.0, 0.0, 0.3), 0.36, (1.15, 1.05, 0.8)),
        ((0.05, 0.02, 0.6), 0.22, (1.0, 1.0, 0.88)),
        ((0.36, 0.14, 0.27), 0.25, (1.0, 1.0, 0.9)),
        ((-0.34, 0.16, 0.26), 0.25, (1.0, 1.0, 0.9)),
        ((0.12, -0.33, 0.24), 0.23, (1.0, 1.0, 0.9)),
        ((-0.22, -0.26, 0.28), 0.21, (1.0, 1.0, 0.9)),
        ((-0.05, 0.38, 0.27), 0.22, (1.0, 1.0, 0.9)),
        ((0.3, -0.12, 0.5), 0.2, (1.0, 1.0, 0.9)),
        ((-0.26, 0.05, 0.52), 0.2, (1.0, 1.0, 0.9)),
        ((0.12, 0.28, 0.5), 0.19, (1.0, 1.0, 0.9)),
    ]
    sh = nh.leaf_shingles(main[2:], n_sub=4, size=(0.5, 0.62), flat=(0.4, 0.5), seed=27, min_z=-0.2,
                          embed=0.95, tilt=0.5, others=main)
    leaves = nh.blob_mesh("prop_bush_leaves", main + sh, "nat_leaf_bush", voxel=0.022, target_tris=840,
                          smooth=(0.25, 1), parent=root, clip_z=-0.06)
    _finish_foliage(leaves, main + [x[:3] for x in sh], weight=0.75, falloff=9.0)
    # berries: ray-cast from outside toward the clump centres
    bvh = nh.world_bvh([leaves])
    b = Part("prop_bush_berries")
    rng = random.Random(5)
    for k, (az, el) in enumerate(((20, 25), (110, 40), (200, 18), (290, 30), (340, 60))):
        a, e = math.radians(az), math.radians(el)
        d = Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
        o = Vector((0, 0, 0.25)) + d * 2.0
        loc, nrm, _, _ = bvh.ray_cast(o, -d, 5.0)
        if loc is None:
            continue
        t1 = nrm.cross(Vector((0, 0, 1)))
        if t1.length < 1e-3:
            t1 = Vector((1, 0, 0))
        t1.normalize()
        t2 = nrm.cross(t1)
        for i in range(2 if k % 2 == 0 else 1):
            jit = (t1 * math.cos(i * 2.4 + k) + t2 * math.sin(i * 2.4 + k)) * 0.04 * i
            r = rng.uniform(0.027, 0.034)
            b.ico("glow_violet", r=r, subdiv=1, loc=tuple(loc + nrm * r * 0.3 + jit))
    berries = b.build(root)
    hp.smooth_obj(berries, angle=180)
    nh.bake_parts(root, [
        (leaves, dict(distance=0.3, strength=0.9, floor=0.25,
                      tint=_canopy_tint(-0.05, 0.8, (0.07, 0.17, 0.15), (1.0, 1.0, 0.9), seed=3, local=0.45,
                                        mid=(0.4, 0.62, 0.52)))),
    ])
    return root


# ---------------------------------------------------------------------------
# rocks
# ---------------------------------------------------------------------------

def _about(c, M):
    """Matrix M applied about point c."""
    c = Vector(c)
    return Matrix.Translation(c) @ M @ Matrix.Translation(-c)


def _rot(deg, axis):
    return Matrix.Rotation(math.radians(deg), 4, Vector(axis).normalized())


def _rock_vcol(obj, seed=0, edge=0.38, base_dark=0.62, zlo=-0.1, zhi=1.2, lichen=0.6,
               side_col=(0.6, 0.66, 0.76)):
    """Painterly stone colouring on top of the baked AO: bright worn convex edges, darker toward the
    ground, slightly lighter / warmer up-facing planes, cool sides, faint lichen patches on top."""
    cv = nh.convexity(obj)
    off = Vector((seed * 3.7, seed * 1.3, seed * 0.7))

    def f(i, p, n):
        e = smoothstep(0.03, 0.22, float(cv[i]))
        k = (1.0 - edge) + edge * e
        g = lerp(base_dark, 1.0, smoothstep(zlo, zhi, p.z))
        top = smoothstep(0.15, 0.8, n.z)
        side = lerp3(side_col, (1.0, 1.0, 1.0), top)
        v = noise.noise(p * 0.8 + off)
        w = 1.0 + 0.1 * noise.noise(p * 2.6 + off * 2)
        warm = (1.0 + 0.05 * v, 1.0, 1.0 - 0.06 * v)
        li = lichen * top * smoothstep(0.25, 0.6, noise.noise(p * 1.9 + off * 3))
        lic = (1.0 - 0.06 * li, 1.0, 1.0 - 0.35 * li)
        return tuple(k * g * w * side[c] * warm[c] * lic[c] for c in range(3))
    nh.mul_vcol(obj, f)


def _moss_tint(p, n):
    """Moss: lighter, warmer sun-catching tops, deeper olive sides, blotchy two-scale variation."""
    m = noise.noise(p * 2.3)
    m2 = noise.noise(p * 6.1 + Vector((3, 1, 2)))
    k = 0.55 + 0.45 * smoothstep(0.3, 1.0, n.z)
    return (k * (0.72 + 0.16 * m + 0.06 * m2), k * (0.8 + 0.12 * m + 0.05 * m2), k * (0.5 + 0.08 * m))


def _moss_mesh(name, puffs, root, target=400):
    """Clumpy moss cushion from moss_clumps() puffs (same union -> decimate language as the foliage)."""
    moss = nh.blob_mesh(name, puffs, "nat_moss", voxel=0.022, target_tris=target, smooth=(0.5, 2), parent=root)
    nh.blend_normals(moss, [q[:3] for q in puffs], weight=0.45, falloff=6.0)
    return moss


def build_rock_a():
    """Wide chiselled boulder: a strata line splits it horizontally, a crack runs through the upper
    slab, a darker companion stone leans on it, pebbles around, a moss cushion on the plateau."""
    root = empty("prop_rock_a", size=0.5)
    big = nh.boulder((2.3, 1.85, 1.4), seed=101, corner=(0.2, 0.38), edge=(0.1, 0.26), chips=5,
                     top_cut=((0.08, -0.06, 1.0), 0.08), top_k=0.55)
    nh.bm_transform(big, Matrix.Translation((0, 0, 0.5)))
    low, up = nh.bm_split(big, (0, 0, 0.34), (0.1, -0.06, 1.0))
    ua, ub = nh.bm_split(up, (0.34, 0.0, 0.0), (0.95, 0.22, 0.1))
    Mup = Matrix.Translation((-0.035, 0.03, 0.025)) @ _about((0, 0, 0.4), _rot(1.2, (1, 0.3, 0)))
    Mub = Matrix.Translation((0.045, 0.01, -0.004)) @ _about((0.45, 0.0, 0.38), _rot(-3.5, (0.22, -0.95, 0))) @ Mup
    comp = nh.boulder((1.0, 0.85, 0.75), seed=102, chips=2)
    pieces = [(low, "nat_rock", None, 0.075, 2), (ua, "nat_rock", Mup, 0.075, 2), (ub, "nat_rock", Mub, 0.075, 2),
              (comp, "nat_rock_dark", mtx((-1.18, -0.42, 0.18), (8, -16, 25)), 0.06, 1)]
    for i, (loc, sz, rot) in enumerate((((0.62, -1.08, 0.04), (0.4, 0.34, 0.28), (0, 10, 40)),
                                        ((1.4, 0.55, 0.03), (0.3, 0.27, 0.22), (-8, 6, 10)))):
        peb = nh.boulder(sz, seed=110 + i, chips=0, corner=(0.2, 0.35), edge=(0.12, 0.25))
        pieces.append((peb, "nat_rock_dark" if i % 2 else "nat_rock", mtx(loc, rot), 0.035, 1))
    stone = nh.bevel_pieces("prop_rock_a_stone", pieces, refine=0.62).build(root)
    nh.finish_hard(stone)
    bvh = nh.world_bvh([stone])
    c, r = nh.find_plateau(bvh, -1.0, 1.0, -0.8, 0.8, min_nz=0.8, band=0.3)
    puffs = nh.moss_clumps(bvh, c, max(0.7, r * 1.2) * 0.55, seed=2, n=10, size=(0.2, 0.28), min_nz=0.62)
    puffs += nh.moss_clumps(bvh, c, max(0.7, r * 1.2), seed=3, n=18, size=(0.12, 0.2), min_nz=0.62)
    puffs += nh.moss_clumps(bvh, (-0.55, 0.35), 0.35, seed=4, n=5, size=(0.09, 0.14), min_nz=0.62)
    moss = _moss_mesh("prop_rock_a_moss", puffs, root, target=500)
    nh.bake_parts(root, [
        (stone, dict(distance=0.55, strength=0.85, floor=0.3)),
        (moss, dict(distance=0.5, strength=0.7, floor=0.4, tint=_moss_tint)),
    ])
    _rock_vcol(stone, seed=1, zhi=1.1)
    return root


def build_rock_b():
    """Tall leaning standing stone made of tilted strata (offset layers -> mossy ledges), a broken-off
    cap lying beside it, a leaning slab and pebbles."""
    root = empty("prop_rock_b", size=0.5)
    tall = nh.boulder((1.3, 1.1, 2.5), seed=201, corner=(0.14, 0.3), edge=(0.08, 0.2), chips=4,
                      top_cut=((-0.5, 0.25, 1.0), 0.16))
    nh.bm_transform(tall, _about((0, 0, -0.15), _rot(5, (0.2, 1, 0))) @ Matrix.Translation((0, 0, 1.1)))
    sn = Vector((0.3, 0.1, 1.0)).normalized()
    l1, rest = nh.bm_split(tall, (0, 0, 0.8), sn)
    l2, l3 = nh.bm_split(rest, (0, 0, 1.62), sn)
    M2 = Matrix.Translation((-0.05, 0.04, 0.025)) @ _about((0, 0, 0.8), _rot(-1.5, (1, 0.2, 0)))
    M3 = Matrix.Translation((0.05, -0.045, 0.03)) @ _about((0, 0, 1.62), _rot(2.0, (0.3, 1, 0))) @ M2
    cap = nh.boulder((0.7, 0.55, 0.42), seed=205, chips=1)
    slab = nh.boulder((0.32, 0.85, 1.2), seed=204, corner=(0.12, 0.25), edge=(0.06, 0.16), chips=1)
    peb = nh.boulder((0.28, 0.25, 0.2), seed=210, chips=0)
    pieces = [(l1, "nat_rock_dark", None, 0.07, 2), (l2, "nat_rock_dark", M2, 0.07, 2),
              (l3, "nat_rock_dark", M3, 0.07, 2),
              (cap, "nat_rock_dark", mtx((0.98, -0.45, 0.1), (14, -8, 35)), 0.05, 1),
              (slab, "nat_rock", mtx((-0.9, -0.05, 0.45), (0, -24, 8)), 0.05, 1),
              (peb, "nat_rock", mtx((0.5, -0.95, 0.03), (0, 8, 30)), 0.03, 1)]
    stone = nh.bevel_pieces("prop_rock_b_stone", pieces, refine=0.45).build(root)
    nh.finish_hard(stone)
    bvh = nh.world_bvh([stone])
    puffs = nh.moss_clumps(bvh, (0.05, 0.0), 0.3, seed=4, n=5, size=(0.17, 0.24), min_nz=0.6)
    puffs += nh.moss_clumps(bvh, (0.05, 0.0), 0.5, seed=5, n=12, size=(0.11, 0.18), min_nz=0.6)
    puffs += nh.moss_clumps(bvh, (-0.55, 0.2), 0.32, seed=6, n=7, size=(0.1, 0.16), min_nz=0.62)
    puffs += nh.moss_clumps(bvh, (0.98, -0.45), 0.28, seed=7, n=6, size=(0.1, 0.15), min_nz=0.62)
    moss = _moss_mesh("prop_rock_b_moss", puffs, root, target=500)
    nh.bake_parts(root, [
        (stone, dict(distance=0.55, strength=0.85, floor=0.3)),
        (moss, dict(distance=0.5, strength=0.7, floor=0.4, tint=_moss_tint)),
    ])
    _rock_vcol(stone, seed=2, zhi=2.2)
    return root


# ---------------------------------------------------------------------------
# prop_crystal
# ---------------------------------------------------------------------------

def _crystal(part, col, base, rot, length, r, seed, embed=0.25, tip=None, seg=6, chamfer=0.16):
    """Quartz shard: irregular hex prism (slight taper toward the root) with a pointed termination.
    Every corner is chamfered into a thin 'edge glint' facet (glow_nat_<col>_hi); the six faces
    alternate between the main glow material and the deep one."""
    rng = random.Random(seed)
    mats = {"cyan": ("glow_cyan", "glow_nat_cyan_deep", "glow_nat_cyan_hi"),
            "violet": ("glow_violet", "glow_nat_violet_deep", "glow_nat_violet_hi")}[col]
    mi = [part._mi(m) for m in mats]
    tip = tip if tip is not None else r * rng.uniform(1.6, 2.2)
    M = mtx(base, rot)
    bm = part.bm
    s0 = rng.random() * math.pi
    rad = [r * rng.uniform(0.85, 1.12) for _ in range(seg)]
    half = math.pi / seg * chamfer

    def ring(z, k):
        out = []
        for j in range(seg):
            a = 2 * math.pi * j / seg + s0
            for da in (-half, half):
                out.append(bm.verts.new(M @ Vector((math.cos(a + da) * rad[j] * k,
                                                    math.sin(a + da) * rad[j] * k, z))))
        return out
    rings = [ring(-embed, 0.82), ring(length * 0.55, 0.96), ring(length, 1.0)]
    ax = Vector((rng.uniform(-0.25, 0.25) * r, rng.uniform(-0.25, 0.25) * r, length + tip))
    apex = bm.verts.new(M @ ax)
    n2 = 2 * seg
    for ri in range(len(rings) - 1):
        a, b = rings[ri], rings[ri + 1]
        for q in range(n2):
            k = (q + 1) % n2
            f = bm.faces.new((a[q], a[k], b[k], b[q]))
            if q % 2 == 0:            # chamfer strip (between the two verts of one corner)
                f.material_index = mi[2]
            else:                     # main face j = q // 2
                j = q // 2
                f.material_index = mi[1] if (ri == 0 or j % 2) else mi[0]
            f.smooth = False
    top = rings[-1]
    for q in range(n2):
        k = (q + 1) % n2
        f = bm.faces.new((top[q], top[k], apex))
        f.material_index = mi[2] if q % 2 == 0 else (mi[0] if (q // 2) % 2 else mi[1])
        f.smooth = False


def _gear(part, mat, r=0.4, thick=0.08, teeth=10, tooth=0.11, rim=0.07, hub=0.08, spokes=4, seg=30,
          loc=(0, 0, 0), rot=(0, 0, 0)):
    """Spoked gear in local XY (axis Z): rim ring + trapezoid teeth + hub + spokes."""
    with Xform(part, mtx(loc, rot)):
        part.torus(mat, R=r - rim / 2, r=rim / 2 / math.cos(math.pi / 4), seg=seg, seg2=4,
                   scale=(1, 1, thick / rim), phase=math.pi / 4)
        part.cyl(mat, r=hub, h=thick * 1.4, seg=12)
        for i in range(spokes):
            a = 180.0 * i / spokes
            box_m(part, mat, mtx((0, 0, 0), (0, 0, a), (2 * (r - rim * 0.6), rim * 0.55, thick * 0.8)))
        w0 = 2 * math.pi * r / teeth * 0.55
        for i in range(teeth):
            a = 2 * math.pi * i / teeth
            ca, sa = math.cos(a), math.sin(a)
            t = Vector((-sa, ca, 0))
            rr = Vector((ca, sa, 0))
            base = rr * (r - 0.01)
            tip = rr * (r + tooth)
            quad = [base - t * w0 / 2, base + t * w0 / 2, tip + t * w0 * 0.3, tip - t * w0 * 0.3]
            vs = [(q.x, q.y, -thick / 2) for q in quad] + [(q.x, q.y, thick / 2) for q in quad]
            part.poly(mat, vs, [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])


def _merge(name, objs, root):
    p = Part(name)
    for o in objs:
        nh.obj_append(p, o)
        me = o.data
        bpy.data.objects.remove(o)
        bpy.data.meshes.remove(me)
    return p.build(root)


def build_crystal():
    """Aether crystal cluster: faceted cyan / violet quartz shards (emissive facets + edge glints) growing
    out of a chiselled dark rock, a brass harvesting clamp with valve and copper feed pipe on the big
    crystal, a half-buried brass gear, a little moss."""
    root = empty("prop_crystal", size=0.5)
    # -- rock base --
    base = nh.boulder((1.8, 1.5, 0.8), seed=301, corner=(0.2, 0.4), edge=(0.12, 0.28), chips=4, top_k=0.7)
    side = nh.boulder((0.85, 0.75, 0.6), seed=302, chips=2)
    side2 = nh.boulder((0.62, 0.52, 0.45), seed=303, chips=1)
    peb1 = nh.boulder((0.26, 0.22, 0.18), seed=310, chips=0)
    peb2 = nh.boulder((0.22, 0.2, 0.16), seed=311, chips=0)
    rock = nh.bevel_pieces("prop_crystal_rock", [
        (base, "nat_rock_dark", mtx((0, 0, 0.12), (0, 0, 8)), 0.06, 2),
        (side, "nat_rock_dark", mtx((0.85, 0.38, 0.06), (6, -10, 30)), 0.05, 2),
        (side2, "nat_rock_dark", mtx((-0.88, -0.45, 0.03), (-8, 6, -20)), 0.04, 2),
        (peb1, "nat_rock_dark", mtx((0.38, -0.98, 0.03), (0, 0, 20)), 0.025, 1),
        (peb2, "nat_rock_dark", mtx((-0.3, 0.95, 0.03), (0, 0, 70)), 0.025, 1),
    ], refine=0.4).build(root)
    nh.finish_hard(rock)
    bvh = nh.world_bvh([rock])

    def ground_z(x, y):
        loc, _, _, _ = bvh.ray_cast(Vector((x, y, 5.0)), Vector((0, 0, -1)), 10.0)
        return loc.z if loc is not None else 0.0

    # -- shards (bases snapped onto the rock surface) --
    s = Part("prop_crystal_shards")
    shards = [  # col, (x, y), rot, length, radius
        ("cyan", (0.0, 0.05), (6, -6, 0), 1.6, 0.23),
        ("cyan", (0.36, 0.16), (12, 30, 0), 0.95, 0.15),
        ("violet", (-0.38, 0.08), (-9, -32, 0), 1.12, 0.17),
        ("violet", (0.16, -0.36), (36, 12, 0), 0.62, 0.12),
        ("cyan", (-0.14, 0.42), (-34, -12, 0), 0.8, 0.13),
        ("cyan", (-0.24, -0.3), (30, -40, 0), 0.5, 0.1),
        ("violet", (0.34, 0.45), (-32, 36, 0), 0.48, 0.09),
        ("violet", (0.98, 0.45), (14, 42, 0), 0.38, 0.085),
        ("cyan", (0.78, 0.2), (-6, 70, 0), 0.3, 0.07),
        ("cyan", (-0.9, -0.48), (22, -34, 0), 0.34, 0.075),
        ("violet", (-0.72, -0.3), (-10, -60, 0), 0.22, 0.055),
        ("cyan", (0.66, -0.74), (34, 52, 0), 0.24, 0.06),
        ("violet", (-0.6, 0.66), (-30, -42, 0), 0.26, 0.065),
        ("cyan", (-0.42, 0.74), (-48, 10, 0), 0.16, 0.045),
        ("violet", (1.15, -0.1), (40, 80, 0), 0.18, 0.05),
        # a small secondary cluster sprouting from the side boulder
        ("cyan", (0.9, 0.5), (-14, 30, 0), 0.42, 0.075),
        ("violet", (0.78, 0.62), (-36, 10, 0), 0.26, 0.055),
        ("cyan", (1.04, 0.32), (26, 64, 0), 0.22, 0.05),
    ]
    main_frame = None
    for i, (c, (x, y), r, L, rad) in enumerate(shards):
        z = ground_z(x, y)
        b = (x, y, z - 0.04)
        _crystal(s, c, b, r, L, rad, seed=400 + i, embed=min(0.3, 0.12 + rad))
        if i == 0:
            main_frame = mtx(b, r)
    # a few aether motes hovering around the big crystal (static; magic hint)
    for i, (pos, r, col) in enumerate((((0.42, -0.2, 1.75), 0.05, "cyan"), ((-0.38, 0.3, 1.95), 0.04, "violet"),
                                       ((0.15, 0.48, 2.35), 0.035, "cyan"), ((-0.5, -0.32, 1.4), 0.03, "cyan"))):
        mats = ("glow_cyan", "glow_nat_cyan_deep") if col == "cyan" else ("glow_violet", "glow_nat_violet_deep")
        bipyramid(s, mats[i % 2], r=r, up=r * 2.2, down=r * 1.6, seg=4, loc=pos, rot=(i * 17, i * 29, i * 41))
    shard_obj = s.build(root)
    hp.flat_obj(shard_obj)

    # -- brass harvesting clamp on the big crystal + valve + copper feed pipe --
    ring = Part("prop_crystal_ring")
    with Xform(ring, main_frame):
        for zz, rr, tr in ((0.62, 0.272, 0.042), (0.9, 0.262, 0.034)):
            ring.torus("brass", R=rr, r=tr, seg=18, seg2=6, loc=(0, 0, zz))
        # rivets around both bands
        for zz, rr in ((0.62, 0.312), (0.9, 0.295)):
            for k in range(6):
                a = math.tau * k / 6 + 0.26
                ring.ico("brass", r=0.017, subdiv=1, loc=(math.cos(a) * rr, math.sin(a) * rr, zz))
    ring_o = ring.build()
    hp.smooth_obj(ring_o, angle=70)
    hw = Part("prop_crystal_hw")
    with Xform(hw, main_frame):
        for k in range(3):
            a = math.radians(k * 120 + 30)
            box_m(hw, "brass", mtx((math.cos(a) * 0.29, math.sin(a) * 0.29, 0.76), (0, 0, math.degrees(a)),
                                   (0.035, 0.05, 0.34)))
        box_m(hw, "brass", mtx((0.33, 0.0, 0.76), (0, 0, 0), (0.12, 0.15, 0.22)))
        hw.cyl("copper", r=0.045, h=0.07, seg=10, loc=(0.41, 0.0, 0.8), rot=(0, 90, 0))
    hw_o = hw.build()
    nh.finish_hard(hp.bevel_obj(hp.smooth_obj(hw_o, angle=40), width=0.012, segments=1, angle=40, harden=False),
                   angle=40)
    wh = Part("prop_crystal_valve")
    with Xform(wh, main_frame @ mtx((0.44, 0.0, 0.8), (0, 90, 0))):
        wh.torus("brass", R=0.075, r=0.014, seg=12, seg2=5)
        for a in (0, 60, 120):
            box_m(wh, "brass", mtx((0, 0, 0), (0, 0, a), (0.15, 0.018, 0.018)))
        wh.cyl("brass", r=0.022, h=0.04, seg=8)
    wh_o = wh.build()
    hp.smooth_obj(wh_o, angle=50)
    # pipe: leaves the housing bottom, arcs outward over the rock (ray-cast clearance) and drops
    # into the ground just past the rock's edge, where a brass collar seals it
    start = main_frame @ Vector((0.33, 0.0, 0.64))
    d = Vector((0.95, 0.32, 0.0)).normalized()
    pts = [start, start + Vector((0.0, 0.0, -0.08)) + d * 0.07]
    k = 0.3
    while k < 1.6:
        x, y = start.x + d.x * k, start.y + d.y * k
        surf = ground_z(x, y)
        pts.append(Vector((x, y, max(surf, 0.0) + 0.055)))
        if surf < 0.03:
            break
        k += 0.14
    end = pts[-1]
    pts.append(Vector((end.x + d.x * 0.08, end.y + d.y * 0.08, -0.25)))
    pp = Part("prop_crystal_pipe")
    nh.sweep(pp, "copper", pts, [0.03] * len(pts), seg=8, n_per=2, cap_end=False, cap_start=False)
    pp.cyl("brass", r=0.052, h=0.06, seg=10, loc=(end.x + d.x * 0.05, end.y + d.y * 0.05, 0.0))
    pipe_o = pp.build()
    hp.smooth_obj(pipe_o, angle=50)
    # half-buried gear leaning on the rock
    g = Part("prop_crystal_gearp")
    _gear(g, "brass", r=0.42, thick=0.075, teeth=10, tooth=0.1, loc=(-0.62, -0.72, 0.1), rot=(72, 0, -28))
    gear_o = g.build()
    hp.smooth_obj(gear_o, angle=40)
    brass = _merge("prop_crystal_brass", [ring_o, hw_o, wh_o, pipe_o, gear_o], root)

    def aether_stain(p, n):
        # rock near the shard roots picks up a faint cool aether tint
        d = Vector((p.x, p.y, 0)).length
        k = 1.0 - smoothstep(0.2, 0.9, d)
        return (1.0 - 0.3 * k, 1.0 - 0.08 * k, 1.0)

    nh.bake_parts(root, [
        (rock, dict(distance=0.5, strength=0.9, floor=0.25, tint=aether_stain)),
        (brass, dict(distance=0.35, strength=0.8, floor=0.35)),
    ])
    _rock_vcol(rock, seed=3, zhi=0.6, base_dark=0.6, lichen=0.0)
    return root


# name, builder, preview kwargs (passed to hp.render_hp)
PROPS = [
    ("prop_crystal", build_crystal, {}),
    ("prop_rock_a", build_rock_a, {}),
    ("prop_rock_b", build_rock_b, {}),
    ("prop_tree", build_tree, {}),
    ("prop_tree_b", build_tree_b, {}),
    ("prop_bush", build_bush, {}),
]

# triangle budget per prop (user-chosen "medium" tier, 2026-10-11)
BUDGET = {
    "prop_crystal": 6000,
    "prop_rock_a": 2500,
    "prop_rock_b": 2500,
    "prop_tree": 5000,
    "prop_tree_b": 5000,
    "prop_bush": 1000,
}
