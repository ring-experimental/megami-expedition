import type { Circle, PropPlacement, ZoneDef } from './types';
import { State } from '../../game/state';

/** 쉼표 역 — the hub: a stopped locomotive 'Kanna' and the village that grew around it. */
const F = (id: string) => !!State.current.flag(id);
const night = () => F('night');

/** house footprint ≈ 7 × 6 m (front +Z): four circles */
const HOUSE: Circle[] = [{ x: -2, z: -1.4, r: 2.3 }, { x: 2, z: -1.4, r: 2.3 }, { x: -2, z: 1.2, r: 2.1 }, { x: 2, z: 1.2, r: 2.1 }];
const LOCO: Circle[] = [-5.6, -2.8, 0, 2.8, 5.6].map((x) => ({ x, z: 0, r: 1.6 }));
const lamp = (x: number, z: number, lightFlag?: string): PropPlacement => ({ name: 'prop_lamp', x, z, colliders: [{ x: 0, z: 0, r: 0.35 }], light: '#ffcf7a', lightFlag });
const fence = (x: number, z: number, rot = 0): PropPlacement => ({ name: 'prop_fence', x, z, rot, colliders: [{ x: -0.8, z: 0, r: 0.3 }, { x: 0, z: 0, r: 0.3 }, { x: 0.8, z: 0, r: 0.3 }] });

export const STATION: ZoneDef = {
  id: 'pause_station',
  name: '쉼표 역',
  sub: '멈춘 기관차 칸나',
  radius: 70,
  sky: { top: '#6a88b0', horizon: '#f2b872', bottom: '#b08a62', sun: '#ffd08a', sunDir: [0.6, 0.18, 0.5], fog: '#d9a978', fogNear: 50, fogFar: 200, hemiSky: '#ffd2a0', hemiGround: '#5a4a35', hemi: 1.05, sunColor: '#ffc98a', sunInt: 2.3, mountain: '#8a7a96', cloud: '#ffd9b0', motes: '#ffd9a8' },
  skyVariants: [{ flag: 'night', sky: { top: '#141a2e', horizon: '#3c3550', bottom: '#1a1622', sun: '#c8d4ff', sunDir: [-0.4, 0.3, -0.6], fog: '#2a2633', fogNear: 30, fogFar: 150, hemiSky: '#5a6a9a', hemiGround: '#1a1622', hemi: 0.55, sunColor: '#9aa8ff', sunInt: 0.7, mountain: '#2a2a3e', cloud: '#4a4a66', motes: '#ffcf7a' } }],
  terrain: {
    roads: [[[0, -70], [0, -40], [0, -14]], [[0, 10], [0, 40], [0, 56]], [[-30, 0], [-12, 0]], [[12, 0], [30, 0]]],
    plazas: [{ x: 0, z: -6, r: 18, rings: [12] }],
    hills: 0.35,
    edge: [60, 84],
    seed: 21,
    palette: { grassA: '#7a8650', grassB: '#8a9658', grassC: '#6a7646', dirt: '#7d6a55', dirtB: '#6d5a45', stoneA: '#8e7a62', stoneB: '#7d6a55', cliff: '#7a6450', cliffB: '#5e4c3c', trim: '#c9a14a', grassTuft: '#7f9a4a' },
    grass: 0.45,
    paved: 26,
  },
  start: { x: 0, z: -60, rot: 0 },
  props: [
    { name: 'prop_rest', x: 8, z: 6, colliders: [{ x: 0, z: 0, r: 1.1 }] },
    { name: 'prop_locomotive', x: 0, z: -6, rot: 0, colliders: LOCO, steam: true, steamY: 5 },
    { name: 'prop_house', x: -20, z: -20, rot: 0.3, colliders: HOUSE },  // 집배대 지부
    { name: 'prop_nail_board', x: -13, z: -16, rot: 0.3, colliders: [{ x: 0, z: 0, r: 0.9 }] },
    { name: 'prop_house', x: 20, z: -20, rot: -0.3, colliders: HOUSE },  // 상점 「톱니와 저울」
    { name: 'prop_house', x: -24, z: 10, rot: 1.2, colliders: HOUSE },   // 공방 「오르간 둥지」
    { name: 'prop_organ', x: -17, z: 12, rot: 1.2, colliders: [{ x: 0, z: 0, r: 1.2 }] },
    { name: 'prop_house', x: 22, z: 12, rot: -1.2, colliders: HOUSE },   // 여관 「김 서린 주전자」
    { name: 'prop_house', x: 0, z: -30, rot: 0, colliders: HOUSE },      // 역사 (잠김)
    { name: 'prop_house', x: -12, z: 30, rot: 2.6, colliders: HOUSE },   // 포피네 집
    { name: 'prop_house', x: 26, z: -4, rot: -1.57, colliders: HOUSE },  // 급수탑 창고
    { name: 'prop_pipe', x: 30.5, z: 2, rot: 0.1, colliders: [{ x: -2.4, z: 0, r: 0.7 }, { x: 0, z: 0, r: 0.7 }, { x: 2.4, z: 0, r: 0.7 }] },
    lamp(-5, -45), lamp(5, -45), lamp(-5, -38), lamp(5, -38), lamp(-8, 18), lamp(8, 18),
    // sq02: the dark lamps by the cliff
    lamp(-6, 40, 'sq02_lamp1'), lamp(6, 40, 'sq02_lamp2'), lamp(0, 52, 'sq02_lamp3'),
    fence(-10, 61, 0.25), fence(0, 63), fence(10, 61, -0.25), fence(-19, 57, 0.6), fence(19, 57, -0.6),
    { name: 'prop_crate', x: -4, z: -12, rot: 0.3, colliders: [{ x: 0, z: 0, r: 0.75 }] },
    { name: 'prop_crate', x: 4, z: -11.5, rot: 1.1, colliders: [{ x: 0, z: 0, r: 0.75 }] },
    { name: 'prop_barrel', x: 30, z: -8, colliders: [{ x: 0, z: 0, r: 0.5 }] },
    { name: 'prop_barrel', x: 31, z: -9.2, colliders: [{ x: 0, z: 0, r: 0.5 }] },
    { name: 'prop_signpost', x: 3, z: -50, rot: -1.57, colliders: [{ x: 0, z: 0, r: 0.45 }] },
    { name: 'prop_vent', x: -28, z: -6, steam: true },
  ],
  chests: [
    { id: 'hub_c1', x: 5, z: -9.6, rot: Math.PI, items: { tonic: 2 }, money: 100 },
    { id: 'hub_c2', x: -31, z: 18, rot: 1.2, items: { capsule: 1 }, money: 0, crystals: { fire: 1 } },
  ],
  spawns: [],
  scatter: [
    { name: 'prop_tree', count: 14, rMin: 40, rMax: 66, colR: 0.6, sMin: 0.9, sMax: 1.3 },
    { name: 'prop_tree_b', count: 10, rMin: 40, rMax: 66, colR: 0.6, sMin: 0.85, sMax: 1.2 },
    { name: 'prop_bush', count: 26, rMin: 28, rMax: 62, colR: 0, sMin: 0.7, sMax: 1.3 },
    { name: 'prop_rock_b', count: 6, rMin: 45, rMax: 66, colR: 0.9, sMin: 0.7, sMax: 1.3 },
  ],
  gates: [
    { id: 'gate_station_north', x: 0, z: -67, r: 3, to: 'plains', toGate: 'gate_plain_south', label: '에테르 평원' },
  ],
  npcs: [
    { id: 'marta', name: '마르타', x: -15, z: -13, rot: 0.6, model: 'npc_marta', color: '#2f4a3a' },
    { id: 'poppy', name: '포피', x: -5, z: 1, rot: 2.6, model: 'npc_poppy', color: '#c8283a', when: () => !night() },
    { id: 'poppy', name: '포피', x: -12, z: 26, rot: 0.2, model: 'npc_poppy', color: '#c8283a', when: night },
    { id: 'shopkeeper', name: '상점 주인', x: 20, z: -14.5, rot: 3.0, model: 'npc_shopkeeper', color: '#6a4a30' },
    // m08: the 녹청 연대 messenger on Kanna's roof
    { id: 'verdi', name: '베르디', x: 0, z: -6, y: 4.6, rot: Math.PI, model: 'wisp', color: '#5e7a5a', when: night, silent: true },
  ],
  spots: [
    { id: 'nail_board', x: -13, z: -15, r: 2.4, label: '못판 보기 <span class="dim">(집배대 의뢰)</span>', afterFlag: 'ch1_hub_arrived' },
    { id: 'pippe', x: -16.2, z: 12.6, r: 2.8, label: '피페와 이야기하기' },
    { id: 'station_door', x: 0, z: -26.2, r: 2.4, label: '역사 문' },
    ...[[-6, 40], [6, 40], [0, 52]].map(([x, z], i) => ({ id: `sq02_lamp${i + 1}`, x, z, r: 2.4, label: '꺼진 에테르 등', afterFlag: 'sq02_accepted', untilFlag: `sq02_lamp${i + 1}` })),
  ],
  landmarks: [{ x: 0, z: -6 }],
};
