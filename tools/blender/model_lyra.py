"""Lyra — companion aether mage / artificer (~1.6 m). Exports public/models/lyra.glb (skinned).

Skeleton (RIG_SPEC.md):
    root (armature)
    └─ hips ─┬─ torso ─┬─ head ─┬─ hat_1
             │         │        ├─ hair_L_1 ─ hair_L_2,  hair_R_1 ─ hair_R_2   (side locks)
             │         │        └─ hair_B_1 ─ hair_B_2 ─ hair_B_3               (braid)
             │         ├─ arm_L ─ forearm_L
             │         └─ arm_R ─ forearm_R ─(rigid) weapon ─(rigid) staff_tip
             ├─ leg_L ─ shin_L,  leg_R ─ shin_R
             └─ skirt_F_1 ─ skirt_F_2,  skirt_B_1 ─ skirt_B_2,  skirt_L_1,  skirt_R_1
Faces -Y, character's right = -X. Staff shaft runs along +Z from the right hand.
The skirt panels are angular sectors of the original flared skirt; their weights are rewritten as
one continuous field (hero_rig_helpers.skirt_weights) so the panels never split apart.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from char_helpers import *
from rig_helpers import rig_from_parts, pose_preview, HUMANOID_TEST_POSE
from hero_rig_helpers import joint_cap, resample, loft_sector, strip, build_at, skirt_weights, limit_influences

reset_scene()
get_mat("cloth_stocking", hex="#3a2e44", metallic=0.0, roughness=0.8)
get_mat("cloth_plum", hex="#432a5c", metallic=0.0, roughness=0.85)   # darker purple (hat, trims)

root = empty("root")

HIP_Z = 0.80
LEG_Z = 0.74
WAIST_Z = 0.86
SHOULDER = (0.262, 0.0, 0.27)
NECK = 0.31
HAND = -0.40
ELBOW = -0.20         # relative to shoulder
KNEE = -0.32          # relative to hip joint
R_ELBOW, R_KNEE = 0.05, 0.05    # skin blend radii — small: the round joint caps cover the bend

# ---- hips: belt + pouches (the skirt is split into panel chains below) ---------------
p = Part("hips")
loft(p, "leather", [(0.0, 0.305, 0.235), (0.07, 0.30, 0.23)], shape="oct", cap=(False, True))  # belt
p.box("brass", size=(0.07, 0.025, 0.06), loc=(0, -0.118, 0.035))
p.box("leather_dark", size=(0.035, 0.02, 0.03), loc=(0, -0.13, 0.035))
for x, rz in ((0.13, -20), (0.165, -55)):
    p.box("leather", size=(0.07, 0.06, 0.085), loc=(x, -0.06 if rz == -20 else 0.02, -0.01), rot=(0, 0, rz))
    p.box("brass", size=(0.02, 0.065, 0.02), loc=(x, -0.06 if rz == -20 else 0.02, 0.02), rot=(0, 0, rz))
p.box("leather", size=(0.08, 0.065, 0.09), loc=(-0.15, 0.03, -0.01), rot=(0, 0, 30))
p.cyl("glass", r=0.02, h=0.06, seg=6, loc=(-0.16, -0.05, 0.0))                   # potion vial
p.cyl("glow_violet", r=0.016, h=0.035, seg=6, loc=(-0.16, -0.05, -0.012))
hips = p.build(root, loc=(0, 0, HIP_Z))

# ---- flared coat-dress skirt (hips frame) -------------------------------------------
PURPLE = [(-0.42, 0.56, 0.48), (-0.12, 0.35, 0.28), (0.02, 0.29, 0.22), (0.07, 0.28, 0.21)]  # coat skirt
CREAM = [(-0.47, 0.50, 0.44), (-0.40, 0.48, 0.42), (-0.10, 0.31, 0.25), (0.02, 0.27, 0.21)]   # underskirt
HEM = [(-0.43, 0.575, 0.495), (-0.39, 0.55, 0.47)]                                           # hem trim
SPLIT = -0.20                       # skirt_F_2 / skirt_B_2 joint height
UPPER = [SPLIT, -0.12, 0.02]        # edge loops (top part hidden under the belt is dropped)
LOWER = [-0.42, -0.30, SPLIT]
N = 10                              # 10-gon: vertex k at 18 + 36k deg (k=7 -> front, k=2 -> back)
SECTORS = {"F": (6, 8), "B": (1, 3), "L": (8, 11), "R": (3, 6)}


def skirt_part(name, sector, upper, lower):
    p = Part(name)
    k0, k1 = SECTORS[sector]
    zs = (lower[:-1] if upper else lower) + (upper if upper else []) if lower else upper
    loft_sector(p, "cloth_purple", resample(PURPLE, zs), N, k0, k1)
    if lower:
        loft_sector(p, "cloth_cream", resample(CREAM, [-0.47, -0.40, -0.28]), N, k0, k1)
        loft_sector(p, "cloth_plum", HEM, N, k0, k1)
    if sector == "F":   # cream front panel (the coat-dress opens at the front) + plum edging
        zs_p = [z for z in [0.03, -0.12, SPLIT, -0.30, -0.43]
                if (upper and z >= SPLIT) or (lower and z <= SPLIT)]

        def edge(xa, xb, ya, yb):
            pts = []
            for z in zs_p:
                f = (0.03 - z) / 0.46
                pts.append((xa + (xb - xa) * f, ya + (yb - ya) * f, z))
            return pts
        mid = edge(0.0, 0.0, -0.112, -0.245)        # centre column rides on the skirt's front ridge
        strip(p, "cloth_cream", edge(-0.03, -0.10, -0.112, -0.245), mid)
        strip(p, "cloth_cream", mid, edge(0.03, 0.10, -0.112, -0.245))
        for s in (1, -1):
            strip(p, "cloth_plum", edge(s * 0.03, s * 0.10, -0.113, -0.247),
                  edge(s * 0.045, s * 0.125, -0.113, -0.25))
    return p


f1 = build_at(skirt_part("skirt_F_1", "F", UPPER, None), hips, (0, -0.115, 0.0))
build_at(skirt_part("skirt_F_2", "F", None, LOWER), f1, (0, -0.167, SPLIT), (0, -0.115, 0.0))
b1 = build_at(skirt_part("skirt_B_1", "B", UPPER, None), hips, (0, 0.115, 0.0))
build_at(skirt_part("skirt_B_2", "B", None, LOWER), b1, (0, 0.167, SPLIT), (0, 0.115, 0.0))
build_at(skirt_part("skirt_L_1", "L", UPPER, LOWER), hips, (0.15, 0.0, 0.0))
build_at(skirt_part("skirt_R_1", "R", UPPER, LOWER), hips, (-0.15, 0.0, 0.0))

# ---- legs: thigh (hip joint -> knee) + shin (knee -> boot), leg frame ---------------
STOCKING = [(-0.42, 0.10, 0.11), (0.02, 0.13, 0.14)]


def make_leg(side, s):
    p = Part("leg_" + side)
    loft(p, "cloth_stocking", resample(STOCKING, [KNEE, KNEE + R_KNEE, 0.02]), shape="oct", cap=(False, False))
    leg = p.build(hips, loc=(s * 0.09, 0, LEG_Z - HIP_Z))
    p = Part("shin_" + side)
    loft(p, "cloth_stocking", resample(STOCKING, [-0.42, KNEE]), shape="oct", cap=(False, False))
    loft(p, "leather", [(-0.74, 0.14, 0.16, 0, -0.01), (-0.60, 0.135, 0.155, 0, -0.01),
                        (-0.40, 0.13, 0.14, 0, 0.0)], shape="oct", cap=(False, False))
    loft(p, "leather", [(-0.74, 0.12, 0.14, 0, -0.09), (-0.67, 0.11, 0.10, 0, -0.09)], shape="oct",
         cap=(False, True))                                                                       # toe
    loft(p, "leather_dark", [(-0.74, 0.145, 0.25, 0, -0.04), (-0.715, 0.145, 0.25, 0, -0.04)], shape="oct")
    loft(p, "leather_dark", [(-0.43, 0.15, 0.16), (-0.37, 0.155, 0.165)], shape="oct", cap=(False, True))  # cuff
    p.box("brass", size=(0.03, 0.02, 0.03), loc=(s * 0.03, -0.083, -0.40))
    for z in (-0.50, -0.58):
        p.box("brass_dark", size=(0.02, 0.02, 0.02), loc=(s * 0.035, -0.08, z))
    shin = build_at(p, leg, (0, 0, KNEE))
    joint_cap("knee_" + side, shin, "cloth_stocking", STOCKING, KNEE)
    return leg


leg_L = make_leg("L", 1)
leg_R = make_leg("R", -1)

# ---- torso: bodice ----------------------------------------------------------------
p = Part("torso")
loft(p, "cloth_purple", [(0.0, 0.26, 0.19), (0.14, 0.29, 0.21), (0.26, 0.34, 0.21), (0.32, 0.25, 0.17)],
     shape="oct", cap=(False, False))
p.poly("cloth_cream", [(-0.06, -0.107, 0.31), (0.06, -0.107, 0.31), (0.035, -0.107, 0.0), (-0.035, -0.107, 0.0)],
       [(0, 1, 2, 3)])
for i, z in enumerate((0.05, 0.12, 0.19)):
    p.cyl("brass", r=0.013, h=0.014, seg=6, loc=(0, -0.112, z), rot=(90, 0, 0))
# high cream collar + brooch
loft(p, "cloth_cream", [(0.29, 0.20, 0.17), (0.35, 0.17, 0.15), (0.38, 0.19, 0.17)], shape=8, cap=(False, True))
p.cyl("brass", r=0.03, h=0.02, seg=6, loc=(0, -0.087, 0.30), rot=(78, 0, 0))
gem(p, "glow_violet", r=0.02, up=0.025, seg=4, loc=(0, -0.097, 0.30))
# capelet over the shoulders
loft(p, "cloth_plum", [(0.20, 0.42, 0.26), (0.27, 0.40, 0.25), (0.33, 0.24, 0.19)], shape=10)
# satchel strap
tbox(p, "leather_dark", 0.02, 0.32, (0.035, 0.22), c0=(0.13, 0.0), c1=(-0.12, 0.0))
torso = p.build(hips, loc=(0, 0, WAIST_Z - HIP_Z))

# ---- head (head frame) ---------------------------------------------------------------
p = Part("head")
lathe(p, "skin", [(0.05, -0.02), (0.05, 0.08)], seg=8, cap=(False, False))   # neck (ends hidden)
HCZ = 0.22
p.sphere("skin", r=0.20, seg=10, rings=8, loc=(0, 0, HCZ), scale=(1.03, 0.96, 0.97))
for s in (1, -1):
    p.box("black", size=(0.046, 0.03, 0.075), loc=(s * 0.072, -0.168, HCZ - 0.035))
    p.box("glow_violet", size=(0.03, 0.01, 0.02), loc=(s * 0.072, -0.182, HCZ - 0.06))  # iris glint (aether-touched)
    p.box("white", size=(0.016, 0.01, 0.018), loc=(s * 0.08, -0.183, HCZ - 0.015))
    p.box("cloth_red", size=(0.03, 0.006, 0.013), loc=(s * 0.122, -0.141, HCZ - 0.07), rot=(0, 0, s * 37))
p.box("leather", size=(0.03, 0.01, 0.008), loc=(0, -0.19, HCZ - 0.11))
# monocle over her right eye (-X)
p.torus("brass", R=0.05, r=0.009, seg=8, seg2=3, loc=(-0.072, -0.188, HCZ - 0.035), rot=(90, 0, 0))
tube(p, "brass_dark", [(-0.115, -0.18, HCZ - 0.06), (-0.17, -0.12, HCZ - 0.12), (-0.19, -0.03, HCZ - 0.06)],
     r=0.006, seg=4)
# silver hair: cap, bangs (side locks and braid are chains below)
p.sphere("hair_silver", r=0.212, seg=10, rings=8, loc=(0, 0.02, HCZ + 0.025), scale=(1.05, 1.0, 1.0))
for x, ang, ln in ((-0.12, -20, 0.13), (-0.05, 8, 0.12), (0.03, -6, 0.13), (0.10, 18, 0.12)):
    p.cone("hair_silver", r=0.055, h=ln, seg=4, loc=(x, -0.18, HCZ + 0.08), rot=(170, ang, 0))
p.ico("hair_silver", r=0.075, loc=(0, 0.20, HCZ - 0.02))           # braid knot
# wide-brim witch hat with brass band + small gear; the bent tip is hat_1
HB = HCZ + 0.12
HAT = [(0.0, 0.34, 0.34, 0, 0.0), (0.12, 0.26, 0.26, 0, 0.01), (0.24, 0.17, 0.17, 0, 0.04),
       (0.33, 0.09, 0.09, 0, 0.10), (0.38, 0.0, 0.0, 0, 0.19)]
HAT_J = 0.20                     # hat_1 joint (above the brim)
lathe(p, "cloth_plum", [(0.0, -0.01), (0.27, -0.02), (0.28, 0.0), (0.18, 0.025), (0.0, 0.03)], seg=14,
      loc=(0, 0.01, HB))
loft(p, "cloth_plum", resample(HAT, [0.0, 0.12, HAT_J]), shape=8, loc=(0, 0.01, HB), cap=(False, False))
loft(p, "brass", [(0.015, 0.355, 0.355), (0.065, 0.335, 0.335)], shape=8, loc=(0, 0.01, HB))
p.gear("brass_dark", r=0.035, thickness=0.02, teeth=6, tooth=0.025, loc=(0.10, -0.142, HB + 0.04),
       rot=(80, 0, 35))
gem(p, "glow_violet", r=0.014, up=0.016, seg=4, loc=(0.104, -0.153, HB + 0.04), rot=(80, 0, 35))
head = p.build(torso, loc=(0, 0, NECK))

hj = resample(HAT, [HAT_J])[0]
p = Part("hat_1")
loft(p, "cloth_plum", resample(HAT, [HAT_J, 0.24, 0.33, 0.38]), shape=8, loc=(0, 0.01, HB), cap=(False, False))
build_at(p, head, (0, 0.01 + hj[4], HB + HAT_J))

# side locks: hair_X_1 (root, under the cap) -> hair_X_2 (lower half + tip)
LOCK_J = -0.06
for side, s in (("L", 1), ("R", -1)):
    LOCK = [(-0.24, 0.0, 0.0, s * 0.205, -0.02), (-0.12, 0.065, 0.09, s * 0.205, -0.01),
            (0.0, 0.08, 0.12, s * 0.195, 0.0), (0.08, 0.05, 0.08, s * 0.17, 0.01)]
    p = Part(f"hair_{side}_1")
    loft(p, "hair_silver", resample(LOCK, [LOCK_J, 0.0, 0.08]), shape=5, loc=(0, 0, HCZ), cap=(False, False))
    piv1 = (s * 0.19, 0.0, HCZ + 0.02)
    h1 = build_at(p, head, piv1)
    p = Part(f"hair_{side}_2")
    loft(p, "hair_silver", LOCK[:1] + resample(LOCK, [-0.12, LOCK_J]), shape=5, loc=(0, 0, HCZ), cap=(False, False))
    lj = resample(LOCK, [LOCK_J])[0]
    build_at(p, h1, (lj[3], lj[4], HCZ + LOCK_J), piv1)

# braid down the back: hair_B_1 (cuff + 2 beads) -> hair_B_2 (2 beads) -> hair_B_3 (2 beads + tip)
braid = [(0, 0.225, HCZ - 0.07), (0, 0.20, HCZ - 0.17), (0, 0.175, HCZ - 0.27), (0, 0.165, HCZ - 0.37),
         (0, 0.16, HCZ - 0.47), (0, 0.16, HCZ - 0.56)]
BRAID_PIV = [(0, 0.215, HCZ - 0.03), (0, 0.19, HCZ - 0.215), (0, 0.168, HCZ - 0.415)]
parent, ppiv = head, (0, 0, 0)
for j in range(3):
    p = Part(f"hair_B_{j + 1}")
    if j == 0:
        p.cyl("brass", r=0.05, h=0.035, seg=6, loc=(0, 0.212, HCZ - 0.115), rot=(-30, 0, 0))
    for i in (2 * j, 2 * j + 1):
        gem(p, "hair_silver", r=0.058 - i * 0.004, up=0.05, down=0.04, seg=6, mid=0.02, loc=braid[i],
            rot=(0, 0, 30 * (i % 2)), scale=(1, 0.85, 1))
    if j == 2:
        p.cone("hair_silver", r=0.03, h=0.08, seg=5, loc=(0, 0.16, HCZ - 0.63), rot=(180, 0, 0))
    parent = build_at(p, parent, BRAID_PIV[j], ppiv)
    ppiv = BRAID_PIV[j]

# ---- arms: upper arm (shoulder -> elbow) + forearm (elbow -> hand), arm frame ---------
SLEEVE = [(-0.27, 0.12, 0.12), (-0.04, 0.105, 0.105)]


def make_arm(side, s):
    p = Part("arm_" + side)
    p.sphere("cloth_purple", r=0.072, seg=8, rings=4, loc=(0, 0, -0.01))
    loft(p, "cloth_purple", resample(SLEEVE, [ELBOW, ELBOW + R_ELBOW, -0.04]), shape="oct", cap=(False, False))
    arm = p.build(torso, loc=(s * SHOULDER[0], SHOULDER[1], SHOULDER[2]))
    p = Part("forearm_" + side)
    loft(p, "cloth_purple", resample(SLEEVE, [-0.27, ELBOW]), shape="oct", cap=(False, False))
    loft(p, "cloth_cream", [(-0.34, 0.16, 0.16), (-0.27, 0.13, 0.13)], shape="oct", cap=(True, False))  # bell cuff
    loft(p, "brass", [(-0.275, 0.132, 0.132), (-0.26, 0.128, 0.128)], shape="oct", cap=(False, True))
    loft(p, "skin", [(-0.47, 0.09, 0.105), (-0.44, 0.105, 0.12), (-0.36, 0.10, 0.115), (-0.33, 0.08, 0.09)],
         shape="oct", cap=(True, False))
    p.box("skin", size=(0.04, 0.05, 0.06), loc=(-s * 0.05, -0.03, -0.40))           # thumb
    forearm = build_at(p, arm, (0, 0, ELBOW))
    joint_cap("elbow_" + side, forearm, "cloth_purple", SLEEVE, ELBOW)
    return arm, forearm


arm_L, forearm_L = make_arm("L", 1)
arm_R, forearm_R = make_arm("R", -1)

# ---- weapon: aether staff, shaft along +Z from the hand ----------------------------
SX, SY = -0.04, -0.085          # shaft passes through the front/outer side of the fist
p = Part("weapon")
p.cyl("wood_dark", r=0.022, h=1.48, seg=6, loc=(SX, SY, 0.49))
p.cone("brass", r=0.03, h=0.08, seg=6, loc=(SX, SY, -0.28), rot=(180, 0, 0))       # ferrule
p.cyl("leather", r=0.028, h=0.16, seg=6, loc=(SX, SY, 0.0))                         # grip wrap
for z in (0.09, -0.09, 0.75):
    p.cyl("brass", r=0.03, h=0.025, seg=6, loc=(SX, SY, z))
# head: brass cradle + violet crystal + orbiting gear ring
TOP = 1.23
p.cyl("brass", r=0.035, r2=0.05, h=0.08, seg=6, loc=(SX, SY, TOP + 0.03))
for k in range(4):
    a = math.radians(45 + 90 * k)
    dx, dy = math.cos(a) * 0.05, math.sin(a) * 0.05
    tube(p, "brass", [(SX + dx, SY + dy, TOP + 0.06), (SX + dx * 1.8, SY + dy * 1.8, TOP + 0.14),
                      (SX + dx * 1.1, SY + dy * 1.1, TOP + 0.24)], r=[0.012, 0.011, 0.0], seg=4)
CRY = TOP + 0.17
p.cone("glow_violet", r=0.065, h=0.13, seg=6, loc=(SX, SY, CRY + 0.065))
p.cone("glow_violet", r=0.065, h=0.09, seg=6, loc=(SX, SY, CRY - 0.045), rot=(180, 0, 0))
p.gear("brass", r=0.15, thickness=0.025, teeth=8, tooth=0.04, hole=0.125, loc=(SX, SY, CRY),
       rot=(90, 20, 0))
p.torus("brass_dark", R=0.115, r=0.008, seg=10, seg2=4, loc=(SX, SY, CRY), rot=(30, 70, 0))
weapon = p.build(forearm_R, loc=(0, 0, HAND - ELBOW))     # same world spot as before (hand)
empty("staff_tip", parent=weapon, loc=(SX, SY, CRY))

# ---- rig -------------------------------------------------------------------------
arm = rig_from_parts(
    root, rigid={"weapon", "staff_tip"},
    smooth={"forearm_L": R_ELBOW, "forearm_R": R_ELBOW, "shin_L": R_KNEE, "shin_R": R_KNEE,
            "hat_1": 0.10, "hair_L_2": 0.055, "hair_R_2": 0.055, "hair_B_2": 0.05, "hair_B_3": 0.05,
            "skirt_F_2": 0.08, "skirt_B_2": 0.08},
    influence={},   # skirt <- thigh influence is position-dependent: skirt_weights below
    skin_name="lyra_skin")
skin = bpy.data.objects["lyra_skin"]
# one continuous skirt: angular blend F/L/B/R, vertical blend _1 -> _2, thighs pull the hem
skirt_weights(skin, (0, 0, HIP_Z), z_attach=0.0, attach_fade=0.15, z_split=SPLIT, split_r=0.08,
              side_x=(-0.06, 0.12), k_front=0.65, k_back=0.3, leg_z=(-0.02, -0.32),
              surface=PURPLE, n=N)
limit_influences(skin, 4)

finish("lyra", budget=3100)
render_view("lyra_face", (0, 0, 1.38), 0.42, azimuth=25, elevation=8)

# ---- deformation previews (pose_preview resets to rest pose afterwards) -----------
CHAINS_SWING = {
    "skirt_F_1": [("X", -20)], "skirt_F_2": [("X", -10)],
    "skirt_B_1": [("X", 25)], "skirt_B_2": [("X", 15)],
    "skirt_L_1": [("Y", -25)], "skirt_R_1": [("Y", 25)],
    "hair_L_1": [("X", 25)], "hair_L_2": [("X", 15)],
    "hair_R_1": [("X", 25)], "hair_R_2": [("X", 15)],
    "hair_B_1": [("X", 20)], "hair_B_2": [("X", 15)], "hair_B_3": [("X", 15)],
    "hat_1": [("X", 30)],
}
pose_preview(arm, "lyra_pose", {**HUMANOID_TEST_POSE, **CHAINS_SWING})
pose_preview(arm, "lyra_pose_back", {**HUMANOID_TEST_POSE, **CHAINS_SWING}, azimuth=200, elevation=15)
RUN = {
    "torso": [("X", -8)], "head": [("X", 6)],
    "leg_L": [("X", -50)], "shin_L": [("X", 60)],
    "leg_R": [("X", 30)], "shin_R": [("X", 65)],
    "arm_L": [("X", 35)], "forearm_L": [("X", -45)],
    "arm_R": [("X", -30)], "forearm_R": [("X", -30)],
    "skirt_F_1": [("X", -15)], "skirt_F_2": [("X", -5)], "skirt_B_1": [("X", 20)], "skirt_B_2": [("X", 10)],
    "hair_L_1": [("X", 30)], "hair_R_1": [("X", 30)],
    "hair_B_1": [("X", 30)], "hair_B_2": [("X", 15)], "hair_B_3": [("X", 10)],
    "hat_1": [("X", 25)],
}
pose_preview(arm, "lyra_run", RUN, azimuth=60, elevation=12)
pose_preview(arm, "lyra_run_side", RUN, azimuth=90, elevation=5)
pose_preview(arm, "lyra_run_back", RUN, azimuth=160, elevation=10)
