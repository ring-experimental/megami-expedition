import { Input, K } from '../core/input';
import { Sfx } from '../core/audio';
import { el } from '../core/utils';
import { bindInput, pb } from './glyph';
import './backlog.css';

/**
 * 대사 기록 (backlog): the last conversations, grouped into scenes. Field talks, story narration and
 * battle negotiations all write here; answers the player picked are kept as their own lines.
 * Session only (not saved). Opened from a conversation (Y / L) and in the field (L / D-pad left).
 */
export interface LogLine { who: string; text: string; color?: string; kind?: 'narr' | 'pick' }
interface Scene { place: string; lines: LogLine[] }

const MAX_LINES = 200;
const esc = (t: string) => t.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c]!);
const plain = (html: string) => html.replace(/<[^>]*>/g, '');

class BacklogStore {
  private scenes: Scene[] = [];
  private open = false;
  /** label for a new scene (the zone the party is in); set by Game */
  place: () => string = () => '';

  add(l: LogLine) {
    if (!this.open || !this.scenes.length) { this.scenes.push({ place: this.place(), lines: [] }); this.open = true; }
    this.scenes[this.scenes.length - 1].lines.push({ ...l, text: plain(l.text) });
    // drop the oldest lines past the cap (and scenes left empty)
    let n = this.scenes.reduce((a, s) => a + s.lines.length, 0);
    while (n > MAX_LINES) {
      this.scenes[0].lines.shift();
      n--;
      if (!this.scenes[0].lines.length) this.scenes.shift();
    }
  }

  /** The conversation ended: the next line starts a new scene. */
  end() { this.open = false; }

  clear() { this.scenes = []; this.open = false; }

  get empty() { return !this.scenes.length; }

  /** The log as HTML, oldest first (the newest line is at the bottom, like the dialogue band). */
  html() {
    return this.scenes.map((s) => `<div class="bl-scene"><div class="bl-place">${esc(s.place || '—')}</div>${s.lines.map((l) =>
      l.kind === 'pick' ? `<div class="bl-line pick"><span class="bl-who">▸ 선택</span><p>${esc(l.text)}</p></div>`
        : !l.who ? `<div class="bl-line narr"><p>${esc(l.text)}</p></div>`
          : `<div class="bl-line"><span class="bl-who" style="--c:${l.color || 'var(--gold-dk)'}">${esc(l.who)}</span><p>${esc(l.text)}</p></div>`).join('')}</div>`).join('');
  }
}
export const Backlog = new BacklogStore();

/** Keys that open / close the backlog from a conversation. */
export const BACKLOG_KEYS = ['KeyL', 'PadY'];
/** Keys that open / close it in the field (Y is the heavy attack, D-pad up/down zoom; left is free). */
export const FIELD_BACKLOG_KEYS = ['KeyL', 'PadLeft'];

/**
 * Full-screen backlog over a conversation: the log scrolled to the newest line, ↑↓ / stick scroll,
 * Y · L · B · Esc close. Resolves when it closes; the conversation underneath waits.
 */
export function showBacklog(layer: HTMLElement, keys: string[] = BACKLOG_KEYS): Promise<void> {
  Sfx.play('ui_ok');
  const r = el('div', 'backlog', `<div class="bl-head"><span class="bl-title">Log</span><span class="bl-sub">대사 기록</span></div><div class="bl-keys"></div>
    <div class="bl-body">${Backlog.empty ? '<div class="bl-empty">아직 기록된 대사가 없습니다.</div>' : Backlog.html()}</div>`, layer);
  const body = r.querySelector('.bl-body') as HTMLElement;
  body.scrollTop = body.scrollHeight;
  bindInput(r.querySelector('.bl-keys') as HTMLElement, (s) => s.device === 'pad'
    ? `${pb('dud')}<span>스크롤</span>${pb(keys.includes('PadLeft') ? 'dl' : 'y')}${pb('b')}<span>닫기</span>`
    : '<kbd>↑</kbd><kbd>↓</kbd><span>스크롤</span><kbd>L</kbd><kbd>Esc</kbd><span>닫기</span>');
  return new Promise((resolve) => {
    let off: (() => void) | null = null;
    const close = () => {
      off?.();
      // the key that closed the log must not also act underneath (Esc → pause, B → back)
      Input.consumePressed();
      Sfx.play('ui_back');
      r.classList.add('out');
      setTimeout(() => r.remove(), 140);
      resolve();
    };
    // wait one frame so the key that opened it does not close it again
    requestAnimationFrame(() => {
      off = Input.listen((code) => {
        if (K.up.includes(code)) body.scrollBy({ top: -90 });
        else if (K.down.includes(code)) body.scrollBy({ top: 90 });
        else if ([...keys, 'PadB', 'Escape', 'Backspace'].includes(code)) close();
      }) as unknown as () => void;
    });
    r.addEventListener('click', (e) => { if (!(e.target as HTMLElement).closest('.bl-body')) close(); });
  });
}
