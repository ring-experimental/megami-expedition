import { Input } from '../core/input';
import { Sfx } from '../core/audio';
import { clamp } from '../core/utils';

const FOCUSABLE = 'button, .rc:not(.locked), .opt';

/**
 * Gamepad focus navigation for DOM menus (title, pause). D-pad/stick moves a `.pad-focus`
 * highlight to the nearest item in that direction, A clicks it, ←/→ adjust a focused slider.
 * Uses a class instead of DOM focus so keyboard Enter/Space never double-activate buttons.
 */
export class PadNav {
  private cur: HTMLElement | null = null;
  /** position to restore after the menu re-renders (-1 = pick the screen's default item) */
  private lastIndex = -1;

  /** Call when a new screen is shown so focus starts on its default item. */
  reset() {
    this.cur?.classList.remove('pad-focus');
    this.cur = null;
    this.lastIndex = -1;
  }

  focus(e: HTMLElement) {
    if (this.cur === e) return;
    this.cur?.classList.remove('pad-focus');
    this.cur = e;
    e.classList.add('pad-focus');
    e.scrollIntoView({ block: 'nearest' });
  }

  update(root: HTMLElement, onBack: () => void, onTab?: (dir: number) => void) {
    const items = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((e) => e.offsetParent !== null && !(e as HTMLButtonElement).disabled);
    if (!items.length) return;
    if (!this.cur || !items.includes(this.cur)) {
      const fallback = this.lastIndex < 0 ? items.find((e) => e.dataset.padFirst !== undefined) ?? items[0] : items[Math.min(this.lastIndex, items.length - 1)];
      this.cur = null;
      this.focus(fallback);
    }
    const cur = this.cur!;
    const dx = Input.pressed('PadLeft', 'PadLSLeft') ? -1 : Input.pressed('PadRight', 'PadLSRight') ? 1 : 0;
    const dy = dx ? 0 : Input.pressed('PadUp', 'PadLSUp') ? -1 : Input.pressed('PadDown', 'PadLSDown') ? 1 : 0;
    const range = cur.querySelector<HTMLInputElement>('input[type=range]');
    if (range && dx) {
      const step = Number(range.step) || 0.1;
      range.value = String(clamp(Number(range.value) + dx * step, Number(range.min), Number(range.max)));
      range.dispatchEvent(new Event('input'));
      Sfx.play('ui_move');
    } else if (dx || dy) {
      const next = this.nearest(items, dx, dy);
      if (next) { this.focus(next); Sfx.play('ui_move'); }
    } else if (Input.pressed('PadA')) {
      const box = cur.querySelector<HTMLInputElement>('input[type=checkbox]');
      if (box) { box.click(); Sfx.play('ui_ok'); }
      else cur.click();
    } else if (Input.pressed('PadB')) {
      onBack();
    } else if (onTab && Input.pressed('PadLB', 'PadRB')) {
      onTab(Input.pressed('PadLB') ? -1 : 1);
    }
    if (this.cur) this.lastIndex = Math.max(0, items.indexOf(this.cur));
  }

  /**
   * Closest item ahead in the pressed direction, measured edge to edge: the gap along the direction
   * plus (weighted) the sideways gap between the two spans — 0 when they overlap, so full-width rows
   * and wide buttons line up naturally. Center offset only breaks ties.
   */
  private nearest(items: HTMLElement[], dx: number, dy: number) {
    const a = this.cur!.getBoundingClientRect();
    const acx = a.left + a.width / 2, acy = a.top + a.height / 2;
    let best: HTMLElement | null = null, bestScore = Infinity;
    for (const e of items) {
      if (e === this.cur) continue;
      const r = e.getBoundingClientRect();
      const ocx = r.left + r.width / 2 - acx, ocy = r.top + r.height / 2 - acy;
      if (ocx * dx + ocy * dy <= 4) continue;
      const along = dx > 0 ? r.left - a.right : dx < 0 ? a.left - r.right : dy > 0 ? r.top - a.bottom : a.top - r.bottom;
      if (along < -8) continue;
      const across = dx ? Math.max(0, r.top - a.bottom, a.top - r.bottom) : Math.max(0, r.left - a.right, a.left - r.right);
      const score = Math.max(0, along) + across * 3 + Math.abs(dx ? ocy : ocx) * 0.01;
      if (score < bestScore) { bestScore = score; best = e; }
    }
    return best;
  }
}
