import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { getProp } from '../core/assets';
import { Input } from '../core/input';
import { Sfx } from '../core/audio';
import { clamp, damp, dampAngle, mulberry32, rand, wrapAngle } from '../core/utils';
import { Effects } from '../fx/effects';
import { FakeLight, patchObject } from '../fx/fakeLights';
import { animateBackdrop, animateMotes, buildBackdrop, buildMotes, buildSky, getEnvMap } from '../fx/environment';
import { ZONES, type ChestDef, type Circle, type GateDef, type NpcDef, type SpawnDef, type SpotDef, type ZoneDef } from '../data/zones';
import { PARTS, CRYSTAL_NAME as CRYSTAL } from '../data/parts';
import type { Element } from '../data/types';
import { ITEMS } from '../data/items';
import { SPECIES } from '../data/units';
import { CRYSTAL_NAME, crystalDrop } from '../data/parts';
import { State } from '../game/state';
import { FieldHud } from '../ui/fieldHud';
import { icon } from '../ui/art';
import { pb } from '../ui/glyph';
import type { Game } from '../game/game';
import { Player } from './player';
import { FieldEnemy } from './fieldEnemy';
import { buildGrass, buildTerrain, heightAt, plazaMask, roadMask, setTerrain } from './terrain';
import { Animator } from '../anim/rig';
import { getModel } from '../core/assets';

interface Projectile { mesh: THREE.Object3D; light: FakeLight; vel: THREE.Vector3; life: number; owner: FieldEnemy }

const PROJ_GEO = new THREE.SphereGeometry(0.28, 10, 8);
const PROJ_MAT = new THREE.MeshBasicMaterial({ color: 0xffa040 });
interface Chest { def: ChestDef; obj: THREE.Object3D; lid: THREE.Object3D | null; open: number }
interface Npc { def: NpcDef; obj: THREE.Object3D; anim: Animator }

export class FieldMode {
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(55, 1, 0.1, 900);
  fx: Effects;
  player: Player;
  enemies: FieldEnemy[] = [];
  hud: FieldHud;
  colliders: Circle[] = [];
  controlsEnabled = false;
  zone!: ZoneDef;
  npcs: Npc[] = [];
  private sun: THREE.DirectionalLight;
  private hemi: THREE.HemisphereLight;
  private projectiles: Projectile[] = [];
  private chests: Chest[] = [];
  /** rest points (점등 표지) placed in this zone; their crystals spin */
  rests: { x: number; z: number; obj: THREE.Object3D; crystal: THREE.Object3D | null }[] = [];
  private airship: THREE.Object3D | null = null;
  private propeller: THREE.Object3D | null = null;
  /** Everything the current zone added (removed on the next loadZone). */
  private zoneObjs: THREE.Object3D[] = [];
  private zoneGeos: THREE.BufferGeometry[] = [];
  private zoneLights: FakeLight[] = [];
  private gateFx: { g: GateDef; t: number }[] = [];
  /** lamps that light up with a story flag (m01's gas lamps) */
  private flagLights: { l: FakeLight; flag: string; on: number; glass: THREE.MeshStandardMaterial[]; glow: number[] }[] = [];
  /** scripted camera: look from `pos` at `look` until `until` (field time) */
  private cine: { pos: THREE.Vector3; look: THREE.Vector3; until: number } | null = null;
  /** Warm light carried by each lamp wisp (fixed pool: the light count never changes, so killing a
   *  wisp doesn't trigger a shader recompile — the light just fades to 0). */
  private wispLights: { e: FieldEnemy; l: FakeLight; node: THREE.Object3D; phase: number }[] = [];
  private steamVents: THREE.Vector3[] = [];
  private backdrop!: THREE.Object3D;
  private motes!: THREE.Points;
  private camYaw = Math.PI;
  private camPitch = 0.32;
  private camDist = 7;
  /** R3 "camera behind the player" swing in progress */
  private camRecenter: number | null = null;
  /** Seconds since the player last turned the camera (auto-follow waits for this). */
  private camIdle = 0;
  /** How long the arrow keys have been held (their turn rate ramps up for fine aim). */
  private camKeyT = 0;
  private camPos = new THREE.Vector3();
  private camLook = new THREE.Vector3();
  private shake = 0;
  private hitstop = 0;
  private time = 0;
  private ventT = 0;
  private interactCooldown = 0;
  private gateCooldown = 0;
  inCutscene = false;

  constructor(private game: Game) {
    const s = this.scene;
    s.environment = getEnvMap(game.renderer);
    s.environmentIntensity = 0.45;
    s.fog = new THREE.Fog('#e9c99b', 60, 230);
    this.hemi = new THREE.HemisphereLight('#ffe2bd', '#5a6a45', 1.1);
    s.add(this.hemi);
    this.sun = new THREE.DirectionalLight('#ffe0b0', 2.6);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(2048, 2048);
    const sc = this.sun.shadow.camera;
    sc.left = sc.bottom = -38;
    sc.right = sc.top = 38;
    sc.near = 1;
    sc.far = 160;
    this.sun.shadow.bias = -0.0006;
    this.sun.shadow.normalBias = 0.04;
    s.add(this.sun, this.sun.target);

    this.fx = new Effects(s);
    this.player = new Player(this);
    s.add(this.player.obj);
    this.hud = new FieldHud(game.ui, this);
    this.loadZone('plains');
    this.respawnPlayer(true);
  }

  // ---------------------------------------------------------------------
  // Zones
  // ---------------------------------------------------------------------
  /** Tear down the current zone and build `id`. The player is placed by the caller. */
  loadZone(id: string) {
    const z = ZONES[id];
    if (!z) throw new Error('unknown zone ' + id);
    this.clearZone();
    this.zone = z;
    State.current.zone = id;
    const s = this.scene;
    const add = (o: THREE.Object3D) => { s.add(o); this.zoneObjs.push(o); return o; };
    setTerrain(z.terrain);
    const sky = { ...z.sky };
    for (const v of z.skyVariants ?? []) if (State.current.flag(v.flag)) Object.assign(sky, v.sky);
    (s.fog as THREE.Fog).color.set(sky.fog);
    (s.fog as THREE.Fog).near = sky.fogNear;
    (s.fog as THREE.Fog).far = sky.fogFar;
    this.hemi.color.set(sky.hemiSky);
    this.hemi.groundColor.set(sky.hemiGround);
    this.hemi.intensity = sky.hemi;
    this.sun.color.set(sky.sunColor);
    this.sun.intensity = sky.sunInt;
    add(buildSky({ top: sky.top, horizon: sky.horizon, bottom: sky.bottom, sun: sky.sun, sunDir: new THREE.Vector3(...sky.sunDir) }));
    this.backdrop = add(buildBackdrop({ mountainColor: sky.mountain, cloudColor: sky.cloud, radius: 170, seed: z.terrain.seed }));
    const terrain = add(buildTerrain()) as THREE.Mesh;
    this.zoneGeos.push(terrain.geometry);
    this.buildProps();
    const grass = add(buildGrass((x, zz) => this.colliders.some((c) => Math.hypot(c.x - x, c.z - zz) < c.r + 0.4), z.radius));
    grass.traverse((o) => { const m = o as THREE.Mesh; if (m.isMesh) this.zoneGeos.push(m.geometry); });
    this.motes = add(buildMotes(260, 60, sky.motes)) as THREE.Points;

    const st = State.current;
    for (const sp of z.spawns) {
      if (!spawnActive(sp)) continue;
      const e = new FieldEnemy(sp, this);
      this.enemies.push(e);
      s.add(e.obj);
      if (st.defeated.has(sp.id)) { e.removed = true; e.obj.visible = false; }
    }
    for (const e of this.enemies) {
      if (e.sp.archetype !== 'wisp') continue;
      const l = this.zoneLight(new FakeLight('#ffb060', 0, 7));
      this.wispLights.push({ e, l, node: e.anim.rig.get('flame') ?? e.model, phase: Math.random() * 6 });
    }
    this.buildNpcs();
    for (const t of z.statues ?? []) {
      const m = getModel(t.model as Parameters<typeof getModel>[0]);
      m.position.set(t.x, heightAt(t.x, t.z), t.z);
      m.rotation.y = t.rot;
      m.scale.multiplyScalar(t.scale ?? 1);
      // hushed: eyes and glows go dark
      m.traverse((o) => { const mm = (o as THREE.Mesh).material as THREE.MeshStandardMaterial | undefined; if (mm?.name?.startsWith('glow_')) mm.emissiveIntensity = 0; });
      add(m);
      this.colliders.push({ x: t.x, z: t.z, r: 0.7 });
    }
    for (const g of z.gates.filter((g) => flagsAllow(g))) {
      // a glowing ring on the ground marks each exit
      const l = this.zoneLight(new FakeLight('#ffd27a', 5, 8));
      l.position.set(g.x, heightAt(g.x, g.z) + 1.5, g.z);
      this.gateFx.push({ g, t: 0 });
    }
    // every lit material samples the fake-light array (no real PointLights in this scene)
    patchObject(s);
    this.refreshLights();
    this.hud.setZone(z);
  }

  refreshLights() {
    for (const f of this.flagLights) {
      const on = !!State.current.flag(f.flag);
      f.l.intensity = on ? f.on : 0;
      f.glass.forEach((g, i) => { g.emissiveIntensity = on ? f.glow[i] : 0.05; });
    }
  }

  /** Swing the camera to look at something for `sec` seconds (story beats). */
  lookAt(pos: THREE.Vector3, look: THREE.Vector3, sec: number) {
    this.cine = { pos, look, until: this.time + sec };
  }

  /** Rebuild the zone in place (flags changed what's placed), keeping the player where they are. */
  rebuild() {
    const p = this.player.pos.clone(), yaw = this.player.yaw;
    this.loadZone(this.zone.id);
    this.player.pos.copy(p);
    this.player.yaw = yaw;
  }

  private zoneLight(l: FakeLight) {
    this.fx.lights.add(l);
    this.zoneLights.push(l);
    return l;
  }

  private clearZone() {
    const s = this.scene;
    for (const o of this.zoneObjs) s.remove(o);
    for (const g of this.zoneGeos) g.dispose();
    for (const l of this.zoneLights) this.fx.lights.remove(l);
    for (const e of this.enemies) { e.dispose(); s.remove(e.obj); }
    for (const n of this.npcs) s.remove(n.obj);
    for (const c of this.chests) s.remove(c.obj);
    for (const pr of this.projectiles) { s.remove(pr.mesh); this.fx.lights.remove(pr.light); }
    this.zoneObjs = [];
    this.zoneGeos = [];
    this.zoneLights = [];
    this.enemies = [];
    this.npcs = [];
    this.chests = [];
    this.projectiles = [];
    this.wispLights = [];
    this.steamVents = [];
    this.colliders = [];
    this.gateFx = [];
    this.flagLights = [];
    this.rests = [];
    this.airship = this.propeller = null;
    this.fx.clear();
  }

  private buildNpcs() {
    for (const d of this.zone.npcs) {
      if (!flagsAllow(d)) continue;
      const model = getModel(d.model as Parameters<typeof getModel>[0]);
      if (d.scale) model.scale.multiplyScalar(d.scale);
      const obj = new THREE.Group();
      obj.add(model);
      obj.position.set(d.x, d.y ?? heightAt(d.x, d.z), d.z);
      obj.rotation.y = d.rot;
      this.scene.add(obj);
      const arche = d.model.startsWith('npc_') || d.model === 'kai' || d.model === 'lyra' ? 'humanoid' : (SPECIES[d.model]?.archetype ?? 'humanoid');
      const anim = new Animator(model, arche);
      this.npcs.push({ def: d, obj, anim });
      if (d.y === undefined) this.colliders.push({ x: d.x, z: d.z, r: 0.5 });
    }
  }

  /** Re-place NPCs / story spawns after flags change (story events call this). */
  refreshActors() {
    const s = this.scene;
    for (const n of this.npcs) { s.remove(n.obj); this.colliders = this.colliders.filter((c) => !(c.x === n.def.x && c.z === n.def.z && c.r === 0.5)); }
    this.npcs = [];
    this.buildNpcs();
    // spawns whose flag condition changed
    for (const sp of this.zone.spawns) {
      const have = this.enemies.find((e) => e.spawn === sp);
      const want = spawnActive(sp);
      if (want && !have) {
        const e = new FieldEnemy(sp, this);
        this.enemies.push(e);
        s.add(e.obj);
      } else if (!want && have) {
        have.dispose();
        s.remove(have.obj);
        this.enemies = this.enemies.filter((e) => e !== have);
      }
    }
    patchObject(s);
  }

  // ---------------------------------------------------------------------
  // World building
  // ---------------------------------------------------------------------
  private buildProps() {
    const s = this.scene;
    const z = this.zone;
    const statics: THREE.Object3D[] = [];
    for (const p of z.props) {
      if (!flagsAllow(p)) continue;
      const o = getProp(p.name);
      o.position.set(p.x, (p.y ?? 0) + heightAt(p.x, p.z), p.z);
      o.rotation.y = p.rot ?? 0;
      o.scale.setScalar(p.scale ?? 1);
      // the rest point's crystal animates and flag-lit lamps switch their glass on; the rest never
      // changes → merged below
      const glass: THREE.MeshStandardMaterial[] = [];
      if (p.lightFlag) {
        o.traverse((n) => {
          const m = n as THREE.Mesh;
          const mat = m.material as THREE.MeshStandardMaterial | undefined;
          if (!m.isMesh || !mat?.name?.startsWith('glow_')) return;
          m.material = mat.clone();
          glass.push(m.material as THREE.MeshStandardMaterial);
        });
      }
      if (p.name === 'prop_rest' || p.lightFlag) { s.add(o); this.zoneObjs.push(o); }
      else statics.push(o);
      const cos = Math.cos(p.rot ?? 0), sin = Math.sin(p.rot ?? 0), k = p.scale ?? 1;
      for (const c of p.colliders ?? []) {
        // rotate local collider offset by the prop's yaw (three.js: x' = x cos + z sin, z' = -x sin + z cos)
        this.colliders.push({ x: p.x + (c.x * cos + c.z * sin) * k, z: p.z + (-c.x * sin + c.z * cos) * k, r: c.r * k });
      }
      if (p.steam) this.steamVents.push(new THREE.Vector3(p.x, heightAt(p.x, p.z) + (p.steamY ?? 0.2), p.z));
      if (p.name === 'prop_rest') {
        this.rests.push({ x: p.x, z: p.z, obj: o, crystal: o.getObjectByName('crystal') ?? null });
        const l = this.zoneLight(new FakeLight('#5ff3ff', 8, 10));
        o.updateMatrixWorld(true);
        l.position.set(0, 2.2, 0).applyMatrix4(o.matrixWorld);
      }
      if (p.name === 'prop_lamp' || p.light) {
        const l = this.zoneLight(new FakeLight(p.light ?? '#7ff0ff', 6, 9));
        o.updateMatrixWorld(true);
        l.position.set(0, 3.2, 0).applyMatrix4(o.matrixWorld);
        if (p.lightFlag) this.flagLights.push({ l, flag: p.lightFlag, on: 6, glass, glow: glass.map((g) => g.emissiveIntensity) });
      }
    }
    for (const c of z.chests.filter((c) => flagsAllow(c))) {
      const o = getProp('prop_chest');
      o.position.set(c.x, heightAt(c.x, c.z), c.z);
      o.rotation.y = c.rot;
      s.add(o);
      this.colliders.push({ x: c.x, z: c.z, r: 0.6 });
      this.chests.push({ def: c, obj: o, lid: o.getObjectByName('lid') ?? null, open: 0 });
    }
    const merged = mergeStatic(statics);
    merged.traverse((o) => { const m = o as THREE.Mesh; if (m.isMesh) this.zoneGeos.push(m.geometry); });
    s.add(merged);
    this.zoneObjs.push(merged);
    // airship circling overhead
    if (z.airship) {
      this.airship = getProp('prop_airship');
      this.propeller = this.airship.getObjectByName('propeller') ?? null;
      s.add(this.airship);
      this.zoneObjs.push(this.airship);
    }

    // scatter trees / rocks / bushes (instanced)
    const rnd = mulberry32(1234 + z.terrain.seed);
    const placed: { name: string; m: THREE.Matrix4 }[] = [];
    const ok = (x: number, z: number, clear: number) =>
      roadMask(x, z) < 0.05 && plazaMask(x, z) < 0.05 &&
      Math.hypot(x - this.zone.start.x, z - this.zone.start.z) > 8 &&
      !this.zone.gates.some((g) => Math.hypot(g.x - x, g.z - z) < g.r + 4) &&
      !this.colliders.some((c) => Math.hypot(c.x - x, c.z - z) < c.r + clear) &&
      !this.zone.spawns.some((sp) => Math.hypot(sp.x - x, sp.z - z) < sp.wander + 2);
    const place = (name: string, count: number, rMin: number, rMax: number, colR: number, sMin: number, sMax: number) => {
      let n = 0;
      for (let i = 0; i < count * 8 && n < count; i++) {
        const a = rnd() * Math.PI * 2, r = rMin + rnd() * (rMax - rMin);
        const x = Math.cos(a) * r, z = Math.sin(a) * r;
        if (!ok(x, z, colR + 1.5)) continue;
        const sc = sMin + rnd() * (sMax - sMin);
        const m = new THREE.Matrix4().compose(
          new THREE.Vector3(x, heightAt(x, z) - 0.1, z),
          new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), rnd() * Math.PI * 2),
          new THREE.Vector3(sc, sc, sc),
        );
        placed.push({ name, m });
        if (colR > 0 && r < this.zone.radius + 2) this.colliders.push({ x, z, r: colR * sc });
        n++;
      }
    };
    for (const d of z.scatter) place(d.name, d.count, d.rMin, d.rMax, d.colR, d.sMin, d.sMax);
    const byName = new Map<string, THREE.Matrix4[]>();
    for (const p of placed) {
      if (!byName.has(p.name)) byName.set(p.name, []);
      byName.get(p.name)!.push(p.m);
    }
    for (const [name, mats] of byName) { const o = instanceProp(name, mats); s.add(o); this.zoneObjs.push(o); }
  }

  // ---------------------------------------------------------------------
  // Queries used by player / enemies
  // ---------------------------------------------------------------------
  groundAt(x: number, z: number) {
    return heightAt(x, z);
  }

  resolveCollisions(p: THREE.Vector3, r: number, _attacking = false, self?: FieldEnemy) {
    for (const c of this.colliders) {
      const dx = p.x - c.x, dz = p.z - c.z;
      const d2 = dx * dx + dz * dz, min = c.r + r;
      if (d2 < min * min && d2 > 1e-6) {
        const d = Math.sqrt(d2);
        p.x = c.x + (dx / d) * min;
        p.z = c.z + (dz / d) * min;
      }
    }
    // keep enemies and player from overlapping
    const bodies: { p: THREE.Vector3; r: number }[] = [];
    if (self) bodies.push({ p: this.player.pos, r: 0.45 });
    for (const e of this.enemies) if (e !== self && e.alive) bodies.push({ p: e.pos, r: e.radius * 0.8 });
    for (const b of bodies) {
      const dx = p.x - b.p.x, dz = p.z - b.p.z;
      const d2 = dx * dx + dz * dz, min = b.r + r;
      if (d2 < min * min && d2 > 1e-6) {
        const d = Math.sqrt(d2);
        p.x = b.p.x + (dx / d) * min;
        p.z = b.p.z + (dz / d) * min;
      }
    }
    const rr = Math.hypot(p.x, p.z), R = this.zone.radius;
    if (rr > R) { p.x *= R / rr; p.z *= R / rr; }
    // interiors: stay inside the nearest room
    const rooms = this.zone.terrain.rooms;
    if (rooms && !rooms.some((m) => Math.hypot(p.x - m.x, p.z - m.z) <= m.r - r)) {
      let best = rooms[0], bd = Infinity;
      for (const m of rooms) { const d = Math.hypot(p.x - m.x, p.z - m.z) - m.r; if (d < bd) { bd = d; best = m; } }
      const dx = p.x - best.x, dz = p.z - best.z, d = Math.hypot(dx, dz) || 1, lim = best.r - r;
      p.x = best.x + (dx / d) * lim;
      p.z = best.z + (dz / d) * lim;
    }
  }

  nearestEnemy(pos: THREE.Vector3, range: number, yaw?: number, arc?: number) {
    let best: FieldEnemy | null = null, bd = Infinity;
    for (const e of this.enemies) {
      if (!e.alive) continue;
      const dx = e.pos.x - pos.x, dz = e.pos.z - pos.z;
      const d = Math.hypot(dx, dz) - e.radius;
      if (d > range || d >= bd) continue;
      if (yaw !== undefined && arc !== undefined && Math.abs(wrapAngle(Math.atan2(dx, dz) - yaw)) > arc) continue;
      bd = d;
      best = e;
    }
    return best;
  }

  /** Called by the player at the active frame of a swing. */
  playerStrike(range: number, arc: number, dmgK: number, brk: number, heavy: boolean, combo: number) {
    const p = this.player;
    const kaiAtk = State.current.stats(State.current.member('kai')).atk;
    const fwd = p.forward;
    const center = p.pos.clone().add(new THREE.Vector3(0, 1.1, 0)).addScaledVector(fwd, 0.8);
    const tilt = heavy ? 0.15 : combo === 2 ? 1.25 : combo === 1 ? -0.25 : 0.25;
    this.fx.slash(center, p.yaw, heavy ? 0xffc46b : 0xbff6ff, heavy ? 2.8 : 2.1, tilt, heavy ? 0.3 : 0.2);
    let hitAny = false;
    for (const e of this.enemies) {
      if (!e.alive) continue;
      const dx = e.pos.x - p.pos.x, dz = e.pos.z - p.pos.z;
      const d = Math.hypot(dx, dz);
      if (d - e.radius > range) continue;
      if (Math.abs(wrapAngle(Math.atan2(dx, dz) - p.yaw)) > arc && d > e.radius + 0.6) continue;
      const dmg = Math.round(kaiAtk * dmgK * rand(0.9, 1.1));
      if (e.takeHit(dmg, brk, heavy)) {
        hitAny = true;
        const hp = e.pos.clone().add(new THREE.Vector3(0, e.sp.height * 0.5 + (e.sp.hover ?? 0) * 0.6, 0));
        this.fx.sparks.burst(hp, heavy ? 26 : 14, { color: heavy ? 0xffc46b : 0xfff1c0, speed: heavy ? 9 : 6, life: 0.35, size: 0.12, gravity: 9, drag: 0.2 });
        this.fx.ring(hp, 0xffffff, heavy ? 1.6 : 1.0, 0.22, p.forward);
        if (e.killable) this.game.ui.popup(hp, String(dmg), 'dmg field');
        else this.game.ui.popup(hp, `BRK +${brk}`, 'brk field');
      }
    }
    if (hitAny) {
      Sfx.play(heavy ? 'hit_heavy' : 'hit');
      Input.rumble(heavy ? 0.5 : 0.15, heavy ? 0.5 : 0.35, heavy ? 120 : 60);
      this.hitstop = heavy ? 0.09 : 0.05;
      this.shake = heavy ? 0.35 : 0.15;
    }
  }

  /** A projectile-like mesh for shader warm-up (game.ts). */
  warmObject() {
    return new THREE.Mesh(PROJ_GEO, PROJ_MAT);
  }

  spawnProjectile(e: FieldEnemy) {
    const m = new THREE.Mesh(PROJ_GEO, PROJ_MAT);
    const l = this.fx.lights.add(new FakeLight(0xffa040, 10, 6));
    l.priority = 1;
    const start = e.pos.clone().add(new THREE.Vector3(0, (e.sp.hover ?? 0.6), 0));
    m.position.copy(start);
    const target = this.player.pos.clone().add(new THREE.Vector3(0, 1, 0));
    const vel = target.sub(start).normalize().multiplyScalar(10);
    this.scene.add(m);
    l.position.copy(start);
    this.projectiles.push({ mesh: m, light: l, vel, life: 1.6, owner: e });
    Sfx.play('fire');
  }

  onEnemyStunned(e: FieldEnemy) {
    this.game.ui.popup(e.topPos(), 'BREAK!', 'break-pop', 1.2);
    this.fx.ring(e.pos.clone().add(new THREE.Vector3(0, 0.2, 0)), 0xffe066, 3, 0.5);
    this.fx.sparks.burst(e.topPos(), 40, { color: 0xffe066, speed: 8, life: 0.6, size: 0.16, gravity: 6 });
    this.hitstop = 0.14;
    this.shake = 0.4;
    State.current.bestiary[e.sp.id].seen = true;
  }

  onEnemyKilled(e: FieldEnemy) {
    const st = State.current;
    st.defeated.add(e.spawn.id);
    const group = e.spawn.formation.map((id) => SPECIES[id]);
    const xp = Math.round(group.reduce((s, sp) => s + sp.xp, 0) * 0.5);
    const money = Math.round(group.reduce((s, sp) => s + sp.money, 0) * 0.5);
    st.money += money;
    const [el] = crystalDrop(e.sp);
    st.addCrystals({ [el]: 1 });
    const ups = st.activeMembers().map((m) => st.giveXp(m, xp)).filter(Boolean);
    this.fx.sparks.burst(e.pos.clone().add(new THREE.Vector3(0, 0.6, 0)), 30, { color: 0xb8ffef, speed: 4, life: 0.8, size: 0.14, up: 1 });
    this.game.ui.toast(`<b>${e.sp.name}</b> 필드 처치 · EXP +${xp} · ${money} 기어 · ${CRYSTAL_NAME[el]} ×1 <span class="dim">(턴제 전투보다 보상이 적고 영입 불가)</span>`);
    for (const u of ups) if (u) this.game.ui.toast(`<b>${u.name}</b> 레벨 업! Lv${u.from} → Lv${u.to}`, 'gold');
    if (ups.length) Sfx.play('levelup');
  }

  /** Enemy body/attack touched the player → battle. */
  contact(e: FieldEnemy) {
    if (!this.controlsEnabled) return;
    const ambush = this.player.isBehind(e);
    this.startBattle(e, ambush ? 'enemy' : 'none');
  }

  async startBattle(e: FieldEnemy, advantage: 'party' | 'enemy' | 'none') {
    if (!this.controlsEnabled) return;
    this.controlsEnabled = false;
    this.player.lock(true);
    // the story may talk first, change the battle, or call it off (quest givers)
    this.inCutscene = true;
    this.hud.setPrompt('');
    const pre = await this.game.story.preBattle(e.spawn.id);
    this.inCutscene = false;
    if (!pre.proceed) {
      this.controlsEnabled = true;
      this.player.lock(false);
      this.player.invuln = 2;
      this.interactCooldown = 0.5;
      e.pacify();
      Input.consumePressed();
      return;
    }
    void this.game.startBattle({
      formation: e.spawn.formation,
      leaderHp: e.killable ? e.hp / e.hpMax : 1,
      advantage: pre.advantage ?? advantage,
      source: e,
      event: pre.event,
    });
  }

  // ---------------------------------------------------------------------
  // Lifecycle
  // ---------------------------------------------------------------------
  enter() {
    this.controlsEnabled = !this.inCutscene;
    this.player.lock(this.inCutscene);
    this.hud.setVisible(true);
    this.game.ui.camera = this.camera;
    if (!State.current.tutorialField) {
      State.current.tutorialField = true;
      setTimeout(() => this.game.ui.toast((s) => (s.device === 'pad'
        ? `${pb('rs')}로 시점을 돌릴 수 있습니다. ${pb('back')}로 버튼 안내 숨기기`
        : '화면을 클릭하면 마우스로, 또는 <kbd>방향키</kbd>로 시점을 돌릴 수 있습니다. <kbd>C</kbd> 시점 정면으로 · <kbd>H</kbd> 버튼 안내 숨기기'), '', 6000), 600);
      // the core field rule, formerly in the always-on help box
      setTimeout(() => this.game.ui.toast((s) => `적의 노란 <b>브레이크 게이지</b>를 채워 기절시키고 ${s.device === 'pad' ? pb('a') : '<kbd>E</kbd>'} → 선제 공격! 등 뒤를 맞으면 기습당한다.`, 'gold', 8000), 1400);
    }
  }

  exit() {
    this.controlsEnabled = false;
    this.hud.setVisible(false);
    this.hud.setPrompt('');
  }

  /** After a battle: victory removes the enemy, flee pacifies it. */
  afterBattle(result: 'victory' | 'fled', e: FieldEnemy | null) {
    this.player.invuln = 2.5;
    if (!e) return;
    if (result === 'victory') {
      State.current.defeated.add(e.spawn.id);
      e.removed = true;
      e.obj.visible = false;
      if (e.ui) e.ui.root.style.display = 'none';
    } else {
      e.pacify();
      const away = new THREE.Vector3().subVectors(this.player.pos, e.pos).setY(0).normalize();
      this.player.pos.addScaledVector(away, 2.5);
      this.resolveCollisions(this.player.pos, 0.45);
    }
  }

  /** After a defeat / new game: back at the last rest point the party used (or the zone start). */
  respawnPlayer(initial = false) {
    const st = State.current;
    const r = st.lastRest;
    if (!initial && r && r.zone !== this.zone.id) this.loadZone(r.zone);
    const p = this.player;
    const at = !initial && r && r.zone === this.zone.id ? { x: r.x, z: r.z + 2.5, rot: Math.PI } : this.zone.start;
    p.pos.set(at.x, 0, at.z);
    p.yaw = at.rot;
    this.camYaw = p.yaw + Math.PI;
    p.invuln = 2;
    if (!initial) this.resetEnemies();
    this.snapCamera();
  }

  /** Move the party through a gate: fade, build the next zone, arrive just inside its matching gate. */
  async travel(g: GateDef) {
    this.controlsEnabled = false;
    this.player.lock(true);
    const ui = this.game.ui;
    await ui.fadeOut(350);
    this.placeAtGate(g.to, g.toGate);
    this.enter();
    ui.fadeIn(450);
    const z = this.zone;
    ui.banner(z.name, z.sub, 'zone', 1800);
    this.game.autosave();
    await this.game.story.onEnterZone(z.id);
  }

  /** Load `zone` (if needed) and stand the player 4 m inside gate `gateId`, facing away from it. */
  placeAtGate(zone: string, gateId: string) {
    if (this.zone.id !== zone) this.loadZone(zone);
    const to = this.zone.gates.find((x) => x.id === gateId);
    const p = this.player;
    if (to) {
      const inward = new THREE.Vector3(-to.x, 0, -to.z).normalize();
      p.pos.set(to.x + inward.x * (to.r + 3.5), 0, to.z + inward.z * (to.r + 3.5));
      p.yaw = Math.atan2(inward.x, inward.z);
    } else {
      p.pos.set(this.zone.start.x, 0, this.zone.start.z);
      p.yaw = this.zone.start.rot;
    }
    this.camYaw = p.yaw + Math.PI;
    p.invuln = 2;
    this.gateCooldown = 1.5;
    this.snapCamera();
  }

  resetEnemies() {
    State.current.defeated.clear();
    for (const e of this.enemies) e.reset();
    for (const pr of this.projectiles) { this.scene.remove(pr.mesh); this.fx.lights.remove(pr.light); }
    this.projectiles = [];
  }

  private snapCamera() {
    this.updateCamera(1, true);
  }

  resize(w: number, h: number) {
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.fx.setViewport(h * this.game.renderer.getPixelRatio(), this.camera.fov);
  }

  update(rawDt: number) {
    let dt = rawDt;
    if (this.hitstop > 0) { this.hitstop -= rawDt; dt = rawDt * 0.08; }
    this.time += dt;
    this.interactCooldown = Math.max(0, this.interactCooldown - rawDt);
    this.gateCooldown = Math.max(0, this.gateCooldown - rawDt);
    const controls = this.controlsEnabled;

    // camera control
    let turned = false;
    if (controls && Input.locked && (Input.mouseDX || Input.mouseDY)) {
      const sens = 0.0024 * State.current.mouseSens;
      this.camYaw -= Input.mouseDX * sens;
      this.camPitch = clamp(this.camPitch + Input.mouseDY * sens, -0.15, 1.15);
      turned = true;
    }
    if (controls) {
      // arrow keys: ←/→ turn, ↑/↓ look up/down; ramps from 35% to full speed over 0.2 s
      const kx = (Input.isDown('ArrowRight') ? 1 : 0) - (Input.isDown('ArrowLeft') ? 1 : 0);
      const ky = (Input.isDown('ArrowDown') ? 1 : 0) - (Input.isDown('ArrowUp') ? 1 : 0);
      this.camKeyT = kx || ky ? this.camKeyT + rawDt : 0;
      if (kx || ky) {
        const s = Math.min(1, 0.35 + this.camKeyT / 0.2 * 0.65) * rawDt;
        this.camYaw -= kx * KEY_YAW_SPEED * s;
        this.camPitch = clamp(this.camPitch + ky * KEY_PITCH_SPEED * s, -0.15, 1.15);
        turned = true;
      }
      // right stick (squared for fine aim), d-pad ↑↓ zoom, R3 / C recenters behind the player
      const { rx, ry } = Input.stick;
      if (rx || ry) {
        const s = 2.6 * State.current.padSens * rawDt;
        this.camYaw -= rx * Math.abs(rx) * s;
        this.camPitch = clamp(this.camPitch + ry * Math.abs(ry) * s * 0.6, -0.15, 1.15);
        turned = true;
      }
      const zoom = (Input.isDown('PadDown') ? 1 : 0) - (Input.isDown('PadUp') ? 1 : 0);
      if (zoom) this.camDist = clamp(this.camDist + zoom * 6 * rawDt, 3.5, 11);
      if (Input.pressed('PadR3', 'KeyC')) this.camRecenter = this.player.yaw + Math.PI;
      if (this.camRecenter !== null) {
        if (turned || Math.abs(wrapAngle(this.camRecenter - this.camYaw)) < 0.01) this.camRecenter = null;
        else this.camYaw = dampAngle(this.camYaw, this.camRecenter, 12, rawDt);
      }
      // auto-follow: running forward (or diagonally) with the camera left alone for a moment,
      // it drifts behind the player. Not when walking back toward the camera or strafing.
      this.camIdle = turned ? 0 : this.camIdle + rawDt;
      // (W alone already runs away from the camera; this swings it on diagonals, in a wide arc)
      const mi = this.player.moveInput;
      const fwd = -mi.z / (Math.hypot(mi.x, mi.z) || 1);
      if (this.camRecenter === null && this.camIdle > 1 && fwd > 0.3 && this.player.speed > 1) {
        this.camYaw = dampAngle(this.camYaw, this.player.yaw + Math.PI, CAM_FOLLOW * fwd, rawDt);
      }
    }
    if (controls && Input.wheel) this.camDist = clamp(this.camDist + Input.wheel * 0.6, 3.5, 11);
    if (controls && Input.pressed('KeyH', 'PadBack')) this.hud.toggleHelp();

    this.player.update(dt, this.camYaw, controls);
    if (!this.inCutscene) {
      for (const e of this.enemies) e.update(dt);
      this.updateProjectiles(dt);
    }
    this.updateWorld(dt);
    if (controls) { this.updateInteract(); this.updateGates(); this.game.story.tickArea(this.zone.id, this.player.pos); }

    this.fx.update(dt);
    this.updateCamera(rawDt);
    this.hud.update(rawDt);

    // sun follows the player for crisp shadows
    const pp = this.player.pos;
    this.sun.position.set(pp.x - 30, pp.y + 45, pp.z + 34);
    this.sun.target.position.copy(pp);
    animateBackdrop(this.backdrop, this.time);
    animateMotes(this.motes, this.time, dt, pp, 60, pp.y - 1);
  }

  private updateProjectiles(dt: number) {
    for (let i = this.projectiles.length - 1; i >= 0; i--) {
      const pr = this.projectiles[i];
      pr.life -= dt;
      pr.mesh.position.addScaledVector(pr.vel, dt);
      pr.light.position.copy(pr.mesh.position);
      this.fx.sparks.emit(pr.mesh.position, { color: 0xffa040, life: 0.3, size: 0.4, sizeEnd: 0.05, alpha: 0.8 });
      const d = pr.mesh.position.distanceTo(this.player.pos.clone().add(new THREE.Vector3(0, 1, 0)));
      const ground = pr.mesh.position.y < this.groundAt(pr.mesh.position.x, pr.mesh.position.z);
      if (d < 0.8 && this.player.invuln <= 0 && this.controlsEnabled) {
        this.scene.remove(pr.mesh);
        this.fx.lights.remove(pr.light);
        this.projectiles.splice(i, 1);
        this.fx.sparks.burst(pr.mesh.position, 20, { color: 0xffa040, speed: 5, life: 0.4, size: 0.15 });
        this.contact(pr.owner);
        return;
      }
      if (pr.life <= 0 || ground) {
        this.fx.sparks.burst(pr.mesh.position, 10, { color: 0xffa040, speed: 3, life: 0.3, size: 0.12 });
        this.scene.remove(pr.mesh);
        this.fx.lights.remove(pr.light);
        this.projectiles.splice(i, 1);
      }
    }
  }

  private updateWorld(dt: number) {
    const t = this.time;
    // airship
    const a = t * 0.05;
    if (this.airship) {
      this.airship.position.set(Math.cos(a) * 48, 34 + Math.sin(t * 0.5) * 1.2, Math.sin(a) * 48 - 10);
      this.airship.rotation.y = -a;
      this.airship.rotation.z = Math.sin(t * 0.4) * 0.03;
    }
    if (this.propeller) this.propeller.rotation.z = t * 12;
    for (const n of this.npcs) n.anim.update(dt);
    // gate markers: a slow golden ring pulse on the ground
    for (const gf of this.gateFx) {
      gf.t -= dt;
      if (gf.t > 0) continue;
      gf.t = 1.1;
      const open = !gf.g.needFlag || State.current.flag(gf.g.needFlag);
      this.fx.ring(new THREE.Vector3(gf.g.x, heightAt(gf.g.x, gf.g.z) + 0.15, gf.g.z), open ? 0xffd27a : 0x8d816c, gf.g.r + 0.8, 1.0);
    }
    for (const w of this.wispLights) {
      const on = w.e.alive && w.e.obj.visible;
      if (on) w.node.getWorldPosition(w.l.position);
      const flicker = 1 + Math.sin(t * 17 + w.phase) * 0.08 + Math.sin(t * 7.3 + w.phase) * 0.06;
      w.l.intensity = on ? 4 * flicker : 0;
    }
    for (const r of this.rests) {
      const c = r.crystal;
      if (!c) continue;
      c.rotation.y = t * 1.2;
      c.position.y = (c.userData.baseY ??= c.position.y) + Math.sin(t * 2) * 0.08;
    }
    // vents
    this.ventT -= dt;
    if (this.ventT <= 0) {
      this.ventT = 0.06;
      for (const v of this.steamVents) {
        if (v.distanceTo(this.player.pos) > 45) continue;
        this.fx.smoke.emit(v.clone().add(new THREE.Vector3(rand(-0.3, 0.3), 0, rand(-0.3, 0.3))), {
          vel: new THREE.Vector3(rand(-0.3, 0.3), rand(2.5, 4), rand(-0.3, 0.3)), color: 0xf4f1ea, life: 1.6, size: 0.5, sizeEnd: 2.2, alpha: 0.35, drag: 0.6,
        });
      }
    }
    // chest lids
    for (const c of this.chests) {
      const target = State.current.openedChests.has(c.def.id) ? 1 : 0;
      c.open = damp(c.open, target, 6, dt);
      if (c.lid) c.lid.rotation.x = -c.open * 1.9;
    }
  }

  /** Walking into a gate ring travels; a shut gate says why once and pushes the player back. */
  private updateGates() {
    if (this.gateCooldown > 0) return;
    const p = this.player.pos;
    for (const g of this.zone.gates) {
      if (!flagsAllow(g) || Math.hypot(p.x - g.x, p.z - g.z) > g.r) continue;
      if (g.needFlag && !State.current.flag(g.needFlag)) {
        this.game.ui.toast(g.lockedText ?? '아직 갈 수 없다.', 'red');
        const back = new THREE.Vector3(-g.x, 0, -g.z).normalize();
        p.addScaledVector(back, 2);
        this.gateCooldown = 1.2;
        return;
      }
      void this.travel(g);
      return;
    }
  }

  private updateInteract() {
    const p = this.player.pos;
    let prompt = '';
    let action: (() => void) | null = null;
    // battle engage
    const e = this.nearestEnemy(p, 3.4);
    if (e) {
      if (e.stunned) {
        prompt = `<span class="kw">선제 공격!</span> ${e.sp.name}와(과) 유리한 전투 개시`;
        action = () => { Sfx.play('advantage'); this.startBattle(e, 'party'); };
      } else {
        prompt = `${e.sp.name}와(과) 전투 개시 <span class="dim">(브레이크 시키면 선제 공격)</span>`;
        action = () => this.startBattle(e, 'none');
      }
    } else if (this.nearNpc(p)) {
      const n = this.nearNpc(p)!;
      prompt = `<b>${n.def.name}</b>와(과) 이야기하기`;
      action = () => this.talkTo(n);
    } else if (this.nearSpot(p)) {
      const sp = this.nearSpot(p)!;
      prompt = sp.label;
      action = () => void this.useSpot(sp);
    } else if (this.rests.some((r) => Math.hypot(p.x - r.x, p.z - r.z) < 3)) {
      const r = this.rests.find((rr) => Math.hypot(p.x - rr.x, p.z - rr.z) < 3)!;
      prompt = `점등 표지에서 휴식 <span class="dim">(HP 회복 · 저장 · 동료와 대화 · 적 재배치)</span>`;
      action = () => void this.doRest(r);
    } else {
      for (const c of this.chests) {
        if (State.current.openedChests.has(c.def.id)) continue;
        if (Math.hypot(p.x - c.def.x, p.z - c.def.z) < 2.2) {
          prompt = `보물상자 열기`;
          action = () => this.openChest(c);
          break;
        }
      }
    }
    this.hud.setPrompt(prompt); // the HUD prefixes the interact key for the current device
    if (action && Input.pressed('KeyE', 'PadA') && this.interactCooldown <= 0) {
      this.interactCooldown = 0.5;
      action();
    }
  }

  private nearNpc(p: THREE.Vector3) {
    return this.npcs.find((n) => !n.def.silent && Math.hypot(p.x - n.def.x, p.z - n.def.z) < 2.4) ?? null;
  }
  private nearSpot(p: THREE.Vector3) {
    return this.zone.spots.find((s) => flagsAllow(s) && Math.hypot(p.x - s.x, p.z - s.z) < s.r) ?? null;
  }

  private async talkTo(n: Npc) {
    // the NPC turns to face Kai while they talk
    n.obj.rotation.y = Math.atan2(this.player.pos.x - n.def.x, this.player.pos.z - n.def.z);
    await this.cutscene(() => this.game.story.talk(n.def.id));
    n.obj.rotation.y = n.def.rot;
  }

  private async useSpot(sp: SpotDef) {
    await this.cutscene(() => this.game.story.spot(sp.id));
  }

  /** Run a story beat with field control suspended (enemies hold still, prompts hide). */
  async cutscene(fn: () => Promise<unknown>) {
    if (this.inCutscene) return;
    this.inCutscene = true;
    this.controlsEnabled = false;
    this.player.lock(true);
    this.hud.setPrompt('');
    Input.exitLock();
    try { await fn(); } finally {
      this.inCutscene = false;
      if (this.game.mode === 'field') {
        this.controlsEnabled = true;
        this.player.lock(false);
        this.interactCooldown = 0.4;
        Input.consumePressed();
      }
    }
  }

  private async doRest(r: (typeof this.rests)[number]) {
    const st = State.current;
    st.healAll();
    st.lastRest = { zone: this.zone.id, x: r.x, z: r.z };
    st.setFlag('rests', st.flag('rests') + 1);
    this.resetEnemies();
    Sfx.play('rest');
    this.fx.pillar(r.obj.position.clone(), 0x5ff3ff, 6, 1.4, 1.4);
    this.game.ui.toast('점등 표지 곁에서 쉬었다. 파티가 완전히 회복되었다. <span class="dim">몬스터가 다시 나타났다.</span>', 'cyan');
    this.game.autosave();
    await this.cutscene(() => this.game.story.rest());
  }

  // ---------------------------------------------------------------------
  // Save / load (game/save.ts)
  // ---------------------------------------------------------------------
  /** Name shown on save slots and the load banner. */
  placeName() {
    return `${this.zone.name} · ${this.zone.sub}`;
  }

  /** Copy the party's position into the state right before it is saved. */
  captureState() {
    const p = this.player;
    State.current.zone = this.zone.id;
    State.current.pos = { x: p.pos.x, z: p.pos.z, yaw: p.yaw };
  }

  /** Rebuild the field from a freshly loaded state: defeated enemies stay gone, opened chests stay open. */
  syncFromState() {
    const st = State.current;
    // always rebuild: spawns, NPCs and gates depend on the loaded story flags
    this.loadZone(ZONES[st.zone] ? st.zone : 'plains');
    for (const e of this.enemies) {
      e.reset();
      if (st.defeated.has(e.spawn.id)) {
        e.removed = true;
        e.obj.visible = false;
        if (e.ui) e.ui.root.style.display = 'none';
      }
    }
    for (const c of this.chests) c.open = st.openedChests.has(c.def.id) ? 1 : 0;
    const p = this.player;
    if (st.pos) {
      p.pos.set(st.pos.x, 0, st.pos.z);
      p.yaw = st.pos.yaw;
    } else {
      p.pos.set(this.zone.start.x, 0, this.zone.start.z);
      p.yaw = this.zone.start.rot;
    }
    this.camYaw = p.yaw + Math.PI;
    p.invuln = 2;
    this.snapCamera();
  }

  private openChest(c: Chest) {
    const st = State.current;
    st.openedChests.add(c.def.id);
    const parts: string[] = [];
    for (const [id, n] of Object.entries(c.def.items)) {
      st.addItem(id, n);
      parts.push(`${icon('item', id, ITEMS[id].icon)} ${ITEMS[id].name} ×${n}`);
    }
    for (const [id, n] of Object.entries(c.def.parts ?? {})) {
      st.parts[id] = (st.parts[id] ?? 0) + n;
      parts.push(`부품 <b>${PARTS[id].name}</b>`);
    }
    if (c.def.crystals) {
      st.addCrystals(c.def.crystals);
      for (const [e, n] of Object.entries(c.def.crystals)) parts.push(`${icon('el', e, '◆')} ${CRYSTAL[e as Element]} ×${n}`);
    }
    if (c.def.money) { st.money += c.def.money; parts.push(`⚙ ${c.def.money} 기어`); }
    if (c.def.flag) { st.setFlag(c.def.flag); if (c.def.flagText) parts.unshift(`<b>${c.def.flagText}</b>`); this.game.story.refresh(); }
    Sfx.play('chest');
    this.fx.sparks.burst(c.obj.position.clone().add(new THREE.Vector3(0, 0.8, 0)), 30, { color: 0xffd34a, speed: 4, up: 1.5, life: 0.8, size: 0.14, gravity: 4 });
    this.game.ui.toast(`보물상자: ${parts.join(' · ')}`, 'gold', 3500);
  }

  private updateCamera(dt: number, snap = false) {
    if (this.cine && this.time < this.cine.until) {
      const k = 1 - Math.exp(-3 * dt);
      this.camPos.lerp(this.cine.pos, k);
      this.camLook.lerp(this.cine.look, k);
      this.camera.position.copy(this.camPos);
      this.camera.lookAt(this.camLook);
      return;
    }
    this.cine = null;
    const p = this.player.pos;
    const look = new THREE.Vector3(p.x, p.y + 1.5, p.z);
    const cp = Math.cos(this.camPitch);
    const off = new THREE.Vector3(Math.sin(this.camYaw) * cp, Math.sin(this.camPitch), Math.cos(this.camYaw) * cp).multiplyScalar(this.camDist);
    const want = look.clone().add(off);
    const gy = this.groundAt(want.x, want.z) + 0.6;
    if (want.y < gy) want.y = gy;
    if (snap) { this.camPos.copy(want); this.camLook.copy(look); }
    else {
      const k = 1 - Math.exp(-14 * dt);
      this.camPos.lerp(want, k);
      this.camLook.lerp(look, 1 - Math.exp(-20 * dt));
    }
    this.camera.position.copy(this.camPos);
    if (this.shake > 0) {
      this.shake = Math.max(0, this.shake - dt * 2.5);
      const s = this.shake * 0.25;
      this.camera.position.add(new THREE.Vector3(rand(-s, s), rand(-s, s), rand(-s, s)));
    }
    this.camera.lookAt(this.camLook);
  }
}

/** Arrow-key camera turn rates at full speed (rad/s). */
const KEY_YAW_SPEED = 2.2;
const KEY_PITCH_SPEED = 1.1;
/** Auto-follow strength: on a diagonal it turns the camera ~0.3 rad/s (a ~25 m running circle). */
const CAM_FOLLOW = 0.55;

/** Cell size (m) for merged static props: big enough to cut draw calls, small enough to still cull. */
const STATIC_CELL = 48;

/**
 * Merge never-moving props into one mesh per (material, cell). The hi-poly props export one
 * primitive per Blender material slot, so 45 placed props were 355 draw calls (+ the shadow pass).
 */
function mergeStatic(objs: THREE.Object3D[]) {
  const g = new THREE.Group();
  const buckets = new Map<string, { mat: THREE.Material; cast: boolean; geos: THREE.BufferGeometry[] }>();
  const c = new THREE.Vector3();
  for (const o of objs) {
    o.updateMatrixWorld(true);
    o.getWorldPosition(c);
    const cell = `${Math.floor(c.x / STATIC_CELL)},${Math.floor(c.z / STATIC_CELL)}`;
    o.traverse((n) => {
      const mesh = n as THREE.Mesh;
      if (!mesh.isMesh || Array.isArray(mesh.material)) return;
      const geo = mesh.geometry.clone().applyMatrix4(mesh.matrixWorld);
      const layout = Object.keys(geo.attributes).sort().join(',') + (geo.index ? ':i' : ':n');
      const key = `${mesh.material.uuid}|${cell}|${layout}|${mesh.castShadow}`;
      let b = buckets.get(key);
      if (!b) buckets.set(key, (b = { mat: mesh.material, cast: mesh.castShadow, geos: [] }));
      b.geos.push(geo);
    });
  }
  for (const b of buckets.values()) {
    const merged = b.geos.length > 1 ? mergeGeometries(b.geos) : b.geos[0];
    if (!merged) continue;
    const m = new THREE.Mesh(merged, b.mat);
    m.castShadow = b.cast;
    m.receiveShadow = true;
    m.matrixAutoUpdate = false; // geometry is already in world space
    g.add(m);
  }
  return g;
}

/** Build InstancedMeshes for each mesh inside a prop. */
/** Chunk size (m) for instanced scatter: one InstancedMesh per chunk and primitive, so the camera and
 *  the sun's shadow camera (±38 m around the player) can frustum-cull far instances of the hi-poly
 *  trees / rocks instead of always drawing all of them. */
const SCATTER_CHUNK = 44;

function instanceProp(name: string, mats: THREE.Matrix4[]) {
  const proto = getProp(name);
  proto.updateMatrixWorld(true);
  const g = new THREE.Group();
  const cells = new Map<string, THREE.Matrix4[]>();
  const p = new THREE.Vector3();
  for (const m of mats) {
    p.setFromMatrixPosition(m);
    const key = `${Math.floor(p.x / SCATTER_CHUNK)},${Math.floor(p.z / SCATTER_CHUNK)}`;
    let list = cells.get(key);
    if (!list) cells.set(key, (list = []));
    list.push(m);
  }
  const tmp = new THREE.Matrix4();
  proto.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh) return;
    const local = mesh.matrixWorld;
    for (const list of cells.values()) {
      const inst = new THREE.InstancedMesh(mesh.geometry, mesh.material, list.length);
      list.forEach((m, i) => inst.setMatrixAt(i, tmp.multiplyMatrices(m, local)));
      inst.castShadow = mesh.castShadow; // assets.prepare() turns it off for glow/jelly/glass parts
      inst.receiveShadow = true;
      inst.computeBoundingSphere();
      g.add(inst);
    }
  });
  return g;
}

/** Spawn / NPC / spot visibility from story flags. */
export function flagsAllow(d: { afterFlag?: string; untilFlag?: string; when?: () => boolean }) {
  const st = State.current;
  return (!d.afterFlag || !!st.flag(d.afterFlag)) && (!d.untilFlag || !st.flag(d.untilFlag)) && (!d.when || d.when());
}
function spawnActive(sp: SpawnDef) {
  return flagsAllow(sp);
}
