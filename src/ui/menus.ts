import * as THREE from 'three';
import { el } from '../core/utils';
import { icon, logoSrc, portraitInner } from './art';
import { Sfx } from '../core/audio';
import { Input } from '../core/input';
import { bindInput, padName, pb } from './glyph';
import { PadNav } from './padNav';
import { controlsPage } from './controlsHelp';
import { State } from '../game/state';
import { Graphics, QUALITY, type Quality } from '../game/graphics';
import type { Game } from '../game/game';
import { DIFFICULTY, ELEMENT_NAME, type Difficulty, type Element } from '../data/types';
import { HEROES, SPECIES, xpToNext } from '../data/units';
import { SKILLS } from '../data/skills';
import { ITEMS } from '../data/items';
import { PERSONALITIES } from '../data/negotiation';

const PAUSE_TABS: [string, string][] = [['party', '파티 편성'], ['bestiary', '몬스터 도감'], ['items', '소지품'], ['settings', '설정'], ['controls', '조작법']];

export class Menus {
  private title: HTMLElement | null = null;
  private pause: HTMLElement | null = null;
  private tab = 'party';
  private nav = new PadNav();
  private diag: HTMLElement | null = null;
  private diagHtml = '';
  /** the mounted controls page (title or pause tab), re-rendered whenever the input device changes */
  private controls: HTMLElement | null = null;

  constructor(private game: Game) {
    Input.subscribe((s) => {
      if (this.controls?.isConnected) this.controls.innerHTML = controlsPage(s);
    });
  }

  // -------------------------------------------------------------------------
  showTitle() {
    this.title?.remove();
    const t = el('div', 'title-screen', undefined, this.game.ui.topLayer);
    this.title = t;
    t.innerHTML = `
      <div class="ts-logo"><div class="ts-gear"></div>${logoSrc() ? `<img class="logo-img" src="${logoSrc()}" alt="MEGAMI EXPEDITION">` : '<h1>MEGAMI<br/>EXPEDITION</h1>'}<div class="ts-sub">증기와 에테르의 원정대 · Prototype</div></div>
      <div class="ts-menu"></div>
      <div class="ts-foot">스팀펑크 × 마법 · 필드 액션 + 턴제 패링 전투 + 협상 영입</div>`;
    const menu = t.querySelector('.ts-menu') as HTMLElement;
    const main = () => {
      this.nav.reset();
      menu.innerHTML = '';
      const b1 = el('button', 'btn big', '새 게임', menu);
      const b2 = el('button', 'btn', '조작법', menu);
      b1.onclick = () => { Sfx.unlock(); Sfx.play('ui_ok'); diff(); };
      b2.onclick = () => { Sfx.unlock(); Sfx.play('ui_ok'); help(); };
    };
    const diff = () => {
      this.nav.reset();
      menu.innerHTML = '<div class="ts-q">난이도 선택 <span class="dim">(패링·QTE 판정 폭 / 받는 피해, 메뉴에서 언제든 변경 가능)</span></div>';
      const row = el('div', 'diff-row', undefined, menu);
      (Object.keys(DIFFICULTY) as Difficulty[]).forEach((k) => {
        const d = DIFFICULTY[k];
        const c = el('button', `diff-card ${k}`, `<div class="dc-name">${d.name}</div><div class="dc-desc">${d.desc}</div>
          <div class="dc-stat">패링 ±${Math.round(d.parry * 1000)}ms · 회피 ±${Math.round(d.dodge * 1000)}ms</div>
          <div class="dc-stat">받는 피해 ×${d.enemyDmg}</div>`, row);
        if (k === 'normal') c.dataset.padFirst = '';
        c.onclick = () => {
          Sfx.play('ui_ok');
          this.title?.classList.add('out');
          setTimeout(() => { this.title?.remove(); this.title = null; }, 500);
          this.game.newGame(k);
        };
      });
      const back = el('button', 'btn small back', '← 뒤로', menu);
      back.onclick = () => { Sfx.play('ui_back'); main(); };
    };
    const help = () => {
      this.nav.reset();
      menu.innerHTML = '';
      this.controls = el('div', 'panel help-panel', controlsPage(Input.state), menu);
      const back = el('button', 'btn small back', '← 뒤로', menu);
      back.onclick = () => { Sfx.play('ui_back'); main(); };
    };
    main();
  }

  /** Gamepad navigation for whichever DOM menu is open (called every frame by Game). */
  padUpdate() {
    if (this.pause) {
      this.nav.update(this.pause, () => { Sfx.play('ui_back'); this.game.closePause(); }, (d) => this.cycleTab(d));
      this.updateDiag();
    } else if (this.title && !this.title.classList.contains('out')) {
      this.nav.update(this.title, () => (this.title?.querySelector('.back') as HTMLElement | null)?.click());
    }
  }

  /** Live view of what the browser reports for each pad (settings tab) — for odd controllers / Steam Input. */
  private updateDiag() {
    if (!this.diag?.isConnected) return;
    const html = Input.pads.length
      ? Input.pads.map((p) => {
          const on = p.index === Input.padIndex;
          const axes = p.axes.map((v, i) => `<span class="${Math.abs(v) > 0.3 ? 'hot' : ''}">${i}:${v.toFixed(2)}</span>`).join(' ');
          const btns = p.buttons.map((b, i) => (b.pressed ? i : -1)).filter((i) => i >= 0).join(' ') || '—';
          return `<div class="pd-pad${on ? ' on' : ''}"><div>${on ? '▶ 사용 중 · ' : ''}#${p.index} ${padName(p, true)} · ${p.mapping === 'standard' ? '표준 배치' : '<span class="kw red">비표준 배치</span>'}</div>
            <div class="dim">축 ${axes} · 누른 버튼 ${btns}</div></div>`;
        }).join('')
      : `<div>감지된 게임패드 없음 — 이 화면을 띄운 채 패드 버튼을 한 번 눌러 보세요.</div>
         <div class="dim">그래도 안 보이면 Steam 같은 프로그램이 패드 입력을 키보드/마우스 입력으로 바꿔 보내고 있는 상태일 수 있습니다.</div>`;
    if (html !== this.diagHtml) {
      this.diag.innerHTML = html;
      this.diagHtml = html;
    }
  }

  private cycleTab(dir: number) {
    const i = PAUSE_TABS.findIndex(([id]) => id === this.tab);
    this.tab = PAUSE_TABS[(i + dir + PAUSE_TABS.length) % PAUSE_TABS.length][0];
    Sfx.play('ui_move');
    this.renderPause();
    const tab = this.pause?.querySelectorAll<HTMLElement>('.pm-tab')[PAUSE_TABS.findIndex(([id]) => id === this.tab)];
    if (tab) this.nav.focus(tab);
  }

  // -------------------------------------------------------------------------
  showPause() {
    this.pause?.remove();
    const p = el('div', 'pause-menu', undefined, this.game.ui.topLayer);
    this.pause = p;
    p.innerHTML = `<div class="pm-box"><div class="pm-head"><h2>메뉴</h2><div class="pm-money">⚙ <span></span> 기어</div></div>
      <div class="pm-tabs"></div><div class="pm-body"></div>
      <div class="pm-foot"><button class="btn resume" data-pad-first>계속하기 <span class="resume-key"></span></button><button class="btn small title-btn">타이틀로</button></div></div>`;
    this.nav.reset();
    bindInput(p.querySelector('.resume-key') as HTMLElement, (s) => (s.device === 'pad' ? `(${pb('b')})` : '(Esc)'));
    (p.querySelector('.resume') as HTMLElement).onclick = () => { Sfx.play('ui_ok'); this.game.closePause(); };
    const titleBtn = p.querySelector('.title-btn') as HTMLElement;
    titleBtn.onclick = () => {
      // two-step confirm instead of window.confirm(), which a gamepad cannot answer
      if (!titleBtn.classList.contains('armed')) {
        titleBtn.classList.add('armed');
        titleBtn.textContent = '한 번 더 누르면 타이틀로 (저장 안 됨)';
        Sfx.play('ui_error');
        setTimeout(() => { titleBtn.classList.remove('armed'); titleBtn.textContent = '타이틀로'; }, 3000);
        return;
      }
      this.hidePause();
      this.game.paused = false;
      this.game.field.exit();
      this.game.showTitle();
    };
    const tabs = p.querySelector('.pm-tabs') as HTMLElement;
    for (const [id, label] of PAUSE_TABS) {
      const b = el('button', 'pm-tab' + (id === this.tab ? ' on' : ''), label, tabs);
      b.onclick = () => { Sfx.play('ui_move'); this.tab = id; this.renderPause(); };
    }
    this.renderPause();
  }

  hidePause() {
    this.pause?.remove();
    this.pause = null;
  }

  private renderPause() {
    const p = this.pause;
    if (!p) return;
    const st = State.current;
    (p.querySelector('.pm-money span') as HTMLElement).textContent = String(st.money);
    p.querySelectorAll('.pm-tab').forEach((b, i) => b.classList.toggle('on', PAUSE_TABS[i][0] === this.tab));
    const body = p.querySelector('.pm-body') as HTMLElement;
    body.innerHTML = '';
    if (this.tab === 'party') {
      bindInput(el('div', 'pm-note', '', body), (s) => `전투 참가 최대 3명 (카이 고정). ${s.device === 'pad' ? `카드에서 ${pb('a')}` : '카드를 클릭해'} 참가/대기를 전환. 같은 종족을 다시 영입하면 해당 동료에게 경험치가 흡수됩니다.`);
      const grid = el('div', 'roster', undefined, body);
      for (const m of st.roster) {
        const s = st.stats(m);
        const on = st.active.includes(m.id);
        const skills = st.skillsOf(m).map((id) => SKILLS[id]?.name).filter(Boolean).join(' · ');
        const sp = m.kind === 'monster' ? SPECIES[m.id] : null;
        const sub = m.kind === 'hero' ? HEROES[m.id as 'kai'].title : `${PERSONALITIES[sp!.personality].name} · 흡수 ${st.bestiary[m.id].absorbed}회`;
        const c = el('div', `rc ${on ? 'on' : ''} ${m.id === 'kai' ? 'locked' : ''}`, `
          <div class="rc-top"><div class="portrait" style="--c:${m.color}">${portraitInner(m.id, m.name)}</div>
          <div><div class="rc-name" style="color:${m.color}">${m.name} <span class="lv">Lv${m.level}</span></div><div class="dim">${sub}</div></div>
          <div class="rc-badge">${on ? '참가' : '대기'}</div></div>
          <div class="bar hp"><div class="fill" style="width:${(m.hp / s.hp) * 100}%"></div></div>
          <div class="rc-hp">HP ${Math.ceil(m.hp)} / ${s.hp} · EXP ${m.xp}/${xpToNext(m.level)}</div>
          <div class="rc-stats">공격 ${s.atk} · 마력 ${s.mag} · 방어 ${s.def} · 저항 ${s.res} · 속도 ${s.spd}</div>
          <div class="rc-skills">${skills}</div>`, grid);
        c.onclick = () => {
          if (m.id === 'kai') { Sfx.play('ui_error'); return; }
          if (on) st.active = st.active.filter((x) => x !== m.id);
          else if (st.active.length < 3) st.active.push(m.id);
          else { Sfx.play('ui_error'); this.game.ui.toast('참가 인원은 최대 3명입니다'); return; }
          Sfx.play('ui_ok');
          this.renderPause();
        };
      }
    } else if (this.tab === 'bestiary') {
      const grid = el('div', 'bestiary', undefined, body);
      for (const sp of Object.values(SPECIES)) {
        const b = st.bestiary[sp.id];
        const per = PERSONALITIES[sp.personality];
        const aff = Object.entries(sp.affinity).map(([k, v]) => `<span class="${v! > 1 ? 'weak' : 'resist'}">${icon('el', k)}${ELEMENT_NAME[k as Element]}${v! > 1 ? ' 약점' : ' 내성'}</span>`).join(' ');
        el('div', `bc ${b.seen ? '' : 'unseen'}`, b.seen ? `
          <div class="rc-top"><div class="portrait" style="--c:${sp.color}">${portraitInner(sp.id, sp.name)}</div>
          <div><div class="rc-name">${sp.name} <span class="lv">Lv${sp.level}</span></div><div class="dim">${{ weak: '약함 (필드 처치 가능)', strong: '강함 (브레이크만 가능)', elite: '정예' }[sp.tier]}</div></div>
          <div class="rc-badge ${b.recruited ? 'ok' : ''}">${b.recruited ? '영입' : '미영입'}</div></div>
          <div class="bc-desc">${sp.desc}</div>
          <div class="bc-row">성격: <b>${per.name}</b> — <span class="dim">${per.desc}</span></div>
          <div class="bc-row">${aff}</div>` : `<div class="rc-name">???</div><div class="dim">아직 만나지 못했다</div>`, grid);
      }
    } else if (this.tab === 'items') {
      const list = el('div', 'items-list', undefined, body);
      for (const [id, n] of Object.entries(st.inventory)) {
        const d = ITEMS[id];
        el('div', 'il-row', `<span>${icon('item', id, d.icon)} ${d.name}</span><span class="dim">${d.desc}</span><span>×${n}</span>`, list);
      }
    } else if (this.tab === 'settings') {
      el('div', 'pm-sec', '난이도 (패링/QTE 판정)', body);
      const row = el('div', 'diff-row small', undefined, body);
      (Object.keys(DIFFICULTY) as Difficulty[]).forEach((k) => {
        const d = DIFFICULTY[k];
        const c = el('button', `diff-card ${k} ${st.difficulty === k ? 'on' : ''}`, `<div class="dc-name">${d.name}</div><div class="dc-desc">${d.desc}</div><div class="dc-stat">패링 ±${Math.round(d.parry * 1000)}ms · 회피 ±${Math.round(d.dodge * 1000)}ms · 피해 ×${d.enemyDmg}</div>`, row);
        c.onclick = () => { st.difficulty = k; Sfx.play('ui_ok'); this.renderPause(); };
      });
      el('div', 'pm-sec', '옵션', body);
      const opt = el('div', 'opts', undefined, body);
      const ring = el('label', 'opt', `<input type="checkbox" ${st.showParryRing ? 'checked' : ''}/> 패링 타이밍 링 표시 <span class="dim">(하드에서는 항상 숨김)</span>`, opt);
      (ring.querySelector('input') as HTMLInputElement).onchange = (e) => { st.showParryRing = (e.target as HTMLInputElement).checked; };
      const vol = el('label', 'opt', `효과음 볼륨 <input type="range" min="0" max="1" step="0.05" value="${Sfx.volume}"/>`, opt);
      (vol.querySelector('input') as HTMLInputElement).oninput = (e) => Sfx.setVolume(Number((e.target as HTMLInputElement).value));
      const sens = el('label', 'opt', `마우스 감도 <input type="range" min="0.3" max="2.5" step="0.1" value="${st.mouseSens}"/>`, opt);
      (sens.querySelector('input') as HTMLInputElement).oninput = (e) => { st.mouseSens = Number((e.target as HTMLInputElement).value); };
      const pad = el('label', 'opt', `패드 시점 감도 <input type="range" min="0.3" max="2.5" step="0.1" value="${st.padSens}"/>`, opt);
      (pad.querySelector('input') as HTMLInputElement).oninput = (e) => { st.padSens = Number((e.target as HTMLInputElement).value); };
      const rum = el('label', 'opt', `<input type="checkbox" ${Input.rumbleOn ? 'checked' : ''}/> 패드 진동`, opt);
      (rum.querySelector('input') as HTMLInputElement).onchange = (e) => {
        Input.rumbleOn = (e.target as HTMLInputElement).checked;
        Input.rumble(0.5, 0.5, 150);
      };
      el('div', 'pm-sec', '그래픽 <span class="dim">(버벅이면 낮음 · 자동 해상도는 프레임이 떨어지면 렌더 해상도를 단계적으로 낮춥니다)</span>', body);
      const grow = el('div', 'diff-row small', undefined, body);
      (Object.keys(QUALITY) as Quality[]).forEach((k) => {
        const q = QUALITY[k];
        const c = el('button', `diff-card ${Graphics.quality === k ? 'on' : ''}`, `<div class="dc-name">${q.name}</div><div class="dc-desc">${q.desc}</div>`, grow);
        c.onclick = () => { Graphics.set({ quality: k }); Sfx.play('ui_ok'); this.renderPause(); };
      });
      const gopt = el('div', 'opts', undefined, body);
      const ar = el('label', 'opt', `<input type="checkbox" ${Graphics.autoRes ? 'checked' : ''}/> 자동 해상도`, gopt);
      (ar.querySelector('input') as HTMLInputElement).onchange = (e) => Graphics.set({ autoRes: (e.target as HTMLInputElement).checked });
      const r = this.game.renderer;
      const buf = r.getDrawingBufferSize(new THREE.Vector2());
      el('div', 'opt dim', `GPU: ${Graphics.gpu.replace(/[<>&]/g, '') || '알 수 없음'}${Graphics.integrated ? ' <span class="kw red">(내장 그래픽)</span>' : ''}<br/>렌더 해상도 ${buf.x}×${buf.y}${Graphics.autoRes ? ` · 자동 단계 ${Math.round(Graphics.scale * 100)}%` : ''}`, gopt);
      el('div', 'pm-sec', '입력 장치 <span class="dim">(브라우저가 보는 게임패드 · 스틱을 움직이면 해당 축 숫자가 바뀝니다)</span>', body);
      this.diag = el('div', 'pad-diag', '', body);
      this.diagHtml = '';
      this.updateDiag();
    } else {
      this.controls = el('div', 'controls-view', controlsPage(Input.state), body);
    }
  }
}
