import { HEROES, SPECIES, allyStats, heroStats, xpToNext } from '../data/units';
import type { Difficulty, Element, Stats } from '../data/types';
import { SKILLS } from '../data/skills';
import { BOARDS, PARTS, artsFor, type CrystalCost, type PartEffect } from '../data/parts';
import { MAX_INHERITED } from '../data/fusion';

/** A persistent party member (hero or recruited monster). */
export interface Member {
  id: string;            // 'kai' | 'lyra' | species id
  kind: 'hero' | 'monster';
  name: string;
  level: number;
  xp: number;
  hp: number;
  model: string;
  color: string;
  /** Monsters: skills inherited at the 공방 (max 2). */
  inherited?: string[];
  /** Story-named individual (티크…): never a fusion material. */
  locked?: boolean;
}

export interface LevelUpInfo { id: string; name: string; from: number; to: number; newSkills: string[] }

export class GameState {
  difficulty: Difficulty = 'normal';
  roster: Member[] = [];
  active: string[] = ['kai', 'lyra'];
  inventory: Record<string, number> = { tonic: 5, hi_tonic: 1, capsule: 2, heart: 2 };
  money = 120;
  defeated = new Set<string>();
  openedChests = new Set<string>();
  /** `known`: affinities (weak/resist) the player has discovered by hitting this species with the element. */
  bestiary: Record<string, { seen: boolean; recruited: boolean; absorbed: number; known: Element[] }> = {};
  showParryRing = true;
  mouseSens = 1;
  padSens = 1;
  tutorialField = false;
  /** Battle tips already shown (battle/tips.ts); cleared from Menu → 조작법 to see them again. */
  tipsSeen = new Set<string>();
  /** Battle choreography speed (×1 / ×1.5 / ×2); timing windows are unaffected. */
  battleSpeed = 1;
  /** Seconds of play (field + battle; menus excluded), shown on save slots. */
  playTime = 0;
  /** Where the party stands: zone id + position (written right before saving, read on load). */
  zone = 'plains';
  pos: { x: number; z: number; yaw: number } | null = null;
  /** Last rest point used — where the party wakes after a defeat. */
  lastRest: { zone: string; x: number; z: number } | null = null;
  /** 부품 owned (count) and each hero's board: slot → part id; which slots are open. */
  parts: Record<string, number> = {};
  boards: Record<string, (string | null)[]> = { kai: [null, null, null, null, null], lyra: [null, null, null, null, null, null] };
  boardOpen: Record<string, number[]> = { kai: [...BOARDS.kai.open], lyra: [...BOARDS.lyra.open] };
  /** 친밀도 per party member (0–3; 3 = MAX). Recruits join at 1 — they came willingly. */
  bond: Record<string, number> = { lyra: 1 };
  /** 속성 결정 by element. */
  crystals: Record<Element, number> = { phys: 0, fire: 0, frost: 0, volt: 0, aether: 0 };
  /** Story / quest progress: free-form counters and switches keyed by id. */
  flags: Record<string, number> = {};

  constructor() {
    // Lyra joins in the story (chapter 1, m02)
    this.addHero('kai');
    this.active = ['kai'];
    for (const id of Object.keys(SPECIES)) this.bestiary[id] = { seen: false, recruited: false, absorbed: 0, known: [] };
  }

  addHero(id: 'kai' | 'lyra') {
    if (this.roster.some((m) => m.id === id)) return;
    const h = HEROES[id];
    const m: Member = { id: h.id, kind: 'hero', name: h.name, level: 4, xp: 0, hp: 0, model: h.model, color: h.color };
    m.hp = this.stats(m).hp;
    this.roster.push(m);
    if (!this.active.includes(id) && this.active.length < 3) this.active.push(id);
  }

  has(id: string) {
    return this.roster.some((m) => m.id === id);
  }

  addBond(id: string, d: number) {
    if (!this.has(id) || id === 'kai') return 0;
    this.bond[id] = Math.max(0, Math.min(3, (this.bond[id] ?? 1) + d));
    return this.bond[id];
  }

  member(id: string) {
    return this.roster.find((m) => m.id === id)!;
  }

  stats(m: Member): Stats {
    if (m.kind !== 'hero') return allyStats(SPECIES[m.id], m.level);
    const s = heroStats(HEROES[m.id as 'kai' | 'lyra'], m.level);
    for (const id of this.boards[m.id] ?? []) {
      const b = id ? PARTS[id]?.stats : null;
      if (b) for (const [k, v] of Object.entries(b)) s[k as keyof Stats] += v ?? 0;
    }
    return s;
  }

  skillsOf(m: Member): string[] {
    if (m.kind === 'hero') {
      const own = HEROES[m.id as 'kai' | 'lyra'].skills.filter((s) => s.level <= m.level).map((s) => s.id);
      return [...own, ...this.artsOf(m)];
    }
    const sp = SPECIES[m.id];
    const late = sp.lateSkill && m.level >= sp.lateSkill.level ? [sp.lateSkill.id] : [];
    return [...sp.allySkills, ...late, ...(m.inherited ?? [])].filter((id, i, a) => SKILLS[id] && a.indexOf(id) === i);
  }

  /** Arts unlocked by the hero's board lines. */
  artsOf(m: Member): string[] {
    if (m.kind !== 'hero') return [];
    return artsFor(m.id as 'kai' | 'lyra', this.boards[m.id] ?? []).map((a) => a.skill.id);
  }

  partEffects(m: Member): Set<PartEffect> {
    const out = new Set<PartEffect>();
    if (m.kind === 'hero') for (const id of this.boards[m.id] ?? []) { const e = id ? PARTS[id]?.effect : undefined; if (e) out.add(e); }
    return out;
  }

  /** Copies of a part not slotted on any board. */
  partsFree(id: string) {
    let used = 0;
    for (const b of Object.values(this.boards)) used += b.filter((x) => x === id).length;
    return (this.parts[id] ?? 0) - used;
  }

  addCrystals(c: Partial<Record<Element, number>>) {
    for (const [e, n] of Object.entries(c)) this.crystals[e as Element] += n ?? 0;
  }
  hasCrystals(c: CrystalCost) {
    const total = Object.values(this.crystals).reduce((a, b) => a + b, 0);
    const named = Object.entries(c).filter(([e]) => e !== 'any');
    const namedSum = named.reduce((a, [, n]) => a + (n ?? 0), 0);
    return named.every(([e, n]) => this.crystals[e as Element] >= (n ?? 0)) && total - namedSum >= (c.any ?? 0);
  }
  spendCrystals(c: CrystalCost) {
    if (!this.hasCrystals(c)) return false;
    for (const [e, n] of Object.entries(c)) if (e !== 'any') this.crystals[e as Element] -= n ?? 0;
    // "any": take from the largest stocks first
    for (let k = c.any ?? 0; k > 0; k--) {
      const e = (Object.keys(this.crystals) as Element[]).sort((a, b) => this.crystals[b] - this.crystals[a])[0];
      this.crystals[e]--;
    }
    return true;
  }

  activeMembers() {
    return this.active.map((id) => this.member(id)).filter(Boolean);
  }

  healAll() {
    for (const m of this.roster) m.hp = this.stats(m).hp;
  }

  /** Grants XP, returns level-ups. */
  giveXp(m: Member, amount: number): LevelUpInfo | null {
    const from = m.level;
    const before = this.skillsOf(m);
    m.xp += amount;
    while (m.xp >= xpToNext(m.level) && m.level < 50) {
      m.xp -= xpToNext(m.level);
      const oldMax = this.stats(m).hp;
      m.level++;
      m.hp += this.stats(m).hp - oldMax;
    }
    if (m.level === from) return null;
    const after = this.skillsOf(m);
    return { id: m.id, name: m.name, from, to: m.level, newSkills: after.filter((s) => !before.includes(s)) };
  }

  /**
   * Recruit a species. If already owned, the newcomer is absorbed as bonus XP
   * into the existing ally of that species (design decision).
   */
  recruit(speciesId: string, level: number): { absorbed: boolean; member: Member; xp: number; levelUp: LevelUpInfo | null } {
    const sp = SPECIES[speciesId];
    const existing = this.roster.find((m) => m.id === speciesId);
    this.bestiary[speciesId].recruited = true;
    if (existing) {
      const xp = Math.round(xpToNext(existing.level) * 0.85 + sp.xp * 2);
      this.bestiary[speciesId].absorbed++;
      const levelUp = this.giveXp(existing, xp);
      return { absorbed: true, member: existing, xp, levelUp };
    }
    const m: Member = { id: sp.id, kind: 'monster', name: sp.name, level, xp: 0, hp: 0, model: sp.model, color: sp.color };
    m.hp = this.stats(m).hp;
    this.roster.push(m);
    this.bond[m.id] = 1;
    if (this.active.length < 3) this.active.push(m.id);
    return { absorbed: false, member: m, xp: 0, levelUp: null };
  }

  flag(id: string) {
    return this.flags[id] ?? 0;
  }
  setFlag(id: string, v = 1) {
    this.flags[id] = v;
  }

  chapterTitle() {
    return '제1장';
  }

  /** Plain JSON: Sets become arrays (tagged so fromJSON can restore them). */
  toJSON(): Record<string, unknown> {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(this)) out[k] = v instanceof Set ? { __set: [...v] } : v;
    return out;
  }

  /**
   * Rebuild from toJSON() output. Starts from a fresh state and overlays the saved fields, so a
   * save made before a field existed still loads (the field keeps its default), and nested records
   * like the bestiary keep entries for species added since.
   */
  static fromJSON(data: unknown): GameState {
    const st = new GameState();
    if (!data || typeof data !== 'object') throw new Error('bad save');
    const target = st as unknown as Record<string, unknown>;
    for (const [k, v] of Object.entries(data as Record<string, unknown>)) {
      if (!(k in target)) continue;
      const cur = target[k];
      if (cur instanceof Set) target[k] = new Set((v as { __set?: unknown[] })?.__set ?? []);
      else if (cur && typeof cur === 'object' && !Array.isArray(cur) && v && typeof v === 'object' && !Array.isArray(v)) Object.assign(cur, v);
      else target[k] = v;
    }
    return st;
  }

  /** 공방 inheritance: the material leaves, the base learns one of its skills (oldest forgotten past the cap). */
  inherit(baseId: string, matId: string, skill: string) {
    const base = this.member(baseId);
    base.inherited = [...(base.inherited ?? []).filter((s) => s !== skill), skill].slice(-MAX_INHERITED);
    const mat = this.member(matId);
    this.giveXp(base, Math.round(xpToNext(base.level) * 0.3 + mat.level * 4));
    this.removeMember(matId);
  }

  /** 공방 fusion: both leave, a new species joins at their average level (+1). */
  fuse(aId: string, bId: string, result: string) {
    const lv = Math.round((this.member(aId).level + this.member(bId).level) / 2) + 1;
    this.removeMember(aId);
    this.removeMember(bId);
    this.bestiary[result].seen = true;
    if (this.roster.some((m) => m.id === result)) { this.recruit(result, lv); return this.member(result); }
    return this.recruit(result, lv).member;
  }

  private removeMember(id: string) {
    this.roster = this.roster.filter((m) => m.id !== id);
    this.active = this.active.filter((x) => x !== id);
  }

  addItem(id: string, n = 1) {
    this.inventory[id] = (this.inventory[id] ?? 0) + n;
  }
  useItem(id: string) {
    if ((this.inventory[id] ?? 0) <= 0) return false;
    this.inventory[id]--;
    return true;
  }
}

export const State = { current: new GameState() };
