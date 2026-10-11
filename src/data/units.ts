import type { Archetype } from '../anim/rig';
import type { ModelName } from '../core/assets';
import type { Element, Stats, StatusId } from './types';

export interface HeroDef {
  id: 'kai' | 'lyra';
  name: string;
  title: string;
  model: ModelName;
  color: string;
  base: Stats;
  growth: Stats;
  skills: { id: string; level: number }[];
  basicElement: Element;
  /** Basic attack is melee (dash in) or ranged (shoot). */
  basicMelee: boolean;
}

export const HEROES: Record<'kai' | 'lyra', HeroDef> = {
  kai: {
    id: 'kai', name: '카이', title: '증기검사', model: 'kai', color: '#e2a64a',
    base: { hp: 120, atk: 18, mag: 8, def: 10, res: 8, spd: 11 },
    growth: { hp: 14, atk: 3, mag: 1, def: 2, res: 1.5, spd: 0.6 },
    skills: [{ id: 'steam_slash', level: 1 }, { id: 'piston_thrust', level: 1 }, { id: 'vent_slash', level: 1 }, { id: 'overheat_storm', level: 5 }],
    basicElement: 'phys', basicMelee: true,
  },
  lyra: {
    id: 'lyra', name: '리라', title: '에테르 마도사', model: 'lyra', color: '#b77bff',
    base: { hp: 90, atk: 9, mag: 20, def: 7, res: 13, spd: 13 },
    growth: { hp: 10, atk: 1, mag: 3.2, def: 1.2, res: 2.2, spd: 0.7 },
    skills: [{ id: 'aether_bolt', level: 1 }, { id: 'resonance_heal', level: 1 }, { id: 'frost_gear', level: 1 }, { id: 'volt_circuit', level: 4 }, { id: 'circuit_fuse', level: 4 }],
    basicElement: 'aether', basicMelee: false,
  },
};

export type PersonalityId = 'timid' | 'childish' | 'proud' | 'curious' | 'honorable' | 'greedy' | 'lonely';
export type Tier = 'weak' | 'strong' | 'elite';

export interface EnemyMove {
  id: string;
  name: string;
  kind: 'melee' | 'ranged' | 'self';
  element: Element;
  /** 'atk' or 'mag' based. */
  stat: 'atk' | 'mag';
  power: number;
  /** Hit times (seconds) after the wind-up ends. */
  hits: number[];
  /** Wind-up duration range [min,max] (randomized → reading the tell matters). */
  windup: [number, number];
  allTargets?: boolean;
  weight: number;
  /** Ground shockwave: only a jump avoids it (parry / dodge don't). */
  jump?: boolean;
  /** Boss phase this move belongs to (1: HP > 60%, 2: below); unset = any phase. */
  phase?: 1 | 2;
  /** Self move usable once per battle, only below this HP ratio. */
  onceBelow?: number;
  status?: { id: StatusId; turns: number; chance: number; self?: boolean };
  /** self-heal ratio for 'self' moves */
  heal?: number;
}

export interface SpeciesDef {
  id: string;
  name: string;
  desc: string;
  model: ModelName;
  archetype: Archetype;
  scale: number;
  tier: Tier;
  level: number;
  stats: Stats;
  /** Element multipliers (>1 weak, <1 resist). */
  affinity: Partial<Record<Element, number>>;
  breakMax: number;
  personality: PersonalityId;
  field: { speed: number; detect: number; attack: 'lunge' | 'projectile'; windup: number; breakMax: number; poise: number };
  moves: EnemyMove[];
  allySkills: string[];
  /** Third skill the recruited ally learns at this level. */
  lateSkill?: { id: string; level: number };
  xp: number;
  money: number;
  drops: { item: string; chance: number }[];
  /** Extra scale applied in turn-based battle so small creatures read well. */
  battleScale: number;
  /** Approx. visual height for UI bars (m, before scale). */
  height: number;
  radius: number;
  hover?: number;
  /** Negotiation gate. */
  talkGate?: 'brokenOrHalf';
  /** Species' own negotiation lines (override the personality's). */
  talk?: Partial<Record<'greet' | 'greetBroken' | 'like' | 'neutral' | 'dislike' | 'angry' | 'join' | 'refuse', string[]>>;
  color: string;
}

export const SPECIES: Record<string, SpeciesDef> = {
  cograt: {
    id: 'cograt', name: '톱니쥐', desc: '태엽으로 움직이는 구리 쥐. 겁이 많지만 무리를 지으면 대담해진다.',
    battleScale: 1.9, model: 'cograt', archetype: 'rat', scale: 1, tier: 'weak', level: 2,
    stats: { hp: 62, atk: 12, mag: 4, def: 6, res: 5, spd: 14 },
    affinity: { volt: 1.5, frost: 1.25 }, breakMax: 50, personality: 'timid',
    field: { speed: 4.2, detect: 11, attack: 'lunge', windup: 0.55, breakMax: 40, poise: 0 },
    moves: [
      { id: 'bite', name: '물어뜯기', kind: 'melee', element: 'phys', stat: 'atk', power: 1.0, hits: [0], windup: [0.5, 0.9], weight: 3 },
      { id: 'gnaw', name: '톱니 연속 물기', kind: 'melee', element: 'phys', stat: 'atk', power: 0.5, hits: [0, 0.26, 0.48], windup: [0.6, 1.0], weight: 2 },
    ],
    allySkills: ['gear_bite', 'wind_up'], lateSkill: { id: 'scrap_swarm', level: 5 }, xp: 14, money: 12, drops: [{ item: 'tonic', chance: 0.25 }],
    height: 0.6, radius: 0.5, color: '#b8673a',
  },
  slime: {
    id: 'slime', name: '보일러 젤리', desc: '보일러 폐수에 에테르가 깃들어 생긴 젤리. 장난을 좋아한다.',
    battleScale: 1.6, model: 'slime', archetype: 'slime', scale: 1, tier: 'weak', level: 3,
    stats: { hp: 85, atk: 10, mag: 13, def: 5, res: 12, spd: 9 },
    affinity: { frost: 1.5, fire: 0.5 }, breakMax: 60, personality: 'childish',
    field: { speed: 3.2, detect: 9, attack: 'lunge', windup: 0.7, breakMax: 45, poise: 0 },
    moves: [
      { id: 'body_slam', name: '몸통 박치기', kind: 'melee', element: 'phys', stat: 'atk', power: 1.15, hits: [0], windup: [0.7, 1.3], weight: 3 },
      { id: 'bounce', name: '통통 3연타', kind: 'melee', element: 'phys', stat: 'atk', power: 0.45, hits: [0, 0.42, 0.62], windup: [0.6, 0.9], weight: 2 },
      { id: 'steam_spout', name: '증기 분사', kind: 'ranged', element: 'fire', stat: 'mag', power: 0.65, hits: [0, 0.35], windup: [0.8, 1.1], weight: 2, status: { id: 'burn', turns: 2, chance: 0.3 } },
    ],
    allySkills: ['steam_heal', 'jelly_guard'], lateSkill: { id: 'pressure_wash', level: 6 }, xp: 18, money: 15, drops: [{ item: 'tonic', chance: 0.35 }],
    height: 0.85, radius: 0.55, color: '#3fd1b8',
  },
  wisp: {
    id: 'wisp', name: '램프 위스프', desc: '버려진 가스등에 깃든 정령. 무엇이든 알고 싶어 한다.',
    battleScale: 1.25, model: 'wisp', archetype: 'wisp', scale: 1, tier: 'weak', level: 4,
    stats: { hp: 72, atk: 6, mag: 18, def: 6, res: 16, spd: 15 },
    affinity: { frost: 1.5, phys: 1.2, fire: 0.25 }, breakMax: 50, personality: 'curious',
    field: { speed: 3.6, detect: 13, attack: 'projectile', windup: 0.8, breakMax: 40, poise: 0 },
    moves: [
      { id: 'fireball', name: '등불탄', kind: 'ranged', element: 'fire', stat: 'mag', power: 1.2, hits: [0], windup: [0.6, 1.2], weight: 3, status: { id: 'burn', turns: 2, chance: 0.25 } },
      { id: 'flicker', name: '명멸', kind: 'ranged', element: 'aether', stat: 'mag', power: 0.5, hits: [0, 0.14, 0.62], windup: [0.7, 1.0], weight: 2 },
      { id: 'ember_rain', name: '불티 비', kind: 'ranged', element: 'fire', stat: 'mag', power: 0.55, hits: [0, 0.4], windup: [1.0, 1.3], allTargets: true, weight: 1 },
    ],
    allySkills: ['lamp_flame', 'will_o_wisp'], lateSkill: { id: 'gaslight', level: 7 }, xp: 22, money: 18, drops: [{ item: 'capsule', chance: 0.25 }],
    height: 1.9, radius: 0.5, hover: 1.3, color: '#ffb347',
  },
  beetle: {
    id: 'beetle', name: '놋쇠 딱정벌레', desc: '광택 나는 놋쇠 갑각을 자랑하는 벌레. 자존심이 세다.',
    battleScale: 1.4, model: 'beetle', archetype: 'beetle', scale: 1, tier: 'strong', level: 5,
    stats: { hp: 215, atk: 17, mag: 5, def: 16, res: 6, spd: 8 },
    affinity: { volt: 1.5, phys: 0.8 }, breakMax: 90, personality: 'proud',
    field: { speed: 3.4, detect: 10, attack: 'lunge', windup: 0.85, breakMax: 70, poise: 1 },
    moves: [
      { id: 'horn_charge', name: '뿔 돌진', kind: 'melee', element: 'phys', stat: 'atk', power: 1.45, hits: [0], windup: [0.9, 1.6], weight: 3 },
      { id: 'shell_spin', name: '외피 회전', kind: 'melee', element: 'phys', stat: 'atk', power: 0.4, hits: [0, 0.2, 0.4, 0.6], windup: [0.7, 1.0], weight: 2 },
      { id: 'harden', name: '경화', kind: 'self', element: 'phys', stat: 'atk', power: 0, hits: [], windup: [0.4, 0.4], weight: 1, status: { id: 'defUp', turns: 3, chance: 1, self: true } },
    ],
    allySkills: ['horn_rush', 'iron_shell'], lateSkill: { id: 'shell_quake', level: 8 }, xp: 40, money: 30, drops: [{ item: 'hi_tonic', chance: 0.3 }],
    height: 0.9, radius: 0.8, color: '#c9a14a',
  },
  knight: {
    id: 'knight', name: '태엽 기사', desc: '멈춘 시계탑을 지키던 자동인형 기사. 명예를 중시한다.',
    battleScale: 1.1, model: 'knight', archetype: 'humanoid', scale: 1, tier: 'strong', level: 7,
    stats: { hp: 440, atk: 24, mag: 8, def: 20, res: 12, spd: 10 },
    affinity: { volt: 1.5, phys: 0.85 }, breakMax: 140, personality: 'honorable',
    field: { speed: 3.8, detect: 12, attack: 'lunge', windup: 0.75, breakMax: 100, poise: 2 },
    moves: [
      { id: 'halberd_drop', name: '할버드 내려찍기', kind: 'melee', element: 'phys', stat: 'atk', power: 1.5, hits: [0], windup: [1.0, 1.8], weight: 3 },
      { id: 'triple_thrust', name: '삼단 찌르기', kind: 'melee', element: 'phys', stat: 'atk', power: 0.6, hits: [0, 0.3, 0.66], windup: [0.6, 0.9], weight: 3 },
      { id: 'whirlwind', name: '발목 베기', kind: 'melee', element: 'phys', stat: 'atk', power: 0.7, hits: [0, 0.5], windup: [0.9, 1.2], allTargets: true, weight: 2, jump: true },
      { id: 'rewind', name: '태엽 되감기', kind: 'self', element: 'phys', stat: 'atk', power: 0, hits: [], windup: [0.5, 0.5], weight: 1, heal: 0.2 },
    ],
    allySkills: ['whirl_slash', 'knights_oath'], lateSkill: { id: 'oath_counter', level: 10 }, xp: 80, money: 60, drops: [{ item: 'heart', chance: 0.4 }, { item: 'hi_tonic', chance: 0.4 }],
    height: 2.2, radius: 0.7, color: '#8a6a2c',
  },
  golem: {
    id: 'golem', name: '증기 골렘', desc: '폐공장의 용광로가 깨어난 거인. 연료라면 뭐든 탐낸다.',
    battleScale: 1.0, model: 'golem', archetype: 'golem', scale: 1, tier: 'elite', level: 10,
    stats: { hp: 960, atk: 30, mag: 20, def: 22, res: 14, spd: 7 },
    affinity: { frost: 1.5, fire: 0.25 }, breakMax: 220, personality: 'greedy',
    field: { speed: 2.8, detect: 14, attack: 'lunge', windup: 1.1, breakMax: 160, poise: 3 },
    moves: [
      { id: 'furnace_punch', name: '용광로 펀치', kind: 'melee', element: 'fire', stat: 'atk', power: 1.7, hits: [0], windup: [1.2, 2.0], weight: 3 },
      { id: 'double_hammer', name: '양손 해머', kind: 'melee', element: 'phys', stat: 'atk', power: 0.95, hits: [0, 0.72], windup: [0.9, 1.2], weight: 3 },
      { id: 'ground_slam', name: '지면 강타', kind: 'melee', element: 'phys', stat: 'atk', power: 1.25, hits: [0], windup: [1.1, 1.6], allTargets: true, weight: 2, jump: true },
      { id: 'steam_burst', name: '증기 대폭발', kind: 'ranged', element: 'fire', stat: 'mag', power: 0.6, hits: [0, 0.25, 0.5], windup: [1.2, 1.4], allTargets: true, weight: 2, status: { id: 'burn', turns: 2, chance: 0.3 } },
      { id: 'stoke', name: '화력 증강', kind: 'self', element: 'fire', stat: 'atk', power: 0, hits: [], windup: [0.5, 0.5], weight: 1, status: { id: 'atkUp', turns: 3, chance: 1, self: true } },
    ],
    allySkills: ['furnace_punch', 'steam_burst'], lateSkill: { id: 'meltdown', level: 13 }, xp: 200, money: 150, drops: [{ item: 'heart', chance: 1 }, { item: 'capsule', chance: 1 }],
    height: 3.4, radius: 1.4, talkGate: 'brokenOrHalf', color: '#ffb347',
  },
  // --- chapter 1 (docs/story/CHAPTER1.md §5) ---------------------------------
  prism_moth: {
    id: 'prism_moth', name: '프리즘 나방', desc: '스테인드글라스 날개로 빛을 모으는 나방. 무엇이 빛을 굽히는지 늘 궁금해한다.',
    battleScale: 1.7, model: 'prism_moth', archetype: 'wisp', scale: 1, tier: 'weak', level: 5,
    stats: { hp: 76, atk: 7, mag: 19, def: 6, res: 15, spd: 16 },
    affinity: { phys: 1.5, volt: 1.25, aether: 0.5 }, breakMax: 55, personality: 'curious',
    field: { speed: 3.8, detect: 12, attack: 'projectile', windup: 0.8, breakMax: 42, poise: 0 },
    moves: [
      { id: 'refract_beam', name: '굴절 광선', kind: 'ranged', element: 'aether', stat: 'mag', power: 1.15, hits: [0], windup: [0.7, 1.2], weight: 3 },
      { id: 'crystal_dust', name: '결정 인분', kind: 'ranged', element: 'frost', stat: 'mag', power: 0.45, hits: [0, 0.36], windup: [0.9, 1.2], allTargets: true, weight: 2 },
      { id: 'flash_veil', name: '섬광', kind: 'self', element: 'aether', stat: 'mag', power: 0, hits: [], windup: [0.4, 0.4], weight: 1, status: { id: 'haste', turns: 2, chance: 1, self: true } },
    ],
    allySkills: ['prism_veil', 'spectrum_dart'], xp: 24, money: 20, drops: [{ item: 'capsule', chance: 0.15 }],
    height: 1.6, radius: 0.6, hover: 1.2, color: '#7fd6e8',
    talk: {
      greet: ['반짝… 너희, 빛을 어떻게 굽히는지 알아? 나 아직 몰라.'],
      greetBroken: ['날개에 금이… 그래도 빛이 들어오는 각도가 궁금해…'],
      like: ['오오! 그런 이유였구나. 날개가 한 칸 밝아졌어.'],
      dislike: ['그건 빛이 아니라 그림자 같은 대답이야.'],
      join: ['너희 곁에선 처음 보는 빛이 많겠지? 같이 갈래!'],
      refuse: ['아직 관찰이 덜 끝났어. 다음 빛에 다시 와.'],
    },
  },
  bellows_toad: {
    id: 'bellows_toad', name: '풀무 두꺼비', desc: '가죽 풀무 몸으로 숨을 쉬는 두꺼비. 연료라면 석탄이든 기어든 삼키려 든다.',
    battleScale: 1.5, model: 'bellows_toad', archetype: 'slime', scale: 1, tier: 'weak', level: 6,
    stats: { hp: 118, atk: 15, mag: 14, def: 9, res: 7, spd: 8 },
    affinity: { frost: 1.5, fire: 0.5 }, breakMax: 70, personality: 'greedy',
    field: { speed: 3.0, detect: 9, attack: 'lunge', windup: 0.8, breakMax: 50, poise: 0 },
    moves: [
      { id: 'puff_slam', name: '부풀어 박치기', kind: 'melee', element: 'phys', stat: 'atk', power: 1.2, hits: [0], windup: [0.9, 1.5], weight: 3 },
      { id: 'bellows_breath', name: '풀무 숨', kind: 'ranged', element: 'fire', stat: 'mag', power: 1.0, hits: [0], windup: [0.9, 1.3], weight: 2, status: { id: 'burn', turns: 2, chance: 0.3 } },
      { id: 'ash_spit', name: '재 뱉기', kind: 'ranged', element: 'fire', stat: 'mag', power: 0.45, hits: [0, 0.3], windup: [0.6, 0.9], weight: 2 },
      { id: 'belly_flop', name: '쿵 착지', kind: 'melee', element: 'phys', stat: 'atk', power: 0.8, hits: [0], windup: [1.1, 1.5], allTargets: true, jump: true, weight: 2 },
    ],
    allySkills: ['bellows_pump', 'ember_burp'], xp: 30, money: 34, drops: [{ item: 'tonic', chance: 0.3 }],
    height: 0.9, radius: 0.7, color: '#a8643a',
    talk: {
      greet: ['꾸르륵… 석탄 냄새가 나는데? 한 덩이만 주면 생각해 보지.'],
      greetBroken: ['풀무가… 바람이 샌다… 기어 하나만… 꾸르륵…'],
      like: ['꾸르… 배가 조금 따뜻해졌다.'],
      dislike: ['말로는 배가 안 불러! 꾸르륵!'],
      join: ['너희를 따라가면 연료 냄새가 안 끊기겠지. 좋아, 간다.'],
      refuse: ['부족해. 아직 한참 부족해.'],
    },
  },
  strongbox_tortoise: {
    id: 'strongbox_tortoise', name: '금고 거북', desc: '폐공장의 금고가 깨어난 거북. 백 년 전 받은 "열지 마라"는 말을 아직 지킨다.',
    battleScale: 1.0, model: 'strongbox_tortoise', archetype: 'beetle', scale: 1, tier: 'strong', level: 8,
    stats: { hp: 640, atk: 22, mag: 9, def: 26, res: 10, spd: 6 },
    affinity: { volt: 1.5, aether: 1.25, phys: 0.6 }, breakMax: 170, personality: 'timid',
    field: { speed: 2.4, detect: 10, attack: 'lunge', windup: 1.0, breakMax: 120, poise: 3 },
    moves: [
      { id: 'shell_ram', name: '금고 박치기', kind: 'melee', element: 'phys', stat: 'atk', power: 1.4, hits: [0], windup: [1.0, 1.7], weight: 3 },
      { id: 'coin_burst', name: '동전 산탄', kind: 'ranged', element: 'phys', stat: 'atk', power: 0.42, hits: [0, 0.28, 0.56, 0.84], windup: [0.8, 1.1], weight: 2 },
      { id: 'vault_drop', name: '금고 낙하', kind: 'melee', element: 'phys', stat: 'atk', power: 1.15, hits: [0], windup: [1.3, 1.8], allTargets: true, jump: true, weight: 2 },
      { id: 'lock_down', name: '자물쇠 잠금', kind: 'self', element: 'phys', stat: 'atk', power: 0, hits: [], windup: [0.5, 0.5], weight: 1, onceBelow: 0.5, status: { id: 'defUp', turns: 3, chance: 1, self: true } },
    ],
    allySkills: ['vault_wall', 'coin_volley'], xp: 120, money: 90, drops: [{ item: 'hi_tonic', chance: 0.5 }],
    height: 1.6, radius: 1.4, color: '#3b3f46',
    talk: {
      greet: ['오, 오지 마! 문 안 열려! 안 열린다고!'],
      greetBroken: ['다이얼이… 헛돌아… 열면 안 되는데…'],
      like: ['…정말? 맡아 준다고? 그런 말 처음 들어.'],
      dislike: ['히익! 억지로 열려고 하지 마!'],
      join: ['나, 처음으로 문 열어 볼래. 너희 쪽으로.'],
      refuse: ['미안… 아직은 잠가 둘래.'],
    },
  },
  grand_carillon: {
    id: 'grand_carillon', name: '그란 카리용', desc: '에테르 평원 탑의 탑심. 50년 동안 정숙만 울리도록 강요받은 종.',
    battleScale: 0.9, model: 'grand_carillon', archetype: 'golem', scale: 1, tier: 'elite', level: 11,
    stats: { hp: 1650, atk: 30, mag: 24, def: 20, res: 18, spd: 9 },
    affinity: { frost: 1.5, volt: 1.25, phys: 0.5, fire: 0.5 }, breakMax: 260, personality: 'lonely', talkGate: 'brokenOrHalf',
    field: { speed: 0, detect: 0, attack: 'lunge', windup: 1.2, breakMax: 200, poise: 3 },
    moves: [
      { id: 'hammer_peal', name: '해머 연타', kind: 'melee', element: 'phys', stat: 'atk', power: 0.42, hits: [0, 0.3, 0.6, 0.9, 1.3, 1.6], windup: [1.0, 1.4], weight: 3, phase: 1 },
      { id: 'hammer_offbeat', name: '엇박 연타', kind: 'melee', element: 'phys', stat: 'atk', power: 0.45, hits: [0, 0.3, 0.95, 1.1, 1.75, 1.9], windup: [1.0, 1.4], weight: 3, phase: 2 },
      { id: 'noon_toll', name: '정오의 타종', kind: 'melee', element: 'phys', stat: 'atk', power: 1.3, hits: [0], windup: [1.4, 2.0], allTargets: true, jump: true, weight: 2, phase: 1 },
      { id: 'noon_toll2', name: '정오의 타종', kind: 'melee', element: 'phys', stat: 'atk', power: 1.1, hits: [0, 0.9], windup: [1.4, 2.0], allTargets: true, jump: true, weight: 2, phase: 2 },
      { id: 'pendulum_sweep', name: '진자 베기', kind: 'melee', element: 'phys', stat: 'atk', power: 0.75, hits: [0, 0.7], windup: [1.0, 1.3], allTargets: true, weight: 2 },
      { id: 'hush_wave', name: '침묵 파동', kind: 'ranged', element: 'aether', stat: 'mag', power: 0.8, hits: [0], windup: [0.9, 1.2], allTargets: true, weight: 2, phase: 2, status: { id: 'atkDown', turns: 2, chance: 0.6 } },
      { id: 'rewind_spin', name: '역회전', kind: 'self', element: 'phys', stat: 'atk', power: 0, hits: [], windup: [0.5, 0.5], weight: 1, onceBelow: 0.4, heal: 0.12 },
    ],
    allySkills: ['noon_bell', 'peal_strike'], xp: 600, money: 300, drops: [{ item: 'heart', chance: 1 }, { item: 'hi_tonic', chance: 1 }],
    height: 4.2, radius: 2.0, hover: 0.6, color: '#b08d3c',
    talk: {
      greet: ['…누구냐. 아무도 올라오지 않는 곳인데.', '또 고치러 왔나. 고칠 데는 없다. 그냥… 조용할 뿐이다.'],
      greetBroken: ['…멈췄군. 이대로 멈추는 것도, 나쁘지 않다.'],
      like: ['…그 말, 오랜만에 듣는다.', '그래. 그렇게 말해 주는 자가 있었지.'],
      neutral: ['…그런가.', '말은 쉽지.'],
      dislike: ['빈말이군. 메아리처럼 텅 비었어.', '그런 말은 종소리보다 빨리 사라진다.'],
      angry: ['나가라. 혼자가 낫다!'],
      join: ['…곁에 있겠다는 말, 믿어 보마.'],
      refuse: ['아직은 혼자인 쪽이 덜 아프다.'],
    },
  },
};

/** Ally stats for a recruited monster at a given level. */
export function allyStats(sp: SpeciesDef, level: number): Stats {
  const k = 1 + 0.09 * (level - sp.level);
  const s = sp.stats;
  return {
    hp: Math.round(s.hp * 0.8 * k + 20),
    atk: Math.round(s.atk * k + 2),
    mag: Math.round(s.mag * k + 2),
    def: Math.round(s.def * k),
    res: Math.round(s.res * k),
    spd: Math.round(s.spd + (level - sp.level) * 0.4),
  };
}

export function heroStats(def: HeroDef, level: number): Stats {
  const g = (k: keyof Stats) => Math.round(def.base[k] + def.growth[k] * (level - 1));
  return { hp: g('hp'), atk: g('atk'), mag: g('mag'), def: g('def'), res: g('res'), spd: g('spd') };
}

export const xpToNext = (level: number) => Math.round(30 + level * level * 8);
