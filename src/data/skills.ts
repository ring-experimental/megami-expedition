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
  /** Pushes the target's next turn back by this % of its turn interval (CTB delay). */
  delay?: number;
  /** Own next turn comes after this × the usual interval (default: 1, or 1.25 for 4+ AP skills). */
  tempo?: number;
  /** Kai: spends all 열압 — power grows with the heat vented. */
  vent?: boolean;
  /** Lyra: fuses the two stored 회로 각인 into a higher spell (resolved at use, see fuseSkill). */
  fuse?: boolean;
}

export const SKILLS: Record<string, SkillDef> = {
  // --- Kai ---------------------------------------------------------------
  steam_slash: { id: 'steam_slash', name: '증기 베기', desc: '증기압을 실은 2연속 베기.', ap: 2, target: 'enemy', kind: 'phys', element: 'phys', power: 0.95, hits: 2, qte: 2, breakPower: 14, anim: 'slash', melee: true },
  piston_thrust: { id: 'piston_thrust', name: '피스톤 스러스트', desc: '피스톤 가속 찌르기. 브레이크 수치를 크게 채우고 적의 턴을 늦춘다.', ap: 3, target: 'enemy', kind: 'phys', element: 'phys', power: 2.0, hits: 1, qte: 1, breakPower: 45, anim: 'thrust', melee: true, delay: 35 },
  vent_slash: { id: 'vent_slash', name: '방열 일섬', desc: '쌓인 열압을 한 번에 방출하는 베기. 열압이 높을수록 강하다.', ap: 2, target: 'enemy', kind: 'phys', element: 'fire', power: 0.6, hits: 1, qte: 1, breakPower: 20, anim: 'heavy', melee: true, vent: true },
  overheat_storm: { id: 'overheat_storm', name: '과열 폭풍', desc: '과열된 증기를 회전 베기로 방출. 적 전체 화염 3회.', ap: 5, target: 'allEnemies', kind: 'phys', element: 'fire', power: 0.85, hits: 3, qte: 3, breakPower: 10, anim: 'spin', melee: true, status: { id: 'burn', turns: 2, chance: 0.35 } },
  // --- Lyra --------------------------------------------------------------
  aether_bolt: { id: 'aether_bolt', name: '에테르 볼트', desc: '응축한 에테르 탄환.', ap: 2, target: 'enemy', kind: 'magic', element: 'aether', power: 1.55, hits: 1, qte: 1, breakPower: 10, anim: 'cast', melee: false },
  frost_gear: { id: 'frost_gear', name: '프로스트 기어', desc: '얼음 톱니가 적 전체를 두 번 할퀸다.', ap: 3, target: 'allEnemies', kind: 'magic', element: 'frost', power: 0.8, hits: 2, qte: 2, breakPower: 8, anim: 'cast', melee: false },
  resonance_heal: { id: 'resonance_heal', name: '치유의 공명', desc: '아군 전체 HP 회복.', ap: 3, target: 'allAllies', kind: 'heal', element: 'aether', power: 1.15, hits: 1, qte: 1, breakPower: 0, anim: 'cast', melee: false },
  circuit_fuse: { id: 'circuit_fuse', name: '회로 결합', desc: '새겨 둔 서로 다른 각인 2개를 엮어 상위 마법을 쓴다.', ap: 3, target: 'enemy', kind: 'magic', element: 'aether', power: 1, hits: 1, qte: 2, breakPower: 20, anim: 'cast', melee: false, fuse: true },
  volt_circuit: { id: 'volt_circuit', name: '번개 회로', desc: '회로를 그려 번개를 3회 떨어뜨린다.', ap: 4, target: 'enemy', kind: 'magic', element: 'volt', power: 0.95, hits: 3, qte: 3, breakPower: 14, anim: 'cast', melee: false },
  // --- Monster allies ----------------------------------------------------
  gear_bite: { id: 'gear_bite', name: '톱니 물기', desc: '톱니 이빨로 3연속 물기.', ap: 2, target: 'enemy', kind: 'phys', element: 'phys', power: 0.55, hits: 3, qte: 3, breakPower: 8, anim: 'lunge', melee: true },
  wind_up: { id: 'wind_up', name: '태엽 감기', desc: '자신의 태엽을 감아 3턴간 가속 + 공격↑.', ap: 2, target: 'self', kind: 'buff', element: 'phys', power: 0, hits: 1, qte: 1, breakPower: 0, anim: 'cast', melee: false, status: { id: 'haste', turns: 3, chance: 1, self: true } },
  steam_heal: { id: 'steam_heal', name: '증기 치유', desc: '따뜻한 증기로 아군 전체 회복.', ap: 3, target: 'allAllies', kind: 'heal', element: 'aether', power: 0.9, hits: 1, qte: 1, breakPower: 0, anim: 'cast', melee: false },
  jelly_guard: { id: 'jelly_guard', name: '젤리 방벽', desc: '아군 전체 3턴간 방어↑.', ap: 2, target: 'allAllies', kind: 'buff', element: 'phys', power: 0, hits: 1, qte: 1, breakPower: 0, anim: 'cast', melee: false, status: { id: 'defUp', turns: 3, chance: 1 } },
  horn_rush: { id: 'horn_rush', name: '뿔 돌진', desc: '육중한 돌진. 브레이크 수치를 크게 채우고 적의 턴을 늦춘다.', ap: 3, target: 'enemy', kind: 'phys', element: 'phys', power: 2.1, hits: 1, qte: 1, breakPower: 50, anim: 'lunge', melee: true, delay: 25 },
  iron_shell: { id: 'iron_shell', name: '강철 외피', desc: '3턴간 적의 공격을 끌어모으고 방어↑.', ap: 2, target: 'self', kind: 'buff', element: 'phys', power: 0, hits: 1, qte: 1, breakPower: 0, anim: 'cast', melee: false, status: { id: 'guard', turns: 3, chance: 1, self: true } },
  lamp_flame: { id: 'lamp_flame', name: '등불 화염', desc: '화염탄. 확률로 화상.', ap: 2, target: 'enemy', kind: 'magic', element: 'fire', power: 1.5, hits: 1, qte: 1, breakPower: 10, anim: 'cast', melee: false, status: { id: 'burn', turns: 3, chance: 0.5 } },
  will_o_wisp: { id: 'will_o_wisp', name: '도깨비불', desc: '적 전체에 에테르 불꽃 2회.', ap: 4, target: 'allEnemies', kind: 'magic', element: 'aether', power: 0.8, hits: 2, qte: 2, breakPower: 8, anim: 'cast', melee: false },
  whirl_slash: { id: 'whirl_slash', name: '회전 베기', desc: '할버드로 적 전체를 2회 벤다.', ap: 4, target: 'allEnemies', kind: 'phys', element: 'phys', power: 0.95, hits: 2, qte: 2, breakPower: 12, anim: 'spin', melee: true },
  knights_oath: { id: 'knights_oath', name: '기사의 맹세', desc: '아군 전체 3턴간 공격↑.', ap: 3, target: 'allAllies', kind: 'buff', element: 'phys', power: 0, hits: 1, qte: 1, breakPower: 0, anim: 'cast', melee: false, status: { id: 'atkUp', turns: 3, chance: 1 } },
  furnace_punch: { id: 'furnace_punch', name: '용광로 펀치', desc: '작열하는 주먹. 브레이크 수치를 크게 채운다.', ap: 4, target: 'enemy', kind: 'phys', element: 'fire', power: 2.6, hits: 1, qte: 1, breakPower: 60, anim: 'heavy', melee: true },
  // --- monster late skills (learned at a level after recruiting) -------------
  scrap_swarm: { id: 'scrap_swarm', name: '고철 떼', desc: '동족을 불러 적 전체를 물어뜯는다.', ap: 4, target: 'allEnemies', kind: 'phys', element: 'phys', power: 0.45, hits: 3, qte: 2, breakPower: 8, anim: 'lunge', melee: true },
  pressure_wash: { id: 'pressure_wash', name: '고압 세척', desc: '뜨거운 물줄기. 적 하나에 화염 피해 + 지연.', ap: 3, target: 'enemy', kind: 'magic', element: 'fire', power: 1.6, hits: 1, qte: 1, breakPower: 12, anim: 'cast', melee: false, delay: 25 },
  gaslight: { id: 'gaslight', name: '가스등 점멸', desc: '눈부신 빛으로 적 전체의 공격을 떨어뜨린다.', ap: 3, target: 'allEnemies', kind: 'magic', element: 'aether', power: 0.6, hits: 1, qte: 1, breakPower: 6, anim: 'cast', melee: false, status: { id: 'atkDown', turns: 3, chance: 0.7 } },
  shell_quake: { id: 'shell_quake', name: '갑각 진동', desc: '땅을 울려 적 전체의 브레이크 수치를 채운다.', ap: 4, target: 'allEnemies', kind: 'phys', element: 'phys', power: 0.7, hits: 1, qte: 1, breakPower: 28, anim: 'heavy', melee: true },
  oath_counter: { id: 'oath_counter', name: '맹세의 일격', desc: '번개를 두른 할버드 일격. 적의 턴을 크게 늦춘다.', ap: 4, target: 'enemy', kind: 'phys', element: 'volt', power: 2.3, hits: 1, qte: 2, breakPower: 30, anim: 'thrust', melee: true, delay: 45 },
  meltdown: { id: 'meltdown', name: '노심 용해', desc: '화로를 개방해 적 전체를 녹인다. 다음 턴이 늦어진다.', ap: 7, target: 'allEnemies', kind: 'magic', element: 'fire', power: 1.5, hits: 2, qte: 2, breakPower: 15, anim: 'cast', melee: false, tempo: 1.5, status: { id: 'burn', turns: 3, chance: 0.5 } },
  steam_burst: { id: 'steam_burst', name: '증기 대폭발', desc: '적 전체에 고압 증기 3회.', ap: 6, target: 'allEnemies', kind: 'magic', element: 'fire', power: 1.0, hits: 3, qte: 3, breakPower: 10, anim: 'cast', melee: false },
};

/** Basic attack (0 AP, +1 AP). */
export const BASIC_ATTACK: SkillDef = {
  id: 'attack', name: '공격', desc: '기본 공격. AP +1', ap: 0, target: 'enemy', kind: 'phys', element: 'phys',
  power: 1.0, hits: 1, qte: 0, breakPower: 10, anim: 'slash', melee: true,
};

/** Turn-interval multiplier after using a skill (CTB): heavy skills cost time, light actions are quick. */
export function tempoOf(sk: SkillDef | null) {
  if (!sk) return 0.8; // items
  if (sk.id === 'attack') return 0.85;
  return sk.tempo ?? (sk.ap >= 4 ? 1.25 : 1);
}

/** Elements that leave a 회로 각인 when Lyra casts an offensive spell of them. */
export const SIGIL_ELEMENTS: Element[] = ['fire', 'frost', 'volt', 'aether'];

/** 회로 결합 table: two different sigils → the spell they make. */
export function fuseSkill(a: Element, b: Element): SkillDef | null {
  const key = [a, b].sort().join('+');
  const base = SKILLS.circuit_fuse;
  const t: Record<string, Partial<SkillDef>> = {
    'frost+volt': { name: '초전도', desc: '냉기로 식힌 회로에 번개를 흘려 한 점을 꿰뚫는다. 브레이크 대량.', element: 'volt', power: 3.0, breakPower: 45 },
    'fire+frost': { name: '증기 폭발', desc: '얼음과 불을 맞부딪쳐 적 전체를 증기로 덮친다.', element: 'fire', target: 'allEnemies', power: 1.2, hits: 2 },
    'fire+volt': { name: '플라즈마', desc: '불꽃에 번개를 감아 태운다. 화상.', element: 'fire', power: 2.6, status: { id: 'burn', turns: 3, chance: 0.8 } },
    'aether+frost': { name: '빙결 공명', desc: '에테르로 냉기를 증폭해 적 전체를 얼린다.', element: 'frost', target: 'allEnemies', power: 1.3 },
    'aether+volt': { name: '뇌명 공명', desc: '에테르 회로를 타고 번개가 적 전체에 두 번 떨어진다.', element: 'volt', target: 'allEnemies', power: 0.9, hits: 2 },
    'aether+fire': { name: '열 공명', desc: '에테르로 불꽃을 키워 적 전체를 태운다.', element: 'fire', target: 'allEnemies', power: 1.25, status: { id: 'burn', turns: 2, chance: 0.4 } },
  };
  const d = t[key];
  return d ? { ...base, ...d, fuse: true } : null;
}
