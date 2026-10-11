"""Prism Moth (hi-poly) — weak floating enemy, archetype **wisp**. Exports public/models/prism_moth.glb.

Clockwork moth with four stained-glass wings (cyan / violet / amber panes in lead cames), a segmented
brass body, a glowing aether crystal under the thorax and two clock hands for antennae.

    root (ground, 0,0,0)
    └─ lantern        thorax centre, z = 1.2 (wisp body node: bob / sway / attack tilt) — thorax,
       │              copper fur collar, six dangling legs, crystal setting, wing bosses
       ├─ flame       aether crystal on the belly (glow_moth_aether); the game's fake light and
       │              spell origin follow it, its flicker scale makes the crystal pulse
       ├─ ring_A      small clockwork gear on the back of the thorax (spins around Z)
       ├─ wing_L      forewing + hindwing (+X), pivot at the wing hinge on the thorax
       ├─ wing_R      mirror (-X)
       ├─ head        pivot at the neck: head, compound eyes, enamel clock dial on the forehead
       │  ├─ antenna_L  minute hand (+X), pivot at the dial centre   (secondary chain "antenna_")
       │  └─ antenna_R  hour hand (-X)
       └─ tail_1      abdomen, first three segments (secondary chain "tail_", sways / lifts)
          └─ tail_2   last three segments + tip

Game motion (src/anim/rig.ts, archetype 'wisp'): wing_L / wing_R yaw +-0.6 rad about the vertical
axis at 14 rad/s -> with the wings spread flat the moth "rows" like a hovering hawk-moth (fore/aft
wing stroke).  The forewing's costa stays clear of the head and the hindwings' inner edges stay clear
of each other at both stroke extremes (check_motion prints [motion] clearances).  tail_* and
antenna_* get the game's generic secondary motion; ring_B does not exist (rig ignores it).

Materials: glow_moth_* panes are emissive (dim emission x the game's minimum intensity 2.2) and
alpha-blended (alpha 0.84 -> glTF BLEND), lead cames are opaque; glow faces get no AO.

Usage:  blender -b --factory-startup -P tools/blender/model_prism_moth.py [-- options]
    --no-preview         export only
    --extra              extra close-ups + flap / sway pose renders
    --quick              only the 3/4 view and the face close-up
    --preview-dir DIR    write previews to DIR (default tools/blender/previews)
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector, noise  # noqa: E402

import common  # noqa: E402
from common import Part, empty, get_mat, reset_scene  # noqa: E402
from char_helpers import gem, prism, sgear, tube  # noqa: E402
import hp_helpers as hp  # noqa: E402
import hp_wisp_helpers as wh  # noqa: E402
import hp_slime_helpers as sh  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if "--preview-dir" in ARGS:
    _pd = ARGS[ARGS.index("--preview-dir") + 1]
    hp.PREVIEW_DIR = common.PREVIEW_DIR = _pd

reset_scene()


# =========================================================================================
# Materials
# =========================================================================================
def _dim(hexs, k):
    h = hexs.lstrip("#")
    return "#" + "".join(f"{int(int(h[i:i + 2], 16) * k):02x}" for i in (0, 2, 4))


PANE_ALPHA = 0.84
PANE_GLOW = 0.42                 # emission colour = pane colour x this (sRGB); game forces strength >= 2.2
PANES = {"c": ("glow_moth_cyan", "#5fd0e0"), "v": ("glow_moth_violet", "#9a7bd8"),
         "a": ("glow_moth_amber", "#e8a84a")}
for _n, _h in PANES.values():
    get_mat(_n, hex=_h, emission=_dim(_h, PANE_GLOW), strength=2.2, alpha=PANE_ALPHA, roughness=0.08)
get_mat("glow_moth_aether", hex="#a98bff", emission="#8f66ff", strength=3.2)
get_mat("moth_lead", hex="#2b2a28", metallic=0.55, roughness=0.5)
get_mat("moth_eye", hex="#1d1730", metallic=0.25, roughness=0.12)
get_mat("moth_hand", hex="#2f3f72", metallic=0.85, roughness=0.28)     # blued steel clock hands
for _m in ("brass", "brass_dark", "copper", "white"):
    get_mat(_m)

LZ = 1.2                          # thorax centre (lantern pivot) height
T_L = Matrix.Translation((0, 0, LZ))

COMPS = {}                        # node name -> component objects (world coordinates)
SOLID, PANE_OBJS = [], []
PANE_SHADE = {}                   # pane object name -> per-face brightness list


def comp(p, node, shade="smooth", angle=40.0, M=T_L, solid=True, bevel=None, sheet=None):
    """Transform a Part (built in lantern-local coords unless M says otherwise) into world space and
    build it as a loose component of `node`."""
    sh.xform(p, M)
    o = p.build(None, loc=(0, 0, 0))
    if sheet is not None:
        sh.orient_sheet(o, sheet)
    if bevel:
        hp.bevel_obj(o, width=bevel[0], segments=bevel[1], angle=bevel[2], harden=False)
    if shade == "wn":
        wh.wn_obj(o, angle)
    elif shade == "flat":
        hp.flat_obj(o)
    else:
        hp.smooth_obj(o, angle)
    COMPS.setdefault(node, []).append(o)
    if "--count" in ARGS:
        print(f"[comp] {node:10s} {o.name:22s} {hp.obj_tris(o)}")
    if solid:
        SOLID.append(o)
    return o


C16, C12, C10, C8 = wh.circle(16), wh.circle(12), wh.circle(10), wh.circle(8)


# =========================================================================================
# THORAX (lantern)
# =========================================================================================
TH_RX, TH_RZ = 0.094, 0.088        # thorax half width / half height


def build_thorax():
    p = Part("lantern")
    prof = [(0.0, -0.118), (0.040, -0.114), (0.068, -0.100), (0.086, -0.076), (0.095, -0.042),
            (0.098, -0.004), (0.096, 0.036), (0.087, 0.072), (0.068, 0.099), (0.040, 0.114), (0.0, 0.120)]
    wh.revolve(p, "brass", prof, wh.circle(18), rot=(-90, 0, 0), scale=(TH_RX / 0.098, TH_RZ / 0.098, 1))
    comp(p, "lantern", "smooth", 40)
    # two machined bands (built round on the profile radius, squashed to the elliptic section)
    p = Part("lantern_bands")
    for y, r in ((-0.050, 0.0960), (0.046, 0.0950)):
        wh.ring_band(p, "brass_dark", r, [(0.007, -0.007), (0.007, 0.007), (-0.004, 0.008), (-0.004, -0.008)],
                     seg=20, loc=(0, y, 0), rot=(-90, 0, 0))
    sh.xform(p, Matrix.Diagonal((TH_RX / 0.098, 1.0, TH_RZ / 0.098, 1.0)))
    comp(p, "lantern", "smooth", 40)
    # rivets along the bands (top half only: that's what the 3/4 camera sees)
    p = Part("lantern_rivets")
    for y, r in ((-0.050, 0.104), (0.046, 0.103)):
        for k in range(5):
            a = math.radians(10 + 160 * k / 4)
            p.sphere("brass", r=0.0055, seg=5, rings=4,
                     loc=(math.cos(a) * r * TH_RX / 0.098, y, math.sin(a) * r * TH_RZ / 0.098))
    comp(p, "lantern", "smooth", 80)
    # dorsal shield plate between the bands (raised, rounded) under the gear
    p = Part("lantern_shield")
    wh.revolve(p, "brass", [(0.0, 0.000), (0.038, 0.000), (0.046, 0.004), (0.048, 0.010), (0.040, 0.014),
                            (0.0, 0.015)], wh.circle(18), loc=(0, 0.004, TH_RZ - 0.010), scale=(1.0, 1.25, 1))
    comp(p, "lantern", "smooth", 40)


def build_collar():
    """Copper 'fur' ruff between head and thorax (fluted flared shell)."""
    p = Part("lantern_collar")
    prof = [(0.052, -0.084), (0.078, -0.088), (0.097, -0.099), (0.104, -0.111), (0.097, -0.123), (0.078, -0.131),
            (0.056, -0.134)]
    wh.revolve(p, "copper", prof, wh.fluted(28, 0.13), caps=(False, False), rot=(-90, 0, 0),
               scale=(1.0, 0.94, 1))
    comp(p, "lantern", "smooth", 70)


LEGS = ((-0.058, -0.050, 30), (-0.004, 0.0, 0), (0.050, 0.055, -28))   # (attach y, foot dy, splay)


def build_legs():
    p = Part("lantern_legs")
    for s in (1, -1):
        for (y, dy, spl) in LEGS:
            a = Vector((s * 0.040, y, -0.068))
            b = Vector((s * 0.098, y + dy * 0.4, -0.092))
            c = Vector((s * 0.112, y + dy * 0.8, -0.150))
            d = Vector((s * 0.098, y + dy, -0.196))
            tube(p, "brass_dark", [a, b, c, d], [0.0095, 0.0085, 0.0058, 0.0035], seg=5)
    comp(p, "lantern", "smooth", 60)


CRYSTAL = Vector((0.0, 0.012, -0.142))     # flame pivot (lantern local)


def build_setting():
    p = Part("lantern_setting")
    wh.revolve(p, "brass", [(0.0, -0.070), (0.026, -0.072), (0.036, -0.084), (0.038, -0.096), (0.034, -0.106),
                            (0.026, -0.110), (0.0, -0.110)], wh.fluted(16, 0.08), loc=(0, CRYSTAL.y, 0))
    for k in range(4):
        a = math.radians(45 + 90 * k)
        d = Vector((math.cos(a), math.sin(a), 0))
        pts = [CRYSTAL + d * 0.033 + Vector((0, 0, 0.034)), CRYSTAL + d * 0.038 + Vector((0, 0, 0.016)),
               CRYSTAL + d * 0.035 + Vector((0, 0, -0.002))]
        tube(p, "brass", pts, [0.0060, 0.0050, 0.0035], seg=5)
    comp(p, "lantern", "smooth", 45)


def build_crystal():
    p = Part("flame")
    gem(p, "glow_moth_aether", r=0.029, up=0.030, down=0.066, seg=6, mid=0.022, loc=tuple(CRYSTAL))
    gem(p, "glow_moth_aether", r=0.010, up=0.010, down=0.026, seg=5, mid=0.006,
        loc=tuple(CRYSTAL + Vector((0.020, -0.012, -0.012))), rot=(14, 32, 0))
    comp(p, "flame", "flat", solid=False)


GEAR = Vector((0.0, 0.020, TH_RZ + 0.018))  # ring_A pivot (lantern local)


def build_gear():
    p = Part("lantern_gearpost")
    p.cyl("brass_dark", r=0.011, h=0.020, seg=10, loc=tuple(GEAR - Vector((0, 0, 0.010))))
    comp(p, "lantern", "smooth", 40)
    p = Part("ring_A")
    sgear(p, "brass", r=0.044, teeth=10, thick=0.008, loc=tuple(GEAR))
    wh.revolve(p, "brass_dark", [(0.0, 0.003), (0.020, 0.003), (0.023, 0.007), (0.020, 0.011), (0.0, 0.012)],
               C10, loc=tuple(GEAR))
    for k in range(4):
        a = math.radians(45 + 90 * k)
        p.box("brass_dark", size=(0.020, 0.006, 0.0095), loc=tuple(GEAR + Vector((math.cos(a), math.sin(a), 0)) * 0.026),
              rot=(0, 0, math.degrees(a)))
    p.sphere("glow_moth_aether", r=0.0065, seg=6, rings=4, loc=tuple(GEAR + Vector((0, 0, 0.012))))
    comp(p, "ring_A", "smooth", 40)


# =========================================================================================
# HEAD (+ clock-hand antennae)
# =========================================================================================
NECK = Vector((0.0, -0.104, -0.004))
HEAD_C = Vector((0.0, -0.168, -0.014))
EYE_C = [Vector((s * 0.054, -0.186, -0.004)) for s in (1, -1)]
DIAL_N = Vector((0.0, -0.80, 0.60)).normalized()
DIAL_C = HEAD_C + Vector((0.0, -0.046, 0.040))
DIAL_R = 0.026


def build_head():
    p = Part("head")
    p.sphere("brass", r=1.0, seg=14, rings=9, loc=tuple(HEAD_C), scale=(0.064, 0.066, 0.060))
    # mouth parts: little coiled brass proboscis under the face
    pts = []
    for i in range(9):
        t = i / 8
        a = 2.6 * math.pi * t
        rr = 0.016 * (1 - 0.65 * t)
        pts.append(HEAD_C + Vector((0, -0.040 - rr * math.sin(a) * 0.4, -0.050 + rr * math.cos(a) - 0.014 * t)))
    tube(p, "brass_dark", pts, [0.0045 - 0.0025 * i / 8 for i in range(9)], seg=5, up=(1, 0, 0))
    comp(p, "head", "smooth", 50)
    # compound eyes with a thin bezel and two glints each
    p = Part("head_eyes")
    for c in EYE_C:
        s = 1 if c.x > 0 else -1
        n = Vector((s * 0.80, -0.55, 0.22)).normalized()
        p.sphere("moth_eye", r=0.047, seg=12, rings=7, loc=tuple(c), rot=sh.orient(n), scale=(1, 1, 0.92))
        p.torus("brass", R=0.041, r=0.0055, seg=14, seg2=4, loc=tuple(c + n * 0.016), rot=sh.orient(n))
        # glints seated on the eye surface (same light direction on both eyes)
        g = Vector((0.20, -0.62, 0.58)).normalized()
        g = (n * 0.45 + g).normalized()
        p.sphere("white", r=0.0085, seg=6, rings=3, loc=tuple(c + g * 0.0405), scale=(1, 1, 0.6),
                 rot=sh.orient(g))
        g2 = (n * 0.8 + Vector((0.0, -0.3, -0.35))).normalized()
        p.sphere("white", r=0.0042, seg=5, rings=3, loc=tuple(c + g2 * 0.043), scale=(1, 1, 0.6), rot=sh.orient(g2))
    comp(p, "head", "smooth", 60)
    # enamel clock dial on the forehead
    M = sh.frame(DIAL_N, up=(0, 0, 1), origin=DIAL_C)
    p = Part("head_dial")
    sh.revolve(p, "brass", [(DIAL_R - 0.002, -0.010), (DIAL_R + 0.005, -0.004), (DIAL_R + 0.004, 0.005),
                            (DIAL_R - 0.002, 0.003)], seg=16, closed=True, M=M)
    sh.revolve(p, "brass", [(0.0, -0.016), (DIAL_R, -0.016), (DIAL_R, -0.006)], seg=16, M=M)
    comp(p, "head", "smooth", 50)
    p = Part("head_dialface")
    sh.disc(p, "white", DIAL_R - 0.0015, z=0.0015, seg=16, M=M)
    for k in range(12):
        ph = math.radians(30 * k)
        L = 0.0060 if k % 3 == 0 else 0.0035
        rc = DIAL_R - 0.0045 - L / 2
        sh.flat_quad(p, "moth_hand", math.sin(ph) * rc, math.cos(ph) * rc, 0.0026 if k % 3 == 0 else 0.0016, L,
                     ang=-ph, z=0.0022, M=M)
    comp(p, "head", "smooth", 180, sheet=DIAL_N)


HANDS = {   # name: (side, angle from dial-up deg, length, lift above dial)
    "antenna_L": (1, 36.0, 0.255, 0.0035),
    "antenna_R": (-1, 40.0, 0.205, 0.0068),
}


def hand_outline(kind, L):
    """Flat clock hand outline [(x, y)], y along the hand from the pivot (0, 0)."""
    if kind == "minute":       # slender, small spade near the tip, round counterweight tail
        right = [(0.0030, 0.010), (0.0026, 0.40 * L), (0.0021, 0.76 * L), (0.0058, 0.80 * L), (0.0088, 0.835 * L),
                 (0.0072, 0.88 * L), (0.0030, 0.94 * L), (0.0, L)]
    else:                      # hour hand: broader, big heart/spade
        right = [(0.0040, 0.010), (0.0034, 0.45 * L), (0.0030, 0.66 * L), (0.0085, 0.71 * L), (0.0135, 0.77 * L),
                 (0.0120, 0.835 * L), (0.0050, 0.90 * L), (0.0, L)]
    left = [(-x, y) for (x, y) in reversed(right[:-1])]
    return right + left


def build_hand(name):
    s, ang, L, lift = HANDS[name]
    u = Vector((0, 0, 1)) - DIAL_N * DIAL_N.z
    u.normalize()
    x = Vector((1, 0, 0))
    a = math.radians(ang)
    d = u * math.cos(a) + x * (s * math.sin(a))          # hand direction (in the dial plane)
    w = DIAL_N.cross(d).normalized()                     # across the hand
    base = DIAL_C + DIAL_N * lift
    p = Part(name)
    outline = hand_outline("minute" if s > 0 else "hour", L)
    vs_top, vs_bot = [], []
    th = 0.0032
    for (ox, oy) in outline:
        c = base + w * ox + d * oy
        vs_top.append(p.bm.verts.new(c + DIAL_N * th / 2))
        vs_bot.append(p.bm.verts.new(c - DIAL_N * th / 2))
    n = len(outline)
    p.bm.faces.new(vs_top)
    p.bm.faces.new(list(reversed(vs_bot)))
    for i in range(n):
        j = (i + 1) % n
        p.bm.faces.new((vs_bot[i], vs_bot[j], vs_top[j], vs_top[i]))
    p._assign(vs_top + vs_bot, "moth_hand")
    # hub boss + counterweight ring on the short tail, Breguet ring on the minute hand
    Mh = sh.frame(DIAL_N, up=tuple(d), origin=base)
    sh.revolve(p, "moth_hand", [(0.0, -th / 2), (0.0065, -th / 2), (0.0065, th / 2 + 0.002), (0.0, th / 2 + 0.003)],
               seg=12, M=Mh, cap0=True)
    sh.revolve(p, "moth_hand", [(0.0058, -th / 2), (0.0090, -th / 2), (0.0090, th / 2), (0.0058, th / 2)],
               seg=12, closed=True, M=Mh @ Matrix.Translation((0, -0.017, 0)))
    tail = [Vector((0, -0.004, 0)), Vector((0, -0.0115, 0))]
    p.bm.verts.ensure_lookup_table()
    tube(p, "moth_hand", [Mh @ t for t in tail], 0.0022, seg=5, up=tuple(DIAL_N))
    if s > 0:
        sh.revolve(p, "moth_hand", [(0.0050, -th / 2), (0.0078, -th / 2), (0.0078, th / 2), (0.0050, th / 2)],
                   seg=12, closed=True, M=Mh @ Matrix.Translation((0, 0.50 * L, 0)))
    comp(p, name, "smooth", 35)
    return base


# =========================================================================================
# ABDOMEN (tail_1 -> tail_2)
# =========================================================================================
TAIL1 = Vector((0.0, 0.098, -0.022))
DIR1 = Vector((0.0, math.cos(math.radians(24)), -math.sin(math.radians(24))))
L1 = 0.200
TAIL2 = TAIL1 + DIR1 * L1
DIR2 = Vector((0.0, math.cos(math.radians(36)), -math.sin(math.radians(36))))
SEG1 = ((0.000, 0.070, 0.078), (0.064, 0.068, 0.076), (0.128, 0.064, 0.070))    # (start, length, radius)
SEG2 = ((0.000, 0.058, 0.064), (0.054, 0.054, 0.055), (0.104, 0.048, 0.045))


def _seg_profile(L, R):
    return [(0.80 * R, 0.0), (0.95 * R, 0.14 * L), (1.0 * R, 0.48 * L), (0.97 * R, 0.80 * L),
            (1.04 * R, 0.88 * L), (0.96 * R, 1.0 * L), (0.70 * R, 1.0 * L)]


def build_abdomen(name, origin, d, segs, tip=False):
    q = Vector((0, 0, 1)).rotation_difference(d)
    rot = tuple(math.degrees(a) for a in q.to_euler("XYZ"))
    p = Part(name)
    for (s0, L, R) in segs:
        prof = _seg_profile(L, R)
        start = len(p.bm.faces)
        wh.revolve(p, "brass", [(r, z + s0) for (r, z) in prof], wh.circle(12), caps=(True, True), loc=tuple(origin),
                   rot=rot, scale=(1.0, 0.90, 1.0))
        wh.paint_faces(p, "brass_dark", start, lambda c, o=origin, s0=s0, L=L: (c - o).dot(d) > s0 + 0.83 * L)
    if tip:
        s0 = segs[-1][0] + segs[-1][1]
        R = segs[-1][2] * 0.72
        wh.revolve(p, "brass_dark", [(R, s0 - 0.004), (R * 0.85, s0 + 0.016), (R * 0.55, s0 + 0.032),
                                     (R * 0.25, s0 + 0.044), (0.0, s0 + 0.050)], C10, loc=tuple(origin), rot=rot,
                   scale=(1.0, 0.90, 1.0))
        p.sphere("glow_moth_aether", r=0.0085, seg=8, rings=5, loc=tuple(origin + d * (s0 + 0.054)))
    comp(p, name, "smooth", 38)


# =========================================================================================
# WINGS
# =========================================================================================
WING_PIV = Vector((0.086, -0.012, 0.060))      # +X side (lantern local)

FORE = dict(
    th=[-12.0, 0.0, 11.5, 23.0, 34.5, 46.0, 58.0],
    R=[(-12, 0.585), (-7, 0.622), (0, 0.620), (12, 0.590), (25, 0.525), (38, 0.430), (48, 0.335), (58, 0.240)],
    rings=[0.15, 0.40, 0.63, 0.84, 1.0], stagger=0.035, scallop=0.030, dihedral=11.0,
    off=Vector((0.0, 0.0, 0.010)), spar=True,
    colors=["vvvvvv",          # ring 0 (root)       sector 0 = costa side
            "ccvvcc",          # ring 1
            "cvaavc",          # ring 2   amber eyespot ringed in violet
            "aacvcv"],         # ring 3 (outer margin, amber wing tip)
)
HIND = dict(
    th=[8.0, 24.0, 40.0, 56.0, 69.0, 82.0],
    R=[(8, 0.300), (22, 0.405), (40, 0.448), (56, 0.400), (69, 0.255), (82, 0.115)],
    rings=[0.20, 0.50, 0.77, 1.0], stagger=0.035, scallop=0.045, dihedral=5.0,
    off=Vector((0.0, 0.012, -0.006)), spar=False,
    colors=["vvvvv",
            "caacv",
            "vcvcc"],
)


def _interp(ctrl, x):
    """Catmull-Rom through [(x, y)] (clamped ends)."""
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


def ring_r(W, i, k, th):
    """Radius of ring k of sector i at angle th (deg).  Outer ring = scalloped edge."""
    R = _interp(W["R"], th)
    n = len(W["rings"])
    if k == n - 1:
        u = (th - W["th"][i]) / (W["th"][i + 1] - W["th"][i])
        return R * (1.0 + W["scallop"] * math.sin(math.pi * max(0.0, min(1.0, u))))
    f = W["rings"][k]
    if 0 < k < n - 1:
        f += W["stagger"] * (1 if (i + k) % 2 else -1)
    return R * f


def P(th, r, z=0.0):
    a = math.radians(th)
    return Vector((r * math.cos(a), r * math.sin(a), z))


LEAD4 = [(0.0046, 0.0), (0.0, 0.0058), (-0.0046, 0.0), (0.0, -0.0058)]
LEAD6 = [(0.0064, 0.0050), (0.0, 0.0090), (-0.0064, 0.0050), (-0.0064, -0.0050), (0.0, -0.0090), (0.0064, -0.0050)]


def wing_parts(W, tag):
    """Lead cames, brass spar + hinge plate, glass panes of one wing (wing-local, +X side, flat)."""
    th, n_s, n_r = W["th"], len(W["th"]) - 1, len(W["rings"])
    lead, brass, panes = Part(f"{tag}_lead"), Part(f"{tag}_brass"), Part(f"{tag}_panes")
    shade = []
    # ---- panes ------------------------------------------------------------------------
    for i in range(n_s):
        for k in range(n_r - 1):
            col = W["colors"][k][i]
            mat = PANES[col][0]
            nt = 4 if k == n_r - 2 else 3
            nr = 2
            grid = []
            for a in range(nt + 1):
                t = th[i] + (th[i + 1] - th[i]) * a / nt
                r0, r1 = ring_r(W, i, k, t), ring_r(W, i, k + 1, t)
                grid.append([panes.bm.verts.new(P(t, r0 + (r1 - r0) * b / nr)) for b in range(nr + 1)])
            vs = [v for row in grid for v in row]
            # deterministic per-pane density variation (antique glass)
            val = 0.80 + 0.20 * (0.5 + 0.5 * noise.noise(Vector((i * 1.7 + 0.3, k * 2.3 + 0.1, len(tag) * 0.9))))
            for a in range(nt):
                for b in range(nr):
                    panes.bm.faces.new((grid[a][b], grid[a + 1][b], grid[a + 1][b + 1], grid[a][b + 1]))
                    shade.append(val)
            panes._assign(vs, mat)
    # ---- interior radial cames ------------------------------------------------------------
    for i in range(1, n_s):
        r0 = min(ring_r(W, i - 1, 0, th[i]), ring_r(W, i, 0, th[i]))
        r1 = _interp(W["R"], th[i])
        wh.sweep(lead, "moth_lead", [P(th[i], r0), P(th[i], r1)], [LEAD4, LEAD4])
    # ---- ring cames (arcs per sector) -------------------------------------------------------
    for i in range(n_s):
        for k in range(n_r - 1):
            pts = [P(t, ring_r(W, i, k, t)) for t in (th[i] + (th[i + 1] - th[i]) * a / 2 for a in range(3))]
            # extend slightly past the radial lines so joints close
            e0 = (pts[0] - pts[1]).normalized() * 0.003
            e1 = (pts[-1] - pts[-2]).normalized() * 0.003
            pts[0] = pts[0] + e0
            pts[-1] = pts[-1] + e1
            wh.sweep(lead, "moth_lead", pts, [LEAD4] * 3)
    # ---- outer border (scalloped edge) + inner margin ------------------------------------
    edge = []
    for i in range(n_s):
        for a in range(4):
            t = th[i] + (th[i + 1] - th[i]) * a / 4
            edge.append(P(t, ring_r(W, i, n_r - 1, t)))
    edge.append(P(th[-1], ring_r(W, n_s - 1, n_r - 1, th[-1])))
    wh.sweep(lead, "moth_lead", edge, [LEAD6] * len(edge))
    r_end = edge[-1].length
    im = [P(th[-1], r_end + 0.002), P(th[-1], r_end * 0.55), P(th[-1], 0.03)]
    wh.sweep(lead, "moth_lead", im, [LEAD6] * 3)
    # ---- brass costa spar (leading edge) + hinge plate --------------------------------------
    r_apex = _interp(W["R"], th[0])
    if W["spar"]:
        spar = [P(th[0], 0.02), P(th[0], r_apex * 0.40), P(th[0], r_apex + 0.010)]
        wh.sweep(brass, "brass", spar, [wh.round_section(r, 6) for r in (0.0105, 0.0085, 0.0052)])
        brass.sphere("brass", r=0.0085, seg=6, rings=4, loc=tuple(P(th[0], r_apex + 0.010)))
    else:
        wh.sweep(lead, "moth_lead", [P(th[0], 0.03), P(th[0], r_apex + 0.002)], [LEAD6] * 2)
    plate = [Vector((0, 0, 0))]
    for a in range(7):
        t = th[0] + (th[-1] - th[0]) * a / 6
        i = min(int((t - th[0]) / (th[-1] - th[0]) * n_s), n_s - 1)
        plate.append(P(t, ring_r(W, i, 0, t) + 0.006))
    prism(brass, "brass", [(q.x, q.y) for q in plate], 0.010, axis="z")
    for a in (0.25, 0.5, 0.75):                         # rivets on the plate
        t = th[0] + (th[-1] - th[0]) * a
        brass.sphere("brass_dark", r=0.0050, seg=5, rings=3, loc=tuple(P(t, 0.045, 0.005)))
    return lead, brass, panes, shade


def build_wing(name, s):
    """Both wings of one side as components of node `name` (pivot WING_PIV mirrored)."""
    piv = Vector((s * WING_PIV.x, WING_PIV.y, WING_PIV.z))
    for W, tag in ((FORE, "fore"), (HIND, "hind")):
        lead, brass, panes, shade = wing_parts(W, f"{name}_{tag}")
        R = Matrix.Translation(W["off"]) @ Matrix.Rotation(math.radians(-W["dihedral"]), 4, "Y")
        for part in (lead, brass, panes):
            sh.xform(part, R)
            if s < 0:
                wh.mirror_x(part)
        M = T_L @ Matrix.Translation(piv)
        comp(lead, name, "smooth", 55, M=M)
        comp(brass, name, "smooth", 40, M=M)
        o = comp(panes, name, "smooth", 180, M=M, solid=False, sheet=(0, 0, 1))
        PANE_OBJS.append(o)
        PANE_SHADE[o.name] = shade
    # hinge knuckle (part of the wing) + boss on the thorax (lantern)
    p = Part(f"{name}_hinge")
    p.cyl("brass_dark", r=0.0150, h=0.064, seg=10, loc=(0, 0.010, 0.004), rot=(90, 0, 0))
    for y in (-0.024, 0.044):
        p.cyl("brass", r=0.0175, h=0.010, seg=10, loc=(0, y, 0.004), rot=(90, 0, 0))
    comp(p, name, "smooth", 40, M=T_L @ Matrix.Translation(piv))
    p = Part(f"lantern_boss_{name}")
    p.cyl("brass_dark", r=0.014, h=0.040, seg=10, loc=(s * (WING_PIV.x - 0.026), WING_PIV.y + 0.010, WING_PIV.z - 0.004),
          rot=(0, 90, 0))
    comp(p, "lantern", "smooth", 40)
    return piv


# =========================================================================================
# ASSEMBLY
# =========================================================================================
build_thorax()
build_collar()
build_legs()
build_setting()
build_crystal()
build_gear()
build_head()
hand_base = {n: build_hand(n) for n in HANDS}
build_abdomen("tail_1", TAIL1, DIR1, SEG1)
build_abdomen("tail_2", TAIL2, DIR2, SEG2, tip=True)
piv_L = build_wing("wing_L", 1)
piv_R = build_wing("wing_R", -1)
bpy.context.view_layer.update()

# ---- vertex colours ----------------------------------------------------------------------------
hp.bake_vertex_ao(objs=SOLID + COMPS["flame"], occluders=SOLID, ground=None, samples=40, distance=0.08,
                  strength=0.75, floor=0.45)
for o in PANE_OBJS:                 # panes: per-pane glass density (glow faces otherwise stay white)
    me = o.data
    attr = me.color_attributes.new(hp.AO_ATTR, "BYTE_COLOR", "CORNER")
    cols = np.ones((len(me.loops), 4), dtype=np.float32)
    for poly, val in zip(me.polygons, PANE_SHADE[o.name]):
        cols[poly.loop_start:poly.loop_start + poly.loop_total, :3] = val
    attr.data.foreach_set("color", cols.ravel())
    me.color_attributes.active_color = attr
    me.color_attributes.render_color_index = me.color_attributes.find(hp.AO_ATTR)

# ---- join into named nodes ---------------------------------------------------------------------
W0 = Vector((0, 0, LZ))
PIVOTS = {
    "lantern": (W0, None), "flame": (W0 + CRYSTAL, "lantern"), "ring_A": (W0 + GEAR, "lantern"),
    "wing_L": (W0 + piv_L, "lantern"), "wing_R": (W0 + piv_R, "lantern"), "head": (W0 + NECK, "lantern"),
    "antenna_L": (W0 + hand_base["antenna_L"], "head"), "antenna_R": (W0 + hand_base["antenna_R"], "head"),
    "tail_1": (W0 + TAIL1, "lantern"), "tail_2": (W0 + TAIL2, "tail_1"),
}
root = empty("root")
NODES = {}
for name, (pv, par) in PIVOTS.items():
    o = sh.join(COMPS[name], name, pv)
    NODES[name] = o
for name, (pv, par) in PIVOTS.items():
    o = NODES[name]
    if par is None:
        o.parent = root
        o.location = pv
    else:
        o.parent = NODES[par]
        o.location = pv - PIVOTS[par][0]
bpy.context.view_layer.update()

total = 0
for name, o in NODES.items():
    t = sh.tris(o)
    total += t
    print(f"[tris] {name:10s} {t}")
print(f"[tris] TOTAL {total}")
if total > 10000:
    print(f"[WARN] prism_moth: {total} tris exceeds the weak-enemy budget 10000")
print("[mats]", sorted({m.name for o in NODES.values() for m in o.data.materials}))


# =========================================================================================
# CHECKS (mimic rig.ts: rotations in model axes; all rest rotations are identity)
# =========================================================================================
def set_pose(wing=0.0, tail=(0.0, 0.0), ant=(0.0, 0.0)):
    NODES["wing_L"].rotation_euler = (0, 0, wing)
    NODES["wing_R"].rotation_euler = (0, 0, -wing)
    for n, k in (("tail_1", 1.0), ("tail_2", 1.4)):
        NODES[n].rotation_euler = (tail[0] * k, 0, tail[1] * k)
    for n in ("antenna_L", "antenna_R"):
        NODES[n].rotation_euler = (ant[0], 0, ant[1])
    bpy.context.view_layer.update()


def check_motion():
    worst = {}
    pairs = (("wing_L", "head"), ("wing_L", "tail_1"), ("wing_L", "tail_2"), ("wing_L", "wing_R"),
             ("wing_L", "antenna_L"), ("wing_L", "ring_A"), ("tail_2", "wing_R"))
    for w in (-0.6, -0.3, 0.0, 0.3, 0.6):
        for tl in ((0.0, 0.0), (0.07, 0.2), (-0.07, -0.2)):
            set_pose(wing=w, tail=tl, ant=(0.12, 0.1))
            for a, b in pairs:
                d, ov = wh.clearance(NODES[a], NODES[b])
                cur = worst.get((a, b), (9, 0))
                worst[(a, b)] = (min(cur[0], d), max(cur[1], ov))
    set_pose()
    for (a, b), (d, ov) in worst.items():
        flag = "  <-- OVERLAP" if ov else ("  <-- tight" if d < 0.006 else "")
        print(f"[motion] {a + '-' + b:22s} min clearance {d * 1000:6.1f} mm  overlaps {ov}{flag}")


check_motion()
hp.export_glb_hp("prism_moth")

def preview_materials():
    """Preview only (after export): alpha-blend the panes like the game (EEVEE default is dithered)."""
    for n, _h in PANES.values():
        try:
            bpy.data.materials[n].surface_render_method = "BLENDED"
        except Exception:
            pass


if "--quick" in ARGS:
    preview_materials()
    hp.render_hp("prism_moth", azimuth=35, elevation=22)
    hp.render_hp("prism_moth_face", target=((0, -0.17, LZ + 0.02), 0.16), azimuth=20, elevation=14)
elif "--no-preview" not in ARGS:
    preview_materials()
    wh.render_aces("prism_moth_aces", ((0, 0.05, LZ), 0.75), azimuth=30, elevation=30)
    hp.render_views("prism_moth", views=(("", 35, 22), ("_front", 0, 8), ("_side", 90, 6), ("_back", 200, 24)))
    hp.render_hp("prism_moth_game", azimuth=25, elevation=30, dist_k=6.5)
    hp.render_hp("prism_moth_top", azimuth=15, elevation=70)
    if "--extra" in ARGS:
        hp.render_hp("prism_moth_face", target=((0, -0.17, LZ + 0.02), 0.16), azimuth=20, elevation=14)
        set_pose(wing=0.6, tail=(0.07, 0.25), ant=(0.12, 0.1))
        hp.render_hp("prism_moth_flap_a", azimuth=35, elevation=30)
        set_pose(wing=-0.6, tail=(-0.07, -0.25), ant=(-0.12, -0.1))
        hp.render_hp("prism_moth_flap_b", azimuth=35, elevation=30)
        set_pose()
print(f"[prism_moth] done, {total} tris")
