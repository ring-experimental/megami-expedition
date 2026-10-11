import type { Element, StatusId } from './types';

export type SkillTarget = 'enemy' | 'allEnemies' | 'ally' | 'allAllies' | 'self';
export type SkillAnim = 'slash' | 'thrust' | 'heavy' | 'cast' | 'lunge' | 'spin';

export interface SkillDef {
  id: string;
  name: string;
  desc: string;
  ap: number;
  target: SkillTarget;
  kind: 'phys' | 'magic' | 'heal' | 'buff';
  element: Element;
  /** Damage/heal multiplier per hit. */
  power: number;
  hits: number;
  /** Number of timing prompts (Expedition-33 style QTE). Each success boosts the skill. */
  qte: number;
  breakPower: number;
  anim: SkillAnim;
  melee: boolean;
  status?: { id: StatusId; turns: number; chance: number; self?: boolean };
}

export const SKILLS: Record<string, SkillDef> = {
  // --- Kai ---------------------------------------------------------------
  steam_slash: { id: 'steam_slash', name: '증기 베기', desc: '증기압을 실은 2연속 베기.', ap: 2, target: 'enemy', kind: 'phys', element: 'phys', power: 0.95, hits: 2, qte: 2, breakPower: 14, anim: 'slash', melee: true },
  piston_thrust: { id: 'piston_thrust', name: '피스톤 스러스트', desc: '피스톤 가속 찌르기. 브레이크 수치를 크게 채운다.', ap: 3, target: 'enemy', kind: 'phys', element: 'phys', power: 2.0, hits: 1, qte: 1, breakPower: 45, anim: 'thrust', melee: true },
  overheat_storm: { id: 'overheat_storm', name: '과열 폭풍', desc: '과열된 증기를 회전 베기로 방출. 적 전체 화염 3회.', ap: 5, target: 'allEnemies', kind: 'phys', element: 'fire', power: 0.85, hits: 3, qte: 3, breakPower: 10, anim: 'spin', melee: true, status: { id: 'burn', turns: 2, chance: 0.35 } },
  // --- Lyra --------------------------------------------------------------
  aether_bolt: { id: 'aether_bolt', name: '에테르 볼트', desc: '응축한 에테르 탄환.', ap: 2, target: 'enemy', kind: 'magic', element: 'aether', power: 1.55, hits: 1, qte: 1, breakPower: 10, anim: 'cast', melee: false },
  frost_gear: { id: 'frost_gear', name: '프로스트 기어', desc: '얼음 톱니가 적 전체를 두 번 할퀸다.', ap: 3, target: 'allEnemies', kind: 'magic', element: 'frost', power: 0.8, hits: 2, qte: 2, breakPower: 8, anim: 'cast', melee: false },
  resonance_heal: { id: 'resonance_heal', name: '치유의 공명', desc: '아군 전체 HP 회복.', ap: 3, target: 'allAllies', kind: 'heal', element: 'aether', power: 1.15, hits: 1, qte: 1, breakPower: 0, anim: 'cast', melee: false },
  volt_circuit: { id: 'volt_circuit', name: '번개 회로', desc: '회로를 그려 번개를 3회 떨어뜨린다.', ap: 4, target: 'enemy', kind: 'magic', element: 'volt', power: 0.95, hits: 3, qte: 3, breakPower: 14, anim: 'cast', melee: false },
  // --- Monster allies ----------------------------------------------------
  gear_bite: { id: 'gear_bite', name: '톱니 물기', desc: '톱니 이빨로 3연속 물기.', ap: 2, target: 'enemy', kind: 'phys', element: 'phys', power: 0.55, hits: 3, qte: 3, breakPower: 8, anim: 'lunge', melee: true },
  wind_up: { id: 'wind_up', name: '태엽 감기', desc: '자신의 태엽을 감아 3턴간 가속 + 공격↑.', ap: 2, target: 'self', kind: 'buff', element: 'phys', power: 0, hits: 1, qte: 1, breakPower: 0, anim: 'cast', melee: false, status: { id: 'haste', turns: 3, chance: 1, self: true } },
  steam_heal: { id: 'steam_heal', name: '증기 치유', desc: '따뜻한 증기로 아군 전체 회복.', ap: 3, target: 'allAllies', kind: 'heal', element: 'aether', power: 0.9, hits: 1, qte: 1, breakPower: 0, anim: 'cast', melee: false },
  jelly_guard: { id: 'jelly_guard', name: '젤리 방벽', desc: '아군 전체 3턴간 방어↑.', ap: 2, target: 'allAllies', kind: 'buff', element: 'phys', power: 0, hits: 1, qte: 1, breakPower: 0, anim: 'cast', melee: false, status: { id: 'defUp', turns: 3, chance: 1 } },
  horn_rush: { id: 'horn_rush', name: '뿔 돌진', desc: '육중한 돌진. 브레이크 수치를 크게 채운다.', ap: 3, target: 'enemy', kind: 'phys', element: 'phys', power: 2.1, hits: 1, qte: 1, breakPower: 50, anim: 'lunge', melee: true },
  iron_shell: { id: 'iron_shell', name: '강철 외피', desc: '3턴간 적의 공격을 끌어모으고 방어↑.', ap: 2, target: 'self', kind: 'buff', element: 'phys', power: 0, hits: 1, qte: 1, breakPower: 0, anim: 'cast', melee: false, status: { id: 'guard', turns: 3, chance: 1, self: true } },
  lamp_flame: { id: 'lamp_flame', name: '등불 화염', desc: '화염탄. 확률로 화상.', ap: 2, target: 'enemy', kind: 'magic', element: 'fire', power: 1.5, hits: 1, qte: 1, breakPower: 10, anim: 'cast', melee: false, status: { id: 'burn', turns: 3, chance: 0.5 } },
  will_o_wisp: { id: 'will_o_wisp', name: '도깨비불', desc: '적 전체에 에테르 불꽃 2회.', ap: 4, target: 'allEnemies', kind: 'magic', element: 'aether', power: 0.8, hits: 2, qte: 2, breakPower: 8, anim: 'cast', melee: false },
  whirl_slash: { id: 'whirl_slash', name: '회전 베기', desc: '할버드로 적 전체를 2회 벤다.', ap: 4, target: 'allEnemies', kind: 'phys', element: 'phys', power: 0.95, hits: 2, qte: 2, breakPower: 12, anim: 'spin', melee: true },
  knights_oath: { id: 'knights_oath', name: '기사의 맹세', desc: '아군 전체 3턴간 공격↑.', ap: 3, target: 'allAllies', kind: 'buff', element: 'phys', power: 0, hits: 1, qte: 1, breakPower: 0, anim: 'cast', melee: false, status: { id: 'atkUp', turns: 3, chance: 1 } },
  furnace_punch: { id: 'furnace_punch', name: '용광로 펀치', desc: '작열하는 주먹. 브레이크 수치를 크게 채운다.', ap: 4, target: 'enemy', kind: 'phys', element: 'fire', power: 2.6, hits: 1, qte: 1, breakPower: 60, anim: 'heavy', melee: true },
  steam_burst: { id: 'steam_burst', name: '증기 대폭발', desc: '적 전체에 고압 증기 3회.', ap: 6, target: 'allEnemies', kind: 'magic', element: 'fire', power: 1.0, hits: 3, qte: 3, breakPower: 10, anim: 'cast', melee: false },
};

/** Basic attack (0 AP, +1 AP). */
export const BASIC_ATTACK: SkillDef = {
  id: 'attack', name: '공격', desc: '기본 공격. AP +1', ap: 0, target: 'enemy', kind: 'phys', element: 'phys',
  power: 1.0, hits: 1, qte: 0, breakPower: 10, anim: 'slash', melee: true,
};
