import type { PersonalityId } from './units';

/** Shin Megami Tensei-style negotiation data. */
export type Tone = 'kind' | 'bold' | 'witty' | 'logical' | 'flatter' | 'threat';

export interface Personality {
  name: string;
  desc: string;
  /** Mood change per answer tone. */
  likes: Record<Tone, number>;
  /** Base recruit chance (0..1) before modifiers. */
  base: number;
  /** Probability of making a demand per talk session. */
  demandRate: number;
  greet: string[];
  greetBroken: string[];
  like: string[];
  neutral: string[];
  dislike: string[];
  angry: string[];
  join: string[];
  refuse: string[];
}

export const PERSONALITIES: Record<PersonalityId, Personality> = {
  timid: {
    name: '겁쟁이', desc: '다정한 말에 약하다. 위협하면 움츠러들지만 마음을 닫는다.',
    likes: { kind: 2, bold: -1, witty: 0, logical: 1, flatter: 1, threat: -1 },
    base: 0.35, demandRate: 0.4,
    greet: ['히익! 오, 오지 마!', '찍... 찍찍? 나, 나랑 얘기하려고?'],
    greetBroken: ['으으... 태엽이 풀렸어... 때리지 마...'],
    like: ['...정말? 너 좋은 사람이구나.', '찍! 그 말 맘에 들어.'],
    neutral: ['으, 응... 그렇구나.', '찍... 잘 모르겠어.'],
    dislike: ['히익! 무, 무서워!', '그런 말 하지 마...'],
    angry: ['싫어 싫어! 저리 가!'],
    join: ['나... 너희랑 같이 가도 돼? 찍!'],
    refuse: ['역시 무서워... 미안!'],
  },
  childish: {
    name: '천진', desc: '재밌는 걸 좋아한다. 딱딱한 이야기는 질색.',
    likes: { kind: 1, bold: 0, witty: 2, logical: -1, flatter: 1, threat: -2 },
    base: 0.4, demandRate: 0.5,
    greet: ['뽀글뽀글~ 너 누구야? 놀자!', '부글! 나랑 얘기할래?'],
    greetBroken: ['뿌우... 김 빠졌어...'],
    like: ['꺄하하! 너 재밌다!', '부글부글~ 좋아 좋아!'],
    neutral: ['흐응~', '뽀글?'],
    dislike: ['우웅... 재미없어.', '머리 아파아...'],
    angry: ['흥! 너랑 안 놀아!'],
    join: ['결정! 너희랑 같이 놀래! 부글~'],
    refuse: ['음~ 오늘은 그냥 갈래!'],
  },
  proud: {
    name: '고집', desc: '칭찬에 약하다. 농담이나 위협은 자존심을 건드린다.',
    likes: { kind: 0, bold: 1, witty: -1, logical: 0, flatter: 2, threat: -2 },
    base: 0.3, demandRate: 0.5,
    greet: ['감히 이 몸의 앞길을 막다니.', '흥, 이 광택이 보이나?'],
    greetBroken: ['크윽... 이 몸의 갑각에 흠집이...'],
    like: ['흠, 보는 눈은 있군.', '후후, 그렇지 그렇지.'],
    neutral: ['흥.', '...그래서?'],
    dislike: ['이 몸을 우습게 보는 건가!', '무례하군.'],
    angry: ['용서 못 한다!'],
    join: ['좋다. 이 몸이 특별히 함께해 주지.'],
    refuse: ['아직 이 몸과 어울리기엔 부족하다.'],
  },
  curious: {
    name: '호기심', desc: '논리적인 대답과 새로운 지식을 좋아한다. 아첨은 꿰뚫어 본다.',
    likes: { kind: 0, bold: 0, witty: 1, logical: 2, flatter: -1, threat: -1 },
    base: 0.35, demandRate: 0.35,
    greet: ['어머, 인간이네? 궁금한 게 있어.', '흐음... 너, 흥미로운 에테르 냄새가 나.'],
    greetBroken: ['불꽃이... 꺼질 것 같아... 그래도 궁금해...'],
    like: ['오오, 그렇구나! 새로운 걸 알았어.', '흥미로워! 더 말해 봐.'],
    neutral: ['흐음, 평범한 대답이네.', '그렇구나...'],
    dislike: ['그건 대답이 아니잖아.', '빤히 보여, 그런 말.'],
    angry: ['따분해! 태워버릴 거야!'],
    join: ['너희를 따라가면 더 많은 걸 알 수 있겠지? 좋아!'],
    refuse: ['아직 관찰이 더 필요해.'],
  },
  honorable: {
    name: '기사도', desc: '정면으로 맞서는 용기를 존중한다. 아첨과 농담을 경멸한다. 패링으로 실력을 증명하면 마음이 움직인다.',
    likes: { kind: 0, bold: 2, witty: -1, logical: 1, flatter: -2, threat: -1 },
    base: 0.2, demandRate: 0.2,
    greet: ['검을 거두고 말을 건다라... 이유를 들어보지.', '...말로 하겠다는 건가.'],
    greetBroken: ['훌륭한 일격이었다. 이야기를 들어주마.'],
    like: ['좋은 대답이다.', '그 각오, 진짜로군.'],
    neutral: ['...음.', '그런가.'],
    dislike: ['경박하군.', '그런 말로 기사를 움직일 수 없다.'],
    angry: ['말은 끝났다. 검으로 답하라!'],
    join: ['그대의 검에 내 태엽을 맡기겠다.'],
    refuse: ['아직 그대를 주군으로 인정할 수 없다.'],
  },
  greedy: {
    name: '탐욕', desc: '연료(아이템·기어)를 바치면 마음이 움직인다. 요구가 많다.',
    likes: { kind: 0, bold: 1, witty: -2, logical: 0, flatter: 1, threat: 0 },
    base: 0.15, demandRate: 1.0,
    greet: ['연료... 연료를 내놓아라...', '부오오... 배가... 고프다...'],
    greetBroken: ['화로가... 식는다... 연료를...'],
    like: ['부오... 나쁘지 않다.', '불꽃이... 조금 따뜻해졌다.'],
    neutral: ['...부오.', '연료는?'],
    dislike: ['부오오오!!', '불쾌하다.'],
    angry: ['전부 녹여버리겠다!'],
    join: ['부오오... 너희를 따라가면... 연료가 끊이지 않겠지.'],
    refuse: ['부족하다... 아직 부족해...'],
  },
  lonely: {
    name: '고독', desc: '오래 혼자였던 기령. 빈말은 금방 알아채고, 곁에 있어 주겠다는 진심에 약하다.',
    likes: { kind: 2, bold: 1, witty: 1, logical: -1, flatter: -2, threat: -1 },
    base: 0.25, demandRate: 0.3,
    greet: ['…누구냐.'],
    greetBroken: ['…멈췄군.'],
    like: ['…그 말, 오랜만에 듣는다.'],
    neutral: ['…그런가.'],
    dislike: ['빈말이군.'],
    angry: ['나가라. 혼자가 낫다!'],
    join: ['…곁에 있겠다는 말, 믿어 보마.'],
    refuse: ['아직은 혼자인 쪽이 덜 아프다.'],
  },
};

export interface Question {
  text: string;
  answers: { text: string; tone: Tone }[];
}

export const QUESTIONS: Question[] = [
  { text: '너희 인간들은 왜 그렇게 태엽을 감아대는 거지?', answers: [
    { text: '멈추지 않고 나아가기 위해서야.', tone: 'bold' },
    { text: '손이 심심해서? 하하.', tone: 'witty' },
    { text: '태엽은 힘을 저장하는 가장 단순한 장치니까.', tone: 'logical' },
  ] },
  { text: '내 몸, 멋있지 않아?', answers: [
    { text: '이 들판에서 제일 반짝이는걸.', tone: 'flatter' },
    { text: '녹슬기 전에 기름칠 해줄게.', tone: 'kind' },
    { text: '내 검이 더 멋있는데?', tone: 'bold' },
  ] },
  { text: '싸우는 거... 무섭지 않아?', answers: [
    { text: '무서워. 그래도 지킬 게 있으니까.', tone: 'kind' },
    { text: '전혀. 덤벼 봐.', tone: 'threat' },
    { text: '무서우니까 이렇게 대화하는 거잖아.', tone: 'witty' },
  ] },
  { text: '에테르는 어디서 오는 걸까?', answers: [
    { text: '별이 흘린 눈물이래.', tone: 'witty' },
    { text: '결정 공명 이론에 따르면 지맥에서 솟아나.', tone: 'logical' },
    { text: '몰라. 같이 찾아볼래?', tone: 'kind' },
  ] },
  { text: '증기와 마법, 어느 쪽이 더 강하지?', answers: [
    { text: '둘을 합치면 최강이지.', tone: 'logical' },
    { text: '그걸 증명하는 게 바로 너잖아.', tone: 'flatter' },
    { text: '강한 건 그걸 쓰는 사람이야.', tone: 'bold' },
  ] },
  { text: '배고파... 뭐 맛있는 거 없어?', answers: [
    { text: '내 도시락 나눠줄게.', tone: 'kind' },
    { text: '먹을 건 없고 검은 있어.', tone: 'threat' },
    { text: '기름 한 방울 칵테일 어때?', tone: 'witty' },
  ] },
  { text: '넌 왜 이런 곳까지 온 거야?', answers: [
    { text: '멈춘 시계탑을 다시 움직이려고.', tone: 'bold' },
    { text: '...사실 길을 잃었어.', tone: 'witty' },
    { text: '너를 만나러 왔지.', tone: 'flatter' },
  ] },
  { text: '날 부숴버릴 생각이었지?', answers: [
    { text: '아니, 친구가 되고 싶어.', tone: 'kind' },
    { text: '지금이라도 그럴 수 있어.', tone: 'threat' },
    { text: '부서진 건 고치면 돼. 난 정비사거든.', tone: 'logical' },
  ] },
  { text: '너에게 가장 소중한 건 뭐야?', answers: [
    { text: '동료들.', tone: 'kind' },
    { text: '내 검과 자존심.', tone: 'bold' },
    { text: '오늘 저녁 메뉴.', tone: 'witty' },
  ] },
  { text: '저 시계탑... 다시 움직일 수 있을까?', answers: [
    { text: '우리가 움직이게 할 거야.', tone: 'bold' },
    { text: '톱니 세 개만 갈면 될 것 같은데.', tone: 'logical' },
    { text: '너처럼 훌륭한 녀석이 도와준다면.', tone: 'flatter' },
  ] },
  { text: '내가 너희보다 약하다고 생각하지?', answers: [
    { text: '아니, 넌 충분히 강해.', tone: 'flatter' },
    { text: '응. 그러니까 순순히 따라와.', tone: 'threat' },
    { text: '강하고 약한 건 상성 문제야.', tone: 'logical' },
  ] },
  { text: '밤이 되면 왜 가스등이 켜지는 걸까?', answers: [
    { text: '누군가 길을 잃지 않게.', tone: 'kind' },
    { text: '압력식 타이머 밸브 덕분이지.', tone: 'logical' },
    { text: '등불도 밤엔 외로우니까.', tone: 'witty' },
  ] },
];

export interface Demand {
  kind: 'item' | 'money' | 'hp';
  text: string;
  item?: string;
  amount?: number;
}

export const DEMANDS: Record<PersonalityId, Demand[]> = {
  timid: [
    { kind: 'item', item: 'tonic', text: '저, 저기... 에테르 토닉 하나만... 줄 수 있어?' },
    { kind: 'money', amount: 20, text: '반짝이는 기어... 20개만 줄래?' },
  ],
  childish: [
    { kind: 'item', item: 'tonic', text: '그 반짝이는 물약! 나 줘 나 줘!' },
    { kind: 'hp', amount: 0.15, text: '너 따뜻해 보여~ 열기 조금만 나눠줘!' },
  ],
  proud: [
    { kind: 'money', amount: 40, text: '이 몸에게 예를 갖춰라. 기어 40개면 되겠군.' },
    { kind: 'item', item: 'hi_tonic', text: '하이 토닉 정도는 바쳐야 예의가 아닌가?' },
  ],
  curious: [
    { kind: 'item', item: 'capsule', text: '그 증기 캡슐, 어떻게 생겼는지 보고 싶어. 줄래?' },
    { kind: 'money', amount: 30, text: '기어 30개! 분해해 보고 싶거든.' },
  ],
  honorable: [
    { kind: 'hp', amount: 0.2, text: '그대의 각오를 보이라. 피로써.' },
  ],
  lonely: [
    { kind: 'hp', amount: 0.2, text: '…곁에 있겠다면, 그 온기를 조금 나눠 다오.' },
    { kind: 'item', item: 'heart', text: '멈춘 것을 다시 감는 심장… 그것을 주겠나.' },
  ],
  greedy: [
    { kind: 'money', amount: 100, text: '기어... 100개... 화로에 넣을 연료를...' },
    { kind: 'item', item: 'hi_tonic', text: '하이 토닉... 그 액체 연료를 내놓아라...' },
    { kind: 'item', item: 'capsule', text: '증기 캡슐... 압축된 증기를... 다오...' },
  ],
};
