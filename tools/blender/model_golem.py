"""Steam Golem — elite enemy (~3.2 m), hi-poly quality pass (2026-10-11).
Exports public/models/golem.glb (skinned, RIG_SPEC.md) + previews tools/blender/previews/golem*.png.

    blender -b --factory-startup -P tools/blender/model_golem.py [-- fast | parts]

Part hierarchy (rig_from_parts turns every mesh part into a bone of the same name):
  root > hips > {torso > {head, arm_L > forearm_L, arm_R > forearm_R, core, chimney > (steam_point)},
                 leg_L > shin_L, leg_R > shin_R}
  (parenthesised = rigid attachment / marker, not skinned)
Faces -Y, character's right = -X, feet on z = 0, fists hang down to ~z = 0.4. Pivots are fixed
(game tuning depends on them).

Construction: riveted iron boiler body built from smooth superellipse lofts (hp_golem_helpers.Surf)
with raised plate courses, brass bands, lap seams, rivet rows and a weld bead modelled as geometry.
Joints are hard mechanical pieces with rigid weights: shoulder drums (axis X) turning in brass socket
flanges, hinge knuckles at elbows/knees with yoke cheeks on the child part (all centred on the joint
axis -> they never open when bent), couters / poleyns covering the joint points, hip balls in sockets.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Matrix, Vector

from common import reset_scene, empty, get_mat
from char_helpers import tube, sgear
import hp_helpers as hp
from hp_golem_helpers import (Surf, capsule, surf_shell, surf_plate, surf_trim, surf_band, surf_rivets,
                              round_profile, rivet, bolt, lathe_axis, arc_plate, arc_bolts, arc_rivets, orient,
                              fplace, theta_at_x, row, col, linspace, LPart, D, TAU,
                              BEVEL_BIG, BEVEL_MID, BEVEL_ROUND)
from rig_helpers import rig_from_parts, HUMANOID_TEST_POSE, pose_world, reset_pose

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FAST = "fast" in ARGS

reset_scene()

# ---- materials (10) ---------------------------------------------------------------------------------
IRON = "golem_iron"
DARK = "golem_dark"
GOLD = "golem_gold"
BRASS, BRASS_D, COPPER, STEEL = "brass", "brass_dark", "copper", "steel"
GLOW, BLACK, WHITE = "glow_amber", "black", "white"
get_mat(IRON, hex="#4a4e58", metallic=0.6, roughness=0.42)
get_mat(DARK, hex="#2b2e35", metallic=0.6, roughness=0.5)
get_mat(GOLD, hex="#ffd35c", metallic=1.0, roughness=0.22)
for _m in (BRASS, BRASS_D, COPPER, STEEL, GLOW, BLACK, WHITE):
    get_mat(_m)

# ---- pivots (game tuning depends on them) -------------------------------------------------------------
HIP_Z = 1.30
LEG = (0.36, 0.0, -0.18)          # hip joint relative to hips
WAIST = 0.12                      # torso pivot above hips
SHOULDER = (1.02, 0.0, 1.15)      # relative to torso
ELBOW = -0.95                     # arm-local
KNEE = -0.55                      # leg-local
HEAD = (0.0, -0.30, 1.38)         # relative to torso (low and forward: hunched)
FRONT, BACK, LEFT, RIGHT = D(270), D(90), 0.0, D(180)

root = empty("root")


def layers(lp):
    """base: chamfered plates/blocks, mid: small chamfer, round: wide chamfer (reads rounded),
    raw: pre-profiled pieces (no bevel), riv: fully smooth (rivets)."""
    return (lp.L("base", bevel=BEVEL_BIG), lp.L("mid", bevel=BEVEL_MID), lp.L("round", bevel=BEVEL_ROUND),
            lp.L("raw"), lp.L("riv", angle=180.0))


def soft(lp):
    """Smooth-ish layer for rounded capsules (only very hard creases stay sharp)."""
    return lp.L("soft", angle=75.0)


def rolled(r=0.022, lift=0.02):
    return round_profile(r, 6, lift=lift)


# =====================================================================================================
# HIPS
# =====================================================================================================
HS = Surf([(-0.34, 0.80, 0.58, 0, 0.0), (-0.22, 0.92, 0.66), (-0.04, 1.00, 0.72), (0.10, 1.00, 0.72),
           (0.17, 0.94, 0.68)], n=2.7)
lp = LPart("hips")
base, mid, rnd, raw, riv = layers(lp)
surf_shell(raw, IRON, HS, linspace(-0.34, 0.17, 5), nth=32, cap=(True, False))
surf_band(raw, BRASS, HS, 0.065, 0.12, 0.04, nth=32)                                         # belt
surf_rivets(riv, BRASS_D, HS, [(D(a), 0.065) for a in range(10, 360, 50) if abs(a - 270) > 35], off=0.04,
            r=0.022, h=0.016)
# coin-box buckle — greedy: a gold coin stuck in the slot on top, coin emblem on the lid
mid.box(BRASS, size=(0.36, 0.10, 0.23), loc=(0, -0.44, 0.065))
mid.box(BRASS_D, size=(0.29, 0.03, 0.17), loc=(0, -0.49, 0.065))
raw.box(BLACK, size=(0.20, 0.03, 0.012), loc=(0, -0.44, 0.181))
raw.cyl(GOLD, r=0.078, h=0.018, seg=20, loc=(0, -0.44, 0.212), rot=(90, 0, 0))
raw.cyl(GOLD, r=0.056, h=0.012, seg=16, loc=(0, -0.507, 0.065), rot=(90, 0, 0))
for x in (-0.12, 0.12):
    for z in (-0.005, 0.135):
        rivet(riv, BRASS_D, (x, -0.495, z), (0, -1, 0), r=0.015, h=0.011)
# hip sockets (dark iron cups over the leg balls)
for s in (1, -1):
    c = (s * LEG[0], LEG[1], LEG[2] + 0.02)
    lathe_axis(raw, DARK, c, (0, 0, 1), [(0.0, -0.03), (0.25, -0.03), (0.255, 0.06), (0.21, 0.19),
                                         (0.0, 0.28)], seg=14)
# front / back faulds (narrow: they hang between the thighs)
for y, tilt in ((-0.36, -8), (0.34, 8)):
    sgn = -1 if y < 0 else 1
    base.box(IRON, size=(0.30, 0.05, 0.36), loc=(0, y, -0.36), rot=(tilt, 0, 0))
    raw.box(BRASS, size=(0.32, 0.065, 0.045), loc=(0, y + sgn * 0.025, -0.535), rot=(tilt, 0, 0))
    for x in (-0.09, 0.09):
        rivet(riv, BRASS_D, (x, y + sgn * 0.03, -0.25), (0, sgn, 0), r=0.016, h=0.012)
hips = lp.build(root, loc=(0, 0, HIP_Z))


# =====================================================================================================
# LEGS: thigh (leg_X, pivot at the hip ball) + shin/foot (shin_X, pivot at the knee knuckle)
# =====================================================================================================
def build_leg(s):
    side = "L" if s > 0 else "R"
    # ---- thigh ----
    lp = LPart("leg_" + side)
    base, mid, rnd, raw, riv = layers(lp)
    raw.sphere(DARK, r=0.215, seg=10, rings=5)                                         # hip ball
    TH = Surf([(-0.47, 0.34, 0.36), (-0.36, 0.44, 0.46), (-0.20, 0.47, 0.49), (-0.06, 0.40, 0.42)], n=2.5)
    surf_shell(raw, IRON, TH, linspace(-0.47, -0.06, 4), nth=24, cap=(True, False))
    surf_plate(base, IRON, TH, D(205), D(385), -0.42, -0.13, off0=-0.01, off1=0.035, nth=12, nz=3,
               inner=False)                                                             # cuisse
    surf_trim(raw, BRASS, TH, [(D(a), -0.415) for a in linspace(205, 385, 9)], rolled(0.022, 0.03))
    surf_rivets(riv, BRASS, TH, [(D(a), -0.18) for a in (255, 325)], off=0.035)
    # tasset: plate hanging over the hip ball on the outer side (moves with the thigh)
    arc_plate(base, IRON, (0, 0, 0), (0, 0, 1), (1, 0, 0), 0.25, 0.29, -75, 75, -0.26, 0.05, seg=10)
    arc_plate(raw, BRASS, (0, 0, 0), (0, 0, 1), (1, 0, 0), 0.245, 0.30, -77, 77, -0.29, -0.245, seg=10)
    arc_rivets(riv, BRASS, (0, 0, 0), (0, 0, 1), (1, 0, 0), 0.29, (-45, 0, 45), -0.04, radial=True)
    # knee knuckle + poleyn (front) on the thigh
    raw.cyl(DARK, r=0.15, h=0.25, seg=16, loc=(0, 0, KNEE), rot=(0, 90, 0))
    arc_plate(base, IRON, (0, 0, KNEE), (1, 0, 0), (0, 1, 0), 0.19, 0.235, 112, 245, -0.20, 0.20, seg=10)
    lathe_axis(raw, BRASS, (0, -0.232, KNEE), (0, -1, 0), [(0.07, 0.0), (0.06, 0.03), (0.035, 0.055),
                                                         (0.0, 0.07)], seg=12)
    if s < 0:
        lp.mirror_x()
    leg = lp.build(hips, loc=(s * LEG[0], LEG[1], LEG[2]))

    # ---- shin + foot (pivot at the knee) ----
    lp = LPart("shin_" + side)
    base, mid, rnd, raw, riv = layers(lp)
    for x in (-0.175, 0.175):                                                          # yoke cheeks
        base.cyl(IRON, r=0.185, h=0.07, seg=20, loc=(x, 0, 0), rot=(0, 90, 0))
        raw.cyl(BRASS, r=0.07, h=0.03, seg=12, loc=(x * 1.27, 0, 0), rot=(0, 90, 0))
        bolt(raw, BRASS_D, (x * 1.36, 0, 0), (math.copysign(1, x), 0, 0), r=0.035, h=0.02)
    SH = Surf([(-0.41, 0.50, 0.52, 0, -0.01), (-0.30, 0.48, 0.50, 0, -0.01), (-0.17, 0.43, 0.44),
               (-0.07, 0.36, 0.34)], n=2.5)
    surf_shell(raw, IRON, SH, linspace(-0.41, -0.07, 4), nth=28, cap=(False, False))
    surf_plate(base, IRON, SH, D(232), D(308), -0.34, -0.10, off0=-0.01, off1=0.03, nth=8, nz=4,
               inner=False)                                                             # greave plate
    surf_rivets(riv, BRASS, SH, [(D(240), -0.14), (D(300), -0.14), (D(240), -0.30), (D(300), -0.30)],
                off=0.03)
    surf_band(raw, BRASS, SH, -0.385, 0.055, 0.035, nth=16)                              # ankle ring
    raw.cyl(COPPER, r=0.055, h=0.24, seg=10, loc=(0, 0.27, -0.24))                     # calf piston
    raw.cyl(STEEL, r=0.024, h=0.26, seg=8, loc=(0, 0.27, -0.02))
    mid.box(DARK, size=(0.12, 0.08, 0.06), loc=(0, 0.25, -0.37))
    # foot: big rounded sabaton, three stubby brass-capped toes, heel spur
    FT = Surf([(-0.53, 0.70, 0.82, 0, -0.10), (-0.47, 0.68, 0.78, 0, -0.10), (-0.41, 0.58, 0.62, 0, -0.06),
               (-0.36, 0.46, 0.46, 0, -0.02)], n=3.0)
    surf_shell(raw, IRON, FT, linspace(-0.53, -0.36, 3), nth=28, cap=(False, False))
    base.box(DARK, size=(0.74, 0.88, 0.07), loc=(0, -0.10, -0.535))                    # sole
    for i, x in enumerate((-0.22, 0.0, 0.22)):
        rz = (-6, 0, 6)[i]
        base.box(IRON, size=(0.21, 0.14, 0.15), loc=(x, -0.53, -0.495), rot=(0, 0, rz))
        rnd.box(BRASS, size=(0.215, 0.075, 0.13), loc=(x * 1.02, -0.60, -0.50), rot=(0, 0, rz))
    base.box(DARK, size=(0.36, 0.16, 0.13), loc=(0, 0.33, -0.50))                      # heel
    surf_rivets(riv, BRASS, FT, [(D(a), -0.45) for a in (215, 325)], off=0.0)
    if s < 0:
        lp.mirror_x()
    lp.build(leg, loc=(0, 0, KNEE))
    return leg


leg_L = build_leg(1)
leg_R = build_leg(-1)


# =====================================================================================================
# TORSO — riveted boiler, hunched forward (centre line leans toward -Y at the top)
# =====================================================================================================
TS = Surf([(-0.06, 0.90, 0.70, 0, 0.04), (0.10, 1.04, 0.78, 0, 0.03), (0.30, 1.28, 0.90, 0, 0.0),
           (0.55, 1.46, 1.02, 0, -0.04), (0.80, 1.56, 1.10, 0, -0.07), (1.00, 1.60, 1.10, 0, -0.09),
           (1.18, 1.60, 1.04, 0, -0.10), (1.31, 1.48, 0.94, 0, -0.11, 2.8), (1.41, 1.26, 0.80, 0, -0.12, 2.9),
           (1.48, 0.98, 0.62, 0, -0.12, 2.9)], n=2.6)
lp = LPart("torso")
base, mid, rnd, raw, riv = layers(lp)
surf_shell(raw, IRON, TS, [-0.06, 0.12, 0.28, 0.44, 0.60, 0.75, 0.90, 1.04, 1.16, 1.26, 1.32, 1.38, 1.43, 1.48],
           nth=40, cap=(False, True))

# plate courses: raised front (furnace) + back plates between the bands, raised upper yoke ring
for c, half in ((FRONT, D(56)), (BACK, D(50))):
    surf_plate(base, IRON, TS, c - half, c + half, 0.42, 1.12, off0=-0.01, off1=0.025, nth=16, nz=7,
               inner=False)
    surf_rivets(riv, BRASS_D, TS, col(c - half + D(4), 0.54, 1.00, 3) + col(c + half - D(4), 0.54, 1.00, 3),
                off=0.025)
surf_plate(base, IRON, TS, 0.0, TAU, 1.25, 1.37, off0=-0.01, off1=0.022, nth=40, nz=2, inner=False)
surf_rivets(riv, BRASS_D, TS, row(D(18), 0, 1.29, 10, closed=True), off=0.022)
# brass bands (belly / chest) with rivets
for z, h in ((0.34, 0.10), (1.185, 0.09)):                       # (front sector hidden by the door)
    surf_band(raw, BRASS, TS, z, h, 0.04, nth=24, th0=FRONT + D(24), th1=FRONT + D(336))
    surf_rivets(riv, BRASS_D, TS, [(D(a), z) for a in range(15, 360, 30) if abs(a - 270) > 30], off=0.04,
                r=0.024, h=0.017)
# vertical weld bead on the back
surf_trim(raw, DARK, TS, [(BACK, z) for z in linspace(0.44, 1.10, 12)], round_profile(0.016, 5, lift=0.025))

# side vents (glowing louvres, between arm and body)
for th in (LEFT, RIGHT):
    P, N = TS.pt(th, 0.70), TS.nrm(th, 0.70)
    loc, rot = fplace(P, N)
    mid.box(DARK, size=(0.40, 0.30, 0.07), loc=loc, rot=rot)
    loc, rot = fplace(P, N, lloc=(0, 0, 0.03))
    raw.box(GLOW, size=(0.32, 0.22, 0.02), loc=loc, rot=rot)

# shoulder sockets (brass flanges the arm drums turn in)
for s in (1, -1):
    c = (s * 0.80, 0.0, SHOULDER[2])
    ax = (s, 0, 0)
    lathe_axis(raw, BRASS_D, c, ax, [(0.25, -0.10), (0.36, -0.10), (0.37, -0.01), (0.27, 0.045)],
               seg=20, ref=(0, 1, 0), closed=True)

# neck seat + raised back collar (the tiny head sits low between the shoulders)
raw.cyl(DARK, r=0.25, h=0.12, seg=16, loc=(HEAD[0], HEAD[1] + 0.04, HEAD[2] + 0.0))
arc_plate(base, IRON, (0, -0.24, 1.32), (0, 0, 1), (1, 0, 0), 0.27, 0.33, -25, 205, 0.0, 0.25, seg=20)
arc_plate(raw, BRASS, (0, -0.24, 1.32), (0, 0, 1), (1, 0, 0), 0.265, 0.345, -27, 207, 0.23, 0.28, seg=20)

# chest gauges (left) and steam valve wheel (right)
GAUGE_TH = FRONT + D(40)
P, N = TS.pt(GAUGE_TH, 1.02, 0.025), TS.nrm(GAUGE_TH, 1.02)
loc, rot = fplace(P, N, lloc=(0, 0, 0.03))
raw.cyl(BRASS, r=0.095, h=0.06, seg=18, loc=loc, rot=rot)
loc, rot = fplace(P, N, lloc=(0, 0, 0.061))
raw.cyl(WHITE, r=0.075, h=0.004, seg=18, loc=loc, rot=rot)
loc, rot = fplace(P, N, lloc=(0.02, 0.02, 0.066), lrot=(0, 0, -45))
raw.box(BLACK, size=(0.075, 0.010, 0.004), loc=loc, rot=rot)
P2, N2 = TS.pt(GAUGE_TH + D(10), 0.86, 0.025), TS.nrm(GAUGE_TH + D(10), 0.86)
loc, rot = fplace(P2, N2, lloc=(0, 0, 0.025))
raw.cyl(BRASS, r=0.06, h=0.05, seg=14, loc=loc, rot=rot)
loc, rot = fplace(P2, N2, lloc=(0, 0, 0.051))
raw.cyl(WHITE, r=0.046, h=0.004, seg=14, loc=loc, rot=rot)
loc, rot = fplace(P2, N2, lloc=(-0.012, 0.012, 0.055), lrot=(0, 0, 45))
raw.box(BLACK, size=(0.045, 0.008, 0.004), loc=loc, rot=rot)
VALVE_TH = FRONT - D(40)
P, N = TS.pt(VALVE_TH, 1.00, 0.025), TS.nrm(VALVE_TH, 1.00)
loc, rot = fplace(P, N, lloc=(0, 0, 0.04))
raw.cyl(COPPER, r=0.03, h=0.08, seg=10, loc=loc, rot=rot)
loc, rot = fplace(P, N, lloc=(0, 0, 0.09))
raw.torus(BRASS, R=0.085, r=0.016, seg=14, seg2=4, loc=loc, rot=rot)
for a in (0, 60, 120):
    loc, rot = fplace(P, N, lloc=(0, 0, 0.09), lrot=(0, 0, a))
    raw.box(BRASS, size=(0.17, 0.018, 0.016), loc=loc, rot=rot)

# back: horizontal boiler tank with straps, pipes, valve
TANK_C = Vector((-0.16, 0.64, 0.66))
raw.cyl(COPPER, r=0.26, h=0.80, seg=20, loc=TANK_C, rot=(0, 90, 0))
for sx in (1, -1):
    lathe_axis(raw, BRASS_D, TANK_C, (sx, 0, 0), [(0.27, 0.37), (0.27, 0.42), (0.245, 0.47), (0.17, 0.515),
                                                (0.0, 0.535)], seg=16)
    arc_rivets(riv, BRASS, TANK_C, (sx, 0, 0), (0, 1, 0), 0.265, range(-30, 200, 46), 0.34, radial=True)
for h in (-0.20, 0.20):
    arc_plate(raw, DARK, TANK_C, (1, 0, 0), (0, 1, 0), 0.258, 0.29, -110, 140, h - 0.035, h + 0.035, seg=10)
lathe_axis(raw, BRASS, TANK_C + Vector((0.08, 0, 0.25)), (0, 0, 1), [(0.04, 0.0), (0.04, 0.10), (0.06, 0.12),
                                                                    (0.06, 0.15), (0.0, 0.16)], seg=10)
# copper steam pipes: tank -> shoulder sockets (they end in the socket flanges)
for s in (1, -1):
    x0 = TANK_C.x + s * 0.30
    pts = [(x0, 0.64, 0.66 + 0.24), (x0 + s * 0.02, 0.62, 1.02), (s * 0.55, 0.50, 1.24), (s * 0.72, 0.30, 1.33),
           (s * 0.80, 0.16, 1.33)]
    tube(raw, COPPER, pts, r=0.045, seg=8)
    raw.cyl(BRASS, r=0.058, h=0.05, seg=10, loc=pts[1], rot=orient(Vector(pts[2]) - Vector(pts[0])))
# safety-valve exhaust on the right upper back (balances the chimney on the left)
SV_Z = 1.27
SV_TH = theta_at_x(TS, SV_Z, -0.24, D(91), D(175))
P, N = TS.pt(SV_TH, SV_Z, 0.0), TS.nrm(SV_TH, SV_Z)
q0 = P - N * 0.03
q1 = P + N * 0.10
q2 = q1 + Vector((0, 0.04, 0.16))
q3 = q2 + Vector((-0.02, 0.0, 0.10))
tube(raw, COPPER, [q0, q1, q2, q3], r=0.05, seg=10)
loc, rot = fplace(P, N, lloc=(0, 0, 0.0))
raw.cyl(BRASS, r=0.085, h=0.04, seg=12, loc=loc, rot=rot)
lathe_axis(raw, BRASS, q3, (0, 0, 1), [(0.05, -0.02), (0.07, 0.0), (0.075, 0.05), (0.045, 0.07), (0.0, 0.08)],
           seg=10)                                                                          # whistle cap
torso = lp.build(hips, loc=(0, 0, WAIST))


# =====================================================================================================
# CORE — furnace door (front of chest), own bone. Local -Y = outward.
# =====================================================================================================
CORE_Z = 0.78
CORE_P = TS.pt(FRONT, CORE_Z, 0.025)
lp = LPart("core")
base, mid, rnd, raw, riv = layers(lp)
OUT = (0, -1, 0)
lathe_axis(raw, IRON, (0, 0, 0), OUT, [(0.34, -0.14), (0.50, -0.16), (0.515, -0.01), (0.50, 0.035),
                                       (0.34, 0.035)], seg=24, closed=True)                    # flange
arc_bolts(raw, BRASS_D, (0, 0, 0), OUT, (1, 0, 0), 0.468, range(22, 382, 45), 0.03, nrm=Vector(OUT),
          r=0.022, h=0.018)
lathe_axis(raw, BRASS, (0, 0, 0), OUT, [(0.315, 0.0), (0.42, 0.0), (0.44, 0.05), (0.415, 0.10),
                                        (0.365, 0.12), (0.33, 0.10), (0.318, 0.06)],
           seg=36, closed=True)                                                                 # bezel
lathe_axis(raw, BLACK, (0, 0, 0), OUT, [(0.325, 0.075), (0.315, 0.0)], seg=32)   # throat
lathe_axis(raw, GLOW, (0, 0, 0), OUT, [(0.318, 0.002), (0.20, -0.004), (0.0, -0.012)], seg=32)  # fire
for x in (-0.22, -0.11, 0.0, 0.11, 0.22):                                                     # grille
    h = math.sqrt(0.322 ** 2 - x ** 2)
    raw.cyl(DARK, r=0.022, h=2 * h, seg=6, loc=(x, -0.035, 0))
raw.box(DARK, size=(0.66, 0.03, 0.06), loc=(0, -0.062, 0))
raw.cyl(BRASS, r=0.085, h=0.05, seg=16, loc=(0, -0.085, 0), rot=(90, 0, 0))
bolt(raw, BRASS_D, (0, -0.11, 0), (0, -1, 0), r=0.035, h=0.025)
for z in (-0.17, 0.17):                                                                        # hinge
    raw.cyl(BRASS, r=0.042, h=0.11, seg=10, loc=(-0.455, -0.08, z))
    mid.box(BRASS_D, size=(0.12, 0.03, 0.08), loc=(-0.40, -0.10, z))
raw.cyl(STEEL, r=0.015, h=0.48, seg=8, loc=(-0.455, -0.08, 0))
mid.box(BRASS_D, size=(0.10, 0.06, 0.14), loc=(0.44, -0.10, 0))                                # latch
raw.cyl(STEEL, r=0.02, h=0.20, seg=8, loc=(0.47, -0.15, -0.05))
raw.sphere(BRASS, r=0.035, seg=10, rings=5, loc=(0.47, -0.15, -0.16))
core = lp.build(torso, loc=tuple(CORE_P))


# =====================================================================================================
# HEAD — tiny domed helmet, narrow visor slit with angry glowing eyes
# =====================================================================================================
lp = LPart("head")
base, mid, rnd, raw, riv = layers(lp)
raw.cyl(DARK, r=0.13, h=0.18, seg=12, loc=(0, 0, -0.03))                                     # neck
HL = Surf([(0.0, 0.32, 0.30), (0.06, 0.40, 0.38), (0.14, 0.42, 0.40)], n=2.3)
surf_shell(raw, IRON, HL, linspace(0.0, 0.14, 3), nth=24)
HV = Surf([(0.12, 0.37, 0.35), (0.24, 0.37, 0.35)], n=2.3)
surf_shell(raw, BLACK, HV, [0.12, 0.24], nth=20, cap=(False, False))
HU = Surf([(0.215, 0.43, 0.41), (0.27, 0.42, 0.40), (0.32, 0.37, 0.35), (0.37, 0.27, 0.25), (0.40, 0.14, 0.13),
           (0.415, 0.0, 0.0)], n=2.3)
surf_shell(raw, IRON, HU, linspace(0.215, 0.415, 5), nth=24)
HB = Surf([(0.12, 0.42, 0.40), (0.23, 0.42, 0.40)], n=2.3)
surf_plate(base, IRON, HB, D(10), D(170), 0.13, 0.225, off0=-0.03, off1=0.0, nth=10, nz=1)  # back of slit
for sx in (1, -1):
    raw.sphere(GLOW, r=0.05, seg=8, rings=5, loc=(sx * 0.08, -0.172, 0.177), scale=(1.45, 0.55, 0.42),
               rot=(0, -sx * 14, 0))                                                         # eyes
    raw.cyl(BRASS, r=0.05, h=0.04, seg=12, loc=(sx * 0.215, 0, 0.175), rot=(0, 90, 0))       # ear bolts
    bolt(raw, BRASS_D, (sx * 0.235, 0, 0.175), (sx, 0, 0), r=0.025, h=0.018)
surf_plate(base, BRASS, HU, FRONT - D(72), FRONT + D(72), lambda th: 0.185 + 0.085 * abs(th - FRONT) / D(72),
           lambda th: 0.255 + 0.085 * abs(th - FRONT) / D(72), off0=-0.005, off1=0.03, nth=12,
           nz=1)                                                                            # visor hood
tube(raw, BRASS, [HU.pt(FRONT, z, 0.004) for z in (0.31, 0.37, 0.405)] +
     [HU.pt(BACK, z, 0.004) for z in (0.405, 0.37, 0.31, 0.24)], r=0.022, seg=6, flat=0.6, up=(1, 0, 0))
surf_rivets(riv, BRASS, HL, row(D(30), 0, 0.075, 6, closed=True), off=0.0, r=0.014, h=0.01)
for x in (-0.045, 0.0, 0.045):                                                               # mouth grille
    raw.box(DARK, size=(0.022, 0.03, 0.07), loc=(x, -0.19, 0.06))
lathe_axis(raw, BRASS_D, (0, 0.08, 0.385), (0, 0, 1), [(0.025, 0.0), (0.025, 0.08), (0.04, 0.10),
                                                      (0.045, 0.13), (0.0, 0.14)], seg=10)  # whistle
head = lp.build(torso, loc=HEAD)


# =====================================================================================================
# CHIMNEY — on the back (+Y), own bone; steam_point marker at the top
# =====================================================================================================
CH_Z = 1.06
CH_TH = theta_at_x(TS, CH_Z, 0.36, D(5), D(89))
CH_P = TS.pt(CH_TH, CH_Z, 0.0)
lp = LPart("chimney")
base, mid, rnd, raw, riv = layers(lp)
STACK_Y = 0.36
lathe_axis(raw, BRASS, (0, 0, 0), (0, 1, 0), [(0.0, -0.06), (0.23, -0.06), (0.24, 0.0), (0.22, 0.04),
                                             (0.0, 0.04)], seg=20)
arc_bolts(raw, BRASS_D, (0, 0, 0), (0, 1, 0), (1, 0, 0), 0.19, range(45, 405, 90), 0.04, r=0.02, h=0.016)
pts = [(0, 0.0, 0.0), (0, 0.13, 0.0)]
for k in range(1, 7):
    a = D(-90 + 90 * k / 6)
    pts.append((0, 0.13 + 0.23 * math.cos(a), 0.23 + 0.23 * math.sin(a)))
pts += [(0, STACK_Y, z) for z in (0.60, 1.12)]
tube(raw, IRON, pts, r=0.15, seg=18)
for z in (0.42, 1.075):                                   # (upper ring hides the crown joint)
    lathe_axis(raw, BRASS, (0, STACK_Y, z), (0, 0, 1), [(0.14, -0.04), (0.18, -0.04), (0.188, 0.0),
                                                       (0.18, 0.04), (0.14, 0.04)],
               seg=20, closed=True)
    arc_rivets(riv, BRASS_D, (0, STACK_Y, z), (0, 0, 1), (1, 0, 0), 0.185, range(0, 360, 90 if z < 0.5 else 180),
               0.0, radial=True, r=0.018, h=0.012)
lathe_axis(raw, IRON, (0, STACK_Y, 0), (0, 0, 1), [(0.145, 1.06), (0.16, 1.13), (0.21, 1.21), (0.245, 1.28),
                                                  (0.25, 1.32), (0.225, 1.33), (0.19, 1.28), (0.16, 1.22),
                                                  (0.14, 1.12)], seg=20, closed=True)
lathe_axis(raw, BRASS, (0, STACK_Y, 0), (0, 0, 1), [(0.23, 1.305), (0.265, 1.305), (0.272, 1.33),
                                                   (0.255, 1.35), (0.225, 1.345)], seg=20, closed=True)
lathe_axis(raw, BLACK, (0, STACK_Y, 0), (0, 0, 1), [(0.165, 1.23), (0.0, 1.23)], seg=16)
mid.box(DARK, size=(0.10, 0.30, 0.06), loc=(0, STACK_Y - 0.17, 0.30))                         # bracket
chimney = lp.build(torso, loc=tuple(CH_P))
empty("steam_point", parent=chimney, loc=(0, STACK_Y, 1.36))


# =====================================================================================================
# ARMS: upper arm (arm_X, pivot at the shoulder drum) + forearm/fist (forearm_X, pivot at the elbow)
# Modelled for the LEFT side (+X) and mirrored for the right.
# =====================================================================================================
def build_arm(s):
    side = "L" if s > 0 else "R"
    # ---- upper arm ----
    lp = LPart("arm_" + side)
    base, mid, rnd, raw, riv = layers(lp)
    raw.cyl(DARK, r=0.24, h=0.48, seg=20, loc=(-0.05, 0, 0), rot=(0, 90, 0))                  # drum
    # pauldron: armoured shell over the drum (loft along +X: surf x -> -Z, surf y -> +Y)
    PA = Surf([(-0.18, 0.72, 0.92, -0.10, 0.0), (0.08, 0.80, 0.98, -0.11, 0.0), (0.28, 0.74, 0.92, -0.10, 0.0),
               (0.40, 0.56, 0.72, -0.08, 0.0), (0.46, 0.30, 0.40, -0.06, 0.0)],
              n=2.9, M=Matrix.Rotation(D(90), 4, "Y"))
    # layered: two side plates + a raised top plate overlapping them (step edges + rivet rows)
    for t0, t1 in ((58, 137), (223, 302)):
        surf_plate(base, BRASS_D, PA, D(t0), D(t1), -0.18, 0.46, off0=0.0, off1=0.05, nth=5, nz=5)
    surf_plate(base, BRASS_D, PA, D(128), D(232), -0.15, 0.45, off0=0.025, off1=0.08, nth=8, nz=4)
    for th in (D(58), D(302)):
        surf_trim(raw, BRASS, PA, [(th, z) for z in linspace(-0.18, 0.44, 6)], rolled(0.03, 0.025))
    surf_trim(raw, BRASS, PA, [(D(a), -0.18) for a in linspace(58, 302, 14)], rolled(0.03, 0.025))
    surf_trim(raw, BRASS, PA, [(D(180), z) for z in linspace(-0.13, 0.40, 6)], rolled(0.035, 0.09))  # ridge
    surf_rivets(riv, BRASS, PA, [(D(a), -0.10) for a in (80, 105, 255, 280)], off=0.05)
    surf_rivets(riv, BRASS, PA, [(D(a), z) for a in (135, 225) for z in (-0.06, 0.14, 0.32)], off=0.08)
    sgear(raw, BRASS, r=0.21, teeth=10, thick=0.05, loc=(0.48, 0, 0.08), rot=(0, 90, 0))
    raw.cyl(BRASS_D, r=0.10, h=0.05, seg=16, loc=(0.515, 0, 0.08), rot=(0, 90, 0))
    bolt(raw, BRASS, (0.54, 0, 0.08), (1, 0, 0), r=0.05, h=0.03)
    # lames below the pauldron on the outer side (shingled)
    for z0, r0, trim in ((-0.20, 0.30, True), (-0.30, 0.27, False)):
        arc_plate(raw, IRON, (0.04, 0, 0), (0, 0, 1), (1, 0, 0), r0, r0 + 0.035, -85, 85, z0 - 0.11, z0, seg=12)
        if trim:
            arc_plate(raw, BRASS, (0.04, 0, 0), (0, 0, 1), (1, 0, 0), r0 - 0.005, r0 + 0.045, -87, 87,
                      z0 - 0.125, z0 - 0.095, seg=10)
    # upper arm sleeve + piston
    UA = Surf([(-0.84, 0.30, 0.30), (-0.72, 0.36, 0.36), (-0.46, 0.37, 0.37), (-0.24, 0.32, 0.32)], n=2.2)
    surf_shell(raw, IRON, UA, linspace(-0.84, -0.24, 4), nth=20, cap=(False, False))
    raw.cyl(COPPER, r=0.05, h=0.30, seg=10, loc=(0, -0.235, -0.44))
    raw.cyl(STEEL, r=0.022, h=0.22, seg=8, loc=(0, -0.235, -0.68))
    mid.box(DARK, size=(0.09, 0.07, 0.05), loc=(0, -0.20, -0.29))
    mid.box(DARK, size=(0.09, 0.07, 0.05), loc=(0, -0.21, -0.79))
    # elbow knuckle + couter (back of the elbow)
    raw.cyl(DARK, r=0.17, h=0.26, seg=16, loc=(0, 0, ELBOW), rot=(0, 90, 0))
    arc_plate(base, IRON, (0, 0, ELBOW), (1, 0, 0), (0, 1, 0), 0.20, 0.245, -70, 62, -0.15, 0.15, seg=10)
    lathe_axis(raw, BRASS, (0, 0.242, ELBOW), (0, 1, 0), [(0.06, 0.0), (0.05, 0.03), (0.0, 0.08)], seg=12)
    if s < 0:
        lp.mirror_x()
    arm = lp.build(torso, loc=(s * SHOULDER[0], SHOULDER[1], SHOULDER[2]))

    # ---- forearm + fist (pivot at the elbow) ----
    lp = LPart("forearm_" + side)
    base, mid, rnd, raw, riv = layers(lp)
    for x in (-0.19, 0.19):                                                                   # yoke cheeks
        base.cyl(IRON, r=0.215, h=0.08, seg=20, loc=(x, 0, 0), rot=(0, 90, 0))
        raw.cyl(BRASS, r=0.08, h=0.03, seg=12, loc=(x * 1.26, 0, 0), rot=(0, 90, 0))
        bolt(raw, BRASS_D, (x * 1.34, 0, 0), (math.copysign(1, x), 0, 0), r=0.04, h=0.022)
    FS = Surf([(-0.60, 0.70, 0.66), (-0.50, 0.76, 0.72), (-0.36, 0.72, 0.68), (-0.22, 0.58, 0.54),
               (-0.10, 0.42, 0.38)], n=2.5)
    surf_shell(raw, IRON, FS, linspace(-0.60, -0.10, 5), nth=28, cap=(False, False))
    surf_plate(base, IRON, FS, D(-55), D(55), -0.47, -0.19, off0=-0.01, off1=0.03, nth=8, nz=4,
               inner=False)                                                                 # vambrace
    surf_rivets(riv, BRASS, FS, col(D(-50), -0.43, -0.23, 2) + col(D(50), -0.43, -0.23, 2), off=0.03)
    for z in (-0.26, -0.33, -0.40):                                                         # heat vents
        P, N = FS.pt(0.0, z, 0.03), FS.nrm(0.0, z)
        loc, rot = fplace(P, N)
        mid.box(DARK, size=(0.24, 0.05, 0.04), loc=loc, rot=rot)
        loc, rot = fplace(P, N, lloc=(0, 0, 0.012))
        raw.box(GLOW, size=(0.20, 0.025, 0.03), loc=loc, rot=rot)
    surf_band(raw, BRASS, FS, -0.555, 0.07, 0.04, nth=24)                                   # wrist cuff
    surf_rivets(riv, BRASS_D, FS, [(D(a), -0.555) for a in (-50, 0, 50, 245, 295)], off=0.04)
    surf_band(raw, BRASS, FS, -0.15, 0.05, 0.03, nth=20, ch=0.0)
    raw.cyl(COPPER, r=0.045, h=0.24, seg=10, loc=(0, -0.40, -0.33))                        # front piston
    raw.cyl(STEEL, r=0.02, h=0.12, seg=8, loc=(0, -0.40, -0.17))
    mid.box(DARK, size=(0.08, 0.06, 0.05), loc=(0, -0.375, -0.46))
    raw.cyl(DARK, r=0.30, h=0.06, seg=20, loc=(0, 0.02, -0.61))                            # wrist ring
    # fist (palm forward): rounded hand mass, curled capsule fingers facing the front with the thumb
    # wrapped across them, armoured back of the hand, brass knuckle caps on the bottom-back edge
    sf = soft(lp)
    HAND = Surf([(-1.00, 0.72, 0.44, 0, 0.07), (-0.92, 0.80, 0.50, 0, 0.06), (-0.72, 0.78, 0.50, 0, 0.05),
                 (-0.60, 0.62, 0.44, 0, 0.05)], n=3.2)
    surf_shell(raw, IRON, HAND, linspace(-1.00, -0.60, 3), nth=20, cap=(False, False))
    surf_plate(base, IRON, HAND, BACK - D(62), BACK + D(62), -0.94, -0.65, off0=-0.01, off1=0.03, nth=8,
               nz=3, inner=False)                                                           # back plate
    surf_rivets(riv, BRASS, HAND, [(BACK + D(a), z) for a in (-45, 45) for z in (-0.70, -0.89)], off=0.03,
                r=0.022, h=0.015)
    for i, x in enumerate((-0.285, -0.095, 0.095, 0.285)):                                  # fingers
        k = (1.0, 1.0, 0.95, 0.86)[i]
        rnd.box(BRASS, size=(0.18, 0.18, 0.16), loc=(x, 0.15, -1.03))                       # knuckle cap
        capsule(sf, IRON, (x, 0.10, -1.115), (x, -0.17, -1.115), 0.172, 0.19, up=(0, 0, 1), seg=8)  # proximal
        capsule(sf, IRON, (x, -0.235, -1.07), (x, -0.235, -1.07 + 0.25 * k), 0.172, 0.17,
                up=(0, 1, 0), seg=8)                                                               # middle
        raw.box(BRASS_D, size=(0.12, 0.02, 0.055), loc=(x, -0.328, -0.86 - 0.25 * (1 - k)))  # nail plate
    capsule(sf, IRON, (-0.37, 0.04, -0.70), (-0.38, -0.22, -0.89), 0.18, 0.20, up=(1, 0, 0))   # thumb
    rnd.box(BRASS, size=(0.17, 0.17, 0.16), loc=(-0.37, -0.29, -0.935))
    capsule(sf, IRON, (-0.30, -0.37, -0.945), (-0.05, -0.38, -0.95), 0.16, 0.16, up=(0, 0, 1))
    raw.box(BRASS_D, size=(0.06, 0.02, 0.10), loc=(-0.04, -0.462, -0.95))
    if s < 0:
        lp.mirror_x()
    lp.build(arm, loc=(0, 0, ELBOW))
    return arm


arm_L = build_arm(1)
arm_R = build_arm(-1)

print(f"[golem] parts built: {hp.scene_tris()} tris")
if "parts" in ARGS:
    sys.exit(0)


# =====================================================================================================
# RIG, AO, EXPORT, PREVIEWS
# =====================================================================================================
def smooth01(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


bpy.context.view_layer.update()
CORE_W = core.matrix_world.translation.copy()
STEAM_W = bpy.data.objects["steam_point"].matrix_world.translation.copy()
HEAD_W = head.matrix_world.translation.copy()
print(f"[golem] core {tuple(round(c, 3) for c in CORE_W)}  steam {tuple(round(c, 3) for c in STEAM_W)}")

rig = rig_from_parts(root, rigid={"steam_point"}, smooth={}, influence={}, skin_name="golem_skin")


def tint(p, n):
    r = g = b = 1.0
    # heat-darkened (tempered) metal around the furnace door
    d = (p - CORE_W).length
    k = smooth01(0.75, 0.42, d) * (1.0 if p.y < CORE_W.y + 0.2 else 0.0)
    r *= 1 - 0.40 * k
    g *= 1 - 0.55 * k
    b *= 1 - 0.65 * k
    # soot at the chimney top
    dxy = math.hypot(p.x - STEAM_W.x, p.y - STEAM_W.y)
    k2 = smooth01(STEAM_W.z - 0.45, STEAM_W.z - 0.02, p.z) * (1.0 if dxy < 0.4 else 0.0)
    r *= 1 - 0.72 * k2
    g *= 1 - 0.76 * k2
    b *= 1 - 0.80 * k2
    # grime toward the ground
    k3 = smooth01(0.45, 0.0, p.z)
    f = 1 - 0.22 * k3
    return (r * f, g * f * 0.98, b * f * 0.95)


hp.bake_vertex_ao(samples=24 if FAST else 48, distance=0.5, strength=0.8, floor=0.32, ground=0.0, tint=tint)
hp.export_glb_hp("golem")

hp.render_views("golem", views=[("", 35, 18), ("_front", 0, 8), ("_side", 90, 8), ("_back", 200, 20)])
hp.render_hp("golem_core", target=(CORE_W + Vector((0, 0, 0.1)), 0.75), azimuth=22, elevation=12)
hp.render_hp("golem_game", azimuth=28, elevation=25, dist_k=7.0)
if not FAST:
    hp.render_hp("golem_head", target=(HEAD_W + Vector((0, 0, 0.15)), 0.5), azimuth=25, elevation=8)
    hp.render_hp("golem_fist", target=(Vector((1.02, -0.05, 0.75)), 0.65), azimuth=40, elevation=10)
    hp.render_hp("golem_low", azimuth=35, elevation=-4, dist_k=2.4)

    def posed(name, rotations, views):
        pose_world(rig, rotations)
        for suffix, az, el in views:
            hp.render_hp(name + suffix, azimuth=az, elevation=el)
        reset_pose(rig)

    posed("golem_pose", HUMANOID_TEST_POSE, [("", 35, 18), ("_back", 215, 15)])
    ATTACK = {                       # double-fist hammer wind-up
        "torso": [("X", -8)], "head": [("X", 8)],
        "arm_L": [("Y", -12), ("X", -155)], "forearm_L": [("X", -60)],
        "arm_R": [("Y", 12), ("X", -155)], "forearm_R": [("X", -60)],
        "leg_L": [("X", -35)], "shin_L": [("X", 45)], "leg_R": [("X", 15)], "shin_R": [("X", 15)],
    }
    posed("golem_attack", ATTACK, [("", 35, 12), ("_side", 90, 8)])
    PUNCH = {                        # furnace punch: right arm forward, elbow bent, crouch
        "torso": [("Z", 25), ("X", 10)],
        "arm_R": [("X", -95)], "forearm_R": [("X", -40)],
        "arm_L": [("X", 30), ("Y", -20)], "forearm_L": [("X", -70)],
        "leg_L": [("X", -40)], "shin_L": [("X", 60)], "leg_R": [("X", 25)], "shin_R": [("X", 40)],
    }
    posed("golem_punch", PUNCH, [("", 50, 12), ("_side", 90, 5)])
    CROUCH = {                       # game 'dodge' clip extremes: thighs -70, knees 100, torso forward
        "torso": [("X", 30)],
        "arm_L": [("X", -60)], "forearm_L": [("X", -60)],
        "arm_R": [("X", -60)], "forearm_R": [("X", -50)],
        "leg_L": [("X", -70)], "shin_L": [("X", 100)], "leg_R": [("X", -70)], "shin_R": [("X", 100)],
    }
    posed("golem_crouch", CROUCH, [("", 60, 10)])
CLOSE = [a.split("=", 1)[1] for a in ARGS if a.startswith("closeups=")]
if CLOSE:                            # extra inspection renders into a scratch dir (not shipped previews)
    d = CLOSE[0]
    hp.render_hp(os.path.join(d, "c_knee"), target=(Vector((0.36, -0.1, 0.7)), 0.45), azimuth=40, elevation=5)
    hp.render_hp(os.path.join(d, "c_elbow"), target=(Vector((1.02, 0.0, 1.55)), 0.45), azimuth=60, elevation=5)
    hp.render_hp(os.path.join(d, "c_shoulder"), target=(Vector((0.95, 0.0, 2.6)), 0.6), azimuth=50, elevation=-10)
    hp.render_hp(os.path.join(d, "c_chimney"), target=(Vector((0.36, 0.86, 3.5)), 0.45), azimuth=150, elevation=30)
    hp.render_hp(os.path.join(d, "c_hips"), target=(Vector((0.0, -0.3, 1.2)), 0.55), azimuth=20, elevation=5)
    hp.render_hp(os.path.join(d, "c_foot"), target=(Vector((-0.36, -0.2, 0.2)), 0.5), azimuth=-35, elevation=15)
    hp.render_hp(os.path.join(d, "c_backtop"), target=(Vector((0.0, 0.5, 2.6)), 0.7), azimuth=160, elevation=30)
    hp.render_hp(os.path.join(d, "c_top"), azimuth=10, elevation=70, dist_k=2.2)
    hp.render_hp(os.path.join(d, "c_game_mid"), azimuth=-25, elevation=25, dist_k=4.5)
    hp.render_hp(os.path.join(d, "c_game_far"), azimuth=150, elevation=28, dist_k=5.5)
print(f"[golem] done, {hp.scene_tris()} tris")
