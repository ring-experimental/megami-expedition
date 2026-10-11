"""arena.glb — hi-poly circular battle arena (see ASSET_SPEC.md "arena.glb" + "Hi-poly pass").

Contract: single top-level empty `root` at the origin; node `arena_platform` = the walkable floor whose
mesh never rises above z = 0 (flush inlays, every groove/chamfer goes down). Central r <= 9 m is flat.

Layout (radii in m, Blender Z up, +Y = the far side behind the enemies in battle):
    0 .. 3.95   brass relief medallion: glow hub, faceted 8-point compass star, bead ring, clock ring
                (12 stone blocks + brass / glowing hour marks), 32-tooth brass gear
    3.95 .. 8.45 four rows of chamfered stone slabs (V-grooves, per-slab tint) — calm stage floor
    8.45 .. 9.35 rune channel: two brass rings around a dark slate channel with raised glowing runes
    9.35 .. 12.0 darker weathered paving (some cracked slabs), 8 sectors split by brass strips,
                8 pillars on brass sockets (r 11.0), glowing conduits rune ring -> pillar
    12.0 .. 13.4 rounded brass rim lip (+0.11 m) with 40 crowned gear teeth, rivets, iron skirt
    below        floating rock underside (stalactites) with sunk gears, hydraulic struts, crystals,
                 broken copper pipes and sagging cables off the edge

Run (from project root):
    blender -b --factory-startup -P tools/blender/model_arena.py [-- options]
options:
    --previews            all previews (overall / top / side, 5 battle-camera views, close-ups)
    --views=all|game|overview|none   explicit preview set (default: overview = arena.png only)
    --fast                skip the vertex-AO bake (white COLOR_0) for quick shape checks
    --scratch             export to $ARENA_SCRATCH instead of public/models (iteration)
    --normals             print a winding/normal consistency report
Nodes: root > arena_platform (floor, top z = 0), arena_rim, arena_pillars, arena_underside, arena_hanging.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: E402,F401,F403
from env_helpers import *  # noqa: E402,F401,F403
from env_helpers import Xform, mtx, set_mat, box_m  # noqa: E402,F401
from mathutils import Matrix, Vector  # noqa: E402
import hp_helpers as hp  # noqa: E402
import hp_arena_helpers as ah  # noqa: E402
from hp_arena_helpers import P, TAU, PROF1, PROF2  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FAST = "--fast" in ARGS
TO_SCRATCH = "--scratch" in ARGS
SCRATCH = os.environ.get("ARENA_SCRATCH", os.path.join(os.environ.get("TEMP", "."), "arena_scratch"))
VIEWS = next((a.split("=", 1)[1] for a in ARGS if a.startswith("--views=")),
             "all" if "--previews" in ARGS else "overview")
BUDGET = 60000

# ---------------------------------------------------------------------------
# layout
# ---------------------------------------------------------------------------
R_MED = 3.95
ROWS_IN = [(3.95, 5.1, 20), (5.1, 6.25, 24), (6.25, 7.4, 28), (7.4, 8.45, 32)]
RING_A = (8.45, 8.62)        # brass ring inside the rune channel
CHANNEL = (8.62, 9.18)
RING_B = (9.18, 9.35)
ROWS_OUT = [(9.35, 10.68, 6), (10.68, 12.0, 6)]   # slabs per 45 deg sector
CONDUIT_W = 0.075            # half width (m) of the glowing conduit gap rune ring -> pillar socket
R_FLOOR = 12.0
STRIP_DA = 0.0078            # half angle of the 8 radial brass strips
PILLAR_R = 11.0
PILLAR_A = [math.radians(22.5 + 45 * k) for k in range(8)]
N_TEETH = 40
TOOTH_A0 = math.radians(4.5)  # teeth centred on the pillars, gaps on the strips


def setup_mats():
    get_mat("stone_mid", hex="#77726b", roughness=0.95)
    get_mat("arena_grout", hex="#2c2926", roughness=1.0)
    get_mat("arena_channel", hex="#1c242c", roughness=0.85)
    get_mat("arena_verdigris", hex="#6a8e80", metallic=0.3, roughness=0.65)
    # floor inlays glow softer than the pillar crystals: units stand on them, and at strength 6 the
    # bloom of the large central hub washed out the stage (in-game check 2026-10-11)
    get_mat("glow_arena_floor_cyan", hex="#5ff3ff", emission="#5ff3ff", strength=2.4)
    get_mat("glow_arena_floor_violet", hex="#b77bff", emission="#b77bff", strength=2.4)


# ---------------------------------------------------------------------------
# floor (arena_platform)
# ---------------------------------------------------------------------------
RUNES = [
    [((0, -.5), (0, .5))],                                                         # isa
    [((-.2, -.5), (-.2, .5)), ((-.2, .1), (.3, .45)), ((-.2, -.2), (.3, .15))],    # fehu
    [((-.25, -.5), (-.25, .5)), ((-.25, .5), (.25, .2)), ((.25, .2), (.25, -.5))],  # uruz
    [((-.2, -.5), (-.2, .5)), ((-.2, .3), (.2, 0)), ((.2, 0), (-.2, -.3))],         # thurisaz
    [((-.2, -.5), (-.2, .5)), ((-.2, .5), (.25, .2)), ((-.2, .2), (.25, -.1))],     # ansuz
    [((.2, .4), (-.2, 0)), ((-.2, 0), (.2, -.4))],                                  # kaunan
    [((-.3, .5), (.3, -.5)), ((-.3, -.5), (.3, .5))],                               # gebo
    [((-.25, -.5), (-.25, .5)), ((.25, -.5), (.25, .5)), ((-.25, .2), (.25, -.2))],  # hagalaz
    [((0, -.5), (0, .5)), ((-.25, .2), (.25, -.15))],                               # naudiz
    [((0, -.5), (0, .5)), ((0, .5), (.22, .28)), ((0, -.5), (-.22, -.28))],         # eihwaz
    [((0, -.5), (0, .5)), ((0, .1), (-.3, .45)), ((0, .1), (.3, .45))],             # algiz
    [((.2, .5), (-.2, .15)), ((-.2, .15), (.2, -.15)), ((.2, -.15), (-.2, -.5))],   # sowilo
    [((0, -.5), (0, .5)), ((0, .5), (-.3, .2)), ((0, .5), (.3, .2))],               # tiwaz
    [((-.15, -.5), (-.15, .5)), ((-.15, .5), (.25, .2))],                           # laguz
    [((0, .45), (.25, 0)), ((.25, 0), (0, -.45)), ((0, -.45), (-.25, 0)), ((-.25, 0), (0, .45))],  # ingwaz
    [((-.25, -.5), (-.25, .5)), ((.25, -.5), (.25, .5)), ((-.25, .5), (.25, .1)), ((.25, .5), (-.25, .1))],  # mannaz
]


def build_floor(root):
    p = ah.part("arena_platform")
    rnd = random.Random(11)
    crack_rnd = random.Random(23)

    def stone_tint(base=1.0, spread=0.085):
        v = base * rnd.uniform(1 - spread, 1 + spread * 0.5)
        w = rnd.uniform(-0.05, 0.05)
        return (v * (1 + w), v, v * (1 - w * 1.2))

    # -- 1) inner paving (FIRST material -> glTF primitive 0 reaches z = 0) -------------------
    for k, (r0, r1, n) in enumerate(ROWS_IN):
        off = (0.5 if k % 2 else 0.0) * TAU / n + 0.013 * k
        for i in range(n):
            a0 = off + TAU * i / n
            ah.slab(p, "stone", r0, r1, a0, a0 + TAU / n, rad_cell=1.2, arc_cell=0.4,
                    tint=stone_tint(1.0 + 0.012 * k))
    # -- 2) outer paving: 8 sectors split by brass strips ---------------------------------------
    for s in range(8):
        sa0 = math.radians(45 * s) + STRIP_DA
        sa1 = math.radians(45 * (s + 1)) - STRIP_DA
        for k, (r0, r1, n) in enumerate(ROWS_OUT):
            for i in range(n):
                a0 = sa0 + (sa1 - sa0) * i / n
                a1 = sa0 + (sa1 - sa0) * (i + 1) / n
                if k == 0 and i == n // 2 - 1:       # leave room for the conduit at the sector middle
                    a1 -= CONDUIT_W / r0
                if k == 0 and i == n // 2:
                    a0 += CONDUIT_W / r0
                tn = stone_tint(0.94, 0.10)
                if crack_rnd.random() < 0.16:          # cracked slab: two pieces split by a slanted crack
                    s_in, s_out = crack_rnd.uniform(0.25, 0.75), crack_rnd.uniform(0.25, 0.75)
                    ci, co = a0 + (a1 - a0) * s_in, a0 + (a1 - a0) * s_out
                    t2 = tuple(c * crack_rnd.uniform(0.9, 0.97) for c in tn)
                    ah.slab(p, "stone_mid", r0, r1, a0, ci, w=0.032, d=0.04, a0o=a0, a1o=co, rad_cell=1.5,
                            arc_cell=0.5, tint=tn)
                    ah.slab(p, "stone_mid", r0, r1, ci, a1, w=0.032, d=0.04, a0o=co, a1o=a1, rad_cell=1.5,
                            arc_cell=0.5, tint=t2)
                    continue
                ah.slab(p, "stone_mid", r0, r1, a0, a1, rad_cell=1.5, arc_cell=0.5, tint=tn)
        sa = math.radians(45 * s)
        ah.slab(p, "brass", ROWS_OUT[0][0], R_FLOOR, sa - STRIP_DA, sa + STRIP_DA, w=0.028, d=0.04,
                prof=PROF1, arc_cell=1.0, rad_cell=0.9)
        # glowing aether conduit: rune ring -> pillar socket (pillar k == sector s)
        am = math.radians(45 * s + 22.5)
        q0, q1 = P(ROWS_OUT[0][0] + 0.02, am), P(PILLAR_R - 0.86, am)
        ah.stroke(p, "glow_arena_floor_cyan" if s % 2 == 0 else "glow_arena_floor_violet", (q0.x, q0.y), (q1.x, q1.y), 0.06, -0.006, -0.034)
    # -- 3) rune channel ------------------------------------------------------------------------
    ah.ring(p, "brass", RING_A[0], RING_A[1], 144, w=0.034, d=0.045, prof=PROF1)
    ah.ring(p, "brass", RING_B[0], RING_B[1], 144, w=0.034, d=0.045, prof=PROF1)
    rc = (CHANNEL[0] + CHANNEL[1]) / 2
    H, W, SW = 0.34, 0.30, 0.045
    n_slots = 72
    for i in range(n_slots):
        ac = TAU * (i + 0.5) / n_slots + math.radians(90)
        if i % 4 == 3:      # separator: small diamond
            dia = [(0, .5), (.5, 0), (0, -.5), (-.5, 0)]     # CCW in world ((u, v) frame is left-handed)
            pts = []
            for (u, v) in dia:
                q = P(rc + v * 0.16, ac + u * 0.16 / rc)
                pts.append((q.x, q.y))
            ah.plate(p, "glow_arena_floor_cyan", pts, z=-0.006, w=0.0, z_bot=-0.034)
            continue
        glyph = RUNES[rnd.randrange(len(RUNES))]
        for (u0, v0), (u1, v1) in glyph:
            q0 = P(rc + v0 * H, ac + u0 * W / rc)
            q1 = P(rc + v1 * H, ac + u1 * W / rc)
            ah.stroke(p, "glow_arena_floor_cyan", (q0.x, q0.y), (q1.x, q1.y), SW, -0.006, -0.034)
    # -- 4) medallion ---------------------------------------------------------------------------
    # gear (32 teeth) — band with a toothed outer edge
    nt = 32
    angs, rad = [], []
    for k in range(nt):
        c = TAU * k / nt
        pt = TAU / nt
        for fa, rr in ((-0.29, 3.42), (-0.15, 3.80), (0.15, 3.80), (0.29, 3.42), (0.5, 3.42)):
            angs.append(c + fa * pt)
            rad.append(rr)
    ah.band(p, "brass", angs, 3.10, rad, w=0.03, d=0.04, prof=PROF2, wall=0.035)
    # clock ring: 12 stone blocks + 12 hour marks (cardinals glow)
    dm = 0.085 / 2.8
    for h in range(12):
        c = TAU * h / 12 + math.radians(90)
        ah.slab(p, "stone", 2.56, 3.04, c + dm, c + TAU / 12 - dm, w=0.03, d=0.04, prof=PROF2,
                arc_cell=0.35, rad_cell=1.0, z_extra=0.035, tint=stone_tint(1.04, 0.03))
        ah.slab(p, "glow_arena_floor_cyan" if h % 3 == 0 else "brass", 2.50, 3.08, c - dm, c + dm, w=0.02, d=0.03,
                prof=PROF1, arc_cell=1.0, rad_cell=1.0, z_extra=0.045,
                z=-0.004 if h % 3 == 0 else 0.0)
    # bead ring
    ah.ring(p, "brass", 2.36, 2.50, 72, w=0.028, d=0.035, prof=PROF1, wall=0.04)
    # compass star: 8 kite points, two tilted facets each (ridge at z=0)
    ze, zb = -0.05, -0.075
    for k in range(8):
        th = TAU * k / 8 + math.radians(90)
        long_pt = k % 2 == 0
        tip = 2.28 if long_pt else 1.62
        half = TAU / 16 - 0.014 / 0.86
        C, T = P(0.75, th), P(tip, th)
        L, R = P(0.86, th + half), P(0.86, th - half)
        bm = p.bm
        vC = bm.verts.new((C.x, C.y, 0.0))
        vT = bm.verts.new((T.x, T.y, 0.0))
        vL = bm.verts.new((L.x, L.y, ze))
        vR = bm.verts.new((R.x, R.y, ze))
        f1 = bm.faces.new((vC, vR, vT))
        f2 = bm.faces.new((vC, vT, vL))
        top = [vC, vR, vT, vL]
        bot = [bm.verts.new((v.co.x, v.co.y, zb)) for v in top]
        sides = ah._quad_strip(bm, top, bot)
        set_mat(p, [f1], "brass")
        set_mat(p, [f2], "brass_dark")
        set_mat(p, sides, "brass_dark")
    # hub: brass ring + glow ring + glow jewel
    ah.ring(p, "glow_arena_floor_cyan", 0.58, 0.70, 48, z=-0.006, w=0.0, d=0.01, wall=0.06)
    ah.ring(p, "brass", 0.20, 0.53, 48, w=0.03, d=0.035, prof=PROF1, wall=0.04)
    octo = [(0.17 * math.cos(TAU * j / 8 + math.pi / 8), 0.17 * math.sin(TAU * j / 8 + math.pi / 8)) for j in range(8)]
    ah.plate(p, "glow_arena_floor_cyan", octo, z=-0.004, w=0.03, d=0.03, z_bot=-0.075)
    # -- 5) recess floors: medallion base (deep) + grout plane under the paving -----------------
    ah.disc_grid(p, "gunmetal", 0.25, R_MED, -0.075, 48, 4, center=True)
    ah.wall_ring(p, "arena_grout", R_MED, -0.075, -0.03, 48, inward=True)
    ah.disc_grid(p, "arena_grout", R_MED, CHANNEL[0], -0.03, 72, 3)
    ah.disc_grid(p, "arena_channel", CHANNEL[0], CHANNEL[1], -0.03, 144, 1)
    ah.disc_grid(p, "arena_grout", CHANNEL[1], R_FLOOR + 0.06, -0.03, 96, 1)
    obj = ah.build_obj(p, root)

    def grime(co, n):      # outer ring darkens toward the rim lip (weathering), stage stays clean
        r = math.hypot(co.x, co.y)
        t = max(0.0, min(1.0, (r - 9.6) / 2.4))
        f = 1.0 - 0.13 * t * t * (3 - 2 * t)
        return (f, f * 0.99, f * 0.975)
    ah.tint_by(obj, grime)
    hp.smooth_obj(obj, 12)
    return obj


# ---------------------------------------------------------------------------
# rim (arena_rim): rounded brass gear ring + teeth + bolts on a dark iron skirt
# ---------------------------------------------------------------------------
TOOTH = [(12.60, -0.50), (13.02, -0.43), (13.36, -0.29), (13.36, 0.29), (13.02, 0.43), (12.60, 0.50)]
Z_GEAR = (0.045, -0.50)        # tooth top / bottom


def _tooth_top(r):
    """Crowned tooth top: flat near the lip, sloping down toward the tip."""
    t = max(0.0, (r - 12.85) / (13.36 - 12.85))
    return Z_GEAR[0] - 0.11 * t


def build_rim(root):
    p = ah.part("arena_rim")
    # brass ring: outer wall (behind the teeth) -> rounded lip -> inner step wall tucked below the floor
    prof = [(12.50, -0.56), (12.72, -0.49), (12.72, 0.0), (12.70, 0.06), (12.64, 0.097), (12.55, 0.108),
            (12.20, 0.108), (12.10, 0.097), (12.05, 0.06), (12.03, 0.0), (12.03, -0.07)]
    ah.lathe_rz(p, "brass", prof, 144, phase=TOOTH_A0)
    # iron skirt under the gear ring
    skirt = [(12.28, -1.04), (12.56, -1.04), (12.63, -0.98), (12.63, -0.62), (12.60, -0.55), (12.45, -0.55)]
    ah.lathe_rz(p, "gunmetal", skirt, 120, phase=TOOTH_A0)
    for k in range(N_TEETH):
        a = TOOTH_A0 + TAU * (k + 0.5) / N_TEETH
        # lip bolt (gap centre) + skirt rivet
        p.cyl("brass_dark", r=0.055, h=0.05, seg=6, loc=P(12.37, a, 0.125), rot=(0, 0, math.degrees(a)))
        if k % 4 == 0:
            p.cyl("brass_dark", r=0.045, h=0.05, seg=6, loc=P(12.64, a, -0.8), rot=(0, 90, math.degrees(a)))
    lip = ah.build_obj(p, root)
    hp.smooth_obj(lip, 35)

    t = ah.part("arena_rim_teeth")
    for k in range(N_TEETH):
        M = Matrix.Rotation(TOOTH_A0 + TAU * k / N_TEETH, 4, "Z")
        ah.prism(t, "brass", TOOTH, Z_GEAR[0], Z_GEAR[1], M=M)
    teeth = ah.build_obj(t, root)
    # crown the tooth tops: slope down toward the tip (machined look, catches the light)
    for v in teeth.data.vertices:
        if v.co.z > 0:
            r = math.hypot(v.co.x, v.co.y)
            v.co.z = _tooth_top(r)
    teeth.data.update()
    hp.bevel_obj(teeth, width=0.04, segments=1, angle=25)
    hp.smooth_obj(teeth, 35)

    b = ah.part("arena_rim_bolts")
    for k in range(N_TEETH):
        a = TOOTH_A0 + TAU * k / N_TEETH
        ah.lathe_rz(b, "brass_dark", [(0.068, -0.012), (0.068, 0.006), (0.045, 0.026), (0.0, 0.034)], 6,
                    M=Matrix.Translation(P(12.82, a, Z_GEAR[0])), phase=a)
    bolts = ah.build_obj(b, root)
    hp.smooth_obj(bolts, 35)
    return ah.join([lip, teeth, bolts], "arena_rim")


# ---------------------------------------------------------------------------
# pillars (arena_pillars) — 8x, one mesh
# ---------------------------------------------------------------------------

def _pillar_frame(a):
    """Local frame at the pillar base: local -Y points to the arena centre."""
    return Matrix.Translation(P(PILLAR_R, a, 0.0)) @ Matrix.Rotation(a - math.pi / 2, 4, "Z")


def build_pillars(root):
    stone = ah.part("pil_stone")      # octagonal plinths (bevelled)
    p = ah.part("pil_main")           # everything else
    for k, a in enumerate(PILLAR_A):
        F = _pillar_frame(a)
        glow = "glow_cyan" if k % 2 == 0 else "glow_violet"
        oct_ph = math.pi / 8
        ah.lathe_rz(stone, "stone_dark", [(0.80, -0.01), (0.80, 0.27), (0.74, 0.33), (0.62, 0.33)], 8, M=F,
                    phase=oct_ph)
        ah.lathe_rz(stone, "stone_dark", [(0.62, 0.30), (0.62, 0.50), (0.57, 0.55), (0.46, 0.55)], 8, M=F,
                    phase=oct_ph)
        # socket plate
        ah.lathe_rz(p, "brass", [(0.92, -0.02), (0.92, 0.02), (0.895, 0.045), (0.85, 0.056), (0.74, 0.056)],
                    20, M=F)
        # collar + rivets
        ah.lathe_rz(p, "brass", [(0.44, 0.53), (0.51, 0.55), (0.535, 0.59), (0.535, 0.66), (0.51, 0.70),
                                 (0.30, 0.70)], 20, M=F)
        for i in range(6):
            ang = TAU * i / 6 + math.pi / 6
            with Xform(p, F):
                p.cyl("brass_dark", r=0.034, h=0.03, seg=6, loc=P(0.545, ang, 0.625),
                      rot=(0, 90, math.degrees(ang)))
        # fluted shaft (16 flutes), slight taper
        seg = 32
        zs = [(0.68, 0.40), (1.15, 0.392), (1.75, 0.372), (2.16, 0.35)]
        bm = p.bm
        rings = []
        for z, r in zs:
            rings.append([bm.verts.new(F @ P(r - (0.024 if j % 2 else 0.0), TAU * j / seg, z)) for j in range(seg)])
        fs = []
        for i in range(len(rings) - 1):
            fs += ah._quad_strip(bm, rings[i], rings[i + 1])
        for f in fs:
            f.normal_flip()
        set_mat(p, fs, "stone_mid")
        # mid band
        ah.lathe_rz(p, "brass", [(0.30, 1.42), (0.40, 1.42), (0.418, 1.44), (0.418, 1.56), (0.40, 1.58),
                                 (0.30, 1.58)], 20, M=F)
        # astragal, capital flare + top ring
        ah.lathe_rz(p, "brass", [(0.30, 2.12), (0.372, 2.12), (0.386, 2.16), (0.372, 2.21), (0.30, 2.21)], 20, M=F)
        ah.lathe_rz(p, "stone_dark", [(0.30, 2.2), (0.36, 2.2), (0.46, 2.29), (0.55, 2.36), (0.56, 2.42),
                                      (0.46, 2.43)], 20, M=F)
        ah.lathe_rz(p, "brass", [(0.54, 2.40), (0.585, 2.43), (0.59, 2.50), (0.56, 2.54), (0.32, 2.55)], 20, M=F)
        for i in range(4):     # corbel brackets under the top ring
            ang = 45.0 + 90.0 * i
            with Xform(p, F @ Matrix.Rotation(math.radians(ang), 4, "Z")):
                extrude_profile(p, "brass", [(0.35, 2.10), (0.62, 2.41), (0.35, 2.41)], 0.075, axis="Y")
        # cradle bowl (outside up, rim, inside down to the pole)
        ah.lathe_rz(p, "brass", [(0.22, 2.53), (0.40, 2.64), (0.47, 2.78), (0.41, 2.80), (0.18, 2.66),
                                 (0.0, 2.65)], 20, M=F)
        # arched claws + clamp ring
        for i in range(4):
            ang = TAU * i / 4 + math.pi / 4
            pts = [F @ P(r, ang, z) for r, z in ((0.44, 2.74), (0.505, 2.93), (0.50, 3.12), (0.42, 3.3),
                                                 (0.31, 3.42), (0.22, 3.48))]
            tube_path(p, "brass", pts, radii=[0.056, 0.05, 0.046, 0.038, 0.027, 0.014], seg=8, cap_start=False)
        with Xform(p, F):
            p.torus("brass_dark", R=0.505, r=0.03, seg=24, seg2=5, loc=(0, 0, 3.05))
        # crystals: big main shard + 3 small ones
        with Xform(p, F):
            shard(p, glow, r=0.26, h=0.72, tip=0.42, seg=6, base=0.5, loc=(0, 0, 2.66), spin=k * 17)
            for j, (x, y, rx, ry, s) in enumerate(((0.2, 0.08, 6, 30, 1.0), (-0.17, 0.12, 10, -32, 0.85),
                                                  (0.02, -0.21, -34, 4, 0.9))):
                shard(p, glow, r=0.08 * s, h=0.22 * s, tip=0.14 * s, seg=5, base=0.6, loc=(x, y, 2.7),
                      rot=(rx, ry, 0), spin=k * 7 + j * 20)
        # rune plate facing the centre (-Y local)
        ah.curved_panel(p, "brass_dark", F, 0.36, 0.425, math.radians(-90 - 24), math.radians(-90 + 24),
                        0.8, 1.32, n=4)
        ah.curved_panel(p, "brass", F, 0.36, 0.432, math.radians(-90 - 26), math.radians(-90 + 26),
                        0.77, 0.8, n=4)
        ah.curved_panel(p, "brass", F, 0.36, 0.432, math.radians(-90 - 26), math.radians(-90 + 26),
                        1.32, 1.35, n=4)
        with Xform(p, F):
            rune = RUNES[(k * 5 + 3) % len(RUNES)]
            for (u0, v0), (u1, v1) in rune:
                q0 = Vector((u0 * 0.2, -0.43, 1.06 + v0 * 0.34))
                q1 = Vector((u1 * 0.2, -0.43, 1.06 + v1 * 0.34))
                d = q1 - q0
                ang = math.degrees(math.atan2(d.z, d.x))
                box_m(p, glow, mtx((q0 + q1) / 2, (0, -ang, 0), (d.length + 0.035, 0.04, 0.035)))
        # copper conduit on the +X side, with brackets
        with Xform(p, F):
            pts = [(0.47, 0.12, 0.05), (0.47, 0.12, 0.42), (0.43, 0.10, 0.62), (0.43, 0.10, 2.1),
                   (0.45, 0.08, 2.32)]
            tube_path(p, "copper", pts, r=0.04, seg=6)
            for z in (1.0, 1.9):
                box_m(p, "brass_dark", mtx((0.42, 0.10, z), (0, 0, 15), (0.1, 0.13, 0.05)))
    so = ah.build_obj(stone, root)
    hp.bevel_obj(so, width=0.03, segments=1, angle=30)
    hp.smooth_obj(so, 35)
    mo = ah.build_obj(p, root)
    hp.smooth_obj(mo, 35)
    me = mo.data
    gl = {i for i, m in enumerate(me.materials) if m.name.startswith("glow_")}
    for f in me.polygons:
        if f.material_index in gl:
            f.use_smooth = False
    return ah.join([mo, so], "arena_pillars")


# ---------------------------------------------------------------------------
# underside (arena_underside): floating rock + clockwork
# ---------------------------------------------------------------------------

def gear3d(part, mat, r_in, r_root, r_tip, teeth, thick, M):
    bm = part.bm
    angs, rad = [], []
    for k in range(teeth):
        c = TAU * k / teeth
        pt = TAU / teeth
        for fa, rr in ((-0.27, r_root), (-0.14, r_tip), (0.14, r_tip), (0.27, r_root), (0.5, r_root)):
            angs.append(c + fa * pt)
            rad.append(rr)
    n = len(angs)
    lay = []
    for z in (thick / 2, -thick / 2):
        o = [bm.verts.new(M @ P(r, a, z)) for a, r in zip(angs, rad)]
        i = [bm.verts.new(M @ P(r_in, a, z)) for a in angs]
        lay.append((o, i))
    (o0, i0), (o1, i1) = lay
    faces = []
    for j in range(n):
        k = (j + 1) % n
        faces.append(bm.faces.new((i0[j], o0[j], o0[k], i0[k])))        # top
        faces.append(bm.faces.new((i1[k], o1[k], o1[j], i1[j])))        # bottom
    faces += ah._quad_strip(bm, o0, o1)                                # outer wall
    faces += ah._quad_strip(bm, list(reversed(i0)), list(reversed(i1)))  # inner wall
    set_mat(part, faces, mat)
    return faces


ROCK_PROF = [(0.0, -7.7), (1.4, -7.35), (2.4, -6.8), (2.9, -6.6), (3.9, -6.3), (4.7, -5.6), (5.9, -5.2),
             (6.5, -4.7), (7.4, -4.25), (8.3, -3.5), (9.3, -3.2), (9.9, -2.6), (10.9, -2.25), (11.5, -1.55),
             (12.05, -1.16), (12.3, -1.0)]


def _rock_z(r):
    for (r0, z0), (r1, z1) in zip(ROCK_PROF, ROCK_PROF[1:]):
        if r0 <= r <= r1:
            return z0 + (z1 - z0) * (r - r0) / (r1 - r0)
    return ROCK_PROF[-1][1]


# (angle deg, radius, gear radius)
UNDER_GEARS = ((38, 9.2, 1.7), (158, 7.6, 2.0), (283, 10.2, 1.45))


def build_underside(root):
    rock = ah.part("und_rock")
    # dense (r, z) profile resampled from ROCK_PROF (more rings -> striations / ledges can show)
    prof = []
    for (r0, z0), (r1, z1) in zip(ROCK_PROF, ROCK_PROF[1:]):
        n = max(1, int(round(abs(z1 - z0) / 0.32)))
        for i in range(n):
            prof.append((r0 + (r1 - r0) * i / n, z0 + (z1 - z0) * i / n))
    prof.append(ROCK_PROF[-1])
    ah.lathe_rz(rock, "stone_mid", prof, 44)
    ro = ah.build_obj(rock, root)
    gear_pts = [(P(rr, math.radians(a), _rock_z(rr)), gr) for a, rr, gr in UNDER_GEARS]

    def wgt(pv):
        w = max(0.0, min(1.0, (-pv.z - 1.3) / 0.7))
        for c, gr in gear_pts:
            dd = (pv - c).length
            if dd < gr + 1.2:
                w *= 0.15 + 0.85 * max(0.0, (dd - gr) / 1.2)
        return w
    from mathutils import noise as mnoise
    me = ro.data
    for v in me.vertices:
        co = v.co
        w = wgt(co)
        if w <= 0:
            continue
        r = math.hypot(co.x, co.y)
        if r < 1e-4:
            co.z += -0.3 * w
            continue
        th = math.atan2(co.y, co.x)
        # columnar striations: noise stretched along z, sampled on a fixed-radius cylinder
        q = Vector((math.cos(th) * 9.0, math.sin(th) * 9.0, co.z * 0.22))
        ridge = mnoise.fractal(q * 0.9, 0.7, 2.0, 3, noise_basis="PERLIN_ORIGINAL")
        lump = mnoise.fractal(co * 0.3 + Vector((7.1, 3.3, 1.9)), 0.6, 2.0, 3, noise_basis="PERLIN_ORIGINAL")
        dr = (0.55 * ridge + 0.75 * lump) * w
        co.x += math.cos(th) * dr
        co.y += math.sin(th) * dr
        # ledges: pull z toward 0.9 m terraces a little
        step = 0.9
        zq = round(co.z / step) * step
        co.z += (zq - co.z) * 0.35 * w + lump * 0.25 * w
    me.update()

    def rock_tint(co, n):
        t = max(0.0, min(1.0, (-co.z - 1.0) / 6.5))
        band = 0.92 + 0.08 * math.sin(co.z * 3.5 + 0.8 * math.sin(co.x * 0.35 + co.y * 0.2))
        top = 1.0 - 0.42 * t
        up = max(0.0, n.z) * 0.12          # ledge tops a touch lighter / warmer
        return (min(1, top * band + up), min(1, top * band * 0.96 + up * 0.9), top * band * (0.88 + 0.1 * t))
    ah.tint_by(ro, rock_tint)
    hp.smooth_obj(ro, 32)

    m = ah.part("und_mech")
    # gears sunk into the rock surface, axis along the local surface normal (outward + down)
    for (a_deg, rr, gr) in UNDER_GEARS:
        a = math.radians(a_deg)
        slope = math.degrees(math.atan2(_rock_z(rr + 0.5) - _rock_z(rr - 0.5), 1.0))
        tilt = 90.0 - slope
        M = (Matrix.Translation(P(rr, a, _rock_z(rr))) @ Matrix.Rotation(a, 4, "Z") @
             Matrix.Rotation(math.radians(90 + tilt), 4, "Y") @ Matrix.Translation((0, 0, 0.05)) @
             Matrix.Rotation(math.radians(a_deg * 3), 4, "Z"))
        gear3d(m, "brass_dark", gr * 0.74, gr, gr + 0.34, 12, 0.3, M)
        with Xform(m, M):
            m.cyl("brass", r=gr * 0.28, h=0.46, seg=14)
            m.cyl("gunmetal", r=gr * 0.1, h=0.66, seg=8)
            for s in range(4):
                sa = 90 * s + 45
                box_m(m, "brass_dark", mtx(P(gr * 0.5, math.radians(sa), 0), (0, 0, sa), (gr * 0.5, 0.18, 0.18)))
    # hydraulic struts from under the gear teeth into the rock
    for k in (8, 22, 35):
        a = TOOTH_A0 + TAU * k / N_TEETH
        p0, p1 = P(12.95, a, -0.5), P(10.6, a, _rock_z(10.6) - 0.15)
        d = (p1 - p0).normalized()
        tube_path(m, "gunmetal", [p0, p0 + (p1 - p0) * 0.55], r=0.16, seg=10)
        tube_path(m, "steel", [p0 + (p1 - p0) * 0.5, p1], r=0.07, seg=8)
        for q, rr in ((p0 + d * 0.12, 0.2), (p0 + (p1 - p0) * 0.53, 0.19), (p1 - d * 0.1, 0.14)):
            tube_path(m, "brass", [q - d * 0.06, q + d * 0.06], r=rr, seg=10)
    # big hanging crystal cluster under the tip
    zt = ROCK_PROF[0][1] + 0.35
    for i, (x, y, rx, ry, h, rr, mat) in enumerate((
            (0.0, 0.0, 180, 0, 2.2, 0.55, "glow_cyan"), (0.9, 0.3, 154, 20, 1.4, 0.34, "glow_violet"),
            (-0.75, 0.55, 156, -24, 1.25, 0.32, "glow_cyan"), (0.15, -0.95, 204, 6, 1.1, 0.3, "glow_violet"),
            (-0.5, -0.55, 198, -16, 0.8, 0.22, "glow_cyan"), (0.6, -0.4, 170, 26, 0.7, 0.2, "glow_cyan"))):
        shard(m, mat, r=rr, h=h, tip=rr * 1.6, seg=6, base=0.7, loc=(x, y, zt), rot=(rx, ry, 0), spin=i * 13)
    # crystal outcrops on the slope
    for i, (a_deg, rr) in enumerate(((95, 6.2), (215, 8.8), (330, 5.0), (260, 7.0))):
        a = math.radians(a_deg)
        base = P(rr, a, _rock_z(rr) - 0.1)
        for j, (dx, dy, tx, ty, s) in enumerate(((0, 0, 0, 0, 1.0), (0.25, 0.1, 18, 12, 0.7), (-0.2, 0.2, -20, 8, 0.6))):
            M = (Matrix.Translation(base + Vector((dx, dy, 0))) @ Matrix.Rotation(a, 4, "Z") @
                 Matrix.Rotation(math.radians(125 + tx), 4, "Y") @ Matrix.Rotation(math.radians(ty), 4, "X"))
            with Xform(m, M):
                shard(m, "glow_cyan" if (i + j) % 3 else "glow_violet", r=0.17 * s, h=0.6 * s, tip=0.3 * s,
                      seg=5, base=0.7, spin=i * 30 + j * 11)
    # dangling rock stalactites (break up the cone silhouette)
    srnd = random.Random(31)
    for i in range(16):
        a = TAU * i / 16 + srnd.uniform(-0.12, 0.12)
        rr = srnd.uniform(2.5, 9.5)
        ln = srnd.uniform(1.4, 3.4) * (1.25 - rr / 14)
        top = P(rr, a, _rock_z(rr) + 0.45)
        ah.rock_spike(m, "stone_mid", top, srnd.uniform(0.7, 1.15), ln + 0.45, seg=7, rings=4, seed=90 + i,
                      lean=(srnd.uniform(-0.3, 0.3), srnd.uniform(-0.3, 0.3)))
    # small floating rocks with crystals
    for i, (x, y, z, s) in enumerate(((5.5, -4.0, -9.4, 0.9), (-6.2, 3.5, -8.6, 0.7), (2.0, 7.0, -10.4, 0.6))):
        jitter_ico(m, "stone_mid", r=s, subdiv=2, loc=(x, y, z), scale=(1.0, 0.9, 0.75), amount=0.22, seed=40 + i)
        shard(m, "glow_cyan" if i % 2 else "glow_violet", r=s * 0.22, h=s * 0.5, tip=s * 0.3, seg=5,
              loc=(x, y, z + s * 0.45), rot=(8, -10, 0), spin=i * 20)
    mo = ah.build_obj(m, root)
    hp.smooth_obj(mo, 35)
    me = mo.data
    gl = {i for i, mm in enumerate(me.materials) if mm.name.startswith("glow_")}
    for f in me.polygons:
        if f.material_index in gl:
            f.use_smooth = False
    return ah.join([ro, mo], "arena_underside")


# ---------------------------------------------------------------------------
# hanging pipes & cables (arena_hanging)
# ---------------------------------------------------------------------------

def _flange(p, q, M_axis, rp, mat="brass"):
    M = Matrix.Translation(q) @ M_axis
    ah.lathe_rz(p, mat, [(rp + 0.005, -0.075), (rp + 0.085, -0.07), (rp + 0.1, -0.045), (rp + 0.1, 0.045),
                         (rp + 0.085, 0.07), (rp + 0.005, 0.075)], 16, M=M)


def build_hanging(root):
    p = ah.part("arena_hanging")
    pitch = TAU / N_TEETH

    def gap(k):
        return TOOTH_A0 + pitch * (k + 0.5)

    # broken copper pipes: out from under the skirt, bend down, corroded lower run, broken off
    for i, (k, drop, rp) in enumerate(((32, 2.6, 0.2), (22, 1.7, 0.17), (12, 3.2, 0.19))):
        a = gap(k)
        zc = -1.3
        bend = [P(11.3, a, zc), P(12.6, a, zc)]
        for t in range(1, 7):
            th = math.radians(90 * t / 6)
            bend.append(P(12.6 + 0.55 * math.sin(th), a, zc - 0.55 + 0.55 * math.cos(th)))
        tube_path(p, "copper", bend + [P(13.15, a, zc - 0.85)], r=rp, seg=12, cap_start=True, cap_end=False)
        low = [P(13.15, a, zc - 0.85), P(13.15, a, zc - 0.55 - drop * 0.5), P(13.17, a + 0.002, zc - 0.55 - drop)]
        rings = tube_path(p, "copper", low, r=rp, seg=12, cap_start=False, cap_end=True, jag=0.13,
                          seed=100 + i)
        cap = [f for f in p.bm.faces if len(f.verts) == 12 and all(v in rings[-1] for v in f.verts)]
        set_mat(p, cap, "gunmetal")
        _flange(p, P(12.25, a, zc), Matrix.Rotation(a, 4, "Z") @ Matrix.Rotation(math.pi / 2, 4, "Y"), rp)
        _flange(p, P(13.15, a, zc - 0.85), Matrix.Identity(4), rp, mat="arena_verdigris")
    # a short broken stub sticking straight out
    a = gap(36)
    tube_path(p, "copper", [P(11.9, a, -1.3), P(13.5, a, -1.36)], r=0.16, seg=12, cap_end=True, jag=0.16, seed=120)
    _flange(p, P(12.8, a, -1.33), Matrix.Rotation(a, 4, "Z") @ Matrix.Rotation(math.pi / 2, 4, "Y"), 0.16,
            mat="arena_verdigris")
    # sagging cables between brackets under the skirt
    for i, (k0, k1, sag) in enumerate(((3, 5, 1.3), (8, 11, 2.0), (17, 19, 1.0), (25, 28, 1.7), (29, 31, 1.1))):
        a0, a1 = gap(k0), gap(k1)
        pts = []
        n = 14
        for t in range(n + 1):
            u = t / n
            aa = a0 + (a1 - a0) * u
            pts.append(P(12.52 + 0.3 * math.sin(math.pi * u), aa, -1.16 - 4 * sag * u * (1 - u)))
        tube_path(p, "gunmetal", pts, r=0.05, seg=6)
        for aa in (a0, a1):
            box_m(p, "brass_dark", mtx(P(12.52, aa, -1.1), (0, 0, math.degrees(aa)), (0.22, 0.2, 0.16)))
    # dangling cable ends with plugs
    for i, (k, L) in enumerate(((14, 2.4), (34, 3.0), (6, 1.8))):
        a = gap(k)
        pts = [P(12.5, a, -1.14), P(12.72, a, -1.4), P(12.86, a + 0.004, -1.14 - L * 0.5),
               P(12.8, a + 0.008, -1.14 - L * 0.85), P(12.78, a + 0.01, -1.14 - L)]
        tube_path(p, "gunmetal", pts, r=0.05, seg=6)
        end = Vector(P(12.78, a + 0.01, -1.14 - L - 0.12))
        p.cyl("brass", r=0.085, h=0.24, seg=8, loc=tuple(end))
        p.cyl("copper", r=0.03, h=0.14, seg=6, loc=tuple(end + Vector((0, 0, -0.18))))
        box_m(p, "brass_dark", mtx(P(12.5, a, -1.1), (0, 0, math.degrees(a)), (0.22, 0.2, 0.16)))
    o = ah.build_obj(p, root)
    hp.smooth_obj(o, 35)
    return o


# ---------------------------------------------------------------------------

def normal_report(obj):
    """Debug: faces whose winding disagrees with bmesh's recalculation (per connected island), and for
    the floor any face pointing down."""
    import bmesh as _bm
    bm = _bm.new()
    bm.from_mesh(obj.data)
    before = [f.normal.copy() for f in bm.faces]
    _bm.ops.recalc_face_normals(bm, faces=bm.faces[:])
    flips = sum(1 for f, n0 in zip(bm.faces, before) if f.normal.dot(n0) < 0)
    from collections import Counter
    mats = obj.data.materials
    c = Counter((mats[f.material_index].name, "up" if n0.z > 0.5 else ("side" if n0.z > -0.5 else "down"))
                for f, n0 in zip(bm.faces, before) if f.normal.dot(n0) < 0)
    if c:
        print("   ", dict(c))
    down = sum(1 for n0 in before if n0.z < -0.5)
    bm.free()
    print(f"[normals] {obj.name:16s} faces={len(before):6d} disagree_with_recalc={flips:5d} facing_down={down}")


def check_platform_top(obj):
    zmax = max(v.co.z for v in obj.data.vertices)
    print(f"[check] arena_platform max z = {zmax:.6f}")
    assert zmax <= 1e-6, "arena_platform rises above z = 0"
    assert abs(zmax) < 1e-6, "arena_platform top is not at z = 0"
    m0 = obj.data.materials[0].name
    z0 = max((obj.data.vertices[i].co.z for f in obj.data.polygons if f.material_index == 0 for i in f.vertices))
    print(f"[check] slot 0 material '{m0}' max z = {z0:.6f}")


def render_all(views):
    if views == "none":
        return
    arena_objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if views == "overview":
        hp.render_hp("arena", size=1000, azimuth=25, elevation=30, dist_k=2.45, objs=arena_objs,
                     target=((0, 0, -1.5), 15.5), sun=(40, -40.6), ground=False)
        return
    B = ah.three_to_blender
    game = [
        ("arena_cam_overview", B((0, 6.5, 15)), B((0, 1.2, -1))),
        ("arena_cam_intro", B((14, 9, 18)), B((0, 1, 0))),
        ("arena_cam_command", B((-4.9, 2.4, 8.6)), B((0.6, 1.0, -4.4))),
        ("arena_cam_party", B((2, 4.5, -2.9)), B((0, 1, 4.6))),
        ("arena_cam_action", B((8.5, 3.2, 1.5)), B((0, 1.1, 0))),
    ]
    dummies = ah.add_dummies([(-3.4, -4.6, 1.75), (0, -5.2, 1.6), (3.4, -4.6, 1.75),
                              (-3.8, 4.4, 1.0), (0, 4.4, 2.1), (3.8, 4.4, 0.6)])
    for name, c, l in game:
        ah.render_cam(name, c, l)
    for o in dummies:
        bpy.data.objects.remove(o)
    if views == "game":
        return
    hp.render_hp("arena", size=1000, azimuth=25, elevation=30, dist_k=2.45, objs=arena_objs,
                 target=((0, 0, -1.5), 15.5), sun=(40, -40.6), ground=False)
    hp.render_hp("arena_top", size=1000, azimuth=0, elevation=89, dist_k=2.75, objs=arena_objs,
                 target=((0, 0, 0), 14.2), sun=(40, -40.6), ground=False)
    hp.render_hp("arena_side", size=1000, azimuth=60, elevation=3, dist_k=2.6, objs=arena_objs,
                 target=((0, 0, -3.5), 15), sun=(40, -40.6), ground=False)
    # pillar close-up (far-side pillar seen from the centre) and medallion close-up
    pa = PILLAR_A[1]
    pc = P(PILLAR_R, pa, 1.95)
    ah.render_cam("arena_pillar", pc - P(5.6, pa, 0) + Vector((1.4, 0, 0.5)), pc, fov_v=42, res=(900, 1000))
    ah.render_cam("arena_center", Vector((0.0, -6.5, 4.0)), Vector((0, -0.2, 0)), fov_v=45, res=(1100, 800))
    pb = P(PILLAR_R, PILLAR_A[2], 0.0)
    ah.render_cam("arena_detail", pb - P(3.6, PILLAR_A[2], 0) + Vector((0.0, -1.6, 1.7)), pb + Vector((0, 0, 0.5)),
                  fov_v=50, res=(1100, 800))
    ah.render_cam("arena_edge", Vector((16.5, -9.0, 1.0)), Vector((11.5, -6.0, -1.2)), fov_v=45, res=(1100, 800))


def main():
    reset_scene()
    setup_mats()
    root = empty("root", size=1.0)
    parts = [build_floor(root), build_rim(root), build_pillars(root), build_underside(root), build_hanging(root)]
    bpy.context.view_layer.update()
    tot = 0
    for o in parts:
        t = hp.obj_tris(o)
        tot += t
        print(f"[tris] {o.name:18s} {t:6d}  mats={[m.name for m in o.data.materials]}")
    print(f"[tris] arena total {tot} / {BUDGET}")
    check_platform_top(parts[0])
    if "--normals" in ARGS:
        for o in parts:
            normal_report(o)
    mats = sorted({m.name for o in parts for m in o.data.materials})
    print(f"[mats] {len(mats)}: {mats}")
    if not FAST:
        hp.bake_vertex_ao(objs=parts, samples=48, distance=1.2, strength=0.85, floor=0.3, ground=None)
    else:
        hp.fill_vertex_color(parts)
    ah.apply_tint(parts)
    hp.export_glb_hp("arena", out_dir=SCRATCH if TO_SCRATCH else None)
    render_all(VIEWS)


main()
