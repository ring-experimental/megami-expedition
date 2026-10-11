import { Input, K } from '../core/input';
import { Sfx } from '../core/audio';
import { el } from '../core/utils';
import { portraitInner, type Expression } from './art';
import { bindInput, pb } from './glyph';
import type { UI } from './ui';
import './dialogue.css';

/** One line of a field scene. `who` is a display name; `pid` picks the portrait (none = narration). */
export interface Line { who: string; text: string; pid?: string; face?: Expression; color?: string }

const esc = (t: string) => t.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c]!);

/**
 * Field conversations (story beats, NPCs, camp talks). Composition: a slanted ink band across the
 * bottom; the speaker's portrait stands on the band — party on the left, everyone else on the
 * right, so who is talking reads at a glance. Narration drops the portrait and dims the band.
 * Advance: E / Enter / Space / F / click (A on a pad); the first press finishes the line.
 */
export class Dialogue {
  private root: HTMLElement | null = null;
  private off: (() => void) | null = null;
  private advance: (() => void) | null = null;
  private pick: { i: number; n: number; set: (i: number) => void; done: () => void } | null = null;

  constructor(private ui: UI) {}

  get open() { return !!this.root; }

  private black = false;
  /** Narration over a black screen (the band sits on solid ink). */
  setBlack(v: boolean) {
    this.black = v;
    this.root?.classList.toggle('black', v);
  }

  private ensure() {
    if (this.root) return this.root;
    const r = el('div', 'fdlg', `<div class="fd-por left"></div><div class="fd-por right"></div>
      <div class="fd-band"><div class="fd-name"></div><div class="fd-text"></div><div class="fd-choices"></div><div class="fd-next"></div></div>`, this.ui.topLayer);
    bindInput(r.querySelector('.fd-next') as HTMLElement, (s) => (s.device === 'pad' ? pb('a') : '▼'));
    r.addEventListener('click', () => this.advance?.());
    this.off = Input.listen((code) => {
      if (this.pick) {
        if (K.up.includes(code) || K.left.includes(code)) this.pick.set(this.pick.i - 1);
        else if (K.down.includes(code) || K.right.includes(code)) this.pick.set(this.pick.i + 1);
        else if (['Enter', 'Space', 'KeyE', 'KeyF', 'PadA', 'NumpadEnter'].includes(code)) this.pick.done();
        else if (/^Digit[1-9]$/.test(code)) { const i = +code.slice(5) - 1; if (i < this.pick.n) { this.pick.set(i); this.pick.done(); } }
        return;
      }
      if (['Enter', 'Space', 'KeyE', 'KeyF', 'PadA', 'NumpadEnter', 'Mouse0'].includes(code)) this.advance?.();
    }) as unknown as () => void;
    this.root = r;
    r.classList.toggle('black', this.black);
    return r;
  }

  close() {
    this.off?.();
    this.off = null;
    this.root?.remove();
    this.root = null;
    this.advance = null;
    this.pick = null;
  }

  private show(line: Line) {
    const r = this.ensure();
    const party = line.pid === 'kai' || line.pid === 'lyra';
    const narr = !line.pid;
    r.classList.toggle('narr', narr);
    const left = r.querySelector('.fd-por.left') as HTMLElement;
    const right = r.querySelector('.fd-por.right') as HTMLElement;
    const slot = party ? left : right;
    const other = party ? right : left;
    other.classList.remove('on');
    if (!narr) {
      if (slot.dataset.pid !== line.pid || slot.dataset.face !== (line.face ?? '')) {
        slot.innerHTML = `<div class="fp-in" style="--c:${line.color ?? '#6b5420'}">${portraitInner(line.pid!, line.who, line.face)}</div>`;
        slot.dataset.pid = line.pid;
        slot.dataset.face = line.face ?? '';
      }
      slot.classList.add('on');
    } else slot.classList.remove('on');
    const name = r.querySelector('.fd-name') as HTMLElement;
    name.textContent = narr ? '' : line.who;
    name.classList.toggle('right', !party && !narr);
    (r.querySelector('.fd-choices') as HTMLElement).innerHTML = '';
    return r.querySelector('.fd-text') as HTMLElement;
  }

  /** Typewriter line; resolves when the player advances past it. */
  say(line: Line): Promise<void> {
    const tEl = this.show(line);
    const r = this.root!;
    return new Promise((resolve) => {
      let i = 0;
      let timer = 0;
      r.classList.remove('done');
      const finish = () => {
        clearInterval(timer);
        i = line.text.length;
        tEl.innerHTML = esc(line.text);
        r.classList.add('done');
        this.advance = () => { Sfx.play('ui_move'); this.advance = null; resolve(); };
      };
      this.advance = finish;
      timer = window.setInterval(() => {
        i++;
        if (i >= line.text.length) { finish(); return; }
        tEl.innerHTML = `${esc(line.text.slice(0, i))}<span class="fd-ghost">${esc(line.text.slice(i))}</span>`;
        if (i % 3 === 0) Sfx.play('talk_blip');
      }, 24);
    });
  }

  /** Lines in order. */
  async play(lines: Line[]) {
    for (const l of lines) await this.say(l);
  }

  /** Question with answer blades (W/S or ↑↓, number keys, click). */
  choose(line: Line, options: string[]): Promise<number> {
    const tEl = this.show(line);
    tEl.innerHTML = esc(line.text);
    const r = this.root!;
    r.classList.add('done', 'asking');
    const box = r.querySelector('.fd-choices') as HTMLElement;
    const els = options.map((o, i) => el('div', 'fd-opt', `<span class="n">${i + 1}</span>${o}`, box));
    return new Promise((resolve) => {
      const set = (i: number) => {
        const n = els.length;
        const k = ((i % n) + n) % n;
        if (this.pick && k !== this.pick.i) Sfx.play('ui_move');
        if (this.pick) this.pick.i = k;
        els.forEach((e, j) => e.classList.toggle('sel', j === k));
      };
      const done = () => {
        const i = this.pick!.i;
        this.pick = null;
        r.classList.remove('asking');
        Sfx.play('ui_ok');
        resolve(i);
      };
      this.pick = { i: 0, n: els.length, set, done };
      set(0);
      els.forEach((e, i) => {
        e.addEventListener('mouseenter', () => set(i));
        e.addEventListener('click', (ev) => { ev.stopPropagation(); set(i); done(); });
      });
      this.advance = null;
    });
  }
}
