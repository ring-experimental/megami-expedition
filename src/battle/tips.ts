import type { InputState } from '../core/input';
import { pb } from '../ui/glyph';

/**
 * Contextual battle tips (UI bible §9-5): each concept is explained once, the first time it comes
 * up, as one or two lines with the actual buttons for the current input device.
 */
export type TipId = 'ap' | 'qte' | 'parry' | 'break' | 'talk';

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
  talk: {
    title: 'Talk',
    body: () => '성격에 맞는 대답을 고르면 분위기가 오른다. 이 적에게 <b>성공한 패링 횟수</b>만큼 영입 확률도 오른다.',
  },
};
