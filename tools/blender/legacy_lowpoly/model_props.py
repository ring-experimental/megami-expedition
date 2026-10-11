"""props.glb — all environment props as top-level nodes (see ASSET_SPEC.md, "props.glb").

Run (from project root):
    blender -b --factory-startup -P tools/blender/model_props.py
Options (after `--`):
    --previews           also render every prop alone -> previews/prop_<name>.png
    --only=a,b           restrict previews to these prop names
    --back               extra rear 3/4 preview per prop (previews/<name>_back.png)
    --no-export          skip the props.glb export (preview iteration only)
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: E402,F401,F403
from env_helpers import *  # noqa: E402,F401,F403
from env_helpers import Xform, mtx, box_m, set_mat  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402


def setup_mats():
    """Extra palette entries used by the props (same prefix rules as common.PALETTE)."""
    get_mat("moss", hex="#6b8f3a", roughness=0.95)
    get_mat("patina", hex="#4f9c8a", metallic=0.55, roughness=0.5)
    get_mat("paint_red", hex="#9e2b25", metallic=0.35, roughness=0.5)
    get_mat("leaf_teal_dark", hex="#2e6c62", roughness=0.9)
    get_mat("leaf_autumn_dark", hex="#9c4a1e", roughness=0.9)
    get_mat("leaf_gold", hex="#d9a23a", roughness=0.9)
    get_mat("rope", hex="#b39a6b", roughness=0.9)


# ---------------------------------------------------------------------------
# props
# ---------------------------------------------------------------------------

def build_lamp():
    root = empty("prop_lamp", size=0.5)
    p = Part("prop_lamp_post")
    # base
    p.cyl("stone_dark", r=0.34, r2=0.3, h=0.2, seg=8, loc=(0, 0, 0.1))
    p.cyl("iron", r=0.22, r2=0.15, h=0.4, seg=8, loc=(0, 0, 0.4))
    p.torus("brass", R=0.155, r=0.035, seg=8, seg2=4, loc=(0, 0, 0.6))
    # post
    p.cyl("iron", r=0.075, r2=0.055, h=2.1, seg=8, loc=(0, 0, 1.65))
    p.cyl("brass", r=0.1, h=0.1, seg=8, loc=(0, 0, 1.35))
    p.gear("brass", r=0.11, thickness=0.05, teeth=8, tooth=0.05, loc=(0, -0.08, 0.95), rot=(90, 0, 0))
    p.cyl("brass_dark", r=0.03, h=0.06, seg=6, loc=(0, -0.11, 0.95), rot=(90, 0, 0))
    # ladder rest crossbar
    p.box("brass", size=(0.7, 0.05, 0.05), loc=(0, 0, 2.45))
    for sx in (-1, 1):
        p.sphere("brass", r=0.045, seg=6, rings=4, loc=(sx * 0.36, 0, 2.45))
    # capital + lantern cage
    p.cyl("iron", r=0.06, r2=0.16, h=0.16, seg=8, loc=(0, 0, 2.78))
    p.cyl("brass", r=0.22, h=0.04, seg=8, loc=(0, 0, 2.88))
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.box("brass", size=(0.035, 0.035, 0.32), loc=(sx * 0.15, sy * 0.15, 3.06))
    p.cyl("brass", r=0.22, h=0.04, seg=8, loc=(0, 0, 3.24))
    p.cone("iron", r=0.27, h=0.18, seg=8, loc=(0, 0, 3.35))
    p.sphere("brass", r=0.045, seg=6, rings=4, loc=(0, 0, 3.47))
    p.build(root)
    b = Part("prop_lamp_bulb")
    b.ico("glow_cyan", r=0.12, subdiv=1, loc=(0, 0, 3.06))
    b.build(root)
    return root


def build_pipe():
    root = empty("prop_pipe", size=0.5)
    cz = 0.75
    p = Part("prop_pipe_body")
    hollow_tube(p, "copper", 0.4, 0.32, 5.6, seg=12, loc=(0, 0, cz), rot=(0, 90, 0), mat_in="gunmetal")
    for sx in (-1, 1):
        hollow_tube(p, "brass", 0.5, 0.32, 0.2, seg=12, loc=(sx * 2.9, 0, cz), rot=(0, 90, 0), mat_in="gunmetal")
        for i in range(8):
            a = 2 * math.pi * (i + 0.5) / 8
            p.box("brass_dark", size=(0.06, 0.07, 0.07),
                  loc=(sx * 2.77, 0.45 * math.cos(a), cz + 0.45 * math.sin(a)))
    hollow_tube(p, "brass", 0.47, 0.38, 0.14, seg=12, loc=(0, 0, cz), rot=(0, 90, 0))
    # supports
    for sx in (-1, 1):
        x = sx * 1.7
        p.box("iron", size=(0.5, 0.9, 0.08), loc=(x, 0, 0.04))
        p.box("iron", size=(0.24, 0.55, 0.34), loc=(x, 0, 0.25))
        p.box("gunmetal", size=(0.3, 0.75, 0.06), loc=(x, 0, 0.39))
        p.torus("brass", R=0.415, r=0.035, seg=12, seg2=4, loc=(x, 0, cz), rot=(0, 90, 0))
        for sy in (-1, 1):
            p.box("brass_dark", size=(0.08, 0.08, 0.05), loc=(x + 0.15, sy * 0.36, 0.1))
            p.box("brass_dark", size=(0.08, 0.08, 0.05), loc=(x - 0.15, sy * 0.36, 0.1))
    # valve on top
    p.cyl("copper", r=0.07, h=0.3, seg=8, loc=(0.9, 0, 1.25))
    wheel(p, "paint_red", R=0.18, r=0.022, spokes=3, loc=(0.9, 0, 1.4), hub_mat="brass")
    # pressure gauge facing front
    p.cyl("brass", r=0.04, h=0.22, seg=6, loc=(-0.9, 0, 1.22))
    p.cyl("brass", r=0.14, h=0.08, seg=10, loc=(-0.9, 0, 1.44), rot=(90, 0, 0))
    p.cyl("white", r=0.11, h=0.02, seg=10, loc=(-0.9, -0.045, 1.44), rot=(90, 0, 0))
    p.box("black", size=(0.015, 0.012, 0.09), loc=(-0.88, -0.058, 1.47), rot=(0, 30, 0))
    p.build(root)
    return root


def build_pipe_arch():
    root = empty("prop_pipe_arch", size=0.5)
    X, H, RB, r = 2.6, 2.65, 1.0, 0.35
    pts = [(-X, 0, 0.25), (-X, 0, 1.2), (-X, 0, 2.0), (-X, 0, H)]
    pts += arc_pts((-X + RB, 0, H), RB, 180, 90, 6)[1:]
    pts += [(0, 0, H + RB)]
    pts += arc_pts((X - RB, 0, H), RB, 90, 0, 6)
    pts += [(X, 0, 2.0), (X, 0, 1.2), (X, 0, 0.25)]
    p = Part("prop_pipe_arch_body")
    tube_path(p, "copper", pts, r=r, seg=10)
    for sx in (-1, 1):
        x = sx * X
        # footing
        p.box("stone_dark", size=(1.0, 1.0, 0.36), loc=(x, 0, 0.18))
        p.cyl("brass", r=0.47, h=0.12, seg=10, loc=(x, 0, 0.42))
        for bx in (-1, 1):
            for by in (-1, 1):
                p.box("brass_dark", size=(0.09, 0.09, 0.06), loc=(x + bx * 0.38, by * 0.38, 0.38))
        # joint flanges
        p.cyl("brass", r=0.45, h=0.14, seg=10, loc=(x, 0, H))
        p.cyl("brass", r=0.45, h=0.14, seg=10, loc=(sx * (X - RB), 0, H + RB), rot=(0, 90, 0))
        # aether sight-glass band
        p.cyl("glow_cyan", r=0.37, h=0.34, seg=10, loc=(x, 0, 1.45))
        p.cyl("brass", r=0.42, h=0.08, seg=10, loc=(x, 0, 1.24))
        p.cyl("brass", r=0.42, h=0.08, seg=10, loc=(x, 0, 1.66))
    # valve wheel on the front at the top
    p.cyl("copper", r=0.08, h=0.32, seg=8, loc=(0, -0.45, H + RB), rot=(90, 0, 0))
    wheel(p, "paint_red", R=0.26, r=0.03, spokes=3, loc=(0, -0.62, H + RB), rot=(90, 0, 0), hub_mat="brass")
    # steam whistle on top
    p.cyl("brass", r=0.08, h=0.4, seg=8, loc=(0.9, 0, H + RB + 0.45))
    p.cyl("brass_dark", r=0.12, h=0.08, seg=8, loc=(0.9, 0, H + RB + 0.28))
    p.cone("brass", r=0.1, h=0.14, seg=8, loc=(0.9, 0, H + RB + 0.72))
    p.build(root)
    return root


def build_vent():
    root = empty("prop_vent", size=0.5)
    p = Part("prop_vent_grate")
    hollow_tube(p, "iron", 0.62, 0.5, 0.16, seg=12, loc=(0, 0, 0.08), mat_in="gunmetal")
    p.torus("brass", R=0.56, r=0.035, seg=12, seg2=4, loc=(0, 0, 0.165))
    for i in range(6):
        a = 2 * math.pi * (i + 0.5) / 6
        p.box("brass_dark", size=(0.06, 0.06, 0.06), loc=(0.62 * math.cos(a), 0.62 * math.sin(a), 0.1),
              rot=(0, 0, math.degrees(a)))
    p.cyl("black", r=0.5, h=0.04, seg=12, loc=(0, 0, 0.02))
    for x in (-0.36, -0.18, 0.0, 0.18, 0.36):
        L = 2 * math.sqrt(0.5 ** 2 - x ** 2)
        p.box("gunmetal", size=(0.05, L, 0.05), loc=(x, 0, 0.125))
    p.box("gunmetal", size=(1.0, 0.05, 0.05), loc=(0, 0, 0.085))
    # valve stub
    tube_path(p, "copper", [(0.82, 0.3, -0.02), (0.82, 0.3, 0.24)], r=0.045, seg=6)
    tube_path(p, "copper", [(0.82, 0.3, 0.07), (0.58, 0.21, 0.07)], r=0.035, seg=6)
    wheel(p, "paint_red", R=0.12, r=0.018, spokes=3, loc=(0.82, 0.3, 0.27), hub_mat="brass")
    p.build(root)
    g = Part("prop_vent_glow")
    g.cyl("glow_cyan", r=0.26, h=0.02, seg=10, loc=(0, 0, 0.045))
    g.build(root)
    return root


def build_crystal():
    root = empty("prop_crystal", size=0.5)
    p = Part("prop_crystal_cluster")
    jitter_ico(p, "stone_dark", r=0.75, subdiv=2, loc=(0, 0, 0.12), scale=(1.25, 1.05, 0.55), seed=11,
               amount=0.2, floor=0.0)
    jitter_ico(p, "stone", r=0.35, subdiv=1, loc=(0.75, 0.25, 0.08), scale=(1, 0.9, 0.6), seed=12, floor=0.0)
    jitter_ico(p, "stone", r=0.25, subdiv=1, loc=(-0.7, -0.35, 0.05), scale=(1, 1, 0.7), seed=13, floor=0.0)
    shards = [
        # (mat, loc, rot, r, h, tip)
        ("glow_cyan", (0.0, 0.05, 0.2), (6, -6, 0), 0.24, 1.4, 0.45),
        ("glow_cyan", (0.33, 0.12, 0.2), (8, 28, 0), 0.16, 0.8, 0.3),
        ("glow_violet", (-0.36, 0.05, 0.2), (-6, -30, 0), 0.17, 0.95, 0.32),
        ("glow_violet", (0.12, -0.32, 0.15), (32, 12, 0), 0.13, 0.55, 0.22),
        ("glow_cyan", (-0.12, 0.38, 0.2), (-30, -10, 0), 0.13, 0.7, 0.25),
        ("glow_violet", (0.78, 0.22, 0.12), (10, 35, 0), 0.08, 0.25, 0.14),
        ("glow_cyan", (-0.68, -0.36, 0.08), (25, -30, 0), 0.07, 0.2, 0.12),
    ]
    for i, (m, loc, rot, r, h, tip) in enumerate(shards):
        shard(p, m, r=r, h=h, tip=tip, loc=loc, rot=rot, spin=i * 17)
    # brass harvesting clamp around the big crystal (same axis as the crystal)
    with Xform(p, mtx((0.0, 0.05, 0.2), (6, -6, 0))):
        p.torus("brass", R=0.27, r=0.045, seg=6, seg2=4, loc=(0, 0, 0.62))
        p.box("brass_dark", size=(0.1, 0.1, 0.14), loc=(0.3, 0, 0.62))
        tube_path(p, "copper", [(0.32, 0, 0.6), (0.6, 0.05, 0.35), (0.7, 0.1, -0.1)], r=0.04, seg=5)
    p.build(root)
    return root


def build_rock_a():
    root = empty("prop_rock_a", size=0.5)
    p = Part("prop_rock_a_mesh")
    jitter_ico(p, "stone", r=1.0, subdiv=2, loc=(0, 0, 0.5), scale=(1.2, 0.95, 0.85), seed=21, amount=0.22,
               floor=0.0, top_mat="moss", top_thresh=0.72)
    jitter_ico(p, "stone_dark", r=0.6, subdiv=2, loc=(1.0, -0.35, 0.3), rot=(0, 20, 30), scale=(1, 0.8, 0.75),
               seed=22, amount=0.25, floor=0.0)
    jitter_ico(p, "stone", r=0.25, subdiv=1, loc=(-1.0, -0.55, 0.1), seed=23, amount=0.15, floor=0.0)
    jitter_ico(p, "stone_dark", r=0.18, subdiv=1, loc=(0.4, -0.95, 0.06), seed=25, amount=0.15, floor=0.0)
    p.build(root)
    return root


def build_rock_b():
    root = empty("prop_rock_b", size=0.5)
    p = Part("prop_rock_b_mesh")
    jitter_ico(p, "stone_dark", r=1.0, subdiv=2, loc=(0, 0, 1.15), rot=(0, 8, 15), scale=(0.65, 0.55, 1.3),
               seed=31, amount=0.24, floor=0.0, top_mat="stone", top_thresh=0.8)
    jitter_ico(p, "stone_dark", r=0.8, subdiv=2, loc=(0.6, 0.15, 0.6), rot=(0, -25, -20), scale=(0.6, 0.55, 0.9),
               seed=32, amount=0.24, floor=0.0, top_mat="stone", top_thresh=0.8)
    jitter_ico(p, "stone", r=0.5, subdiv=1, loc=(-0.55, -0.3, 0.3), rot=(0, 15, 40), scale=(1, 0.8, 0.7),
               seed=33, amount=0.2, floor=0.0)
    jitter_ico(p, "stone", r=0.22, subdiv=1, loc=(0.35, -0.65, 0.08), seed=34, amount=0.15, floor=0.0)
    p.build(root)
    return root


def build_tree():
    root = empty("prop_tree", size=0.5)
    t = Part("prop_tree_trunk")
    tube_path(t, "wood", [(0, 0, -0.05), (0.06, 0, 1.0), (-0.04, 0.04, 2.0), (0.05, 0, 3.0)],
              radii=[0.38, 0.29, 0.23, 0.16], seg=6)
    for i in range(5):
        a = 2 * math.pi * i / 5 + 0.3
        tube_path(t, "wood", [(0.7 * math.cos(a), 0.7 * math.sin(a), -0.03),
                              (0.34 * math.cos(a), 0.34 * math.sin(a), 0.2),
                              (0.1 * math.cos(a), 0.1 * math.sin(a), 0.65)],
                  radii=[0.07, 0.15, 0.17], seg=5)
    tube_path(t, "wood", [(0.02, 0, 1.9), (0.6, -0.1, 2.5), (1.0, -0.15, 2.85)], radii=[0.13, 0.09, 0.07], seg=5)
    tube_path(t, "wood", [(0.0, 0.02, 2.2), (-0.55, 0.15, 2.75), (-0.85, 0.2, 3.1)], radii=[0.12, 0.08, 0.06],
              seg=5)
    # brass survey tag nailed to the trunk (tiny steampunk touch)
    t.box("brass", size=(0.16, 0.04, 0.1), loc=(0.02, -0.255, 1.2))
    t.build(root)
    c = Part("prop_tree_canopy")
    blobs = [
        ((0, 0, 3.6), 1.5, (1.0, 1.0, 0.85), 41),
        ((1.1, -0.2, 3.05), 1.0, (1, 1, 0.85), 42),
        ((-1.0, 0.25, 3.2), 1.05, (1, 1, 0.85), 43),
        ((0.25, 0.6, 4.25), 0.95, (1, 1, 0.9), 44),
        ((-0.35, -0.55, 4.15), 0.85, (1, 1, 0.9), 45),
        ((0.1, 0.95, 3.05), 0.8, (1, 1, 0.85), 46),
    ]
    for loc, r, sc, seed in blobs:
        jitter_ico(c, "leaf_teal", r=r, subdiv=2, loc=loc, scale=sc, seed=seed, amount=0.2,
                   bottom_mat="leaf_teal_dark", bottom_thresh=-0.25)
    # glowing aether seeds hanging under the canopy
    for loc in ((0.95, -0.9, 2.3), (-1.15, -0.4, 2.5), (0.35, -1.0, 2.75), (-0.5, -0.9, 3.05)):
        jitter_ico(c, "glow_cyan", r=0.11, subdiv=1, loc=loc, scale=(1, 1, 1.3), seed=47, amount=0.1)
    c.build(root)
    return root


def build_tree_b():
    root = empty("prop_tree_b", size=0.5)
    t = Part("prop_tree_b_trunk")
    tube_path(t, "wood_dark", [(0, 0, -0.05), (0.05, 0.02, 0.8), (0.0, 0.0, 1.5)], radii=[0.32, 0.23, 0.2], seg=6)
    tube_path(t, "wood_dark", [(0.0, 0.0, 1.4), (0.45, -0.05, 2.2), (0.95, -0.1, 2.9)],
              radii=[0.17, 0.13, 0.09], seg=6)
    tube_path(t, "wood_dark", [(0.0, 0.0, 1.4), (-0.4, 0.1, 2.3), (-0.75, 0.15, 3.25)],
              radii=[0.17, 0.12, 0.08], seg=6)
    tube_path(t, "wood_dark", [(0.0, 0.0, 1.45), (0.05, 0.35, 2.2), (0.1, 0.55, 2.6)],
              radii=[0.1, 0.07, 0.05], seg=5)
    for i in range(4):
        a = 2 * math.pi * i / 4 + 0.7
        tube_path(t, "wood_dark", [(0.55 * math.cos(a), 0.55 * math.sin(a), -0.03),
                                   (0.24 * math.cos(a), 0.24 * math.sin(a), 0.15),
                                   (0.08 * math.cos(a), 0.08 * math.sin(a), 0.5)],
                  radii=[0.05, 0.12, 0.14], seg=5)
    t.build(root)
    c = Part("prop_tree_b_canopy")
    blobs = [  # (top mat, loc, r, scale, seed) -- two big lobes on the forks, a crown, small fillers
        ("leaf_autumn", (1.0, -0.1, 3.1), 1.2, (1.15, 1.0, 0.62), 51),
        ("leaf_autumn", (1.35, 0.35, 2.75), 0.7, (1.1, 1.0, 0.65), 52),
        ("leaf_gold", (-0.8, 0.15, 3.5), 1.1, (1.1, 1.0, 0.62), 53),
        ("leaf_gold", (-1.15, -0.25, 3.15), 0.7, (1.1, 1.0, 0.65), 54),
        ("leaf_autumn", (0.1, 0.6, 2.75), 0.65, (1.1, 1.0, 0.7), 55),
        ("leaf_autumn", (0.1, 0.05, 3.95), 0.75, (1.0, 1.0, 0.7), 56),
    ]
    for m, loc, r, sc, seed in blobs:
        jitter_ico(c, m, r=r, subdiv=2, loc=loc, scale=sc, seed=seed, amount=0.22,
                   bottom_mat="leaf_autumn_dark", bottom_thresh=-0.3)
    # fallen leaves
    for i, (x, y) in enumerate(((0.7, -0.6), (-0.6, -0.7), (0.9, 0.5), (-0.85, 0.4), (0.15, -1.0),
                                (1.3, -0.2), (-1.2, -0.3))):
        c.box("leaf_autumn" if i % 2 else "leaf_gold", size=(0.22, 0.14, 0.02), loc=(x, y, 0.01),
              rot=(0, 0, i * 47))
    c.build(root)
    return root


def build_bush():
    root = empty("prop_bush", size=0.5)
    p = Part("prop_bush_mesh")
    kw = dict(subdiv=2, amount=0.2, floor=0.0, bottom_mat="leaf_teal_dark", bottom_thresh=-0.2)
    jitter_ico(p, "leaf_teal", r=0.45, loc=(0, 0, 0.36), scale=(1.05, 1, 0.9), seed=61, **kw)
    jitter_ico(p, "leaf_teal", r=0.33, loc=(0.42, 0.12, 0.24), seed=62, **kw)
    jitter_ico(p, "leaf_teal", r=0.3, loc=(-0.4, 0.08, 0.22), seed=63, **kw)
    jitter_ico(p, "leaf_teal", r=0.26, loc=(0.1, -0.3, 0.2), seed=64, **kw)
    for loc in ((0.2, -0.42, 0.42), (-0.32, -0.3, 0.33), (0.52, -0.16, 0.36), (-0.05, -0.25, 0.68),
                (-0.5, 0.2, 0.4), (0.3, 0.2, 0.68)):
        jitter_ico(p, "glow_violet", r=0.055, subdiv=1, loc=loc, seed=65, amount=0.1)
    p.build(root)
    return root


def build_gear_monument():
    root = empty("prop_gear_monument", size=0.5)
    cz = 2.0
    g = Part("prop_gear_monument_gear")
    g.gear("brass", r=2.5, thickness=0.45, teeth=18, tooth=0.5, hole=1.95, loc=(0, 0, cz), rot=(90, 0, 0))
    for i in range(6):
        a = 360.0 * i / 6 + 30
        ar = math.radians(a)
        g.box("brass_dark", size=(0.3, 0.32, 1.6),
              loc=(1.25 * math.cos(ar), 0, cz + 1.25 * math.sin(ar)), rot=(0, 90 - a, 0))
    g.cyl("brass_dark", r=0.55, h=0.6, seg=12, loc=(0, 0, cz), rot=(90, 0, 0))
    g.cyl("brass", r=0.32, h=0.7, seg=12, loc=(0, 0, cz), rot=(90, 0, 0))
    g.torus("glow_cyan", R=0.44, r=0.035, seg=12, seg2=4, loc=(0, -0.31, cz), rot=(90, 0, 0))
    g.torus("glow_cyan", R=0.44, r=0.035, seg=12, seg2=4, loc=(0, 0.31, cz), rot=(90, 0, 0))
    # moss creeping onto the rim where it meets the mound
    for i, (x, z, r) in enumerate(((-2.1, 1.15, 0.38), (2.05, 1.1, 0.4), (-2.45, 1.75, 0.26),
                                   (2.4, 1.55, 0.24))):
        jitter_ico(g, "moss", r=r, subdiv=1, loc=(x, 0, z), scale=(1.2, 1.0, 0.75), seed=70 + i, amount=0.2)
    g.build(root)
    s = Part("prop_gear_monument_base")
    jitter_ico(s, "stone", r=1.0, subdiv=2, loc=(0, 0, 0.0), scale=(3.3, 1.65, 1.35), seed=75, amount=0.1,
               floor=0.0, top_mat="moss", top_thresh=0.55)
    for i, (x, y, r) in enumerate(((-2.9, -1.0, 0.6), (3.0, 0.7, 0.65), (1.8, -1.3, 0.5), (-1.6, 1.35, 0.55),
                                   (3.35, -0.7, 0.38), (-3.3, 0.5, 0.4))):
        jitter_ico(s, "stone_dark", r=r, subdiv=1, loc=(x, y, r * 0.45), scale=(1.1, 1, 0.8), seed=80 + i,
                   amount=0.2, floor=0.0)
    # brass plaque on the front of the mound
    s.box("brass_dark", size=(0.9, 0.1, 0.45), loc=(0, -1.55, 0.45), rot=(-25, 0, 0))
    s.box("brass", size=(0.75, 0.1, 0.32), loc=(0, -1.58, 0.46), rot=(-25, 0, 0))
    s.build(root)
    return root


def _clock_face(p, F):
    """Clock face in a local frame (outward = local -Y, up = +Z), placed by matrix F."""
    with Xform(p, F):
        p.gear("brass_dark", r=1.6, thickness=0.12, teeth=18, tooth=0.3, loc=(0, -0.05, 0), rot=(90, 0, 0),
               seg=36)
        p.torus("brass", R=1.6, r=0.12, seg=24, seg2=4, loc=(0, -0.2, 0), rot=(90, 0, 0))
        p.torus("glow_amber", R=1.42, r=0.07, seg=24, seg2=4, loc=(0, -0.2, 0), rot=(90, 0, 0))
        p.cyl("white", r=1.38, h=0.1, seg=24, loc=(0, -0.17, 0), rot=(90, 0, 0))
        for i in range(12):
            a = math.radians(i * 30)
            big = i % 3 == 0
            p.box("black", size=(0.09 if big else 0.06, 0.04, 0.3 if big else 0.18),
                  loc=(1.13 * math.sin(a), -0.23, 1.13 * math.cos(a)), rot=(0, i * 30, 0))
        # hands at ~10:10 (rotation about the face normal = local Y)
        s60, c60 = math.sin(math.radians(60)), math.cos(math.radians(60))
        p.box("black", size=(0.13, 0.04, 0.75), loc=(-0.37 * s60, -0.27, 0.37 * c60), rot=(0, -60, 0))
        p.box("black", size=(0.08, 0.04, 1.1), loc=(0.53 * s60, -0.31, 0.53 * c60), rot=(0, 60, 0))
        p.cyl("brass", r=0.12, h=0.16, seg=8, loc=(0, -0.3, 0), rot=(90, 0, 0))


def build_clocktower():
    root = empty("prop_clocktower", size=0.5)
    W = 4.4                     # shaft width
    Z_SHAFT0, Z_SHAFT1 = 0.8, 9.5
    HW, Z_H0, Z_H1 = 4.8, 9.9, 14.1   # clock housing
    Z_CLOCK = 12.1
    s = Part("prop_clocktower_stone")
    # plinth + front step
    s.box("stone_dark", size=(5.4, 5.4, 0.8), loc=(0, 0, 0.4))
    s.box("stone_dark", size=(2.2, 0.35, 0.4), loc=(0, -2.85, 0.2))
    # shaft with corner pilasters and string courses
    hs = Z_SHAFT1 - Z_SHAFT0
    s.box("stone", size=(W, W, hs), loc=(0, 0, Z_SHAFT0 + hs / 2))
    for sx in (-1, 1):
        for sy in (-1, 1):
            s.box("stone_dark", size=(0.8, 0.8, hs), loc=(sx * (W / 2 - 0.25), sy * (W / 2 - 0.25),
                                                        Z_SHAFT0 + hs / 2))
    for z, w, h in ((3.6, W + 0.35, 0.25), (6.9, W + 0.35, 0.25), (9.7, W + 0.8, 0.4)):
        s.box("stone_dark", size=(w, w, h), loc=(0, 0, z))
    # door surround (front, -Y)
    s.box("stone_dark", size=(1.7, 0.2, 2.2), loc=(0, -W / 2 - 0.05, 0.8 + 1.1))
    s.cyl("stone_dark", r=0.85, h=0.2, seg=10, loc=(0, -W / 2 - 0.05, 3.0), rot=(90, 0, 0))
    s.build(root)

    m = Part("prop_clocktower_metal")
    # door
    m.box("wood_dark", size=(1.2, 0.2, 2.0), loc=(0, -W / 2 - 0.12, 0.8 + 1.0))
    m.cyl("wood_dark", r=0.6, h=0.2, seg=10, loc=(0, -W / 2 - 0.12, 2.8), rot=(90, 0, 0))
    for x in (-0.35, 0.35):
        m.box("brass", size=(0.08, 0.06, 2.4), loc=(x, -W / 2 - 0.23, 0.8 + 1.2))
    m.box("brass", size=(1.2, 0.06, 0.1), loc=(0, -W / 2 - 0.23, 2.1))
    m.sphere("brass", r=0.07, seg=6, rings=4, loc=(0.18, -W / 2 - 0.27, 1.9))
    # door lanterns
    for sx in (-1, 1):
        m.box("iron", size=(0.08, 0.35, 0.08), loc=(sx * 1.15, -W / 2 - 0.2, 2.9))
        m.cyl("brass", r=0.13, h=0.05, seg=6, loc=(sx * 1.15, -W / 2 - 0.42, 2.72))
        m.cyl("glow_cyan", r=0.1, h=0.26, seg=6, loc=(sx * 1.15, -W / 2 - 0.42, 2.88))
        m.cone("iron", r=0.16, h=0.15, seg=6, loc=(sx * 1.15, -W / 2 - 0.42, 3.08))
    # arched glowing windows
    for k in range(4):
        F = Matrix.Rotation(math.radians(90 * k), 4, "Z")
        with Xform(m, F):
            for z in (5.0, 8.0):
                if k == 0 and z < 6:
                    continue
                m.box("brass_dark", size=(0.9, 0.12, 1.2), loc=(0, -W / 2 - 0.02, z))
                m.cyl("brass_dark", r=0.45, h=0.12, seg=8, loc=(0, -W / 2 - 0.02, z + 0.6), rot=(90, 0, 0))
                m.box("glow_amber", size=(0.62, 0.12, 1.0), loc=(0, -W / 2 - 0.05, z))
                m.cyl("glow_amber", r=0.31, h=0.12, seg=8, loc=(0, -W / 2 - 0.05, z + 0.5), rot=(90, 0, 0))
                m.box("iron", size=(0.06, 0.14, 1.3), loc=(0, -W / 2 - 0.08, z + 0.1))
    # front: gear rosette window above the door
    m.gear("brass", r=0.5, thickness=0.12, teeth=10, tooth=0.16, loc=(0, -W / 2 - 0.08, 5.1), rot=(90, 0, 0))
    m.cyl("glow_cyan", r=0.3, h=0.14, seg=8, loc=(0, -W / 2 - 0.1, 5.1), rot=(90, 0, 0))
    m.cyl("brass_dark", r=0.1, h=0.18, seg=6, loc=(0, -W / 2 - 0.12, 5.1), rot=(90, 0, 0))
    # side steam pipes (+X wall) with a valve manifold
    for y in (-0.7, 0.7):
        tube_path(m, "copper", [(W / 2 + 0.02, y, Z_SHAFT0 + 0.1), (W / 2 + 0.25, y, Z_SHAFT0 + 0.25),
                                (W / 2 + 0.25, y, Z_SHAFT1 - 0.2), (W / 2 + 0.02, y, Z_SHAFT1)], r=0.13, seg=8)
        for z in (2.5, 5.0, 7.5):
            m.box("brass", size=(0.42, 0.34, 0.1), loc=(W / 2 + 0.17, y, z))
    m.cyl("brass", r=0.16, h=1.4, seg=8, loc=(W / 2 + 0.25, 0, 1.6), rot=(90, 0, 0))
    m.cyl("brass", r=0.06, h=0.3, seg=6, loc=(W / 2 + 0.45, 0, 1.6), rot=(0, 90, 0))
    wheel(m, "paint_red", R=0.22, r=0.03, spokes=3, loc=(W / 2 + 0.6, 0, 1.6), rot=(0, 90, 0), hub_mat="brass")

    # clock housing
    hh = Z_H1 - Z_H0
    m.box("copper", size=(HW, HW, hh), loc=(0, 0, Z_H0 + hh / 2))
    for sx in (-1, 1):
        for sy in (-1, 1):
            m.box("brass_dark", size=(0.5, 0.5, hh), loc=(sx * (HW / 2 - 0.15), sy * (HW / 2 - 0.15), Z_H0 + hh / 2))
    m.box("brass_dark", size=(HW + 0.3, HW + 0.3, 0.25), loc=(0, 0, Z_H1 + 0.1))
    # balcony rail on the cornice
    for k in range(4):
        F = Matrix.Rotation(math.radians(90 * k), 4, "Z")
        with Xform(m, F):
            for i in range(7):
                m.box("brass", size=(0.07, 0.07, 0.4), loc=(-2.4 + i * 0.8, -2.5, Z_H0 + 0.2))
            m.box("brass", size=(5.0, 0.09, 0.09), loc=(0, -2.5, Z_H0 + 0.4))
    for k in range(4):
        F = Matrix.Translation((0, 0, Z_CLOCK)) @ Matrix.Rotation(math.radians(90 * k), 4, "Z") @             Matrix.Translation((0, -HW / 2, 0))
        _clock_face(m, F)
    # roof
    z_roof = Z_H1 + 0.225
    m.cone("patina", r=(HW + 0.5) / math.sqrt(2), h=2.4, seg=4, loc=(0, 0, z_roof + 1.2), rot=(0, 0, 45))
    # cupola with aether light + spire
    zc = z_roof + 2.15
    m.cyl("brass", r=0.6, h=0.12, seg=8, loc=(0, 0, zc))
    for i in range(6):
        a = 2 * math.pi * i / 6
        m.box("brass_dark", size=(0.08, 0.08, 0.6), loc=(0.45 * math.cos(a), 0.45 * math.sin(a), zc + 0.36))
    m.ico("glow_cyan", r=0.28, subdiv=1, loc=(0, 0, zc + 0.36))
    m.cone("patina", r=0.62, h=0.45, seg=8, loc=(0, 0, zc + 0.88))
    m.cyl("brass", r=0.06, h=0.4, seg=6, loc=(0, 0, zc + 1.2))
    m.gear("brass", r=0.18, thickness=0.05, teeth=8, tooth=0.08, loc=(0, 0, zc + 1.3), rot=(90, 0, 0))
    m.cone("brass", r=0.07, h=0.3, seg=6, loc=(0, 0, zc + 1.6))
    m.build(root)
    return root


def build_airship():
    root = empty("prop_airship", size=0.5)
    BZ = 8.2  # envelope axis height
    e = Part("prop_airship_envelope")
    # envelope revolved around local Z, rotated so local +Z (nose) -> -Y
    prof = [(-5.6, 0), (-5.1, 0.7), (-4.2, 1.45), (-2.7, 2.05), (-0.8, 2.35), (1.2, 2.35), (3.0, 2.05),
            (4.3, 1.5), (5.0, 0.85), (5.3, 0)]
    L = 1.08  # length stretch -> ~12 m overall
    prof = [(z * L, r) for z, r in prof]
    lathe(e, "cloth_cream", prof, seg=12, loc=(0, 0, BZ), rot=(90, 0, 0), mat_alt="cloth_red", alt_every=1,
          phase=math.pi / 12)
    for z, rr in ((-3.6, 1.72), (0.2, 2.4), (3.5, 1.86)):
        e.torus("brass", R=rr, r=0.07, seg=12, seg2=4, loc=(0, -z * L, BZ), rot=(90, 0, 0))
    e.sphere("brass", r=0.25, seg=8, rings=4, loc=(0, -5.32 * L, BZ))
    # tail fins (+Y end): top, bottom, sides
    # fin outline in (radial, along +Y from y=3.3); inner edge follows the envelope
    fin = [(1.6, 0.0), (2.9, 0.4), (3.2, 1.7), (2.7, 2.2), (0.5, 1.8), (1.2, 1.0)]
    for k in range(4):
        F = Matrix.Translation((0, 3.3 * L, BZ)) @ Matrix.Rotation(math.radians(90 * k + 45), 4, "Y")
        with Xform(e, F):
            extrude_profile(e, "cloth_red", fin, 0.1, axis="Z", side_mat="brass")
    # keel frame under the envelope
    e.box("brass_dark", size=(0.3, 4.6, 0.5), loc=(0, 0.1, BZ - 2.25))
    e.build(root)

    gz = 4.7  # gondola deck height
    g = Part("prop_airship_gondola")
    hull = [(-2.7, 0.15), (-2.25, -0.35), (-1.4, -0.65), (1.5, -0.65), (2.25, -0.35), (2.5, 0.15)]
    extrude_profile(g, "wood", [(y, gz + z) for y, z in hull], 1.6, axis="X")
    g.box("brass", size=(1.7, 5.1, 0.1), loc=(0, -0.1, gz + 0.18))
    g.box("brass_dark", size=(1.64, 4.2, 0.12), loc=(0, -0.05, gz - 0.35))
    # rails
    for sx in (-1, 1):
        g.box("brass", size=(0.06, 4.6, 0.06), loc=(sx * 0.8, -0.15, gz + 0.65))
        for i in range(7):
            g.box("brass", size=(0.05, 0.05, 0.45), loc=(sx * 0.8, -2.1 + i * 0.66, gz + 0.43))
    # cabin
    g.box("wood_dark", size=(1.2, 1.9, 1.1), loc=(0, 0.35, gz + 0.78))
    g.box("copper", size=(1.4, 2.1, 0.12), loc=(0, 0.35, gz + 1.39))
    for sx in (-1, 1):
        for y in (-0.15, 0.85):
            g.box("glow_amber", size=(0.06, 0.38, 0.3), loc=(sx * 0.6, y, gz + 0.85))
    g.cyl("glow_amber", r=0.17, h=0.06, seg=8, loc=(0, -0.62, gz + 0.85), rot=(90, 0, 0))
    g.torus("brass", R=0.19, r=0.035, seg=8, seg2=4, loc=(0, -0.64, gz + 0.85), rot=(90, 0, 0))
    # chimney
    g.cyl("iron", r=0.12, h=0.9, seg=8, loc=(0.3, 1.0, gz + 1.85))
    g.cyl("brass", r=0.17, h=0.1, seg=8, loc=(0.3, 1.0, gz + 2.3))
    # struts to the keel
    for sx in (-1, 1):
        for y in (-1.8, 1.4):
            tube_path(g, "brass_dark", [(sx * 0.75, y, gz + 0.15), (sx * 0.12, y + 0.2 * (1 if y < 0 else -1),
                                                                    BZ - 2.3)], r=0.04, seg=5)
    # ropes from envelope to gondola rails
    for sx in (-1, 1):
        for y in (-2.0, 0.0, 2.0):
            tube_path(g, "rope", [(sx * 0.8, y * 0.95, gz + 0.65), (sx * 1.55, y, BZ - 1.4)], r=0.02, seg=4)
    # stern engine + shaft
    g.box("iron", size=(0.8, 0.7, 0.7), loc=(0, 2.35, gz + 0.1))
    g.cyl("brass", r=0.3, h=0.5, seg=10, loc=(0, 2.8, gz + 0.1), rot=(90, 0, 0))
    g.cyl("glow_cyan", r=0.16, h=0.1, seg=8, loc=(0.41, 2.35, gz + 0.1), rot=(0, 90, 0))
    g.cyl("glow_cyan", r=0.16, h=0.1, seg=8, loc=(-0.41, 2.35, gz + 0.1), rot=(0, 90, 0))
    g.cyl("steel", r=0.06, h=0.5, seg=6, loc=(0, 3.2, gz + 0.1), rot=(90, 0, 0))
    # bow figurehead: brass gear + lantern
    g.gear("brass", r=0.3, thickness=0.08, teeth=8, tooth=0.1, loc=(0, -2.62, gz + 0.1), rot=(90, 0, 90))
    g.cyl("glow_cyan", r=0.08, h=0.1, seg=6, loc=(0, -2.62, gz + 0.1), rot=(0, 90, 0))
    g.build(root)

    pr = Part("propeller")
    pr.cyl("brass", r=0.14, h=0.24, seg=8, rot=(90, 0, 0))
    pr.cone("brass", r=0.14, h=0.2, seg=8, loc=(0, 0.22, 0), rot=(-90, 0, 0))
    for i in range(4):
        a = math.radians(90 * i + 45)
        M = Matrix.Rotation(a, 4, "Y") @ Matrix.Translation((0, 0, 0.62)) @ \
            Matrix.Rotation(math.radians(22), 4, "Z") @ Matrix.Diagonal((0.26, 0.05, 1.0, 1.0))
        box_m(pr, "wood", M)
        M2 = Matrix.Rotation(a, 4, "Y") @ Matrix.Translation((0, 0, 1.15)) @ \
            Matrix.Rotation(math.radians(22), 4, "Z") @ Matrix.Diagonal((0.28, 0.07, 0.12, 1.0))
        box_m(pr, "brass", M2)
    pr.build(root, loc=(0, 3.5, gz + 0.1))
    return root


def build_rest():
    root = empty("prop_rest", size=0.5)
    p = Part("prop_rest_fountain")
    p.cyl("stone_dark", r=1.15, h=0.2, seg=8, loc=(0, 0, 0.1), rot=(0, 0, 22.5))
    p.cyl("stone", r=0.92, h=0.2, seg=8, loc=(0, 0, 0.3), rot=(0, 0, 22.5))
    # rune ring on the lower step
    p.torus("glow_cyan", R=1.03, r=0.03, seg=16, seg2=4, loc=(0, 0, 0.205), scale=(1, 1, 0.5))
    for i in range(8):
        a = 2 * math.pi * (i + 0.5) / 8
        p.box("glow_cyan", size=(0.12, 0.04, 0.12), loc=(1.07 * math.cos(a), 1.07 * math.sin(a), 0.1),
              rot=(0, 0, math.degrees(a) + 90))
    # basin on a stem
    lathe(p, "brass", [(0.4, 0.3), (0.55, 0.22), (0.85, 0.2), (0.95, 0.35), (1.08, 0.7), (1.16, 0.82),
                       (1.12, 0.74)], seg=10)
    p.torus("brass_dark", R=0.8, r=0.05, seg=10, seg2=4, loc=(0, 0, 1.15))
    p.cyl("glow_cyan", r=0.72, h=0.02, seg=10, loc=(0, 0, 1.13))
    # central pillar with three claws holding the crystal
    p.cyl("brass_dark", r=0.12, r2=0.09, h=0.55, seg=8, loc=(0, 0, 1.4))
    p.gear("brass", r=0.2, thickness=0.06, teeth=8, tooth=0.07, loc=(0, 0, 1.3))
    p.cyl("brass", r=0.16, h=0.06, seg=8, loc=(0, 0, 1.66))
    for i in range(3):
        a = 2 * math.pi * i / 3 + math.pi / 2
        c, s_ = math.cos(a), math.sin(a)
        tube_path(p, "copper", [(0.1 * c, 0.1 * s_, 1.62), (0.35 * c, 0.35 * s_, 1.78),
                                (0.42 * c, 0.42 * s_, 2.05), (0.32 * c, 0.32 * s_, 2.32)],
                  radii=[0.05, 0.045, 0.04, 0.03], seg=5)
        p.cone("brass", r=0.05, h=0.14, seg=5, loc=(0.31 * c, 0.31 * s_, 2.38))
    # two little brass lamps on the basin rim
    for sx in (-1, 1):
        p.cyl("brass", r=0.04, h=0.2, seg=6, loc=(sx * 0.82, 0, 1.25))
        p.ico("glow_cyan", r=0.06, subdiv=0, loc=(sx * 0.82, 0, 1.38))
    p.build(root)
    c = Part("crystal")
    bipyramid(c, "glow_cyan", r=0.2, up=0.4, down=0.3, seg=6)
    c.build(root, loc=(0, 0, 2.1))
    return root


def build_chest():
    root = empty("prop_chest", size=0.5)
    W, D, H = 0.9, 0.58, 0.42
    p = Part("prop_chest_body")
    p.box("wood", size=(W, D, H - 0.04), loc=(0, 0, 0.04 + (H - 0.04) / 2))
    p.box("wood_dark", size=(W - 0.04, D - 0.04, 0.05), loc=(0, 0, 0.025))
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.box("brass", size=(0.08, 0.08, H - 0.02), loc=(sx * (W / 2 - 0.03), sy * (D / 2 - 0.03), H / 2))
            p.box("brass_dark", size=(0.1, 0.1, 0.06), loc=(sx * (W / 2 - 0.04), sy * (D / 2 - 0.04), 0.03))
    p.box("brass", size=(W + 0.02, D + 0.02, 0.05), loc=(0, 0, H - 0.03))
    for sx in (-1, 1):
        p.box("wood_dark", size=(0.03, D + 0.01, H - 0.12), loc=(sx * 0.22, 0, H / 2 + 0.02))
    # lock plate
    p.box("brass", size=(0.18, 0.04, 0.16), loc=(0, -D / 2 - 0.01, H - 0.1))
    p.box("glow_amber", size=(0.035, 0.03, 0.06), loc=(0, -D / 2 - 0.025, H - 0.11))
    # side handles
    for sx in (-1, 1):
        p.torus("iron", R=0.07, r=0.015, seg=8, seg2=4, loc=(sx * (W / 2 + 0.02), 0, H - 0.15), rot=(0, 90, 0))
    p.build(root)
    lid = Part("lid")
    R = D / 2
    # geometry relative to the hinge pivot (back top edge): lid spans y in [-D, 0]
    half_cyl_x(lid, "wood", R, W, seg=6, loc=(0, -R, 0), scale_z=0.42 / 0.58 * 1.0)
    for x in (-W / 2 + 0.04, -0.22, 0.22, W / 2 - 0.04):
        half_cyl_x(lid, "brass", R + 0.012, 0.06, seg=6, loc=(x, -R, -0.002), scale_z=(0.42 / 0.58) * 1.03)
    lid.box("brass", size=(W + 0.02, D + 0.02, 0.04), loc=(0, -R, 0.02))
    lid.box("brass", size=(0.12, 0.04, 0.12), loc=(0, -D - 0.015, 0.0))
    for sx in (-1, 1):
        lid.cyl("iron", r=0.025, h=0.1, seg=6, loc=(sx * 0.3, 0.005, 0.0), rot=(0, 90, 0))
    lid.build(root, loc=(0, D / 2, H))
    return root


def build_fence():
    root = empty("prop_fence", size=0.5)
    p = Part("prop_fence_mesh")
    for sx in (-1, 1):
        x = sx * 1.0
        p.box("stone_dark", size=(0.22, 0.22, 0.14), loc=(x, 0, 0.07))
        p.box("iron", size=(0.1, 0.1, 1.04), loc=(x, 0, 0.14 + 0.52))
        p.box("brass", size=(0.14, 0.14, 0.04), loc=(x, 0, 1.18))
        p.sphere("brass", r=0.065, seg=6, rings=4, loc=(x, 0, 1.25))
        p.cone("brass", r=0.025, h=0.08, seg=4, loc=(x, 0, 1.33))
    for z in (0.22, 0.95):
        p.box("iron", size=(2.0, 0.05, 0.05), loc=(0, 0, z))
    for i in range(9):
        x = -0.8 + i * 0.2
        p.box("iron", size=(0.035, 0.035, 0.92), loc=(x, 0, 0.14 + 0.46), rot=(0, 0, 45))
        p.cone("brass", r=0.04, h=0.12, seg=4, loc=(x, 0, 1.12))
        p.box("brass", size=(0.06, 0.06, 0.03), loc=(x, 0, 1.05))
    p.gear("brass", r=0.13, thickness=0.04, teeth=8, tooth=0.06, hole=0.07, loc=(0, 0, 0.58), rot=(90, 0, 0))
    p.torus("brass", R=0.08, r=0.015, seg=8, seg2=4, loc=(-0.4, 0, 0.58), rot=(90, 0, 0))
    p.torus("brass", R=0.08, r=0.015, seg=8, seg2=4, loc=(0.4, 0, 0.58), rot=(90, 0, 0))
    p.build(root)
    return root


def build_crate():
    root = empty("prop_crate", size=0.5)
    S = 1.0
    p = Part("prop_crate_mesh")
    p.box("wood", size=(S - 0.04, S - 0.04, S - 0.04), loc=(0, 0, S / 2))
    h = S / 2 - 0.05
    t = 0.11
    for a in (-1, 1):
        for b in (-1, 1):
            p.box("wood_dark", size=(S, t, t), loc=(0, a * h, S / 2 + b * h))
            p.box("wood_dark", size=(t, S, t), loc=(a * h, 0, S / 2 + b * h))
            p.box("wood_dark", size=(t, t, S), loc=(a * h, b * h, S / 2))
    L = (S - 2 * t) * math.sqrt(2)
    for k in range(4):
        F = Matrix.Translation((0, 0, S / 2)) @ Matrix.Rotation(math.radians(90 * k), 4, "Z")
        with Xform(p, F):
            p.box("wood_dark", size=(L, 0.08, 0.1), loc=(0, -S / 2 + 0.02, 0), rot=(0, 45 if k % 2 else -45, 0))
    for a in (-1, 1):
        for b in (-1, 1):
            for c in (0, 1):
                p.box("brass", size=(0.15, 0.15, 0.15),
                      loc=(a * (S / 2 - 0.06), b * (S / 2 - 0.06), 0.075 + c * (S - 0.15)))
    p.box("brass", size=(0.34, 0.03, 0.18), loc=(0, -S / 2 - 0.03, S - 0.2))
    p.box("black", size=(0.24, 0.02, 0.04), loc=(0, -S / 2 - 0.045, S - 0.2))
    p.build(root)
    return root


def build_barrel():
    root = empty("prop_barrel", size=0.5)
    p = Part("prop_barrel_mesh")
    prof = [(0.0, 0.0), (0.0, 0.37), (0.15, 0.42), (0.38, 0.46), (0.55, 0.47), (0.72, 0.46), (0.95, 0.42),
            (1.1, 0.37), (1.07, 0.33), (1.07, 0.0)]
    lathe(p, "wood", prof, seg=12, mat_alt="wood_dark", alt_every=1, cap_mat="wood_dark")
    for z, rr in ((0.12, 0.415), (0.36, 0.462), (0.74, 0.462), (0.98, 0.415)):
        p.torus("iron", R=rr, r=0.025, seg=12, seg2=4, loc=(0, 0, z), scale=(1, 1, 1.6))
    p.cyl("brass", r=0.04, h=0.14, seg=6, loc=(0, -0.5, 0.28), rot=(90, 0, 0))
    p.box("brass", size=(0.03, 0.03, 0.08), loc=(0, -0.55, 0.32))
    p.box("wood_dark", size=(0.5, 0.06, 0.03), loc=(0, 0.05, 1.085))
    p.build(root)
    return root


def build_signpost():
    root = empty("prop_signpost", size=0.5)
    p = Part("prop_signpost_mesh")
    p.box("wood_dark", size=(0.16, 0.16, 2.08), loc=(0, 0, 1.04), rot=(0, 0, 0))
    p.cyl("brass", r=0.13, h=0.06, seg=8, loc=(0, 0, 2.08))
    p.gear("brass", r=0.1, thickness=0.05, teeth=8, tooth=0.05, loc=(0, 0, 2.15))
    p.cone("brass", r=0.06, h=0.1, seg=6, loc=(0, 0, 2.23))
    signs = [  # (z, dir, length, rot_z)
        (1.85, 1, 0.95, 0),
        (1.52, -1, 0.85, 0),
        (1.2, 1, 0.7, -20),
    ]
    for i, (z, d, L, rz) in enumerate(signs):
        arrow = [(-0.12, -0.12), (L - 0.15, -0.12), (L, 0.0), (L - 0.15, 0.12), (-0.12, 0.12)]
        pts = [(d * x, y) for x, y in arrow]
        if d < 0:
            pts = pts[::-1]
        with Xform(p, mtx((0, 0, z), (0, 0, rz))):
            extrude_profile(p, "wood", pts, 0.05, axis="Y", loc=(0, -0.105, 0))
            p.box("brass", size=(L * 0.55, 0.02, 0.13), loc=(d * (L * 0.4), -0.135, 0))
            p.box("brass_dark", size=(0.05, 0.03, 0.05), loc=(0, -0.14, 0))
    # small hanging lantern on the back
    p.box("iron", size=(0.04, 0.4, 0.04), loc=(0, 0.25, 1.95))
    p.box("iron", size=(0.02, 0.02, 0.12), loc=(0, 0.42, 1.88))
    p.cyl("brass", r=0.08, h=0.03, seg=6, loc=(0, 0.42, 1.8))
    p.cyl("glow_amber", r=0.06, h=0.14, seg=6, loc=(0, 0.42, 1.71))
    p.cyl("brass", r=0.08, h=0.03, seg=6, loc=(0, 0.42, 1.62))
    for i, (x, y) in enumerate(((0.22, -0.12), (-0.2, 0.15), (0.05, 0.25), (-0.15, -0.2))):
        jitter_ico(p, "stone", r=0.13, subdiv=0, loc=(x, y, 0.04), seed=90 + i, amount=0.15, floor=0.0)
    p.build(root)
    return root


# name, builder, preview kwargs
PROPS = [
    ("prop_lamp", build_lamp, {}),
    ("prop_pipe", build_pipe, {}),
    ("prop_pipe_arch", build_pipe_arch, {}),
    ("prop_vent", build_vent, dict(elevation=40)),
    ("prop_crystal", build_crystal, {}),
    ("prop_rock_a", build_rock_a, {}),
    ("prop_rock_b", build_rock_b, {}),
    ("prop_tree", build_tree, {}),
    ("prop_tree_b", build_tree_b, {}),
    ("prop_bush", build_bush, {}),
    ("prop_gear_monument", build_gear_monument, {}),
    ("prop_clocktower", build_clocktower, {}),
    ("prop_airship", build_airship, dict(elevation=12)),
    ("prop_rest", build_rest, {}),
    ("prop_chest", build_chest, dict(elevation=25)),
    ("prop_fence", build_fence, {}),
    ("prop_crate", build_crate, {}),
    ("prop_barrel", build_barrel, {}),
    ("prop_signpost", build_signpost, {}),
]
LANDMARKS = {"prop_clocktower", "prop_airship"}


def _report(name, root):
    tris = tree_tris(root)
    budget = 8000 if name in LANDMARKS else 1500
    mins, maxs = tree_bbox(root)
    size = maxs - mins
    flag = "" if tris <= budget else "  !!! OVER BUDGET"
    print(f"[tris] {name:22s} {tris:5d} / {budget}  size=({size.x:.2f}, {size.y:.2f}, {size.z:.2f})"
          f"  zmin={mins.z:.3f}{flag}")
    return tris


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    only = None
    for a in argv:
        if a.startswith("--only="):
            only = set(a.split("=", 1)[1].split(","))
    if "--previews" in argv:
        for name, fn, pv in PROPS:
            if only and name not in only:
                continue
            reset_scene()
            setup_mats()
            root = fn()
            bpy.context.view_layer.update()
            _report(name, root)
            mins, maxs = tree_bbox(root)
            rad = max(maxs.x - mins.x, maxs.y - mins.y) * 0.6 + 0.3
            preview_ground(rad)
            render_preview(name, size=560, **pv)
            if "--back" in argv:
                kw = dict(pv)
                kw["azimuth"] = 215
                render_preview(name + "_back", size=560, **kw)
    if "--no-export" in argv:
        return
    reset_scene()
    setup_mats()
    x = 0.0
    total = 0
    for name, fn, _ in PROPS:
        root = fn()
        bpy.context.view_layer.update()
        mins, maxs = tree_bbox(root)
        root.location.x = x - mins.x
        x += (maxs.x - mins.x) + 3.0
        bpy.context.view_layer.update()
        total += _report(name, root)
    print(f"[tris] total {total}")
    export_glb("props")
    render_preview("props", size=1400, azimuth=20, elevation=20)


main()
