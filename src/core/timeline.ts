/**
 * Game-time scheduler used by battle choreography (async/await friendly).
 * Pauses with the game, and maps real input timestamps into its own clock
 * so parry/QTE windows are frame-rate independent.
 */
interface Task {
  start: number;
  dur: number;
  fn?: (t: number) => void;
  ease?: (t: number) => number;
  resolve: () => void;
}

export class Timeline {
  time = 0;
  private lastReal = performance.now();
  /** game seconds per real second over the last frame (1 unless frames are clamped) */
  private rate = 1;
  private tasks: Task[] = [];
  private gen = 0;

  update(dt: number) {
    this.time += dt;
    const now = performance.now();
    // Below 20 fps the frame delta is clamped, so game time runs slower than real time. Map input
    // timestamps at that same rate, or parry/QTE presses get judged early/late by up to ~60 ms.
    const real = (now - this.lastReal) / 1000;
    this.rate = real > 1e-3 ? Math.min(1, dt / real) : 1;
    this.lastReal = now;
    const tasks = this.tasks;
    this.tasks = [];
    const keep: Task[] = [];
    for (const t of tasks) {
      const p = t.dur <= 0 ? 1 : Math.min(1, (this.time - t.start) / t.dur);
      if (t.fn) t.fn(t.ease ? t.ease(p) : p);
      if (p >= 1) t.resolve();
      else keep.push(t);
    }
    // tasks created during callbacks were pushed to this.tasks
    this.tasks = keep.concat(this.tasks);
  }

  /** Convert a performance.now() timestamp to timeline time. */
  at(realMs: number) {
    return this.time + Math.max(0, (realMs - this.lastReal) / 1000) * this.rate;
  }

  wait(sec: number): Promise<void> {
    const gen = this.gen;
    return new Promise((resolve) => {
      this.tasks.push({ start: this.time, dur: sec, resolve: () => gen === this.gen && resolve() });
    });
  }

  tween(sec: number, fn: (t: number) => void, ease?: (t: number) => number): Promise<void> {
    const gen = this.gen;
    fn(0);
    return new Promise((resolve) => {
      this.tasks.push({ start: this.time, dur: sec, fn, ease, resolve: () => gen === this.gen && resolve() });
    });
  }

  /** Drop all pending tasks; their promises never resolve (aborts running choreography). */
  clear() {
    this.gen++;
    this.tasks = [];
  }
}
