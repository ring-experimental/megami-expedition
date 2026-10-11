import * as THREE from 'three';
import { Animator } from '../anim/rig';
import { SteamVent } from '../fx/effects';
import { getModel } from '../core/assets';
import type { Member } from '../game/state';
import { State } from '../game/state';
import { HEROES, SPECIES, type HeroDef, type SpeciesDef } from '../data/units';
import type { Element, Stats, StatusId } from '../data/types';

let uidSeq = 0;

export class BUnit {
  uid = 'u' + uidSeq++;
  side: 'party' | 'enemy';
  name: string;
  level: number;
  stats: Stats;
  hp: number;
  maxHp: number;
  ap = 1;
  brk = 0;
  brkMax = 0;
  broken = false;
  statuses: { id: StatusId; turns: number }[] = [];
  member?: Member;
  species?: SpeciesDef;
  hero?: HeroDef;
  obj = new THREE.Group();
  model: THREE.Object3D;
  anim: Animator;
  home = new THREE.Vector3();
  homeYaw = 0;
  ct = 0;
  /** Parries landed against this enemy (raises recruit chance). */
  rapport = 0;
  /** Negotiation mood (persists through the battle). */
  mood = 0;
  asked = new Set<number>();
  talks = 0;
  removed = false;
  skills: string[] = [];
  color: string;
  flashT = 0;
  ui: Record<string, HTMLElement> = {};
  /** Kai's 열압 (0–100): skills build it, parries vent it, 100 → 과열. */
  heat = 0;
  /** Lyra's 회로 각인: elements of her last offensive spells (max 2, oldest first). */
  sigils: Element[] = [];
  /** Turn-order bonus picked up this turn (applies to the action taken in it). */
  bonus: 'crit' | 'brk' | null = null;
  /** Steam from a `steam_point` node (Kai's backpack, the golem's chimney); emitted by Battle. */
  steam: SteamVent | null = null;

  constructor(side: 'party' | 'enemy', src: { member?: Member; species?: SpeciesDef; hpRatio?: number }) {
    this.side = side;
    if (src.member) {
      const m = src.member;
      this.member = m;
      this.name = m.name;
      this.level = m.level;
      this.stats = State.current.stats(m);
      this.maxHp = this.stats.hp;
      this.hp = Math.max(1, Math.min(m.hp, this.maxHp));
      this.skills = State.current.skillsOf(m);
      this.color = m.color;
      if (m.kind === 'hero') this.hero = HEROES[m.id as 'kai' | 'lyra'];
      else this.species = SPECIES[m.id];
    } else {
      const sp = src.species!;
      this.species = sp;
      this.name = sp.name;
      this.level = sp.level;
      this.stats = { ...sp.stats };
      this.maxHp = sp.stats.hp;
      this.hp = Math.max(1, Math.round(this.maxHp * (src.hpRatio ?? 1)));
      this.brkMax = sp.breakMax;
      this.color = sp.color;
    }
    const modelName = this.hero ? this.hero.model : this.species!.model;
    this.model = getModel(modelName);
    if (this.species) this.model.scale.setScalar(this.species.scale * this.species.battleScale);
    this.obj.add(this.model);
    const arche = this.hero ? 'humanoid' : this.species!.archetype;
    this.anim = new Animator(this.model, arche);
    const sp = this.anim.rig.get('steam_point');
    if (sp) this.steam = new SteamVent(sp, this.hero ? 'pack' : 'chimney', this.scl);
  }

  get ko() { return this.hp <= 0; }
  /** Portrait / asset id. */
  get pid() { return this.hero ? this.hero.id : this.species!.id; }
  get alive() { return !this.ko && !this.removed; }
  get scl() { return this.species ? this.species.scale * this.species.battleScale : 1; }
  get height() { return this.hero ? (this.hero.id === 'kai' ? 1.8 : 1.65) : this.species!.height * this.scl; }
  get radius() { return this.hero ? 0.5 : this.species!.radius * this.scl; }
  get isMonster() { return !this.hero; }
  get pos() { return this.obj.position; }

  topPos() {
    return this.obj.position.clone().add(new THREE.Vector3(0, this.height + 0.35, 0));
  }
  centerPos() {
    const h = this.species?.hover ? this.species.hover * this.scl : this.height * 0.55;
    return this.obj.position.clone().add(new THREE.Vector3(0, h, 0));
  }

  has(id: StatusId) {
    return this.statuses.some((s) => s.id === id);
  }
  addStatus(id: StatusId, turns: number) {
    const s = this.statuses.find((x) => x.id === id);
    if (s) s.turns = Math.max(s.turns, turns);
    else this.statuses.push({ id, turns });
  }
  speed() {
    return this.stats.spd * (this.has('haste') ? 1.5 : 1);
  }
  atkMult() {
    return (this.has('atkUp') ? 1.3 : 1) * (this.has('atkDown') ? 0.75 : 1) * (this.has('enraged') ? 1.3 : 1) * (this.has('overheat') ? 1.35 : 1);
  }
  defMult() {
    return (this.has('defUp') ? 0.7 : 1) * (this.has('guard') ? 0.8 : 1);
  }

  setHome(p: THREE.Vector3, yaw: number) {
    this.home.copy(p);
    this.homeYaw = yaw;
    this.obj.position.copy(p);
    this.obj.rotation.y = yaw;
  }

  update(dt: number) {
    this.anim.update(dt);
    if (this.flashT > 0) {
      this.flashT -= dt;
      const k = Math.max(0, this.flashT / 0.15);
      this.model.traverse((o) => {
        const m = (o as THREE.Mesh).material as THREE.MeshStandardMaterial | undefined;
        if (m && 'emissive' in m && !m.name.startsWith('glow_')) m.emissive.setRGB(k, k, k);
      });
    }
  }
}
