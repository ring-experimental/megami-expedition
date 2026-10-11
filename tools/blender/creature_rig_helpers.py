"""Small helpers for rigging the creature enemies (cograt, beetle). See RIG_SPEC.md.

Builds on common.py / char_helpers.py / rig_helpers.py (which must not be edited).

    vsub(a, b), vadd(a, b)              tuple vector math for pivot bookkeeping
    pose_views(arm, name, pose, views)  render several pose_preview angles of one test pose
"""
from mathutils import Vector

from rig_helpers import pose_preview


def vsub(a, b):
    return tuple(Vector(a) - Vector(b))


def vadd(a, b):
    return tuple(Vector(a) + Vector(b))


def pose_views(arm, name, pose, views=(("", 35, 18),)):
    """Render `<name>_pose<suffix>.png` for each (suffix, azimuth, elevation) in views.
    pose_preview resets the armature to its rest pose after every render."""
    out = []
    for suffix, az, el in views:
        out.append(pose_preview(arm, f"{name}_pose{suffix}", pose, azimuth=az, elevation=el))
    return out
