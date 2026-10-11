"""Brass Beetle — armored medium enemy (~0.75 m tall, ~1.3 m long). Hi-poly.
Exports public/models/beetle.glb.

Skeleton (RIG_SPEC.md), armature object 'root':
  body (root bone, pivot z=0.36) > head > horn, antenna_L, antenna_R
                                 > shell_L, shell_R          elytra, pivot at the hinge (top-front, midline)
                                 > leg_FL > leg_FL_2, leg_ML > leg_ML_2, leg_BL > leg_BL_2  (and _R)
  upper leg pivots at the hip ball on the body side, the lower `_2` segment at the knee ball.
Faces -Y. All joints are mechanical (ball joints / sockets) -> rigid weights.

Construction: every bone is a set of world-space pieces (hp_beetle_helpers.BoneBuilder) that are
smoothed separately and joined into one rigid part, then rig_from_parts() skins them.
  * elytra + pronotum: closed thick parametric domes (polished brass outside, finished brass_dark /
    iron underside), engraved panel grooves with dark inlay, rolled rims, rivet rows and gear
    medallions bent onto the surface (conform)
  * under the elytra (seen when the shells open): machinery bay with a glowing aether core in a
    brass cage, gears and folded mechanical wings (brass ribs + translucent membrane)
  * head: brass_dark capsule with a polished face plate + cheek plates, caged glow_green lamp eyes,
    steel mandibles, lamellate antennae; big banded horn with a steel tip on a ball socket
  * legs: hip balls in socket rings, keeled brass femur armour with a hydraulic piston, knee ball
    joints in cups, faceted gunmetal tibiae with brass greaves and steel spines (front: digging
    teeth), bead tarsi and hooked claws
  * vertex AO baked twice (shells closed / removed) and blended, so the bay that is only seen with
    the shells open is not pitch black (hp_beetle_helpers.bake_ao_open)

Materials (8): brass_polish, brass_dark, copper, iron, gunmetal, steel, glow_green, jelly_wing.
Previews: beetle(_front/_side/_back/_top/_game/_head).png, beetle_pose*.png (rig.ts stunned shells
open, attack windup, gait); `-- check` adds beetle_chk_*.png close-ups, `-- quick` skips some poses.

Usage: blender -b --factory-startup -P tools/blender/model_beetle.py [-- quick] [check]
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import hp_helpers as hp  # noqa: E402
from common import empty, get_mat, reset_scene  # noqa: E402
from hp_beetle_helpers import (BoneBuilder, _face, bake_ao_open, ball, bolt, catmull, conform,  # noqa: E402
                               dome, gear_ring, grid_faces, grid_rows, lathe_m, mark, mtx, resample,
                               set_mat, smoothstep, sp, sweep, thick_patch, torus_m)
from rig_helpers import pose_world, reset_pose, rig_from_parts  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
QUICK = "quick" in ARGS

reset_scene()
root = empty("root")

# ---- materials (8) ---------------------------------------------------------------------------
BR = "brass_polish"      # carapace, horn, femurs
BD = "brass_dark"        # rims, bands, inlays, undersides
CU = "copper"            # gears
IR = "iron"              # hull / underside
GM = "gunmetal"          # head, tibiae
ST = "steel"             # tips, claws, mandible blades, spines
GL = "glow_green"        # eyes, aether core, medallion gems
WG = "jelly_wing"        # wing membrane (translucent)
get_mat(BR, hex="#d2aa50", metallic=0.92, roughness=0.27)
for _m in (BD, CU, IR, GM, ST, GL):
    get_mat(_m)
get_mat(WG, hex="#5fbf98", metallic=0.0, roughness=0.25, alpha=0.65)
HORN_MAT = BR

ROUND = 75.0     # smoothing angle for round pieces (tubes, balls, rivets)
HARD = 34.0      # smoothing angle for plates / gears

V = Vector
BODY_P = V((0, 0, 0.36))
HEAD_P = V((0, -0.375, 0.425))
HORN_P = V((0, -0.532, 0.478))
EX = 2 / 2.6     # superellipse exponent of the dome sections


def mirror(v, s):
    return V((v[0] * s, v[1], v[2]))


def merge_samples(base, extra, tol):
    out = sorted(set(round(x, 6) for x in extra))
    for b in base:
        if all(abs(b - e) > tol for e in out):
            out.append(b)
    return sorted(out)


def groove_rows(c, w):
    return [c - w, c - w / 3, c + w / 3, c + w]


def in_groove(x, c, w):
    return abs(x - c) < w * 0.5


def s_dist(u):
    """sample distribution along the shells: denser toward the rear tip"""
    return 0.42 * u + 0.58 * math.sin(u * math.pi / 2)


def medallion(hard, rnd, bvh, c, nrm, along, R, teeth, spokes, gem=0.008):
    """Gear medallion bent onto a dome: brass_dark bezel cup, copper ring gear, glow gem hub."""
    M = mtx(c, nrm, along)
    mk = mark(hard, rnd)
    lathe_m(hard, BD, [(R, -0.004), (R * 0.97, 0.006), (R * 0.88, 0.0095), (R * 0.77, 0.008),
                       (R * 0.74, 0.002), (0.0, 0.002)], M, seg=max(20, teeth * 2), cap=(False, False))
    gear_ring(hard, CU, M @ Matrix.Translation((0, 0, 0.0015)), R * 0.69, R * 0.59, teeth, 0.0085,
              r_hole=R * 0.43, spokes=spokes, hub=R * 0.17, hub_h=0.011, spoke_w=R * 0.13, mat_hub=BD,
              bottom=False, hub_seg=10)
    conform(mk, bvh, M)
    dome(rnd, GL, c + nrm * 0.011, nrm, gem, h=gem * 0.8, seg=8)
    return M


# =============================================================================================
# Elytra (shell_L / shell_R)
# =============================================================================================
EL_Y0, EL_Y1, EL_QA = -0.075, 0.575, -0.42
EL_W, EL_H, EL_HB, EL_T = 0.300, 0.225, 0.13, 0.014
EL_PHI = math.radians(104)
GAP = 0.0025


def _fw(q, m):
    return max(0.0, 1 - abs(q) ** m) ** (1 / m)


def el_surf(s, t, side, inset=0.0):
    y1 = EL_Y1 - inset
    q = EL_QA + (1 - EL_QA) * s
    fw, fh = _fw(q, 2.8), _fw(q, 2.3)
    W = (EL_W - inset) * fw
    H = (EL_H - inset) * fh
    Hb = (EL_HB - inset * 0.5) * fw
    zeq = 0.40 - 0.02 * s * s
    phi = t * EL_PHI
    x = W * sp(math.sin(phi), EX)
    c = math.cos(phi)
    z = zeq + (H if c >= 0 else Hb) * sp(c, EX)
    y = EL_Y0 + (y1 - EL_Y0) * s
    return V((side * (GAP + x), y, z))


def el_normal(s, t, side):
    e = 1e-3
    a = el_surf(min(s + e, 1.0), t, side) - el_surf(max(s - e, 0.0), t, side)
    b = el_surf(s, min(t + e, 1.0), side) - el_surf(s, max(t - e, 0.0), side)
    n = a.cross(b).normalized()
    out = el_surf(s, t, side) - el_surf(s, t, side, EL_T)
    return n if n.dot(out) > 0 else -n


EL_GT = (0.50, 0.80)      # longitudinal grooves (t)
EL_GS = (0.11, 0.80)      # transverse grooves (s): front band | rear cap
EL_WT, EL_WS = 0.026, 0.018
EL_DEPTH = 0.0045


def el_depth(s, t):
    lo, hi = EL_GS
    for tg in EL_GT:
        if in_groove(t, tg, EL_WT) and lo - EL_WS < s < hi + EL_WS:
            return EL_DEPTH
    for sg in EL_GS:
        if in_groove(s, sg, EL_WS) and 0.015 < t < 0.985:
            return EL_DEPTH
    return 0.0


def el_mat(u0, u1, v0, v1):
    lo, hi = EL_GS
    for tg in EL_GT:
        if in_groove(v0, tg, EL_WT) and in_groove(v1, tg, EL_WT) and lo - EL_WS < u0 and u1 < hi + EL_WS:
            return BD
    for sg in EL_GS:
        if in_groove(u0, sg, EL_WS) and in_groove(u1, sg, EL_WS) and v0 > 0.01 and v1 < 0.99:
            return BD
    return None


def build_shell(side, name, parent):
    sx = side
    top = el_surf(0.0, 0.0, side)
    piv = V((sx * GAP, top.y, top.z))         # hinge: top of the front edge on the midline
    bb = BoneBuilder(name, piv)
    hard = bb.piece(smooth=HARD)
    rnd = bb.piece(smooth=ROUND)
    # --- dome: polished brass outside, finished brass_dark underside ---
    extra_s = [x for g in EL_GS for x in groove_rows(g, EL_WS)]
    us = merge_samples([s_dist(i / 18) for i in range(19)], extra_s, EL_WS * 0.95)
    vs = merge_samples([i / 12 for i in range(13)], [x for g in EL_GT for x in groove_rows(g, EL_WT)],
                       EL_WT * 0.95)
    res = thick_patch(hard, lambda u, v: el_surf(u, v, side), lambda u, v: el_surf(u, v, side, EL_T),
                      us, vs, BR, mat_in=BD, mat_edge=BD, us_in=[s_dist(i / 10) for i in range(11)],
                      vs_in=[i / 6 for i in range(7)], depth=el_depth, outer_mat=el_mat)
    bvh = res["bvh"]

    # --- rolled rim: outer edge -> around the tip -> sutural bead along the midline ---
    def mid(u, v):
        return (el_surf(u, v, side) + el_surf(u, v, side, EL_T)) * 0.5
    outer = [mid(s_dist(i / 24), 1.0) + el_normal(s_dist(i / 24), 0.97, side) * 0.003 for i in range(24)]
    inner = [mid(s_dist(i / 24), 0.0) + V((sx * 0.0018, 0, 0.003)) for i in range(23, -1, -1)]
    path = resample(catmull(outer + [mid(1.0, 0.5)] + inner, 2), 42)
    n = len(path)
    radii = [0.0105 if i / (n - 1) < 0.42 else 0.0105 - 0.0038 * smoothstep(0.42, 0.6, i / (n - 1))
             for i in range(n)]
    sweep(rnd, BD, path, radii, seg=6)
    # --- rivets: front band, side band, rear cap ---
    spots = [(0.055, t) for t in (0.14, 0.32, 0.66)] + [(s, 0.905) for s in (0.2, 0.36, 0.52, 0.68)] \
        + [(0.875, t) for t in (0.2, 0.42, 0.64)]
    for s, t in spots:
        dome(rnd, BD, el_surf(s, t, side), el_normal(s, t, side), 0.0085)
    # --- gear medallion on the dome ---
    s0, t0 = 0.45, 0.215
    c = el_surf(s0, t0, side)
    nrm = el_normal(s0, t0, side)
    along = (el_surf(s0 + 0.01, t0, side) - c).normalized()
    medallion(hard, rnd, bvh, c, nrm, along, 0.066, 9, 4)
    # --- underside ribs (seen when open) + hinge knuckle ---
    for tt in (0.48,):
        pts = [el_surf(0.05 + 0.8 * s_dist(i / 8), tt, side, EL_T + 0.003) for i in range(9)]
        sweep(rnd, BD, pts, [0.0] + [0.0065] * 7 + [0.0], seg=5)
    ball(rnd, BD, piv + V((sx * 0.03, 0.012, -0.022)), 0.015, seg=6, rings=4)
    return bb.build(parent, BODY_P)


# =============================================================================================
# Body: hull, pronotum, machinery bay
# =============================================================================================
HULL = [  # y, half-width, z bottom, z top, superellipse n
    (-0.405, 0.075, 0.37, 0.475, 2.2),
    (-0.37, 0.135, 0.30, 0.525, 2.4),
    (-0.30, 0.185, 0.235, 0.565, 2.6),
    (-0.20, 0.21, 0.205, 0.575, 2.8),
    (-0.08, 0.215, 0.195, 0.57, 2.8),
    (0.00, 0.22, 0.19, 0.535, 3.0),
    (0.10, 0.235, 0.185, 0.505, 3.2),
    (0.22, 0.24, 0.185, 0.50, 3.2),
    (0.34, 0.225, 0.20, 0.49, 3.0),
    (0.44, 0.18, 0.235, 0.47, 2.8),
    (0.51, 0.12, 0.27, 0.445, 2.6),
    (0.555, 0.05, 0.31, 0.42, 2.4),
]
HULL_TIP = (0.568, 0.37)


def hull_sec(y):
    if y <= HULL[0][0]:
        return HULL[0][1:]
    for a, b in zip(HULL, HULL[1:]):
        if a[0] <= y <= b[0]:
            f = (y - a[0]) / (b[0] - a[0])
            return tuple(a[i] + (b[i] - a[i]) * f for i in range(1, 5))
    return HULL[-1][1:]


def hull_x(y, z):
    hw, zb, zt, n = hull_sec(y)
    zc, hh = (zb + zt) / 2, (zt - zb) / 2
    r = min(1.0, abs(z - zc) / hh)
    return hw * max(0.0, 1 - r ** n) ** (1 / n)


def hull_ztop(x, y):
    hw, zb, zt, n = hull_sec(y)
    zc, hh = (zb + zt) / 2, (zt - zb) / 2
    r = min(1.0, abs(x) / hw)
    return zc + hh * max(0.0, 1 - r ** n) ** (1 / n)


def hull_ring(y, k=1.0, seg=16):
    hw, zb, zt, n = hull_sec(y)
    zc, hh = (zb + zt) / 2, (zt - zb) / 2
    e = 2 / n
    return [V((hw * k * sp(math.cos(2 * math.pi * i / seg), e), y,
               zc + hh * k * sp(math.sin(2 * math.pi * i / seg), e))) for i in range(seg)]


def build_hull(p):
    bm = p.bm
    rings = [hull_ring(y) for y in (-0.405, -0.385, -0.35, -0.30, -0.22, -0.13, -0.05)]
    # abdomen: overlapping ventrite plates (each plate starts proud and tapers into the next)
    edges = [0.02, 0.12, 0.22, 0.32, 0.42, 0.50]
    trims = []
    for a, b in zip(edges, edges[1:]):
        rings.append(hull_ring(a, 1.0))
        trims.append(len(rings))
        rings.append(hull_ring(a + 0.005, 1.045))
        rings.append(hull_ring(a + 0.02, 1.04))
        rings.append(hull_ring(b - 0.004, 1.0))
    rings.append(hull_ring(0.535, 1.0))
    rows = grid_rows(bm, rings)
    fs = grid_faces(bm, rows, close_v=True)
    fs.append(_face(bm, list(reversed(rows[0]))))
    tv = bm.verts.new(V((0, HULL_TIP[0], HULL_TIP[1])))
    last = rows[-1]
    for i in range(len(last)):
        fs.append(_face(bm, [last[i], last[(i + 1) % len(last)], tv]))
    set_mat(p, fs, IR)
    deck = [f for f in fs if f and f.calc_center_median().z > 0.462 and -0.07 < f.calc_center_median().y < 0.5]
    set_mat(p, deck, BD)
    nv = len(rings[0])
    for r in trims:     # faces between ring r and r+1 (grid_faces order: row-major, nv per row)
        set_mat(p, fs[r * nv:(r + 1) * nv], BD)


PR_PHI = math.radians(112)
PR_T = 0.014


def pr_surf(s, t, inset=0.0):
    phi = t * PR_PHI
    yf = -0.428 + 0.062 * (1 - t * t)
    yr = -0.045 - 0.016 * t * t
    y = yf + (yr - yf) * s
    W = 0.212 + 0.078 * (1 - (1 - s) ** 2)
    ztop = 0.528 + 0.122 * (1 - (1 - s) ** 2)
    zeq = 0.452 - 0.042 * s
    H = ztop - zeq
    Hb = 0.085 + 0.035 * s
    x = (W - inset) * sp(math.sin(phi), EX)
    c = math.cos(phi)
    z = zeq + ((H - inset) if c >= 0 else (Hb - inset * 0.5)) * sp(c, EX)
    return V((x, y, z))


def pr_normal(s, t):
    e = 1e-3
    a = pr_surf(min(s + e, 1.0), t) - pr_surf(max(s - e, 0.0), t)
    b = pr_surf(s, min(t + e, 1.0)) - pr_surf(s, max(t - e, -1.0))
    n = a.cross(b).normalized()
    out = pr_surf(s, t) - pr_surf(s, t, PR_T)
    return n if n.dot(out) > 0 else -n


PR_GS, PR_WS = 0.17, 0.032
PR_GT, PR_WT = 0.80, 0.032
PR_RW = 0.034
EMB_S = 0.60


def pr_ridge(s):
    """centre bead height factor (0..1); interrupted under the emblem"""
    a = smoothstep(PR_GS + PR_WS, 0.3, s)
    b = 1.0 - smoothstep(EMB_S - 0.24, EMB_S - 0.16, s) + smoothstep(EMB_S + 0.16, EMB_S + 0.24, s)
    return a * min(1.0, b)


def pr_depth(s, t):
    if in_groove(abs(t), PR_GT, PR_WT) and s > 0.06:
        return 0.0045 * smoothstep(0.06, 0.2, s)
    if in_groove(s, PR_GS, PR_WS) and abs(t) < PR_GT:
        return 0.0045
    if in_groove(t, 0.0, PR_RW) and s > PR_GS + PR_WS:
        return -0.005 * pr_ridge(s)
    return 0.0


def pr_mat(u0, u1, v0, v1):
    if in_groove(abs(v0), PR_GT, PR_WT) and in_groove(abs(v1), PR_GT, PR_WT) and u0 > 0.1 and v0 * v1 > 0:
        return BD
    if in_groove(u0, PR_GS, PR_WS) and in_groove(u1, PR_GS, PR_WS) and abs(v0) < PR_GT and abs(v1) < PR_GT:
        return BD
    return None


def build_pronotum(bb):
    hard = bb.piece(smooth=HARD)
    rnd = bb.piece(smooth=ROUND)
    us = merge_samples([s_dist(i / 12) for i in range(13)], groove_rows(PR_GS, PR_WS), PR_WS * 0.95)
    extra = groove_rows(-PR_GT, PR_WT) + groove_rows(PR_GT, PR_WT) + groove_rows(0.0, PR_RW)
    vs = merge_samples([-1 + 2 * i / 16 for i in range(17)], extra, PR_WT * 0.95)
    res = thick_patch(hard, lambda u, v: pr_surf(u, v), lambda u, v: pr_surf(u, v, PR_T), us, vs, BR,
                      mat_in=IR, mat_edge=BD, us_in=[i / 6 for i in range(7)],
                      vs_in=[-1 + 2 * i / 10 for i in range(11)], depth=pr_depth, outer_mat=pr_mat)
    bvh = res["bvh"]

    # rolled rim all around (front notch, sides, rear lip over the elytra)
    def mid(u, v):
        return (pr_surf(u, v) + pr_surf(u, v, PR_T)) * 0.5
    loop = [mid(0.0, -1 + 2 * i / 14) for i in range(14)] + [mid(i / 8, 1.0) for i in range(8)] \
        + [mid(1.0, 1 - 2 * i / 14) for i in range(14)] + [mid(1 - i / 8, -1.0) for i in range(8)]
    for _ in range(2):
        loop = [(loop[i - 1] + loop[i] * 2 + loop[(i + 1) % len(loop)]) * 0.25 for i in range(len(loop))]
    sweep(rnd, BD, loop, 0.0115, seg=6, closed=True, up=(0, 0, 1))
    # central clockwork emblem
    c = pr_surf(EMB_S, 0.0)
    nrm = pr_normal(EMB_S, 0.0)
    medallion(hard, rnd, bvh, c, nrm, V((1, 0, 0)), 0.086, 12, 6, gem=0.012)
    # rivets in the side bands + front band, hex bolts flanking the emblem
    for sgn in (1, -1):
        for s in (0.3, 0.52, 0.74):
            dome(rnd, BD, pr_surf(s, sgn * 0.9), pr_normal(s, sgn * 0.9), 0.0085)
        for t in (0.25, 0.52):
            dome(rnd, BD, pr_surf(0.085, sgn * t), pr_normal(0.085, sgn * t), 0.008)
        bolt(rnd, BD, pr_surf(EMB_S, sgn * 0.34), pr_normal(EMB_S, sgn * 0.34), 0.011, 0.007, seg=6)


HIPS = {}   # (leg, side) -> pivot


def hip_pivot(y, z, side):
    return V((side * (hull_x(y, z) + 0.006), y, z))


def build_bay(bb):
    """Machinery under the elytra: aether core, gears, folded wings."""
    hard = bb.piece(smooth=HARD)
    rnd = bb.piece(smooth=ROUND)
    # --- aether core: glow capsule in a brass cage, along Y on the midline ---
    y0, y1, zc, rc = 0.03, 0.33, 0.548, 0.032
    Mc = mtx((0, y0, zc), (0, 1, 0), (1, 0, 0))
    L = y1 - y0
    lathe_m(rnd, GL, [(0.0, 0.006), (rc, 0.02), (rc, L / 2), (rc, L - 0.02), (0.0, L - 0.006)], Mc, seg=12)
    for z0, flip in ((0.0, 1), (L, -1)):          # end caps
        prof = [(0.0, -0.012), (0.03, -0.012), (0.042, -0.004), (0.042, 0.016), (0.034, 0.024), (0.0, 0.024)]
        prof = [(r, z0 + flip * z) for (r, z) in prof]
        if flip < 0:
            prof = list(reversed(prof))
        lathe_m(rnd, BR, prof, Mc, seg=10)
    for f in (0.36, 0.64):                         # cage rings
        torus_m(rnd, BD, Mc @ Matrix.Translation((0, 0, L * f)), rc + 0.004, 0.0045, seg=12, seg2=4)
    for k in range(4):                             # cage bars
        a = 2 * math.pi * k / 4 + 0.785
        off = V((math.cos(a), 0, math.sin(a))) * (rc + 0.005)
        sweep(rnd, BR, [V((0, y0 + 0.02, zc)) + off, V((0, y1 - 0.02, zc)) + off], 0.0035, seg=5, cap=False)
    for y in (y0 + 0.04, y1 - 0.04):               # cradle post
        zt = hull_ztop(0.0, y)
        sweep(rnd, BD, [V((0, y, zt - 0.01)), V((0, y, zc - 0.02))], 0.008, seg=6, cap=False)
    # --- gears either side of the core (axis Z) ---
    for sgn in (1, -1):
        for (x, y, r, teeth, mat, holes) in ((0.083, 0.115, 0.05, 10, CU, True), (0.09, 0.208, 0.039, 8, BR, False)):
            x *= sgn
            z = hull_ztop(x + 0.03 * sgn, y) + 0.002
            M = Matrix.Translation((x, y, z)) @ Matrix.Rotation(sgn * 0.2, 4, "Z")
            if holes:
                gear_ring(hard, mat, M, r, r - 0.008, teeth, 0.009, r_hole=r * 0.7, spokes=4, hub=r * 0.28,
                          hub_h=0.013, spoke_w=r * 0.2, mat_hub=BD, bottom=False, hub_seg=8)
            else:
                gear_ring(hard, mat, M, r, r - 0.008, teeth, 0.009, hub=r * 0.3, hub_h=0.013, mat_hub=BD,
                          bottom=False, hub_seg=8)
    # --- folded wings on the flanks ---
    for sgn in (1, -1):
        build_wing(hard, rnd, sgn)


def build_wing(hard, rnd, sgn):
    """Folded hind wing lying over the gears (translucent membrane, brass ribs)."""
    bm = hard.bm
    nu, nv = 7, 4
    rows = []
    for i in range(nu + 1):
        f = i / nu
        y = -0.025 + 0.47 * f
        taper = math.sqrt(max(0.0, 1 - ((f - 0.3) / 0.7) ** 2)) if f > 0.3 else 1.0
        x0 = 0.098 + 0.02 * f
        x1 = x0 + 0.105 * taper + 0.002
        row = []
        for j in range(nv + 1):
            g = j / nv
            x = x0 + (x1 - x0) * g
            pleat = 0.0035 * (j % 2) * min(1.0, taper * 3)
            z = 0.536 - 0.22 * (x - 0.1) - 0.02 * f * f + pleat
            row.append(V((sgn * x, y, z)))
        rows.append(row)
    R = grid_rows(bm, rows)
    set_mat(hard, grid_faces(bm, R), WG)
    for j, r, mt in ((0, 0.0042, BR), (2, 0.003, BD), (nv, 0.0048, BR)):
        pts = [rows[i][j] + V((0, 0, 0.0025)) for i in range(nu + 1)]
        if j == nv:
            pts = pts[:-1] + [rows[nu][0] + V((0, 0, 0.0025))]
        sweep(rnd, mt, pts, [r] * nu + [0.0015], seg=5)
    ball(rnd, BR, rows[0][0].lerp(rows[0][nv], 0.5) + V((0, -0.004, 0.0)), 0.013, seg=8, rings=5)


def build_body(parent):
    bb = BoneBuilder("body", BODY_P)
    hull = bb.piece(smooth=50)
    build_hull(hull)
    build_pronotum(bb)
    build_bay(bb)
    rnd = bb.piece(smooth=ROUND)
    hard = bb.piece(smooth=HARD)
    # leg socket rings on the hull
    for (lg, y, z) in (("F", -0.24, 0.27), ("M", -0.05, 0.262), ("B", 0.12, 0.262)):
        for side, sname in ((1, "L"), (-1, "R")):
            h = hip_pivot(y, z, side)
            HIPS[(lg, sname)] = h
            n = (h - V((0, y, z + 0.05))).normalized()
            M = mtx(h - n * 0.012, n)
            torus_m(rnd, BD, M, 0.043, 0.0095, seg=10, seg2=4, phase=math.pi / 4)
    # thorax ventral plate (gunmetal) between the legs
    pts = [V((0, y, hull_sec(y)[1] - 0.004)) for y in (-0.36, -0.28, -0.16, -0.04, 0.04)]
    sweep(hard, GM, pts, [0.05, 0.085, 0.1, 0.09, 0.0], seg=8, up=(1, 0, 0), fx=1.0, fy=0.25)
    # neck collar ring (where the head ball sits)
    Mn = mtx(HEAD_P + V((0, 0.02, 0.0)), (0, -1, 0), (1, 0, 0))
    torus_m(rnd, BD, Mn, 0.082, 0.012, seg=16, seg2=5)
    return bb.build(parent, (0, 0, 0))


# =============================================================================================
# Head + horn + antennae
# =============================================================================================
HC = V((0, -0.47, 0.418))
HR = V((0.118, 0.1, 0.078))


def head_surf(s, t, grow=0.0):
    """Superellipsoid head capsule. s: 0 = front pole (-Y) .. 1 = back pole, t: angle around Y."""
    th = s * math.pi
    ph = t * 2 * math.pi
    e1, e2 = 2 / 2.4, 2 / 2.6
    cy, sy = math.cos(th), math.sin(th)
    x = (HR.x + grow) * sp(sy, e1) * sp(math.cos(ph), e2)
    z = (HR.z + grow) * sp(sy, e1) * sp(math.sin(ph), e2)
    y = -(HR.y + grow) * sp(cy, e1)
    return HC + V((x, y, z))


def ANT_BASE(sx):
    return V((sx * 0.06, -0.552, 0.432))


def build_head(parent):
    bb = BoneBuilder("head", HEAD_P)
    caps = bb.piece(smooth=60)
    hard = bb.piece(smooth=HARD)
    rnd = bb.piece(smooth=ROUND)
    # neck ball (fills the socket under the pronotum for any head turn)
    ball(caps, BD, HEAD_P, 0.072, seg=12, rings=7)
    # capsule
    rows = [[head_surf(i / 10, j / 14) for j in range(14)] for i in range(11)]
    R = grid_rows(caps.bm, rows)
    set_mat(caps, grid_faces(caps.bm, R, close_v=True), BD)

    # brass face plate over the top-front (thick patch on the capsule)
    def plate(u, v, g):
        return head_surf(0.08 + 0.52 * u, 0.25 + v * 0.19, g)
    thick_patch(hard, lambda u, v: plate(u, v, 0.009), lambda u, v: plate(u, v, -0.004),
                [i / 7 for i in range(8)], [-1 + 2 * i / 10 for i in range(11)], BR, mat_in=GM, mat_edge=BD,
                us_in=[0, 0.5, 1], vs_in=[-1, -0.5, 0, 0.5, 1])
    loop = [plate(0, -1 + 2 * i / 9, 0.0035) for i in range(9)] + [plate(i / 5, 1, 0.0035) for i in range(5)] \
        + [plate(1, 1 - 2 * i / 9, 0.0035) for i in range(9)] + [plate(1 - i / 5, -1, 0.0035) for i in range(5)]
    for _ in range(2):
        loop = [(loop[i - 1] + loop[i] * 2 + loop[(i + 1) % len(loop)]) * 0.25 for i in range(len(loop))]
    sweep(rnd, BD, loop, 0.0065, seg=5, closed=True, up=(0, 0, 1))
    # neck band where the capsule meets the neck ball
    Mb = mtx(V((0, -0.405, 0.418)), (0, -1, 0), (1, 0, 0), scale=(1.0, 0.72, 1.0))
    torus_m(rnd, BD, Mb, 0.104, 0.009, seg=16, seg2=4, phase=math.pi / 4)
    # cheek plates under the eyes
    for t0 in (-0.085, 0.585):
        thick_patch(hard, lambda u, v, t0=t0: head_surf(0.30 + 0.28 * u, t0 + 0.06 * v, 0.006),
                    lambda u, v, t0=t0: head_surf(0.30 + 0.28 * u, t0 + 0.06 * v, -0.003),
                    [0, 0.33, 0.66, 1.0], [-1, 0, 1], BD, mat_in=IR, mat_edge=BD)
    # horn socket collar on the plate
    hdir = V((0, -0.62, 0.78)).normalized()
    Mh = mtx(HORN_P - hdir * 0.012, hdir, (1, 0, 0))
    lathe_m(rnd, BD, [(0.07, -0.01), (0.072, 0.006), (0.065, 0.016), (0.057, 0.018)], Mh, seg=16,
            cap=(False, False))
    # lamp eyes: glow dome + brass bezel + iron cage bars
    for sx in (1, -1):
        c = V((sx * 0.104, -0.505, 0.432))
        d = V((sx * 0.80, -0.52, 0.30)).normalized()
        Me = mtx(c, d, (0, 0, 1))
        lathe_m(caps, GL, [(0.034, -0.012), (0.034, 0.004), (0.026, 0.021), (0.0, 0.031)], Me, seg=12,
                cap=(False, False))
        torus_m(rnd, BR, Me @ Matrix.Translation((0, 0, 0.004)), 0.037, 0.0085, seg=14, seg2=5)
        for ang in (0.0, math.pi / 2):
            arc = []
            for k in range(6):
                a = -math.pi / 2 + math.pi * k / 5
                rr = 0.035
                arc.append(Me @ V((rr * math.sin(a) * math.cos(ang), rr * math.sin(a) * math.sin(ang),
                                   0.004 + 0.029 * math.cos(a))))
            sweep(rnd, GM, arc, 0.0028, seg=4, cap=False)
        # mandible: brass base + steel blade, curving inward, with teeth
        pts = [V((sx * 0.048, -0.545, 0.372)), V((sx * 0.078, -0.592, 0.364)), V((sx * 0.074, -0.637, 0.357)),
               V((sx * 0.046, -0.672, 0.356)), V((sx * 0.014, -0.688, 0.36))]
        pts = resample(catmull(pts, 3), 8)
        n = len(pts)
        rad = [0.022 * (1 - i / (n - 1)) ** 0.7 for i in range(n)]
        rad[-1] = 0.0
        mats = [BD if i < 2 else ST for i in range(n - 1)]
        sweep(rnd, ST, pts, rad, seg=8, up=(0, 0, 1), fx=0.5, fy=1.0, mats=mats)
        for f, L in ((0.45, 0.018), (0.7, 0.013)):
            q = pts[int(f * (n - 1))]
            Mt = mtx(q, V((-sx, -0.3, 0)).normalized(), (0, 0, 1))
            lathe_m(rnd, ST, [(0.0065, 0.0), (0.0, L)], Mt, seg=5, cap=(False, False))
    # clypeus lip between the mandibles
    sweep(hard, BD, [V((-0.05, -0.563, 0.385)), V((0, -0.576, 0.39)), V((0.05, -0.563, 0.385))], 0.012,
          seg=6, up=(0, 0, 1), fx=0.6)
    return bb.build(parent, BODY_P)


def build_antenna(sx, name, parent):
    base = ANT_BASE(sx)
    bb = BoneBuilder(name, base)
    rnd = bb.piece(smooth=ROUND)
    ctrl = [base, base + V((sx * 0.03, -0.045, 0.02)), base + V((sx * 0.065, -0.075, 0.045)),
            base + V((sx * 0.085, -0.088, 0.065))]
    pts = catmull(ctrl, 2)
    sweep(rnd, IR, pts, [0.0065] * (len(pts) - 1) + [0.0045], seg=5)
    for q, r in ((ctrl[1], 0.0085), (ctrl[2], 0.0075)):
        ball(rnd, BD, q, r, seg=6, rings=4)
    tip = ctrl[-1]
    d = (ctrl[-1] - ctrl[-2]).normalized()
    side = d.cross(V((0, 0, 1))).normalized()
    for a in (-0.45, 0.0, 0.45):
        off = d * 0.012 + side * (math.sin(a) * 0.010)
        Ml = mtx(tip + off, (V((0, 0, 1)) * math.cos(a) + side * math.sin(a)).normalized(), d,
                 scale=(1.0, 0.75, 0.28))
        for v in ball(rnd, BR, V((0, 0, 0)), 0.02, seg=6, rings=4):
            v.co = Ml @ v.co
    return bb.build(parent, HEAD_P)


def build_horn(parent):
    bb = BoneBuilder("horn", HORN_P)
    rnd = bb.piece(smooth=ROUND)
    ball(rnd, BD, HORN_P, 0.056, seg=12, rings=6)
    ctrl = [V((0, -0.532, 0.47)), V((0, -0.578, 0.50)), V((0, -0.622, 0.55)), V((0, -0.655, 0.612)),
            V((0, -0.671, 0.672)), V((0, -0.668, 0.722)), V((0, -0.652, 0.758))]
    pts = resample(catmull(ctrl, 6), 20)
    n = len(pts)
    rs = [0.058 * (1 - i / (n - 1)) ** 0.8 + 0.0015 * (1 - i / (n - 1)) for i in range(n)]
    rs[-1] = 0.0
    tip_from = int(0.8 * (n - 1))
    mats = [HORN_MAT if i < tip_from else ST for i in range(n - 1)]
    sweep(rnd, HORN_MAT, pts, rs, seg=12, up=(1, 0, 0), fx=0.84, fy=1.0, mats=mats)
    # brass bands
    for f, rr in ((0.1, 0.0085), (0.37, 0.0075), (0.6, 0.0065)):
        i = int(round(f * (n - 1)))
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        M = mtx(pts[i], t, (1, 0, 0), scale=(0.86, 1.0, 1.0))
        torus_m(rnd, BD, M, rs[i] + 0.002, rr, seg=12, seg2=4, phase=math.pi / 4)
    # dorsal tooth (back side of the horn)
    i = int(0.5 * (n - 1))
    t = (pts[i + 1] - pts[i - 1]).normalized()
    back = V((0, 1, 0)) - t * t.y
    back.normalize()
    q = pts[i] + back * rs[i] * 0.8
    d = (back * 0.75 + t * 0.66).normalized()
    Mt = mtx(q, d, (1, 0, 0), scale=(0.75, 1.0, 1.0))
    lathe_m(rnd, HORN_MAT, [(0.017, -0.01), (0.015, 0.008), (0.009, 0.028), (0.0, 0.045)], Mt, seg=8,
            cap=(False, False))
    return bb.build(parent, HEAD_P)


# =============================================================================================
# Legs
# =============================================================================================
LEGS = {   # knee, ankle, foot (left side; right mirrored)
    "F": (V((0.39, -0.33, 0.35)), V((0.50, -0.47, 0.068)), V((0.53, -0.535, 0.0))),
    "M": (V((0.44, -0.05, 0.345)), V((0.585, -0.04, 0.068)), V((0.632, -0.035, 0.0))),
    "B": (V((0.41, 0.215, 0.345)), V((0.53, 0.395, 0.068)), V((0.565, 0.455, 0.0))),
}


KEEL = [(1.0, 0.0), (0.62, 0.42), (0.05, 0.56), (-0.55, 0.48), (-0.95, 0.0), (-0.55, -0.48), (0.05, -0.56),
        (0.62, -0.42)]                                  # femur armour section (N = up, B = side)
HEX = [(math.cos(math.pi * k / 3), math.sin(math.pi * k / 3)) for k in range(6)]
PLATE = [(1.0, 0.0), (0.55, 0.92), (-0.55, 0.92), (-1.0, 0.0), (-0.55, -0.92), (0.55, -0.92)]


def build_leg(lg, side, sname, parent):
    H = HIPS[(lg, sname)]
    K0, A0, F0 = LEGS[lg]
    K, A, F = mirror(K0, side), mirror(A0, side), mirror(F0, side)
    # ---------------- femur: keeled brass armour, hydraulic piston underneath ----------------
    bb = BoneBuilder(f"leg_{lg}{sname}", H)
    rnd = bb.piece(smooth=ROUND)
    arm = bb.piece(smooth=42)
    ball(rnd, BD, H, 0.04, seg=6, rings=4)
    d = (K - H).normalized()
    pts = catmull([H + d * 0.022, H.lerp(K, 0.32) + V((0, 0, 0.014)), H.lerp(K, 0.66) + V((0, 0, 0.012)),
                   K - d * 0.034], 2)
    n = len(pts)
    rr = [0.025, 0.031, 0.035, 0.035, 0.033, 0.03, 0.027][:n]
    sweep(arm, BR, pts, rr, up=(0, 0, 1), fx=1.0, fy=0.85, shape=KEEL)
    i = int(0.78 * (n - 1))
    t = (pts[i + 1] - pts[i - 1]).normalized()
    torus_m(rnd, BD, mtx(pts[i], t, (0, 0, 1), scale=(1.0, 0.55, 1.0)), rr[i] + 0.002, 0.0055, seg=10, seg2=4,
            phase=math.pi / 4)
    # piston: brass_dark cylinder + steel rod along the underside
    below = V((0, 0, -1)) - d * (-d.z)
    below.normalize()
    p0 = H.lerp(K, 0.22) + below * 0.036
    p1 = H.lerp(K, 0.56) + below * 0.034
    p2 = H.lerp(K, 0.86) + below * 0.03
    sweep(rnd, BD, [p0, p1], 0.0115, seg=8)
    sweep(rnd, ST, [p1, p2], 0.0055, seg=6)
    for q, off in ((p0, 0.03), (p2, 0.026)):
        sweep(rnd, IR, [q, q - below * off], 0.0065, seg=5, cap=False)
    # knee cup (opens toward the knee ball)
    lathe_m(rnd, IR, [(0.0, -0.024), (0.026, -0.02), (0.038, -0.01), (0.043, 0.004), (0.039, 0.017)],
            mtx(K - d * 0.02, d), seg=10, cap=(False, False))
    femur = bb.build(parent, BODY_P)
    # ---------------- tibia (_2): faceted gunmetal shank, brass greave, steel spines ----------------
    bb = BoneBuilder(f"leg_{lg}{sname}_2", K)
    rnd = bb.piece(smooth=ROUND)
    hard = bb.piece(smooth=HARD)
    ball(rnd, BR, K, 0.034, seg=8, rings=6)
    dt = (A - K).normalized()
    outward = V((side, 0, 0)) - dt * dt.x * side
    outward.normalize()
    pts = catmull([K + dt * 0.02, K.lerp(A, 0.45) + outward * 0.006, A], 3)
    n = len(pts)
    wide = 1.18 if lg == "F" else 1.0
    rr = [0.022, 0.023, 0.025, 0.027, 0.029 * wide, 0.03 * wide, 0.028 * wide][:n]
    rr[-1] = 0.019
    sweep(hard, GM, pts, rr, up=outward, fx=0.72, fy=1.0, shape=HEX)
    # greave plate on the outer face
    g = catmull([K.lerp(A, f) + outward * 0.019 for f in (0.06, 0.32, 0.64)], 3)
    m = len(g)
    gr = [0.03 * math.sin(math.pi * (0.12 + 0.88 * i / (m - 1))) + 0.006 for i in range(m)]
    gr[0] = gr[-1] = 0.0
    sweep(hard, BR, g, gr, up=outward, fx=0.3, fy=1.0, shape=PLATE)
    dome(rnd, BD, K.lerp(A, 0.3) + outward * 0.027, outward, 0.007)
    # spines (mid/back) or digging teeth (front) on the outer edge
    back = V((0, 1, 0))
    for f, L in ((0.55, 0.034), (0.72, 0.03), (0.88, 0.027)):
        q = K.lerp(A, f)
        if lg == "F":
            dd = (outward * 0.9 + V((0, -0.25, -0.35))).normalized()
            Ms = mtx(q + outward * 0.014, dd, dt, scale=(1.0, 0.35, 1.0))
            lathe_m(rnd, ST, [(0.016, -0.004), (0.012, 0.01), (0.0, L + 0.008)], Ms, seg=6, cap=(False, False))
        else:
            dd = (outward * 0.65 + back * 0.55 + V((0, 0, -0.4))).normalized()
            Ms = mtx(q + outward * 0.008, dd, dt)
            lathe_m(rnd, ST, [(0.0075, -0.004), (0.006, 0.006), (0.0, L)], Ms, seg=5, cap=(False, False))
    # tarsus beads + claws
    fd = F - A
    hor = V((fd.x, fd.y, 0)).normalized()
    beads = [A + hor * 0.022 + V((0, 0, -0.014)), A + hor * 0.048 + V((0, 0, -0.03))]
    sweep(rnd, IR, [A + dt * -0.01] + beads, 0.0075, seg=5, cap=False)
    ball(rnd, BD, beads[0], 0.0145, seg=8, rings=5)
    ball(rnd, IR, beads[1], 0.012, seg=8, rings=4)
    tipb = beads[-1]
    lat = V((-hor.y, hor.x, 0))
    for sg in (1, -1):
        c = [tipb, tipb + hor * 0.017 + lat * sg * 0.009 + V((0, 0, 0.002)),
             tipb + hor * 0.032 + lat * sg * 0.017 + V((0, 0, -0.012)),
             tipb + hor * 0.038 + lat * sg * 0.021]
        c[-1] = V((c[-1].x, c[-1].y, 0.0))
        c = resample(catmull(c, 2), 5)
        sweep(rnd, ST, c, [0.0065, 0.0058, 0.0045, 0.003, 0.0], seg=5, cap=False)
    bb.build(femur, H)
    return femur


# =============================================================================================
# Assemble
# =============================================================================================
body = build_body(root)
build_shell(1, "shell_L", body)
build_shell(-1, "shell_R", body)
head = build_head(body)
build_horn(head)
build_antenna(1, "antenna_L", head)
build_antenna(-1, "antenna_R", head)
for lg in "FMB":
    for side, sname in ((1, "L"), (-1, "R")):
        build_leg(lg, side, sname, body)

print(f"[tris] pre-rig total {hp.scene_tris()}")
for nm, t in sorted(((o.name, hp.obj_tris(o)) for o in bpy.context.scene.objects if o.type == "MESH"),
                    key=lambda r: -r[1]):
    print(f"[tris] {nm:14s} {t}")

arm = rig_from_parts(root, rigid=set(), smooth={}, skin_name="beetle_skin")
skin = bpy.data.objects["beetle_skin"]


def tint(p, n):
    # a touch of grime toward the ground, slightly brighter tops
    k = 0.92 + 0.08 * max(0.0, n.z)
    if p.z < 0.25:
        k *= 0.82 + 0.18 * (p.z / 0.25)
    return (k, k, k)


bake_ao_open(skin, samples=48, distance=0.22, strength=0.85, floor=0.3, ground=0.0, tint=tint, lo=0.5, hi=0.3)
hp.export_glb_hp("beetle")

# ---- previews ----------------------------------------------------------------------------
hp.render_views("beetle")
hp.render_hp("beetle_game", azimuth=35, elevation=25, dist_k=7.0, size=560)
hp.render_hp("beetle_head", target=((0, -0.56, 0.52), 0.30), azimuth=32, elevation=10)
hp.render_hp("beetle_top", azimuth=20, elevation=70)

DEG = 180 / math.pi
STUN = {   # rig.ts stunned: shell_L rot (0.25, -0.3, 0.42) rad (three.js YXZ) -> Blender world axes
    "shell_L": [("Y", -0.42 * DEG), ("X", 0.25 * DEG), ("Z", -0.3 * DEG)],
    "shell_R": [("Y", 0.42 * DEG), ("X", 0.25 * DEG), ("Z", 0.3 * DEG)],
}
WINDUP = {  # attack windup: body [-12,0,0], head [-18,0,0], shell_L [12,-15,22] deg
    "body": [("X", -12)], "head": [("X", -18)],
    "shell_L": [("Y", -22), ("X", 12), ("Z", -15)],
    "shell_R": [("Y", 22), ("X", 12), ("Z", 15)],
}
WALK = {   # gait peak: leg rot (g*0.5, g*0.3) rad, knees cos * 0.3; head turned
    "leg_FL": [("X", 0.5 * DEG), ("Z", 0.3 * DEG)], "leg_BL": [("X", 0.5 * DEG), ("Z", 0.3 * DEG)],
    "leg_MR": [("X", 0.5 * DEG), ("Z", 0.3 * DEG)],
    "leg_FR": [("X", -0.5 * DEG), ("Z", -0.3 * DEG)], "leg_BR": [("X", -0.5 * DEG), ("Z", -0.3 * DEG)],
    "leg_ML": [("X", -0.5 * DEG), ("Z", -0.3 * DEG)],
    "leg_FL_2": [("X", 0.3 * DEG)], "leg_BL_2": [("X", 0.3 * DEG)], "leg_MR_2": [("X", 0.3 * DEG)],
    "leg_FR_2": [("X", -0.3 * DEG)], "leg_BR_2": [("X", -0.3 * DEG)], "leg_ML_2": [("X", -0.3 * DEG)],
    "head": [("Z", 0.15 * DEG)], "horn": [("X", -20)],
}


def pose_render(name, pose, **kw):
    pose_world(arm, pose)
    hp.render_hp(name, **kw)
    reset_pose(arm)


pose_render("beetle_pose_open", STUN, azimuth=160, elevation=40)
pose_render("beetle_pose_open2", STUN, azimuth=215, elevation=55)
pose_render("beetle_pose_bay", STUN, target=((0, 0.12, 0.55), 0.42), azimuth=180, elevation=50)
if not QUICK:
    pose_render("beetle_pose", dict(WALK, **STUN), azimuth=35, elevation=18)
    pose_render("beetle_pose_windup", WINDUP, azimuth=60, elevation=15)
    pose_render("beetle_pose_back", WALK, azimuth=150, elevation=30)
if "check" in ARGS:
    STRIKE = {"body": [("X", 18)], "head": [("X", 22)], "horn": [("X", -25)]}
    pose_render("beetle_chk_strike", STRIKE, target=((0, -0.5, 0.5), 0.4), azimuth=70, elevation=10)
    pose_render("beetle_chk_windup", WINDUP, target=((0, -0.45, 0.55), 0.4), azimuth=60, elevation=10)
    hp.render_hp("beetle_chk_under", azimuth=30, elevation=-25, ground=False)
    pose_render("beetle_chk_hinge", STUN, target=((0.1, -0.08, 0.6), 0.22), azimuth=120, elevation=35)
    pose_render("beetle_chk_openlow", STUN, azimuth=110, elevation=4)
    pose_render("beetle_chk_walkfront", WALK, azimuth=-20, elevation=12)
