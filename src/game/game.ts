import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import { Input } from '../core/input';
import { Sfx } from '../core/audio';
import { getModel, loadModels, missingModels, MODEL_NAMES } from '../core/assets';
import { patchObject, uploadFakeLights } from '../fx/fakeLights';
import { Graphics, QUALITY } from './graphics';
import { UI } from '../ui/ui';
import { Menus } from '../ui/menus';
import { padName } from '../ui/glyph';
import { FieldMode } from '../field/field';
import { BattleMode, type BattleRequest } from '../battle/battle';
import { GameState, State } from './state';
import type { Difficulty } from '../data/types';

type Mode = 'loading' | 'title' | 'field' | 'battle' | 'transition';

export class Game {
  renderer: THREE.WebGLRenderer;
  composer: EffectComposer;
  renderPass: RenderPass;
  bloom: UnrealBloomPass;
  ui: UI;
  menus!: Menus;
  field!: FieldMode;
  battle!: BattleMode;
  mode: Mode = 'loading';
  paused = false;
  private clock = new THREE.Clock();
  private pauseOpenedAt = 0;
  private titleT = 0;
  /** Paused frames don't change: render one, then let the GPU idle (and the menu stay smooth). */
  private pauseRendered = false;
  private msaa = -1;

  constructor(canvas: HTMLCanvasElement, uiRoot: HTMLElement) {
    // no canvas MSAA: the scene is drawn into the composer's target, the canvas only gets the final
    // full-screen quad (antialiasing, when enabled, is MSAA on that target — see applyQuality)
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: 'high-performance' });
    Graphics.init(this.renderer.getContext());
    Graphics.onChange = () => this.applyQuality();
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.composer = new EffectComposer(this.renderer);
    this.renderPass = new RenderPass(new THREE.Scene(), new THREE.PerspectiveCamera());
    this.bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.32, 0.35, 1.05);
    this.composer.addPass(this.renderPass);
    this.composer.addPass(this.bloom);
    this.composer.addPass(new OutputPass());
    this.ui = new UI(uiRoot);
    Input.init(canvas);
    window.addEventListener('resize', () => this.resize());
    canvas.addEventListener('click', () => {
      Sfx.unlock();
      if (this.mode === 'field' && !this.paused && this.field.controlsEnabled) Input.requestLock();
    });
    window.addEventListener('keydown', () => Sfx.unlock(), { once: true });
    let announced = '';
    Input.subscribe((s) => {
      // pad button labels (A / ✕ / B…) and the menu focus ring are styled from these
      document.body.classList.toggle('pad', s.device === 'pad');
      document.body.dataset.pad = s.padStyle;
      if (s.device !== 'pad' || !s.pad) return;
      Sfx.unlock();
      if (announced === s.pad.index + s.pad.id) return;
      announced = s.pad.index + s.pad.id;
      if (s.pad.mapping === 'standard') this.ui.toast(`🎮 게임패드 연결: ${padName(s.pad)}`, 'cyan');
      else this.ui.toast(`🎮 ${padName(s.pad)} — 브라우저가 표준 배치로 인식하지 못한 패드라 일부 버튼·오른쪽 스틱이 다르게 동작할 수 있습니다. <span class="dim">메뉴 → 설정 → 입력 장치에서 확인</span>`, 'red', 7000);
    });
    Input.onLockChange = (locked) => {
      // Esc while pointer-locked releases the lock without a keydown → open the pause menu
      if (!locked && this.mode === 'field' && !this.paused && this.field.controlsEnabled) this.openPause();
    };
  }

  async init() {
    const loading = this.ui.root.appendChild(document.createElement('div'));
    loading.className = 'loading';
    loading.innerHTML = `<div class="ld-title">MEGAMI EXPEDITION</div><div class="ld-bar"><div class="ld-fill"></div></div><div class="ld-text">에테르 압력 충전 중...</div>`;
    const fill = loading.querySelector('.ld-fill') as HTMLElement;
    await loadModels((d, t) => (fill.style.width = `${(d / t) * 100}%`));
    const missing = missingModels();
    await new Promise((r) => setTimeout(r, 50));
    this.field = new FieldMode(this);
    this.battle = new BattleMode(this);
    this.menus = new Menus(this);
    this.applyQuality();
    (loading.querySelector('.ld-text') as HTMLElement).textContent = '셰이더 준비 중...';
    await this.warmUp();
    loading.classList.add('out');
    setTimeout(() => loading.remove(), 600);
    if (missing.length) this.ui.toast(`누락된 모델(임시 도형 사용): ${missing.join(', ')}`, 'red', 6000);
    if (Graphics.integrated) {
      this.ui.toast(`⚠ 브라우저가 CPU 내장 그래픽(<b>${Graphics.gpu.replace(/^ANGLE \(|\)$/g, '')}</b>)으로 실행 중입니다. 외장 그래픽카드가 있다면 Windows 설정 → 시스템 → 디스플레이 → 그래픽에서 브라우저를 <b>고성능</b>으로 지정하거나 모니터를 그래픽카드에 연결하세요. <span class="dim">(그래픽 품질을 '낮음'으로 시작합니다 · 메뉴 → 설정)</span>`, 'red', 12000);
    }
    this.showTitle();
    this.clock.getDelta();
    this.renderer.setAnimationLoop(() => this.frame());
  }

  /**
   * Compile every shader the game will need behind the loading screen, including the shadow-depth
   * variants (`compile()` skips those) and the battle versions of all unit models (the battle scene
   * has different lights, so field programs don't cover it). Without this the first battle / first
   * effect of each kind froze the game while ANGLE compiled programs.
   */
  private async warmUp() {
    const r = this.renderer;
    const b = this.battle;
    const tmp: [THREE.Scene, THREE.Object3D][] = [];
    // every unit model in the battle scene (its lights differ from the field's → separate programs)
    MODEL_NAMES.filter((n) => n !== 'props' && n !== 'arena').forEach((n, i) => {
      const m = getModel(n);
      m.position.set((i - 4) * 2.2, 0, 0); // inside the battle key light's shadow frustum
      b.scene.add(m);
      tmp.push([b.scene, m]);
    });
    const proj = this.field.warmObject();
    this.field.scene.add(proj);
    tmp.push([this.field.scene, proj]);
    // one of every one-shot effect, in both scenes
    const teles = [b, this.field].map(({ fx, scene }) => {
      const p = new THREE.Vector3(0, 1, 0);
      fx.ring(p, 0xffffff); fx.slash(p, 0, 0xffffff); fx.flash(p, 0xffffff); fx.pillar(p, 0xffffff);
      fx.shards(p); fx.bolt(p); void fx.projectile(p, p.clone().setX(2), 0xffffff);
      fx.sparks.emit(p); fx.smoke.emit(p);
      fx.update(0.01); // effects set their real scale/opacity on the first update
      const t = fx.telegraph(scene, 4, 1);
      t.set(0.5);
      return t;
    });
    const scenes = [[this.field.scene, this.field.camera, this.field.fx.lights], [b.scene, b.camera, b.fx.lights]] as const;
    // draw everything regardless of the camera: anything culled here would compile mid-game instead
    const culled: THREE.Object3D[] = [];
    for (const [scene] of scenes) {
      patchObject(scene);
      scene.traverse((o) => { if (o.frustumCulled) { o.frustumCulled = false; culled.push(o); } });
    }
    try {
      // compile for the composer's target (tone mapping happens in OutputPass, so the scene programs
      // differ from what a plain compile-to-canvas would build)
      r.setRenderTarget(this.composer.renderTarget1);
      await Promise.all(scenes.map(([scene, camera]) => r.compileAsync(scene, camera)));
    } catch {
      /* compileAsync unsupported → the renders below still compile synchronously */
    } finally {
      r.setRenderTarget(null);
    }
    // real frames: shadow-depth programs (incl. skinned) are only built while rendering shadows
    for (const [scene, camera, lights] of scenes) {
      r.shadowMap.needsUpdate = true;
      uploadFakeLights(lights, camera);
      this.renderPass.scene = scene;
      this.renderPass.camera = camera;
      this.composer.render(0);
    }
    for (const o of culled) o.frustumCulled = true;
    for (const [scene, o] of tmp) scene.remove(o);
    for (const t of teles) t.remove();
    b.fx.clear();
    this.field.fx.clear();
  }

  /** Apply the graphics preset + dynamic-resolution step (pixel budget, shadows, bloom, MSAA). */
  applyQuality() {
    const q = QUALITY[Graphics.quality];
    if (q.msaa !== this.msaa) {
      this.msaa = q.msaa;
      // three only takes the sample count at creation → rebuild the composer's targets
      const size = this.renderer.getSize(new THREE.Vector2());
      const rt = new THREE.WebGLRenderTarget(Math.max(1, size.x), Math.max(1, size.y), { type: THREE.HalfFloatType, samples: q.msaa });
      this.composer.reset(rt);
    }
    this.bloom.enabled = q.bloom;
    for (const scene of [this.field?.scene, this.battle?.scene]) {
      scene?.traverse((o) => {
        const l = o as THREE.DirectionalLight;
        if (!l.isDirectionalLight || !l.castShadow || l.shadow.mapSize.x === q.shadowSize) return;
        l.shadow.mapSize.set(q.shadowSize, q.shadowSize);
        l.shadow.map?.dispose();
        l.shadow.map = null; // recreated at the new size on the next shadow render
      });
    }
    this.resize();
  }

  /** Drawing-buffer pixel ratio: device ratio, capped by the preset's megapixel budget, times the dynamic step. */
  private pixelRatio(w: number, h: number) {
    let pr = Math.min(window.devicePixelRatio || 1, 2);
    const budget = QUALITY[Graphics.quality].maxMP * 1e6;
    if (w * h * pr * pr > budget) pr = Math.sqrt(budget / (w * h));
    return pr * Graphics.scale;
  }

  resize() {
    const w = window.innerWidth, h = window.innerHeight;
    if (w < 2 || h < 2) return;
    const pr = this.pixelRatio(w, h);
    this.renderer.setPixelRatio(pr);
    this.renderer.setSize(w, h);
    this.composer.setPixelRatio(pr);
    this.composer.setSize(w, h);
    this.pauseRendered = false;
    this.ui.resize(w, h);
    this.field?.resize(w, h);
    this.battle?.resize(w, h);
  }

  showTitle() {
    this.mode = 'title';
    this.field.hud.setVisible(false);
    this.menus.showTitle();
  }

  newGame(diff: Difficulty) {
    State.current = new GameState();
    State.current.difficulty = diff;
    this.field.resetEnemies();
    this.field.respawnPlayer();
    this.ui.fadeOut(300).then(() => {
      this.mode = 'field';
      this.field.enter();
      this.ui.fadeIn(600);
      this.ui.banner('에테르 평원', '멈춘 시계탑을 향해', 'zone', 2200);
    });
  }

  async startBattle(req: BattleRequest) {
    if (this.mode !== 'field') return;
    this.mode = 'transition';
    Input.exitLock();
    this.field.exit();
    Sfx.play('battle_start');
    Input.rumble(0.6, 0.6, 250);
    this.ui.flash(req.advantage === 'enemy' ? '#ff5040' : req.advantage === 'party' ? '#ffe9a0' : '#ffffff', 220);
    await this.ui.battleWipe(req.advantage === 'party' ? 'advantage' : req.advantage === 'enemy' ? 'ambush' : 'neutral');
    this.mode = 'battle';
    let result = await this.battle.start(req);
    while (result === 'retry') {
      // restore pre-battle HP (simple: full heal of active members to keep testing quick)
      for (const m of State.current.activeMembers()) m.hp = Math.max(m.hp, State.current.stats(m).hp);
      await this.ui.fadeOut(300);
      this.ui.fadeIn(300);
      result = await this.battle.start(req);
    }
    await this.ui.fadeOut(350);
    this.mode = 'field';
    this.ui.camera = this.field.camera;
    if (result === 'defeat') {
      State.current.healAll();
      this.field.respawnPlayer();
      this.ui.toast('에테르 샘에서 정신을 차렸다...', 'cyan');
    } else {
      this.field.afterBattle(result === 'victory' ? 'victory' : 'fled', req.source);
    }
    this.field.enter();
    this.ui.fadeIn(400);
  }

  openPause() {
    if (this.paused || this.mode !== 'field') return;
    this.paused = true;
    this.pauseRendered = false;
    this.pauseOpenedAt = performance.now();
    Input.exitLock();
    this.menus.showPause();
  }

  closePause() {
    this.paused = false;
    this.menus.hidePause();
    // the button that closed the menu (A/B on a pad) must not also attack/dodge this frame
    Input.consumePressed();
    Input.requestLock();
  }

  private frame() {
    const real = this.clock.getDelta();
    // dynamic resolution: only from real gameplay frames (menus/pauses idle the GPU)
    if ((this.mode === 'field' || this.mode === 'battle') && !this.paused && Graphics.sample(real)) this.resize();
    this.tick(Math.min(real, 1 / 20), true);
  }

  /**
   * Debug helper: advance the simulation with a fixed timestep even when the page is hidden
   * (rAF paused). Yields a macrotask between frames so async battle choreography can progress.
   */
  async debugAdvance(sec: number, render = true) {
    const steps = Math.max(1, Math.round(sec * 60));
    for (let i = 0; i < steps; i++) {
      this.tick(1 / 60, render && i === steps - 1);
      await yieldTask();
    }
    this.clock.getDelta();
  }

  private tick(dt: number, render: boolean) {
    Input.pollGamepads();
    if (this.mode === 'field' && !this.paused && Input.pressed('Escape', 'PadStart') && this.field.controlsEnabled) this.openPause();
    else if (this.paused && Input.pressed('Escape', 'PadStart') && performance.now() - this.pauseOpenedAt > 350) this.closePause();
    else if (this.mode === 'title' || this.paused) this.menus.padUpdate();

    let scene: THREE.Scene, camera: THREE.Camera;
    if (this.mode === 'battle') {
      this.battle.update(dt);
      scene = this.battle.scene;
      camera = this.battle.camera;
    } else {
      if (this.mode === 'title') {
        this.titleT += dt;
        this.field.update(dt);
        const a = this.titleT * 0.06;
        this.field.camera.position.set(Math.sin(a) * 24, 9 + Math.sin(this.titleT * 0.2) * 1.5, -30 + Math.cos(a) * 24);
        this.field.camera.lookAt(0, 7, -46);
      } else if (!this.paused) {
        this.field.update(dt);
      }
      scene = this.field.scene;
      camera = this.field.camera;
    }
    this.ui.update(dt);
    if (render && !(this.paused && this.pauseRendered)) {
      uploadFakeLights(this.mode === 'battle' ? this.battle.fx.lights : this.field.fx.lights, camera);
      this.renderPass.scene = scene;
      this.renderPass.camera = camera;
      this.composer.render(dt);
      if (this.paused) this.pauseRendered = true;
    }
    Input.endFrame();
  }
}

const _chan = new MessageChannel();
const _queue: (() => void)[] = [];
_chan.port1.onmessage = () => _queue.shift()?.();
function yieldTask() {
  return new Promise<void>((r) => { _queue.push(r); _chan.port2.postMessage(0); });
}
