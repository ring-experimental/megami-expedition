"""props.glb — all environment props as top-level nodes (see ASSET_SPEC.md, "props.glb").

The builders live in group modules so several people/agents can work on them in parallel:
    props_nature.py      prop_crystal, prop_rock_a, prop_rock_b, prop_tree, prop_tree_b, prop_bush
    props_steam.py       prop_lamp, prop_pipe, prop_pipe_arch, prop_vent, prop_fence, prop_gear_monument
    props_small.py       prop_rest, prop_chest, prop_crate, prop_barrel, prop_signpost
    props_clocktower.py  prop_clocktower
    props_airship.py     prop_airship
Each module exposes setup_mats(), PROPS = [(name, builder, preview_kwargs), ...] and BUDGET = {name: tris}.
Builders are responsible for their own hi-poly finishing (hp_helpers: bevel / smooth / bake_tree_ao).

Run (from project root):
    blender -b --factory-startup -P tools/blender/model_props.py              # full props.glb export
Options (after `--`):
    --group=nature,steam   only these groups (NO props.glb export unless --out is given)
    --previews             render every prop alone (EEVEE) -> previews/prop_<name>.png
    --only=a,b             restrict previews to these prop names
    --back                 extra rear 3/4 preview per prop (previews/<name>_back.png)
    --no-export            skip the export (preview iteration only)
    --out=DIR              export to DIR/props.glb instead of public/models (test exports)
"""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: E402,F401,F403
from env_helpers import tree_bbox  # noqa: E402
import hp_helpers as hp  # noqa: E402

GROUPS = ["nature", "steam", "small", "clocktower", "airship"]


def setup_shared_mats():
    """Extra palette entries shared by several groups (same prefix rules as common.PALETTE)."""
    get_mat("moss", hex="#6b8f3a", roughness=0.95)
    get_mat("patina", hex="#4f9c8a", metallic=0.55, roughness=0.5)
    get_mat("paint_red", hex="#9e2b25", metallic=0.35, roughness=0.5)
    get_mat("leaf_teal_dark", hex="#2e6c62", roughness=0.9)
    get_mat("leaf_autumn_dark", hex="#9c4a1e", roughness=0.9)
    get_mat("leaf_gold", hex="#d9a23a", roughness=0.9)
    get_mat("rope", hex="#b39a6b", roughness=0.9)


def load_groups(names):
    mods = [importlib.import_module("props_" + g) for g in names]
    return mods


def setup_mats(mods):
    setup_shared_mats()
    for m in mods:
        m.setup_mats()


def _report(name, root, budget):
    tris = hp.tree_tris(root)
    mins, maxs = tree_bbox(root)
    size = maxs - mins
    flag = "" if tris <= budget else "  !!! OVER BUDGET"
    print(f"[tris] {name:22s} {tris:6d} / {budget}  size=({size.x:.2f}, {size.y:.2f}, {size.z:.2f})"
          f"  zmin={mins.z:.3f}{flag}")
    return tris


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    only = None
    groups = GROUPS
    out_dir = None
    for a in argv:
        if a.startswith("--only="):
            only = set(a.split("=", 1)[1].split(","))
        elif a.startswith("--group="):
            groups = [g.strip().replace("props_", "") for g in a.split("=", 1)[1].split(",")]
        elif a.startswith("--out="):
            out_dir = a.split("=", 1)[1]
    partial = groups != GROUPS
    mods = load_groups(groups)
    entries = [(name, fn, pv, m.BUDGET.get(name, 1500)) for m in mods for (name, fn, pv) in m.PROPS]

    if "--previews" in argv:
        for name, fn, pv, budget in entries:
            if only and name not in only:
                continue
            reset_scene()
            setup_mats(mods)
            root = fn()
            bpy.context.view_layer.update()
            _report(name, root, budget)
            hp.render_hp(name, **pv)
            if "--back" in argv:
                kw = dict(pv)
                kw["azimuth"] = 215
                hp.render_hp(name + "_back", **kw)
    if "--no-export" in argv:
        return
    if partial and not out_dir:
        print("[export] skipped: --group given without --out (props.glb must contain every group)")
        return
    reset_scene()
    setup_mats(mods)
    x = 0.0
    total = 0
    for name, fn, _, budget in entries:
        root = fn()
        bpy.context.view_layer.update()
        mins, maxs = tree_bbox(root)
        root.location.x = x - mins.x
        x += (maxs.x - mins.x) + 3.0
        bpy.context.view_layer.update()
        total += _report(name, root, budget)
    print(f"[tris] total {total}")
    hp.export_glb_hp("props", out_dir=out_dir)
    if not partial:
        render_preview("props", size=1400, azimuth=20, elevation=20)


main()
