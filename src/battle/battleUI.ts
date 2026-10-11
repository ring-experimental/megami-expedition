import * as THREE from 'three';
import { Input, K, type InputState } from '../core/input';
import { Sfx } from '../core/audio';
import { el } from '../core/utils';
import { STATUS_INFO } from '../data/types';
import type { UI } from '../ui/ui';
import { icon, portraitInner, type Expression } from '../ui/art';
import { bindInput, pb } from '../ui/glyph';
import type { Timeline } from '../core/timeline';
import type { BUnit } from './bunit';

export interface MenuItem<T> { label: string; right?: string; desc?: string; disabled?: boolean; value: T; cls?: string }

interface ActiveMenu {
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
  private cmdBox: HTMLElement;
  private cmdTitle: HTMLElement;
  private cmdList: HTMLElement;
  private cmdDesc: HTMLElement;
  private defHint: HTMLElement;
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
    this.cmdBox = el('div', 'cmd-box', undefined, this.root);
    this.cmdTitle = el('div', 'cmd-title', '', this.cmdBox);
    this.cmdList = el('div', 'cmd-list', '', this.cmdBox);
    this.cmdDesc = el('div', 'cmd-desc', '', this.cmdBox);
    bindInput(el('div', 'cmd-hint', '', this.cmdBox), (s) => s.device === 'pad'
      ? `${pb('dpad')} 선택 · ${pb('a')} 결정 · ${pb('b')} 취소`
      : '<kbd>W</kbd><kbd>S</kbd> 선택 · <kbd>Enter</kbd> 결정 · <kbd>Esc</kbd> 취소');
    this.defHint = bindInput(el('div', 'def-hint', '', this.root), (s) => s.device === 'pad'
      ? `<span>${pb('a')}/${pb('rb')} 패링</span><span>${pb('b')} 회피</span>`
      : '<span><kbd>F</kbd>/<kbd>좌클릭</kbd> 패링</span><span><kbd>Space</kbd>/<kbd>우클릭</kbd> 회피</span>');
    this.arrow = el('div', 'target-arrow', '▼', ui.layer);
    this.ringLayer = el('div', 'ring-layer', undefined, this.root);
    this.dialog = el('div', 'dialog hidden', undefined, this.root);
    this.hideCommand();
    this.showDefHint(false);
    this.arrow.style.display = 'none';
    this.root.style.display = 'none';
  }

  show(v: boolean) {
    this.root.style.display = v ? '' : 'none';
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
        const st = el('div', 'statuses', '', plate);
        const tag = el('div', 'ep-tag', '', plate);
        plate.addEventListener('click', () => this.clickTarget(u));
        plate.addEventListener('mouseenter', () => this.hoverTarget(u));
        u.ui = { plate, hp, hpt, brk, st, tag };
      } else {
        const card = el('div', 'party-card', undefined, this.partyPanel);
        const por = el('div', 'portrait', portraitInner(u.pid, u.name), card);
        por.style.setProperty('--c', u.color);
        const info = el('div', 'pc-info', undefined, card);
        el('div', 'pc-name', `${u.name} <span class="lv">Lv${u.level}</span>`, info);
        const hpw = el('div', 'bar hp', undefined, info);
        const hp = el('div', 'fill', undefined, hpw);
        const hpt = el('div', 'pc-hp', '', info);
        const ap = el('div', 'ap-pips', '', info);
        const st = el('div', 'statuses', '', info);
        card.addEventListener('click', () => this.clickTarget(u));
        card.addEventListener('mouseenter', () => this.hoverTarget(u));
        u.ui = { plate: card, hp, hpt, ap, st };
      }
    }
  }

  setActive(u: BUnit | null) {
    for (const x of this.units) x.ui.plate?.classList.toggle('active', x === u);
  }

  setOrder(list: BUnit[]) {
    this.order.innerHTML = '';
    el('div', 'to-label', 'TURN', this.order);
    list.forEach((u, i) => {
      const c = el('div', `to-chip ${u.side}${i === 0 ? ' now' : ''}${u.broken ? ' broken' : ''}`, portraitInner(u.pid, u.name), this.order);
      c.style.setProperty('--c', u.color);
      c.title = u.name;
    });
  }

  refresh() {
    for (const u of this.units) {
      const ui = u.ui;
      if (!ui.plate) continue;
      ui.hp.style.width = `${Math.max(0, u.hp / u.maxHp) * 100}%`;
      ui.hpt.textContent = `${Math.max(0, Math.ceil(u.hp))} / ${u.maxHp}`;
      ui.st.innerHTML = u.statuses.map((s) => `<span class="st ${STATUS_INFO[s.id].good ? 'good' : 'bad'}" title="${STATUS_INFO[s.id].name}">${icon('st', s.id, STATUS_INFO[s.id].icon)}${s.turns}</span>`).join('');
      ui.plate.classList.toggle('ko', u.ko);
      if (u.side === 'enemy') {
        ui.brk.style.width = `${(u.broken ? 1 : u.brk / u.brkMax) * 100}%`;
        ui.plate.classList.toggle('broken', u.broken);
        ui.tag.innerHTML = u.broken ? 'BREAK' : u.rapport > 0 ? `<span class="rapport" title="패링 성공 횟수 (설득 보너스)">♦${u.rapport}</span>` : '';
        ui.plate.style.display = u.removed || u.ko ? 'none' : '';
      } else {
        ui.ap.innerHTML = Array.from({ length: 9 }, (_, i) => `<i class="${i < u.ap ? 'on' : ''}"></i>`).join('');
      }
    }
  }

  // -------------------------------------------------------------------------
  // Command menu
  // -------------------------------------------------------------------------
  menuSelect<T>(title: string, items: MenuItem<T>[], opts: { cancellable?: boolean; onHover?: (v: T) => void; startIndex?: number } = {}): Promise<T | null> {
    this.cmdBox.style.display = '';
    this.cmdTitle.innerHTML = title;
    this.cmdList.innerHTML = '';
    const els = items.map((it, i) => {
      const e = el('div', `cmd-item${it.disabled ? ' disabled' : ''} ${it.cls ?? ''}`, `<span>${it.label}</span>${it.right ? `<span class="r">${it.right}</span>` : ''}`, this.cmdList);
      e.addEventListener('mouseenter', () => this.menu && this.menuIndex(i));
      e.addEventListener('click', () => { if (this.menu) { this.menuIndex(i); this.menuConfirm(); } });
      return e;
    });
    return new Promise((resolve) => {
      let start = opts.startIndex ?? 0;
      while (items[start]?.disabled && start < items.length - 1) start++;
      this.menu = { items: items as MenuItem<unknown>[], index: start, resolve: resolve as (v: unknown) => void, cancellable: opts.cancellable ?? true, onHover: opts.onHover as ((v: unknown) => void) | undefined, els };
      this.menuIndex(start, true);
    });
  }

  private menuIndex(i: number, silent = false) {
    const m = this.menu!;
    if (i !== m.index && !silent) Sfx.play('ui_move');
    m.index = i;
    m.els.forEach((e, k) => e.classList.toggle('sel', k === i));
    const it = m.items[i];
    // the description slot keeps a fixed height even when empty (no layout shift)
    this.cmdDesc.innerHTML = it?.desc ?? '';
    this.cmdDesc.title = this.cmdDesc.textContent ?? '';
    if (import.meta.env.DEV && this.cmdDesc.scrollHeight > this.cmdDesc.clientHeight + 1) {
      console.warn('[ui] command description exceeds the 2-line slot and is clipped:', this.cmdDesc.textContent);
    }
    if (it) m.onHover?.(it.value);
  }

  private menuConfirm() {
    const m = this.menu!;
    const it = m.items[m.index];
    if (!it || it.disabled) { Sfx.play('ui_error'); return; }
    Sfx.play('ui_ok');
    this.menu = null;
    this.hideCommand();
    m.resolve(it.value);
  }

  hideCommand() {
    this.cmdBox.style.display = 'none';
  }

  // -------------------------------------------------------------------------
  // Target selection
  // -------------------------------------------------------------------------
  selectTarget(units: BUnit[], opts: { all?: boolean; onHover?: (u: BUnit | 'all') => void; camera: THREE.Camera }): Promise<BUnit | 'all' | null> {
    // order left → right on screen
    const sorted = [...units].sort((a, b) => a.pos.clone().project(opts.camera).x - b.pos.clone().project(opts.camera).x);
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
  ring(anchor: () => THREE.Vector3, tEnd: number, lead: number, kind: 'parry' | 'qte') {
    const e = el('div', `timing-ring ${kind}`, '<div class="outer"></div><div class="inner"></div>', this.ringLayer);
    if (kind === 'qte') bindInput(el('div', 'key', '', e), (s) => (s.device === 'pad' ? pb('a') : 'F'));
    const r: Ring = { el: e, anchor, tEnd, lead, kind, done: false };
    this.rings.push(r);
    return {
      result: (txt: string, cls: string) => {
        r.done = true;
        e.classList.add('res', cls);
        e.querySelector('.inner')!.innerHTML = `<span>${txt}</span>`;
        setTimeout(() => e.remove(), 450);
      },
      remove: () => { r.done = true; e.remove(); },
    };
  }

  showDefHint(v: boolean) {
    this.defHint.style.display = v ? '' : 'none';
  }

  // -------------------------------------------------------------------------
  // Dialog (negotiation)
  // -------------------------------------------------------------------------
  async say(speaker: string, text: string, color = '#e8c27a', pid = '', expr?: Expression) {
    this.dialog.classList.remove('hidden');
    this.dialog.innerHTML = `<div class="dl-portrait" style="--c:${color}">${portraitInner(pid || 'system', speaker, expr)}</div><div class="dl-body"><div class="dl-name" style="color:${color}">${speaker}</div><div class="dl-text"></div><div class="dl-next">▼</div></div>`;
    const tEl = this.dialog.querySelector('.dl-text') as HTMLElement;
    let skip = false;
    await new Promise<void>((resolve) => {
      this.dialogWait = { resolve, skip: () => { skip = true; } };
      let i = 0;
      const tick = () => {
        if (skip) i = text.length;
        tEl.textContent = text.slice(0, i);
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

  choose(speaker: string, text: string, choices: string[], color = '#e8c27a', pid = ''): Promise<number> {
    this.dialog.classList.remove('hidden');
    this.dialog.classList.add('done');
    this.dialog.innerHTML = `<div class="dl-portrait" style="--c:${color}">${portraitInner(pid || 'system', speaker)}</div><div class="dl-body"><div class="dl-name" style="color:${color}">${speaker}</div><div class="dl-text">${text}</div><div class="dl-choices"></div></div>`;
    const box = this.dialog.querySelector('.dl-choices') as HTMLElement;
    const els = choices.map((c, i) => {
      const e = el('div', 'dl-choice', `<span class="n"></span>${c}`, box);
      // number keys pick a choice on the keyboard; meaningless on a pad
      bindInput(e.querySelector('.n') as HTMLElement, (s) => (s.device === 'pad' ? '' : String(i + 1)));
      e.addEventListener('mouseenter', () => this.choiceIndex(i));
      e.addEventListener('click', () => { this.choiceIndex(i); this.choiceConfirm(); });
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
    c.resolve(c.index);
  }

  /** Recruit chance gauge with breakdown; animates a roll and resolves with success. */
  async chanceRoll(breakdown: [string, number][], chance: number, success: boolean) {
    this.dialog.classList.remove('hidden');
    this.dialog.classList.add('done');
    const rows = breakdown.filter(([, v]) => Math.abs(v) >= 0.005).map(([k, v]) => `<div class="cr-row"><span>${k}</span><span class="${v >= 0 ? 'pos' : 'neg'}">${v >= 0 ? '+' : ''}${Math.round(v * 100)}%</span></div>`).join('');
    this.dialog.innerHTML = `<div class="chance-box"><div class="cr-title">영입 판정</div><div class="cr-rows">${rows}</div>
      <div class="cr-gauge"><div class="cr-zone" style="width:${chance * 100}%"></div><div class="cr-needle"></div></div>
      <div class="cr-pct">${Math.round(chance * 100)}%</div><div class="cr-result"></div></div>`;
    const needle = this.dialog.querySelector('.cr-needle') as HTMLElement;
    const res = this.dialog.querySelector('.cr-result') as HTMLElement;
    // the needle sweeps and lands inside (success) or outside (fail) the zone
    const land = success ? Math.random() * chance * 0.92 + chance * 0.04 : chance + (1 - chance) * (0.08 + Math.random() * 0.84);
    await this.tl.tween(1.5, (k) => {
      const sweep = k < 1 ? (Math.sin(k * Math.PI * 5) * 0.5 + 0.5) * (1 - k) + land * k : land;
      needle.style.left = `${sweep * 100}%`;
    });
    res.textContent = success ? '성공!' : '실패...';
    res.className = 'cr-result ' + (success ? 'ok' : 'ng');
    await this.tl.wait(0.9);
  }

  /** Centered panel that waits for confirm. Pass a function when the content names keys/buttons. */
  panel(content: string | ((s: InputState) => string), cls = ''): Promise<void> {
    const p = el('div', 'result-panel ' + cls, typeof content === 'string' ? content : '', this.root);
    if (typeof content !== 'string') bindInput(el('div', '', '', p), content);
    bindInput(el('div', 'rp-next', '', p), (s) => `계속 ${s.device === 'pad' ? pb('a') : '<kbd>Enter</kbd> / 클릭'}`);
    return new Promise((resolve) => {
      const done = () => { p.remove(); this.dialogWait = null; resolve(); };
      this.tl.wait(0.35).then(() => {
        this.dialogWait = { resolve: done };
        p.addEventListener('click', () => { if (this.dialogWait?.resolve === done) done(); });
      });
    });
  }

  closeDialog() {
    this.dialog.classList.add('hidden');
    this.dialog.innerHTML = '';
    this.dialogWait = null;
    this.dialogChoice = null;
  }

  // -------------------------------------------------------------------------
  update(_dt: number, now: number) {
    this.now = now;
    // menu nav
    if (this.menu) {
      const m = this.menu;
      const n = m.items.length;
      if (Input.pressed(...K.up)) this.menuIndex((m.index - 1 + n) % n);
      else if (Input.pressed(...K.down)) this.menuIndex((m.index + 1) % n);
      else if (Input.pressed('Enter', 'Space', 'NumpadEnter', 'PadA')) this.menuConfirm();
      else if (m.cancellable && Input.pressed('Escape', 'Backspace', 'KeyQ', 'PadB')) {
        Sfx.play('ui_back');
        this.menu = null;
        this.hideCommand();
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
        this.ui.placeAt(this.arrow, this.target.units[this.target.index].topPos().add(new THREE.Vector3(0, 0.45, 0)));
      } else if (this.target?.all) this.arrow.style.display = 'none';
    }
    if (this.dialogChoice) {
      const c = this.dialogChoice;
      if (Input.pressed(...K.up)) this.choiceIndex(c.index - 1);
      else if (Input.pressed(...K.down)) this.choiceIndex(c.index + 1);
      else if (Input.pressed('Enter', 'Space', 'NumpadEnter', 'KeyF', 'PadA')) this.choiceConfirm();
      else for (let k = 0; k < c.els.length; k++) if (Input.pressed('Digit' + (k + 1))) { this.choiceIndex(k); this.choiceConfirm(); break; }
    } else if (this.dialogWait && Input.pressed('Enter', 'Space', 'NumpadEnter', 'KeyF', 'Mouse0', 'PadA')) {
      const w = this.dialogWait;
      if (w.skip) w.skip();
      else { this.dialogWait = null; w.resolve(); }
    }
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
