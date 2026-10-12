import * as THREE from 'three';
import { el } from '../core/utils';
import { State } from '../game/state';
import type { UI } from './ui';
import type { FieldMode } from '../field/field';
import type { FieldEnemy } from '../field/fieldEnemy';
import { ZONES, type GateDef, type ZoneDef } from '../data/zones';
import type { Pos, QuestView } from '../story/chapter1';
import { Input, type InputState } from '../core/input';
import { portraitInner } from './art';
import { pb, type PadButton } from './glyph';
import { heightAt } from '../field/terrain';
import './fieldHud.css';

const _bw = new THREE.Vector3();
const _bc = new THREE.Vector3();

/**
 * Action buttons, laid out like the pad's face buttons (UI bible §9-6). Keyboard players see the
 * matching key/mouse button in the same slot; a slot lights up while its input is held.
 */
interface Action { slot: string; label: string; pad: PadButton; key: string; codes: string[] }
const MOUSE = (side: 'l' | 'r') => `<kbd class="ms ${side}" title="${side === 'l' ? '좌클릭 / J' : '우클릭 / K'}"></kbd>`;
const FACE: Action[] = [
  { slot: 'y', label: '강공격', pad: 'y', key: MOUSE('r'), codes: ['Mouse2', 'KeyK', 'PadY'] },
  { slot: 'x', label: '약공격', pad: 'x', key: MOUSE('l'), codes: ['Mouse0', 'KeyJ', 'PadX'] },
  { slot: 'b', label: '회피', pad: 'b', key: '<kbd>Space</kbd>', codes: ['Space', 'PadB'] },
  { slot: 'a', label: '조사', pad: 'a', key: '<kbd>E</kbd>', codes: ['KeyE', 'PadA'] },
];
const SHOULDER: Action[] = [
  { slot: 'run', label: '달리기', pad: 'lb', key: '<kbd>Shift</kbd>', codes: ['ShiftLeft', 'ShiftRight', 'PadLB'] },
  { slot: 'menu', label: '메뉴', pad: 'start', key: '<kbd>Esc</kbd>', codes: ['Escape', 'PadStart'] },
  { slot: 'log', label: '대사 기록', pad: 'dl', key: '<kbd>L</kbd>', codes: ['KeyL', 'PadLeft'] },
  { slot: 'hide', label: '안내 숨기기', pad: 'back', key: '<kbd>H</kbd>', codes: [] },
];

/** Brass compass ring drawn over the minimap canvas (north-up map, so the ring is static). */
function compassSvg() {
  const c = 100;
  const teeth = Array.from({ length: 40 }, (_, i) => {
    const a = (i / 40) * Math.PI * 2;
    const p = (r: number, da = 0) => `${(c + Math.cos(a + da) * r).toFixed(1)},${(c + Math.sin(a + da) * r).toFixed(1)}`;
    return `<path d="M${p(93, -0.045)} L${p(99, -0.025)} L${p(99, 0.025)} L${p(93, 0.045)}Z"/>`;
  }).join('');
  const ticks = Array.from({ length: 72 }, (_, i) => {
    const a = (i / 72) * Math.PI * 2;
    const r2 = i % 18 === 0 ? 82 : i % 6 === 0 ? 86 : 88;
    return `<line x1="${c + Math.cos(a) * 91}" y1="${c + Math.sin(a) * 91}" x2="${c + Math.cos(a) * r2}" y2="${c + Math.sin(a) * r2}"/>`;
  }).join('');
  return `<svg viewBox="0 0 200 200"><g fill="#b58a2c" stroke="#0b0907" stroke-width="1">${teeth}</g>`
    + `<circle cx="100" cy="100" r="92" fill="none" stroke="#d4a83a" stroke-width="4"/><circle cx="100" cy="100" r="92" fill="none" stroke="#0b0907" stroke-width="1" />`
    + `<g stroke="#0b0907" stroke-width="1.2">${ticks}</g>`
    + `<path d="M100 2 L108 18 L100 14 L92 18Z" fill="#f2c94c" stroke="#0b0907" stroke-width="1.2"/>`
    + `<g font-family="Cinzel, serif" font-weight="800" font-size="11" fill="#f2c94c" text-anchor="middle" stroke="#0b0907" stroke-width="2.5" paint-order="stroke">`
    + `<text x="100" y="30">N</text><text x="174" y="104">E</text><text x="100" y="180">S</text><text x="26" y="104">W</text></g></svg>`;
}

export class FieldHud {
  root: HTMLElement;
  private party: HTMLElement;
  private zoneName: HTMLElement;
  /** current objective line under the minimap (story/quest tracker) */
  private goal: HTMLElement | null = null;
  private prompt: HTMLElement;
  private actions: HTMLElement;
  private slots = new Map<string, { el: HTMLElement; a: Action }>();
  private mapCanvas: HTMLCanvasElement;
  private map: CanvasRenderingContext2D;
  private alerts: { el: HTMLElement; e: FieldEnemy; t: number }[] = [];
  private promptText = '';
  private interactKey = '';
  private mapT = 0;
  private beacons: HTMLElement[] = [];
  /**
   * The field keeps simulating while the HUD is hidden (title backdrop, battle-start wipe), so the
   * HUD must not draw then — otherwise it re-shows the enemy plates `setVisible(false)` just hid.
   */
  private visible = true;

  constructor(private ui: UI, private field: FieldMode) {
    this.root = el('div', 'field-hud', undefined, ui.hudLayer);
    const tl = el('div', 'fh-topleft', undefined, this.root);
    this.zoneName = el('div', 'zone-name', '', tl);
    this.party = el('div', 'fh-party', undefined, tl);
    const tr = el('div', 'fh-map', undefined, this.root);
    this.mapCanvas = el('canvas', '', undefined, tr);
    this.mapCanvas.width = this.mapCanvas.height = 180;
    this.map = this.mapCanvas.getContext('2d')!;
    el('div', 'fh-compass', compassSvg(), tr);
    this.prompt = el('div', 'fh-prompt', '', this.root);
    this.actions = el('div', 'fh-actions', undefined, this.root);
    // in-world objective markers (main first, then the tracked quest). They live on the world layer:
    // the HUD layer is CSS-zoomed by the UI scale, which would multiply their screen coordinates.
    this.beacons = [true, false].map((main) => el('div', `fh-beacon${main ? '' : ' q'}`, '<i class="fb-arrow"></i><b class="fb-gem"></b><span class="fb-d"></span>', ui.layer));
    Input.subscribe((s) => {
      this.renderActions(s);
      this.interactKey = s.device === 'pad' ? pb('a') : '<kbd>E</kbd>';
      this.renderPrompt();
    });
    this.setVisible(false);
  }

  setZone(z: ZoneDef) {
    this.zoneName.textContent = `${z.name} · ${z.sub}`;
  }

  goalPos: Pos | null = null;
  /** the sub-quest picked with 수첩 → 찾기 (one at a time) */
  questPos: Pos | null = null;

  /**
   * Objective tracker under the minimap: the main objective, plus the tracked quest's current step
   * as a second row. Each target gets a minimap marker (filled = main, hollow = quest) and a needle
   * on the compass rim; a target in another zone is pointed at through the gate that leads there.
   */
  setGoal(html: string, pos: Pos | null = null, quest: QuestView | null = null) {
    this.goalPos = pos;
    this.questPos = quest?.pos ?? null;
    if (!this.goal) this.goal = el('div', 'fh-goal', '', this.root);
    const via = (p: Pos | null) => { const g = p && this.route(p); return g ? `<span class="fg-via">${g.label} 방면</span>` : ''; };
    this.goal.innerHTML = (html ? `<div class="fg-row"><span class="fg-k">목표</span>${html}${via(pos)}</div>` : '')
      + (quest ? `<div class="fg-row q"><span class="fg-k">의뢰</span><b>${quest.title}</b><span class="fg-step">${quest.state === 'open' ? `${quest.giver.replace(/ \(.*\)$/, '')}에게 의뢰 받기` : quest.step}</span>${via(quest.pos)}</div>` : '');
    this.goal.style.display = html || quest ? '' : 'none';
  }

  /** The gate in the current zone on the way to `p`'s zone (null when `p` is here or unreachable). */
  private route(p: Pos): GateDef | null {
    const from = this.field.zone?.id;
    if (!from || p.zone === from) return null;
    // breadth-first over the zone graph; remember the first gate taken out of the current zone
    const seen = new Set([from]);
    let frontier: [string, GateDef][] = ZONES[from].gates.map((g) => [g.to, g]);
    while (frontier.length) {
      const next: [string, GateDef][] = [];
      for (const [z, first] of frontier) {
        if (z === p.zone) return first;
        if (seen.has(z) || !ZONES[z]) continue;
        seen.add(z);
        for (const g of ZONES[z].gates) next.push([g.to, first]);
      }
      frontier = next;
    }
    return null;
  }

  /**
   * Objective markers in the 3D view: a gold diamond (main) / hollow diamond (quest) floating over the
   * target with its distance. Off screen or behind the camera, it sticks to the screen edge with an
   * arrow toward it. Targets in another zone are marked at the gate that leads there. Hidden within
   * 4 m (you're there) and during cutscenes.
   */
  private updateBeacons() {
    const f = this.field;
    const cam = f.camera;
    // the camera was moved this frame but its matrices refresh only at render: project with this frame's
    cam.updateMatrixWorld();
    const W = this.ui.width, H = this.ui.height;
    [this.goalPos, this.questPos].forEach((pos, i) => {
      const b = this.beacons[i];
      const m = this.markerAt(pos);
      const dist = m ? Math.hypot(m.x - f.player.pos.x, m.z - f.player.pos.z) : 0;
      if (!m || f.inCutscene || dist < 4) { b.style.display = 'none'; return; }
      _bw.set(m.x, heightAt(m.x, m.z) + 2.4, m.z);
      _bc.copy(_bw).applyMatrix4(cam.matrixWorldInverse);
      const behind = _bc.z > 0;
      _bw.project(cam);
      let x = _bw.x, y = _bw.y;
      if (behind) { x = -x; y = -y; }
      const mx = 0.9, my = 0.8;
      const edge = behind || Math.abs(x) > mx || Math.abs(y) > my;
      if (edge) {
        // push the point out along its direction from the centre until it meets the margin box
        if (behind && Math.hypot(x, y) < 1e-3) y = -1;
        const k = 1 / Math.max(Math.abs(x) / mx, Math.abs(y) / my);
        x *= k; y *= k;
      }
      b.style.display = '';
      b.classList.toggle('edge', edge);
      b.style.transform = `translate(${((x * 0.5 + 0.5) * W).toFixed(1)}px, ${((-y * 0.5 + 0.5) * H).toFixed(1)}px) scale(${this.ui.scale}) translate(-50%, -9px)`; // anchor = the diamond's centre (9 px down)
      if (edge) (b.firstElementChild as HTMLElement).style.transform = `rotate(${Math.atan2(-y, x)}rad)`;
      const d = b.lastElementChild as HTMLElement;
      const txt = `${Math.round(dist)}m`;
      if (d.textContent !== txt) d.textContent = txt;
    });
  }

  /** Where to point for a target: itself when it is in this zone, otherwise the gate toward it. */
  private markerAt(p: Pos | null): { x: number; z: number } | null {
    if (!p) return null;
    if (p.zone === this.field.zone.id) return p;
    return this.route(p);
  }

  setVisible(v: boolean) {
    this.visible = v;
    this.root.style.display = v ? '' : 'none';
    if (!v) {
      for (const b of this.beacons) b.style.display = 'none';
      for (const e of this.field.enemies) if (e.ui) e.ui.root.style.display = 'none';
      // an alert raised right before a battle would otherwise sit unplaced at (0,0) all battle
      for (const a of this.alerts) a.el.remove();
      this.alerts = [];
    }
  }

  /** H / View: hide or show the action-button guide. */
  toggleHelp() {
    this.actions.classList.toggle('hidden');
  }

  private renderActions(s: InputState) {
    const pad = s.device === 'pad';
    this.actions.innerHTML = '';
    this.slots.clear();
    const face = el('div', 'fa-face', undefined, this.actions);
    for (const a of FACE) {
      const e = el('div', `fa-btn fa-${a.slot}`, `<div class="fa-glyph">${pad ? pb(a.pad) : a.key}</div><div class="fa-label">${a.label}</div>`, face);
      this.slots.set(a.slot, { el: e, a });
    }
    const sh = el('div', 'fa-sub', undefined, this.actions);
    for (const a of SHOULDER) {
      const e = el('div', `fa-chip fa-${a.slot}`, `${pad ? pb(a.pad) : a.key}<span>${a.label}</span>`, sh);
      this.slots.set(a.slot, { el: e, a });
    }
    this.renderPrompt();
  }

  /** Interaction prompt text (without the key — that follows the input device). Cheap to call every frame. */
  setPrompt(text: string) {
    if (text === this.promptText) return;
    this.promptText = text;
    this.renderPrompt();
  }

  private renderPrompt() {
    this.prompt.innerHTML = this.promptText ? `${this.interactKey}<span>${this.promptText}</span>` : '';
    this.prompt.style.display = this.promptText ? '' : 'none';
    // the A slot names what it would do right now, and dims when there is nothing to do
    const a = this.slots.get('a');
    if (a) {
      // the prompt is HTML with a dim aside; the slot only gets the plain action
      const short = this.promptText.replace(/<span class="dim">[\s\S]*?<\/span>/g, '').replace(/<[^>]+>/g, '').trim();
      (a.el.querySelector('.fa-label') as HTMLElement).textContent = short || '조사';
      a.el.classList.toggle('idle', !this.promptText);
    }
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
    if (!this.visible) return;
    // party: slanted portrait cards, same grammar as the battle cards
    const html = State.current.activeMembers().map((m, i) => {
      const max = State.current.stats(m).hp;
      const k = Math.max(0, m.hp / max);
      return `<div class="fh-card${k <= 0.3 ? ' low' : ''}" style="--row:${i}"><div class="fc-por" style="--c:${m.color}">${portraitInner(m.id, m.name)}</div>
        <div class="fc-info"><div class="fc-name">${m.name}<span class="lv">Lv${m.level}</span></div>
        <div class="fc-row"><div class="bar hp"><div class="fill" style="width:${k * 100}%"></div></div><div class="fc-hp">${Math.ceil(m.hp)}<small>/${max}</small></div></div></div></div>`;
    }).join('');
    if (this.party.dataset.h !== html) { this.party.innerHTML = html; this.party.dataset.h = html; }

    // action slots light up while held
    for (const { el: e, a } of this.slots.values()) if (a.codes.length) e.classList.toggle('on', Input.isDown(...a.codes));

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
    this.updateBeacons();
    // the minimap doesn't need 60 Hz
    this.mapT -= dt;
    if (this.mapT <= 0) { this.mapT = 1 / 15; this.drawMap(); }
  }

  /** Minimap inside the compass ring: ink ground, gold landmarks, crimson enemies (bible §3). */
  private drawMap() {
    const g = this.map;
    const S = 180, R = S / 2;
    const z = this.field.zone;
    const sc = (R - 6) / z.radius;
    g.clearRect(0, 0, S, S);
    g.save();
    g.beginPath();
    g.arc(R, R, R - 2, 0, Math.PI * 2);
    g.fillStyle = 'rgba(11,9,7,0.82)';
    g.fill();
    g.clip();
    const tx = (x: number) => R + x * sc;
    const tz = (z: number) => R + z * sc;
    // roads
    g.strokeStyle = 'rgba(107,84,32,0.9)';
    g.lineWidth = 3;
    g.beginPath();
    for (const r of z.terrain.roads) r.forEach(([x, zz], i) => (i ? g.lineTo(tx(x), tz(zz)) : g.moveTo(tx(x), tz(zz))));
    g.stroke();
    // plazas + landmarks
    g.fillStyle = 'rgba(107,84,32,0.5)';
    if (z.terrain.paved) { g.beginPath(); g.arc(tx(0), tz(0), z.terrain.paved * sc, 0, Math.PI * 2); g.fill(); }
    for (const p of z.terrain.plazas) { g.beginPath(); g.arc(tx(p.x), tz(p.z), p.r * sc, 0, Math.PI * 2); g.fill(); }
    g.fillStyle = '#f2c94c';
    for (const l of z.landmarks ?? []) g.fillRect(tx(l.x) - 3, tz(l.z) - 3, 6, 6);
    // rest point: gold ring; gates: gold chevrons at the rim; NPCs: bone dots
    g.strokeStyle = '#f2c94c';
    g.lineWidth = 2;
    for (const r of this.field.rests) { g.beginPath(); g.arc(tx(r.x), tz(r.z), 4.5, 0, Math.PI * 2); g.stroke(); }
    for (const gt of z.gates) {
      if (gt.afterFlag && !State.current.flag(gt.afterFlag)) continue;
      const open = !gt.needFlag || State.current.flag(gt.needFlag);
      g.fillStyle = open ? '#f2c94c' : '#6b5420';
      g.beginPath(); g.moveTo(tx(gt.x), tz(gt.z) - 5); g.lineTo(tx(gt.x) + 5, tz(gt.z) + 4); g.lineTo(tx(gt.x) - 5, tz(gt.z) + 4); g.closePath(); g.fill();
    }
    g.fillStyle = '#efe6d2';
    for (const n of this.field.npcs) { g.beginPath(); g.arc(tx(n.def.x), tz(n.def.z), 2.2, 0, Math.PI * 2); g.fill(); }
    // chests
    g.fillStyle = '#d4a83a';
    for (const c of z.chests) {
      if (c.afterFlag && !State.current.flag(c.afterFlag)) continue;
      if (State.current.openedChests.has(c.id)) continue;
      g.fillRect(tx(c.x) - 2.5, tz(c.z) - 2.5, 5, 5);
    }
    // enemies: crimson, stunned ones gold, stronger tiers bigger with an outline
    for (const e of this.field.enemies) {
      if (!e.alive) continue;
      const r = e.sp.tier === 'weak' ? 2.6 : e.sp.tier === 'strong' ? 3.6 : 4.4;
      g.fillStyle = e.stunned ? '#f2c94c' : '#c8283a';
      g.beginPath(); g.arc(tx(e.pos.x), tz(e.pos.z), r, 0, Math.PI * 2); g.fill();
      if (e.sp.tier !== 'weak') { g.strokeStyle = '#efe6d2'; g.lineWidth = 1; g.stroke(); }
    }
    const p = this.field.player;
    // player arrow
    g.translate(tx(p.pos.x), tz(p.pos.z));
    g.rotate(-p.yaw + Math.PI);
    g.fillStyle = '#efe6d2';
    g.strokeStyle = '#0b0907';
    g.lineWidth = 1.5;
    g.beginPath(); g.moveTo(0, -7); g.lineTo(5, 5.5); g.lineTo(0, 3); g.lineTo(-5, 5.5); g.closePath(); g.fill(); g.stroke();
    g.restore();
    this.drawMarkers(tx, tz);
  }

  /**
   * Objective markers, drawn last so nothing covers them: a large gold diamond (main) / hollow
   * diamond (tracked quest) with a pulsing ring, at the gate toward the target when it is in another
   * zone. A needle on the compass rim points from the player toward each target farther than 30 m.
   */
  private drawMarkers(tx: (x: number) => number, tz: (z: number) => number) {
    const g = this.map;
    const R = 90;
    const p = this.field.player;
    const pulse = (performance.now() / 1200) % 1;
    const marks: [{ x: number; z: number } | null, boolean][] = [[this.markerAt(this.questPos), false], [this.markerAt(this.goalPos), true]];
    for (const [m, main] of marks) {
      if (!m) continue;
      const gx = tx(m.x), gz = tz(m.z);
      // pulse ring: grows and fades
      g.save();
      g.globalAlpha = 1 - pulse;
      g.strokeStyle = '#f2c94c';
      g.lineWidth = 2;
      g.beginPath(); g.arc(gx, gz, 8 + pulse * 14, 0, Math.PI * 2); g.stroke();
      g.restore();
      const diamond = (s: number) => { g.beginPath(); g.moveTo(gx, gz - s * 1.2); g.lineTo(gx + s, gz); g.lineTo(gx, gz + s * 1.2); g.lineTo(gx - s, gz); g.closePath(); };
      g.fillStyle = '#0b0907';
      diamond(10); g.fill();
      g.fillStyle = '#f2c94c';
      diamond(7.5); g.fill();
      if (!main) { g.fillStyle = '#0b0907'; diamond(4); g.fill(); }
      const dx = m.x - p.pos.x, dz = m.z - p.pos.z;
      if (dx * dx + dz * dz < 30 * 30) continue;
      const a = Math.atan2(dz, dx);
      const rr = R - 10;
      g.save();
      g.translate(R + Math.cos(a) * rr, R + Math.sin(a) * rr);
      g.rotate(a);
      g.beginPath(); g.moveTo(7, 0); g.lineTo(-6, -6.5); g.lineTo(-2.5, 0); g.lineTo(-6, 6.5); g.closePath();
      g.lineWidth = 2;
      g.strokeStyle = '#0b0907';
      g.fillStyle = main ? '#f2c94c' : '#0b0907';
      g.fill(); g.stroke();
      if (!main) { g.strokeStyle = '#f2c94c'; g.lineWidth = 1.5; g.stroke(); }
      g.restore();
    }
  }
}
