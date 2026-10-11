"""Cog Rat — weak, timid clockwork rat enemy (~0.45 m body height, ~0.8 m long). Hi-poly pass
(2026-10-11, ASSET_SPEC.md "Hi-poly pass"). Exports public/models/cograt.glb.

Skeleton (RIG_SPEC.md), armature object 'root':
  body (root bone) > head > {ear_L, ear_R}
                   > tail_1 > tail_2 > tail_3 > tail_4
                   > leg_FL, leg_FR, leg_BL, leg_BR
  rigid attachment: key (bone-parented to body, spins around its local Z)
Faces -Y (head toward -Y), L = +X. Everything is modelled in world space (hp_cograt_helpers) and
moved onto its joint pivot by build_world().

Design: pear-shaped copper barrel made of shingled plates with raised brass hoop bands (one grid
surface: plate steps, bands, belly seam lips and the rolled neck rim are real geometry), iron belly,
riveted bands, glass portholes on the flanks showing a gear + a red aether core, hip/shoulder hub
discs (centred on the leg pivots so the gait rotation never opens a gap), a big round head with a
short snout, huge brass ear dishes with gear membranes, big lens eyes in brass bezels with worried
brow plates + catch-lights, nose cap, buck teeth, whiskers; bead tail on an iron rod ending in a
gear; wind-up key with a gear collar and a red gem in the bow.

Usage: blender -b --factory-startup -P tools/blender/model_cograt.py [-- flags]
  flags: views face game pose   (default: all) ; "none" = export only
  previews (tools/blender/previews/): cograt, _front, _side, _back (EEVEE) · cograt_face (eye close-up) ·
  cograt_game (game distance), cograt_high (high 3/4, like the game camera) · cograt_pose, _pose_back
  (workbench deformation test) + cograt_pose_lunge / _rear / _curl (EEVEE, attack-clip / gait extremes)
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # noqa: E401,E702
import math

import bpy
from mathutils import Matrix, Vector

from common import get_mat, empty, reset_scene
from char_helpers import tube, tri_report
from rig_helpers import rig_from_parts, pose_world, reset_pose
from creature_rig_helpers import pose_views
import hp_helpers as hp
import hp_cograt_helpers as H
from hp_cograt_helpers import Profile, super_pt, frame, lathe_m, grid, rivet, capsule, gear, torus_m, \
    sweep, rounded_rect, build_world, SPart

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FLAGS = set(ARGS) if ARGS else {"views", "face", "game", "pose"}

reset_scene()

# ---- materials (11) ------------------------------------------------------------------------
get_mat("copper")
get_mat("copper_dark", hex="#7c4026", metallic=0.85, roughness=0.5)
get_mat("brass")
get_mat("brass_dark")
get_mat("iron")
get_mat("steel")
get_mat("ivory", hex="#efe2c2", metallic=0.0, roughness=0.35)
get_mat("black", hex="#141012", metallic=0.2, roughness=0.25)
get_mat("glass", alpha=0.35)
get_mat("glow_red")
get_mat("glow_white")

V = Vector
root = empty("root")

# ---- pivots (DESIGN space; everything above the feet is finally lowered by DZ) ---------------
DZ = 0.02                        # shorter legs: the whole upper body sits 2 cm lower than designed
BODY_PIV = V((0, 0.03, 0.255))   # -> final z 0.235 (body centre)
HEAD_PIV = V((0, -0.192, 0.262))   # centre of the body's neck opening (ball joint, see build_head)
EAR_PIV = {1: V((0.076, -0.207, 0.422)), -1: V((-0.076, -0.207, 0.422))}
TAIL_PIV = V((0, 0.293, 0.249))
LEG_PIV = {"FL": V((0.115, -0.092, 0.170)), "FR": V((-0.115, -0.092, 0.170)),
           "BL": V((0.155, 0.140, 0.180)), "BR": V((-0.155, 0.140, 0.180))}
KEY_PIV = V((0, 0.075, 0.422))


def F(v):
    """design space -> final world space"""
    return V(v) - V((0, 0, DZ))


def bw(p, parent, piv, ppiv=None):
    """Build a design-space part: lowered by DZ, origin at its (lowered) joint pivot."""
    import bmesh
    bmesh.ops.translate(p.bm, vec=V((0, 0, -DZ)), verts=p.bm.verts[:])
    return build_world(p, parent, F(piv), F(ppiv) if ppiv is not None else V((0, 0, 0)))


# =============================================================================================
# BODY — one grid surface
# =============================================================================================
BODY = Profile([
    # y,      hw,    ht,    hb,    zc,    n
    (-0.195, 0.094, 0.080, 0.090, 0.258, 2.10),
    (-0.170, 0.114, 0.097, 0.108, 0.256, 2.15),
    (-0.125, 0.136, 0.116, 0.128, 0.254, 2.20),
    (-0.055, 0.155, 0.137, 0.142, 0.255, 2.25),
    (0.025, 0.170, 0.154, 0.150, 0.259, 2.25),
    (0.105, 0.181, 0.166, 0.150, 0.263, 2.25),
    (0.165, 0.181, 0.162, 0.146, 0.262, 2.20),
    (0.215, 0.168, 0.146, 0.134, 0.258, 2.15),
    (0.252, 0.140, 0.117, 0.112, 0.253, 2.10),
    (0.276, 0.106, 0.086, 0.086, 0.250, 2.05),
    (0.291, 0.070, 0.057, 0.057, 0.249, 2.00),
    (0.300, 0.035, 0.029, 0.030, 0.249, 2.00),
])


def body_pt(y, th, off=0.0, scale=1.0, sec_y=None):
    hw, ht, hb, zc, n = BODY.at(y if sec_y is None else sec_y)
    u, v = super_pt(hw * scale + off, ht * scale + off, hb * scale + off, n, th)
    return V((u, y, zc + v))


def surf_normal(fn, y, th, eps=1e-3):
    p = fn(y, th)
    a = fn(y + eps, th) - p
    b = fn(y, th + eps) - p
    nrm = b.cross(a)
    c = fn(y, th, scale=0.0)
    if nrm.dot(p - c) < 0:
        nrm = -nrm
    return nrm.normalized()


BANDS = (-0.060, 0.222)          # brass hoops between chest / saddle / rump plates
BAND_RINGS = [(-0.0165, 0.0, "brass"), (-0.0135, 0.0078, "brass"), (-0.006, 0.0108, "brass"),
              (0.006, 0.0108, "brass"), (0.0135, 0.0078, "brass"), (0.0165, -0.0028, "copper")]
BODY_COLS = 22                   # angular step of the visible (upper) shell: 360/22
SEAM_TH = -2 * 2 * math.pi / BODY_COLS
BELLY_STEPS = 4                  # the iron underside is rarely seen -> coarser columns


def body_columns():
    """(theta, radial offset) in cyclic order: 16 columns over the copper upper shell from seam to seam
    (raised lip on both seam columns), then BELLY_STEPS-1 coarse columns across the iron belly."""
    step = 2 * math.pi / BODY_COLS
    upper = [(SEAM_TH + k * step, 0.0022 if k in (0, 15) else 0.0) for k in range(16)]
    a0, a1 = SEAM_TH + 15 * step, SEAM_TH + 2 * math.pi
    belly = [(a0 + (a1 - a0) * j / BELLY_STEPS, 0.0) for j in range(1, BELLY_STEPS)]
    return [((t + 2 * math.pi) % (2 * math.pi), o) for t, o in upper + belly]


def in_belly(t):
    d = math.degrees(t) % 360
    return (180 - math.degrees(SEAM_TH) - 0.5) <= d <= (math.degrees(SEAM_TH) % 360 + 0.5)


def build_body():
    p = SPart("body")
    cols = body_columns()
    S0 = -0.192
    # (y, scale, off, sec_y, mat_after)
    rings = [(-0.166, 0.70, 0.0, S0, "iron"),           # recessed throat (head's neck ball sits here)
             (-0.182, 0.80, 0.0, S0, "brass"),          # rolled neck rim
             (-0.200, 0.89, 0.0, S0, "brass"),
             (-0.205, 0.98, 0.0, S0, "brass"),
             (-0.199, 1.065, 0.0, S0, "brass"),
             (-0.186, 1.075, 0.0, S0, "brass"),
             (-0.178, 1.0, -0.002, -0.178, "copper")]   # chest plate tucked under the rim
    ys = [-0.158, -0.122, -0.088, -0.030, 0.004, 0.038, 0.072, 0.106, 0.140, 0.174,
          0.256, 0.276, 0.290, 0.2985]
    plain = []
    for y in ys:
        off = 0.0016 if any(0 < b - y < 0.05 for b in BANDS) else 0.0     # shingle: plate rises to the band
        plain.append((y, 1.0, off, None, "copper"))
    for b in BANDS:
        plain += [(b + dy, 1.0, o, None, m) for dy, o, m in BAND_RINGS]
    plain.sort(key=lambda r: r[0])
    rings += plain
    pts = []
    for (y, sc, off, sy, _m) in rings:
        pts.append([body_pt(y, t, off + co * (1.0 if sy is None else 0.0), sc, sy) for (t, co) in cols])
    nc = len(cols)
    def mid(a, b):
        return a + (((b - a) + 2 * math.pi) % (2 * math.pi)) / 2
    belly_cols = [in_belly(mid(cols[j][0], cols[(j + 1) % nc][0])) for j in range(nc)]

    def mat_fn(i, j):
        m = rings[i][4]
        return "iron" if (m == "copper" and belly_cols[j]) else m
    zc_in = BODY.at(S0)[3]
    # rear end stays open: the last ring (r ~0.037) is hidden inside the tail drive gear's disc (r 0.039),
    # which avoids a pole fan (long triangles -> pinched shading / AO streaks on the rump)
    grid(p, pts, mat_fn, start_pole=V((0, -0.152, zc_in + 0.01)))

    # rivets on the bands (upper half + flanks)
    for b in BANDS:
        for deg in (18, 50, 90, 130, 162):
            th = math.radians(deg)
            rivet(p, "brass_dark", body_pt(b, th, 0.0108), surf_normal(body_pt, b, th), r=0.0062, h=0.0045)

    # flank portholes: brass bezel, iron backplate, gear + red aether core behind glass
    for s in (1, -1):
        y0, th = 0.050, math.radians(17 if s > 0 else 163)
        c = body_pt(y0, th)
        nrm = (surf_normal(body_pt, y0, th) + V((0, 0, 0.05))).normalized()
        M = frame(c, nrm)
        lathe_m(p, [(0.041, -0.012, "brass"), (0.045, 0.002, "brass"), (0.0435, 0.010, "brass"),
                    (0.038, 0.0145, "brass"), (0.032, 0.012, "brass"), (0.0295, 0.0012, "iron"),
                    (0.0, 0.0012, "iron")], 16, M, close_top=False, close_bottom=False)
        gear(p, "brass_dark", M @ Matrix.Translation((0, 0, 0.0028)), r=0.0245, thick=0.003, teeth=6, depth=0.0055,
             bottom=False)
        lathe_m(p, [(0.0, 0.002, "glow_red"), (0.0068, 0.0045, "glow_red"), (0.0048, 0.0098, "glow_red"),
                    (0.0, 0.0112, "glow_red")], 8, M)
        lathe_m(p, [(0.0315, 0.0078, "glass"), (0.022, 0.0145, "glass"), (0.0, 0.0175, "glass")], 16, M,
                close_bottom=False)

    # saddle plate on the back (brass_dark, riveted) — breaks up the big copper area the game camera sees
    saddle(p)
    # key socket (brass collar with a dark bore)
    lathe_m(p, [(0.036, -0.03, "brass"), (0.039, -0.004, "brass"), (0.036, 0.004, "brass"),
                (0.029, 0.007, "brass"), (0.0, 0.004, "iron")], 16, frame(KEY_PIV, (0, 0, 1)), close_bottom=False)
    # tail drive gear around the socket (the "winding" of the tail) + tail socket on the rump
    # (the rump's section radius is 0.047 at y ~ 0.294 -> the gear's back face sits flush there)
    gear(p, "brass_dark", frame(V((0, 0.2985, TAIL_PIV.z)), (0, 1, 0)), r=0.047, thick=0.009, teeth=9,
         depth=0.008, bottom=False)
    lathe_m(p, [(0.031, -0.02, "brass"), (0.034, 0.004, "brass"), (0.030, 0.012, "brass"),
                (0.020, 0.015, "brass"), (0.0, 0.012, "iron")], 14, frame(TAIL_PIV + V((0, 0.007, 0)), (0, 1, 0.05)),
            close_bottom=False)
    return bw(p, root, BODY_PIV)


SADDLE = dict(y0=-0.016, y1=0.166, half_deg=36.0, ny=8, nt=6, top=0.0048, bottom=-0.003)


def saddle(p):
    """Raised plate conforming to the body surface: top grid + walls sunk into the shell."""
    sd = SADDLE
    yc, hy = (sd["y0"] + sd["y1"]) / 2, (sd["y1"] - sd["y0"]) / 2
    rows = []
    for i in range(sd["ny"] + 1):
        t = -0.96 + 1.92 * i / sd["ny"]
        y = yc + hy * t
        w = math.radians(sd["half_deg"]) * (1 - abs(t) ** 4) ** 0.25
        rows.append([(y, math.pi / 2 + w * (-1 + 2 * j / sd["nt"])) for j in range(sd["nt"] + 1)])
    bm = p.bm
    mi = p._mi("brass_dark")
    top = [[bm.verts.new(body_pt(y, t, sd["top"])) for (y, t) in r] for r in rows]
    for i in range(len(rows) - 1):
        for j in range(sd["nt"]):
            bm.faces.new((top[i][j], top[i][j + 1], top[i + 1][j + 1], top[i + 1][j])).material_index = mi
    # boundary loop (row 0 -> right column -> last row reversed -> left column reversed)
    ny, nt = sd["ny"], sd["nt"]
    loop = [(0, j) for j in range(nt + 1)] + [(i, nt) for i in range(1, ny + 1)] + \
           [(ny, j) for j in range(nt - 1, -1, -1)] + [(i, 0) for i in range(ny - 1, 0, -1)]
    lo = [bm.verts.new(body_pt(rows[i][j][0], rows[i][j][1], sd["bottom"])) for (i, j) in loop]
    for k in range(len(loop)):
        k2 = (k + 1) % len(loop)
        a, b = top[loop[k][0]][loop[k][1]], top[loop[k2][0]][loop[k2][1]]
        bm.faces.new((a, b, lo[k2], lo[k])).material_index = mi
    for (i, j) in ((0, 0), (0, nt), (ny, 0), (ny, nt)):
        ii = 1 if i == 0 else ny - 1
        jj = 1 if j == 0 else nt - 1
        y = (rows[i][j][0] * 0.35 + rows[ii][jj][0] * 0.65)
        t = (rows[i][j][1] * 0.35 + rows[ii][jj][1] * 0.65)
        rivet(p, "brass", body_pt(y, t, sd["top"]), surf_normal(body_pt, y, t), r=0.0058, h=0.004)


# =============================================================================================
# HEAD
# =============================================================================================
HEAD = Profile([
    (-0.140, 0.050, 0.048, 0.040, 0.314, 2.00),
    (-0.155, 0.082, 0.080, 0.062, 0.318, 2.00),
    (-0.180, 0.108, 0.104, 0.080, 0.322, 2.05),
    (-0.215, 0.128, 0.121, 0.091, 0.324, 2.10),
    (-0.255, 0.135, 0.124, 0.096, 0.323, 2.10),
    (-0.295, 0.126, 0.110, 0.093, 0.318, 2.10),
    (-0.335, 0.100, 0.085, 0.080, 0.308, 2.05),
    (-0.372, 0.076, 0.064, 0.066, 0.299, 2.00),
    (-0.410, 0.058, 0.049, 0.054, 0.291, 2.00),
    (-0.440, 0.045, 0.039, 0.043, 0.286, 2.00),
    (-0.457, 0.031, 0.028, 0.031, 0.284, 2.00),
])
HEAD_COLS = 24
MUZZLE_Y = -0.366


def head_pt(y, th, off=0.0, scale=1.0):
    hw, ht, hb, zc, n = HEAD.at(y)
    u, v = super_pt(hw * scale + off, ht * scale + off, hb * scale + off, n, th)
    return V((u, y, zc + v))


def build_head(body):
    p = SPart("head")
    cols = [2 * math.pi * k / HEAD_COLS for k in range(HEAD_COLS)]
    ring = [(y, 0.0, "copper") for y in (-0.152, -0.196, -0.224, -0.250, -0.276, -0.302, -0.326, -0.346)]
    ring += [(MUZZLE_Y + 0.010, 0.0, "brass"), (MUZZLE_Y + 0.0075, 0.0055, "brass"),
             (MUZZLE_Y - 0.0075, 0.0055, "brass"), (MUZZLE_Y - 0.010, -0.0015, "copper")]
    ring += [(y, 0.0, "copper") for y in (-0.388, -0.410, -0.430, -0.446, -0.457)]
    ring.sort(key=lambda r: -r[0])
    pts = [[head_pt(y, t, o) for t in cols] for (y, o, _m) in ring]
    grid(p, pts, lambda i, j: ring[i][2], start_pole=V((0, -0.134, 0.313)), end_pole=V((0, -0.463, 0.284)))

    # neck ball joint: a sphere centred exactly on the head pivot is rotation-invariant, so it keeps the
    # body's neck opening (inner rim radius ~0.084) plugged whatever the head does
    rb = 0.086
    with p.soft(65):
        lathe_m(p, [(rb * math.sin(math.pi * k / 6), -rb * math.cos(math.pi * k / 6), "iron") for k in range(7)], 10,
                frame(HEAD_PIV, (0, -1, 0)))

    # muzzle band rivets
    for deg in (32, 90, 148):
        th = math.radians(deg)
        rivet(p, "brass_dark", head_pt(MUZZLE_Y, th, 0.0055), surf_normal(head_pt, MUZZLE_Y, th), r=0.0048, h=0.0035)

    # nose cap: glossy black button + brass ring
    Mn = frame(V((0, -0.455, 0.285)), (0, -1, 0.12))
    lathe_m(p, [(0.026, -0.007, "brass"), (0.0322, -0.0015, "brass"), (0.0305, 0.0035, "brass"), (0.0262, 0.0045, "black"),
                (0.0262, 0.010, "black"), (0.020, 0.0195, "black"), (0.0, 0.0245, "black")], 14, Mn, close_bottom=False)

    # lower jaw (iron) + buck teeth
    jaw = Profile([(-0.305, 0.040, 0.020, 0.018, 0.250, 2.0), (-0.345, 0.043, 0.022, 0.020, 0.244, 2.0),
                   (-0.395, 0.036, 0.020, 0.018, 0.244, 2.0), (-0.425, 0.024, 0.016, 0.014, 0.248, 2.0)])
    jc = [2 * math.pi * k / 12 for k in range(12)]
    jpts = []
    for y in (-0.31, -0.345, -0.38, -0.414):
        hw, ht, hb, zc, n = jaw.at(y)
        row = []
        for t in jc:
            u, v = super_pt(hw, ht, hb, n, t)
            row.append(V((u, y, zc + v)))
        jpts.append(row)
    grid(p, jpts, lambda i, j: "iron", start_pole=V((0, -0.298, 0.252)), end_pole=V((0, -0.428, 0.249)))
    for s in (1, -1):
        sweep(p, "ivory", [V((s * 0.0096, -0.4505, 0.266)), V((s * 0.0096, -0.4495, 0.234))],
              rounded_rect(0.0158, 0.0092, 0.0042, n=1), up=(0, -1, 0))

    # eyes --------------------------------------------------------------------------------------
    for s in (1, -1):
        ye, th = -0.286, math.radians(30 if s > 0 else 150)
        c = head_pt(ye, th, -0.004)
        ns = surf_normal(head_pt, ye, th)
        axis = (ns + V((0, -0.62, 0.06))).normalized()
        M = frame(c, axis)
        # bezel (brass) with a steel glint ring on the inner lip
        lathe_m(p, [(0.048, -0.016, "brass"), (0.0515, 0.000, "brass"), (0.0505, 0.0085, "brass"),
                    (0.045, 0.0135, "brass"), (0.040, 0.0125, "steel"), (0.0372, 0.0085, "iron"),
                    (0.0352, 0.0, "iron")], 20, M, close_top=False, close_bottom=False)
        a, h = 0.0358, 0.0175
        R = (a * a + h * h) / (2 * h)

        def lens_z(r):
            return h - (R - math.sqrt(max(0.0, R * R - r * r)))
        lathe_m(p, [(a, 0.0, "glow_red"), (a * 0.72, lens_z(a * 0.72), "glow_red"),
                    (a * 0.38, lens_z(a * 0.38), "glow_red"), (0.0, h, "glow_red")], 20, M, close_bottom=False)
        pr = 0.018
        lathe_m(p, [(pr, lens_z(pr) + 0.0007, "black"), (pr * 0.55, lens_z(pr * 0.55) + 0.0009, "black"),
                    (0.0, h + 0.0009, "black")], 14, M, close_bottom=False)
        # catch-light toward the viewer's upper-left (world -X, +Z) projected onto the lens
        d = V((-0.55, 0.0, 0.85))
        d = (d - axis * d.dot(axis)).normalized()
        cl = c + d * 0.0165 + axis * (lens_z(0.0165) + 0.0012)
        with p.soft(70):
            lathe_m(p, [(0.0, -0.003, "glow_white"), (0.0058, -0.0005, "glow_white"), (0.0, 0.0022, "glow_white")], 8,
                    frame(cl, axis))
        # worried brow plate: arc above the bezel, inner end raised, reaching down onto the head
        up = V((0, 0, 1))
        up = (up - axis * up.dot(axis)).normalized()
        side = axis.cross(up).normalized()
        if side.x * s < 0:
            side = -side
        tilt = math.radians(16)
        upt = (up * math.cos(tilt) - side * math.sin(tilt)).normalized()
        sdt = axis.cross(upt).normalized()
        bpts = []
        for k in range(8):
            ang = math.radians(-60 + 120 * k / 7)
            bpts.append(c + axis * 0.012 + (upt * math.cos(ang) + sdt * math.sin(ang)) * 0.0555)
        prof = [(-0.006, -0.024), (0.0065, -0.020), (0.0085, 0.0), (0.005, 0.0055), (-0.004, 0.006), (-0.0075, 0.0)]
        sweep(p, "copper_dark", bpts, prof, up=tuple(axis))

    # whiskers: brass studs + steel wires
    for s in (1, -1):
        th = math.radians(4 if s > 0 else 176)
        base = head_pt(-0.404, th, 0.0)
        nb = surf_normal(head_pt, -0.404, th)
        with p.soft(60):
            lathe_m(p, [(0.0125, -0.006, "brass"), (0.0128, 0.002, "brass"), (0.0, 0.0048, "brass")], 8,
                    frame(base, nb))
        for (dz, dy) in ((0.020, -0.006), (0.0, 0.0), (-0.018, 0.010)):
            o = base + nb * 0.003 + V((0, 0, dz * 0.3))
            w = [o, o + V((s * 0.05, 0.004 + dy * 0.3, dz * 0.5)), o + V((s * 0.10, 0.016 + dy, dz * 0.9 - 0.004)),
                 o + V((s * 0.145, 0.034 + dy * 1.5, dz * 1.2 - 0.016))]
            with p.soft(130):
                tube(p, "steel", [tuple(q) for q in w], r=[0.0030, 0.0025, 0.0019, 0.0012], seg=3)
    return bw(p, body, HEAD_PIV, BODY_PIV)


# =============================================================================================
# EARS
# =============================================================================================
def build_ear(head, s):
    side = "L" if s > 0 else "R"
    piv = EAR_PIV[s]
    p = SPart("ear_" + side)
    c = piv + V((s * 0.050, 0.004, 0.060))
    axis = V((s * 0.50, -0.83, 0.22)).normalized()
    M = frame(c, axis)
    R = 0.080
    lathe_m(p, [(0.0, -0.016, "brass"), (0.048, -0.0135, "brass"), (R - 0.002, -0.004, "brass"),
                (R + 0.0012, 0.003, "brass"), (R - 0.003, 0.0095, "brass"), (R - 0.0105, 0.0085, "brass"),
                (R - 0.014, 0.003, "copper_dark"), (0.0, -0.001, "copper_dark")], 22, M, close_top=False)
    gear(p, "brass_dark", M @ Matrix.Translation((0, 0, 0.0016)), r=0.047, thick=0.0045, teeth=9, depth=0.0075,
         bottom=False)
    with p.soft(60):
        lathe_m(p, [(0.0, 0.0, "brass"), (0.013, 0.003, "brass"), (0.010, 0.0075, "brass"), (0.0, 0.009, "brass")],
                10, M)
        # stalk from the head socket to the dish
        bot = c + (M.to_3x3() @ V((0, -1, 0))) * (R * 0.70) - axis * 0.010
        capsule(p, "brass_dark", piv + V((0, 0, -0.01)), bot, 0.0135, 0.011, seg=8, rings=1)
        # boss on the convex back of the dish (seen when the rat turns away)
        lathe_m(p, [(0.0175, -0.0125, "brass_dark"), (0.0175, -0.0175, "brass_dark"), (0.011, -0.0215, "brass_dark"),
                    (0.0, -0.0225, "brass_dark")], 10, M, close_bottom=False)
    return bw(p, head, piv, HEAD_PIV)


# =============================================================================================
# LEGS
# =============================================================================================
def build_leg(body, name):
    piv = F(LEG_PIV[name])          # legs are modelled directly in final space (feet on z = 0)
    s = 1 if name.endswith("L") else -1
    back = name.startswith("B")
    p = SPart("leg_" + name)
    ax = V((s, 0, 0))
    # hub disc centred on the pivot (axis X): the gait rotation never opens a gap. It stands proud of the
    # flank so the whole round plate reads (the body would otherwise swallow its upper half).
    M = frame(piv + V((s * (0.010 if back else 0.004), 0, 0)), ax)
    if back:
        Rh = 0.068
        lathe_m(p, [(Rh - 0.007, -0.012, "copper"), (Rh, 0.0, "copper"), (Rh, 0.008, "copper"),
                    (Rh - 0.003, 0.018, "brass"), (Rh - 0.010, 0.022, "brass"), (0.034, 0.021, "copper"),
                    (0.024, 0.026, "brass"), (0.0, 0.029, "brass")], 18, M)
        for k in range(4):
            a = 2 * math.pi * k / 4 + 0.785
            rivet(p, "brass_dark", M @ V((0.046 * math.cos(a), 0.046 * math.sin(a), 0.0212)), ax, r=0.005,
                  h=0.0035, sink=0.002)
        ankle = V((piv.x - s * 0.002, piv.y + 0.050, 0.036))
        top = piv + V((s * 0.004, 0.0, -0.012))
        with p.soft(60):
            capsule(p, "iron", top, ankle, 0.021, 0.016, seg=8, rings=1)
            d = ankle - top
            lathe_m(p, [(0.0245, 0.0, "copper"), (0.0275, 0.008, "copper"), (0.026, 0.050, "copper"),
                        (0.022, 0.058, "brass")], 8, frame(top + d * 0.18, d), close_top=True)
        heel, toe_y, fw = ankle.y + 0.024, ankle.y - 0.090, 0.060
    else:
        Rh = 0.046
        lathe_m(p, [(Rh - 0.005, -0.010, "copper"), (Rh, 0.0, "copper"), (Rh, 0.006, "copper"),
                    (Rh - 0.002, 0.014, "brass"), (Rh - 0.008, 0.018, "brass"), (0.018, 0.0185, "copper"),
                    (0.0, 0.023, "brass")], 14, M)
        ankle = V((piv.x - s * 0.006, piv.y - 0.012, 0.032))
        top = piv + V((s * 0.004, 0.0, -0.008))
        with p.soft(60):
            capsule(p, "iron", top, ankle, 0.018, 0.0145, seg=8, rings=1)
            d = ankle - top
            lathe_m(p, [(0.0215, 0.0, "copper"), (0.0245, 0.007, "copper"), (0.023, 0.044, "copper"),
                        (0.019, 0.052, "brass")], 8, frame(top + d * 0.22, d), close_top=True)
        heel, toe_y, fw = ankle.y + 0.020, ankle.y - 0.050, 0.054
    foot_x = ankle.x
    # ankle cuff
    with p.soft(60):
        lathe_m(p, [(0.0, -0.016, "brass_dark"), (0.020, -0.010, "brass_dark"), (0.022, 0.006, "brass_dark"),
                    (0.0, 0.015, "brass_dark")], 8, frame(ankle + V((0, 0, 0.004)), (0, 0, 1)))
    # foot plate: rounded slab lofted along -Y
    fprof = Profile([(heel, fw * 0.55, 0.020), (heel - 0.022, fw * 0.95, 0.028),
                     (toe_y + 0.014, fw, 0.022), (toe_y, fw * 0.86, 0.015)])
    fc = [2 * math.pi * k / 8 for k in range(8)]
    fpts = []
    for k in range(4):
        y = heel - k * (heel - toe_y) / 3
        w, hgt = fprof.at(y)
        row = []
        for t in fc:
            u, v = super_pt(w / 2, hgt, 0.004, 2.6, t)
            row.append(V((foot_x + u, y, 0.004 + max(-0.003, v))))
        fpts.append(row)
    with p.soft(62):
        grid(p, fpts, lambda i, j: "brass", start_pole=V((foot_x, heel + 0.007, 0.010)),
             end_pole=V((foot_x, toe_y - 0.006, 0.008)))
    # toes + claws
    for k, dx in enumerate((-0.019, 0.0, 0.019)):
        tb = V((foot_x + dx * (fw / 0.054), toe_y + 0.008, 0.011))
        tt = tb + V((dx * 0.3, -0.024 - (0.004 if k == 1 else 0), -0.002))
        with p.soft(70):
            capsule(p, "copper", tb, tt, 0.0105, 0.009, seg=6, rings=1)
        d = (tt - tb).normalized()
        lathe_m(p, [(0.0062, 0.0, "ivory"), (0.0044, 0.0065, "ivory"), (0.0, 0.0135, "ivory")], 4,
                frame(tt + d * 0.004 + V((0, 0, -0.003)), d + V((0, 0, -0.35))))
    return build_world(p, body, piv, F(BODY_PIV))


# =============================================================================================
# TAIL — beads on an iron rod, 4-bone chain
# =============================================================================================
TAIL_CTRL = [V(q) for q in [(0, 0.293, 0.249), (0, 0.362, 0.240), (0, 0.430, 0.244), (0, 0.492, 0.270),
                            (0, 0.542, 0.316), (0, 0.573, 0.376), (0, 0.582, 0.440), (0, 0.568, 0.498),
                            (0, 0.540, 0.540)]]


def tail_sample(n=128):
    pts = []
    C = TAIL_CTRL
    per = n // (len(C) - 1)
    for i in range(len(C) - 1):
        p0, p1, p2, p3 = C[max(0, i - 1)], C[i], C[i + 1], C[min(len(C) - 1, i + 2)]
        for k in range(per):
            pts.append(V(H._cr(p0, p1, p2, p3, k / per)))
    pts.append(C[-1].copy())
    acc = [0.0]
    for a, b in zip(pts[:-1], pts[1:]):
        acc.append(acc[-1] + (b - a).length)
    return pts, acc


TP, TS = tail_sample()
TAIL_LEN = TS[-1]


def tail_at(s):
    s = max(0.0, min(TAIL_LEN, s))
    for i in range(len(TS) - 1):
        if TS[i + 1] >= s:
            t = (s - TS[i]) / max(1e-9, TS[i + 1] - TS[i])
            return TP[i].lerp(TP[i + 1], t), (TP[i + 1] - TP[i]).normalized()
    return TP[-1].copy(), (TP[-1] - TP[-2]).normalized()


def build_tail(body):
    beads = []
    s, k = 0.026, 0
    while True:
        L = 0.050 - k * 0.0030
        r = 0.031 - k * 0.0020
        if s + L > TAIL_LEN - 0.045:
            break
        beads.append((s, L, r))
        s += L + 0.012
        k += 1
    nb = len(beads)
    gaps = [b[0] + b[1] + 0.006 for b in beads[:-1]]
    jidx = {9: (1, 3, 5), 8: (1, 3, 5), 10: (2, 4, 6)}.get(nb, (nb // 4, nb // 2, (3 * nb) // 4))
    joints = [0.0] + [gaps[i] for i in jidx]
    print(f"[tail] length {TAIL_LEN:.3f} m, {nb} beads, joints at {[round(j, 3) for j in joints]}")
    parent, ppiv = body, BODY_PIV
    objs = []
    for ci in range(4):
        s0 = joints[ci]
        s1 = joints[ci + 1] if ci < 3 else TAIL_LEN
        piv, _ = tail_at(s0)
        p = SPart(f"tail_{ci + 1}")
        n = max(3, int((s1 - s0) / 0.04) + 1)
        rod = [tail_at(s0 + (s1 - s0) * i / (n - 1))[0] for i in range(n)]
        with p.soft(80):
            tube(p, "iron", [tuple(q) for q in rod], r=0.0074 - ci * 0.0006, seg=5, cap=True)
        for bi, (bs, L, r) in enumerate(beads):
            if not (s0 <= bs and bs + L <= s1 + 1e-6):
                continue
            c, d = tail_at(bs + L / 2)
            mat = "copper" if bi % 2 == 0 else "brass"
            lathe_m(p, [(r * 0.55, -L / 2, mat), (r, -L / 2 + 0.0065, mat), (r, L / 2 - 0.0065, mat),
                        (r * 0.55, L / 2, mat)], 6, frame(c, d))      # hex nuts
        if ci == 3:
            tip, d = tail_at(TAIL_LEN)
            Mg = frame(tip + d * 0.020, V((1, 0, 0)), up=tuple(d))
            gear(p, "brass", Mg, r=0.034, thick=0.010, teeth=8, depth=0.008, two_sided=True)
            for sg in (1, -1):
                lathe_m(p, [(0.0, 0.004, "glow_red"), (0.0085, 0.005, "glow_red"), (0.006, 0.0085, "glow_red"),
                            (0.0, 0.0098, "glow_red")], 8, Mg @ Matrix.Rotation(0 if sg > 0 else math.pi, 4, "X"))
        o = bw(p, parent, piv, ppiv)
        objs.append(o)
        parent, ppiv = o, piv
    return objs


# =============================================================================================
# KEY (rigid attachment, spins around local Z)
# =============================================================================================
def build_key(body):
    p = SPart("key")
    O = KEY_PIV
    gear(p, "brass_dark", Matrix.Translation(O + V((0, 0, 0.0105))), r=0.033, thick=0.010, teeth=8, depth=0.007,
         bottom=False)
    with p.soft(60):
        lathe_m(p, [(0.0, -0.01, "brass"), (0.0135, -0.01, "brass"), (0.0135, 0.076, "brass"), (0.0, 0.076, "brass")],
                10, Matrix.Translation(O))
        lathe_m(p, [(0.0145, 0.0, "brass"), (0.021, 0.005, "brass"), (0.021, 0.014, "brass"), (0.0, 0.019, "brass")],
                12, Matrix.Translation(O + V((0, 0, 0.044))))
    # bow: two big lobes in the XZ plane + central boss with a red gem on both faces
    by = O + V((0, 0, 0.106))
    with p.soft(80):
        for dx in (0.039, -0.039):
            torus_m(p, "brass", frame(by + V((dx, 0, 0.005)), (0, 1, 0)), R=0.028, r=0.0105, seg=14, seg2=5,
                    squash=0.72)
    Mb = frame(by, (0, 1, 0))
    with p.soft(60):
        lathe_m(p, [(0.0, -0.011, "brass"), (0.017, -0.009, "brass"), (0.020, 0.0, "brass"), (0.017, 0.009, "brass"),
                    (0.0, 0.011, "brass")], 10, Mb)
    for ax in ((0, -1, 0), (0, 1, 0)):
        lathe_m(p, [(0.0, 0.006, "glow_red"), (0.0078, 0.0085, "glow_red"), (0.0058, 0.0128, "glow_red"),
                    (0.0, 0.0142, "glow_red")], 8, frame(by, ax))
    return bw(p, body, KEY_PIV, BODY_PIV)


# =============================================================================================
# assemble
# =============================================================================================
body = build_body()
head = build_head(body)
ears = [build_ear(head, s) for s in (1, -1)]
legs = [build_leg(body, n) for n in ("FL", "FR", "BL", "BR")]
tails = build_tail(body)
key = build_key(body)

for o in [body, head, key] + ears + legs + tails:     # (smoothing happens in build_world)
    H.check_closed(o)

TAIL_SMOOTH = 0.022
arm = rig_from_parts(root, rigid={"key"},
                     smooth={"tail_2": TAIL_SMOOTH, "tail_3": TAIL_SMOOTH, "tail_4": TAIL_SMOOTH},
                     skin_name="cograt_skin")
total = tri_report()
if total > 10000:
    print(f"[WARN] cograt: {total} tris exceeds budget 10000")

hp.bake_vertex_ao(ground=0.0, distance=0.18, samples=48, strength=0.85, floor=0.3)


def plate_tone(co, mat, bone):
    """Chest and rump plates a shade darker than the saddle plate -> the shell reads as separate plates."""
    if bone != "body" or mat != "copper":
        return 1.0
    return 1.0 if BANDS[0] < co.y < BANDS[1] else 0.80


H.tint_skin(bpy.data.objects["cograt_skin"], plate_tone)
hp.export_glb_hp("cograt")

if "none" not in FLAGS:
    if "views" in FLAGS:
        hp.render_views("cograt")
    if "face" in FLAGS:
        hp.render_hp("cograt_face", target=(F((0, -0.33, 0.36)), 0.17), azimuth=28, elevation=12)
    if "game" in FLAGS:
        hp.render_hp("cograt_game", dist_k=7, elevation=25, azimuth=35)
        hp.render_hp("cograt_high", azimuth=25, elevation=42, dist_k=2.8)
    if "pose" in FLAGS:
        COGRAT_TEST_POSE = {
            "head": [("Z", 25), ("X", -10)],
            "ear_L": [("X", -30), ("Y", 20)],
            "ear_R": [("X", 20), ("Y", -15)],
            "leg_FL": [("X", -40)],
            "leg_BR": [("X", -35)],
            "leg_FR": [("X", 40)],
            "leg_BL": [("X", 40)],
            "tail_1": [("Z", -25), ("X", 5)],
            "tail_2": [("Z", -25), ("X", 10)],
            "tail_3": [("Y", 25)],
            "tail_4": [("Y", 35), ("X", 15)],
        }
        pose_views(arm, "cograt", COGRAT_TEST_POSE, views=(("", 35, 18), ("_back", 160, 40)))
        # EEVEE extremes of what the game does: attack lunge (body/head pitch + ~48 deg gait), rear-up with
        # head turn (neck ball joint), strong tail curl
        EXTREMES = {
            "lunge": {"body": [("X", 15)], "head": [("X", 20)], "leg_FL": [("X", -48)], "leg_BR": [("X", -48)],
                      "leg_FR": [("X", 48)], "leg_BL": [("X", 48)], "ear_L": [("X", 25)], "ear_R": [("X", 25)],
                      "tail_1": [("X", -8)], "tail_2": [("X", -10)], "tail_3": [("X", -12)],
                      "tail_4": [("X", -15)]},
            "rear": {"body": [("X", -15)], "head": [("X", -20), ("Z", 15)], "tail_1": [("Z", 20)],
                     "tail_2": [("Z", 25)], "tail_3": [("Z", 25)], "tail_4": [("Z", 25)], "ear_L": [("Y", 25)],
                     "ear_R": [("Y", -25)]},
            "curl": {"head": [("Z", -30), ("X", 12)], "tail_1": [("Z", -28), ("X", 10)], "tail_2": [("Z", -30)],
                     "tail_3": [("Z", -32), ("X", 12)], "tail_4": [("Z", -35), ("X", 15)], "leg_FR": [("X", -40)],
                     "leg_BL": [("X", -40)], "leg_FL": [("X", 35)], "leg_BR": [("X", 35)]},
        }
        for nm, pose in EXTREMES.items():
            pose_world(arm, pose)
            hp.render_hp(f"cograt_pose_{nm}", azimuth=55, elevation=20, size=640)
            reset_pose(arm)
