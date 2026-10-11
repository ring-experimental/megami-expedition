import * as THREE from 'three';
import { clamp, el } from '../core/utils';
import { artSrc, icon, logoSrc, portraitInner } from './art';
import { FEATHER_SVG, gearSvg } from './ornaments';
import { Sfx } from '../core/audio';
import { Input } from '../core/input';
import { bindInput, padName, pb } from './glyph';
import { PadNav, type Adjustable } from './padNav';
import { controlsPage } from './controlsHelp';
import './menus.css';
import './title.css';

/** Optional art file or the SVG placeholder. */
const img = (src: string | null, fallback: string) => (src ? `<img src="${src}" alt="" draggable="false">` : fallback);
import { State, type Member } from '../game/state';
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
  // Title — large logo top-left over the live 3D field, menu bottom-right (UI bible §9-8)
  // -------------------------------------------------------------------------
  showTitle() {
    this.title?.remove();
    const t = el('div', 'title-screen', undefined, this.game.ui.topLayer);
    this.title = t;
    const logo = logoSrc();
    const feather = img(artSrc('ui/feather'), FEATHER_SVG);
    t.innerHTML = `
      <div class="ts-gears"><div class="ts-gear big">${gearSvg(16)}</div><div class="ts-gear small">${gearSvg(11)}</div></div>
      <div class="ts-feathers">${[0, 1, 2].map((i) => `<div class="ts-feather" style="--i:${i}">${feather}</div>`).join('')}</div>
      <div class="ts-logo">${logo ? `<img class="logo-img" src="${logo}" alt="MEGAMI EXPEDITION">` : '<h1>MEGAMI<br/>EXPEDITION</h1>'}
        <div class="ts-sub"><span>증기와 에테르의 원정대</span><small>Prototype</small></div></div>
      <div class="ts-menu"></div>
      <div class="ts-foot">스팀펑크 × 마법 · 필드 액션 + 턴제 패링 전투 + 협상 영입</div>`;
    const menu = t.querySelector('.ts-menu') as HTMLElement;
    const back = () => {
      const b = el('button', 'mn-btn small back', '← 뒤로', menu);
      b.onclick = () => { Sfx.play('ui_back'); main(); };
    };
    const main = () => {
      this.nav.reset();
      menu.className = 'ts-menu';
      menu.innerHTML = '';
      const b1 = el('button', 'mn-btn big', '새 게임', menu);
      const b2 = el('button', 'mn-btn', '조작법', menu);
      b1.dataset.padFirst = '';
      b1.onclick = () => { Sfx.unlock(); Sfx.play('ui_ok'); diff(); };
      b2.onclick = () => { Sfx.unlock(); Sfx.play('ui_ok'); help(); };
    };
    const diff = () => {
      this.nav.reset();
      menu.className = 'ts-menu wide';
      menu.innerHTML = '<div class="ts-q"><span>난이도 선택</span><small>패링 · QTE 판정 폭과 받는 피해 — 메뉴 → 설정에서 언제든 바꿀 수 있습니다</small></div>';
      const row = el('div', 'ts-diffs', undefined, menu);
      (Object.keys(DIFFICULTY) as Difficulty[]).forEach((k, i) => {
        const d = DIFFICULTY[k];
        const c = el('button', `ts-diff ${k}`, `<div class="td-name">${d.name}</div><div class="td-desc">${d.desc}</div>
          <div class="td-stat"><span>패링</span><b>±${Math.round(d.parry * 1000)}ms</b></div>
          <div class="td-stat"><span>회피</span><b>±${Math.round(d.dodge * 1000)}ms</b></div>
          <div class="td-stat"><span>받는 피해</span><b>×${d.enemyDmg}</b></div>`, row);
        c.style.setProperty('--i', String(i));
        if (k === 'normal') c.dataset.padFirst = '';
        c.onclick = () => {
          Sfx.play('ui_ok');
          this.title?.classList.add('out');
          setTimeout(() => { this.title?.remove(); this.title = null; }, 500);
          this.game.newGame(k);
        };
      });
      back();
    };
    const help = () => {
      this.nav.reset();
      menu.className = 'ts-menu wide';
      menu.innerHTML = '';
      this.controls = el('div', 'ts-help', controlsPage(Input.state), menu);
      back();
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
    const tab = this.pause?.querySelectorAll<HTMLElement>('.mn-tab')[PAUSE_TABS.findIndex(([id]) => id === this.tab)];
    if (tab) this.nav.focus(tab);
  }

  // -------------------------------------------------------------------------
  // Pause menu — full-screen, slanted tabs on the left (UI bible §9-7)
  // -------------------------------------------------------------------------
  showPause() {
    this.pause?.remove();
    const p = el('div', 'pause-menu', undefined, this.game.ui.topLayer);
    this.pause = p;
    p.innerHTML = `<div class="mn-title">Menu</div><div class="mn-money">⚙ <b></b> 기어</div>
      <div class="mn-tabs"></div>
      <div class="mn-foot"><button class="mn-btn resume" data-pad-first>계속하기 <span class="resume-key"></span></button><button class="mn-btn small title-btn">타이틀로</button></div>
      <div class="mn-body"></div>`;
    this.nav.reset();
    bindInput(p.querySelector('.resume-key') as HTMLElement, (s) => (s.device === 'pad' ? pb('b') : '<kbd>Esc</kbd>'));
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
    const tabs = p.querySelector('.mn-tabs') as HTMLElement;
    PAUSE_TABS.forEach(([id, label], i) => {
      const b = el('button', 'mn-tab' + (id === this.tab ? ' on' : ''), `<span>${label}</span>`, tabs);
      b.style.setProperty('--i', String(i));
      b.onclick = () => { if (this.tab !== id) { Sfx.play('ui_move'); this.tab = id; this.renderPause(); } };
    });
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
    (p.querySelector('.mn-money b') as HTMLElement).textContent = String(st.money);
    p.querySelectorAll('.mn-tab').forEach((b, i) => b.classList.toggle('on', PAUSE_TABS[i][0] === this.tab));
    const body = p.querySelector('.mn-body') as HTMLElement;
    body.innerHTML = '';
    body.className = `mn-body tab-${this.tab}`;
    if (this.tab === 'party') this.renderParty(body);
    else if (this.tab === 'bestiary') this.renderBestiary(body);
    else if (this.tab === 'items') this.renderItems(body);
    else if (this.tab === 'settings') this.renderSettings(body);
    else this.renderControls(body);
  }

  /** Party: three battle slots on top, the reserve below, details of the hovered/focused card. */
  private renderParty(body: HTMLElement) {
    const st = State.current;
    bindInput(el('div', 'mn-note', '', body), (s) => `전투 참가 최대 3명 (카이 고정). ${s.device === 'pad' ? `카드에서 ${pb('a')}` : '카드를 클릭해'} 참가 ↔ 대기를 바꿉니다. 같은 종족을 다시 영입하면 그 동료에게 경험치로 흡수됩니다.`);
    const slots = el('div', 'pt-slots', undefined, body);
    el('div', 'mn-sec', '대기', body);
    const reserve = el('div', 'pt-reserve', undefined, body);
    const detail = el('div', 'pt-detail', '', body);
    const show = (m: Member) => {
      const s = st.stats(m);
      const skills = st.skillsOf(m).map((id) => SKILLS[id]?.name).filter(Boolean);
      const stat = (k: string, v: number) => `<div class="pd-stat"><span>${k}</span><b>${v}</b><i style="width:${Math.min(100, (v / 40) * 100)}%"></i></div>`;
      detail.innerHTML = `<div class="pd-name">${m.name}<span class="lv">Lv${m.level}</span></div>
        <div class="pd-stats">${stat('공격', s.atk)}${stat('마력', s.mag)}${stat('방어', s.def)}${stat('저항', s.res)}${stat('속도', s.spd)}</div>
        <div class="pd-skills">${skills.map((n) => `<span>${n}</span>`).join('') || '<span class="dim">스킬 없음</span>'}</div>`;
    };
    const card = (m: Member, big: boolean) => {
      const s = st.stats(m);
      const on = st.active.includes(m.id);
      const sp = m.kind === 'monster' ? SPECIES[m.id] : null;
      const sub = m.kind === 'hero' ? HEROES[m.id as 'kai'].title : `${PERSONALITIES[sp!.personality].name} · 흡수 ${st.bestiary[m.id].absorbed}회`;
      const c = el('div', `rc ${big ? 'pt-card' : 'pt-mini'}${on ? ' on' : ''}${m.id === 'kai' ? ' fixed' : ''}`, `
        <div class="pt-por" style="--c:${m.color}">${portraitInner(m.id, m.name)}</div>
        <div class="pt-info"><div class="pt-name">${m.name}<span class="lv">Lv${m.level}</span></div><div class="pt-sub">${sub}</div>
        <div class="pt-bar hp"><i style="width:${(m.hp / s.hp) * 100}%"></i></div><div class="pt-num">HP ${Math.ceil(m.hp)} / ${s.hp}</div>
        ${big ? `<div class="pt-bar xp"><i style="width:${(m.xp / xpToNext(m.level)) * 100}%"></i></div><div class="pt-num">EXP ${m.xp} / ${xpToNext(m.level)}</div>` : ''}</div>
        ${big ? `<div class="pt-stamp">${m.id === 'kai' ? '고정' : '참가'}</div>` : ''}`, big ? slots : reserve);
      c.addEventListener('mouseenter', () => show(m));
      c.addEventListener('padfocus', () => show(m));
      c.onclick = () => {
        if (m.id === 'kai') { Sfx.play('ui_error'); return; }
        if (on) st.active = st.active.filter((x) => x !== m.id);
        else if (st.active.length < 3) st.active.push(m.id);
        else { Sfx.play('ui_error'); this.game.ui.toast('참가 인원은 최대 3명입니다'); return; }
        Sfx.play('ui_ok');
        this.renderPause();
      };
      return c;
    };
    const active = st.active.map((id) => st.member(id));
    active.forEach((m) => card(m, true));
    for (let i = active.length; i < 3; i++) el('div', 'pt-card empty', '<span>빈 자리</span>', slots);
    const rest = st.roster.filter((m) => !st.active.includes(m.id));
    rest.forEach((m) => card(m, false));
    if (!rest.length) el('div', 'mn-note dim', '대기 중인 동료가 없습니다. 전투에서 몬스터와 대화해 영입해 보세요.', reserve);
    show(active[0] ?? st.roster[0]);
  }

  /** Bestiary: species list on the left, a large entry on the right. */
  private renderBestiary(body: HTMLElement) {
    const st = State.current;
    const list = el('div', 'bs-list', undefined, body);
    const detail = el('div', 'bs-detail', '', body);
    const all = Object.values(SPECIES);
    const show = (sp: (typeof all)[number], row: HTMLElement) => {
      list.querySelectorAll('.bs-row').forEach((r) => r.classList.toggle('sel', r === row));
      const b = st.bestiary[sp.id];
      if (!b.seen) { detail.innerHTML = '<div class="bs-unknown">???<div class="dim">아직 만나지 못했다</div></div>'; return; }
      const per = PERSONALITIES[sp.personality];
      // only affinities discovered in battle (bestiary.known) are listed
      const found = Object.entries(sp.affinity).filter(([k]) => b.known.includes(k as Element));
      const aff = found.map(([k, v]) => `<span class="${v! > 1 ? 'weak' : 'resist'}">${icon('el', k)}${ELEMENT_NAME[k as Element]} ${v! > 1 ? '약점' : '내성'}</span>`).join('')
        + (found.length < Object.keys(sp.affinity).length ? `<span class="unk">${found.length ? '그 외 ' : ''}???</span>` : '');
      detail.innerHTML = `<div class="bs-por" style="--c:${sp.color}">${portraitInner(sp.id, sp.name)}</div>
        <div class="bs-info"><div class="bs-name">${sp.name}<span class="lv">Lv${sp.level}</span></div>
        <div class="bs-tier">${{ weak: '약함 · 필드에서 처치 가능', strong: '강함 · 브레이크만 가능', elite: '정예' }[sp.tier]}</div>
        <div class="bs-stamp${b.recruited ? ' ok' : ''}">${b.recruited ? '영입' : '미영입'}</div>
        <p class="bs-desc">${sp.desc}</p>
        <div class="bs-row-k">성격</div><p><b>${per.name}</b> — ${per.desc}</p>
        <div class="bs-row-k">약점 · 내성</div><div class="bs-aff">${aff || '<span class="unk">없음</span>'}</div>
        ${b.recruited ? `<div class="bs-row-k">흡수</div><p>${b.absorbed}회</p>` : ''}</div>`;
    };
    let first: [typeof all[number], HTMLElement] | null = null;
    for (const sp of all) {
      const b = st.bestiary[sp.id];
      const row = el('div', `bs-row mn-focus${b.seen ? '' : ' unseen'}`, `<div class="bs-chip" style="--c:${sp.color}">${b.seen ? portraitInner(sp.id, sp.name) : ''}</div><span>${b.seen ? sp.name : '???'}</span>${b.recruited ? '<i>영입</i>' : ''}`, list);
      row.addEventListener('mouseenter', () => show(sp, row));
      row.addEventListener('padfocus', () => show(sp, row));
      row.onclick = () => show(sp, row);
      if (!first) first = [sp, row];
    }
    if (first) show(first[0], first[1]);
  }

  private renderItems(body: HTMLElement) {
    const list = el('div', 'it-list', undefined, body);
    const entries = Object.entries(State.current.inventory).filter(([, n]) => n > 0);
    for (const [id, n] of entries) {
      const d = ITEMS[id];
      el('div', 'it-row', `<span class="it-ico">${icon('item', id, d.icon)}</span><span class="it-name">${d.name}</span><span class="it-desc">${d.desc}</span><span class="it-n">×${n}</span>`, list);
    }
    if (!entries.length) el('div', 'mn-note', '가진 물건이 없습니다.', list);
  }

  /** Settings as console-style rows: ◀ value ▶, adjusted with ←/→ on a pad or the arrow buttons. */
  private renderSettings(body: HTMLElement) {
    const st = State.current;
    const sec = (t: string) => el('div', 'mn-sec', t, body);
    /** One row. `get` returns the value html, `step` changes it by ±1 (or toggles), `note` is an optional line below. */
    const row = (label: string, get: () => string, step: (dir: number) => void, note?: () => string) => {
      const r = el('div', 'st-row mn-focus', `<div class="st-label">${label}</div><div class="st-ctl"><button class="st-arrow" tabindex="-1">◀</button><div class="st-val"></div><button class="st-arrow" tabindex="-1">▶</button></div><div class="st-note"></div>`, body) as Adjustable;
      const val = r.querySelector('.st-val') as HTMLElement;
      const nt = r.querySelector('.st-note') as HTMLElement;
      const paint = () => { val.innerHTML = get(); nt.innerHTML = note ? note() : ''; nt.style.display = note ? '' : 'none'; };
      r.adjust = (dir) => { step(dir); Sfx.play('ui_move'); paint(); };
      const [prev, next] = r.querySelectorAll<HTMLElement>('.st-arrow');
      prev.onclick = (e) => { e.stopPropagation(); r.adjust!(-1); };
      next.onclick = (e) => { e.stopPropagation(); r.adjust!(1); };
      r.onclick = () => r.adjust!(1); // A / click on the row advances the value
      paint();
      return r;
    };
    const cycle = <T extends string>(keys: T[], cur: T, dir: number) => keys[(keys.indexOf(cur) + dir + keys.length) % keys.length];
    const toggle = (on: boolean) => `<span class="st-tg${on ? '' : ' sel'}">끄기</span><span class="st-tg${on ? ' sel' : ''}">켜기</span>`;
    const gauge = (v: number, min: number, max: number, text: string) => {
      const n = Math.round(((v - min) / (max - min)) * 10);
      return `<span class="st-gauge">${Array.from({ length: 10 }, (_, i) => `<i class="${i < n ? 'on' : ''}"></i>`).join('')}</span><b>${text}</b>`;
    };
    const num = (v: number, d: number, lo: number, hi: number, s: number) => Math.round(clamp(v + d * s, lo, hi) * 100) / 100;
    const diffs = Object.keys(DIFFICULTY) as Difficulty[];
    const quals = Object.keys(QUALITY) as Quality[];

    sec('게임');
    row('난이도', () => `<b>${DIFFICULTY[st.difficulty].name}</b>`, (d) => { st.difficulty = cycle(diffs, st.difficulty, d); },
      () => { const d = DIFFICULTY[st.difficulty]; return `${d.desc} · 패링 ±${Math.round(d.parry * 1000)}ms · 회피 ±${Math.round(d.dodge * 1000)}ms · 받는 피해 ×${d.enemyDmg}`; }).dataset.padFirst = '';
    row('패링 타이밍 링', () => toggle(st.showParryRing), () => { st.showParryRing = !st.showParryRing; }, () => '하드에서는 항상 숨김');
    sec('소리 · 조작');
    row('효과음 볼륨', () => gauge(Sfx.volume, 0, 1, `${Math.round(Sfx.volume * 100)}%`), (d) => Sfx.setVolume(num(Sfx.volume, d, 0, 1, 0.1)));
    row('마우스 감도', () => gauge(st.mouseSens, 0.3, 2.5, `×${st.mouseSens.toFixed(1)}`), (d) => { st.mouseSens = num(st.mouseSens, d, 0.3, 2.5, 0.1); });
    row('패드 시점 감도', () => gauge(st.padSens, 0.3, 2.5, `×${st.padSens.toFixed(1)}`), (d) => { st.padSens = num(st.padSens, d, 0.3, 2.5, 0.1); });
    row('패드 진동', () => toggle(Input.rumbleOn), () => { Input.rumbleOn = !Input.rumbleOn; Input.rumble(0.5, 0.5, 150); });
    sec('그래픽');
    row('품질', () => `<b>${QUALITY[Graphics.quality].name}</b>`, (d) => Graphics.set({ quality: cycle(quals, Graphics.quality, d) }), () => QUALITY[Graphics.quality].desc);
    row('자동 해상도', () => toggle(Graphics.autoRes), () => Graphics.set({ autoRes: !Graphics.autoRes }), () => '프레임이 떨어지면 렌더 해상도를 단계적으로 낮춥니다');
    const buf = this.game.renderer.getDrawingBufferSize(new THREE.Vector2());
    el('div', 'mn-note', `GPU: ${Graphics.gpu.replace(/[<>&]/g, '') || '알 수 없음'}${Graphics.integrated ? ' <span class="warn">(내장 그래픽)</span>' : ''} · 렌더 해상도 ${buf.x}×${buf.y}${Graphics.autoRes ? ` · 자동 단계 ${Math.round(Graphics.scale * 100)}%` : ''}`, body);
    sec('입력 장치 <span class="dim">(브라우저가 보는 게임패드 · 스틱을 움직이면 해당 축 숫자가 바뀝니다)</span>');
    this.diag = el('div', 'pad-diag', '', body);
    this.diagHtml = '';
    this.updateDiag();
  }

  private renderControls(body: HTMLElement) {
    // battle tips (battle/tips.ts) appear once each; this re-arms them for the next battle
    const seen = State.current.tipsSeen;
    const replay = el('div', 'mn-replay', '', body);
    const b = el('button', 'mn-btn small', '전투 안내 다시 보기', replay);
    el('span', 'dim', seen.size ? '다음 전투부터 각 안내가 처음 나올 때처럼 다시 뜹니다' : '다음 전투에서 안내가 다시 나옵니다', replay);
    b.disabled = !seen.size;
    b.onclick = () => { seen.clear(); Sfx.play('ui_ok'); this.renderPause(); };
    this.controls = el('div', 'controls-view', controlsPage(Input.state), body);
  }
}
