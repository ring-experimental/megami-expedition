"""Geometry helpers for the steam-works props (props_steam.py) (hi-poly).

Own module: the shared helper modules (common / env_helpers / hp_helpers ...) are read-only.
Everything here adds geometry straight into a common.Part's bmesh (same idea as env_helpers), so a
prop stays a handful of meshes with few materials:

    place(loc, n, spin)      4x4 frame whose local +Z points along n (mount anything on any surface)
    revolve(...)             lathe a (z, r) profile around local Z: per-span materials, flutes (rfunc),
                             closed profiles (hollow rings, thick-walled pipes with open ends)
    prism(...)               extrude a 2D outline with a real 45 deg chamfer on both faces
    ring_prism(...)          same with a hole (gear rims, washers, frames) — outer/inner chamfers
    gear_outline(...)        tooth outline (convex flanks, flat tips) for ring_prism / prism
    sweep(...)               sweep any 2D section along a 3D polyline (tubes, flat-bar scrolls, straps)
    hex_bolt / rivet / ball / torus_m   fasteners & small round parts
    moss_pad / lumpy_blob / rubble      organic, noise-displaced shapes

Chamfers are modelled, not bevel-modifier generated: cheap, predictable triangle counts and crisp
45 deg highlight strips once hp_helpers.smooth_obj(angle=35) marks them sharp.
"""
import math

from mathutils import Matrix, Vector, noise

from env_helpers import set_mat

TAU = 2.0 * math.pi
I4 = Matrix.Identity(4)


# ---------------------------------------------------------------------------
# frames / matrices
# ---------------------------------------------------------------------------

def frame_z(n, ref=None):
    """3x3 rotation whose columns are (x, y, z) with z = n. x is horizontal when possible, so local
    +Y points 'up' for wall-mounted parts."""
    z = Vector(n).normalized()
    if ref is None:
        ref = Vector((0, 0, 1)) if abs(z.z) < 0.9 else Vector((0, -1, 0))
    x = Vector(ref).cross(z)
    if x.length < 1e-6:
        x = Vector((1, 0, 0)).cross(z) if abs(z.x) < 0.9 else Vector((0, 1, 0)).cross(z)
    x.normalize()
    y = z.cross(x)
    m = Matrix.Identity(3)
    m.col[0] = x
    m.col[1] = y
    m.col[2] = z
    return m


def place(loc=(0, 0, 0), n=(0, 0, 1), spin=0.0, ref=None, scale=None):
    """Translation(loc) @ frame(local Z -> n) @ spin about local Z (radians) @ scale."""
    M = Matrix.Translation(Vector(loc)) @ frame_z(n, ref).to_4x4()
    if spin:
        M = M @ Matrix.Rotation(spin, 4, "Z")
    if scale is not None:
        s = (scale,) * 3 if isinstance(scale, (int, float)) else tuple(scale)
        M = M @ Matrix.Diagonal((*s, 1.0))
    return M


def T(x=0.0, y=0.0, z=0.0):
    return Matrix.Translation(Vector((x, y, z)))


def Rot(axis, deg):
    return Matrix.Rotation(math.radians(deg), 4, axis)


def S(x, y=None, z=None):
    y = x if y is None else y
    z = x if z is None else z
    return Matrix.Diagonal((x, y, z, 1.0))


def axis_x(loc=(0, 0, 0)):
    """local Z -> world +X (local X -> world -Z)."""
    return T(*loc) @ Rot("Y", 90)


def axis_y(loc=(0, 0, 0)):
    """local Z -> world +Y (local Y -> world -Z)."""
    return T(*loc) @ Rot("X", -90)


def axis_my(loc=(0, 0, 0)):
    """local Z -> world -Y (front-facing discs, local Y -> world +Z)."""
    return T(*loc) @ Rot("X", 90)


# ---------------------------------------------------------------------------
# noise
# ---------------------------------------------------------------------------

def fbm(p, seed=0, octaves=3):
    off = Vector((seed * 17.31 + 3.1, seed * 9.73 - 7.7, seed * 3.17 + 1.3))
    p = Vector(p)
    s, a, f, norm = 0.0, 1.0, 1.0, 0.0
    for _ in range(octaves):
        s += a * noise.noise((p + off) * f)
        norm += a
        a *= 0.5
        f *= 2.03
    return s / norm


def noise_vec(p, seed=0, octaves=2):
    return Vector((fbm(p, seed, octaves), fbm(p, seed + 11, octaves), fbm(p, seed + 23, octaves)))


def smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------------------
# lathe
# ---------------------------------------------------------------------------

def revolve(part, profile, seg=24, M=I4, mats="iron", phase=0.0, cap_bottom=True, cap_top=True,
            closed=False, rfunc=None, cap_mat=None):
    """Revolve [(z, r), ...] around local Z (bottom -> top). r == 0 -> pole vertex.
    mats: one material name, or one per span (len(profile) - 1, or len(profile) when closed).
    closed=True connects the last point back to the first (hollow rings / thick pipes).
    rfunc(angle, z) -> radius multiplier (flutes, panels)."""
    bm = part.bm
    n = len(profile)
    spans = n if closed else n - 1
    if isinstance(mats, str):
        mats = [mats] * spans
    rings = []
    for z, r in profile:
        if r <= 1e-7:
            rings.append([bm.verts.new(M @ Vector((0.0, 0.0, z)))])
            continue
        ring = []
        for j in range(seg):
            a = TAU * j / seg + phase
            k = rfunc(a, z) if rfunc else 1.0
            ring.append(bm.verts.new(M @ Vector((r * k * math.cos(a), r * k * math.sin(a), z))))
        rings.append(ring)
    for i in range(spans):
        a, b = rings[i], rings[(i + 1) % n]
        fs = []
        if len(a) == 1 and len(b) == 1:
            continue
        for j in range(seg):
            k = (j + 1) % seg
            if len(a) == 1:
                fs.append(bm.faces.new((a[0], b[k], b[j])))
            elif len(b) == 1:
                fs.append(bm.faces.new((a[j], a[k], b[0])))
            else:
                fs.append(bm.faces.new((a[j], a[k], b[k], b[j])))
        set_mat(part, fs, mats[i])
    if not closed:
        if cap_bottom and len(rings[0]) > 1:
            set_mat(part, [bm.faces.new(list(reversed(rings[0])))], cap_mat or mats[0])
        if cap_top and len(rings[-1]) > 1:
            set_mat(part, [bm.faces.new(rings[-1])], cap_mat or mats[-1])
    return rings


def torus_m(part, mat, R, r, seg=24, seg2=8, M=I4, phase2=0.0, phase=0.0):
    prof = [(r * math.sin(TAU * j / seg2 + phase2), R + r * math.cos(TAU * j / seg2 + phase2))
            for j in range(seg2)]
    return revolve(part, prof, seg=seg, M=M, mats=mat, closed=True, phase=phase)


def ball(part, mat, r, seg=12, rings=6, M=I4, squash=1.0):
    prof = [(-r * squash * math.cos(math.pi * i / rings), r * math.sin(math.pi * i / rings))
            for i in range(rings + 1)]
    return revolve(part, prof, seg=seg, M=M, mats=mat)


def band(part, mat, z0, z1, r_out, r_in, ch=0.0, seg=24, M=I4, phase=0.0):
    """Hollow ring (collar / flange band) between z0..z1, chamfered outer edges."""
    if ch > 0:
        prof = [(z0, r_in), (z0, r_out - ch), (z0 + ch, r_out), (z1 - ch, r_out), (z1, r_out - ch), (z1, r_in)]
    else:
        prof = [(z0, r_in), (z0, r_out), (z1, r_out), (z1, r_in)]
    return revolve(part, prof, seg=seg, M=M, mats=mat, closed=True, phase=phase)


# ---------------------------------------------------------------------------
# outlines / chamfered extrusions
# ---------------------------------------------------------------------------

def rrect(w, h, r=0.0, n=2, cx=0.0, cy=0.0):
    """Rounded rectangle outline, CCW. n = segments per corner (1 = chamfered corner)."""
    if r <= 0:
        return [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)]
    pts = []
    for ccx, ccy, a0 in ((w / 2 - r, -h / 2 + r, -90), (w / 2 - r, h / 2 - r, 0),
                         (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180)):
        for i in range(n + 1):
            a = math.radians(a0 + 90.0 * i / n)
            pts.append((cx + ccx + r * math.cos(a), cy + ccy + r * math.sin(a)))
    return pts


def circle_pts(r, seg, phase=0.0, cx=0.0, cy=0.0):
    return [(cx + r * math.cos(TAU * j / seg + phase), cy + r * math.sin(TAU * j / seg + phase)) for j in range(seg)]


def offset_outline(pts, d, limit=3.0):
    """Offset a closed CCW 2D outline by d along its outward normal (d < 0 -> inward). Mitred."""
    n = len(pts)
    P = [Vector((x, y)) for x, y in pts]
    out = []
    for i in range(n):
        a, b, c = P[i - 1], P[i], P[(i + 1) % n]
        e1, e2 = b - a, c - b
        if e1.length < 1e-9 or e2.length < 1e-9:
            out.append(b.copy())
            continue
        e1.normalize()
        e2.normalize()
        n1 = Vector((e1.y, -e1.x))
        n2 = Vector((e2.y, -e2.x))
        m = n1 + n2
        if m.length < 1e-6:
            m = n1.copy()
        m.normalize()
        k = d / max(1.0 / limit, m.dot(n1))
        out.append(b + m * k)
    return [(v.x, v.y) for v in out]


def _loop(bm, M, pts, z):
    return [bm.verts.new(M @ Vector((x, y, z))) for x, y in pts]


def _strip(bm, a, b, closed=True):
    n = len(a)
    fs = []
    for i in range(n if closed else n - 1):
        k = (i + 1) % n
        fs.append(bm.faces.new((a[i], a[k], b[k], b[i])))
    return fs


def prism(part, mat, outline, depth, ch=0.0, M=I4, side_mat=None, face_mat=None, back_ch=None,
          jitter=0.0, seed=0, jitter_freq=3.0, cap_back=True):
    """Extrude a CCW 2D outline (local XY) along local Z (centred, -depth/2 .. +depth/2) with a 45 deg
    chamfer `ch` on the front (-Z) face and `back_ch` (default ch) on the back face.
    jitter: coherent noise displacement (chunky stone)."""
    bm = part.bm
    fch = ch
    bch = ch if back_ch is None else back_ch
    d2 = depth / 2
    loops = []
    if fch > 0:
        loops.append(_loop(bm, M, offset_outline(outline, -fch), -d2))
        loops.append(_loop(bm, M, outline, -d2 + fch))
    else:
        loops.append(_loop(bm, M, outline, -d2))
    if bch > 0:
        loops.append(_loop(bm, M, outline, d2 - bch))
        loops.append(_loop(bm, M, offset_outline(outline, -bch), d2))
    else:
        loops.append(_loop(bm, M, outline, d2))
    sides = []
    for a, b in zip(loops[:-1], loops[1:]):
        sides += _strip(bm, a, b)
    caps = [bm.faces.new(list(reversed(loops[0])))]
    if cap_back:
        caps.append(bm.faces.new(loops[-1]))
    set_mat(part, sides, side_mat or mat)
    set_mat(part, caps, face_mat or mat)
    if jitter:
        for lp in loops:
            for v in lp:
                v.co += noise_vec(v.co * jitter_freq, seed) * jitter
    return loops


def ring_prism(part, mat, outer, inner, depth, ch=0.0, ch_in=None, M=I4, side_mat=None, inner_mat=None,
               face_mat=None, mid=None):
    """Extruded ring between two CCW outlines with the same point count (gear rims, frames).
    Chamfer `ch` on the outer edges, `ch_in` on the hole edges, both faces.
    mid: optional outline (same count) inserted as an extra loop on both faces (vertex-colour resolution)."""
    bm = part.bm
    ch_in = ch if ch_in is None else ch_in
    d2 = depth / 2
    if ch > 0:
        oi = offset_outline(outer, -ch)
        O = [_loop(bm, M, oi, -d2), _loop(bm, M, outer, -d2 + ch), _loop(bm, M, outer, d2 - ch), _loop(bm, M, oi, d2)]
    else:
        O = [_loop(bm, M, outer, -d2), _loop(bm, M, outer, d2)]
    if ch_in > 0:
        ii = offset_outline(inner, ch_in)
        I = [_loop(bm, M, ii, -d2), _loop(bm, M, inner, -d2 + ch_in), _loop(bm, M, inner, d2 - ch_in),
             _loop(bm, M, ii, d2)]
    else:
        I = [_loop(bm, M, inner, -d2), _loop(bm, M, inner, d2)]
    so, si = [], []
    for a, b in zip(O[:-1], O[1:]):
        so += _strip(bm, a, b)
    for a, b in zip(I[:-1], I[1:]):
        si += _strip(bm, b, a)
    if mid:
        mf, mb = _loop(bm, M, mid, -d2), _loop(bm, M, mid, d2)
        faces = _strip(bm, I[0], mf) + _strip(bm, mf, O[0]) + _strip(bm, O[-1], mb) + _strip(bm, mb, I[-1])
    else:
        faces = _strip(bm, I[0], O[0]) + _strip(bm, O[-1], I[-1])
    set_mat(part, so, side_mat or mat)
    set_mat(part, si, inner_mat or side_mat or mat)
    set_mat(part, faces, face_mat or mat)
    return O, I


def gear_outline(r_root, r_tip, teeth, base=0.55, top=0.3, phase=0.0, bulge=0.38, gap_mid=True):
    """Gear tooth outline, CCW. Returns (pts, angles). Tooth centre i at phase + i * 2pi/teeth.
    base/top: tooth width as a fraction of the pitch at root / tip. bulge < 0.5 -> convex flanks."""
    P = TAU / teeth
    wb, wt = base * P / 2, top * P / 2
    wm = wb + (wt - wb) * bulge
    rm = r_root + (r_tip - r_root) * 0.5
    pts, angs = [], []
    for i in range(teeth):
        c = phase + i * P
        seq = [(c - wb, r_root), (c - wm, rm), (c - wt, r_tip), (c + wt, r_tip), (c + wm, rm), (c + wb, r_root)]
        if gap_mid:
            seq.append((c + P / 2, r_root))
        for a, r in seq:
            pts.append((r * math.cos(a), r * math.sin(a)))
            angs.append(a)
    return pts, angs


def at_angles(angs, r):
    return [(r * math.cos(a), r * math.sin(a)) for a in angs]


def gear(part, mat, r_root, r_tip, teeth, thick, r_in, ch=0.004, ch_in=None, M=I4, phase=0.0,
         base=0.55, top=0.3, spokes=0, spoke_w=None, hub_r=None, hub_len=None, hub_mat=None, gap_mid=True,
         spoke_mat=None):
    """Complete small gear in local XY (axis local Z): toothed rim (ring_prism), straight spokes, hub."""
    out, angs = gear_outline(r_root, r_tip, teeth, base=base, top=top, phase=phase, gap_mid=gap_mid)
    ring_prism(part, mat, out, at_angles(angs, r_in), thick, ch=ch, ch_in=ch if ch_in is None else ch_in, M=M)
    if spokes:
        hub_r = hub_r or r_in * 0.35
        spoke_w = spoke_w or r_in * 0.28
        for i in range(spokes):
            a = phase + TAU * i / spokes + (TAU / teeth) / 2
            L = r_in + 0.004 - hub_r * 0.6
            mid = hub_r * 0.6 + L / 2
            Ms = M @ T(mid * math.cos(a), mid * math.sin(a), 0) @ Matrix.Rotation(a, 4, "Z")
            prism(part, spoke_mat or mat, rrect(L, spoke_w, spoke_w * 0.25, 1), thick * 0.7,
                  ch=min(ch, thick * 0.15), M=Ms)
        hl = hub_len or thick * 1.6
        revolve(part, [(-hl / 2, hub_r * 0.9), (-hl / 2 + hub_r * 0.1, hub_r), (hl / 2 - hub_r * 0.1, hub_r),
                       (hl / 2, hub_r * 0.9)], seg=12, M=M, mats=hub_mat or mat)
    return out


# ---------------------------------------------------------------------------
# sweeps
# ---------------------------------------------------------------------------

def path_frames(pts, up=None):
    """Parallel-transport frames [(p, tangent, normal, binormal)] along a polyline."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    tans = []
    for i in range(n):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = (pts[i + 1] - pts[i]).normalized() + (pts[i] - pts[i - 1]).normalized()
        tans.append(t.normalized())
    t0 = tans[0]
    if up is not None:
        u = Vector(up)
        nrm = u - t0 * u.dot(t0)
    else:
        ref = Vector((0, 1, 0)) if abs(t0.y) < 0.9 else Vector((1, 0, 0))
        nrm = ref.cross(t0)
    nrm.normalize()
    frames = []
    for i in range(n):
        if i > 0:
            ax = tans[i - 1].cross(tans[i])
            if ax.length > 1e-9:
                ang = tans[i - 1].angle(tans[i])
                nrm = Matrix.Rotation(ang, 3, ax.normalized()) @ nrm
            nrm = (nrm - tans[i] * nrm.dot(tans[i])).normalized()
        frames.append((pts[i], tans[i], nrm, tans[i].cross(nrm)))
    return frames


def circle_sec(r, seg, phase=None):
    ph = (math.pi / seg) if phase is None else phase
    return [(r * math.cos(TAU * j / seg + ph), r * math.sin(TAU * j / seg + ph)) for j in range(seg)]


def sweep(part, mat, pts, section, scales=None, up=None, cap_start=True, cap_end=True, mats=None):
    """Sweep a closed 2D section [(u, v)] (u along the frame normal, v along the binormal) along pts.
    scales: per-point float or (su, sv). mats: per-segment material list. Returns the rings.
    Use enough points on bends (no mitring)."""
    frames = path_frames(pts, up)
    bm = part.bm
    rings = []
    for i, (p, t, nr, bi) in enumerate(frames):
        s = scales[i] if scales else 1.0
        su, sv = (s, s) if isinstance(s, (int, float)) else s
        rings.append([bm.verts.new(p + nr * (u * su) + bi * (v * sv)) for u, v in section])
    for i in range(len(rings) - 1):
        set_mat(part, _strip(bm, rings[i], rings[i + 1]), mats[i] if mats else mat)
    if cap_start:
        set_mat(part, [bm.faces.new(list(reversed(rings[0])))], mats[0] if mats else mat)
    if cap_end:
        set_mat(part, [bm.faces.new(rings[-1])], mats[-1] if mats else mat)
    return rings


def tube(part, mat, pts, r, seg=12, **kw):
    return sweep(part, mat, pts, circle_sec(r, seg), **kw)


def bezier(p0, p1, p2, p3, n):
    out = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        out.append(tuple(mt ** 3 * a + 3 * mt * mt * t * b + 3 * mt * t * t * c + t ** 3 * d
                         for a, b, c, d in zip(p0, p1, p2, p3)))
    return out


def spiral(center, r0, r1, a0, a1, n, plane="XZ"):
    """Points on a planar spiral (degrees), radius r0 -> r1."""
    out = []
    for i in range(n + 1):
        t = i / n
        a = math.radians(a0 + (a1 - a0) * t)
        r = r0 + (r1 - r0) * t
        c, s = math.cos(a) * r, math.sin(a) * r
        if plane == "XZ":
            out.append((center[0] + c, center[1], center[2] + s))
        elif plane == "XY":
            out.append((center[0] + c, center[1] + s, center[2]))
        else:
            out.append((center[0], center[1] + c, center[2] + s))
    return out


def arc(center, radius, a0, a1, n, plane="XZ"):
    return spiral(center, radius, radius, a0, a1, n, plane)


# ---------------------------------------------------------------------------
# fasteners
# ---------------------------------------------------------------------------

def hex_bolt(part, mat, M, r=0.03, h=0.03, washer=0.0, wmat=None, stub=False, seg_w=8, chamfer=True):
    """Hex bolt head / nut sitting on the local z = 0 plane, axis +Z (build M with place()).
    chamfer=False -> plain hex prism (16 tris) for bolts that are only a few pixels in game."""
    z0 = 0.0
    if washer > 0:
        revolve(part, [(-0.003, r * washer), (h * 0.22, r * washer)], seg=seg_w, M=M, mats=wmat or mat,
                cap_bottom=False)
        z0 = h * 0.22
    prof = [(z0 - 0.002, r), (z0 + h * 0.68, r), (z0 + h, r * 0.78)] if chamfer else [(z0 - 0.002, r), (z0 + h, r)]
    revolve(part, prof, seg=6, M=M, mats=mat, phase=math.pi / 6, cap_bottom=False)
    if stub:
        revolve(part, [(z0 + h - 0.002, r * 0.48), (z0 + h + r * 0.6, r * 0.48)], seg=6, M=M, mats=mat,
                cap_bottom=False)


def rivet(part, mat, M, r=0.02, seg=6):
    revolve(part, [(-0.003, r), (r * 0.38, r * 0.78), (r * 0.58, 0.0)], seg=seg, M=M, mats=mat, cap_bottom=False)


def stub_end(part, mat, M, r=0.012, h=0.025, seg=6):
    revolve(part, [(-0.003, r), (h * 0.75, r), (h, r * 0.7)], seg=seg, M=M, mats=mat, cap_bottom=False)


# ---------------------------------------------------------------------------
# organic
# ---------------------------------------------------------------------------

def moss_pad(part, mat, center, rx, ry, h=0.05, seg=14, rings=3, seed=0, droop=0.03, rot=0.0, lump=0.25,
             zfunc=None):
    """Closed lens-shaped moss/soil pad lying on a surface at center.z (top bulges up by h, the rim
    tucks `droop` below the surface). zfunc(x, y) -> surface z overrides center.z per vertex."""
    bm = part.bm
    cx, cy, cz = center
    cr, sr = math.cos(rot), math.sin(rot)
    top = bm.verts.new((cx, cy, (zfunc(cx, cy) if zfunc else cz) + h))
    rings_v = []
    for k in range(1, rings + 1):
        t = k / rings
        ring = []
        for j in range(seg):
            a = TAU * j / seg
            q = Vector((math.cos(a) * 1.3, math.sin(a) * 1.3, seed * 0.37))
            w = 1.0 + lump * fbm(q, seed)
            lx, ly = math.cos(a) * rx * t * w, math.sin(a) * ry * t * w
            x, y = cx + lx * cr - ly * sr, cy + lx * sr + ly * cr
            base = zfunc(x, y) if zfunc else cz
            if k == rings:
                z = base - droop
            else:
                z = base + h * (1 - t * t) * (1.0 + 0.35 * fbm(Vector((x, y, 0.0)) * 3.0, seed + 5))
            ring.append(bm.verts.new((x, y, z)))
        rings_v.append(ring)
    fs = []
    r0 = rings_v[0]
    for j in range(seg):
        fs.append(bm.faces.new((top, r0[j], r0[(j + 1) % seg])))
    for a, b in zip(rings_v[:-1], rings_v[1:]):
        fs += _strip(bm, a, b)
    fs.append(bm.faces.new(list(reversed(rings_v[-1]))))
    set_mat(part, fs, mat)
    return fs


def lumpy_blob(part, mat, center, size, seg=24, rings=12, amp=0.12, freq=1.6, seed=0, floor=None,
               top_mat=None, top_thresh=0.55):
    """UV sphere scaled to `size` (radii) with coherent radial noise; floor clamps z."""
    bm = part.bm
    c = Vector(center)
    verts_rows = []
    for i in range(rings + 1):
        th = math.pi * i / rings
        if i == 0 or i == rings:
            z = -math.cos(th)
            d = Vector((0, 0, z))
            p = c + Vector((0, 0, z * size[2]))
            p += d * amp * fbm(p * freq, seed) * size[2]
            if floor is not None:
                p.z = max(p.z, floor)
            verts_rows.append([bm.verts.new(p)])
            continue
        row = []
        for j in range(seg):
            ph = TAU * j / seg
            d = Vector((math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), -math.cos(th)))
            p = c + Vector((d.x * size[0], d.y * size[1], d.z * size[2]))
            m = amp * fbm(p * freq, seed)
            p += Vector((d.x * size[0], d.y * size[1], d.z * size[2])).normalized() * m * min(size)
            if floor is not None:
                p.z = max(p.z, floor)
            row.append(bm.verts.new(p))
        verts_rows.append(row)
    fs = []
    for a, b in zip(verts_rows[:-1], verts_rows[1:]):
        if len(a) == 1:
            for j in range(seg):
                fs.append(bm.faces.new((a[0], b[(j + 1) % seg], b[j])))
        elif len(b) == 1:
            for j in range(seg):
                fs.append(bm.faces.new((a[j], a[(j + 1) % seg], b[0])))
        else:
            fs += _strip(bm, a, b)
    set_mat(part, fs, mat)
    if top_mat:
        top = []
        for f in fs:
            f.normal_update()
            if f.normal.z > top_thresh:
                top.append(f)
        set_mat(part, top, top_mat)
    return fs


def rubble(part, mat, center, size, seed=0, ch=0.025, rot=0.0, tilt=(0.0, 0.0), sides=6, jitter=0.03):
    """Chunky broken stone: irregular polygon prism, chamfered, noise-jittered, tilted."""
    rnd_pts = []
    for j in range(sides):
        a = TAU * j / sides + 0.4 * fbm(Vector((j * 0.7, seed * 0.31, 0.5)), seed)
        rr = 1.0 + 0.28 * fbm(Vector((j * 1.3, seed * 0.17, 2.0)), seed + 3)
        rnd_pts.append((math.cos(a) * size[0] * 0.5 * rr, math.sin(a) * size[1] * 0.5 * rr))
    M = (T(*center) @ Rot("Z", math.degrees(rot)) @ Rot("X", tilt[0]) @ Rot("Y", tilt[1]))
    return prism(part, mat, rnd_pts, size[2], ch=ch, M=M, jitter=jitter, seed=seed)


def cull_faces(obj, keep):
    """Delete faces of a built mesh object for which keep(world_centre, world_verts) is False (geometry
    buried inside other parts / under the ground). Returns the number of faces removed."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    mw = obj.matrix_world
    dead = [f for f in bm.faces if not keep(mw @ f.calc_center_median(), [mw @ v.co for v in f.verts])]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return len(dead)


def paint_faces(obj, mat_from, mat_to, pred):
    """Re-assign faces of a built mesh from material `mat_from` to `mat_to` where
    pred(world_centre, world_normal) is True (verdigris / stains in irregular patches, no extra tris)."""
    from common import get_mat
    me = obj.data
    names = [m.name if m else "" for m in me.materials]
    if mat_from not in names:
        return 0
    src = names.index(mat_from)
    if mat_to not in names:
        me.materials.append(get_mat(mat_to))
        names.append(mat_to)
    dst = names.index(mat_to)
    mw = obj.matrix_world
    nm = mw.to_3x3().inverted_safe().transposed()
    n = 0
    for p in me.polygons:
        if p.material_index == src and pred(mw @ p.center, (nm @ p.normal).normalized()):
            p.material_index = dst
            n += 1
    me.update()
    return n
