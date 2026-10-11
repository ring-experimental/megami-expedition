import * as THREE from 'three';
import { clamp, el, josa } from '../core/utils';
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
import { Save, MANUAL_SLOTS, SLOT_NAME, formatDate, formatPlayTime, partyLine, type SlotId } from '../game/save';
import { Graphics, QUALITY, type Quality } from '../game/graphics';
import type { Game } from '../game/game';
import { BATTLE_SPEEDS, DIFFICULTY, ELEMENT_NAME, type Difficulty, type Element } from '../data/types';
import { HEROES, SPECIES, xpToNext } from '../data/units';
import { SKILLS } from '../data/skills';
import { ITEMS } from '../data/items';
import { PERSONALITIES } from '../data/negotiation';
import { ARTS, BOARDS, CRYSTAL_NAME, EFFECT_DESC, PARTS, artsFor, lineTotals } from '../data/parts';
import { MAX_INHERITED, fusionRecipe } from '../data/fusion';

const STAT_KO: Record<string, string> = { hp: 'HP', atk: '공격', mag: '마력', def: '방어', res: '저항', spd: '속도' };
const costHtml = (c: Partial<Record<Element | 'any', number>>) => Object.entries(c).map(([e, n]) => (e === 'any' ? `아무 결정 ${n}` : `${icon('el', e, ELEMENT_NAME[e as Element])}${n}`)).join(' ');
const needHtml = (c: Partial<Record<Element, number>>) => Object.entries(c).map(([e, n]) => `${ELEMENT_NAME[e as Element]} ${n}`).join(' + ');

const ALL_TABS: [string, string][] = [['journal', '수첩'], ['party', '파티 편성'], ['board', '부품'], ['workshop', '공방'], ['bestiary', '몬스터 도감'], ['items', '소지품'], ['save', '저장 · 불러오기'], ['settings', '설정'], ['controls', '조작법']];
/** The 공방 tab appears once the party has reached the workshop (story flag). */
const pauseTabs = () => ALL_TABS.filter(([id]) => (id !== 'workshop' || State.current.flag('workshop')) && (id !== 'board' || State.current.flag('ch1_hub_arrived')));

export class Menus {
  private title: HTMLElement | null = null;
  private pause: HTMLElement | null = null;
  private tab = 'party';
  private nav = new PadNav();
  /**
   * Swapping a reserve member in while the party is full: 'ask' shows the confirm dialog, 'pick'
   * waits for the active member to replace. Back (Esc / B / Backspace) returns to before the click.
   */
  private partyPick: { id: string; step: 'ask' | 'pick' } | null = null;
  /** where pad/keyboard focus is confined during partyPick (the dialog, or the active slots) */
  private pickRoot: HTMLElement | null = null;
  private diag: HTMLElement | null = null;
  private diagHtml = '';
  /** the mounted controls page (title or pause tab), re-rendered whenever the input device changes */
  private controls: HTMLElement | null = null;

  constructor(private game: Game) {
    Input.subscribe((s) => {
      if (this.controls?.isConnected) this.controls.innerHTML = controlsPage(s);
    });
    // PadNav drives the menus from the keyboard: keep the browser from also clicking the button
    // that has DOM focus (Enter/Space) or moving its own focus ring around (Tab)
    window.addEventListener('keydown', (e) => {
      const open = this.pause || (this.title && !this.title.classList.contains('out'));
      if (open && ['Enter', 'NumpadEnter', 'Space', 'Tab'].includes(e.code)) e.preventDefault();
    }, true);
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
    // same brass gear art as the battle command ring; the SVG gears stay as the fallback
    const gear = artSrc('ui/gear_ring');
    t.innerHTML = `
      <div class="ts-gears"><div class="ts-gear big">${img(gear, gearSvg(16))}</div><div class="ts-gear small">${img(gear, gearSvg(11))}</div></div>
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
      const latest = Save.latest();
      if (latest) {
        const c = el('button', 'mn-btn big', '이어하기', menu);
        c.dataset.padFirst = '';
        c.onclick = () => { Sfx.unlock(); Sfx.play('ui_ok'); void this.game.loadSlot(latest); };
      }
      const b1 = el('button', `mn-btn${latest ? '' : ' big'}`, '새 게임', menu);
      if (!latest) b1.dataset.padFirst = '';
      if (latest) { const bl = el('button', 'mn-btn', '불러오기', menu); bl.onclick = () => { Sfx.unlock(); Sfx.play('ui_ok'); load(); }; }
      const b2 = el('button', 'mn-btn', '조작법', menu);
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
          this.hideTitle();
          this.game.newGame(k);
        };
      });
      back();
    };
    const load = () => {
      this.nav.reset();
      menu.className = 'ts-menu wide';
      menu.innerHTML = '<div class="ts-q"><span>불러오기</span><small>저장한 지점에서 이어서 시작합니다</small></div>';
      const box = el('div', 'sv-list ts-saves', undefined, menu);
      this.slotList(box, 'load', (slot) => { void this.game.loadSlot(slot); });
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

  /** Fade the title screen out (no-op if it is already gone or going). */
  hideTitle() {
    const t = this.title;
    if (!t || t.classList.contains('out')) return;
    t.classList.add('out');
    setTimeout(() => { t.remove(); if (this.title === t) this.title = null; }, 500);
  }

  /** Gamepad navigation for whichever DOM menu is open (called every frame by Game). */
  padUpdate() {
    if (this.pause && this.partyPick && this.pickRoot?.isConnected) {
      this.nav.update(this.pickRoot, () => this.cancelPick(), undefined, ['Backspace']);
    } else if (this.pause) {
      this.nav.update(this.pause, () => { Sfx.play('ui_back'); this.game.closePause(); }, (d) => this.cycleTab(d), ['Backspace']);
      this.updateDiag();
    } else if (this.title && !this.title.classList.contains('out')) {
      this.nav.update(this.title, () => (this.title?.querySelector('.back') as HTMLElement | null)?.click());
    }
  }

  /** Esc / Start in the pause menu: steps back out of a sub-state first. True if it did. */
  back() {
    if (!this.partyPick) return false;
    this.cancelPick();
    return true;
  }

  private cancelPick() {
    const id = this.partyPick?.id;
    this.partyPick = null;
    Sfx.play('ui_back');
    this.renderPause();
    // focus returns to the reserve card that started it
    const c = this.pause?.querySelector<HTMLElement>(`.pt-mini[data-id="${id}"]`);
    if (c) this.nav.focus(c);
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
    const i = pauseTabs().findIndex(([id]) => id === this.tab);
    this.tab = pauseTabs()[(i + dir + pauseTabs().length) % pauseTabs().length][0];
    Sfx.play('ui_move');
    this.renderPause();
    const tab = this.pause?.querySelectorAll<HTMLElement>('.mn-tab')[pauseTabs().findIndex(([id]) => id === this.tab)];
    if (tab) this.nav.focus(tab);
  }

  // -------------------------------------------------------------------------
  // Pause menu — full-screen, slanted tabs on the left (UI bible §9-7)
  // -------------------------------------------------------------------------
  showPause() {
    this.pause?.remove();
    this.partyPick = null;
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
        titleBtn.textContent = '한 번 더 누르면 타이틀로 (마지막 저장 이후 진행은 사라짐)';
        Sfx.play('ui_error');
        setTimeout(() => { titleBtn.classList.remove('armed'); titleBtn.textContent = '타이틀로'; }, 3000);
        return;
      }
      this.game.setMode('title'); // leaving the field also closes this menu
    };
    const tabs = p.querySelector('.mn-tabs') as HTMLElement;
    pauseTabs().forEach(([id, label], i) => {
      const b = el('button', 'mn-tab' + (id === this.tab ? ' on' : ''), `<span>${label}</span>`, tabs);
      b.style.setProperty('--i', String(i));
      b.onclick = () => { if (this.tab !== id && !this.partyPick) { Sfx.play('ui_move'); this.tab = id; this.renderPause(); } };
    });
    // tab-switch keys under the tabs, following the input device
    bindInput(el('div', 'mn-tabhint', '', tabs), (s) => (s.device === 'pad' ? `${pb('lb')}${pb('rb')}` : '<kbd>Q</kbd><kbd>E</kbd>') + '<span>탭 전환</span>');
    this.renderPause();
  }

  /** Open the pause menu on a given tab (e.g. 피페 → 공방). */
  openTab(id: string) {
    if (!this.pause || !pauseTabs().some(([t]) => t === id)) return;
    this.tab = id;
    this.renderPause();
  }

  hidePause() {
    this.partyPick = null;
    this.pause?.remove();
    this.pause = null;
  }

  private renderPause() {
    const p = this.pause;
    if (!p) return;
    const st = State.current;
    p.querySelector('.mn-modal')?.remove();
    (p.querySelector('.mn-money b') as HTMLElement).textContent = String(st.money);
    p.querySelectorAll('.mn-tab').forEach((b, i) => b.classList.toggle('on', pauseTabs()[i][0] === this.tab));
    const body = p.querySelector('.mn-body') as HTMLElement;
    body.innerHTML = '';
    body.className = `mn-body tab-${this.tab}`;
    if (this.tab === 'party') this.renderParty(body);
    else if (this.tab === 'bestiary') this.renderBestiary(body);
    else if (this.tab === 'items') this.renderItems(body);
    else if (this.tab === 'save') this.renderSave(body);
    else if (this.tab === 'board') this.renderBoard(body);
    else if (this.tab === 'journal') this.renderJournal(body);
    else if (this.tab === 'workshop') this.renderWorkshop(body);
    else if (this.tab === 'settings') this.renderSettings(body);
    else this.renderControls(body);
  }

  /** Party: three battle slots on top, the reserve below, details of the hovered/focused card. */
  private renderParty(body: HTMLElement) {
    const st = State.current;
    const pick = this.partyPick;
    const picking = pick?.step === 'pick';
    if (picking) {
      const name = st.member(pick.id).name;
      const bar = el('div', 'mn-note pt-pickbar', '', body);
      bindInput(bar, (s) => `<b>${josa(name, '과', '와')}</b> 교체할 참가 멤버를 고르세요 <button class="pt-cancel">${s.device === 'pad' ? pb('b') : '<kbd>Esc</kbd>'} 취소</button>`);
      bar.addEventListener('click', (e) => { if ((e.target as HTMLElement).closest('.pt-cancel')) this.cancelPick(); });
    } else {
      bindInput(el('div', 'mn-note', '', body), (s) => `전투 참가 최대 3명 (카이 고정). ${s.device === 'pad' ? `카드에서 ${pb('a')}` : '카드를 클릭해'} 참가 ↔ 대기를 바꿉니다. 참가 인원이 가득 차면 대기 멤버를 골라 교체합니다. 같은 종족을 다시 영입하면 그 동료에게 경험치로 흡수됩니다.`);
    }
    const slots = el('div', `pt-slots${picking ? ' picking' : ''}`, undefined, body);
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
      // while picking, only the swappable active cards stay focusable (.rc.locked is skipped by PadNav)
      const pickCls = !picking ? '' : !big ? (m.id === pick.id ? ' picked locked' : ' locked') : m.id === 'kai' ? ' locked' : ' swap-target';
      const c = el('div', `rc ${big ? 'pt-card' : 'pt-mini'}${on ? ' on' : ''}${m.id === 'kai' ? ' fixed' : ''}${pickCls}`, `
        <div class="pt-por" style="--c:${m.color}">${portraitInner(m.id, m.name)}</div>
        <div class="pt-info"><div class="pt-name">${m.name}<span class="lv">Lv${m.level}</span></div><div class="pt-sub">${sub}</div>
        <div class="pt-bar hp"><i style="width:${(m.hp / s.hp) * 100}%"></i></div><div class="pt-num">HP ${Math.ceil(m.hp)} / ${s.hp}</div>
        ${big ? `<div class="pt-bar xp"><i style="width:${(m.xp / xpToNext(m.level)) * 100}%"></i></div><div class="pt-num">EXP ${m.xp} / ${xpToNext(m.level)}</div>` : ''}</div>
        ${big ? `<div class="pt-stamp">${m.id === 'kai' ? '고정' : '참가'}</div>` : ''}`, big ? slots : reserve);
      c.addEventListener('mouseenter', () => show(m));
      c.addEventListener('padfocus', () => show(m));
      c.dataset.id = m.id;
      c.onclick = () => {
        if (picking) {
          // the swap: the reserve member takes this one's slot
          if (!big || m.id === 'kai') { Sfx.play('ui_error'); return; }
          st.active[st.active.indexOf(m.id)] = pick.id;
          this.partyPick = null;
          Sfx.play('ui_ok');
          this.renderPause();
          const nc = this.pause?.querySelector<HTMLElement>(`.pt-card[data-id="${pick.id}"]`);
          if (nc) this.nav.focus(nc);
          return;
        }
        if (m.id === 'kai') { Sfx.play('ui_error'); return; }
        if (on) st.active = st.active.filter((x) => x !== m.id);
        else if (st.active.length < 3) st.active.push(m.id);
        else { Sfx.play('ui_ok'); this.partyPick = { id: m.id, step: 'ask' }; this.renderPause(); return; }
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

    this.pickRoot = null;
    if (pick?.step === 'ask') this.pickRoot = this.swapDialog(st.member(pick.id).name);
    else if (picking) {
      this.pickRoot = slots;
      show(st.member(pick.id));
      const first = slots.querySelector<HTMLElement>('.swap-target');
      if (first) this.nav.focus(first);
    }
  }

  /** "Swap <name> in?" — one line + Yes / No, over the darkened party tab. */
  private swapDialog(name: string) {
    const d = el('div', 'mn-modal', `<div class="mm-box"><div class="mm-q"><b>${josa(name, '을', '를')}</b> 참가시킬까요?</div>
      <div class="mm-sub">참가 인원이 가득 찼습니다. 다음에 교체할 참가 멤버를 고릅니다.</div>
      <div class="mm-btns"><button class="mn-btn yes" data-pad-first>예</button><button class="mn-btn no">아니오</button></div></div>`, this.pause!);
    this.nav.reset();
    (d.querySelector('.yes') as HTMLElement).onclick = () => {
      Sfx.play('ui_ok');
      this.partyPick!.step = 'pick';
      this.renderPause();
    };
    (d.querySelector('.no') as HTMLElement).onclick = () => this.cancelPick();
    // a click on the dimmed backdrop also says no
    d.addEventListener('click', (e) => { if (e.target === d) this.cancelPick(); });
    return d.querySelector('.mm-box') as HTMLElement;
  }

  // -------------------------------------------------------------------------
  // 부품 board (data/parts.ts): slots joined by lines, arts from each line's element totals
  // -------------------------------------------------------------------------
  private boardHero: 'kai' | 'lyra' = 'kai';

  private renderBoard(body: HTMLElement) {
    const st = State.current;
    const hero = this.boardHero;
    const def = BOARDS[hero];
    const slots = st.boards[hero];
    const open = st.boardOpen[hero];
    const heads = el('div', 'bd-heads', undefined, body);
    (['kai', 'lyra'] as const).filter((h) => st.has(h)).forEach((h) => {
      const b = el('button', `mn-btn small bd-head${h === hero ? ' on' : ''}`, `${HEROES[h].name} · ${BOARDS[h].name}`, heads);
      if (h === hero) b.dataset.padFirst = '';
      b.onclick = () => { if (this.boardHero !== h) { this.boardHero = h; Sfx.play('ui_move'); this.renderPause(); } };
    });
    el('div', 'bd-crystals', (Object.keys(CRYSTAL_NAME) as Element[]).map((e) => `<span title="${CRYSTAL_NAME[e]}">${icon('el', e, ELEMENT_NAME[e])}<b>${st.crystals[e]}</b></span>`).join(''), heads);
    const wrap = el('div', 'bd-wrap', undefined, body);
    const panel = el('div', 'bd-panel', undefined, wrap);
    const lineSvg = def.lines.map((line, li) => `<polyline class="bd-line l${li}" points="${line.map((i) => def.pos[i].join(',')).join(' ')}"/>`).join('');
    el('div', 'bd-svg', `<svg viewBox="0 0 100 100" preserveAspectRatio="none">${lineSvg}</svg>`, panel);
    const info = el('div', 'bd-info', '', wrap);
    def.pos.forEach(([x, y], i) => {
      const id = slots[i];
      const locked = !open.includes(i);
      const p = id ? PARTS[id] : null;
      const pips = p ? Object.entries(p.elem).map(([e, v]) => `<i>${icon('el', e, ELEMENT_NAME[e as Element])}${v}</i>`).join('') : '';
      const b = el('button', `bd-slot${locked ? ' locked' : ''}${p ? ' full' : ''}`, locked
        ? `<span class="bd-lock">🔒</span><small>${costHtml(def.unlock[i] ?? {})}</small>`
        : p ? `<span class="bd-pn">${p.name}</span><span class="bd-pips">${pips}</span>` : '<span class="bd-empty">빈 슬롯</span>', panel);
      b.style.left = `${x}%`;
      b.style.top = `${y}%`;
      b.onclick = () => (locked ? this.unlockSlot(hero, i) : this.pickPart(hero, i));
    });
    // right: line totals, arts, effects
    const totals = lineTotals(def, slots);
    const arts = artsFor(hero, slots);
    const m = st.member(hero);
    const effects = [...st.partEffects(m)];
    info.innerHTML = `<div class="mn-sec">라인</div>${totals.map((t, li) => `<div class="bd-tot"><span class="bd-ln l${li}">라인 ${li + 1}</span>${(Object.entries(t) as [Element, number][]).map(([e, v]) => `${icon('el', e, ELEMENT_NAME[e])}<b>${v}</b>`).join(' ') || '<span class="dim">비어 있음</span>'}</div>`).join('')}
      <div class="mn-sec">아츠</div>${arts.length ? arts.map((a) => `<div class="bd-art">${icon('el', a.skill.element, '')}<b>${a.skill.name}</b> <span class="dim">${a.skill.ap} AP · ${a.skill.desc}</span></div>`).join('') : '<div class="mn-note">한 라인의 속성 합이 조건에 닿으면 아츠가 열립니다.</div>'}
      <div class="bd-next dim">${ARTS.filter((a) => a.who === hero && !arts.includes(a)).map((a) => `${a.skill.name} — ${needHtml(a.need)}`).join(' · ')}</div>
      ${effects.length ? `<div class="mn-sec">효과</div>${effects.map((e) => `<div class="bd-art">${EFFECT_DESC[e]}</div>`).join('')}` : ''}`;
  }

  private pickPart(hero: 'kai' | 'lyra', slot: number) {
    const st = State.current;
    const cur = st.boards[hero][slot];
    const owned = Object.keys(PARTS).filter((id) => (st.parts[id] ?? 0) > 0);
    const rows = owned.map((id) => {
      const p = PARTS[id];
      const free = st.partsFree(id);
      // a hero can't slot the same part twice
      const dup = id !== cur && st.boards[hero].includes(id);
      const ok = id === cur || (free > 0 && !dup);
      const stats = p.stats ? Object.entries(p.stats).map(([k, v]) => `${STAT_KO[k]} +${v}`).join(' ') : '';
      return `<button class="bd-pick${ok ? '' : ' off'}${id === cur ? ' cur' : ''}" data-id="${id}"><b>${p.name}</b><span class="bd-pips">${Object.entries(p.elem).map(([e, v]) => `<i>${icon('el', e, '')}${v}</i>`).join('')}</span>
        <span class="dim">${[stats, p.effect ? EFFECT_DESC[p.effect] : ''].filter(Boolean).join(' · ')}</span><span class="bd-n">${dup ? '장착 중' : `×${free}`}</span></button>`;
    }).join('');
    const d = el('div', 'mn-modal', `<div class="mm-box bd-modal"><div class="mm-q">${BOARDS[hero].name} · 슬롯 ${slot + 1}</div><div class="bd-picks">${rows || '<div class="mn-note">가진 부품이 없습니다.</div>'}</div>
      <div class="mm-btns">${cur ? '<button class="mn-btn clear">비우기</button>' : ''}<button class="mn-btn no">닫기</button></div></div>`, this.pause!);
    this.nav.reset();
    this.pickRoot = d.querySelector('.mm-box') as HTMLElement;
    this.partyPick = { id: '', step: 'ask' }; // reuse the modal focus confinement
    const close = () => { this.partyPick = null; this.pickRoot = null; this.renderPause(); };
    d.querySelectorAll<HTMLElement>('.bd-pick').forEach((b) => {
      b.onclick = () => {
        if (b.classList.contains('off')) { Sfx.play('ui_error'); return; }
        st.boards[hero][slot] = b.dataset.id === cur ? null : b.dataset.id!;
        Sfx.play('ui_ok');
        this.syncHp(hero);
        close();
      };
    });
    (d.querySelector('.clear') as HTMLElement | null)?.addEventListener('click', () => { st.boards[hero][slot] = null; Sfx.play('ui_back'); this.syncHp(hero); close(); });
    (d.querySelector('.no') as HTMLElement).onclick = () => { Sfx.play('ui_back'); close(); };
    d.addEventListener('click', (e) => { if (e.target === d) { Sfx.play('ui_back'); close(); } });
    const first = d.querySelector<HTMLElement>('.bd-pick:not(.off)') ?? d.querySelector<HTMLElement>('.mn-btn');
    if (first) this.nav.focus(first);
  }

  /** HP stays within the (possibly lower) max after a part with HP comes off. */
  private syncHp(hero: string) {
    const st = State.current;
    const m = st.member(hero);
    m.hp = Math.min(m.hp, st.stats(m).hp);
  }

  private unlockSlot(hero: 'kai' | 'lyra', slot: number) {
    const st = State.current;
    const cost = BOARDS[hero].unlock[slot] ?? {};
    if (!st.hasCrystals(cost)) { Sfx.play('ui_error'); this.game.ui.toast(`속성 결정이 부족합니다: ${costHtml(cost)}`, 'red'); return; }
    st.spendCrystals(cost);
    st.boardOpen[hero].push(slot);
    Sfx.play('chest');
    this.game.ui.toast(`${BOARDS[hero].name}의 슬롯 ${slot + 1}이(가) 열렸다`, 'gold');
    this.renderPause();
  }

  // -------------------------------------------------------------------------
  // 공방: part crafting, monster inheritance / fusion
  // -------------------------------------------------------------------------
  private forge: { base?: string; mat?: string } = {};

  private renderWorkshop(body: HTMLElement) {
    const st = State.current;
    el('div', 'mn-sec', '부품 제작', body);
    const list = el('div', 'ws-list', undefined, body);
    for (const p of Object.values(PARTS)) {
      if (!p.craft) continue;
      const can = st.hasCrystals(p.craft.crystals) && st.money >= p.craft.money;
      const r = el('button', `ws-row${can ? '' : ' off'}`, `<b>${p.name}</b><span class="bd-pips">${Object.entries(p.elem).map(([e, v]) => `<i>${icon('el', e, '')}${v}</i>`).join('')}</span>
        <span class="dim">${p.effect ? EFFECT_DESC[p.effect] : p.stats ? Object.entries(p.stats).map(([k, v]) => `${STAT_KO[k]} +${v}`).join(' ') : ''}</span>
        <span class="ws-cost">${costHtml(p.craft.crystals)} · ⚙${p.craft.money}</span><span class="bd-n">보유 ${st.parts[p.id] ?? 0}</span>`, list);
      r.onclick = () => {
        if (!can) { Sfx.play('ui_error'); return; }
        st.spendCrystals(p.craft!.crystals);
        st.money -= p.craft!.money;
        st.parts[p.id] = (st.parts[p.id] ?? 0) + 1;
        Sfx.play('chest');
        this.game.ui.toast(`${p.name} 제작 완료`, 'gold');
        this.renderPause();
      };
    }
    el('div', 'mn-sec', '기령 합주 · 계승', body);
    if (!st.flag('fusion')) { el('div', 'mn-note', '피페: "곡조가 조금 더 모이면 합주를 해 주마." <span class="dim">(이야기를 진행하면 열립니다)</span>', body); return; }
    const mons = st.roster.filter((m) => m.kind === 'monster');
    const f = this.forge;
    bindInput(el('div', 'mn-note', '', body), () => !f.base ? '남길 동료(바탕)를 고르세요. 재료가 된 동료는 파티를 떠납니다.'
      : !f.mat ? `<b>${st.member(f.base).name}</b>에게 합칠 재료를 고르세요.` : '물려받을 스킬을 고르세요.');
    const row = el('div', 'ws-mons', undefined, body);
    if (mons.length < 2) el('div', 'mn-note dim', '영입한 몬스터가 둘 이상 있어야 합니다.', row);
    for (const m of mons) {
      const sel = f.base === m.id || f.mat === m.id;
      const bond = st.bond[m.id] ?? 1;
      const c = el('button', `ws-mon${sel ? ' sel' : ''}${m.locked ? ' off' : ''}`, `<div class="bs-chip" style="--c:${m.color}">${portraitInner(m.id, m.name)}</div><span>${m.name}<span class="lv">Lv${m.level}</span><small class="ws-bond">${'♥'.repeat(bond)}${'♡'.repeat(3 - bond)}</small></span>`, row);
      c.onclick = () => {
        if (m.locked) { Sfx.play('ui_error'); this.game.ui.toast(`피페: "${m.name}은(는) 이야기 한가운데 있는 곡조라 안 건드린단다."`); return; }
        if (bond < 1) { Sfx.play('ui_error'); this.game.ui.toast(`${m.name}이(가) 내키지 않아 한다. (친밀도 0 — 캠프에서 이야기해 보자)`); return; }
        if (f.base === m.id) { this.forge = {}; Sfx.play('ui_back'); }
        else if (!f.base) { f.base = m.id; Sfx.play('ui_ok'); }
        else if (!f.mat) { f.mat = m.id; Sfx.play('ui_ok'); }
        this.renderPause();
      };
    }
    if (f.base && f.mat) {
      const rec = fusionRecipe(f.base, f.mat);
      const base = st.member(f.base), mat = st.member(f.mat);
      const box = el('div', 'ws-result', '', body);
      if (rec && rec.when && !rec.when()) {
        box.innerHTML = `<div class="ws-q">피페: "이 둘은… 아직 곡조가 맞지 않는구나." <span class="dim">(조건: ${rec.whenText})</span></div>`;
      } else if (rec) {
        const sp = SPECIES[rec.result];
        box.innerHTML = `<div class="ws-q"><b>${base.name}</b> + <b>${mat.name}</b> → <b class="kw">${sp.name}</b> <span class="dim">— 피페: "${rec.line}"</span></div>`;
        const b = el('button', 'mn-btn', '합주한다', box);
        b.dataset.padFirst = '';
        b.onclick = () => { const r = st.fuse(base.id, mat.id, rec.result); this.forge = {}; Sfx.play('recruit'); this.game.ui.toast(`<b>${r.name}</b>이(가) 태어났다! Lv${r.level}`, 'gold', 3500); this.game.story.onFusion(rec.result); this.renderPause(); };
      } else {
        const skills = st.skillsOf(mat).filter((id) => !st.skillsOf(base).includes(id));
        box.innerHTML = `<div class="ws-q"><b>${mat.name}</b>의 스킬 하나를 <b>${base.name}</b>에게 <span class="dim">(계승 ${(base.inherited ?? []).length}/${MAX_INHERITED} · 넘치면 가장 오래된 것을 잊음)</span></div>`;
        for (const id of skills) {
          const b = el('button', 'mn-btn small', `${icon('el', SKILLS[id].element, '')}${SKILLS[id].name}`, box);
          b.onclick = () => { st.inherit(base.id, mat.id, id); this.forge = {}; Sfx.play('recruit'); this.game.ui.toast(`${base.name}이(가) <b>${SKILLS[id].name}</b>을(를) 물려받았다`, 'gold', 3000); this.renderPause(); };
        }
        if (!skills.length) el('div', 'mn-note', '물려줄 수 있는 새 스킬이 없습니다.', box);
      }
      const cancel = el('button', 'mn-btn small back', '다시 고르기', box);
      cancel.onclick = () => { this.forge = {}; Sfx.play('ui_back'); this.renderPause(); };
    }
  }

  /** 수첩: the current objective, the sub-quests and the party's bonds. */
  private renderJournal(body: HTMLElement) {
    const st = State.current;
    const story = this.game.story;
    el('div', 'mn-sec', '지금 할 일', body);
    el('div', 'jr-goal', `<b>${story.ch.goal()}</b><span class="dim">${st.chapterTitle()} 「노래하는 정오」 · 플레이 ${Math.floor(st.playTime / 60)}분</span>`, body);
    el('div', 'mn-sec', '의뢰', body);
    const qs = story.ch.quests().filter((q) => q.state !== 'locked');
    const list = el('div', 'jr-list', undefined, body);
    for (const q of qs) {
      el('div', `jr-q ${q.state}`, `<div class="jr-t"><span class="jr-st">${{ open: '미수락', active: '진행 중', done: '완료' }[q.state as 'open']}</span>${q.title}<span class="dim"> — ${q.giver}</span></div>
        <div class="jr-s">${q.state === 'done' ? '완료했다.' : q.step}</div><div class="jr-r dim">보수: ${q.reward}</div>`, list);
    }
    if (!qs.length) el('div', 'mn-note', '아직 받은 의뢰가 없습니다. 쉼표 역의 못판을 확인하세요.', list);
    const mates = st.roster.filter((m) => m.id !== 'kai');
    if (mates.length) {
      el('div', 'mn-sec', '친밀도', body);
      el('div', 'jr-bonds', mates.map((m) => { const b = st.bond[m.id] ?? 1; return `<span><b>${m.name}</b> ${'♥'.repeat(b)}${'♡'.repeat(3 - b)}</span>`; }).join(''), body);
    }
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

  /**
   * Save slot cards. 'save' mode shows the quicksave + three manual slots (the autosave is read-only),
   * 'load' mode shows every slot that has data. A filled slot asks once more before it is overwritten.
   */
  private slotList(box: HTMLElement, mode: 'save' | 'load', pick: (slot: SlotId) => void) {
    const slots: SlotId[] = mode === 'save' ? ['quick', ...MANUAL_SLOTS] : ['auto', 'quick', ...MANUAL_SLOTS];
    let first = true;
    for (const slot of slots) {
      const h = Save.header(slot);
      if (mode === 'load' && !h) continue;
      const card = el('button', `sv-slot${h ? '' : ' empty'}`, h
        ? `<div class="sv-name">${SLOT_NAME[slot]}</div><div class="sv-place">${h.chapter} · ${h.place}</div>
           <div class="sv-party">${partyLine(h)}</div>
           <div class="sv-meta"><span>⚙ ${h.money}</span><span>플레이 ${formatPlayTime(h.playTime)}</span><span>${formatDate(h.savedAt)}</span></div>`
        : `<div class="sv-name">${SLOT_NAME[slot]}</div><div class="sv-place dim">비어 있음</div>`, box);
      if (first) { card.dataset.padFirst = ''; first = false; }
      card.onclick = () => {
        if (mode === 'save' && h && !card.classList.contains('armed')) {
          card.classList.add('armed');
          card.querySelector('.sv-name')!.innerHTML = `${SLOT_NAME[slot]} <span class="sv-warn">한 번 더 누르면 덮어씁니다</span>`;
          Sfx.play('ui_error');
          setTimeout(() => { if (card.isConnected) { card.classList.remove('armed'); card.querySelector('.sv-name')!.textContent = SLOT_NAME[slot]; } }, 3000);
          return;
        }
        Sfx.play('ui_ok');
        pick(slot);
      };
    }
    if (mode === 'load' && first) el('div', 'mn-note', '저장된 데이터가 없습니다.', box);
  }

  private renderSave(body: HTMLElement) {
    bindInput(el('div', 'mn-note', '', body), (s) => `필드에서는 언제든 저장할 수 있습니다. 휴식 · 전투 승리 · 지역 이동 때 <b>자동 저장</b>됩니다.${s.device === 'pad' ? '' : ' 필드에서 <kbd>F5</kbd> 퀵세이브 · <kbd>F9</kbd> 퀵로드.'}`);
    el('div', 'mn-sec', '저장', body);
    const save = el('div', 'sv-list', undefined, body);
    this.slotList(save, 'save', (slot) => { if (this.game.saveTo(slot)) this.renderPause(); });
    el('div', 'mn-sec', '불러오기', body);
    const load = el('div', 'sv-list', undefined, body);
    this.slotList(load, 'load', (slot) => { void this.game.loadSlot(slot); });
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
    row('전투 배속', () => `<b>×${st.battleSpeed}</b>`, (d) => { st.battleSpeed = BATTLE_SPEEDS[(BATTLE_SPEEDS.indexOf(st.battleSpeed) + d + BATTLE_SPEEDS.length) % BATTLE_SPEEDS.length]; },
      () => '연출만 빨라집니다. 패링 · 회피 · QTE 판정은 항상 ×1 (전투 중 Tab / View 버튼으로도 전환)');
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
