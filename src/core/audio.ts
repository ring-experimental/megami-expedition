/**
 * Tiny WebAudio synthesizer for placeholder SFX (no audio files needed).
 * Replace with real sound assets later via the same play(name) API.
 */
type SfxName =
  | 'ui_move' | 'ui_ok' | 'ui_back' | 'ui_error'
  | 'swing' | 'swing_heavy' | 'hit' | 'hit_heavy' | 'parry' | 'dodge' | 'counter'
  | 'break' | 'stun' | 'magic' | 'fire' | 'frost' | 'volt' | 'heal' | 'buff'
  | 'battle_start' | 'ambush' | 'advantage' | 'victory' | 'defeat' | 'levelup'
  | 'recruit' | 'talk_fail' | 'talk_blip' | 'qte_perfect' | 'qte_good' | 'qte_miss'
  | 'alert' | 'step' | 'chest' | 'rest' | 'ko' | 'ink_slash';

class AudioSynth {
  ctx: AudioContext | null = null;
  master!: GainNode;
  volume = 0.6;
  private noiseBuf: AudioBuffer | null = null;

  unlock() {
    if (!this.ctx) {
      this.ctx = new AudioContext();
      this.master = this.ctx.createGain();
      this.master.gain.value = this.volume;
      const comp = this.ctx.createDynamicsCompressor();
      this.master.connect(comp).connect(this.ctx.destination);
      const len = this.ctx.sampleRate;
      this.noiseBuf = this.ctx.createBuffer(1, len, this.ctx.sampleRate);
      const d = this.noiseBuf.getChannelData(0);
      for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
    }
    if (this.ctx.state === 'suspended') this.ctx.resume();
  }

  setVolume(v: number) {
    this.volume = v;
    if (this.ctx) this.master.gain.value = v;
  }

  private tone(freq: number, dur: number, type: OscillatorType, vol: number, opts: { to?: number; delay?: number; attack?: number } = {}) {
    const ctx = this.ctx!;
    const t0 = ctx.currentTime + (opts.delay ?? 0);
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = type;
    o.frequency.setValueAtTime(freq, t0);
    if (opts.to) o.frequency.exponentialRampToValueAtTime(Math.max(20, opts.to), t0 + dur);
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(vol, t0 + (opts.attack ?? 0.005));
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    o.connect(g).connect(this.master);
    o.start(t0);
    o.stop(t0 + dur + 0.05);
  }

  private noise(dur: number, vol: number, opts: { type?: BiquadFilterType; freq?: number; to?: number; q?: number; delay?: number } = {}) {
    const ctx = this.ctx!;
    const t0 = ctx.currentTime + (opts.delay ?? 0);
    const src = ctx.createBufferSource();
    src.buffer = this.noiseBuf;
    const f = ctx.createBiquadFilter();
    f.type = opts.type ?? 'bandpass';
    f.frequency.setValueAtTime(opts.freq ?? 1000, t0);
    if (opts.to) f.frequency.exponentialRampToValueAtTime(opts.to, t0 + dur);
    f.Q.value = opts.q ?? 1;
    const g = ctx.createGain();
    g.gain.setValueAtTime(vol, t0);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    src.connect(f).connect(g).connect(this.master);
    src.start(t0);
    src.stop(t0 + dur + 0.05);
  }

  private arp(notes: number[], step: number, type: OscillatorType, vol: number, dur = 0.25) {
    notes.forEach((n, i) => this.tone(n, dur, type, vol, { delay: i * step }));
  }

  play(name: SfxName) {
    if (!this.ctx) return;
    switch (name) {
      case 'ui_move': this.tone(880, 0.05, 'square', 0.05); break;
      case 'ui_ok': this.tone(660, 0.07, 'square', 0.07); this.tone(990, 0.09, 'square', 0.06, { delay: 0.05 }); break;
      case 'ui_back': this.tone(520, 0.08, 'square', 0.06, { to: 300 }); break;
      case 'ui_error': this.tone(160, 0.18, 'sawtooth', 0.08); break;
      case 'talk_blip': this.tone(520 + Math.random() * 160, 0.03, 'triangle', 0.04); break;
      case 'swing': this.noise(0.16, 0.25, { type: 'bandpass', freq: 2500, to: 700, q: 1.5 }); break;
      case 'swing_heavy': this.noise(0.32, 0.35, { type: 'bandpass', freq: 1400, to: 300, q: 1.2 }); this.tone(120, 0.3, 'sine', 0.15, { to: 60 }); break;
      case 'hit': this.noise(0.12, 0.45, { type: 'lowpass', freq: 3000, to: 400 }); this.tone(180, 0.1, 'square', 0.12, { to: 70 }); break;
      case 'hit_heavy': this.noise(0.25, 0.6, { type: 'lowpass', freq: 2200, to: 200 }); this.tone(110, 0.25, 'square', 0.18, { to: 40 }); break;
      case 'parry':
        // metallic clang: detuned high partials + bright noise tick
        [1320, 1980, 2640, 3730].forEach((f, i) => this.tone(f, 0.45 - i * 0.07, 'triangle', 0.12));
        this.noise(0.07, 0.5, { type: 'highpass', freq: 4000 });
        break;
      case 'counter': this.tone(400, 0.15, 'sawtooth', 0.12, { to: 1200 }); this.noise(0.2, 0.4, { type: 'lowpass', freq: 3000, to: 300, delay: 0.1 }); break;
      case 'dodge': this.noise(0.22, 0.25, { type: 'bandpass', freq: 600, to: 2400, q: 2 }); break;
      case 'break':
        this.noise(0.6, 0.6, { type: 'highpass', freq: 2500, to: 6000 });
        [880, 1175, 1568].forEach((f, i) => this.tone(f, 0.5, 'triangle', 0.08, { delay: i * 0.04 }));
        break;
      case 'stun': this.arp([1568, 1318, 1568, 1318], 0.07, 'sine', 0.06, 0.12); break;
      case 'magic': this.tone(300, 0.5, 'sine', 0.15, { to: 1400 }); this.tone(450, 0.5, 'triangle', 0.06, { to: 2100, delay: 0.03 }); break;
      case 'fire': this.noise(0.6, 0.5, { type: 'lowpass', freq: 900, to: 200 }); this.tone(90, 0.5, 'sawtooth', 0.08, { to: 50 }); break;
      case 'frost': [2093, 2637, 3136].forEach((f, i) => this.tone(f, 0.35, 'sine', 0.06, { delay: i * 0.05 })); this.noise(0.4, 0.2, { type: 'highpass', freq: 5000 }); break;
      case 'volt': for (let i = 0; i < 5; i++) this.noise(0.05, 0.4, { type: 'bandpass', freq: 1500 + Math.random() * 3000, q: 4, delay: i * 0.045 }); this.tone(60, 0.3, 'sawtooth', 0.12); break;
      case 'heal': this.arp([523, 659, 784, 1046], 0.06, 'sine', 0.1, 0.4); break;
      case 'buff': this.arp([392, 523, 659], 0.05, 'triangle', 0.08, 0.3); break;
      // a blade through paper: bright hiss sweeping down + a dull thump under it
      case 'ink_slash': this.noise(0.14, 0.5, { type: 'bandpass', freq: 6000, to: 1200, q: 2 }); this.tone(90, 0.18, 'sine', 0.2, { to: 40 }); break;
      case 'battle_start': this.noise(0.5, 0.4, { type: 'bandpass', freq: 400, to: 4000, q: 1 }); this.tone(110, 0.6, 'sawtooth', 0.12, { to: 440 }); break;
      case 'advantage': this.arp([523, 659, 784, 1046, 1318], 0.05, 'square', 0.07, 0.2); break;
      case 'ambush': this.arp([466, 440, 415, 392], 0.08, 'sawtooth', 0.09, 0.25); break;
      case 'victory': this.arp([523, 523, 523, 659, 587, 659, 784], 0.11, 'square', 0.08, 0.3); break;
      case 'defeat': this.arp([392, 349, 311, 262], 0.25, 'triangle', 0.12, 0.6); break;
      case 'levelup': this.arp([523, 659, 784, 1046, 784, 1046], 0.07, 'square', 0.07, 0.25); break;
      case 'recruit': this.arp([392, 523, 659, 784, 1046, 1318], 0.08, 'triangle', 0.12, 0.5); break;
      case 'talk_fail': this.tone(300, 0.35, 'sawtooth', 0.08, { to: 150 }); break;
      case 'qte_perfect': this.tone(1568, 0.18, 'square', 0.08); this.tone(2093, 0.25, 'square', 0.07, { delay: 0.05 }); break;
      case 'qte_good': this.tone(1046, 0.15, 'square', 0.07); break;
      case 'qte_miss': this.tone(200, 0.15, 'square', 0.06, { to: 120 }); break;
      case 'alert': this.tone(880, 0.08, 'square', 0.07); this.tone(1320, 0.12, 'square', 0.07, { delay: 0.08 }); break;
      case 'step': this.noise(0.05, 0.08, { type: 'lowpass', freq: 600 }); break;
      case 'chest': this.arp([784, 988, 1175, 1568], 0.06, 'triangle', 0.1, 0.35); break;
      case 'rest': this.arp([392, 494, 587, 784, 988], 0.12, 'sine', 0.1, 0.8); break;
      case 'ko': this.tone(300, 0.6, 'triangle', 0.12, { to: 60 }); break;
    }
  }
}

export const Sfx = new AudioSynth();
export type { SfxName };
