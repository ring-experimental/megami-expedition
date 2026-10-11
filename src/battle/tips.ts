import type { InputState } from '../core/input';
import { pb } from '../ui/glyph';

/**
 * Contextual battle tips (UI bible §9-5): each concept is explained once, the first time it comes
 * up, as one or two lines with the actual buttons for the current input device.
 */
export type TipId = 'ap' | 'qte' | 'parry' | 'break' | 'talk' | 'jump' | 'heat' | 'circuit' | 'bonus' | 'holdup';

export interface Tip { title: string; body: (s: InputState) => string }

const k = (s: InputState, pad: string, keys: string) => (s.device === 'pad' ? pad : keys);

export const TIPS: Record<TipId, Tip> = {
  ap: {
    title: 'AP',
    body: () => '턴마다 <b>AP +1</b>. 기본 공격은 AP를 모으고(+1), 스킬은 AP를 쓴다.',
  },
  qte: {
    title: 'QTE',
    body: (s) => `기술 도중 원이 맞물리는 순간 ${k(s, `${pb('a')} ${pb('b')} ${pb('rb')}`, '<kbd>F</kbd> <kbd>Space</kbd> <kbd>좌클릭</kbd>')} — 정확할수록 위력이 오른다.`,
  },
  parry: {
    title: 'Parry',
    body: (s) => `명중 순간 ${k(s, `${pb('a')} ${pb('rb')}`, '<kbd>F</kbd> <kbd>좌클릭</kbd>')} <b>패링</b> — 판정은 좁지만 AP +1, 전부 막으면 반격.<br>`
      + `${k(s, pb('b'), '<kbd>Space</kbd> <kbd>우클릭</kbd>')} <b>회피</b> — 판정이 넓다. 연타하면 잠시 입력이 막힌다.`,
  },
  break: {
    title: 'Break',
    body: () => '노란 게이지가 가득 찬 적은 <b>1턴 기절</b>하고 받는 피해가 <b>1.5배</b>.',
  },
  jump: {
    title: 'Jump',
    body: (s) => `<b>JUMP</b> 표시가 붙은 공격은 땅을 타고 오는 충격파 — 패링·회피로는 못 막는다. 명중 순간 ${k(s, pb('y'), '<kbd>W</kbd>')} <b>점프</b>. 전부 넘으면 반격.`,
  },
  heat: {
    title: '열압',
    body: () => '카이의 기술은 보일러에 <b>열압</b>을 쌓는다. 100%가 되면 <b>과열</b>(공격 ×1.35, 매 턴 HP 소모). 패링하면 열이 빠지고, <b>방열 일섬</b>은 쌓인 열을 한 번에 쏟아낸다.',
  },
  circuit: {
    title: '회로 각인',
    body: () => '리라가 속성 마법을 쓰면 그 속성의 <b>각인</b>이 남는다(최대 2개). 서로 다른 각인 2개로 <b>회로 결합</b> — 조합마다 다른 상위 마법이 나온다.',
  },
  bonus: {
    title: 'Turn Bonus',
    body: () => '턴 순서의 일부 칸에는 <b>보너스</b>가 붙어 있다(HP 회복 · AP · 크리티컬 · 브레이크). 그 칸에 차례가 온 쪽이 받는다 — 적도 받는다. 무거운 기술은 다음 턴이 늦어지고, <b>지연</b> 기술은 적의 턴을 민다. 고르는 동안 바뀌는 순서가 미리 보인다.',
  },
  holdup: {
    title: 'Hold Up',
    body: () => '살아 있는 적이 <b>전원 브레이크</b>되면 포위한다. <b>총공격</b>으로 몰아치거나, 도망칠 곳 없는 적과 <b>포위 협상</b>을 하거나, <b>갈취</b>하고 놓아줄 수 있다.',
  },
  talk: {
    title: 'Talk',
    body: () => '성격에 맞는 대답을 고르면 분위기가 오른다. 이 적에게 <b>성공한 패링 횟수</b>만큼 영입 확률도 오른다.',
  },
};
