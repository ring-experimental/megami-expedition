import type { Circle, ZoneDef } from './types';

/** 멈춘 시계탑 내부 — two round rooms joined by a lift: the engine room (south) and the belfry (north). */
const pipeCols: Circle[] = [{ x: -2.4, z: 0, r: 0.7 }, { x: 0, z: 0, r: 0.7 }, { x: 2.4, z: 0, r: 0.7 }];

export const TOWER: ZoneDef = {
  id: 'clocktower_interior',
  name: '멈춘 시계탑',
  sub: '기관실 · 종루',
  radius: 70,
  sky: { top: '#1a1612', horizon: '#c89a52', bottom: '#1a1612', sun: '#ffd08a', sunDir: [0.2, 0.8, 0.3], fog: '#3a2e22', fogNear: 18, fogFar: 90, hemiSky: '#c89a62', hemiGround: '#2a2018', hemi: 0.75, sunColor: '#ffd8a0', sunInt: 1.6, mountain: '#2a2018', cloud: '#5a4a38', motes: '#ffd9a8' },
  skyVariants: [{ flag: 'ch1_boss_done', sky: { top: '#9ec4e8', horizon: '#d8b46a', fog: '#5a4a38', sunInt: 2.4 } }],
  terrain: {
    roads: [],
    plazas: [{ x: 0, z: 26, r: 22, rings: [8, 16] }, { x: 0, z: -36, r: 18, rings: [7, 13] }],
    hills: 0.05,
    edge: [70, 90],
    seed: 41,
    palette: { grassA: '#4a4038', grassB: '#4a4038', grassC: '#4a4038', dirt: '#6b5420', dirtB: '#5a4618', stoneA: '#6b5420', stoneB: '#4a4038', cliff: '#4a4038', cliffB: '#3a322c', trim: '#c9a14a', grassTuft: '#4a4038' },
    grass: 0,
    rooms: [{ x: 0, z: 26, r: 24 }, { x: 0, z: -36, r: 20 }],
  },
  start: { x: 0, z: 42, rot: Math.PI },
  props: [
    { name: 'prop_drive_shaft', x: 0, z: 22, rot: 0, colliders: [{ x: 0, z: 0, r: 1.6 }] },
    { name: 'prop_gear_monument', x: -16, z: 40, rot: 0.4, colliders: [{ x: -2.3, z: 0, r: 1.65 }, { x: -0.8, z: 0, r: 1.6 }, { x: 0.8, z: 0, r: 1.6 }, { x: 2.3, z: 0, r: 1.65 }] },
    { name: 'prop_gear_monument', x: 16, z: 8, rot: -0.8, colliders: [{ x: -2.3, z: 0, r: 1.65 }, { x: -0.8, z: 0, r: 1.6 }, { x: 0.8, z: 0, r: 1.6 }, { x: 2.3, z: 0, r: 1.65 }] },
    { name: 'prop_pipe', x: -21, z: 26, rot: Math.PI / 2, colliders: pipeCols },
    { name: 'prop_pipe', x: 21, z: 30, rot: Math.PI / 2, colliders: pipeCols },
    { name: 'prop_lamp', x: -10, z: 44, colliders: [{ x: 0, z: 0, r: 0.35 }], light: '#ffcf7a' },
    { name: 'prop_lamp', x: 10, z: 44, colliders: [{ x: 0, z: 0, r: 0.35 }], light: '#ffcf7a' },
    { name: 'prop_lamp', x: -12, z: -24, colliders: [{ x: 0, z: 0, r: 0.35 }], light: '#ffcf7a' },
    { name: 'prop_lamp', x: 12, z: -24, colliders: [{ x: 0, z: 0, r: 0.35 }], light: '#ffcf7a' },
    { name: 'prop_crate', x: 18, z: 18, rot: 0.4, colliders: [{ x: 0, z: 0, r: 0.75 }] },
    { name: 'prop_rest', x: 14, z: 36, colliders: [{ x: 0, z: 0, r: 1.1 }] },
  ],
  chests: [
    { id: 't_c1', x: -18, z: 34, rot: 1.2, items: { hi_tonic: 2 }, money: 0 },
    { id: 't_c2', x: 18, z: 20.6, rot: -1.6, items: {}, money: 80, parts: { p_renner_cog: 1 } },
    { id: 't_c3', x: 12, z: -48, rot: -0.6, items: { heart: 1 }, money: 0, crystals: { aether: 3 }, afterFlag: 'ch1_boss_done' },
  ],
  spawns: [
    { id: 't_s1', x: -12, z: 30, formation: ['knight', 'prism_moth'], wander: 3 },
    { id: 't_s2', x: 12, z: 12, formation: ['beetle', 'wisp'], wander: 3 },
  ],
  scatter: [],
  gates: [
    { id: 'gate_tower_exit', x: 0, z: 47.5, r: 2.2, to: 'plains', toGate: 'gate_tower_door', label: '에테르 평원' },
  ],
  npcs: [
    { id: 'carillon', name: '그란 카리용', x: 0, z: -42, rot: 0, model: 'grand_carillon', color: '#b08d3c', silent: true },
    { id: 'bail', name: '바일', x: 6, z: -22, rot: -2.4, model: 'npc_bail', color: '#9aa0a8', untilFlag: 'ch1_boss_done', silent: true },
  ],
  spots: [
    { id: 'dowin_note', x: -19, z: 16, r: 3, label: '벽에 긁힌 글씨' },
    { id: 'lift_up', x: 0, z: 5, r: 2.4, label: '승강 리프트 <span class="dim">(종루로)</span>' },
    { id: 'lift_down', x: 0, z: -18, r: 2.4, label: '승강 리프트 <span class="dim">(기관실로)</span>' },
  ],
  landmarks: [{ x: 0, z: 22 }, { x: 0, z: -42 }],
};
