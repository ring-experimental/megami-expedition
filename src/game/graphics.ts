/**
 * Graphics quality + dynamic resolution. Persisted per browser (not part of the run state).
 *
 * The game is fill-rate bound (half resolution = −56% GPU time on the measured iGPU), so the main
 * lever is the internal render resolution: a per-preset pixel budget caps HiDPI/4K screens, and an
 * automatic controller steps it down/up in a few fixed steps with hysteresis (resizing the composer
 * reallocates ~14 render targets, so it must not change often). Settings that would recompile
 * shaders (light counts, shadow on/off) are never touched at runtime.
 */
export type Quality = 'low' | 'medium' | 'high';

export interface QualityPreset {
  name: string;
  desc: string;
  /** Max internal render size in megapixels (drawing buffer, before dynamic scaling). */
  maxMP: number;
  shadowSize: number;
  bloom: boolean;
  /** MSAA samples on the composer's scene target (canvas MSAA is useless behind post-processing). */
  msaa: number;
}

export const QUALITY: Record<Quality, QualityPreset> = {
  low: { name: '낮음', desc: '내장 그래픽용 · 블룸 끔', maxMP: 1.0, shadowSize: 1024, bloom: false, msaa: 0 },
  medium: { name: '보통', desc: '1080p급 해상도 상한', maxMP: 2.1, shadowSize: 2048, bloom: true, msaa: 0 },
  high: { name: '높음', desc: '최대 4K · MSAA 4×', maxMP: 8.3, shadowSize: 2048, bloom: true, msaa: 4 },
};

/** Dynamic resolution steps (multiplier on the preset's pixel ratio). */
export const RES_STEPS = [1, 0.85, 0.7, 0.55];

const KEY = 'megami.graphics';

/** GPU name from WEBGL_debug_renderer_info ('' if hidden by the browser). */
export function gpuName(gl: WebGLRenderingContext | WebGL2RenderingContext) {
  try {
    const ext = gl.getExtension('WEBGL_debug_renderer_info');
    return ext ? String(gl.getParameter(ext.UNMASKED_RENDERER_WEBGL)) : '';
  } catch {
    return '';
  }
}

/** CPU-integrated graphics (AMD "Radeon(TM) Graphics"/Vega iGPUs, Intel). */
export function isIntegratedGpu(name: string) {
  if (/nvidia|geforce|quadro|radeon\s*(rx|pro)|arc\s*a\d/i.test(name)) return false;
  return /radeon\(tm\)\s*graphics|radeon\s*graphics|vega\s*\d+\s*graphics|intel|uhd|iris/i.test(name);
}

class GraphicsSettings {
  quality: Quality = 'high';
  autoRes = true;
  /** Index into RES_STEPS, driven by the controller below. */
  step = 0;
  gpu = '';
  integrated = false;
  /** true when the player never picked a preset (we chose from the GPU name). */
  private chosen = false;
  onChange: (() => void) | null = null;

  // controller state (drei PerformanceMonitor-like: 250 ms windows, 75% agreement, flip-flop lock)
  private winT = 0;
  private winFrames = 0;
  private windows: number[] = [];
  private changes = 0;
  private lastDir = 0;
  locked = false;
  fps = 0;

  init(gl: WebGLRenderingContext | WebGL2RenderingContext) {
    this.gpu = gpuName(gl);
    this.integrated = isIntegratedGpu(this.gpu);
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) {
        const v = JSON.parse(raw) as { quality?: Quality; autoRes?: boolean };
        if (v.quality && v.quality in QUALITY) { this.quality = v.quality; this.chosen = true; }
        if (typeof v.autoRes === 'boolean') this.autoRes = v.autoRes;
      }
    } catch {
      /* storage blocked */
    }
    if (!this.chosen) this.quality = this.integrated ? 'low' : 'high';
  }

  get preset() {
    return QUALITY[this.quality];
  }
  get scale() {
    return this.autoRes ? RES_STEPS[this.step] : 1;
  }

  set(q: Partial<{ quality: Quality; autoRes: boolean }>) {
    if (q.quality) { this.quality = q.quality; this.chosen = true; }
    if (q.autoRes !== undefined) this.autoRes = q.autoRes;
    this.step = 0;
    this.resetMonitor(true);
    try {
      localStorage.setItem(KEY, JSON.stringify({ quality: this.quality, autoRes: this.autoRes }));
    } catch {
      /* storage blocked */
    }
    this.onChange?.();
  }

  resetMonitor(unlock = false) {
    this.winT = 0;
    this.winFrames = 0;
    this.windows = [];
    if (unlock) { this.locked = false; this.changes = 0; this.lastDir = 0; }
  }

  /**
   * Feed the real (unclamped) frame time. Returns true when the resolution step changed.
   * Lower when >75% of the last 10 windows ran under 45 fps, raise when >75% ran at ≥ 57 fps.
   */
  sample(realDt: number) {
    if (realDt <= 0 || realDt > 0.5) return false; // tab switches / debugger pauses
    this.winT += realDt;
    this.winFrames++;
    if (this.winT < 0.25) return false;
    const fps = this.winFrames / this.winT;
    this.fps = fps;
    this.winT = 0;
    this.winFrames = 0;
    this.windows.push(fps);
    if (this.windows.length < 10) return false;
    const low = this.windows.filter((f) => f < 45).length / this.windows.length;
    const high = this.windows.filter((f) => f >= 57).length / this.windows.length;
    this.windows = [];
    if (!this.autoRes || this.locked) return false;
    let dir = 0;
    if (low > 0.75 && this.step < RES_STEPS.length - 1) dir = 1;
    else if (high > 0.75 && this.step > 0) dir = -1;
    if (!dir) return false;
    if (this.lastDir && dir !== this.lastDir) this.changes++;
    this.lastDir = dir;
    this.step += dir;
    // oscillating between two steps → settle on the lower one and stop measuring
    if (this.changes >= 4) { this.locked = true; this.step = Math.max(this.step, this.step - dir); }
    return true;
  }
}

export const Graphics = new GraphicsSettings();
