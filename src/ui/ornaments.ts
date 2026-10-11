/**
 * Shared SVG ornaments (placeholders until 2D art lands — UI bible §10): the brass gear used by the
 * battle command ring and the title screen, and the goddess feather for moments of grace.
 */

/** Brass gear outline in a 152×152 viewBox (centre 76,76). */
export function gearSvg(teeth = 14, rOut = 74, rRoot = 64, rHole = 44) {
  const pts: string[] = [];
  const step = (Math.PI * 2) / teeth;
  for (let i = 0; i < teeth; i++) {
    for (const [da, r] of [[-0.5, rRoot], [-0.3, rOut], [0.18, rOut], [0.32, rRoot]] as const) {
      const t = (i + da) * step;
      pts.push(`${(76 + Math.cos(t) * r).toFixed(1)},${(76 + Math.sin(t) * r).toFixed(1)}`);
    }
  }
  const ticks = Array.from({ length: 36 }, (_, i) => {
    const t = (i / 36) * Math.PI * 2;
    const r1 = 52, r2 = i % 3 === 0 ? 60 : 56;
    return `<line x1="${76 + Math.cos(t) * r1}" y1="${76 + Math.sin(t) * r1}" x2="${76 + Math.cos(t) * r2}" y2="${76 + Math.sin(t) * r2}"/>`;
  }).join('');
  return `<svg viewBox="0 0 152 152"><defs><linearGradient id="crg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f2c94c"/><stop offset=".55" stop-color="#b58a2c"/><stop offset="1" stop-color="#5a4318"/></linearGradient></defs>`
    + `<path fill="url(#crg)" stroke="#0b0907" stroke-width="2" fill-rule="evenodd" d="M${pts.join('L')}Z M${76 + rHole},76 A${rHole},${rHole} 0 1 0 ${76 - rHole},76 A${rHole},${rHole} 0 1 0 ${76 + rHole},76Z"/>`
    + `<g stroke="#0b0907" stroke-width="1.5" opacity=".7">${ticks}</g></svg>`;
}

export const FEATHER_SVG = '<svg viewBox="0 0 40 120"><path d="M20 118 C18 90 6 70 8 40 C10 18 18 6 22 2 C30 18 34 40 30 64 C27 86 22 100 20 118Z" fill="#fbf4e2" stroke="#d4a83a" stroke-width="1.5"/><path d="M20 118 C21 80 22 40 22 4" stroke="#d4a83a" stroke-width="1.5" fill="none"/></svg>';
