/**
 * Controls help rendered for the device in use. Views call these from an Input.subscribe()
 * listener, so they re-render the moment the player switches between keyboard/mouse and a pad
 * (or plugs in a pad with a different layout).
 */
import type { InputState, PadStyle } from '../core/input';
import { padName, pb } from './glyph';

const LAYOUT: Record<PadStyle, string> = { xbox: 'Xbox 배치', ps: 'PlayStation 배치', nintendo: 'Nintendo 배치' };

/** "⌨ 키보드 · 마우스" or "🎮 <pad name> · <layout>" */
export function deviceLabel(s: InputState) {
  if (s.device === 'kb') return '⌨ 키보드 · 마우스';
  return `🎮 ${s.pad ? padName(s.pad) : '게임패드'} · ${s.pad && s.pad.mapping !== 'standard' ? '비표준 배치' : LAYOUT[s.padStyle]}`;
}

const fieldTips = (engage: string) => `<p class="dim">적의 노란 게이지(브레이크)를 채우면 기절 → ${engage}로 선제 공격 전투.<br/>적의 돌진/탄에 닿으면 전투 시작, 등 뒤를 맞으면 기습.<br/>약한 적(Lv 낮은 소형)은 필드에서 처치 가능하지만 영입할 수 없다.</p>`;
const BATTLE_TIPS = `<p class="dim">패링 성공: AP+1, 적 브레이크 누적, 해당 적 <b>영입 확률 상승</b>.<br/>공격의 모든 타격을 패링하면 자동 반격.<br/>대화: 성격에 맞는 대답 → 분위기 상승 → 영입 판정.</p>`;

const KB_GRID = `
  <div class="ctl-grid">
    <div><h3>필드</h3>
      <p><kbd>WASD</kbd> 이동 · <kbd>Shift</kbd> 달리기</p>
      <p><kbd>마우스</kbd> 시점 (화면 클릭으로 고정) · <kbd>방향키</kbd> 시점 · <kbd>C</kbd> 시점 정면으로 · <kbd>휠</kbd> 줌</p>
      <p><kbd>좌클릭</kbd>/<kbd>J</kbd> 약공격 3연타 · <kbd>우클릭</kbd>/<kbd>K</kbd> 강공격</p>
      <p><kbd>Space</kbd> 회피 · <kbd>E</kbd> 전투 개시/조사 · <kbd>Esc</kbd> 메뉴 · <kbd>H</kbd> 버튼 안내 숨기기</p>
      ${fieldTips('<kbd>E</kbd>')}
    </div>
    <div><h3>턴제 전투</h3>
      <p><kbd>W</kbd><kbd>S</kbd>/<kbd>1~5</kbd> 커맨드 · <kbd>A</kbd><kbd>D</kbd> 대상 · <kbd>Enter</kbd> 결정 · <kbd>Esc</kbd> 취소</p>
      <p>적 공격 시: <kbd>F</kbd>/<kbd>좌클릭</kbd> <b>패링</b> · <kbd>Space</kbd>/<kbd>우클릭</kbd> <b>회피</b></p>
      <p>스킬 QTE: 원이 맞물릴 때 <kbd>F</kbd>/<kbd>Space</kbd>/<kbd>좌클릭</kbd></p>
      ${BATTLE_TIPS}
    </div>
  </div>`;

const PAD_GRID = `
  <div class="ctl-grid">
    <div><h3>필드</h3>
      <p>${pb('ls')} 이동 (기울기만큼 속도) · ${pb('lb')} 누르고 있기 / ${pb('l3')} 달리기</p>
      <p>${pb('rs')} 시점 · ${pb('r3')} 시점 정면으로 · ${pb('dud')} 줌</p>
      <p>${pb('x')} 약공격 3연타 · ${pb('y')} 강공격 · ${pb('b')} 회피</p>
      <p>${pb('a')} 전투 개시/조사 · ${pb('start')} 메뉴 · ${pb('back')} 버튼 안내 숨기기</p>
      ${fieldTips(pb('a'))}
    </div>
    <div><h3>턴제 전투 · 메뉴</h3>
      <p>${pb('dpad')}/${pb('ls')} 커맨드·대상 선택 · ${pb('a')} 결정 · ${pb('b')} 취소</p>
      <p>적 공격 시: ${pb('a')}/${pb('rb')} <b>패링</b> · ${pb('b')} <b>회피</b></p>
      <p>스킬 QTE: 원이 맞물릴 때 ${pb('a')}/${pb('b')}/${pb('rb')}</p>
      <p>메뉴: ${pb('dpad')}/${pb('ls')} 이동 · ${pb('a')} 선택 · ${pb('b')} 닫기 · ${pb('lb')}${pb('rb')} 탭 전환</p>
      ${BATTLE_TIPS}
    </div>
  </div>`;

/** Full controls page (title → 조작법, pause → 조작법). */
export function controlsPage(s: InputState) {
  const pad = s.device === 'pad';
  const warn = pad && s.pad && s.pad.mapping !== 'standard'
    ? `<div class="ctl-warn">브라우저가 표준 배치로 인식하지 못한 패드입니다 — 실제 버튼 위치가 아래 표와 다를 수 있어요. 메뉴 → 설정 → 입력 장치에서 실제 입력을 확인하세요.</div>`
    : '';
  return `<div class="ctl-device"><b>${deviceLabel(s)}</b><span class="dim">${pad ? '키보드·마우스를 쓰면' : '게임패드 버튼을 누르면'} 그 장치의 조작법으로 바뀝니다</span></div>
    ${warn}${pad ? PAD_GRID : KB_GRID}
    ${pad ? '<p class="dim ctl-foot">진동 · 패드 시점 감도는 메뉴 → 설정.</p>' : ''}`;
}
