"""Chapter-1 town NPCs — low-poly, flat shaded, same humanoid skeleton as kai / lyra.

Exports public/models/npc_marta.glb, npc_bail.glb, npc_poppy.glb, npc_shopkeeper.glb (skinned).

    blender -b --factory-startup -P tools/blender/model_npc.py                 # all four
    blender -b --factory-startup -P tools/blender/model_npc.py -- marta poppy  # some of them
    NPC_PREVIEW_DIR=/some/dir  ... (previews go there instead of tools/blender/previews)

Skeleton (RIG_SPEC.md "Humanoids"), identical bone names / parents to the heroes:
    root (armature)
    └─ hips ─┬─ torso ─┬─ head [─ hair_L_1, hair_R_1  (poppy pigtails)]
             │         ├─ arm_L ─ forearm_L (+ elbow_L cap)
             │         ├─ arm_R ─ forearm_R (+ elbow_R cap) ─(rigid empty) weapon   (hand marker)
             │         └─ [scarf_1 ─ scarf_2  (poppy)]
             ├─ leg_L ─ shin_L (+ knee_L cap),  leg_R ─ shin_R (+ knee_R cap)
             └─ [coat_FL_1─coat_FL_2, coat_FR_1─coat_FR_2, coat_L_1─coat_L_2, coat_R_1─coat_R_2
                 (marta / bail long coats: front quarters + vented back tails)]
                [tabard_F_1 ─ tabard_F_2  (shopkeeper apron)]
Faces -Y, character's right = -X, feet on z = 0. Style follows model_kai.py / model_lyra.py
(chibi head, Part primitives, flat shading, <= 3100 tris, joint caps at elbows and knees).

Canon notes (docs/story/WORLD.md): Marta's right arm is an old prosthesis with a gas-lamp hook;
Bail has Lyra's silver-white hair cut short and his LEFT arm is the silence-needle gauntlet.
Both are single constants in build_bail() (BAIL_HAIR / GAUNTLET_SIDE) if art direction changes.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import math
import common
from common import *
from char_helpers import *
from rig_helpers import rig_from_parts, pose_preview, HUMANOID_TEST_POSE
from hero_rig_helpers import (joint_cap, resample, loft_sector, build_at, skirt_weights,
                              limit_influences, ss)

if os.environ.get("NPC_PREVIEW_DIR"):
    common.PREVIEW_DIR = os.environ["NPC_PREVIEW_DIR"]


# =========================================================================================
# shared helpers
# =========================================================================================

class Body:
    """Key heights of one character (world z for *_Z, part-relative otherwise)."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def face_y(B, x, z, inset=0.0):
    """y of the front surface of the head ellipsoid at head-frame (x, z) (head pivot = neck)."""
    sx, sy, sz = B.HSCALE
    u = 1.0 - (x / (sx * B.HR)) ** 2 - ((z - B.HCZ) / (sz * B.HR)) ** 2
    return -sy * B.HR * math.sqrt(max(0.0, u)) + inset


def head_base(p, B, skin="skin", neck_r=0.055, ears=True):
    lathe(p, skin, [(neck_r, -0.03), (neck_r, 0.09)], seg=8, cap=(False, False))
    p.sphere(skin, r=B.HR, seg=10, rings=8, loc=(0, 0, B.HCZ), scale=B.HSCALE)
    if ears:
        for s in (1, -1):
            p.sphere(skin, r=0.042 * B.HR / 0.2, seg=6, rings=4,
                     loc=(s * B.HR * B.HSCALE[0] * 0.98, 0.01, B.HCZ - 0.012), scale=(0.6, 1, 1))


def eyes(p, B, w, h, x, z, white=(0.016, 0.018), iris=None, gap=0.03):
    """Kai-style block eyes on the face surface (+ highlight, optional coloured glint)."""
    for s in (1, -1):
        y = face_y(B, x, z) + 0.008
        p.box("black", size=(w, gap, h), loc=(s * x, y, z))
        p.box("white", size=(white[0], 0.01, white[1]),
              loc=(s * (x + w * 0.15), y - gap / 2 - 0.002, z + h * 0.22))
        if iris:
            p.box(iris, size=(w * 0.6, 0.01, h * 0.25), loc=(s * x, y - gap / 2 - 0.001, z - h * 0.28))


def brows(p, B, mat, x, z, w=0.065, h=0.016, tilt=8.0, d=0.02):
    """tilt > 0: inner ends up (soft/worried); < 0: inner ends down (stern)."""
    for s in (1, -1):
        p.box(mat, size=(w, d, h), loc=(s * x, face_y(B, x, z) + 0.004, z), rot=(0, s * tilt, 0))


def boot(p, s, zb, k=1.0, mat="leather", sole="leather_dark", h=0.31, cuff=True, buckle=True):
    """Kai's chunky boot scaled by k; zb = sole bottom in the leg frame."""
    w, d = 0.16 * k, 0.18 * k
    loft(p, mat, [(zb, w, d, 0, -0.01 * k), (zb + 0.14 * k, w, d, 0, -0.01 * k),
                  (zb + h * k, w * 0.97, d * 0.92, 0, 0.0)], shape="oct", cap=(False, False))
    loft(p, mat, [(zb, w * 0.94, d * 0.89, 0, -0.11 * k), (zb + 0.09 * k, w * 0.88, d * 0.67, 0, -0.11 * k)],
         shape="oct", cap=(False, True))
    loft(p, sole, [(zb, w * 1.06, d * 1.6, 0, -0.045 * k), (zb + 0.03 * k, w * 1.06, d * 1.6, 0, -0.045 * k)],
         shape="oct")
    if cuff:
        loft(p, sole, [(zb + (h - 0.03) * k, w * 1.06, d * 1.03), (zb + (h + 0.04) * k, w * 1.09, d * 1.06)],
             shape="oct", cap=(False, True))
    if buckle:
        p.box("brass", size=(0.03 * k, 0.02, 0.03 * k), loc=(s * 0.02 * k, -d * 0.53 - 0.004, zb + 0.17 * k))


def make_legs(hips, B, mat, profile, shin_extra, cap_mat=None):
    """Thigh (hip joint -> knee) + shin (knee -> foot) per side, Kai layout. profile in leg frame."""
    top = profile[-1][0]
    bot = profile[0][0]
    for side, s in (("L", 1), ("R", -1)):
        p = Part("leg_" + side)
        loft(p, mat, resample(profile, [B.KNEE, B.KNEE + 0.05, top]), shape="oct", cap=(False, False))
        leg = p.build(hips, loc=(s * B.LEG_X, 0, B.LEG_Z - B.HIP_Z))
        p = Part("shin_" + side)
        loft(p, mat, resample(profile, [bot, B.KNEE]), shape="oct", cap=(False, False))
        shin_extra(p, side, s)
        shin = build_at(p, leg, (0, 0, B.KNEE))
        joint_cap("knee_" + side, shin, cap_mat or mat, profile, B.KNEE)


def make_arm(torso, B, side, s, upper_mat, upper_profile, lower_fn, cap_mat=None, cap_profile=None,
             shoulder_r=0.08, shoulder_mat=None, upper_extra=None):
    """arm_* (shoulder -> elbow) + forearm_* (elbow -> hand); lower_fn(p, side, s) adds the forearm,
    cuff and hand in the ARM frame (z relative to the shoulder)."""
    p = Part("arm_" + side)
    p.sphere(shoulder_mat or upper_mat, r=shoulder_r, seg=8, rings=6, loc=(0, 0, -0.01))
    loft(p, upper_mat, resample(upper_profile, [B.ELBOW, B.ELBOW + 0.05, upper_profile[-1][0]]),
         shape="oct", cap=(False, False))
    if upper_extra:
        upper_extra(p, side, s)
    arm = p.build(torso, loc=(s * B.SHOULDER[0], B.SHOULDER[1], B.SHOULDER[2]))
    p = Part("forearm_" + side)
    lower_fn(p, side, s)
    forearm = build_at(p, arm, (0, 0, B.ELBOW))
    joint_cap("elbow_" + side, forearm, cap_mat or upper_mat, cap_profile or upper_profile, B.ELBOW)
    return arm, forearm


def mitten(p, s, B, mat, z0, w=0.11, d=0.13, thumb_mat=None, k=1.0):
    """Chunky mitten hand (Kai's glove block) hanging below z0 (arm frame)."""
    loft(p, mat, [(z0 - 0.16 * k, w * 0.85, d * 0.86), (z0 - 0.13 * k, w, d * 1.1), (z0 - 0.03 * k, w, d * 1.08),
                  (z0, w * 0.85, d * 0.92)], shape="oct", cap=(True, False))
    p.box(thumb_mat or mat, size=(0.042 * k, 0.055 * k, 0.065 * k), loc=(-s * 0.055 * k, -0.035 * k, z0 - 0.07 * k))


# ---- long coat skirt: angular sectors of one 16-gon loft, split into chains -------------
N_COAT = 16       # phase 0: vertex k at 22.5*k deg -> k=0 left (+X), 4 back, 8 right, 12 front


def ring_pt(profile, z, k, n=N_COAT):
    _, w, d, cx, cy = resample(profile, [z])[0]
    a = 2 * math.pi * k / n
    return (cx + w / 2 * math.cos(a), cy + d / 2 * math.sin(a), z)


def coat_chains(hips, profile, mat, panels, z_top, z_split, z_hem, hem_mat=None, hem_h=0.05, hem_out=0.012,
                extra_upper=None):
    """panels: {base_name: (k0, k1)} -> base_1 (belt .. split) and base_2 (split .. hem) per panel.
    Returns {base: (piv1, piv2)} in the hips frame."""
    upper = [z_split, (z_split + z_top) / 2, z_top]
    lower = [z_hem, (z_hem + z_split) / 2, z_split]
    hem = [(z_hem - 0.005, ) + resample(profile, [z_hem])[0][1:3],
           (z_hem + hem_h, ) + resample(profile, [z_hem + hem_h])[0][1:3]]
    hem = [(z, w + 2 * hem_out, d + 2 * hem_out) for (z, w, d) in hem]
    piv = {}
    for base, (k0, k1) in panels.items():
        km = (k0 + k1) / 2.0
        p1 = ring_pt(profile, z_top, km)
        p2 = ring_pt(profile, z_split, km)
        p = Part(base + "_1")
        loft_sector(p, mat, resample(profile, upper), N_COAT, k0, k1, phase=0.0)
        if extra_upper:
            extra_upper(p, base, k0, k1)
        c1 = build_at(p, hips, p1)
        p = Part(base + "_2")
        loft_sector(p, mat, resample(profile, lower), N_COAT, k0, k1, phase=0.0)
        if hem_mat:
            loft_sector(p, hem_mat, hem, N_COAT, k0, k1, phase=0.0)
        build_at(p, c1, p2, p1)
        piv[base] = (p1, p2)
    return piv


COAT_PANELS_WIDE = {"coat_FL": (14, 16), "coat_L": (0, 4), "coat_R": (4, 8), "coat_FR": (8, 10)}
COAT_PANELS_CLOSED = {"coat_FL": (13, 16), "coat_L": (0, 4), "coat_R": (4, 8), "coat_FR": (8, 11)}


def coat_dirs(panels):
    out = {}
    for base, (k0, k1) in panels.items():
        out[base.split("_")[1]] = ((k0 + k1) / 2.0 * 360.0 / N_COAT % 360.0, [base + "_1", base + "_2"])
    return out


# ---- rig / export / previews -------------------------------------------------------------
BASE_SMOOTH = {"forearm_L": 0.05, "forearm_R": 0.05, "shin_L": 0.05, "shin_R": 0.05}
RUN = {
    "torso": [("X", -8)], "head": [("X", 6)],
    "leg_L": [("X", -50)], "shin_L": [("X", 60)],
    "leg_R": [("X", 30)], "shin_R": [("X", 65)],
    "arm_L": [("X", 35)], "forearm_L": [("X", -45)],
    "arm_R": [("X", -40)], "forearm_R": [("X", -50)],
}


def finalize(name, root, B, smooth=None, weights=None, swing=None, run_swing=None):
    arm = rig_from_parts(root, rigid={"weapon"}, smooth={**BASE_SMOOTH, **(smooth or {})},
                         influence={}, skin_name=name + "_skin")
    skin = bpy.data.objects[name + "_skin"]
    if weights:
        weights(skin)
    limit_influences(skin, 4)
    tris = finish(name, budget=3100)
    render_view(name + "_face", (0, 0, B.FACE_Z), B.FACE_R, azimuth=25, elevation=8)
    pose_preview(arm, name + "_pose", {**HUMANOID_TEST_POSE, **(swing or {})})
    pose_preview(arm, name + "_run", {**RUN, **(run_swing or {})}, azimuth=60, elevation=12)
    pose_preview(arm, name + "_run_side", {**RUN, **(run_swing or {})}, azimuth=90, elevation=5)
    zs = [(arm.matrix_world @ v.co).z for o in bpy.context.scene.objects if o.type == "MESH"
          for v in o.data.vertices]
    print(f"[npc] {name}: tris={tris} height={max(zs):.3f} min_z={min(zs):.3f}")
    return arm


def coat_weights(B, panels, z_split, leg_z, k_front=0.6, k_back=0.3, split_r=0.09):
    def fn(skin):
        skirt_weights(skin, (0, 0, B.HIP_Z), dirs=coat_dirs(panels), prefix="coat_",
                      z_attach=0.03, attach_fade=0.12, z_split=z_split, split_r=split_r,
                      side_x=(-0.06, 0.12), k_front=k_front, k_back=k_back, leg_z=leg_z, sharp=2.0)
    return fn


COAT_SWING = {"coat_FL_1": [("X", -15)], "coat_FR_1": [("X", -10)], "coat_L_1": [("X", 25)],
              "coat_R_1": [("X", 20)], "coat_L_2": [("X", 10)], "coat_R_2": [("X", 10)]}
COAT_RUN = {"coat_FL_1": [("X", -25)], "coat_FR_1": [("X", 12)], "coat_L_1": [("X", 20)],
            "coat_R_1": [("X", 30)], "coat_L_2": [("X", 10)], "coat_R_2": [("X", 10)]}


# =========================================================================================
# 마르타 Marta — courier-union branch chief (~1.70 m)
# =========================================================================================

def build_marta():
    reset_scene()
    get_mat("cloth_coat_green", hex="#2f4a3a", metallic=0.0, roughness=0.85)
    get_mat("cloth_green_dark", hex="#1f3328", metallic=0.0, roughness=0.85)
    get_mat("cloth_charcoal", hex="#33343d", metallic=0.0, roughness=0.85)
    get_mat("hair_grey", hex="#a3a3a8", metallic=0.0, roughness=0.7)
    get_mat("skin_tan", hex="#e2b48e", metallic=0.0, roughness=0.6)
    B = Body(HIP_Z=0.84, LEG_Z=0.78, LEG_X=0.105, WAIST_Z=0.91, SHOULDER=(0.30, 0.0, 0.28), NECK=0.36,
             ELBOW=-0.20, HAND=-0.40, KNEE=-0.37, HR=0.205, HCZ=0.215, HSCALE=(1.05, 0.96, 0.95),
             FACE_Z=1.48, FACE_R=0.42)
    root = empty("root")

    # hips: trousers seat + belt (coat skirt chains below)
    p = Part("hips")
    loft(p, "cloth_charcoal", [(-0.12, 0.31, 0.21), (0.0, 0.34, 0.23), (0.08, 0.34, 0.23)], shape="oct")
    loft(p, "leather_dark", [(0.0, 0.385, 0.275), (0.07, 0.385, 0.275)], shape="oct")
    p.box("brass", size=(0.08, 0.03, 0.065), loc=(0, -0.14, 0.035))
    p.box("leather_dark", size=(0.04, 0.02, 0.035), loc=(0, -0.152, 0.035))
    # courier satchel on her left hip (strap runs up over the chest)
    tbox(p, "leather", -0.20, 0.0, (0.10, 0.22), (0.09, 0.21), c0=(0.245, 0.0), c1=(0.235, 0.0))
    tbox(p, "leather_dark", -0.07, 0.01, (0.112, 0.225), c0=(0.248, 0.0))                 # flap
    p.box("brass", size=(0.02, 0.05, 0.035), loc=(0.305, 0.0, -0.075))
    p.box("cloth_cream", size=(0.06, 0.12, 0.05), loc=(0.235, -0.02, 0.02), rot=(0, 0, 8))  # letters
    hips = p.build(root, loc=(0, 0, B.HIP_Z))

    # knee-length coat skirt, open at the front
    COAT = [(-0.45, 0.54, 0.44), (-0.20, 0.45, 0.35), (0.0, 0.385, 0.28), (0.06, 0.38, 0.275)]
    SPLIT = -0.21

    def coat_front_buttons(p, base, k0, k1):
        if base in ("coat_FL", "coat_FR"):
            k = k0 if base == "coat_FL" else k1
            for z in (-0.06, -0.15):
                x, y, _ = ring_pt(COAT, z, k)
                p.cyl("brass", r=0.017, h=0.016, seg=6, loc=(x * 0.93, y - 0.006, z), rot=(90, 0, 0))
    coat_chains(hips, COAT, "cloth_coat_green", COAT_PANELS_WIDE, 0.04, SPLIT, -0.45,
                hem_mat="cloth_green_dark", extra_upper=coat_front_buttons)

    TROUSER = [(-0.46, 0.13, 0.14), (-0.23, 0.14, 0.15), (0.04, 0.16, 0.17)]

    def shin_extra(p, side, s):
        boot(p, s, -0.77, k=1.0, h=0.30)
    make_legs(hips, B, "cloth_charcoal", TROUSER, shin_extra)

    # torso: double-breasted coat, turned-up collar, satchel strap, radio handset
    p = Part("torso")
    loft(p, "cloth_coat_green", [(0.0, 0.37, 0.27), (0.14, 0.41, 0.29), (0.27, 0.45, 0.27), (0.35, 0.33, 0.21)],
         shape="oct", cap=(False, True))
    p.poly("cloth_cream", [(-0.06, -0.137, 0.35), (0.06, -0.137, 0.35), (0.0, -0.144, 0.24)], [(0, 1, 2)])
    for s in (1, -1):
        p.poly("cloth_green_dark", [(s * 0.06, -0.139, 0.35), (s * 0.16, -0.132, 0.32), (s * 0.012, -0.147, 0.22)],
               [(0, 1, 2)])                                                                  # lapels
        for i, z in enumerate((0.05, 0.12, 0.19)):
            p.cyl("brass", r=0.019, h=0.016, seg=6, loc=(s * 0.075, -0.142 - 0.003 * i, z), rot=(90, 0, 0))
        p.box("cloth_green_dark", size=(0.13, 0.13, 0.03), loc=(s * 0.225, 0.0, 0.33), rot=(0, s * 14, 0))
        p.cyl("brass", r=0.016, h=0.012, seg=6, loc=(s * 0.27, -0.03, 0.33), rot=(0, s * 14, 0))
    loft(p, "cloth_green_dark", [(0.32, 0.30, 0.23), (0.37, 0.27, 0.215), (0.43, 0.29, 0.23)], shape=8,
         cap=(False, False))                                                                 # collar
    tbox(p, "leather_dark", 0.02, 0.34, (0.045, 0.30), c0=(0.15, 0.0), c1=(-0.14, 0.0))       # strap
    # radio handset clipped to the strap (her right chest)
    p.box("iron", size=(0.065, 0.045, 0.12), loc=(-0.10, -0.158, 0.24), rot=(0, 30, 0))
    p.box("brass", size=(0.05, 0.012, 0.035), loc=(-0.112, -0.183, 0.27), rot=(0, 30, 0))
    p.cyl("brass_dark", r=0.007, h=0.12, seg=4, loc=(-0.07, -0.16, 0.34), rot=(0, 30, 0))
    p.sphere("glow_amber", r=0.012, seg=6, rings=4, loc=(-0.04, -0.16, 0.395))
    torso = p.build(hips, loc=(0, 0, B.WAIST_Z - B.HIP_Z))

    # head: short grey hair, courier peaked cap, radio headset, stern brows
    p = Part("head")
    head_base(p, B, skin="skin_tan")
    eyes(p, B, 0.045, 0.055, 0.078, B.HCZ - 0.035)
    brows(p, B, "hair_grey", 0.078, B.HCZ + 0.012, w=0.075, h=0.022, tilt=-14, d=0.024)
    p.box("leather", size=(0.06, 0.01, 0.01), loc=(0, face_y(B, 0, B.HCZ - 0.115) + 0.002, B.HCZ - 0.115))
    p.box("skin_tan", size=(0.035, 0.03, 0.04), loc=(0, face_y(B, 0, B.HCZ - 0.065) - 0.005, B.HCZ - 0.065))  # nose
    p.sphere("hair_grey", r=B.HR * 1.07, seg=10, rings=8, loc=(0, 0.03, B.HCZ + 0.035), scale=(1.04, 0.98, 0.95))
    for s in (1, -1):
        for y, z in ((-0.06, -0.02), (0.04, -0.05), (0.13, -0.04)):
            p.cone("hair_grey", r=0.05, h=0.11, seg=4, loc=(s * 0.19, y, B.HCZ + z), rot=(180, s * -12, 0))
    for x in (-0.08, 0.0, 0.08):   # short tapered nape
        p.cone("hair_grey", r=0.055, h=0.09, seg=4, loc=(x, 0.165 - abs(x) * 0.3, B.HCZ - 0.10), rot=(200, 0, 0))
    # peaked courier cap
    HB = B.HCZ + 0.10
    loft(p, "cloth_coat_green", [(0.0, 0.43, 0.43, 0, 0.01), (0.07, 0.45, 0.45, 0, 0.0),
                                 (0.11, 0.47, 0.47, 0, -0.01), (0.135, 0.36, 0.36, 0, -0.01),
                                 (0.145, 0.0, 0.0, 0, -0.01)], shape=10, loc=(0, 0.0, HB))
    loft(p, "leather_dark", [(0.0, 0.445, 0.445, 0, 0.01), (0.045, 0.445, 0.445, 0, 0.01)], shape=10,
         loc=(0, 0.0, HB))
    prism(p, "leather_dark", [(-0.17, -0.0), (0.17, -0.0), (0.15, -0.08), (0.08, -0.12), (-0.08, -0.12),
                              (-0.15, -0.08)], 0.016, loc=(0, -0.20, HB + 0.005), rot=(18, 0, 0), axis="z")
    p.box("brass", size=(0.07, 0.02, 0.05), loc=(0, -0.235, HB + 0.075))                      # union badge
    p.box("brass_dark", size=(0.03, 0.01, 0.02), loc=(0, -0.246, HB + 0.075))
    # radio headset: band over the cap, earcup + antenna on her left, mic boom to the mouth
    band = [(math.cos(math.radians(a)) * 0.245, 0.01, HB + 0.02 + math.sin(math.radians(a)) * 0.125)
            for a in (0, 35, 70, 90, 110, 145, 180)]
    tube(p, "iron", band, r=0.012, seg=4)
    p.cyl("iron", r=0.06, h=0.05, seg=8, loc=(0.235, 0.01, B.HCZ - 0.005), rot=(0, 90, 0))
    p.cyl("brass", r=0.045, h=0.02, seg=8, loc=(0.262, 0.01, B.HCZ - 0.005), rot=(0, 90, 0))
    p.cyl("iron", r=0.04, h=0.04, seg=6, loc=(-0.23, 0.01, B.HCZ - 0.005), rot=(0, 90, 0))
    p.cyl("brass_dark", r=0.006, h=0.16, seg=4, loc=(0.27, 0.04, B.HCZ + 0.10), rot=(-8, 12, 0))
    p.sphere("glow_amber", r=0.013, seg=6, rings=4, loc=(0.286, 0.051, B.HCZ + 0.18))
    tube(p, "iron", [(0.24, -0.04, B.HCZ - 0.03), (0.20, -0.14, B.HCZ - 0.09), (0.11, -0.20, B.HCZ - 0.115)],
         r=0.008, seg=4)
    p.cyl("black", r=0.017, h=0.03, seg=6, loc=(0.10, -0.205, B.HCZ - 0.115), rot=(0, 90, 0))
    head = p.build(torso, loc=(0, 0, B.NECK))

    SLEEVE = [(-0.30, 0.125, 0.125), (-0.05, 0.14, 0.14)]

    def lower_left(p, side, s):
        loft(p, "cloth_coat_green", resample(SLEEVE, [-0.30, B.ELBOW]), shape="oct", cap=(False, False))
        loft(p, "cloth_green_dark", [(-0.36, 0.155, 0.155), (-0.28, 0.15, 0.15)], shape="oct")
        p.cyl("brass", r=0.012, h=0.012, seg=6, loc=(s * 0.05, -0.075, -0.33), rot=(90, 0, 0))
        mitten(p, s, B, "leather", -0.35, w=0.115, d=0.135)

    def lower_prosthetic(p, side, s):
        # coat sleeve ends in a wide cuff just below the elbow; an old brass/iron arm comes out of it
        loft(p, "cloth_coat_green", resample(SLEEVE, [-0.27, B.ELBOW]), shape="oct", cap=(False, False))
        loft(p, "cloth_green_dark", [(-0.30, 0.165, 0.165), (-0.25, 0.16, 0.16)], shape="oct")
        loft(p, "iron", [(-0.40, 0.065, 0.065), (-0.30, 0.08, 0.08)], shape=6, cap=(True, False))
        for z in (-0.33, -0.385):
            p.cyl("brass", r=0.05, h=0.02, seg=6, loc=(0, 0, z))
        p.cyl("brass_dark", r=0.012, h=0.10, seg=4, loc=(-s * 0.05, -0.02, -0.35))        # piston
        p.sphere("brass", r=0.045, seg=6, rings=4, loc=(0, 0, -0.42))                     # wrist ball
        # gas-lamp hook: shank down, then curls forward and up
        hook = [(0, 0, -0.43), (0, 0, -0.52), (0, -0.02, -0.57), (0, -0.07, -0.59), (0, -0.11, -0.565),
                (0, -0.12, -0.52)]
        tube(p, "steel", hook, r=[0.02, 0.019, 0.018, 0.017, 0.016, 0.01], seg=5)
        p.cyl("brass_dark", r=0.03, h=0.02, seg=6, loc=(0, 0, -0.46))
    arm_L, forearm_L = make_arm(torso, B, "L", 1, "cloth_coat_green", SLEEVE, lower_left, shoulder_r=0.09)
    arm_R, forearm_R = make_arm(torso, B, "R", -1, "cloth_coat_green", SLEEVE, lower_prosthetic,
                                shoulder_r=0.09)
    empty("weapon", parent=forearm_R, loc=(0, 0, B.HAND - B.ELBOW))

    finalize("npc_marta", root, B,
             smooth={"coat_FL_2": 0.09, "coat_FR_2": 0.09, "coat_L_2": 0.09, "coat_R_2": 0.09},
             weights=coat_weights(B, COAT_PANELS_WIDE, SPLIT, (-0.02, -0.40), k_front=0.6),
             swing=COAT_SWING, run_swing=COAT_RUN)


# =========================================================================================
# 바일 Bail — tuning-council silence enforcer, Lyra's brother (~1.85 m)
# =========================================================================================

def build_bail():
    BAIL_HAIR = "hair_silver"          # WORLD.md: Lyra's silver-white hair, cut short
    GAUNTLET_SIDE = "L"                # WORLD.md: the whole LEFT arm is the needle gauntlet
    reset_scene()
    get_mat("cloth_silver", hex="#9aa0a8", metallic=0.0, roughness=0.75)
    get_mat("cloth_slate", hex="#474c56", metallic=0.0, roughness=0.8)
    get_mat("cloth_black", hex="#25262c", metallic=0.0, roughness=0.85)
    get_mat("leather_black", hex="#1c1c20", metallic=0.0, roughness=0.6)
    get_mat("glow_ice", hex="#bfe4ff", emission="#bfe4ff", strength=5.0)
    B = Body(HIP_Z=0.95, LEG_Z=0.89, LEG_X=0.095, WAIST_Z=1.02, SHOULDER=(0.275, 0.0, 0.31), NECK=0.38,
             ELBOW=-0.23, HAND=-0.45, KNEE=-0.43, HR=0.198, HCZ=0.215, HSCALE=(1.0, 0.97, 1.0),
             FACE_Z=1.62, FACE_R=0.42)
    root = empty("root")

    p = Part("hips")
    loft(p, "cloth_black", [(-0.12, 0.28, 0.20), (0.0, 0.31, 0.215), (0.08, 0.31, 0.215)], shape="oct")
    loft(p, "leather_black", [(0.0, 0.345, 0.255), (0.07, 0.345, 0.255)], shape="oct")
    p.box("steel", size=(0.075, 0.03, 0.06), loc=(0, -0.13, 0.035))
    p.box("leather_black", size=(0.04, 0.02, 0.03), loc=(0, -0.142, 0.035))
    # needle case on the right hip
    p.box("gunmetal", size=(0.07, 0.11, 0.13), loc=(-0.19, 0.02, -0.02))
    for y in (-0.01, 0.02, 0.05):
        p.cyl("steel", r=0.007, h=0.05, seg=4, loc=(-0.19, y, 0.065))
    hips = p.build(root, loc=(0, 0, B.HIP_Z))

    # long officer coat to mid-shin, narrow front opening, vented back
    COAT = [(-0.66, 0.50, 0.42), (-0.30, 0.41, 0.32), (0.0, 0.345, 0.255), (0.06, 0.34, 0.25)]
    SPLIT = -0.28

    def coat_trim(p, base, k0, k1):
        if base in ("coat_FL", "coat_FR"):       # slate piping along the front edge
            k = k0 if base == "coat_FL" else k1
            for z in (-0.08, -0.18):
                x, y, _ = ring_pt(COAT, z, k)
                p.cyl("steel", r=0.014, h=0.014, seg=6, loc=(x * 0.9, y - 0.006, z), rot=(90, 0, 0))
    coat_chains(hips, COAT, "cloth_silver", COAT_PANELS_CLOSED, 0.04, SPLIT, -0.66,
                hem_mat="cloth_slate", hem_h=0.06, extra_upper=coat_trim)

    TROUSER = [(-0.52, 0.12, 0.13), (-0.26, 0.13, 0.14), (0.04, 0.15, 0.16)]

    def shin_extra(p, side, s):    # tall black riding boots up to just below the knee
        boot(p, s, -0.88, k=0.95, mat="leather_black", sole="leather_black", h=0.36, cuff=False, buckle=False)
        loft(p, "leather_black", [(-0.56, 0.14, 0.155), (-0.48, 0.15, 0.165)], shape="oct", cap=(False, True))
        p.box("steel", size=(0.03, 0.02, 0.025), loc=(s * 0.03, -0.085, -0.60))
    make_legs(hips, B, "cloth_black", TROUSER, shin_extra)

    p = Part("torso")
    loft(p, "cloth_silver", [(0.0, 0.29, 0.21), (0.16, 0.34, 0.225), (0.31, 0.41, 0.23), (0.38, 0.29, 0.19)],
         shape="oct", cap=(False, True))
    # double-breasted front: slate placket + two rows of steel buttons
    p.poly("cloth_slate", [(-0.03, -0.114, 0.36), (0.03, -0.114, 0.36), (0.03, -0.107, 0.0), (-0.03, -0.107, 0.0)],
           [(0, 1, 2, 3)])
    for s in (1, -1):
        for i, z in enumerate((0.05, 0.13, 0.21, 0.29)):
            p.cyl("steel", r=0.014, h=0.014, seg=6, loc=(s * 0.06, -0.113 - 0.0025 * i, z), rot=(90, 0, 0))
        # shoulder boards
        p.box("cloth_slate", size=(0.12, 0.10, 0.02), loc=(s * 0.21, 0.0, 0.355), rot=(0, s * 12, 0))
        p.box("steel", size=(0.02, 0.10, 0.025), loc=(s * 0.265, 0.0, 0.343), rot=(0, s * 12, 0))
    # high stand collar
    loft(p, "cloth_silver", [(0.34, 0.22, 0.185), (0.40, 0.20, 0.175), (0.46, 0.215, 0.185)], shape=8,
         cap=(False, False))
    loft(p, "cloth_slate", [(0.455, 0.22, 0.19), (0.475, 0.22, 0.19)], shape=8, cap=(False, False))
    # needle bandolier: left shoulder -> right hip
    tbox(p, "leather_black", 0.02, 0.36, (0.04, 0.245), c0=(-0.13, 0.0), c1=(0.14, 0.0))
    for i in range(4):
        f = 0.25 + 0.15 * i
        x, z = 0.14 - 0.27 * f, 0.36 - 0.34 * f
        p.cyl("steel", r=0.009, h=0.09, seg=4, loc=(x, -0.133, z), rot=(0, -38, 0))
        p.sphere("glow_ice", r=0.012, seg=4, rings=3, loc=(x - 0.028, -0.135, z + 0.035))
    p.box("cloth_slate", size=(0.20, 0.02, 0.045), loc=(0, 0.112, 0.04))                     # back half-belt
    for s in (1, -1):
        p.cyl("steel", r=0.013, h=0.012, seg=6, loc=(s * 0.08, 0.124, 0.04), rot=(90, 0, 0))
    torso = p.build(hips, loc=(0, 0, B.WAIST_Z - B.HIP_Z))

    p = Part("head")
    head_base(p, B, neck_r=0.052)
    # narrow, calm eyes with an ice-grey glint; level brows; no blush
    eyes(p, B, 0.05, 0.034, 0.072, B.HCZ - 0.035, white=(0.012, 0.01), iris="glow_ice")
    brows(p, B, BAIL_HAIR, 0.074, B.HCZ + 0.012, w=0.07, h=0.012, tilt=-4)
    for s in (1, -1):   # sharp upper lids: a cool, level gaze
        z = B.HCZ - 0.014
        p.box("black", size=(0.064, 0.012, 0.01), loc=(s * 0.074, face_y(B, 0.074, z) - 0.004, z), rot=(0, s * -7, 0))
    p.box("leather", size=(0.032, 0.01, 0.007), loc=(0, face_y(B, 0, B.HCZ - 0.11) + 0.002, B.HCZ - 0.11))
    # short, neat hair: cap + side-swept fringe, tapered at the back
    p.sphere(BAIL_HAIR, r=B.HR * 1.065, seg=10, rings=8, loc=(0, 0.025, B.HCZ + 0.03), scale=(1.03, 1.0, 0.98))
    for x, ang, ln in ((-0.12, -62, 0.13), (-0.05, -66, 0.14), (0.03, -70, 0.13), (0.10, -72, 0.10)):
        p.cone(BAIL_HAIR, r=0.045, h=ln, seg=4, loc=(x, face_y(B, x, B.HCZ + 0.10) - 0.02, B.HCZ + 0.10),
               rot=(172, ang, 0))
    for s in (1, -1):
        p.cone(BAIL_HAIR, r=0.045, h=0.09, seg=4, loc=(s * 0.19, -0.02, B.HCZ - 0.01), rot=(180, s * -8, 0))
    p.cone(BAIL_HAIR, r=0.07, h=0.10, seg=4, loc=(0, 0.17, B.HCZ - 0.02), rot=(165, 0, 0))
    head = p.build(torso, loc=(0, 0, B.NECK))

    SLEEVE = [(-0.33, 0.115, 0.115), (-0.05, 0.125, 0.125)]

    def lower_coat(p, side, s):
        loft(p, "cloth_silver", resample(SLEEVE, [-0.33, B.ELBOW]), shape="oct", cap=(False, False))
        loft(p, "cloth_slate", [(-0.39, 0.14, 0.14), (-0.32, 0.135, 0.135)], shape="oct")
        mitten(p, s, B, "white", -0.385, w=0.105, d=0.125)                 # officer's white glove

    # the gauntlet: black armour plates, launcher barrel along the forearm, needle pointing down
    GAUNT = [(-0.33, 0.14, 0.15), (-0.05, 0.12, 0.12)]

    def upper_gauntlet(p, side, s):
        for i, (z, w) in enumerate(((0.02, 0.15), (-0.045, 0.15), (-0.105, 0.14))):   # layered pauldron
            p.box("gunmetal", size=(w, 0.17 - 0.012 * i, 0.055), loc=(s * (0.035 + 0.008 * i), 0, z),
                  rot=(0, s * (24 - 6 * i), 0))
        p.box("steel", size=(0.14, 0.012, 0.012), loc=(s * 0.035, -0.087, 0.02), rot=(0, s * 24, 0))
        p.box("glow_ice", size=(0.012, 0.012, 0.012), loc=(s * 0.09, -0.088, -0.02))

    def lower_gauntlet(p, side, s):
        loft(p, "gunmetal", [(-0.37, 0.13, 0.14), (-0.30, 0.15, 0.16), (B.ELBOW - 0.01, 0.135, 0.14)],
             shape="oct", cap=(True, False))
        p.box("leather_black", size=(0.16, 0.17, 0.03), loc=(0, 0, -0.30))
        # launcher housing on the outer side of the forearm
        p.cyl("leather_black", r=0.045, h=0.20, seg=6, loc=(s * 0.08, 0.0, -0.29))
        p.cyl("steel", r=0.05, h=0.02, seg=6, loc=(s * 0.08, 0.0, -0.20))
        p.cyl("steel", r=0.05, h=0.02, seg=6, loc=(s * 0.08, 0.0, -0.37))
        p.box("glow_ice", size=(0.012, 0.012, 0.13), loc=(s * 0.127, 0.0, -0.29))
        p.cone("steel", r=0.012, h=0.08, seg=4, loc=(s * 0.08, 0.0, -0.42), rot=(180, 0, 0))    # needle
        # armoured fist
        loft(p, "leather_black", [(-0.53, 0.10, 0.12), (-0.50, 0.125, 0.15), (-0.40, 0.125, 0.15),
                                  (-0.37, 0.11, 0.13)], shape="oct", cap=(True, False))
        for z in (-0.44, -0.49):
            p.box("gunmetal", size=(0.13, 0.03, 0.035), loc=(0, -0.07, z))
        p.box("leather_black", size=(0.045, 0.06, 0.07), loc=(-s * 0.065, -0.035, -0.45))
    if GAUNTLET_SIDE == "L":
        make_arm(torso, B, "L", 1, "gunmetal", GAUNT, lower_gauntlet, upper_extra=upper_gauntlet,
                 shoulder_r=0.085)
        arm_R, forearm_R = make_arm(torso, B, "R", -1, "cloth_silver", SLEEVE, lower_coat)
    else:
        make_arm(torso, B, "L", 1, "cloth_silver", SLEEVE, lower_coat)
        arm_R, forearm_R = make_arm(torso, B, "R", -1, "gunmetal", GAUNT, lower_gauntlet,
                                    upper_extra=upper_gauntlet, shoulder_r=0.085)
    empty("weapon", parent=forearm_R, loc=(0, 0, B.HAND - B.ELBOW))

    finalize("npc_bail", root, B,
             smooth={"coat_FL_2": 0.10, "coat_FR_2": 0.10, "coat_L_2": 0.10, "coat_R_2": 0.10},
             weights=coat_weights(B, COAT_PANELS_CLOSED, SPLIT, (-0.02, -0.46), k_front=0.7, k_back=0.35,
                                  split_r=0.10),
             swing=COAT_SWING, run_swing=COAT_RUN)


# =========================================================================================
# 포피 Poppy — cheerful village kid (~1.15 m)
# =========================================================================================

def build_poppy():
    reset_scene()
    get_mat("cloth_denim", hex="#4a6a9a", metallic=0.0, roughness=0.85)
    get_mat("cloth_denim_light", hex="#7d9cc4", metallic=0.0, roughness=0.85)
    get_mat("cloth_mustard", hex="#e0b04a", metallic=0.0, roughness=0.85)
    get_mat("cloth_scarlet", hex="#c8283a", metallic=0.0, roughness=0.85)
    get_mat("hair_ginger", hex="#c8642a", metallic=0.0, roughness=0.7)
    B = Body(HIP_Z=0.50, LEG_Z=0.465, LEG_X=0.07, WAIST_Z=0.55, SHOULDER=(0.185, 0.0, 0.19), NECK=0.215,
             ELBOW=-0.13, HAND=-0.26, KNEE=-0.22, HR=0.19, HCZ=0.195, HSCALE=(1.05, 0.97, 0.97),
             FACE_Z=0.97, FACE_R=0.36)
    k = 0.62    # kid scale for boots / hands
    root = empty("root")

    p = Part("hips")
    loft(p, "cloth_denim", [(-0.08, 0.22, 0.16), (0.0, 0.245, 0.175), (0.06, 0.25, 0.18)], shape="oct")
    for s in (1, -1):
        p.box("cloth_denim_light", size=(0.06, 0.012, 0.05), loc=(s * 0.065, -0.093, -0.02))       # pockets
    p.box("cloth_scarlet", size=(0.05, 0.07, 0.03), loc=(0.11, 0.07, -0.03), rot=(0, 0, 20))        # rag
    hips = p.build(root, loc=(0, 0, B.HIP_Z))

    TROUSER = [(-0.30, 0.10, 0.11), (-0.15, 0.10, 0.11), (0.03, 0.115, 0.125)]

    def shin_extra(p, side, s):
        loft(p, "cloth_denim_light", [(-0.31, 0.115, 0.125), (-0.26, 0.12, 0.13)], shape="oct")   # rolled cuff
        boot(p, s, -0.455, k=k, mat="leather", h=0.26, cuff=False, buckle=False)
        p.box("cloth_cream", size=(0.07, 0.03, 0.01), loc=(0, -0.07, -0.43))                      # toe cap
    make_legs(hips, B, "cloth_denim", TROUSER, shin_extra)

    p = Part("torso")
    loft(p, "cloth_mustard", [(0.0, 0.24, 0.17), (0.10, 0.26, 0.18), (0.19, 0.29, 0.18), (0.245, 0.20, 0.15)],
         shape="oct", cap=(False, True))
    for z in (0.05, 0.12):   # shirt stripes
        loft(p, "cloth_cream", [(z, 0.25 + 0.03 * z / 0.12, 0.177), (z + 0.022, 0.255 + 0.03 * z / 0.12, 0.18)],
             shape="oct", cap=(False, False))
    # overall bib + straps
    p.poly("cloth_denim", [(-0.085, -0.094, 0.0), (0.085, -0.094, 0.0), (0.075, -0.098, 0.16), (-0.075, -0.098, 0.16)],
           [(0, 1, 2, 3)])
    p.box("cloth_denim_light", size=(0.07, 0.01, 0.05), loc=(0, -0.102, 0.09))                    # bib pocket
    for s in (1, -1):
        tbox(p, "cloth_denim", 0.15, 0.25, (0.04, 0.20), c0=(s * 0.07, 0.0), c1=(s * 0.085, 0.0))
        p.cyl("brass", r=0.016, h=0.014, seg=6, loc=(s * 0.07, -0.104, 0.155), rot=(90, 0, 0))
    # red scarf around the neck (the hanging tail is the scarf chain)
    p.torus("cloth_scarlet", R=0.072, r=0.036, seg=10, seg2=5, loc=(0, 0.0, 0.24), rot=(-8, 0, 0))
    torso = p.build(hips, loc=(0, 0, B.WAIST_Z - B.HIP_Z))

    SCARF = [(0.08, 0.07, 0.025, -0.075, -0.10), (0.25, 0.06, 0.025, -0.045, -0.085)]
    SJ = 0.165
    p = Part("scarf_1")
    loft(p, "cloth_scarlet", resample(SCARF, [SJ, 0.25]), shape="rect", cap=(False, False))
    sc1 = build_at(p, torso, (-0.045, -0.085, 0.25))
    p = Part("scarf_2")
    loft(p, "cloth_scarlet", resample(SCARF, [0.08, SJ]), shape="rect", cap=(False, False))
    tbox(p, "cloth_scarlet", 0.05, 0.085, (0.075, 0.028), (0.07, 0.028), c0=(-0.078, -0.103), c1=(-0.076, -0.10))
    mid = resample(SCARF, [SJ])[0]
    build_at(p, sc1, (mid[3], mid[4], SJ), (-0.045, -0.085, 0.25))

    p = Part("head")
    head_base(p, B, neck_r=0.045)
    eyes(p, B, 0.058, 0.085, 0.072, B.HCZ - 0.03, white=(0.022, 0.026))
    for s in (1, -1):   # second, smaller sparkle + blush + freckles
        p.box("white", size=(0.01, 0.01, 0.01), loc=(s * 0.062, face_y(B, 0.062, B.HCZ - 0.055) - 0.01,
                                                     B.HCZ - 0.055))
        p.box("cloth_scarlet", size=(0.035, 0.006, 0.016), loc=(s * 0.115, face_y(B, 0.115, B.HCZ - 0.085),
                                                                 B.HCZ - 0.085), rot=(0, 0, s * 30))
        for dx, dz in ((0.0, 0.0), (0.02, -0.012), (-0.015, -0.015)):
            x, z = s * (0.06 + dx), B.HCZ - 0.098 + dz
            p.box("hair_ginger", size=(0.008, 0.005, 0.008), loc=(x, face_y(B, x, z) - 0.001, z))
    brows(p, B, "hair_ginger", 0.072, B.HCZ + 0.03, w=0.05, h=0.013, tilt=12)
    # big open grin
    zm = B.HCZ - 0.10
    p.poly("leather_dark", [(-0.035, face_y(B, -0.035, zm) - 0.003, zm), (0.035, face_y(B, 0.035, zm) - 0.003, zm),
                            (0.0, face_y(B, 0.0, zm - 0.03) - 0.003, zm - 0.03)], [(0, 1, 2)])
    p.poly("cloth_scarlet", [(-0.016, face_y(B, -0.016, zm - 0.016) - 0.004, zm - 0.016),
                             (0.016, face_y(B, 0.016, zm - 0.016) - 0.004, zm - 0.016),
                             (0.0, face_y(B, 0.0, zm - 0.028) - 0.004, zm - 0.028)], [(0, 1, 2)])
    # messy ginger bob
    p.sphere("hair_ginger", r=B.HR * 1.08, seg=10, rings=8, loc=(0, 0.025, B.HCZ + 0.03), scale=(1.06, 1.0, 0.98))
    for x, ang in ((-0.10, -18), (-0.035, 6), (0.035, -8), (0.10, 16)):
        p.cone("hair_ginger", r=0.045, h=0.085, seg=4, loc=(x, face_y(B, x, B.HCZ + 0.06) - 0.015, B.HCZ + 0.06),
               rot=(165, ang, 0))
    for s in (1, -1):
        p.cone("hair_ginger", r=0.05, h=0.10, seg=4, loc=(s * 0.18, -0.03, B.HCZ - 0.02), rot=(180, s * -15, 0))
    p.cone("hair_ginger", r=0.05, h=0.11, seg=4, loc=(0.03, -0.0, B.HCZ + 0.19), rot=(-30, 25, 0))  # cowlick
    # big goggles pushed up on the forehead
    GZ = B.HCZ + 0.15
    GY = -0.15
    p.torus("leather_dark", R=B.HR * 1.1, r=0.016, seg=12, seg2=4, loc=(0, 0.025, GZ - 0.04), rot=(-16, 0, 0))
    for s in (1, -1):
        p.cyl("brass", r=0.066, h=0.055, seg=8, loc=(s * 0.072, GY, GZ), rot=(-50, 0, s * -8))
        p.cyl("glass", r=0.05, h=0.06, seg=8, loc=(s * 0.072, GY - 0.003, GZ + 0.002), rot=(-50, 0, s * -8))
        p.torus("copper", R=0.06, r=0.01, seg=8, seg2=3, loc=(s * 0.072, GY - 0.022, GZ + 0.018),
                rot=(-50, 0, s * -8))
    p.box("brass_dark", size=(0.04, 0.025, 0.025), loc=(0, GY - 0.01, GZ + 0.005), rot=(-50, 0, 0))
    head = p.build(torso, loc=(0, 0, B.NECK))

    # pigtails: one-bone hair chains, tied with red bands
    for side, s in (("L", 1), ("R", -1)):
        piv = (s * 0.19, 0.06, B.HCZ + 0.03)
        p = Part(f"hair_{side}_1")
        p.sphere("cloth_scarlet", r=0.03, seg=6, rings=4, loc=(s * 0.215, 0.07, B.HCZ + 0.02))
        loft(p, "hair_ginger", [(-0.15, 0.0, 0.0, s * 0.26, 0.09), (-0.08, 0.08, 0.08, s * 0.255, 0.085),
                                (-0.02, 0.07, 0.07, s * 0.235, 0.075), (0.0, 0.05, 0.05, s * 0.225, 0.07)],
             shape=5, loc=(0, 0, B.HCZ + 0.02))
        build_at(p, head, piv)

    SLEEVE = [(-0.20, 0.075, 0.075), (-0.03, 0.085, 0.085)]

    def upper(p, side, s):   # puffy short sleeve over the shoulder
        loft(p, "cloth_mustard", [(-0.09, 0.11, 0.11), (-0.06, 0.115, 0.115), (0.0, 0.10, 0.10)], shape="oct",
             cap=(True, False))

    def lower(p, side, s):
        loft(p, "skin", resample(SLEEVE, [-0.20, B.ELBOW]), shape="oct", cap=(False, False))
        loft(p, "skin", [(-0.31, 0.065, 0.075), (-0.29, 0.08, 0.09), (-0.22, 0.078, 0.088), (-0.20, 0.07, 0.08)],
             shape="oct", cap=(True, False))
        p.box("skin", size=(0.03, 0.035, 0.045), loc=(-s * 0.04, -0.022, -0.25))
        p.cyl("cloth_scarlet", r=0.042, h=0.02, seg=6, loc=(0, 0, -0.19))    # wrist band
    make_arm(torso, B, "L", 1, "skin", SLEEVE, lower, shoulder_r=0.06, shoulder_mat="cloth_mustard",
             upper_extra=upper)
    arm_R, forearm_R = make_arm(torso, B, "R", -1, "skin", SLEEVE, lower, shoulder_r=0.06,
                                shoulder_mat="cloth_mustard", upper_extra=upper)
    empty("weapon", parent=forearm_R, loc=(0, 0, B.HAND - B.ELBOW))

    finalize("npc_poppy", root, B,
             smooth={"forearm_L": 0.035, "forearm_R": 0.035, "shin_L": 0.04, "shin_R": 0.04, "scarf_2": 0.04},
             swing={"scarf_1": [("X", -35), ("Y", 15)], "scarf_2": [("X", -20)],
                    "hair_L_1": [("Y", -25)], "hair_R_1": [("Y", 25)]},
             run_swing={"scarf_1": [("X", -40)], "scarf_2": [("X", -25)],
                        "hair_L_1": [("X", 30)], "hair_R_1": [("X", 30)]})


# =========================================================================================
# 상점 주인 Shopkeeper — portly merchant (~1.70 m)
# =========================================================================================

def build_shopkeeper():
    reset_scene()
    get_mat("cloth_vest", hex="#6a4a30", metallic=0.0, roughness=0.85)
    get_mat("cloth_canvas", hex="#e9dfc7", metallic=0.0, roughness=0.9)
    get_mat("cloth_shirt", hex="#f2efe6", metallic=0.0, roughness=0.85)
    get_mat("cloth_umber", hex="#4a3a2c", metallic=0.0, roughness=0.85)
    get_mat("hair_chestnut", hex="#6e4428", metallic=0.0, roughness=0.7)
    B = Body(HIP_Z=0.80, LEG_Z=0.74, LEG_X=0.115, WAIST_Z=0.87, SHOULDER=(0.31, 0.0, 0.31), NECK=0.40,
             ELBOW=-0.20, HAND=-0.40, KNEE=-0.35, HR=0.21, HCZ=0.215, HSCALE=(1.06, 0.97, 0.96),
             FACE_Z=1.48, FACE_R=0.42)
    root = empty("root")

    # hips: round belly bottom + belt
    p = Part("hips")
    loft(p, "cloth_umber", [(-0.10, 0.36, 0.27), (0.0, 0.44, 0.37, 0, -0.04), (0.08, 0.46, 0.40, 0, -0.05)],
         shape="oct")
    loft(p, "leather_dark", [(0.03, 0.475, 0.415, 0, -0.05), (0.085, 0.475, 0.415, 0, -0.05)], shape="oct")
    p.box("brass", size=(0.07, 0.03, 0.05), loc=(0, -0.262, 0.058))
    # coin purse + ledger on the hips
    p.sphere("leather", r=0.055, seg=6, rings=4, loc=(0.23, -0.02, -0.03), scale=(0.8, 1, 1.1))
    p.box("brass", size=(0.03, 0.03, 0.015), loc=(0.23, -0.02, 0.03))
    p.box("wood_dark", size=(0.05, 0.13, 0.17), loc=(-0.235, 0.02, -0.03))
    hips = p.build(root, loc=(0, 0, B.HIP_Z))

    # apron skirt: tabard_F_1 (waist .. split) -> tabard_F_2 (split .. knee), front of the belly
    APRON = [(-0.40, 0.38, 0.0, 0, -0.262), (-0.18, 0.38, 0.0, 0, -0.27), (0.06, 0.40, 0.0, 0, -0.268)]
    AJ = -0.17

    def apron(p, z0, z1, mat="cloth_canvas"):
        a = resample(APRON, [z0])[0]
        b = resample(APRON, [z1])[0]
        verts, faces = [], []
        for (z, w, _, cx, cy) in (a, b):
            for u in (-1, -0.6, 0.6, 1):
                verts.append((u * w / 2, cy + 0.035 * (1 - abs(u)) * -1, z))
        faces = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6)]
        p.poly(mat, verts, faces)
        # back faces (double-sided panel)
        p.poly(mat, [(x, y + 0.006, z) for (x, y, z) in verts], [tuple(reversed(f)) for f in faces])
    p = Part("tabard_F_1")
    apron(p, AJ, 0.06)
    a1 = build_at(p, hips, (0, -0.268, 0.06))
    p = Part("tabard_F_2")
    apron(p, -0.40, AJ)
    p.box("cloth_umber", size=(0.10, 0.012, 0.08), loc=(-0.08, -0.29, -0.30))          # apron pocket
    p.cyl("brass_dark", r=0.008, h=0.10, seg=4, loc=(-0.06, -0.292, -0.24), rot=(0, 15, 0))  # pencil
    build_at(p, a1, (0, -0.27, AJ), (0, -0.268, 0.06))

    TROUSER = [(-0.44, 0.14, 0.15), (-0.22, 0.15, 0.16), (0.04, 0.18, 0.19)]

    def shin_extra(p, side, s):
        boot(p, s, -0.73, k=1.0, mat="leather_dark", sole="black", h=0.22, cuff=False, buckle=False)
        p.box("brass", size=(0.045, 0.02, 0.03), loc=(0, -0.13, -0.67))
    make_legs(hips, B, "cloth_umber", TROUSER, shin_extra)

    # torso: big round belly in a waistcoat, shirt collar, bow tie, apron bib with brass scale emblem
    VEST = [(0.0, 0.46, 0.40, 0, -0.05), (0.10, 0.52, 0.46, 0, -0.06), (0.22, 0.50, 0.38, 0, -0.03),
            (0.32, 0.45, 0.28), (0.40, 0.31, 0.21)]
    p = Part("torso")
    loft(p, "cloth_vest", VEST, shape=10, cap=(False, True))
    for s in (1, -1):
        p.poly("cloth_shirt", [(0.0, -0.142, 0.405), (s * 0.085, -0.13, 0.39), (0.0, -0.17, 0.30)], [(0, 1, 2)])
    p.box("cloth_red", size=(0.05, 0.03, 0.035), loc=(0, -0.155, 0.37))
    for s in (1, -1):
        p.cone("cloth_red", r=0.035, h=0.06, seg=4, loc=(s * 0.04, -0.152, 0.37), rot=(0, s * -90, 0))
    # apron bib over the belly (front sector of the vest, pushed out a little)
    def bib_pt(z, u):
        _, w, d, cx, cy = resample(VEST, [z])[0]
        a = math.radians(270 + u * 32)
        return (cx + (w / 2 + 0.008) * math.cos(a), cy + (d / 2 + 0.012) * math.sin(a), z)
    zs = [0.0, 0.10, 0.20, 0.28]
    us = [-1, -0.5, 0, 0.5, 1]
    verts = [bib_pt(z, u) for z in zs for u in us]
    faces = [(i * 5 + j, i * 5 + j + 1, (i + 1) * 5 + j + 1, (i + 1) * 5 + j) for i in range(3) for j in range(4)]
    p.poly("cloth_canvas", verts, faces)
    for s in (1, -1):   # neck straps of the apron
        top = bib_pt(0.28, s * 1)
        tube(p, "cloth_canvas", [top, (s * 0.12, -0.10, 0.36), (s * 0.10, 0.0, 0.405)], r=0.014, seg=4, flat=0.4)
    # brass scale emblem on the bib
    e = bib_pt(0.17, 0)
    ey = e[1] - 0.008
    p.box("brass", size=(0.012, 0.01, 0.075), loc=(0, ey, 0.17))
    p.box("brass", size=(0.10, 0.01, 0.01), loc=(0, ey, 0.205))
    for s in (1, -1):
        p.cyl("brass", r=0.022, r2=0.012, h=0.012, seg=6, loc=(s * 0.048, ey, 0.17), rot=(0, 0, 0))
        p.box("brass_dark", size=(0.004, 0.006, 0.03), loc=(s * 0.048, ey, 0.19))
    p.box("brass", size=(0.05, 0.01, 0.01), loc=(0, ey, 0.135))
    # pocket-watch chain across the vest (visible beside the bib)
    tube(p, "brass", [(0.12, -0.215, 0.10), (0.17, -0.205, 0.07), (0.20, -0.18, 0.09)], r=0.006, seg=4)
    torso = p.build(hips, loc=(0, 0, B.WAIST_Z - B.HIP_Z))

    p = Part("head")
    head_base(p, B, neck_r=0.07)
    eyes(p, B, 0.04, 0.045, 0.075, B.HCZ - 0.03, white=(0.013, 0.014))
    brows(p, B, "hair_chestnut", 0.078, B.HCZ + 0.02, w=0.07, h=0.024, tilt=10, d=0.026)
    p.sphere("skin", r=0.04, seg=6, rings=4, loc=(0, face_y(B, 0, B.HCZ - 0.075) - 0.01, B.HCZ - 0.075))  # nose
    for s in (1, -1):
        p.box("cloth_red", size=(0.04, 0.006, 0.018), loc=(s * 0.125, face_y(B, 0.125, B.HCZ - 0.085),
                                                            B.HCZ - 0.085), rot=(0, 0, s * 30))
    # handlebar moustache
    zm = B.HCZ - 0.105
    for s in (1, -1):
        tube(p, "hair_chestnut", [(s * 0.005, face_y(B, 0.01, zm) - 0.022, zm),
                                  (s * 0.06, face_y(B, 0.06, zm - 0.01) - 0.022, zm - 0.012),
                                  (s * 0.11, face_y(B, 0.11, zm) - 0.01, zm + 0.005),
                                  (s * 0.135, face_y(B, 0.135, zm + 0.04) + 0.004, zm + 0.04)],
             r=[0.034, 0.036, 0.022, 0.0], seg=5)
    p.box("leather", size=(0.03, 0.01, 0.008), loc=(0, face_y(B, 0, zm - 0.045) + 0.003, zm - 0.045))
    # monocle on his right eye (-X) with a chain to the collar
    mx, mz = -0.075, B.HCZ - 0.03
    p.torus("brass", R=0.042, r=0.008, seg=8, seg2=3, loc=(mx, face_y(B, mx, mz) - 0.02, mz), rot=(90, 0, 0))
    p.cyl("glass", r=0.037, h=0.006, seg=8, loc=(mx, face_y(B, mx, mz) - 0.02, mz), rot=(90, 0, 0))
    tube(p, "brass_dark", [(mx - 0.035, face_y(B, mx, mz) - 0.018, mz - 0.025), (-0.15, -0.14, B.HCZ - 0.13),
                           (-0.12, -0.10, -0.0)], r=0.005, seg=4)
    # balding: chestnut fringe around the sides / back, shiny crown
    p.sphere("hair_chestnut", r=0.16, seg=8, rings=6, loc=(0, 0.095, B.HCZ - 0.005), scale=(1.3, 0.9, 0.78))
    for s in (1, -1):
        p.sphere("hair_chestnut", r=0.075, seg=6, rings=4, loc=(s * 0.205, 0.03, B.HCZ + 0.02), scale=(0.65, 1.3, 1.0))
    head = p.build(torso, loc=(0, 0, B.NECK))

    # rolled shirt sleeves: shirt on the upper arm, thick roll at the elbow, bare forearm
    SLEEVE = [(-0.30, 0.13, 0.13), (-0.05, 0.145, 0.145)]
    FORE = [(-0.33, 0.10, 0.105), (B.ELBOW, 0.12, 0.125)]

    def lower(p, side, s):
        loft(p, "skin", resample(FORE, [-0.33, B.ELBOW + 0.01]), shape="oct", cap=(False, False))
        loft(p, "cloth_shirt", [(B.ELBOW - 0.05, 0.155, 0.16), (B.ELBOW - 0.02, 0.165, 0.17),
                                (B.ELBOW + 0.02, 0.16, 0.165)], shape="oct")
        loft(p, "skin", [(-0.49, 0.10, 0.12), (-0.46, 0.12, 0.14), (-0.37, 0.115, 0.135), (-0.33, 0.10, 0.11)],
             shape="oct", cap=(True, False))
        p.box("skin", size=(0.042, 0.055, 0.065), loc=(-s * 0.06, -0.035, -0.41))
    make_arm(torso, B, "L", 1, "cloth_shirt", SLEEVE, lower, shoulder_r=0.085)
    arm_R, forearm_R = make_arm(torso, B, "R", -1, "cloth_shirt", SLEEVE, lower, shoulder_r=0.085)
    empty("weapon", parent=forearm_R, loc=(0, 0, B.HAND - B.ELBOW))

    finalize("npc_shopkeeper", root, B, smooth={"tabard_F_2": 0.08},
             swing={"tabard_F_1": [("X", -25)], "tabard_F_2": [("X", -10)]},
             run_swing={"tabard_F_1": [("X", -30)], "tabard_F_2": [("X", -10)]})


BUILDERS = {"marta": build_marta, "bail": build_bail, "poppy": build_poppy, "shopkeeper": build_shopkeeper}

if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for name in (argv or list(BUILDERS)):
        BUILDERS[name.replace("npc_", "")]()
