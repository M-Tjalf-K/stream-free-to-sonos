class PCM extends AudioWorkletProcessor {
  constructor() { super(); this.samples = new Int16Array(9600 * 2); this.offset = 0; }
  process(inputs) {
    const channels = inputs[0];
    for (let i = 0; i < 128; i++) {
      for (let c = 0; c < 2; c++) {
        const value = Math.max(-1, Math.min(1, channels[c]?.[i] ?? channels[0]?.[i] ?? 0));
        this.samples[this.offset++] = value < 0 ? value * 32768 : value * 32767;
      }
      if (this.offset === this.samples.length) {
        this.port.postMessage(this.samples.buffer, [this.samples.buffer]);
        this.samples = new Int16Array(9600 * 2);
        this.offset = 0;
      }
    }
    return true;
  }
}
registerProcessor("pcm", PCM);
