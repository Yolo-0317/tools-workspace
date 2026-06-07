/** Mic capture → 16 kHz mono int16 PCM for Whisper. */

const TARGET_RATE = 16000;

export type PcmHandler = (pcm: ArrayBuffer) => void;

export type VadHandler = () => void;

export type CaptureOptions = {
  onPcm: PcmHandler;
  onSpeechStart?: () => void;
  onUtteranceEnd?: VadHandler;
  /** RMS threshold for speech (tune per mic). */
  speechThreshold?: number;
  /** ms of silence after speech to end utterance. */
  silenceMs?: number;
  /** ms of speech required before utterance counts. */
  minSpeechMs?: number;
};

export class PcmCapture {
  private ctx: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private processor: ScriptProcessorNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private running = false;
  private speechActive = false;
  private hadSpeech = false;
  private firedSpeechStart = false;
  private speechMs = 0;
  private silenceMs = 0;
  private opts: CaptureOptions;

  constructor(opts: CaptureOptions) {
    this.opts = {
      speechThreshold: opts.speechThreshold ?? 0.018,
      silenceMs: opts.silenceMs ?? 900,
      minSpeechMs: opts.minSpeechMs ?? 280,
      ...opts,
    };
  }

  async start(): Promise<void> {
    if (this.running) return;
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    this.ctx = new AudioContext();
    const inputRate = this.ctx.sampleRate;
    this.source = this.ctx.createMediaStreamSource(this.stream);
    this.processor = this.ctx.createScriptProcessor(4096, 1, 1);
    const threshold = this.opts.speechThreshold ?? 0.018;
    const silenceNeeded = this.opts.silenceMs ?? 900;
    const minSpeech = this.opts.minSpeechMs ?? 280;
    const frameMs = (4096 / inputRate) * 1000;

    this.processor.onaudioprocess = (ev) => {
      if (!this.running) return;
      const input = ev.inputBuffer.getChannelData(0);
      const down = resampleTo16k(input, inputRate);
      this.opts.onPcm(down.buffer);

      let sum = 0;
      for (let i = 0; i < input.length; i++) sum += input[i] * input[i];
      const rms = Math.sqrt(sum / input.length);
      const speaking = rms > threshold;

      if (speaking) {
        if (!this.speechActive) {
          this.speechActive = true;
          this.speechMs = 0;
        }
        this.speechMs += frameMs;
        this.silenceMs = 0;
        if (!this.firedSpeechStart && this.speechMs >= minSpeech) {
          this.firedSpeechStart = true;
          this.opts.onSpeechStart?.();
        }
        this.hadSpeech = this.hadSpeech || this.speechMs >= minSpeech;
      } else if (this.speechActive) {
        this.silenceMs += frameMs;
        if (this.silenceMs >= silenceNeeded) {
          this.speechActive = false;
          this.firedSpeechStart = false;
          if (this.hadSpeech) {
            this.hadSpeech = false;
            this.speechMs = 0;
            this.opts.onUtteranceEnd?.();
          } else {
            this.speechMs = 0;
          }
          this.silenceMs = 0;
        }
      }
    };

    this.source.connect(this.processor);
    this.processor.connect(this.ctx.destination);
    this.running = true;
  }

  /** Clear VAD state after teacher TTS (avoids echo triggering utterance_end). */
  resetVad(): void {
    this.speechActive = false;
    this.hadSpeech = false;
    this.firedSpeechStart = false;
    this.speechMs = 0;
    this.silenceMs = 0;
  }

  stop(): void {
    this.running = false;
    this.processor?.disconnect();
    this.source?.disconnect();
    this.stream?.getTracks().forEach((t) => t.stop());
    void this.ctx?.close();
    this.processor = null;
    this.source = null;
    this.stream = null;
    this.ctx = null;
  }
}

function resampleTo16k(input: Float32Array, inputRate: number): Int16Array {
  if (inputRate === TARGET_RATE) return floatToInt16(input);
  const ratio = inputRate / TARGET_RATE;
  const outLen = Math.floor(input.length / ratio);
  const out = new Int16Array(outLen);
  for (let i = 0; i < outLen; i++) {
    const idx = Math.floor(i * ratio);
    const s = Math.max(-1, Math.min(1, input[idx] ?? 0));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

function floatToInt16(input: Float32Array): Int16Array {
  const out = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}
