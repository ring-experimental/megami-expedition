import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { getProp } from '../core/assets';
import { Input } from '../core/input';
import { Sfx } from '../core/audio';
import { clamp, damp, dampAngle, mulberry32, rand, wrapAngle } from '../core/utils';
import { Effects } from '../fx/effects';
import { FakeLight, patchObject } from '../fx/fakeLights';
import { animateBackdrop, animateMotes, buildBackdrop, buildMotes, buildSky, getEnvMap } from '../fx/environment';
import { CHESTS, PLAYER_START, PROPS, REST_POINT, SPAWNS, WORLD_RADIUS, ZONE_NAME, type Circle, type ChestDef } from '../data/world';
import { ITEMS } from '../data/items';
import { SPECIES } from '../data/units';
import { State } from '../game/state';
import { FieldHud } from '../ui/fieldHud';
import { icon } from '../ui/art';
import { pb } from '../ui/glyph';
import type { Game } from '../game/game';
import { Player } from './player';
import { FieldEnemy } from './fieldEnemy';
import { buildGrass, buildTerrain, heightAt, plazaMask, roadMask } from './terrain';

interface Projectile { mesh: THREE.Object3D; light: FakeLight; vel: THREE.Vector3; life: number; owner: FieldEnemy }

const PROJ_GEO = new THREE.SphereGeometry(0.28, 10, 8);
const PROJ_MAT = new THREE.MeshBasicMaterial({ color: 0xffa040 });
interface Chest { def: ChestDef; obj: THREE.Object3D; lid: THREE.Object3D | null; open: number }

export class FieldMode {
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(55, 1, 0.1, 900);
  fx: Effects;
  player: Player;
  enemies: FieldEnemy[] = [];
  hud: FieldHud;
  colliders: Circle[] = [];
  controlsEnabled = false;
  private sun: THREE.DirectionalLight;
  private projectiles: Projectile[] = [];
  private chests: Chest[] = [];
  private rest!: THREE.Object3D;
  private restCrystal: THREE.Object3D | null = null;
  private airship!: THREE.Object3D;
  private propeller: THREE.Object3D | null = null;
  /** Warm light carried by each lamp wisp (fixed pool: the light count never changes, so killing a
   *  wisp doesn't trigger a shader recompile — the light just fades to 0). */
  private wispLights: { e: FieldEnemy; l: FakeLight; node: THREE.Object3D; phase: number }[] = [];
  private steamVents: THREE.Vector3[] = [];
  private backdrop: THREE.Object3D;
  private motes: THREE.Points;
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

  constructor(private game: Game) {
    const s = this.scene;
    s.environment = getEnvMap(game.renderer);
    s.environmentIntensity = 0.45;
    s.fog = new THREE.Fog('#e9c99b', 60, 230);
    s.add(buildSky({ top: '#3f7fb8', horizon: '#ffd7a0', bottom: '#c9a57a', sun: '#ffe2b0', sunDir: new THREE.Vector3(-0.5, 0.35, 0.6) }));
    this.backdrop = buildBackdrop({ mountainColor: '#8f8aa6', cloudColor: '#ffe9d2', radius: 170 });
    s.add(this.backdrop);

    s.add(new THREE.HemisphereLight('#ffe2bd', '#5a6a45', 1.1));
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
    s.add(buildTerrain());
    this.buildProps();
    s.add(buildGrass((x, z) => this.colliders.some((c) => Math.hypot(c.x - x, c.z - z) < c.r + 0.4)));
    this.motes = buildMotes(260, 60);
    s.add(this.motes);

    this.player = new Player(this);
    s.add(this.player.obj);
    this.hud = new FieldHud(game.ui, this);

    for (const sp of SPAWNS) {
      const e = new FieldEnemy(sp, this);
      this.enemies.push(e);
      s.add(e.obj);
    }
    for (const e of this.enemies) {
      if (e.sp.archetype !== 'wisp') continue;
      const l = this.fx.lights.add(new FakeLight('#ffb060', 0, 7));
      this.wispLights.push({ e, l, node: e.anim.rig.get('flame') ?? e.model, phase: Math.random() * 6 });
    }
    // every lit material samples the fake-light array (no real PointLights in this scene)
    patchObject(s);
    this.respawnPlayer(true);
  }

  // ---------------------------------------------------------------------
  // World building
  // ---------------------------------------------------------------------
  private buildProps() {
    const s = this.scene;
    const statics: THREE.Object3D[] = [];
    for (const p of PROPS) {
      const o = getProp(p.name);
      o.position.set(p.x, (p.y ?? 0) + heightAt(p.x, p.z), p.z);
      o.rotation.y = p.rot ?? 0;
      o.scale.setScalar(p.scale ?? 1);
      // the rest point's crystal animates; everything else never moves → merged below
      if (p.name === 'prop_rest') s.add(o);
      else statics.push(o);
      const cos = Math.cos(p.rot ?? 0), sin = Math.sin(p.rot ?? 0), k = p.scale ?? 1;
      for (const c of p.colliders ?? []) {
        // rotate local collider offset by the prop's yaw (three.js: x' = x cos + z sin, z' = -x sin + z cos)
        this.colliders.push({ x: p.x + (c.x * cos + c.z * sin) * k, z: p.z + (-c.x * sin + c.z * cos) * k, r: c.r * k });
      }
      if (p.steam) this.steamVents.push(new THREE.Vector3(p.x, heightAt(p.x, p.z) + 0.2, p.z));
      if (p.name === 'prop_rest') {
        this.rest = o;
        this.restCrystal = o.getObjectByName('crystal') ?? null;
        const l = this.fx.lights.add(new FakeLight('#5ff3ff', 8, 10));
        o.updateMatrixWorld(true);
        l.position.set(0, 2.2, 0).applyMatrix4(o.matrixWorld);
      }
      if (p.name === 'prop_lamp') {
        const l = this.fx.lights.add(new FakeLight('#7ff0ff', 6, 9));
        o.updateMatrixWorld(true);
        l.position.set(0, 3.2, 0).applyMatrix4(o.matrixWorld);
      }
    }
    for (const c of CHESTS) {
      const o = getProp('prop_chest');
      o.position.set(c.x, heightAt(c.x, c.z), c.z);
      o.rotation.y = c.rot;
      s.add(o);
      this.colliders.push({ x: c.x, z: c.z, r: 0.6 });
      this.chests.push({ def: c, obj: o, lid: o.getObjectByName('lid') ?? null, open: 0 });
    }
    s.add(mergeStatic(statics));
    // airship circling overhead
    this.airship = getProp('prop_airship');
    this.propeller = this.airship.getObjectByName('propeller') ?? null;
    s.add(this.airship);

    // scatter trees / rocks / bushes (instanced)
    const rnd = mulberry32(1234);
    const placed: { name: string; m: THREE.Matrix4 }[] = [];
    const ok = (x: number, z: number, clear: number) =>
      roadMask(x, z) < 0.05 && plazaMask(x, z) < 0.05 &&
      Math.hypot(x - PLAYER_START.x, z - PLAYER_START.z) > 8 &&
      !this.colliders.some((c) => Math.hypot(c.x - x, c.z - z) < c.r + clear) &&
      !SPAWNS.some((sp) => Math.hypot(sp.x - x, sp.z - z) < sp.wander + 2);
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
        if (colR > 0 && r < WORLD_RADIUS + 2) this.colliders.push({ x, z, r: colR * sc });
        n++;
      }
    };
    place('prop_tree', 46, 50, 92, 0.6, 0.9, 1.35);
    place('prop_tree_b', 30, 46, 92, 0.6, 0.85, 1.3);
    place('prop_tree', 10, 15, 48, 0.6, 0.8, 1.1);
    place('prop_tree_b', 8, 15, 48, 0.6, 0.8, 1.1);
    place('prop_rock_a', 22, 20, 90, 1.25, 0.7, 1.6); // wide slab boulder (~1.25 m footprint radius)
    place('prop_rock_b', 22, 20, 90, 0.9, 0.7, 1.6); // tall standing stone
    place('prop_bush', 70, 10, 74, 0, 0.7, 1.4);
    const byName = new Map<string, THREE.Matrix4[]>();
    for (const p of placed) {
      if (!byName.has(p.name)) byName.set(p.name, []);
      byName.get(p.name)!.push(p.m);
    }
    for (const [name, mats] of byName) s.add(instanceProp(name, mats));
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
    const rr = Math.hypot(p.x, p.z);
    if (rr > WORLD_RADIUS) { p.x *= WORLD_RADIUS / rr; p.z *= WORLD_RADIUS / rr; }
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
    const ups = st.activeMembers().map((m) => st.giveXp(m, xp)).filter(Boolean);
    this.fx.sparks.burst(e.pos.clone().add(new THREE.Vector3(0, 0.6, 0)), 30, { color: 0xb8ffef, speed: 4, life: 0.8, size: 0.14, up: 1 });
    this.game.ui.toast(`<b>${e.sp.name}</b> 필드 처치 · EXP +${xp} · ${money} 기어 <span class="dim">(턴제 전투보다 보상이 적고 영입 불가)</span>`);
    for (const u of ups) if (u) this.game.ui.toast(`<b>${u.name}</b> 레벨 업! Lv${u.from} → Lv${u.to}`, 'gold');
    if (ups.length) Sfx.play('levelup');
  }

  /** Enemy body/attack touched the player → battle. */
  contact(e: FieldEnemy) {
    if (!this.controlsEnabled) return;
    const ambush = this.player.isBehind(e);
    this.startBattle(e, ambush ? 'enemy' : 'none');
  }

  startBattle(e: FieldEnemy, advantage: 'party' | 'enemy' | 'none') {
    this.controlsEnabled = false;
    this.player.lock(true);
    this.game.startBattle({
      formation: e.spawn.formation,
      leaderHp: e.killable ? e.hp / e.hpMax : 1,
      advantage,
      source: e,
    });
  }

  // ---------------------------------------------------------------------
  // Lifecycle
  // ---------------------------------------------------------------------
  enter() {
    this.controlsEnabled = true;
    this.player.lock(false);
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

  respawnPlayer(initial = false) {
    const p = this.player;
    p.pos.set(PLAYER_START.x, 0, PLAYER_START.z);
    p.yaw = PLAYER_START.rot;
    this.camYaw = p.yaw + Math.PI;
    p.invuln = 2;
    if (!initial) this.resetEnemies();
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
    for (const e of this.enemies) e.update(dt);
    this.updateProjectiles(dt);
    this.updateWorld(dt);
    if (controls) this.updateInteract();

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
    this.airship.position.set(Math.cos(a) * 48, 34 + Math.sin(t * 0.5) * 1.2, Math.sin(a) * 48 - 10);
    this.airship.rotation.y = -a;
    this.airship.rotation.z = Math.sin(t * 0.4) * 0.03;
    if (this.propeller) this.propeller.rotation.z = t * 12;
    for (const w of this.wispLights) {
      const on = w.e.alive && w.e.obj.visible;
      if (on) w.node.getWorldPosition(w.l.position);
      const flicker = 1 + Math.sin(t * 17 + w.phase) * 0.08 + Math.sin(t * 7.3 + w.phase) * 0.06;
      w.l.intensity = on ? 4 * flicker : 0;
    }
    if (this.restCrystal) {
      this.restCrystal.rotation.y = t * 1.2;
      this.restCrystal.position.y = (this.restCrystal.userData.baseY ??= this.restCrystal.position.y) + Math.sin(t * 2) * 0.08;
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
    } else if (Math.hypot(p.x - REST_POINT.x, p.z - REST_POINT.z) < 3) {
      prompt = `에테르 샘에서 휴식 <span class="dim">(HP 전부 회복 · 적 재배치)</span>`;
      action = () => this.doRest();
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

  private doRest() {
    State.current.healAll();
    this.resetEnemies();
    Sfx.play('rest');
    this.fx.pillar(this.rest.position.clone(), 0x5ff3ff, 6, 1.4, 1.4);
    this.game.ui.toast('에테르 샘의 힘으로 파티가 완전히 회복되었다. <span class="dim">몬스터가 다시 나타났다.</span>', 'cyan');
    this.game.autosave();
  }

  // ---------------------------------------------------------------------
  // Save / load (game/save.ts)
  // ---------------------------------------------------------------------
  /** Name shown on save slots and the load banner. */
  placeName() {
    return ZONE_NAME;
  }

  /** Copy the party's position into the state right before it is saved. */
  captureState() {
    const p = this.player;
    State.current.zone = 'plains';
    State.current.pos = { x: p.pos.x, z: p.pos.z, yaw: p.yaw };
  }

  /** Rebuild the field from a freshly loaded state: defeated enemies stay gone, opened chests stay open. */
  syncFromState() {
    const st = State.current;
    for (const pr of this.projectiles) { this.scene.remove(pr.mesh); this.fx.lights.remove(pr.light); }
    this.projectiles = [];
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
      p.pos.set(PLAYER_START.x, 0, PLAYER_START.z);
      p.yaw = PLAYER_START.rot;
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
    st.money += c.def.money;
    parts.push(`⚙ ${c.def.money} 기어`);
    Sfx.play('chest');
    this.fx.sparks.burst(c.obj.position.clone().add(new THREE.Vector3(0, 0.8, 0)), 30, { color: 0xffd34a, speed: 4, up: 1.5, life: 0.8, size: 0.14, gravity: 4 });
    this.game.ui.toast(`보물상자: ${parts.join(' · ')}`, 'gold', 3500);
  }

  private updateCamera(dt: number, snap = false) {
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
