/** Short cue when it is the child's turn (no reading required). */

let audioCtx: AudioContext | null = null;

function getCtx(): AudioContext {
  if (!audioCtx) {
    audioCtx = new AudioContext();
  }
  void audioCtx.resume();
  return audioCtx;
}

function beep(freq: number, start: number, duration: number, volume = 0.12): void {
  const ctx = getCtx();
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = "sine";
  osc.frequency.value = freq;
  osc.connect(gain);
  gain.connect(ctx.destination);
  gain.gain.setValueAtTime(volume, start);
  gain.gain.exponentialRampToValueAtTime(0.001, start + duration);
  osc.start(start);
  osc.stop(start + duration + 0.02);
}

/** Two-tone chime + light vibration (mobile). */
export function playChildTurnCue(): void {
  try {
    const t = getCtx().currentTime;
    beep(784, t, 0.14);
    beep(988, t + 0.18, 0.22, 0.14);
  } catch {
    /* ignore */
  }
  if (typeof navigator !== "undefined" && navigator.vibrate) {
    navigator.vibrate([60, 40, 80]);
  }
}
