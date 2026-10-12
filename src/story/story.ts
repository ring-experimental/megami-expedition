import * as THREE from 'three';
import { Sfx } from '../core/audio';
import { Dialogue, type Line } from '../ui/dialogue';
import { State } from '../game/state';
import { ITEMS } from '../data/items';
import { PARTS, CRYSTAL_NAME } from '../data/parts';
import { SPECIES } from '../data/units';
import type { Element } from '../data/types';
import { icon } from '../ui/art';
import type { Game } from '../game/game';
import type { BattleEvent, BattleReport, BattleResult } from '../battle/battle';
import { Chapter1 } from './chapter1';

/** A scene line: [speaker, text] — the speaker picks the portrait (see SPEAKERS). */
export type L = [string, string];

/** Display name → portrait id / colour. Unknown names are narration-style system voices. */
const SPEAKERS: Record<string, { pid: string; color: string }> = {
  카이: { pid: 'kai', color: '#e2a64a' },
  리라: { pid: 'lyra', color: '#b77bff' },
  티크: { pid: 'cograt', color: '#b8673a' },
  마르타: { pid: 'marta', color: '#2f4a3a' },
  '마르타(무전)': { pid: 'marta', color: '#2f4a3a' },
  피페: { pid: 'pippe', color: '#5a3a24' },
  바일: { pid: 'bail', color: '#9aa0a8' },
  '바일(무전)': { pid: 'bail', color: '#9aa0a8' },
  포피: { pid: 'poppy', color: '#c8283a' },
  베르디: { pid: 'verdi', color: '#5e7a5a' },
  '상점 주인': { pid: 'shopkeeper', color: '#6a4a30' },
  '도윈(메모)': { pid: '', color: '' },
  '광채 3세': { pid: 'beetle', color: '#c9a14a' },
  '문지기 기사': { pid: 'knight', color: '#8a6a2c' },
  '톱니쥐(두목)': { pid: 'cograt', color: '#b8673a' },
};
for (const sp of Object.values(SPECIES)) SPEAKERS[sp.name] ??= { pid: sp.id, color: sp.color };

export interface Reward { items?: Record<string, number>; money?: number; parts?: Record<string, number>; crystals?: Partial<Record<Element, number>> }
export interface PreBattle { proceed: boolean; event?: BattleEvent; advantage?: 'party' | 'enemy' | 'none' }

/**
 * Story engine: field conversations, flags, rewards, story battles and the objective tracker.
 * Chapter content (story/chapter1.ts) is written against this API; FieldMode / Game call the hooks.
 */
export class Story {
  dlg: Dialogue;
  ch: Chapter1;
  private busyArea = false;

  constructor(public game: Game) {
    this.dlg = new Dialogue(game.ui);
    this.ch = new Chapter1(this);
  }

  get st() { return State.current; }
  get field() { return this.game.field; }
  flag(id: string) { return this.st.flag(id); }
  set(id: string, v = 1) { this.st.setFlag(id, v); }

  // ---------------------------------------------------------------------
  // Scene helpers
  // ---------------------------------------------------------------------
  line([who, text]: L): Line {
    if (who === '내레이션') return { who: '', text };
    const sp = SPEAKERS[who];
    return { who, text, pid: sp?.pid || undefined, color: sp?.color };
  }

  /** Play lines, then close the band. */
  async say(...lines: L[]) {
    for (const l of lines) await this.dlg.say(this.line(l));
    this.dlg.close();
  }

  /** Narration over a black screen (openings, title cards). */
  async black(...lines: string[]) {
    this.dlg.setBlack(true);
    for (const t of lines) await this.dlg.say({ who: '', text: t });
    this.dlg.close();
    this.dlg.setBlack(false);
  }

  async ask(l: L, options: string[]) {
    const i = await this.dlg.choose(this.line(l), options);
    this.dlg.close();
    return i;
  }

  toast(html: string, cls = 'gold', ms = 3200) {
    this.game.ui.toast(html, cls, ms);
  }

  give(r: Reward, note = '') {
    const st = this.st;
    const parts: string[] = [];
    for (const [id, n] of Object.entries(r.items ?? {})) { st.addItem(id, n); parts.push(`${icon('item', id, ITEMS[id].icon)} ${ITEMS[id].name} ×${n}`); }
    for (const [id, n] of Object.entries(r.parts ?? {})) { st.parts[id] = (st.parts[id] ?? 0) + n; parts.push(`부품 <b>${PARTS[id].name}</b>`); }
    if (r.crystals) { st.addCrystals(r.crystals); for (const [e, n] of Object.entries(r.crystals)) parts.push(`${icon('el', e, '◆')} ${CRYSTAL_NAME[e as Element]} ×${n}`); }
    if (r.money) { st.money += r.money; parts.push(`⚙ ${r.money} 기어`); }
    if (parts.length) { Sfx.play('chest'); this.toast(`${note ? `<b>${note}</b> · ` : ''}${parts.join(' · ')}`, 'gold', 4200); }
  }

  /** Recruit outside battle (quest rewards): joins with a fixed name/level. */
  recruit(species: string, level: number, name?: string) {
    const r = this.st.recruit(species, level);
    if (name && !r.absorbed) r.member.name = name;
    Sfx.play('recruit');
    this.toast(r.absorbed ? `<b>${SPECIES[species].name}</b>이(가) 동료에게 합류해 경험치가 되었다` : `<b>${r.member.name}</b>이(가) 동료가 되었다! ${this.st.active.includes(species) ? '(파티 참가)' : '(대기 · 메뉴에서 편성)'}`, 'gold', 4000);
    return r;
  }

  async fade(fn: () => void | Promise<void>, ms = 400) {
    await this.game.ui.fadeOut(ms);
    await fn();
    await this.game.ui.fadeIn(ms);
  }

  /** Story battle started from a scene (no field enemy). */
  async battle(formation: string[], event: BattleEvent, advantage: 'party' | 'enemy' | 'none' = 'none') {
    const r = await this.game.startBattle({ formation, leaderHp: 1, advantage, source: null, event });
    this.refresh();
    return r;
  }

  /** Camera swing to a point (e.g. the clock tower's hands). */
  async look(pos: [number, number, number], at: [number, number, number], sec: number) {
    this.field.lookAt(new THREE.Vector3(...pos), new THREE.Vector3(...at), sec);
    await new Promise((r) => setTimeout(r, sec * 1000));
  }

  /** Re-evaluate the objective tracker and flag-driven actors. */
  refresh() {
    const f = this.game.field;
    if (!f) return;
    const o = this.ch.objective();
    f.hud.setGoal(o.text, o.pos, this.trackedQuest());
    f.refreshActors();
    f.refreshLights();
  }

  /** The quest picked with 수첩 → 찾기, while it is still open or in progress (finished ones untrack themselves). */
  trackedQuest() {
    const id = this.st.tracked;
    if (!id) return null;
    const q = this.ch.quests().find((v) => v.id === id);
    if (q && (q.state === 'open' || q.state === 'active')) return q;
    this.st.tracked = null;
    return null;
  }

  // ---------------------------------------------------------------------
  // Hooks (FieldMode / Game)
  // ---------------------------------------------------------------------
  async onNewGame() { await this.ch.opening(); this.refresh(); }
  async talk(npc: string) { await this.ch.talk(npc); this.refresh(); }
  async spot(id: string) { await this.ch.spot(id); this.refresh(); }
  async rest() { await this.ch.rest(); this.refresh(); }
  async onEnterZone(zone: string) { await this.ch.enterZone(zone); this.refresh(); }
  onFusion(species: string) { this.ch.onFusion(species); this.refresh(); }

  async preBattle(spawn: string): Promise<PreBattle> {
    const r = await this.ch.preBattle(spawn);
    this.refresh();
    return r;
  }

  async afterSpawnBattle(spawn: string, result: BattleResult, report: BattleReport) {
    await this.ch.afterSpawnBattle(spawn, result, report);
    this.refresh();
  }

  /** Area triggers: checked every field frame; one runs at a time as a cutscene. */
  tickArea(zone: string, pos: THREE.Vector3) {
    if (this.busyArea || this.field.inCutscene) return;
    const a = this.ch.areaAt(zone, pos.x, pos.z);
    if (!a) return;
    this.busyArea = true;
    void this.field.cutscene(async () => { await a(); this.refresh(); }).finally(() => { this.busyArea = false; });
  }
}
