import { Input } from '../core/input';
import { Sfx } from '../core/audio';
import { clamp } from '../core/utils';

const FOCUSABLE = 'button, .rc:not(.locked), .opt, .mn-focus';

/** A focusable row that ←/→ adjusts in place (settings ◀ value ▶) instead of moving focus. */
export type Adjustable = HTMLElement & { adjust?: (dir: number) => void };

/** Keyboard keys that drive menu focus (the pad has its own; the mouse just hovers). */
const KB = {
  left: ['ArrowLeft', 'KeyA'], right: ['ArrowRight', 'KeyD'], up: ['ArrowUp', 'KeyW'], down: ['ArrowDown', 'KeyS'],
  ok: ['Enter', 'NumpadEnter', 'Space'], prevTab: ['KeyQ'], nextTab: ['KeyE'],
};

/**
 * The focus highlight shows while the menus are driven by pad or keyboard (`body.navfocus`) and
 * hides once the mouse moves — hover is the mouse's highlight.
 */
let installed = false;
function installNavFocus() {
  if (installed) return;
  installed = true;
  const set = (v: boolean) => document.body.classList.toggle('navfocus', v);
  Input.subscribe((s) => { if (s.device === 'pad') set(true); });
  window.addEventListener('mousemove', (e) => { if (e.isTrusted && Input.state.device !== 'pad' && (e.movementX || e.movementY)) set(false); });
}

/**
 * Pad and keyboard focus navigation for DOM menus (title, pause). D-pad/stick or arrows/WASD move
 * a `.pad-focus` highlight to the nearest item in that direction, A or Enter/Space clicks it, ←/→
 * adjust a focused setting row, LB/RB or Q/E switch tabs, Tab/Shift+Tab step through the items.
 * The mouse moves the same focus by hovering, so keys continue from where the pointer was.
 * Uses a class instead of DOM focus; Menus suppresses the browser's own Enter/Space/Tab handling.
 */
export class PadNav {
  private cur: HTMLElement | null = null;
  /** position to restore after the menu re-renders (-1 = pick the screen's default item) */
  private lastIndex = -1;
  private hooked = new WeakSet<HTMLElement>();

  constructor() {
    installNavFocus();
  }

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
    // lets menus mirror pad focus (e.g. a detail panel that follows the focused card)
    e.dispatchEvent(new Event('padfocus'));
  }

  /**
   * @param back keyboard keys that go back here (the pad always uses B). Esc on the pause menu
   *   is left to Game, which guards against the Esc that released the pointer lock.
   */
  update(root: HTMLElement, onBack: () => void, onTab?: (dir: number) => void, back: string[] = ['Escape', 'Backspace']) {
    if (!this.hooked.has(root)) {
      this.hooked.add(root);
      // hovering moves the focus (silently), so the highlight and the keys agree
      root.addEventListener('mouseover', (e) => {
        const t = (e.target as HTMLElement).closest<HTMLElement>(FOCUSABLE);
        if (t && root.contains(t) && !(t as HTMLButtonElement).disabled) this.focus(t);
      });
    }
    const items = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((e) => e.offsetParent !== null && !(e as HTMLButtonElement).disabled);
    if (!items.length) return;
    const kbUsed = [KB.left, KB.right, KB.up, KB.down, KB.ok, KB.prevTab, KB.nextTab, ['Tab']].some((c) => Input.pressed(...c));
    if (kbUsed) document.body.classList.add('navfocus');
    if (!this.cur || !items.includes(this.cur)) {
      const fallback = this.lastIndex < 0 ? items.find((e) => e.dataset.padFirst !== undefined) ?? items[0] : items[Math.min(this.lastIndex, items.length - 1)];
      this.cur = null;
      this.focus(fallback);
    }
    const cur = this.cur!;
    const dx = Input.pressed('PadLeft', 'PadLSLeft', ...KB.left) ? -1 : Input.pressed('PadRight', 'PadLSRight', ...KB.right) ? 1 : 0;
    const dy = dx ? 0 : Input.pressed('PadUp', 'PadLSUp', ...KB.up) ? -1 : Input.pressed('PadDown', 'PadLSDown', ...KB.down) ? 1 : 0;
    const tabStep = Input.pressed('Tab') ? (Input.isDown('ShiftLeft', 'ShiftRight') ? -1 : 1) : 0;
    const range = cur.querySelector<HTMLInputElement>('input[type=range]');
    const adj = (cur as Adjustable).adjust;
    if (adj && dx) {
      adj(dx);
    } else if (range && dx) {
      const step = Number(range.step) || 0.1;
      range.value = String(clamp(Number(range.value) + dx * step, Number(range.min), Number(range.max)));
      range.dispatchEvent(new Event('input'));
      Sfx.play('ui_move');
    } else if (dx || dy) {
      const next = this.nearest(items, dx, dy);
      if (next) { this.focus(next); Sfx.play('ui_move'); }
    } else if (tabStep) {
      // document order, wrapping
      this.focus(items[(items.indexOf(cur) + tabStep + items.length) % items.length]);
      Sfx.play('ui_move');
    } else if (Input.pressed('PadA', ...KB.ok)) {
      const box = cur.querySelector<HTMLInputElement>('input[type=checkbox]');
      if (box) { box.click(); Sfx.play('ui_ok'); }
      else cur.click();
    } else if (Input.pressed('PadB', ...back)) {
      onBack();
    } else if (onTab && Input.pressed('PadLB', 'PadRB', ...KB.prevTab, ...KB.nextTab)) {
      onTab(Input.pressed('PadLB', ...KB.prevTab) ? -1 : 1);
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
