import type { Story, L, PreBattle } from './story';
import type { BattleReport, BattleResult } from '../battle/battle';
import { ITEMS } from '../data/items';
import { PARTS } from '../data/parts';
import { Sfx } from '../core/audio';

/**
 * Chapter 1 「노래하는 정오」 — docs/story/CHAPTER1.md. Beats m01–m10, sub-quests sq01–sq05, camp
 * talks ct01–ct06. Progress lives in story flags (appendix A of the design doc).
 */
type Area = { id: string; zone: string; x: number; z: number; r: number; when: () => boolean; run: () => Promise<void> };

const SHOP: { id: string; price: number; kind: 'item' | 'part' | 'crystal'; after?: string }[] = [
  { id: 'tonic', price: 30, kind: 'item' },
  { id: 'hi_tonic', price: 90, kind: 'item' },
  { id: 'capsule', price: 60, kind: 'item' },
  { id: 'heart', price: 150, kind: 'item' },
  { id: 'p_heat_coil', price: 200, kind: 'part' },
  { id: 'p_cooling_fin', price: 200, kind: 'part' },
  { id: 'frost', price: 80, kind: 'crystal', after: 'ch1_met_bail' },
  { id: 'volt', price: 80, kind: 'crystal', after: 'ch1_met_bail' },
];

/** Quests for the notice board / log: title, giver, and the current step text. */
export interface QuestView { id: string; title: string; giver: string; state: 'locked' | 'open' | 'active' | 'done'; step: string; reward: string }

export class Chapter1 {
  private areas: Area[];
  /** m05 puzzle: how many crystals struck in the right order */
  private grove = 0;

  constructor(private s: Story) {
    const f = (id: string) => !!s.flag(id);
    this.areas = [
      { id: 'm02', zone: 'plains', x: -26, z: 4, r: 10, when: () => f('ch1_lamps_lit') && !f('ch1_lyra_joined'), run: () => this.m02() },
      { id: 'm05', zone: 'plains', x: 44, z: 4, r: 16, when: () => f('ch1_hub_arrived') && !f('m05_intro'), run: () => this.m05intro() },
      { id: 'm06c', zone: 'ashstack_works', x: 0, z: -26, r: 10, when: () => !f('ch1_met_bail'), run: () => this.m06yard() },
      { id: 'm07', zone: 'ashstack_works', x: -40, z: 0, r: 7, when: () => f('ch1_met_bail') && !f('ch1_valve_got'), run: () => this.m07() },
      { id: 'm09', zone: 'plains', x: 0, z: -36, r: 12, when: () => f('ch1_night_talk') && !f('ch1_holdup_done'), run: () => this.m09() },
      { id: 'm10c', zone: 'clocktower_interior', x: 0, z: -24, r: 5.5, when: () => !f('ch1_boss_done'), run: () => this.m10boss() },
    ];
  }

  private f(id: string) { return !!this.s.flag(id); }
  private set(id: string, v = 1) { this.s.set(id, v); }
  private say(...l: L[]) { return this.s.say(...l); }

  // =====================================================================
  // Objective tracker
  // =====================================================================
  goal(): string {
    const f = (id: string) => this.f(id);
    const s = this.s;
    let text = '';
    let pos: { zone: string; x: number; z: number } | null = null;
    if (!f('ch1_lamps_lit')) {
      const n = [1, 2, 3, 4, 5, 6].filter((i) => f(`lamp${i}`)).length;
      text = n < 6 ? `가스등 켜기 (${n}/6)` : '가스등을 갉던 톱니쥐 쫓아내기';
      const next = [45, 34, 23, 12, 1, -10].findIndex((_, i) => !f(`lamp${i + 1}`));
      pos = next >= 0 ? { zone: 'plains', x: next % 2 ? -4.2 : 4.2, z: [45, 34, 23, 12, 1, -10][next] } : { zone: 'plains', x: -10, z: 32 };
    } else if (!f('ch1_lyra_joined')) { text = '서쪽 파이프 야드의 이상한 불빛'; pos = { zone: 'plains', x: -26, z: 4 }; }
    else if (!f('ch1_tick_recruited')) { text = '가스등 뒤에 숨은 톱니쥐와 이야기하기'; pos = { zone: 'plains', x: 13, z: 41 }; }
    else if (!f('ch1_hub_arrived')) {
      text = s.st.zone === 'pause_station' ? '집배대 지부의 마르타, 공방의 피페 만나기' : '남쪽 길로 쉼표 역에 가기';
      pos = s.st.zone === 'pause_station' ? (f('met_marta') ? { zone: 'pause_station', x: -17, z: 12 } : { zone: 'pause_station', x: -15, z: -13 }) : { zone: 'plains', x: 0, z: 72 };
    } else if (!f('ch1_crystal_got')) { text = '동쪽 결정 숲의 노래하는 결정'; pos = { zone: 'plains', x: 46, z: 6 }; }
    else if (!f('ch1_met_bail')) { text = '서쪽 잿빛 굴뚝 조사'; pos = s.st.zone === 'ashstack_works' ? { zone: 'ashstack_works', x: 0, z: -26 } : { zone: 'plains', x: -72, z: 0 }; }
    else if (!f('ch1_valve_got')) { text = '굴뚝 서쪽 차고의 밸브실'; pos = { zone: 'ashstack_works', x: -46, z: 0 }; }
    else if (!f('ch1_night_talk')) { text = '쉼표 역에 돌아가 점등 표지에서 쉬기'; pos = { zone: 'pause_station', x: 8, z: 6 }; }
    else if (!f('ch1_holdup_done')) { text = '공명 결정과 밸브를 들고 탑 앞으로'; pos = { zone: 'plains', x: 0, z: -36 }; }
    else if (!f('ch1_tower_open')) { text = '탑 정문 조사'; pos = { zone: 'plains', x: 0, z: -46 }; }
    else if (!f('ch1_boss_done')) { text = '시계탑 종루로'; pos = s.st.zone === 'clocktower_interior' ? { zone: 'clocktower_interior', x: 0, z: 5 } : { zone: 'plains', x: 0, z: -46 }; }
    else if (!f('ch1_complete')) { text = '쉼표 역으로'; pos = { zone: 'pause_station', x: -15, z: -13 }; }
    else text = '제1장 클리어 — 못판의 의뢰와 남은 동료를 찾아보자';
    this.s.field?.hud.setGoal(text, pos);
    return text;
  }

  // =====================================================================
  // m01 「11시 47분」
  // =====================================================================
  async opening() {
    await this.s.black(
      '7년 전, 에테르 평원의 시계탑에서 사고가 있었다.',
      '기관사 한 명이 사라졌고, 그의 아들은 가슴에 기계 심장을 달고 살아남았다.',
      '그리고 7일 전. 그 탑이 정오 종을 울리지 않았다.',
    );
    await this.s.game.ui.fadeIn(600);
    this.s.game.ui.banner('제1장', '노래하는 정오', 'zone', 2600);
    await this.s.look([6, 9, -20], [0, 11, -52], 2.4);
    await this.say(
      ['카이', '…움직였다. 방금, 분침이.'],
      ['카이', '7일 동안 꿈쩍도 안 하더니.'],
      ['마르타(무전)', '카이, 꾸물대지 마. 길가 등 여섯 개, 다 켜고 와.'],
      ['카이', '쥐들이 또 심지를 갉았나 봐요. 평원이 오늘따라 시끄러워.'],
      ['마르타(무전)', '또 기계 소리 듣는 거냐. 귀 말고 눈을 써, 꼬마.'],
    );
  }

  private async lightLamp(i: number) {
    this.set(`lamp${i}`);
    Sfx.play('rest');
    this.s.field.refreshLights();
    const n = [1, 2, 3, 4, 5, 6].filter((k) => this.f(`lamp${k}`)).length;
    this.s.toast(`가스등을 켰다 (${n}/6)`, '', 1800);
    if (n === 2 && !this.f('m01_rats')) {
      this.set('m01_rats');
      await this.say(
        ['톱니쥐', '찍! 오, 오지 마! 이 불은 우리가 끈 거야!'],
        ['카이', '왜 끈 건데?'],
        ['톱니쥐', '밝으면… 끌려가는 게 보이잖아! 찍찍!'],
      );
      this.s.toast('필드에서 공격해 노란 <b>브레이크 게이지</b>를 채우면 적이 기절한다 → 선제 공격', 'gold', 6000);
    }
    this.checkLamps();
  }

  private checkLamps() {
    if (this.f('ch1_lamps_lit')) return;
    if ([1, 2, 3, 4, 5, 6].every((k) => this.f(`lamp${k}`)) && this.s.st.defeated.has('s_rat1')) {
      this.set('ch1_lamps_lit');
      this.s.toast('마르타(무전): 됐다. …서쪽에서 이상한 불빛이 보인다. 가 봐라.', 'gold', 5000);
    }
  }

  // =====================================================================
  // m02 「듣는 소녀」
  // =====================================================================
  private async m02() {
    await this.say(
      ['리라', '…잠깐, 다시 말해 줘. 탑이 어떻게 아프다고?'],
      ['보일러 젤리', '부글! 끌려가! 머리가 북쪽으로 끌려가!'],
      ['카이', '야! 거기서 떨어져!'],
      ['리라', '아, 아니— 지금 대화 중이었는데!'],
      ['램프 위스프', '인간이 하나 더? 흥미로워… 태워 볼까?'],
      ['리라', '…대화는 끝났네. 좋아, 도와줘. 이 아이들은 냉기에 약해.'],
    );
    this.s.st.addHero('lyra');
    const { result } = await this.s.battle(['slime', 'wisp'], { id: 'ev_lyra' });
    if (result !== 'victory') { this.s.st.active = this.s.st.active.filter((x) => x !== 'lyra'); this.s.st.roster = this.s.st.roster.filter((m) => m.id !== 'lyra'); return; }
    await this.say(
      ['카이', '너, 쟤네 말 알아들어?'],
      ['리라', '들리진 않아. 보여. (모노클을 톡 친다) 감정이 색으로.'],
      ['카이', '난 들리는데. 어릴 때부터.'],
      ['리라', '…뭐? 기령의 목소리가?'],
      ['리라', '리라 벨모어. 조율원에서 탑 조사차 왔어.'],
      ['카이', '카이. 집배대 견습. 등 켜는 중이었어.'],
      ['리라', '…저기 등 뒤에서 누가 떨고 있어. 회청색. 겁먹은 색이야.'],
    );
    this.set('ch1_lyra_joined');
    this.s.toast('<b>리라</b>가 동료가 되었다', 'gold');
  }

  // =====================================================================
  // m03 「겁쟁이의 박자」 (ev_tick, a field spawn the player walks up to)
  // =====================================================================
  private async m03pre(): Promise<PreBattle> {
    await this.say(
      ['톱니쥐', '히익! 때, 때리지 마… 태엽 풀렸어…'],
      ['리라', '공포도 72%… 아니, 80. 카이, 칼 내려.'],
      ['카이', '(칼을 내린다) 아까 끌려간다고 했지. 뭐가?'],
      ['톱니쥐', '머릿속이… 북쪽으로 끌려가. 종이 안 울리니까 붙잡아 줄 게 없어.'],
      ['리라', '내가 색을 읽을게. 넌 들어 줘. 둘이면 대화가 돼.'],
    );
    this.s.toast('턴이 오면 커맨드에서 <b>대화</b>를 고르자', 'gold', 5000);
    return { proceed: true, advantage: 'none', event: { id: 'ev_tick', broken: true, scriptTalk: 'tick', noFlee: true } };
  }

  private async m03after(report: BattleReport) {
    const st = this.s.st;
    if (!report.recruited.includes('cograt')) {
      // the tutorial rat never goes away until it has been talked to
      st.defeated.delete('ev_tick');
      await this.say(['리라', '…도망쳤어. 다시 가 보자. 이번엔 말로.']);
      return;
    }
    const tick = st.member('cograt');
    tick.name = '티크';
    tick.locked = true;
    await this.say(
      ['내레이션', '(흰·금빛 깃털 한 장이 천천히 내려와 카이의 손바닥에 앉는다.)'],
      ['리라', '…깃털. 여신의 깃털이야. 120년 동안 한 장도 관측된 적 없는.'],
      ['카이', '주운 거 아니야. 떨어진 거야. 얘가 같이 가자고 하니까.'],
      ['리라', '기록해야 해. 아니, 기록하면 안 돼. …조율원은 깃털을 회수하거든.'],
      ['카이', '이름 붙여 줄게. 째깍대니까… 티크.'],
      ['티크', '티크! 찍! 좋아!'],
      ['마르타(무전)', '둘 다 마을로 와. 지금. 남쪽 길 끝이다.'],
    );
    this.set('ch1_tick_recruited');
    this.s.toast('이제 전투에서 <b>대화</b> 커맨드로 몬스터를 영입할 수 있다. 메뉴 → 파티 편성', 'gold', 5000);
  }

  // =====================================================================
  // m04 「쉼표 역」
  // =====================================================================
  async enterZone(zone: string) {
    if (zone === 'pause_station' && !this.f('m04_plaza')) {
      this.set('m04_plaza');
      await this.say(
        ['포피', '우와, 언니 모자 크다! 그 쥐는 뭐야? 물어?'],
        ['티크', '아, 안 물어! 찍!'],
        ['포피', '말했다! 쥐가 말했어!'],
        ['리라', '…이 마을 사람들은 기령이 말해도 안 놀라?'],
        ['포피', '놀랐어! 엄청 좋아서!'],
      );
    }
    if (zone === 'ashstack_works' && !this.f('ch1_gauge')) {
      await this.say(
        ['리라', '카이, 등 돌려. 그 행낭 보일러, 호스 꽂을 구멍 있지?'],
        ['카이', '처음 보는 사람이 왜 내 보일러에— 아, 이제 처음은 아니구나.'],
        ['리라', '혼자 싸우면 압력이 버려지거든. 아까워. 다 같이 모았다가 한 번에 터뜨리는 거야.'],
      );
      this.set('ch1_gauge');
      this.s.toast('<b>증기압 게이지</b>와 연계기 「증기 회로참」이 열렸다', 'gold', 5000);
    }
    if (zone === 'clocktower_interior' && !this.f('ch1_engine_room')) {
      this.set('ch1_engine_room');
      await this.say(['리라', '구동축이 돈다… 위에서 종이 우는 소리가 나.'], ['티크', '찍… 머리가 울려.']);
    }
  }

  private async marta() {
    if (!this.f('met_marta')) {
      await this.say(
        ['마르타', '등 여섯 개 켜랬더니, 쥐랑 조율원 아가씨를 달고 왔군.'],
        ['리라', '리라 벨모어입니다. 탑 정문에 조율원 정숙 봉인이 걸려 있었어요.'],
        ['마르타', '…알아. 7일 전에 은회색 코트가 다녀갔지.'],
        ['카이', '마르타, 깃털이 떨어졌어요. 이거.'],
        ['마르타', '(한참 보다가) 도윈 녀석이 살아 있었으면 춤을 췄겠다.'],
        ['리라', '봉인은 구동축이 멈춰서 걸린 거예요. 축을 돌리려면 공명 결정 하나, 주 압력 밸브 하나.'],
        ['마르타', '결정은 동쪽 결정 숲, 밸브는 서쪽 잿빛 굴뚝. 굴뚝은 결정부터 가져오고 가. 거긴 험해.'],
        ['마르타', '받아라. 네 심장 울림통에 맞는 음핀이다.'],
      );
      this.set('met_marta');
      this.s.give({ parts: { p_steel_spring: 1 } }, '마르타');
      this.s.toast('메뉴 → <b>부품</b>: 같은 줄에 꽂은 부품의 속성 합이 기준을 넘으면 아츠가 열린다. 같은 속성을 이웃하게 꽂으면 +1.', 'gold', 7000);
      this.checkHub();
      return;
    }
    // sub-quest turn-ins and small talk
    if (this.f('sq01_bag_found') && !this.f('sq01_done')) return this.sq01done();
    if (this.f('ch1_complete') && !this.f('epilogue_seen')) return;
    const lines: L[][] = [
      [['마르타', '못판 봐라. 일은 늘 있다.']],
      [['마르타', '결정 숲은 동쪽, 굴뚝은 서쪽. 길 잃지 마라.']],
      [['마르타', '도윈은… 네 아빠는 기계 소리를 듣는다고 우겼지. 너처럼.']],
    ];
    await this.say(...lines[Math.floor(Math.random() * lines.length)]);
  }

  private async pippe() {
    if (!this.f('met_pippe')) {
      await this.say(
        ['피페', '어머나, 곡조 하나 들고 왔구나. 겁 많은 회청색 곡조네.'],
        ['티크', '오, 오르간이 말해…'],
        ['피페', '할미는 피페란다. 서로 다른 곡조 둘을 모아 오면 합주를 해 주마.'],
        ['피페', '단, 둘 다 좋다고 해야 해. 억지로 부르는 노래는 노래가 아니거든.'],
      );
      this.set('met_pippe');
      this.set('workshop');
      this.s.toast('메뉴에 <b>공방</b>이 열렸다 (부품 제작 · 합주는 이야기를 진행하면)', 'gold', 5000);
      this.checkHub();
      return;
    }
    if (this.f('ch1_night_talk') && !this.f('sq05_accepted')) return this.sq05start();
    if (this.f('sq05_first_fusion') && !this.f('sq05_done')) return this.sq05done();
    const i = await this.s.ask(['피페', '무슨 곡조를 들려줄까?'], ['공방을 연다 (부품 제작 · 합주)', '이야기만 한다', '그만둔다']);
    if (i === 0) { this.s.game.openPause(); this.s.game.menus.openTab('workshop'); }
    else if (i === 1) await this.say(['피페', this.f('fusion') ? '곡조 둘이 서로 좋다고 하면 합주가 돼. 친밀도라고들 하더구나.' : '곡조가 조금 더 모이면 합주를 해 주마.']);
  }

  private checkHub() {
    if (this.f('met_marta') && this.f('met_pippe') && !this.f('ch1_hub_arrived')) {
      this.set('ch1_hub_arrived');
      this.s.toast('못판에 의뢰가 붙었다. 다음 목표: 동쪽 결정 숲', 'gold', 4500);
    }
  }

  private async poppy() {
    if (!this.f('ch1_hub_arrived')) { await this.say(['포피', '쥐가 말했어! 말했다고!']); return; }
    if (!this.f('sq02_accepted')) return this.sq02start();
    if (this.f('sq02_lamps_lit') && !this.f('sq02_done')) return this.sq02done();
    if (this.f('sq02_accepted') && !this.f('sq02_done')) { await this.say(['포피', '절벽 쪽 등 세 개! 불꽃 친구랑 같이 가 줘!']); return; }
    await this.say(['포피', this.f('night') ? '밤에도 안 무서워. 등이 켜져 있으니까!' : '오늘은 기관차 지붕에 올라가면 안 된대. 칫.']);
  }

  private async shop() {
    const st = this.s.st;
    await this.say(['상점 주인', '어서 오시게. 「톱니와 저울」일세. 저울은 정직하고 톱니는 튼튼하지.']);
    for (;;) {
      const list = SHOP.filter((x) => !x.after || this.f(x.after));
      const name = (x: (typeof SHOP)[number]) => (x.kind === 'item' ? ITEMS[x.id].name : x.kind === 'part' ? `부품 · ${PARTS[x.id].name}` : `${{ frost: '냉기', volt: '뇌전' }[x.id]} 결정`);
      const owned = (x: (typeof SHOP)[number]) => (x.kind === 'item' ? st.inventory[x.id] ?? 0 : x.kind === 'part' ? st.parts[x.id] ?? 0 : st.crystals[x.id as 'frost']);
      const i = await this.s.ask(['상점 주인', `무엇을 드릴까. (가진 기어 ${st.money})`], [...list.map((x) => `${name(x)} — ⚙${x.price} (보유 ${owned(x)})`), '그만둔다']);
      if (i >= list.length) break;
      const x = list[i];
      if (st.money < x.price) { Sfx.play('ui_error'); this.s.toast('기어가 모자라다', 'red'); continue; }
      st.money -= x.price;
      if (x.kind === 'item') st.addItem(x.id);
      else if (x.kind === 'part') st.parts[x.id] = (st.parts[x.id] ?? 0) + 1;
      else st.addCrystals({ [x.id]: 1 });
      Sfx.play('chest');
      this.s.toast(`${name(x)} 구입 · 남은 기어 ${st.money}`, '', 2000);
    }
    await this.say(['상점 주인', '또 오시게.']);
  }

  // =====================================================================
  // m05 「결정 숲의 노래」
  // =====================================================================
  private async m05intro() {
    this.set('m05_intro');
    await this.say(
      ['리라', '들어 봐. 결정마다 음이 달라. 큰 게 낮고, 작은 게 높아.'],
      ['카이', '낮은 데서 높은 데로… 계단처럼?'],
      ['티크', '차, 찍… 반짝이 나방이 쳐다봐.'],
    );
  }

  private async strike(which: 'a' | 'b' | 'c') {
    const order = ['a', 'b', 'c'];
    Sfx.play(which === 'a' ? 'qte_good' : which === 'b' ? 'qte_perfect' : 'parry');
    if (order[this.grove] === which) {
      this.grove++;
      this.s.toast(`결정이 울린다 (${this.grove}/3)`, '', 1500);
      if (this.grove < 3) return;
      this.grove = 0;
      await this.say(
        ['내레이션', '(세 결정이 화음으로 울리고, 가장 큰 결정에서 손바닥만 한 공명 결정이 떠오른다.)'],
        ['프리즘 나방', '그 결정… 가져가면 여기 빛이 꺼져? 궁금해, 궁금해!'],
        ['놋쇠 딱정벌레', '이 몸이 지키는 숲에서 감히!'],
        ['리라', '빛은 안 꺼져. 원래 탑에 있던 걸 돌려줄 뿐이야. …말이 통할 분위기는 아니네.'],
      );
      const { result } = await this.s.battle(['beetle', 'prism_moth', 'prism_moth'], { id: 'ev_grove', noFlee: true });
      if (result !== 'victory') return;
      this.s.give({ crystals: { phys: 2, aether: 2 } }, '에테르 비늘');
      await this.say(
        ['리라', '바닥 봐. 비늘이 떨어졌어. 태엽이 풀리면 몸에서 떨어지는 에테르 비늘이야.'],
        ['카이', '다친 건 아니지?'],
        ['리라', '잠든 거야. 쉼표 등이 울리면 다시 깨어나. 이걸로 울림통 홈을 뚫을 수 있어.'],
        ['리라', '그리고 문양 둘을 엮는 법. 이제 보여 줄게.'],
        ['마르타(무전)', '결정 챙겼으면 서쪽 차단봉 올려 두마. 굴뚝에선 등 조심해라.'],
      );
      this.set('ch1_crystal_got');
      this.s.field.rebuild(); // the west barrier comes down
      this.s.toast('공명 결정을 얻었다 · 메뉴 → 부품에서 <b>속성 결정</b>으로 홈을 뚫을 수 있다 · 서쪽 굴뚝 길이 열렸다', 'gold', 6000);
    } else {
      this.grove = 0;
      await this.say(['리라', '음이 엉켰어. 처음부터— 앗, 나방이 몰려와!']);
      await this.s.battle(['prism_moth', 'prism_moth'], { id: 'sp_moth_puzzle' });
    }
  }

  // =====================================================================
  // m06 「잿빛 굴뚝」
  // =====================================================================
  private async m06yard() {
    await this.say(
      ['바일', '…쉿. 이제 안 아플 거다.'],
      ['내레이션', '(정숙 침이 꽂힌 톱니쥐가 조용해진다. 눈의 불빛이 꺼진다.)'],
      ['리라', '…오빠.'],
      ['바일', '리라. 아버지가 걱정하신다. 돌아가자.'],
      ['리라', '걱정하시는 게 나야, 아니면 내가 보게 될 것이야?'],
      ['바일', '봐라. 이제 안 아프다.'],
      ['카이', '그거, 안 아픈 게 아니라 아무것도 못 느끼는 거잖아.'],
      ['바일', '차이가 있나. …밸브는 가져가라. 어차피 그 탑은 다시 못 울린다.'],
    );
    const { result } = await this.s.battle(['knight', 'knight'], { id: 'ev_bail', hushed: true, names: ['정숙된 태엽 기사', '정숙된 태엽 기사'], noFlee: true });
    if (result !== 'victory') return;
    await this.say(
      ['리라', '렌즈에… 아무 색도 안 보여. 회색뿐이야.'],
      ['카이', '바일은?'],
      ['리라', '갔어. 오빠는 절대 먼저 치지 않아. 늘 받아치지.'],
      ['카이', '…난 늘 먼저 베는데.'],
    );
    this.set('ch1_met_bail');
    this.s.field.refreshActors();
  }

  // =====================================================================
  // m07 「금고지기」
  // =====================================================================
  private async m07() {
    await this.say(
      ['금고 거북', '오, 오지 마! 이 문은 안 열려! 감독님이 열지 말라고 했어!'],
      ['카이', '감독님이 언제 그랬는데?'],
      ['금고 거북', '…백 년 전. 그 뒤로 아무도 안 왔어. 아무도 그만하라고 안 했어.'],
      ['리라', '그래서 멈출 수가 없는 거구나.'],
      ['금고 거북', '다가오면 잠근다! 다 잠근다!'],
    );
    this.s.toast('패링에 성공할수록 이 적을 설득하기 쉬워진다 (♦ 표시)', 'gold', 5000);
    const { result, report } = await this.s.battle(['strongbox_tortoise'], { id: 'ev_tortoise' });
    if (result === 'defeat') return;
    await this.tortoiseAfter(report);
  }

  private async tortoiseAfter(report: BattleReport) {
    const joined = report.recruited.includes('strongbox_tortoise');
    if (joined) {
      await this.say(
        ['카이', '이제 그만 지켜도 돼. 우리가 맡을게. 대신 너도 같이 가자.'],
        ['금고 거북', '…맡아 준다고? 그럼 나, 처음으로 문 열어 볼래.'],
      );
      this.set('ch1_tortoise_joined');
    } else if (!this.f('ch1_valve_got')) {
      await this.say(
        ['금고 거북', '열쇠만… 열쇠만 줄게. 나는 아직 여기 있을래.'],
        ['리라', '언젠가 다시 오자. 저 아이, 아직 "그만해도 된다"는 말을 기다리고 있어.'],
      );
    }
    if (!this.f('tortoise_hinge')) { this.set('tortoise_hinge'); this.s.give({ parts: { p_strongbox_hinge: 1 } }, '금고 거북'); }
    if (!this.f('ch1_valve_got')) {
      this.set('ch1_valve_got');
      this.s.toast('<b>주 압력 밸브</b>를 얻었다 · 동쪽으로 가는 광차 레일 지름길이 열렸다', 'gold', 5000);
    }
  }

  // =====================================================================
  // m08 「쉼표의 밤」 — first rest at the hub with both keys
  // =====================================================================
  private async m08() {
    await this.s.fade(() => { this.set('night'); this.s.field.rebuild(); }, 700);
    await this.say(
      ['리라', '카이. 렌즈로 보면 네 가슴에서 색이 보여. 기령의 색.'],
      ['카이', '…무슨 색인데.'],
      ['리라', '회청이랑 금이 섞였어. 여섯 성격 어디에도 없는 색이야.'],
      ['카이', '아버지가 마지막에 그랬어. "이 아이도 살고 싶대." 난 그게 나인 줄 알았는데.'],
      ['티크', '…거기, 따뜻해. 나랑 비슷한 냄새가 나.'],
    );
    this.s.st.addBond('lyra', 1);
    this.s.st.addBond('cograt', 1);
    this.s.toast('<b>캠프 대화</b> — 동료와 이야기하면 친밀도가 오른다 (리라 ♥ · 티크 ♥). 친밀도가 가득 차면 연계기가 열린다.', 'gold', 6500);
    await this.say(
      ['리라', '집에 메트로라는 자동인형이 있었어. 매일 밤 노래를 불러 줬지.'],
      ['리라', '고장 났을 때 오빠가 침을 꽂았어. 아프지 말라고.'],
      ['리라', '지금도 내 곁에 와. 그런데 입이 안 움직여.'],
      ['카이', '그럼 탑부터 울리자. 노래가 어디 갔는지는 몰라도, 시작은 거기야.'],
    );
    await this.s.look([6, 6, 8], [0, 4.6, -6], 1.6);
    await this.say(
      ['베르디', '종을 울릴 거라면 —끝— 노래로 울려라 —끝—'],
      ['베르디', '정숙으로 울리면 우리가 먼저 탑을 부순다 —끝—'],
      ['카이', '넌 누구야?'],
      ['베르디', '녹청 연대 —끝— 답신은 깃털로 받겠다 —끝—'],
    );
    this.set('ct01');
    await this.s.fade(() => { this.set('night', 0); this.s.field.rebuild(); }, 700);
    await this.say(
      ['피페', '곡조가 늘었구나. 합주해 보련? 둘 다 좋다고 하면 말이야.'],
      ['티크', '나, 나는 빼 줘! 찍!'],
      ['피페', '호호, 너는 이야기 한가운데 있는 곡조라 안 건드린단다.'],
    );
    this.set('fusion');
    this.set('ch1_night_talk');
    const mons = this.s.st.roster.filter((m) => m.kind === 'monster' && !m.locked);
    if (mons.length < 2) await this.say(['피페', '곡조가 하나뿐이구나. 결정 숲 나방이나 굴뚝 두꺼비랑 얘기해 보렴.']);
    this.s.toast('<b>공방 합주</b>가 열렸다 · 다음 목표: 탑 앞으로', 'gold', 5000);
  }

  // =====================================================================
  // m09 「기적 쉼표」
  // =====================================================================
  private async m09() {
    await this.say(
      ['태엽 기사', '멈춰라. 탑심께서 7일째 비명을 지르신다. 아무도 들이지 않겠다.'],
      ['톱니쥐', '찍! 찍! 무서워! 다 무서워!'],
      ['리라', '전부 태엽을 풀어 버리면… 다 같이 멈춰서 말이 들릴지도 몰라.'],
      ['카이', '한꺼번에? 해 보자.'],
    );
    this.set('ch1_holdup');
    this.s.toast('적 <b>전원을 브레이크</b>시키면 홀드업 — 행낭 보일러의 기적으로 전장을 멈춘다', 'gold', 6000);
    const { result, report } = await this.s.battle(['knight', 'cograt', 'cograt'], {
      id: 'ev_gate',
      lines: { cornered: [['카이', '(행낭 보일러의 기적을 길게 당긴다.)'], ['태엽 기사', '…이 기적 소리. 레너 기관사가 쓰던 소리다. 그대, 레너의 핏줄인가.'], ['카이', '아들이야.'], ['태엽 기사', '그렇다면 들어라. 탑심께 검은 침이 박혔다. 뽑아 드려라.']] },
    });
    if (result === 'defeat') return;
    if (report.holdup === 'extort') {
      await this.say(['티크', '…카이, 그거 조율원 순찰대가 하는 짓이야.'], ['카이', '…미안. 급했어.']);
      for (const m of this.s.st.roster) this.s.st.addBond(m.id, -1);
      this.s.toast('동료의 친밀도가 내려갔다', 'red');
    }
    if (!report.holdup) await this.say(['리라', '…한 번에 다 멈추게 하는 건 어려웠네. 그래도 길은 열렸어.']);
    this.set('ch1_holdup_done');
    await this.say(['리라', '정문이야. 결정과 밸브를 끼워 보자.']);
  }

  private async towerDoor() {
    await this.say(
      ['내레이션', '(공명 결정과 압력 밸브를 끼우자 구동축이 덜컹 돌고, 봉인 문양이 재처럼 흩어진다.)'],
      ['리라', '열렸어. 안에서… 종이 우는 소리가 나.'],
    );
    this.set('ch1_tower_open');
    this.s.field.rebuild();
    this.s.toast('탑 앞에 두 번째 <b>점등 표지</b>가 켜졌다', 'gold');
  }

  // =====================================================================
  // m10 「종심」
  // =====================================================================
  private async m10boss() {
    await this.say(
      ['바일', '여기서 돌아가라. 저건 7일째 침을 맞고도 멈추지 않았다. 한 발이면 끝난다.'],
      ['리라', '오빠. 탑이 멈추고 평원이 7일 동안 어떻게 됐는지 봤어?'],
      ['바일', '봤다. 그래서 수도의 등은 꺼지지 않았지.'],
      ['카이', '…"그래서"? 일부러 끈 거야?'],
      ['내레이션', '(바일이 건틀릿을 겨눈다. 종이 울부짖고, 해머 팔이 바일을 벽까지 날려 버린다.)'],
      ['그란 카리용', '또 침이냐. 또 조용히 하라는 거냐!'],
    );
    const { result, report } = await this.s.battle(['grand_carillon'], {
      id: 'ev_carillon',
      noFlee: true,
      lines: {
        p2: '박이… 어긋난다. 침이 박을 갉는다!',
        parried: '…들었구나. 내 박을.',
        cornered: [
          ['그란 카리용', '나는 정오를 알리려고 만들어졌다. 울지 말라면, 나는 무엇이냐.'],
          ['카이', '울어도 돼. 7일 동안 혼자 참았잖아. 이번엔 우리가 같이 들을게.'],
          ['그란 카리용', '같이… 오십 년 동안 정오마다 울었지만, 들어 준 자는 레너 하나뿐이었다.'],
          ['카이', '그 레너, 우리 아빠야.'],
          ['그란 카리용', '그렇다면 뽑아라, 레너의 아들. 이번엔 노래로 울겠다.'],
        ],
      },
    });
    if (result === 'defeat') return;
    const joined = report.recruited.includes('grand_carillon');
    if (joined) this.set('ch1_carillon_joined');
    else await this.say(['카이', '미안. 조금만 참아. (침을 붙잡는다)'], ['그란 카리용', '…거칠군. 다음에 만나면, 이야기를 마저 하자.']);
    if (report.holdup === 'extort') for (const m of this.s.st.roster) this.s.st.addBond(m.id, -1);
    this.set('ch1_boss_done');
    await this.ending();
  }

  private async ending() {
    const ui = this.s.game.ui;
    await this.s.fade(() => { this.s.field.placeAtGate('plains', 'gate_tower_door'); }, 700);
    await this.s.look([10, 7, -24], [0, 13, -52], 1.2);
    await this.say(['내레이션', '(정오. 종이 50년 만에 노래로 울린다. 하나, 둘… 열둘.)']);
    ui.feathers(5);
    await this.say(
      ['내레이션', '(평원의 기령들이 멈춰 하늘을 올려다본다. 깃털 다섯 장이 천천히 내려온다.)'],
      ['티크', '카이… 머리가 조용해. 아니, 조용한 게 아니라… 다 들려.'],
      ['내레이션', '(열두 번째 종 뒤에, 기록에 없는 열세 번째 음이 울린다. 카이의 가슴이 같은 박으로 뛴다.)'],
      ['카이', '…방금 그거, 종이 아니야. 나야.'],
      ['리라', '(모노클 너머로) 깃털 떨어진 자리마다… 금빛 실이 북쪽으로 이어져 있어.'],
      ['바일(무전)', '제1 조율관께. 호른 변경 탑 재가동, 노래 모드. 기록에 없는 열세 번째 음 관측. 정오 회수, 지연됩니다.'],
      ['리라', '…제1 조율관. 아버지야.'],
    );
    await this.s.fade(() => { this.s.field.placeAtGate('pause_station', 'gate_station_north'); const p = this.s.field.player; p.pos.set(-15, 0, -9); p.yaw = Math.PI; }, 700);
    await this.say(
      ['마르타', '장부에 올려 두마. 집배대 장거리 배달, 북행 편.'],
      ['카이', '짐은요?'],
      ['마르타', '네 심장 소리. 받는 사람은 저 실 끝에 있겠지.'],
      ['리라', '간선 철도는 끊겼는데요.'],
      ['마르타', '그러니까 배달부가 걷는 거다. 원래 그래.'],
    );
    this.set('epilogue_seen');
    await this.s.black('제1장 「노래하는 정오」 — 끝', '같은 시각, 증기 운하 지대의 한 변경.', '은회색 코트 셋이 탑을 오르고, 그 탑의 종은 소리 없이 멎었다.');
    this.set('ch1_complete');
    if (this.f('ch1_carillon_joined')) this.s.recruit('grand_carillon', 11);
    await ui.fadeIn(600);
    ui.banner('제1장 클리어', '못판의 남은 의뢰와 동료들이 기다린다', 'zone', 3200);
    this.s.game.autosave();
  }

  // =====================================================================
  // Sub-quests
  // =====================================================================
  quests(): QuestView[] {
    const f = (id: string) => this.f(id);
    const st = (accepted: string, done: string, open: boolean) => (f(done) ? 'done' : f(accepted) ? 'active' : open ? 'open' : 'locked') as QuestView['state'];
    return [
      { id: 'sq01', title: '잃어버린 우편 가방', giver: '마르타 (못판)', state: st('sq01_accepted', 'sq01_done', f('ch1_hub_arrived')),
        step: f('sq01_bag_found') ? '마르타에게 보고' : '서쪽 파이프 야드(−34, 20)의 톱니쥐 두목에게서 가방 찾기 — 협상하면 보너스', reward: '150 기어 · 에테르 토닉 ×2 (평화적 해결 시 부품 추가)' },
      { id: 'sq02', title: '꺼진 등에 불을', giver: '포피', state: st('sq02_accepted', 'sq02_done', f('ch1_hub_arrived')),
        step: f('sq02_lamps_lit') ? '포피에게 알리기' : this.s.st.has('wisp') ? '램프 위스프를 파티에 넣고 절벽 쪽 꺼진 등 3개 조사' : '램프 위스프 영입하기', reward: '부품 렌즈 조각 · 하이 토닉' },
      { id: 'sq03', title: '광택 대결', giver: '광채 3세 (평원 −44, −16)', state: st('sq03_accepted', 'sq03_done', f('ch1_tick_recruited')),
        step: '아이템 없이 패링 3회 이상 성공한 뒤 브레이크', reward: '광채 3세 영입 · 메트로놈 핀 · 강철 결정 ×2' },
      { id: 'sq04', title: '교대 근무', giver: '문지기 기사 (평원 −12, −40)', state: st('sq04_accepted', 'sq04_done', f('ch1_crystal_got')),
        step: f('sq04_oath_found') ? '문지기 기사에게 서약서 낭독' : '잿빛 굴뚝 감독관 사무실 터(−30, −34)에서 교대 서약서 찾기', reward: '태엽 기사 영입 · 작은 종추 · 하이 토닉 ×2' },
      { id: 'sq05', title: '첫 합주', giver: '피페', state: st('sq05_accepted', 'sq05_done', f('ch1_night_talk')),
        step: f('sq05_first_fusion') ? '피페에게 새 두꺼비 보여 주기' : '공방에서 보일러 젤리 + 램프 위스프 합주', reward: '부품 풀무 가죽 · 에테르 결정 ×2' },
    ];
  }

  private async nailBoard() {
    for (;;) {
      const qs = this.quests().filter((q) => q.state !== 'locked');
      const label = (q: QuestView) => `${q.state === 'done' ? '✔ ' : q.state === 'active' ? '▶ ' : ''}${q.title} — ${q.giver}`;
      const i = await this.s.ask(['내레이션', '못판에 의뢰서가 꽂혀 있다.'], [...qs.map(label), '닫는다']);
      if (i >= qs.length) return;
      const q = qs[i];
      await this.say(['내레이션', `「${q.title}」 ${q.state === 'done' ? '(완료)' : ''} — ${q.step}. 보수: ${q.reward}`]);
      if (q.id === 'sq01' && q.state === 'open') {
        const a = await this.s.ask(['마르타', '서쪽 파이프 야드 쥐들이 우편 가방을 물어 갔다. 편지가 스물세 통이야. 맡겠냐?'], ['맡는다', '나중에']);
        if (a === 0) { this.set('sq01_accepted'); this.s.field.refreshActors(); this.s.toast('의뢰 수락: 잃어버린 우편 가방', 'gold'); }
      }
    }
  }

  private async sq01done() {
    await this.say(['마르타', this.f('sq01_peaceful') ? '하나도 안 젖었군. …쥐랑 흥정했냐? 너답다.' : '편지는 무사하군. 쥐들은… 됐다, 수고했다.']);
    this.s.give({ money: 150, items: { tonic: 2 }, ...(this.f('sq01_peaceful') ? { parts: { p_copper_helix: 1 } } : {}) }, '잃어버린 우편 가방');
    this.set('sq01_done');
  }

  private async sq02start() {
    await this.say(
      ['포피', '저기 등이 꺼지고 나서 밤에 절벽 쪽이 무서워. 불 켜 줄 수 있어?'],
      ['리라', '성냥으로는 안 켜져. 저건 에테르 등이야. …불을 아는 아이가 필요해.'],
    );
    this.set('sq02_accepted');
    if (this.s.st.has('wisp')) this.set('sq02_wisp_recruited');
    this.s.toast('의뢰 수락: 꺼진 등에 불을 — 램프 위스프를 파티에 넣고 절벽 쪽 등 3개 조사', 'gold', 5000);
  }

  private async sq02lamp(i: number) {
    const st = this.s.st;
    if (!st.active.includes('wisp')) { await this.say(['리라', '불을 아는 아이가 있어야 해. 램프 위스프를 파티에 넣자.']); return; }
    this.set(`sq02_lamp${i}`);
    this.s.field.refreshLights();
    Sfx.play('fire');
    if (i === 1) await this.say(['램프 위스프', '여기 살라는 건 아니지? 그냥 불만? 흐음, 흥미로운 일이네.']);
    if ([1, 2, 3].every((k) => this.f(`sq02_lamp${k}`))) {
      this.set('sq02_lamps_lit');
      await this.say(['램프 위스프', '지나가는 사람들 얘기, 등 안에서 다 들리겠다.']);
    }
  }

  private async sq02done() {
    await this.say(['포피', '켜졌다! 고마워, 불꽃아!']);
    this.s.give({ parts: { p_lens_shard: 1 }, items: { hi_tonic: 1 } }, '꺼진 등에 불을');
    this.set('sq02_done');
  }

  private async sq05start() {
    await this.say(['피페', '끓는 물 곡조랑 등불 곡조. 둘을 겹치면 뭐가 될까?']);
    this.set('sq05_accepted');
    this.s.toast('의뢰 수락: 첫 합주 — 공방에서 보일러 젤리 + 램프 위스프', 'gold', 5000);
  }

  private async sq05done() {
    await this.say(['풀무 두꺼비', '꾸르륵… 배고파. 태어나자마자 배고파.'], ['피페', '호호, 욕심 많은 곡조가 나왔구나. 소절은 잘 남았니?']);
    this.s.give({ parts: { p_bellows_leather: 1 }, crystals: { aether: 2 } }, '첫 합주');
    this.set('sq05_done');
  }

  onFusion(species: string) {
    if (species === 'bellows_toad' && this.f('sq05_accepted') && !this.f('sq05_first_fusion')) {
      this.set('sq05_first_fusion');
      this.s.toast('피페에게 새 두꺼비를 보여 주자', 'gold');
    }
  }

  // =====================================================================
  // Pre/after battle hooks for field spawns
  // =====================================================================
  async preBattle(spawn: string): Promise<PreBattle> {
    const go: PreBattle = { proceed: true };
    if (spawn === 'ev_tick') return this.m03pre();
    if (spawn === 'ev_tortoise') return { proceed: true, event: { id: 'ev_tortoise' } };
    if (spawn === 's_rat2_boss') {
      await this.say(['톱니쥐(두목)', '찍! 이건 둥지야! 종이가 폭신해!'], ['카이', '둥지는 다른 걸로 만들어 줄게. 편지는 기다리는 사람이 있어.']);
      return { proceed: true, event: { id: 's_rat2_boss', names: ['톱니쥐 두목'] } };
    }
    if (spawn === 's_beetle1' && this.f('ch1_tick_recruited') && !this.f('sq03_done')) {
      if (!this.f('sq03_accepted')) {
        await this.say(['광채 3세', '이 몸의 뿔 돌진을 세 번 받아 낼 수 있나? 물약 따위에 기대지 말고.'], ['카이', '세 번 받으면?'], ['광채 3세', '이 광택을 너희 편에 빌려주지.']);
        const a = await this.s.ask(['광채 3세', '어떤가.'], ['받아들인다', '나중에']);
        if (a !== 0) return { proceed: false };
        this.set('sq03_accepted');
      } else await this.say(['광채 3세', '또 왔군. 이번엔 물약 없이 받아 봐라.']);
      return { proceed: true, advantage: 'none', event: { id: 'sq03', duel: true, names: ['광채 3세'] } };
    }
    if (spawn === 's_knight1' && this.f('ch1_crystal_got') && !this.f('sq04_done')) {
      if (!this.f('sq04_accepted')) {
        await this.say(
          ['문지기 기사', '교대 신호 없이 자리를 뜰 수 없다. 백 년째 다음 근무자가 오지 않는다.'],
          ['카이', '신호가 적힌 종이 같은 거 있어?'],
          ['문지기 기사', '교대 서약서. 공장 감독관 사무실에 보관했었다.'],
        );
        this.set('sq04_accepted');
        this.s.toast('의뢰 수락: 교대 근무 — 잿빛 굴뚝 감독관 사무실 터에서 교대 서약서', 'gold', 5000);
      }
      if (this.f('sq04_oath_found')) {
        await this.say(
          ['카이', '(낭독) "근무를 마친 자에게 휴식을. 다음 박자는 우리가 잇는다."'],
          ['문지기 기사', '…그 문장이다. 이제 쉬어도 되는가.'],
          ['문지기 기사', '아니. 그대의 검에 내 태엽을 맡기겠다.'],
        );
        this.s.recruit('knight', 8, '문지기 기사');
        this.s.give({ parts: { p_quiet_bell: 1 }, items: { hi_tonic: 2 } }, '교대 근무');
        this.set('sq04_done');
      } else if (this.f('sq04_accepted')) await this.say(['문지기 기사', '서약서를 찾으면 다시 오라. 나는 여기 있다.']);
      return { proceed: false };
    }
    return go;
  }

  async afterSpawnBattle(spawn: string, result: BattleResult, report: BattleReport) {
    if (spawn === 's_rat1') this.checkLamps();
    if (spawn === 'ev_tick') return this.m03after(report);
    if (spawn === 'ev_tortoise' && result === 'victory') return this.tortoiseAfter(report);
    if (spawn === 's_rat2_boss' && result === 'victory') {
      this.set('sq01_bag_found');
      if (report.recruited.includes('cograt')) {
        this.set('sq01_peaceful');
        await this.say(['톱니쥐(두목)', '…기다리는 사람? 그럼 돌려줄게. 대신 솜 줘.']);
      }
      this.s.toast('우편 가방을 되찾았다 — 마르타에게 보고하자', 'gold');
    }
    if (spawn === 'sq03' || spawn === 's_beetle1') {
      if (report.duelWon) {
        await this.say(['광채 3세', '흠… 세 번 다 정확했다. 보는 눈이 아니라 받는 손이 있군.'], ['광채 3세', '좋다. 이 몸이 특별히 함께해 주지.']);
        this.s.recruit('beetle', 7, '광채 3세');
        this.s.give({ parts: { p_metronome_pin: 1 }, crystals: { phys: 2 } }, '광택 대결');
        this.set('sq03_done');
      } else if (this.f('sq03_accepted') && !this.f('sq03_done')) {
        this.s.st.defeated.delete('s_beetle1');
        await this.say(['광채 3세', '흥, 아직이다. 쉬고 다시 와라. (패링 3회 이상 · 아이템 없이 브레이크)']);
      }
    }
  }

  // =====================================================================
  // NPCs, spots, rest
  // =====================================================================
  async talk(npc: string) {
    switch (npc) {
      case 'marta': return this.marta();
      case 'poppy': return this.poppy();
      case 'shopkeeper': return this.shop();
    }
  }

  async spot(id: string) {
    const lamp = /^lamp(\d)$/.exec(id);
    if (lamp) return this.lightLamp(+lamp[1]);
    const sq2 = /^sq02_lamp(\d)$/.exec(id);
    if (sq2) return this.sq02lamp(+sq2[1]);
    switch (id) {
      case 'crys_a': return this.strike('a');
      case 'crys_b': return this.strike('b');
      case 'crys_c': return this.strike('c');
      case 'tower_door': return this.towerDoor();
      case 'pippe': return this.pippe();
      case 'nail_board': return this.nailBoard();
      case 'station_door': return this.say(['내레이션', '역사 문은 굳게 잠겨 있다. 녹슨 자물쇠에 조율원 문장이 찍혀 있다.']);
      case 'valve_seat': return this.say(['리라', '밸브가 있던 자리야. 이제 탑에 가져가기만 하면 돼.']);
      case 'shortcut_w': case 'shortcut_e': {
        const toEast = id === 'shortcut_w';
        await this.s.fade(() => { const p = this.s.field.player; p.pos.set(toEast ? 58 : -40, 0, toEast ? 6 : 2); p.yaw = toEast ? -Math.PI / 2 : Math.PI / 2; });
        return;
      }
      case 'dowin_note': {
        await this.say(['내레이션', '벽에 공구로 긁어 쓴 글씨가 있다.'], ['도윈(메모)', '탑심은 아이와 같다. 정숙 대신 노래를. 들어 주면 운다. 울게 둬라.'], ['카이', '…아빠 글씨야.']);
        this.set('ch1_dowin_note');
        return;
      }
      case 'lift_up': case 'lift_down': {
        const up = id === 'lift_up';
        Sfx.play('rest');
        await this.s.fade(() => { const p = this.s.field.player; p.pos.set(0, 0, up ? -19.5 : 7); p.yaw = up ? Math.PI : 0; });
        return;
      }
    }
  }

  /** Camp talks (ct01–ct06) at any rest point; m08 triggers on the hub's rest with both keys. */
  async rest() {
    const f = (id: string) => this.f(id);
    const st = this.s.st;
    if (st.zone === 'pause_station' && f('ch1_crystal_got') && f('ch1_valve_got') && !f('ch1_night_talk')) return this.m08();
    const talks: { id: string; title: string; when: boolean; lines: L[]; bond: string[] }[] = [
      { id: 'ct02', title: '먼저 베는 버릇', when: f('ch1_met_bail') && st.has('lyra'), bond: ['lyra'], lines: [
        ['리라', '너, 싸울 때 늘 먼저 뛰어들지. 열압 그래프가 톱니 같아.'], ['카이', '가만히 있으면 누가 다칠 것 같아서.'],
        ['리라', '오빠는 반대야. 절대 먼저 안 쳐. 다치는 걸 보고 나서 움직여.'], ['카이', '둘 다 별로네.'],
        ['리라', '응. 그러니까 넌 패링을 배워. 받으면서 식히는 거.'], ['카이', '…선생님 같다.'], ['리라', '수석이었거든.']] },
      { id: 'ct03', title: '티크의 첫 기억', when: f('ch1_tick_recruited') && st.flag('rests') >= 2 && st.has('cograt'), bond: ['cograt'], lines: [
        ['티크', '카이. 나, 원래 장난감이었어. 어떤 아이가 감아 줬어.'], ['카이', '그 아이는?'],
        ['티크', '몰라. 고양이가 오면 매번 도망쳤어. 백 번, 천 번, 만 번.'], ['티크', '그러다 보니까… 무서운 게 나였어. 내가 무서움이 됐어.'],
        ['카이', '지금도 무서워?'], ['티크', '응. 그래도 너 뒤에 있으면 반만 무서워. 찍.']] },
      { id: 'ct04', title: '처음 연 문', when: f('ch1_tortoise_joined') && st.has('strongbox_tortoise'), bond: ['strongbox_tortoise'], lines: [
        ['금고 거북', '저기… 내 안에 뭐가 들었는지 궁금하지 않아?'], ['카이', '궁금하지. 보여 주고 싶으면.'],
        ['금고 거북', '(덜컥) …아무것도 없어. 백 년 동안 빈 금고였어.'], ['리라', '그럼 넌 뭘 지킨 거야?'],
        ['금고 거북', '"열지 마라"는 말. 그 말이 없어지면 내가 없어질 것 같았어.'], ['카이', '이제 "같이 가자"는 말을 넣어 둬.']] },
      { id: 'ct05', title: '광택의 비결', when: f('sq03_done') && st.has('beetle'), bond: ['beetle', 'cograt'], lines: [
        ['광채 3세', '쥐. 너는 어째서 그리 칙칙하지?'], ['티크', '차, 찍! 구리라서 그래!'],
        ['광채 3세', '흥, 이 몸의 비결을 알려 주마. 매일 아침 같은 방향으로 백 번 닦는다.'], ['리라', '그거 결이 생기는 방식이랑 똑같네. 반복이 성격이 되는.'],
        ['광채 3세', '…그래서 이 몸이 이리 거만한 건가.'], ['티크', '알고 있었구나…']] },
      { id: 'ct06', title: '노래하는 정오 다음 날', when: f('ch1_complete'), bond: ['lyra', 'cograt', 'grand_carillon'], lines: [
        ['티크', '카이, 신기해. 종이 울린 다음부터 내 말이 길어졌어.'], ['리라', '색도 진해졌어. 정숙이 아니라 노래라서야.'],
        ['카이', '리라. 아버지 일… 괜찮아?'], ['리라', '안 괜찮아. 그래서 가 보려고. 직접 물어볼 거야.'],
        ...(st.has('grand_carillon') ? [['그란 카리용', '…정오에 너희 이름도 넣어 울려 주마.'] as L, ['카이', '그건 좀 창피한데.'] as L] : [])] },
    ];
    const open = talks.filter((t) => t.when && !f(t.id));
    if (!open.length) return;
    const i = await this.s.ask(['내레이션', '모닥불이 탁탁 튄다. 동료와 이야기할까?'], [...open.map((t) => `「${t.title}」`), '그냥 쉰다']);
    if (i >= open.length) return;
    const t = open[i];
    await this.say(...t.lines);
    this.set(t.id);
    const ups = t.bond.filter((id) => st.has(id)).map((id) => [id, st.addBond(id, 1)] as const);
    this.s.toast(`친밀도 ↑ ${ups.map(([id, v]) => `${st.member(id).name} ${'♥'.repeat(v)}`).join(' · ')}`, 'gold', 4000);
    // Tick at MAX bond: the gear-gust combo
    if (st.bond.cograt >= 3 && !f('combo_gear_gust')) {
      this.set('combo_gear_gust');
      this.s.toast('티크와의 연계기 「톱니 돌풍」이 열렸다', 'gold', 4500);
    }
  }

  areaAt(zone: string, x: number, z: number) {
    const a = this.areas.find((r) => r.zone === zone && Math.hypot(x - r.x, z - r.z) < r.r && r.when());
    return a ? a.run : null;
  }
}
