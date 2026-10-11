"""Lamp Wisp — floating magical enemy. Exports public/models/wisp.glb.

root (ground) > lantern (z = 1.3) > {flame, ring_A, ring_B_tilt > ring_B, wing_L, wing_R}
ring_A / ring_B spin around their local Z. ring_B's 60 deg tilt lives in the parent empty ring_B_tilt.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from char_helpers import *

reset_scene()
get_mat("jelly_glass", hex="#cfeef5", metallic=0.1, roughness=0.05, alpha=0.25)   # translucent panes
root = empty("root")

LANTERN_Z = 1.3
R_HEX = 0.16                  # lantern corner radius

# ---- lantern ------------------------------------------------------------------
p = Part("lantern")
loft(p, "brass", [(-0.27, 0.42, 0.42), (-0.21, 0.40, 0.40), (-0.19, 0.34, 0.34)], shape=6, phase=0.0)
loft(p, "brass_dark", [(-0.40, 0.0, 0.0), (-0.31, 0.12, 0.12), (-0.27, 0.30, 0.30)], shape=6, phase=0.0)
gem(p, "glow_amber", r=0.03, up=0.02, down=0.06, seg=5, loc=(0, 0, -0.41))            # drip of light
for k in range(6):
    a = math.radians(60 * k)
    p.box("brass_dark", size=(0.035, 0.035, 0.40), loc=(math.cos(a) * R_HEX, math.sin(a) * R_HEX, 0.0),
          rot=(0, 0, 60 * k))
    am = math.radians(60 * k + 30)
    ri = R_HEX * math.cos(math.radians(30))
    p.box("jelly_glass", size=(0.012, R_HEX, 0.36), loc=(math.cos(am) * ri, math.sin(am) * ri, 0.0),
          rot=(0, 0, 60 * k + 30))
loft(p, "brass", [(0.18, 0.38, 0.38), (0.22, 0.42, 0.42), (0.25, 0.40, 0.40), (0.36, 0.08, 0.08)],
     shape=6, phase=0.0)                                                                  # roof
p.cyl("brass_dark", r=0.035, h=0.05, seg=6, loc=(0, 0, 0.38))
p.torus("brass", R=0.06, r=0.014, seg=8, seg2=4, loc=(0, 0, 0.46), rot=(90, 0, 0))     # handle
lantern = p.build(root, loc=(0, 0, LANTERN_Z))

# ---- flame (living, with little eyes) -----------------------------------------------
p = Part("flame")
gem(p, "glow_amber", r=0.105, up=0.20, down=0.08, seg=6, mid=0.04, loc=(0, 0, -0.06))
gem(p, "glow_white", r=0.05, up=0.10, down=0.05, seg=5, loc=(0, 0, -0.06))
for s in (1, -1):
    p.box("black", size=(0.028, 0.03, 0.055), loc=(s * 0.038, -0.088, -0.04))
flame = p.build(lantern, loc=(0, 0, 0))

# ---- rings ----------------------------------------------------------------------
def ring(name, parent, R):
    p = Part(name)
    p.torus("brass", R=R, r=0.014, seg=20, seg2=4)
    for k in range(3):
        a = math.radians(120 * k)
        gem(p, "glow_amber" if k == 0 else "brass_dark", r=0.026, up=0.026, seg=4,
            loc=(math.cos(a) * R, math.sin(a) * R, 0))
    return p.build(parent, loc=(0, 0, 0))

ring_A = ring("ring_A", lantern, 0.30)
ring_A.location = (0, 0, -0.10)
tilt = empty("ring_B_tilt", parent=lantern, loc=(0, 0, 0.0))
tilt.rotation_euler = (math.radians(60), 0, 0)
ring_B = ring("ring_B", tilt, 0.37)

# ---- gear wings -------------------------------------------------------------------
def make_wing(name, s):
    p = Part(name)
    p.cyl("brass_dark", r=0.03, h=0.06, seg=6, loc=(s * 0.02, 0, 0), rot=(0, 90, 0))
    tube(p, "brass", [(0, 0, 0), (s * 0.12, 0.0, 0.06), (s * 0.26, 0.0, 0.20)], r=0.016, seg=4)
    # copper fins (feathers) behind the gears
    for k, (ang, ln) in enumerate(((20, 0.34), (45, 0.30), (70, 0.22))):
        a = math.radians(ang)
        tip = (s * math.cos(a) * ln, 0.035, math.sin(a) * ln + 0.02)
        prism(p, "copper", [(s * 0.05, 0.02), (tip[0] - s * 0.03, tip[2] + 0.03), (tip[0] + s * 0.02, tip[2]),
                            (s * 0.09, 0.0)], 0.012, loc=(0, 0.035, 0), axis="y")
    p.gear("brass", r=0.085, thickness=0.025, teeth=8, tooth=0.03, hole=0.05,
           loc=(s * 0.15, -0.005, 0.10), rot=(90, 0, 0))
    p.cyl("brass_dark", r=0.02, h=0.04, seg=6, loc=(s * 0.15, -0.005, 0.10), rot=(90, 0, 0))
    sgear(p, "brass_dark", r=0.06, teeth=7, thick=0.022, loc=(s * 0.27, -0.005, 0.22), rot=(90, 0, 0))
    p.cyl("glow_amber", r=0.015, h=0.03, seg=6, loc=(s * 0.27, -0.01, 0.22), rot=(90, 0, 0))
    sgear(p, "brass", r=0.04, teeth=6, thick=0.02, loc=(s * 0.30, -0.005, 0.07), rot=(90, 0, 0))
    return p.build(lantern, loc=(s * (R_HEX + 0.02), 0.03, 0.08))

wing_L = make_wing("wing_L", 1)
wing_R = make_wing("wing_R", -1)

finish("wisp")
render_view("wisp_lantern", (0, 0, 1.3), 0.45, azimuth=0, elevation=5)
