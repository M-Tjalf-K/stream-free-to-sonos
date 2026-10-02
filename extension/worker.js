let port, serial = 0;
const pending = new Map();
let state = {active: false, status: "Bereit", devices: []};
let busy = false;

function connect() {
  if (port) return;
  port = chrome.runtime.connectNative("de.local.sonos");
  const connection = port;
  port.onMessage.addListener(message => {
    if (message.event) {
      state.status = message.error || message.status;
      if (message.error) stop(message.error).catch(() => {});
      return;
    }
    const request = pending.get(message.id);
    if (!request) return;
    clearTimeout(request.timer);
    pending.delete(message.id);
    message.error ? request.reject(new Error(message.error)) : request.resolve(message.result);
  });
  port.onDisconnect.addListener(() => {
    const error = chrome.runtime.lastError?.message || "Verbindung zum Helfer beendet";
    if (port !== connection) return;
    port = undefined;
    for (const request of pending.values()) { clearTimeout(request.timer); request.reject(new Error(error)); }
    pending.clear();
    if (state.active) {
      state.active = false;
      state.status = error;
      chrome.action.setBadgeText({text: "!"});
      chrome.runtime.sendMessage({target: "offscreen", type: "stop"}).catch(() => {});
    }
  });
}

function native(type, data = {}) {
  connect();
  return new Promise((resolve, reject) => {
    const id = ++serial;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error("Helfer antwortet nicht")); }, 20000);
    pending.set(id, {resolve, reject, timer});
    port.postMessage({id, type, ...data});
  });
}

async function stop(status = "Übertragung beendet") {
  state.active = false;
  await chrome.runtime.sendMessage({target: "offscreen", type: "stop"}).catch(() => {});
  if (port) {
    try { await native("stop"); } finally { port?.disconnect(); port = undefined; }
  }
  state.status = status;
  await chrome.action.setBadgeText({text: ""});
}

async function handle(message) {
  if (message.type === "state") return state;
  if (message.type === "capture-error") { await stop(message.error); return state; }
  if (message.type === "devices") {
    if (state.active) throw new Error("Gerätesuche während einer Übertragung nicht möglich");
    try { state.devices = await native("discover", {ip: message.ip || ""}); }
    finally { if (!state.active) { const old = port; port = undefined; old?.disconnect(); } }
    state.status = state.devices.length ? "Verbunden" : "Keine Geräte gefunden – IP manuell eingeben";
    return state;
  }
  if (message.type === "volume") {
    try { return await native("volume", {ip: message.ip, volume: message.volume}); }
    finally { if (!state.active) { const old = port; port = undefined; old?.disconnect(); } }
  }
  if (message.type === "stop") { await stop(); return state; }
  if (message.type === "start") {
    if (busy || state.active) throw new Error("Eine Übertragung läuft bereits");
    busy = true;
    try {
      // Request the stream ID before any slow native operation, following the user's click.
      const streamId = await chrome.tabCapture.getMediaStreamId({targetTabId: message.tabId});
      if (!(await chrome.offscreen.hasDocument())) {
        await chrome.offscreen.createDocument({url: "offscreen.html", reasons: ["USER_MEDIA"], justification: "Tab-Ton lokal an Sonos übertragen"});
      }
      const session = await native("start", {ip: message.ip});
      state.active = true;
      state.status = "Audiostream startet …";
      const result = await chrome.runtime.sendMessage({target: "offscreen", type: "start", streamId, session});
      if (!result?.ok) throw new Error(result?.error || "Audioerfassung fehlgeschlagen");
      await chrome.action.setBadgeText({text: "ON"});
      await chrome.action.setBadgeBackgroundColor({color: "#167d59"});
      return state;
    } catch (error) { await stop(error.message).catch(() => {}); throw error; }
    finally { busy = false; }
  }
  throw new Error("Unbekannter Befehl");
}

chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (sender.id !== chrome.runtime.id || message.target === "offscreen") return;
  handle(message).then(result => respond({ok: true, result}), error => {
    state.status = error.message;
    respond({ok: false, error: error.message});
  });
  return true;
});
