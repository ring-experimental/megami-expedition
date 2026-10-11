import * as THREE from 'three';

/**
 * Cheap stand-in for THREE.PointLight (lamps, wisps, projectiles, hit flashes).
 *
 * Real point lights cost a full PBR BRDF per light on every pixel, and adding/removing one changes
 * `numPointLights` in three.js' program cache key → every lit material recompiles (measured 2.8 s
 * freezes on ANGLE/D3D11). Fake lights instead live in a FIXED-size uniform array that every lit
 * material samples (diffuse-only falloff, same attenuation curve as PointLight), so lights can
 * appear and disappear freely with zero recompiles. Only one scene renders per frame, so a single
 * global uniform block is uploaded from the active scene's light set right before rendering.
 */
export const MAX_FAKE_LIGHTS = 12;

export class FakeLight {
  position = new THREE.Vector3();
  color = new THREE.Color();
  /** Same unit as PointLight.intensity (candela-ish, physically based falloff). */
  intensity = 0;
  /** Cutoff distance (like PointLight.distance). */
  distance = 8;
  /** Lights with higher priority win when more than MAX_FAKE_LIGHTS are in range. */
  priority = 0;
  constructor(color: THREE.ColorRepresentation = 0xffffff, intensity = 0, distance = 8) {
    this.color.set(color);
    this.intensity = intensity;
    this.distance = distance;
  }
}

/** All fake lights of one scene. */
export class FakeLightSet {
  lights: FakeLight[] = [];
  add(l: FakeLight) {
    this.lights.push(l);
    return l;
  }
  remove(l: FakeLight) {
    const i = this.lights.indexOf(l);
    if (i >= 0) this.lights.splice(i, 1);
  }
}

const posArr = Array.from({ length: MAX_FAKE_LIGHTS }, () => new THREE.Vector4());
const colArr = Array.from({ length: MAX_FAKE_LIGHTS }, () => new THREE.Vector3());
/** Shared by every patched program (onBeforeCompile hands this exact object to each shader). */
const uniforms = {
  uFakeLightPos: { value: posArr }, // xyz = view-space position, w = cutoff distance
  uFakeLightCol: { value: colArr }, // linear color * intensity (0 = slot unused)
};

const _v = new THREE.Vector3();
const _pick: { l: FakeLight; score: number }[] = [];

/** Choose the most relevant lights for `camera` and upload them (call right before rendering). */
export function uploadFakeLights(set: FakeLightSet, camera: THREE.Camera) {
  camera.updateMatrixWorld();
  const cam = camera.position;
  _pick.length = 0;
  for (const l of set.lights) {
    if (l.intensity <= 0) continue;
    // lights whose sphere is far from the camera barely touch the screen
    const d = Math.max(0, l.position.distanceTo(cam) - l.distance);
    _pick.push({ l, score: d - l.priority * 1000 });
  }
  if (_pick.length > MAX_FAKE_LIGHTS) _pick.sort((a, b) => a.score - b.score);
  const view = camera.matrixWorldInverse;
  for (let i = 0; i < MAX_FAKE_LIGHTS; i++) {
    const p = _pick[i];
    if (!p) { colArr[i].set(0, 0, 0); posArr[i].set(0, 0, 0, 1); continue; }
    _v.copy(p.l.position).applyMatrix4(view);
    posArr[i].set(_v.x, _v.y, _v.z, p.l.distance);
    colArr[i].set(p.l.color.r, p.l.color.g, p.l.color.b).multiplyScalar(p.l.intensity);
  }
}

const FRAG_DECL = /* glsl */ `
#define NUM_FAKE_LIGHTS ${MAX_FAKE_LIGHTS}
uniform vec4 uFakeLightPos[ NUM_FAKE_LIGHTS ];
uniform vec3 uFakeLightCol[ NUM_FAKE_LIGHTS ];
`;
const FRAG_LOOP = /* glsl */ `
{
  // diffuse-only point lights with PointLight's attenuation (see fx/fakeLights.ts)
  vec3 fakeDiffuse = max( material.diffuseColor, diffuseColor.rgb * 0.3 );
  for ( int i = 0; i < NUM_FAKE_LIGHTS; i ++ ) {
    vec3 fakeCol = uFakeLightCol[ i ];
    vec4 fakePos = uFakeLightPos[ i ];
    vec3 fakeL = fakePos.xyz - geometryPosition;
    float fakeD = length( fakeL );
    float fakeAtt = getDistanceAttenuation( fakeD, fakePos.w, 2.0 );
    float fakeNdl = saturate( dot( geometryNormal, fakeL / max( fakeD, 1e-4 ) ) );
    reflectedLight.directDiffuse += fakeCol * ( fakeAtt * fakeNdl ) * BRDF_Lambert( fakeDiffuse );
  }
}
`;

function onBeforeCompile(this: THREE.Material, shader: THREE.WebGLProgramParametersWithUniforms) {
  shader.uniforms.uFakeLightPos = uniforms.uFakeLightPos;
  shader.uniforms.uFakeLightCol = uniforms.uFakeLightCol;
  shader.fragmentShader = shader.fragmentShader
    .replace('#include <lights_pars_begin>', '#include <lights_pars_begin>\n' + FRAG_DECL)
    .replace('#include <lights_fragment_end>', FRAG_LOOP + '\n#include <lights_fragment_end>');
  if (this.userData.vertexPBR) {
    // merged multi-material meshes (core/assets.ts mergePrimitives): per-vertex roughness/metalness
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nattribute vec2 pbr;\nvarying vec2 vPBR;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvPBR = pbr;');
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', '#include <common>\nvarying vec2 vPBR;')
      .replace('#include <roughnessmap_fragment>', '#include <roughnessmap_fragment>\nroughnessFactor *= vPBR.x;')
      .replace('#include <metalnessmap_fragment>', '#include <metalnessmap_fragment>\nmetalnessFactor *= vPBR.y;');
  }
}

function cacheKey(this: THREE.Material) {
  return 'fakeLights' + MAX_FAKE_LIGHTS + (this.userData.vertexPBR ? '+pbr' : '');
}

const PATCHABLE = new Set(['MeshStandardMaterial', 'MeshPhysicalMaterial', 'MeshLambertMaterial', 'MeshPhongMaterial', 'MeshToonMaterial']);

/** Make a lit material receive fake lights (idempotent; clones keep working via re-patching). */
export function patchMaterial(m: THREE.Material) {
  if (!PATCHABLE.has(m.type) || m.onBeforeCompile === onBeforeCompile) return;
  m.onBeforeCompile = onBeforeCompile;
  // shared functions → programs are still shared between materials with the same features
  m.customProgramCacheKey = cacheKey;
  m.needsUpdate = true;
}

/** Patch every material under `root` (call after building a scene / spawning models). */
export function patchObject(root: THREE.Object3D) {
  root.traverse((o) => {
    const mat = (o as THREE.Mesh).material;
    if (!mat) return;
    for (const m of Array.isArray(mat) ? mat : [mat]) patchMaterial(m);
  });
}
