import { State } from '../game/state';

/**
 * 공방 (피페의 합주): two recruited monsters → one. A listed pair fuses into another species (both
 * consumed); any other pair is an inheritance — the base keeps its body and learns one of the
 * material's skills. Both must agree: 친밀도 1+ each (extortion and neglect lower it).
 */
export interface FusionRecipe { a: string; b: string; result: string; line: string; when?: () => boolean; whenText?: string }

export const FUSIONS: FusionRecipe[] = [
  { a: 'slime', b: 'wisp', result: 'bellows_toad', line: '끓는 물에 불꽃을 얹으면, 숨을 쉬지.' },
  { a: 'prism_moth', b: 'slime', result: 'wisp', line: '빛을 물에 녹이면 등불이 된단다.' },
  { a: 'wisp', b: 'beetle', result: 'prism_moth', line: '불꽃에 껍질을 입히면 유리가 되지.' },
  { a: 'beetle', b: 'bellows_toad', result: 'strongbox_tortoise', line: '고집에 허기를 더하면… 지키는 마음이 되더구나.',
    when: () => State.current.bestiary.strongbox_tortoise?.seen, whenText: '금고 거북을 만나 본 뒤' },
  { a: 'bellows_toad', b: 'strongbox_tortoise', result: 'golem', line: '큰 곡조야. 할미 파이프가 다 울리겠네.',
    when: () => { const st = State.current; return st.has('bellows_toad') && st.has('strongbox_tortoise') && (st.member('bellows_toad').level + st.member('strongbox_tortoise').level) / 2 >= 8; },
    whenText: '두 동료의 평균 레벨 8 이상' },
];

export function fusionRecipe(a: string, b: string) {
  return FUSIONS.find((f) => (f.a === a && f.b === b) || (f.a === b && f.b === a)) ?? null;
}

/** Inherited skills a monster can hold on top of its own. */
export const MAX_INHERITED = 2;
