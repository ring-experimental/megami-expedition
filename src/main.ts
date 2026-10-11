import { Game } from './game/game';

const canvas = document.getElementById('game') as HTMLCanvasElement;
const ui = document.getElementById('ui') as HTMLElement;
const game = new Game(canvas, ui);
game.init().catch((e) => {
  console.error(e);
  ui.innerHTML = `<div class="fatal">초기화 실패: ${String(e?.message ?? e)}</div>`;
});

// handy for debugging in the console
(window as unknown as { game: Game }).game = game;
if (import.meta.env.DEV) import('./debug').then((m) => m.installDebug(game));
