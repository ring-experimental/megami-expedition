# Rig Spec — skeletons & skinning (extends ASSET_SPEC.md)

Rigged models are a skeleton + one skinned mesh with **elbows, knees and secondary-motion chains
(cloth, hair, scarf, tails, ears)**. Bone names are the ASSET_SPEC node names, which the game's
procedural animation drives by name.

Tooling: `tools/blender/rig_helpers.py`
- `rig_from_parts(root, rigid=..., smooth=..., influence=..., skin_name=...)` — converts the Part
  hierarchy the script builds into an armature named `root` + one joined skinned mesh. Every MESH part
  becomes a bone with the same name, head at the part's pivot, same parent chain. EMPTY objects and
  names listed in `rigid` stay separate rigid objects, bone-parented to their nearest bone.
- `pose_preview(arm, filename, rotations)` / `pose_world` / `reset_pose` / `HUMANOID_TEST_POSE` —
  render deformation tests (rotations about WORLD axes through the bone head; Blender world: −Y is the
  model's front, +Z up, model's left is +X; raising an arm forward = ("X", negative)).
- Do NOT edit `common.py` or `rig_helpers.py` (shared by parallel agents). Put extra helpers in your own
  module if needed.

## Global rules
1. **Silhouette, colors, proportions and pivots follow ASSET_SPEC.md.** Split parts where joints/chains
   exist and shape geometry so joints bend cleanly (rounded elbow/knee cap or overlap so no gaps open
   when bent ~90°).
2. **Use every node name** listed in ASSET_SPEC.md (they become bone names or stay rigid
   attachments). Names are case-sensitive.
3. Rest pose: standing, limbs hanging straight down, slightly apart.
4. Call `rig_from_parts(...)` once at the end of the script, then `export_glb(...)`, then render previews
   (normal previews + at least one `pose_preview` with joints bent and chains swung). LOOK at them and
   iterate until bends look clean (no tearing, no big interpenetration, cloth follows legs reasonably).
5. Use `smooth` radii (≈0.05–0.10 m) at elbows, knees and along cloth/hair/tail chains for soft bends;
   rigid weights elsewhere. Use `influence` to make cloth panels that hang over the legs partly follow
   the thighs (e.g. `{"skirt_F_1": [("leg_L", 0.3), ("leg_R", 0.3)]}`) so legs don't poke through.
6. **Round elbows/knees on soft limbs** (sleeves, trousers, stockings): add a joint cap with
   `hero_rig_helpers.joint_cap(name, child_part, mat, profile, z)` — a closed cylinder along the hinge
   axis centred on the joint, its own rigid bone (`elbow_L`, `knee_R`, ...; keep it OUT of `smooth`).
   Linear-blend skinning alone turns the outer corner of a >90° bend into a flat bevel; the cylinder
   keeps it round. Keep the joint `smooth` radius small (~0.05). Armored joints use hard pieces
   (hinge barrels, gears, ball joints) instead.
7. Tri budgets: ASSET_SPEC.md (heroes ≤ 3 100 incl. joint caps). Keep material slots few — each slot is a draw call.
8. glTF rest rotations on bones are expected (non-identity) — the game handles them. `check_glb.py`
   validates: skin present, required bone names present as joints, required rigid attachments present
   and parented under the right bone.

## Required skeletons

### Humanoids (kai, lyra, knight, golem)
```
root (armature)
└─ hips
   ├─ torso
   │  ├─ head
   │  ├─ arm_L ─ forearm_L          arm_* = upper arm (shoulder→elbow), forearm_* = elbow→hand incl. hand
   │  └─ arm_R ─ forearm_R ─(rigid) weapon      weapon pivot at the hand
   ├─ leg_L ─ shin_L                leg_* = thigh (hip→knee), shin_* = knee→ankle incl. boot/foot
   └─ leg_R ─ shin_R
```
- The elbow sits roughly halfway down the arm, the knee roughly halfway down the leg.
- Rigid attachments stay rigid objects: `weapon` (child of **forearm_R**), `steam_point`, `staff_tip`,
  knight `shield` (child of **forearm_L**) and knight `key` (torso). Golem `core` / `chimney` may stay
  separate mesh parts (they then become bones) — keep `steam_point` under `chimney`.

### Secondary-motion chains (game animates these procedurally by name prefix)
Prefixes recognised by the game: `coat_ skirt_ scarf_ tabard_ cape_ hair_ hat_ tail_ ear_ antenna_`.
Chains are numbered from the attachment outward: `<prefix><side>_1`, `<prefix><side>_2`, ...
(side letters: L, R, F (front), B (back); omit when there is a single chain, e.g. `scarf_1`, `tail_1`).

| model | required chains |
|---|---|
| kai | back coat tails `coat_L_1 → coat_L_2`, `coat_R_1 → coat_R_2` (parent hips; side panels may join these or get `coat_SL_1`/`coat_SR_1`) · scarf tail `scarf_1 → scarf_2` (parent torso) |
| lyra | skirt panels `skirt_F_1 → skirt_F_2`, `skirt_B_1 → skirt_B_2`, `skirt_L_1`, `skirt_R_1` (parent hips; F/side panels get thigh `influence`) · hair `hair_L_1 → hair_L_2`, `hair_R_1 → hair_R_2` and/or ponytail/braid `hair_B_1 → hair_B_2 → hair_B_3` (parent head) · hat tip `hat_1` (parent head) |
| knight | tabard `tabard_F_1 → tabard_F_2` (parent hips, thigh influence), optional back `tabard_B_1 → tabard_B_2` |
| golem | none required |
| cograt | `body` (root bone) → `head` → `ear_L`, `ear_R`; `tail_1 → tail_2 → tail_3 → tail_4` (parent body); legs `leg_FL leg_FR leg_BL leg_BR` (single segment ok); rigid `key` on body |
| beetle | `body` → `head` → `horn`; `shell_L`, `shell_R` (parent body); six legs, each two segments: `leg_FL → leg_FL_2`, `leg_ML → leg_ML_2`, `leg_BL → leg_BL_2`, same for R; optional `antenna_L`, `antenna_R` (parent head) |

slime and wisp are not rigged: their named parts are animated as rigid nodes.

## Deliverables per model
- updated `tools/blender/model_<name>.py`, regenerated `public/models/<name>.glb`
- previews (local only, git-ignored): `<name>.png` (+ front/side/back) and `<name>_pose.png` (bent test pose)
- report: bone list, rigid attachments, tri count, anything that still clips
