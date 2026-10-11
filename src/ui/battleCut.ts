import { el } from '../core/utils';
import { Sfx } from '../core/audio';
import { Input } from '../core/input';
import { artSrc } from './art';
import './battleCut.css';

export type CutKind = 'advantage' | 'ambush' | 'neutral';

/** The cut line's slope: the bible's main angle (−6°, rising to the right). */
const ANGLE = (6 * Math.PI) / 180;
/** Hitstop + desaturation before the first stroke (s). */
const FREEZE = 0.15;
/** Beat held on the fully desaturated frame before the stroke lands (s). */
const HOLD = 0.12;
/** Ambush strikes land this far apart (s). */
const AMBUSH_GAP = 0.07;
/** The halves fly apart over this long (s). Runs over the live battle scene. */
const SPLIT = 0.6;

const wait = (s: number) => new Promise((r) => setTimeout(r, s * 1000));

/**
 * Battle-start transition (UI bible §1: ink = the duel moment). The last field frame freezes and
 * drains to ink tones except around the enemy, an ink stroke cuts it along the bible's angle, and
 * the two halves fly apart. Kind changes the strokes: advantage = one gold cut from the left,
 * neutral = one ink cut, ambush = crimson cuts from the right with a shake.
 *
 * Resolves once the cut has landed: the caller switches to the battle scene then, and the halves
 * keep sliding apart over it and remove themselves.
 */
export async function battleCut(parent: HTMLElement, shot: HTMLCanvasElement, focus: { x: number; y: number } | null, kind: CutKind) {
  const W = window.innerWidth, H = window.innerHeight;
  // the cut passes through the enemy, kept off the screen edges so both halves read as halves
  const px = focus ? Math.min(W * 0.8, Math.max(W * 0.2, focus.x)) : W / 2;
  const py = focus ? Math.min(H * 0.7, Math.max(H * 0.3, focus.y)) : H / 2;
  const t = Math.tan(ANGLE);
  const yL = py + t * px, yR = py - t * (W - px);

  const root = el('div', `bcut ${kind}`, undefined, parent);
  shot.className = 'bc-base';
  root.appendChild(shot);
  const ink = inkFrame(shot, focus, W, H);
  const halves = (['top', 'bot'] as const).map((side) => {
    const h = el('div', `bc-half ${side}`, undefined, root);
    const c = h.appendChild(document.createElement('canvas'));
    c.width = ink.width; c.height = ink.height;
    c.getContext('2d')!.drawImage(ink, 0, 0);
    c.style.clipPath = side === 'top'
      ? `polygon(0 0, ${W}px 0, ${W}px ${yR}px, 0 ${yL}px)`
      : `polygon(0 ${yL}px, ${W}px ${yR}px, ${W}px ${H}px, 0 ${H}px)`;
    return h;
  });

  // freeze: the ink halves fade in over the colored frame (hitstop + desaturation)
  root.style.setProperty('--freeze', `${FREEZE * 1000}ms`);
  await wait(FREEZE + HOLD);

  // the strokes
  const from = kind === 'ambush' ? 'r' : 'l';
  const strokes: [number, number, string][] = kind === 'ambush'
    ? [[0, 14, 'thin'], [-0.4, -10, 'thin'], [0, 0, 'main']] // [offset ⟂ (×H/100), extra angle °, weight]
    : [[0, 0, 'main']];
  for (const [i, [off, dAngle, w]] of strokes.entries()) {
    if (i) await wait(AMBUSH_GAP);
    const s = el('div', `bc-stroke ${w} from-${from}`, '<div class="bc-ink"></div>', root);
    s.style.left = `${px}px`;
    s.style.top = `${py + (off * H) / 100}px`;
    s.style.transform = `translate(-50%, -50%) rotate(${-6 + dAngle}deg)`;
    Sfx.play('ink_slash');
    Input.rumble(w === 'main' ? 0.7 : 0.35, w === 'main' ? 0.7 : 0.5, w === 'main' ? 220 : 90);
    if (kind === 'ambush') {
      root.classList.remove('shake');
      void root.offsetWidth; // restart the shake animation
      root.classList.add('shake');
    }
  }
  const src = artSrc('ui/ink_splat');
  const splat = el('div', 'bc-splat' + (src ? ' art' : ''), undefined, root);
  if (src) splat.style.setProperty('--splat', `url("${src}")`);
  splat.style.left = `${px}px`;
  splat.style.top = `${py}px`;
  await wait(0.1);

  // split: the colored frame goes, the halves fly apart along the cut over the battle scene
  shot.remove();
  const dir = kind === 'ambush' ? -1 : 1; // the cut's direction decides which way the halves go
  const along = W * 0.75, apart = H * 0.35;
  const [ux, uy] = [Math.cos(ANGLE), -Math.sin(ANGLE)];
  const [nx, ny] = [Math.sin(ANGLE), Math.cos(ANGLE)]; // normal pointing down-right of the cut
  halves.forEach((h, i) => {
    const s = i === 0 ? -1 : 1; // top half: back along the cut and up; bottom: forward and down
    h.style.setProperty('--dx', `${(s * dir * ux * along + s * nx * apart).toFixed(1)}px`);
    h.style.setProperty('--dy', `${(s * dir * uy * along + s * ny * apart).toFixed(1)}px`);
    h.style.setProperty('--rot', `${s * dir * 3}deg`);
  });
  root.style.setProperty('--split', `${SPLIT * 1000}ms`);
  root.classList.add('split');
  setTimeout(() => root.remove(), SPLIT * 1000 + 100);
}

/** The frozen frame in ink tones, with the enemy left in color under a soft spotlight. */
function inkFrame(shot: HTMLCanvasElement, focus: { x: number; y: number } | null, W: number, H: number) {
  const c = document.createElement('canvas');
  c.width = shot.width; c.height = shot.height;
  const g = c.getContext('2d')!;
  g.filter = 'grayscale(1) sepia(0.35) contrast(1.2) brightness(0.62)';
  g.drawImage(shot, 0, 0);
  g.filter = 'none';
  if (focus) {
    const k = c.width / W;
    const x = focus.x * k, y = focus.y * k, r = H * k;
    const spot = document.createElement('canvas');
    spot.width = c.width; spot.height = c.height;
    const s = spot.getContext('2d')!;
    s.drawImage(shot, 0, 0);
    s.globalCompositeOperation = 'destination-in';
    const grad = s.createRadialGradient(x, y, r * 0.08, x, y, r * 0.24);
    grad.addColorStop(0, '#000');
    grad.addColorStop(1, 'rgba(0,0,0,0)');
    s.fillStyle = grad;
    s.fillRect(0, 0, spot.width, spot.height);
    g.drawImage(spot, 0, 0);
  }
  return c;
}
