import * as THREE from 'three';
import { el, worldToScreen } from '../core/utils';
import type { InputState } from '../core/input';
import { bindInput } from './glyph';

/** Shared DOM overlay helpers. */
export class UI {
  root: HTMLElement;
  layer: HTMLElement;      // world-anchored elements (bars, numbers)
  hudLayer: HTMLElement;   // mode HUDs
  topLayer: HTMLElement;   // banners / toasts / dialogs
  private fade: HTMLElement;
  private toasts: HTMLElement;
  private anchored: { el: HTMLElement; pos: THREE.Vector3; t: number; dur: number; drift: number }[] = [];
  camera: THREE.Camera | null = null;
  width = window.innerWidth;
  height = window.innerHeight;
  /**
   * UI size factor: layouts are authored for a 720px-tall screen and scale with the window height.
   * HUD/top layers get CSS `zoom`; world-anchored elements (placeAt, popups) scale themselves.
   */
  scale = 1;

  constructor(root: HTMLElement) {
    this.root = root;
    this.layer = el('div', 'layer world-layer', undefined, root);
    this.hudLayer = el('div', 'layer hud-layer', undefined, root);
    this.topLayer = el('div', 'layer top-layer', undefined, root);
    this.toasts = el('div', 'toasts', undefined, this.topLayer);
    this.fade = el('div', 'fade', undefined, root);
    this.resize(this.width, this.height);
  }

  resize(w: number, h: number) {
    this.width = w;
    this.height = h;
    this.scale = Math.min(4, Math.max(0.75, h / 720));
    this.root.style.setProperty('--ui-scale', String(this.scale));
  }

  project(pos: THREE.Vector3) {
    if (!this.camera) return null;
    return worldToScreen(pos, this.camera, this.width, this.height);
  }

  /** Place an element at a world position (call every frame). */
  placeAt(e: HTMLElement, pos: THREE.Vector3, anchor: 'bottom' | 'center' = 'bottom') {
    const p = this.project(pos);
    if (!p) { e.style.display = 'none'; return false; }
    e.style.display = '';
    // scale about the anchor point so the element stays pinned to the world position
    e.style.transformOrigin = anchor === 'bottom' ? '50% 100%' : '50% 50%';
    e.style.transform = `translate(${p.x}px, ${p.y}px) translate(-50%, ${anchor === 'bottom' ? '-100%' : '-50%'}) scale(${this.scale})`;
    return true;
  }

  /** Floating number / text at a world position. */
  popup(pos: THREE.Vector3, html: string, cls = '', dur = 1.0) {
    const e = el('div', 'popup ' + cls, html, this.layer);
    this.anchored.push({ el: e, pos: pos.clone(), t: 0, dur, drift: 0.9 });
  }

  update(dt: number) {
    for (let i = this.anchored.length - 1; i >= 0; i--) {
      const a = this.anchored[i];
      a.t += dt;
      const k = a.t / a.dur;
      const p = this.project(a.pos);
      if (p) {
        a.el.style.transform = `translate(${p.x}px, ${p.y - k * 60 * a.drift * this.scale}px) translate(-50%, -50%) scale(${this.scale})`;
        a.el.style.opacity = String(k > 0.7 ? 1 - (k - 0.7) / 0.3 : 1);
      }
      if (k >= 1) {
        a.el.remove();
        this.anchored.splice(i, 1);
      }
    }
  }

  clearPopups() {
    for (const a of this.anchored) a.el.remove();
    this.anchored = [];
  }

  /** Pass a function when the text names keys/buttons, so it follows the input device while shown. */
  toast(html: string | ((s: InputState) => string), cls = '', ms = 2600) {
    const e = el('div', 'toast ' + cls, typeof html === 'string' ? html : '', this.toasts);
    if (typeof html !== 'string') bindInput(e, html);
    setTimeout(() => e.classList.add('out'), ms);
    setTimeout(() => e.remove(), ms + 500);
  }

  /** Big center banner. */
  banner(text: string, sub = '', cls = '', ms = 1400) {
    const e = el('div', 'banner ' + cls, `<div class="banner-main">${text}</div>${sub ? `<div class="banner-sub">${sub}</div>` : ''}`, this.topLayer);
    setTimeout(() => e.classList.add('out'), ms);
    setTimeout(() => e.remove(), ms + 600);
  }

  /** Fade out any banners still on screen (e.g. before a tip takes the stage). */
  clearBanners() {
    for (const b of this.topLayer.querySelectorAll('.banner')) b.classList.add('out');
  }

  /** Small top-center move name plate. */
  moveName(text: string, cls = '', ms = 1600) {
    const e = el('div', 'move-name ' + cls, text, this.topLayer);
    setTimeout(() => e.classList.add('out'), ms);
    setTimeout(() => e.remove(), ms + 400);
  }

  flash(color = '#fff', ms = 180) {
    const e = el('div', 'screen-flash', undefined, this.topLayer);
    e.style.background = color;
    e.style.animationDuration = ms + 'ms';
    setTimeout(() => e.remove(), ms + 50);
  }

  async fadeOut(ms = 400, color = '#000') {
    this.fade.style.background = color;
    this.fade.style.transition = `opacity ${ms}ms`;
    this.fade.style.opacity = '1';
    await new Promise((r) => setTimeout(r, ms));
  }
  async fadeIn(ms = 400) {
    this.fade.style.transition = `opacity ${ms}ms`;
    this.fade.style.opacity = '0';
    await new Promise((r) => setTimeout(r, ms));
  }

  /** Battle-start shatter transition (CSS). */
  async battleWipe(kind: 'advantage' | 'ambush' | 'neutral') {
    const e = el('div', 'battle-wipe ' + kind, '', this.topLayer);
    for (let i = 0; i < 12; i++) el('div', 'shard', undefined, e).style.setProperty('--i', String(i));
    await new Promise((r) => setTimeout(r, 650));
    setTimeout(() => e.remove(), 900);
  }
}
