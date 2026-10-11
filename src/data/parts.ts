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
  | 'heatGain'      // Kai: 열압 builds ×1.2
  | 'heatVent'      // Kai: parries vent 10 more 열압
  | 'brkUp'         // break dealt +10%
  | 'talkMood'      // negotiation starts at mood +1
  | 'startSteam'    // battle starts with 증기압 +0.5
  | 'parryAp'       // parry: +1 extra AP (once per turn)
  | 'winHeal'       // victory: HP +5%
  | 'holdupTalk'    // hold-up 포위 협상 +15%
  | 'firstHitGuard' // first hit taken each battle −30%
  | 'gaugeGain'     // 증기압 fills +15%
  | 'overheatLight'; // Kai: 과열 scalds 3% instead of 5%

export const EFFECT_DESC: Record<PartEffect, string> = {
  heatGain: '카이: 열압 상승량 ×1.2',
  heatVent: '카이: 패링 시 열압 추가 −10',
  brkUp: '주는 브레이크 +10%',
  talkMood: '협상 시작 시 분위기 +1',
  startSteam: '전투 시작 시 증기압 +0.5칸',
  parryAp: '패링 성공 시 AP +1 추가 (턴당 1회)',
  winHeal: '전투 승리 시 HP 5% 회복',
  holdupTalk: '홀드업 포위 협상 성공률 +15%',
  firstHitGuard: '전투마다 첫 피격 피해 −30%',
  gaugeGain: '증기압 게이지 충전량 +15%',
  overheatLight: '카이 전용: 과열 중 HP 소모 5% → 3%',
};

/** Crystal cost; `any` = that many crystals of any element. */
export type CrystalCost = Partial<Record<Element | 'any', number>>;

export interface PartDef {
  id: string;
  name: string;
  desc: string;
  elem: Partial<Record<Element, number>>;
  stats?: Partial<Stats>;
  effect?: PartEffect;
  /** only this hero can slot it */
  only?: 'kai' | 'lyra';
  /** Crafting cost at the 공방 (crystals + 기어); parts without one are found only. */
  craft?: { crystals: CrystalCost; money: number };
  /** shop price (기어) when the shop stocks it */
  price?: number;
}

export const PARTS: Record<string, PartDef> = {
  p_steel_spring: { id: 'p_steel_spring', name: '강철 스프링', desc: '마르타가 준 음핀. 단단하게 버틴다.', elem: { phys: 2 }, stats: { def: 2 }, craft: { crystals: { phys: 4 }, money: 60 } },
  p_heat_coil: { id: 'p_heat_coil', name: '열관 코일', desc: '보일러 열을 칼끝으로 보낸다.', elem: { fire: 2 }, stats: { atk: 2 }, effect: 'heatGain', price: 200, craft: { crystals: { fire: 4 }, money: 80 } },
  p_cooling_fin: { id: 'p_cooling_fin', name: '냉각 핀', desc: '열을 빼앗는 얇은 날개들.', elem: { frost: 2 }, stats: { res: 2 }, effect: 'heatVent', price: 200, craft: { crystals: { frost: 4 }, money: 80 } },
  p_copper_helix: { id: 'p_copper_helix', name: '구리 나선', desc: '찌릿한 전하를 감은 나선.', elem: { volt: 2, phys: 1 }, stats: { spd: 1 }, effect: 'brkUp' },
  p_lens_shard: { id: 'p_lens_shard', name: '렌즈 조각', desc: '기령의 색이 조금 더 잘 보인다.', elem: { aether: 3 }, stats: { mag: 3 }, effect: 'talkMood' },
  p_supercharger: { id: 'p_supercharger', name: '과급 톱니', desc: '시작부터 압력을 밀어 넣는다.', elem: { fire: 1, phys: 1 }, stats: { atk: 1 }, effect: 'startSteam' },
  p_metronome_pin: { id: 'p_metronome_pin', name: '메트로놈 핀', desc: '상대의 박에 맞춰 튀어 오른다.', elem: { aether: 1, phys: 1 }, effect: 'parryAp' },
  p_lamp_wick: { id: 'p_lamp_wick', name: '등심지', desc: '이긴 뒤에도 꺼지지 않는 작은 불.', elem: { fire: 1, aether: 1 }, stats: { hp: 20 }, effect: 'winHeal' },
  p_quiet_bell: { id: 'p_quiet_bell', name: '작은 종추', desc: '멈춘 상대에게 말이 닿게 한다.', elem: { frost: 1, volt: 1 }, stats: { res: 1 }, effect: 'holdupTalk' },
  p_strongbox_hinge: { id: 'p_strongbox_hinge', name: '금고 경첩', desc: '첫 충격만은 반드시 막아 낸다.', elem: { phys: 2, frost: 1 }, stats: { def: 3 }, effect: 'firstHitGuard' },
  p_bellows_leather: { id: 'p_bellows_leather', name: '풀무 가죽', desc: '압력을 더 많이 모은다.', elem: { fire: 2, aether: 1 }, effect: 'gaugeGain' },
  p_renner_cog: { id: 'p_renner_cog', name: '레너의 톱니', desc: '아버지의 책상에 남아 있던 톱니.', elem: { phys: 3, aether: 1 }, stats: { atk: 3 }, effect: 'overheatLight', only: 'kai' },
};

export interface BoardDef {
  name: string;
  /** slot positions on the board panel (0–100 coordinates) */
  pos: [number, number][];
  /** lines of slot indices (in order: neighbours on a line harmonize) */
  lines: number[][];
  /** slots open at the start; the rest cost crystals */
  open: number[];
  unlock: Record<number, CrystalCost>;
}

/**
 * 울림통 (music-box drum built into each hero): Kai has one long line of 5, Lyra three short
 * lines of 2. Same-element parts in neighbouring slots of a line add +1 to that element (화음).
 */
export const BOARDS: Record<'kai' | 'lyra', BoardDef> = {
  kai: {
    name: '심장 울림통',
    pos: [[12, 62], [30, 36], [50, 56], [70, 36], [88, 62]],
    lines: [[0, 1, 2, 3, 4]],
    open: [0, 1, 2],
    unlock: { 3: { phys: 2 }, 4: { any: 4 } },
  },
  lyra: {
    name: '지팡이 울림통',
    pos: [[20, 26], [20, 74], [50, 26], [50, 74], [80, 26], [80, 74]],
    lines: [[0, 1], [2, 3], [4, 5]],
    open: [0, 2, 4],
    unlock: { 1: { any: 2 }, 3: { any: 2 }, 5: { any: 2 } },
  },
};

/** Arts: each hero's own magic, opened while one line's element total reaches `need`. */
export interface ArtDef { who: 'kai' | 'lyra'; skill: SkillDef; need: Partial<Record<Element, number>> }
const art = (who: 'kai' | 'lyra', id: string, name: string, desc: string, need: Partial<Record<Element, number>>, s: Partial<SkillDef>): ArtDef => ({
  who,
  need,
  skill: { id, name, desc, ap: 3, target: 'enemy', kind: 'phys', element: 'phys', power: 1.4, hits: 1, qte: 1, breakPower: 10, anim: 'slash', melee: true, ...s },
});
export const ARTS: ArtDef[] = [
  art('kai', 'boiler_cleave', '보일러 내려베기', '보일러 열을 실은 내려베기. 열압 +25, 확률로 화상.', { fire: 3 }, { element: 'fire', power: 1.6, breakPower: 25, anim: 'heavy', heat: 25, status: { id: 'burn', turns: 2, chance: 0.3 } }),
  art('kai', 'rivet_rush', '리벳 연타', '빠른 다섯 찌르기.', { phys: 4 }, { power: 0.4, hits: 5, qte: 3, breakPower: 20, anim: 'thrust' }),
  art('kai', 'arc_edge', '전호 베기', '칼날에 번개를 감는다.', { volt: 3 }, { element: 'volt', power: 1.4, breakPower: 30 }),
  art('kai', 'frost_quench', '담금질', '냉기로 보일러를 식힌다. 열압 −40, 2턴간 방어↑.', { frost: 3 }, { ap: 1, target: 'self', kind: 'buff', element: 'frost', power: 0, breakPower: 0, anim: 'cast', melee: false, heat: -40, status: { id: 'defUp', turns: 2, chance: 1, self: true } }),
  art('lyra', 'ember_glyph', '불씨 각인', '화 문양을 남기는 불씨. 회로 결합의 재료.', { fire: 2 }, { ap: 2, kind: 'magic', element: 'fire', power: 1.3, anim: 'cast', melee: false }),
  art('lyra', 'spark_needle', '전침', '번개 바늘 한 줄기.', { volt: 2 }, { ap: 2, kind: 'magic', element: 'volt', power: 1.2, breakPower: 12, anim: 'cast', melee: false }),
  art('lyra', 'rime_lock', '서리 자물쇠', '대상의 다음 턴을 크게 늦춘다.', { frost: 3 }, { kind: 'magic', element: 'frost', power: 1.0, breakPower: 15, anim: 'cast', melee: false, delay: 40 }),
  art('lyra', 'aegis_chord', '보호 화음', '아군 전체 3턴간 방어↑.', { aether: 3 }, { target: 'allAllies', kind: 'buff', element: 'aether', power: 0, breakPower: 0, anim: 'cast', melee: false, status: { id: 'defUp', turns: 3, chance: 1 } }),
];
export const ART_SKILLS: Record<string, SkillDef> = Object.fromEntries(ARTS.map((a) => [a.skill.id, a.skill]));
// arts resolve through the same skill table as everything else (battle menus, level-up notes)
Object.assign(SKILLS, ART_SKILLS);

/** Element totals per line, including +1 for each same-element pair in neighbouring slots. */
export function lineTotals(board: BoardDef, slots: (string | null)[]) {
  return board.lines.map((line) => {
    const t: Partial<Record<Element, number>> = {};
    line.forEach((i, k) => {
      const p = slots[i] ? PARTS[slots[i]!] : null;
      if (!p) return;
      for (const [e, v] of Object.entries(p.elem)) t[e as Element] = (t[e as Element] ?? 0) + (v ?? 0);
      const prev = k > 0 && slots[line[k - 1]] ? PARTS[slots[line[k - 1]]!] : null;
      if (prev) for (const e of Object.keys(p.elem) as Element[]) if (prev.elem[e]) t[e] = (t[e] ?? 0) + 1;
    });
    return t;
  });
}

/** The hero's arts whose requirement is met by at least one line. */
export function artsFor(hero: 'kai' | 'lyra', slots: (string | null)[]) {
  const lines = lineTotals(BOARDS[hero], slots);
  return ARTS.filter((a) => a.who === hero && lines.some((t) => Object.entries(a.need).every(([e, v]) => (t[e as Element] ?? 0) >= (v ?? 0))));
}

/** 속성 결정 a defeated species leaves: its first elemental move's element (else 강철), more for tougher tiers. */
export function crystalDrop(sp: SpeciesDef): [Element, number] {
  const el = sp.moves.find((m) => m.element !== 'phys')?.element ?? 'phys';
  const n = sp.tier === 'elite' ? 6 : sp.tier === 'strong' ? 3 : 1 + Math.round(Math.random());
  return [el, n];
}
