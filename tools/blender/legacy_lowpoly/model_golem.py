"""Steam Golem — elite enemy (~3.2 m). Exports public/models/golem.glb (skinned, RIG_SPEC.md).

Part hierarchy built here (rig_from_parts turns every mesh part into a bone of the same name):
  root > hips > {torso > {head, arm_L > forearm_L, arm_R > forearm_R, core, chimney > (steam_point)},
                 leg_L > shin_L, leg_R > shin_R}
  (parenthesised = rigid attachment / marker, not skinned)
Faces -Y, character's right = -X. Huge fists (part of forearm_X) hang down to ~z = 0.4.

Joints are mechanical ball joints with rigid weights: the brass elbow / knee / hip spheres sit on the
joint pivot (on the parent side), so ~90° bends never open gaps; the knee gear (on the shin) is centred
on the knee axis and the calf piston rod slides into the thigh when the knee bends.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from char_helpers import *
from rig_helpers import rig_from_parts, HUMANOID_TEST_POSE
from enemy_rig_helpers import build_at, pose_views

reset_scene()
root = empty("root")

HIP_Z = 1.30
LEG = (0.36, 0.0, -0.18)          # hip joint relative to hips
WAIST = 0.12                      # torso pivot above hips
SHOULDER = (1.02, 0.0, 1.15)      # relative to torso
FIST_BOTTOM = -2.17               # relative to shoulder -> world z ~0.40
ELBOW = -0.95                     # arm-local: centre of the elbow ball
KNEE = -0.55                      # leg-local: centre of the knee ball / gear

# ---- hips ---------------------------------------------------------------------
p = Part("hips")
loft(p, "iron", [(-0.30, 0.80, 0.62), (-0.05, 0.98, 0.72), (0.14, 0.94, 0.70)], shape="oct")
loft(p, "brass_dark", [(0.0, 1.01, 0.75), (0.10, 1.00, 0.74)], shape="oct")
p.box("brass", size=(0.22, 0.06, 0.16), loc=(0, -0.38, 0.05))
for x, y, rz in ((0, -0.36, 0), (0, 0.36, 0)):
    tbox(p, "iron", -0.42, 0.0, (0.40, 0.05), (0.46, 0.05), c0=(x, y * 1.05), c1=(x, y))       # skirt plates
hips = p.build(root, loc=(0, 0, HIP_Z))

# ---- legs: thigh (leg_X, pivot at the hip ball) + shin (shin_X, pivot at the knee ball) ------------
def make_leg(s):
    side = "L" if s > 0 else "R"
    h = HIP_Z + LEG[2]               # pivot height -> foot sole at -h
    p = Part("leg_" + side)
    p.sphere("brass_dark", r=0.21, seg=8, rings=4, loc=(0, 0, 0))                              # hip ball
    loft(p, "iron", [(-0.50, 0.32, 0.34), (-0.05, 0.38, 0.40)], shape="oct")                  # thigh
    p.sphere("brass", r=0.20, seg=8, rings=4, loc=(0, -0.04, KNEE))                            # knee ball
    leg = p.build(hips, loc=(s * LEG[0], LEG[1], LEG[2]))
    p = Part("shin_" + side)
    sgear(p, "copper", r=0.16, teeth=6, thick=0.05, loc=(s * 0.17, 0, KNEE), rot=(0, 90, 0))   # knee gear
    loft(p, "iron", [(-0.94, 0.50, 0.52), (-0.75, 0.46, 0.48), (-0.58, 0.36, 0.38)], shape="oct")  # shin
    loft(p, "brass", [(-0.80, 0.475, 0.495), (-0.74, 0.465, 0.485)], shape="oct")
    p.cyl("copper", r=0.07, h=0.34, seg=6, loc=(0, 0.25, -0.74))                                # piston
    p.cyl("steel", r=0.035, h=0.18, seg=6, loc=(0, 0.25, -0.50))                                # rod
    # giant foot
    loft(p, "gunmetal", [(-h, 0.60, 0.86, 0, -0.10), (-h + 0.14, 0.60, 0.86, 0, -0.10),
                         (-h + 0.24, 0.50, 0.60, 0, -0.02)], shape="oct")
    for dx in (-0.18, 0.0, 0.18):
        p.box("brass", size=(0.15, 0.12, 0.12), loc=(dx, -0.50, -h + 0.07))                    # toe caps
    build_at(p, leg, (0, 0, KNEE))
    return leg

leg_L = make_leg(1)
leg_R = make_leg(-1)

# ---- torso (furnace / boiler body) -------------------------------------------------
p = Part("torso")
loft(p, "iron", [(0.0, 0.92, 0.70), (0.35, 1.40, 0.96), (0.85, 1.58, 1.06), (1.20, 1.50, 0.98),
                 (1.38, 1.10, 0.76), (1.46, 0.72, 0.52)], shape=10)
for z0, w, d in ((0.33, 1.40, 0.97), (1.18, 1.53, 1.00)):
    loft(p, "brass", [(z0, w + 0.04, d + 0.04), (z0 + 0.09, w + 0.05, d + 0.04)], shape=10)
# brass furnace plate framing the core (the core itself is a separate node)
p.cyl("brass_dark", r=0.50, h=0.10, seg=8, loc=(0, -0.48, 0.80), rot=(90, 22.5, 0))
for k in range(8):
    a = math.radians(45 * k + 22.5)
    p.box("brass", size=(0.06, 0.04, 0.06), loc=(math.cos(a) * 0.44, -0.535, 0.80 + math.sin(a) * 0.44))
loft(p, "brass", [(1.36, 1.16, 0.80), (1.46, 0.78, 0.56)], shape=10)                       # collar
# glowing side vents
for s in (1, -1):
    for z in (0.62, 0.78):
        p.box("glow_amber", size=(0.04, 0.30, 0.05), loc=(s * 0.78, 0.0, z))
# boiler tank on the back
p.cyl("copper", r=0.30, h=0.80, seg=8, loc=(-0.15, 0.55, 0.85), rot=(0, 90, 0))
p.cyl("brass_dark", r=0.32, h=0.06, seg=8, loc=(-0.52, 0.55, 0.85), rot=(0, 90, 0))
p.cyl("brass_dark", r=0.32, h=0.06, seg=8, loc=(0.22, 0.55, 0.85), rot=(0, 90, 0))
torso = p.build(hips, loc=(0, 0, WAIST))

# ---- core: furnace grille + glow (front of chest) — its own (rigidly weighted) bone ------------
p = Part("core")
p.cyl("glow_amber", r=0.34, h=0.12, seg=8, loc=(0, -0.02, 0), rot=(90, 22.5, 0))
p.torus("brass", R=0.37, r=0.06, seg=8, seg2=4, loc=(0, -0.05, 0), rot=(90, 0, 0))
for x in (-0.21, -0.07, 0.07, 0.21):
    p.box("iron", size=(0.045, 0.04, 0.66 - abs(x) * 1.2), loc=(x, -0.09, 0))
p.box("iron", size=(0.64, 0.04, 0.045), loc=(0, -0.10, 0.0))
p.cyl("brass_dark", r=0.06, h=0.05, seg=6, loc=(0, -0.12, 0.0), rot=(90, 0, 0))
core = p.build(torso, loc=(0, -0.54, 0.80))

# ---- head (tiny) ------------------------------------------------------------------
p = Part("head")
loft(p, "iron", [(0.0, 0.34, 0.32), (0.18, 0.38, 0.36), (0.28, 0.30, 0.30), (0.33, 0.14, 0.14)], shape="oct")
p.box("black", size=(0.30, 0.04, 0.08), loc=(0, -0.17, 0.15))
for s in (1, -1):
    p.box("glow_amber", size=(0.08, 0.03, 0.05), loc=(s * 0.075, -0.185, 0.15))
p.box("brass", size=(0.36, 0.08, 0.04), loc=(0, -0.15, 0.215), rot=(-20, 0, 0))             # brow
p.cyl("brass_dark", r=0.03, h=0.12, seg=6, loc=(0, 0.0, 0.38))                               # whistle
p.cone("brass", r=0.05, h=0.06, seg=6, loc=(0, 0.0, 0.46))
head = p.build(torso, loc=(0, -0.22, 1.44))

# ---- chimney (back, +Y) — its own bone; steam_point marker stays rigidly under it -------------
p = Part("chimney")
p.cyl("iron", r=0.13, h=0.30, seg=8, loc=(0, 0.10, 0.0), rot=(90, 0, 0))                   # elbow out of the back
p.sphere("iron", r=0.15, seg=8, rings=4, loc=(0, 0.25, 0.0))
p.cyl("iron", r=0.15, h=1.15, seg=8, loc=(0, 0.25, 0.58))
for z in (0.25, 0.75):
    p.cyl("brass", r=0.17, h=0.06, seg=8, loc=(0, 0.25, z))
lathe(p, "brass_dark", [(0.15, 1.12), (0.24, 1.26), (0.24, 1.32), (0.18, 1.32)], seg=8, loc=(0, 0.25, 0),
      cap=(False, True))
p.cyl("black", r=0.17, h=0.02, seg=8, loc=(0, 0.25, 1.315))
chimney = p.build(torso, loc=(0.28, 0.50, 1.00))
empty("steam_point", parent=chimney, loc=(0, 0.25, 1.36))

# ---- arms: upper arm (arm_X, pivot at the shoulder) + forearm/fist (forearm_X, pivot at the elbow) --
def make_arm(s):
    side = "L" if s > 0 else "R"
    p = Part("arm_" + side)
    lathe(p, "brass_dark", [(0.0, 0.30), (0.26, 0.24), (0.38, 0.05), (0.38, -0.18), (0.30, -0.22)], seg=8,
          loc=(s * 0.04, 0, 0), scale=(1.0, 0.9, 1.0))                                             # pauldron
    loft(p, "brass", [(-0.20, 0.80, 0.70), (-0.12, 0.80, 0.70)], shape=8, loc=(s * 0.04, 0, 0))
    sgear(p, "brass", r=0.20, teeth=7, thick=0.05, loc=(s * 0.41, 0, -0.02), rot=(0, 90, 0))
    p.cyl("copper", r=0.13, h=0.75, seg=6, loc=(0, 0, -0.55))                                   # upper arm piston
    loft(p, "iron", [(-0.60, 0.30, 0.30), (-0.30, 0.34, 0.34)], shape="oct")
    p.sphere("brass_dark", r=0.21, seg=8, rings=4, loc=(0, 0, ELBOW))                          # elbow ball
    arm = p.build(torso, loc=(s * SHOULDER[0], SHOULDER[1], SHOULDER[2]))
    p = Part("forearm_" + side)
    loft(p, "iron", [(-1.55, 0.70, 0.70), (-1.25, 0.62, 0.62), (-1.02, 0.44, 0.44)], shape="oct")  # forearm
    loft(p, "brass", [(-1.40, 0.70, 0.70), (-1.32, 0.68, 0.68)], shape="oct")
    loft(p, "gunmetal", [(FIST_BOTTOM, 0.58, 0.60), (FIST_BOTTOM + 0.10, 0.66, 0.68), (-1.62, 0.66, 0.68),
                         (-1.55, 0.58, 0.60)], shape="oct")                                       # fist
    for dx in (-0.21, -0.07, 0.07, 0.21):
        p.box("brass", size=(0.12, 0.10, 0.14), loc=(dx, -0.33, -1.95))                         # knuckles
    p.box("gunmetal", size=(0.16, 0.22, 0.26), loc=(-s * 0.34, -0.12, -1.85))                 # thumb
    build_at(p, arm, (0, 0, ELBOW))
    return arm

arm_L = make_arm(1)
arm_R = make_arm(-1)

# ---- rig ------------------------------------------------------------------------------
arm = rig_from_parts(root, rigid={"steam_point"}, smooth={}, influence={}, skin_name="golem_skin")

finish("golem")

# ---- deformation tests (pose is reset to rest afterwards) -----------------------------------
pose_views(arm, HUMANOID_TEST_POSE, [("golem_pose", 35, 18), ("golem_pose_back", 215, 15)])
ATTACK = {                       # double-fist hammer wind-up
    "torso": [("X", -8)],
    "head": [("X", 8)],
    "arm_L": [("Y", -12), ("X", -155)],
    "forearm_L": [("X", -60)],
    "arm_R": [("Y", 12), ("X", -155)],
    "forearm_R": [("X", -60)],
    "leg_L": [("X", -35)],
    "shin_L": [("X", 45)],
    "leg_R": [("X", 15)],
    "shin_R": [("X", 15)],
}
pose_views(arm, ATTACK, [("golem_attack", 35, 12), ("golem_attack_side", 90, 8)])
