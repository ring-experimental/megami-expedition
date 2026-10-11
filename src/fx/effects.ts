import * as THREE from 'three';
import { rand } from '../core/utils';
import { FakeLight, FakeLightSet, patchMaterial } from './fakeLights';

// ---------------------------------------------------------------------------
// CPU particle system rendered as soft points
// ---------------------------------------------------------------------------
let _sprite: THREE.Texture | null = null;
function spriteTex() {
  if (_sprite) return _sprite;
  const c = document.createElement('canvas');
  c.width = c.height = 64;
  const g = c.getContext('2d')!;
  const grd = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grd.addColorStop(0, 'rgba(255,255,255,1)');
  grd.addColorStop(0.35, 'rgba(255,255,255,0.6)');
  grd.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grd;
  g.fillRect(0, 0, 64, 64);
  _sprite = new THREE.CanvasTexture(c);
  return _sprite;
}

export interface EmitOpts {
  vel?: THREE.Vector3;
  color?: THREE.ColorRepresentation;
  life?: number;
  size?: number;
  sizeEnd?: number;
  gravity?: number;
  drag?: number;
  alpha?: number;
}

/**
 * Periodic steam puffs from a model's `steam_point` node: Kai's backpack ('pack') or the steam
 * golem's chimney ('chimney', bigger and greyer). `scale` = model scale in the scene.
 */
export class SteamVent {
  private t = Math.random() * 0.2;
  private p = new THREE.Vector3();
  constructor(public node: THREE.Object3D, private style: 'pack' | 'chimney', private scale = 1) {}

  /** busy = running / attacking: puff faster. */
  update(dt: number, smoke: Particles, busy = false) {
    this.t -= dt;
    if (this.t > 0) return;
    this.node.getWorldPosition(this.p);
    const s = this.scale;
    if (this.style === 'pack') {
      this.t = busy ? 0.05 : 0.18;
      smoke.emit(this.p, { vel: new THREE.Vector3((Math.random() - 0.5) * 0.3, 1.2, (Math.random() - 0.5) * 0.3), color: 0xf2efe8, life: 1.1, size: 0.25, sizeEnd: 0.8, alpha: 0.45, drag: 0.5 });
    } else {
      this.t = busy ? 0.07 : 0.16;
      smoke.emit(this.p, {
        vel: new THREE.Vector3((Math.random() - 0.5) * 0.4 * s, (1.5 + Math.random() * 0.5) * s, (Math.random() - 0.5) * 0.4 * s),
        color: Math.random() < 0.3 ? 0x9d978e : 0xd9d3c9, life: 1.8, size: 0.4 * s, sizeEnd: 1.5 * s, alpha: 0.5, drag: 0.45,
      });
    }
  }
}

export class Particles {
  points: THREE.Points;
  private max: number;
  private n = 0;
  private pos: Float32Array;
  private col: Float32Array;
  private siz: Float32Array;
  private vel: Float32Array;
  private life: Float32Array;
  private maxLife: Float32Array;
  private s0: Float32Array;
  private s1: Float32Array;
  private grav: Float32Array;
  private drag: Float32Array;
  private a0: Float32Array;
  private geo: THREE.BufferGeometry;
  material: THREE.ShaderMaterial;
  private _c = new THREE.Color();

  constructor(max: number, additive: boolean) {
    this.max = max;
    this.pos = new Float32Array(max * 3);
    this.col = new Float32Array(max * 4);
    this.siz = new Float32Array(max);
    this.vel = new Float32Array(max * 3);
    this.life = new Float32Array(max);
    this.maxLife = new Float32Array(max);
    this.s0 = new Float32Array(max);
    this.s1 = new Float32Array(max);
    this.grav = new Float32Array(max);
    this.drag = new Float32Array(max);
    this.a0 = new Float32Array(max);
    this.geo = new THREE.BufferGeometry();
    this.geo.setAttribute('position', new THREE.BufferAttribute(this.pos, 3).setUsage(THREE.DynamicDrawUsage));
    this.geo.setAttribute('pcolor', new THREE.BufferAttribute(this.col, 4).setUsage(THREE.DynamicDrawUsage));
    this.geo.setAttribute('size', new THREE.BufferAttribute(this.siz, 1).setUsage(THREE.DynamicDrawUsage));
    this.material = new THREE.ShaderMaterial({
      uniforms: { map: { value: spriteTex() }, uScale: { value: 800 } },
      vertexShader: `
        attribute float size; attribute vec4 pcolor; varying vec4 vColor; uniform float uScale;
        void main(){ vColor = pcolor; vec4 mv = modelViewMatrix * vec4(position,1.0);
          gl_PointSize = size * uScale / max(0.1, -mv.z); gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `
        uniform sampler2D map; varying vec4 vColor;
        void main(){ float a = texture2D(map, gl_PointCoord).a * vColor.a; if (a < 0.01) discard; gl_FragColor = vec4(vColor.rgb, a); }`,
      transparent: true,
      depthWrite: false,
      blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending,
    });
    this.points = new THREE.Points(this.geo, this.material);
    this.points.frustumCulled = false;
    this.points.renderOrder = additive ? 10 : 9;
  }

  setViewport(heightPx: number, fovDeg: number) {
    this.material.uniforms.uScale.value = heightPx / (2 * Math.tan((fovDeg * Math.PI) / 360));
  }

  emit(p: THREE.Vector3, o: EmitOpts = {}) {
    if (this.n >= this.max) return;
    const i = this.n++;
    this.pos.set([p.x, p.y, p.z], i * 3);
    const v = o.vel;
    this.vel.set(v ? [v.x, v.y, v.z] : [0, 0, 0], i * 3);
    this._c.set(o.color ?? 0xffffff);
    this.col.set([this._c.r, this._c.g, this._c.b, o.alpha ?? 1], i * 4);
    this.life[i] = this.maxLife[i] = o.life ?? 0.6;
    this.s0[i] = o.size ?? 0.2;
    this.s1[i] = o.sizeEnd ?? (o.size ?? 0.2) * 0.2;
    this.siz[i] = this.s0[i];
    this.grav[i] = o.gravity ?? 0;
    this.drag[i] = o.drag ?? 1;
    this.a0[i] = o.alpha ?? 1;
  }

  burst(p: THREE.Vector3, count: number, o: EmitOpts & { speed?: number; up?: number; spread?: number } = {}) {
    const sp = o.speed ?? 5;
    for (let k = 0; k < count; k++) {
      const dir = new THREE.Vector3(rand(-1, 1), rand(-1, 1) + (o.up ?? 0), rand(-1, 1)).normalize().multiplyScalar(sp * rand(0.4, 1));
      const pos = o.spread ? p.clone().add(new THREE.Vector3(rand(-1, 1), rand(-1, 1), rand(-1, 1)).multiplyScalar(o.spread)) : p;
      this.emit(pos, { ...o, vel: dir, life: (o.life ?? 0.5) * rand(0.6, 1.2) });
    }
  }

  update(dt: number) {
    let i = 0;
    while (i < this.n) {
      this.life[i] -= dt;
      if (this.life[i] <= 0) {
        this.swapRemove(i);
        continue;
      }
      const t = 1 - this.life[i] / this.maxLife[i];
      const i3 = i * 3;
      const d = Math.pow(this.drag[i], dt);
      this.vel[i3] *= d; this.vel[i3 + 1] = this.vel[i3 + 1] * d - this.grav[i] * dt; this.vel[i3 + 2] *= d;
      this.pos[i3] += this.vel[i3] * dt;
      this.pos[i3 + 1] += this.vel[i3 + 1] * dt;
      this.pos[i3 + 2] += this.vel[i3 + 2] * dt;
      this.siz[i] = this.s0[i] + (this.s1[i] - this.s0[i]) * t;
      this.col[i * 4 + 3] = this.a0[i] * (t < 0.1 ? t / 0.1 : 1 - (t - 0.1) / 0.9);
      i++;
    }
    this.geo.setDrawRange(0, this.n);
    // upload only the live particles, not the whole pool
    for (const [name, stride] of [['position', 3], ['pcolor', 4], ['size', 1]] as const) {
      const a = this.geo.attributes[name] as THREE.BufferAttribute;
      a.clearUpdateRanges();
      if (this.n > 0) {
        a.addUpdateRange(0, this.n * stride);
        a.needsUpdate = true;
      }
    }
  }

  private swapRemove(i: number) {
    const last = --this.n;
    if (i === last) return;
    const cp = (arr: Float32Array, stride: number) => arr.copyWithin(i * stride, last * stride, last * stride + stride);
    cp(this.pos, 3); cp(this.vel, 3); cp(this.col, 4);
    this.siz[i] = this.siz[last]; this.life[i] = this.life[last]; this.maxLife[i] = this.maxLife[last];
    this.s0[i] = this.s0[last]; this.s1[i] = this.s1[last]; this.grav[i] = this.grav[last];
    this.drag[i] = this.drag[last]; this.a0[i] = this.a0[last];
  }

  clear() {
    this.n = 0;
  }
}

// ---------------------------------------------------------------------------
// One-shot mesh effects (rings, slash arcs, projectiles, lights)
// ---------------------------------------------------------------------------
interface Live { obj: THREE.Object3D | null; light?: FakeLight; t: number; dur: number; update: (k: number, dt: number) => void; done?: () => void }

// Geometries shared by every one-shot effect (allocating + uploading a new buffer per hit caused
// GC churn and first-use stalls). Marked `shared` so Effects never disposes them.
const shared = <T extends THREE.BufferGeometry>(g: T) => { g.userData.shared = true; return g; };
const GEO = {
  ring: shared(new THREE.RingGeometry(0.85, 1, 48)),
  orb: shared(new THREE.SphereGeometry(1, 12, 8)),
  orbCore: shared(new THREE.SphereGeometry(0.5, 8, 6)),
  pillar: shared(new THREE.CylinderGeometry(1, 1, 1, 24, 1, true)),
  shard: shared(new THREE.ConeGeometry(0.18, 1, 5)),
};
const slashGeos = new Map<string, THREE.BufferGeometry>();
function slashGeo(radius: number, from: number, len: number) {
  const key = `${radius.toFixed(2)}|${from.toFixed(2)}|${len.toFixed(2)}`;
  let geo = slashGeos.get(key);
  if (geo) return geo;
  geo = shared(new THREE.RingGeometry(radius * 0.55, radius, 32, 1, from, len));
  // fade along the arc using vertex colors
  const cols: number[] = [];
  const posAttr = geo.attributes.position;
  for (let i = 0; i < posAttr.count; i++) {
    const a = Math.atan2(posAttr.getY(i), posAttr.getX(i));
    const f = Math.max(0, Math.min(1, (a - from) / len));
    cols.push(f, f, f);
  }
  geo.setAttribute('color', new THREE.Float32BufferAttribute(cols, 3));
  slashGeos.set(key, geo);
  return geo;
}

export class Effects {
  sparks = new Particles(2500, true);
  smoke = new Particles(1500, false);
  /** Fake (shader-array) lights of this scene: flashes, projectiles, lamps — see fx/fakeLights.ts. */
  lights = new FakeLightSet();
  private live: Live[] = [];
  constructor(public scene: THREE.Scene) {
    scene.add(this.sparks.points, this.smoke.points);
  }

  setViewport(h: number, fov: number) {
    this.sparks.setViewport(h, fov);
    this.smoke.setViewport(h, fov);
  }

  update(dt: number) {
    this.sparks.update(dt);
    this.smoke.update(dt);
    for (let i = this.live.length - 1; i >= 0; i--) {
      const l = this.live[i];
      l.t += dt;
      const k = Math.min(1, l.t / l.dur);
      l.update(k, dt);
      if (k >= 1) {
        this.dispose(l);
        this.live.splice(i, 1);
        l.done?.();
      }
    }
  }

  private dispose(l: Live) {
    if (l.light) this.lights.remove(l.light);
    if (!l.obj) return;
    this.scene.remove(l.obj);
    // Materials are deliberately NOT disposed: dispose() releases the shader program once no
    // material uses it, so the next hit of the same kind recompiled it (100–300 ms hitches). The
    // material objects themselves are garbage-collected; the few programs stay cached.
    l.obj.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.geometry && !m.geometry.userData.shared) m.geometry.dispose();
    });
  }

  clear() {
    for (const l of this.live) this.dispose(l);
    this.live = [];
    this.sparks.clear();
    this.smoke.clear();
  }

  private add(obj: THREE.Object3D | null, dur: number, update: Live['update'], done?: () => void, light?: FakeLight) {
    if (obj) this.scene.add(obj);
    this.live.push({ obj, light, t: 0, dur, update, done });
  }

  /** A fake point light owned by an effect (removed with it). */
  private addLight(color: THREE.ColorRepresentation, intensity: number, dist: number) {
    const l = this.lights.add(new FakeLight(color, intensity, dist));
    l.priority = 1; // short-lived hit lights beat ambient lamps for the limited slots
    return l;
  }

  /** Expanding flat ring (shockwave). */
  ring(pos: THREE.Vector3, color: THREE.ColorRepresentation, radius = 2, dur = 0.4, vertical?: THREE.Vector3) {
    const mat = new THREE.MeshBasicMaterial({ color, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
    const m = new THREE.Mesh(GEO.ring, mat);
    m.position.copy(pos);
    if (vertical) m.lookAt(pos.clone().add(vertical));
    else m.rotation.x = -Math.PI / 2;
    this.add(m, dur, (k) => {
      const s = 0.2 + radius * (1 - Math.pow(1 - k, 3));
      m.scale.set(s, s, s);
      mat.opacity = 1 - k;
    });
  }

  /** Crescent slash trail in a plane around `pos`, facing yaw. tilt rotates the arc plane (radians). */
  slash(pos: THREE.Vector3, yaw: number, color: THREE.ColorRepresentation, radius = 1.8, tilt = 0, dur = 0.22, from = -1.4, len = 2.8) {
    const mat = new THREE.MeshBasicMaterial({ color, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
    const geo = slashGeo(radius, from, len);
    mat.vertexColors = true;
    const m = new THREE.Mesh(geo, mat);
    const holder = new THREE.Group();
    holder.position.copy(pos);
    holder.rotation.y = yaw;
    m.rotation.x = -Math.PI / 2 + tilt;
    m.rotation.z = -Math.PI / 2;
    holder.add(m);
    this.add(holder, dur, (k) => {
      mat.opacity = 1 - k;
      const s = 1 + k * 0.15;
      m.scale.set(s, s, s);
    });
  }

  /** Short-lived point light flash. */
  flash(pos: THREE.Vector3, color: THREE.ColorRepresentation, intensity = 30, dist = 8, dur = 0.25) {
    const l = this.addLight(color, intensity, dist);
    l.position.copy(pos);
    this.add(null, dur, (k) => { l.intensity = intensity * (1 - k); }, undefined, l);
  }

  /** Glowing orb flying from a to b (arc), with trail. Resolves on impact. */
  projectile(a: THREE.Vector3, b: THREE.Vector3, color: THREE.ColorRepresentation, dur = 0.45, size = 0.25, arc = 1): Promise<void> {
    return new Promise((resolve) => {
      const mat = new THREE.MeshBasicMaterial({ color, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false });
      const m = new THREE.Mesh(GEO.orb, mat);
      m.scale.setScalar(size);
      const core = new THREE.Mesh(GEO.orbCore, new THREE.MeshBasicMaterial({ color: 0xffffff }));
      m.add(core);
      const light = this.addLight(color, 8, 6);
      const p = new THREE.Vector3();
      this.add(m, dur, (k) => {
        p.lerpVectors(a, b, k);
        p.y += Math.sin(k * Math.PI) * arc;
        m.position.copy(p);
        light.position.copy(p);
        this.sparks.emit(p, { color, life: 0.35, size: size * 2.2, sizeEnd: 0.02, alpha: 0.8 });
      }, resolve, light);
    });
  }

  /** Vertical light pillar (heal / recruit / buff). */
  pillar(pos: THREE.Vector3, color: THREE.ColorRepresentation, height = 4, radius = 0.8, dur = 0.9) {
    const mat = new THREE.MeshBasicMaterial({ color, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
    const m = new THREE.Mesh(GEO.pillar, mat);
    m.position.copy(pos).add(new THREE.Vector3(0, height / 2, 0));
    this.add(m, dur, (k) => {
      mat.opacity = Math.sin(k * Math.PI) * 0.6;
      m.scale.set(radius * (1 - k * 0.5), height, radius * (1 - k * 0.5));
    });
    for (let i = 0; i < 24; i++) {
      this.sparks.emit(pos.clone().add(new THREE.Vector3(rand(-radius, radius), rand(0, 0.5), rand(-radius, radius))), {
        vel: new THREE.Vector3(0, rand(2, 5), 0), color, life: rand(0.5, 1), size: 0.18, alpha: 0.9,
      });
    }
  }

  /** Lightning bolt from sky to target. */
  bolt(target: THREE.Vector3, color: THREE.ColorRepresentation = 0xfff04a) {
    const pts: THREE.Vector3[] = [];
    const top = target.clone().add(new THREE.Vector3(rand(-1, 1), 9, rand(-1, 1)));
    for (let i = 0; i <= 10; i++) {
      const p = top.clone().lerp(target, i / 10);
      if (i > 0 && i < 10) p.add(new THREE.Vector3(rand(-0.5, 0.5), 0, rand(-0.5, 0.5)));
      pts.push(p);
    }
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({ color, transparent: true, blending: THREE.AdditiveBlending });
    const line = new THREE.Line(geo, mat);
    this.add(line, 0.25, (k) => { mat.opacity = 1 - k; });
    this.flash(target.clone().add(new THREE.Vector3(0, 1, 0)), color, 60, 12, 0.25);
  }

  /** Ice shards bursting out of the ground. */
  shards(pos: THREE.Vector3, color: THREE.ColorRepresentation = 0x8fe8ff, count = 6) {
    for (let i = 0; i < count; i++) {
      const mat = new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.8, transparent: true, flatShading: true, roughness: 0.1 });
      patchMaterial(mat);
      const m = new THREE.Mesh(GEO.shard, mat);
      const h = rand(0.8, 1.6);
      const a = (i / count) * Math.PI * 2 + rand(-0.3, 0.3);
      const r = rand(0.2, 0.7);
      m.position.set(pos.x + Math.cos(a) * r, pos.y, pos.z + Math.sin(a) * r);
      m.rotation.set(Math.sin(a) * 0.5, 0, -Math.cos(a) * 0.5);
      const base = m.position.y;
      this.add(m, 0.7, (k) => {
        const g = k < 0.2 ? k / 0.2 : 1;
        m.scale.set(1, g * h, 1);
        m.position.y = base + 0.4 * g;
        mat.opacity = k > 0.6 ? 1 - (k - 0.6) / 0.4 : 1;
      });
    }
  }

  /** Ground telegraph (field enemy attack warning). Returns handle to remove. */
  telegraph(parent: THREE.Object3D, length: number, width: number, color: THREE.ColorRepresentation = 0xff3020) {
    const g = new THREE.Group();
    const fillMat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2 });
    const fill = new THREE.Mesh(new THREE.PlaneGeometry(width, length), fillMat);
    fill.position.z = length / 2;
    const edgeMat = new THREE.LineBasicMaterial({ color: 0xffe0d0, transparent: true, opacity: 0 });
    const hw = width / 2;
    const edge = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-hw, 0, 0), new THREE.Vector3(hw, 0, 0), new THREE.Vector3(hw, length, 0), new THREE.Vector3(-hw, length, 0),
    ]), edgeMat);
    const fillHolder = new THREE.Group();
    fillHolder.add(fill);
    fill.rotation.x = -Math.PI / 2;
    const edgeHolder = new THREE.Group();
    edge.rotation.x = Math.PI / 2; // local +Y → world +Z (forward)
    edgeHolder.add(edge);
    g.add(fillHolder, edgeHolder);
    g.position.y = 0.12;
    // keep the decal level even if the enemy pitches during its wind-up animation
    parent.add(g);
    return {
      set: (k: number) => {
        fillMat.opacity = 0.18 + 0.4 * k;
        edgeMat.opacity = 0.5 + 0.5 * k;
        fillHolder.scale.z = 0.25 + 0.75 * k;
        fill.position.z = length / 2;
      },
      remove: () => {
        parent.remove(g);
        fill.geometry.dispose(); // materials kept alive so their programs stay compiled (see dispose())
        edge.geometry.dispose();
      },
    };
  }
}
