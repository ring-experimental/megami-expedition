import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { clone as skeletonClone } from 'three/examples/jsm/utils/SkeletonUtils.js';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import type { GLTFParser } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { patchMaterial, patchObject } from '../fx/fakeLights';

/** Models produced by tools/blender/*.py → public/models/*.glb */
export const MODEL_NAMES = ['kai', 'lyra', 'knight', 'cograt', 'slime', 'beetle', 'wisp', 'golem', 'props', 'arena'] as const;
export type ModelName = (typeof MODEL_NAMES)[number];

const loaded = new Map<string, THREE.Object3D>();
const missing = new Set<string>();

/** Tweak glTF materials by naming convention (see tools/blender/ASSET_SPEC.md). */
function prepare(root: THREE.Object3D) {
  root.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh) return;
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    for (const m of mats as THREE.MeshStandardMaterial[]) {
      const n = m.name || '';
      if (n.startsWith('glow_')) {
        m.emissiveIntensity = Math.max(m.emissiveIntensity, 2.2);
        m.toneMapped = true;
        mesh.castShadow = false;
      } else if (n.startsWith('jelly_')) {
        m.transparent = true;
        m.opacity = m.opacity < 1 ? m.opacity : 0.72; // keep the GLB alpha when the model sets one
        m.depthWrite = false;
        m.roughness = 0.15;
        mesh.castShadow = false;
      } else if (n === 'glass') {
        m.transparent = true;
        m.opacity = 0.35;
        m.depthWrite = false;
        mesh.castShadow = false;
      }
      // shading comes from the GLB normals: low-poly heroes export per-face (flat) normals,
      // hi-poly models export smooth normals with sharp edges split (tools/blender/hp_helpers.py)
      m.needsUpdate = true;
    }
  });
}

const SPECIAL = /^(glow_|jelly_)|^glass$/;

/** Plain flat-colour PBR material that can be folded into vertex attributes. */
function foldable(m: THREE.Material): m is THREE.MeshStandardMaterial {
  const s = m as THREE.MeshStandardMaterial;
  return !!s.isMeshStandardMaterial && !SPECIAL.test(s.name) && !s.transparent && !s.map && !s.normalMap &&
    !s.roughnessMap && !s.metalnessMap && !s.emissiveMap && !s.aoMap && !s.alphaMap && s.emissive.getHex() === 0;
}

/**
 * The Blender exports have one glTF primitive per material slot (8–22 per model), i.e. one draw call
 * each — per instance and again in the shadow pass. Fold every plain flat-colour primitive of the
 * same glTF mesh into ONE mesh: base colour is baked into the vertex colours (multiplied with the
 * vertex AO), roughness/metalness go to a `pbr` attribute that fx/fakeLights.ts feeds to the shader.
 * Glow / jelly / glass parts stay separate (names are relied on elsewhere). Node names are kept:
 * merged meshes replace the primitives inside the same node group, so rig animation is unaffected.
 */
function mergePrimitives(root: THREE.Object3D, parser: GLTFParser) {
  const groups = new Map<string, THREE.Mesh[]>();
  root.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh || Array.isArray(mesh.material) || !foldable(mesh.material) || !mesh.parent) return;
    const assoc = parser.associations.get(mesh) as { meshes?: number } | undefined;
    if (assoc?.meshes === undefined) return;
    // GLTFLoader puts the primitives of one multi-primitive mesh at identity under the node's group
    if (!mesh.position.equals(ZERO) || mesh.quaternion.w !== 1 || !mesh.scale.equals(ONE)) return;
    const sk = mesh as THREE.SkinnedMesh;
    const g = mesh.geometry;
    const layout = Object.keys(g.attributes).filter((a) => a !== 'color').sort().join(',') + (g.index ? ':i' : ':n') +
      (Object.keys(g.morphAttributes).length ? ':morph' : '');
    const key = [mesh.parent.uuid, assoc.meshes, sk.isSkinnedMesh ? sk.skeleton.uuid : '-', mesh.material.side, layout].join('|');
    let list = groups.get(key);
    if (!list) groups.set(key, (list = []));
    list.push(mesh);
  });
  for (const list of groups.values()) {
    if (list.length < 2 || list.some((m) => Object.keys(m.geometry.morphAttributes).length)) continue;
    const geos = list.map((mesh) => {
      const mat = mesh.material as THREE.MeshStandardMaterial;
      const g = mesh.geometry.clone();
      const n = g.attributes.position.count;
      const src = g.attributes.color as THREE.BufferAttribute | undefined;
      const col = new Float32Array(n * 3);
      const pbr = new Float32Array(n * 2);
      for (let i = 0; i < n; i++) {
        col[i * 3] = (src ? src.getX(i) : 1) * mat.color.r;
        col[i * 3 + 1] = (src ? src.getY(i) : 1) * mat.color.g;
        col[i * 3 + 2] = (src ? src.getZ(i) : 1) * mat.color.b;
        pbr[i * 2] = mat.roughness;
        pbr[i * 2 + 1] = mat.metalness;
      }
      g.setAttribute('color', new THREE.BufferAttribute(col, 3));
      g.setAttribute('pbr', new THREE.BufferAttribute(pbr, 2));
      return g;
    });
    const merged = mergeGeometries(geos);
    if (!merged) continue;
    const first = list[0];
    const fm = first.material as THREE.MeshStandardMaterial;
    const mat = new THREE.MeshStandardMaterial({ name: 'merged', vertexColors: true, roughness: 1, metalness: 1, side: fm.side, flatShading: fm.flatShading, envMapIntensity: fm.envMapIntensity });
    mat.userData.vertexPBR = true;
    patchMaterial(mat);
    let out: THREE.Mesh;
    if ((first as THREE.SkinnedMesh).isSkinnedMesh) {
      const sk = first as THREE.SkinnedMesh;
      const m = new THREE.SkinnedMesh(merged, mat);
      m.bind(sk.skeleton, sk.bindMatrix);
      m.bindMode = sk.bindMode;
      out = m;
    } else {
      out = new THREE.Mesh(merged, mat);
    }
    out.name = first.name;
    out.castShadow = list.some((m) => m.castShadow);
    out.receiveShadow = true;
    const parent = first.parent!;
    parent.add(out);
    for (const m of list) { parent.remove(m); m.geometry.dispose(); }
  }
}
const ZERO = new THREE.Vector3();
const ONE = new THREE.Vector3(1, 1, 1);

export async function loadModels(onProgress: (done: number, total: number) => void) {
  const loader = new GLTFLoader();
  let done = 0;
  await Promise.all(
    MODEL_NAMES.map(async (name) => {
      try {
        const gltf = await loader.loadAsync(`models/${name}.glb`);
        prepare(gltf.scene);
        mergePrimitives(gltf.scene, gltf.parser);
        patchObject(gltf.scene);
        loaded.set(name, gltf.scene);
      } catch (e) {
        console.warn(`[assets] ${name}.glb missing — using placeholder`, e);
        missing.add(name);
      }
      onProgress(++done, MODEL_NAMES.length);
    }),
  );
}

export function missingModels() {
  return [...missing];
}

/** Deep clone with per-instance materials (so hit flashes don't leak between instances). */
function cloneWithMaterials(src: THREE.Object3D) {
  // SkeletonUtils.clone re-binds skinned meshes to the cloned bones (plain clone() would not)
  const c = skeletonClone(src);
  c.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh) return;
    // procedural poses move limbs outside the bind-pose bounds -> avoid false culling
    if ((mesh as THREE.SkinnedMesh).isSkinnedMesh) {
      // Procedural poses move limbs outside the bind-pose bounds. Instead of disabling culling
      // (every enemy was drawn — and shadow-cast — even behind the camera), give each skinned part
      // a padded bind-pose sphere once: still culls off-screen units, never clips a pose.
      const geo = mesh.geometry;
      if (!geo.boundingSphere) geo.computeBoundingSphere();
      const sphere = geo.boundingSphere!.clone();
      sphere.radius = sphere.radius * 1.5 + 0.6;
      (mesh as THREE.SkinnedMesh).boundingSphere = sphere;
    }
    mesh.material = Array.isArray(mesh.material) ? mesh.material.map((m) => m.clone()) : mesh.material.clone();
    // clone() drops onBeforeCompile (fake lights + per-vertex PBR of merged meshes)
    for (const m of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) patchMaterial(m);
  });
  return c;
}

/** Character / enemy / arena model instance. */
export function getModel(name: ModelName): THREE.Object3D {
  const src = loaded.get(name);
  if (src) return cloneWithMaterials(src);
  return placeholderModel(name);
}

/** Single prop from props.glb by top-level node name. */
export function getProp(name: string): THREE.Object3D {
  const props = loaded.get('props');
  const src = props?.getObjectByName(name);
  if (src) {
    const c = src.clone(true);
    c.position.set(0, 0, 0);
    c.rotation.set(0, 0, 0);
    return c;
  }
  return placeholderProp(name);
}

// ---------------------------------------------------------------------------
// Placeholders (keep the game runnable when a GLB is missing)
// ---------------------------------------------------------------------------
const pm = (color: number, emissive = 0) =>
  new THREE.MeshStandardMaterial({ color, emissive: emissive ? color : 0, emissiveIntensity: emissive, flatShading: true, roughness: 0.6 });

function box(w: number, h: number, d: number, color: number, y = 0, emissive = 0) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), pm(color, emissive));
  m.position.y = y;
  m.castShadow = true;
  return m;
}

function node(name: string, parent: THREE.Object3D, x: number, y: number, z: number) {
  const g = new THREE.Group();
  g.name = name;
  g.position.set(x, y, z);
  parent.add(g);
  return g;
}

function humanoid(h: number, body: number, accent: number) {
  const s = h / 1.75;
  const root = new THREE.Group();
  root.name = 'root';
  const hips = node('hips', root, 0, 0.92 * s, 0);
  const torso = node('torso', hips, 0, 0.05 * s, 0);
  torso.add(box(0.5 * s, 0.55 * s, 0.3 * s, body, 0.28 * s));
  const head = node('head', torso, 0, 0.58 * s, 0);
  head.add(box(0.34 * s, 0.34 * s, 0.34 * s, 0xf1c9a5, 0.17 * s));
  const armL = node('arm_L', torso, 0.33 * s, 0.5 * s, 0);
  armL.add(box(0.14 * s, 0.6 * s, 0.14 * s, body, -0.3 * s));
  const armR = node('arm_R', torso, -0.33 * s, 0.5 * s, 0);
  armR.add(box(0.14 * s, 0.6 * s, 0.14 * s, body, -0.3 * s));
  const weapon = node('weapon', armR, 0, -0.6 * s, 0);
  const blade = box(0.06, 0.06, 1.1 * s, accent, 0, 0.6);
  blade.position.z = 0.55 * s;
  weapon.add(blade);
  const legL = node('leg_L', hips, 0.13 * s, 0, 0);
  legL.add(box(0.17 * s, 0.9 * s, 0.18 * s, 0x3b2416, -0.45 * s));
  const legR = node('leg_R', hips, -0.13 * s, 0, 0);
  legR.add(box(0.17 * s, 0.9 * s, 0.18 * s, 0x3b2416, -0.45 * s));
  return root;
}

function blob(color: number, size: number, floatY = 0) {
  const root = new THREE.Group();
  root.name = 'root';
  const body = node(floatY ? 'lantern' : 'body', root, 0, floatY || size * 0.5, 0);
  const m = new THREE.Mesh(new THREE.IcosahedronGeometry(size * 0.5, 1), pm(color, floatY ? 0.8 : 0));
  m.castShadow = true;
  body.add(m);
  const head = node('head', body, 0, size * 0.1, size * 0.45);
  head.add(box(size * 0.35, size * 0.3, size * 0.3, color));
  return root;
}

function placeholderModel(name: ModelName): THREE.Object3D {
  switch (name) {
    case 'kai': return humanoid(1.75, 0x26324f, 0x9aa2ad);
    case 'lyra': return humanoid(1.6, 0x5b3a7a, 0xb77bff);
    case 'knight': return humanoid(2.1, 0x8a6a2c, 0x3a3c42);
    case 'golem': return humanoid(3.2, 0x3a3c42, 0xffb347);
    case 'cograt': return blob(0xb8673a, 0.6);
    case 'slime': return blob(0x3fd1b8, 0.7);
    case 'beetle': return blob(0xc9a14a, 0.9);
    case 'wisp': return blob(0xffb347, 0.6, 1.3);
    case 'arena': {
      const g = new THREE.Group();
      const m = new THREE.Mesh(new THREE.CylinderGeometry(13, 12, 2, 32), pm(0x8d877c));
      m.position.y = -1;
      m.receiveShadow = true;
      g.add(m);
      return g;
    }
    default: return new THREE.Group();
  }
}

function placeholderProp(name: string): THREE.Object3D {
  const g = new THREE.Group();
  g.name = name;
  const add = (m: THREE.Mesh) => { m.castShadow = true; m.receiveShadow = true; g.add(m); return m; };
  if (name.includes('tree')) {
    add(new THREE.Mesh(new THREE.CylinderGeometry(0.25, 0.35, 2.5, 6), pm(0x7a5230))).position.y = 1.25;
    add(new THREE.Mesh(new THREE.IcosahedronGeometry(1.8, 0), pm(name.endsWith('_b') ? 0xc4702a : 0x3f8a7e))).position.y = 3.6;
  } else if (name.includes('rock')) {
    add(new THREE.Mesh(new THREE.DodecahedronGeometry(1.1, 0), pm(0x8d877c))).position.y = 0.7;
  } else if (name.includes('crystal')) {
    add(new THREE.Mesh(new THREE.OctahedronGeometry(0.7, 0), pm(0x5ff3ff, 2))).position.y = 1;
  } else if (name.includes('clocktower')) {
    add(new THREE.Mesh(new THREE.BoxGeometry(5, 18, 5), pm(0x8d877c))).position.y = 9;
  } else if (name.includes('lamp')) {
    add(new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.1, 3.4, 6), pm(0x3a3c42))).position.y = 1.7;
    add(new THREE.Mesh(new THREE.SphereGeometry(0.22, 8, 6), pm(0x5ff3ff, 3))).position.y = 3.4;
  } else if (name === 'prop_rest') {
    add(new THREE.Mesh(new THREE.CylinderGeometry(0.8, 1, 1, 8), pm(0xc9a14a))).position.y = 0.5;
    const c = new THREE.Group();
    c.name = 'crystal';
    c.position.y = 1.8;
    const cm = new THREE.Mesh(new THREE.OctahedronGeometry(0.4, 0), pm(0x5ff3ff, 3));
    c.add(cm);
    g.add(c);
  } else if (name === 'prop_chest') {
    add(new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.5, 0.6), pm(0x7a5230))).position.y = 0.25;
    const lid = new THREE.Group();
    lid.name = 'lid';
    lid.position.set(0, 0.5, -0.3);
    const lm = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.2, 0.6), pm(0xc9a14a));
    lm.position.set(0, 0.1, 0.3);
    lid.add(lm);
    g.add(lid);
  } else {
    add(new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), pm(0x8a6a2c))).position.y = 0.5;
  }
  return g;
}
