export interface ItemDef {
  id: string;
  name: string;
  desc: string;
  target: 'ally' | 'allyKO' | 'allAllies';
  heal?: number;
  healRatio?: number;
  ap?: number;
  revive?: number;
  icon: string;
}

export const ITEMS: Record<string, ItemDef> = {
  tonic: { id: 'tonic', name: '에테르 토닉', desc: 'HP 80 회복', target: 'ally', heal: 80, icon: '🧪' },
  hi_tonic: { id: 'hi_tonic', name: '하이 토닉', desc: 'HP 200 회복', target: 'ally', heal: 200, icon: '⚗️' },
  capsule: { id: 'capsule', name: '증기 캡슐', desc: 'AP +3', target: 'ally', ap: 3, icon: '💨' },
  heart: { id: 'heart', name: '태엽 심장', desc: '전투불능 회복 (HP 50%)', target: 'allyKO', revive: 0.5, icon: '⚙️' },
};
