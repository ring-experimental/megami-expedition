import * as THREE from 'three';
import { clamp, mulberry32 } from '../core/utils';
import type { TerrainDef } from '../data/zones';

/** The current zone's terrain (roads get flattened and painted as dirt, plazas paved). Set by FieldMode. */
let T: TerrainDef;
export function setTerrain(t: TerrainDef) {
  T = t;
}

function segDist(px: number, pz: number, ax: number, az: number, bx: number, bz: number) {
  const dx = bx - ax, dz = bz - az;
  const t = clamp(((px - ax) * dx + (pz - az) * dz) / (dx * dx + dz * dz), 0, 1);
  const x = ax + dx * t - px, z = az + dz * t - pz;
  return Math.sqrt(x * x + z * z);
}

export function roadDist(x: number, z: number) {
  let d = Infinity;
  for (const r of T.roads) for (let i = 0; i < r.length - 1; i++) d = Math.min(d, segDist(x, z, r[i][0], r[i][1], r[i + 1][0], r[i + 1][1]));
  return d;
}

const ss = (e0: number, e1: number, x: number) => {
  const t = clamp((x - e0) / (e1 - e0), 0, 1);
  return t * t * (3 - 2 * t);
};

export function plazaMask(x: number, z: number) {
  let m = 0;
  for (const p of T.plazas) m = Math.max(m, 1 - ss(p.r - 3, p.r + 2, Math.hypot(x - p.x, z - p.z)));
  return m;
}
export function roadMask(x: number, z: number) {
  return 1 - ss(2.2, 4.2, roadDist(x, z));
}

function edgeFactor(x: number, z: number) {
  return ss(T.edge[0], T.edge[1], Math.hypot(x, z));
}

export function heightAt(x: number, z: number) {
  const k = T.seed * 0.37;
  let h = T.hills * (
    1.3 * Math.sin(x * 0.045 + 1.3 + k) * Math.cos(z * 0.05 - 0.7) +
    0.6 * Math.sin(x * 0.11 + z * 0.07 + k) +
    0.3 * Math.sin(z * 0.19 - x * 0.05) +
    0.15 * Math.sin(x * 0.37) * Math.sin(z * 0.29));
  const rm = roadMask(x, z);
  const pm = plazaMask(x, z);
  h = h * (1 - rm * 0.7);
  h = h * (1 - pm) + 0.05 * pm;
  if (T.rooms) {
    // interiors: flat floors in the rooms, a wall rising just outside each
    let inside = 0;
    for (const r of T.rooms) inside = Math.max(inside, 1 - ss(r.r - 1, r.r + 1.5, Math.hypot(x - r.x, z - r.z)));
    return h * 0.05 + (1 - inside) * 16;
  }
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
  const rnd = mulberry32(T.seed);
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
  const P = T.palette;
  const grassA = new THREE.Color(P.grassA), grassB = new THREE.Color(P.grassB), grassC = new THREE.Color(P.grassC);
  const dirt = new THREE.Color(P.dirt), dirtB = new THREE.Color(P.dirtB);
  const stoneA = new THREE.Color(P.stoneA), stoneB = new THREE.Color(P.stoneB);
  const cliff = new THREE.Color(P.cliff), cliffB = new THREE.Color(P.cliffB);
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
    const pm = Math.max(plazaMask(cx, cz), T.paved && Math.hypot(cx, cz) < T.paved ? 1 : 0);
    if (pm > 0.5) {
      const tile = (Math.floor(cx / 2.2) + Math.floor(cz / 2.2)) & 1;
      c.copy(tile ? stoneA : stoneB).offsetHSL(0, 0, (n2 - 0.5) * 0.04);
      for (const pl of T.plazas) {
        const rr = Math.hypot(cx - pl.x, cz - pl.z);
        if (pl.rings?.some((r) => Math.abs(rr - r) < 0.6)) c.set(P.trim);
      }
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
export function buildGrass(avoid: (x: number, z: number) => boolean, radius: number): THREE.Object3D {
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
  const count = Math.max(1, Math.round(4200 * T.grass));
  const mat = new THREE.MeshStandardMaterial({ color: 0xffffff, flatShading: true, roughness: 1 });
  const inst = new THREE.InstancedMesh(merged, mat, count);
  const flowers = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(0.08, 0), new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0x222222, flatShading: true }), 600);
  const paved = T.paved ?? 0;
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3();
  const col = new THREE.Color();
  let n = 0, f = 0;
  const flowerCols = ['#f3d36b', '#e9eef7', '#d98ad6', '#7fd7ff'];
  for (let tries = 0; tries < Math.max(1, count) * 3 && n < count; tries++) {
    const x = (rnd() - 0.5) * radius * 2, z = (rnd() - 0.5) * radius * 2;
    const rr = Math.hypot(x, z);
    if (rr > radius - 2 || rr < paved || roadMask(x, z) > 0.2 || plazaMask(x, z) > 0.2 || avoid(x, z)) continue;
    const y = heightAt(x, z);
    q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), rnd() * 6.28);
    const sc = 0.7 + rnd() * 0.9;
    s.set(sc, sc * (0.8 + rnd() * 0.6), sc);
    p.set(x, y - 0.05, z);
    m.compose(p, q, s);
    inst.setMatrixAt(n, m);
    col.set(T.palette.grassTuft).offsetHSL((rnd() - 0.5) * 0.06, 0, (rnd() - 0.5) * 0.15);
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
  // keep the per-instance colour attribute even on bare ground: a mesh without it compiles another program
  if (!n) inst.setColorAt(0, col.set(T.palette.grassTuft));
  if (!f) flowers.setColorAt(0, col.set('#ffffff'));
  inst.count = T.grass > 0 ? n : 0;
  flowers.count = T.grass > 0 ? f : 0;
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
