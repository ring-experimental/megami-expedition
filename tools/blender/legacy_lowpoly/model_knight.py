"""Clockwork Knight — strong enemy (~2.1 m). Exports public/models/knight.glb (skinned, RIG_SPEC.md).

Part hierarchy built here (rig_from_parts turns every mesh part into a bone of the same name):
  root > hips > {torso > {head, arm_L > forearm_L > (shield), arm_R > forearm_R > (weapon), (key)},
                 leg_L > shin_L, leg_R > shin_R, tabard_F_1 > tabard_F_2, tabard_B_1 > tabard_B_2}
  (parenthesised = rigid attachments, not skinned)
Faces -Y, character's right = -X. Halberd shaft along +Z from the right hand.
key: sticks out of the back along +Y and spins around its local Y axis.

Joints are mechanical (rigid weights): elbows get an iron hinge barrel on the bend axis + the brass
gear, knees the brass poleyn (on the thigh) + gear, hips the brass hip gear (on the thigh, centred on
the hip axis). Only the cloth tabard chains are soft-blended (enemy_rig_helpers.reweight_chain).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from common import _mtx
from char_helpers import *
from rig_helpers import rig_from_parts, HUMANOID_TEST_POSE
from enemy_rig_helpers import build_at, tag_part, reweight_chain, side_thigh_influence, pose_views

reset_scene()
root = empty("root")

HIP_Z = 1.05
LEG_Z = 0.97
WAIST_Z = 1.13
SHOULDER = (0.47, 0.0, 0.50)
NECK = 0.60
HAND = -0.80
ELBOW = -0.44        # arm-local, centre of the elbow gear (between upper arm and gauntlet)
KNEE = -0.47         # leg-local, centre of the knee gear (between thigh and greave)
TABARD_TOP = 0.02    # hips-local z of the tabard hinge (under the belt)
TABARD_SEAM = -0.28  # hips-local z where tabard_*_1 ends and tabard_*_2 starts (mid-thigh)


def tatter(x0, x1, z_top, z_bot, n, jag):
    """Outline (x, z) of a cloth panel with a jagged bottom edge."""
    pts = [(x0, z_top), (x1, z_top)]
    for i in range(n + 1):
        t = i / n
        x = x1 + (x0 - x1) * t
        z = z_bot + (jag if i % 2 else 0) + (0.03 * ((i * 37) % 3))
        pts.append((x, z))
    return pts


# ---- hips ---------------------------------------------------------------------
p = Part("hips")
loft(p, "iron", [(-0.17, 0.42, 0.30), (-0.02, 0.48, 0.33), (0.08, 0.46, 0.32)], shape="oct")
loft(p, "brass_dark", [(-0.01, 0.50, 0.35), (0.07, 0.50, 0.35)], shape="oct", cap=(False, False))  # belt
p.box("brass", size=(0.12, 0.04, 0.10), loc=(0, -0.18, 0.03))
for s in (1, -1):
    tbox(p, "iron", -0.34, 0.0, (0.05, 0.26), (0.05, 0.28), c0=(s * 0.29, 0.0), c1=(s * 0.25, 0.0))  # tassets
    tbox(p, "brass", -0.36, -0.32, (0.06, 0.27), c0=(s * 0.295, 0.0))
hips = p.build(root, loc=(0, 0, HIP_Z))

# ---- tattered tabard, front and back: two-bone cloth chains hanging from the belt ----------------
def make_tabard(side, x0, x1, z_bot, n, jag, y, tilt):
    """Same panel as the old single prism (hips space, loc=(0, y, 0), rot=(tilt, 0, 0)), split at
    TABARD_SEAM into tabard_<side>_1 (plain upper strip) and tabard_<side>_2 (jagged lower part).
    The seam edge gets a centre vertex so each half of the cloth can follow its own thigh."""
    M = _mtx((0, y, 0), (tilt, 0, 0))
    piv1 = M @ Vector((0, 0, TABARD_TOP))
    piv2 = M @ Vector((0, 0, TABARD_SEAM))
    p = Part(f"tabard_{side}_1")
    prism(p, "cloth_red", [(x0, 0.06), (x1, 0.06), (x1, TABARD_SEAM), (0, TABARD_SEAM), (x0, TABARD_SEAM)], 0.025,
          loc=(0, y, 0), axis="y", rot=(tilt, 0, 0))
    t1 = build_at(p, hips, piv1)
    p = Part(f"tabard_{side}_2")
    outline = tatter(x0, x1, TABARD_SEAM, z_bot, n, jag)
    prism(p, "cloth_red", outline[:1] + [(0, TABARD_SEAM)] + outline[1:], 0.025,
          loc=(0, y, 0), axis="y", rot=(tilt, 0, 0))
    t2 = build_at(p, t1, piv2 - piv1, frame=-piv1)
    tag_part(t1, f"__tabard_{side}")
    tag_part(t2, f"__tabard_{side}")
    return t1, t2

make_tabard("F", -0.15, 0.15, -0.66, 6, 0.09, -0.185, -6)
make_tabard("B", -0.17, 0.17, -0.70, 6, 0.10, 0.185, 6)

# ---- legs: thigh (leg_X, pivot at the hip) + shin (shin_X, pivot at the knee) ---------------
def make_leg(s):
    side = "L" if s > 0 else "R"
    p = Part("leg_" + side)
    loft(p, "iron", [(-0.44, 0.17, 0.19), (-0.20, 0.20, 0.22), (0.04, 0.21, 0.23)], shape="oct")      # thigh
    p.ico("brass", r=0.09, loc=(0, -0.07, -0.48), scale=(1.1, 0.8, 1.0))                             # poleyn
    sgear(p, "brass", r=0.11, teeth=6, thick=0.04, loc=(s * 0.075, 0.0, 0.0), rot=(0, 90, 0))        # hip gear
    leg = p.build(hips, loc=(s * 0.17, 0, LEG_Z - HIP_Z))
    p = Part("shin_" + side)
    sgear(p, "brass_dark", r=0.09, teeth=6, thick=0.04, loc=(s * 0.10, 0.0, KNEE), rot=(0, 90, 0))   # knee gear
    loft(p, "iron", [(-0.84, 0.24, 0.26), (-0.66, 0.22, 0.24), (-0.50, 0.19, 0.21)], shape="oct")     # greave
    loft(p, "brass", [(-0.70, 0.235, 0.255), (-0.66, 0.235, 0.255)], shape="oct", cap=(False, False))
    # big sabaton
    loft(p, "gunmetal", [(-0.97, 0.29, 0.41, 0, -0.06), (-0.88, 0.28, 0.40, 0, -0.06),
                         (-0.82, 0.22, 0.24, 0, 0.0)], shape="oct")
    p.box("iron", size=(0.20, 0.10, 0.06), loc=(0, -0.24, -0.92), rot=(-20, 0, 0))
    build_at(p, leg, (0, 0, KNEE))
    return leg

leg_L = make_leg(1)
leg_R = make_leg(-1)

# ---- torso --------------------------------------------------------------------
p = Part("torso")
loft(p, "iron", [(0.0, 0.44, 0.32), (0.12, 0.50, 0.36), (0.34, 0.68, 0.44), (0.52, 0.72, 0.44),
                 (0.60, 0.50, 0.34)], shape="oct")
# brass breastplate
prism(p, "brass", [(-0.27, 0.54), (0.27, 0.54), (0.30, 0.36), (0.20, 0.20), (0.0, 0.14), (-0.20, 0.20),
                   (-0.30, 0.36)], 0.06, loc=(0, -0.205, 0), axis="y")
prism(p, "cloth_red", [(-0.15, 0.24), (0.15, 0.24), (0.14, -0.02), (-0.14, -0.02)], 0.02,
      loc=(0, -0.18, 0), axis="y", rot=(-10, 0, 0))
sgear(p, "brass_dark", r=0.085, teeth=6, thick=0.03, loc=(0, -0.24, 0.36), rot=(90, 0, 0))
p.cyl("glow_amber", r=0.03, h=0.03, seg=6, loc=(0, -0.25, 0.36), rot=(90, 0, 0))
# abdomen ribs + exposed gear at the side
loft(p, "brass_dark", [(0.08, 0.48, 0.35), (0.12, 0.50, 0.36)], shape="oct", cap=(False, False))
sgear(p, "brass", r=0.10, teeth=6, thick=0.04, loc=(-0.24, -0.06, 0.10), rot=(0, 90, 0))
# gorget
loft(p, "brass", [(0.55, 0.42, 0.32), (0.62, 0.36, 0.28), (0.66, 0.30, 0.24)], shape="oct")
# back plate with key socket
tbox(p, "brass_dark", 0.18, 0.50, (0.40, 0.04), c0=(0, 0.215))
p.cyl("brass", r=0.07, h=0.05, seg=8, loc=(0, 0.235, 0.36), rot=(90, 0, 0))
torso = p.build(hips, loc=(0, 0, WAIST_Z - HIP_Z))

# ---- key (rigid, spins around local Y) ------------------------------------------------
p = Part("key")
p.cyl("brass", r=0.035, h=0.24, seg=6, loc=(0, 0.12, 0), rot=(90, 0, 0))
p.cyl("brass_dark", r=0.055, h=0.04, seg=6, loc=(0, 0.06, 0), rot=(90, 0, 0))
p.box("brass", size=(0.06, 0.08, 0.10), loc=(0, 0.26, 0))
for s in (1, -1):
    p.torus("brass", R=0.085, r=0.03, seg=8, seg2=3, loc=(0, 0.29, s * 0.115), rot=(0, 90, 0))
key = p.build(torso, loc=(0, 0.25, 0.36))

# ---- head (helmet) ------------------------------------------------------------
p = Part("head")
loft(p, "iron", [(0.0, 0.26, 0.26), (0.06, 0.33, 0.35), (0.27, 0.34, 0.36), (0.36, 0.22, 0.25)], shape="oct")
loft(p, "brass", [(0.05, 0.345, 0.365), (0.10, 0.345, 0.365)], shape="oct", cap=(False, False))
p.box("black", size=(0.27, 0.06, 0.055), loc=(0, -0.165, 0.19))                  # visor slit
for s in (1, -1):
    p.box("glow_amber", size=(0.07, 0.03, 0.03), loc=(s * 0.065, -0.183, 0.19))
    for z in (0.09, 0.12):
        p.box("black", size=(0.04, 0.02, 0.012), loc=(s * 0.06, -0.177, z))      # breath holes
    p.cyl("brass", r=0.04, h=0.03, seg=6, loc=(s * 0.17, 0.0, 0.19), rot=(0, 90, 0))
prism(p, "brass", [(-0.16, 0.30), (-0.05, 0.38), (0.12, 0.42), (0.20, 0.36), (0.14, 0.30)], 0.04,
      loc=(0, 0, 0), axis="x")                                                       # crest fin
p.box("brass", size=(0.05, 0.03, 0.20), loc=(0, -0.175, 0.25))                     # nose guard ridge
head = p.build(torso, loc=(0, 0, NECK))

# ---- arms: upper arm (arm_X, pivot at the shoulder) + forearm (forearm_X, pivot at the elbow) --------
def make_arm(s):
    side = "L" if s > 0 else "R"
    p = Part("arm_" + side)
    # layered pauldron (wide, shallow in Y so the halberd can pass in front)
    lathe(p, "brass", [(0.0, 0.14), (0.14, 0.11), (0.21, 0.02), (0.22, -0.08), (0.20, -0.10)], seg=8,
          loc=(s * 0.02, 0, 0), scale=(1.0, 0.78, 1.0))
    lathe(p, "iron", [(0.20, -0.07), (0.22, -0.16)], seg=8, loc=(s * 0.03, 0, 0), scale=(1.0, 0.78, 1.0),
          cap=(True, False))
    loft(p, "iron", [(-0.42, 0.15, 0.15), (-0.08, 0.17, 0.17)], shape="oct")                  # upper arm
    p.cyl("gunmetal", r=0.085, h=0.15, seg=6, loc=(0, 0, ELBOW), rot=(0, 90, 0))              # elbow hinge
    arm = p.build(torso, loc=(s * SHOULDER[0], SHOULDER[1], SHOULDER[2]))
    p = Part("forearm_" + side)
    sgear(p, "brass_dark", r=0.09, teeth=5, thick=0.04, loc=(s * 0.08, 0.0, ELBOW), rot=(0, 90, 0))
    loft(p, "brass", [(-0.70, 0.22, 0.23), (-0.50, 0.20, 0.21), (-0.47, 0.17, 0.18)], shape="oct")  # gauntlet
    loft(p, "iron", [(-0.90, 0.19, 0.20), (-0.86, 0.21, 0.22), (-0.72, 0.21, 0.22), (-0.69, 0.19, 0.20)],
         shape="oct")                                                                                # fist
    p.box("brass_dark", size=(0.20, 0.04, 0.05), loc=(0, -0.11, -0.76))                             # knuckles
    p.box("iron", size=(0.06, 0.08, 0.10), loc=(-s * 0.105, -0.05, -0.80))                            # thumb
    fore = build_at(p, arm, (0, 0, ELBOW))
    return arm, fore

arm_L, forearm_L = make_arm(1)
arm_R, forearm_R = make_arm(-1)

# ---- shield (rigid, child of forearm_L): gear-shaped, on the outer side, facing -Y/+X ----------
FACE = (0, 90, -45)           # local Z -> (+X, -Y) diagonal
n = Vector((0.7071, -0.7071, 0.0))
def along(d):
    return tuple(n * d)
p = Part("shield")
p.box("leather_dark", size=(0.06, 0.06, 0.20), loc=along(0.03))
sgear(p, "iron", r=0.36, teeth=11, depth=0.065, thick=0.05, loc=along(0.08), rot=FACE)
p.cyl("brass", r=0.25, h=0.065, seg=10, loc=along(0.085), rot=FACE)
p.cyl("brass_dark", r=0.13, h=0.03, seg=6, loc=along(0.125), rot=FACE)
p.cone("iron", r=0.07, h=0.09, seg=6, loc=along(0.17), rot=FACE)
p.cyl("glow_amber", r=0.03, h=0.03, seg=6, loc=along(0.142), rot=FACE)
shield = p.build(forearm_L, loc=(0.11, -0.01, -0.58 - ELBOW))      # same world spot as before (arm z -0.58)

# ---- weapon (rigid, child of forearm_R): clockwork halberd, shaft along +Z from the hand ------------
SX, SY = -0.10, -0.18        # shaft runs in front of/outside the fist, held by a brass clamp
p = Part("weapon")
p.box("brass", size=(0.06, 0.12, 0.10), loc=(SX * 0.5, -0.13, 0.0))                  # gauntlet clamp
p.cyl("brass_dark", r=0.05, h=0.12, seg=6, loc=(SX, SY, 0.0))
p.cyl("wood_dark", r=0.03, h=2.05, seg=6, loc=(SX, SY, 0.47))
p.cone("iron", r=0.04, h=0.12, seg=6, loc=(SX, SY, -0.60), rot=(180, 0, 0))
for z in (-0.35, 0.80):
    p.cyl("brass", r=0.04, h=0.04, seg=6, loc=(SX, SY, z))
# head: socket, axe blade (faces -Y), back spike (+Y), spear tip
HZ = 1.30
p.cyl("brass", r=0.05, h=0.32, seg=6, loc=(SX, SY, HZ))
sgear(p, "brass_dark", r=0.09, teeth=6, thick=0.03, loc=(SX - 0.05, SY, HZ - 0.08), rot=(0, 90, 0))
axe = [(-0.03, 0.08), (-0.03, -0.06), (-0.16, -0.10), (-0.31, -0.25), (-0.37, -0.11), (-0.39, 0.04),
       (-0.37, 0.19), (-0.31, 0.33), (-0.16, 0.14)]
prism(p, "steel", [(y + SY, z + HZ) for (y, z) in axe], [0.04, 0.04, 0.03, 0.01, 0.012, 0.012, 0.012, 0.01, 0.03],
      loc=(SX, 0, 0), axis="x")
prism(p, "iron", [(0.03 + SY, HZ + 0.06), (0.03 + SY, HZ - 0.06), (0.26 + SY, HZ - 0.02)], 0.04,
      loc=(SX, 0, 0), axis="x")                                                         # back spike
gem(p, "steel", r=0.045, up=0.30, down=0.04, seg=4, loc=(SX, SY, HZ + 0.20))           # spear tip
weapon = p.build(forearm_R, loc=(0, 0, HAND - ELBOW))               # pivot at the hand, as before

# ---- rig ------------------------------------------------------------------------------
arm = rig_from_parts(root, rigid={"weapon", "shield", "key"},
                     smooth={}, influence={}, skin_name="knight_skin")
skin = bpy.data.objects["knight_skin"]
# tabard cloth: soft hinge under the belt and a soft bend at the seam. NO thigh influence: splitting
# the panel between both thighs shears it diagonally and drags its inner edge into the forward thigh.
# Instead the game swings each panel as one piece with the most-forward / most-backward thigh
# (src/anim/rig.ts thighFollow: tabard F ≈ 0.9 × thigh angle, B ≈ 0.85 ×), which clears the knee.
reweight_chain(arm, skin, "__tabard_F", ["tabard_F_1", "tabard_F_2"], radius=0.08, anchor_radius=0.04)
reweight_chain(arm, skin, "__tabard_B", ["tabard_B_1", "tabard_B_2"], radius=0.08, anchor_radius=0.04)

finish("knight")
render_view("knight_face", (0, -0.1, 1.85), 0.45, azimuth=25, elevation=8)

# ---- deformation tests (pose is reset to rest afterwards) -----------------------------------
TEST = dict(HUMANOID_TEST_POSE)
# the game swings the front panel forward by ~half the stepping thigh's angle per chain bone
# game: F follows the most-forward thigh (leg_L 45° → F_1 −40°, F_2 −9°), B the most-backward (20° → 17°, 4°)
TEST.update({"tabard_F_1": [("X", -40)], "tabard_F_2": [("X", -9)],
             "tabard_B_1": [("X", 17)], "tabard_B_2": [("X", 4)]})
pose_views(arm, TEST, [("knight_pose", 35, 18), ("knight_pose_back", 215, 15)])
ATTACK = {
    "torso": [("X", 8), ("Z", 10)],
    "head": [("X", -8)],
    "arm_L": [("Y", -20), ("X", -150)],
    "forearm_L": [("X", -55)],
    "arm_R": [("Y", 20), ("X", -160)],
    "forearm_R": [("X", -105)],          # forearm points back -> halberd levelled forward overhead
    "leg_L": [("X", -50)],
    "shin_L": [("X", 60)],
    "leg_R": [("X", 20)],
    "shin_R": [("X", 20)],
    "tabard_F_1": [("X", -45)], "tabard_F_2": [("X", -10)],   # leg_L 50° forward
    "tabard_B_1": [("X", 17)], "tabard_B_2": [("X", 4)],      # leg_R 20° back
}
pose_views(arm, ATTACK, [("knight_attack", 35, 12), ("knight_attack_side", 90, 8)])
