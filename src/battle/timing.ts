import { Input, K } from '../core/input';
import type { Timeline } from '../core/timeline';
import { DIFFICULTY, type Difficulty } from '../data/types';

export type DefenseResult = 'parry' | 'dodge' | 'hit';

/**
 * Expedition-33 style defense: each incoming hit has a time; the player may parry (tight window,
 * grants AP + counter when all hits are parried) or dodge (wider window, no reward).
 * Mashing is punished with a short lockout after a whiffed input.
 */
export class DefenseSession {
  private hits: { t: number; result: DefenseResult | null; cb: (r: DefenseResult) => void }[] = [];
  private lockUntil = -1;
  private off: () => void;
  onWhiff: ((kind: 'parry' | 'dodge') => void) | null = null;
  private late = 0.1;

  constructor(private tl: Timeline, private diff: Difficulty) {
    this.off = Input.listen((code, ms) => this.onKey(code, ms)) as unknown as () => void;
  }

  addHit(t: number, cb: (r: DefenseResult) => void) {
    this.hits.push({ t, result: null, cb });
  }

  private onKey(code: string, ms: number) {
    const kind = K.parry.includes(code) ? 'parry' : K.dodge.includes(code) ? 'dodge' : null;
    if (!kind) return;
    const t = this.tl.at(ms);
    if (t < this.lockUntil) return;
    const d = DIFFICULTY[this.diff];
    const w = kind === 'parry' ? d.parry : d.dodge;
    const h = this.hits.find((x) => !x.result && t >= x.t - w && t <= x.t + Math.min(w * 0.6, this.late));
    if (h) {
      h.result = kind;
      h.cb(kind);
      this.lockUntil = t + 0.08;
    } else {
      // only penalize presses reasonably close to an upcoming hit
      this.lockUntil = t + (kind === 'parry' ? 0.38 : 0.3);
      this.onWhiff?.(kind);
    }
  }

  update(now: number) {
    for (const h of this.hits) {
      if (!h.result && now > h.t + this.late) {
        h.result = 'hit';
        h.cb('hit');
      }
    }
  }

  get done() {
    return this.hits.every((h) => h.result);
  }
  get results() {
    return this.hits.map((h) => h.result);
  }

  dispose() {
    this.off();
  }
}

export type QteGrade = 'perfect' | 'good' | 'miss';

/** Skill QTE: press when the ring closes. */
export class QteSession {
  private prompts: { t: number; grade: QteGrade | null; cb: (g: QteGrade) => void }[] = [];
  private off: () => void;
  private lockUntil = -1;

  constructor(private tl: Timeline, private diff: Difficulty) {
    this.off = Input.listen((code, ms) => this.onKey(code, ms)) as unknown as () => void;
  }

  add(t: number, cb: (g: QteGrade) => void) {
    this.prompts.push({ t, grade: null, cb });
  }

  private onKey(code: string, ms: number) {
    if (!K.qte.includes(code)) return;
    const t = this.tl.at(ms);
    if (t < this.lockUntil) return;
    const d = DIFFICULTY[this.diff];
    const p = this.prompts.find((x) => !x.grade && t >= x.t - 0.45);
    if (!p) return;
    const err = Math.abs(t - p.t);
    p.grade = err <= d.qtePerfect ? 'perfect' : err <= d.qteGood ? 'good' : 'miss';
    if (p.grade === 'miss') this.lockUntil = t + 0.2;
    p.cb(p.grade);
  }

  update(now: number) {
    const d = DIFFICULTY[this.diff];
    for (const p of this.prompts) {
      if (!p.grade && now > p.t + d.qteGood) {
        p.grade = 'miss';
        p.cb('miss');
      }
    }
  }

  dispose() {
    this.off();
  }
}

export const QTE_MULT: Record<QteGrade, number> = { perfect: 1.3, good: 1.1, miss: 0.8 };
