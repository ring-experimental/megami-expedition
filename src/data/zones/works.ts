import type { Circle, ZoneDef } from './types';
import { State } from '../../game/state';

/** 잿빛 굴뚝 — the abandoned factory: loading yard (east) → steam passage → chimney ring → garage arena (west). */
const F = (id: string) => !!State.current.flag(id);
const pipeCols: Circle[] = [{ x: -2.4, z: 0, r: 0.7 }, { x: 0, z: 0, r: 0.7 }, { x: 2.4, z: 0, r: 0.7 }];
const archCols: Circle[] = [{ x: -2.8, z: 0, r: 0.6 }, { x: 2.8, z: 0, r: 0.6 }];
const chimney = (x: number, z: number) => ({ name: 'prop_chimney', x, z, colliders: [{ x: 0, z: 0, r: 1.8 }], steam: true, steamY: 18 });
const box = (name: string, x: number, z: number, rot = 0) => ({ name, x, z, rot, colliders: [{ x: 0, z: 0, r: name === 'prop_crate' ? 0.75 : 0.5 }] });

export const WORKS: ZoneDef = {
  id: 'ashstack_works',
  name: '잿빛 굴뚝',
  sub: '폐공장',
  radius: 72,
  sky: { top: '#5b6068', horizon: '#b9a58a', bottom: '#6a625a', sun: '#e8d2b0', sunDir: [0.3, 0.3, -0.7], fog: '#8c8579', fogNear: 25, fogFar: 140, hemiSky: '#c8beb0', hemiGround: '#3d3a36', hemi: 0.9, sunColor: '#e8d8c0', sunInt: 1.8, mountain: '#5e5a62', cloud: '#a8a098', motes: '#e8d0a0' },
  terrain: {
    roads: [[[70, 0], [40, 0], [22, 0]], [[-22, 0], [-50, 0]], [[0, -14], [0, -34]], [[44, 4], [56, 14]]],
    plazas: [{ x: 0, z: 0, r: 20, rings: [14] }, { x: -50, z: 0, r: 16, rings: [11] }, { x: 0, z: -32, r: 9 }],
    hills: 0.35,
    edge: [62, 86],
    seed: 33,
    palette: { grassA: '#55504a', grassB: '#5e5850', grassC: '#4a4642', dirt: '#3d3a36', dirtB: '#34312e', stoneA: '#5a5650', stoneB: '#4a4642', cliff: '#5a3a2e', cliffB: '#3d2a22', trim: '#8a4b2a', grassTuft: '#6a6a4a' },
    grass: 0.12,
  },
  start: { x: 62, z: 0, rot: -Math.PI / 2 },
  props: [
    chimney(14, 0), chimney(7, 12), chimney(-7, 12), chimney(-14, 0), chimney(-7, -12), chimney(7, -12),
    { name: 'prop_vent', x: 34, z: -3, steam: true }, { name: 'prop_vent', x: 30, z: 3, steam: true }, { name: 'prop_vent', x: 26, z: -3, steam: true },
    { name: 'prop_pipe', x: 50, z: 18, rot: 0.3, colliders: pipeCols }, { name: 'prop_pipe', x: 44, z: -20, rot: 1.2, colliders: pipeCols },
    { name: 'prop_pipe', x: -24, z: 22, rot: 0.8, colliders: pipeCols }, { name: 'prop_pipe', x: -28, z: -20, rot: 1.4, colliders: pipeCols },
    { name: 'prop_pipe_arch', x: 38, z: 0, rot: Math.PI / 2, colliders: archCols }, { name: 'prop_pipe_arch', x: -34, z: 0, rot: Math.PI / 2, colliders: archCols },
    box('prop_crate', 52, -8, 0.3), box('prop_crate', 54, -6.4, 1), box('prop_crate', 56, 12, 0.2), box('prop_barrel', 46, 24), box('prop_barrel', -40, 14), box('prop_barrel', 47, 25.2),
    { name: 'prop_drive_shaft', x: -60, z: 0, rot: Math.PI / 2, scale: 0.4, colliders: [{ x: 0, z: 0, r: 2.5 }] },
    { name: 'prop_rest', x: 18, z: 12, colliders: [{ x: 0, z: 0, r: 1.1 }] },
    { name: 'prop_lamp', x: 60, z: -5, colliders: [{ x: 0, z: 0, r: 0.35 }], light: '#ffb060' },
    { name: 'prop_lamp', x: 60, z: 5, colliders: [{ x: 0, z: 0, r: 0.35 }], light: '#ffb060' },
    { name: 'prop_lamp', x: -38, z: -6, colliders: [{ x: 0, z: 0, r: 0.35 }], light: '#ffb060' },
    { name: 'prop_lamp', x: -38, z: 6, colliders: [{ x: 0, z: 0, r: 0.35 }], light: '#ffb060' },
    { name: 'prop_fence', x: -8, z: -40, rot: 0.3, colliders: [{ x: -0.8, z: 0, r: 0.3 }, { x: 0, z: 0, r: 0.3 }, { x: 0.8, z: 0, r: 0.3 }] },
    { name: 'prop_fence', x: 8, z: -40, rot: -0.3, colliders: [{ x: -0.8, z: 0, r: 0.3 }, { x: 0, z: 0, r: 0.3 }, { x: 0.8, z: 0, r: 0.3 }] },
  ],
  chests: [
    { id: 'w_c1', x: 58, z: -22, rot: 0.6, items: { capsule: 2 }, money: 40 },
    { id: 'w_c2', x: -6, z: 34, rot: 2.8, items: {}, money: 0, parts: { p_supercharger: 1 } },
    { id: 'w_c3', x: -30, z: -34, rot: 0.9, items: { hi_tonic: 1 }, money: 0, flag: 'sq04_oath_found', flagText: '교대 서약서' },
    { id: 'w_c4', x: 24, z: -30, rot: -0.4, items: {}, money: 0, crystals: { fire: 3 } },
  ],
  spawns: [
    { id: 'w_s1', x: 50, z: 10, formation: ['cograt', 'cograt', 'bellows_toad'], wander: 5 },
    { id: 'w_s2', x: 44, z: -14, formation: ['bellows_toad', 'slime'], wander: 5 },
    { id: 'w_s3', x: 6, z: 24, formation: ['bellows_toad', 'bellows_toad'], wander: 5 },
    { id: 'w_s4', x: -18, z: -16, formation: ['beetle', 'bellows_toad'], wander: 4 },
    { id: 'w_s5', x: -20, z: 22, formation: ['prism_moth', 'bellows_toad', 'cograt'], wander: 5 },
    // m07: after the first meeting the tortoise stays in the garage until it joins
    { id: 'ev_tortoise', x: -52, z: 0, formation: ['strongbox_tortoise'], wander: 2, afterFlag: 'ch1_valve_got', untilFlag: 'ch1_tortoise_joined' },
  ],
  scatter: [
    { name: 'prop_rock_a', count: 16, rMin: 30, rMax: 80, colR: 1.25, sMin: 0.7, sMax: 1.5 },
    { name: 'prop_rock_b', count: 16, rMin: 30, rMax: 80, colR: 0.9, sMin: 0.7, sMax: 1.5 },
    { name: 'prop_tree_b', count: 10, rMin: 50, rMax: 82, colR: 0.6, sMin: 0.7, sMax: 1.0 },
    { name: 'prop_bush', count: 14, rMin: 30, rMax: 66, colR: 0, sMin: 0.6, sMax: 1.0 },
  ],
  gates: [
    { id: 'gate_works_east', x: 69, z: 0, r: 3, to: 'plains', toGate: 'gate_plain_west', label: '에테르 평원' },
  ],
  npcs: [
    // m06: Bail in the silent yard, gone after the first meeting
    { id: 'bail', name: '바일', x: 0, z: -30, rot: 0, model: 'npc_bail', color: '#9aa0a8', untilFlag: 'ch1_met_bail', silent: true },
  ],
  statues: [
    { model: 'cograt', x: -4, z: -33, rot: 0.4 },
    { model: 'knight', x: 4, z: -35, rot: -0.3 },
    { model: 'cograt', x: 0, z: -38, rot: 0 },
  ],
  spots: [
    { id: 'shortcut_w', x: -40, z: -4, r: 2.4, label: '광차 레일 지름길 <span class="dim">(적재장으로)</span>', afterFlag: 'ch1_valve_got' },
    { id: 'shortcut_e', x: 58, z: 2, r: 2.4, label: '광차 레일 지름길 <span class="dim">(차고로)</span>', afterFlag: 'ch1_valve_got' },
    { id: 'valve_seat', x: -57, z: 0, r: 3, label: '밸브 받침 조사', when: () => F('ch1_valve_got') },
  ],
  landmarks: [{ x: 0, z: 0 }, { x: -50, z: 0 }],
};
