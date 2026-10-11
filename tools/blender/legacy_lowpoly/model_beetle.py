"""Brass Beetle — armored medium enemy (~0.7 m tall, ~1.3 m long). Exports public/models/beetle.glb.

Skeleton (RIG_SPEC.md), armature object 'root':
  body (root bone) > head > {horn, antenna_L, antenna_R}
                   > shell_L, shell_R                      elytra, pivot at the hinge (rigid weights)
                   > leg_FL > leg_FL_2, leg_ML > leg_ML_2, leg_BL > leg_BL_2  (and _R)
  upper leg segment pivots at the body side, the lower `_2` segment at the knee ball joint.
Faces -Y. Elytra pivot at the hinge on the top-front of the back (rotate up/out to open).
All joints are mechanical ball joints / hinges -> rigid weights (no smoothing needed).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from char_helpers import *
from rig_helpers import rig_from_parts
from creature_rig_helpers import vsub, pose_views

reset_scene()
root = empty("root")

BODY_Z = 0.35
ALONG_NEG_Y = (90, 0, 0)      # loft local Z -> -Y, section depth -> +Z
ALONG_POS_Y = (-90, 0, 0)

# ---- body ---------------------------------------------------------------------
p = Part("body")
loft(p, "iron", [(-0.36, 0.30, 0.22), (-0.20, 0.52, 0.32, 0, 0.0), (0.05, 0.58, 0.34), (0.30, 0.50, 0.28),
                 (0.45, 0.30, 0.18, 0, 0.01), (0.52, 0.0, 0.0, 0, 0.02)], shape=8, rot=ALONG_POS_Y)
# pronotum (thorax shield) at the front
loft(p, "brass", [(0.06, 0.46, 0.34, 0, 0.03), (0.18, 0.56, 0.40, 0, 0.04), (0.32, 0.50, 0.34, 0, 0.03),
                  (0.38, 0.36, 0.24, 0, 0.02)], shape=8, rot=ALONG_NEG_Y)
loft(p, "brass_dark", [(0.18, 0.575, 0.41, 0, 0.04), (0.22, 0.575, 0.41, 0, 0.04)], shape=8, rot=ALONG_NEG_Y)
# belly plates
for y in (-0.10, 0.08, 0.26):
    p.box("brass_dark", size=(0.30, 0.10, 0.04), loc=(0, y, -0.135))
# aether vents on the back (revealed when the shell opens)
for x in (-0.08, 0.08):
    p.box("glow_green", size=(0.04, 0.34, 0.03), loc=(x, 0.12, 0.155))
p.box("copper", size=(0.30, 0.40, 0.02), loc=(0, 0.12, 0.14))
body = p.build(root, loc=(0, 0, BODY_Z))

# ---- shells (elytra) --------------------------------------------------------------
# crescent cross-section (u: 0 midline -> 1 outer edge, v: 0 bottom edge -> 1 top)
CRESCENT = [(0.0, 1.0), (0.5, 0.87), (0.87, 0.5), (1.0, 0.0), (0.86, -0.02), (0.73, 0.42), (0.42, 0.74),
            (0.0, 0.85)]
HINGE = (-0.14, 0.215)      # (y, z) of the hinge relative to the body pivot


def make_shell(name, s):
    shape = [(s * u, v) for (u, v) in CRESCENT]
    p = Part(name)
    secs = [(0.00, 0.29, 0.20, 0, -0.20), (0.14, 0.31, 0.23, 0, -0.21), (0.34, 0.31, 0.24, 0, -0.22),
            (0.52, 0.26, 0.20, 0, -0.20), (0.64, 0.15, 0.13, 0, -0.15), (0.69, 0.05, 0.05, 0, -0.10)]
    loft(p, "brass", [(-z, w, d, cx, cy) for (z, w, d, cx, cy) in secs], shape=shape, rot=ALONG_NEG_Y)
    # polished rim + rivets + a gear crest
    tube(p, "brass_dark", [(s * 0.29, 0.0, -0.20), (s * 0.31, 0.14, -0.21), (s * 0.31, 0.34, -0.22),
                           (s * 0.26, 0.52, -0.20), (s * 0.15, 0.64, -0.15), (s * 0.02, 0.69, -0.10)],
         r=0.014, seg=4)
    for y, z in ((0.12, 0.02), (0.30, 0.02), (0.48, -0.01)):
        p.box("brass_dark", size=(0.03, 0.03, 0.02), loc=(s * 0.06, y, z))
    sgear(p, "copper", r=0.07, teeth=6, thick=0.02, loc=(s * 0.17, 0.30, -0.015), rot=(0, s * 30, 0))
    return p.build(body, loc=(s * 0.005, HINGE[0], HINGE[1]))

shell_L = make_shell("shell_L", 1)
shell_R = make_shell("shell_R", -1)

# ---- head + horn + antennae -----------------------------------------------------------
p = Part("head")
loft(p, "gunmetal", [(-0.02, 0.30, 0.24), (0.08, 0.31, 0.24), (0.18, 0.22, 0.16, 0, -0.02),
                     (0.22, 0.12, 0.08, 0, -0.03)], shape=8, rot=ALONG_NEG_Y)
p.box("brass", size=(0.20, 0.06, 0.06), loc=(0, -0.14, 0.07), rot=(-25, 0, 0))     # brow plate
for s in (1, -1):
    gem(p, "glow_green", r=0.045, up=0.03, seg=6, loc=(s * 0.125, -0.09, 0.03), rot=(0, s * 65, 0))
    p.cyl("brass", r=0.055, h=0.02, seg=6, loc=(s * 0.118, -0.09, 0.03), rot=(0, s * 65, 0))
    tube(p, "brass", [(s * 0.06, -0.19, -0.05), (s * 0.08, -0.26, -0.07), (s * 0.03, -0.31, -0.06)],
         r=[0.022, 0.016, 0.0], seg=4)                                                       # mandibles
head = p.build(body, loc=(0, -0.36, 0.02))

for s, side in ((1, "L"), (-1, "R")):                    # antennae, pivot at the base in the brow plate
    piv = (s * 0.08, -0.15, 0.08)
    p = Part("antenna_" + side)
    tube(p, "iron", [vsub(q, piv) for q in ((s * 0.08, -0.15, 0.08), (s * 0.15, -0.24, 0.16),
                                            (s * 0.22, -0.28, 0.18))], r=0.008, seg=4)
    p.sphere("brass", r=0.018, seg=4, rings=3, loc=vsub((s * 0.22, -0.28, 0.18), piv))
    p.build(head, loc=piv)

p = Part("horn")
p.cyl("brass_dark", r=0.075, h=0.04, seg=6, loc=(0, 0, 0.0))
tube(p, "brass", [(0, 0, 0), (0, -0.10, 0.03), (0, -0.20, 0.09), (0, -0.27, 0.18), (0, -0.29, 0.28)],
     r=[0.07, 0.06, 0.046, 0.03, 0.0], seg=6)
tube(p, "brass", [(0, -0.19, 0.08), (0, -0.21, 0.15), (0, -0.19, 0.19)], r=[0.025, 0.015, 0.0], seg=4)
gem(p, "steel", r=0.02, up=0.05, down=0.01, seg=4, loc=(0, -0.29, 0.28), rot=(-10, 0, 0))
horn = p.build(head, loc=(0, -0.12, 0.08))

# ---- legs (out & down to z = 0): upper segment + lower `_2` segment from the knee ball ----
def make_leg(name, s, y, sweep):
    h = BODY_Z - 0.08               # pivot height above the ground
    knee = (s * 0.24, sweep * 0.55, 0.07)
    foot = (s * 0.36, sweep, -h + 0.03)
    # upper (femur): ball socket at the body + iron tube up/out to the knee
    p = Part(name)
    p.sphere("brass_dark", r=0.055, seg=6, rings=4, loc=(0, 0, 0))
    tube(p, "iron", [(0, 0, 0), (s * 0.12, sweep * 0.3, 0.06), knee], r=[0.05, 0.05, 0.038], seg=5)
    upper = p.build(body, loc=(s * 0.22, y, -0.08))
    # lower (tibia) `_2`: knee ball + shin + guard + claw foot, modelled relative to the knee
    p = Part(name + "_2")
    p.sphere("brass", r=0.048, seg=6, rings=4, loc=(0, 0, 0))
    mid = tuple(knee[i] + (foot[i] - knee[i]) * 0.45 for i in range(3))
    tube(p, "gunmetal", [vsub(q, knee) for q in (knee, mid, foot)], r=[0.042, 0.036, 0.02], seg=5)
    tube(p, "brass", [vsub(q, knee) for q in (knee, mid)], r=[0.046, 0.04], seg=5)        # tibia guard
    p.cone("brass", r=0.035, h=0.06, seg=4, loc=vsub((foot[0], foot[1], -h + 0.03), knee), rot=(180, 0, 0))
    for dy in (-0.04, 0.04):
        p.box("brass_dark", size=(0.025, 0.07, 0.02),
              loc=vsub((foot[0] + s * 0.015, foot[1] + dy, -h + 0.01), knee), rot=(0, 0, s * dy * 300))
    p.build(upper, loc=knee)
    return upper

for s, side in ((1, "L"), (-1, "R")):
    make_leg("leg_F" + side, s, -0.18, -0.14)
    make_leg("leg_M" + side, s, 0.02, 0.0)
    make_leg("leg_B" + side, s, 0.22, 0.16)

# ---- rig + export + previews ------------------------------------------------------------
arm = rig_from_parts(root, rigid=set(), smooth={}, skin_name="beetle_skin")
finish("beetle")          # tri report + export_glb("beetle") + rest-pose previews

# deformation test: elytra lifted open, alternating tripod mid-step with knees bent, head/horn raised.
# World axes: -Y front, +X = beetle's left. L legs: forward = Z-, lift = Y-, knee tuck = Y+ (R mirrored).
BEETLE_TEST_POSE = {
    "head": [("X", -12)],
    "horn": [("X", -18)],
    "antenna_L": [("X", -25), ("Z", -15)],
    "antenna_R": [("X", -10), ("Z", 25)],
    "shell_L": [("Z", -20), ("X", 30), ("Y", -15)],
    "shell_R": [("Z", 20), ("X", 30), ("Y", 15)],
    # swing tripod (FL, MR, BL): lifted, swung forward, knee tucked
    "leg_FL": [("Z", -15), ("Y", -28)], "leg_FL_2": [("Y", 50)],
    "leg_MR": [("Z", 15), ("Y", 28)], "leg_MR_2": [("Y", -50)],
    "leg_BL": [("Z", -15), ("Y", -28)], "leg_BL_2": [("Y", 50)],
    # stance tripod (FR, ML, BR): planted, swept back, knee slightly flexed
    "leg_FR": [("Z", -15), ("Y", 8)], "leg_FR_2": [("Y", -12)],
    "leg_ML": [("Z", 15), ("Y", -8)], "leg_ML_2": [("Y", 12)],
    "leg_BR": [("Z", -15), ("Y", 8)], "leg_BR_2": [("Y", -12)],
}
pose_views(arm, "beetle", BEETLE_TEST_POSE, views=(("", 35, 18), ("_back", 150, 35)))
