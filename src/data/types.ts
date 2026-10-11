export type Element = 'phys' | 'fire' | 'frost' | 'volt' | 'aether';
export const ELEMENT_NAME: Record<Element, string> = {
  phys: '물리', fire: '화염', frost: '냉기', volt: '번개', aether: '에테르',
};
export const ELEMENT_COLOR: Record<Element, number> = {
  phys: 0xfff1d0, fire: 0xff7a2a, frost: 0x8fe8ff, volt: 0xfff04a, aether: 0xc58bff,
};

export interface Stats { hp: number; atk: number; mag: number; def: number; res: number; spd: number; }

export type StatusId = 'atkUp' | 'defUp' | 'haste' | 'burn' | 'guard' | 'atkDown' | 'enraged';
export const STATUS_INFO: Record<StatusId, { name: string; icon: string; good: boolean }> = {
  atkUp: { name: '공격↑', icon: '⚔', good: true },
  defUp: { name: '방어↑', icon: '🛡', good: true },
  haste: { name: '가속', icon: '⏩', good: true },
  guard: { name: '도발', icon: '◎', good: true },
  burn: { name: '화상', icon: '🔥', good: false },
  atkDown: { name: '공격↓', icon: '↓', good: false },
  enraged: { name: '격노', icon: '💢', good: false },
};

export type Difficulty = 'story' | 'normal' | 'hard';
export const DIFFICULTY: Record<Difficulty, {
  name: string; desc: string;
  parry: number; dodge: number; qtePerfect: number; qteGood: number;
  enemyDmg: number; showRing: boolean;
}> = {
  story: { name: '스토리', desc: '패링 판정이 넉넉합니다. 타이밍 링이 표시됩니다.', parry: 0.16, dodge: 0.26, qtePerfect: 0.09, qteGood: 0.2, enemyDmg: 0.7, showRing: true },
  normal: { name: '노말', desc: '33원정대 기본에 가까운 판정. 타이밍 링이 표시됩니다.', parry: 0.095, dodge: 0.18, qtePerfect: 0.06, qteGood: 0.14, enemyDmg: 1, showRing: true },
  hard: { name: '하드', desc: '좁은 판정, 타이밍 링 없음. 적의 동작을 읽어야 합니다.', parry: 0.055, dodge: 0.115, qtePerfect: 0.04, qteGood: 0.1, enemyDmg: 1.25, showRing: false },
};

/** Battle choreography speeds (settings / Tab · Y in battle). */
export const BATTLE_SPEEDS = [1, 1.5, 2];
