import * as THREE from 'three';
import { el } from '../core/utils';
import { State } from '../game/state';
import type { UI } from './ui';
import type { FieldMode } from '../field/field';
import type { FieldEnemy } from '../field/fieldEnemy';
import { CHESTS, REST_POINT, WORLD_RADIUS, ZONE_NAME } from '../data/world';
import { HEROES } from '../data/units';
import { Input } from '../core/input';
import { fieldHelp } from './controlsHelp';
import { pb } from './glyph';

export class FieldHud {
  root: HTMLElement;
  private party: HTMLElement;
  private prompt: HTMLElement;
  private help: HTMLElement;
  private mapCanvas: HTMLCanvasElement;
  private map: CanvasRenderingContext2D;
  private alerts: { el: HTMLElement; e: FieldEnemy; t: number }[] = [];
  private promptText = '';
  private interactKey = '';
  private mapT = 0;

  constructor(private ui: UI, private field: FieldMode) {
    this.root = el('div', 'field-hud', undefined, ui.hudLayer);
    const tl = el('div', 'fh-topleft', undefined, this.root);
    el('div', 'zone-name', ZONE_NAME, tl);
    this.party = el('div', 'fh-party', undefined, tl);
    const tr = el('div', 'fh-map', undefined, this.root);
    this.mapCanvas = el('canvas', '', undefined, tr);
    this.mapCanvas.width = this.mapCanvas.height = 180;
    this.map = this.mapCanvas.getContext('2d')!;
    this.prompt = el('div', 'fh-prompt', '', this.root);
    this.help = el('div', 'fh-help', '', this.root);
    Input.subscribe((s) => {
      this.help.innerHTML = fieldHelp(s);
      this.interactKey = s.device === 'pad' ? pb('a') : '<kbd>E</kbd>';
      this.renderPrompt();
    });
    this.setVisible(false);
  }

  setVisible(v: boolean) {
    this.root.style.display = v ? '' : 'none';
    if (!v) for (const e of this.field.enemies) if (e.ui) e.ui.root.style.display = 'none';
  }

  toggleHelp() {
    this.help.classList.toggle('hidden');
  }

  /** Interaction prompt text (without the key — that follows the input device). Cheap to call every frame. */
  setPrompt(text: string) {
    if (text === this.promptText) return;
    this.promptText = text;
    this.renderPrompt();
  }

  private renderPrompt() {
    this.prompt.innerHTML = this.promptText ? `${this.interactKey} ${this.promptText}` : '';
    this.prompt.style.display = this.promptText ? '' : 'none';
  }

  alert(e: FieldEnemy) {
    const a = el('div', 'enemy-alert', '!', this.ui.layer);
    this.alerts.push({ el: a, e, t: 0 });
  }

  private ensureEnemyUi(e: FieldEnemy) {
    if (e.ui) return e.ui;
    const root = el('div', 'enemy-plate field', undefined, this.ui.layer);
    const tag = el('div', 'ep-name', `${e.sp.name} <span class="lv">Lv${e.sp.level}</span>`, root);
    const hpw = el('div', 'bar hp', undefined, root);
    const hp = el('div', 'fill', undefined, hpw);
    const bw = el('div', 'bar brk', undefined, root);
    const brk = el('div', 'fill', undefined, bw);
    if (!e.killable) hpw.style.display = 'none';
    e.ui = { root, hp, brk, tag };
    return e.ui;
  }

  update(dt: number) {
    // party
    const html = State.current.activeMembers().map((m) => {
      const st = State.current.stats(m);
      const k = Math.max(0, m.hp / st.hp);
      const title = m.kind === 'hero' ? HEROES[m.id as 'kai'].title : '동료';
      return `<div class="pm"><div class="pm-name" style="color:${m.color}">${m.name} <span class="lv">Lv${m.level}</span> <span class="dim">${title}</span></div>
        <div class="bar hp"><div class="fill" style="width:${k * 100}%"></div></div><div class="pm-hp">${Math.ceil(m.hp)} / ${st.hp}</div></div>`;
    }).join('');
    if (this.party.dataset.h !== html) { this.party.innerHTML = html; this.party.dataset.h = html; }

    // enemy plates
    const ppos = this.field.player.pos;
    for (const e of this.field.enemies) {
      const ui = this.ensureEnemyUi(e);
      const d = e.pos.distanceTo(ppos);
      const show = e.alive && d < 22 && (e.state !== 'idle' && e.state !== 'wander' || d < 10 || e.brk > 0);
      if (!show) { ui.root.style.display = 'none'; continue; }
      if (!this.ui.placeAt(ui.root, e.topPos())) continue;
      ui.hp.style.width = `${(e.hp / e.hpMax) * 100}%`;
      ui.brk.style.width = `${(e.brk / e.brkMax) * 100}%`;
      ui.root.classList.toggle('stunned', e.stunned);
      ui.root.classList.toggle('far', d > 14);
    }
    for (let i = this.alerts.length - 1; i >= 0; i--) {
      const a = this.alerts[i];
      a.t += dt;
      this.ui.placeAt(a.el, a.e.topPos().add(new THREE.Vector3(0, 0.6, 0)));
      if (a.t > 0.9) { a.el.remove(); this.alerts.splice(i, 1); }
    }
    // the minimap doesn't need 60 Hz
    this.mapT -= dt;
    if (this.mapT <= 0) { this.mapT = 1 / 15; this.drawMap(); }
  }

  private drawMap() {
    const g = this.map;
    const S = 180, R = S / 2;
    const sc = (R - 6) / WORLD_RADIUS;
    g.clearRect(0, 0, S, S);
    g.save();
    g.beginPath();
    g.arc(R, R, R - 2, 0, Math.PI * 2);
    g.fillStyle = 'rgba(25,20,14,0.72)';
    g.fill();
    g.clip();
    const tx = (x: number) => R + x * sc;
    const tz = (z: number) => R + z * sc;
    // roads
    g.strokeStyle = 'rgba(200,160,100,0.45)';
    g.lineWidth = 3;
    g.beginPath();
    g.moveTo(tx(0), tz(70)); g.lineTo(tx(0), tz(-30));
    g.moveTo(tx(0), tz(22)); g.lineTo(tx(-30), tz(8)); g.lineTo(tx(-46), tz(-20));
    g.moveTo(tx(0), tz(2)); g.lineTo(tx(32), tz(-8)); g.lineTo(tx(48), tz(-18));
    g.moveTo(tx(0), tz(-30)); g.lineTo(tx(36), tz(-44));
    g.stroke();
    g.fillStyle = 'rgba(200,180,140,0.35)';
    g.beginPath(); g.arc(tx(0), tz(-40), 15 * sc, 0, Math.PI * 2); g.fill();
    g.fillStyle = '#e8c27a';
    g.fillRect(tx(0) - 3, tz(-52) - 3, 6, 6);
    // rest
    g.fillStyle = '#5ff3ff';
    g.beginPath(); g.arc(tx(REST_POINT.x), tz(REST_POINT.z), 4, 0, Math.PI * 2); g.fill();
    // chests
    for (const c of CHESTS) {
      if (State.current.openedChests.has(c.id)) continue;
      g.fillStyle = '#ffd34a';
      g.fillRect(tx(c.x) - 2.5, tz(c.z) - 2.5, 5, 5);
    }
    // enemies
    for (const e of this.field.enemies) {
      if (!e.alive) continue;
      g.fillStyle = e.stunned ? '#ffe066' : e.sp.tier === 'elite' ? '#ff4aa8' : e.sp.tier === 'strong' ? '#ff7a3a' : '#ff4a3a';
      g.beginPath(); g.arc(tx(e.pos.x), tz(e.pos.z), e.sp.tier === 'weak' ? 2.6 : 3.6, 0, Math.PI * 2); g.fill();
    }
    // player arrow
    const p = this.field.player;
    g.translate(tx(p.pos.x), tz(p.pos.z));
    g.rotate(-p.yaw + Math.PI);
    g.fillStyle = '#ffffff';
    g.beginPath(); g.moveTo(0, -6); g.lineTo(4.5, 5); g.lineTo(0, 2.5); g.lineTo(-4.5, 5); g.closePath(); g.fill();
    g.restore();
    g.strokeStyle = '#b08a4a';
    g.lineWidth = 3;
    g.beginPath(); g.arc(R, R, R - 2, 0, Math.PI * 2); g.stroke();
    g.fillStyle = '#e8c27a';
    g.font = 'bold 11px Cinzel, serif';
    g.fillText('N', R - 4, 13);
  }
}
