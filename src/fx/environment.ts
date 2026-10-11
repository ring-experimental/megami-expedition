import * as THREE from 'three';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { mulberry32 } from '../core/utils';

let envTex: THREE.Texture | null = null;
export function getEnvMap(renderer: THREE.WebGLRenderer) {
  if (!envTex) {
    const pmrem = new THREE.PMREMGenerator(renderer);
    envTex = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    pmrem.dispose();
  }
  return envTex;
}

export interface SkyColors { top: string; horizon: string; bottom: string; sun: string; sunDir: THREE.Vector3 }

export function buildSky(c: SkyColors) {
  const mat = new THREE.ShaderMaterial({
    side: THREE.BackSide,
    depthWrite: false,
    fog: false,
    uniforms: {
      top: { value: new THREE.Color(c.top) },
      horizon: { value: new THREE.Color(c.horizon) },
      bottom: { value: new THREE.Color(c.bottom) },
      sunCol: { value: new THREE.Color(c.sun) },
      sunDir: { value: c.sunDir.clone().normalize() },
    },
    vertexShader: `varying vec3 vDir; void main(){ vDir = normalize(position); vec4 p = projectionMatrix * modelViewMatrix * vec4(position,1.0); gl_Position = p.xyww; }`,
    fragmentShader: `
      uniform vec3 top; uniform vec3 horizon; uniform vec3 bottom; uniform vec3 sunCol; uniform vec3 sunDir; varying vec3 vDir;
      void main(){
        float h = vDir.y;
        vec3 c = mix(horizon, top, smoothstep(0.0, 0.55, h));
        c = mix(c, bottom, smoothstep(0.0, -0.25, h));
        float s = max(dot(normalize(vDir), sunDir), 0.0);
        c += sunCol * (pow(s, 600.0) * 4.0 + pow(s, 12.0) * 0.45 + pow(s, 3.0) * 0.12);
        gl_FragColor = vec4(c, 1.0);
      }`,
  });
  const m = new THREE.Mesh(new THREE.SphereGeometry(450, 32, 16), mat);
  m.renderOrder = -10;
  m.frustumCulled = false;
  return m;
}

/** Distant scenery: mountain ring, floating islands, puffy clouds. */
export function buildBackdrop(opts: { mountainColor: string; cloudColor: string; seed?: number; radius?: number }) {
  const g = new THREE.Group();
  const rnd = mulberry32(opts.seed ?? 3);
  const R = opts.radius ?? 200;
  const mMat = new THREE.MeshStandardMaterial({ color: opts.mountainColor, flatShading: true, roughness: 1 });
  for (let i = 0; i < 26; i++) {
    const a = (i / 26) * Math.PI * 2 + rnd() * 0.2;
    const r = R + rnd() * 70;
    const h = 30 + rnd() * 50;
    const m = new THREE.Mesh(new THREE.ConeGeometry(18 + rnd() * 22, h, 5 + Math.floor(rnd() * 3)), mMat);
    m.position.set(Math.cos(a) * r, h / 2 - 8, Math.sin(a) * r);
    m.rotation.y = rnd() * 6;
    g.add(m);
  }
  // floating islands
  const rock = new THREE.MeshStandardMaterial({ color: '#7d6a58', flatShading: true, roughness: 1 });
  const grass = new THREE.MeshStandardMaterial({ color: '#6f9a4a', flatShading: true, roughness: 1 });
  const crystal = new THREE.MeshStandardMaterial({ color: '#7fe9ff', emissive: '#5ff3ff', emissiveIntensity: 1.6, flatShading: true });
  for (let i = 0; i < 9; i++) {
    const a = rnd() * Math.PI * 2;
    const r = R * 0.65 + rnd() * R * 0.5;
    const s = 4 + rnd() * 9;
    const isl = new THREE.Group();
    const under = new THREE.Mesh(new THREE.ConeGeometry(s, s * 1.6, 6), rock);
    under.rotation.x = Math.PI;
    under.position.y = -s * 0.8;
    const top = new THREE.Mesh(new THREE.CylinderGeometry(s * 1.02, s, s * 0.25, 6), grass);
    isl.add(under, top);
    if (rnd() < 0.6) {
      const c = new THREE.Mesh(new THREE.OctahedronGeometry(s * 0.25, 0), crystal);
      c.position.set(s * 0.3, s * 0.3, 0);
      c.scale.y = 2;
      isl.add(c);
    }
    isl.position.set(Math.cos(a) * r, 35 + rnd() * 45, Math.sin(a) * r);
    isl.userData.bob = rnd() * 6;
    g.add(isl);
  }
  // clouds
  const cMat = new THREE.MeshStandardMaterial({ color: opts.cloudColor, emissive: opts.cloudColor, emissiveIntensity: 0.35, flatShading: true, roughness: 1 });
  for (let i = 0; i < 22; i++) {
    const cl = new THREE.Group();
    const n = 3 + Math.floor(rnd() * 4);
    for (let k = 0; k < n; k++) {
      const p = new THREE.Mesh(new THREE.IcosahedronGeometry(5 + rnd() * 6, 0), cMat);
      p.position.set(k * 6 - n * 3, rnd() * 3, rnd() * 5);
      p.scale.y = 0.55;
      cl.add(p);
    }
    const a = rnd() * Math.PI * 2, r = R * 0.9 + rnd() * R * 0.8;
    cl.position.set(Math.cos(a) * r, 60 + rnd() * 50, Math.sin(a) * r);
    cl.lookAt(0, cl.position.y, 0);
    g.add(cl);
  }
  return g;
}

export function animateBackdrop(g: THREE.Object3D, t: number) {
  g.rotation.y = t * 0.004;
  for (const c of g.children) if (c.userData.bob !== undefined) c.position.y += Math.sin(t * 0.4 + c.userData.bob) * 0.01;
}

/** Floating aether motes around a center. */
export function buildMotes(count: number, area: number, color = '#9ff6ff') {
  const geo = new THREE.BufferGeometry();
  const pos = new Float32Array(count * 3);
  const rnd = mulberry32(11);
  for (let i = 0; i < count; i++) pos.set([(rnd() - 0.5) * area, rnd() * 10, (rnd() - 0.5) * area], i * 3);
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const mat = new THREE.PointsMaterial({ color, size: 0.12, transparent: true, opacity: 0.85, blending: THREE.AdditiveBlending, depthWrite: false });
  const pts = new THREE.Points(geo, mat);
  pts.frustumCulled = false;
  return pts;
}

export function animateMotes(pts: THREE.Points, t: number, dt: number, center: THREE.Vector3, area: number, baseY = 0) {
  const pos = pts.geometry.attributes.position as THREE.BufferAttribute;
  for (let i = 0; i < pos.count; i++) {
    let x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
    y += dt * (0.25 + (i % 7) * 0.05);
    x += Math.sin(t * 0.7 + i) * dt * 0.3;
    if (y > baseY + 10) y = baseY;
    if (x - center.x > area / 2) x -= area; else if (x - center.x < -area / 2) x += area;
    if (z - center.z > area / 2) z -= area; else if (z - center.z < -area / 2) z += area;
    pos.setXYZ(i, x, y, z);
  }
  pos.needsUpdate = true;
}
