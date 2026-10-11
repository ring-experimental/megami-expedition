# Asset Spec — Megami Expedition (prototype)

Theme: **steampunk + magic** (brass/copper/iron machinery, steam, leather & cloth, glowing aether crystals and runes).
Style: stylized, chunky readable silhouettes, slightly cute proportions (big heads/hands OK).
Heroes **kai / lyra**: low-poly, flat shaded. **Every other model**: hi-poly, smooth shading with hard edges (see *Build quality*).
Everything is built by Python scripts in `tools/blender/` using `common.py` and exported to `public/models/*.glb`.

## Global conventions (MUST follow — game code depends on them)

- 1 unit = 1 m. Blender Z up (exporter converts to Y up).
- **Every model faces −Y in Blender** (front view / numpad 1 shows its face). This becomes +Z in three.js.
- Character's **right side is −X**, left side is +X.
- Model origin = ground contact point, centered (feet on z = 0). Flying models also have root at ground (z = 0) and their body floats above.
- Each file has a single top-level empty named `root` at (0,0,0) (props.glb is the exception, see below).
- **Animated parts are built as separate objects whose origin is at the joint/pivot** (`Part(...).build(parent, loc=pivot)`; geometry modeled relative to the pivot). Rigged models then turn them into bones with `rig_from_parts` (RIG_SPEC.md). The game animates these nodes/bones procedurally by name, so:
  - limbs hang straight down from their pivot at rest (rest pose = standing, arms down at sides, slightly apart from the body),
  - names must match exactly (case-sensitive, ASCII, underscores only),
  - each part's rest rotation is (0,0,0) — put any visual tilt into the geometry, not the object rotation.
- Materials: use `get_mat(name)` with palette names from `common.py`. Prefixes matter: `glow_*` = emissive (gets bloom), `jelly_*` = translucent. You may add new palette entries in your own script via `get_mat("name", hex="#rrggbb", ...)` — keep the prefix rules.
- Triangle budgets: see *Build quality* below.
- Always `render_preview(...)` and look at the PNG to check proportions / that parts are attached. Iterate until it reads well.

## Characters & enemies (one GLB each)

Heights are approximate. "children" lists required named nodes; you can add extra unnamed-detail geometry inside any part.

### Humanoid skeleton (used by kai, lyra, knight)
```
root (empty, 0,0,0)
└─ hips            pivot at pelvis (~0.52 × height)
   ├─ torso        pivot at waist (just above hips) — chest, coat, backpack, etc.
   │  ├─ head      pivot at neck base
   │  ├─ arm_L     pivot at left shoulder (+X side), arm hangs down −Z, hand at the bottom
   │  └─ arm_R     pivot at right shoulder (−X side)
   │     └─ weapon pivot at the hand (bottom end of arm_R)
   ├─ leg_L        pivot at left hip joint (+X), leg extends down to z=0, foot points −Y
   └─ leg_R        pivot at right hip joint (−X)
```
Elbows/knees (`forearm_*`, `shin_*`) and cloth/hair chains are added by the rig — see RIG_SPEC.md.

1. **kai.glb** — protagonist, young steam-swordsman, ~1.75 m. Short messy brown hair, aviator goggles pushed up on forehead, navy long coat with brass buttons and coat tails, red scarf, leather gloves & boots, compact brass steam pack on his back (two small chimneys) with an empty **`steam_point`** at a chimney top (child of torso).
   `weapon`: steam greatsword, ~1.2 m blade. **With the arm hanging down, the blade points forward (−Y)**, grip in the hand. Broad steel blade, brass guard with a small piston on the blade's spine, a thin `glow_cyan` rune line along the blade.
2. **lyra.glb** — fixed companion, aether mage/artificer, ~1.6 m. Long silver hair (ponytail or braid), wide-brim witch hat with a brass band + small gear, monocle lens, purple & cream coat-dress, leather belt with pouches, boots.
   `weapon`: staff held vertical — **shaft along +Z from the hand** (~1.6 m total, mostly above the hand), brass ring/gear orbiting the head and a `glow_violet` crystal on top; empty **`staff_tip`** at the crystal (child of weapon).
3. **knight.glb** — "Clockwork Knight", strong enemy, ~2.1 m. Bulky brass/iron armored automaton, visor slit with `glow_amber` eyes, exposed gears at joints, tattered cloth_red tabard.
   `weapon`: clockwork halberd held upright (shaft along +Z from the hand, axe-blade near top).
   extra children: **`shield`** (child of arm_L, round gear-shaped shield on the outer side of the arm, facing −Y/+X), **`key`** (child of torso, big wind-up key sticking out of the back along +Y; spins around its local **Y** axis).

### Other enemies
4. **cograt.glb** — "Cog Rat", weak, ~0.45 m tall / 0.8 m long. Clockwork rat: copper body, brass ears, `glow_red` eyes, segmented tail.
   ```
   root
   └─ body    pivot at body center (z≈0.25)
      ├─ head     pivot at neck, head extends toward −Y
      ├─ tail     pivot at rear (+Y end), tail extends +Y (curving up)
      ├─ leg_FL, leg_FR, leg_BL, leg_BR   pivot at top of each leg, extends down to z=0 (F = −Y side, L = +X)
      └─ key      wind-up key on top of the back, spins around local Z
   ```
5. **slime.glb** — "Boiler Jelly", weak, ~0.7 m tall. Translucent `jelly_teal` dome blob with a visible inner `glow_cyan` core, a small brass boiler valve/chimney on top, two brass pressure-gauge "eyes" on the front.
   ```
   root
   └─ body    pivot at ground center (0,0,0) — whole jelly (scaled for squash & stretch from here)
      ├─ valve    pivot at top of jelly
      ├─ eye_L    (+X) on the front face
      └─ eye_R    (−X)
   ```
6. **beetle.glb** — "Brass Beetle", medium (armored), ~0.7 m tall / 1.3 m long. Polished brass carapace, iron underside, `glow_green` eyes, a single big horn.
   ```
   root
   └─ body    pivot at body center (z≈0.35)
      ├─ head     pivot at front of body
      │  └─ horn  pivot at horn base
      ├─ shell_L, shell_R   elytra halves; pivot at the hinge on the top-front of the back (they rotate up/out to open)
      └─ leg_FL, leg_ML, leg_BL, leg_FR, leg_MR, leg_BR   pivot at body side, leg goes out & down to z=0
   ```
7. **wisp.glb** — "Lamp Wisp", magical medium enemy, floats. Brass lantern with glass panes, a living `glow_amber` flame inside, two thin brass rings orbiting it, small gear "wings".
   ```
   root (ground)
   └─ lantern  pivot at lantern center, z = 1.3
      ├─ flame    glow sphere/teardrop at lantern center
      ├─ ring_A   torus around the lantern (spins around local Z)
      ├─ ring_B   torus, tilted ~60° (spins around its local Z; put the tilt in a parent empty `ring_B_tilt` if needed — ring_B rest rotation must stay 0)
      ├─ wing_L   pivot at attach point (+X side)
      └─ wing_R   pivot at attach point (−X side)
   ```
8. **golem.glb** — "Steam Golem", elite (strongest), ~3.2 m. Massive iron/brass furnace body, glowing `glow_amber` furnace core in the chest, tiny head, huge fists, chimney stack on the back.
   ```
   root
   └─ hips   pivot ~1.3 m
      ├─ torso   pivot at waist
      │  ├─ head
      │  ├─ arm_L, arm_R   pivot at shoulders, huge forearms/fists hanging down to ~z=0.4
      │  ├─ core     furnace grille + glow (front of chest)
      │  └─ chimney  on the back (+Y); empty `steam_point` at its top
      ├─ leg_L
      └─ leg_R
   ```

## props.glb (one file, many top-level objects)

Every prop is a **top-level object (or top-level empty with children) named exactly as below**, origin at its base center on the ground, placed anywhere in the file (spread them out on X so the preview is readable — the game re-positions them). No `root` empty here.

| name | description | approx size |
|---|---|---|
| `prop_lamp` | gas street lamp, iron post, brass cage, `glow_cyan` magic bulb | 3.5 m tall |
| `prop_pipe` | thick steam pipe segment lying along X, flanges at ends, with supports; ends open | 6 m long, 0.8 m dia |
| `prop_pipe_arch` | steam pipe arching over the ground like an inverted U (walk-under) | 6 m wide, 4 m tall |
| `prop_vent` | iron grate steam vent on the ground (flat, ~1.2 m), with a small valve wheel | 0.3 m tall |
| `prop_crystal` | cluster of aether crystals `glow_cyan` + `glow_violet`, on a rock base | 2 m tall |
| `prop_rock_a`, `prop_rock_b` | stylized boulders (stone / stone_dark) | 1.5–2.5 m |
| `prop_tree` | stylized tree, chunky canopy (`leaf_teal`) | 5 m |
| `prop_tree_b` | autumn variant (`leaf_autumn`), different silhouette | 4.5 m |
| `prop_bush` | small bush | 0.8 m |
| `prop_gear_monument` | giant half-buried brass gear standing upright, mossy stone base | 5 m |
| `prop_clocktower` | landmark clock tower: stone base, brass top, clock face (`white` + `black` hands, `glow_amber` ring), gear details | 18 m tall, ≤6 m wide |
| `prop_airship` | small airship (balloon + gondola + propeller) — child **`propeller`** (spins around local Y) | 12 m long |
| `prop_rest` | rest point: brass aether fountain/beacon with a floating `glow_cyan` crystal — child **`crystal`** (bobs/spins) | 2.5 m |
| `prop_chest` | treasure chest (wood + brass) — child **`lid`** pivot at the back hinge (rotates around X to open) | 0.9 m |
| `prop_fence` | iron fence segment along X with brass finials | 2 m long, 1.2 m tall |
| `prop_crate` | wooden crate | 1 m |
| `prop_barrel` | wood/iron barrel | 1.1 m |
| `prop_signpost` | wooden signpost with brass plates | 2.2 m |

## arena.glb

Battle arena, `root` empty at center. Circular platform ~**26 m diameter**, walkable **top surface exactly at z = 0** (the platform extends below). Brass & stone concentric rings with engraved gear pattern, toothed gear rim, 8 short pillars on the rim with `glow_cyan`/`glow_violet` crystals, a few broken pipes and cables hanging off the edge. Keep the central ~18 m clear and flat.

---

## Build quality (hi-poly)

Applies to **every model except the heroes kai / lyra** (low-poly, flat shaded, ≤ 3 100 tris).
Concept, silhouette, palette identity, node names, pivots, skeletons and sizes above are binding.

- **Shading: smooth + hard edges.** The game uses the GLB normals (no forced `flatShading`).
  Curved surfaces smooth, crisp metal edges via sharp edges (`hp_helpers.smooth_obj(obj, angle≈30–40)`),
  boxy silhouettes get real bevels (`hp_helpers.bevel_obj`) so edges catch highlights. Organic forms
  (jelly, leaves, rock) may use subdivision + noise displacement. Crystals/gems may stay faceted (`flat_obj`).
- **Vertex AO**: bake `hp_helpers.bake_vertex_ao(...)` (rigged/single models, after `rig_from_parts`) or
  `hp_helpers.bake_tree_ao(prop_root, ...)` (each prop) right before export; optional `tint=` for
  gradients/grime. Exported as COLOR_0 and multiplied with the material colour in three.js.
  glow_/jelly_/glass faces are kept white automatically.
- **Export** with `hp_helpers.export_glb_hp(name)` (keeps COLOR_0). Previews with `hp_helpers.render_hp` /
  `render_views` (EEVEE, closest to the in-game look) — plus common.render_preview (workbench) if useful.
- **Budgets ("medium" tier)** — enforced by check_glb.py / verify_env.py / model_props.py:

  | model | tris | | prop | tris |
  |---|---|---|---|---|
  | cograt | 10 000 | | prop_tree, prop_tree_b (×~94 instanced) | 5 000 |
  | slime | 8 000 | | prop_bush (×70) | 1 000 |
  | wisp | 10 000 | | prop_rock_a/b (×44) | 2 500 |
  | beetle | 20 000 | | prop_crystal, prop_lamp, prop_pipe, prop_chest | 6 000 |
  | knight | 25 000 | | prop_pipe_arch | 8 000 |
  | golem | 30 000 | | prop_vent, prop_fence, prop_barrel, prop_signpost | 4 000 |
  | arena | 60 000 | | prop_crate | 3 000 |
  | | | | prop_rest 12 000 · prop_gear_monument 15 000 · prop_clocktower / prop_airship 40 000 |

  Spend triangles where the camera sees them (silhouette, faces/eyes, bevels on big forms); don't waste
  them on hidden undersides. Draw calls ≈ materials per mesh — keep material count per model reasonable (≤ ~14).
- **props.glb is assembled from group modules** (`props_nature.py`, `props_steam.py`, `props_small.py`,
  `props_clocktower.py`, `props_airship.py`) by `model_props.py`. Group-specific materials use a group
  prefix (`nat_`, `stm_`, `sml_`, `clk_`, `air_`; emissive: `glow_<pfx>_*`) so modules never clash.
- Shared helper modules (`common.py`, `char_helpers.py`, `rig_helpers.py`, `env_helpers.py`,
  `hp_helpers.py`, `creature_rig_helpers.py`, `enemy_rig_helpers.py`, `hero_rig_helpers.py`) are
  **read-only** for model work — put new helpers in your own module (e.g. `hp_<model>_helpers.py`).
