let stream, context, node, session, stopped = true, sending = false;
let queue = [], abort;
async function cleanup() {
  stopped = true;
  abort?.abort();
  node?.disconnect();
  stream?.getTracks().forEach(track => track.stop());
  if (context && context.state !== "closed") await context.close();
  stream = context = node = session = undefined;
  queue = [];
}
async function drain() {
  if (sending) return;
  sending = true;
  try {
    while (!stopped && queue.length) {
      const data = queue.shift();
      const response = await fetch(session.upload, {
        method: "POST", headers: {"Content-Type": "application/octet-stream", "X-Session-Token": session.token},
        body: data, signal: abort.signal
      });
      if (!response.ok) throw new Error("Audioverbindung unterbrochen (" + response.status + ")");
    }
  } catch (error) {
    if (!stopped) {
      await cleanup();
      chrome.runtime.sendMessage({type: "capture-error", error: error.message}).catch(() => {});
    }
  } finally { sending = false; }
}
chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (message.target !== "offscreen") return;
  (async () => {
    await cleanup();
    if (message.type === "stop") return;
    stream = await navigator.mediaDevices.getUserMedia({audio: {mandatory: {chromeMediaSource: "tab", chromeMediaSourceId: message.streamId}}, video: false});
    context = new AudioContext({sampleRate: 48000});
    await context.audioWorklet.addModule("pcm-worklet.js");
    session = message.session;
    abort = new AbortController();
    stopped = false;
    node = new AudioWorkletNode(context, "pcm", {numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [2]});
    node.port.onmessage = event => {
      if (stopped) return;
      if (queue.length >= 20) {
        cleanup().then(() => chrome.runtime.sendMessage({type: "capture-error", error: "Audioübertragung zu langsam"}));
        return;
      }
      queue.push(event.data);
      drain();
    };
    stream.getAudioTracks()[0].addEventListener("ended", () => {
      if (!stopped) chrome.runtime.sendMessage({type: "capture-error", error: "Quell-Tab geschlossen"}).catch(() => {});
    });
    const source = context.createMediaStreamSource(stream);
    source.connect(node);
    // The worklet produces silence locally; its graph stays active for capturing PCM.
    node.connect(context.destination);
    await context.resume();
  })().then(() => respond({ok: true}), async error => { await cleanup(); respond({ok: false, error: error.message}); });
  return true;
});
