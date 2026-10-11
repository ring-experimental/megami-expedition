import type { Element, Stats } from './types';
import type { SpeciesDef } from './units';
import { SKILLS, type SkillDef } from './skills';

/**
 * Quartz-style build (궤적의 쿼츠 방식): each hero has a board of slots joined into lines. Slotted
 * 부품 add stats, an optional effect, and element values; an art unlocks while the element totals
 * on any ONE line reach its requirement. Locked slots open with 속성 결정 (monster drops).
 */

/** 속성 결정 — dropped by monsters, spent on slots and part crafting. */
export const CRYSTAL_NAME: Record<Element, string> = { phys: '강철 결정', fire: '화염 결정', frost: '냉기 결정', volt: '뇌전 결정', aether: '에테르 결정' };
export const CRYSTAL_ICON: Record<Element, string> = { phys: '◆', fire: '◆', frost: '◆', volt: '◆', aether: '◆' };

/** Battle hooks a part can switch on (read through GameState.partEffects). */
export type PartEffect =
  | 'parryAp'     // parry: +1 extra AP
  | 'counterUp'   // counter attacks ×1.5
  | 'brkUp'       // break damage ×1.25
  | 'talkMood'    // negotiation starts at mood +1
  | 'startHaste'  // 가속 for the first 2 turns
  | 'healUp'      // heals ×1.25
  | 'heatVent'    // Kai: parries vent 10 more heat, overheat lasts a turn longer
  | 'revealWeak'; // enemies' affinities are known from the start

export const EFFECT_DESC: Record<PartEffect, string> = {
  parryAp: '패링 성공 시 AP +1 추가',
  counterUp: '반격 피해 ×1.5',
  brkUp: '브레이크 수치 ×1.25',
  talkMood: '협상 시작 시 분위기 +1',
  startHaste: '전투 시작 2턴간 가속',
  healUp: '회복량 ×1.25',
  heatVent: '패링 시 열압 추가 방출 · 과열 1턴 연장',
  revealWeak: '적의 약점·내성을 처음부터 안다',
};

export interface PartDef {
  id: string;
  name: string;
  desc: string;
  elem: Partial<Record<Element, number>>;
  stats?: Partial<Stats>;
  effect?: PartEffect;
  /** Crafting cost at the 공방 (crystals + 기어); parts without one are found only. */
  craft?: { crystals: Partial<Record<Element, number>>; money: number };
}

export const PARTS: Record<string, PartDef> = {
  piston_ring: { id: 'piston_ring', name: '피스톤 링', desc: '타격의 반동을 되밀어 주는 링.', elem: { phys: 1 }, stats: { atk: 4 }, craft: { crystals: { phys: 3 }, money: 40 } },
  brass_plate: { id: 'brass_plate', name: '황동 판', desc: '얇게 두드린 황동 장갑.', elem: { phys: 1 }, stats: { def: 4 }, craft: { crystals: { phys: 3 }, money: 40 } },
  boiler_coil: { id: 'boiler_coil', name: '보일러 코일', desc: '체온을 데워 버티게 해 주는 코일.', elem: { fire: 1 }, stats: { hp: 30 }, craft: { crystals: { fire: 3 }, money: 50 } },
  ember_valve: { id: 'ember_valve', name: '불씨 밸브', desc: '불씨를 머금은 밸브. 화염 회로의 시작.', elem: { fire: 2 }, stats: { mag: 2 }, craft: { crystals: { fire: 4 }, money: 60 } },
  cooling_fin: { id: 'cooling_fin', name: '냉각 핀', desc: '열을 빼앗는 얇은 날개들.', elem: { frost: 2 }, stats: { res: 3 }, craft: { crystals: { frost: 4 }, money: 60 } },
  volt_coil: { id: 'volt_coil', name: '축전 코일', desc: '찌릿한 전하를 감아 둔 코일.', elem: { volt: 2 }, stats: { spd: 1 }, craft: { crystals: { volt: 4 }, money: 60 } },
  aether_lens: { id: 'aether_lens', name: '에테르 렌즈', desc: '에테르의 흐름을 모으는 렌즈.', elem: { aether: 2 }, stats: { mag: 3 }, craft: { crystals: { aether: 4 }, money: 70 } },
  beat_spring: { id: 'beat_spring', name: '맞박 태엽', desc: '상대의 박자에 맞춰 튀어 오르는 태엽.', elem: { phys: 1, aether: 1 }, effect: 'parryAp', craft: { crystals: { phys: 3, aether: 3 }, money: 120 } },
  recoil_spring: { id: 'recoil_spring', name: '반동 스프링', desc: '받아 낸 힘을 그대로 되돌린다.', elem: { phys: 2 }, effect: 'counterUp', craft: { crystals: { phys: 6 }, money: 120 } },
  wedge_gear: { id: 'wedge_gear', name: '쐐기 톱니', desc: '틈을 벌리는 쐐기 모양 톱니.', elem: { phys: 1, volt: 1 }, effect: 'brkUp', craft: { crystals: { phys: 3, volt: 3 }, money: 120 } },
  silver_whistle: { id: 'silver_whistle', name: '은 호루라기', desc: '기령이 좋아하는 맑은 소리.', elem: { aether: 1 }, effect: 'talkMood', craft: { crystals: { aether: 5 }, money: 100 } },
  escapement: { id: 'escapement', name: '가속 탈진기', desc: '시계의 탈진기를 빠르게 깎아 냈다.', elem: { volt: 1, frost: 1 }, effect: 'startHaste' },
  warm_circuit: { id: 'warm_circuit', name: '온기 회로', desc: '치유의 공명을 데워 키운다.', elem: { aether: 1, fire: 1 }, effect: 'healUp', craft: { crystals: { aether: 3, fire: 3 }, money: 120 } },
  heat_sink: { id: 'heat_sink', name: '방열판', desc: '카이의 보일러에 덧대는 방열판.', elem: { frost: 1 }, effect: 'heatVent' },
  echo_compass: { id: 'echo_compass', name: '공명 나침반', desc: '상대의 떨림으로 약한 곳을 짚는다.', elem: { aether: 2 }, effect: 'revealWeak' },
};

export interface BoardDef {
  name: string;
  /** slot positions on the board panel (0–100 coordinates) */
  pos: [number, number][];
  /** lines of slot indices; arts check each line's element total separately */
  lines: number[][];
  /** slots open at the start; the rest cost crystals */
  open: number[];
  unlock: Record<number, Partial<Record<Element, number>>>;
}

/** Kai: one long line and a short one through the centre. Lyra: the reverse — her long line feeds magic. */
export const BOARDS: Record<'kai' | 'lyra', BoardDef> = {
  kai: {
    name: '울림쇠',
    pos: [[50, 50], [72, 24], [88, 52], [70, 80], [28, 26], [13, 62]],
    lines: [[0, 1, 2, 3], [0, 4, 5]],
    open: [0, 1, 4],
    unlock: { 2: { phys: 4 }, 3: { fire: 4, phys: 2 }, 5: { phys: 6 } },
  },
  lyra: {
    name: '각인 고리',
    pos: [[50, 50], [28, 24], [12, 54], [72, 24], [88, 52], [70, 80]],
    lines: [[0, 1, 2], [0, 3, 4, 5]],
    open: [0, 1, 3],
    unlock: { 2: { aether: 4 }, 4: { frost: 3, volt: 3 }, 5: { aether: 6 } },
  },
};

/** Arts: magic usable by whoever has the line totals. Lyra's arts also leave 회로 각인. */
export interface ArtDef { skill: SkillDef; need: Partial<Record<Element, number>> }
const art = (id: string, name: string, desc: string, need: Partial<Record<Element, number>>, s: Partial<SkillDef>): ArtDef => ({
  need,
  skill: { id, name, desc, ap: 2, target: 'enemy', kind: 'magic', element: 'aether', power: 1.4, hits: 1, qte: 1, breakPower: 10, anim: 'cast', melee: false, ...s },
});
export const ARTS: ArtDef[] = [
  art('art_flare', '플레어', '불꽃 덩이를 던진다.', { fire: 2 }, { element: 'fire', power: 1.45, status: { id: 'burn', turns: 2, chance: 0.3 } }),
  art('art_blaze', '블레이즈', '적 전체를 불길로 휩쓴다.', { fire: 4 }, { element: 'fire', target: 'allEnemies', ap: 4, power: 0.95 }),
  art('art_icicle', '아이시클', '얼음 송곳을 꽂는다.', { frost: 2 }, { element: 'frost', power: 1.45, breakPower: 14 }),
  art('art_spark', '스파크', '번개 한 줄기를 떨어뜨린다.', { volt: 2 }, { element: 'volt', power: 1.45 }),
  art('art_ether_ray', '에테르 레이', '응축한 에테르 광선.', { aether: 4 }, { element: 'aether', ap: 3, power: 2.1 }),
  art('art_cure', '큐어', '아군 하나의 HP를 회복한다.', { aether: 2 }, { kind: 'heal', target: 'ally', element: 'aether', power: 1.0, qte: 1, breakPower: 0 }),
  art('art_aegis', '에기스', '아군 전체 3턴간 방어↑.', { phys: 3 }, { kind: 'buff', target: 'allAllies', element: 'phys', power: 0, breakPower: 0, status: { id: 'defUp', turns: 3, chance: 1 } }),
  art('art_clock_up', '클록 업', '아군 하나에 3턴간 가속.', { volt: 2, frost: 1 }, { kind: 'buff', target: 'ally', element: 'volt', power: 0, breakPower: 0, status: { id: 'haste', turns: 3, chance: 1 } }),
];
export const ART_SKILLS: Record<string, SkillDef> = Object.fromEntries(ARTS.map((a) => [a.skill.id, a.skill]));
// arts resolve through the same skill table as everything else (battle menus, level-up notes)
Object.assign(SKILLS, ART_SKILLS);

/** Sum of element values per line for a board loadout. */
export function lineTotals(board: BoardDef, slots: (string | null)[]) {
  return board.lines.map((line) => {
    const t: Partial<Record<Element, number>> = {};
    for (const i of line) {
      const p = slots[i] ? PARTS[slots[i]!] : null;
      if (!p) continue;
      for (const [e, v] of Object.entries(p.elem)) t[e as Element] = (t[e as Element] ?? 0) + (v ?? 0);
    }
    return t;
  });
}

/** Arts whose requirement is met by at least one line. */
export function artsFor(board: BoardDef, slots: (string | null)[]) {
  const lines = lineTotals(board, slots);
  return ARTS.filter((a) => lines.some((t) => Object.entries(a.need).every(([e, v]) => (t[e as Element] ?? 0) >= (v ?? 0))));
}

/** 속성 결정 a defeated species leaves: its first elemental move's element (else 강철), more for tougher tiers. */
export function crystalDrop(sp: SpeciesDef): [Element, number] {
  const el = sp.moves.find((m) => m.element !== 'phys')?.element ?? 'phys';
  const n = sp.tier === 'elite' ? 6 : sp.tier === 'strong' ? 3 : 1 + Math.round(Math.random());
  return [el, n];
}
