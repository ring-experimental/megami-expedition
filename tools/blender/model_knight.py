"""Clockwork Knight — strong enemy (~2.1 m). Hi-poly.
Exports public/models/knight.glb (skinned, RIG_SPEC.md) + previews tools/blender/previews/knight*.png.

Part hierarchy built here (rig_from_parts turns every mesh part into a bone of the same name):
  root > hips > {torso > {head, arm_L > forearm_L > (shield), arm_R > forearm_R > (weapon), (key)},
                 leg_L > shin_L, leg_R > shin_R, tabard_F_1 > tabard_F_2, tabard_B_1 > tabard_B_2}
  (parenthesised = rigid attachments, not skinned)
Faces -Y, character's right = -X. Halberd shaft along +Z from the right hand (fixed pivot/offset,
game tuning depends on it). key: sticks out of the back along +Y and spins around its local Y axis.

Joints are mechanical (rigid weights): shoulders/elbows/knees are gunmetal ball joints with brass
gears on the hinge axis, couters/poleyns sit on the parent segment so the bend stays covered.
Only the cloth tabard chains are soft-blended (enemy_rig_helpers.reweight_chain).

Geometry helpers (plates, stacks, gears, fists ...) live in hp_knight_helpers.py.

Usage:  blender -b --factory-startup -P tools/blender/model_knight.py [-- quick | cost]
        quick = no rig/export, EEVEE previews of the static model (fast iteration)
        cost  = only print the per-section triangle costs
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import math

import bpy
from mathutils import Matrix, Vector

from common import Part, get_mat, empty, reset_scene, render_preview
from char_helpers import prism, tri_report
from rig_helpers import rig_from_parts, HUMANOID_TEST_POSE
from enemy_rig_helpers import tag_part, reweight_chain, pose_views
import hp_helpers as hp
from hp_knight_helpers import (M_, frame, basis, piece, merge, rbox, se, pchip, Stack, front_angle, back_angle,
                               loft_rings, revolve, ring_rr, grid_shell, lin, rivet, gear, tube_pts, edge_roll,
                               fist, finish_obj, bez, smooth01, lerp, TAU)

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
QUICK = "quick" in ARGS
COST = "cost" in ARGS

reset_scene()

# ---- materials (palette names, knight-tuned values; 10 materials) ---------------------------
get_mat("iron", hex="#3b3f48", metallic=0.8, roughness=0.42)
get_mat("gunmetal", hex="#25282e", metallic=0.75, roughness=0.5)
get_mat("brass", hex="#c9a14a", metallic=0.9, roughness=0.32)
get_mat("brass_dark", hex="#8a6a2c", metallic=0.9, roughness=0.42)
get_mat("steel", hex="#b4bcc6", metallic=0.9, roughness=0.22)
get_mat("cloth_red", hex="#a8302a", metallic=0.0, roughness=0.85)
get_mat("leather_dark", hex="#3b2416", metallic=0.0, roughness=0.7)
get_mat("wood_dark", hex="#4a3020", metallic=0.0, roughness=0.75)
get_mat("black", hex="#0e0e10", metallic=0.0, roughness=0.6)
get_mat("glow_amber")

root = empty("root")

HIP_Z = 1.05
LEG_Z = 0.97
LEG_X = 0.17
WAIST_Z = 1.13
SHOULDER = (0.47, 0.0, 0.50)
NECK = 0.60
HAND = -0.80
ELBOW = -0.44        # arm-local, centre of the elbow ball
KNEE = -0.47         # leg-local, centre of the knee ball
TABARD_TOP = 0.02    # hips-local z of the tabard hinge (under the belt)
TABARD_SEAM = -0.28  # hips-local z where tabard_*_1 ends and tabard_*_2 starts (mid-thigh)
SX, SY = -0.10, -0.18  # halberd shaft offset from the right hand pivot
SMOOTH_ANGLE = 48.0    # > 45 so single-segment chamfers blend (with weighted normals) like rounded edges

PARTS = []
_COST = {}


def mark(p, label):
    """Debug: print the triangles added to part p since the previous mark (bevels included)."""
    t = sum(len(f.verts) - 2 for f in p.bm.faces)
    if COST:
        print(f"[cost] {p.name:11s} {label:16s} {t - _COST.get(p.name, 0)}")
    _COST[p.name] = t


def done(obj, angle=SMOOTH_ANGLE):
    finish_obj(obj, angle=angle)
    PARTS.append(obj)
    return obj


def plate(p, mat, G, t=0.014, bevel=(0.005, 1), **kw):
    """grid_shell in its own piece (outer-edge bevel), merged into p."""
    q = piece()
    grid_shell(q, mat, G, t, **kw)
    merge(p, q, bevel=(bevel + (40,)) if bevel else None)


def ring_band(p, mat, stack, z0, z1, off0, off1, n=24, t=0.012, bulge=0.004, rows=2, inner=False, bevel=(0.004, 1)):
    """Closed armour band around a Stack between z0 and z1 (offset off0 -> off1), slightly convex."""
    G = [stack.ring(lerp(z0, z1, s), n, off=lerp(off0, off1, s) + bulge * math.sin(math.pi * s)) for s in lin(0, 1, rows)]
    plate(p, mat, G, t, bevel=bevel, closed_u=True, inward=(0, 0, (z0 + z1) / 2), inner=inner)


def ball(p, mat, c, r, seg=12, rings=6):
    prof = [(0, -r)] + [(r * math.sin(math.pi * k / rings), -r * math.cos(math.pi * k / rings)) for k in range(1, rings)] + [(0, r)]
    revolve(p, mat, prof, seg=seg, M=M_(c))


# =============================================================================================
# TORSO (pivot at the waist)
# =============================================================================================
TS = Stack([
    (-0.06, 0.40, 0.30, 0.0),
    (0.04, 0.42, 0.31, 0.0),
    (0.16, 0.48, 0.34, -0.005),
    (0.27, 0.60, 0.40, -0.012),
    (0.38, 0.68, 0.43, -0.015),
    (0.455, 0.70, 0.42, -0.010),
    (0.48, 0.61, 0.37, 0.0),
    (0.50, 0.47, 0.315, 0.0),
    (0.51, 0.32, 0.25, 0.0),
    (0.515, 0.20, 0.19, 0.0),
], e=2.6)
BP_SPAN = 1.22       # breastplate half-angle (rad) around the front
BP_OFF = 0.022


def bp_pt(u, z, off=BP_OFF):
    """Point on the breastplate surface (u in -1..1 across, z torso-local) incl. the centre keel."""
    P = TS.pt(front_angle(u, BP_SPAN), z, off)
    k = max(0.0, 1 - abs(u) / 0.32)
    P.y -= 0.024 * k * k * smooth01((z - 0.10) / 0.2)
    return P


def bp_bot(u):
    return 0.125 + 0.13 * abs(u) ** 1.6


def bp_top(u):
    return 0.462 + 0.036 * abs(u) ** 1.3


def build_torso(hips_obj):
    p = Part("torso")
    TS.loft(p, "iron", [-0.06, 0.04, 0.12, 0.2, 0.28, 0.36, 0.42, 0.46, 0.485, 0.505, 0.515], 16)
    mark(p, "core")
    # --- breastplate (brass) with rolled neckline and an engraved inset line ---
    us = lin(-1, 1, 15)
    G = [[bp_pt(u, lerp(bp_bot(u), bp_top(u), i / 5)) for u in us] for i in range(6)]
    plate(p, "brass", G, 0.016, bevel=(0.006, 1), inward=(0, 0.1, 0.3), inner=False)
    edge_roll(p, "brass", [bp_pt(u, bp_top(u) - 0.004, BP_OFF + 0.003) for u in lin(-0.99, 0.99, 15)], r=0.011, seg=6)
    for sgn in (-1, 1):       # engraved side lines (above the plackart)
        fil = [bp_pt(sgn * 0.80, z, BP_OFF + 0.001) for z in lin(bp_top(0.8) - 0.045, 0.21, 4)]
        tube_pts(p, "brass_dark", fil, 0.0045, seg=3)
    # plackart: iron plate over the lower breastplate, pointed (ogee) top with a rolled brass edge
    def pk_top(u):
        return 0.252 - 0.085 * abs(u) ** 1.15
    us = lin(-0.9, 0.9, 13)
    G = [[bp_pt(u, lerp(bp_bot(u) - 0.012, pk_top(u), i / 3), BP_OFF + 0.012) for u in us] for i in range(4)]
    plate(p, "iron", G, 0.012, bevel=(0.005, 1), inward=(0, 0.1, 0.2), inner=False)
    edge_roll(p, "brass", [bp_pt(u, pk_top(u) - 0.003, BP_OFF + 0.015) for u in us], r=0.008, seg=4)
    mark(p, "breastplate")
    # --- chest core: bezel + gear + amber heart ---
    c = bp_pt(0, 0.35, BP_OFF + 0.012)
    n = Vector((0, -1, 0.10)).normalized()
    Mc = frame(c, n)
    revolve(p, "gunmetal", [(0, -0.012), (0.07, -0.012), (0.07, 0.002), (0, 0.002)], seg=16, M=Mc)
    revolve(p, "brass", [(0.064, -0.01), (0.09, -0.01), (0.093, 0.008), (0.08, 0.016), (0.064, 0.008)], seg=20, M=Mc, closed=True)
    gear(p, "brass_dark", 0.06, 8, 0.012, depth=0.013, hole=0.026, M=Mc @ M_((0, 0, 0.006)), spokes=4, back=False)
    revolve(p, "glow_amber", [(0, 0.0), (0.03, 0.0), (0.026, 0.012), (0.012, 0.02), (0, 0.022)], seg=12,
            M=Mc @ M_((0, 0, 0.004)))
    for k in range(4):
        a = TAU * k / 4 + TAU / 8
        rivet(p, "gunmetal", Mc @ Vector((0.078 * math.cos(a), 0.078 * math.sin(a), 0.014)), n, r=0.007, h=0.005)
    mark(p, "chest core")
    # --- abdomen lames (brass_dark), lobster-tail overlap ---
    for (z0, z1) in ((0.17, 0.09), (0.11, 0.03), (0.05, -0.03)):
        ring_band(p, "brass_dark", TS, z0, z1, 0.006, 0.022, n=18, t=0.012, bevel=None)
    mark(p, "abdomen")
    # --- gorget: two steep rings standing up from the shoulder slope (brass + iron) ---
    for (z0, z1, w0, w1, d0, d1, mat) in ((0.472, 0.552, 0.635, 0.47, 0.435, 0.378, "brass"),
                                          (0.528, 0.594, 0.48, 0.36, 0.388, 0.372, "iron")):
        G = []
        for s in lin(0, 1, 3):
            b = 0.01 * math.sin(math.pi * s)
            w, d = lerp(w0, w1, s) + b, lerp(d0, d1, s) + b
            G.append([Vector((*se(-math.pi / 2 + TAU * i / 22, w / 2, d / 2, 2.2), lerp(z0, z1, s))) for i in range(22)])
        plate(p, mat, G, 0.014, bevel=(0.005, 1) if mat == "brass" else None, closed_u=True, inward=(0, 0, z0 - 0.1),
              inner=False)
    mark(p, "gorget")
    # --- backplate (iron) with brass spine and rolled edges ---
    us = lin(-1, 1, 11)

    def bk(u, z, off=0.02):
        P = TS.pt(back_angle(u, 1.15), z, off)
        k = max(0.0, 1 - abs(u) / 0.25)
        P.y += 0.014 * k * k
        return P
    G = [[bk(u, z) for u in us] for z in lin(0.15, 0.48, 6)]
    plate(p, "iron", G, 0.016, bevel=(0.006, 1), inward=(0, -0.1, 0.3), inner=False)
    edge_roll(p, "brass", [bk(u, 0.48, 0.023) for u in lin(-0.99, 0.99, 11)], r=0.009, seg=4)
    edge_roll(p, "brass", [bk(u, 0.15, 0.023) for u in lin(-0.99, 0.99, 11)], r=0.009, seg=4)
    for u in (-0.82, -0.62, 0.62, 0.82):
        for z in (0.2, 0.43):
            if abs(u) > 0.7 or z > 0.3:
                P = bk(u, z, 0.021)
                rivet(p, "brass", P, (P.x, P.y, 0), r=0.01, h=0.006)
    mark(p, "backplate")
    # --- clockwork drum on the back (key socket) ---
    Md = basis((1, 0, 0), (0, 0, 1), (0, 1, 0), (0, 0.205, 0.36))     # local Z -> +Y (back)
    revolve(p, "brass", [(0, 0.0), (0.138, 0.0), (0.14, 0.05), (0.124, 0.062), (0.11, 0.035), (0.0, 0.035)], seg=20, M=Md)
    gear(p, "brass_dark", 0.088, 10, 0.012, depth=0.015, hole=0.05, spokes=5, M=Md @ M_((0, 0, 0.044)), back=False)
    revolve(p, "brass", [(0, 0.035), (0.045, 0.035), (0.045, 0.072), (0.038, 0.082), (0, 0.082)], seg=12, M=Md)
    for k in range(4):
        a = TAU * k / 4 + TAU / 8
        rivet(p, "gunmetal", Md @ Vector((0.122 * math.cos(a), 0.122 * math.sin(a), 0.06)), (0, 1, 0), r=0.009)
    mark(p, "drum")
    return done(p.build(hips_obj, loc=(0, 0, WAIST_Z - HIP_Z)))


# =============================================================================================
# HIPS (pivot at the pelvis)
# =============================================================================================
HS_ = Stack([
    (-0.17, 0.34, 0.25, 0.0),
    (-0.10, 0.44, 0.30, 0.0),
    (-0.02, 0.48, 0.325, 0.0),
    (0.06, 0.47, 0.325, 0.0),
    (0.11, 0.42, 0.31, 0.0),
], e=2.4)


def build_hips():
    p = Part("hips")
    HS_.loft(p, "iron", lin(-0.17, 0.11, 6), 16)
    revolve(p, "gunmetal", [(0.17, 0.08), (0.19, 0.12), (0.17, 0.16), (0.0, 0.16)], seg=18)   # waist joint
    mark(p, "core")
    # belt (leather) with brass studs + buckle
    ring_band(p, "leather_dark", HS_, -0.01, 0.065, 0.012, 0.012, n=18, t=0.012, bulge=0.002)
    for k in range(8):
        a = -math.pi / 2 + TAU * (k + 0.5) / 8
        if abs(math.cos(a)) < 0.4 and math.sin(a) < 0:
            continue                                                # skip behind the buckle
        P = HS_.pt(a, 0.028, 0.025)
        rivet(p, "brass", P, (P.x, P.y, 0), r=0.01, h=0.006)
    yb = -(0.325 / 2 + 0.03)
    rbox(p, "brass", (0.15, 0.03, 0.11), loc=(0, yb, 0.028), r=0.01, segs=1)
    gear(p, "brass_dark", 0.042, 8, 0.012, depth=0.01, hole=0.018, spokes=4, back=False,
         M=frame((0, yb - 0.018, 0.028), (0, -1, 0)))
    revolve(p, "glow_amber", [(0, 0), (0.014, 0), (0.01, 0.008), (0, 0.01)], seg=10, M=frame((0, yb - 0.02, 0.028), (0, -1, 0)))
    mark(p, "belt")
    # fauld: two iron lames flaring below the belt
    for (z0, z1, o0, o1) in ((0.0, -0.075, 0.016, 0.032), (-0.055, -0.13, 0.03, 0.046)):
        ring_band(p, "iron", HS_, z0, z1, o0, o1, n=18, t=0.012)
    mark(p, "fauld")
    # tassets: overlapping curved lames per side, around the leg axis (clear of the thigh swing)
    for s in (1, -1):
        cx = s * LEG_X
        span = math.radians(40)
        for k, (z0, z1, r0, r1) in enumerate(((0.0, -0.13, 0.158, 0.168), (-0.11, -0.24, 0.165, 0.175),
                                              (-0.22, -0.34, 0.172, 0.182))):
            G = [[Vector((cx + s * (lerp(r0, r1, t) + 0.006 * math.cos(u * math.pi / 2)) * math.cos(u * span),
                          (lerp(r0, r1, t) + 0.006 * math.cos(u * math.pi / 2)) * math.sin(u * span), lerp(z0, z1, t)))
                  for u in lin(-1, 1, 5)] for t in (0.0, 1.0)]
            plate(p, "iron", G, 0.012, bevel=(0.005, 1), inward=(cx, 0, z0))
            if k != 1:
                edge_roll(p, "brass", [Vector((cx + s * (r1 + 0.007) * math.cos(u * span), (r1 + 0.007) * math.sin(u * span), z1 + 0.003))
                                       for u in lin(-1, 1, 5)], r=0.0065, seg=3)
            if k == 0:
                rivet(p, "brass", Vector((cx + s * (r0 + 0.008), 0.0, z0 - 0.03)), (s, 0, 0), r=0.01, h=0.006)
    mark(p, "tassets")
    return done(p.build(root, loc=(0, 0, HIP_Z)))


# =============================================================================================
# TABARD (cloth chains, front + back)
# =============================================================================================
def build_tabard(side, hips_obj):
    """Grid cloth panel in hips space, split at TABARD_SEAM into tabard_<side>_1 / _2."""
    front = side == "F"
    y0 = -0.222 if front else 0.222
    tilt = math.radians(6)
    xw_top, xw_bot = (0.15, 0.168) if front else (0.17, 0.188)
    z_top = 0.05
    z_hem = -0.66 if front else -0.70
    tears = [0.0, -0.06, 0.025, -0.09, -0.01, 0.035, -0.065, 0.02, -0.08, -0.015, 0.0]
    if not front:
        tears = list(reversed(tears))
    fr = [-1.0, -0.87] + lin(-0.70, 0.70, 7) + [0.87, 1.0]          # column fractions (trim bands at the edges)
    sgn_y = -1 if front else 1

    def pt(f, z):
        t = (z_top - z) / (z_top - z_hem)
        x = f * (xw_top + (xw_bot - xw_top) * max(0.0, t))
        y = y0 + sgn_y * (z_top - z) * math.tan(tilt)
        fold = 0.016 * math.sin(f * 7.5 + (0.6 if front else 1.9)) * smooth01(0.1 + 1.1 * t)
        return Vector((x, y + sgn_y * fold, z))

    cols_u = [[pt(f, z) for z in lin(z_top, TABARD_SEAM, 5)] for f in fr]
    cols_l = [[pt(f, z) for z in lin(TABARD_SEAM, z_hem + tears[j], 6)] for j, f in enumerate(fr)]
    Gu = [[cols_u[j][i] for j in range(len(fr))] for i in range(len(cols_u[0]))]
    Gl = [[cols_l[j][i] for j in range(len(fr))] for i in range(len(cols_l[0]))]
    trim = {0, len(fr) - 2}

    def fm(i, j):
        return "brass_dark" if j in trim else "cloth_red"
    inward = (0, y0 - sgn_y * 0.5, -0.3)
    piv1 = Vector((0, y0 + sgn_y * (z_top - TABARD_TOP) * math.tan(tilt), TABARD_TOP))
    piv2 = Vector((0, y0 + sgn_y * (z_top - TABARD_SEAM) * math.tan(tilt), TABARD_SEAM))
    p = Part(f"tabard_{side}_1")
    grid_shell(p, "cloth_red", Gu, 0.012, inward=inward, face_mat=fm)
    if front:
        c = pt(0, -0.075) + Vector((0, -0.008, 0))
        Mf = frame(c, (0, -1, -0.1))
        gear(p, "brass", 0.06, 8, 0.01, depth=0.013, hole=0.03, M=Mf, spokes=4, back=False)
        revolve(p, "brass_dark", [(0, 0), (0.022, 0), (0.018, 0.008), (0, 0.01)], seg=10, M=Mf)
    for sx in (-1, 1):
        p.box("brass", size=(0.03, 0.012, 0.05), loc=tuple(pt(sx * 0.75, z_top - 0.012) + Vector((0, sgn_y * 0.008, 0))))
    for v in p.bm.verts:
        v.co -= piv1
    mark(p, "panel")
    t1 = p.build(hips_obj, loc=tuple(piv1))
    p = Part(f"tabard_{side}_2")
    grid_shell(p, "cloth_red", Gl, 0.012, inward=inward, face_mat=fm)
    for v in p.bm.verts:
        v.co -= piv2
    mark(p, "panel")
    t2 = p.build(t1, loc=tuple(piv2 - piv1))
    tag_part(t1, f"__tabard_{side}")
    tag_part(t2, f"__tabard_{side}")
    done(t1, angle=60)
    done(t2, angle=60)
    return t1, t2


# =============================================================================================
# HEAD (great helm)
# =============================================================================================
HELM = Stack([
    (-0.045, 0.300, 0.330, 0.004, 0.000),
    (-0.010, 0.318, 0.348, 0.000, 0.012),
    (0.050, 0.332, 0.366, -0.008, 0.022),
    (0.120, 0.340, 0.376, -0.012, 0.024),
    (0.170, 0.345, 0.376, -0.012, 0.020),
    (0.240, 0.350, 0.372, -0.010, 0.012),
    (0.300, 0.344, 0.360, -0.005, 0.008),
    (0.350, 0.316, 0.330, 0.000, 0.004),
    (0.390, 0.250, 0.262, 0.000, 0.0),
    (0.415, 0.150, 0.160, 0.000, 0.0),
    (0.426, 0.050, 0.055, 0.000, 0.0),
], e=2.3, keel_w=0.5)
SLIT = (0.172, 0.208)


def slit_depth(a):
    da = abs(((a + math.pi / 2 + math.pi) % TAU) - math.pi)
    return 0.032 * (1 - smooth01((da - 0.85) / 0.35))


def helm_in(P, z):
    return Vector((P.x, P.y - HELM.at(z)[2], 0)).normalized()


def build_head(torso_obj):
    p = Part("head")
    n = 24
    angs = [-math.pi / 2 + TAU * i / n for i in range(n)]
    zs = [-0.045, -0.015, 0.03, 0.09, 0.14, SLIT[0] - 0.004, SLIT[0], SLIT[0] + 0.004,
          SLIT[1] - 0.004, SLIT[1], SLIT[1] + 0.004, 0.25, 0.30, 0.345, 0.38, 0.405, 0.42]
    depth_k = {6: 0.35, 7: 1.0, 8: 1.0, 9: 0.35}
    rings = []
    for k, z in enumerate(zs):
        ring = []
        for a in angs:
            P = HELM.pt(a, z)
            d = slit_depth(a) * depth_k.get(k, 0.0)
            ring.append(P - helm_in(P, z) * d if d else P)
        rings.append(ring)
    rings.append([Vector((0, 0, 0.428))])
    loft_rings(p, "iron", rings, caps=(True, False), band_mats={7: "black", 6: "gunmetal", 8: "gunmetal"})
    mark(p, "helm")
    # eyes: two amber lozenges at the bottom of the slit, slightly slanted (stern)
    for s in (1, -1):
        a = -math.pi / 2 + s * 0.30
        z = (SLIT[0] + SLIT[1]) / 2
        P = HELM.pt(a, z)
        c = P - helm_in(P, z) * 0.026
        q = piece()
        revolve(q, "glow_amber", [(0, -0.03), (0.010, -0.022), (0.012, 0.0), (0.010, 0.022), (0, 0.03)], seg=8)
        yaw = math.atan2(c.x, -c.y)
        Me = (Matrix.Translation(c) @ Matrix.Rotation(yaw, 4, "Z") @ Matrix.Rotation(math.radians(-8 * s), 4, "Y") @
              Matrix.Rotation(math.radians(90), 4, "Y") @ M_(scale=(0.8, 1.0, 1.15)))
        merge(p, q, M=Me)
    mark(p, "eyes")
    # brass brow band above the slit (with rivets) and lower rim
    ring_band(p, "brass", HELM, SLIT[1] + 0.006, 0.262, 0.006, 0.006, n=24, t=0.01, bulge=0.003)
    for k in range(6):
        a = -math.pi / 2 + TAU * (k + 0.5) / 6
        P = HELM.pt(a, 0.236, 0.012)
        rivet(p, "gunmetal", P, (P.x, P.y, 0), r=0.008, h=0.005)
    mark(p, "bands")
    # central keel strip down the face + four reinforcing ribs up the skull
    G = [[HELM.pt(-math.pi / 2 + u * 0.12, z, 0.004) for u in lin(-1, 1, 3)] for z in lin(-0.03, SLIT[0] - 0.006, 5)]
    plate(p, "brass", G, 0.008, bevel=(0.003, 1), inward=(0, 0, 0.1), inner=False)
    for a0 in (-math.pi / 2 - 1.0, -math.pi / 2 + 1.0, math.pi / 2 - 0.9, math.pi / 2 + 0.9):
        G = [[HELM.pt(a0 + u * 0.075 * (1.2 - 0.55 * t), z, 0.006) for u in lin(-1, 1, 3)]
             for t, z in zip(lin(0, 1, 6), lin(0.258, 0.392, 6))]
        plate(p, "brass", G, 0.008, bevel=(0.003, 1), inward=(0, 0, 0.25), inner=False)
    mark(p, "keel+ribs")
    # breathing slots (3 per side)
    for s in (1, -1):
        for k, z in enumerate((0.045, 0.08, 0.115)):
            a = -math.pi / 2 + s * (0.42 + 0.02 * k)
            P = HELM.pt(a, z, -0.002)
            nrm = -helm_in(P, z)
            tang = Vector((0, 0, 1)).cross(nrm).normalized()
            q = piece()
            q.box("black", size=(0.05, 0.012, 0.01))
            merge(p, q, M=basis(tang, nrm, Vector((0, 0, 1)), P))
    mark(p, "slots")
    # ear rosettes (visor pivots)
    for s in (1, -1):
        P = HELM.pt(0 if s > 0 else math.pi, 0.19, 0.0)
        Mr = frame(P, (s, 0, 0))
        revolve(p, "brass", [(0, -0.01), (0.052, -0.01), (0.054, 0.006), (0.044, 0.016), (0.026, 0.02), (0, 0.022)], seg=14, M=Mr)
        rivet(p, "gunmetal", Mr @ Vector((0, 0, 0.02)), (s, 0, 0), r=0.016, h=0.01, seg=8)
    mark(p, "rosettes")
    # crest: brass half-gear standing fore-aft on the skull
    Mg = basis((0, 1, 0), (0, 0, 1), (1, 0, 0), (0, 0.01, 0.37))
    gear(p, "brass", 0.155, 16, 0.024, depth=0.03, hole=0.04, tip=0.32, root=0.5, M=Mg, arc=(0.3, math.pi - 0.3))
    for s in (1, -1):
        rivet(p, "brass_dark", Vector((s * 0.013, 0.01, 0.445)), (s, 0, 0), r=0.024, h=0.009, seg=8)
    mark(p, "crest")
    # neck (gunmetal, hidden by the gorget) so turning the head never shows a gap
    revolve(p, "gunmetal", [(0.0, -0.10), (0.11, -0.10), (0.12, -0.02), (0.13, 0.02), (0.0, 0.02)], seg=14)
    mark(p, "neck")
    return done(p.build(torso_obj, loc=(0, 0, NECK)))


# =============================================================================================
# ARMS
# =============================================================================================
def build_arm(s, torso_obj):
    side = "L" if s > 0 else "R"
    p = Part("arm_" + side)
    ball(p, "gunmetal", (0, 0, 0), 0.095, seg=8, rings=4)
    mark(p, "ball")
    # pauldron: bell-shaped brass plate (profile curve, flared lip), open toward the neck and below
    C = Vector((s * 0.03, 0.0, -0.01))
    PT = [0.0, 0.25, 0.5, 0.7, 0.85, 1.0]
    PR = [0.0, 0.095, 0.165, 0.200, 0.213, 0.228]
    PZ = [0.180, 0.163, 0.120, 0.050, -0.022, -0.092]
    KY = 0.72                                   # shallow in Y: the halberd passes in front of the right one
    nth = 18

    def dome(th, t, grow=0.0):
        r = pchip(PT, PR, t) + grow
        z = pchip(PT, PZ, t) + grow * 0.4
        thw = ((th + math.pi) % TAU) - math.pi
        r *= 1.0 + 0.06 * max(0.0, 1 - abs(thw) / 0.5) ** 2 * smooth01(t / 0.6)    # ridge on the outer meridian
        return C + Vector((s * r * math.cos(th), KY * r * math.sin(th), z))

    def tmax(th):
        return 0.68 + 0.32 * (1 + math.cos(th)) / 2
    G = [[dome(0.0, 0.0)]]
    for i in range(1, 8):
        G.append([dome(TAU * j / nth, tmax(TAU * j / nth) * i / 7) for j in range(nth)])
    plate(p, "brass", G, 0.016, bevel=(0.006, 1), closed_u=True, inward=C - Vector((0, 0, 0.05)), inner=False)
    edge_roll(p, "brass_dark", [dome(TAU * j / nth, tmax(TAU * j / nth), 0.007) for j in range(nth + 1)], r=0.012, seg=4)
    for th in (-0.75, 0.75):
        P = dome(th, tmax(th) - 0.12, 0.002)
        rivet(p, "gunmetal", P, P - C - Vector((0, 0, 0.05)), r=0.011, h=0.006)
    # gear boss on the outer face
    Pg = dome(0.0, 0.56, 0.0)
    ng = (dome(0.0, 0.60) - dome(0.0, 0.52)).cross(Vector((0, 1, 0)))
    ng = ng if ng.dot(Pg - C) > 0 else -ng
    Mg = frame(Pg + ng.normalized() * 0.006, ng, up=(0, 1, 0))
    gear(p, "brass_dark", 0.062, 9, 0.012, depth=0.014, hole=0.024, spokes=3, M=Mg, back=False)
    rivet(p, "gunmetal", Mg @ Vector((0, 0, 0.004)), ng, r=0.02, h=0.01, seg=8)
    mark(p, "pauldron")
    # two brass_dark lames stepping down below the bell
    for (z0, z1, r0, r1) in ((-0.085, -0.155, 0.205, 0.184), (-0.14, -0.21, 0.174, 0.152)):
        span = math.radians(112)
        G = [[Vector((s * 0.025 + s * lerp(r0, r1, t) * math.cos(u * span), 0.76 * lerp(r0, r1, t) * math.sin(u * span),
                      lerp(z0, z1, t))) for u in lin(-1, 1, 11)] for t in (0.0, 1.0)]
        plate(p, "brass_dark", G, 0.012, bevel=(0.004, 1), inward=(s * 0.025, 0, z0), inner=False)
        edge_roll(p, "brass", [Vector((s * 0.025 + s * (r1 + 0.004) * math.cos(u * span), 0.76 * (r1 + 0.004) * math.sin(u * span),
                                       z1 + 0.002)) for u in lin(-1, 1, 11)], r=0.0065, seg=3)
    mark(p, "lames")
    # upper arm (rerebrace) + brass band
    UA = Stack([(-0.06, 0.16, 0.16), (-0.20, 0.172, 0.172), (-0.33, 0.162, 0.165), (-0.40, 0.15, 0.155)], e=2.2)
    UA.loft(p, "iron", lin(-0.06, -0.40, 5), 14)
    ring_band(p, "brass", UA, -0.315, -0.365, 0.008, 0.008, n=14, t=0.01)
    mark(p, "upper arm")
    # elbow ball + couter cup on the back of the elbow
    ball(p, "gunmetal", (0, 0, ELBOW), 0.08, seg=10, rings=6)
    Gc = [[Vector((0, 0.10, ELBOW))]]
    for i in range(1, 5):
        ph = math.radians(80) * i / 4
        Gc.append([Vector((0.094 * math.sin(ph) * math.cos(TAU * j / 14), 0.10 * math.cos(ph),
                           ELBOW + 0.10 * math.sin(ph) * math.sin(TAU * j / 14))) for j in range(14)])
    plate(p, "brass", Gc, 0.012, bevel=(0.004, 1), closed_u=True, inward=(0, 0.0, ELBOW), inner=False)
    rivet(p, "gunmetal", Vector((0, 0.106, ELBOW)), (0, 1, 0), r=0.014, h=0.008)
    mark(p, "elbow")
    arm = done(p.build(torso_obj, loc=(s * SHOULDER[0], SHOULDER[1], SHOULDER[2])))

    # ---- forearm (pivot at the elbow) ----
    p = Part("forearm_" + side)
    gear(p, "brass_dark", 0.074, 9, 0.02, depth=0.014, hole=0.03, spokes=4, back=False,
         M=frame((s * 0.074, 0, 0), (s, 0, 0)), hub=(0.022, 0.03), hub_mat="brass")
    VA = Stack([(-0.04, 0.148, 0.148), (-0.12, 0.158, 0.158), (-0.24, 0.142, 0.142), (-0.30, 0.13, 0.13)], e=2.1)
    VA.loft(p, "iron", lin(-0.04, -0.20, 3), 10)
    mark(p, "gear+vambrace")
    # gauntlet cuff: flared brass bell with rolled rims
    nseg = 18
    rows = [[Vector(((0.083 + 0.031 * t ** 1.4) * math.cos(TAU * j / nseg), (0.083 + 0.031 * t ** 1.4) * math.sin(TAU * j / nseg),
                     lerp(-0.105, -0.29, t))) for j in range(nseg)] for t in lin(0, 1, 3)]
    plate(p, "brass", rows, 0.012, bevel=None, closed_u=True, inward=(0, 0, -0.2))
    edge_roll(p, "brass", [Vector((0.086 * math.cos(TAU * j / nseg), 0.086 * math.sin(TAU * j / nseg), -0.105)) for j in range(nseg + 1)],
              r=0.008, seg=3)
    edge_roll(p, "brass_dark", [Vector((0.116 * math.cos(TAU * j / nseg), 0.116 * math.sin(TAU * j / nseg), -0.29)) for j in range(nseg + 1)],
              r=0.009, seg=4)
    mark(p, "cuff")
    # hand
    hz = HAND - ELBOW
    if s > 0:
        # left: closed fist hanging down, knuckles forward/outward, thumb across the index finger
        rbox(p, "iron", (0.08, 0.11, 0.07), loc=(0.0, -0.005, hz + 0.04), r=0.018, segs=2)
        fist(p, "iron", "brass", Vector((0.0, -0.005, hz - 0.002)), (0, -1, 0), (0, 0, 1), r_in=0.017, fw=0.02,
             spread=0.03, arc=(-95, -285), knuckles=False, seg=5, steps=5)
        tube_pts(p, "iron", bez([(-0.036, -0.05, hz + 0.045), (-0.034, -0.075, hz + 0.005), (-0.005, -0.084, hz - 0.03),
                                 (0.022, -0.076, hz - 0.034)], 5), [0.019, 0.019, 0.017, 0.015, 0.012], seg=6)
    else:
        # right: wraps the vertical halberd shaft (same place as before: hand pivot + (SX, SY))
        S = Vector((SX, SY, hz - 0.02))
        od = Vector((-SX, -SY, 0)).normalized()
        sd = Vector((0, 0, 1)).cross(od)
        palm = S + od * 0.062 + Vector((0, 0, 0.008))
        rbox(p, "iron", (0.075, 0.042, 0.12), r=0.014, segs=2, M=basis(sd, od, (0, 0, 1), palm))
        tube_pts(p, "iron", bez([(0.0, -0.005, hz + 0.08), (0.0, -0.03, hz + 0.055), tuple(palm + Vector((0, 0, 0.045)))], 4),
                 [0.05, 0.047, 0.042, 0.038], seg=10, flat=0.8)
        fist(p, "iron", "brass", S, (0, 0, 1), od, r_in=0.027, fw=0.02, spread=0.03, arc=(48, 300))
        ct = S + Vector((0, 0, 0.058))
        tpts = [ct + (od * math.cos(math.radians(t)) + sd * math.sin(math.radians(t))) * 0.046 for t in (335, 300, 262, 225, 195)]
        tube_pts(p, "iron", [palm + Vector((0, 0, 0.04)) - sd * 0.02] + tpts, [0.02, 0.019, 0.018, 0.017, 0.015, 0.012],
                 seg=6, flat=0.8)
    mark(p, "hand")
    fore = done(p.build(arm, loc=(0, 0, ELBOW)))
    return arm, fore


# =============================================================================================
# SHIELD (rigid, child of forearm_L): gear-shaped, outer side, facing (+X, -Y)
# =============================================================================================
def build_shield(fore_L):
    p = Part("shield")
    R = Matrix.Rotation(math.radians(-45), 4, "Z") @ Matrix.Rotation(math.radians(90), 4, "Y")   # local Z -> (+X,-Y)/sqrt2
    n = R.to_3x3() @ Vector((0, 0, 1))
    for z in (-0.09, 0.09):
        rbox(p, "leather_dark", (0.05, 0.08, 0.05), loc=(0.0, 0.0, 0.025), r=0.006, segs=1, M=R @ M_((0, z, 0)))
    revolve(p, "iron", [(0, 0.045), (0.30, 0.045), (0.30, 0.07), (0, 0.07)], seg=20, M=R)
    gear(p, "iron", 0.375, 11, 0.055, depth=0.064, hole=0.27, M=R @ M_((0, 0, 0.085)), bevel=(0.006, 1), inner_wall=False)
    mark(p, "back+rim")
    # brass dish face
    revolve(p, "brass", [(0.0, 0.135), (0.08, 0.132), (0.16, 0.124), (0.23, 0.113), (0.278, 0.104), (0.29, 0.09),
                         (0.29, 0.065), (0.0, 0.065)], seg=20, M=R)
    mark(p, "dish")
    # engraved ring + raised iron spokes
    revolve(p, "brass_dark", [(0.198, 0.118), (0.212, 0.118), (0.212, 0.124), (0.198, 0.125)], seg=24, M=R, closed=True)
    for k in range(6):
        a = TAU * k / 6
        q2 = piece()
        q2.box("iron", size=(0.19, 0.03, 0.022), loc=(0.175, 0, 0.0))
        merge(p, q2, M=R @ M_((0, 0, 0.122)) @ Matrix.Rotation(a, 4, "Z") @ Matrix.Rotation(math.radians(-6.5), 4, "Y"))
        rivet(p, "brass", R @ Vector((0.245 * math.cos(a), 0.245 * math.sin(a), 0.1235)), n, r=0.01, h=0.006)
    mark(p, "spokes")
    # boss
    revolve(p, "iron", [(0.05, 0.12), (0.098, 0.12), (0.1, 0.14), (0.088, 0.156), (0.06, 0.156)], seg=16, M=R, closed=True)
    revolve(p, "brass", [(0, 0.13), (0.066, 0.13), (0.062, 0.155), (0.04, 0.17), (0, 0.174)], seg=16, M=R)
    gear(p, "brass_dark", 0.05, 8, 0.012, depth=0.01, hole=0.022, M=R @ M_((0, 0, 0.172)), back=False)
    revolve(p, "glow_amber", [(0, 0.165), (0.021, 0.165), (0.018, 0.182), (0.008, 0.19), (0, 0.192)], seg=12, M=R)
    mark(p, "boss")
    return done(p.build(fore_L, loc=(0.11, -0.01, -0.58 - ELBOW)))


# =============================================================================================
# WEAPON (rigid, child of forearm_R): clockwork halberd, shaft along +Z from the hand
# =============================================================================================
def blade_pt(u, v):
    """Crescent axe blade in (y, z) relative to the shaft: attachment (u=0) on the socket front,
    cutting edge (u=1) a crescent; the horns curve down/up (concave outlines)."""
    zb = 1.27 + 0.16 * (v - 0.5) * 2
    yb = -0.03
    ang = (v - 0.5) * 2.0
    ze = 1.32 + 0.33 * ang + 0.02 * ang ** 3
    ye = -0.40 + 0.085 * ang * ang
    y = yb + (ye - yb) * u
    z = zb + (ze - zb) * u
    z -= 0.075 * math.sin(math.pi * min(u, 1.0)) * ang * (1 - 0.3 * u)
    return y, z


def build_weapon(fore_R):
    p = Part("weapon")
    Ms = M_((SX, SY, 0))
    revolve(p, "wood_dark", [(0, -0.60), (0.026, -0.60), (0.026, 1.10), (0, 1.10)], seg=8, M=Ms)
    prof = [(0.0296 if k % 2 == 0 else 0.0274, -0.17 + 0.32 * k / 9) for k in range(10)]
    revolve(p, "leather_dark", [(0, -0.172)] + prof + [(0, 0.152)], seg=8, M=Ms)
    for z in (-0.32, 0.42, 0.96):
        revolve(p, "brass", [(0, z - 0.02), (0.031, z - 0.02), (0.035, z), (0.031, z + 0.02), (0, z + 0.02)], seg=10, M=Ms)
    revolve(p, "iron", [(0, -0.585), (0.031, -0.585), (0.034, -0.62), (0.028, -0.66), (0.012, -0.74), (0, -0.78)], seg=8, M=Ms)
    mark(p, "shaft")
    # head: socket, gear collar, aether core
    revolve(p, "brass", [(0, 1.0), (0.034, 1.0), (0.04, 1.035), (0.034, 1.06), (0.034, 1.135), (0.045, 1.145),
                         (0.045, 1.24), (0, 1.25)], seg=12, M=Ms)
    gear(p, "brass_dark", 0.072, 10, 0.026, depth=0.016, hole=0.03, M=Ms @ M_((0, 0, 1.085)), inner_wall=False)
    revolve(p, "glow_amber", [(0.044, 1.175), (0.05, 1.185), (0.05, 1.205), (0.044, 1.215)], seg=10, M=Ms, closed=True)
    revolve(p, "iron", [(0, 1.25), (0.034, 1.25), (0.031, 1.45), (0.036, 1.46), (0.036, 1.48), (0, 1.48)], seg=10, M=Ms)
    for s in (1, -1):
        p.box("iron", size=(0.012, 0.02, 0.18), loc=(SX + s * 0.028, SY, 0.92))
    mark(p, "head")
    # crescent axe blade toward -Y: iron body + polished steel edge band with a sharp ridge
    nv = 12

    def th(u):
        return 0.034 * (1 - u) ** 0.8 + 0.004

    for (us_, mat) in ((lin(0.0, 0.78, 4), "iron"), (lin(0.78, 1.0, 3), "steel")):
        rings = []
        vs = lin(0, 1, nv)
        for u in us_:
            ring = [Vector((SX + th(u) / 2, SY + blade_pt(u, v)[0], blade_pt(u, v)[1])) for v in vs]
            ring += [Vector((SX - th(u) / 2, SY + blade_pt(u, v)[0], blade_pt(u, v)[1])) for v in reversed(vs)]
            rings.append(ring)
        q = piece()
        loft_rings(q, mat, rings, caps=(us_[0] == 0.0, False))
        if mat == "steel":
            bm = q.bm
            nv2 = 2 * nv
            vl = list(bm.verts)[-nv2:]
            mi = q._mi("steel")
            rv = [bm.verts.new(Vector((SX, SY + blade_pt(1.012, v)[0], blade_pt(1.012, v)[1]))) for v in vs]
            for k in range(nv - 1):
                bm.faces.new((vl[k], vl[k + 1], rv[k + 1], rv[k])).material_index = mi
                bm.faces.new((vl[nv2 - 2 - k], vl[nv2 - 1 - k], rv[k], rv[k + 1])).material_index = mi
            bm.faces.new((vl[0], rv[0], vl[nv2 - 1])).material_index = mi
            bm.faces.new((vl[nv - 1], vl[nv], rv[nv - 1])).material_index = mi
        merge(p, q)
    y, z = blade_pt(0.30, 0.5)
    for s in (1, -1):
        Mr = frame((SX + s * (th(0.30) / 2 + 0.002), SY + y, z), (s, 0, 0))
        gear(p, "brass", 0.046, 8, 0.008, depth=0.011, hole=0.016, M=Mr, back=False)
        rivet(p, "brass_dark", Mr @ Vector((0, 0, 0.0)), (s, 0, 0), r=0.016, h=0.008)
        inl = [Vector((SX + s * (th(0.64) / 2 + 0.001), SY + blade_pt(0.64, v)[0], blade_pt(0.64, v)[1])) for v in lin(0.1, 0.9, 9)]
        tube_pts(p, "brass", inl, 0.0045, seg=3)
    mark(p, "blade")
    # back hook (fluke) toward +Y, curving down
    pts = bez([(SX, SY + 0.03, 1.33), (SX, SY + 0.14, 1.34), (SX, SY + 0.24, 1.30), (SX, SY + 0.29, 1.21)], 7)
    tube_pts(p, "iron", pts, [0.036, 0.032, 0.026, 0.02, 0.013, 0.007, 0.0], seg=6, flat=0.45, up=(1, 0, 0))
    # top spike (leaf-shaped, diamond section)
    SP = Stack([(1.47, 0.055, 0.055), (1.52, 0.045, 0.038), (1.62, 0.07, 0.032), (1.73, 0.055, 0.024),
                (1.84, 0.026, 0.013), (1.92, 0.004, 0.003)], e=1.25)
    rings = [[v + Vector((SX, SY, 0)) for v in SP.ring(z, 8, a0=0.0)] for z in lin(1.47, 1.92, 9)]
    rings.append([Vector((SX, SY, 1.935))])
    loft_rings(p, "steel", rings, caps=(True, False))
    revolve(p, "brass", [(0, 1.455), (0.038, 1.455), (0.044, 1.47), (0.038, 1.485), (0, 1.485)], seg=12, M=Ms)
    mark(p, "hook+spike")
    return done(p.build(fore_R, loc=(0, 0, HAND - ELBOW)))


# =============================================================================================
# KEY (rigid, child of torso): big wind-up key out of the back along +Y, spins around local Y
# =============================================================================================
def build_key(torso_obj):
    p = Part("key")
    MY = basis((1, 0, 0), (0, 0, -1), (0, 1, 0))     # local Z -> +Y
    revolve(p, "brass", [(0, 0.0), (0.03, 0.0), (0.03, 0.20), (0.036, 0.21), (0.036, 0.235), (0, 0.235)], seg=12, M=MY)
    gear(p, "brass_dark", 0.06, 8, 0.016, depth=0.013, M=MY @ M_((0, 0, 0.07)), back=False)
    revolve(p, "brass", [(0, 0.15), (0.038, 0.15), (0.042, 0.16), (0.038, 0.17), (0, 0.17)], seg=12, M=MY)
    mark(p, "shaft")
    for sz in (1, -1):
        R0, hw, ht = 0.072, 0.019, 0.017
        revolve(p, "brass", [(R0 - hw, -ht), (R0 + hw - 0.007, -ht), (R0 + hw, -ht + 0.007), (R0 + hw, ht - 0.007),
                             (R0 + hw - 0.007, ht), (R0 - hw, ht)], seg=16, closed=True,
                M=basis((0, 1, 0), (0, 0, 1), (1, 0, 0), (0, 0.315, sz * 0.118)))
    q = piece()
    prism(q, "brass", [(0.225, 0.0), (0.27, 0.065), (0.36, 0.05), (0.40, 0.0), (0.36, -0.05), (0.27, -0.065)], 0.036, axis="x")
    merge(p, q, bevel=(0.006, 1, 30))
    for sx in (1, -1):
        Mr = frame((sx * 0.018, 0.31, 0.0), (sx, 0, 0))
        revolve(p, "brass_dark", [(0.032, -0.002), (0.03, 0.007), (0.014, 0.012), (0, 0.013)], seg=10, M=Mr)
    revolve(p, "brass", [(0, 0.395), (0.02, 0.40), (0.02, 0.42), (0.012, 0.43), (0, 0.432)], seg=10, M=MY)
    mark(p, "bow")
    return done(p.build(torso_obj, loc=(0, 0.25, 0.36)))


# =============================================================================================
# LEGS
# =============================================================================================
FOOT = [(0.125, 0.14, 0.075), (0.10, 0.18, 0.125), (0.04, 0.215, 0.15), (-0.04, 0.23, 0.145),
        (-0.12, 0.23, 0.12), (-0.20, 0.215, 0.095), (-0.26, 0.18, 0.072), (-0.30, 0.13, 0.052)]
ZG = -(LEG_Z + KNEE)          # shin-local z of the ground (= -0.50)


def foot_pt(y, a, off):
    ys = [st[0] for st in FOOT][::-1]
    w = pchip(ys, [st[1] for st in FOOT][::-1], y)
    h = pchip(ys, [st[2] for st in FOOT][::-1], y)
    x, zz = se(a, w / 2 + off, h / 2 + off, 2.6)
    return Vector((x, y, ZG + h / 2 + zz))


def build_leg(s, hips_obj):
    side = "L" if s > 0 else "R"
    p = Part("leg_" + side)
    TH = Stack([(0.07, 0.195, 0.205), (0.02, 0.23, 0.24), (-0.12, 0.24, 0.25, -0.005), (-0.28, 0.226, 0.236, -0.005),
                (-0.38, 0.205, 0.215), (-0.44, 0.185, 0.195)], e=2.3)
    TH.loft(p, "iron", lin(0.07, -0.44, 6), 14)

    def cu(u, z, off=0.012):
        P = TH.pt(front_angle(u, 1.25), z, off)
        k = max(0.0, 1 - abs(u) / 0.3)
        P.y -= 0.012 * k * k
        return P
    G = [[cu(u, z) for u in lin(-1, 1, 9)] for z in lin(-0.02, -0.37, 5)]
    plate(p, "iron", G, 0.012, bevel=(0.005, 1), inward=(0, 0.05, -0.2), inner=False)
    edge_roll(p, "brass", [cu(u, -0.372, 0.017) for u in lin(-1, 1, 9)], r=0.008, seg=4)
    G = [[cu(u * 0.14, z, 0.014) for u in lin(-1, 1, 3)] for z in lin(-0.03, -0.365, 5)]
    plate(p, "brass", G, 0.006, bevel=(0.003, 1), inward=(0, 0.05, -0.2), inner=False)
    mark(p, "thigh")
    # hip gear on the outer side, centred on the hip axis
    gear(p, "brass", 0.10, 10, 0.024, depth=0.016, hole=0.045, spokes=4, back=False, M=frame((s * 0.122, 0, 0), (s, 0, 0)),
         hub=(0.03, 0.04), hub_mat="brass_dark")
    mark(p, "hip gear")
    # knee ball + poleyn (knee cop) on the front
    ball(p, "gunmetal", (0, 0, KNEE), 0.085, seg=12, rings=6)
    Gp = [[Vector((0, -0.125, KNEE))]]
    for i in range(1, 6):
        ph = math.radians(84) * i / 5
        Gp.append([Vector((0.115 * math.sin(ph) * math.cos(TAU * j / 16), -0.125 * math.cos(ph),
                           KNEE + 0.11 * math.sin(ph) * math.sin(TAU * j / 16))) for j in range(16)])
    plate(p, "brass", Gp, 0.014, bevel=(0.005, 1), closed_u=True, inward=(0, 0, KNEE), inner=False)
    rivet(p, "brass_dark", Vector((0, -0.131, KNEE)), (0, -1, 0), r=0.02, h=0.01, seg=8)
    mark(p, "knee")
    leg = done(p.build(hips_obj, loc=(s * LEG_X, 0, LEG_Z - HIP_Z)))

    # ---- shin (pivot at the knee) ----
    p = Part("shin_" + side)
    gear(p, "brass_dark", 0.082, 9, 0.02, depth=0.014, hole=0.032, spokes=4, back=False,
         M=frame((s * 0.098, 0.005, 0), (s, 0, 0)), hub=(0.024, 0.032), hub_mat="brass")
    mark(p, "knee gear")
    GR = Stack([(-0.03, 0.172, 0.182), (-0.07, 0.205, 0.22, -0.010, 0.015), (-0.16, 0.224, 0.238, -0.012, 0.022),
                (-0.26, 0.206, 0.22, -0.006, 0.016), (-0.33, 0.178, 0.188, 0.0, 0.008), (-0.38, 0.172, 0.182)], e=2.3)
    GR.loft(p, "iron", lin(-0.03, -0.38, 7), 14)
    ring_band(p, "brass", GR, -0.055, -0.095, 0.008, 0.01, n=18, t=0.012)
    G = [[GR.pt(-math.pi / 2 + u * 0.16, z, 0.003) for u in lin(-1, 1, 3)] for z in lin(-0.097, -0.345, 6)]
    plate(p, "brass", G, 0.008, bevel=(0.003, 1), inward=(0, 0, -0.2), inner=False)
    G = [[Vector(((0.096 + 0.012 * t) * math.cos(TAU * j / 16), (0.101 + 0.012 * t) * math.sin(TAU * j / 16), z))
          for j in range(16)] for t, z in zip(lin(0, 1, 2), lin(-0.345, -0.40, 2))]
    plate(p, "brass", G, 0.012, bevel=None, closed_u=True, inward=(0, 0, -0.37), inner=False)
    mark(p, "greave")
    # sabaton: gunmetal foot core, overlapping iron lames with brass rims, brass toe cap, sole
    rings = []
    for (y, w, h) in FOOT:
        ring = []
        for i in range(10):
            x, zz = se(TAU * i / 10, w / 2, h / 2, 2.6)
            ring.append(Vector((x, y, max(ZG + h / 2 + zz, ZG + 0.012))))
        rings.append(ring)
    rings.append([Vector((0, -0.315, ZG + 0.02))])
    loft_rings(p, "gunmetal", rings, caps=(True, False))
    for k, (y0, y1) in enumerate(((0.06, -0.075), (-0.055, -0.20))):
        G = [[foot_pt(y, a, 0.010 + 0.004 * k + 0.006 * t) for a in lin(math.radians(8), math.radians(172), 9)]
             for t, y in zip(lin(0, 1, 2), lin(y0, y1, 2))]
        plate(p, "iron", G, 0.010, bevel=(0.004, 1), inward=(0, (y0 + y1) / 2, ZG), inner=False)
        edge_roll(p, "brass", [foot_pt(y1 - 0.002, a, 0.017 + 0.004 * k) for a in lin(math.radians(8), math.radians(172), 9)],
                  r=0.006, seg=3)
    G = [[foot_pt(y, a, 0.012 + 0.006 * t) for a in lin(math.radians(5), math.radians(175), 9)]
         for t, y in zip(lin(0, 1, 3), lin(-0.19, -0.29, 3))]
    plate(p, "brass", G, 0.010, bevel=(0.004, 1), inward=(0, -0.24, ZG + 0.01), inner=False)
    rbox(p, "gunmetal", (0.22, 0.44, 0.026), loc=(0, -0.09, ZG + 0.013), r=0.01, segs=1)
    rbox(p, "iron", (0.12, 0.04, 0.08), loc=(0, 0.135, ZG + 0.07), r=0.012, segs=1)
    mark(p, "sabaton")
    shin = done(p.build(leg, loc=(0, 0, KNEE)))
    return leg, shin


# =============================================================================================
# BUILD
# =============================================================================================
hips = build_hips()
torso = build_torso(hips)
head = build_head(torso)
arm_L, forearm_L = build_arm(1, torso)
arm_R, forearm_R = build_arm(-1, torso)
leg_L, shin_L = build_leg(1, hips)
leg_R, shin_R = build_leg(-1, hips)
build_tabard("F", hips)
build_tabard("B", hips)
shield = build_shield(forearm_L)
weapon = build_weapon(forearm_R)
key = build_key(torso)

total = tri_report()
print(f"[knight] TOTAL {total} tris (budget 25000), {len(bpy.data.materials)} materials")

if COST:
    sys.exit(0)
if QUICK:
    bpy.context.view_layer.update()
    hp.bake_vertex_ao(samples=16, distance=0.3, strength=0.85, floor=0.3, ground=0.0)
    hp.render_views("knight_wip", size=720)
    hp.render_hp("knight_wip_face", target=((0, -0.1, 1.95), 0.36), azimuth=25, elevation=8, size=640)
    hp.render_hp("knight_wip_game", azimuth=30, elevation=25, dist_k=4, size=480)
    for a in ARGS:
        if a.startswith("shot="):          # shot=name:x,y,z,radius,azimuth,elevation (extra close-ups)
            nm, vals = a[5:].split(":")
            x, y, z, r, az, el = (float(v) for v in vals.split(","))
            hp.render_hp("knight_wip_" + nm, target=((x, y, z), r), azimuth=az, elevation=el, size=560)
    sys.exit(0)

# =============================================================================================
# RIG (one skinned mesh + rigid weapon / shield / key), AO, EXPORT
# =============================================================================================
arm = rig_from_parts(root, rigid={"weapon", "shield", "key"}, smooth={}, influence={}, skin_name="knight_skin")
skin = bpy.data.objects["knight_skin"]
# tabard cloth: soft hinge under the belt and a soft bend at the seam (seam-continuous weights). No thigh
# weights: the game swings each panel with the most-forward / most-backward thigh (rig.ts thighFollow).
reweight_chain(arm, skin, "__tabard_F", ["tabard_F_1", "tabard_F_2"], radius=0.08, anchor_radius=0.04)
reweight_chain(arm, skin, "__tabard_B", ["tabard_B_1", "tabard_B_2"], radius=0.08, anchor_radius=0.04)
bpy.context.view_layer.update()


def ao_tint(p, n):
    """Slight grime toward the feet and a touch of sky light on up-facing surfaces."""
    k = 0.86 + 0.14 * smooth01(p.z / 0.9)
    up = 1.0 + 0.05 * max(0.0, n.z)
    return (k * up, k * up, k * up)


hp.bake_vertex_ao(samples=40, distance=0.32, strength=0.85, floor=0.3, ground=0.0, tint=ao_tint)
hp.export_glb_hp("knight")

# ---- previews ------------------------------------------------------------------------------
from rig_helpers import pose_world, reset_pose
hp.render_views("knight", size=720)
hp.render_hp("knight_face", target=((0, -0.1, 1.95), 0.36), azimuth=25, elevation=8, size=640)
hp.render_hp("knight_game", azimuth=30, elevation=25, dist_k=7, size=480)


def pose_hp(rotations, views):
    pose_world(arm, rotations)
    for (fn, az, el) in views:
        hp.render_hp(fn, azimuth=az, elevation=el, size=640)
    reset_pose(arm)


TEST = dict(HUMANOID_TEST_POSE)
# game: F follows the most-forward thigh (leg_L 45 deg -> F_1 -40, F_2 -9), B the most-backward (20 -> 17, 4)
TEST.update({"tabard_F_1": [("X", -40)], "tabard_F_2": [("X", -9)],
             "tabard_B_1": [("X", 17)], "tabard_B_2": [("X", 4)]})
pose_hp(TEST, [("knight_pose", 35, 18), ("knight_pose_back", 215, 15)])
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
    "tabard_F_1": [("X", -45)], "tabard_F_2": [("X", -10)],   # leg_L 50 deg forward
    "tabard_B_1": [("X", 17)], "tabard_B_2": [("X", 4)],      # leg_R 20 deg back
}
pose_hp(ATTACK, [("knight_attack", 35, 12), ("knight_attack_side", 90, 8)])
# deep bends: elbows / knees ~90-100 deg, legs apart (dodge-like crouch) - checks the ball joints
BEND = {
    "torso": [("X", 20)],
    "arm_L": [("X", -60)], "forearm_L": [("X", -95)],
    "arm_R": [("X", -50)], "forearm_R": [("X", -90)],
    "leg_L": [("X", -70), ("Y", -8)], "shin_L": [("X", 100)],
    "leg_R": [("X", -40), ("Y", 8)], "shin_R": [("X", 95)],
    "tabard_F_1": [("X", -63)], "tabard_F_2": [("X", -15)],
}
pose_hp(BEND, [("knight_bend", 40, 10), ("knight_bend_side", 95, 5)])


def pose_closeups(rotations, shots):
    """EEVEE close-ups framed on posed bone heads: shots = [(file, bone, radius, azimuth, elevation)]."""
    pose_world(arm, rotations)
    for (fn, bone, rad, az, el) in shots:
        c = arm.matrix_world @ arm.pose.bones[bone].head
        hp.render_hp(fn, target=(c, rad), azimuth=az, elevation=el, size=480)
    reset_pose(arm)


pose_closeups(BEND, [("knight_joint_elbow", "forearm_R", 0.28, -75, 10), ("knight_joint_elbow_back", "forearm_L", 0.28, 150, 15),
                     ("knight_joint_knee", "shin_L", 0.32, 75, 5),
                     ("knight_joint_knee_front", "shin_R", 0.32, -20, 15)])
# game-like poses (rig.ts humanoid locomotion): battle "ready" stance and a walking stride
READY = {
    "torso": [("X", 5), ("Z", 14)], "head": [("Z", -11)],
    "arm_R": [("X", -29), ("Y", 6)], "forearm_R": [("X", -24)],
    "arm_L": [("Y", -6)], "forearm_L": [("X", -8)],
    "leg_L": [("X", -14), ("Y", -5)], "shin_L": [("X", 17)],
    "leg_R": [("X", 11), ("Y", 5)], "shin_R": [("X", 16)],
    "tabard_F_1": [("X", -13)], "tabard_B_1": [("X", 9)],
}
WALK = {
    "torso": [("X", 6), ("Z", 7)],
    "arm_L": [("X", 30), ("Y", -6)], "forearm_L": [("X", -25)],
    "arm_R": [("X", -20), ("Y", 6)], "forearm_R": [("X", -20)],
    "leg_L": [("X", -37)], "shin_L": [("X", 10)],
    "leg_R": [("X", 37)], "shin_R": [("X", 55)],
    "tabard_F_1": [("X", -33)], "tabard_F_2": [("X", -7)], "tabard_B_1": [("X", 31)], "tabard_B_2": [("X", 7)],
}
pose_hp(READY, [("knight_ready", 30, 12), ("knight_ready_side", -80, 8)])
pose_hp(WALK, [("knight_walk", 60, 10)])
