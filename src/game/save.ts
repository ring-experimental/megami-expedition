import { GameState, State } from './state';
import { HEROES } from '../data/units';

/**
 * Save slots in localStorage: one autosave, one quicksave and three manual slots.
 * A save is the whole GameState (see GameState.toJSON) plus a small header for the slot list.
 * Storage can be missing or full (private windows, blocked site data) — every access is guarded
 * and failures are reported back instead of thrown.
 */
export type SlotId = 'auto' | 'quick' | 'slot1' | 'slot2' | 'slot3';
export const MANUAL_SLOTS: SlotId[] = ['slot1', 'slot2', 'slot3'];
export const SLOT_NAME: Record<SlotId, string> = { auto: '자동 저장', quick: '퀵세이브', slot1: '슬롯 1', slot2: '슬롯 2', slot3: '슬롯 3' };

/** Bump when the format changes in a way GameState.fromJSON can't absorb (new fields are fine). */
const VERSION = 1;
const KEY = (s: SlotId) => `megami.save.${s}`;

export interface SaveHeader {
  version: number;
  savedAt: number;
  playTime: number;
  place: string;
  chapter: string;
  money: number;
  party: { id: string; name: string; level: number }[];
}
interface SaveFile { header: SaveHeader; state: unknown }

export const Save = {
  /** Writes the current state. Returns false if storage refused it. */
  write(slot: SlotId, place: string): boolean {
    const st = State.current;
    const header: SaveHeader = {
      version: VERSION,
      savedAt: Date.now(),
      playTime: st.playTime,
      place,
      chapter: st.chapterTitle(),
      money: st.money,
      party: st.activeMembers().map((m) => ({ id: m.id, name: m.name, level: m.level })),
    };
    try {
      localStorage.setItem(KEY(slot), JSON.stringify({ header, state: st.toJSON() } satisfies SaveFile));
      return true;
    } catch {
      return false;
    }
  },

  header(slot: SlotId): SaveHeader | null {
    const f = read(slot);
    return f?.header ?? null;
  },

  /** Loads a slot into State.current. Returns false if it is empty or unreadable. */
  load(slot: SlotId): boolean {
    const f = read(slot);
    if (!f) return false;
    try {
      State.current = GameState.fromJSON(f.state);
      return true;
    } catch {
      return false;
    }
  },

  remove(slot: SlotId) {
    try { localStorage.removeItem(KEY(slot)); } catch { /* storage unavailable */ }
  },

  /** The most recently written slot (for "이어하기"). */
  latest(): SlotId | null {
    let best: SlotId | null = null, t = -1;
    for (const s of ['auto', 'quick', ...MANUAL_SLOTS] as SlotId[]) {
      const h = this.header(s);
      if (h && h.savedAt > t) { t = h.savedAt; best = s; }
    }
    return best;
  },
};

function read(slot: SlotId): SaveFile | null {
  try {
    const raw = localStorage.getItem(KEY(slot));
    if (!raw) return null;
    const f = JSON.parse(raw) as SaveFile;
    if (!f?.header || f.header.version > VERSION || !f.state) return null;
    return f;
  } catch {
    return null;
  }
}

/** "1:05:09" / "12:03" */
export function formatPlayTime(sec: number) {
  const s = Math.floor(sec % 60), m = Math.floor(sec / 60) % 60, h = Math.floor(sec / 3600);
  const two = (n: number) => String(n).padStart(2, '0');
  return h ? `${h}:${two(m)}:${two(s)}` : `${m}:${two(s)}`;
}

export function formatDate(t: number) {
  const d = new Date(t);
  const two = (n: number) => String(n).padStart(2, '0');
  return `${d.getMonth() + 1}/${d.getDate()} ${two(d.getHours())}:${two(d.getMinutes())}`;
}

/** Party line for a slot card: "카이 Lv5 · 리라 Lv5 · 톱니쥐 Lv4". */
export function partyLine(h: SaveHeader) {
  return h.party.map((p) => `${p.name} Lv${p.level}`).join(' · ') || HEROES.kai.name;
}
