/**
 * Device-dependent UI. Anything that names a key or button renders from Input.subscribe(), so it
 * flips the moment the player switches between keyboard/mouse and a pad. Pad button *labels*
 * (A vs ✕ vs B…) come from CSS keyed on `body[data-pad]`, which Game's subscriber keeps current.
 */
import { Input, type InputState } from '../core/input';

export type PadButton = 'a' | 'b' | 'x' | 'y' | 'lb' | 'rb' | 'lt' | 'rt' | 'start' | 'back' | 'ls' | 'rs' | 'l3' | 'r3' | 'dpad' | 'dud' | 'dl';

/** A gamepad button glyph (label comes from CSS). */
export const pb = (b: PadButton) => `<kbd class="pb pb-${b}"></kbd>`;

/**
 * Render `el` from the input state now and on every device change. The subscription drops itself
 * once the element has left the DOM, so short-lived UI (rings, panels, toasts) can bind freely.
 */
export function bindInput(el: HTMLElement, render: (s: InputState) => string) {
  let attached = false;
  const off = Input.subscribe((s) => {
    if (attached && !el.isConnected) { off(); return; }
    attached ||= el.isConnected;
    el.innerHTML = render(s);
  });
  return el;
}

/** HTML-safe controller name; `full` keeps the browser's "(… Vendor: xxxx Product: xxxx)" part. */
export function padName(gp: { id: string }, full = false) {
  const id = full ? gp.id : gp.id.replace(/\s*\([^)]*(?:STANDARD GAMEPAD|Vendor:)[^)]*\)\s*$/i, '').trim() || gp.id;
  return id.slice(0, 90).replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`);
}
