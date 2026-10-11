"""Landmark: small airship circling over the field — hi-poly pass (2026-10-11).

Builders for props.glb (assembled by model_props.py). The builder returns the top-level EMPTY
`prop_airship` (origin at its base centre, z = 0; the airship floats above it exactly like the legacy
low-poly one: envelope axis at z = 8.2). Nose toward -Y, ~12 m long.

    prop_airship (empty)
    ├─ prop_airship_body   every static part (envelope, fins, rigging, gondola, engine, duct) — one mesh
    └─ propeller           pusher propeller, pivot at the hub, spins about its local Y (game: rotation.z)

Form language: a plump red/cream striped cigar envelope (12 pillowed gores with brass seam ribs, three
brass bands, brass nose cap with mooring spike, brass tail cone), X-tail with framed fins and hinged
cream rudders, a winged-gear crest with a glowing aether core on each flank, brass load belts along the
lower +-45 deg seams with V-rigged suspension ropes, and a clinker-built wooden sky-boat gondola (red
sheer strake, tarred garboard, brass trim, glowing portholes, cabin with lit windows, rail, lanterns,
sandbags, aether crystal lamp under the keel) pushed by a ducted 5-blade scimitar propeller.
Vertex colours = baked AO x a painted seam tint on the gores (_gore_tint).

Test this group alone (no props.glb export):
    blender -b --factory-startup -P tools/blender/model_props.py -- --group=airship --previews [--back]
Test export to a scratch dir:  ... -- --group=airship --out=<dir>
Env AIR_FAST=1 skips the vertex-AO bake (faster preview iteration).
"""
import bisect
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: E402,F401,F403
from env_helpers import Xform, box_m, mtx  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
import bmesh  # noqa: E402
import hp_helpers as hp  # noqa: E402
import hp_airship_helpers as ah  # noqa: E402
from hp_airship_helpers import (Track, mark_bevel, add_grid, revolve_y, revolve_m, sweep, sweep_custom,  # noqa: E402
                                tube, rrect_shape, circle_shape, round_corners, bezier2, coons, smoothstep,
                                stack_decal, gear_outline)

# ---------------------------------------------------------------------------
# materials (11)
# ---------------------------------------------------------------------------
RED, CREAM = "air_canvas_red", "air_canvas_cream"
BRASS, BRASS_D, COPPER, IRON = "brass", "brass_dark", "copper", "iron"
WOOD, WOOD_D, ROPE = "wood", "wood_dark", "rope"
AMBER, CYAN = "glow_amber", "glow_cyan"


def setup_mats():
    """Group-specific materials (air_ prefix). Doped canvas: a touch glossier than cloth_* so the
    envelope catches a soft highlight along its length."""
    get_mat(RED, hex="#ad3128", roughness=0.6)
    get_mat(CREAM, hex="#eadcb6", roughness=0.62)
    get_mat(ROPE, hex="#b39a6b", roughness=0.9)  # shared entry (model_props); cached if it exists


# ---------------------------------------------------------------------------
# envelope geometry
# ---------------------------------------------------------------------------
ENV_Z = 8.2                                  # envelope axis height (legacy)
Y_NOSE, Y_MID0, Y_MID1, Y_TAIL = -5.72, -1.30, 0.86, 6.05
R_MAX = 2.36
GORES, PER_GORE = 12, 5
SEG = GORES * PER_GORE
CREASE = 0.028                               # gore pillowing (fraction of radius)
BANDS = (-3.85, -0.45, 2.55)                 # brass bands (y)
TH0 = -math.pi / GORES                       # first seam -> gore 0 centred on the bottom
CREST_Y = -2.15                              # flank crest centre (y)
CREST_WING = [(0.34, 0.20), (0.62, 0.40), (0.95, 0.52), (1.22, 0.55), (1.0, 0.40), (1.16, 0.33), (0.94, 0.22),
              (1.06, 0.12), (0.86, 0.05), (0.92, -0.06), (0.7, -0.07), (0.38, -0.12)]
TAIL_C0 = Y_TAIL - 0.46                      # tail cone start
NOSE_PSI = math.asin(0.62 / R_MAX)           # nose cap extent (ellipse parameter)


def env_r0(y):
    """Bare profile: elliptic nose, short parallel mid-body, tapering power-law tail."""
    if y <= Y_MID0:
        x = (Y_MID0 - y) / (Y_MID0 - Y_NOSE)
        return R_MAX * math.sqrt(max(0.0, 1 - x * x))
    if y >= Y_MID1:
        x = (y - Y_MID1) / (Y_TAIL - Y_MID1)
        return R_MAX * max(0.0, 1 - x * x) ** 0.8
    return R_MAX


def band_k(y, w):
    return max(math.exp(-((y - b) / w) ** 2) for b in BANDS)


def env_rr(y):
    """Gore crest radius (bands pinch the envelope slightly)."""
    return env_r0(y) * (1.0 - 0.014 * band_k(y, 0.32))


def crease(y):
    return CREASE * (1.0 - band_k(y, 0.17))


def gore_bulge(u):
    return math.sin(math.pi * u) ** 0.55


def env_r(y, th):
    g = (th - TH0) / (2 * math.pi / GORES)
    u = g - math.floor(g)
    return env_rr(y) * (1 - crease(y) * (1 - gore_bulge(u)))


def radial(th):
    return Vector((math.sin(th), 0.0, -math.cos(th)))


def env_pt(y, th, dr=0.0):
    return Vector((0.0, y, ENV_Z)) + radial(th) * (env_r(y, th) + dr)


def env_normal(y, th):
    dy = 0.01
    drdy = (env_rr(y + dy) - env_rr(y - dy)) / (2 * dy)
    return (radial(th) - Vector((0, drdy, 0))).normalized()


def seam_theta(s):
    return TH0 + s * 2 * math.pi / GORES


def env_stations(step=0.30):
    """y stations spaced evenly along the profile arc, plus extra rings around the bands."""
    ya, yb = Y_NOSE + 0.035, Y_TAIL - 0.40
    n = 6000
    ys = [ya + (yb - ya) * i / n for i in range(n + 1)]
    L = [0.0]
    for i in range(1, len(ys)):
        L.append(L[-1] + math.hypot(ys[i] - ys[i - 1], env_r0(ys[i]) - env_r0(ys[i - 1])))
    m = max(2, int(round(L[-1] / step)))
    out = []
    for k in range(m + 1):
        s = L[-1] * k / m
        i = min(bisect.bisect_left(L, s), len(ys) - 1)
        out.append(ys[i])
    for b in BANDS:
        out += [b + d for d in (-0.095, 0.0, 0.095)]
    out = sorted(out)
    res = [out[0]]
    for y in out[1:]:
        if y - res[-1] > 0.06:
            res.append(y)
    return res


def build_envelope(parent):
    p = Part("prop_airship_envelope")
    ys = env_stations()
    prof = [(Y_NOSE + 0.004, 0.0)] + [(y, env_rr(y)) for y in ys] + [(ys[-1] + 0.22, 0.0)]

    def rfun(i, j, th, r):
        u = (j % PER_GORE) / PER_GORE
        return r * (1 - crease(prof[i][0]) * (1 - gore_bulge(u)))

    def gore_mat(i, j):
        return RED if (j // PER_GORE) % 2 == 0 else CREAM

    revolve_y(p, RED, prof, seg=SEG, cz=ENV_Z, theta0=TH0, rfun=rfun, mat_fn=gore_mat)

    # brass bands: rounded straps hugging the (pinched, crease-free) envelope
    for b in BANDS:
        w, t = 0.095, 0.045
        bp = [(b - w, env_rr(b - w) - 0.012), (b - w, env_rr(b - w) + t * 0.55), (b - w * 0.72, env_rr(b) + t),
              (b + w * 0.72, env_rr(b) + t), (b + w, env_rr(b + w) + t * 0.55), (b + w, env_rr(b + w) - 0.012)]
        revolve_y(p, BRASS, bp, seg=40, cz=ENV_Z, theta0=TH0, closed=True)

    # brass nose cap following the elliptic nose + mooring spike
    a = Y_MID0 - Y_NOSE

    def nose(psi, off):
        y, r = Y_MID0 - a * math.cos(psi), R_MAX * math.sin(psi)
        n = Vector((-R_MAX * math.cos(psi), a * math.sin(psi))).normalized()
        return (y + n.x * off, r + n.y * off), Vector((a * math.sin(psi), R_MAX * math.cos(psi))).normalized()

    cap = []
    n_cap = 9
    for k in range(n_cap + 1):
        f = k / n_cap
        off = 0.035 + 0.15 * (1 - f ** 1.5) + 0.022 * math.exp(-((f - 0.62) / 0.06) ** 2)
        cap.append(nose(NOSE_PSI * f, off)[0])
    (ye, re), tg = nose(NOSE_PSI, 0.0)
    cap += [(ye - 0.01, re + 0.08), (ye + tg.x * 0.075, re + tg.y * 0.075 + 0.075),
            (ye + tg.x * 0.075, re + tg.y * 0.075 - 0.01)]
    for k in range(4, -1, -1):
        cap.append(nose(NOSE_PSI * k / 4, -0.012)[0])
    cap[0] = (cap[0][0], 0.0)
    cap[-1] = (cap[-1][0], 0.0)
    revolve_y(p, BRASS, cap, seg=36, cz=ENV_Z, theta0=TH0)
    yn = Y_NOSE - 0.16
    spike = [(yn + 0.03, 0.0), (yn + 0.03, 0.13), (yn - 0.04, 0.12), (yn - 0.07, 0.075), (yn - 0.12, 0.055),
             (yn - 0.15, 0.08), (yn - 0.2, 0.09), (yn - 0.25, 0.08), (yn - 0.28, 0.05), (yn - 0.32, 0.035),
             (yn - 0.5, 0.0)]
    revolve_y(p, BRASS, spike, seg=16, cz=ENV_Z)

    # brass tail cone (rim lip, straight taper, ball finial)
    yc = TAIL_C0
    rc = env_rr(yc) + 0.035
    yt = Y_TAIL + 0.22
    tail = [(yc - 0.07, 0.0), (yc - 0.07, rc - 0.06), (yc - 0.07, rc + 0.035), (yc - 0.025, rc + 0.055),
            (yc + 0.02, rc + 0.025)]
    Lc = yt - (yc + 0.02)
    for k in range(1, 7):
        f = k / 6
        tail.append((yc + 0.02 + Lc * f, 0.06 + (rc - 0.06) * (1 - f) ** 1.1))
    tail += [(yt + 0.03, 0.085), (yt + 0.08, 0.095), (yt + 0.13, 0.08), (yt + 0.16, 0.05), (yt + 0.3, 0.0)]
    revolve_y(p, BRASS, tail, seg=28, cz=ENV_Z, theta0=TH0)

    # flank crest: winged brass gear with a glowing aether core, on the cream side gores
    for sgn in (1, -1):
        def surf(u, v, h, sgn=sgn):
            y = CREST_Y + u
            return env_pt(y, sgn * (math.pi / 2 + v / env_rr(y)), h)
        stack_decal(p, BRASS, gear_outline(0.42, 10, 0.085), (0.0, 0.0),
                    [(1.0, -0.03), (1.0, 0.032), (0.95, 0.044)], surf)
        stack_decal(p, BRASS_D, circle_shape(0.25, 20), (0.0, 0.0), [(1.0, 0.0), (1.0, 0.056), (0.9, 0.064)], surf)
        stack_decal(p, CYAN, circle_shape(0.18, 16), (0.0, 0.0), [(1.0, 0.0), (1.0, 0.07), (0.6, 0.088)], surf)
        for su in (1, -1):
            wing = [(su * u, v) for (u, v) in CREST_WING]
            stack_decal(p, BRASS, wing, (su * 0.6, 0.15), [(1.0, -0.03), (1.0, 0.03), (0.5, 0.046)], surf)
    return p.build(parent)


# ---------------------------------------------------------------------------
# rigging: seam ribs, load belts + eyelets, suspension ropes, keel beam
# ---------------------------------------------------------------------------
BELT_TH = math.radians(45.0)                  # belts run along the +-45 deg seams (fins continue the line)
BELT_Y = (-3.3, 2.95)
BELT_PTS = tuple(y + d for y in (-2.15, -1.05, 0.05, 1.15, 2.05) for d in (-0.3, 0.3))


def belt_point(y, side):
    th = side * BELT_TH
    return env_pt(y, th, 0.045), env_normal(y, th)


def build_rigging(parent, hull):
    p = Part("prop_airship_rigging")
    # seam ribs (thicker battens near the nose)
    y0 = Y_NOSE + (Y_MID0 - Y_NOSE) * (1 - math.cos(NOSE_PSI)) - 0.04
    y1 = TAIL_C0 + 0.02
    nseam = 20
    ys = [y0 + (y1 - y0) * (1 - math.cos(math.pi * k / nseam)) / 2 for k in range(nseam + 1)]
    radii = [1.0 + 0.85 * (1 - smoothstep(Y_NOSE + 0.5, Y_NOSE + 1.7, y)) for y in ys]
    for s in range(GORES):
        th = seam_theta(s)
        pts = [tuple(env_pt(y, th, 0.012)) for y in ys]
        tube(p, BRASS_D, pts, 0.022, seg=4, radii=radii, up=tuple(radial(th)))

    # load belts on the +-45 deg seams with eyelets
    for side in (-1, 1):
        th = side * BELT_TH
        n = 26
        cs, ns, bs = [], [], []
        for k in range(n + 1):
            y = BELT_Y[0] + (BELT_Y[1] - BELT_Y[0]) * k / n
            c = env_pt(y, th, 0.018)
            nrm = env_normal(y, th)
            tang = Vector((math.cos(th), 0, math.sin(th)))
            cs.append(c)
            ns.append(nrm)
            bs.append(tang)
        sweep_custom(p, BRASS_D, cs, ns, bs, rrect_shape(0.045, 0.15, 0.015, 1))
        for y in BELT_PTS:
            c, nrm = belt_point(y, side)
            with Xform(p, ah.orient(c, nrm, up=(0, 1, 0))):
                p.torus(BRASS, R=0.055, r=0.016, seg=6, seg2=4, loc=(0, 0, 0.0), rot=(90, 0, 0))

    # suspension ropes: one V per gondola rail point, up to two belt eyelets
    for side in (-1, 1):
        for yg in hull["rope_pts"]:
            bot = hull["rail_at"](yg, side)
            for dy in (-0.3, 0.3):
                top, _ = belt_point(yg + dy, side)
                tube(p, ROPE, [tuple(top + Vector((0, 0, -0.05))), tuple(bot)], 0.024, seg=6)

    # keel beam along the envelope belly + brass end caps / collars
    kys = [-2.55 + k * 0.3 for k in range(17)]
    kpts = [(0.0, y, ENV_Z - env_r(y, 0.0) - 0.075) for y in kys]
    sweep(p, WOOD_D, kpts, rrect_shape(0.13, 0.16, 0.03, 2), up=(0, 0, 1), mode="up")
    for y in (-2.45, -1.2, 0.05, 1.3, 2.15):
        z = ENV_Z - env_r(y, 0.0) - 0.075
        sweep(p, BRASS, [(0, y - 0.04, z), (0, y + 0.04, z)], rrect_shape(0.155, 0.185, 0.035, 2), mode="up")
    return p.build(parent)


# ---------------------------------------------------------------------------
# fins (X tail, framed canvas + hinged rudders)
# ---------------------------------------------------------------------------
FIN_THETAS = [math.radians(a) for a in (45, 135, 225, 315)]
Y_F0, Y_HINGE = 2.85, 5.12
TIP_LE, TIP_TE = (4.30, 3.30), (Y_HINGE, 3.36)
RUD_Y0, RUD_Y1 = 5.18, 5.82
RUD_TIP = (5.60, 3.28)


def fin_world(th):
    er = radial(th)
    en = Vector((math.cos(th), 0.0, math.sin(th)))

    def W(y, rho, t=0.0):
        return Vector((0.0, y, ENV_Z)) + er * rho + en * t
    return W


def V2(a, b=None):
    return Vector(a) if b is None else Vector((a, b))


def fin_patches():
    def root(y):
        return env_r0(y) - 0.045

    main = coons(lambda u: V2(Y_F0 + (Y_HINGE - Y_F0) * u, root(Y_F0 + (Y_HINGE - Y_F0) * u)),
                 lambda u: V2(TIP_LE).lerp(V2(TIP_TE), u),
                 lambda v: bezier2((Y_F0, root(Y_F0)), (3.18, 3.05), TIP_LE, v),
                 lambda v: V2(Y_HINGE, root(Y_HINGE) + (TIP_TE[1] - root(Y_HINGE)) * v))
    rud = coons(lambda u: V2(RUD_Y0 + (RUD_Y1 - RUD_Y0) * u, root(RUD_Y0 + (RUD_Y1 - RUD_Y0) * u)),
                lambda u: V2(RUD_Y0, TIP_TE[1]).lerp(V2(RUD_TIP), u),
                lambda v: V2(RUD_Y0, root(RUD_Y0) + (TIP_TE[1] - root(RUD_Y0)) * v),
                lambda v: bezier2((RUD_Y1, root(RUD_Y1)), (5.98, 2.55), RUD_TIP, v))
    return main, rud


def fin_body(p, mat, P, W, nu, nv, T, taper=0.45, mat_fn=None):
    rows = []
    for i in range(nv + 1):
        v = i / nv
        top, bot = [], []
        for j in range(nu + 1):
            u = j / nu
            y, rho = P(u, v)
            t = T * (1 - taper * v) * (0.34 + 0.66 * math.sin(math.pi * u) ** 0.5)
            top.append(tuple(W(y, rho, t / 2)))
            bot.append(tuple(W(y, rho, -t / 2)))
        rows.append(top + bot[::-1])
    add_grid(p, rows, mat, closed_u=True, cap0=mat, cap1=mat, mat_fn=mat_fn)


def build_fins(parent):
    p = Part("prop_airship_fins")
    main, rud = fin_patches()
    for th in FIN_THETAS:
        W = fin_world(th)
        fin_body(p, RED, main, W, nu=8, nv=6, T=0.07)
        fin_body(p, CREAM, rud, W, nu=5, nv=6, T=0.055)
        # frame around the main fin: leading edge -> tip -> hinge spar
        le = [main(0.0, k / 6) for k in range(7)]
        tip = [main(k / 3, 1.0) for k in range(1, 4)]
        hinge = [main(1.0, 1.0 - k / 4) for k in range(1, 5)]
        outline = [tuple(W(q.x, q.y)) for q in le + tip + hinge]
        tube(p, BRASS_D, round_corners(outline, 0.12, 2), 0.042, seg=6, up=tuple(Vector((math.cos(th), 0, math.sin(th)))))
        # rudder frame: hinge (thin) + tip + trailing edge
        rtop = [rud(k / 3, 1.0) for k in range(4)]
        rte = [rud(1.0, 1.0 - k / 6) for k in range(1, 7)]
        rout = [tuple(W(q.x, q.y)) for q in rtop + rte]
        tube(p, BRASS_D, round_corners(rout, 0.12, 2), 0.036, seg=6, up=tuple(Vector((math.cos(th), 0, math.sin(th)))))
        rh = [tuple(W(*rud(0.0, k / 4))) for k in range(5)]
        tube(p, BRASS_D, rh, 0.03, seg=6)
        # spanwise ribs on the fin canvas
        for u in (0.52,):
            rib = [tuple(W(*main(u, k / 5))) for k in range(6)]
            tube(p, BRASS, rib, 0.022, seg=5)
        # hinge knuckles
        for v in (0.22, 0.55, 0.86):
            a = W(*main(1.0, v))
            d = (W(*main(1.0, v + 0.04)) - a).normalized()
            tube(p, BRASS, [tuple(a - d * 0.07), tuple(a + d * 0.07)], 0.05, seg=8)
        # tip light
        c = W(TIP_LE[0] - 0.02, TIP_LE[1] + 0.04)
        er = radial(th)
        revolve_m(p, BRASS, [(-0.06, 0.0), (-0.06, 0.06), (0.0, 0.085), (0.02, 0.085), (0.02, 0.0)], seg=10,
                  M=ah.orient(c, er))
        p.sphere(CYAN, r=0.07, seg=10, rings=6, loc=tuple(c + er * 0.04))
    return p.build(parent)


# ---------------------------------------------------------------------------
# gondola: clinker-built sky boat
# ---------------------------------------------------------------------------
GY0, GY1 = -2.90, 2.45       # bow stem / stern transom
Z_DECK = 4.45
HW, HD = 0.86, 0.70          # max half width, max depth below deck
HN = 2.5                     # section superellipse exponent
K_STRAKES = 5
CLINK = 0.03                # plank lap
BULW = 0.05                  # bulwark thickness
RAKE = 0.30                  # stem rake (top of the bow leans forward)
Y_HUB, Z_HUB = 3.58, 4.68    # propeller hub


def hull_w(t):
    if t < 0.42:
        f = max(0.0, 1 - (1 - t / 0.42) ** 2) ** 0.62
    else:
        u = (t - 0.42) / 0.58
        f = 1 - 0.30 * u * u
    return HW * f


def hull_depth(t):
    if t < 0.5:
        k = 0.86 * ((0.5 - t) / 0.5) ** 2
    else:
        k = 0.45 * ((t - 0.5) / 0.5) ** 2.2
    return HD * (1 - k)


def hull_sheer(t):
    return 0.30 + 0.34 * max(0.0, 1 - t / 0.30) ** 2 + 0.12 * max(0.0, (t - 0.78) / 0.22) ** 2


def hull_curve(t, n=160):
    w, s, d = hull_w(t), hull_sheer(t), hull_depth(t)
    zt, H = Z_DECK + s, s + d
    pts = []
    for i in range(n + 1):
        ph = (math.pi / 2) * i / n
        c, si = math.cos(ph), math.sin(ph)
        pts.append((w * (max(c, 0.0) ** (2 / HN)), zt - H * (si ** (2 / HN))))
    L = [0.0]
    for i in range(1, len(pts)):
        L.append(L[-1] + math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
    return pts, L


def curve_at(pts, L, f):
    s = min(max(f, 0.0), 1.0) * L[-1]
    i = min(max(bisect.bisect_left(L, s) - 1, 0), len(pts) - 2)
    seg = L[i + 1] - L[i]
    a = 0.0 if seg < 1e-12 else (s - L[i]) / seg
    x = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * a
    z = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * a
    tx, tz = pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]
    ln = math.hypot(tx, tz) or 1.0
    return (x, z), (-tz / ln, tx / ln)


def x_at_z(pts, z0):
    for (x0, za), (x1, zb) in zip(pts, pts[1:]):
        if (za - z0) * (zb - z0) <= 0 and za != zb:
            return x0 + (x1 - x0) * (z0 - za) / (zb - za)
    return 0.0


def hull_y(t, z):
    """Station y with the raked stem (upper bow leans forward)."""
    y = GY0 + (GY1 - GY0) * t
    zk = Z_DECK - hull_depth(t)
    h = max(0.0, (z - zk) / max(0.2, (Z_DECK + hull_sheer(t)) - zk))
    return y - RAKE * (h ** 1.4) * (1 - t) ** 4


def hull_point(t, f, side=1, off=0.0):
    pts, L = hull_curve(t)
    (x, z), (nx, nz) = curve_at(pts, L, f)
    x, z = x + nx * off, z + nz * off
    return Vector((side * x, hull_y(t, z), z))


def hull_frame(t, f, side=1, off=0.0):
    p = hull_point(t, f, side, off)
    dt = (hull_point(min(t + 0.01, 1), f, side, off) - hull_point(max(t - 0.01, 0), f, side, off))
    df = (hull_point(t, min(f + 0.01, 1), side, off) - hull_point(t, max(f - 0.01, 0), side, off))
    n = df.cross(dt).normalized() if side > 0 else dt.cross(df).normalized()
    if n.x * side < 0:
        n = -n
    return p, n


def clink(t):
    return CLINK * min(1.0, hull_w(t) / (0.45 * HW))


def hull_section(t):
    pts, L = hull_curve(t)
    w = hull_w(t)
    dl = clink(t)
    side, smat = [], []
    for k in range(K_STRAKES):
        for q, fr in enumerate((0.0, 0.5, 1.0)):
            if k == K_STRAKES - 1 and q == 2:
                continue
            (x, z), (nx, nz) = curve_at(pts, L, (k + fr) / K_STRAKES)
            side.append((x + nx * dl * fr, z + nz * dl * fr))
            smat.append(RED if k == 0 else (WOOD_D if k == K_STRAKES - 1 else WOOD))
    zk = pts[-1][1] - dl
    zt = Z_DECK + hull_sheer(t)
    x_in = max(0.0, x_at_z(pts, Z_DECK) - BULW * min(1.0, w / 0.3))
    x_in = min(x_in, max(0.0, w - 0.02))
    loop = [(0.0, Z_DECK), (x_in, Z_DECK), (x_in, zt)] + side + [(0.0, zk)] + \
           [(-x, z) for (x, z) in reversed(side)] + [(-x_in, zt), (-x_in, Z_DECK)]
    mats = [WOOD_D, WOOD_D, WOOD_D] + smat + [smat[-1]] + [smat[-2 - i] for i in range(len(side) - 1)] + \
           [WOOD_D, WOOD_D, WOOD_D]
    return loop, mats, x_in, zt, zk


def hull_ts(n=30):
    return [(i / n) ** 1.35 for i in range(n + 1)]


def rail_line(t, side):
    """Centre of the gunwale cap rail."""
    pts, L = hull_curve(t)
    w = hull_w(t)
    _, _, x_in, zt, _ = hull_section(t)
    x = (x_in + w) / 2
    z = zt + 0.025
    return Vector((side * x, hull_y(t, z), z))


def t_of_y(y):
    return (y - GY0) / (GY1 - GY0)




def lantern(p, M, glow=AMBER, s=1.0):
    """Ship lantern along local Z (centre of the glass at the origin), ~0.36*s tall."""
    M = M @ Matrix.Scale(s, 4)
    revolve_m(p, glow, [(-0.085, 0.0), (-0.085, 0.05), (-0.05, 0.068), (0.05, 0.068), (0.085, 0.05),
                        (0.085, 0.0)], seg=8, M=M)
    revolve_m(p, BRASS, [(-0.15, 0.0), (-0.15, 0.025), (-0.125, 0.055), (-0.1, 0.09), (-0.082, 0.09),
                         (-0.082, 0.0)], seg=10, M=M)
    revolve_m(p, BRASS, [(0.082, 0.0), (0.082, 0.095), (0.1, 0.095), (0.15, 0.055), (0.185, 0.025),
                         (0.2, 0.0)], seg=10, M=M)
    with Xform(p, M):
        p.torus(BRASS, R=0.04, r=0.011, seg=10, seg2=5, loc=(0, 0, 0.235), rot=(90, 0, 0))
        for k in range(4):
            a = math.pi / 4 + k * math.pi / 2
            box_m(p, BRASS, mtx((0.083 * math.cos(a), 0.083 * math.sin(a), 0.0), (0, 0, math.degrees(a)),
                                (0.022, 0.022, 0.18)))


def build_gondola(parent):
    p = Part("prop_airship_gondola")
    ts = hull_ts()
    # --- hull (one closed loft; the bow ring collapses into the raked stem) -----------------
    rows = []
    mats = None
    for t in ts:
        loop, mats, x_in, zt, zk = hull_section(t)
        rows.append([(x, hull_y(t, z), z) for (x, z) in loop])
    vr = add_grid(p, rows, WOOD, closed_u=True, cap1=WOOD, mat_fn=lambda i, j: mats[j])
    bmesh.ops.remove_doubles(p.bm, verts=vr[0], dist=1e-5)

    # --- brass trim ----------------------------------------------------------------------
    # cap rail: closed loop round the gunwale (port stern -> bow -> starboard stern -> transom)
    rts = ts[::2] if (len(ts) - 1) % 2 == 0 else ts[::2] + [ts[-1]]
    port = [rail_line(t, 1) for t in reversed(rts)]
    star = [rail_line(t, -1) for t in rts[1:]]
    loop = round_corners([tuple(v) for v in port + star], 0.08, 3, closed=True)
    sweep(p, BRASS, loop, rrect_shape(0.05, 0.095, 0.018, 1), mode="up", closed_path=True)
    # rub rail under the red sheer strake
    for side in (1, -1):
        pts = [tuple(hull_point(t, 1.0 / K_STRAKES, side, clink(t) + 0.012)) for t in ts[2:]]
        tube(p, BRASS, pts, 0.024, seg=6)
    # keel band: up the raked stem, along the keel, to the transom
    stem = [hull_point(0.0, 1 - k / 10, 1, 0.0) for k in range(11)][::-1]   # keel -> top
    stem = [Vector((0, v.y - 0.025, v.z)) for v in stem]
    keel = [Vector((0, hull_y(t, 0), Z_DECK - hull_depth(t) - clink(t) - 0.012)) for t in ts[1::2] + [ts[-1]]]
    kpath = [tuple(v) for v in stem[::-1]] + [tuple(v) for v in keel]
    kpath = round_corners(kpath, 0.12, 3)
    sweep(p, BRASS, kpath, rrect_shape(0.055, 0.08, 0.018, 1), up=(1, 0, 0))

    # --- portholes ------------------------------------------------------------------------
    for side in (1, -1):
        for t in (0.26, 0.40, 0.54, 0.68, 0.82):
            c, n = hull_frame(t, 1.55 / K_STRAKES, side, clink(t) * 0.55)
            with Xform(p, ah.orient(c, n)):
                p.torus(BRASS, R=0.082, r=0.022, seg=10, seg2=4)
                p.cyl(AMBER, r=0.07, h=0.03, seg=10, loc=(0, 0, -0.005))

    # --- bow: gear medallions, bowsprit + lantern ---------------------------------------------
    for side in (1, -1):
        c, n = hull_frame(0.12, 0.30, side, clink(0.12) + 0.01)
        with Xform(p, ah.orient(c, n)):
            ah.gear(p, BRASS, r=0.21, teeth=10, thick=0.045, hole=0.0)
            p.torus(BRASS_D, R=0.1, r=0.02, seg=12, seg2=4, loc=(0, 0, 0.03))
            p.cyl(CYAN, r=0.085, h=0.05, seg=12, loc=(0, 0, 0.02))
    st = hull_point(0.0, 0.0, 1)
    b0 = Vector((0, st.y + 0.25, st.z - 0.06))
    b1 = Vector((0, st.y - 0.72, st.z + 0.22))
    tube(p, WOOD_D, [tuple(b0), tuple(b1)], 0.045, seg=10)
    tube(p, BRASS, [tuple(b1 + (b0 - b1).normalized() * 0.06), tuple(b1 - (b0 - b1).normalized() * 0.04)], 0.055, seg=10)
    tube(p, BRASS_D, [tuple(b1 + Vector((0, 0, -0.02))), tuple(b1 + Vector((0, 0, -0.2)))], 0.012, seg=6)
    lantern(p, Matrix.Translation(b1 + Vector((0, 0, -0.41))), s=1.0)

    # --- deck rail: posts + continuous top rail -------------------------------------------
    post_ts = [0.07 + 0.9 * k / 8 for k in range(9)]
    tops = {1: [], -1: []}
    for side in (1, -1):
        for t in post_ts:
            b = rail_line(t, side) + Vector((0, 0, 0.02))
            tp = b + Vector((0, 0, 0.30))
            tube(p, BRASS, [tuple(b), tuple(tp)], 0.017, seg=8)
            tops[side].append(tp)
    bow = rail_line(0.012, 1)
    bow = Vector((0.0, bow.y + 0.03, bow.z + 0.3))
    rail = [tuple(v) for v in reversed(tops[1])] + [tuple(bow)] + [tuple(v) for v in tops[-1]]
    rail = round_corners(rail, 0.1, 3, closed=True)
    sweep(p, BRASS, rail, ah.circle_shape(0.022, 8), mode="up", closed_path=True)

    # --- cabin ---------------------------------------------------------------------------
    build_cabin(p)

    # --- belly aether lamp ------------------------------------------------------------------
    tl = 0.47
    yk = hull_y(tl, 0)
    zk = Z_DECK - hull_depth(tl) - clink(tl)
    tube(p, BRASS_D, [(0, yk, zk + 0.02), (0, yk, zk - 0.16)], 0.02, seg=8)
    zc = zk - 0.38
    p.torus(BRASS, R=0.07, r=0.018, seg=12, seg2=6, loc=(0, yk, zk - 0.17))
    from char_helpers import gem
    gem(p, CYAN, r=0.1, up=0.17, down=0.21, seg=6, loc=(0, yk, zc))
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        bar = []
        for q in range(7):
            f = q / 6
            rr = 0.07 + 0.08 * math.sin(math.pi * f)
            bar.append((math.cos(a) * rr * (1 - 0.6 * f ** 3), yk + math.sin(a) * rr * (1 - 0.6 * f ** 3),
                        zk - 0.17 - f * 0.47))
        tube(p, BRASS, bar, 0.011, seg=6)
    revolve_m(p, BRASS, [(-0.71, 0.0), (-0.66, 0.035), (-0.63, 0.04), (-0.6, 0.0)], seg=10,
              M=Matrix.Translation((0, yk, zk)))

    # --- canvas sandbags hanging off the cap rail (between the portholes) -------------------------
    for side in (1, -1):
        for t in (0.33, 0.75):
            r0 = rail_line(t, side)
            w = hull_w(t)
            c = Vector((side * (w + 0.15), r0.y, r0.z - 0.36))
            tube(p, ROPE, [tuple(r0 + Vector((side * 0.02, 0, 0.0))), tuple(c + Vector((0, 0, 0.17)))], 0.014, seg=5)
            M = Matrix.Translation(c) @ Matrix.Rotation(math.radians(side * -10), 4, "Y") @                 Matrix.Diagonal((1.0, 0.85, 1.0, 1.0))
            revolve_m(p, ROPE, [(-0.17, 0.0), (-0.165, 0.07), (-0.13, 0.115), (-0.04, 0.135), (0.05, 0.12),
                                 (0.1, 0.07), (0.125, 0.032), (0.15, 0.04), (0.175, 0.03), (0.19, 0.0)],
                      seg=9, M=M)
            revolve_m(p, WOOD_D, [(0.11, 0.0), (0.11, 0.045), (0.135, 0.045), (0.135, 0.0)], seg=9, M=M)

    # --- stern lanterns on posts ---------------------------------------------------------
    for side in (1, -1):
        b = rail_line(0.985, side)
        tube(p, BRASS_D, [tuple(b), tuple(b + Vector((0, 0, 0.45)))], 0.022, seg=8)
        lantern(p, Matrix.Translation(b + Vector((0, 0, 0.62))), s=0.8)

    # --- engine, duct, chimney -----------------------------------------------------------
    build_engine(p)

    return p.build(parent)


def build_cabin(p):
    CY0, CY1, CW, CH = -0.40, 1.40, 0.56, 0.74
    zb, zt = Z_DECK, Z_DECK + CH
    ym = (CY0 + CY1) / 2
    with Track(p) as tr:
        p.box(WOOD_D, size=(2 * CW, CY1 - CY0, CH), loc=(0, ym, zb + CH / 2))
        # base & eave trims
        p.box(BRASS_D, size=(2 * CW + 0.05, CY1 - CY0 + 0.05, 0.07), loc=(0, ym, zb + 0.035))
        p.box(WOOD, size=(2 * CW + 0.06, CY1 - CY0 + 0.06, 0.07), loc=(0, ym, zt - 0.035))
        # corner posts
        for sx in (-1, 1):
            for sy, yy in ((-1, CY0), (1, CY1)):
                p.box(BRASS, size=(0.075, 0.075, CH), loc=(sx * CW, yy, zb + CH / 2))
    mark_bevel(p, tr.idx, angle=30)
    # side windows (glow panes, brass frames + mullions)
    for sx in (-1, 1):
        for yy in (-0.05, 0.5, 1.05):
            window(p, Vector((sx * CW, yy, zb + 0.43)), Vector((sx, 0, 0)), 0.34, 0.3)
    # front windows
    for xx in (-0.24, 0.24):
        window(p, Vector((xx, CY0, zb + 0.45)), Vector((0, -1, 0)), 0.3, 0.28)
    # rear door
    p.box(WOOD, size=(0.42, 0.04, 0.6), loc=(0, CY1 + 0.02, zb + 0.32))
    p.box(BRASS, size=(0.48, 0.03, 0.05), loc=(0, CY1 + 0.03, zb + 0.64))
    p.sphere(BRASS, r=0.03, seg=8, rings=5, loc=(0.13, CY1 + 0.05, zb + 0.32))
    # barrel roof (copper shell) + brass ridge + standing seams
    RW, RH, TH = CW + 0.13, 0.25, 0.04
    ry0, ry1 = CY0 - 0.14, CY1 + 0.14
    n = 14
    outer = [(RW * math.cos(math.pi * k / n), zt + RH * math.sin(math.pi * k / n)) for k in range(n + 1)]
    inner = [((RW - TH) * math.cos(math.pi * k / n), zt + (RH - TH) * math.sin(math.pi * k / n))
             for k in range(n + 1)]
    sec = outer + inner[::-1]
    with Track(p) as tr:
        add_grid(p, [[(x, ry0, z) for (x, z) in sec], [(x, ry1, z) for (x, z) in sec]], COPPER,
                 closed_u=True, cap0=COPPER, cap1=COPPER)
    mark_bevel(p, tr.idx, angle=40)
    for yy in [ry0 + 0.12 + (ry1 - ry0 - 0.24) * k / 3 for k in range(4)]:
        arc = [((RW + 0.008) * math.cos(math.pi * k / n), yy, zt + (RH + 0.008) * math.sin(math.pi * k / n))
               for k in range(n + 1)]
        tube(p, COPPER, arc, 0.016, seg=4)
    sweep(p, BRASS, [(0, ry0 - 0.02, zt + RH + 0.01), (0, ry1 + 0.02, zt + RH + 0.01)],
          rrect_shape(0.05, 0.07, 0.015, 2), mode="up")
    # stove pipe
    tube(p, IRON, [(0.25, 1.1, zt + 0.12), (0.25, 1.1, zt + 0.52)], 0.05, seg=12)
    revolve_m(p, BRASS, [(0.0, 0.0), (0.0, 0.07), (0.04, 0.085), (0.08, 0.06), (0.08, 0.0)], seg=12,
              M=Matrix.Translation((0.25, 1.1, zt + 0.5)))


def window(p, c, n, w, h):
    M = ah.orient(c, n, up=(0, 0, 1))
    with Xform(p, M):
        fw = 0.045
        p.box(AMBER, size=(w - fw, h - fw, 0.03), loc=(0, 0, 0.0))
        p.box(BRASS, size=(w, fw, 0.05), loc=(0, (h - fw) / 2, 0.01))
        p.box(BRASS, size=(w, fw, 0.05), loc=(0, -(h - fw) / 2, 0.01))
        p.box(BRASS, size=(fw, h, 0.05), loc=((w - fw) / 2, 0, 0.01))
        p.box(BRASS, size=(fw, h, 0.05), loc=(-(w - fw) / 2, 0, 0.01))
        p.box(BRASS, size=(0.022, h, 0.035), loc=(0, 0, 0.01))
        p.box(BRASS, size=(w, 0.022, 0.035), loc=(0, 0, 0.01))


def build_engine(p):
    cz = Z_HUB
    # transom bracket
    with Track(p) as tr:
        p.box(IRON, size=(0.62, 0.22, 0.16), loc=(0, GY1 + 0.04, cz - 0.2))
        p.box(IRON, size=(0.16, 0.22, 0.5), loc=(0, GY1 + 0.04, cz - 0.05))
    mark_bevel(p, tr.idx, angle=30)
    body = [(GY1 - 0.03, 0.0), (GY1 - 0.03, 0.27), (GY1 + 0.02, 0.34), (GY1 + 0.08, 0.37), (GY1 + 0.62, 0.37),
            (GY1 + 0.7, 0.33), (GY1 + 0.76, 0.25), (GY1 + 0.84, 0.19), (GY1 + 0.95, 0.15), (Y_HUB - 0.18, 0.12),
            (Y_HUB - 0.18, 0.0)]

    def bmat(i, j):
        return BRASS if i in (1, 2, 5, 6, 7, 8) else IRON
    revolve_y(p, IRON, body, seg=24, cz=cz, mat_fn=bmat)
    # copper coil round the boiler
    coil = []
    turns, n = 1.75, 36
    for k in range(n + 1):
        f = k / n
        a = 2 * math.pi * turns * f
        coil.append((0.395 * math.sin(a), GY1 + 0.16 + 0.42 * f, cz - 0.395 * math.cos(a)))
    tube(p, COPPER, coil, 0.026, seg=5)
    # aether vents (both sides)
    for sx in (-1, 1):
        c = Vector((sx * 0.37, GY1 + 0.36, cz + 0.02))
        with Xform(p, ah.orient(c, Vector((sx, 0, 0)))):
            p.torus(BRASS, R=0.1, r=0.025, seg=14, seg2=6)
            p.cyl(CYAN, r=0.09, h=0.04, seg=14)
    # chimney stack (raked back) with flared brass crown
    ch = [(0.0, GY1 + 0.3, cz + 0.3), (0.0, GY1 + 0.33, cz + 0.62), (0.0, GY1 + 0.42, cz + 0.98)]
    tube(p, IRON, ch, 0.085, seg=14, radii=[1.0, 1.0, 1.12])
    d = (Vector(ch[2]) - Vector(ch[1])).normalized()
    revolve_m(p, BRASS, [(-0.05, 0.0), (-0.05, 0.1), (0.02, 0.11), (0.08, 0.15), (0.11, 0.15), (0.11, 0.0)],
              seg=16, M=ah.orient(Vector(ch[2]), d))
    revolve_m(p, BRASS, [(-0.03, 0.0), (-0.03, 0.11), (0.03, 0.11), (0.03, 0.0)], seg=16,
              M=ah.orient(Vector(ch[1]), d))
    # duct ring (brass, copper mid band) + 4 struts in front of the blades
    duct = [(3.39, 1.085), (3.355, 1.105), (3.35, 1.14), (3.37, 1.17), (3.42, 1.185), (3.5, 1.19), (3.6, 1.19),
            (3.68, 1.185), (3.73, 1.17), (3.75, 1.14), (3.745, 1.105), (3.71, 1.085)]

    def dmat(i, j):
        return COPPER if i in (5,) else BRASS
    revolve_y(p, BRASS, duct, seg=44, cz=cz, closed=True, mat_fn=dmat)
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        r0, r1 = 0.13, 1.1
        tube(p, BRASS_D, [(math.sin(a) * r0, Y_HUB - 0.24, cz - math.cos(a) * r0),
                          (math.sin(a) * r1, 3.37, cz - math.cos(a) * r1)], 0.026, seg=8)


# ---------------------------------------------------------------------------
# propeller (pivot at the hub, spins about local Y)
# ---------------------------------------------------------------------------
N_BLADES = 5
BLADE_R = 0.99


def build_propeller(parent):
    p = Part("propeller")
    # spinner + back plate + shaft
    revolve_y(p, BRASS, [(-0.09, 0.0), (-0.09, 0.15), (-0.06, 0.18), (0.03, 0.18), (0.07, 0.165), (0.13, 0.14),
                         (0.2, 0.1), (0.26, 0.055), (0.3, 0.0)], seg=24)
    revolve_y(p, IRON, [(-0.27, 0.0), (-0.27, 0.055), (-0.08, 0.055), (-0.08, 0.0)], seg=12)
    pitch = 1.6
    ns = 12
    for k in range(N_BLADES):
        a = 2 * math.pi * k / N_BLADES + math.radians(18)
        er = Vector((math.sin(a), 0.0, math.cos(a)))
        em = Vector((-math.cos(a), 0.0, math.sin(a)))     # direction of motion (rotation about -Y)
        rows = []
        for i in range(ns + 1):
            s = i / ns
            s = 1 - (1 - s) ** 1.25
            rho = 0.1 + (BLADE_R - 0.1) * s
            if s < 0.45:
                c = 0.075 + 0.2 * smoothstep(0.02, 0.45, s)
            else:
                c = 0.275 * math.sqrt(max(0.0, 1 - ((s - 0.45) / 0.55) ** 2))
            c = max(c, 0.035)
            th = 0.06 * (1 - s) + 0.014
            beta = math.atan(pitch / (2 * math.pi * max(rho, 0.15)))
            sw = 0.13 * s * s
            dc = em * math.cos(beta) - Vector((0, 1, 0)) * math.sin(beta)
            dn = em * math.sin(beta) + Vector((0, 1, 0)) * math.cos(beta)
            sec = []
            m = 5
            for q in range(m + 1):                          # LE -> TE upper (forward face)
                u = 0.5 * math.cos(math.pi * q / m)
                h = 0.5 * th * max(0.1, 1 - (2 * u) ** 2) ** 0.6
                sec.append((u, -h - 0.15 * th))
            for q in range(m - 1, 0, -1):                   # TE -> LE lower
                u = 0.5 * math.cos(math.pi * q / m)
                h = 0.5 * th * max(0.1, 1 - (2 * u) ** 2) ** 0.6
                sec.append((u, h * 0.75 - 0.15 * th))
            row = []
            for (u, v) in sec:
                pt = er * rho - em * sw + dc * (u * c) + dn * v
                row.append(tuple(pt))
            rows.append(row)

        def bm_(i, j, ns=ns):
            return BRASS if (i >= ns - 2 or i < 1) else WOOD
        add_grid(p, rows, WOOD, closed_u=True, cap0=BRASS, cap1=BRASS, mat_fn=bm_)
    return p.build(parent, loc=(0.0, Y_HUB, Z_HUB))


# ---------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------

def hull_info():
    rope_pts = (-2.15, -1.05, 0.05, 1.15, 2.05)

    def rail_at(y, side):
        t = min(max(t_of_y(y), 0.0), 1.0)
        return rail_line(t, side) + Vector((0, 0, 0.03))
    return {"rope_pts": rope_pts, "rail_at": rail_at}


def _gore_tint(p, n):
    """Vertex-colour multiplier: envelope fabric darkens toward each seam (painted pillow shading that
    keeps the gores readable from far away); fades out under the brass bands. Everything else: 1."""
    if not (Y_NOSE < p.y < Y_TAIL):
        return (1.0, 1.0, 1.0)
    dx, dz = p.x, p.z - ENV_Z
    th = math.atan2(dx, -dz)
    if abs(math.hypot(dx, dz) - env_r(p.y, th)) > 0.004:
        return (1.0, 1.0, 1.0)
    g = (th - TH0) / (2 * math.pi / GORES)
    u = g - math.floor(g)
    k = 0.8 + 0.2 * gore_bulge(u)
    k = 1.0 - (1.0 - k) * (1.0 - band_k(p.y, 0.17))
    return (k, k, k)


def build_airship():
    root = empty("prop_airship", size=0.5)
    info = hull_info()
    env = build_envelope(root)
    rig = build_rigging(root, info)
    fins = build_fins(root)
    gon = build_gondola(root)
    prop = build_propeller(root)

    # finishing: bevel hard-surface bits (bevel weights), smooth + sharp edges
    hp.smooth_obj(gon, angle=46)
    hp.bevel_obj(gon, width=0.016, segments=2, limit="WEIGHT", harden=True)
    hp.smooth_obj(gon, angle=46)
    hp.smooth_obj(env, angle=40)
    hp.smooth_obj(rig, angle=80)
    hp.smooth_obj(fins, angle=50)
    hp.smooth_obj(prop, angle=50)
    ah.join_objects([env, rig, fins, gon], "prop_airship_body")
    if os.environ.get("AIR_FAST"):
        hp.fill_vertex_color(hp.tree_meshes(root))
    else:
        hp.bake_tree_ao(root, ground=None, distance=0.8, samples=32, strength=0.85, floor=0.3, tint=_gore_tint)
    return root


# name, builder, preview kwargs (passed to hp.render_hp)
PROPS = [
    ("prop_airship", build_airship, dict(elevation=12)),
]

# triangle budget per prop (user-chosen "medium" tier, 2026-10-11)
BUDGET = {
    "prop_airship": 40000,
}
