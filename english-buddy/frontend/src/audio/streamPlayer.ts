/** Accumulate streamed MP3, decode & play; stop() for barge-in. */

export class StreamPlayer {
  private ctx: AudioContext | null = null;
  private chunks: Uint8Array[] = [];
  private source: AudioBufferSourceNode | null = null;
  private stopped = false;
  private playGen = 0;

  private ensureCtx(): AudioContext {
    if (!this.ctx) this.ctx = new AudioContext();
    return this.ctx;
  }

  enqueue(mp3: ArrayBuffer): void {
    if (this.stopped) return;
    this.chunks.push(new Uint8Array(mp3));
    void this.tryPlayLatest();
  }

  private totalBytes(): number {
    return this.chunks.reduce((n, c) => n + c.length, 0);
  }

  private blob(): Blob {
    return new Blob(this.chunks as BlobPart[], { type: "audio/mpeg" });
  }

  /** Re-decode growing MP3 blob (short kid replies — OK on M1). */
  private async tryPlayLatest(): Promise<void> {
    if (this.stopped || this.totalBytes() < 4096) return;
    const gen = ++this.playGen;
    const ctx = this.ensureCtx();
    if (ctx.state === "suspended") await ctx.resume();

    try {
      const buf = await ctx.decodeAudioData(await this.blob().arrayBuffer());
      if (this.stopped || gen !== this.playGen) return;
      this.source?.stop();
      this.source = ctx.createBufferSource();
      this.source.buffer = buf;
      this.source.connect(ctx.destination);
      this.source.start(0);
    } catch {
      /* need more mp3 bytes */
    }
  }

  async flushAndFinish(): Promise<void> {
    if (this.stopped) return;
    await this.tryPlayLatest();
    const src = this.source;
    if (!src || this.stopped) return;
    await new Promise<void>((resolve) => {
      src.onended = () => resolve();
      setTimeout(resolve, 120_000);
    });
  }

  stop(): void {
    this.stopped = true;
    this.chunks = [];
    this.playGen++;
    try {
      this.source?.stop();
    } catch {
      /* */
    }
    this.source = null;
  }

  reset(): void {
    this.stop();
    this.stopped = false;
    this.chunks = [];
  }

  /** Between streamed sentences. */
  nextSentence(): void {
    this.chunks = [];
    this.playGen++;
    try {
      this.source?.stop();
    } catch {
      /* */
    }
    this.source = null;
  }
}
