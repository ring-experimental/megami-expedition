import * as THREE from 'three';
import { DEG, clamp, smoothstep } from '../core/utils';

/**
 * Procedural animation for the models produced in Blender — rigid named parts or skinned
 * armatures (bones keep the same names, see tools/blender/RIG_SPEC.md).
 * Every frame: begin() → add offsets (locomotion + action clip) → apply().
 *
 * Offsets are euler angles in MODEL-aligned axes (three.js: +X model's left, +Y up, +Z forward),
 * applied at the joint. Bones carry non-identity rest rotations, so each offset O is conjugated
 * into the joint's parent frame: local = C⁻¹·O·C·rest, where C is the parent's rest orientation
 * relative to the model. For rigid parts C = identity, which reduces to the original behaviour.
 */
interface PartState {
  obj: THREE.Object3D;
  restQ: THREE.Quaternion;
  restP: THREE.Vector3;
  restS: THREE.Vector3;
  frame: THREE.Quaternion;
  frameInv: THREE.Quaternion;
  rot: THREE.Vector3;
  pos: THREE.Vector3;
  scl: THREE.Vector3;
}

const _e = new THREE.Euler();
const _q = new THREE.Quaternion();
const _v = new THREE.Vector3();
const _wp = new THREE.Vector3();
const _wv = new THREE.Vector3();
const _fw = new THREE.Vector3();
const _wq = new THREE.Quaternion();

export class Rig {
  parts = new Map<string, PartState>();
  constructor(public model: THREE.Object3D) {
    model.updateMatrixWorld(true);
    const modelInv = model.getWorldQuaternion(new THREE.Quaternion()).invert();
    model.traverse((o) => {
      // the model root itself is driven by the Animator ($p / $r offsets), never reset here
      if (o === model || !o.name || this.parts.has(o.name)) return;
      const frame = o.parent ? modelInv.clone().multiply(o.parent.getWorldQuaternion(new THREE.Quaternion())) : new THREE.Quaternion();
      this.parts.set(o.name, {
        obj: o,
        restQ: o.quaternion.clone(),
        restP: o.position.clone(),
        restS: o.scale.clone(),
        frame,
        frameInv: frame.clone().invert(),
        rot: new THREE.Vector3(),
        pos: new THREE.Vector3(),
        scl: new THREE.Vector3(1, 1, 1),
      });
    });
  }
  has(name: string) {
    return this.parts.has(name);
  }
  get(name: string) {
    return this.parts.get(name)?.obj;
  }
  names() {
    return [...this.parts.keys()];
  }
  /** Accumulated offset (radians, model axes) of a part this frame, if it exists. */
  rotOf(name: string) {
    return this.parts.get(name)?.rot;
  }
  begin() {
    for (const p of this.parts.values()) {
      p.rot.set(0, 0, 0);
      p.pos.set(0, 0, 0);
      p.scl.set(1, 1, 1);
    }
  }
  rot(name: string, x: number, y = 0, z = 0) {
    const p = this.parts.get(name);
    if (p) { p.rot.x += x; p.rot.y += y; p.rot.z += z; }
  }
  pos(name: string, x: number, y: number, z: number) {
    const p = this.parts.get(name);
    if (p) { p.pos.x += x; p.pos.y += y; p.pos.z += z; }
  }
  scale(name: string, x: number, y: number, z: number) {
    const p = this.parts.get(name);
    if (p) { p.scl.x *= x; p.scl.y *= y; p.scl.z *= z; }
  }
  apply() {
    for (const p of this.parts.values()) {
      if (p.rot.x || p.rot.y || p.rot.z) {
        _e.set(p.rot.x, p.rot.y, p.rot.z, 'YXZ');
        _q.setFromEuler(_e);
        // local = C⁻¹ · O · C · rest
        p.obj.quaternion.copy(p.frameInv).multiply(_q).multiply(p.frame).multiply(p.restQ);
      } else {
        p.obj.quaternion.copy(p.restQ);
      }
      p.obj.position.copy(p.restP).add(_v.copy(p.pos).applyQuaternion(p.frameInv));
      p.obj.scale.copy(p.restS).multiply(p.scl);
    }
  }
}

// ---------------------------------------------------------------------------
// Clips: keyframed poses (degrees). "$" = model offset (pos in meters, rot deg)
// ---------------------------------------------------------------------------
export type Pose = Record<string, [number, number, number]>;
export interface Key { t: number; pose: Pose; }
export interface Clip { dur: number; keys: Key[]; hold?: boolean; }

function samplePose(clip: Clip, t: number, out: Map<string, [number, number, number]>) {
  out.clear();
  const keys = clip.keys;
  let a = keys[0], b = keys[keys.length - 1];
  for (let i = 0; i < keys.length - 1; i++) {
    if (t >= keys[i].t && t <= keys[i + 1].t) { a = keys[i]; b = keys[i + 1]; break; }
  }
  if (t >= keys[keys.length - 1].t) a = b = keys[keys.length - 1];
  const span = b.t - a.t;
  const f = span > 0 ? smoothstep(clamp((t - a.t) / span, 0, 1)) : 1;
  const names = new Set([...Object.keys(a.pose), ...Object.keys(b.pose)]);
  for (const n of names) {
    const pa = a.pose[n] ?? [0, 0, 0];
    const pb = b.pose[n] ?? [0, 0, 0];
    out.set(n, [pa[0] + (pb[0] - pa[0]) * f, pa[1] + (pb[1] - pa[1]) * f, pa[2] + (pb[2] - pa[2]) * f]);
  }
}

// Humanoid conventions (three.js space, model faces +Z):
//  rx < 0 raises a limb forward. arm_L outward = +rz, arm_R outward = −rz. torso ry > 0 turns to its left.
//  Kai's sword points forward when arm hangs; weapon rx +90 with arm rx −90 makes the blade extend the arm.
const H: Record<string, Clip> = {
  slash1: { dur: 0.42, keys: [
    { t: 0, pose: {} },
    { t: 0.1, pose: { torso: [5, -55, 0], arm_R: [-80, 0, -10], forearm_R: [-35, 0, 0], weapon: [90, 0, 0], arm_L: [-20, 0, 20], forearm_L: [-30, 0, 0], hips: [0, -10, 0], shin_R: [20, 0, 0] } },
    { t: 0.2, pose: { torso: [10, 60, 0], arm_R: [-90, 0, 0], weapon: [90, 0, 0], arm_L: [-10, 0, 30], hips: [0, 15, 0], $p: [0, 0, 0.25] } },
    { t: 0.42, pose: { torso: [5, 20, 0], arm_R: [-40, 0, -10], weapon: [40, 0, 0] } },
  ] },
  slash2: { dur: 0.42, keys: [
    { t: 0, pose: { torso: [5, 40, 0], arm_R: [-60, 0, 0], weapon: [60, 0, 0] } },
    { t: 0.1, pose: { torso: [5, 65, 0], arm_R: [-95, 0, 0], forearm_R: [-30, 0, 0], weapon: [100, 0, 0], hips: [0, 10, 0], shin_L: [20, 0, 0] } },
    { t: 0.2, pose: { torso: [10, -60, 0], arm_R: [-90, 0, 0], weapon: [90, 0, 0], hips: [0, -15, 0], $p: [0, 0, 0.25] } },
    { t: 0.42, pose: { torso: [0, -15, 0], arm_R: [-35, 0, 0], weapon: [35, 0, 0] } },
  ] },
  slash3: { dur: 0.55, keys: [
    { t: 0, pose: { torso: [0, -15, 0] } },
    { t: 0.16, pose: { torso: [-18, 0, 0], arm_R: [-170, 0, 10], forearm_R: [-45, 0, 0], weapon: [70, 0, 0], arm_L: [-150, 0, -10], forearm_L: [-45, 0, 0], $p: [0, 0.15, 0] } },
    { t: 0.27, pose: { torso: [30, 0, 0], arm_R: [-55, 0, 0], weapon: [100, 0, 0], arm_L: [-50, 0, -10], leg_L: [-25, 0, 0], shin_L: [30, 0, 0], leg_R: [20, 0, 0], shin_R: [35, 0, 0], $p: [0, -0.12, 0.35] } },
    { t: 0.55, pose: { torso: [10, 0, 0], arm_R: [-30, 0, 0], weapon: [40, 0, 0] } },
  ] },
  heavy: { dur: 0.95, keys: [
    { t: 0, pose: {} },
    { t: 0.35, pose: { torso: [-10, -80, 0], hips: [0, -20, 0], arm_R: [-100, 0, -30], forearm_R: [-40, 0, 0], weapon: [80, 0, 0], arm_L: [-60, 0, 30], forearm_L: [-40, 0, 0], leg_L: [-20, 0, 0], shin_L: [30, 0, 0], leg_R: [25, 0, 0], shin_R: [30, 0, 0], $p: [0, -0.15, -0.1] } },
    { t: 0.5, pose: { torso: [15, 90, 0], hips: [0, 30, 0], arm_R: [-90, 0, 0], weapon: [90, 0, 0], arm_L: [-30, 0, 40], leg_L: [-30, 0, 0], shin_L: [35, 0, 0], leg_R: [20, 0, 0], shin_R: [20, 0, 0], $p: [0, -0.1, 0.6] } },
    { t: 0.95, pose: { torso: [5, 20, 0], arm_R: [-30, 0, 0], weapon: [30, 0, 0] } },
  ] },
  thrust: { dur: 0.6, keys: [
    { t: 0, pose: {} },
    { t: 0.22, pose: { torso: [-5, -35, 0], arm_R: [-60, 0, -20], forearm_R: [-70, 0, 0], weapon: [60, 0, 0], leg_R: [25, 0, 0], shin_R: [30, 0, 0], leg_L: [-15, 0, 0], shin_L: [20, 0, 0], $p: [0, -0.1, -0.15] } },
    { t: 0.32, pose: { torso: [15, 15, 0], arm_R: [-92, 0, 0], weapon: [92, 0, 0], arm_L: [20, 0, 25], forearm_L: [-40, 0, 0], leg_L: [-40, 0, 0], shin_L: [40, 0, 0], leg_R: [30, 0, 0], shin_R: [15, 0, 0], $p: [0, -0.15, 0.7] } },
    { t: 0.6, pose: { arm_R: [-30, 0, 0], weapon: [30, 0, 0] } },
  ] },
  cast: { dur: 0.8, keys: [
    { t: 0, pose: {} },
    { t: 0.3, pose: { torso: [-10, 0, 0], arm_R: [-150, 0, 10], forearm_R: [-25, 0, 0], weapon: [60, 0, 0], arm_L: [-150, 0, -10], forearm_L: [-30, 0, 0], head: [-15, 0, 0] } },
    { t: 0.45, pose: { torso: [12, 0, 0], arm_R: [-95, 0, 0], weapon: [55, 0, 0], arm_L: [-85, 0, 0], $p: [0, 0, 0.15] } },
    { t: 0.8, pose: {} },
  ] },
  hit: { dur: 0.35, keys: [
    { t: 0, pose: {} },
    { t: 0.06, pose: { torso: [-22, 0, 8], head: [-15, 0, 0], arm_L: [-30, 0, 30], forearm_L: [-30, 0, 0], arm_R: [-30, 0, -30], forearm_R: [-30, 0, 0], shin_L: [15, 0, 0], shin_R: [15, 0, 0], $p: [0, 0, -0.25] } },
    { t: 0.35, pose: {} },
  ] },
  parry: { dur: 0.3, keys: [
    { t: 0, pose: {} },
    { t: 0.05, pose: { torso: [5, -30, 0], arm_R: [-100, 0, 30], forearm_R: [-45, 0, 0], weapon: [100, 0, 50], arm_L: [-40, 0, 20], forearm_L: [-50, 0, 0], shin_L: [20, 0, 0], shin_R: [25, 0, 0], $p: [0, -0.05, -0.1] } },
    { t: 0.3, pose: {} },
  ] },
  dodge: { dur: 0.45, keys: [
    { t: 0, pose: {} },
    { t: 0.08, pose: { torso: [30, 0, 0], leg_L: [-70, 0, 0], shin_L: [100, 0, 0], leg_R: [-70, 0, 0], shin_R: [100, 0, 0], arm_L: [-60, 0, 0], forearm_L: [-60, 0, 0], arm_R: [-60, 0, 0], forearm_R: [-50, 0, 0], $p: [0, -0.4, 0] } },
    { t: 0.35, pose: { torso: [30, 0, 0], leg_L: [-70, 0, 0], shin_L: [100, 0, 0], leg_R: [-70, 0, 0], shin_R: [100, 0, 0], arm_L: [-60, 0, 0], forearm_L: [-60, 0, 0], arm_R: [-60, 0, 0], forearm_R: [-50, 0, 0], $p: [0, -0.4, 0] } },
    { t: 0.45, pose: {} },
  ] },
  sidestep: { dur: 0.4, keys: [
    { t: 0, pose: {} },
    { t: 0.08, pose: { torso: [0, 0, 20], leg_L: [0, 0, 25], leg_R: [0, 0, 10], $p: [1.1, -0.1, 0], $r: [0, 0, -12] } },
    { t: 0.28, pose: { torso: [0, 0, 20], leg_L: [0, 0, 25], leg_R: [0, 0, 10], $p: [1.1, -0.1, 0], $r: [0, 0, -12] } },
    { t: 0.4, pose: {} },
  ] },
  victory: { dur: 1.2, hold: true, keys: [
    { t: 0, pose: {} },
    { t: 0.35, pose: { arm_R: [-170, 0, -10], weapon: [80, 0, 0], arm_L: [10, 0, 25], torso: [-8, 15, 0], head: [-10, 0, 0], $p: [0, 0.2, 0] } },
    { t: 1.2, pose: { arm_R: [-160, 0, -15], weapon: [80, 0, 0], arm_L: [5, 0, 20], torso: [-6, 15, 0], head: [-8, 0, 0] } },
  ] },
  ko: { dur: 0.8, hold: true, keys: [
    { t: 0, pose: {} },
    { t: 0.25, pose: { torso: [30, 0, 0], head: [20, 0, 0], leg_L: [-60, 0, 0], shin_L: [70, 0, 0], leg_R: [-50, 0, 0], shin_R: [60, 0, 0], arm_L: [-30, 0, 30], arm_R: [-30, 0, -30], $p: [0, -0.5, 0] } },
    { t: 0.8, pose: { torso: [10, 0, 0], head: [10, 0, 0], leg_L: [-10, 0, 0], leg_R: [-5, 0, 0], arm_L: [-170, 0, 20], arm_R: [-170, 0, -20], $p: [0, 0.18, -0.6], $r: [-90, 0, 0] } },
  ] },
  talk: { dur: 1.0, keys: [
    { t: 0, pose: {} },
    { t: 0.25, pose: { arm_L: [-60, 0, 35], forearm_L: [-50, 0, 0], torso: [0, 10, 0], head: [-5, 0, 0] } },
    { t: 0.6, pose: { arm_L: [-50, 0, 45], forearm_L: [-35, 0, 0], torso: [0, 5, 0] } },
    { t: 1.0, pose: {} },
  ] },
  item: { dur: 0.7, keys: [
    { t: 0, pose: {} },
    { t: 0.25, pose: { arm_L: [-90, 0, 0], forearm_L: [-60, 0, 0], head: [-15, 0, 0] } },
    { t: 0.7, pose: {} },
  ] },
  charge: { dur: 0.6, hold: true, keys: [
    { t: 0, pose: {} },
    { t: 0.6, pose: { torso: [-15, -25, 0], arm_R: [-110, 0, -40], forearm_R: [-40, 0, 0], weapon: [80, 0, 0], arm_L: [-50, 0, 30], forearm_L: [-40, 0, 0], leg_L: [-20, 0, 0], shin_L: [30, 0, 0], leg_R: [20, 0, 0], shin_R: [25, 0, 0], $p: [0, -0.15, 0] } },
  ] },
  stagger: { dur: 0.5, keys: [
    { t: 0, pose: {} },
    { t: 0.1, pose: { torso: [-25, 10, 10], head: [-20, 0, 0], arm_L: [-40, 0, 40], arm_R: [-40, 0, -40], $p: [0, 0, -0.4] } },
    { t: 0.5, pose: {} },
  ] },
};

// Monster clips (parts are optional; missing ones are ignored)
const M: Record<string, Clip> = {
  attack: { dur: 0.55, keys: [
    { t: 0, pose: {} },
    { t: 0.25, pose: { body: [-15, 0, 0], head: [-20, 0, 0], lantern: [-15, 0, 0], torso: [-20, 0, 0], arm_R: [-150, 0, 0], arm_L: [-150, 0, 0], $p: [0, 0.05, -0.25] } },
    { t: 0.33, pose: { body: [15, 0, 0], head: [20, 0, 0], lantern: [20, 0, 0], torso: [25, 0, 0], arm_R: [-60, 0, 0], arm_L: [-60, 0, 0], horn: [-20, 0, 0], $p: [0, -0.05, 0.6] } },
    { t: 0.55, pose: {} },
  ] },
  windup: { dur: 0.5, hold: true, keys: [
    { t: 0, pose: {} },
    { t: 0.5, pose: { body: [-12, 0, 0], head: [-18, 0, 0], lantern: [-12, 0, 0], torso: [-15, 0, 0], arm_R: [-160, 0, 0], arm_L: [-160, 0, 0], shell_L: [12, -15, 22], shell_R: [12, 15, -22], $p: [0, -0.05, -0.3] } },
  ] },
  strike: { dur: 0.3, keys: [
    { t: 0, pose: { body: [-12, 0, 0], head: [-18, 0, 0], lantern: [-12, 0, 0], torso: [-15, 0, 0], arm_R: [-160, 0, 0], arm_L: [-160, 0, 0], $p: [0, -0.05, -0.3] } },
    { t: 0.08, pose: { body: [18, 0, 0], head: [22, 0, 0], lantern: [20, 0, 0], torso: [25, 0, 0], arm_R: [-50, 0, 0], arm_L: [-50, 0, 0], horn: [-25, 0, 0], $p: [0, -0.05, 0.5] } },
    { t: 0.3, pose: {} },
  ] },
  hit: { dur: 0.35, keys: [
    { t: 0, pose: {} },
    { t: 0.06, pose: { body: [-18, 0, 8], head: [-18, 0, 0], lantern: [-20, 0, 10], torso: [-18, 0, 8], $p: [0, 0, -0.3] } },
    { t: 0.35, pose: {} },
  ] },
  cast: { dur: 0.7, keys: [
    { t: 0, pose: {} },
    { t: 0.3, pose: { body: [-20, 0, 0], head: [-25, 0, 0], lantern: [0, 0, 0], torso: [-15, 0, 0], arm_R: [-170, 0, 0], arm_L: [-170, 0, 0], $p: [0, 0.3, 0] } },
    { t: 0.42, pose: { body: [12, 0, 0], head: [12, 0, 0], torso: [15, 0, 0], arm_R: [-90, 0, 0], arm_L: [-90, 0, 0], $p: [0, 0.1, 0.2] } },
    { t: 0.7, pose: {} },
  ] },
  ko: { dur: 0.8, hold: true, keys: [
    { t: 0, pose: {} },
    { t: 0.8, pose: { head: [30, 0, 0], torso: [40, 0, 0], arm_L: [-40, 0, 30], arm_R: [-40, 0, -30], $p: [0, -0.1, 0], $r: [0, 0, 85] } },
  ] },
  victory: { dur: 0.8, hold: true, keys: [{ t: 0, pose: {} }, { t: 0.4, pose: { $p: [0, 0.4, 0] } }, { t: 0.8, pose: {} }] },
  talk: { dur: 0.8, keys: [{ t: 0, pose: {} }, { t: 0.3, pose: { head: [-10, 15, 0], body: [0, 10, 0] } }, { t: 0.8, pose: {} }] },
  item: { dur: 0.5, keys: [{ t: 0, pose: {} }, { t: 0.2, pose: { $p: [0, 0.3, 0] } }, { t: 0.5, pose: {} }] },
};
M.dodge = H.dodge;
M.sidestep = H.sidestep;
M.parry = { dur: 0.3, keys: [{ t: 0, pose: {} }, { t: 0.05, pose: { body: [-10, 20, 0], $p: [0, 0, -0.15] } }, { t: 0.3, pose: {} }] };
M.stagger = M.hit;
M.slash1 = M.slash2 = M.slash3 = M.heavy = M.thrust = M.charge = M.attack;

export type Archetype = 'humanoid' | 'rat' | 'slime' | 'beetle' | 'wisp' | 'golem';

// ---------------------------------------------------------------------------
// Animator
// ---------------------------------------------------------------------------
interface Action { clip: Clip; t: number; speed: number; resolve?: () => void; weight: number; fadeOut: boolean; }

export class Animator {
  rig: Rig;
  time = Math.random() * 10;
  /** Locomotion speed (m/s), set by the owner every frame. */
  speed = 0;
  phase = 0;
  action: Action | null = null;
  stunned = false;
  ko = false;
  /** Pose layered on top while "held" (e.g. battle ready stance). */
  stance: 'idle' | 'ready' = 'idle';
  private sampled = new Map<string, [number, number, number]>();
  private baseRot = new THREE.Euler();
  private basePos = new THREE.Vector3();
  private clips: Record<string, Clip>;
  /** Secondary-motion chains (cloth, hair, tails, ears) found by bone-name prefix. */
  private chains: { name: string; prefix: string; side: string; idx: number; phase: number }[] = [];
  /** Smoothed velocity of the owner in model-local axes (x left, y up, z forward) and yaw rate. */
  private vel = new THREE.Vector3();
  private yawRate = 0;
  private prevPos = new THREE.Vector3();
  private prevYaw = 0;
  private tracking = false;

  constructor(public model: THREE.Object3D, public archetype: Archetype) {
    this.rig = new Rig(model);
    this.basePos.copy(model.position);
    this.baseRot.copy(model.rotation);
    this.clips = archetype === 'humanoid' || archetype === 'golem' ? H : M;
    this.shieldArm = this.rig.has('shield');
    const re = /^(coat|skirt|scarf|tabard|cape|hair|hat|tail|ear|antenna)(?:_([A-Z]{1,2}))?(?:_(\d+))?$/;
    for (const name of this.rig.names()) {
      const m = re.exec(name);
      if (m) this.chains.push({ name, prefix: m[1], side: m[2] ?? '', idx: Number(m[3] ?? 1), phase: Math.random() * 6 });
    }
  }

  hasClip(name: string) {
    return !!this.clips[name];
  }

  play(name: string, speed = 1): Promise<void> {
    const clip = this.clips[name] ?? M[name];
    if (!clip) return Promise.resolve();
    this.action?.resolve?.();
    return new Promise((resolve) => {
      this.action = { clip, t: 0, speed, resolve, weight: 1, fadeOut: false };
    });
  }

  /** Stop a held clip, blending back to locomotion. */
  release() {
    if (this.action) this.action.fadeOut = true;
  }

  update(dt: number) {
    this.time += dt;
    const r = this.rig;
    r.begin();
    this.trackMotion(dt);
    this.locomotion(dt);

    let mp = [0, 0, 0], mr = [0, 0, 0];
    const a = this.action;
    if (a) {
      a.t += dt * a.speed;
      if (a.fadeOut) a.weight -= dt * 6;
      samplePose(a.clip, Math.min(a.t, a.clip.dur), this.sampled);
      const w = clamp(a.weight, 0, 1);
      for (const [name, v] of this.sampled) {
        if (name === '$p') mp = v.map((x) => x * w);
        else if (name === '$r') mr = v.map((x) => x * w);
        else if (name === 'arm_L' && this.shieldArm) r.rot(name, Math.max(v[0], -75) * DEG * w, v[1] * DEG * w, v[2] * DEG * w);
        else r.rot(name, v[0] * DEG * w, v[1] * DEG * w, v[2] * DEG * w);
      }
      if (a.t >= a.clip.dur) {
        if (a.resolve) { a.resolve(); a.resolve = undefined; }
        if (!a.clip.hold) this.action = null;
      }
      if (a.weight <= 0) this.action = null;
    }
    if (this.archetype === 'beetle') this.slideShells();
    this.secondary();
    this.model.position.set(this.basePos.x + mp[0], this.basePos.y + mp[1] + this.bob, this.basePos.z + mp[2]);
    this.model.rotation.set(this.baseRot.x + mr[0] * DEG, this.baseRot.y + mr[1] * DEG, this.baseRot.z + mr[2] * DEG);
    r.apply();
  }

  private bob = 0;
  /** Shield on the left forearm (knight): monster clips raise both arms overhead, which would park
   *  the shield in front of the visor — keep that arm in a chest-high guard instead. */
  private shieldArm = false;

  /** Beetle elytra hinge on the centre line, so opening them (stunned / windup) swings their inner
   *  front corners forward over the pronotum — slide them back and up a little as they open. */
  private slideShells() {
    for (const n of ['shell_L', 'shell_R']) {
      const o = this.rig.rotOf(n);
      if (!o) continue;
      const k = clamp(Math.abs(o.z) / 0.42, 0, 1);
      if (k > 0) this.rig.pos(n, 0, 0.01 * k, -0.035 * k);
    }
  }

  private trackMotion(dt: number) {
    const holder = this.model.parent;
    if (!holder || dt <= 0) return;
    holder.getWorldPosition(_wp);
    holder.getWorldQuaternion(_wq);
    _fw.set(0, 0, 1).applyQuaternion(_wq);
    const yaw = Math.atan2(_fw.x, _fw.z);
    if (this.tracking) {
      _wv.subVectors(_wp, this.prevPos).divideScalar(dt).applyQuaternion(_wq.invert());
      if (_wv.lengthSq() > 900) _wv.set(0, 0, 0); // teleports
      this.vel.lerp(_wv, 1 - Math.exp(-6 * dt));
      let dy = yaw - this.prevYaw;
      while (dy > Math.PI) dy -= Math.PI * 2;
      while (dy < -Math.PI) dy += Math.PI * 2;
      this.yawRate += (clamp(dy / dt, -10, 10) - this.yawRate) * (1 - Math.exp(-6 * dt));
    }
    this.prevPos.copy(_wp);
    this.prevYaw = yaw;
    this.tracking = true;
  }

  /**
   * Cloth panels hanging from the hips must swing with the thighs or the knees poke through.
   * Front panels follow the most-forward thigh, back panels the most-backward one, side panels
   * their own thigh (signed). The first segment carries most of the rotation; outer segments add a
   * little extra flare. Returns an X rotation offset (radians, + = free end backward).
   */
  private thighFollow(prefix: string, side: string, idx: number, legL: number, legR: number, thighFwd: number, thighBack: number) {
    const seg = idx === 1 ? 1 : 0.22;
    // a tabard is a stiff panel hinged just in front of the hip joint (no thigh skin weights),
    // so it must rotate almost as far as the thigh to keep the knee behind it
    const kF = prefix === 'tabard' ? 0.9 : 0.62;
    const kB = prefix === 'tabard' ? 0.85 : 0.55;
    if (side === 'F') return -kF * thighFwd * seg;
    if (side === 'B') return kB * thighBack * seg;
    // Kai's coat_L / coat_R are back tails: only pushed back by a back-swinging thigh
    if (prefix === 'coat' && (side === 'L' || side === 'R')) return 0.5 * Math.max(0, side === 'L' ? legL : legR) * seg;
    if (side.endsWith('L')) return 0.48 * legL * seg;
    if (side.endsWith('R')) return 0.48 * legR * seg;
    return 0;
  }

  /** Procedural lag/sway for cloth, hair, scarf, tails, ears driven by the owner's motion. */
  private secondary() {
    if (!this.chains.length) return;
    const r = this.rig;
    const t = this.time;
    const fwd = clamp(this.vel.z, -6, 9);
    const lat = clamp(this.vel.x, -6, 6);
    const up = clamp(this.vel.y, -6, 6);
    const turn = clamp(this.yawRate, -6, 6);
    const run = Math.min(1, Math.abs(fwd) / 3);
    // final thigh angles (locomotion + clip): rot.x < 0 = thigh forward, > 0 = thigh back
    const legL = r.rotOf('leg_L')?.x ?? 0;
    const legR = r.rotOf('leg_R')?.x ?? 0;
    const thighFwd = Math.max(0, -legL, -legR);
    const thighBack = Math.max(0, legL, legR);
    for (const c of this.chains) {
      const k = 0.6 + 0.4 * c.idx; // outer segments swing more
      const wob = Math.sin(t * 2.1 + c.phase) * 0.04 * k;
      switch (c.prefix) {
        case 'scarf': {
          // hangs on the chest: never swing back into the body — flutter forward/outward instead
          const flap = run * (0.5 + 0.5 * Math.sin(t * 6.1 + c.phase));
          const rx = -(0.12 * flap + Math.abs(up) * 0.04 + Math.max(0, fwd) * 0.02) * k + wob * 0.5;
          const rz = (Math.sin(t * 5.3 + c.phase) * 0.14 * run - lat * 0.05 + turn * 0.06) * k;
          r.rot(c.name, clamp(rx, -0.8, 0.05), 0, clamp(rz, -0.6, 0.6));
          break;
        }
        case 'coat': case 'skirt': case 'tabard': case 'cape': case 'hair': {
          const front = c.side === 'F';
          const side = c.side.endsWith('L') ? 1 : c.side.endsWith('R') ? -1 : 0;
          // moving forward -> trailing cloth flares back (+X = free end toward -Z)
          let rx = (front ? 0.2 : 1) * Math.max(0, fwd) * 0.075 * k - Math.max(0, -fwd) * 0.05 * k - up * 0.04 * k + wob;
          if (c.prefix !== 'hair') rx += this.thighFollow(c.prefix, c.side, c.idx, legL, legR, thighFwd, thighBack);
          if (c.prefix === 'hair' || c.prefix === 'cape') rx += Math.sin(t * 5.3 + c.phase) * 0.06 * run * k;
          let rz = -lat * 0.05 * k + turn * 0.06 * k + Math.sin(t * 1.7 + c.phase) * 0.025 * k;
          if (side) rz += side * Math.max(0, fwd) * 0.012 * k;
          r.rot(c.name, clamp(rx, -1.4, 1.3), 0, clamp(rz, -0.6, 0.6));
          break;
        }
        case 'hat':
          r.rot(c.name, -Math.max(0, fwd) * 0.05 - up * 0.03 + wob, 0, Math.sin(t * 1.9 + c.phase) * 0.05 - turn * 0.05);
          break;
        case 'tail': {
          const sway = Math.sin(t * 3.2 - c.idx * 0.7) * 0.2 * k - turn * 0.07 * k - lat * 0.03 * k;
          const lift = 0.07 * k * Math.sin(t * 2 - c.idx * 0.5) - Math.max(0, fwd) * 0.02 * k;
          r.rot(c.name, lift, sway, 0);
          break;
        }
        case 'ear': {
          const twitch = Math.pow(Math.max(0, Math.sin(t * (this.archetype === 'rat' ? 2.3 : 0.8) + c.phase * 3)), 12);
          r.rot(c.name, -Math.max(0, fwd) * 0.05 + Math.sin(t * 1.3 + c.phase) * 0.05, 0, Math.sin(t * 26) * 0.3 * twitch * (c.side === 'L' ? 1 : -1));
          break;
        }
        case 'antenna':
          r.rot(c.name, Math.sin(t * 3 + c.phase) * 0.12 - Math.max(0, fwd) * 0.04, Math.sin(t * 2.2 + c.phase) * 0.1, 0);
          break;
      }
    }
  }

  private locomotion(dt: number) {
    const r = this.rig;
    const t = this.time;
    const s = this.speed;
    const moving = clamp(s / 4, 0, 1.6);
    this.phase += dt * (s > 0.1 ? 1.6 + s * 1.25 : 0);
    const ph = this.phase * Math.PI;
    const sin = Math.sin(ph);
    const breathe = Math.sin(t * 2.2);
    this.bob = 0;
    const ready = this.stance === 'ready' ? 1 : 0;

    switch (this.archetype) {
      case 'humanoid':
      case 'golem': {
        const heavy = this.archetype === 'golem' ? 0.6 : 1;
        r.rot('leg_L', -sin * 0.65 * moving * heavy);
        r.rot('leg_R', sin * 0.65 * moving * heavy);
        r.rot('arm_L', sin * 0.55 * moving * heavy, 0, 0.1 + 0.03 * breathe);
        r.rot('arm_R', -sin * 0.35 * moving * heavy - ready * 0.5, 0, -0.1 - 0.03 * breathe);
        r.rot('weapon', ready * 0.2);
        r.rot('torso', 0.1 * moving + 0.025 * breathe + ready * 0.08, Math.sin(ph) * 0.12 * moving + ready * 0.25);
        r.rot('head', -0.04 * moving - 0.02 * breathe, -ready * 0.2);
        r.rot('hips', 0, -Math.sin(ph) * 0.08 * moving);
        // knees bend while the leg swings forward, elbows stay softly bent
        const cos = Math.cos(ph);
        r.rot('shin_L', moving * heavy * (0.12 + 0.85 * Math.max(0, cos)));
        r.rot('shin_R', moving * heavy * (0.12 + 0.85 * Math.max(0, -cos)));
        r.rot('forearm_L', -0.14 - 0.3 * moving * heavy - 0.03 * breathe);
        r.rot('forearm_R', -0.12 - 0.22 * moving * heavy - ready * 0.3);
        this.bob = Math.abs(Math.cos(ph)) * 0.07 * moving * heavy + (this.stunned ? -0.1 : 0);
        if (ready) {
          r.rot('leg_L', -0.25, 0, 0.08);
          r.rot('leg_R', 0.2, 0, -0.08);
          r.rot('shin_L', 0.3);
          r.rot('shin_R', 0.28);
          this.bob -= 0.06;
        }
        if (this.stunned) {
          r.rot('shin_L', 0.35);
          r.rot('shin_R', 0.3);
          r.rot('torso', 0.35, Math.sin(t * 3) * 0.2);
          r.rot('head', 0.3, Math.sin(t * 4) * 0.3);
          r.rot('arm_L', 0.2, 0, 0.3);
          r.rot('arm_R', 0.2, 0, -0.3);
        }
        r.rot('key', 0, 0, -t * 3); // knight key: Blender Y axis → three −Z
        r.rot('core', 0, 0, 0);
        break;
      }
      case 'rat': {
        const gait = Math.sin(ph * 1.5);
        r.rot('leg_FL', gait * 0.8 * moving);
        r.rot('leg_BR', gait * 0.8 * moving);
        r.rot('leg_FR', -gait * 0.8 * moving);
        r.rot('leg_BL', -gait * 0.8 * moving);
        r.rot('tail_1', 0.15 * Math.sin(t * 3), Math.sin(t * 5) * 0.35); // chain root; tail_2..4 add sway
        // skittish: a constant tiny tremble plus quick glances over either shoulder
        const glance = Math.pow(Math.max(0, Math.sin(t * 0.9)), 10) * Math.sign(Math.sin(t * 0.45));
        r.rot('head', 0.1 * Math.sin(t * 4.3) + Math.sin(t * 31) * 0.015, Math.sin(t * 1.7) * 0.25 + glance * 0.55);
        r.rot('key', 0, t * (4 + s * 2), 0); // Blender Z → three Y
        this.bob = Math.abs(gait) * 0.04 * moving;
        if (this.stunned) r.rot('body', 0, 0, Math.sin(t * 6) * 0.3);
        break;
      }
      case 'slime': {
        const hop = s > 0.1 ? Math.abs(Math.sin(ph * 0.9)) : 0;
        const sq = 1 + 0.06 * breathe - hop * 0.08 + (s > 0.1 ? 0 : 0);
        r.scale('body', 1 / Math.sqrt(sq), sq, 1 / Math.sqrt(sq));
        this.bob = hop * 0.35;
        r.rot('valve', 0, t * 2, 0);
        r.rot('eye_L', 0, 0, Math.sin(t * 3) * 0.3);
        r.rot('eye_R', 0, 0, -Math.sin(t * 3.4) * 0.3);
        if (this.stunned) r.scale('body', 1.15, 0.8, 1.15);
        break;
      }
      case 'beetle': {
        const g = Math.sin(ph * 1.6);
        r.rot('leg_FL', g * 0.5 * moving, g * 0.3 * moving);
        r.rot('leg_BL', g * 0.5 * moving, g * 0.3 * moving);
        r.rot('leg_MR', g * 0.5 * moving, g * 0.3 * moving);
        r.rot('leg_FR', -g * 0.5 * moving, -g * 0.3 * moving);
        r.rot('leg_BR', -g * 0.5 * moving, -g * 0.3 * moving);
        r.rot('leg_ML', -g * 0.5 * moving, -g * 0.3 * moving);
        const g2 = Math.cos(ph * 1.6) * 0.3 * moving;
        for (const n of ['FL', 'BL', 'MR']) r.rot(`leg_${n}_2`, g2);
        for (const n of ['FR', 'BR', 'ML']) r.rot(`leg_${n}_2`, -g2);
        r.rot('head', 0.05 * breathe, Math.sin(t * 1.3) * 0.15);
        this.bob = Math.abs(g) * 0.025 * moving;
        if (this.stunned) {
          r.rot('body', 0, 0, Math.sin(t * 5) * 0.15);
          // open in a V: lift outward + splay the rear out (pure sideways rotation makes them cross)
          r.rot('shell_L', 0.25, -0.3, 0.42);
          r.rot('shell_R', 0.25, 0.3, -0.42);
        }
        break;
      }
      case 'wisp': {
        this.bob = Math.sin(t * 2) * 0.15;
        r.rot('ring_A', 0, t * 1.8, 0);
        r.rot('ring_B', 0, -t * 2.6, 0);
        r.rot('wing_L', 0, Math.sin(t * 14) * 0.6, 0);
        r.rot('wing_R', 0, -Math.sin(t * 14) * 0.6, 0);
        r.rot('lantern', 0.15 * moving, Math.sin(t * 0.9) * 0.3, Math.sin(t * 1.3) * 0.08);
        const fl = 1 + Math.sin(t * 17) * 0.06 + Math.sin(t * 7) * 0.05;
        r.scale('flame', fl, fl * 1.05, fl);
        if (this.stunned) r.rot('lantern', 0.5, t * 4, 0);
        break;
      }
    }
  }
}
