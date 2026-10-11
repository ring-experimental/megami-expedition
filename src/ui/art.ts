/**
 * 2D art drop-in hooks. Files placed in public/art/ are picked up automatically
 * (see docs/2D_ASSET_PROMPTS.md for the full list); missing files fall back to
 * letters / emoji so the game always renders.
 */
import files from 'virtual:art-manifest';

/** lower-cased path → actual file path (lookups are case-insensitive) */
const available = new Map(files.map((f) => [f.toLowerCase(), f]));

const find = (base: string) => {
  for (const ext of ['.png', '.webp']) {
    const hit = available.get((base + ext).toLowerCase());
    if (hit) return hit;
  }
  return null;
};

export type Expression = 'happy' | 'angry';

/** Portrait content for a circular/rounded frame: art/portraits/<id>[_expr].png or the name's first letter. */
export function portraitInner(id: string, name: string, expr?: Expression) {
  const src = (expr && find(`art/portraits/${id}_${expr}`)) || find(`art/portraits/${id}`);
  return src ? `<img class="pimg" src="${src}" alt="">` : `<span>${name[0] ?? ''}</span>`;
}

export type IconKind = 'cmd' | 'el' | 'item' | 'st';

/** Inline icon: art/icons/<kind>_<id>.png, or the fallback text (emoji) when absent. */
export function icon(kind: IconKind, id: string, fallback = '') {
  const src = find(`art/icons/${kind}_${id}`);
  return src ? `<img class="ico ico-${kind}" src="${src}" alt="">` : fallback;
}

export function logoSrc() {
  return find('art/ui/logo');
}
