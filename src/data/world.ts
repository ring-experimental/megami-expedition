/** Field layout for the prototype zone "에테르 평원 — 멈춘 시계탑". three.js coords: x east, z south. */

export interface Circle { x: number; z: number; r: number }
export interface PropPlacement { name: string; x: number; z: number; rot?: number; scale?: number; y?: number; colliders?: Circle[]; steam?: boolean }

export const ZONE_NAME = '에테르 평원 · 멈춘 시계탑';
export const PLAYER_START = { x: 0, z: 60, rot: Math.PI };
export const REST_POINT = { x: 5, z: 57 };
export const WORLD_RADIUS = 76;

const pipeCols: Circle[] = [{ x: -2.4, z: 0, r: 0.7 }, { x: 0, z: 0, r: 0.7 }, { x: 2.4, z: 0, r: 0.7 }];
const archCols: Circle[] = [{ x: -2.8, z: 0, r: 0.6 }, { x: 2.8, z: 0, r: 0.6 }];

export const PROPS: PropPlacement[] = [
  { name: 'prop_rest', x: REST_POINT.x, z: REST_POINT.z, colliders: [{ x: 0, z: 0, r: 1.1 }] },
  // signposts: rot aims the 시계탑 board (local +X) at the clock tower; 마석 points east (local +Z), 증기 west
  { name: 'prop_signpost', x: -3.2, z: 50, rot: 1.54, colliders: [{ x: 0, z: 0, r: 0.45 }] },
  // lamp-lit road north
  ...[45, 34, 23, 12, 1, -10].map((z, i) => ({ name: 'prop_lamp', x: i % 2 ? -4.2 : 4.2, z, colliders: [{ x: 0, z: 0, r: 0.35 }] })),
  { name: 'prop_clocktower', x: 0, z: -52, colliders: [{ x: 0, z: 0, r: 4.2 }] },
  { name: 'prop_fence', x: -7, z: -38, rot: 0.2, colliders: [{ x: -0.8, z: 0, r: 0.3 }, { x: 0, z: 0, r: 0.3 }, { x: 0.8, z: 0, r: 0.3 }] },
  { name: 'prop_fence', x: 7, z: -38, rot: -0.2, colliders: [{ x: -0.8, z: 0, r: 0.3 }, { x: 0, z: 0, r: 0.3 }, { x: 0.8, z: 0, r: 0.3 }] },
  { name: 'prop_lamp', x: -9, z: -44, colliders: [{ x: 0, z: 0, r: 0.35 }] },
  { name: 'prop_lamp', x: 9, z: -44, colliders: [{ x: 0, z: 0, r: 0.35 }] },
  // west pipe yard
  { name: 'prop_pipe_arch', x: -26, z: 12, rot: Math.PI / 2, colliders: archCols },
  { name: 'prop_pipe_arch', x: -40, z: -8, rot: 0.3, colliders: archCols },
  { name: 'prop_pipe', x: -46, z: 22, rot: 0.35, colliders: pipeCols },
  { name: 'prop_pipe', x: -24, z: -22, rot: 1.2, colliders: pipeCols },
  { name: 'prop_pipe', x: -52, z: 2, rot: 1.5, colliders: pipeCols },
  { name: 'prop_vent', x: -34, z: 2, steam: true },
  { name: 'prop_vent', x: -19, z: 26, steam: true },
  { name: 'prop_vent', x: -30, z: -30, steam: true },
  { name: 'prop_vent', x: 24, z: 14, steam: true },
  { name: 'prop_crate', x: -40, z: 32, rot: 0.2, colliders: [{ x: 0, z: 0, r: 0.75 }] },
  { name: 'prop_crate', x: -41.6, z: 33.4, rot: 0.9, colliders: [{ x: 0, z: 0, r: 0.75 }] },
  { name: 'prop_crate', x: -40.8, z: 32.7, y: 1, rot: 0.5 },
  { name: 'prop_barrel', x: -38, z: 30, colliders: [{ x: 0, z: 0, r: 0.5 }] },
  { name: 'prop_barrel', x: -37, z: 31.2, colliders: [{ x: 0, z: 0, r: 0.5 }] },
  { name: 'prop_barrel', x: -16, z: -16, colliders: [{ x: 0, z: 0, r: 0.5 }] },
  { name: 'prop_crate', x: -15, z: -14.5, rot: 0.4, colliders: [{ x: 0, z: 0, r: 0.75 }] },
  // east crystal grove
  { name: 'prop_crystal', x: 34, z: -4, colliders: [{ x: 0, z: 0, r: 1.1 }] },
  { name: 'prop_crystal', x: 46, z: 6, rot: 1, scale: 1.3, colliders: [{ x: 0, z: 0, r: 1.4 }] },
  { name: 'prop_crystal', x: 52, z: -14, rot: 2, colliders: [{ x: 0, z: 0, r: 1.1 }] },
  { name: 'prop_crystal', x: 29, z: -23, rot: 0.5, scale: 0.8, colliders: [{ x: 0, z: 0, r: 0.9 }] },
  { name: 'prop_crystal', x: 57, z: 19, rot: 3, scale: 1.1, colliders: [{ x: 0, z: 0, r: 1.2 }] },
  { name: 'prop_crystal', x: 20, z: -8, rot: 4, scale: 0.7, colliders: [{ x: 0, z: 0, r: 0.8 }] },
  // golem's lair
  // plinth ≈ 6.1 × 3.0 m: four circles reach its corners
  { name: 'prop_gear_monument', x: 44, z: -50, rot: -0.6, colliders: [{ x: -2.3, z: 0, r: 1.65 }, { x: -0.8, z: 0, r: 1.6 }, { x: 0.8, z: 0, r: 1.6 }, { x: 2.3, z: 0, r: 1.65 }] },
  { name: 'prop_pipe', x: 34, z: -56, rot: -0.2, colliders: pipeCols },
  { name: 'prop_vent', x: 38, z: -42, steam: true },
  // misc
  { name: 'prop_signpost', x: 6, z: -22, rot: 1.77, colliders: [{ x: 0, z: 0, r: 0.45 }] },
  { name: 'prop_barrel', x: 7, z: -20, colliders: [{ x: 0, z: 0, r: 0.5 }] },
];

export interface ChestDef { id: string; x: number; z: number; rot: number; items: Record<string, number>; money: number }
export const CHESTS: ChestDef[] = [
  { id: 'c1', x: -48, z: -22, rot: 0.8, items: { hi_tonic: 2 }, money: 50 },
  { id: 'c2', x: 54, z: 26, rot: -2.2, items: { capsule: 2, tonic: 1 }, money: 30 },
  { id: 'c3', x: 16, z: -44, rot: 0.2, items: { heart: 1 }, money: 80 },
  { id: 'c4', x: -14, z: 44, rot: 1.6, items: { tonic: 2 }, money: 20 },
];

export interface SpawnDef { id: string; x: number; z: number; formation: string[]; wander: number }
export const SPAWNS: SpawnDef[] = [
  { id: 's_rat1', x: -10, z: 32, formation: ['cograt', 'cograt'], wander: 6 },
  { id: 's_rat2', x: -34, z: 20, formation: ['cograt', 'cograt', 'cograt'], wander: 6 },
  { id: 's_rat3', x: 13, z: 40, formation: ['cograt'], wander: 5 },
  { id: 's_slime1', x: 18, z: 20, formation: ['slime', 'cograt'], wander: 6 },
  { id: 's_slime2', x: -28, z: -4, formation: ['slime', 'slime'], wander: 5 },
  { id: 's_wisp1', x: 38, z: 2, formation: ['wisp'], wander: 6 },
  { id: 's_wisp2', x: 48, z: -20, formation: ['wisp', 'slime'], wander: 6 },
  { id: 's_wisp3', x: 26, z: -30, formation: ['wisp', 'wisp'], wander: 5 },
  { id: 's_beetle1', x: -44, z: -16, formation: ['beetle'], wander: 5 },
  { id: 's_beetle2', x: -20, z: -30, formation: ['beetle', 'cograt'], wander: 5 },
  { id: 's_knight1', x: -12, z: -40, formation: ['knight'], wander: 4 },
  { id: 's_knight2', x: 14, z: -32, formation: ['knight', 'wisp'], wander: 4 },
  { id: 's_golem', x: 40, z: -44, formation: ['golem'], wander: 4 },
];
