import type { ChestDef, Circle, PropPlacement, SpawnDef, ZoneDef } from './types';
import { State } from '../../game/state';

const F = (id: string) => !!State.current.flag(id);

/** 에테르 평원 — the opening field around the stopped clock tower. */
const REST = { x: 5, z: 57 };

const pipeCols: Circle[] = [{ x: -2.4, z: 0, r: 0.7 }, { x: 0, z: 0, r: 0.7 }, { x: 2.4, z: 0, r: 0.7 }];
const archCols: Circle[] = [{ x: -2.8, z: 0, r: 0.6 }, { x: 2.8, z: 0, r: 0.6 }];

const PROPS: PropPlacement[] = [
  { name: 'prop_rest', x: REST.x, z: REST.z, colliders: [{ x: 0, z: 0, r: 1.1 }] },
  // signposts: rot aims the 시계탑 board (local +X) at the clock tower; 마석 points east (local +Z), 증기 west
  { name: 'prop_signpost', x: -3.2, z: 50, rot: 1.54, colliders: [{ x: 0, z: 0, r: 0.45 }] },
  // lamp-lit road north
  // m01: Kai lights these six (lamp1..lamp6) on his dawn round
  ...[45, 34, 23, 12, 1, -10].map((z, i) => ({ name: 'prop_lamp', x: i % 2 ? -4.2 : 4.2, z, colliders: [{ x: 0, z: 0, r: 0.35 }], lightFlag: `lamp${i + 1}` })),
  // second rest point in front of the tower (m09)
  { name: 'prop_rest', x: -6, z: -28, colliders: [{ x: 0, z: 0, r: 1.1 }], afterFlag: 'ch1_tower_open' },
  // west road barrier until the grove crystal is found (m05)
  { name: 'prop_fence', x: -70, z: -3, rot: Math.PI / 2, colliders: [{ x: -0.8, z: 0, r: 0.3 }, { x: 0, z: 0, r: 0.3 }, { x: 0.8, z: 0, r: 0.3 }], untilFlag: 'ch1_crystal_got' },
  { name: 'prop_fence', x: -70, z: 3, rot: Math.PI / 2, colliders: [{ x: -0.8, z: 0, r: 0.3 }, { x: 0, z: 0, r: 0.3 }, { x: 0.8, z: 0, r: 0.3 }], untilFlag: 'ch1_crystal_got' },
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


const CHESTS: ChestDef[] = [
  { id: 'c5', x: 60, z: -6, rot: -1.8, items: {}, money: 0, parts: { p_lamp_wick: 1 }, crystals: { volt: 2 } },
  { id: 'c6', x: -6, z: -62, rot: 0.4, items: { tonic: 1 }, money: 60, crystals: { frost: 2 } },
  { id: 'c1', x: -48, z: -22, rot: 0.8, items: { hi_tonic: 2 }, money: 50 },
  { id: 'c2', x: 54, z: 26, rot: -2.2, items: { capsule: 2, tonic: 1 }, money: 30 },
  { id: 'c3', x: 16, z: -44, rot: 0.2, items: { heart: 1 }, money: 80 },
  { id: 'c4', x: -14, z: 44, rot: 1.6, items: { tonic: 2 }, money: 20 },
];


const SPAWNS: SpawnDef[] = [
  { id: 's_rat1', x: -10, z: 32, formation: ['cograt', 'cograt'], wander: 6 },
  // sq01: while the mail bag is missing, the yard's rats are led by a 'boss' carrying it
  { id: 's_rat2', x: -34, z: 20, formation: ['cograt', 'cograt', 'cograt'], wander: 6, when: () => !(F('sq01_accepted') && !F('sq01_bag_found')) },
  { id: 's_rat2_boss', x: -34, z: 20, formation: ['cograt', 'cograt', 'cograt'], wander: 4, when: () => F('sq01_accepted') && !F('sq01_bag_found') },
  // m03: the rat hiding behind the lamp takes s_rat3's place until Tick joins
  { id: 's_rat3', x: 13, z: 40, formation: ['cograt'], wander: 5, when: () => !(F('ch1_lyra_joined') && !F('ch1_tick_recruited')) },
  { id: 'ev_tick', x: 13, z: 41.5, formation: ['cograt'], wander: 0.5, afterFlag: 'ch1_lyra_joined', untilFlag: 'ch1_tick_recruited', passive: true },
  { id: 'sp_moth1', x: 40, z: 12, formation: ['prism_moth', 'prism_moth'], wander: 6, afterFlag: 'ch1_hub_arrived' },
  { id: 'sp_moth2', x: 30, z: -14, formation: ['prism_moth', 'wisp'], wander: 6, afterFlag: 'ch1_hub_arrived' },
  { id: 's_slime1', x: 18, z: 20, formation: ['slime', 'cograt'], wander: 6 },
  { id: 's_slime2', x: -28, z: -4, formation: ['slime', 'slime'], wander: 5 },
  { id: 's_wisp1', x: 38, z: 2, formation: ['wisp'], wander: 6 },
  { id: 's_wisp2', x: 48, z: -20, formation: ['wisp', 'slime'], wander: 6 },
  { id: 's_wisp3', x: 26, z: -30, formation: ['wisp', 'wisp'], wander: 5 },
  // sq03: 광채 3세 waits to talk once Tick has joined
  { id: 's_beetle1', x: -44, z: -16, formation: ['beetle'], wander: 5, untilFlag: 'sq03_done', passive: () => F('ch1_tick_recruited') },
  { id: 's_beetle2', x: -20, z: -30, formation: ['beetle', 'cograt'], wander: 5 },
  // sq04: the gate knight talks once the crystal is found
  { id: 's_knight1', x: -12, z: -40, formation: ['knight'], wander: 4, untilFlag: 'sq04_done', passive: () => F('ch1_crystal_got') },
  { id: 's_knight2', x: 14, z: -32, formation: ['knight', 'wisp'], wander: 4, when: () => !(F('ch1_night_talk') && !F('ch1_holdup_done')) },
  { id: 's_golem', x: 40, z: -44, formation: ['golem'], wander: 4 },
];

export const PLAINS: ZoneDef = {
  id: 'plains',
  name: '에테르 평원',
  sub: '멈춘 시계탑',
  radius: 76,
  // dawn until the bell sings (ch1_boss_done), then a clear noon
  sky: { top: '#4f78b0', horizon: '#f0c48a', bottom: '#c9a57a', sun: '#ffd9a8', sunDir: [-0.6, 0.22, 0.6], fog: '#d8bc9a', fogNear: 60, fogFar: 230, hemiSky: '#ffdcb8', hemiGround: '#5a6a45', hemi: 1.05, sunColor: '#ffd7a8', sunInt: 2.4, mountain: '#8f8aa6', cloud: '#ffe2c8', motes: '#9ff6ff' },
  skyVariants: [{ flag: 'ch1_boss_done', sky: { top: '#5d97d8', horizon: '#e8e2c4', fog: '#cfd6d0', sun: '#fff4dc', sunDir: [-0.3, 0.7, 0.4], sunColor: '#fff2dc', sunInt: 2.8, cloud: '#ffffff' } }],
  terrain: {
    roads: [
      [[0, 70], [0, 40], [0, 10], [0, -30]],
      [[0, 22], [-14, 16], [-30, 8], [-42, -6], [-46, -20]],
      [[0, 2], [16, -2], [32, -8], [48, -18]],
      [[0, -30], [18, -38], [36, -44]],
      [[0, 40], [-14, 44]],
    ],
    plazas: [{ x: 0, z: -40, r: 15, rings: [9, 13.2] }],
    hills: 1,
    edge: [68, 92],
    seed: 7,
    palette: { grassA: '#6d9a45', grassB: '#8fae4e', grassC: '#5a8a4a', dirt: '#a67f55', dirtB: '#8e6a45', stoneA: '#9b958a', stoneB: '#857f74', cliff: '#8a7660', cliffB: '#6e5d4c', trim: '#b08a4a', grassTuft: '#7fb04a' },
    grass: 1,
  },
  start: { x: 0, z: 60, rot: Math.PI },
  props: PROPS,
  chests: CHESTS,
  spawns: SPAWNS,
  scatter: [
    { name: 'prop_tree', count: 46, rMin: 50, rMax: 92, colR: 0.6, sMin: 0.9, sMax: 1.35 },
    { name: 'prop_tree_b', count: 30, rMin: 46, rMax: 92, colR: 0.6, sMin: 0.85, sMax: 1.3 },
    { name: 'prop_tree', count: 10, rMin: 15, rMax: 48, colR: 0.6, sMin: 0.8, sMax: 1.1 },
    { name: 'prop_tree_b', count: 8, rMin: 15, rMax: 48, colR: 0.6, sMin: 0.8, sMax: 1.1 },
    { name: 'prop_rock_a', count: 22, rMin: 20, rMax: 90, colR: 1.25, sMin: 0.7, sMax: 1.6 },
    { name: 'prop_rock_b', count: 22, rMin: 20, rMax: 90, colR: 0.9, sMin: 0.7, sMax: 1.6 },
    { name: 'prop_bush', count: 70, rMin: 10, rMax: 74, colR: 0, sMin: 0.7, sMax: 1.4 },
  ],
  gates: [
    { id: 'gate_plain_south', x: 0, z: 73, r: 3, to: 'pause_station', toGate: 'gate_station_north', label: '쉼표 역', needFlag: 'ch1_tick_recruited', lockedText: '마르타(무전): 등부터 다 켜고 와라. 해 뜨기 전에.' },
    { id: 'gate_plain_west', x: -73, z: 0, r: 3, to: 'ashstack_works', toGate: 'gate_works_east', label: '잿빛 굴뚝', needFlag: 'ch1_crystal_got', lockedText: '집배대 차단봉: "굴뚝 방면 통행 금지 — 결정부터 가져오고 가라. 마르타"' },
    { id: 'gate_tower_door', x: 0, z: -46.6, r: 1.4, to: 'clocktower_interior', toGate: 'gate_tower_exit', label: '시계탑', afterFlag: 'ch1_tower_open' },
  ],
  npcs: [],
  spots: [
    ...[45, 34, 23, 12, 1, -10].map((z, i) => ({ id: `lamp${i + 1}`, x: i % 2 ? -4.2 : 4.2, z, r: 2.4, label: '가스등 켜기', untilFlag: `lamp${i + 1}` })),
    { id: 'crys_a', x: 46, z: 6, r: 3, label: '노래하는 결정을 두드린다 <span class="dim">(큰 결정)</span>', afterFlag: 'ch1_hub_arrived', untilFlag: 'ch1_crystal_got' },
    { id: 'crys_b', x: 57, z: 19, r: 3, label: '노래하는 결정을 두드린다 <span class="dim">(중간 결정)</span>', afterFlag: 'ch1_hub_arrived', untilFlag: 'ch1_crystal_got' },
    { id: 'crys_c', x: 34, z: -4, r: 3, label: '노래하는 결정을 두드린다 <span class="dim">(작은 결정)</span>', afterFlag: 'ch1_hub_arrived', untilFlag: 'ch1_crystal_got' },
    { id: 'tower_door', x: 0, z: -45.6, r: 3.2, label: '탑 정문 조사', afterFlag: 'ch1_holdup_done', untilFlag: 'ch1_tower_open' },
  ],
  airship: true,
  landmarks: [{ x: 0, z: -52 }],
};
