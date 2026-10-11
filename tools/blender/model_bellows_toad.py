"""Bellows Toad (hi-poly) — weak enemy, archetype **slime**. Exports public/models/bellows_toad.glb.

A squat, bottom-heavy toad whose body is an accordion-pleated leather bellows held between a brass
base ring and a brass head lid, with four stubby brass legs, a soot-blackened copper nozzle for a
mouth (ember glow deep inside), two pressure-gauge eyes and a red relief-valve wheel on top.

    root
    └─ body    pivot at ground centre (0,0,0) — bellows bag, frame, lid, lips, nozzle, legs
       │       (the game's squash & stretch on this node = the bellows breathing)
       ├─ valve    pivot on top of the lid; spins around its local Z (game: rot y)
       ├─ eye_L    (+X) pressure gauge, pivot at the gauge centre (wobbles about the forward axis)
       └─ eye_R    (-X)

All rest rotations are identity (the forward tilt of the lid lives in the geometry).
COLOR_0: baked vertex AO x tints (pleat valleys darker, soot on the nozzle tip and around the mouth);
glass covers alpha 0.45 (game opacity 0.35 x 0.45) like the Boiler Jelly's gauges.

Usage:  blender -b --factory-startup -P tools/blender/model_bellows_toad.py [-- options]
    --no-preview         export only
    --extra              close-ups, game-distance and squash / stretch renders
    --count              per-component triangle counts
    --preview-dir DIR    write previews to DIR (default tools/blender/previews)
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector, noise  # noqa: E402

import common  # noqa: E402
from common import Part, empty, get_mat, reset_scene  # noqa: E402
from char_helpers import tube  # noqa: E402
import hp_helpers as hp  # noqa: E402
import hp_slime_helpers as sh  # noqa: E402
import hp_wisp_helpers as wh  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if "--preview-dir" in ARGS:
    _pd = ARGS[ARGS.index("--preview-dir") + 1]
    hp.PREVIEW_DIR = common.PREVIEW_DIR = _pd

reset_scene()

get_mat("toad_leather", hex="#7a4a2c", metallic=0.0, roughness=0.72)
get_mat("toad_copper", hex="#8a4b2a", metallic=0.85, roughness=0.45)
get_mat("glow_toad_ember", hex="#b8320c", emission="#ff3c0a", strength=2.6)
for _m in ("brass", "brass_dark", "black", "white", "cloth_red", "glass"):
    get_mat(_m)

COMPS = {"body": [], "valve": [], "eye_L": [], "eye_R": []}
SOLID, GLASS, DECALS, NOZZLE, BAG = [], [], [], [], []
DIAL_INFO = {}


def add(p, part, kind="solid", smooth=40.0, face=None, bevel=None):
    o = sh.build_comp(p)
    if face:
        sh.orient_sheet(o, face[0], face[1])
    if bevel:
        hp.bevel_obj(o, width=bevel[0], segments=bevel[1], angle=bevel[2], harden=False)
    hp.smooth_obj(o, angle=smooth)
    COMPS[part].append(o)
    {"solid": SOLID, "glass": GLASS, "decal": DECALS, "nozzle": NOZZLE, "bag": BAG}[kind].append(o)
    if "--count" in ARGS:
        print(f"[comp] {part:6s} {o.name:22s} {sh.tris(o)}")
    return o


def _smooth01(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def catmull(ctrl, x):
    xs = [c[0] for c in ctrl]
    if x <= xs[0]:
        return ctrl[0][1]
    if x >= xs[-1]:
        return ctrl[-1][1]
    i = max(j for j in range(len(xs) - 1) if xs[j] <= x)
    p0 = ctrl[max(i - 1, 0)][1]
    p1, p2 = ctrl[i][1], ctrl[i + 1][1]
    p3 = ctrl[min(i + 2, len(ctrl) - 1)][1]
    t = (x - xs[i]) / (xs[i + 1] - xs[i])
    return 0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)


FRONT = -math.pi / 2
SY = 0.88                     # depth / width ratio of the body
LID_Z = 0.600                 # lid rim height (before the forward tilt)
TILT = math.radians(9.0)      # lid tilts forward (front lower) -> sloping toad face
M_HEAD = Matrix.Translation((0, 0, LID_Z)) @ Matrix.Rotation(TILT, 4, "X") @ Matrix.Translation((0, 0, -LID_Z))


def tilt_w(z):
    return _smooth01((z - 0.36) / 0.26)


def tilt_pt(v):
    """Blend from untilted (low on the bag) to the lid tilt (top of the bag)."""
    w = tilt_w(v.z)
    if w <= 0:
        return v
    return v.lerp(M_HEAD @ v, w)


# =========================================================================================
# Bellows bag (leather, accordion pleats)
# =========================================================================================
BAG_R = [(0.095, 0.400), (0.13, 0.502), (0.18, 0.562), (0.24, 0.574), (0.31, 0.552), (0.39, 0.506),
         (0.47, 0.448), (0.55, 0.388), (0.62, 0.343), (0.66, 0.320)]
N_AROUND = 32
PLEAT_Z0, PLEAT_Z1, N_PLEATS = 0.145, 0.595, 7
PLEAT_A = 0.040


def bag_r(theta, z):
    r = catmull(BAG_R, z)
    # throat pouch: the front sags forward / down
    fr = math.exp(-(_wrap(theta - FRONT) / 0.75) ** 2)
    r *= 1.0 + 0.095 * fr * math.exp(-((z - 0.22) / 0.13) ** 2)
    # haunches: rear sides bulge low
    for c in (math.radians(25), math.radians(155)):
        r *= 1.0 + 0.045 * math.exp(-(_wrap(theta - c) / 0.55) ** 2) * math.exp(-((z - 0.20) / 0.10) ** 2)
    # soft lumpiness
    q = Vector((math.cos(theta), math.sin(theta), z * 2.0)) * 1.6
    r *= 1.0 + 0.012 * noise.noise(q + Vector((3.1, 0.7, 5.3)))
    return r


def bag_pt(theta, r, z):
    return tilt_pt(Vector((r * math.cos(theta), r * math.sin(theta) * SY, z)))


PLEAT_ZS = []


def bag_rings():
    """[(z, kind)] kind: 'v' valley, 'r' ridge, 't' tuck (no modulation)."""
    rings = [(0.095, "t"), (0.120, "t")]
    pitch = (PLEAT_Z1 - PLEAT_Z0) / N_PLEATS
    for k in range(N_PLEATS):
        z = PLEAT_Z0 + pitch * k
        rings.append((z, "v"))
        rings.append((z + pitch * 0.5, "r"))
        PLEAT_ZS.append(z + pitch * 0.5)
    rings.append((PLEAT_Z1, "v"))
    rings += [(0.635, "t"), (0.665, "t")]
    return rings


def pleat_amp(z):
    # deeper folds on the sagging belly, shallower near the frames
    return PLEAT_A * (0.55 + 0.45 * math.exp(-((z - 0.25) / 0.20) ** 2))


def build_bag():
    p = Part("c_bag")
    bm = p.bm
    rows = []
    for (z, kind) in bag_rings():
        row = []
        for j in range(N_AROUND):
            th = 2 * math.pi * j / N_AROUND
            r = bag_r(th, z)
            if kind == "v":
                r *= 1.0 - pleat_amp(z)
            elif kind == "r":
                r *= 1.0 + pleat_amp(z)
            elif z < 0.13:
                r *= 0.93
            else:
                r *= 0.90
            row.append(bm.verts.new(bag_pt(th, r, z)))
        rows.append(row)
    n = N_AROUND
    for k in range(len(rows) - 1):
        A, B = rows[k], rows[k + 1]
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((A[i], A[j], B[j], B[i]))
    p._assign([v for r in rows for v in r], "toad_leather")
    return add(p, "body", "bag", smooth=48)


def ridge_pt(theta, z, out=0.0):
    r = bag_r(theta, z) * (1.0 + pleat_amp(z)) + out
    return bag_pt(theta, r, z)


# =========================================================================================
# Brass frame: base ring + bottom board, straps, lid, lips
# =========================================================================================
def build_base():
    p = Part("c_base")
    prof = [(0.300, 0.050), (0.395, 0.052), (0.428, 0.064), (0.440, 0.086), (0.438, 0.118), (0.424, 0.136),
            (0.398, 0.146), (0.360, 0.148)]
    wh.revolve(p, "brass", prof, wh.circle(32), caps=(True, True),
               scale=(1.0, SY, 1.0))
    wh.revolve(p, "brass_dark", [(0.0, 0.040), (0.36, 0.040), (0.37, 0.052), (0.0, 0.052)], wh.circle(24),
               scale=(1.0, SY, 1.0))
    # bolt heads around the ring
    for k in range(10):
        a = 2 * math.pi * (k + 0.5) / 10
        n = Vector((math.cos(a), math.sin(a) * SY, 0)).normalized()
        c = Vector((math.cos(a) * 0.441, math.sin(a) * 0.441 * SY, 0.101))
        p.sphere("brass_dark", r=0.0130, seg=5, rings=3, loc=tuple(c), rot=sh.orient(n), scale=(1, 1, 0.55))
    add(p, "body", smooth=40)


STRAPS = [math.radians(a) for a in (-22, -158, 36, 144)]


def build_straps():
    p = Part("c_straps")
    sec = [(0.0045, 0.019), (-0.0045, 0.019), (-0.0045, -0.019), (0.0045, -0.019)]
    for th in STRAPS:
        zs = [0.140] + PLEAT_ZS + [0.612]
        pts = []
        for z in zs:
            if z in PLEAT_ZS:
                pts.append(ridge_pt(th, z, 0.004))
            else:
                pts.append(bag_pt(th, bag_r(th, z) * 0.98 + 0.012, z))
        # radial outward direction as the sweep "up" -> the strap lies flat on the bag
        outward = (math.cos(th), math.sin(th) * SY, 0.0)
        wh.sweep(p, "brass", pts, [sec] * len(pts), up=outward)
        for z in (zs[0] + 0.012, zs[-1] - 0.020):
            c = bag_pt(th, bag_r(th, z) * 0.98 + 0.024, z)
            p.sphere("brass_dark", r=0.0105, seg=5, rings=3, loc=tuple(c))
    add(p, "body", smooth=45)


LID_PROF = [(0.300, 0.578), (0.392, 0.586), (0.414, 0.604), (0.410, 0.626), (0.392, 0.640), (0.372, 0.648),
            (0.352, 0.676), (0.312, 0.712), (0.252, 0.744), (0.180, 0.766), (0.100, 0.780), (0.0, 0.785)]


def lid_z(r):
    """Height of the (untilted) lid dome at radius r (elliptic radius)."""
    pts = LID_PROF[5:]
    for (ra, za), (rb, zb) in zip(pts, pts[1:]):
        if rb <= r <= ra:
            t = (r - rb) / (ra - rb)
            return zb + (za - zb) * t
    return LID_PROF[-1][1] if r < 0.2 else LID_PROF[5][1]


def build_lid():
    p = Part("c_lid")
    wh.revolve(p, "brass", LID_PROF, wh.circle(32), caps=(True, False),
               scale=(1.0, SY, 1.0))
    wh.paint_faces(p, "brass_dark", 0, lambda c: c.z < 0.645 and math.hypot(c.x, c.y / SY) > 0.385)
    sh.xform(p, M_HEAD)
    add(p, "body", smooth=38)
    # rivets on the lid shoulder
    p = Part("c_lid_rivets")
    for k in range(12):
        a = 2 * math.pi * (k + 0.5) / 12
        if abs(_wrap(a - FRONT)) < 0.75:
            continue                               # the lips cover the front
        r = 0.362
        c = Vector((math.cos(a) * r, math.sin(a) * r * SY, 0.664))
        p.sphere("brass_dark", r=0.0100, seg=5, rings=3, loc=tuple(M_HEAD @ c))
    add(p, "body", smooth=60)


def build_lips():
    """Wide toad mouth: a thick rounded brass lip band across the front of the lid rim."""
    p = Part("c_lips")
    a0, a1 = FRONT - 1.05, FRONT + 1.05
    pts, secs = [], []
    n = 18
    for i in range(n + 1):
        t = i / n
        a = a0 + (a1 - a0) * t
        r = 0.420 + 0.012 * math.sin(math.pi * t)
        z = 0.600 - 0.010 * math.sin(math.pi * t) ** 2         # the smile sags a little in the middle
        pts.append(Vector((math.cos(a) * r, math.sin(a) * r * SY, z)))
        w = 0.6 + 0.4 * math.sin(math.pi * t)
        secs.append(wh.round_section(0.026 * w + 0.006, 8, flat=0.75))
    secs[0] = secs[-1] = None
    wh.sweep(p, "brass", pts, secs, up=(0, 0, 1))
    sh.xform(p, M_HEAD)
    add(p, "body", smooth=60)


# =========================================================================================
# Nozzle mouth (copper, soot-blackened) + ember
# =========================================================================================
NZ_BASE = Vector((0.0, -0.352, 0.452))
NZ_DIR = Vector((0.0, -0.975, 0.08)).normalized()
NZ_LEN = 0.215


def build_nozzle():
    M = sh.frame(NZ_DIR, up=(0, 0, 1), origin=NZ_BASE)
    p = Part("c_nozzle_flange")
    sh.revolve(p, "brass", [(0.060, -0.040), (0.088, -0.030), (0.100, -0.014), (0.098, 0.004), (0.086, 0.014),
                            (0.070, 0.016)], seg=16, M=M, cap0=False)
    for k in range(6):
        a = 2 * math.pi * k / 6 + 0.26
        p.sphere("brass_dark", r=0.0085, seg=5, rings=3, loc=tuple(M @ Vector((math.cos(a) * 0.084,
                                                                              math.sin(a) * 0.084, 0.016))))
    add(p, "body", smooth=45)
    p = Part("c_nozzle")
    L = NZ_LEN
    prof = [(0.074, 0.000), (0.076, 0.022), (0.082, 0.030), (0.076, 0.044), (0.064, 0.080),
            (0.058, 0.118), (0.064, 0.126), (0.062, 0.142), (0.052, 0.150), (0.051, L - 0.024),
            (0.064, L - 0.008), (0.066, L), (0.056, L + 0.004), (0.046, L - 0.004), (0.044, L - 0.030)]
    sh.revolve(p, "toad_copper", prof, seg=18, M=M)
    sh.revolve(p, "black", [(0.0445, L - 0.030), (0.040, L - 0.070), (0.0, L - 0.074)], seg=18, M=M)
    add(p, "body", "nozzle", smooth=42)
    p = Part("c_ember")
    sh.revolve(p, "glow_toad_ember", [(0.0, L - 0.045), (0.020, L - 0.050), (0.032, L - 0.062), (0.0, L - 0.066)],
               seg=12, M=M)
    add(p, "body", "nozzle", smooth=180)


def soot_tint(pw, nw):
    """Soot: darker toward the nozzle tip, faint smudge on the lips above it."""
    d = (pw - NZ_BASE).dot(NZ_DIR)
    t = _smooth01((d - 0.03) / (NZ_LEN - 0.03))
    k = 1.0 - 0.80 * t ** 1.3
    return (k, k * 0.96, k * 0.93)


def body_tint(pw, nw):
    k = 1.0
    # smudge of soot on the lips / lid right above the nozzle
    q = Vector((pw.x, pw.y, pw.z)) - (NZ_BASE + Vector((0, -0.05, 0.09)))
    k *= 1.0 - 0.45 * math.exp(-(q.x / 0.09) ** 2 - (q.z / 0.06) ** 2) * (1.0 if pw.y < -0.30 else 0.0)
    return (k, k, k)


def bag_tint(pw, nw):
    """Leather: worn, lighter ridges and darker folds, a little darker at the bottom."""
    z = pw.z
    pitch = (PLEAT_Z1 - PLEAT_Z0) / N_PLEATS
    ph = ((z - PLEAT_Z0) / pitch) % 1.0                       # 0 valley -> 0.5 ridge -> 1 valley
    ridge = 1.0 - abs(ph - 0.5) * 2.0
    k = 0.86 + 0.20 * ridge ** 2
    k *= 0.88 + 0.12 * _smooth01((z - 0.10) / 0.25)
    return (k, k * 0.98, k * 0.95)


# =========================================================================================
# Legs
# =========================================================================================
LEGS = [  # (hip xy, ankle xy, foot direction deg (0 = +X, CCW))
    ((0.300, -0.225), (0.375, -0.300), -62.0),
    ((0.320, 0.215), (0.420, 0.270), 28.0),
]


def build_legs():
    p = Part("c_legs")
    for s in (1, -1):
        for (hip, ank, fd) in LEGS:
            H = Vector((s * hip[0], hip[1], 0.092))
            A = Vector((s * ank[0], ank[1], 0.040))
            p.sphere("brass", r=0.056, seg=8, rings=5, loc=tuple(H), scale=(1, 1, 0.85))
            tube(p, "brass_dark", [H, A], [0.034, 0.030], seg=8, cap=False)
            mid = H.lerp(A, 0.45)
            dirv = (A - H).normalized()
            p.cyl("brass", r=0.041, h=0.020, seg=8, loc=tuple(mid), rot=sh.orient(dirv))
            p.sphere("brass", r=0.036, seg=6, rings=4, loc=tuple(A + Vector((0, 0, -0.004))), scale=(1, 1, 0.8))
            a0 = math.radians(fd if s > 0 else 180 - fd)
            for t in (-0.62, 0.0, 0.62):
                a = a0 + t
                d = Vector((math.cos(a), math.sin(a), 0))
                e = A + d * 0.020 + Vector((0, 0, -0.016))
                f = A + d * (0.090 if t == 0 else 0.074) + Vector((0, 0, -0.026))
                tube(p, "brass", [e, f], [0.017, 0.014], seg=5, cap=False)
                p.sphere("brass", r=0.021, seg=6, rings=4, loc=tuple(f + d * 0.006 + Vector((0, 0, -0.002))),
                         scale=(1.15, 1.15, 0.72))
    add(p, "body", smooth=45)


# =========================================================================================
# Pressure-gauge eyes (after the Boiler Jelly's, bigger and sitting up on the lid like toad eyes)
# =========================================================================================
EYES = {"eye_L": (1.0, 1, 1.04), "eye_R": (-1.0, -1, 0.96)}     # (x sign, side, scale)
EYE_LOCAL = Vector((0.178, -0.170, 0.0))
EYE_N = Vector((0.34, -0.80, 0.50))
EYE_OUT = 0.064
GLASS_ALPHA = 0.45


def eye_frame(name):
    sx, side, s = EYES[name]
    x, y = EYE_LOCAL.x * sx, EYE_LOCAL.y
    z = lid_z(math.hypot(x, y / SY))
    base = M_HEAD @ Vector((x, y, z))
    n = (M_HEAD.to_3x3() @ Vector((EYE_N.x * sx, EYE_N.y, EYE_N.z))).normalized()
    C = base + n * EYE_OUT
    return C, n, sh.frame(n, up=(0, 0, 1), origin=C) @ Matrix.Scale(s, 4), side, s


def build_eye(name):
    C, ng, M, side, s = eye_frame(name)

    def dial_dir(phi):
        a = math.radians(phi)
        return math.sin(a), math.cos(a)

    # turret can (sunk into the lid; part of the eye so the wobble keeps it aligned)
    p = Part(f"c_{name}_housing")
    sh.revolve(p, "brass_dark", [(0.0, -0.105), (0.074, -0.105), (0.086, -0.040), (0.094, -0.004)],
               seg=16, M=M, cap1=True)
    add(p, name, smooth=40)
    # bezel ring + screws
    p = Part(f"c_{name}_bezel")
    sh.revolve(p, "brass", [(0.084, 0.000), (0.084, 0.021), (0.091, 0.031), (0.102, 0.029), (0.108, 0.015),
                            (0.104, -0.006)], seg=20, closed=True, M=M)
    for k in range(4):
        x, y = dial_dir(45 + 90 * k)
        sh.revolve(p, "brass_dark", [(0.0058, 0.027), (0.0040, 0.0330), (0.0, 0.0342)],
                   seg=6, M=M @ Matrix.Translation((x * 0.0965, y * 0.0965, 0.0)))
    add(p, name, smooth=50)
    # dial face + ticks + red zone
    p = Part(f"c_{name}_dial")
    sh.disc(p, "white", 0.0855, z=0.006, seg=24, M=M, fan=True)
    for k in range(11):
        phi = -135 + 27 * k
        x, y = dial_dir(phi)
        major = k % 2 == 0
        L = 0.0150 if major else 0.0095
        rc = 0.0745 - L / 2
        sh.flat_quad(p, "black", x * rc, y * rc, 0.0048 if major else 0.0033, L, ang=-math.radians(phi),
                     z=0.0072, M=M)
    a0, a1 = (math.radians(90 - 135), math.radians(90 - 88)) if side > 0 else \
        (math.radians(90 + 88), math.radians(90 + 135))
    sh.arc_strip(p, "cloth_red", 0.052, 0.0765, a0, a1, z=0.0066, seg=7, M=M)
    o = add(p, name, "decal", smooth=180, face=(ng, None))
    DIAL_INFO[o.name] = (C, ng, 0.0855 * s)
    # needle (+ pupil hub + catch-lights): pegged toward the red zone -> greedy, eager look
    p = Part(f"c_{name}_needle")
    phi_n = side * 52.0
    R = Matrix.Rotation(-math.radians(phi_n), 4, "Z")
    sh.flat_poly(p, "black", [(0.0, -0.024), (0.0052, -0.010), (0.0034, 0.030), (0.0, 0.066),
                              (-0.0034, 0.030), (-0.0052, -0.010)], z=0.0130, thick=0.0025, M=M @ R)
    sh.revolve(p, "black", [(0.0360, 0.0085), (0.0360, 0.0140), (0.0300, 0.0200), (0.0170, 0.0230),
                            (0.0, 0.0238)], seg=12, M=M, cap0=True)
    sh.disc(p, "white", 0.0105, z=0.0236, seg=10, M=M, cx=-0.0125, cy=0.0125)
    sh.disc(p, "white", 0.0045, z=0.0232, seg=8, M=M, cx=0.0135, cy=-0.0112)
    add(p, name, smooth=50, face=(ng, {"white"}))
    # glass cover
    p = Part(f"c_{name}_glass")
    sh.revolve(p, "glass", [(0.0855, 0.0205), (0.055, 0.0310), (0.0, 0.0343)], seg=20, M=M)
    add(p, name, "glass", smooth=180, face=(ng, None))
    return C


# =========================================================================================
# Relief valve (spins) on top of the lid
# =========================================================================================
VALVE_LOCAL = Vector((0.0, 0.085, 0.0))


def valve_pivot():
    z = lid_z(math.hypot(VALVE_LOCAL.x, VALVE_LOCAL.y / SY))
    return M_HEAD @ Vector((VALVE_LOCAL.x, VALVE_LOCAL.y, z))


def build_valve(V):
    T = Matrix.Translation(V)
    p = Part("c_valve_flange")
    sh.revolve(p, "brass_dark", [(0.0, -0.022), (0.070, -0.022), (0.077, -0.012), (0.076, 0.004), (0.068, 0.010),
                                 (0.042, 0.012), (0.0, 0.013)], seg=12, M=T)
    for k in range(5):
        a = 2 * math.pi * (k + 0.5) / 5
        p.cyl("brass", r=0.0085, h=0.008, seg=5, loc=(V.x + math.cos(a) * 0.058, V.y + math.sin(a) * 0.058, V.z + 0.012))
    add(p, "valve", smooth=40)
    p = Part("c_valve_body")
    sh.revolve(p, "brass", [(0.030, 0.008), (0.030, 0.024), (0.040, 0.034), (0.046, 0.048), (0.042, 0.062),
                            (0.030, 0.072), (0.020, 0.076), (0.020, 0.096), (0.024, 0.100), (0.0, 0.101)],
               seg=12, M=T, cap0=True)
    add(p, "valve", smooth=45)
    WZ = 0.084
    p = Part("c_valve_wheel")
    p.torus("cloth_red", R=0.062, r=0.0085, seg=18, seg2=5, loc=tuple(V + Vector((0, 0, WZ))))
    p.cyl("cloth_red", r=0.018, h=0.018, seg=10, loc=tuple(V + Vector((0, 0, WZ))))
    for k in range(4):
        a = 2 * math.pi * k / 4 + 0.4
        pts = [V + Vector((math.cos(a) * 0.015, math.sin(a) * 0.015, WZ)),
               V + Vector((math.cos(a + 0.2) * 0.036, math.sin(a + 0.2) * 0.036, WZ + 0.002)),
               V + Vector((math.cos(a + 0.36) * 0.058, math.sin(a + 0.36) * 0.058, WZ))]
        tube(p, "cloth_red", pts, 0.0050, seg=5)
    add(p, "valve", smooth=55)
    # little steam whistle on top
    p = Part("c_valve_whistle")
    sh.revolve(p, "brass", [(0.013, 0.098), (0.013, 0.150), (0.017, 0.156), (0.017, 0.166), (0.0, 0.168)],
               seg=10, M=T, cap0=True)
    p.box("black", size=(0.016, 0.004, 0.008), loc=tuple(V + Vector((0, -0.0128, 0.134))))
    p.sphere("brass_dark", r=0.009, seg=6, rings=4, loc=tuple(V + Vector((0, 0, 0.174))))
    add(p, "valve", smooth=45)


# =========================================================================================
# Assemble
# =========================================================================================
bag = build_bag()
build_base()
build_straps()
build_lid()
build_lips()
build_nozzle()
build_legs()
eye_c = {n: build_eye(n) for n in EYES}
VP = valve_pivot()
build_valve(VP)

occ = SOLID + BAG + NOZZLE + DECALS
hp.bake_vertex_ao(objs=SOLID, occluders=occ, samples=48, distance=0.09, strength=0.8, floor=0.35, ground=0.0,
                  tint=body_tint)
hp.bake_vertex_ao(objs=BAG, occluders=occ, samples=48, distance=0.10, strength=0.85, floor=0.30, ground=0.0,
                  tint=bag_tint)
hp.bake_vertex_ao(objs=NOZZLE, occluders=occ, samples=40, distance=0.07, strength=0.7, floor=0.4, ground=0.0,
                  tint=soot_tint)
for d in DECALS:
    c, n, r = DIAL_INFO[d.name]
    sh.radial_colour(d, c, n, r, edge=0.80, start=0.6)
hp.fill_vertex_color(GLASS, color=(1.0, 1.0, 1.0))
for g in GLASS:
    a = g.data.color_attributes[hp.AO_ATTR]
    cols = np.ones((len(g.data.loops), 4), dtype=np.float32)
    cols[:, 3] = GLASS_ALPHA
    a.data.foreach_set("color", cols.ravel())

root = empty("root")
body = sh.join(COMPS["body"], "body", (0, 0, 0))
body.parent = root
valve = sh.join(COMPS["valve"], "valve", VP)
valve.parent = body
eye_L = sh.join(COMPS["eye_L"], "eye_L", eye_c["eye_L"])
eye_L.parent = body
eye_R = sh.join(COMPS["eye_R"], "eye_R", eye_c["eye_R"])
eye_R.parent = body
bpy.context.view_layer.update()

total = 0
for o in (body, valve, eye_L, eye_R):
    t = sh.tris(o)
    total += t
    print(f"[tris] {o.name:6s} {t}")
print(f"[tris] TOTAL {total}")
if total > 8000:
    print(f"[WARN] bellows_toad: {total} tris exceeds the slime-tier budget 8000")
print("[mats]", sorted({m.name for o in (body, valve, eye_L, eye_R) for m in o.data.materials}))
bb = [o.matrix_world @ Vector(c) for o in (body, valve, eye_L, eye_R) for c in o.bound_box]
mn = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
mx = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
print(f"[size] width {mx.x - mn.x:.3f}  depth {mx.y - mn.y:.3f}  height {mx.z:.3f}")


def check_wobble():
    """Eyes wobble +-0.3 rad about the forward (-Y) axis in the game: report the gauge-vs-body clearance."""
    for e in (eye_L, eye_R):
        n = eye_frame(e.name)[1]
        worst = 9.0
        ovs = 0
        for a in (-0.3, 0.0, 0.3):
            e.rotation_euler = (0, a, 0)       # Blender Y = model forward axis
            bpy.context.view_layer.update()
            d, ov = wh.clearance(e, body, keep_a=lambda co, n=n: co.dot(n) > -0.008)
            worst = min(worst, d)
            ovs = max(ovs, ov)
            print(f"[motion]   {e.name} wobble {a:+.1f}: clearance {d * 1000:.1f} mm, overlaps {ov}")
        e.rotation_euler = (0, 0, 0)
        print(f"[motion] {e.name} gauge front vs body: min clearance {worst * 1000:.1f} mm, overlaps {ovs}")
    bpy.context.view_layer.update()


check_wobble()
hp.export_glb_hp("bellows_toad")


def preview_materials():
    """Preview only: glass alpha 0.35 x COLOR_0 alpha, blended (like the game)."""
    m = bpy.data.materials.get("glass")
    if m:
        nt = m.node_tree
        bsdf = nt.nodes["Principled BSDF"]
        at = nt.nodes.new("ShaderNodeVertexColor")
        at.layer_name = hp.AO_ATTR
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = 0.35
        nt.links.new(at.outputs["Alpha"], mul.inputs[0])
        nt.links.new(mul.outputs[0], bsdf.inputs["Alpha"])
        try:
            m.surface_render_method = "BLENDED"
        except Exception:
            pass


if "--no-preview" not in ARGS:
    preview_materials()
    hp.render_views("bellows_toad", views=(("", 35, 20), ("_front", 0, 8), ("_side", 90, 8), ("_back", 200, 22)))
    hp.render_hp("bellows_toad_game", azimuth=25, elevation=30, dist_k=6.5)
    if "--extra" in ARGS:
        hp.render_hp("bellows_toad_face", target=((0, -0.35, 0.62), 0.30), azimuth=15, elevation=14)
        hp.render_hp("bellows_toad_top", azimuth=30, elevation=60)
        for nm, sc in (("bellows_toad_squash", (1.08, 1.08, 0.86)), ("bellows_toad_stretch", (0.97, 0.97, 1.06))):
            body.scale = sc
            bpy.context.view_layer.update()
            hp.render_hp(nm, azimuth=30, elevation=18)
        body.scale = (1, 1, 1)
print(f"[bellows_toad] done, {total} tris")
