import * as THREE from 'three';
import { clamp, mulberry32 } from '../core/utils';

/** Roads (polyline segments) that get flattened and painted as dirt. */
const ROADS: [number, number][][] = [
  [[0, 70], [0, 40], [0, 10], [0, -30]],
  [[0, 22], [-14, 16], [-30, 8], [-42, -6], [-46, -20]],
  [[0, 2], [16, -2], [32, -8], [48, -18]],
  [[0, -30], [18, -38], [36, -44]],
  [[0, 40], [-14, 44]],
];
const PLAZA = { x: 0, z: -40, r: 15 };

function segDist(px: number, pz: number, ax: number, az: number, bx: number, bz: number) {
  const dx = bx - ax, dz = bz - az;
  const t = clamp(((px - ax) * dx + (pz - az) * dz) / (dx * dx + dz * dz), 0, 1);
  const x = ax + dx * t - px, z = az + dz * t - pz;
  return Math.sqrt(x * x + z * z);
}

export function roadDist(x: number, z: number) {
  let d = Infinity;
  for (const r of ROADS) for (let i = 0; i < r.length - 1; i++) d = Math.min(d, segDist(x, z, r[i][0], r[i][1], r[i + 1][0], r[i + 1][1]));
  return d;
}

const ss = (e0: number, e1: number, x: number) => {
  const t = clamp((x - e0) / (e1 - e0), 0, 1);
  return t * t * (3 - 2 * t);
};

export function plazaMask(x: number, z: number) {
  return 1 - ss(PLAZA.r - 3, PLAZA.r + 2, Math.hypot(x - PLAZA.x, z - PLAZA.z));
}
export function roadMask(x: number, z: number) {
  return 1 - ss(2.2, 4.2, roadDist(x, z));
}

function edgeFactor(x: number, z: number) {
  return ss(68, 92, Math.hypot(x, z));
}

export function heightAt(x: number, z: number) {
  let h =
    1.3 * Math.sin(x * 0.045 + 1.3) * Math.cos(z * 0.05 - 0.7) +
    0.6 * Math.sin(x * 0.11 + z * 0.07) +
    0.3 * Math.sin(z * 0.19 - x * 0.05) +
    0.15 * Math.sin(x * 0.37) * Math.sin(z * 0.29);
  const rm = roadMask(x, z);
  const pm = plazaMask(x, z);
  h = h * (1 - rm * 0.7);
  h = h * (1 - pm) + 0.05 * pm;
  const e = edgeFactor(x, z);
  if (e > 0) {
    const a = Math.atan2(z, x);
    h += e * e * 26 + e * (2.4 * Math.sin(a * 7) + 1.6 * Math.sin(a * 13 + 1) + 1.2 * Math.sin(x * 0.3) * Math.cos(z * 0.3));
  }
  return h;
}

export function buildTerrain(): THREE.Mesh {
  const size = 240, seg = 150;
  let geo: THREE.BufferGeometry = new THREE.PlaneGeometry(size, size, seg, seg);
  geo.rotateX(-Math.PI / 2);
  geo = geo.toNonIndexed();
  const pos = geo.attributes.position as THREE.BufferAttribute;
  const rnd = mulberry32(7);
  // jitter grid slightly for a hand-made faceted look (same jitter for shared vertices)
  const jit = new Map<string, [number, number]>();
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), z = pos.getZ(i);
    const key = `${x.toFixed(2)},${z.toFixed(2)}`;
    let j = jit.get(key);
    if (!j) {
      const edge = Math.abs(x) >= size / 2 - 0.01 || Math.abs(z) >= size / 2 - 0.01;
      j = edge ? [0, 0] : [(rnd() - 0.5) * 0.6, (rnd() - 0.5) * 0.6];
      jit.set(key, j);
    }
    const nx = x + j[0], nz = z + j[1];
    pos.setXYZ(i, nx, heightAt(nx, nz), nz);
  }
  geo.computeVertexNormals();
  const nrm = geo.attributes.normal as THREE.BufferAttribute;
  const colors = new Float32Array(pos.count * 3);
  const c = new THREE.Color();
  const grassA = new THREE.Color('#6d9a45'), grassB = new THREE.Color('#8fae4e'), grassC = new THREE.Color('#5a8a4a');
  const dirt = new THREE.Color('#a67f55'), dirtB = new THREE.Color('#8e6a45');
  const stoneA = new THREE.Color('#9b958a'), stoneB = new THREE.Color('#857f74');
  const cliff = new THREE.Color('#8a7660'), cliffB = new THREE.Color('#6e5d4c');
  for (let i = 0; i < pos.count; i += 3) {
    const cx = (pos.getX(i) + pos.getX(i + 1) + pos.getX(i + 2)) / 3;
    const cz = (pos.getZ(i) + pos.getZ(i + 1) + pos.getZ(i + 2)) / 3;
    const ny = (nrm.getY(i) + nrm.getY(i + 1) + nrm.getY(i + 2)) / 3;
    const n = Math.sin(cx * 0.21 + Math.sin(cz * 0.13) * 2) * 0.5 + 0.5;
    const n2 = rnd();
    c.copy(grassA).lerp(grassB, n * 0.7).lerp(grassC, n2 * 0.35);
    const rm = roadMask(cx, cz);
    if (rm > 0.35) c.copy(dirt).lerp(dirtB, n2 * 0.6);
    else if (rm > 0.1) c.lerp(dirt, 0.45);
    const pm = plazaMask(cx, cz);
    if (pm > 0.5) {
      const tile = (Math.floor(cx / 2.2) + Math.floor(cz / 2.2)) & 1;
      c.copy(tile ? stoneA : stoneB).offsetHSL(0, 0, (n2 - 0.5) * 0.04);
      const rr = Math.hypot(cx - PLAZA.x, cz - PLAZA.z);
      if (Math.abs(rr - 9) < 0.7 || Math.abs(rr - 13.2) < 0.5) c.set('#b08a4a');
    }
    const e = edgeFactor(cx, cz);
    if (ny < 0.8 || e > 0.35) c.copy(cliff).lerp(cliffB, n2 * 0.7);
    for (let k = 0; k < 3; k++) colors.set([c.r, c.g, c.b], (i + k) * 3);
  }
  geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  const mat = new THREE.MeshStandardMaterial({ vertexColors: true, flatShading: true, roughness: 0.95, metalness: 0 });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.receiveShadow = true;
  return mesh;
}

/** Instanced grass tufts & flowers for ground richness. */
export function buildGrass(avoid: (x: number, z: number) => boolean): THREE.Object3D {
  const g = new THREE.Group();
  const tuft = new THREE.ConeGeometry(0.07, 0.5, 3);
  tuft.translate(0, 0.25, 0);
  const blades: THREE.BufferGeometry[] = [];
  for (let i = 0; i < 3; i++) {
    const b = tuft.clone();
    b.rotateZ((i - 1) * 0.35);
    b.rotateY(i * 2.1);
    b.translate((i - 1) * 0.06, 0, 0);
    blades.push(b);
  }
  const merged = mergeGeos(blades);
  const rnd = mulberry32(42);
  const count = 4200;
  const mat = new THREE.MeshStandardMaterial({ color: 0xffffff, flatShading: true, roughness: 1 });
  const inst = new THREE.InstancedMesh(merged, mat, count);
  const flowers = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(0.08, 0), new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0x222222, flatShading: true }), 600);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3();
  const col = new THREE.Color();
  let n = 0, f = 0;
  const flowerCols = ['#f3d36b', '#e9eef7', '#d98ad6', '#7fd7ff'];
  for (let tries = 0; tries < count * 3 && n < count; tries++) {
    const x = (rnd() - 0.5) * 150, z = (rnd() - 0.5) * 150;
    if (Math.hypot(x, z) > 74 || roadMask(x, z) > 0.2 || plazaMask(x, z) > 0.2 || avoid(x, z)) continue;
    const y = heightAt(x, z);
    q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), rnd() * 6.28);
    const sc = 0.7 + rnd() * 0.9;
    s.set(sc, sc * (0.8 + rnd() * 0.6), sc);
    p.set(x, y - 0.05, z);
    m.compose(p, q, s);
    inst.setMatrixAt(n, m);
    col.set('#7fb04a').offsetHSL((rnd() - 0.5) * 0.06, 0, (rnd() - 0.5) * 0.15);
    inst.setColorAt(n, col);
    n++;
    if (f < 600 && rnd() < 0.14) {
      p.set(x + 0.15, y + 0.35 * sc, z + 0.1);
      m.compose(p, q, s.set(1, 1, 1));
      flowers.setMatrixAt(f, m);
      flowers.setColorAt(f, col.set(flowerCols[Math.floor(rnd() * flowerCols.length)]));
      f++;
    }
  }
  inst.count = n;
  flowers.count = f;
  inst.receiveShadow = true;
  g.add(inst, flowers);
  return g;
}

function mergeGeos(geos: THREE.BufferGeometry[]) {
  const nonIdx = geos.map((g) => (g.index ? g.toNonIndexed() : g));
  let total = 0;
  for (const g of nonIdx) total += g.attributes.position.count;
  const pos = new Float32Array(total * 3);
  let o = 0;
  for (const g of nonIdx) {
    pos.set(g.attributes.position.array as Float32Array, o);
    o += g.attributes.position.count * 3;
  }
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  out.computeVertexNormals();
  return out;
}
