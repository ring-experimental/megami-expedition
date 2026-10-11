"""Boiler Jelly — weak slime enemy (~0.7 m tall). Exports public/models/slime.glb.

root > body (pivot at ground centre; scaled for squash & stretch) > {valve, eye_L, eye_R}
Translucent jelly_teal dome with a glow_cyan core, brass boiler valve on top, brass gauge eyes.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from char_helpers import *

reset_scene()
root = empty("root")

TOP = 0.60
# dome profile (r, z) bottom -> top
PROFILE = [(0.0, 0.0), (0.37, 0.0), (0.42, 0.05), (0.43, 0.15), (0.40, 0.29), (0.33, 0.42), (0.23, 0.53),
           (0.11, 0.59), (0.0, TOP)]


def dome_r(z):
    for (r0, z0), (r1, z1) in zip(PROFILE[1:], PROFILE[2:]):
        if z0 <= z <= z1:
            return r0 + (r1 - r0) * (z - z0) / (z1 - z0)
    return 0.0


# ---- body ---------------------------------------------------------------------
p = Part("body")
lathe(p, "jelly_teal", PROFILE, seg=14)
# drips / lumps around the base
for i, a in enumerate(range(15, 360, 50)):
    r = math.radians(a)
    rr = 0.40 + 0.02 * (i % 2)
    p.ico("jelly_teal", r=0.07 + 0.015 * (i % 3), loc=(math.cos(r) * rr, math.sin(r) * rr, 0.035),
          scale=(1.2, 1.2, 0.55))
# inner glowing core + brass boiler cage holding it (seen through the jelly)
p.ico("glow_cyan", r=0.13, loc=(0, 0.02, 0.27))
gem(p, "glow_cyan", r=0.07, up=0.12, down=0.10, seg=5, loc=(0, 0.02, 0.27), rot=(0, 0, 18))
p.torus("brass", R=0.17, r=0.014, seg=10, seg2=3, loc=(0, 0.02, 0.27))
p.torus("brass", R=0.17, r=0.014, seg=10, seg2=3, loc=(0, 0.02, 0.27), rot=(90, 0, 0))
p.cyl("brass_dark", r=0.03, h=0.30, seg=6, loc=(0, 0.02, 0.47))                     # feed pipe to the valve
p.cyl("brass_dark", r=0.12, h=0.03, seg=8, loc=(0, 0.02, 0.06))                     # base plate
body = p.build(root, loc=(0, 0, 0))

# ---- valve (pivot at top of the jelly) ---------------------------------------------
p = Part("valve")
p.cyl("brass_dark", r=0.085, r2=0.07, h=0.05, seg=8, loc=(0, 0, 0.0))               # collar sunk into jelly
p.cyl("brass", r=0.045, h=0.16, seg=8, loc=(0, 0, 0.09))
p.cyl("brass_dark", r=0.06, h=0.03, seg=8, loc=(0, 0, 0.17))
p.cyl("iron", r=0.035, h=0.04, seg=8, loc=(0, 0, 0.20))                              # chimney mouth
# side spout + valve wheel
p.cyl("brass", r=0.022, h=0.10, seg=6, loc=(0.07, 0, 0.10), rot=(0, 90, 0))
p.cyl("copper", r=0.03, h=0.03, seg=6, loc=(0.12, 0, 0.10), rot=(0, 90, 0))
p.torus("copper", R=0.05, r=0.012, seg=8, seg2=3, loc=(0.0, -0.075, 0.10), rot=(90, 0, 0))
p.box("copper", size=(0.10, 0.012, 0.012), loc=(0.0, -0.075, 0.10))
p.box("copper", size=(0.012, 0.012, 0.10), loc=(0.0, -0.075, 0.10))
p.cyl("brass_dark", r=0.015, h=0.05, seg=6, loc=(0, -0.05, 0.10), rot=(90, 0, 0))
valve = p.build(body, loc=(0, 0, TOP - 0.01))

# ---- eyes: brass pressure gauges on the front face ---------------------------------
def make_eye(name, s):
    z = 0.33
    x = s * 0.15
    y = -math.sqrt(max(dome_r(z) ** 2 - x * x, 0.0)) + 0.025
    p = Part(name)
    yaw = s * 22          # gauges turn slightly outward, following the dome
    ry = math.radians(yaw)
    nrm = Vector((math.sin(ry), -math.cos(ry), 0))     # face normal
    right = Vector((math.cos(ry), math.sin(ry), 0))    # in-plane horizontal axis

    def fp(u, v, d):                                   # point on the gauge face plane
        return tuple(right * u + Vector((0, 0, v)) + nrm * d)

    p.cyl("brass", r=0.10, h=0.05, seg=10, loc=(0, 0, 0), rot=(90, 0, yaw))
    p.cyl("white", r=0.08, h=0.054, seg=10, loc=(0, 0, 0), rot=(90, 0, yaw))
    p.torus("brass_dark", R=0.088, r=0.013, seg=10, seg2=3, loc=fp(0, 0, 0.027), rot=(90, 0, yaw))
    # needle tilted toward the middle (gives the "eyes" a look direction) + pupil hub
    tilt = -s * 25
    t = math.radians(tilt)
    p.box("black", size=(0.014, 0.01, 0.062), loc=fp(math.sin(t) * 0.028, math.cos(t) * 0.028, 0.03),
          rot=(0, tilt, yaw))
    p.cyl("black", r=0.024, h=0.012, seg=6, loc=fp(0, 0, 0.029), rot=(90, 0, yaw))
    for k in range(5):
        a = math.radians(-60 + 30 * k)
        p.box("black", size=(0.008, 0.01, 0.016), loc=fp(math.sin(a) * 0.066, math.cos(a) * 0.066, 0.028),
              rot=(0, math.degrees(a), yaw))
    p.box("cloth_red", size=(0.008, 0.01, 0.016), loc=fp(math.sin(1.2) * 0.066, math.cos(1.2) * 0.066, 0.028),
          rot=(0, math.degrees(1.2), yaw))
    return p.build(body, loc=(x, y, z))

eye_L = make_eye("eye_L", 1)
eye_R = make_eye("eye_R", -1)

finish("slime", views=(("", 30, 18), ("_front", 0, 5), ("_side", 90, 8), ("_back", 200, 25)))
