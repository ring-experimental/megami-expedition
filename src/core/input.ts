/** Keyboard / mouse / gamepad state with per-frame "pressed" edges and timestamped listeners. */
export type InputListener = (code: string, timeMs: number) => void;
export type InputDevice = 'kb' | 'pad';
/** Button-glyph family of the active pad (face buttons share positions, only the labels differ). */
export type PadStyle = 'xbox' | 'ps' | 'nintendo';
/** What the player is controlling the game with right now — UI subscribes to this. */
export interface InputState {
  device: InputDevice;
  padStyle: PadStyle;
  /** the pad that last drove the game (null until a pad has been used) */
  pad: { index: number; id: string; mapping: string } | null;
}
export type InputStateListener = (s: InputState) => void;

/** Standard Gamepad mapping (w3c.github.io/gamepad/#remapping) → virtual key codes. */
const PAD_CODES = ['PadA', 'PadB', 'PadX', 'PadY', 'PadLB', 'PadRB', 'PadLT', 'PadRT', 'PadBack', 'PadStart', 'PadL3', 'PadR3', 'PadUp', 'PadDown', 'PadLeft', 'PadRight'];
/** Menu navigation codes that auto-repeat while held (keyboard ignores OS repeat, so this is pad-only). */
const NAV_REPEAT = new Set(['PadUp', 'PadDown', 'PadLeft', 'PadRight', 'PadLSUp', 'PadLSDown', 'PadLSLeft', 'PadLSRight']);
const DEADZONE = 0.2;

/** Radial deadzone, rescaled so output starts at 0 right outside it. */
function deadzone(x: number, y: number): [number, number] {
  const m = Math.hypot(x, y);
  if (m < DEADZONE) return [0, 0];
  const k = Math.min(1, (m - DEADZONE) / (1 - DEADZONE)) / m;
  return [x * k, y * k];
}

function padStyleOf(id: string): PadStyle {
  if (/054c|playstation|dualsense|dualshock|wireless controller/i.test(id)) return 'ps';
  if (/057e|nintendo|pro controller|joy-con/i.test(id)) return 'nintendo';
  return 'xbox';
}

class InputManager {
  private down = new Set<string>();
  private pressedSet = new Set<string>();
  private releasedSet = new Set<string>();
  private listeners = new Set<InputListener>();
  mouseDX = 0;
  mouseDY = 0;
  wheel = 0;
  locked = false;
  canvas!: HTMLCanvasElement;
  onLockChange: ((locked: boolean) => void) | null = null;

  /** Last device the player touched — drives which button glyphs the UI shows (see subscribe()). */
  device: InputDevice = 'kb';
  padStyle: PadStyle = 'xbox';
  pad: InputState['pad'] = null;
  private stateSubs = new Set<InputStateListener>();
  /** Analog sticks after deadzone, -1..1 (y = down). */
  stick = { lx: 0, ly: 0, rx: 0, ry: 0 };
  rumbleOn = true;
  /** Every connected pad this frame and the index of the one driving the game (for diagnostics). */
  pads: Gamepad[] = [];
  padIndex = -1;
  private padBusy = new Set<number>();
  private padHeld = new Set<string>();
  private repeatAt = new Map<string, number>();
  private moveTravel = 0;
  private moveT = 0;

  init(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    window.addEventListener('keydown', (e) => {
      if (e.code === 'Tab' || e.code === 'Space' || e.code.startsWith('Arrow')) e.preventDefault();
      if (e.repeat) return;
      if (e.isTrusted) this.setDevice('kb');
      this.press(e.code, e.timeStamp || performance.now());
    });
    window.addEventListener('keyup', (e) => {
      this.down.delete(e.code);
      this.releasedSet.add(e.code);
    });
    window.addEventListener('blur', () => this.down.clear());
    // any real mouse use returns the UI to keyboard/mouse — clicks on DOM menus and plain cursor
    // movement count too, not just the canvas or pointer-locked look
    window.addEventListener('pointerdown', (e) => { if (e.isTrusted && e.pointerType === 'mouse') this.setDevice('kb'); }, true);
    canvas.addEventListener('mousedown', (e) => {
      this.press('Mouse' + e.button, e.timeStamp || performance.now());
    });
    window.addEventListener('mouseup', (e) => {
      const code = 'Mouse' + e.button;
      this.down.delete(code);
      this.releasedSet.add(code);
    });
    canvas.addEventListener('contextmenu', (e) => e.preventDefault());
    window.addEventListener('mousemove', (e) => {
      if (this.locked) {
        this.mouseDX += e.movementX;
        this.mouseDY += e.movementY;
      }
      // a deliberate move (~30px within 0.3s), so a nudged desk doesn't steal the UI from the pad
      if (!e.isTrusted || this.device !== 'pad') return;
      if (e.timeStamp - this.moveT > 300) this.moveTravel = 0;
      this.moveT = e.timeStamp;
      this.moveTravel += Math.abs(e.movementX) + Math.abs(e.movementY);
      if (this.moveTravel > 30) this.setDevice('kb');
    });
    window.addEventListener('wheel', (e) => {
      this.wheel += Math.sign(e.deltaY);
      if (e.isTrusted) this.setDevice('kb');
    });
    document.addEventListener('pointerlockchange', () => {
      this.locked = document.pointerLockElement === canvas;
      this.onLockChange?.(this.locked);
    });
  }

  private press(code: string, t: number) {
    this.down.add(code);
    this.pressedSet.add(code);
    this.emit(code, t);
  }

  private emit(code: string, t: number) {
    for (const l of this.listeners) l(code, t);
  }

  get state(): InputState {
    return { device: this.device, padStyle: this.padStyle, pad: this.pad };
  }

  /**
   * Follow the input state: `fn` runs now and again whenever the active device, the pad's button
   * layout or the pad driving the game changes (never per frame). Returns an unsubscribe function.
   */
  subscribe(fn: InputStateListener) {
    this.stateSubs.add(fn);
    fn(this.state);
    return () => { this.stateSubs.delete(fn); };
  }

  private setDevice(d: InputDevice, gp?: Gamepad) {
    const style = gp ? padStyleOf(gp.id) : this.padStyle;
    const pad = gp ? { index: gp.index, id: gp.id, mapping: gp.mapping } : this.pad;
    if (d === this.device && style === this.padStyle && pad?.index === this.pad?.index && pad?.id === this.pad?.id) return;
    this.device = d;
    this.padStyle = style;
    this.pad = pad;
    const s = this.state;
    for (const fn of this.stateSubs) fn(s);
  }

  /**
   * Sample gamepads (the API has no events for buttons) — call once at the start of every frame.
   * Buttons become `Pad*` codes in the same down/pressed sets and listeners as keys, so game code
   * just adds them to its key lists. The left stick also acts as a d-pad (`PadLS*`) for menus.
   */
  pollGamepads() {
    let pads: (Gamepad | null)[] = [];
    try {
      pads = Array.from(navigator.getGamepads?.() ?? []);
    } catch {
      /* blocked by permissions policy */
    }
    const live = pads.filter((p): p is Gamepad => !!p && p.connected);
    this.pads = live;
    // One controller often shows up twice (e.g. Steam's virtual Xbox pad + the raw device, whose
    // axes are in a different order). Prefer pads the browser remapped to the standard layout, and
    // hand control to another pad only when it *starts* being used — two devices reporting the same
    // held input must not ping-pong every frame.
    const pool = live.some((p) => p.mapping === 'standard') ? live.filter((p) => p.mapping === 'standard') : live;
    const busy = new Set<number>();
    for (const p of pool) {
      if (!p.buttons.some((b) => b.pressed) && Math.hypot(p.axes[0] ?? 0, p.axes[1] ?? 0) < 0.6) continue;
      busy.add(p.index);
      if (!this.padBusy.has(p.index)) this.padIndex = p.index;
    }
    this.padBusy = busy;
    let gp = pool.find((p) => p.index === this.padIndex) ?? null;
    if (!gp && pool.length) this.padIndex = (gp = pool[0]).index;

    const now = performance.now();
    // gamepad timestamps share performance.now()'s timebase and are closer to the actual press
    const t = gp && gp.timestamp > now - 50 && gp.timestamp <= now ? gp.timestamp : now;
    const held = new Set<string>();
    let [lx, ly, rx, ry] = [0, 0, 0, 0];
    if (gp) {
      gp.buttons.forEach((b, i) => {
        if (i >= PAD_CODES.length) return;
        // analog triggers report `pressed` at a hair's touch; require half a pull
        if (i === 6 || i === 7 ? b.value > 0.5 : b.pressed) held.add(PAD_CODES[i]);
      });
      [lx, ly] = deadzone(gp.axes[0] ?? 0, gp.axes[1] ?? 0);
      [rx, ry] = deadzone(gp.axes[2] ?? 0, gp.axes[3] ?? 0);
      const dir = (code: string, v: number) => { if (v > (this.padHeld.has(code) ? 0.35 : 0.6)) held.add(code); };
      dir('PadLSUp', -ly);
      dir('PadLSDown', ly);
      dir('PadLSLeft', -lx);
      dir('PadLSRight', lx);
    }
    let fresh = false;
    for (const c of held) {
      if (!this.padHeld.has(c)) {
        this.press(c, t);
        this.repeatAt.set(c, now + 380);
        fresh = true;
      } else if (NAV_REPEAT.has(c) && now >= (this.repeatAt.get(c) ?? Infinity)) {
        this.pressedSet.add(c);
        this.repeatAt.set(c, now + 110);
      }
    }
    for (const c of this.padHeld) {
      if (held.has(c)) continue;
      this.down.delete(c);
      this.releasedSet.add(c);
    }
    this.padHeld = held;
    this.stick = { lx, ly, rx, ry };
    if (gp && (fresh || Math.hypot(lx, ly) > 0.5 || Math.hypot(rx, ry) > 0.5)) this.setDevice('pad', gp);
  }

  /** Controller vibration (0..1 motor strengths) — no-op without a pad or with rumble disabled. */
  rumble(strong: number, weak: number, ms: number) {
    if (!this.rumbleOn || this.device !== 'pad') return;
    try {
      const gp = navigator.getGamepads?.()[this.padIndex];
      gp?.vibrationActuator?.playEffect('dual-rumble', { duration: ms, strongMagnitude: strong, weakMagnitude: weak })?.catch(() => {});
    } catch {
      /* vibration unsupported */
    }
  }

  listen(fn: InputListener) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  isDown(...codes: string[]) {
    return codes.some((c) => this.down.has(c));
  }
  pressed(...codes: string[]) {
    return codes.some((c) => this.pressedSet.has(c));
  }
  released(...codes: string[]) {
    return codes.some((c) => this.releasedSet.has(c));
  }
  /** Swallow this frame's presses (e.g. the button that closed a menu must not also act in the field). */
  consumePressed() {
    this.pressedSet.clear();
  }

  requestLock() {
    if (this.locked) return;
    try {
      const p = this.canvas.requestPointerLock?.() as unknown as Promise<void> | undefined;
      if (p && typeof p.catch === 'function') p.catch(() => {});
    } catch {
      /* browsers may refuse right after exiting the lock */
    }
  }
  exitLock() {
    if (this.locked) document.exitPointerLock();
  }

  endFrame() {
    this.pressedSet.clear();
    this.releasedSet.clear();
    this.mouseDX = 0;
    this.mouseDY = 0;
    this.wheel = 0;
  }
}

export const Input = new InputManager();

/** Common key groups */
export const K = {
  confirm: ['Enter', 'Space', 'KeyF', 'NumpadEnter', 'PadA'],
  back: ['Escape', 'Backspace', 'KeyQ', 'PadB'],
  up: ['KeyW', 'ArrowUp', 'PadUp', 'PadLSUp'],
  down: ['KeyS', 'ArrowDown', 'PadDown', 'PadLSDown'],
  left: ['KeyA', 'ArrowLeft', 'PadLeft', 'PadLSLeft'],
  right: ['KeyD', 'ArrowRight', 'PadRight', 'PadLSRight'],
  parry: ['KeyF', 'Mouse0', 'PadA', 'PadRB'],
  dodge: ['Space', 'Mouse2', 'PadB'],
  qte: ['KeyF', 'Space', 'Mouse0', 'PadA', 'PadB', 'PadRB'],
};
