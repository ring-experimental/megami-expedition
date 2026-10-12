/**
 * Dev-only console helpers (loaded only by `npm run dev`).
 * Lets the game be driven deterministically even when the tab is hidden (rAF paused):
 *   await dbg.battle('s_rat2', 'none'); await dbg.auto({ parry: true });
 */
import * as THREE from 'three';
import type { Game } from './game/game';
import { State } from './game/state';
import { heightAt } from './field/terrain';

export function installDebug(game: Game) {
  const step = (s: number, render = false) => game.debugAdvance(s, render);
  const key = (code: string, type: 'keydown' | 'keyup') => window.dispatchEvent(new KeyboardEvent(type, { code }));
  const tap = async (code: string, after = 0.1) => {
    key(code, 'keydown');
    await step(0.034);
    key(code, 'keyup');
    await step(after);
  };
  const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

  const dbg = {
    game,
    get state() { return State.current; },
    step,
    tap,
    /** Save a PNG data URL to tools/blender/previews/game_<name>.png (dev server only). */
    async saveSnap(name: string, dataUrl: string) {
      const r = await fetch(`/__snap?name=${encodeURIComponent(name)}`, { method: 'POST', body: dataUrl });
      return r.text();
    },
    async newGame(diff: 'story' | 'normal' | 'hard' = 'normal') {
      game.menus.hideTitle();
      game.newGame(diff);
      await sleep(1200);
    },
    async battle(spawnId: string, adv: 'party' | 'enemy' | 'none' = 'none') {
      if (game.mode !== 'field') await dbg.newGame();
      const f = game.field;
      const e = f.enemies.find((x) => x.spawn.id === spawnId)!;
      f.player.pos.set(e.pos.x, 0, e.pos.z + 2.5);
      f.startBattle(e, adv);
      await sleep(1200);
      await step(2);
    },
    /**
     * E2E check for the field objective markers: where each on-screen marker's diamond is drawn vs
     * where the target projects through the field camera onto the canvas (CSS px). Run at several
     * viewport sizes / aspect ratios; `err` should stay under 1 px, and edge markers `inside` the canvas.
     */
    beaconCheck() {
      const f = game.field;
      const canvas = (game as unknown as { renderer: { domElement: HTMLCanvasElement } }).renderer.domElement.getBoundingClientRect();
      const hud = f.hud as unknown as { goalPos: { x: number; z: number; zone: string } | null; questPos: { x: number; z: number; zone: string } | null; markerAt(p: unknown): { x: number; z: number } | null };
      return [...document.querySelectorAll<HTMLElement>('.fh-beacon')].map((b, i) => {
        const m = hud.markerAt(i === 0 ? hud.goalPos : hud.questPos);
        if (!m || b.style.display === 'none') return { i, shown: false };
        // measure with the bob animation paused so only placement error remains
        const gemEl = b.querySelector('.fb-gem') as HTMLElement;
        gemEl.style.animation = 'none';
        const gem = gemEl.getBoundingClientRect();
        gemEl.style.animation = '';
        const got = { x: gem.left + gem.width / 2, y: gem.top + gem.height / 2 };
        if (b.classList.contains('edge')) {
          const inside = got.x >= canvas.left && got.x <= canvas.right && got.y >= canvas.top && got.y <= canvas.bottom;
          return { i, shown: true, edge: true, inside, got };
        }
        const v = new THREE.Vector3(m.x, heightAt(m.x, m.z) + 2.4, m.z).project(f.camera);
        const want = { x: canvas.left + (v.x * 0.5 + 0.5) * canvas.width, y: canvas.top + (-v.y * 0.5 + 0.5) * canvas.height };
        return { i, shown: true, edge: false, err: Math.round(Math.hypot(got.x - want.x, got.y - want.y) * 10) / 10, got, want };
      });
    },

    /** Drive the battle: party uses basic attacks, perfect parries (or none). */
    async auto(opts: { parry?: boolean; dodge?: boolean; maxSteps?: number; stopOnEnemyTurn?: boolean } = {}) {
      const b = game.battle;
      const log: string[] = [];
      for (let i = 0; i < (opts.maxSteps ?? 80) && b.active; i++) {
        const bui = b.bui as unknown as { menu: { items: { label: string }[] } | null; dialogWait: unknown };
        if (bui.menu) {
          if (!bui.menu.items[0].label.endsWith('공격')) { await tap('Escape'); continue; }
          log.push('party:' + b['current' as keyof typeof b]?.toString());
          await tap('Digit1', 0.15);
          await tap('Enter', 0.05);
          continue;
        }
        const def = (b as unknown as { sessions: { hits?: { t: number }[]; results?: string[] }[] }).sessions.find((s) => s.hits);
        if (def && def.hits) {
          for (const h of def.hits) {
            while (b.tl.time < h.t - 0.03) await step(1 / 60);
            if (opts.parry) { key('KeyF', 'keydown'); key('KeyF', 'keyup'); }
            else if (opts.dodge) { key('Space', 'keydown'); key('Space', 'keyup'); }
            await step(1 / 60);
          }
          await step(0.3);
          log.push('enemy:' + def.results!.join(','));
          if (opts.stopOnEnemyTurn) break;
          continue;
        }
        if (bui.dialogWait) { await tap('Enter', 0.3); continue; }
        await step(0.1);
      }
      await step(0.05, true);
      return log;
    },

    /**
     * Pose-check sheet: isolates `unit` in the battle arena, holds each pose (clip-style degrees,
     * model axes) and renders every camera view at `tile`² px into one PNG saved as
     * tools/blender/previews/game_<name>.png. `follow: false` disables cloth thigh-following
     * (to compare with the old behaviour).
     *   await dbg.poseSheet('knight', b => b.enemies[0], [{label:'50°', pose:{leg_R:[-50,0,0]}}],
     *                       [[[0,1,4],[0,0.8,1.5]]])
     */
    async poseSheet(
      name: string,
      pickUnit: (b: Game['battle']) => { obj: THREE.Object3D; anim: unknown; pos: THREE.Vector3 },
      items: { label: string; pose: Record<string, [number, number, number]>; follow?: boolean; color?: string }[],
      views: [[number, number, number], [number, number, number]][],
      tile = 520,
    ) {
      const b = game.battle;
      const unit = pickUnit(b);
      const anim = unit.anim as { clips: Record<string, unknown>; play(n: string): void; thighFollow?: unknown };
      for (const u of b.units) u.obj.visible = u.obj === unit.obj;
      unit.pos.set(0, 0, 1.5);
      unit.obj.rotation.y = Math.PI / 2;
      const ui = document.getElementById('ui')!;
      ui.style.visibility = 'hidden';
      const grid = document.createElement('canvas');
      grid.width = tile * items.length;
      grid.height = tile * views.length;
      const g = grid.getContext('2d')!;
      const r = game.renderer, cam = b.camera;
      for (let i = 0; i < items.length; i++) {
        const it = items[i];
        if (it.follow === false) anim.thighFollow = () => 0;
        else delete anim.thighFollow;
        anim.clips.__pose = { dur: 0.05, hold: true, keys: [{ t: 0, pose: it.pose }, { t: 0.05, pose: it.pose }] };
        anim.play('__pose');
        await step(0.35);
        for (let j = 0; j < views.length; j++) {
          const [cp, lk] = views[j];
          r.setSize(tile, tile, false);
          game.composer.setSize(tile, tile);
          cam.aspect = 1;
          cam.updateProjectionMatrix();
          cam.position.set(...cp);
          cam.lookAt(new THREE.Vector3(...lk));
          cam.updateMatrixWorld();
          game.renderPass.scene = b.scene;
          game.renderPass.camera = cam;
          game.composer.render();
          // copy the canvas in the same task as the render (img.decode() never settles while the tab is hidden)
          g.drawImage(r.domElement, i * tile, j * tile);
          g.fillStyle = it.color ?? '#000';
          g.font = 'bold 24px sans-serif';
          g.fillText(it.label, i * tile + 10, j * tile + 30);
        }
      }
      delete anim.thighFollow;
      game.resize();
      ui.style.visibility = '';
      return dbg.saveSnap(name, grid.toDataURL('image/png'));
    },
  };
  (window as unknown as { dbg: typeof dbg }).dbg = dbg;
}
