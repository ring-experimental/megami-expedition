"""Grand Carillon (그란 카리용) — chapter-1 boss, archetype **golem**. Hi-poly.
~4.2 m tall (needle tip), the bell hovers with its lip at z = 0.62. Exports public/models/grand_carillon.glb.

An antique cast-brass bell (verdigris streaks, cast inscription band, gear medallion) with a gear
crown pierced by the black HUSH NEEDLE (dripping black oil). Inside the arched mouth on the front
sits a softly lit glass clock face: winding-arbor eyes, hour / minute hands as brows. Two black-iron
striking hammers are its arms, four decorative hammers fan out on its back, short piston feet hide
under the skirt and a lyre pendulum swings behind as a tail. Narrow top, wide bottom.

Skeleton (golem / humanoid names, src/anim/rig.ts), armature object 'root':
  root > hips (z 1.15, clapper + foot yoke inside the bell)
           > torso (z 1.25) > head (clock face, pivot at the dial centre) > brow_L (minute hand),
                                                                           brow_R (hour hand)
                            > needle (hush needle, pivot at the puncture: pull it out along its axis)
                            > arm_L > forearm_L (striking hammer), arm_R > forearm_R
                            > (steam_point)  rigid empty on the crown whistle
           > leg_L > shin_L, leg_R > shin_R  (short piston feet under the skirt)
           > tail_1 > tail_2 > tail_3        (pendulum, brass bob at the end; secondary-motion chain)
The four back hammers are part of the torso (no bones, per CHAPTER1.md 5-4).

Usage: blender -b --factory-startup -P tools/blender/model_grand_carillon.py [-- out=<dir>] [quick]
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import hp_helpers as hp  # noqa: E402
from common import empty, get_mat, reset_scene  # noqa: E402
from hp_beetle_helpers import (BoneBuilder, _face, ball, box_m, catmull, dome, gear_ring, lathe_m,  # noqa: E402
                               mtx, resample, set_mat, strip, sweep, torus_m)
from hp_grand_carillon_helpers import (TAU, BellProfile, bell_band, bell_shell, round_section,  # noqa: E402
                                       surf_frame)
from rig_helpers import pose_world, reset_pose, rig_from_parts  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
QUICK = "quick" in ARGS
OUT = next((a.split("=", 1)[1] for a in ARGS if a.startswith("out=")), hp.PREVIEW_DIR)
os.makedirs(OUT, exist_ok=True)

reset_scene()
root = empty("root")
V = Vector
D = math.radians

# ---- materials (13) --------------------------------------------------------------------------
BEL = "bell_brass"      # antique cast brass
VRD = "verdigris"       # green patina streaks
BIN = "bell_inner"      # inside of the bell
HAM = "hammer_iron"     # striking hammers (black iron)
NDL = "hush_iron"       # the hush needle
OIL = "oil_black"       # dripping black oil (glossy)
BRS = "brass"           # bright brass: gears, bands, bezels
CU = "copper"           # pistons
STE = "steel"           # axles
DIA = "glow_dial"       # softly lit enamel dial (low emission)
BLK = "black"           # numerals, hands
GLS = "glass"           # dial cover (game: transparent)
GLW = "glow_amber"      # eyes, hover jets
get_mat(BEL, hex="#b08d3c", metallic=0.88, roughness=0.4)
get_mat(VRD, hex="#5e7a5a", metallic=0.2, roughness=0.78)
get_mat(BIN, hex="#3a3020", metallic=0.6, roughness=0.62)
get_mat(HAM, hex="#2b2a28", metallic=0.65, roughness=0.46)
get_mat(NDL, hex="#1a1a1c", metallic=0.8, roughness=0.28)
get_mat(OIL, hex="#060607", metallic=0.15, roughness=0.06)
get_mat(DIA, hex="#efe6cf", emission="#6e6656", strength=1.0, roughness=0.35)
get_mat(GLS, alpha=0.22)
for _m in (BRS, CU, STE, BLK, GLW):
    get_mat(_m)

ROUND = 75.0
HARD = 34.0


def bevel(w, seg=2, angle=30.0):
    return dict(width=w, segments=seg, angle=angle)


# ---- bell profile / pivots --------------------------------------------------------------------
LIP = 0.62
BELL = BellProfile([(LIP, 1.30), (0.68, 1.335), (0.76, 1.33), (0.86, 1.275), (1.05, 1.165), (1.35, 1.035),
                    (1.75, 0.925), (2.2, 0.845), (2.6, 0.805), (2.9, 0.785), (3.06, 0.755), (3.18, 0.67),
                    (3.26, 0.51), (3.31, 0.30), (3.33, 0.0)],
                   [(LIP, 0.13), (0.8, 0.11), (1.1, 0.07), (3.0, 0.06), (3.33, 0.06)])
ARCH_TOP = 1.74
ARCH_A0 = D(37)
HIPS_Z = 1.15
TORSO_Z = 1.25
FACE_C = V((0, -0.70, 1.20))
FACE_R = 0.40
FACE_TILT = D(10)                  # dial tilted back so the battle camera sees it
SHOULDER = V((1.30, 0.0, 2.55))
ELBOW_Z = 2.02
LEG_X = 0.34
LEG_P = V((LEG_X, 0.0, 1.02))
KNEE_Z = 0.82
NEEDLE_IN = V((0.05, 0.02, 3.42))   # puncture point in the crown
NEEDLE_DIR = V((-0.42, 0.22, 0.88)).normalized()
NEEDLE_L = 1.02
TAIL = [V((0, 0.50, 1.05)), V((0, 0.88, 0.73)), V((0, 1.22, 0.50)), V((0, 1.52, 0.40))]


def open_a(z):
    if z >= ARCH_TOP:
        return 0.0
    u = max(0.0, (z - LIP) / (ARCH_TOP - LIP))
    return ARCH_A0 * max(0.0, 1 - u ** 2.4) ** 0.5


def face_frame():
    """Matrix of the clock face: local Z = outward normal (front, tilted up), local X = +X."""
    n = V((0, -math.cos(FACE_TILT), math.sin(FACE_TILT)))
    return mtx(FACE_C, n, (1, 0, 0))


FM = face_frame()


# ---- verdigris streaks ------------------------------------------------------------------------
_rr = random.Random(11)
STREAKS = []
for _k in range(30):
    th = _rr.uniform(0, TAU)
    z0 = _rr.choice([3.01, 3.01, 2.40, 2.40, 2.40, 2.71, 1.9, 0.77])
    L = _rr.uniform(0.3, 1.1) if z0 > 1.0 else _rr.uniform(0.06, 0.1)
    L = min(L, z0 - (LIP + 0.1))
    STREAKS.append((th, _rr.uniform(0.07, 0.15), z0, L))


def surface_streak(p, mat, th0, z0, L, w0, wob=0.03, n=7, thick=0.14, off=0.002, seed=0):
    """Flattened tapering streak lying on the bell surface (verdigris run, oil rivulet)."""
    pts, rads = [], []
    for i in range(n):
        f = i / (n - 1)
        z = z0 - L * f
        th = th0 + wob * math.sin(f * 4.0 + seed)
        if abs(th) < open_a(z) + D(3):           # never run across the mouth opening
            th = math.copysign(open_a(z) + D(3), th if th != 0 else 1.0)
        pts.append(surf_frame(BELL, th, z, off)[0])
        rads.append(w0 * (1 - 0.75 * f) * (0.8 + 0.2 * math.sin(f * 9 + seed)))
    rads[-1] *= 0.5
    up = surf_frame(BELL, th0, z0 - L * 0.5)[1]
    sweep(p, mat, pts, rads, seg=6, up=up, fx=thick, fy=1.0)
    return pts[-1]


def build_verdigris(p):
    for k, (th, w, z0, L) in enumerate(STREAKS):
        if z0 - L < ARCH_TOP + 0.05 and abs((th + math.pi) % TAU - math.pi) < ARCH_A0 + w + D(4):
            continue                              # would cross the mouth opening
        surface_streak(p, VRD, th, z0, L, w * BELL.r(z0) * 0.5, seed=k)
    rr = random.Random(21)
    for k in range(14):                           # patina pooled under the sound-bow moulding
        th = rr.uniform(0, TAU)
        if abs((th + math.pi) % TAU - math.pi) < ARCH_A0 + D(4):
            continue
        q, n, t = surf_frame(BELL, th, 0.72, 0.0)
        ball(p, VRD, q, rr.uniform(0.06, 0.11), seg=8, rings=4, z_axis=n, x_hint=t,
             scale=(1.0, 0.7, 0.12))


# =============================================================================================
# HIPS — clapper + foot yoke inside the bell
# =============================================================================================
def build_hips(parent):
    P = V((0, 0, HIPS_Z))
    bb = BoneBuilder("hips", P)
    rnd = bb.piece(smooth=ROUND)
    hard = bb.piece(smooth=HARD, bevel=bevel(0.012, 1))
    hard.box(HAM, size=(2 * LEG_X + 0.26, 0.22, 0.14), loc=(0, 0, 1.08))          # yoke bar
    hard.box(HAM, size=(0.18, 0.62, 0.12), loc=(0, 0.28, 1.06))                   # tail mount arm
    sweep(rnd, HAM, [V((0, 0.0, 1.06)), V((0, 0.0, 1.55))], 0.05, seg=10)         # clapper rod
    ball(rnd, HAM, V((0, 0.0, 0.98)), 0.2, seg=16, rings=10)                     # clapper ball
    torus_m(rnd, BRS, mtx(V((0, 0, 1.08)), (0, 0, 1)), 0.075, 0.025, seg=12, seg2=5)
    for sx in (1, -1):
        lathe_m(rnd, BRS, [(0.0, -0.06), (0.13, -0.06), (0.14, 0.0), (0.12, 0.06), (0.0, 0.07)],
                mtx(V((sx * LEG_X, 0, 1.02)), (0, 0, 1)), seg=14)                 # leg sockets
    return bb.build(parent, (0, 0, 0))


def build_leg(s, parent):
    side = "L" if s > 0 else "R"
    H = V((s * LEG_X, 0, LEG_P.z))
    bb = BoneBuilder("leg_" + side, H)
    rnd = bb.piece(smooth=ROUND)
    ball(rnd, HAM, H, 0.1, seg=12, rings=7)
    lathe_m(rnd, CU, [(0.0, -0.04), (0.105, -0.04), (0.11, -0.02), (0.11, -0.19), (0.12, -0.2), (0.0, -0.22)],
            mtx(H, (0, 0, 1)), seg=14, cap=(False, False))
    torus_m(rnd, BRS, mtx(H + V((0, 0, -0.07)), (0, 0, 1)), 0.112, 0.016, seg=14, seg2=4)
    leg = bb.build(parent, (0, 0, HIPS_Z))
    K = V((s * LEG_X, 0, KNEE_Z))
    bb = BoneBuilder("shin_" + side, K)
    rnd = bb.piece(smooth=ROUND)
    hard = bb.piece(smooth=HARD, bevel=bevel(0.015, 1))
    sweep(rnd, STE, [K + V((0, 0, 0.06)), K + V((0, 0, -0.2))], 0.045, seg=10)
    hard.cyl(HAM, r=0.17, h=0.08, r2=0.14, seg=16, loc=K + V((0, 0, -0.23)))
    torus_m(rnd, GLW, mtx(K + V((0, 0, -0.275)), (0, 0, 1)), 0.11, 0.022, seg=16, seg2=4)   # hover jet
    hard.cyl(BLK, r=0.085, h=0.02, seg=12, loc=K + V((0, 0, -0.272)))
    bb.build(leg, H)
    return leg


def build_tail(parent):
    prev = parent
    prev_p = V((0, 0, HIPS_Z))
    for i in range(3):
        a, b = TAIL[i], TAIL[i + 1]
        bb = BoneBuilder(f"tail_{i + 1}", a)
        rnd = bb.piece(smooth=ROUND)
        # lyre rod: twin brass rods with an iron spine
        d = (b - a).normalized()
        for sx in (1, -1):
            off = V((sx * 0.045, 0, 0))
            sweep(rnd, BRS, [a + off, b + off * 0.8], 0.022, seg=8)
        sweep(rnd, HAM, [a, b], 0.03, seg=8)
        ball(rnd, BRS, a, 0.06, seg=10, rings=6)
        if i == 2:
            # pendulum bob: big brass lens facing +-X, rim bead, verdigris centre boss
            c = b + d * 0.24
            nb = d.cross(V((1, 0, 0))).normalized()          # bob faces back / front, swings sideways
            M = mtx(c, nb, (1, 0, 0))
            lathe_m(rnd, BEL, [(0.0, -0.055), (0.2, -0.045), (0.26, -0.012), (0.265, 0.0), (0.26, 0.012),
                               (0.2, 0.045), (0.0, 0.055)], M, seg=22)
            for sx in (1, -1):
                torus_m(rnd, BRS, M @ Matrix.Translation((0, 0, sx * 0.03)), 0.22, 0.014, seg=20, seg2=4)
                lathe_m(rnd, VRD, [(0.07, 0.0), (0.065, 0.01), (0.0, 0.02)],
                        M @ Matrix.Translation((0, 0, sx * 0.042)) @ Matrix.Rotation(0 if sx > 0 else math.pi, 4, "X"),
                        seg=12, cap=(False, False))
            sweep(rnd, BRS, [b, c - d * 0.25], 0.035, seg=8)
        obj = bb.build(prev, prev_p)
        prev, prev_p = obj, a
    return


# =============================================================================================
# TORSO — the bell: wall, mouldings, inscription, medallion, crown, back hammers, shoulder axles
# =============================================================================================
def build_torso(parent):
    P = V((0, 0, TORSO_Z))
    bb = BoneBuilder("torso", P)
    wall = bb.piece(smooth=40)
    rnd = bb.piece(smooth=ROUND)
    hard = bb.piece(smooth=HARD)
    hardb = bb.piece(smooth=HARD, bevel=bevel(0.01, 1))
    # --- wall ---
    zs = [LIP, 0.66, 0.70, 0.75, 0.80, 0.86, 0.94, 1.04, 1.16, 1.28, 1.40, 1.50, 1.58, 1.64, 1.68, 1.71,
          1.73, ARCH_TOP, 1.85, 2.05, 2.3, 2.5, 2.7, 2.9, 3.04, 3.13, 3.2, 3.26, 3.3, 3.33]
    zin = [z for z in zs if z <= ARCH_TOP] + [2.3, 2.9, 3.13, 3.26, 3.33]
    bell_shell(wall, BELL, zs, zin, 48, open_a, BEL, BIN, BEL)
    build_verdigris(bb.piece(smooth=60))
    # --- mouldings: sound bow, lip, waist bands, shoulder ---
    rs = round_section
    for z, h, out in ((0.665, 0.05, 0.022), (0.80, 0.035, 0.016)):
        a = open_a(z) + D(1.5)
        bell_band(rnd, BRS if z < 0.7 else BEL, BELL, z, rs(h, out, 3), a, TAU - a, seg=32)
    for z, h, out in ((2.42, 0.045, 0.02), (2.73, 0.045, 0.02), (3.04, 0.04, 0.02)):
        bell_band(rnd, BEL, BELL, z, rs(h, out, 3), 0.0, TAU, seg=36)
    # --- opening edge bead (follows the arch) ---
    pts = []
    for k in range(25):
        z = LIP + 0.005 + (ARCH_TOP - LIP - 0.005) * (k / 24) ** 0.7
        pts.append((open_a(z), z))
    path = [surf_frame(BELL, a + D(1.2), z, 0.012)[0] for a, z in pts] + \
           [surf_frame(BELL, -a - D(1.2), z, 0.012)[0] for a, z in reversed(pts[:-1])]
    path = resample(catmull(path, 2), 64)
    sweep(rnd, BRS, path, 0.024, seg=6)
    # --- cast inscription between the waist bands (letter-like relief) ---
    rr = random.Random(3)
    th = D(-125)
    while th < D(125):
        w = rr.choice([0.035, 0.05, 0.06])
        z = 2.575
        for stroke in range(rr.choice([1, 2, 2])):
            sz = (w * rr.uniform(0.25, 1.0), 0.016, rr.uniform(0.05, 0.11))
            dz = rr.uniform(-0.03, 0.03)
            q, n, t = surf_frame(BELL, th + rr.uniform(-0.01, 0.01), z + dz, 0.004)
            box_m(hard, BEL, mtx(q, n, t), (sz[0], sz[2], sz[1]))
        th += (w + 0.03) / BELL.r(2.575) + 0.012
    # --- front gear medallion above the arch ---
    q, n, t = surf_frame(BELL, 0.0, 2.15, 0.0)
    M = mtx(q - n * 0.01, n, t)
    lathe_m(hard, BEL, [(0.24, 0.0), (0.235, 0.025), (0.215, 0.035), (0.0, 0.035)], M, seg=36, cap=(False, False))
    gear_ring(hard, BRS, M @ Matrix.Translation((0, 0, 0.03)), 0.19, 0.165, 16, 0.025, r_hole=0.12, spokes=6,
              hub=0.05, hub_h=0.04, mat_hub=BRS, bottom=False)
    torus_m(rnd, BEL, M @ Matrix.Translation((0, 0, 0.03)), 0.225, 0.012, seg=36, seg2=4)
    # --- shoulder axles (bell side -> shoulder hub) ---
    for sx in (1, -1):
        a0 = V((sx * 0.70, 0, SHOULDER.z))
        a1 = V((sx * (SHOULDER.x - 0.14), 0, SHOULDER.z))
        lathe_m(rnd, BRS, [(0.0, -0.02), (0.2, -0.02), (0.21, 0.04), (0.15, 0.09), (0.0, 0.1)],
                mtx(V((sx * 0.74, 0, SHOULDER.z)), (sx, 0, 0)), seg=20)                 # socket
        sweep(rnd, STE, [a0, a1], 0.075, seg=14)
        torus_m(rnd, BRS, mtx(a0.lerp(a1, 0.6), (sx, 0, 0)), 0.085, 0.02, seg=14, seg2=4)
        # brace strut from the axle down to the wall
        b0 = a0.lerp(a1, 0.75) + V((0, 0, -0.04))
        q2, n2, _ = surf_frame(BELL, D(90) * sx, 2.15, 0.0)
        sweep(rnd, HAM, [b0, q2], 0.035, seg=8)
        dome(rnd, BRS, q2, n2, 0.05, seg=10)
    # --- back hammer fan (decorative, no bones) ---
    hub = V((0, 0.88, 2.6))
    lathe_m(rnd, BRS, [(0.0, -0.06), (0.2, -0.06), (0.22, 0.0), (0.18, 0.06), (0.0, 0.08)],
            mtx(hub, (0, 1, 0)), seg=20)
    gear_ring(hard, BRS, mtx(hub + V((0, 0.03, 0)), (0, 1, 0)), 0.3, 0.26, 14, 0.04, r_hole=0.2, spokes=0,
              bottom=True)
    for ang in (-64, -24, 24, 64):
        a = D(ang)
        d = V((math.sin(a), 0.22, math.cos(a))).normalized()
        L = 1.22 if abs(ang) < 40 else 1.05
        s0 = hub + d * 0.15 + V((0, 0.08, 0))
        s1 = hub + d * L + V((0, 0.08, 0))
        sweep(rnd, HAM, [s0, s1], 0.04, seg=10)
        torus_m(rnd, BRS, mtx(s0.lerp(s1, 0.25), d), 0.046, 0.012, seg=10, seg2=4)
        # mallet head across the shaft (in the fan plane)
        side = V((0, 1, 0)).cross(d).normalized()
        Mh = mtx(s1, side, d)
        lathe_m(rnd, HAM, [(0.0, -0.25), (0.11, -0.25), (0.13, -0.22), (0.13, 0.22), (0.11, 0.25), (0.0, 0.25)],
                Mh, seg=12)
        for sg in (1, -1):
            torus_m(rnd, BRS, Mh @ Matrix.Translation((0, 0, sg * 0.17)), 0.133, 0.014, seg=12, seg2=4)
            lathe_m(rnd, BRS, [(0.1, 0.0), (0.09, 0.03), (0.0, 0.04)],
                    Mh @ Matrix.Translation((0, 0, sg * 0.25)) @ Matrix.Rotation(0 if sg > 0 else math.pi, 4, "X"),
                    seg=12, cap=(False, False))
    # --- gear crown on top ---
    CZ = 3.30
    lathe_m(rnd, BRS, [(0.0, CZ - 0.02), (0.44, CZ - 0.02), (0.47, CZ + 0.02), (0.44, CZ + 0.06), (0.0, CZ + 0.06)],
            mtx(V((0, 0, 0)), (0, 0, 1)), seg=32)
    gear_ring(hard, BRS, mtx(V((0, 0, CZ + 0.0))), 0.56, 0.49, 20, 0.07, r_hole=0.4, spokes=0, bottom=True)
    for k in range(8):
        a = TAU * (k + 0.5) / 8
        base = V((math.sin(a) * 0.45, -math.cos(a) * 0.45, CZ + 0.04))
        out = V((math.sin(a), -math.cos(a), 0))
        tip = base + out * 0.1 + V((0, 0, 0.34 if k % 2 == 0 else 0.24))
        Mt = mtx(base, (tip - base).normalized(), out, scale=(1.0, 0.45, 1.0))
        L = (tip - base).length
        lathe_m(hard, BRS, [(0.13, 0.0), (0.12, 0.05), (0.06, L * 0.75), (0.0, L)], Mt, seg=4, cap=(False, False))
        ball(rnd, BRS, tip, 0.04 if k % 2 == 0 else 0.03, seg=8, rings=5)
    # upright crown wheel (the needle is driven through it)
    Mw = mtx(V((0, 0.02, CZ + 0.36)), (0, -1, 0), (1, 0, 0))
    gear_ring(hard, BRS, Mw @ Matrix.Translation((0, 0, -0.03)), 0.3, 0.26, 18, 0.06, r_hole=0.2, spokes=5,
              hub=0.07, hub_h=0.08, mat_hub=BEL, bottom=True)
    hard.box(BEL, size=(0.12, 0.14, 0.34), loc=(0, 0.02, CZ + 0.14))                    # wheel post
    # steam whistle on the crown (back-left) -> steam_point
    wb = V((0.26, 0.26, CZ + 0.05))
    lathe_m(rnd, BRS, [(0.0, 0.0), (0.06, 0.0), (0.06, 0.14), (0.045, 0.16), (0.045, 0.26), (0.07, 0.28),
                       (0.07, 0.34), (0.0, 0.35)], mtx(wb, (0, 0, 1)), seg=12)
    # --- black oil: puddle at the puncture, rivulets over the crown and down the shoulder ---
    oil = bb.piece(smooth=70)
    ball(oil, OIL, NEEDLE_IN + V((0, 0, -0.02)), 0.11, seg=12, rings=6, scale=(1.2, 1.0, 0.45))
    for k, (th0, L) in enumerate(((D(-28), 0.55), (D(12), 0.85), (D(62), 0.45), (D(-75), 0.65), (D(150), 0.5))):
        # over the crown ring edge
        top = [V((math.sin(th0) * 0.36, -math.cos(th0) * 0.36, CZ + 0.075)),
               V((math.sin(th0) * 0.46, -math.cos(th0) * 0.46, CZ + 0.06)),
               V((math.sin(th0) * 0.49, -math.cos(th0) * 0.49, CZ + 0.0))]
        sweep(oil, OIL, top, [0.04, 0.035, 0.03], seg=6, up=(0, 0, 1), fx=0.35, fy=1.0)
        end = surface_streak(oil, OIL, th0, 3.27, L, 0.032, wob=0.04, n=8, thick=0.3, off=0.006, seed=k)
        ball(oil, OIL, end + V((0, 0, -0.025)), 0.032, seg=8, rings=6, scale=(1, 1, 1.5))
    # drop hanging off the crown wheel
    ball(oil, OIL, V((0.12, -0.05, CZ + 0.12)), 0.03, seg=8, rings=5, scale=(1, 1, 1.6))
    return bb.build(parent, (0, 0, HIPS_Z))


# =============================================================================================
# HEAD — glass clock face inside the mouth, eyes, brow hands (own bones)
# =============================================================================================
def build_head(parent):
    bb = BoneBuilder("head", FACE_C)
    rnd = bb.piece(smooth=ROUND)
    hard = bb.piece(smooth=HARD)
    M = FM
    # back housing (dark brass drum) + mounting stem to the bell interior
    lathe_m(rnd, BIN, [(0.0, -0.22), (0.36, -0.22), (0.44, -0.12), (0.46, -0.02), (0.0, -0.02)], M, seg=40)
    sweep(rnd, HAM, [FACE_C + V((0, 0.15, 0)), FACE_C + V((0, 0.55, 0.1))], 0.07, seg=10)
    # bezel ring
    lathe_m(rnd, BRS, [(FACE_R - 0.01, 0.0), (FACE_R + 0.06, -0.02), (FACE_R + 0.075, 0.02), (FACE_R + 0.05, 0.06),
                       (FACE_R + 0.01, 0.065), (FACE_R - 0.005, 0.035)], M, seg=40, cap=(False, False))
    # enamel dial (softly lit)
    lathe_m(hard, DIA, [(FACE_R, 0.0), (FACE_R, 0.012), (0.0, 0.012)], M, seg=48, cap=(False, False))
    # hour marks: 12 bars, heavier at 12 / 3 / 6 / 9; minute dots ring
    for k in range(12):
        a = TAU * k / 12
        big = k % 3 == 0
        L = 0.075 if big else 0.05
        c = M @ V((math.sin(a) * (FACE_R - 0.04 - L / 2), math.cos(a) * (FACE_R - 0.04 - L / 2), 0.016))
        R = (M.to_3x3() @ Matrix.Rotation(-a, 3, "Z")).to_4x4()
        box_m(hard, BLK, Matrix.Translation(c) @ R, (0.022 if big else 0.012, L, 0.008))
    torus_m(rnd, BLK, M @ Matrix.Translation((0, 0, 0.014)), FACE_R - 0.025, 0.004, seg=48, seg2=3)
    # eyes: winding-arbor holes (black sockets, amber glow, brass bezels)
    for sx in (1, -1):
        Me = M @ Matrix.Translation((sx * 0.16, -0.06, 0.012))
        lathe_m(rnd, BRS, [(0.085, -0.005), (0.088, 0.012), (0.075, 0.026), (0.062, 0.02), (0.06, 0.0)], Me, seg=20,
                cap=(False, False))
        lathe_m(hard, BLK, [(0.061, 0.004), (0.0, 0.004)], Me, seg=20, cap=(False, False))
        lathe_m(rnd, GLW, [(0.036, 0.0), (0.034, 0.012), (0.018, 0.024), (0.0, 0.026)], Me, seg=14,
                cap=(False, False))
    # arbor hub (nose)
    lathe_m(rnd, BRS, [(0.045, 0.012), (0.045, 0.04), (0.03, 0.055), (0.0, 0.06)], M, seg=16, cap=(False, False))
    # glass cover (shallow dome)
    lathe_m(rnd, GLS, [(FACE_R + 0.005, 0.05), (FACE_R * 0.7, 0.085), (FACE_R * 0.35, 0.1), (0.0, 0.104)], M, seg=32,
            cap=(False, False))
    head = bb.build(parent, (0, 0, TORSO_Z))
    # brow hands (pivot at the dial centre, rotate around the face normal)
    for name, ang, L, w in (("brow_R", D(-56), 0.29, 0.05), ("brow_L", D(56), 0.36, 0.036)):
        bb = BoneBuilder(name, FACE_C)
        hand = bb.piece(smooth=HARD, bevel=bevel(0.004, 1))
        R = (M.to_3x3() @ Matrix.Rotation(-ang, 3, "Z")).to_4x4()
        Mh = Matrix.Translation(M @ V((0, 0, 0.03 if name == "brow_R" else 0.042))) @ R
        box_m(hand, BLK, Mh @ Matrix.Translation((0, L * 0.45, 0)), (w * 0.5, L * 0.9, 0.01))
        # spade / arrow tip and counterweight
        tip = [Mh @ V((0, L * 0.86, 0)), Mh @ V((w, L * 0.93, 0)), Mh @ V((0, L * 1.06, 0)), Mh @ V((-w, L * 0.93, 0))]
        vs = [hand.bm.verts.new(q) for q in tip]
        vt = [hand.bm.verts.new(q + M.to_3x3() @ V((0, 0, 0.01))) for q in tip]
        fs = [_face(hand.bm, vs[::-1]), _face(hand.bm, vt)] + strip(hand.bm, vs, vt, closed=True)
        set_mat(hand, fs, BLK)
        hand.cyl(BLK, r=w * 0.7, h=0.012, seg=12, loc=tuple(Mh @ V((0, -0.06, 0))),
                 rot=tuple(math.degrees(a) for a in R.to_euler()))
        hand.cyl(BRS if name == "brow_L" else BLK, r=0.03, h=0.012, seg=12, loc=tuple(Mh @ V((0, 0, 0.002))),
                 rot=tuple(math.degrees(a) for a in R.to_euler()))
        bb.build(head, FACE_C)
    return head


# =============================================================================================
# NEEDLE — the black hush needle stuck in the crown (own bone: pull it out along its axis)
# =============================================================================================
def build_needle(parent):
    bb = BoneBuilder("needle", NEEDLE_IN)
    rnd = bb.piece(smooth=ROUND)
    hard = bb.piece(smooth=HARD)
    d = NEEDLE_DIR
    a = NEEDLE_IN - d * 0.12                    # buried point
    b = NEEDLE_IN + d * NEEDLE_L                # eye end
    M = mtx(a, d, (1, 0, 0))
    L = (b - a).length
    lathe_m(rnd, NDL, [(0.0, 0.0), (0.03, 0.1), (0.055, 0.3), (0.068, 0.5), (0.068, L - 0.42), (0.058, L - 0.33),
                       (0.03, L - 0.29), (0.0, L - 0.27)], M, seg=14)
    # the needle eye: an open elongated loop at the blunt end (loop plane contains the needle axis)
    side = d.cross(V((0, 0, 1))).normalized()
    Me = mtx(a + d * (L - 0.15), side, d, scale=(2.3, 1.0, 1.0))
    torus_m(rnd, NDL, Me, 0.065, 0.026, seg=20, seg2=6)
    torus_m(rnd, NDL, M @ Matrix.Translation((0, 0, 0.62)), 0.07, 0.016, seg=14, seg2=4)
    # oil running down the shaft from the eye + drips hanging below
    oil = bb.piece(smooth=70)
    for k, ang in enumerate((0.4, 2.3)):
        side = (M.to_3x3() @ V((math.cos(ang), math.sin(ang), 0))).normalized()
        pts = [M @ V((0, 0, z)) + side * 0.066 for z in (L - 0.34, L - 0.5, 0.75, 0.46)]
        pts = catmull(pts, 2)
        sweep(oil, OIL, [q + side * 0.012 for q in pts], [0.02] * (len(pts) - 1) + [0.012], seg=6, up=side,
              fx=0.45, fy=1.0)
        ball(oil, OIL, pts[-1] + V((0, 0, -0.03)), 0.025, seg=8, rings=5, scale=(1, 1, 1.6))
    return bb.build(parent, (0, 0, TORSO_Z))


# =============================================================================================
# ARMS — black-iron striking hammers
# =============================================================================================
def build_arm(s, parent):
    side = "L" if s > 0 else "R"
    S = V((s * SHOULDER.x, 0, SHOULDER.z))
    bb = BoneBuilder("arm_" + side, S)
    rnd = bb.piece(smooth=ROUND)
    bar = bb.piece(smooth=HARD, bevel=bevel(0.012, 2))
    # shoulder hub: gear disc on the axle
    gear_ring(rnd, BRS, mtx(S + V((s * -0.07, 0, 0)), (s, 0, 0)), 0.2, 0.17, 12, 0.08, r_hole=0.1, spokes=4,
              hub=0.07, hub_h=0.1, mat_hub=HAM, bottom=True)
    lathe_m(rnd, HAM, [(0.0, -0.08), (0.13, -0.08), (0.14, 0.06), (0.1, 0.1), (0.0, 0.11)], mtx(S, (s, 0, 0)), seg=16)
    # lever arm: flat iron bar to the elbow, brass rivets
    E = V((s * SHOULDER.x, 0, ELBOW_Z))
    bar.box(HAM, size=(0.1, 0.17, SHOULDER.z - ELBOW_Z), loc=(S + E) / 2)
    for f in (0.3, 0.55, 0.8):
        q = S.lerp(E, f)
        dome(rnd, BRS, q + V((s * 0.05, 0, 0)), (s, 0, 0), 0.022, seg=8)
    arm = bb.build(parent, (0, 0, TORSO_Z))
    bb = BoneBuilder("forearm_" + side, E)
    rnd = bb.piece(smooth=ROUND)
    hard = bb.piece(smooth=HARD, bevel=bevel(0.012, 2))
    # elbow knuckle (brass drum along X)
    lathe_m(rnd, BRS, [(0.0, -0.1), (0.08, -0.1), (0.09, -0.08), (0.09, 0.08), (0.08, 0.1), (0.0, 0.1)],
            mtx(E, (1, 0, 0)), seg=16)
    # haft
    Hc = V((s * SHOULDER.x, 0, 1.47))
    sweep(rnd, HAM, [E, Hc + V((0, 0, 0.12))], 0.05, seg=10)
    for z in (1.86, 1.70):
        torus_m(rnd, BRS, mtx(V((E.x, 0, z)), (0, 0, 1)), 0.055, 0.014, seg=12, seg2=4)
    # hammer head: big iron mallet along Y, brass bands and striking caps
    Mh = mtx(Hc, (0, -1, 0), (1, 0, 0))
    lathe_m(rnd, HAM, [(0.0, -0.40), (0.16, -0.40), (0.205, -0.35), (0.21, -0.13), (0.19, 0.0), (0.21, 0.13),
                       (0.205, 0.35), (0.16, 0.40), (0.0, 0.40)], Mh, seg=16)
    for sg in (1, -1):
        torus_m(rnd, BRS, Mh @ Matrix.Translation((0, 0, sg * 0.26)), 0.21, 0.024, seg=16, seg2=4)
        lathe_m(rnd, BRS, [(0.155, 0.0), (0.15, 0.035), (0.1, 0.06), (0.0, 0.066)],
                Mh @ Matrix.Translation((0, 0, sg * 0.395)) @ Matrix.Rotation(0 if sg > 0 else math.pi, 4, "X"),
                seg=16, cap=(False, False))
    hard.box(BRS, size=(0.14, 0.16, 0.1), loc=Hc + V((0, 0, 0.21)))       # collar where the haft enters
    bb.build(arm, S)
    return arm


# =============================================================================================
# Assemble
# =============================================================================================
hips = build_hips(root)
torso = build_torso(hips)
build_leg(1, hips)
build_leg(-1, hips)
build_tail(hips)
head = build_head(torso)
build_needle(torso)
build_arm(1, torso)
build_arm(-1, torso)
empty("steam_point", parent=torso, loc=(0.26, 0.26, 3.30 + 0.05 + 0.36 - TORSO_Z))

print(f"[tris] pre-rig total {hp.scene_tris()}")
for nm, t in sorted(((o.name, hp.obj_tris(o)) for o in bpy.context.scene.objects if o.type == "MESH"),
                    key=lambda r: -r[1]):
    print(f"[tris] {nm:14s} {t}")

arm = rig_from_parts(root, rigid=set(), smooth={}, skin_name="grand_carillon_skin")
skin = bpy.data.objects["grand_carillon_skin"]


def tint(p, n):
    k = 0.94 + 0.06 * max(0.0, n.z)
    return (k, k, k * 0.97)


hp.bake_vertex_ao(objs=[skin], samples=24 if QUICK else 40, distance=0.45, strength=0.75, floor=0.35, ground=0.0,
                  tint=tint)
hp.export_glb_hp("grand_carillon")

N = os.path.join(OUT, "grand_carillon")
hp.render_hp(N, azimuth=35, elevation=18)
hp.render_hp(N + "_game", azimuth=25, elevation=18, dist_k=4.0, size=560)
hp.render_hp(N + "_face", target=((0, -0.9, 1.3), 0.75), azimuth=15, elevation=12)
if not QUICK:
    hp.render_views(N, views=(("_front", 0, 8), ("_side", 90, 8), ("_back", 200, 20)))
    hp.render_hp(N + "_crown", target=((0, 0, 3.6), 0.8), azimuth=30, elevation=25)
    hp.render_hp(N + "_needle", target=((-0.15, 0.1, 3.75), 0.6), azimuth=25, elevation=18)


def posed(name, rotations, **kw):
    pose_world(arm, rotations)
    hp.render_hp(name, **kw)
    reset_pose(arm)


ATTACK = {"torso": [("X", -10)], "arm_L": [("X", -150)], "forearm_L": [("X", -50)],
          "arm_R": [("X", -150)], "forearm_R": [("X", -50)], "tail_1": [("Z", 15)], "tail_2": [("Z", 12)],
          "brow_L": [("Y", -20)], "brow_R": [("Y", 20)]}
posed(N + "_pose_attack", ATTACK, azimuth=40, elevation=12)
if not QUICK:
    SLAM = {"torso": [("X", 25)], "arm_L": [("X", -60)], "arm_R": [("X", -60)], "head": [("Z", 15)],
            "leg_L": [("X", -25)], "leg_R": [("X", 20)], "shin_L": [("X", 20)]}
    posed(N + "_pose_slam", SLAM, azimuth=70, elevation=10)
print(f"[done] grand_carillon {hp.scene_tris()} tris")
