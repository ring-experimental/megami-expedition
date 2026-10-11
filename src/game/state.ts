import { HEROES, SPECIES, allyStats, heroStats, xpToNext } from '../data/units';
import type { Difficulty, Element, Stats } from '../data/types';
import { SKILLS } from '../data/skills';

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
  /** Story / quest progress: free-form counters and switches keyed by id. */
  flags: Record<string, number> = {};

  constructor() {
    for (const h of Object.values(HEROES)) {
      const m: Member = { id: h.id, kind: 'hero', name: h.name, level: 4, xp: 0, hp: 0, model: h.model, color: h.color };
      m.hp = this.stats(m).hp;
      this.roster.push(m);
    }
    for (const id of Object.keys(SPECIES)) this.bestiary[id] = { seen: false, recruited: false, absorbed: 0, known: [] };
  }

  member(id: string) {
    return this.roster.find((m) => m.id === id)!;
  }

  stats(m: Member): Stats {
    if (m.kind === 'hero') return heroStats(HEROES[m.id as 'kai' | 'lyra'], m.level);
    return allyStats(SPECIES[m.id], m.level);
  }

  skillsOf(m: Member): string[] {
    if (m.kind === 'hero') return HEROES[m.id as 'kai' | 'lyra'].skills.filter((s) => s.level <= m.level).map((s) => s.id);
    return SPECIES[m.id].allySkills.filter((id) => SKILLS[id]);
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
