const $ = id => document.getElementById(id);
let tabId, active = false;
async function send(type, data = {}) {
  const reply = await chrome.runtime.sendMessage({type, ...data});
  if (!reply?.ok) throw new Error(reply?.error || "Keine Antwort");
  return reply.result;
}
function render(state) {
  active = state.active;
  $("status").textContent = state.status;
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
  try { await task(); } catch (error) { $("status").textContent = error.message; }
}
$("refresh").onclick = () => action(async () => { $("status").textContent = "Suche im Heimnetz …"; render(await send("devices")); });
$("add").onclick = () => action(async () => render(await send("devices", {ip: $("ip").value.trim()})));
$("devices").onchange = updateVolume;
$("start").onclick = () => action(async () => { $("start").disabled = true; $("status").textContent = "Starte …"; try { render(await send("start", {tabId, ip: $("devices").value})); } finally { $("start").disabled = active || !$("devices").value; } });
$("stop").onclick = () => action(async () => render(await send("stop")));
$("volume").oninput = () => { $("level").value = $("volume").value + " %"; };
$("volume").onchange = () => action(async () => { await send("volume", {ip: $("devices").value, volume: Number($("volume").value)}); $("devices").selectedOptions[0].dataset.volume = $("volume").value; });
action(async () => {
  const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
  tabId = tab.id; $("source").textContent = tab.title || "Aktueller Tab";
  const state = await send("state");
  render(state);
  if (!state.devices.length) { $("status").textContent = "Suche im Heimnetz …"; render(await send("devices")); }
});
setInterval(() => action(async () => { const state = await send("state"); $("status").textContent = state.status; if (active !== state.active) render(state); }), 1000);
