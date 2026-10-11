"""Kai — protagonist, young steam-swordsman (~1.75 m). Exports public/models/kai.glb (skinned).

Skeleton (RIG_SPEC.md):
    root (armature)
    └─ hips ─┬─ torso ─┬─ head
             │         ├─ arm_L ─ forearm_L
             │         ├─ arm_R ─ forearm_R ─(rigid) weapon
             │         ├─ scarf_1 ─ scarf_2
             │         └─(rigid) steam_point
             ├─ leg_L ─ shin_L,  leg_R ─ shin_R
             ├─ coat_L_1 ─ coat_L_2,  coat_R_1 ─ coat_R_2      (back coat tails)
             └─ coat_SL_1,  coat_SR_1                           (side coat panels)
Faces -Y, character's right = -X.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from char_helpers import *
from rig_helpers import rig_from_parts, pose_preview, HUMANOID_TEST_POSE
from hero_rig_helpers import joint_cap, resample, build_at, add_influence, limit_influences, ss

reset_scene()
get_mat("cloth_charcoal", hex="#33343d", metallic=0.0, roughness=0.85)  # trousers

root = empty("root")

# ---- key heights (world) ----------------------------------------------------
HIP_Z = 0.87          # hips pivot (pelvis)
LEG_Z = 0.81          # hip joints
WAIST_Z = 0.94        # torso pivot
SHOULDER = (0.285, 0.0, 0.29)   # arm pivot relative to torso
NECK = 0.37           # head pivot relative to torso
HAND = -0.42          # hand centre relative to shoulder
ELBOW = -0.21         # elbow relative to shoulder
KNEE = -0.38          # knee relative to hip joint
R_ELBOW, R_KNEE = 0.05, 0.05    # skin blend radii — small: the round joint caps cover the bend

# ---- hips ---------------------------------------------------------------------
p = Part("hips")
loft(p, "cloth_charcoal", [(-0.12, 0.30, 0.19), (0.0, 0.32, 0.21), (0.08, 0.30, 0.20)], shape="oct")
loft(p, "leather_dark", [(0.0, 0.335, 0.225), (0.065, 0.335, 0.225)], shape="oct")      # belt
p.box("brass", size=(0.07, 0.03, 0.06), loc=(0, -0.115, 0.033))                           # buckle
p.box("leather", size=(0.07, 0.06, 0.09), loc=(0.15, -0.04, -0.02), rot=(0, 0, -12))      # pouch
p.box("brass", size=(0.02, 0.02, 0.02), loc=(0.163, -0.075, 0.0))
hips = p.build(root, loc=(0, 0, HIP_Z))

# ---- coat skirt (hips frame): back tails = 2-bone chains, side panels = 1 bone ----------
COAT_J = -0.23        # coat_X_2 joint height (hips frame)
R_COAT = 0.10


def coat_tail(s, zs):
    """Back coat tail profile (was one tbox -0.50..0.04), sampled at heights zs."""
    out = []
    for z in zs:
        f = (z + 0.50) / 0.54
        out.append((z, 0.20 + (0.165 - 0.20) * f, 0.035, s * (0.115 - 0.03 * f), 0.14 - 0.025 * f))
    return out


for side, s in (("L", 1), ("R", -1)):
    top = coat_tail(s, [0.04])[0]
    mid = coat_tail(s, [COAT_J])[0]
    piv1 = (top[3], top[4], 0.04)
    piv2 = (mid[3], mid[4], COAT_J)
    p = Part(f"coat_{side}_1")
    loft(p, "cloth_navy", coat_tail(s, [COAT_J, COAT_J + R_COAT, 0.04]), shape="rect", cap=(False, False))
    c1 = build_at(p, hips, piv1)
    p = Part(f"coat_{side}_2")
    loft(p, "cloth_navy", coat_tail(s, [-0.50, COAT_J - R_COAT, COAT_J]), shape="rect", cap=(True, False))
    build_at(p, c1, piv2, piv1)
    p = Part(f"coat_S{side}_1")
    tbox(p, "cloth_navy", -0.40, 0.04, (0.035, 0.20), (0.035, 0.17),
         c0=(s * 0.205, 0.05), c1=(s * 0.17, 0.02))
    tbox(p, "brass", -0.425, -0.395, (0.036, 0.037), c0=(s * 0.205, 0.0))   # tip weight (was floating 4 cm below)
    build_at(p, hips, (s * 0.17, 0.02, 0.04))

# ---- legs: thigh (hip joint -> knee) + shin (knee -> boot), leg frame ---------------
TROUSER = [(-0.46, 0.12, 0.13), (-0.23, 0.13, 0.14), (0.04, 0.15, 0.16)]


def make_leg(side, s):
    p = Part("leg_" + side)
    loft(p, "cloth_charcoal", resample(TROUSER, [KNEE, KNEE + R_KNEE, 0.04]), shape="oct", cap=(False, False))
    leg = p.build(hips, loc=(s * 0.10, 0, LEG_Z - HIP_Z))
    p = Part("shin_" + side)
    loft(p, "cloth_charcoal", resample(TROUSER, [-0.46, KNEE]), shape="oct", cap=(False, False))
    # chunky boot
    loft(p, "leather", [(-0.80, 0.16, 0.18, 0, -0.01), (-0.66, 0.16, 0.18, 0, -0.01),
                        (-0.49, 0.155, 0.165, 0, 0.0)], shape="oct", cap=(False, False))
    loft(p, "leather", [(-0.80, 0.15, 0.16, 0, -0.11), (-0.71, 0.14, 0.12, 0, -0.11)], shape="oct",
         cap=(False, True))                                                                 # toe
    loft(p, "leather_dark", [(-0.80, 0.17, 0.29, 0, -0.045), (-0.77, 0.17, 0.29, 0, -0.045)], shape="oct")  # sole
    loft(p, "leather_dark", [(-0.52, 0.17, 0.185), (-0.45, 0.175, 0.19)], shape="oct", cap=(False, True))  # cuff
    p.box("brass", size=(0.04, 0.02, 0.035), loc=(s * 0.02, -0.096, -0.485))              # buckle
    p.box("brass", size=(0.03, 0.02, 0.03), loc=(s * 0.02, -0.098, -0.63))
    shin = build_at(p, leg, (0, 0, KNEE))
    joint_cap("knee_" + side, shin, "cloth_charcoal", TROUSER, KNEE)
    return leg


leg_L = make_leg("L", 1)
leg_R = make_leg("R", -1)

# ---- torso --------------------------------------------------------------------
p = Part("torso")
loft(p, "cloth_navy", [(0.0, 0.30, 0.20), (0.16, 0.34, 0.22), (0.30, 0.40, 0.23), (0.37, 0.30, 0.19)],
     shape="oct", cap=(False, True))
# shirt V + lapels
p.poly("cloth_cream", [(-0.07, -0.118, 0.37), (0.07, -0.118, 0.37), (0.0, -0.122, 0.17)], [(0, 1, 2)])
for s in (1, -1):
    p.poly("cloth_navy", [(s * 0.07, -0.12, 0.37), (s * 0.14, -0.12, 0.33), (s * 0.015, -0.126, 0.16)],
           [(0, 1, 2)])
    p.poly("brass_dark", [(s * 0.016, -0.123, 0.15), (s * 0.03, -0.123, 0.15),
                          (s * 0.03, -0.112, -0.0), (s * 0.016, -0.112, -0.0)], [(0, 1, 2, 3)])
    for i, z in enumerate((0.04, 0.10, 0.16)):
        p.cyl("brass", r=0.016, h=0.016, seg=6, loc=(s * 0.06, -0.117 - 0.002 * i, z), rot=(90, 0, 0))
    # epaulette
    p.box("brass", size=(0.10, 0.11, 0.025), loc=(s * 0.215, 0.0, 0.335), rot=(0, s * 12, 0))
# scarf around the neck (the hanging tail is the scarf_1 -> scarf_2 chain below)
p.torus("cloth_red", R=0.095, r=0.045, seg=10, seg2=5, loc=(0, 0.0, 0.385), rot=(-8, 0, 0))
# steam pack on the back
tbox(p, "brass", 0.06, 0.34, (0.30, 0.13), c0=(0, 0.19))
tbox(p, "brass_dark", 0.10, 0.30, (0.22, 0.02), c0=(0, 0.26))
p.cyl("copper", r=0.065, h=0.30, seg=8, loc=(0.0, 0.265, 0.20))
for z in (0.10, 0.30):
    p.cyl("brass_dark", r=0.07, h=0.025, seg=8, loc=(0.0, 0.265, z))
p.gear("copper", r=0.05, thickness=0.02, teeth=6, tooth=0.03, loc=(0.0, 0.331, 0.20), rot=(90, 0, 0))
for s in (1, -1):
    p.cyl("iron", r=0.034, h=0.26, seg=6, loc=(s * 0.125, 0.235, 0.45))
    p.cyl("brass", r=0.045, h=0.03, seg=6, loc=(s * 0.125, 0.235, 0.585))
    p.cyl("brass_dark", r=0.04, h=0.02, seg=6, loc=(s * 0.125, 0.235, 0.34))
    # leather straps over the shoulders
    tbox(p, "leather_dark", 0.06, 0.375, (0.05, 0.02), c0=(s * 0.11, 0.113))
torso = p.build(hips, loc=(0, 0, WAIST_Z - HIP_Z))
empty("steam_point", parent=torso, loc=(-0.125, 0.235, 0.60))

# scarf tail hanging over the chest (torso frame): scarf_1 (upper) -> scarf_2 (lower + fringe end)
SCARF = [(0.16, 0.075, 0.03, 0.10, -0.135), (0.37, 0.07, 0.03, 0.06, -0.115)]
SJ = 0.265
p = Part("scarf_1")
loft(p, "cloth_red", resample(SCARF, [SJ, 0.37]), shape="rect", cap=(False, False))
sc1 = build_at(p, torso, (0.06, -0.115, 0.37))
p = Part("scarf_2")
loft(p, "cloth_red", resample(SCARF, [0.16, SJ]), shape="rect", cap=(False, False))
tbox(p, "cloth_red", 0.12, 0.165, (0.08, 0.03), (0.075, 0.03), c0=(0.105, -0.14), c1=(0.10, -0.137))
mid = resample(SCARF, [SJ])[0]
build_at(p, sc1, (mid[3], mid[4], SJ), (0.06, -0.115, 0.37))

# ---- head ---------------------------------------------------------------------
p = Part("head")
lathe(p, "skin", [(0.06, -0.02), (0.06, 0.08)], seg=8, cap=(False, False))   # neck (ends hidden)
# big chibi head: centre (0, 0, 0.23), radius ~0.215
K = 0.215 / 0.18   # scale factor for the face details designed at r=0.18
def hp(x, y, z):   # head-local point, details authored around a 0.18 head centred at z=0.19
    return (x * K, y * K, 0.23 + (z - 0.19) * K)
p.sphere("skin", r=0.215, seg=10, rings=8, loc=(0, 0, 0.23), scale=(1.04, 0.96, 0.97))
for s in (1, -1):
    p.sphere("skin", r=0.04, seg=6, rings=4, loc=hp(s * 0.178, 0.01, 0.18), scale=(0.6, 1, 1))  # ears
    p.box("black", size=(0.05, 0.03, 0.08), loc=hp(s * 0.066, -0.155, 0.165))                 # eyes
    p.box("white", size=(0.018, 0.01, 0.02), loc=hp(s * 0.073, -0.17, 0.182))
    p.box("hair_brown", size=(0.065, 0.02, 0.016), loc=hp(s * 0.07, -0.157, 0.218), rot=(0, s * 8, 0))  # brows
    p.box("cloth_red", size=(0.03, 0.006, 0.014), loc=hp(s * 0.112, -0.127, 0.135), rot=(0, 0, s * 37))  # blush
p.box("leather_dark", size=(0.035, 0.01, 0.009), loc=hp(0, -0.172, 0.11))   # tiny mouth
# hair: cap + messy spikes
p.sphere("hair_brown", r=0.192 * K, seg=10, rings=8, loc=hp(0, 0.025, 0.215), scale=(1.06, 1.0, 1.0))
spikes = [  # (loc, rot, r, h)
    ((0.00, -0.12, 0.33), (-60, 0, 0), 0.07, 0.16),
    ((0.09, -0.11, 0.31), (-55, 25, 0), 0.06, 0.15),
    ((-0.09, -0.11, 0.31), (-55, -25, 0), 0.06, 0.15),
    ((0.05, 0.00, 0.40), (-15, 20, 0), 0.07, 0.14),
    ((-0.06, 0.03, 0.40), (10, -25, 0), 0.07, 0.14),
    ((0.00, 0.13, 0.33), (55, 0, 0), 0.08, 0.16),
    ((0.12, 0.10, 0.27), (50, 40, 0), 0.07, 0.15),
    ((-0.12, 0.10, 0.27), (50, -40, 0), 0.07, 0.15),
    ((0.17, -0.02, 0.27), (0, 60, 0), 0.06, 0.13),
    ((-0.17, -0.02, 0.27), (0, -60, 0), 0.06, 0.13),
    ((0.00, 0.17, 0.18), (95, 0, 0), 0.07, 0.12),
    ((0.163, -0.03, 0.15), (180, -12, 0), 0.04, 0.10),
    ((-0.163, -0.03, 0.15), (180, 12, 0), 0.04, 0.10),
]
for loc, rot, r, h in spikes:
    p.cone("hair_brown", r=r * K, h=h * K, seg=4, loc=hp(*loc), rot=rot)
# bangs over the forehead
for x, ang in ((-0.10, -15), (-0.035, 5), (0.04, -5), (0.105, 15)):
    p.cone("hair_brown", r=0.045 * K, h=0.11 * K, seg=4, loc=hp(x, -0.165, 0.265), rot=(180 - 10, ang, 0))
# goggles pushed up on the forehead
p.torus("leather_dark", R=0.199 * K, r=0.018, seg=12, seg2=4, loc=hp(0, 0.02, 0.27), rot=(-14, 0, 0))
for s in (1, -1):
    p.cyl("brass", r=0.062, h=0.05, seg=8, loc=hp(s * 0.062, -0.17, 0.305), rot=(-62, 0, 0))
    p.cyl("glass", r=0.047, h=0.056, seg=8, loc=hp(s * 0.062, -0.172, 0.306), rot=(-62, 0, 0))
p.box("brass_dark", size=(0.035, 0.024, 0.024), loc=hp(0, -0.18, 0.31), rot=(-62, 0, 0))
head = p.build(torso, loc=(0, 0, NECK))

# ---- arms: upper arm (shoulder -> elbow) + forearm (elbow -> glove), arm frame ---------
SLEEVE = [(-0.30, 0.115, 0.115), (-0.05, 0.13, 0.13)]


def make_arm(side, s):
    p = Part("arm_" + side)
    p.sphere("cloth_navy", r=0.085, seg=8, rings=6, loc=(0, 0, -0.01))
    loft(p, "cloth_navy", resample(SLEEVE, [ELBOW, ELBOW + R_ELBOW, -0.05]), shape="oct", cap=(False, False))
    arm = p.build(torso, loc=(s * SHOULDER[0], SHOULDER[1], SHOULDER[2]))
    p = Part("forearm_" + side)
    loft(p, "cloth_navy", resample(SLEEVE, [-0.30, ELBOW]), shape="oct", cap=(False, False))
    loft(p, "cloth_navy", [(-0.36, 0.145, 0.145), (-0.29, 0.14, 0.14)], shape="oct")      # cuff
    loft(p, "brass", [(-0.30, 0.142, 0.142), (-0.285, 0.142, 0.142)], shape="oct", cap=(False, True))
    # chunky leather glove
    loft(p, "leather", [(-0.51, 0.11, 0.13), (-0.48, 0.13, 0.145), (-0.38, 0.13, 0.14), (-0.35, 0.11, 0.12)],
         shape="oct", cap=(True, False))
    p.box("leather", size=(0.045, 0.06, 0.07), loc=(-s * 0.06, -0.035, -0.42), rot=(0, 0, 0))  # thumb
    p.box("leather_dark", size=(0.135, 0.15, 0.025), loc=(0, 0, -0.37))
    forearm = build_at(p, arm, (0, 0, ELBOW))
    joint_cap("elbow_" + side, forearm, "cloth_navy", SLEEVE, ELBOW)
    return arm, forearm


arm_L, forearm_L = make_arm("L", 1)
arm_R, forearm_R = make_arm("R", -1)

# ---- weapon: steam greatsword (blade points -Y with the arm hanging down) ----------
p = Part("weapon")
p.cyl("leather_dark", r=0.028, h=0.26, seg=6, loc=(0, 0.03, 0), rot=(90, 0, 0))          # grip
for y in (-0.03, 0.06):
    p.cyl("brass_dark", r=0.032, h=0.02, seg=6, loc=(0, y, 0), rot=(90, 0, 0))
p.sphere("brass", r=0.045, seg=6, rings=4, loc=(0, 0.185, 0))                              # pommel
# guard (spans the blade width, i.e. Z)
p.box("brass", size=(0.07, 0.06, 0.30), loc=(0, -0.13, 0.0))
p.cyl("brass_dark", r=0.035, h=0.08, seg=6, loc=(0, -0.13, 0.16))
p.cyl("brass_dark", r=0.035, h=0.08, seg=6, loc=(0, -0.13, -0.16))
# blade: broad, flat faces +-X, edge down, spine up
BL0, BL1 = -0.16, -1.36
blade = [(BL0, -0.095), (BL0, 0.095), (BL1 + 0.14, 0.095), (BL1, -0.005), (BL1 + 0.20, -0.095)]
prism(p, "steel", blade, thick=[0.05, 0.05, 0.04, 0.012, 0.03], axis="x")
p.box("brass_dark", size=(0.065, 0.10, 0.21), loc=(0, -0.21, 0.0))                       # ricasso collar
# rune line (glows through both flats)
p.box("glow_cyan", size=(0.054, 0.80, 0.016), loc=(0, -0.68, -0.005))
p.box("glow_cyan", size=(0.054, 0.016, 0.05), loc=(0, -0.30, -0.005))
p.box("glow_cyan", size=(0.054, 0.016, 0.05), loc=(0, -1.06, -0.005))
# piston on the spine
p.cyl("brass", r=0.028, h=0.24, seg=6, loc=(0, -0.38, 0.125), rot=(90, 0, 0))
p.cyl("copper", r=0.013, h=0.20, seg=6, loc=(0, -0.58, 0.125), rot=(90, 0, 0))
p.box("brass_dark", size=(0.04, 0.03, 0.05), loc=(0, -0.68, 0.11))
p.box("brass_dark", size=(0.04, 0.03, 0.05), loc=(0, -0.28, 0.11))
weapon = p.build(forearm_R, loc=(0, 0, HAND - ELBOW))     # same world spot as before (hand)

# ---- rig -------------------------------------------------------------------------
arm = rig_from_parts(
    root, rigid={"weapon", "steam_point"},
    smooth={"forearm_L": R_ELBOW, "forearm_R": R_ELBOW, "shin_L": R_KNEE, "shin_R": R_KNEE,
            "coat_L_2": R_COAT, "coat_R_2": R_COAT, "scarf_2": 0.05},
    influence={},   # thigh influence on the coat is position-dependent -> add_influence below
    skin_name="kai_skin")
skin = bpy.data.objects["kai_skin"]
# coat follows the thighs more toward the hem (0 at the belt, so the waistline never shears)
for side in ("L", "R"):
    add_influence(skin, [f"coat_{side}_1", f"coat_{side}_2"], f"leg_{side}",
                  lambda co: 0.35 * ss(HIP_Z + 0.02, HIP_Z - 0.42, co.z))
    add_influence(skin, [f"coat_S{side}_1"], f"leg_{side}",
                  lambda co: 0.30 * ss(HIP_Z + 0.02, HIP_Z - 0.40, co.z))
limit_influences(skin, 4)

finish("kai", budget=3100)
render_view("kai_face", (0, 0, 1.45), 0.4, azimuth=25, elevation=8)

# ---- deformation previews (pose_preview resets to rest pose afterwards) -----------
CHAINS_SWING = {
    "coat_L_1": [("X", 20)], "coat_L_2": [("X", 15)],
    "coat_R_1": [("X", 30)], "coat_R_2": [("X", 10)],
    "coat_SL_1": [("Y", -20)], "coat_SR_1": [("Y", 25)],
    "scarf_1": [("X", -35), ("Y", 15)], "scarf_2": [("X", -20)],
}
pose_preview(arm, "kai_pose", {**HUMANOID_TEST_POSE, **CHAINS_SWING})
pose_preview(arm, "kai_pose_back", {**HUMANOID_TEST_POSE, **CHAINS_SWING}, azimuth=200, elevation=15)
RUN = {
    "torso": [("X", -8)], "head": [("X", 6)],
    "leg_L": [("X", -50)], "shin_L": [("X", 60)],
    "leg_R": [("X", 30)], "shin_R": [("X", 65)],
    "arm_L": [("X", 35)], "forearm_L": [("X", -45)],
    "arm_R": [("X", -40)], "forearm_R": [("X", -50)],
    "coat_L_1": [("X", 25)], "coat_L_2": [("X", 15)],
    "coat_R_1": [("X", 25)], "coat_R_2": [("X", 15)],
    "coat_SL_1": [("X", 10)], "coat_SR_1": [("X", 10)],
    "scarf_1": [("X", -40), ("Y", 20)], "scarf_2": [("X", -25)],
}
pose_preview(arm, "kai_run", RUN, azimuth=60, elevation=12)
pose_preview(arm, "kai_run_side", RUN, azimuth=90, elevation=5)
pose_preview(arm, "kai_run_back", RUN, azimuth=160, elevation=10)
