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
