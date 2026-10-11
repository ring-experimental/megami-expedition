"""Lamp Wisp (hi-poly) — floating magical enemy. Exports public/models/wisp.glb.

    root (ground, 0,0,0)
    └─ lantern        pivot at lantern centre, z = 1.3   (Victorian hex lantern: base, glass cage,
       │              pagoda roof with crested ribs, vent crown, hanging ring, light-drop finial;
       │              the front pane is a hinged door left ajar so the flame can peek out)
       ├─ flame       glow teardrop with twisting tongues + white-hot core "face" (eyes, little o
       │              mouth); origin = lantern centre (flicker scale pivot)
       ├─ ring_A      horizontal toothed ring around the base with 3 bezel rune stones (spins Z)
       ├─ ring_B_tilt empty, 60 deg about X
       │  └─ ring_B   big armillary band with rune cartouches + threaded glow beads (rest identity)
       ├─ wing_L      spoked gear hub + four feathered brass/copper blades, pivot at the +X boss
       └─ wing_R      mirror, pivot at the -X boss

Game motion (src/anim/rig.ts): rotations are applied in MODEL axes, so ring_B precesses about the
lantern's vertical axis and sweeps the sphere band |z| <= R_B*sin(60) -> the wings are kept inside
ring_B's sphere; ring_A sweeps its own plane below the wings and the door.  check_motion() verifies
the clearances (printed as [motion] lines).

Usage:  blender -b --factory-startup -P tools/blender/model_wisp.py [-- full|quick|anim|none]
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Quaternion, Vector  # noqa: E402

from common import Part, empty, get_mat, reset_scene  # noqa: E402
from char_helpers import prism, sgear, tri_report  # noqa: E402
import hp_helpers as hp  # noqa: E402
import hp_wisp_helpers as wh  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = ARGS[0] if ARGS else "full"

reset_scene()
# materials --------------------------------------------------------------------------------
get_mat("glass", alpha=0.35)                     # game: name 'glass' -> transparent, opacity 0.35
get_mat("glow_white")                            # white-hot flame core
get_mat("glow_amber")                            # rune stones, light drop, gem hubs
get_mat("glow_wisp_fire", hex="#ff7a2a", emission="#ff6a1c", strength=2.4)   # flame body (orange under ACES)
get_mat("wisp_eye", hex="#1b0f08", metallic=0.0, roughness=0.25)

root = empty("root")

LZ = 1.3                    # lantern centre height
RC = 0.150                  # cage post radius (hex corner radius)
AP = RC * math.cos(math.radians(30))            # pane apothem
HEX = wh.ngon_outline(6, fillet=0.07, k=2)      # corners at 0, 60, ... deg -> flat front pane (-Y)
C16, C12, C10 = wh.circle(16), wh.circle(12), wh.circle(10)
C8 = wh.circle(8, math.pi / 8)
WZ = 0.030                  # wing attach height (lantern local)
WX = 0.164                  # wing pivot |x| (outer face of the boss)
ZA = -0.228                 # ring_A height (lantern local) - below the open door
RA = 0.300                  # ring_A mid radius
RB = 0.520                  # ring_B radius
TILT_B = 60.0
DOOR_PANE = 4               # pane index facing -Y (30 + 60*4 = 270 deg)
DOOR_OPEN = 112.0           # door opening angle (deg)


def fp(pts, r=0.003, segs=1):
    return wh.fillet_profile(pts, r, segs)


def sub(name, fill, shade="wn", angle=50.0):
    """Build one sub-mesh of the lantern (joined later) with its own shading treatment."""
    p = Part(name)
    fill(p)
    o = p.build(root, loc=(0, 0, LZ))
    if shade == "wn":
        wh.wn_obj(o, angle)
    elif shade == "smooth":
        hp.smooth_obj(o, angle)
    elif shade == "flat":
        hp.flat_obj(o)
    print(f"[sub] {name:16s} {hp.obj_tris(o)}")
    return o


def pane_matrix(k, out=0.0):
    """Frame of pane k: x along the pane (CCW), y outward normal, z up; origin on the pane centre line."""
    a = math.radians(30 + 60 * k)
    return Matrix.Translation((math.cos(a) * (AP + out), math.sin(a) * (AP + out), 0)) @ \
        Matrix.Rotation(a - math.pi / 2, 4, "Z")


def door_matrix():
    """Door frame (same axes as pane_matrix of the front pane: x toward -X when closed, y outward)
    rotated about the hinge on the front-left (-X) corner post.  The door body lies on local -x."""
    a = math.radians(30 + 60 * DOOR_PANE)
    hinge_ang = a - math.radians(30)                 # corner at 240 deg
    hinge = Vector((math.cos(hinge_ang) * (RC + 0.004), math.sin(hinge_ang) * (RC + 0.004), 0))
    return Matrix.Translation(hinge) @ Matrix.Rotation(a - math.pi / 2 - math.radians(DOOR_OPEN), 4, "Z")


def _box_m(p, mat, M, size, loc):
    """Box in a local frame M (no extra rotation)."""
    T = M @ Matrix.Translation(loc)
    l, r, _ = T.decompose()
    p.box(mat, size=size, loc=tuple(l), rot=tuple(math.degrees(v) for v in r.to_euler()))


def _prism_m(p, mat, M, outline, thick, y=0.0):
    """Flat outline [(x, z)] in frame M, extruded along the frame's y (centred on y)."""
    T = M @ Matrix.Translation((0, y, 0))
    l, r, _ = T.decompose()
    prism(p, mat, outline, thick, loc=tuple(l), rot=tuple(math.degrees(v) for v in r.to_euler()), axis="y")


# =========================================================================================
# LANTERN
# =========================================================================================

def f_base(p):
    prof = fp([(0.0, -0.300), (0.150, -0.300, 0.0), (0.172, -0.291), (0.181, -0.278, 0.002),
               (0.181, -0.254, 0.002), (0.167, -0.249, 0.002), (0.160, -0.236, 0.0),
               (0.166, -0.224, 0.002), (0.186, -0.219, 0.002), (0.188, -0.200, 0.002),
               (0.172, -0.193, 0.002), (0.140, -0.192, 0.0), (0.0, -0.192)])
    wh.revolve(p, "brass", prof, HEX)
    wh.paint_faces(p, "brass_dark", 0, lambda c: -0.2785 < c.z < -0.2535)     # rune band


def f_bowl(p):
    prof = [(0.0, -0.296), (0.132, -0.296), (0.128, -0.306), (0.112, -0.322), (0.088, -0.338),
            (0.062, -0.350), (0.040, -0.359), (0.025, -0.368), (0.019, -0.380), (0.028, -0.388),
            (0.033, -0.398), (0.027, -0.409), (0.013, -0.414), (0.011, -0.420), (0.0, -0.420)]
    wh.revolve(p, "brass", prof, wh.fluted(24, 0.07))
    for k in range(3):                       # three little claws holding the light drop
        a = math.radians(90 + 120 * k)
        d = Vector((math.cos(a), math.sin(a), 0))
        pts = [d * 0.010 + Vector((0, 0, -0.414)), d * 0.019 + Vector((0, 0, -0.424)),
               d * 0.023 + Vector((0, 0, -0.437)), d * 0.019 + Vector((0, 0, -0.447))]
        wh.sweep(p, "brass", pts, [wh.round_section(r, 4) for r in (0.0035, 0.0035, 0.003, 0.0022)])


def f_drop(p):
    prof = [(0.0, -0.413), (0.010, -0.418), (0.017, -0.428), (0.020, -0.440), (0.017, -0.453),
            (0.010, -0.466), (0.004, -0.478), (0.0, -0.488)]
    wh.revolve(p, "glow_amber", prof, C10)


def f_posts(p):
    prof = [(0.0, -0.193), (0.0150, -0.193), (0.0150, -0.182), (0.0105, -0.176),
            (0.0105, 0.152), (0.0150, 0.159), (0.0150, 0.168), (0.0, 0.168)]
    for k in range(6):
        a = math.radians(60 * k)
        wh.revolve(p, "brass_dark", prof, C8, loc=(RC * math.cos(a), RC * math.sin(a), 0))


ARCH_W = RC + 0.002
ARCH_SPRING, ARCH_APEX, ARCH_TOP = 0.088, 0.140, 0.168


def _arch_pts(w, spring, apex, n=9):
    pts = []
    for i in range(n):
        u = -w / 2 + w * i / (n - 1)
        x = abs(u) / (w / 2)
        pts.append((u, spring + (apex - spring) * (1 - x) ** 0.62))
    return pts


def _pane_dress(p, M):
    """Gothic arch spandrel + rim + lower kick rail on a pane whose frame is M (y = outward)."""
    arc = _arch_pts(ARCH_W, ARCH_SPRING, ARCH_APEX)
    _prism_m(p, "brass", M, arc + [(ARCH_W / 2, ARCH_TOP), (-ARCH_W / 2, ARCH_TOP)], 0.004, y=0.003)
    rim = [M @ Vector((u * 0.97, 0.005, v - 0.002)) for (u, v) in arc]
    wh.sweep(p, "brass", rim, [wh.round_section(0.0034, 4)] * len(rim), up=tuple(M.to_3x3() @ Vector((0, 0, 1))))
    _box_m(p, "brass_dark", M, (ARCH_W - 0.012, 0.006, 0.010), (0, 0.002, -0.150))


def f_arches(p):
    for k in range(6):
        if k != DOOR_PANE:
            _pane_dress(p, pane_matrix(k))


def f_door(p):
    """Front door left ajar: frame stiles, dressed like a pane, hinge barrels and a knob."""
    D = door_matrix()
    w = RC - 0.002
    C = D @ Matrix.Translation((-(w / 2 + 0.004), 0, 0))   # door centre frame
    _pane_dress(p, C)
    for x in (-w / 2 + 0.004, w / 2 - 0.004):             # stiles
        _box_m(p, "brass_dark", C, (0.008, 0.007, 0.356), (x, 0.0, -0.012))
    _box_m(p, "brass_dark", C, (w, 0.007, 0.010), (0, 0.0, -0.187))         # bottom rail
    for z in (-0.130, 0.110):                                             # hinge barrels
        l = D @ Vector((0.0, 0.0, z))
        p.cyl("brass", r=0.0065, h=0.030, seg=8, loc=tuple(l))
    kn = C @ Vector((-(w / 2 - 0.016), 0.009, -0.020))                    # knob on the free edge
    p.sphere("brass", r=0.0075, seg=8, rings=5, loc=tuple(kn))


def f_glass(p):
    for k in range(6):
        if k == DOOR_PANE:
            continue
        _box_m(p, "glass", pane_matrix(k), (RC - 0.004, 0.003, 0.360), (0, -0.002, -0.012))
    D = door_matrix()
    w = RC - 0.002
    _box_m(p, "glass", D, (w - 0.010, 0.003, 0.350), (-(w / 2 + 0.004), 0.0, -0.012))


def f_burner(p):
    prof = [(0.0, -0.193), (0.052, -0.193), (0.054, -0.186), (0.044, -0.176), (0.032, -0.166),
            (0.029, -0.150), (0.036, -0.146), (0.036, -0.139), (0.0, -0.139)]
    wh.revolve(p, "gunmetal", prof, C12)
    p.cyl("brass_dark", r=0.0075, h=0.018, seg=8, loc=(0, 0, -0.131))


def f_cap(p):
    prof = fp([(0.0, 0.166), (0.150, 0.166, 0.0), (0.176, 0.170, 0.002), (0.181, 0.184, 0.002),
               (0.204, 0.195, 0.004), (0.224, 0.202, 0.002), (0.226, 0.211, 0.002), (0.214, 0.216, 0.002),
               (0.180, 0.228, 0.0), (0.146, 0.246, 0.0), (0.114, 0.270, 0.0), (0.094, 0.292, 0.0),
               (0.088, 0.302, 0.002), (0.0, 0.302)])
    wh.revolve(p, "brass", prof, HEX)
    wh.paint_faces(p, "copper", 0, lambda c: 0.2175 < c.z < 0.2985)          # copper roof panels


def f_ribs(p):
    """Crested ribs along the six roof corners, curling up at the eaves into a bead."""
    path_rz = [(0.249, 0.240), (0.247, 0.226), (0.234, 0.218), (0.212, 0.222), (0.178, 0.235),
               (0.145, 0.253), (0.112, 0.278), (0.092, 0.305)]
    radii = [0.0036, 0.0050, 0.0060, 0.0062, 0.0060, 0.0056, 0.0050, 0.0042]
    for k in range(6):
        a = math.radians(60 * k)
        c, s = math.cos(a) * 0.985, math.sin(a) * 0.985
        pts = [(c * r, s * r, z) for (r, z) in path_rz]
        wh.sweep(p, "brass", pts, [wh.round_section(r, 4, phase=0.0) for r in radii], up=(0, 0, 1))
        p.sphere("brass", r=0.0085, seg=6, rings=4, loc=(c * 0.250, s * 0.250, 0.244))


def f_crown(p):
    wh.revolve(p, "brass", [(0.0, 0.298), (0.087, 0.298), (0.091, 0.305), (0.084, 0.312), (0.0, 0.312)], C16)
    for k in range(6):                       # vent gallery columns around the dark core
        a = math.radians(30 + 60 * k)
        p.cyl("brass", r=0.0072, h=0.036, seg=6, loc=(0.073 * math.cos(a), 0.073 * math.sin(a), 0.329))
    wh.revolve(p, "brass", [(0.0, 0.344), (0.081, 0.344), (0.085, 0.350), (0.078, 0.356), (0.0, 0.356)], C16)
    # vent hood (mushroom dome)
    wh.revolve(p, "brass", [(0.0, 0.355), (0.094, 0.360), (0.099, 0.367), (0.092, 0.376), (0.074, 0.389),
                            (0.052, 0.401), (0.030, 0.409), (0.0, 0.414)], wh.fluted(16, 0.06))
    # finial knob + hanging ring
    wh.revolve(p, "brass_dark", [(0.0, 0.410), (0.017, 0.414), (0.021, 0.424), (0.016, 0.434),
                                 (0.009, 0.440), (0.008, 0.447), (0.0, 0.449)], C10)
    p.torus("brass", R=0.032, r=0.0072, seg=14, seg2=5, loc=(0, 0, 0.484), rot=(90, 0, 0))


def f_vent_core(p):
    p.cyl("gunmetal", r=0.060, h=0.040, seg=12, loc=(0, 0, 0.329))


def f_bosses(p):
    prof = [(0.0, 0.140), (0.027, 0.140), (0.028, 0.149), (0.023, 0.158), (0.015, 0.163), (0.0, 0.164)]
    for s in (1, -1):
        wh.revolve(p, "brass", prof, C12, loc=(0, 0, WZ), rot=(0, 90 * s, 0))


BASE_RUNES = ("algiz", "sowilo", "ingwaz", "tiwaz", "kenaz", "fehu")


def build_runes():
    """Glowing rune glyphs on the dark base band (flat decal quads, built without normal recalc)."""
    p = Part("lantern_runes")
    ap = 0.181 * math.cos(math.radians(30)) + 0.0007
    for k in range(6):
        a = math.radians(30 + 60 * k)
        M = Matrix.Translation((math.cos(a) * ap, math.sin(a) * ap, -0.266)) @ Matrix.Rotation(a - math.pi / 2, 4, "Z")
        wh.rune(p, "glow_amber", M, BASE_RUNES[(k + 2) % 6], h=0.0175, bar=0.0028)
    o = wh.build_raw(p, root, loc=(0, 0, LZ))
    hp.smooth_obj(o, 30)
    print(f"[sub] lantern_runes    {hp.obj_tris(o)}")
    return o


def build_lantern():
    parts = [
        sub("lantern", f_base, "wn", 50),
        sub("lantern_bowl", f_bowl, "smooth", 40),
        sub("lantern_drop", f_drop, "smooth", 80),
        sub("lantern_posts", f_posts, "wn", 50),
        sub("lantern_arches", f_arches, "smooth", 40),
        sub("lantern_door", f_door, "smooth", 40),
        sub("lantern_burner", f_burner, "wn", 50),
        sub("lantern_cap", f_cap, "wn", 50),
        sub("lantern_ribs", f_ribs, "smooth", 50),
        sub("lantern_crown", f_crown, "smooth", 45),
        sub("lantern_vent", f_vent_core, "smooth", 40),
        sub("lantern_bosses", f_bosses, "smooth", 45),
    ]
    parts.append(build_runes())
    glass = sub("lantern_glass", f_glass, "flat")
    return parts, glass


# =========================================================================================
# FLAME
# =========================================================================================

FIRE = dict(z0=-0.112, z1=0.134, rmax=0.088, belly=0.30, tip_pow=1.25)
CORE = dict(z0=-0.098, z1=0.046, rmax=0.056, belly=0.50, tip_pow=1.0)
CORE_Y = -0.036                              # core pushed toward the open door


def _on_core(x, z, embed=0.0):
    """Point on the front surface of the white-hot core at (x, z) (flame local)."""
    r = wh.flame_radius(z, **CORE)
    y = CORE_Y - math.sqrt(max(r * r - x * x, 0.0))
    n = Vector((x, y - CORE_Y, 0.0)).normalized()
    return Vector((x, y, z)) - n * embed, n


def build_flame(parent):
    p = Part("flame")
    # outer living flame: three twisting tongues (a valley faces the door at face height),
    # tip leaning out toward the open door
    wh.flame(p, "glow_wisp_fire", FIRE["z0"], FIRE["z1"], FIRE["rmax"], n_z=11, n_t=20, lobes=3, twist=0.55,
             amp=0.30, bend=(0.004, -0.016), belly=FIRE["belly"], tip_pow=FIRE["tip_pow"], sharp=2.0,
             phase=math.radians(-62))
    # two side flicks breaking the teardrop into a fire silhouette
    for (x, y, z, tilt, h, r, curl) in ((0.036, 0.012, 0.042, 20, 0.092, 0.022, -0.020),
                                        (-0.046, 0.016, -0.008, -42, 0.064, 0.019, 0.016)):
        wh.flame(p, "glow_wisp_fire", 0.0, h, r, n_z=6, n_t=8, lobes=0, amp=0.0, belly=0.35, tip_pow=1.6,
                 bend=(curl, 0.006), loc=(x, y, z), rot=(0, tilt, 0))
    # white-hot core bulging out of the lower front -> bright face patch
    wh.flame(p, "glow_white", CORE["z0"], CORE["z1"], CORE["rmax"], n_z=7, n_t=12, lobes=1, twist=0.0, amp=0.0,
             belly=CORE["belly"], tip_pow=CORE["tip_pow"], loc=(0, CORE_Y, 0))
    # curious face: big oval eyes with a glint, small round "o" mouth (seated on the core surface)
    for s in (1, -1):
        c, n = _on_core(0.025 * s, -0.022, embed=0.003)
        rz = math.degrees(math.atan2(n.x, -n.y))
        p.sphere("wisp_eye", r=1.0, seg=8, rings=6, loc=tuple(c), rot=(0, 0, rz), scale=(0.0135, 0.008, 0.021))
        g = c + n * 0.0075 + Vector((0.0035 * s, 0, 0.008))
        p.sphere("glow_white", r=0.0040, seg=6, rings=3, loc=tuple(g))
    c, n = _on_core(0.0, -0.060, embed=0.002)
    p.sphere("wisp_eye", r=1.0, seg=8, rings=5, loc=tuple(c), scale=(0.0085, 0.006, 0.007))
    o = p.build(parent, loc=(0, 0, 0))
    hp.smooth_obj(o, 70)
    return o


# =========================================================================================
# RINGS
# =========================================================================================

def build_ring_a(parent):
    p = Part("ring_A")
    wh.gear_ring_lp(p, "brass", r_in=RA - 0.016, r_root=RA + 0.006, r_tip=RA + 0.015, teeth=26, thick=0.009)
    for k in range(3):
        a = math.radians(90 + 120 * k)
        c = (math.cos(a) * RA, math.sin(a) * RA, 0)
        # round lug with a bezel-set rune stone on top
        wh.revolve(p, "brass", [(0.0, -0.0075), (0.019, -0.0075), (0.021, -0.003), (0.021, 0.004),
                                (0.017, 0.0085), (0.0, 0.0085)], C10, loc=c)
        wh.revolve(p, "glow_amber", [(0.0, 0.006), (0.0115, 0.006), (0.011, 0.0105), (0.007, 0.0145),
                                     (0.0, 0.016)], C10, loc=c)
    o = p.build(parent, loc=(0, 0, ZA))
    hp.smooth_obj(o, 40)
    return o


def build_ring_b(parent):
    p = Part("ring_B")
    pr = Part("ring_B_runes")
    band = [(0.0045, -0.0125), (0.0060, 0.0), (0.0045, 0.0125), (-0.0040, 0.0125), (-0.0052, 0.0),
            (-0.0040, -0.0125)]
    wh.ring_band(p, "brass", RB, band, seg=48)
    plate = [(0.0090, -0.0185), (0.0108, 0.0), (0.0090, 0.0185), (-0.0060, 0.0185), (-0.0072, 0.0),
             (-0.0060, -0.0185)]
    for k in range(3):
        a = math.radians(90 + 120 * k)
        wh.ring_band(p, "brass_dark", RB, plate, seg=6, arc=(a - 0.085, a + 0.085))
        for e in (-1, 1):                    # end ribs of the cartouche
            ae = a + e * 0.088
            wh.ring_band(p, "brass", RB, [(0.0118, -0.021), (0.0118, 0.021), (-0.0078, 0.021), (-0.0078, -0.021)],
                         seg=1, arc=(ae - 0.012, ae + 0.012))
        M = Matrix.Translation((math.cos(a) * (RB + 0.0113), math.sin(a) * (RB + 0.0113), 0)) @ \
            Matrix.Rotation(a - math.pi / 2, 4, "Z")
        wh.rune(pr, "glow_amber", M, ("algiz", "tiwaz", "ingwaz")[k], h=0.024, bar=0.0032)
        # glow bead threaded on the band between the cartouches, with two little collars
        b = a + math.pi / 3
        p.sphere("glow_amber", r=0.0165, seg=8, rings=5, loc=(math.cos(b) * RB, math.sin(b) * RB, 0))
        for e in (-1, 1):
            be = b + e * 0.040
            wh.ring_band(p, "brass_dark", RB, [(0.0095, -0.0145), (0.0095, 0.0145), (-0.0085, 0.0145),
                                               (-0.0085, -0.0145)], seg=1, arc=(be - 0.008, be + 0.008))
    o = p.build(parent, loc=(0, 0, 0))
    hp.smooth_obj(o, 40)
    r = wh.build_raw(pr, parent, loc=(0, 0, 0))
    return o, r


# =========================================================================================
# WINGS
# =========================================================================================
HUB = 0.074
BACK_SWEEP = 12.0
BLADES = (  # (angle deg from +X toward +Z, length, max width, depth layer, material)
    (-8.0, 0.200, 0.046, 0.010, "copper"),
    (17.0, 0.232, 0.052, 0.015, "brass"),
    (42.0, 0.212, 0.048, 0.020, "copper"),
    (67.0, 0.168, 0.040, 0.025, "brass"),
)


def _blade(p, mat, ang, L, W, depth, curl=0.022):
    th = math.radians(ang)
    d = Vector((math.cos(th), 0, math.sin(th)))
    e = Vector((-math.sin(th), 0, math.cos(th)))
    u0 = 0.022
    prof = ((0.0, 0.42), (0.14, 0.74), (0.30, 0.93), (0.46, 1.0), (0.62, 0.93), (0.77, 0.74),
            (0.89, 0.46), (1.0, 0.0))
    pts, secs = [], []
    t = 0.0034
    for (s, wf) in prof:
        u = u0 + (L - u0) * s
        pts.append(Vector((HUB, depth, 0)) + d * u - e * (curl * s ** 2))
        if wf <= 0:
            secs.append(None)
            continue
        w = W * wf
        ch = min(0.0045, w * 0.22)
        # x = depth (-Y is the front), y = across the blade; front ridge, flat back
        secs.append([(0.0, w / 2), (-t, w / 2 - ch), (-t * 1.55, 0.0), (-t, -w / 2 + ch), (0.0, -w / 2),
                     (t * 0.8, -w / 2 + ch), (t * 0.8, w / 2 - ch)])
    wh.sweep(p, mat, pts, secs, up=(0, 1, 0))


def build_wing(name, s):
    pb = Part(name)                          # blades: crisp ridge + chamfers (own shading)
    for (ang, L, W, dep, mat) in BLADES:
        _blade(pb, mat, ang, L, W, dep)
    ph = Part(name + "_hub")                 # axle, spoked gear, small gear
    ph.cyl("brass_dark", r=0.0115, h=0.05, seg=8, loc=(0.020, 0, 0), rot=(0, 90, 0))
    wh.gear_ring_lp(ph, "brass", r_in=0.039, r_root=0.050, r_tip=0.058, teeth=11, thick=0.011,
                    loc=(HUB, 0, 0), rot=(90, 0, 0))
    wh.revolve(ph, "brass_dark", [(0.0, -0.009), (0.015, -0.009), (0.017, -0.004), (0.017, 0.006),
                                  (0.0, 0.006)], C10, loc=(HUB, 0, 0), rot=(90, 0, 0))
    for k in range(5):
        a = math.radians(90 + 72 * k)
        cc = Vector((HUB, 0, 0)) + Vector((math.cos(a), 0, math.sin(a))) * 0.028
        ph.box("brass", size=(0.026, 0.006, 0.0075), loc=tuple(cc), rot=(0, -math.degrees(a), 0))
    ph.sphere("glow_amber", r=0.0095, seg=6, rings=4, loc=(HUB, -0.0095, 0), scale=(1, 0.65, 1))
    sgear(ph, "brass_dark", r=0.028, teeth=7, thick=0.008, loc=(0.028, -0.001, 0.062), rot=(90, 0, 0))
    ph.cyl("brass", r=0.0075, h=0.012, seg=6, loc=(0.028, -0.003, 0.062), rot=(90, 0, 0))
    rotm = Matrix.Rotation(math.radians(BACK_SWEEP), 3, "Z")
    for p_ in (pb, ph):
        bmesh.ops.rotate(p_.bm, verts=p_.bm.verts[:], cent=(0, 0, 0), matrix=rotm)
        if s < 0:
            wh.mirror_x(p_)
    return pb, ph


def finish_wing(lantern, name, s):
    pb, ph = build_wing(name, s)
    loc = (s * WX, 0, WZ)
    ob = pb.build(lantern, loc=loc)
    hp.smooth_obj(ob, 10)
    oh = ph.build(lantern, loc=loc)
    hp.smooth_obj(oh, 40)
    return ob, oh


# =========================================================================================
# ASSEMBLY
# =========================================================================================
lantern_parts, glass = build_lantern()
lantern = lantern_parts[0]
for o in lantern_parts[1:] + [glass]:        # sub-meshes share the lantern pivot
    o.parent = lantern
    o.location = (0, 0, 0)
flame = build_flame(lantern)
ring_A = build_ring_a(lantern)
tilt = empty("ring_B_tilt", parent=lantern, loc=(0, 0, 0))
tilt.rotation_euler = (math.radians(TILT_B), 0, 0)
ring_B, ring_B_runes = build_ring_b(tilt)
wingL_b, wingL_h = finish_wing(lantern, "wing_L", 1)
wingR_b, wingR_h = finish_wing(lantern, "wing_R", -1)
bpy.context.view_layer.update()

# ---- vertex AO (before joining: glass and glow don't occlude; rings bake on their own) ----
solid = lantern_parts + [wingL_b, wingL_h, wingR_b, wingR_h]
hp.bake_vertex_ao(objs=solid + [flame], occluders=solid, ground=None, samples=48, distance=0.10,
                  strength=0.75, floor=0.45)
hp.bake_vertex_ao(objs=[ring_A], occluders=[ring_A], ground=None, samples=32, distance=0.05,
                  strength=0.6, floor=0.55)
hp.bake_vertex_ao(objs=[ring_B], occluders=[ring_B], ground=None, samples=32, distance=0.05,
                  strength=0.6, floor=0.55)
hp.fill_vertex_color([glass, ring_B_runes])
ring_B = wh.join_objects([ring_B, ring_B_runes])

lantern = wh.join_objects(lantern_parts + [glass])
wing_L = wh.join_objects([wingL_b, wingL_h])
wing_R = wh.join_objects([wingR_b, wingR_h])
bpy.context.view_layer.update()


# =========================================================================================
# CHECKS
# =========================================================================================

def set_pose(ring_a=0.0, ring_b=0.0, wings=0.0, flame_s=1.0):
    """Mimic src/anim/rig.ts: model-axis rotations conjugated into the parent frame."""
    ring_A.rotation_euler = (0, 0, ring_a)
    tq = tilt.rotation_euler.to_quaternion()
    ring_B.rotation_mode = "QUATERNION"
    ring_B.rotation_quaternion = tq.inverted() @ Quaternion((0, 0, 1), ring_b) @ tq
    wing_L.rotation_euler = (0, 0, wings)
    wing_R.rotation_euler = (0, 0, -wings)
    flame.scale = (flame_s, flame_s, flame_s * 1.05 if flame_s != 1.0 else 1.0)
    bpy.context.view_layer.update()


def check_motion():
    beyond_axle = lambda co: abs(co.x) > 0.012          # noqa: E731  (axle sits in its boss by design)
    above_wick = lambda co: co.z > -0.118                # noqa: E731  (wick sits in the flame by design)
    pairs = ((ring_A, lantern, None, None), (ring_A, wing_L, None, None), (ring_A, wing_R, None, None),
             (ring_B, lantern, None, None), (ring_B, wing_L, None, None), (ring_B, wing_R, None, None),
             (ring_B, ring_A, None, None), (wing_L, lantern, beyond_axle, None),
             (wing_R, lantern, beyond_axle, None))
    worst = {}
    for i in range(12):
        ang = math.tau * i / 12
        for w in (-0.6, 0.0, 0.6):
            set_pose(ring_a=ang, ring_b=ang * 1.3, wings=w)
            for a_, b_, fa, fb in pairs:
                d, ov = wh.clearance(a_, b_, fa, fb)
                key = f"{a_.name}-{b_.name}"
                cur = worst.get(key, (9, 0))
                worst[key] = (min(cur[0], d), max(cur[1], ov))
    for fs in (1.11, 0.89):
        set_pose(flame_s=fs)
        worst[f"flame x{fs}-lantern"] = wh.clearance(flame, lantern, None, above_wick)
    set_pose()
    for k, (d, ov) in worst.items():
        flag = "  <-- OVERLAP" if ov else ("  <-- tight" if d < 0.008 else "")
        print(f"[motion] {k:24s} min clearance {d * 1000:6.1f} mm  overlaps {ov}{flag}")


total = tri_report()
check_motion()

if MODE != "none":
    hp.export_glb_hp("wisp")

if MODE in ("full", "quick"):
    views = (("", 35, 18), ("_front", 0, 6), ("_side", 90, 8), ("_back", 200, 20))
    if MODE == "quick":
        views = (("", 35, 18), ("_front", 0, 6))
    hp.render_views("wisp", views=views)
    hp.render_hp("wisp_flame", target=((0, -0.05, LZ - 0.02), 0.24), azimuth=12, elevation=6)
    wh.render_aces("wisp_aces", ((0, 0, LZ - 0.02), 0.60), azimuth=30, elevation=18)
    wh.render_aces("wisp_aces_flame", ((0, -0.05, LZ - 0.02), 0.20), azimuth=12, elevation=6)
    wh.render_aces("wisp_aces_wing", ((0.32, 0.0, LZ + 0.08), 0.20), azimuth=20, elevation=12)
if MODE == "full":
    hp.render_hp("wisp_low", azimuth=30, elevation=-22)
    hp.render_hp("wisp_game", azimuth=25, elevation=25, dist_k=7.0)
    hp.render_hp("wisp_top", azimuth=20, elevation=62)
if MODE in ("full", "anim"):
    set_pose(ring_a=0.7, ring_b=1.2, wings=0.6, flame_s=1.11)
    hp.render_hp("wisp_anim_a", azimuth=35, elevation=18)
    set_pose(ring_a=2.0, ring_b=2.6, wings=-0.6, flame_s=0.89)
    hp.render_hp("wisp_anim_b", azimuth=-40, elevation=10)
    set_pose()
print(f"[wisp] done, {total} tris")
