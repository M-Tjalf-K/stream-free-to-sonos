const $ = id => document.getElementById(id);
let tabId, active = false;
let language = "en", currentStatus = "ready", sourceTitle = "";
let devices = [], groupWorking = false;
const t = message => SonosI18n.translate(message, language);
function showStatus(message) {
  currentStatus = message;
  $("status").textContent = t(message);
}
function applyLanguage(value) {
  language = value === "de" ? "de" : "en";
  document.documentElement.lang = language;
  $("language").dataset.language = language;
  $("language-flag").src = "flags/" + language + ".svg";
  $("language").title = t("switchLanguage");
  $("language").setAttribute("aria-label", t("switchLanguage"));
  document.querySelectorAll("[data-i18n]").forEach(element => { element.textContent = t(element.dataset.i18n); });
  $("ip").setAttribute("aria-label", t("ip"));
  $("source").textContent = sourceTitle || t("currentTab");
  showStatus(currentStatus);
  updateGroupControls();
}
async function send(type, data = {}) {
  const reply = await chrome.runtime.sendMessage({type, ...data});
  if (!reply?.ok) throw new Error(reply?.error || "noReply");
  return reply.result;
}
function render(state) {
  active = state.active;
  groupWorking = Boolean(state.groupBusy);
  showStatus(state.status);
  if (state.devices) {
    devices = state.devices;
    const selected = $("devices").value;
    $("devices").replaceChildren(...state.devices.map(device => {
      const option = document.createElement("option"); option.value = device.ip; option.textContent = device.name; option.dataset.volume = device.volume; return option;
    }));
    if ([...$("devices").options].some(option => option.value === selected)) $("devices").value = selected;
    updateVolume();
    renderGroups();
  }
  $("start").disabled = active || groupWorking || !$("devices").value;
  $("stop").disabled = !active || groupWorking;
  $("refresh").disabled = $("add").disabled = $("devices").disabled = active || groupWorking;
  $("volume").disabled ||= groupWorking;
  updateGroupControls();
}
function rooms() {
  return devices.flatMap(group => group.members || []).sort((a, b) => a.name.localeCompare(b.name));
}
function renderGroups() {
  const previous = $("group-main").value;
  $("group-main").replaceChildren(...rooms().map(room => {
    const option = document.createElement("option"); option.value = room.ip; option.textContent = room.name; return option;
  }));
  const selected = rooms().some(room => room.ip === previous) ? previous : $("devices").value;
  if (rooms().some(room => room.ip === selected)) $("group-main").value = selected;
  renderGroupRooms();
}
function renderGroupRooms() {
  const main = $("group-main").value;
  const group = devices.find(item => item.members?.some(room => room.ip === main));
  const selected = new Set((group?.members || []).map(room => room.ip));
  $("group-rooms").replaceChildren(...rooms().map(room => {
    const label = document.createElement("label");
    const input = document.createElement("input"); input.type = "checkbox"; input.value = room.ip;
    input.checked = selected.has(room.ip); input.disabled = room.ip === main;
    label.append(input, document.createTextNode(room.name)); return label;
  }));
  updateGroupControls();
}
function updateGroupControls() {
  const main = $("group-main").value;
  const group = devices.find(item => item.members?.some(room => room.ip === main));
  $("group-controls").disabled = active || groupWorking || !main;
  $("group-dissolve").disabled = !group || group.members.length < 2;
  $("group-hint").textContent = t(groupWorking ? "groupUpdating" : active ? "groupWhileStreaming" : !main ? "groupNoRooms" : "groupMainHint");
}
async function changeGroup(dissolve = false) {
  if (active || groupWorking) return;
  const ip = $("group-main").value;
  const members = dissolve ? [ip] : [...$("group-rooms").querySelectorAll("input:checked")].map(input => input.value);
  groupWorking = true;
  updateGroupControls();
  $("start").disabled = $("refresh").disabled = $("add").disabled = $("devices").disabled = $("volume").disabled = true;
  showStatus("groupUpdating");
  try {
    render(await send("set-group", {ip, members, dissolve}));
    $("devices").value = ip;
    updateVolume();
  } catch (error) {
    try { render(await send("state")); } catch { /* Keep the original error. */ }
    showStatus(error.message);
  } finally {
    groupWorking = false;
    updateGroupControls();
  }
}
function updateVolume() {
  const option = $("devices").selectedOptions[0];
  $("volume").disabled = !option;
  if (option) { $("volume").value = option.dataset.volume; $("level").value = option.dataset.volume + " %"; }
}
async function action(task) {
  try { await task(); } catch (error) { showStatus(error.message); }
}
$("language").onclick = () => action(async () => {
  applyLanguage(language === "en" ? "de" : "en");
  await chrome.storage.local.set({language});
});
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && changes.language) applyLanguage(changes.language.newValue);
});
$("refresh").onclick = () => action(async () => { showStatus("searching"); render(await send("devices")); });
$("add").onclick = () => action(async () => render(await send("devices", {ip: $("ip").value.trim()})));
$("devices").onchange = () => { updateVolume(); $("group-main").value = $("devices").value; renderGroupRooms(); };
$("group-main").onchange = renderGroupRooms;
$("group-apply").onclick = () => changeGroup();
$("group-dissolve").onclick = () => changeGroup(true);
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
setInterval(() => action(async () => { const state = await send("state"); showStatus(state.status); if (active !== state.active || groupWorking !== Boolean(state.groupBusy)) render(state); }), 1000);
