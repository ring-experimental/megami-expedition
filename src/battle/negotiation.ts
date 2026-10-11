import { Sfx } from '../core/audio';
import { clamp, pick, shuffle } from '../core/utils';
import { DEMANDS, PERSONALITIES, QUESTIONS, type Tone } from '../data/negotiation';
import { ITEMS } from '../data/items';
import { State } from '../game/state';
import { icon } from '../ui/art';
import type { BattleUI } from './battleUI';
import type { BUnit } from './bunit';

export type TalkOutcome = 'joined' | 'failed' | 'angry' | 'left' | 'blocked';

const TONE_LABEL: Record<Tone, string> = { kind: '다정', bold: '대담', witty: '유머', logical: '논리', flatter: '칭찬', threat: '위협' };

/**
 * Shin Megami Tensei style negotiation.
 *  - two questions per talk; answers change mood by personality
 *  - optional demand (item / gears / HP)
 *  - final roll: base + mood + parries (rapport) + HP loss + broken + level diff
 */
export interface TalkOptions {
  /** Hold-up 포위 협상: +25% chance, the enemy can't storm off or fly into a rage. */
  cornered?: boolean;
  /** Other party members still standing — a recruited monster of the same species / temperament chimes in. */
  allies?: BUnit[];
}

export async function negotiate(ui: BattleUI, talker: BUnit, enemy: BUnit, showHints: boolean, opts: TalkOptions = {}): Promise<{ outcome: TalkOutcome; chance?: number }> {
  const sp = enemy.species!;
  const per = PERSONALITIES[sp.personality];
  const st = State.current;
  const name = sp.name;
  const col = sp.color;
  ui.beginTalk(enemy); // every exit below ends with ui.closeDialog(), which ends the talk scene

  if (sp.talkGate === 'brokenOrHalf' && !enemy.broken && enemy.hp > enemy.maxHp * 0.5 && !opts.cornered) {
    await ui.say(name, pick(per.greet), col, sp.id);
    await ui.say('시스템', '말이 통하지 않는다... (브레이크 상태이거나 HP가 절반 이하일 때 협상 가능)', '#9aa2ad');
    ui.closeDialog();
    return { outcome: 'blocked' };
  }

  enemy.talks++;
  await ui.say(name, enemy.broken ? pick(per.greetBroken) : pick(per.greet), col, sp.id);
  if (opts.cornered) await ui.say('시스템', '도망칠 곳이 없다 — 상대가 귀를 기울인다. (영입 확률 +25%)', '#9aa2ad');
  if (enemy.talks === 1 && showHints) {
    await ui.say('시스템', `성격: 「${per.name}」 — ${per.desc}`, '#9aa2ad');
  }
  // a recruited monster of the same kind (or the same temperament) vouches for the party
  const kin = opts.allies?.find((a) => a.species?.id === sp.id) ?? opts.allies?.find((a) => a.species && a.species.personality === sp.personality);
  if (kin) {
    const same = kin.species!.id === sp.id;
    await ui.say(kin.name, (same ? VOUCH_SAME[sp.personality] : VOUCH_KIN[sp.personality]) ?? '이 사람들, 믿어도 돼.', kin.color, kin.pid);
    enemy.mood += same ? 2 : 1;
    Sfx.play('ui_ok');
    await ui.say(name, pick(per.like), col, sp.id, 'happy');
  }

  // two questions
  const pool = shuffle(QUESTIONS.map((_, i) => i).filter((i) => !enemy.asked.has(i)));
  if (pool.length < 2) enemy.asked.clear();
  const qs = (pool.length >= 2 ? pool : shuffle(QUESTIONS.map((_, i) => i))).slice(0, 2);
  for (const qi of qs) {
    enemy.asked.add(qi);
    const q = QUESTIONS[qi];
    const answers = shuffle([...q.answers]);
    const idx = await ui.choose(name, q.text, answers.map((a) => (showHints ? `${a.text} <span class="tone">${TONE_LABEL[a.tone]}</span>` : a.text)), col, sp.id);
    const tone = answers[idx].tone;
    const delta = per.likes[tone];
    enemy.mood += delta;
    const line = delta >= 1 ? pick(per.like) : delta === 0 ? pick(per.neutral) : pick(per.dislike);
    const face = delta >= 1 ? 'happy' : delta < 0 ? 'angry' : undefined;
    if (delta > 0) Sfx.play('ui_ok');
    else if (delta < 0) Sfx.play('talk_fail');
    await ui.say(name, line + (showHints ? `  (${delta >= 0 ? '+' : ''}${delta})` : ''), col, sp.id, face);
    if (enemy.mood <= -3 && !opts.cornered) {
      await ui.say(name, pick(per.angry), col, sp.id, 'angry');
      ui.closeDialog();
      enemy.mood = -1;
      return { outcome: 'angry' };
    }
  }

  // demand
  let gave = false;
  if (Math.random() < per.demandRate) {
    const d = pick(DEMANDS[sp.personality]);
    let detail = '';
    let can = true;
    if (d.kind === 'item') { detail = `${icon('item', d.item!, ITEMS[d.item!].icon)} ${ITEMS[d.item!].name} (보유 ${st.inventory[d.item!] ?? 0})`; can = (st.inventory[d.item!] ?? 0) > 0; }
    if (d.kind === 'money') { detail = `⚙ ${d.amount} 기어 (보유 ${st.money})`; can = st.money >= d.amount!; }
    if (d.kind === 'hp') { const amt = Math.ceil(talker.maxHp * d.amount!); detail = `${talker.name}의 HP ${amt}`; can = talker.hp > amt; }
    const idx = await ui.choose(name, `${d.text}<div class="demand">요구: ${detail}</div>`, [can ? '건넨다' : '건넨다 (부족함)', '거절한다'], col, sp.id);
    if (idx === 0 && can) {
      if (d.kind === 'item') st.useItem(d.item!);
      if (d.kind === 'money') st.money -= d.amount!;
      if (d.kind === 'hp') talker.hp -= Math.ceil(talker.maxHp * d.amount!);
      gave = true;
      enemy.mood += sp.personality === 'greedy' ? 3 : 2;
      Sfx.play('chest');
      await ui.say(name, pick(per.like), col, sp.id, 'happy');
    } else {
      enemy.mood -= 1;
      Sfx.play('talk_fail');
      await ui.say(name, idx === 0 ? '...없잖아.' : pick(per.dislike), col, sp.id, 'angry');
    }
  }

  // greedy/childish may run off with the gift (classic SMT trolling)
  if (gave && !opts.cornered && (sp.personality === 'childish' || sp.personality === 'greedy') && Math.random() < 0.1) {
    await ui.say(name, sp.personality === 'childish' ? '고마워~ 그럼 안녕! 부글부글~' : '부오오... 연료는 잘 받았다.', col, sp.id);
    ui.closeDialog();
    return { outcome: 'left' };
  }

  // final roll
  const lvDiff = clamp((talker.level - enemy.level) * 0.02, -0.12, 0.1);
  const already = st.bestiary[sp.id]?.recruited ? 0.08 : 0;
  const parts: [string, number][] = [
    [`기본 (성격: ${per.name})`, per.base],
    [`분위기 ${enemy.mood >= 0 ? '+' : ''}${enemy.mood}`, enemy.mood * 0.07],
    [`패링 성공 ×${enemy.rapport}`, Math.min(0.36, enemy.rapport * 0.06)],
    ['적 HP 손실', (1 - enemy.hp / enemy.maxHp) * 0.25],
    ['브레이크 상태', enemy.broken ? 0.15 : 0],
    ['레벨 차이', lvDiff],
    ['같은 종족 동료 보유', already],
    ['포위 협상', opts.cornered ? 0.25 : 0],
  ];
  let chance = parts.reduce((s, [, v]) => s + v, 0);
  if (sp.personality === 'honorable' && enemy.rapport === 0) {
    parts.push(['실력 미증명 (패링 0회) ×0.5', -chance * 0.5]);
    chance *= 0.5;
  }
  chance = clamp(chance, 0.05, 0.95);
  const success = Math.random() < chance;
  await ui.chanceRoll(parts, chance, success);
  if (success) {
    Sfx.play('recruit');
    await ui.say(name, pick(per.join), col, sp.id, 'happy');
    ui.closeDialog();
    return { outcome: 'joined', chance };
  }
  Sfx.play('talk_fail');
  await ui.say(name, pick(per.refuse), col, sp.id, 'angry');
  if (sp.personality === 'honorable' && enemy.rapport === 0) await ui.say(name, '...검으로 증명해 보아라. (패링에 성공하면 마음이 움직인다)', col, sp.id);
  // a talk that went well still leaves something behind: the creature lets slip what hurts it
  const b = st.bestiary[sp.id];
  const hidden = (Object.keys(sp.affinity) as (keyof typeof sp.affinity)[]).filter((k) => !b.known.includes(k));
  if (enemy.mood >= 2 && hidden.length) {
    b.known.push(...hidden);
    ui.refreshAffinity();
    await ui.say(name, TELL[sp.personality] ?? '...약한 곳? 말해 줄까 말까.', col, sp.id);
    await ui.say('시스템', `${name}의 약점·내성을 알아냈다.`, '#9aa2ad');
  }
  // the timid bolt when it goes badly
  if (sp.personality === 'timid' && !opts.cornered && enemy.mood < 0 && Math.random() < 0.4) {
    await ui.say(name, '히익—! (도망쳤다)', col, sp.id, 'angry');
    ui.closeDialog();
    return { outcome: 'left', chance };
  }
  ui.closeDialog();
  return { outcome: 'failed', chance };
}

const VOUCH_SAME: Record<string, string> = {
  timid: '찍찍! 이 사람들 무섭지 않아. 나 봐, 멀쩡하지?',
  childish: '부글~ 얘들이랑 있으면 매일 놀 수 있어!',
  proud: '이 몸이 인정한 자들이다. 너도 예를 갖춰라.',
  curious: '이 사람들 따라다니면 모르는 게 매일 생겨!',
  honorable: '내가 검을 맡긴 이들이다. 믿어도 좋다.',
  greedy: '부오... 여기 있으면... 연료가 끊이지 않는다.',
};
const VOUCH_KIN: Record<string, string> = {
  timid: '저, 저기... 이 사람들 착해. 진짜야.',
  childish: '같이 가자~ 재밌다니까!',
  proud: '흥, 이 몸 정도는 아니지만 쓸 만한 자들이다.',
  curious: '흥미로운 일행이야. 관찰해 볼 가치가 있어.',
  honorable: '이들의 검은 정직하다.',
  greedy: '...대접은 나쁘지 않다.',
};
/** What a creature lets slip about its weak spots after a friendly talk. */
const TELL: Record<string, string> = {
  timid: '나, 나는... 차가운 거랑 찌릿한 게 제일 무서워...',
  childish: '부글... 얼음은 싫어. 뭐든 다 굳어버리잖아.',
  proud: '...이 몸의 갑각도 번개만은 어쩔 수 없지. 말하지 마라.',
  curious: '내 불꽃은 차가운 거에 약해. 연구해 봐도 좋아.',
  honorable: '기사는 약점을 숨기지 않는다. 내 태엽은 번개에 흐트러진다.',
  greedy: '부오... 화로가 식는 건... 싫다...',
};
