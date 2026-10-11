import * as THREE from 'three';
import { Animator } from '../anim/rig';
import { getModel } from '../core/assets';
import { Sfx } from '../core/audio';
import { Input } from '../core/input';
import { dampAngle, rand } from '../core/utils';
import type { SpawnDef } from '../data/world';
import { SPECIES, type SpeciesDef } from '../data/units';
import { SteamVent } from '../fx/effects';
import type { FieldMode } from './field';

export type EState = 'idle' | 'wander' | 'notice' | 'chase' | 'windup' | 'lunge' | 'recover' | 'flinch' | 'stunned' | 'dead' | 'cooldown' | 'return';

export class FieldEnemy {
  obj = new THREE.Group();
  model: THREE.Object3D;
  anim: Animator;
  sp: SpeciesDef;
  home: THREE.Vector3;
  yaw = rand(0, Math.PI * 2);
  state: EState = 'idle';
  t = 0;
  hp: number;
  hpMax: number;
  brk = 0;
  brkMax: number;
  lastHit = -99;
  wanderTarget = new THREE.Vector3();
  telegraph: { set: (k: number) => void; remove: () => void } | null = null;
  lungeDir = new THREE.Vector3();
  removed = false;
  flashT = 0;
  ui: { root: HTMLElement; hp: HTMLElement; brk: HTMLElement; tag: HTMLElement } | null = null;
  private time = 0;
  private starT = 0;
  /** Chimney steam (steam golem) — any model with a `steam_point` node. */
  private steam: SteamVent | null = null;
  private sink = 0;

  constructor(public spawn: SpawnDef, private field: FieldMode) {
    this.sp = SPECIES[spawn.formation[0]];
    this.model = getModel(this.sp.model);
    this.model.scale.setScalar(this.sp.scale);
    this.obj.add(this.model);
    this.anim = new Animator(this.model, this.sp.archetype);
    const sp = this.anim.rig.get('steam_point');
    if (sp) this.steam = new SteamVent(sp, 'chimney', this.sp.scale);
    this.home = new THREE.Vector3(spawn.x, 0, spawn.z);
    this.obj.position.copy(this.home);
    this.hpMax = this.hp = this.sp.stats.hp;
    this.brkMax = this.sp.field.breakMax;
    this.pickWander();
  }

  get pos() {
    return this.obj.position;
  }
  get alive() {
    return this.state !== 'dead' && !this.removed;
  }
  get stunned() {
    return this.state === 'stunned';
  }
  get radius() {
    return this.sp.radius * this.sp.scale;
  }
  /** Whether this enemy can be killed in the field (weak tier only). */
  get killable() {
    return this.sp.tier === 'weak';
  }

  private set(s: EState) {
    if (this.state === 'windup' || this.state === 'lunge') this.clearTelegraph();
    this.state = s;
    this.t = 0;
  }

  private pickWander() {
    const a = rand(0, Math.PI * 2), r = rand(0, this.spawn.wander);
    this.wanderTarget.set(this.home.x + Math.cos(a) * r, 0, this.home.z + Math.sin(a) * r);
  }

  private clearTelegraph() {
    this.telegraph?.remove();
    this.telegraph = null;
  }

  update(dt: number) {
    if (this.removed) return;
    this.time += dt;
    this.t += dt;
    const player = this.field.player;
    const toP = new THREE.Vector3().subVectors(player.pos, this.pos).setY(0);
    const dist = toP.length();
    const f = this.sp.field;
    let speed = 0;
    const faceTo = (dir: THREE.Vector3, k = 8) => { if (dir.lengthSq() > 1e-4) this.yaw = dampAngle(this.yaw, Math.atan2(dir.x, dir.z), k, dt); };

    // break gauge decays after a while
    if (this.state !== 'stunned' && this.time - this.lastHit > 3.5) this.brk = Math.max(0, this.brk - dt * this.brkMax * 0.12);

    switch (this.state) {
      case 'idle':
      case 'wander': {
        if (this.state === 'idle' && this.t > rand(1.5, 3)) this.set('wander');
        if (this.state === 'wander') {
          const d = new THREE.Vector3().subVectors(this.wanderTarget, this.pos).setY(0);
          if (d.length() < 0.5 || this.t > 6) { this.pickWander(); this.set('idle'); }
          else { faceTo(d, 4); speed = f.speed * 0.35; }
        }
        if (dist < f.detect && this.field.controlsEnabled && player.invuln <= 0) {
          this.set('notice');
          this.field.hud.alert(this);
          Sfx.play('alert');
        }
        break;
      }
      case 'notice':
        faceTo(toP, 10);
        if (this.t > 0.45) this.set('chase');
        break;
      case 'chase': {
        faceTo(toP, 8);
        const attackRange = f.attack === 'projectile' ? 9 : 3.6 + this.radius;
        if (dist > attackRange * 0.85) speed = f.speed;
        if (dist < attackRange && this.t > 0.4) {
          this.set('windup');
          this.anim.play('windup', 1 / Math.max(0.3, f.windup) * 0.5);
          this.telegraph = this.field.fx.telegraph(this.obj, f.attack === 'projectile' ? 9 : 4.2, f.attack === 'projectile' ? 0.9 : this.radius * 2 + 0.4);
        }
        if (this.home.distanceTo(this.pos.clone().setY(0)) > 26 || dist > f.detect * 2.2) this.set('return');
        break;
      }
      case 'windup': {
        if (this.t < f.windup * 0.7) faceTo(toP, 6);
        this.telegraph?.set(Math.min(1, this.t / f.windup));
        if (this.t >= f.windup) {
          this.clearTelegraph();
          this.anim.release();
          this.anim.play('strike');
          if (f.attack === 'projectile') {
            this.field.spawnProjectile(this);
            this.set('recover');
          } else {
            this.lungeDir.set(Math.sin(this.yaw), 0, Math.cos(this.yaw));
            this.set('lunge');
            Sfx.play('swing');
          }
        }
        break;
      }
      case 'lunge': {
        const k = this.t / 0.38;
        const sp = 12 * (1 - k * 0.6);
        this.pos.addScaledVector(this.lungeDir, sp * dt);
        this.field.resolveCollisions(this.pos, this.radius * 0.8, false, this);
        if (dist < this.radius + 0.55 && player.invuln <= 0) {
          this.field.contact(this);
          return;
        }
        if (this.t >= 0.38) this.set('recover');
        break;
      }
      case 'recover':
        if (this.t > 1.1) this.set('chase');
        break;
      case 'flinch':
        if (this.t > 0.45) this.set('chase');
        break;
      case 'stunned':
        this.anim.stunned = true;
        this.starT -= dt;
        if (this.starT <= 0) {
          this.starT = 0.12;
          const a = this.time * 6;
          const top = this.topPos();
          this.field.fx.sparks.emit(top.add(new THREE.Vector3(Math.cos(a) * 0.5, 0, Math.sin(a) * 0.5)), { color: 0xffe066, life: 0.5, size: 0.22, sizeEnd: 0.05 });
        }
        if (this.t > 6) {
          this.anim.stunned = false;
          this.brk = 0;
          this.set('chase');
        }
        break;
      case 'cooldown':
        if (this.t > 4) this.set('return');
        break;
      case 'return': {
        const d = new THREE.Vector3().subVectors(this.home, this.pos).setY(0);
        faceTo(d, 5);
        speed = f.speed * 0.8;
        if (d.length() < 1) { this.set('idle'); }
        if (dist < f.detect * 0.6 && this.t > 2 && this.field.controlsEnabled) this.set('chase');
        break;
      }
      case 'dead': {
        this.sink += dt * 0.7 * Math.min(1, this.t / 0.6);
        if (this.t > 1.4) { this.removed = true; this.obj.visible = false; }
        break;
      }
    }

    if (speed > 0) {
      const fwd = new THREE.Vector3(Math.sin(this.yaw), 0, Math.cos(this.yaw));
      this.pos.addScaledVector(fwd, speed * dt);
      this.field.resolveCollisions(this.pos, this.radius * 0.8, false, this);
    }
    this.anim.speed = speed;
    this.obj.rotation.y = this.yaw;
    this.pos.y = this.field.groundAt(this.pos.x, this.pos.z) - this.sink;
    this.anim.update(dt);
    if (this.steam && this.alive && this.obj.visible) {
      this.steam.update(dt, this.field.fx.smoke, speed > 2 || this.state === 'windup' || this.state === 'lunge');
    }

    // hit flash
    if (this.flashT > 0) {
      this.flashT -= dt;
      const k = Math.max(0, this.flashT / 0.12);
      this.model.traverse((o) => {
        const m = (o as THREE.Mesh).material as THREE.MeshStandardMaterial | undefined;
        if (m && 'emissive' in m && !m.name.startsWith('glow_')) {
          m.emissive.setRGB(k, k * 0.9, k * 0.8);
        }
      });
    }
  }

  topPos() {
    return this.pos.clone().add(new THREE.Vector3(0, this.sp.height * this.sp.scale + 0.3, 0));
  }

  /** Field hit from the player. Returns true if the hit connected. */
  takeHit(dmg: number, brk: number, heavy: boolean) {
    if (!this.alive) return false;
    this.lastHit = this.time;
    this.flashT = 0.12;
    if (this.killable) this.hp = Math.max(0, this.hp - dmg);
    if (this.killable && this.hp <= 0) {
      this.set('dead');
      this.anim.stunned = false;
      this.anim.play('ko');
      this.field.onEnemyKilled(this);
      return true;
    }
    if (this.state !== 'stunned') {
      this.brk = Math.min(this.brkMax, this.brk + brk);
      if (this.brk >= this.brkMax) {
        this.set('stunned');
        this.anim.play('hit');
        Sfx.play('break');
        Input.rumble(0.8, 0.5, 200);
        this.field.onEnemyStunned(this);
        return true;
      }
    }
    const poise = this.sp.field.poise;
    const interrupt = poise === 0 || (poise === 1 && heavy);
    if (this.state !== 'stunned' && interrupt && this.state !== 'lunge') {
      this.set('flinch');
      this.anim.play('hit');
      // knockback
      const away = new THREE.Vector3().subVectors(this.pos, this.field.player.pos).setY(0).normalize();
      this.pos.addScaledVector(away, heavy ? 1.2 : 0.45);
      this.field.resolveCollisions(this.pos, this.radius * 0.8, false, this);
    } else if (this.state === 'idle' || this.state === 'wander' || this.state === 'return') {
      this.set('chase');
    }
    return true;
  }

  /** After returning from a battle the player fled from. */
  pacify() {
    this.anim.stunned = false;
    this.brk = 0;
    this.set('cooldown');
  }

  reset() {
    this.removed = false;
    this.obj.visible = true;
    this.sink = 0;
    this.hp = this.hpMax;
    this.brk = 0;
    this.anim.stunned = false;
    this.anim.ko = false;
    this.anim.action = null;
    this.pos.copy(this.home);
    this.set('idle');
  }
}
