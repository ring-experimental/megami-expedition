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
export async function negotiate(ui: BattleUI, talker: BUnit, enemy: BUnit, showHints: boolean): Promise<{ outcome: TalkOutcome; chance?: number }> {
  const sp = enemy.species!;
  const per = PERSONALITIES[sp.personality];
  const st = State.current;
  const name = sp.name;
  const col = sp.color;
  ui.beginTalk(enemy); // every exit below ends with ui.closeDialog(), which ends the talk scene

  if (sp.talkGate === 'brokenOrHalf' && !enemy.broken && enemy.hp > enemy.maxHp * 0.5) {
    await ui.say(name, pick(per.greet), col, sp.id);
    await ui.say('시스템', '말이 통하지 않는다... (브레이크 상태이거나 HP가 절반 이하일 때 협상 가능)', '#9aa2ad');
    ui.closeDialog();
    return { outcome: 'blocked' };
  }

  enemy.talks++;
  await ui.say(name, enemy.broken ? pick(per.greetBroken) : pick(per.greet), col, sp.id);
  if (enemy.talks === 1 && showHints) {
    await ui.say('시스템', `성격: 「${per.name}」 — ${per.desc}`, '#9aa2ad');
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
    if (enemy.mood <= -3) {
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
  if (gave && (sp.personality === 'childish' || sp.personality === 'greedy') && Math.random() < 0.1) {
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
  ui.closeDialog();
  return { outcome: 'failed', chance };
}
