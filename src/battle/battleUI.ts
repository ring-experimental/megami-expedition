import * as THREE from 'three';
import { Input, K } from '../core/input';
import { Sfx } from '../core/audio';
import { el } from '../core/utils';
import { ELEMENT_NAME, STATUS_INFO, type Element } from '../data/types';
import { State } from '../game/state';
import type { UI } from '../ui/ui';
import { artSrc, icon, portraitInner, type Expression } from '../ui/art';
import { FEATHER_SVG, gearSvg } from '../ui/ornaments';
import { bindInput, pb } from '../ui/glyph';
import type { Timeline } from '../core/timeline';
import type { BUnit } from './bunit';
import type { Tip } from './tips';
import { xpToNext } from '../data/units';
import './battleUI.css';

const GEAR_SVG = gearSvg();

/** 2D art drop-ins (docs/2D_ASSET_PROMPTS.md §7); each falls back to the CSS/SVG placeholder. */
const img = (src: string | null, fallback: string) => (src ? `<img src="${src}" alt="" draggable="false">` : fallback);
/** Ring geometry: labels orbit at RING_R px; the selected command parks at POINTER (degrees, screen space). */
const RING_R = 108;
const POINTER = -18;

const BLADE_SVG = '<svg viewBox="0 0 26 54"><path d="M13 54 L4 22 L9 20 L9 8 L4 8 L4 3 L22 3 L22 8 L17 8 L17 20 L22 22 Z" fill="#f2c94c" stroke="#0b0907" stroke-width="2" stroke-linejoin="round"/><path d="M13 50 L13 24" stroke="#0b0907" stroke-width="1.2"/></svg>';

/** Roulette gear: the first `gold` teeth are gold (success), the rest ink. Tooth 0 starts at the top. */
function rouletteSvg(teeth: number, gold: number) {
  const c = 100, rOut = 96, rRoot = 82, rHole = 58;
  const step = (Math.PI * 2) / teeth;
  const P = (a: number, r: number) => `${(c + Math.cos(a) * r).toFixed(1)},${(c + Math.sin(a) * r).toFixed(1)}`;
  const parts: string[] = [];
  for (let i = 0; i < teeth; i++) {
    const a0 = -Math.PI / 2 + i * step;
    // one wedge per tooth: hole edge → root → flank → tip → root → hole edge
    const d = `M${P(a0, rHole)} L${P(a0, rRoot)} L${P(a0 + step * 0.22, rOut)} L${P(a0 + step * 0.78, rOut)} L${P(a0 + step, rRoot)} L${P(a0 + step, rHole)} Z`;
    parts.push(`<path d="${d}" fill="${i < gold ? '#f2c94c' : '#241c13'}" stroke="#0b0907" stroke-width="1.5"/>`);
  }
  return `<svg viewBox="0 0 200 200">${parts.join('')}<circle cx="100" cy="100" r="${rHole}" fill="#0b0907" stroke="#6b5420" stroke-width="2"/></svg>`;
}


/** Plain text → HTML-safe (dialogue lines are plain text). */
const esc = (t: string) => t.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c]!);

const INK_SVG = '<svg viewBox="0 0 1000 150" preserveAspectRatio="none"><g fill="#0b0907">'
  + '<path d="M0 40 Q250 10 520 34 T1000 24 L1000 120 Q760 140 480 116 T0 128 Z"/>'
  + '<circle cx="120" cy="18" r="9"/><circle cx="160" cy="8" r="4"/><circle cx="860" cy="138" r="8"/><circle cx="900" cy="146" r="3"/><circle cx="640" cy="10" r="5"/></g></svg>';

/** One member card on the victory screen (before/after are captured around State.giveXp). */
export interface VictoryRow { pid: string; name: string; color: string; gain: number; reserve: boolean; fromLv: number; fromXp: number; toLv: number; toXp: number; newSkills: string[] }
export interface VictoryData { xp: number; money: number; drops: string[]; recruited: string[]; rows: VictoryRow[]; bonuses: { label: string; pct: number }[] }

export interface MenuItem<T> { label: string; right?: string; desc?: string; disabled?: boolean; value: T; cls?: string }

interface ActiveMenu {
  kind: 'ring' | 'blades';
  items: MenuItem<unknown>[];
  index: number;
  resolve: (v: unknown) => void;
  cancellable: boolean;
  onHover?: (v: unknown) => void;
  els: HTMLElement[];
}

interface ActiveTarget {
  units: BUnit[];
  index: number;
  all: boolean;
  resolve: (v: BUnit | 'all' | null) => void;
  onHover?: (u: BUnit | 'all') => void;
}

interface Ring { el: HTMLElement; anchor: () => THREE.Vector3; tEnd: number; lead: number; kind: string; done: boolean }

export class BattleUI {
  root: HTMLElement;
  private order: HTMLElement;
  private partyPanel: HTMLElement;
  private ringEl: HTMLElement;
  private ringGear: HTMLElement;
  private ringItems: HTMLElement;
  private ringName: HTMLElement;
  private ringAp: HTMLElement;
  private ringTicks: HTMLElement;
  private ringDesc: HTMLElement;
  private bladesEl: HTMLElement;
  private bladeTitle: HTMLElement;
  private bladeList: HTMLElement;
  private bladeDesc: HTMLElement;
  /** Unit the command ring is attached to (null = ring hidden). */
  private ringUnit: BUnit | null = null;
  /** Cumulative ring rotation in teeth — never wrapped, so every move animates the short way. */
  private ringRot = 0;
  private ringPos = { x: 0, y: 0 };
  private talkPor: HTMLElement | null = null;
  private talkPid = '';
  private talkFan: HTMLElement | null = null;
  private talkRoll: HTMLElement | null = null;
  /** Fixed spot for a blade list (defeat screen); null = sprout from the ring or default spot. */
  private bladeSpot: { x: number; y: number } | null = null;
  private defHint: HTMLElement;
  private speedEl: HTMLElement;
  private speed = 1;
  private arrow: HTMLElement;
  private dialog: HTMLElement;
  private ringLayer: HTMLElement;
  private menu: ActiveMenu | null = null;
  private target: ActiveTarget | null = null;
  private rings: Ring[] = [];
  private dialogWait: { resolve: () => void; skip?: () => void } | null = null;
  private dialogChoice: { resolve: (i: number) => void; index: number; els: HTMLElement[] } | null = null;
  units: BUnit[] = [];
  now = 0;

  constructor(private ui: UI, private tl: Timeline) {
    this.root = el('div', 'battle-hud', undefined, ui.hudLayer);
    this.order = el('div', 'turn-order', undefined, this.root);
    this.partyPanel = el('div', 'party-panel', undefined, this.root);
    // command ring (top-level command) — follows the acting unit on screen
    this.ringEl = el('div', 'cmd-ring hidden-ring', undefined, this.root);
    this.ringGear = el('div', 'cr-gear', img(artSrc('ui/gear_ring'), GEAR_SVG), this.ringEl);
    const core = el('div', 'cr-core', undefined, this.ringEl);
    this.ringTicks = el('div', 'cr-ticks', '', core);
    this.ringAp = el('div', 'cr-ap', '0', core);
    el('div', 'cr-ap-l', 'AP', core);
    this.ringItems = el('div', 'cr-items', undefined, this.ringEl);
    this.ringName = el('div', 'cr-name', '', this.ringEl);
    this.ringDesc = el('div', 'cr-desc', '', this.ringEl);
    bindInput(el('div', 'cr-hint', '', this.ringEl), (s) => s.device === 'pad'
      ? `${pb('dpad')} 회전 · ${pb('a')} 결정`
      : '<kbd>W</kbd><kbd>S</kbd> 회전 · <kbd>Enter</kbd> 결정');
    // blade list (sub-menus) — sprouts from the ring's pointer tooth
    this.bladesEl = el('div', 'cmd-blades hidden-ring', undefined, this.root);
    this.bladeTitle = el('div', 'cb-title', '', this.bladesEl);
    this.bladeList = el('div', 'cb-list', '', this.bladesEl);
    this.bladeDesc = el('div', 'cb-desc', '', this.bladesEl);
    bindInput(el('div', 'cb-hint', '', this.bladesEl), (s) => s.device === 'pad'
      ? `${pb('dpad')} 선택 · ${pb('a')} 결정<span class="cancel"> · ${pb('b')} 취소</span>`
      : '<kbd>W</kbd><kbd>S</kbd> 선택 · <kbd>Enter</kbd> 결정<span class="cancel"> · <kbd>Esc</kbd> 취소</span>');
    this.defHint = bindInput(el('div', 'def-hint', '', this.root), (s) => s.device === 'pad'
      ? `<span class="dh-n">${pb('a')}/${pb('rb')} 패링</span><span class="dh-n">${pb('b')} 회피</span><span class="dh-j">${pb('y')} 점프!</span>`
      : '<span class="dh-n"><kbd>F</kbd>/<kbd>좌클릭</kbd> 패링</span><span class="dh-n"><kbd>Space</kbd>/<kbd>우클릭</kbd> 회피</span><span class="dh-j"><kbd>W</kbd> 점프!</span>');
    this.speedEl = bindInput(el('div', 'battle-speed', '', this.root), (s) => `<b>${this.speed > 1 ? '▶▶' : '▶'} ×${this.speed}</b><span>${s.device === 'pad' ? pb('back') : '<kbd>Tab</kbd>'} 배속</span>`);
    this.arrow = el('div', 'target-arrow', img(artSrc('ui/target_blade'), BLADE_SVG), ui.layer);
    // textures used from CSS (ink blots behind moment words, ink grain on panels)
    for (const [file, cls] of [['ui/ink_splat', 'art-ink-splat'], ['ui/ink_texture', 'art-ink-tex']]) {
      const src = artSrc(file);
      if (src) { ui.root.classList.add(cls); ui.root.style.setProperty('--' + cls, `url("${src}")`); }
    }
    // world layer: timing rings are placed with placeAt, which expects unzoomed screen pixels
    this.ringLayer = el('div', 'ring-layer', undefined, ui.layer);
    this.dialog = el('div', 'dialog hidden', undefined, this.root);
    this.hideCommand();
    this.showDefHint(false);
    this.arrow.style.display = 'none';
    this.root.style.display = 'none';
  }

  show(v: boolean) {
    this.root.style.display = v ? '' : 'none';
    // banners / move names live in the shared top layer; battle restyles them via this flag
    this.ui.root.classList.toggle('battle-on', v);
    if (!v) {
      this.arrow.style.display = 'none';
      for (const u of this.units) u.ui.plate?.remove();
      this.units = [];
      this.partyPanel.innerHTML = '';
      this.rings.forEach((r) => r.el.remove());
      this.rings = [];
      this.closeDialog();
    }
  }

  // -------------------------------------------------------------------------
  // Units
  // -------------------------------------------------------------------------
  setUnits(units: BUnit[]) {
    for (const u of this.units) if (u.side === 'enemy') u.ui.plate?.remove();
    this.units = units;
    this.partyPanel.innerHTML = '';
    for (const u of units) {
      if (u.side === 'enemy') {
        const plate = el('div', 'enemy-plate battle', undefined, this.ui.layer);
        el('div', 'ep-name', `${u.name} <span class="lv">Lv${u.level}</span>`, plate);
        const hpw = el('div', 'bar hp', undefined, plate);
        const hp = el('div', 'fill', undefined, hpw);
        const hpt = el('div', 'ep-hp', '', plate);
        const bw = el('div', 'bar brk', undefined, plate);
        const brk = el('div', 'fill', undefined, bw);
        const weak = el('div', 'ep-weak', this.affinityHtml(u), plate);
        const st = el('div', 'statuses', '', plate);
        const tag = el('div', 'ep-tag', '', plate);
        plate.addEventListener('click', () => this.clickTarget(u));
        plate.addEventListener('mouseenter', () => this.hoverTarget(u));
        u.ui = { plate, hp, hpt, brk, st, tag, weak };
      } else {
        // tall slanted portrait (gold frame → ink inside), name/HP/AP overlaid on its lower part
        const card = el('div', 'party-card', undefined, this.partyPanel);
        card.style.setProperty('--i', String(this.partyPanel.children.length - 1));
        const inner = el('div', 'pc-inner', undefined, el('div', 'pc-frame', undefined, card));
        el('div', 'portrait', portraitInner(u.pid, u.name), inner);
        const info = el('div', 'pc-info', undefined, inner);
        el('div', 'pc-name', `${u.name}<span class="lv">Lv${u.level}</span>`, info);
        const hpt = el('div', 'pc-hp', '', info);
        const hpw = el('div', 'bar hp', undefined, info);
        const hp = el('div', 'fill', undefined, hpw);
        const ap = el('div', 'ap-pips', '', info);
        // character mechanics: Kai's 열압 gauge, Lyra's 회로 각인 slots
        const mech = el('div', `pc-mech${u.hero?.id === 'kai' ? ' heat' : u.hero?.id === 'lyra' ? ' sigil' : ''}`, '', info);
        const st = el('div', 'statuses', '', card);
        card.addEventListener('click', () => this.clickTarget(u));
        card.addEventListener('mouseenter', () => this.hoverTarget(u));
        u.ui = { plate: card, hp, hpt, ap, st, mech };
      }
    }
  }

  setActive(u: BUnit | null) {
    for (const x of this.units) x.ui.plate?.classList.toggle('active', x === u);
    // during a party turn the others step back
    this.partyPanel.classList.toggle('has-active', !!u && u.side === 'party');
  }

  /** `bonuses[i]`: the slot bonus chip i lands on; `preview`: the order as the hovered action would leave it. */
  setOrder(list: BUnit[], bonuses: (string | null)[] = [], preview = false) {
    this.order.innerHTML = '';
    this.order.classList.toggle('preview', preview);
    el('div', 'to-label', preview ? 'Next' : 'Turn', this.order);
    const BONUS: Record<string, string> = { heal: 'HP', ap: 'AP', crit: 'CRT', brk: 'BRK' };
    list.forEach((u, i) => {
      const b = bonuses[i];
      // the chip is clipped to its slanted shape, so the bonus tag sits beside it in a slot wrapper
      const slot = el('div', `to-slot ${u.side}`, b ? `<span class="to-bonus b-${b}">${BONUS[b]}</span>` : '', this.order);
      const c = el('div', `to-chip ${u.side}${i === 0 ? ' now' : ''}${u.broken ? ' broken' : ''}`, `<div class="chip-in">${portraitInner(u.pid, u.name)}</div>`);
      slot.prepend(c);
      c.style.setProperty('--c', u.color);
      c.title = u.name;
    });
  }

  refresh() {
    for (const u of this.units) {
      const ui = u.ui;
      if (!ui.plate) continue;
      ui.hp.style.width = `${Math.max(0, u.hp / u.maxHp) * 100}%`;
      const hpNow = Math.max(0, Math.ceil(u.hp));
      if (u.side === 'enemy') ui.hpt.textContent = `${hpNow} / ${u.maxHp}`;
      else ui.hpt.innerHTML = `${hpNow}<small>/${u.maxHp}</small>`;
      ui.plate.classList.toggle('low', !u.ko && u.hp / u.maxHp <= 0.3);
      ui.st.innerHTML = u.statuses.map((s) => `<span class="st ${STATUS_INFO[s.id].good ? 'good' : 'bad'}" title="${STATUS_INFO[s.id].name}">${icon('st', s.id, STATUS_INFO[s.id].icon)}${s.turns}</span>`).join('');
      ui.plate.classList.toggle('ko', u.ko);
      if (u.side === 'enemy') {
        ui.brk.style.width = `${(u.broken ? 1 : u.brk / u.brkMax) * 100}%`;
        ui.plate.classList.toggle('broken', u.broken);
        ui.tag.innerHTML = u.broken ? 'Break' : u.rapport > 0 ? `<span class="rapport" title="패링 성공 횟수 (설득 보너스)">♦${u.rapport}</span>` : '';
        ui.plate.style.display = u.removed || u.ko ? 'none' : '';
      } else {
        ui.ap.innerHTML = Array.from({ length: 9 }, (_, i) => `<i class="${i < u.ap ? 'on' : ''}"></i>`).join('');
        if (u.hero?.id === 'kai') {
          const over = u.has('overheat');
          ui.mech.innerHTML = `<span class="mh-l">${over ? '과열' : '열압'}</span><span class="mh-bar${over ? ' over' : ''}"><i style="width:${over ? 100 : u.heat}%"></i></span>`;
        } else if (u.hero?.id === 'lyra') {
          ui.mech.innerHTML = `<span class="mh-l">각인</span>${[0, 1].map((i) => (u.sigils[i] ? `<span class="sg">${icon('el', u.sigils[i], ELEMENT_NAME[u.sigils[i]])}</span>` : '<span class="sg empty"></span>')).join('')}`;
        }
      }
    }
  }

  // -------------------------------------------------------------------------
  // Command menu
  // -------------------------------------------------------------------------
  /**
   * Pick from a list. `ring` attaches the top-level command gear to that unit; otherwise the items
   * show as a blade list (sprouting from the ring while it is parked, or at a fixed spot).
   */
  menuSelect<T>(title: string, items: MenuItem<T>[], opts: { cancellable?: boolean; onHover?: (v: T) => void; startIndex?: number; ring?: BUnit } = {}): Promise<T | null> {
    const kind = opts.ring ? 'ring' : 'blades';
    let els: HTMLElement[];
    if (opts.ring) {
      this.ringUnit = opts.ring;
      this.ringEl.classList.remove('hidden-ring', 'parked', 'enter');
      void this.ringEl.offsetWidth; // restart the entry animation
      this.ringEl.classList.add('enter');
      this.ringName.innerHTML = `${opts.ring.name}<small>의 턴</small>`;
      this.ringAp.textContent = String(opts.ring.ap);
      this.ringTicks.innerHTML = this.apTicks(opts.ring.ap);
      this.ringItems.innerHTML = '';
      els = items.map((it, i) => {
        const right = it.right && it.right !== '▶' ? `<span class="r">${it.right}</span>` : '';
        const e = el('div', `cr-item${it.disabled ? ' disabled' : ''}`, `<div>${it.label}${right}</div>`, this.ringItems);
        // the mouse only highlights — rotating under the cursor would move the item away from it
        e.addEventListener('mouseenter', () => this.menu && this.menuIndex(i, false, false));
        e.addEventListener('click', () => { if (this.menu) { this.menuIndex(i, true, false); this.menuConfirm(); } });
        return e;
      });
      this.placeRing();
    } else {
      this.bladesEl.classList.remove('hidden-ring');
      this.bladesEl.classList.toggle('no-cancel', opts.cancellable === false);
      this.bladeTitle.innerHTML = title;
      this.bladeList.innerHTML = '';
      els = items.map((it, i) => {
        const e = el('div', `cb-item${it.disabled ? ' disabled' : ''} ${it.cls ?? ''}`, `<span>${it.label}</span>${it.right ? `<span class="r">${it.right}</span>` : ''}`, this.bladeList);
        e.style.setProperty('--i', String(i));
        e.addEventListener('mouseenter', () => this.menu && this.menuIndex(i));
        e.addEventListener('click', () => { if (this.menu) { this.menuIndex(i); this.menuConfirm(); } });
        return e;
      });
      if (import.meta.env.DEV && items.length > 7) console.warn('[ui] blade list has more than 7 items and is not windowed');
      this.placeBlades();
    }
    return new Promise((resolve) => {
      let start = opts.startIndex ?? 0;
      while (items[start]?.disabled && start < items.length - 1) start++;
      this.menu = { kind, items: items as MenuItem<unknown>[], index: start, resolve: resolve as (v: unknown) => void, cancellable: opts.cancellable ?? true, onHover: opts.onHover as ((v: unknown) => void) | undefined, els };
      if (kind === 'ring') this.ringRot = start;
      this.menuIndex(start, true);
    });
  }

  /** 9 AP ticks around the ring core, clockwise from the top. */
  private apTicks(ap: number) {
    return Array.from({ length: 9 }, (_, i) =>
      `<i style="transform:rotate(${-90 + i * 40}deg) translate(37px)" class="${i < ap ? 'on' : ''}"></i>`).join('');
  }

  /** Orbit the ring labels for the current rotation; the selected one parks at POINTER. */
  private layoutRing() {
    const m = this.menu;
    if (!m || m.kind !== 'ring') return;
    const n = m.items.length;
    const step = 360 / n;
    this.ringGear.style.transform = `rotate(${-this.ringRot * step}deg)`;
    m.els.forEach((e, i) => {
      // nearest copy of item i relative to the cumulative rotation keeps the CSS tween one tooth long
      let rel = i - this.ringRot;
      rel -= Math.round(rel / n) * n;
      const a = POINTER + rel * step;
      e.style.transform = `rotate(${a}deg) translate(${RING_R}px) rotate(${-a}deg)`;
      const d = Math.abs(rel);
      e.style.opacity = String(d === 0 ? 1 : d === 1 ? 0.85 : 0.55);
    });
  }

  private menuIndex(i: number, silent = false, rotate = true) {
    const m = this.menu!;
    if (i !== m.index && !silent) Sfx.play('ui_move');
    m.index = i;
    m.els.forEach((e, k) => e.classList.toggle('sel', k === i));
    const it = m.items[i];
    const desc = m.kind === 'ring' ? this.ringDesc : this.bladeDesc;
    // the description slot keeps a fixed height even when empty (no layout shift)
    desc.innerHTML = it?.desc ?? '';
    desc.title = desc.textContent ?? '';
    if (import.meta.env.DEV && desc.scrollHeight > desc.clientHeight + 1) {
      console.warn('[ui] command description exceeds the 2-line slot and is clipped:', desc.textContent);
    }
    if (m.kind === 'ring') {
      if (rotate) {
        // turn the gear the short way round
        const n = m.items.length;
        let d = (((i - this.ringRot) % n) + n) % n;
        if (d > n / 2) d -= n;
        this.ringRot += d;
      }
      this.layoutRing();
    }
    if (it) m.onHover?.(it.value);
  }

  private menuConfirm() {
    const m = this.menu!;
    const it = m.items[m.index];
    if (!it || it.disabled) { Sfx.play('ui_error'); return; }
    Sfx.play('ui_ok');
    this.menu = null;
    // the ring stays parked behind a sub-menu; target selection / acting hides it
    if (m.kind === 'ring') this.ringEl.classList.add('parked');
    else this.bladesEl.classList.add('hidden-ring');
    m.resolve(it.value);
  }

  hideCommand() {
    this.ringEl.classList.add('hidden-ring');
    this.bladesEl.classList.add('hidden-ring');
    this.ringUnit = null;
  }

  /** Ring screen position: beside the acting unit, clamped on screen. */
  private placeRing() {
    if (!this.ringUnit) return;
    const p = this.ui.project(this.ringUnit.centerPos());
    if (!p) return;
    // the ring lives in the zoomed HUD layer: work in its (unscaled) CSS pixels
    const k = this.ui.scale;
    p.x /= k; p.y /= k;
    const w = this.ui.width / k, h = this.ui.height / k;
    // keep room on the right for the blade list that sprouts from the pointer tooth
    const x = Math.min(w - 485, Math.max(170, p.x + Math.max(200, w * 0.2)));
    const y = Math.min(h - 190, Math.max(190, p.y + 10));
    this.ringPos = { x, y };
    this.ringEl.style.transform = `translate(${x}px, ${y}px)`;
    if (!this.bladesEl.classList.contains('hidden-ring')) this.placeBlades();
  }

  private placeBlades() {
    const w = this.ui.width / this.ui.scale, h = this.ui.height / this.ui.scale;
    const bh = this.bladesEl.offsetHeight || 260;
    let x = w * 0.6, y = h * 0.4;
    const fromRing = !!this.ringUnit && !this.ringEl.classList.contains('hidden-ring');
    // sprouting from a ring tooth: the tooth label already names the list
    this.bladesEl.classList.toggle('from-ring', fromRing);
    if (this.bladeSpot) ({ x, y } = this.bladeSpot);
    else if (fromRing) {
      const a = (POINTER * Math.PI) / 180;
      x = this.ringPos.x + Math.cos(a) * (RING_R + 30);
      y = this.ringPos.y + Math.sin(a) * (RING_R + 30) - 20;
    }
    x = Math.min(w - 336, Math.max(16, x));
    y = Math.min(h - bh - 16, Math.max(16, y));
    this.bladesEl.style.transform = `translate(${x}px, ${y}px)`;
  }

  refreshAffinity() {
    for (const u of this.units) if (u.side === 'enemy' && u.ui.weak) u.ui.weak.innerHTML = this.affinityHtml(u);
  }

  /** Discovered weaknesses (large) and resistances (small) for the target panel; '?' until one is found. */
  private affinityHtml(u: BUnit) {
    const aff = u.species?.affinity ?? {};
    const known = State.current.bestiary[u.species!.id]?.known ?? [];
    const keys = (Object.keys(aff) as Element[]).filter((k) => known.includes(k));
    if (!keys.length) return '<span class="wk unknown">Weak ?</span>';
    const weak = keys.filter((k) => (aff[k] ?? 1) > 1);
    const resist = keys.filter((k) => (aff[k] ?? 1) < 1);
    return weak.map((k) => `<span class="wk" title="약점: ${ELEMENT_NAME[k]}">${icon('el', k, ELEMENT_NAME[k])}</span>`).join('')
      + (weak.length ? '<span class="wk">Weak</span>' : '')
      + resist.map((k) => `<span class="rs" title="내성: ${ELEMENT_NAME[k]}">${icon('el', k, ELEMENT_NAME[k])}</span>`).join('');
  }

  // -------------------------------------------------------------------------
  // Cut-in (skills, BREAK, COUNTER) — UI bible §9-1
  // -------------------------------------------------------------------------
  /** Slanted ink band with portrait + title. Resolves after `hold` seconds; the band clears itself. */
  async cutIn(opts: { title: string; sub?: string; unit?: BUnit; enemy?: boolean }, hold = 0.5) {
    const u = opts.unit;
    const bust = u && artSrc('portraits/cutin_' + u.pid);
    const por = u ? `<div class="ci-por" style="--c:${u.color}">${bust ? `<img class="pimg" src="${bust}" alt="">` : portraitInner(u.pid, u.name)}</div>` : '';
    const e = el('div', `cutin${u ? '' : ' noportrait'}${opts.enemy ? ' enemy' : ''}`,
      `<div class="ci-band"></div><div class="ci-ink">${img(artSrc('ui/ink_band'), INK_SVG)}</div>${por}<div class="ci-text"><div class="ci-title">${opts.title}</div>${opts.sub ? `<div class="ci-sub">${opts.sub}</div>` : ''}</div>`,
      this.root);
    this.tl.wait(0.72).then(() => e.remove());
    await this.tl.wait(hold);
  }

  // -------------------------------------------------------------------------
  // Hold up (all enemies broken) — the party closes in: slanted portrait panels slam in one by
  // one over an ink wash, then the title. Stays up behind the choice; close() folds it away.
  // -------------------------------------------------------------------------
  async holdUp(party: BUnit[]) {
    const panels = party.map((u, i) => {
      const bust = artSrc('portraits/cutin_' + u.pid);
      return `<div class="hu-panel" style="--i:${i};--c:${u.color}">${bust ? `<img class="pimg" src="${bust}" alt="">` : portraitInner(u.pid, u.name)}</div>`;
    }).join('');
    const e = el('div', 'holdup', `<div class="hu-wash"></div><div class="hu-ink">${img(artSrc('ui/ink_band'), INK_SVG)}</div>
      <div class="hu-panels" style="--n:${party.length}">${panels}</div>
      <div class="hu-title"><span>Hold Up</span><small>적 전원 브레이크 — 포위했다!</small></div>`, this.root);
    e.style.setProperty('--n', String(party.length));
    this.ui.root.classList.add('battle-holdup');
    Sfx.play('advantage');
    party.forEach((_, i) => this.tl.wait(0.16 + i * 0.12).then(() => Sfx.play('hit_heavy')));
    await this.tl.wait(0.25 + party.length * 0.12 + 0.35);
    Sfx.play('break');
    return {
      close: async () => { e.classList.add('out'); this.ui.root.classList.remove('battle-holdup'); await this.tl.wait(0.3); e.remove(); },
    };
  }

  /** One huge ink word over everything (all-out attack finish). */
  async inkWord(text: string, hold = 0.7) {
    const e = el('div', 'allout-flash', `<span>${text}</span>`, this.root);
    await this.tl.wait(hold);
    e.remove();
  }

  /** Blade list at a fixed spot (hold-up choices sit beside the portrait panels). */
  async menuAt<T>(title: string, items: MenuItem<T>[], x: number, yFrac: number, opts: { cancellable?: boolean } = {}) {
    this.bladeSpot = { x, y: (this.ui.height / this.ui.scale) * yFrac };
    const v = await this.menuSelect(title, items, opts);
    this.bladeSpot = null;
    return v;
  }

  // -------------------------------------------------------------------------
  // Target selection
  // -------------------------------------------------------------------------
  selectTarget(units: BUnit[], opts: { all?: boolean; onHover?: (u: BUnit | 'all') => void; camera: THREE.Camera }): Promise<BUnit | 'all' | null> {
    // order left → right on screen
    const sorted = [...units].sort((a, b) => a.pos.clone().project(opts.camera).x - b.pos.clone().project(opts.camera).x);
    this.hideCommand();
    return new Promise((resolve) => {
      this.target = { units: sorted, index: 0, all: !!opts.all, resolve, onHover: opts.onHover };
      for (const u of sorted) u.ui.plate?.classList.add('targetable');
      this.targetIndex(0, true);
    });
  }

  private targetIndex(i: number, silent = false) {
    const t = this.target!;
    if (!silent && i !== t.index) Sfx.play('ui_move');
    t.index = (i + t.units.length) % t.units.length;
    for (const u of this.units) u.ui.plate?.classList.toggle('targeted', t.all ? t.units.includes(u) : u === t.units[t.index]);
    t.onHover?.(t.all ? 'all' : t.units[t.index]);
  }

  private clickTarget(u: BUnit) {
    const t = this.target;
    if (!t) return;
    const i = t.units.indexOf(u);
    if (i < 0) return;
    this.targetIndex(i);
    this.targetConfirm();
  }
  private hoverTarget(u: BUnit) {
    const t = this.target;
    if (!t || t.all) return;
    const i = t.units.indexOf(u);
    if (i >= 0) this.targetIndex(i);
  }

  private targetConfirm() {
    const t = this.target!;
    Sfx.play('ui_ok');
    this.endTarget();
    t.resolve(t.all ? 'all' : t.units[t.index]);
  }
  private endTarget() {
    for (const u of this.units) u.ui.plate?.classList.remove('targetable', 'targeted');
    this.target = null;
    this.arrow.style.display = 'none';
  }

  // -------------------------------------------------------------------------
  // Timing rings (parry / QTE)
  // -------------------------------------------------------------------------
  ring(anchor: () => THREE.Vector3, tEnd: number, lead: number, kind: 'parry' | 'qte' | 'jump') {
    const e = el('div', `timing-ring ${kind}`, '<div class="outer"></div><div class="inner"></div>', this.ringLayer);
    if (kind === 'qte') bindInput(el('div', 'key', '', e), (s) => (s.device === 'pad' ? pb('a') : 'F'));
    const r: Ring = { el: e, anchor, tEnd, lead, kind, done: false };
    this.rings.push(r);
    return {
      result: (txt: string, cls: string) => {
        r.done = true;
        // result classes are prefixed: the ring kind 'parry' and the result 'parry' would collide
        e.classList.add('res', 'r-' + cls);
        e.querySelector('.inner')!.innerHTML = `<span>${txt}</span>`;
        setTimeout(() => e.remove(), 450);
      },
      remove: () => { r.done = true; e.remove(); },
    };
  }

  /** Top-right speed plate; hidden at ×1 except for a key hint. */
  setSpeed(k: number) {
    this.speed = k;
    this.speedEl.querySelector('b')!.textContent = `${k > 1 ? '▶▶' : '▶'} ×${k}`;
    this.speedEl.classList.toggle('fast', k > 1);
  }

  showDefHint(v: boolean, jump = false) {
    this.defHint.style.display = v ? '' : 'none';
    this.defHint.classList.toggle('jump', jump);
  }

  // -------------------------------------------------------------------------
  // Negotiation — face-to-face layout (UI bible §9-3)
  // -------------------------------------------------------------------------
  /** Enter the talk scene: battle HUD steps back, the enemy's portrait faces the player. */
  beginTalk(enemy: BUnit) {
    this.endTalk();
    this.ui.root.classList.add('battle-talk');
    this.talkPid = enemy.pid;
    this.talkPor = el('div', 'talk-por', `<div class="tp-in" style="--c:${enemy.color}">${portraitInner(enemy.pid, enemy.name)}</div>`, this.root);
  }

  endTalk() {
    this.ui.root.classList.remove('battle-talk');
    this.talkPor?.remove();
    this.talkPor = null;
    this.talkPid = '';
    this.talkFan?.remove();
    this.talkFan = null;
    this.talkRoll?.remove();
    this.talkRoll = null;
  }

  /** Swap the big portrait's expression with a small reaction (happy hop / angry shake). */
  private setExpression(expr?: Expression) {
    const por = this.talkPor;
    if (!por) return;
    (por.querySelector('.tp-in') as HTMLElement).innerHTML = portraitInner(this.talkPid, '', expr);
    por.classList.remove('happy', 'angry');
    if (expr) {
      void por.offsetWidth; // restart the reaction animation
      por.classList.add(expr);
    }
  }

  /** Name tab of the band; the enemy speaks through the big portrait, system lines dim it. */
  private dialogHead(speaker: string, pid: string) {
    const sys = !pid;
    this.dialog.classList.toggle('system', sys);
    this.talkPor?.classList.toggle('dim', sys);
    return `<div class="dl-name">${speaker}</div>`;
  }

  async say(speaker: string, text: string, _color = '', pid = '', expr?: Expression) {
    this.dialog.classList.remove('hidden');
    if (pid && pid === this.talkPid) this.setExpression(expr);
    this.dialog.innerHTML = `${this.dialogHead(speaker, pid)}<div class="dl-text"></div><div class="dl-next"></div>`;
    const tEl = this.dialog.querySelector('.dl-text') as HTMLElement;
    let skip = false;
    await new Promise<void>((resolve) => {
      this.dialogWait = { resolve, skip: () => { skip = true; } };
      let i = 0;
      const tick = () => {
        if (skip) i = text.length;
        // the untyped rest is laid out but invisible, so the bottom-anchored band never grows mid-line
        tEl.innerHTML = `${esc(text.slice(0, i))}<span class="dl-ghost">${esc(text.slice(i))}</span>`;
        if (i % 2 === 0 && i < text.length) Sfx.play('talk_blip');
        if (i < text.length) { i++; this.tl.wait(0.022).then(tick); }
        else {
          this.dialog.classList.add('done');
          this.dialogWait = { resolve };
        }
      };
      this.dialog.classList.remove('done');
      tick();
    });
  }

  /** Question in the band, answers as a fan of blade cards above it. */
  choose(speaker: string, text: string, choices: string[], _color = '', pid = ''): Promise<number> {
    this.dialog.classList.remove('hidden');
    this.dialog.classList.add('done');
    if (pid && pid === this.talkPid) this.setExpression();
    this.dialog.innerHTML = `${this.dialogHead(speaker, pid)}<div class="dl-text">${text}</div>`;
    this.talkFan?.remove();
    const fan = (this.talkFan = el('div', 'talk-fan', undefined, this.root));
    const n = choices.length;
    const els = choices.map((c, i) => {
      const e = el('div', 'fan-card', `<span class="n"></span><div class="fc-text">${c}</div>`, fan);
      // spread around a pivot below the cards: angle and sideways offset per slot
      const k = n === 1 ? 0 : i / (n - 1) - 0.5;
      e.style.setProperty('--a', `${k * (n > 2 ? 22 : 12)}deg`);
      e.style.setProperty('--x', `${k * (n > 2 ? 500 : 290)}px`);
      e.style.setProperty('--i', String(i));
      // number keys pick a choice on the keyboard; meaningless on a pad
      bindInput(e.querySelector('.n') as HTMLElement, (s) => (s.device === 'pad' ? '' : String(i + 1)));
      e.addEventListener('mouseenter', () => this.dialogChoice && this.choiceIndex(i));
      e.addEventListener('click', () => { if (this.dialogChoice) { this.choiceIndex(i); this.choiceConfirm(); } });
      return e;
    });
    return new Promise((resolve) => {
      this.dialogChoice = { resolve, index: 0, els };
      this.choiceIndex(0);
    });
  }

  private choiceIndex(i: number) {
    const c = this.dialogChoice!;
    if (c.index !== i) Sfx.play('ui_move');
    c.index = (i + c.els.length) % c.els.length;
    c.els.forEach((e, k) => e.classList.toggle('sel', k === c.index));
  }
  private choiceConfirm() {
    const c = this.dialogChoice!;
    this.dialogChoice = null;
    Sfx.play('ui_ok');
    // the picked card flies up, the rest fold away
    c.els.forEach((e, k) => e.classList.add(k === c.index ? 'picked' : 'folded'));
    const fan = this.talkFan;
    this.talkFan = null;
    this.tl.wait(0.3).then(() => fan?.remove());
    c.resolve(c.index);
  }

  /**
   * Recruit roll as a gear roulette: the share of gold teeth is the chance; the gear spins and
   * stops with a gold tooth (success) or an ink tooth (fail) under the pointer.
   */
  async chanceRoll(breakdown: [string, number][], chance: number, success: boolean) {
    this.dialog.classList.add('hidden');
    const teeth = 20;
    const gold = Math.max(1, Math.min(teeth - 1, Math.round(chance * teeth)));
    const step = 360 / teeth;
    const rows = breakdown.filter(([, v]) => Math.abs(v) >= 0.005)
      .map(([k, v]) => `<div class="rl-row"><span>${k}</span><b class="${v >= 0 ? 'pos' : 'neg'}">${v >= 0 ? '+' : ''}${Math.round(v * 100)}%</b></div>`).join('');
    const box = (this.talkRoll = el('div', 'talk-roll', `<div class="rl-title">Recruit</div>`
      + `<div class="rl-wheel"><div class="rl-gear">${rouletteSvg(teeth, gold)}</div><div class="rl-pct"><span>${Math.round(chance * 100)}<small>%</small></span></div><div class="rl-ptr">${BLADE_SVG}</div></div>`
      + `<div class="rl-rows">${rows}</div><div class="rl-result"></div>`, this.root));
    const gear = box.querySelector('.rl-gear') as HTMLElement;
    // pick the tooth that ends under the pointer (top), then spin 3 turns + the offset to it
    const tooth = success ? Math.floor(Math.random() * gold) : gold + Math.floor(Math.random() * (teeth - gold));
    const end = 360 * 3 + (360 - (tooth + 0.5) * step);
    let lastTooth = -1;
    await this.tl.tween(2.0, (k) => {
      const r = end * (1 - Math.pow(1 - k, 4)); // fast start, long ratcheting stop
      gear.style.transform = `rotate(${r}deg)`;
      const t = Math.floor(r / step);
      if (t !== lastTooth) { lastTooth = t; if (k < 0.97) Sfx.play('ui_move'); }
    });
    (box.querySelector('.rl-result') as HTMLElement).textContent = success ? 'Success' : 'Failed';
    box.classList.add(success ? 'ok' : 'ng');
    if (success) this.feathers();
    await this.tl.wait(1.0);
    box.remove();
    if (this.talkRoll === box) this.talkRoll = null;
  }

  /** The goddess's feathers drift down — reserved for big moments of grace (UI bible §1). */
  private feathers() {
    const layer = el('div', 'feathers', undefined, this.root);
    const art = artSrc('ui/feather');
    for (let i = 0; i < 14; i++) {
      const f = el('div', 'feather', img(art, FEATHER_SVG), layer);
      f.style.left = `${8 + Math.random() * 84}%`;
      f.style.setProperty('--d', `${(Math.random() * 0.9).toFixed(2)}s`);
      f.style.setProperty('--s', (0.6 + Math.random() * 0.7).toFixed(2));
      f.style.setProperty('--sw', `${((Math.random() < 0.5 ? -1 : 1) * (30 + Math.random() * 50)).toFixed(0)}px`);
    }
    this.tl.wait(3.4).then(() => layer.remove());
  }

  // -------------------------------------------------------------------------
  // Result screens (UI bible §9-4)
  // -------------------------------------------------------------------------
  /**
   * Victory: an ink wedge on the left stamps the rewards in one by one, slanted member cards on the
   * right fill their EXP bars. First confirm skips the animation, the next one closes.
   */
  async victoryScreen(d: VictoryData) {
    this.ui.root.classList.add('battle-result');
    const scr = el('div', 'result-screen victory', undefined, this.root);
    const left = el('div', 'rs-left', '<div class="rs-title">Victory</div>', scr);
    const rewards = el('div', 'rs-rewards', undefined, left);
    const cards = el('div', `rs-cards${d.rows.length > 5 ? ' compact' : ''}`, undefined, scr);
    const next = bindInput(el('div', 'rs-next', '', scr), (s) => `계속 ${s.device === 'pad' ? pb('a') : '<kbd>Enter</kbd>'}`);
    let skip = false;
    this.dialogWait = { resolve: () => {}, skip: () => { skip = true; } };
    const wait = (sec: number) => (skip ? Promise.resolve() : this.tl.wait(sec));
    /** Frame-stepped tween that jumps to the end as soon as the player skips. */
    const tween = async (dur: number, fn: (k: number) => void) => {
      const t0 = this.tl.time;
      while (!skip) {
        const k = Math.min(1, (this.tl.time - t0) / dur);
        fn(k);
        if (k >= 1) return;
        await this.tl.wait(1 / 60);
      }
      fn(1);
    };

    // member cards (enter together, staggered by CSS)
    const ui = d.rows.map((r, i) => {
      const c = el('div', `rs-card${r.reserve ? ' reserve' : ''}`, `<div class="rs-por" style="--c:${r.color}">${portraitInner(r.pid, r.name)}</div>
        <div class="rs-info"><div class="rs-name">${r.name}<span class="lv">Lv${r.fromLv}</span>${r.reserve ? '<span class="rs-res">대기</span>' : ''}</div>
        <div class="rs-bar"><div class="fill"></div></div><div class="rs-gain">EXP <b>+${r.gain}</b></div><div class="rs-tag"></div></div>`, cards);
      c.style.setProperty('--i', String(i));
      return { c, fill: c.querySelector('.fill') as HTMLElement, lv: c.querySelector('.lv') as HTMLElement, tag: c.querySelector('.rs-tag') as HTMLElement };
    });
    const pct = (xp: number, lv: number) => `${Math.min(100, (xp / xpToNext(lv)) * 100)}%`;
    d.rows.forEach((r, i) => { ui[i].fill.style.width = pct(r.fromXp, r.fromLv); });

    // rewards stamp in one row at a time
    await wait(0.35);
    const lines: string[] = [];
    if (d.bonuses.length) {
      const total = d.bonuses.reduce((s, b) => s + b.pct, 0);
      lines.push(`<b class="bonus">전술</b><span>×${(1 + total / 100).toFixed(1)} <small>${d.bonuses.map((b) => `${b.label} +${b.pct}%`).join(' · ')}</small></span>`);
    }
    lines.push(`<b>EXP</b><span class="num">${d.xp}</span>`, `<b>⚙ 기어</b><span class="num gear">0</span>`);
    for (const h of d.drops) lines.push(`<b>획득</b><span>${h}</span>`);
    for (const n of d.recruited) lines.push(`<b class="rec">영입</b><span>${n}</span>`);
    for (const html of lines) {
      const row = el('div', 'rs-row', html, rewards);
      if (!skip) Sfx.play('ui_move');
      const gear = row.querySelector('.gear') as HTMLElement | null;
      if (gear) await tween(0.45, (k) => { gear.textContent = `+${Math.round(d.money * k)}`; });
      await wait(0.14);
    }

    // EXP bars fill together; each level crossed resets the bar and stamps LEVEL UP
    let leveled = false;
    await Promise.all(d.rows.map(async (r, i) => {
      const u = ui[i];
      let lv = r.fromLv, xp = r.fromXp, left = r.gain;
      while (left > 0 && !skip) {
        const take = Math.min(xpToNext(lv) - xp, left);
        const x0 = xp;
        await tween(Math.max(0.2, (0.9 * take) / Math.max(1, r.gain)), (k) => { u.fill.style.width = pct(x0 + take * k, lv); });
        if (skip) break;
        xp += take;
        left -= take;
        if (xp >= xpToNext(lv) && lv < r.toLv) {
          lv++;
          xp = 0;
          u.lv.textContent = `Lv${lv}`;
          u.c.classList.add('up');
          if (!leveled) { leveled = true; Sfx.play('levelup'); this.feathers(); }
          await wait(0.12);
        }
      }
      u.fill.style.width = pct(r.toXp, r.toLv);
      u.lv.textContent = `Lv${r.toLv}`;
      if (r.toLv > r.fromLv) {
        u.c.classList.add('up');
        u.tag.innerHTML = `<span class="lvup">Level Up</span>${r.newSkills.length ? `<span class="skill">새 스킬 · ${r.newSkills.join(', ')}</span>` : ''}`;
      }
    }));
    if (leveled && skip) this.feathers();

    // wait for the player, then fold away
    next.classList.add('on');
    await new Promise<void>((resolve) => {
      this.tl.wait(0.25).then(() => {
        const done = () => { this.dialogWait = null; resolve(); };
        this.dialogWait = { resolve: done };
        scr.addEventListener('click', () => { if (this.dialogWait?.resolve === done) done(); });
      });
    });
    Sfx.play('ui_ok');
    scr.classList.add('out');
    await this.tl.wait(0.2);
    scr.remove();
    this.ui.root.classList.remove('battle-result');
  }

  /** Defeat: the same split composition in crimson; the choices are a blade list inside the wedge. */
  async defeatScreen<T>(items: MenuItem<T>[]): Promise<T | null> {
    this.ui.root.classList.add('battle-result');
    const scr = el('div', 'result-screen defeat', '<div class="rs-left"><div class="rs-title">Defeated</div><div class="rs-sub">원정대가 쓰러졌다</div></div>', this.root);
    await this.tl.wait(0.6);
    this.bladeSpot = { x: 56, y: (this.ui.height / this.ui.scale) * 0.5 };
    const v = await this.menuSelect('', items, { cancellable: false });
    this.bladeSpot = null;
    scr.remove();
    this.ui.root.classList.remove('battle-result');
    return v;
  }

  /** Contextual tip: the battle waits on it (UI bible §9-5). */
  async tip(t: Tip) {
    this.ui.clearBanners();
    const veil = el('div', 'tip-veil', undefined, this.root);
    const e = el('div', 'tip', `<div class="tip-title">${t.title}</div>`, this.root);
    bindInput(el('div', 'tip-body', '', e), t.body);
    bindInput(el('div', 'tip-next', '', e), (s) => `확인 ${s.device === 'pad' ? pb('a') : '<kbd>Enter</kbd>'}`);
    Sfx.play('ui_ok');
    await new Promise<void>((resolve) => {
      // short lock so a held attack/parry key can't dismiss it unread
      this.tl.wait(0.4).then(() => {
        const done = () => { this.dialogWait = null; resolve(); };
        this.dialogWait = { resolve: done };
        e.addEventListener('click', () => { if (this.dialogWait?.resolve === done) done(); });
      });
    });
    Sfx.play('ui_back');
    e.classList.add('out');
    veil.classList.add('out');
    await this.tl.wait(0.15);
    e.remove();
    veil.remove();
  }

  closeDialog() {
    this.dialog.classList.add('hidden');
    this.dialog.innerHTML = '';
    this.dialogWait = null;
    this.dialogChoice = null;
    this.endTalk();
  }

  // -------------------------------------------------------------------------
  update(_dt: number, now: number) {
    this.now = now;
    // menu nav
    if (this.menu) {
      const m = this.menu;
      const n = m.items.length;
      // the ring is circular, so left/right turn it too
      const prev = m.kind === 'ring' ? [...K.up, ...K.left] : K.up;
      const next = m.kind === 'ring' ? [...K.down, ...K.right] : K.down;
      if (Input.pressed(...prev)) this.menuIndex((m.index - 1 + n) % n);
      else if (Input.pressed(...next)) this.menuIndex((m.index + 1) % n);
      else if (Input.pressed('Enter', 'Space', 'NumpadEnter', 'PadA')) this.menuConfirm();
      else if (m.cancellable && Input.pressed('Escape', 'Backspace', 'KeyQ', 'PadB')) {
        Sfx.play('ui_back');
        this.menu = null;
        if (m.kind === 'ring') this.hideCommand();
        else this.bladesEl.classList.add('hidden-ring');
        m.resolve(null);
      } else {
        for (let k = 0; k < Math.min(9, n); k++) if (Input.pressed('Digit' + (k + 1))) { this.menuIndex(k); this.menuConfirm(); break; }
      }
    }
    if (this.target) {
      const t = this.target;
      if (!t.all && Input.pressed(...K.left, ...K.up)) this.targetIndex(t.index - 1);
      else if (!t.all && Input.pressed(...K.right, ...K.down)) this.targetIndex(t.index + 1);
      else if (Input.pressed('Enter', 'Space', 'NumpadEnter', 'KeyF', 'PadA')) this.targetConfirm();
      else if (Input.pressed('Escape', 'Backspace', 'KeyQ', 'PadB')) {
        Sfx.play('ui_back');
        const r = t.resolve;
        this.endTarget();
        r(null);
      }
      if (this.target && !this.target.all) {
        this.arrow.style.display = '';
        this.ui.placeAt(this.arrow, this.target.units[this.target.index].topPos().add(new THREE.Vector3(0, -0.1, 0)));
      } else if (this.target?.all) this.arrow.style.display = 'none';
    }
    if (this.dialogChoice) {
      const c = this.dialogChoice;
      // the fan is horizontal; up/down still work
      if (Input.pressed(...K.left, ...K.up)) this.choiceIndex(c.index - 1);
      else if (Input.pressed(...K.right, ...K.down)) this.choiceIndex(c.index + 1);
      else if (Input.pressed('Enter', 'Space', 'NumpadEnter', 'KeyF', 'PadA')) this.choiceConfirm();
      else for (let k = 0; k < c.els.length; k++) if (Input.pressed('Digit' + (k + 1))) { this.choiceIndex(k); this.choiceConfirm(); break; }
    } else if (this.dialogWait && Input.pressed('Enter', 'Space', 'NumpadEnter', 'KeyF', 'Mouse0', 'PadA')) {
      const w = this.dialogWait;
      if (w.skip) w.skip();
      else { this.dialogWait = null; w.resolve(); }
    }
    if (this.ringUnit) this.placeRing();
    // enemy plates follow units
    for (const u of this.units) {
      if (u.side !== 'enemy' || !u.ui.plate || u.removed || u.ko) continue;
      this.ui.placeAt(u.ui.plate, u.topPos());
    }
    // rings
    for (let i = this.rings.length - 1; i >= 0; i--) {
      const r = this.rings[i];
      if (!r.el.isConnected) { this.rings.splice(i, 1); continue; }
      this.ui.placeAt(r.el, r.anchor(), 'center');
      if (r.done) continue;
      const k = (r.tEnd - now) / r.lead; // 1 → 0
      const outer = r.el.querySelector('.outer') as HTMLElement;
      const s = 1 + Math.max(0, k) * 2.2;
      outer.style.transform = `translate(-50%,-50%) scale(${s})`;
      outer.style.opacity = String(k > 1 ? 0 : Math.min(1, (1 - k) * 3));
      if (now > r.tEnd + 0.25) { r.el.remove(); this.rings.splice(i, 1); }
    }
  }
}
