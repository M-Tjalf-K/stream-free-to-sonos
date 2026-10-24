const $ = id => document.getElementById(id);
let tabId, active = false;
let language = "en", currentStatus = "ready", sourceTitle = "";
const t = message => SonosI18n.translate(message, language);
function showStatus(message) {
  currentStatus = message;
  $("status").textContent = t(message);
}
function applyLanguage(value) {
  language = value === "de" ? "de" : "en";
  document.documentElement.lang = language;
  $("language").value = language;
  document.querySelectorAll("[data-i18n]").forEach(element => { element.textContent = t(element.dataset.i18n); });
  $("ip").setAttribute("aria-label", t("ip"));
  $("source").textContent = sourceTitle || t("currentTab");
  showStatus(currentStatus);
}
async function send(type, data = {}) {
  const reply = await chrome.runtime.sendMessage({type, ...data});
  if (!reply?.ok) throw new Error(reply?.error || "noReply");
  return reply.result;
}
function render(state) {
  active = state.active;
  showStatus(state.status);
  if (state.devices) {
    const selected = $("devices").value;
    $("devices").replaceChildren(...state.devices.map(device => {
      const option = document.createElement("option"); option.value = device.ip; option.textContent = device.name; option.dataset.volume = device.volume; return option;
    }));
    if ([...$("devices").options].some(option => option.value === selected)) $("devices").value = selected;
    updateVolume();
  }
  $("start").disabled = active || !$("devices").value;
  $("stop").disabled = !active;
  $("refresh").disabled = $("add").disabled = $("devices").disabled = active;
}
function updateVolume() {
  const option = $("devices").selectedOptions[0];
  $("volume").disabled = !option;
  if (option) { $("volume").value = option.dataset.volume; $("level").value = option.dataset.volume + " %"; }
}
async function action(task) {
  try { await task(); } catch (error) { showStatus(error.message); }
}
$("language").onchange = () => action(async () => {
  applyLanguage($("language").value);
  await chrome.storage.local.set({language});
});
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && changes.language) applyLanguage(changes.language.newValue);
});
$("refresh").onclick = () => action(async () => { showStatus("searching"); render(await send("devices")); });
$("add").onclick = () => action(async () => render(await send("devices", {ip: $("ip").value.trim()})));
$("devices").onchange = updateVolume;
$("start").onclick = () => action(async () => { $("start").disabled = true; showStatus("starting"); try { render(await send("start", {tabId, ip: $("devices").value})); } finally { $("start").disabled = active || !$("devices").value; } });
$("stop").onclick = () => action(async () => render(await send("stop")));
$("volume").oninput = () => { $("level").value = $("volume").value + " %"; };
$("volume").onchange = () => action(async () => { await send("volume", {ip: $("devices").value, volume: Number($("volume").value)}); $("devices").selectedOptions[0].dataset.volume = $("volume").value; });
action(async () => {
  const settings = await chrome.storage.local.get("language");
  applyLanguage(settings.language);
  const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
  tabId = tab?.id; sourceTitle = tab?.title || ""; $("source").textContent = sourceTitle || t("currentTab");
  const state = await send("state");
  render(state);
  if (!state.devices.length) { showStatus("searching"); render(await send("devices")); }
});
setInterval(() => action(async () => { const state = await send("state"); showStatus(state.status); if (active !== state.active) render(state); }), 1000);
