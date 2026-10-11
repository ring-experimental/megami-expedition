"""arena.glb — circular battle arena (see ASSET_SPEC.md, "arena.glb").

Walkable top surface is exactly z = 0 out to r = 12.5 (central r <= 9 is flat and clear),
brass gear teeth on the rim reach r ~= 13.3 (~26.6 m diameter). The platform is a floating
rock/clockwork chunk underneath (down to z ~= -6.5).

Run (from project root):
    blender -b --factory-startup -P tools/blender/model_arena.py
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: E402,F401,F403
from env_helpers import *  # noqa: E402,F401,F403
from env_helpers import Xform, mtx, set_mat  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

SEG = 48            # angular segments of the platform (7.5 deg each)
R_TOP = 12.5        # radius of the walkable disc
N_TEETH = 24


def setup_mats():
    get_mat("stone_mid", hex="#75706a", roughness=0.95)


def _const(m):
    return lambda j: m


# (outer radius, material(j)) from the center outwards; j = angular segment index
FLOOR_BANDS = [
    (1.0, _const("brass")),                                            # center medallion
    (1.25, _const("glow_cyan")),                                       # inner rune ring
    (1.5, _const("brass_dark")),
    (3.2, lambda j: "brass_dark" if j % 6 == 0 else "stone"),          # 8 engraved spokes
    (3.6, _const("brass")),
    (4.0, lambda j: "brass" if j % 2 == 0 else "stone_dark"),          # gear teeth (24)
    (5.8, lambda j: "stone_mid" if (j // 3) % 2 == 0 else "stone"),    # paving
    (7.6, lambda j: "stone" if (j // 3) % 2 == 0 else "stone_mid"),
    (8.0, _const("brass_dark")),
    (8.55, _const("stone")),
    (8.75, _const("glow_cyan")),                                       # boundary rune circle (~17.5 m)
    (9.0, _const("stone")),
    (10.6, lambda j: "stone_dark" if (j // 2) % 2 == 0 else "stone_mid"),   # rim paving, staggered
    (12.0, lambda j: "stone_mid" if ((j + 1) // 2) % 2 == 0 else "stone_dark"),
    (R_TOP, _const("brass")),                                          # brass edge band
]

# underside profile (z, r) below the rim wall; jittered for a rocky look
UNDERSIDE = [(-1.6, 12.0), (-2.7, 10.4), (-3.9, 8.0), (-5.0, 5.2), (-5.9, 2.6)]
Z_WALL = (-0.3, -1.2)
Z_BOTTOM = -6.5


def build_platform(parent):
    """Floor + rim wall + underside as ONE closed manifold (so normals come out right)."""
    p = Part("arena_platform")
    bm = p.bm
    rng = random.Random(7)

    def ring(r, z, jitter=0.0, zj=0.0):
        out = []
        for j in range(SEG):
            a = 2 * math.pi * j / SEG
            rr = r + (rng.uniform(-jitter, jitter) if jitter else 0.0)
            zz = z + (rng.uniform(-zj, zj) if zj else 0.0)
            out.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), zz)))
        return out

    center = bm.verts.new((0, 0, 0))
    rings = []
    for r, _ in FLOOR_BANDS:
        rings.append(ring(r, 0.0))
    # center fan
    mfn = FLOOR_BANDS[0][1]
    for j in range(SEG):
        k = (j + 1) % SEG
        f = bm.faces.new((center, rings[0][j], rings[0][k]))
        set_mat(p, [f], mfn(j))
    for i in range(1, len(FLOOR_BANDS)):
        mfn = FLOOR_BANDS[i][1]
        a, b = rings[i - 1], rings[i]
        for j in range(SEG):
            k = (j + 1) % SEG
            f = bm.faces.new((a[j], b[j], b[k], a[k]))
            set_mat(p, [f], mfn(j))

    # rim wall + underside
    side = [rings[-1], ring(R_TOP, Z_WALL[0]), ring(R_TOP, Z_WALL[1])]
    side_mats = ["brass_dark", "stone_dark"]
    for z, r in UNDERSIDE:
        side.append(ring(r, z, jitter=0.35, zj=0.25))
        side_mats.append("stone_dark")
    for i in range(1, len(side)):
        a, b = side[i - 1], side[i]
        for j in range(SEG):
            k = (j + 1) % SEG
            f = bm.faces.new((a[j], a[k], b[k], b[j]))
            m = side_mats[i - 1]
            if i >= 3 and rng.random() < 0.3:
                m = "stone"
            set_mat(p, [f], m)
    pole = bm.verts.new((0, 0, Z_BOTTOM))
    last = side[-1]
    for j in range(SEG):
        k = (j + 1) % SEG
        f = bm.faces.new((last[j], last[k], pole))
        set_mat(p, [f], "stone_dark")
    return p.build(parent)


def build_teeth(parent):
    p = Part("arena_rim_teeth")
    for i in range(N_TEETH):
        a = 360.0 * i / N_TEETH
        ar = math.radians(a)
        r = 12.9
        p.box("brass", size=(1.0, 1.25, 0.95), loc=(r * math.cos(ar), r * math.sin(ar), -0.12 - 0.475),
              rot=(0, 0, a))
        # rivet on each tooth face
        p.box("brass_dark", size=(0.08, 0.3, 0.3), loc=((r + 0.52) * math.cos(ar), (r + 0.52) * math.sin(ar), -0.6),
              rot=(0, 0, a))
    return p.build(parent)


def build_pillars(parent):
    p = Part("arena_pillars")
    for k in range(8):
        a = 360.0 * k / 8 + 22.5
        ar = math.radians(a)
        R = 11.3
        x, y = R * math.cos(ar), R * math.sin(ar)
        mat = "glow_cyan" if k % 2 == 0 else "glow_violet"
        # local frame: origin at pillar base, local -Y faces the arena center
        F = Matrix.Translation((x, y, 0)) @ Matrix.Rotation(ar - math.pi / 2, 4, "Z")
        with Xform(p, F):
            p.cyl("stone_dark", r=0.66, r2=0.58, h=0.3, seg=8, loc=(0, 0, 0.15), rot=(0, 0, 22.5))
            p.cyl("stone", r=0.42, r2=0.35, h=1.3, seg=8, loc=(0, 0, 0.95), rot=(0, 0, 22.5))
            p.cyl("brass", r=0.47, h=0.12, seg=8, loc=(0, 0, 0.4), rot=(0, 0, 22.5))
            p.cyl("brass", r=0.42, h=0.12, seg=8, loc=(0, 0, 1.56), rot=(0, 0, 22.5))
            # rune plate on the side facing the arena center (local -Y)
            p.box("brass_dark", size=(0.34, 0.06, 0.5), loc=(0, -0.39, 1.0), rot=(3, 0, 0))
            p.box(mat, size=(0.12, 0.06, 0.3), loc=(0, -0.42, 1.0), rot=(3, 0, 0))
            # crystal cradle
            p.cyl("brass", r=0.3, r2=0.5, h=0.25, seg=8, loc=(0, 0, 1.745), rot=(0, 0, 22.5))
            for i in range(4):
                b = math.radians(90 * i + 45)
                p.box("brass_dark", size=(0.08, 0.08, 0.4),
                      loc=(0.4 * math.cos(b), 0.4 * math.sin(b), 1.98),
                      rot=(math.degrees(-math.sin(b)) * 0.25, math.degrees(math.cos(b)) * 0.25, 0))
            shard(p, mat, r=0.22, h=0.5, tip=0.32, loc=(0, 0, 1.8), spin=k * 11)
            shard(p, mat, r=0.1, h=0.22, tip=0.14, loc=(0.16, 0.05, 1.82), rot=(0, 28, 0))
            shard(p, mat, r=0.09, h=0.18, tip=0.12, loc=(-0.15, -0.06, 1.82), rot=(0, -30, 0))
    return p.build(parent)


def _radial(r, a_deg, z):
    a = math.radians(a_deg)
    return (r * math.cos(a), r * math.sin(a), z)


def build_hanging(parent):
    """Broken pipes and cables hanging off the edge."""
    p = Part("arena_hanging")
    half = 180.0 / N_TEETH  # between two teeth
    # broken pipes: (angle, drop end z, radius)
    for i, (a, zend, rp) in enumerate(((60 + half, -3.6, 0.26), (165 + half, -2.6, 0.2), (285 + half, -4.2, 0.24))):
        pts = [_radial(11.7, a, -1.45), _radial(12.6, a, -1.45)]
        for t in range(1, 6):
            th = math.radians(90 * t / 5)
            pts.append(_radial(12.6 + 0.6 * math.sin(th), a, -2.05 + 0.6 * math.cos(th)))
        pts.append(_radial(13.2, a, (zend - 2.05) * 0.5))
        pts.append(_radial(13.2 + 0.1, a, zend))
        tube_path(p, "copper", pts, r=rp, seg=8, cap_end=False, jag=0.18, seed=100 + i)
        p.cyl("brass", r=rp + 0.08, h=0.14, seg=8, loc=_radial(12.35, a, -1.45), rot=(0, 90, a))
        p.cyl("brass", r=rp + 0.07, h=0.12, seg=8, loc=_radial(13.21, a, -2.8), rot=(0, 0, 0))
    # one short broken stub sticking straight out
    a = 225 + half
    tube_path(p, "copper", [_radial(11.9, a, -1.5), _radial(13.6, a, -1.55)], r=0.2, seg=8, cap_end=False,
              jag=0.2, seed=120)
    # sagging cables between two anchor points under the rim
    for i, (a0, a1, sag) in enumerate(((20 + half, 35 + half, 1.5), (110 + half, 132 + half, 2.2),
                                       (200 + half, 212 + half, 1.1), (320 + half, 342 + half, 1.9))):
        pts = []
        n = 10
        for t in range(n + 1):
            u = t / n
            aa = a0 + (a1 - a0) * u
            pts.append(_radial(12.35 + 0.35 * math.sin(math.pi * u), aa, -1.3 - 4 * sag * u * (1 - u)))
        tube_path(p, "gunmetal", pts, r=0.06, seg=5)
        for aa in (a0, a1):
            p.box("brass_dark", size=(0.25, 0.25, 0.25), loc=_radial(12.35, aa, -1.3), rot=(0, 0, aa))
    # dangling cable ends with brass plugs
    for i, (a, L) in enumerate(((85 + half, 2.6), (255 + half, 3.2))):
        pts = [_radial(12.3, a, -1.3), _radial(12.6, a, -1.6), _radial(12.75, a + 0.6, -1.3 - L * 0.6),
               _radial(12.7, a + 1.0, -1.3 - L)]
        tube_path(p, "gunmetal", pts, r=0.06, seg=5)
        p.cyl("brass", r=0.1, h=0.25, seg=6, loc=_radial(12.7, a + 1.0, -1.3 - L - 0.1))
        p.box("brass_dark", size=(0.25, 0.25, 0.25), loc=_radial(12.3, a, -1.3), rot=(0, 0, a))
    return p.build(parent)


def build_underside(parent):
    p = Part("arena_underside")
    # big clockwork gears half-sunk into the rock, facing outwards
    for i, (a, rr, z, gr) in enumerate(((35, 9.9, -3.0, 1.5), (150, 8.6, -3.9, 1.8), (265, 10.3, -2.8, 1.3))):
        ar = math.radians(a)
        F = Matrix.Translation(_radial(rr, a, z)) @ Matrix.Rotation(ar, 4, "Z") @ \
            Matrix.Rotation(math.radians(90), 4, "Y") @ Matrix.Rotation(math.radians(-25), 4, "Y")
        with Xform(p, F):
            p.gear("brass_dark", r=gr, thickness=0.35, teeth=10, tooth=0.4, hole=gr * 0.55)
            p.cyl("brass", r=gr * 0.3, h=0.5, seg=8)
    # aether crystals hanging from the bottom
    for i, (x, y, rot, h, m) in enumerate(((0, 0, (180, 0, 0), 1.6, "glow_cyan"),
                                           (0.8, 0.3, (160, 15, 0), 1.0, "glow_violet"),
                                           (-0.7, 0.5, (160, -20, 30), 0.9, "glow_cyan"),
                                           (0.1, -0.9, (200, 0, 0), 0.8, "glow_violet"))):
        shard(p, m, r=0.4 if i == 0 else 0.25, h=h, tip=0.6 if i == 0 else 0.35, loc=(x, y, Z_BOTTOM + 0.6),
              rot=rot, spin=i * 13)
    return p.build(parent)


def main():
    reset_scene()
    setup_mats()
    root = empty("root", size=1.0)
    parts = [build_platform(root), build_teeth(root), build_pillars(root), build_hanging(root),
             build_underside(root)]
    bpy.context.view_layer.update()
    for o in parts:
        print(f"[tris] {o.name:18s} {mesh_tris(o)}")
    print(f"[tris] arena total {tree_tris(root)} / 8000")
    export_glb("arena")
    render_preview("arena", size=900, azimuth=25, elevation=35)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--previews" in argv:
        render_preview("arena_side", size=900, azimuth=60, elevation=4)
        render_preview("arena_top", size=900, azimuth=0, elevation=89)


main()
