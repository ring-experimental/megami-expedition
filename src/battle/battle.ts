import * as THREE from 'three';
import { getModel, getProp } from '../core/assets';
import { Sfx } from '../core/audio';
import { Input } from '../core/input';
import { Timeline } from '../core/timeline';
import { chance, clamp, easeInOutQuad, easeOutCubic, josa, rand } from '../core/utils';
import { Effects } from '../fx/effects';
import { patchObject } from '../fx/fakeLights';
import { animateBackdrop, animateMotes, buildBackdrop, buildMotes, buildSky, getEnvMap } from '../fx/environment';
import { BASIC_ATTACK, SIGIL_ELEMENTS, SKILLS, fuseSkill, tempoOf, type SkillDef } from '../data/skills';
import { ITEMS } from '../data/items';
import { SPECIES, type EnemyMove } from '../data/units';
import { BATTLE_SPEEDS, DIFFICULTY, ELEMENT_COLOR, ELEMENT_NAME, type Element } from '../data/types';
import { State } from '../game/state';
import type { Game } from '../game/game';
import type { FieldEnemy } from '../field/fieldEnemy';
import { BUnit } from './bunit';
import { BattleUI, type MenuItem, type VictoryRow } from './battleUI';
import { DefenseSession, QTE_MULT, QteSession, spaceHits, type DefenseResult, type QteGrade } from './timing';
import { negotiate } from './negotiation';
import { TIPS, type TipId } from './tips';
import { icon } from '../ui/art';

export interface BattleRequest {
  formation: string[];
  leaderHp: number;
  advantage: 'party' | 'enemy' | 'none';
  source: FieldEnemy | null;
}
export type BattleResult = 'victory' | 'fled' | 'defeat' | 'retry';

type Cmd =
  | { kind: 'attack'; target: BUnit }
  | { kind: 'skill'; skill: SkillDef; targets: BUnit[] }
  | { kind: 'item'; item: string; target: BUnit }
  | { kind: 'talk'; target: BUnit }
  | { kind: 'flee' };

const ENEMY_Z = -4.4;
const PARTY_Z = 4.6;

export class BattleMode {
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(50, 1, 0.1, 900);
  fx: Effects;
  tl = new Timeline();
  bui: BattleUI;
  units: BUnit[] = [];
  active = false;
  private req!: BattleRequest;
  private sessions: { update: (now: number) => void; dispose: () => void }[] = [];
  private camPos = new THREE.Vector3(0, 8, 16);
  private camLook = new THREE.Vector3(0, 1, 0);
  private wantPos = new THREE.Vector3(0, 8, 16);
  private wantLook = new THREE.Vector3(0, 1, 0);
  private camLambda = 4;
  private shake = 0;
  private backdrop: THREE.Object3D;
  private motes: THREE.Points;
  private time = 0;
  private recruited: string[] = [];
  private lastCmd: Record<string, number> = {};
  private pendingTip: TipId | null = null;
  /** Turns taken so far; turn-order slot n carries `slotBonus.get(n)` (궤적-style AT bonus). */
  private turnNo = 0;
  private slotBonus = new Map<number, SlotBonus>();
  /** Multiplier on the acting unit's next turn interval, set by the action it took (CTB tempo). */
  private actionTempo = 1;
  /** a weakness hit this action already pulled the actor's next turn forward */
  private pulled = false;
  /** Feats tallied for the tactical bonus (victory EXP / 기어 multiplier). */
  private feats = { parries: 0, counters: 0, weak: 0, breaks: 0, dmgTaken: 0, partyTurns: 0 };

  constructor(private game: Game) {
    const s = this.scene;
    s.environment = getEnvMap(game.renderer);
    s.environmentIntensity = 0.5;
    s.fog = new THREE.Fog('#c99a86', 70, 260);
    s.add(buildSky({ top: '#2b3f7a', horizon: '#ffb38a', bottom: '#7a5a6a', sun: '#ffc9a0', sunDir: new THREE.Vector3(0.3, 0.18, -1) }));
    this.backdrop = buildBackdrop({ mountainColor: '#7d6f8f', cloudColor: '#ffd2bd', seed: 9, radius: 120 });
    s.add(this.backdrop);
    s.add(new THREE.HemisphereLight('#ffd6c0', '#4a3f5a', 1.0));
    const key = new THREE.DirectionalLight('#ffe2c4', 2.4);
    key.position.set(-12, 22, 14);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    const sc = key.shadow.camera;
    sc.left = sc.bottom = -18;
    sc.right = sc.top = 18;
    sc.far = 80;
    key.shadow.bias = -0.0005;
    key.shadow.normalBias = 0.03;
    s.add(key);
    const rim = new THREE.DirectionalLight('#8fb8ff', 1.2);
    rim.position.set(10, 8, -16);
    s.add(rim);
    const arena = getModel('arena');
    s.add(arena);
    const tower = getProp('prop_clocktower');
    tower.position.set(-46, -18, -95);
    tower.scale.setScalar(1.8);
    s.add(tower);
    this.motes = buildMotes(220, 40, '#ffd9a8');
    s.add(this.motes);
    this.fx = new Effects(s);
    patchObject(s);
    this.bui = new BattleUI(game.ui, this.tl);
  }

  get party() { return this.units.filter((u) => u.side === 'party'); }
  get enemies() { return this.units.filter((u) => u.side === 'enemy'); }
  get diff() { return State.current.difficulty; }

  resize(w: number, h: number) {
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.fx.setViewport(h * this.game.renderer.getPixelRatio(), this.camera.fov);
  }

  // =====================================================================
  // Setup
  // =====================================================================
  private setup(req: BattleRequest) {
    this.req = req;
    this.recruited = [];
    this.feats = { parries: 0, counters: 0, weak: 0, breaks: 0, dmgTaken: 0, partyTurns: 0 };
    this.turnNo = 0;
    this.slotBonus.clear();
    for (const u of this.units) this.scene.remove(u.obj);
    this.units = [];
    this.fx.clear();
    this.tl.clear();
    const st = State.current;
    const members = st.activeMembers();
    const px = members.length === 1 ? [0] : members.length === 2 ? [-1.9, 1.9] : [-3.4, 0, 3.4];
    members.forEach((m, i) => {
      const u = new BUnit('party', { member: m });
      u.setHome(new THREE.Vector3(px[i], 0, PARTY_Z + (i === 1 ? 0.6 : 0)), Math.PI);
      if (u.hero) u.anim.stance = 'ready';
      u.ap = 1;
      this.units.push(u);
    });
    const n = req.formation.length;
    const ex = n === 1 ? [0] : n === 2 ? [-2.4, 2.4] : [-3.8, 0, 3.8];
    req.formation.forEach((id, i) => {
      const sp = SPECIES[id];
      const u = new BUnit('enemy', { species: sp, hpRatio: i === 0 ? req.leaderHp : 1 });
      u.setHome(new THREE.Vector3(ex[i] * (sp.radius * sp.battleScale > 1 ? 1.3 : 1), 0, ENEMY_Z - (i === 1 && n === 3 ? 0.9 : 0) - (sp.radius * sp.battleScale > 1.2 ? 0.8 : 0)), 0);
      st.bestiary[id].seen = true;
      this.units.push(u);
    });
    for (const u of this.units) this.scene.add(u.obj);
    patchObject(this.scene); // cloned unit materials lose onBeforeCompile

    // initial turn times (CTB)
    for (const u of this.units) u.ct = (100 / u.speed()) * rand(0.15, 0.9);
    if (req.advantage === 'party') {
      this.party.forEach((u, i) => (u.ct = i * 0.01));
      for (const e of this.enemies) { e.ct += 2; e.broken = true; e.brk = e.brkMax; }
    } else if (req.advantage === 'enemy') {
      this.enemies.forEach((u, i) => (u.ct = i * 0.01));
      for (const p of this.party) p.ct += 2;
    }
    this.bui.setUnits(this.units);
    this.bui.refresh();
  }

  // =====================================================================
  // Main flow
  // =====================================================================
  async start(req: BattleRequest): Promise<BattleResult> {
    this.setup(req);
    this.active = true;
    this.game.ui.camera = this.camera;
    this.bui.show(true);
    this.bui.setSpeed(st0().battleSpeed);
    this.updateOrder();

    // intro camera sweep
    this.setCam(new THREE.Vector3(14, 9, 18), new THREE.Vector3(0, 1, 0), 0, true);
    this.setCam(new THREE.Vector3(0, 6.5, 15), new THREE.Vector3(0, 1.2, -1), 2.2);
    await this.tl.wait(0.25);
    if (req.advantage === 'party') { this.game.ui.banner('선제 공격!', '적 전원 브레이크 · 아군 선행동', 'gold'); Sfx.play('advantage'); }
    else if (req.advantage === 'enemy') { this.game.ui.banner('기습당했다!', '적이 먼저 행동한다', 'red'); Sfx.play('ambush'); }
    else { this.game.ui.banner('BATTLE', '', ''); Sfx.play('battle_start'); }
    for (const e of this.enemies) if (e.broken) this.fx.ring(e.centerPos(), 0xffe066, 2, 0.6);
    this.bui.refresh();
    await this.tl.wait(1.3);

    let result: BattleResult | null = null;
    while (!result) {
      result = this.checkEnd();
      if (result) break;
      const u = this.nextActor();
      u.ct += 100 / u.speed();
      this.updateOrder();
      if (!(await this.turnStart(u))) { result = this.checkEnd(); continue; }
      if (u.side === 'party') {
        this.feats.partyTurns++;
        this.actionTempo = 1;
        this.pulled = false;
        const r = await this.partyTurn(u);
        if (r === 'fled') { result = 'fled'; break; }
        // heavy skills push the next turn back, quick actions and weakness hits pull it forward
        u.ct += (this.actionTempo - 1) * (100 / u.speed());
      } else {
        await this.enemyTurn(u);
      }
      this.turnEnd(u);
      this.bui.refresh();
      await this.tl.wait(0.15);
      result = this.checkEnd();
    }
    return this.finish(result);
  }

  private checkEnd(): BattleResult | null {
    if (this.enemies.every((e) => !e.alive)) return 'victory';
    if (this.party.every((p) => p.ko)) return 'defeat';
    return null;
  }

  private nextActor() {
    let best: BUnit | null = null;
    for (const u of this.units) {
      if (u.removed || (u.side === 'enemy' && u.ko)) continue;
      if (u.side === 'party' && u.ko) continue;
      if (!best || u.ct < best.ct) best = u;
    }
    return best!;
  }

  private computeOrder(n: number, ctOverride?: Map<BUnit, number>) {
    const sim = this.units.filter((u) => u.alive).map((u) => ({ u, ct: ctOverride?.get(u) ?? u.ct, spd: u.speed() }));
    const out: BUnit[] = [];
    for (let i = 0; i < n && sim.length; i++) {
      sim.sort((a, b) => a.ct - b.ct);
      out.push(sim[0].u);
      sim[0].ct += 100 / sim[0].spd;
    }
    return out;
  }

  private current: BUnit | null = null;
  private updateOrder(ctOverride?: Map<BUnit, number>) {
    const list = this.computeOrder(8, ctOverride);
    // slot bonuses: the acting unit already took its slot (turnNo - 1); the rest are upcoming slots
    const cur = !!(this.current && this.current.alive);
    if (cur) list.unshift(this.current!);
    const shown = list.slice(0, 8);
    const bonuses = shown.map((_, i) => (cur && i === 0 ? null : this.bonusAt(this.turnNo + i - (cur ? 1 : 0))));
    this.bui.setOrder(shown, bonuses, !!ctOverride);
  }

  /** Bonus of turn slot n, rolled the first time the slot comes into view (none in the first 2). */
  private bonusAt(n: number): SlotBonus | null {
    if (!this.slotBonus.has(n)) {
      const roll = n < 2 ? null : chance(0.24) ? SLOT_BONUSES[Math.floor(Math.random() * SLOT_BONUSES.length)] : null;
      this.slotBonus.set(n, roll as SlotBonus);
    }
    return this.slotBonus.get(n) ?? null;
  }

  /**
   * FFX-style preview while choosing: the order as it would be after this action (own tempo,
   * plus a delay on the hovered target). Shows who would land on the bonus slots.
   */
  private previewOrder(u: BUnit, tempo: number, target?: BUnit, delay = 0) {
    const m = new Map<BUnit, number>();
    m.set(u, u.ct + (tempo - 1) * (100 / u.speed()));
    if (target && delay) m.set(target, target.ct + (delay / 100) * (100 / target.speed()));
    this.updateOrder(m);
  }

  /** Returns false if the unit cannot act this turn. */
  /** Show a tip the first time its concept comes up (the battle waits on it). */
  private async tip(id: TipId) {
    const seen = State.current.tipsSeen;
    if (seen.has(id)) return;
    seen.add(id);
    await this.bui.tip(TIPS[id]);
  }

  private async turnStart(u: BUnit) {
    // tips raised mid-action (break) wait for the next turn boundary
    if (this.pendingTip) { const t = this.pendingTip; this.pendingTip = null; await this.tip(t); }
    const slot = this.turnNo++;
    this.current = u;
    this.updateOrder();
    if ([...this.slotBonus.values()].some(Boolean)) await this.tip('bonus');
    this.bui.setActive(u);
    if (u.has('overheat')) {
      const d = Math.max(1, Math.round(u.maxHp * 0.05));
      u.hp = Math.max(1, u.hp - d); // the boiler scalds but never knocks Kai out
      this.fx.smoke.burst(u.centerPos(), 14, { color: 0xf4f1ea, speed: 2.5, up: 1.5, life: 0.8, size: 0.5, sizeEnd: 1.6, alpha: 0.5 });
      this.game.ui.popup(u.centerPos(), `${d}`, 'dmg burn');
      this.bui.refresh();
      await this.tl.wait(0.3);
    }
    if (u.has('burn')) {
      const d = Math.max(1, Math.round(u.maxHp * 0.06));
      u.hp = Math.max(u.side === 'party' ? 0 : 0, u.hp - d);
      this.fx.sparks.burst(u.centerPos(), 16, { color: 0xff7a2a, speed: 3, up: 1, life: 0.6, size: 0.18 });
      this.game.ui.popup(u.centerPos(), `${d}`, 'dmg burn');
      Sfx.play('fire');
      this.bui.refresh();
      if (u.hp <= 0) { await this.ko(u); return false; }
      await this.tl.wait(0.4);
    }
    if (u.broken) {
      u.broken = false;
      u.brk = 0;
      this.setCam(u.centerPos().add(new THREE.Vector3(3, 2, 6)), u.centerPos(), 4);
      this.game.ui.popup(u.topPos(), '기절 중...', 'info');
      u.anim.stunned = true;
      await this.tl.wait(0.8);
      u.anim.stunned = false;
      this.game.ui.popup(u.topPos(), '브레이크 회복', 'info');
      this.bui.refresh();
      await this.tl.wait(0.3);
      return false;
    }
    if (u.side === 'party') u.ap = Math.min(9, u.ap + 1);
    const b = this.slotBonus.get(slot);
    if (b) await this.applySlotBonus(u, b);
    this.bui.refresh();
    return true;
  }

  private async applySlotBonus(u: BUnit, b: SlotBonus) {
    const party = u.side === 'party';
    const label = { heal: 'HP +15%', ap: party ? 'AP +2' : '방어↑', crit: 'CRITICAL', brk: party ? 'BREAK ×2' : '공격↑' }[b];
    this.game.ui.popup(u.topPos(), label, `bonus ${u.side}`, 1.1);
    Sfx.play(party ? 'buff' : 'ui_error');
    if (b === 'heal') this.heal(u, Math.round(u.maxHp * 0.15));
    else if (b === 'ap') { if (party) u.ap = Math.min(9, u.ap + 2); else u.addStatus('defUp', 2); }
    else if (b === 'crit') u.bonus = 'crit';
    else if (party) u.bonus = 'brk';
    else u.addStatus('atkUp', 2);
    this.fx.pillar(u.pos.clone(), party ? 0xffe9a0 : 0xff6a50, 3, u.radius + 0.3, 0.6);
    await this.tl.wait(0.35);
  }

  private turnEnd(u: BUnit) {
    u.bonus = null;
    for (const s of u.statuses) s.turns--;
    u.statuses = u.statuses.filter((s) => s.turns > 0);
    this.current = null;
    this.bui.setActive(null);
  }

  // =====================================================================
  // Party turn
  // =====================================================================
  private async partyTurn(u: BUnit): Promise<'done' | 'fled'> {
    for (;;) {
      this.camCommand(u);
      await this.tip('ap');
      const cmd = await this.chooseCommand(u);
      this.updateOrder(); // drop the hover preview
      if (cmd) this.bui.hideCommand();
      if (!cmd) continue;
      switch (cmd.kind) {
        case 'attack': await this.doAttack(u, cmd.target); return 'done';
        case 'skill': await this.doSkill(u, cmd.skill, cmd.targets); return 'done';
        case 'item': await this.doItem(u, cmd.item, cmd.target); return 'done';
        case 'talk': {
          const consumed = await this.doTalk(u, cmd.target);
          if (consumed) return 'done';
          continue;
        }
        case 'flee': {
          if (await this.doFlee()) return 'fled';
          return 'done';
        }
      }
    }
  }

  private async chooseCommand(u: BUnit): Promise<Cmd | null> {
    const st = State.current;
    const enemies = this.enemies.filter((e) => e.alive);
    const title = `<span style="color:${u.color}">${u.name}</span>의 턴 <span class="ap">AP ${u.ap}</span>`;
    const top = await this.bui.menuSelect<string>(title, [
      { label: `${icon('cmd', 'attack')}공격`, right: 'AP +1', desc: u.hero?.basicMelee === false || u.species?.archetype === 'wisp' ? '원거리 기본 공격. AP +1' : '기본 공격. AP +1', value: 'attack' },
      { label: `${icon('cmd', 'skill')}스킬`, right: '▶', desc: 'AP를 소모하는 스킬. 사용 중 타이밍 입력(QTE)으로 위력 상승.', value: 'skill' },
      { label: `${icon('cmd', 'talk')}대화`, right: '▶', desc: '적과 협상해 동료로 영입을 시도한다. (턴 소모)', value: 'talk' },
      { label: `${icon('cmd', 'item')}아이템`, right: '▶', desc: '소지품을 사용한다.', value: 'item' },
      { label: `${icon('cmd', 'flee')}도주`, desc: '전투에서 벗어난다.', value: 'flee' },
    ], { cancellable: false, startIndex: this.lastCmd[u.uid] ?? 0, ring: u,
      onHover: (v) => this.previewOrder(u, v === 'attack' ? tempoOf(BASIC_ATTACK) : v === 'item' ? tempoOf(null) : 1) });
    const idx = ['attack', 'skill', 'talk', 'item', 'flee'].indexOf(top!);
    this.lastCmd[u.uid] = idx;
    const pickEnemy = async (sk: SkillDef = BASIC_ATTACK) => {
      const t = await this.bui.selectTarget(enemies, { camera: this.camera, onHover: (x) => {
        if (x === 'all') return;
        this.camTarget(u, x);
        this.previewOrder(u, tempoOf(sk), x, sk.delay ?? 0);
      } });
      return t === 'all' ? null : t;
    };
    if (top === 'attack') {
      const t = await pickEnemy();
      return t ? { kind: 'attack', target: t } : null;
    }
    if (top === 'skill') {
      const items: MenuItem<SkillDef>[] = u.skills.map((id) => SKILLS[id]).filter(Boolean).map((base) => {
        // 회로 결합 shows the spell the stored sigils make; 방열 일섬 shows the heat it would vent
        const fused = base.fuse ? (u.sigils.length === 2 ? fuseSkill(u.sigils[0], u.sigils[1]) : null) : null;
        const sk = fused ?? base;
        const extra = base.fuse
          ? (fused ? ` <span class="kw">${u.sigils.map((e) => ELEMENT_NAME[e]).join('+')} → ${fused.name}</span>` : ' <span class="dim">(서로 다른 각인 2개 필요)</span>')
          : base.vent ? ` <span class="kw">열압 ${Math.round(u.heat)}%</span>` : '';
        const tempo = tempoOf(sk);
        const tags = [ELEMENT_NAME[sk.element], sk.qte ? `QTE ${sk.qte}회` : '', sk.delay ? '지연' : '', tempo > 1 ? '다음 턴 늦음' : ''].filter(Boolean).join(' · ');
        return {
          label: `${icon('el', sk.element)}${base.fuse && fused ? fused.name : sk.name}`,
          right: `${sk.ap} AP`,
          desc: `${sk.desc}${extra} <span class="dim">[${tags}]</span>`,
          disabled: sk.ap > u.ap || (base.fuse && !fused),
          value: sk,
        };
      });
      const sk = await this.bui.menuSelect<SkillDef>(`${u.name} · 스킬`, items, { onHover: (v) => this.previewOrder(u, tempoOf(v)) });
      if (!sk) { this.updateOrder(); return null; }
      if (sk.target === 'enemy') {
        const t = await pickEnemy(sk);
        return t ? { kind: 'skill', skill: sk, targets: [t] } : null;
      }
      if (sk.target === 'allEnemies') {
        const t = await this.bui.selectTarget(enemies, { all: true, camera: this.camera, onHover: () => this.camOverview() });
        return t ? { kind: 'skill', skill: sk, targets: enemies } : null;
      }
      if (sk.target === 'allAllies') {
        const allies = this.party.filter((p) => !p.ko);
        const t = await this.bui.selectTarget(allies, { all: true, camera: this.camera, onHover: () => this.camParty() });
        return t ? { kind: 'skill', skill: sk, targets: allies } : null;
      }
      if (sk.target === 'self') return { kind: 'skill', skill: sk, targets: [u] };
      const allies = this.party.filter((p) => !p.ko);
      const t = await this.bui.selectTarget(allies, { camera: this.camera, onHover: () => this.camParty() });
      return t && t !== 'all' ? { kind: 'skill', skill: sk, targets: [t] } : null;
    }
    if (top === 'talk') {
      const t = await pickEnemy();
      return t ? { kind: 'talk', target: t } : null;
    }
    if (top === 'item') {
      const items = Object.entries(st.inventory).filter(([, n]) => n > 0).map(([id, n]) => ({
        label: `${icon('item', id, ITEMS[id].icon)} ${ITEMS[id].name}`, right: `×${n}`, desc: ITEMS[id].desc, value: id,
      }));
      if (!items.length) { this.game.ui.toast('사용할 아이템이 없다'); return null; }
      const id = await this.bui.menuSelect<string>('아이템', items);
      if (!id) return null;
      const def = ITEMS[id];
      const cands = this.party.filter((p) => (def.target === 'allyKO' ? p.ko : !p.ko));
      if (!cands.length) { this.game.ui.toast('대상이 없다'); return null; }
      const t = await this.bui.selectTarget(cands, { camera: this.camera, onHover: () => this.camParty() });
      return t && t !== 'all' ? { kind: 'item', item: id, target: t } : null;
    }
    if (top === 'flee') return { kind: 'flee' };
    return null;
  }

  // =====================================================================
  // Party actions
  // =====================================================================
  private isRanged(u: BUnit) {
    if (u.hero) return !u.hero.basicMelee;
    return u.species?.archetype === 'wisp';
  }

  private async doAttack(u: BUnit, target: BUnit) {
    this.actionTempo = tempoOf(BASIC_ATTACK);
    await this.performSkill(u, BASIC_ATTACK, [target], this.isRanged(u));
    u.ap = Math.min(9, u.ap + 1);
    await this.addHeat(u, 8);
    this.bui.refresh();
  }

  private async doSkill(u: BUnit, sk: SkillDef, targets: BUnit[]) {
    u.ap -= sk.ap;
    this.actionTempo = tempoOf(sk);
    this.bui.refresh();
    if (sk.qte > 0) await this.tip('qte');
    if (sk.vent) await this.tip('heat');
    await this.bui.cutIn({ unit: u, title: sk.name, sub: sk.fuse ? `${u.name} · 회로 결합` : u.name });
    const vented = sk.vent ? u.heat : 0;
    await this.performSkill(u, sk.vent ? { ...sk, power: sk.power + (vented / 100) * 2.6 } : sk, targets, !sk.melee);
    if (sk.vent) { u.heat = 0; if (vented >= 50) this.game.ui.popup(u.topPos(), `방열 ${Math.round(vented)}%`, 'buff'); }
    else await this.addHeat(u, sk.ap * 12);
    if (sk.fuse) u.sigils = [];
    else if (u.hero?.id === 'lyra' && sk.kind === 'magic' && SIGIL_ELEMENTS.includes(sk.element)) {
      const first = !u.sigils.length;
      u.sigils = [...u.sigils, sk.element].slice(-2);
      this.game.ui.popup(u.topPos(), `각인 · ${ELEMENT_NAME[sk.element]}`, 'buff');
      if (first) this.pendingTip ??= 'circuit';
    }
    this.bui.refresh();
  }

  /** Kai's 열압: at 100 the boiler overheats (공격 ×1.35, scalds 5% HP a turn, 2 turns), then resets. */
  private async addHeat(u: BUnit, v: number) {
    if (u.hero?.id !== 'kai' || u.has('overheat')) return;
    u.heat = Math.min(100, u.heat + v);
    if (u.heat < 100) return;
    u.heat = 0;
    u.addStatus('overheat', 3);
    Sfx.play('fire');
    this.fx.smoke.burst(u.centerPos(), 30, { color: 0xf4f1ea, speed: 4, up: 2, life: 1, size: 0.6, sizeEnd: 2.2, alpha: 0.6 });
    await this.bui.cutIn({ unit: u, title: '과열', sub: '공격 ×1.35 · 매 턴 HP 5% 소모' }, 0.45);
    if (!State.current.tipsSeen.has('heat')) this.pendingTip ??= 'heat';
  }

  /** Shared choreography for attacks / skills with QTE. */
  private async performSkill(u: BUnit, sk: SkillDef, targets: BUnit[], ranged: boolean) {
    const alive = () => targets.filter((t) => t.alive || (sk.kind !== 'phys' && sk.kind !== 'magic' && !t.ko));
    const isOffense = sk.kind === 'phys' || sk.kind === 'magic';
    const main = targets[0];
    const element: Element = sk.id === 'attack' ? (u.hero?.basicElement ?? (u.species?.archetype === 'wisp' ? 'fire' : 'phys')) : sk.element;
    const kind = sk.id === 'attack' && this.isRanged(u) ? 'magic' : sk.kind;
    // approach
    if (isOffense && !ranged) {
      const dest = sk.target === 'allEnemies'
        ? new THREE.Vector3(0, 0, ENEMY_Z + 3.2)
        : main.home.clone().add(new THREE.Vector3(0, 0, 1.3 + main.radius + u.radius));
      this.camAction(u, main);
      await this.moveUnit(u, dest, 0.38, sk.target === 'allEnemies' ? new THREE.Vector3(0, 0, ENEMY_Z) : main.pos);
    } else {
      this.camAction(u, main);
      await this.tl.wait(0.2);
    }

    const qte = sk.qte > 0 ? new QteSession(this.tl, this.diff) : null;
    if (qte) this.sessions.push(qte);
    for (let h = 0; h < sk.hits; h++) {
      if (!alive().length && isOffense) break;
      let grade: QteGrade | null = null;
      if (qte && h < sk.qte) {
        const lead = h === 0 ? 0.8 : 0.55;
        const tEnd = this.tl.time + lead;
        const anchorUnit = isOffense ? alive()[0] ?? main : u;
        const ring = this.bui.ring(() => anchorUnit.centerPos(), tEnd, lead, 'qte');
        if (h === 0) u.anim.play(ranged || !isOffense ? 'cast' : 'charge', ranged || !isOffense ? 0.6 : 1.2);
        grade = await new Promise<QteGrade>((res) => qte.add(tEnd, res));
        ring.result(grade === 'perfect' ? 'PERFECT' : grade === 'good' ? 'GOOD' : 'MISS', grade);
        Sfx.play(grade === 'perfect' ? 'qte_perfect' : grade === 'good' ? 'qte_good' : 'qte_miss');
        if (grade === 'perfect') Input.rumble(0, 0.6, 70);
      }
      const mult = grade ? QTE_MULT[grade] : 1;
      // strike
      const clip = this.strikeClip(u, sk, h, ranged);
      u.anim.release();
      u.anim.play(clip.name, clip.speed);
      await this.tl.wait(clip.hitAt);
      if (ranged && isOffense) {
        const from = this.castPoint(u);
        const tgt = alive();
        Sfx.play('magic');
        await Promise.all(tgt.map((t) => this.fx.projectile(from, t.centerPos(), ELEMENT_COLOR[element], 0.32, 0.22, 0.8)));
      } else if (!isOffense) {
        Sfx.play(sk.kind === 'heal' ? 'heal' : 'buff');
      } else {
        Sfx.play(sk.anim === 'heavy' || sk.anim === 'thrust' ? 'swing_heavy' : 'swing');
        const yaw = u.obj.rotation.y;
        this.fx.slash(u.pos.clone().add(new THREE.Vector3(0, 1.1, 0)).add(new THREE.Vector3(Math.sin(yaw), 0, Math.cos(yaw)).multiplyScalar(0.8)), yaw, ELEMENT_COLOR[element], 2, (h % 3 - 1) * 0.6, 0.22);
      }
      for (const t of alive()) {
        if (isOffense) {
          this.hitUnit(u, t, { kind: kind as 'phys' | 'magic', element, power: sk.power, mult, brk: sk.breakPower * (grade === 'perfect' ? 1.5 : 1) });
          if (sk.delay && h === 0 && t.alive) {
            t.ct += (sk.delay / 100) * (100 / t.speed());
            this.game.ui.popup(t.topPos().add(new THREE.Vector3(0, 0.4, 0)), 'DELAY', 'info');
            this.updateOrder();
          }
          if (sk.status && !sk.status.self && t.alive && chance(sk.status.chance)) {
            t.addStatus(sk.status.id, sk.status.turns);
            this.game.ui.popup(t.topPos(), sk.status.id === 'burn' ? '화상' : '상태 이상', 'info');
          }
        } else if (sk.kind === 'heal') {
          const amt = Math.round(u.stats.mag * sk.power * 2.4 * mult + 10);
          this.heal(t, amt);
        } else if (sk.kind === 'buff' && sk.status) {
          t.addStatus(sk.status.id, sk.status.turns + (grade === 'perfect' ? 1 : 0));
          if (sk.id === 'wind_up') t.addStatus('atkUp', sk.status.turns);
          if (sk.id === 'iron_shell') t.addStatus('defUp', sk.status.turns);
          this.fx.pillar(t.pos.clone(), sk.status.id === 'defUp' || sk.status.id === 'guard' ? 0x8fe8ff : 0xffc46b, 3, 0.7, 0.8);
          this.game.ui.popup(t.topPos(), `${statusLabel(sk.status.id)}`, 'buff');
        }
      }
      this.bui.refresh();
      await this.tl.wait(Math.max(0.12, clip.rest));
    }
    if (qte) { qte.dispose(); this.sessions = this.sessions.filter((s) => s !== qte); }
    if (sk.status?.self && sk.kind !== 'buff') u.addStatus(sk.status.id, sk.status.turns);
    await this.tl.wait(0.2);
    if (isOffense && !ranged) await this.returnHome(u);
    else this.faceHome(u);
  }

  private strikeClip(u: BUnit, sk: SkillDef, h: number, ranged: boolean) {
    if (ranged || sk.anim === 'cast' || sk.kind === 'heal' || sk.kind === 'buff') return { name: 'cast', speed: 1.3, hitAt: 0.34, rest: 0.25 };
    if (!u.hero) return { name: 'attack', speed: 1.1, hitAt: 0.3, rest: 0.25 };
    if (sk.anim === 'thrust') return { name: 'thrust', speed: 1, hitAt: 0.32, rest: 0.3 };
    if (sk.anim === 'heavy') return { name: 'heavy', speed: 1, hitAt: 0.5, rest: 0.35 };
    if (sk.anim === 'spin') return [{ name: 'heavy', speed: 1.2, hitAt: 0.42, rest: 0.2 }, { name: 'slash1', speed: 1, hitAt: 0.2, rest: 0.15 }, { name: 'slash2', speed: 1, hitAt: 0.2, rest: 0.2 }][h % 3];
    return [{ name: 'slash1', speed: 1, hitAt: 0.2, rest: 0.15 }, { name: 'slash2', speed: 1, hitAt: 0.2, rest: 0.15 }, { name: 'slash3', speed: 1, hitAt: 0.27, rest: 0.25 }][h % 3];
  }

  private castPoint(u: BUnit) {
    const tip = u.anim.rig.get('staff_tip') ?? u.anim.rig.get('flame') ?? u.anim.rig.get('weapon');
    const p = new THREE.Vector3();
    if (tip) tip.getWorldPosition(p);
    else p.copy(u.centerPos());
    return p;
  }

  private async doItem(u: BUnit, id: string, t: BUnit) {
    this.actionTempo = tempoOf(null);
    const def = ITEMS[id];
    if (!State.current.useItem(id)) return;
    this.game.ui.moveName(`${icon('item', id, def.icon)} ${def.name}`);
    u.anim.play('item');
    await this.tl.wait(0.35);
    if (def.revive && t.ko) {
      t.hp = Math.round(t.maxHp * def.revive);
      t.anim.release();
      t.anim.action = null;
      t.anim.model.rotation.set(0, 0, 0);
      this.fx.pillar(t.pos.clone(), 0xffe9a0, 4, 0.9, 1.1);
      this.game.ui.popup(t.topPos(), '부활!', 'heal');
      Sfx.play('heal');
    }
    if (def.heal) this.heal(t, def.heal);
    if (def.ap) {
      t.ap = Math.min(9, t.ap + def.ap);
      this.fx.pillar(t.pos.clone(), 0xbff6ff, 3, 0.7, 0.8);
      this.game.ui.popup(t.topPos(), `AP +${def.ap}`, 'buff');
      Sfx.play('buff');
    }
    this.bui.refresh();
    await this.tl.wait(0.6);
  }

  private async doTalk(u: BUnit, e: BUnit): Promise<boolean> {
    // two-shot camera
    const mid = u.pos.clone().lerp(e.pos, 0.5);
    this.setCam(mid.clone().add(new THREE.Vector3(6.5, 2.4, 1.5)), mid.clone().add(new THREE.Vector3(0, 1.1, 0)), 4);
    u.anim.play('talk');
    e.anim.play('talk');
    await this.tip('talk');
    const res = await negotiate(this.bui, u, e, State.current.difficulty !== 'hard');
    const st = State.current;
    switch (res.outcome) {
      case 'blocked':
        return false;
      case 'joined': {
        const sp = e.species!;
        const r = st.recruit(sp.id, e.level);
        this.recruited.push(sp.id);
        this.fx.pillar(e.pos.clone(), 0xb8ffef, 6, 1.3, 1.6);
        Sfx.play('recruit');
        if (r.absorbed) {
          this.game.ui.banner(`${josa(sp.name, '이', '가')} 동료에게 합류!`, `같은 종족 동료 흡수 · EXP +${r.xp}${r.levelUp ? ` · Lv${r.levelUp.from}→${r.levelUp.to}` : ''}`, 'cyan', 2000);
        } else {
          this.game.ui.banner(`${josa(sp.name, '이', '가')} 동료가 되었다!`, r.member && st.active.includes(sp.id) ? '파티에 합류했다 (다음 전투부터 참가)' : '대기 멤버로 합류했다 (메뉴에서 편성)', 'cyan', 2000);
        }
        await this.vanish(e);
        break;
      }
      case 'left':
        this.game.ui.banner(`${josa(e.name, '은', '는')} 떠나버렸다...`, '', '', 1400);
        await this.vanish(e);
        break;
      case 'angry':
        e.addStatus('enraged', 3);
        e.ct = Math.min(e.ct, this.nextActor().ct - 0.01);
        this.game.ui.popup(e.topPos(), '격노!', 'dmg');
        Sfx.play('talk_fail');
        break;
      case 'failed':
        break;
    }
    this.updateOrder();
    this.bui.refresh();
    return true;
  }

  private async vanish(e: BUnit) {
    const from = e.obj.scale.x;
    const p0 = e.pos.y;
    await this.tl.tween(0.9, (k) => {
      e.obj.scale.setScalar(from * (1 - k * 0.9));
      e.pos.y = p0 + k * 2;
    }, easeInOutQuad);
    e.removed = true;
    e.obj.visible = false;
    if (e.ui.plate) e.ui.plate.style.display = 'none';
  }

  private async doFlee(): Promise<boolean> {
    const elite = this.enemies.some((e) => e.alive && e.species?.tier === 'elite');
    const p = clamp(0.6 + (this.req.advantage === 'party' ? 0.2 : 0) - (elite ? 0.35 : 0), 0.1, 0.95);
    this.game.ui.moveName('도주');
    if (Math.random() < p) {
      Sfx.play('dodge');
      for (const u of this.party) if (!u.ko) { u.obj.rotation.y = 0; u.anim.speed = 6; }
      await this.tl.tween(0.6, (k) => { for (const u of this.party) if (!u.ko) u.pos.z = u.home.z + k * 6; });
      return true;
    }
    this.game.ui.banner('도주 실패!', '', 'red', 900);
    Sfx.play('ui_error');
    await this.tl.wait(0.8);
    return false;
  }

  // =====================================================================
  // Enemy turn
  // =====================================================================
  private chooseMove(e: BUnit): EnemyMove {
    const moves = e.species!.moves.filter((m) => {
      if (m.kind !== 'self') return true;
      if (m.heal) return e.hp < e.maxHp * 0.5;
      if (m.status) return !e.has(m.status.id);
      return true;
    });
    const total = moves.reduce((s, m) => s + m.weight, 0);
    let r = Math.random() * total;
    for (const m of moves) { r -= m.weight; if (r <= 0) return m; }
    return moves[0];
  }

  private pickTarget(): BUnit {
    const alive = this.party.filter((p) => !p.ko);
    const guard = alive.find((p) => p.has('guard'));
    if (guard && chance(0.8)) return guard;
    const w = alive.map((p) => 1 + (1 - p.hp / p.maxHp) * 1.2);
    let r = Math.random() * w.reduce((a, b) => a + b, 0);
    for (let i = 0; i < alive.length; i++) { r -= w[i]; if (r <= 0) return alive[i]; }
    return alive[0];
  }

  private async enemyTurn(e: BUnit) {
    const mv = this.chooseMove(e);
    if (mv.kind !== 'self') await this.tip('parry');
    if (mv.jump) await this.tip('jump');
    this.game.ui.moveName(`${e.name} · ${mv.name}${mv.jump ? ' <span class="jump-tag">JUMP</span>' : ''}`, 'enemy');
    if (mv.kind === 'self') {
      this.setCam(e.centerPos().add(new THREE.Vector3(2.5, 1.5, 5)), e.centerPos(), 4);
      await e.anim.play('cast');
      if (mv.heal) this.heal(e, Math.round(e.maxHp * mv.heal));
      if (mv.status) {
        e.addStatus(mv.status.id, mv.status.turns);
        this.fx.pillar(e.pos.clone(), mv.status.id === 'defUp' ? 0x8fe8ff : 0xff7a2a, 4, e.radius + 0.4, 0.9);
        this.game.ui.popup(e.topPos(), statusLabel(mv.status.id), 'buff');
        Sfx.play('buff');
      }
      this.bui.refresh();
      await this.tl.wait(0.5);
      return;
    }

    const alive = this.party.filter((p) => !p.ko);
    if (!alive.length) return;
    const main = mv.allTargets ? alive[Math.floor(alive.length / 2)] : this.pickTarget();
    const targets = mv.allTargets ? alive : [main];
    this.camDefend(mv.allTargets ? null : main, e);
    await this.tl.wait(0.45);

    if (mv.kind === 'melee') {
      const dest = mv.allTargets
        ? new THREE.Vector3(0, 0, PARTY_Z - 2.6 - e.radius)
        : main.home.clone().add(new THREE.Vector3(0, 0, -(1.2 + e.radius + main.radius)));
      await this.moveUnit(e, dest, 0.6, mv.allTargets ? new THREE.Vector3(0, 0, PARTY_Z) : main.pos);
      this.camDefend(mv.allTargets ? null : main, e);
    }

    // wind-up (randomized: read the tell!)
    const diff = DIFFICULTY[this.diff];
    const windup = rand(mv.windup[0], mv.windup[1]);
    e.anim.play('windup', 0.5 / windup);
    const t0 = this.tl.time + windup;
    const hitTimes = spaceHits(mv.hits).map((h) => t0 + h);
    const def = new DefenseSession(this.tl, this.diff, !!mv.jump);
    this.sessions.push(def);
    this.bui.showDefHint(true, !!mv.jump);
    def.onWhiff = (kind) => {
      for (const t of targets) {
        if (t.ko) continue;
        if (kind === 'jump') void this.hop(t, 0.5);
        else t.anim.play(kind === 'parry' ? 'parry' : 'sidestep', 1.4);
      }
    };
    const showRing = diff.showRing && State.current.showParryRing;
    const results: DefenseResult[] = [];
    const anchor = mv.allTargets ? () => new THREE.Vector3(0, 1.2, PARTY_Z) : () => main.centerPos();
    const rings = hitTimes.map((ht) => (showRing ? this.bui.ring(anchor, ht, 0.7, mv.jump ? 'jump' : 'parry') : null));

    hitTimes.forEach((ht, i) => {
      // strike visuals scheduled to land on time
      if (mv.kind === 'melee') {
        this.tl.wait(Math.max(0, ht - 0.08 - this.tl.time)).then(() => { e.anim.release(); e.anim.play('strike'); });
      } else {
        const travel = 0.38;
        this.tl.wait(Math.max(0, ht - travel - 0.1 - this.tl.time)).then(() => {
          e.anim.play(i === 0 ? 'cast' : 'strike', 1.4);
        });
        this.tl.wait(Math.max(0, ht - travel - this.tl.time)).then(() => {
          const from = this.castPoint(e);
          for (const t of targets) this.fx.projectile(from, t.centerPos(), ELEMENT_COLOR[mv.element], travel, 0.26, 0.6);
        });
      }
      // hard mode tell: a quick glint just before impact
      if (!showRing) {
        this.tl.wait(Math.max(0, ht - 0.32 - this.tl.time)).then(() => {
          this.fx.sparks.emit(e.centerPos().add(new THREE.Vector3(0, 0.4, 0.4)), { color: 0xffffff, life: 0.18, size: 0.9, sizeEnd: 0.1 });
          e.flashT = 0.1;
        });
      }
      // a ground shockwave rolls out under the party on impact
      if (mv.jump) {
        this.tl.wait(Math.max(0, ht - 0.05 - this.tl.time)).then(() => {
          this.fx.ring(new THREE.Vector3(0, 0.15, PARTY_Z - 1), 0xffd27a, 7, 0.35);
          this.fx.smoke.burst(new THREE.Vector3(0, 0.2, PARTY_Z - 1.5), 18, { color: 0xd9c7a8, speed: 5, up: 0.4, life: 0.6, size: 0.5, sizeEnd: 1.4, alpha: 0.5 });
          this.shake = Math.max(this.shake, 0.25);
        });
      }
      def.addHit(ht, (res) => {
        results[i] = res;
        rings[i]?.result(res === 'parry' ? 'PARRY' : res === 'dodge' ? 'DODGE' : res === 'jump' ? 'JUMP' : '', res);
        this.resolveEnemyHit(e, mv, targets, res);
      });
    });

    // wait until all hits resolved
    while (!def.done) await this.tl.wait(0.03);
    def.dispose();
    this.sessions = this.sessions.filter((s) => s !== def);
    this.bui.showDefHint(false);
    e.anim.release();
    await this.tl.wait(0.35);

    // perfect defense (every hit parried, or every shockwave jumped) → counter attack
    if (results.length && (results.every((r) => r === 'parry') || results.every((r) => r === 'jump')) && e.alive) {
      const counterer = targets.find((t) => !t.ko);
      if (counterer) await this.counter(counterer, e);
    }
    if (mv.kind === 'melee' && e.alive) await this.returnHome(e);
    this.bui.refresh();
  }

  private resolveEnemyHit(e: BUnit, mv: EnemyMove, targets: BUnit[], res: DefenseResult) {
    const live = targets.filter((t) => !t.ko);
    if (res === 'parry') {
      e.rapport++;
      this.feats.parries++;
      Sfx.play('parry');
      Input.rumble(0.35, 0.8, 90);
      this.shake = 0.18;
      for (const t of live) {
        t.anim.play('parry', 1.2);
        t.ap = Math.min(9, t.ap + 1);
        const p = t.centerPos().lerp(e.centerPos(), 0.3);
        this.fx.sparks.burst(p, 26, { color: 0xbff6ff, speed: 9, life: 0.35, size: 0.12, drag: 0.1 });
        this.fx.ring(p, 0xbff6ff, 1.6, 0.25, e.pos.clone().sub(t.pos));
        this.fx.flash(p, 0xbff6ff, 25, 6, 0.15);
      }
      this.game.ui.popup(live[0]?.topPos() ?? e.topPos(), 'PARRY!', 'parry');
      if (!e.broken) this.addBreak(e, 5);
      // Kai vents boiler pressure into the parry
      for (const t of live) if (t.hero?.id === 'kai') t.heat = Math.max(0, t.heat - 10);
    } else if (res === 'jump') {
      Sfx.play('dodge');
      for (const t of live) void this.hop(t);
      this.game.ui.popup(live[0]?.topPos() ?? e.topPos(), 'JUMP', 'dodge');
    } else if (res === 'dodge') {
      Sfx.play('dodge');
      for (const t of live) t.anim.play('sidestep', 1.1);
      this.game.ui.popup(live[0]?.topPos() ?? e.topPos(), 'DODGE', 'dodge');
    } else {
      for (const t of live) {
        this.hitUnit(e, t, { kind: mv.stat === 'mag' ? 'magic' : 'phys', element: mv.element, power: mv.power, mult: DIFFICULTY[this.diff].enemyDmg, brk: 0 });
        if (mv.status && !mv.status.self && t.alive && chance(mv.status.chance)) {
          t.addStatus(mv.status.id, mv.status.turns);
          this.game.ui.popup(t.topPos(), statusLabel(mv.status.id), 'info');
        }
      }
    }
    this.bui.refresh();
  }

  private async counter(u: BUnit, e: BUnit) {
    this.feats.counters++;
    await this.bui.cutIn({ unit: u, title: 'Counter', sub: u.name }, 0.35);
    Sfx.play('counter');
    const ranged = this.isRanged(u);
    this.camAction(u, e);
    if (ranged) {
      u.anim.play('cast', 1.5);
      await this.tl.wait(0.25);
      await this.fx.projectile(this.castPoint(u), e.centerPos(), ELEMENT_COLOR[u.hero?.basicElement ?? 'aether'], 0.25, 0.3, 0.3);
    } else {
      const d = e.pos.clone().sub(u.pos).setY(0);
      const dest = e.pos.clone().sub(d.normalize().multiplyScalar(1.1 + e.radius));
      await this.moveUnit(u, dest, 0.18, e.pos);
      u.anim.play('slash3', 1.3);
      await this.tl.wait(0.2);
      this.fx.slash(u.pos.clone().add(new THREE.Vector3(0, 1.1, 0)), u.obj.rotation.y, 0xffe9a0, 2.4, 1.2, 0.25);
    }
    this.hitUnit(u, e, { kind: ranged ? 'magic' : 'phys', element: u.hero?.basicElement ?? 'phys', power: 1.5, mult: 1, brk: 25 });
    await this.tl.wait(0.4);
    if (!ranged) await this.returnHome(u);
  }

  // =====================================================================
  // Damage / heal / break
  // =====================================================================
  private hitUnit(att: BUnit, def: BUnit, o: { kind: 'phys' | 'magic'; element: Element; power: number; mult: number; brk: number }) {
    if (!def.alive) return;
    const atk = o.kind === 'magic' ? att.stats.mag : att.stats.atk;
    const dst = o.kind === 'magic' ? def.stats.res : def.stats.def;
    let dmg = atk * o.power * 2.2 * (60 / (60 + dst)) * att.atkMult() * def.defMult() * o.mult * rand(0.92, 1.08);
    const aff = def.species && def.side === 'enemy' ? def.species.affinity[o.element] ?? 1 : 1;
    dmg *= aff;
    if (def.broken) dmg *= 1.5;
    const crit = att.bonus === 'crit';
    if (crit) dmg *= 1.5;
    dmg = Math.max(1, Math.round(dmg));
    def.hp = Math.max(0, def.hp - dmg);
    if (def.side === 'party') this.feats.dmgTaken += dmg;
    else if (aff > 1) {
      this.feats.weak++;
      // press-turn flavour: exploiting a weakness brings the attacker's next turn sooner (once per action)
      if (att.side === 'party' && !this.pulled) { this.pulled = true; this.actionTempo -= 0.15; }
    }
    def.flashT = 0.15;
    const p = def.centerPos();
    const col = ELEMENT_COLOR[o.element];
    this.elementFx(o.element, def);
    this.fx.sparks.burst(p, 16, { color: col, speed: 6, life: 0.35, size: 0.12, gravity: 6 });
    this.game.ui.popup(p.clone().add(new THREE.Vector3(rand(-0.3, 0.3), 0.3, 0)), `${dmg}`, `dmg ${def.side}${aff > 1 ? ' weak' : aff < 1 ? ' resist' : ''}${def.broken || crit ? ' crit' : ''}`);
    if (aff !== 1) this.discoverAffinity(def, o.element);
    if (aff > 1) this.game.ui.popup(def.topPos(), 'WEAK', 'weak-tag', 0.9);
    else if (aff < 1) this.game.ui.popup(def.topPos(), 'RESIST', 'resist-tag', 0.9);
    Sfx.play(dmg > def.maxHp * 0.2 ? 'hit_heavy' : 'hit');
    this.shake = Math.max(this.shake, def.side === 'party' ? 0.25 : 0.12);
    if (def.side === 'party') Input.rumble(0.7, 0.4, 160);
    if (def.hp <= 0) { this.ko(def); return; }
    def.anim.play('hit');
    if (def.side === 'enemy' && o.brk > 0) this.addBreak(def, o.brk * (aff > 1 ? 1.3 : 1) * (att.bonus === 'brk' ? 2 : 1));
  }

  private elementFx(el: Element, t: BUnit) {
    const p = t.centerPos();
    switch (el) {
      case 'fire': this.fx.sparks.burst(p, 22, { color: 0xff7a2a, speed: 4, up: 1.4, life: 0.6, size: 0.22 }); this.fx.flash(p, 0xff7a2a, 30, 8); Sfx.play('fire'); break;
      case 'frost': this.fx.shards(t.pos.clone(), 0x8fe8ff, 6); Sfx.play('frost'); break;
      case 'volt': this.fx.bolt(p); Sfx.play('volt'); break;
      case 'aether': this.fx.ring(p, 0xc58bff, 2, 0.35, this.camera.position.clone().sub(p)); this.fx.flash(p, 0xc58bff, 25, 6); break;
      default: this.fx.ring(p, 0xffffff, 1.2, 0.2, this.camera.position.clone().sub(p));
    }
  }

  /** First weak/resist hit on a species reveals that affinity (target panel + bestiary). */
  private discoverAffinity(def: BUnit, element: Element) {
    const b = State.current.bestiary[def.species!.id];
    if (b.known.includes(element)) return;
    b.known.push(element);
    this.bui.refreshAffinity();
  }

  private addBreak(e: BUnit, v: number) {
    if (e.broken || !e.alive) return;
    e.brk = Math.min(e.brkMax, e.brk + v);
    if (e.brk >= e.brkMax) {
      e.broken = true;
      this.feats.breaks++;
      Sfx.play('break');
      Input.rumble(0.9, 0.5, 220);
      void this.bui.cutIn({ title: 'Break', sub: e.name });
      if (!State.current.tipsSeen.has('break')) this.pendingTip = 'break';
      this.fx.ring(e.pos.clone().add(new THREE.Vector3(0, 0.1, 0)), 0xffe066, 3.5, 0.5);
      this.fx.sparks.burst(e.centerPos(), 40, { color: 0xffe066, speed: 9, life: 0.6, size: 0.15, gravity: 5 });
      this.shake = 0.4;
      this.updateOrder();
    }
  }

  private heal(t: BUnit, amt: number) {
    const before = t.hp;
    t.hp = Math.min(t.maxHp, t.hp + amt);
    this.fx.pillar(t.pos.clone(), 0x9dffb0, 3, 0.7, 0.9);
    this.game.ui.popup(t.centerPos(), `+${Math.round(t.hp - before)}`, 'heal');
  }

  private async ko(u: BUnit) {
    u.anim.stunned = false;
    u.anim.play('ko');
    Sfx.play('ko');
    this.game.ui.popup(u.topPos(), u.side === 'enemy' ? '격파' : '전투불능', 'info');
    if (u.side === 'enemy') {
      this.fx.sparks.burst(u.centerPos(), 30, { color: 0xffd9a8, speed: 5, life: 0.8, size: 0.14, up: 0.6 });
      const s0 = u.obj.scale.x;
      this.tl.wait(0.8).then(() => this.tl.tween(0.5, (k) => u.obj.scale.setScalar(s0 * (1 - k)))).then(() => (u.obj.visible = false));
    }
    this.bui.refresh();
    this.updateOrder();
  }

  // =====================================================================
  // Movement helpers
  // =====================================================================
  private async moveUnit(u: BUnit, to: THREE.Vector3, dur: number, faceTo?: THREE.Vector3) {
    const from = u.pos.clone();
    const dest = to.clone().setY(0);
    const look = faceTo ?? dest;
    const yaw = Math.atan2(look.x - from.x, look.z - from.z);
    u.obj.rotation.y = yaw;
    u.anim.speed = Math.min(9, from.distanceTo(dest) / dur);
    await this.tl.tween(dur, (k) => u.pos.lerpVectors(from, dest, k), easeOutCubic);
    if (faceTo) u.obj.rotation.y = Math.atan2(faceTo.x - u.pos.x, faceTo.z - u.pos.z);
    u.anim.speed = 0;
  }

  /** Party jump over a shockwave (no clip for it: a quick arc on the root). */
  private async hop(u: BUnit, h = 1.1) {
    const y0 = u.home.y;
    await this.tl.tween(0.42, (k) => { u.pos.y = y0 + Math.sin(k * Math.PI) * h; });
    u.pos.y = y0;
  }

  private async returnHome(u: BUnit) {
    if (u.ko) { u.pos.copy(u.home); u.obj.rotation.y = u.homeYaw; return; }
    await this.moveUnit(u, u.home, 0.42);
    this.faceHome(u);
  }

  private faceHome(u: BUnit) {
    u.obj.rotation.y = u.homeYaw;
  }

  // =====================================================================
  // Camera
  // =====================================================================
  private setCam(pos: THREE.Vector3, look: THREE.Vector3, lambda = 4, snap = false) {
    this.wantPos.copy(pos);
    this.wantLook.copy(look);
    this.camLambda = lambda;
    if (snap) { this.camPos.copy(pos); this.camLook.copy(look); }
  }
  private enemyCenter() {
    const es = this.enemies.filter((e) => e.alive);
    const c = new THREE.Vector3();
    for (const e of es) c.add(e.pos);
    return es.length ? c.divideScalar(es.length) : new THREE.Vector3(0, 0, ENEMY_Z);
  }
  private camCommand(u: BUnit) {
    const ec = this.enemyCenter();
    // over the outer shoulder so other party members don't block the view
    const side = u.home.x < -0.5 ? -1 : 1;
    this.setCam(u.home.clone().add(new THREE.Vector3(side * 1.5, 2.4, 4.0)), ec.clone().add(new THREE.Vector3(-side * 0.6, 1.0, 0)), 4);
  }
  private camTarget(u: BUnit, t: BUnit) {
    const dir = t.pos.clone().sub(u.home).setY(0).normalize();
    this.setCam(u.home.clone().addScaledVector(dir, -2.6).add(new THREE.Vector3(1.4, 2.1, 0)), t.centerPos(), 5);
  }
  private camOverview() {
    this.setCam(new THREE.Vector3(0, 7.5, 15), new THREE.Vector3(0, 1, -2), 4);
  }
  private camParty() {
    this.setCam(new THREE.Vector3(2, 4.5, PARTY_Z - 7.5), new THREE.Vector3(0, 1, PARTY_Z), 4);
  }
  private camAction(a: BUnit, b: BUnit) {
    const mid = a.pos.clone().lerp(b.pos, 0.5);
    const side = a.side === 'party' ? 1 : -1;
    this.setCam(mid.clone().add(new THREE.Vector3(8.5 * side, 3.2, 1.5)), mid.add(new THREE.Vector3(0, 1.1, 0)), 3.5);
  }
  private camDefend(t: BUnit | null, e: BUnit) {
    const tp = t ? t.home.clone() : new THREE.Vector3(0, 0, PARTY_Z);
    const dir = e.pos.clone().sub(tp).setY(0).normalize();
    const side = new THREE.Vector3(-dir.z, 0, dir.x);
    this.setCam(tp.clone().addScaledVector(dir, -4.6).addScaledVector(side, -2.2).add(new THREE.Vector3(0, 2.6, 0)), tp.clone().lerp(e.pos, 0.5).add(new THREE.Vector3(0, 1.2, 0)), 3.5);
  }

  // =====================================================================
  // Finish
  // =====================================================================
  private async finish(result: BattleResult): Promise<BattleResult> {
    const st = State.current;
    this.bui.hideCommand();
    if (result === 'victory') {
      Sfx.play('victory');
      for (const p of this.party) if (!p.ko) { p.anim.stance = 'idle'; p.anim.play('victory'); this.faceHome(p); p.pos.copy(p.home); p.obj.rotation.y = 0; }
      this.setCam(new THREE.Vector3(2.5, 2.4, PARTY_Z - 6), new THREE.Vector3(0, 1.2, PARTY_Z), 2.5);
      await this.tl.wait(1.0);
      // rewards (× tactical bonus)
      const defeated = this.enemies.filter((e) => e.ko && !e.removed);
      const bonuses = this.tacticalBonuses();
      const mult = 1 + bonuses.reduce((s, b) => s + b.pct, 0) / 100;
      const xp = Math.round(defeated.reduce((s, e) => s + e.species!.xp, 0) * mult);
      const money = Math.round(defeated.reduce((s, e) => s + e.species!.money, 0) * mult);
      st.money += money;
      const drops: string[] = [];
      for (const e of defeated) for (const d of e.species!.drops) if (chance(d.chance)) { st.addItem(d.item); drops.push(`${icon('item', d.item, ITEMS[d.item].icon)} ${ITEMS[d.item].name}`); }
      this.syncHp();
      // active members first, then the reserve (half EXP)
      const rows: VictoryRow[] = [];
      const order = [...st.roster].sort((a, b) => Number(!st.active.includes(a.id)) - Number(!st.active.includes(b.id)));
      for (const m of order) {
        const isActive = st.active.includes(m.id);
        const gain = Math.round(xp * (isActive ? 1 : 0.5));
        if (!gain) continue;
        const fromLv = m.level, fromXp = m.xp;
        const up = st.giveXp(m, gain);
        rows.push({ pid: m.id, name: m.name, color: m.color, gain, reserve: !isActive, fromLv, fromXp, toLv: m.level, toXp: m.xp, newSkills: up ? up.newSkills.map((s) => SKILLS[s].name) : [] });
      }
      await this.bui.victoryScreen({ xp, money, drops, recruited: this.recruited.map((id) => SPECIES[id].name), rows, bonuses });
    } else if (result === 'fled') {
      this.syncHp();
      this.game.ui.toast('무사히 도망쳤다');
    } else if (result === 'defeat') {
      Sfx.play('defeat');
      this.setCam(new THREE.Vector3(0, 10, PARTY_Z + 6), new THREE.Vector3(0, 0, PARTY_Z), 1.5);
      await this.tl.wait(1.2);
      const choice = await this.bui.defeatScreen<string>([
        { label: '다시 도전', desc: '이 전투를 처음부터 다시 시작합니다.', value: 'retry' },
        { label: '에테르 샘에서 재시작', desc: 'HP를 회복하고 휴식 지점으로 돌아갑니다.', value: 'rest' },
      ]);
      if (choice === 'retry') result = 'retry';
    }
    this.end();
    return result;
  }

  /**
   * Tactical bonus (궤적-style): feats this battle add to the EXP / 기어 multiplier, capped at +100%.
   * Only counts when something was actually defeated (a pure recruit/flee run earns nothing extra).
   */
  private tacticalBonuses() {
    const f = this.feats;
    const out: { label: string; pct: number }[] = [];
    const add = (ok: boolean, label: string, pct: number) => { if (ok) out.push({ label, pct }); };
    add(this.req.advantage === 'party', '선제 공격', 10);
    add(f.parries >= 3, `패링 ${f.parries}회`, Math.min(30, f.parries * 5));
    add(f.counters > 0, `반격 ${f.counters}회`, Math.min(20, f.counters * 10));
    add(f.weak >= 2, '약점 공략', 10);
    add(f.breaks > 0, f.breaks > 1 ? `브레이크 ${f.breaks}회` : '브레이크', Math.min(20, f.breaks * 10));
    add(f.dmgTaken === 0, '무피해', 20);
    add(f.partyTurns <= 3, '속전속결', 10);
    add(this.party.some((p) => !p.ko && p.hp <= p.maxHp * 0.3), '위기 극복', 10);
    let total = 0;
    return out.filter((b) => { if (total >= 100) return false; b.pct = Math.min(b.pct, 100 - total); total += b.pct; return true; });
  }

  private cycleSpeed() {
    const st = State.current;
    st.battleSpeed = BATTLE_SPEEDS[(BATTLE_SPEEDS.indexOf(st.battleSpeed) + 1) % BATTLE_SPEEDS.length];
    this.bui.setSpeed(st.battleSpeed);
    Sfx.play('ui_move');
  }

  private syncHp() {
    for (const p of this.party) p.member!.hp = Math.max(1, p.hp);
  }

  private end() {
    this.active = false;
    for (const s of this.sessions) s.dispose();
    this.sessions = [];
    this.tl.clear();
    this.bui.show(false);
    this.game.ui.clearPopups();
  }

  // =====================================================================
  update(rawDt: number) {
    if (!this.active) return;
    // battle speed (settings / Tab · View): choreography only — parry, dodge and QTE windows always run at ×1
    if (Input.pressed('Tab', 'PadBack')) this.cycleSpeed();
    const dt = this.sessions.length ? rawDt : rawDt * State.current.battleSpeed;
    this.time += dt;
    this.tl.update(dt);
    for (const s of this.sessions) s.update(this.tl.time);
    for (const u of this.units) {
      if (!u.obj.visible) continue;
      u.update(dt);
      if (u.alive) u.steam?.update(dt, this.fx.smoke, !!u.anim.action);
    }
    this.fx.update(dt);
    // camera
    const k = 1 - Math.exp(-this.camLambda * dt);
    this.camPos.lerp(this.wantPos, k);
    this.camLook.lerp(this.wantLook, k);
    this.camera.position.copy(this.camPos);
    if (this.shake > 0) {
      this.shake = Math.max(0, this.shake - dt * 2.2);
      const s = this.shake * 0.25;
      this.camera.position.add(new THREE.Vector3(rand(-s, s), rand(-s, s), rand(-s, s)));
    }
    this.camera.lookAt(this.camLook);
    this.bui.update(dt, this.tl.time);
    animateBackdrop(this.backdrop, this.time);
    animateMotes(this.motes, this.time, dt, new THREE.Vector3(), 40, -1);
  }
}

const st0 = () => State.current;

/** Turn-order slot bonuses (궤적 AT bonus): heal / AP (+2, enemies: 방어↑) / crit ×1.5 / break ×2 (enemies: 공격↑). */
type SlotBonus = 'heal' | 'ap' | 'crit' | 'brk';
const SLOT_BONUSES: SlotBonus[] = ['heal', 'ap', 'crit', 'brk'];

function statusLabel(id: string) {
  const m: Record<string, string> = { atkUp: '공격↑', defUp: '방어↑', haste: '가속', guard: '도발', burn: '화상', atkDown: '공격↓', enraged: '격노' };
  return m[id] ?? id;
}

