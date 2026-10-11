import * as THREE from 'three';
import { Animator } from '../anim/rig';
import { getModel } from '../core/assets';
import { Input } from '../core/input';
import { Sfx } from '../core/audio';
import { clamp, dampAngle, wrapAngle } from '../core/utils';
import { SteamVent } from '../fx/effects';
import type { FieldMode } from './field';
import type { FieldEnemy } from './fieldEnemy';

type PState = 'move' | 'light' | 'heavy' | 'dodge' | 'locked';

interface SwingDef { clip: string; dur: number; hitAt: number; range: number; arc: number; dmg: number; brk: number; heavy: boolean; lunge: number; chainFrom: number }

const SWINGS: SwingDef[] = [
  { clip: 'slash1', dur: 0.42, hitAt: 0.17, range: 2.5, arc: 1.3, dmg: 0.4, brk: 9, heavy: false, lunge: 3.2, chainFrom: 0.14 },
  { clip: 'slash2', dur: 0.42, hitAt: 0.17, range: 2.5, arc: 1.3, dmg: 0.4, brk: 9, heavy: false, lunge: 3.2, chainFrom: 0.14 },
  { clip: 'slash3', dur: 0.58, hitAt: 0.27, range: 2.8, arc: 1.0, dmg: 0.6, brk: 15, heavy: false, lunge: 4.2, chainFrom: 99 },
];
const HEAVY: SwingDef = { clip: 'heavy', dur: 0.95, hitAt: 0.46, range: 3.2, arc: 1.6, dmg: 0.8, brk: 30, heavy: true, lunge: 5, chainFrom: 99 };

export class Player {
  obj = new THREE.Group();
  model: THREE.Object3D;
  anim: Animator;
  yaw = Math.PI;
  state: PState = 'move';
  stateT = 0;
  combo = 0;
  buffered: 'light' | 'heavy' | null = null;
  swing: SwingDef | null = null;
  hitDone = false;
  invuln = 0;
  dodgeDir = new THREE.Vector3();
  speed = 0;
  private steam: SteamVent | null = null;
  private stepT = 0;
  private aimYaw: number | null = null;
  /** L3 sprint toggle — stays on until the stick is released */
  private padSprint = false;
  /** This frame's movement input, camera-relative (−z = forward): read by the camera's auto-follow. */
  moveInput = { x: 0, z: 0 };

  constructor(private field: FieldMode) {
    this.model = getModel('kai');
    this.obj.add(this.model);
    this.anim = new Animator(this.model, 'humanoid');
    const sp = this.anim.rig.get('steam_point');
    if (sp) this.steam = new SteamVent(sp, 'pack');
  }

  get pos() {
    return this.obj.position;
  }
  get forward() {
    return new THREE.Vector3(Math.sin(this.yaw), 0, Math.cos(this.yaw));
  }

  update(dt: number, camYaw: number, controls: boolean) {
    this.stateT += dt;
    this.invuln = Math.max(0, this.invuln - dt);

    // movement input relative to camera (keys are all-or-nothing, the left stick is analog)
    let ix = 0, iz = 0;
    if (controls) {
      // arrow keys turn the camera instead (FieldMode)
      if (Input.isDown('KeyW')) iz -= 1;
      if (Input.isDown('KeyS')) iz += 1;
      if (Input.isDown('KeyA')) ix -= 1;
      if (Input.isDown('KeyD')) ix += 1;
      if (!ix && !iz) { ix = Input.stick.lx; iz = Input.stick.ly; }
      if (Input.pressed('PadL3')) this.padSprint = !this.padSprint;
    }
    this.moveInput.x = ix;
    this.moveInput.z = iz;
    const move = new THREE.Vector3(ix, 0, iz);
    const amount = Math.min(1, move.length());
    if (amount === 0) this.padSprint = false;
    if (amount > 0) move.normalize().applyAxisAngle(new THREE.Vector3(0, 1, 0), camYaw);

    const wantLight = controls && Input.pressed('Mouse0', 'KeyJ', 'PadX');
    const wantHeavy = controls && Input.pressed('Mouse2', 'KeyK', 'PadY');
    const wantDodge = controls && Input.pressed('Space', 'PadB');

    switch (this.state) {
      case 'move': {
        const sprint = this.padSprint || Input.isDown('ShiftLeft', 'ShiftRight', 'PadLB');
        const target = amount > 0 ? (sprint ? 7.6 : 4.8) * (0.3 + 0.7 * amount) : 0;
        this.speed += (target - this.speed) * Math.min(1, dt * 12);
        if (move.lengthSq() > 0) this.yaw = dampAngle(this.yaw, Math.atan2(move.x, move.z), 14, dt);
        const f = this.forward;
        this.moveBy(f.x * this.speed * dt, f.z * this.speed * dt);
        this.anim.speed = this.speed;
        if (this.speed > 1) {
          this.stepT += dt * this.speed;
          if (this.stepT > 1.6) { this.stepT = 0; Sfx.play('step'); }
        }
        if (wantDodge) this.startDodge(move);
        else if (wantLight) this.startSwing(SWINGS[0], 'light', 0);
        else if (wantHeavy) this.startSwing(HEAVY, 'heavy', 0);
        break;
      }
      case 'light':
      case 'heavy': {
        const sw = this.swing!;
        this.speed = 0;
        this.anim.speed = 0;
        if (this.aimYaw !== null) this.yaw = dampAngle(this.yaw, this.aimYaw, 25, dt);
        // forward lunge during the wind-up → strike
        if (this.stateT < sw.hitAt + 0.05) {
          const k = this.stateT / (sw.hitAt + 0.05);
          const f = this.forward;
          const sp = sw.lunge * (1 - k);
          this.moveBy(f.x * sp * dt, f.z * sp * dt, true);
        }
        if (!this.hitDone && this.stateT >= sw.hitAt) {
          this.hitDone = true;
          this.field.playerStrike(sw.range, sw.arc, sw.dmg, sw.brk, sw.heavy, this.combo);
        }
        if (wantLight) this.buffered = 'light';
        if (wantHeavy) this.buffered = 'heavy';
        if (wantDodge && this.stateT > sw.hitAt) { this.startDodge(move); break; }
        if (this.stateT >= sw.chainFrom && this.buffered === 'light' && this.state === 'light' && this.combo < SWINGS.length - 1 && this.stateT > sw.hitAt + 0.05) {
          this.startSwing(SWINGS[this.combo + 1], 'light', this.combo + 1);
          break;
        }
        if (this.stateT >= sw.dur) {
          if (this.buffered === 'heavy') this.startSwing(HEAVY, 'heavy', 0);
          else if (this.buffered === 'light' && this.state === 'heavy') this.startSwing(SWINGS[0], 'light', 0);
          else { this.state = 'move'; this.stateT = 0; }
        }
        break;
      }
      case 'dodge': {
        const k = this.stateT / 0.45;
        const sp = 9.5 * (1 - k * k);
        this.moveBy(this.dodgeDir.x * sp * dt, this.dodgeDir.z * sp * dt);
        this.anim.speed = 0;
        if (this.stateT >= 0.45) { this.state = 'move'; this.stateT = 0; }
        if (this.stateT > 0.3 && wantLight) { this.startSwing(SWINGS[0], 'light', 0); }
        break;
      }
      case 'locked':
        this.speed = 0;
        this.anim.speed = 0;
        break;
    }

    this.obj.rotation.y = this.yaw;
    this.pos.y = this.field.groundAt(this.pos.x, this.pos.z);
    this.anim.update(dt);

    // backpack steam
    this.steam?.update(dt, this.field.fx.smoke, this.speed > 5);
  }

  private moveBy(dx: number, dz: number, attacking = false) {
    const p = this.pos;
    p.x += dx;
    p.z += dz;
    this.field.resolveCollisions(p, 0.45, attacking);
  }

  private startSwing(sw: SwingDef, kind: 'light' | 'heavy', combo: number) {
    this.state = kind;
    this.stateT = 0;
    this.combo = combo;
    this.swing = sw;
    this.hitDone = false;
    this.buffered = null;
    this.anim.play(sw.clip, 1);
    Sfx.play(sw.heavy ? 'swing_heavy' : 'swing');
    // soft auto-aim toward nearest enemy in front
    const t = this.field.nearestEnemy(this.pos, 6, this.yaw, 1.9);
    this.aimYaw = t ? Math.atan2(t.pos.x - this.pos.x, t.pos.z - this.pos.z) : null;
    // input direction overrides when pressing a direction and no target
    if (!t) this.aimYaw = null;
  }

  private startDodge(move: THREE.Vector3) {
    this.state = 'dodge';
    this.stateT = 0;
    this.invuln = 0.4;
    this.dodgeDir.copy(move.lengthSq() > 0 ? move : this.forward.multiplyScalar(-1));
    if (move.lengthSq() > 0) this.yaw = Math.atan2(move.x, move.z);
    this.anim.play(move.lengthSq() > 0 ? 'dodge' : 'sidestep', 1);
    Sfx.play('dodge');
  }

  lock(on: boolean) {
    this.state = on ? 'locked' : 'move';
    this.stateT = 0;
  }

  /** True when this enemy is behind the player (for ambush). */
  isBehind(e: FieldEnemy) {
    const to = new THREE.Vector3().subVectors(e.pos, this.pos).setY(0).normalize();
    const a = Math.abs(wrapAngle(Math.atan2(to.x, to.z) - this.yaw));
    return a > clamp(Math.PI * 0.62, 0, Math.PI);
  }
}
