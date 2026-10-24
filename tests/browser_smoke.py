"""Browser/native smoke check. Optional: .venv Python + Playwright + Chromium."""
import os
import json
from pathlib import Path
import tempfile
import sys
import shutil
import xml.etree.ElementTree as ET
from unittest.mock import patch
import winreg
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "helper"))
import host
ID = "dpdoiohoioboehbhnnkoogibhgiikigd"
artifacts = ROOT / ".test-artifacts"
artifacts.mkdir(exist_ok=True)
native_manifest = Path(os.environ.get("SONOS_SMOKE_MANIFEST", str(Path(os.environ["LOCALAPPDATA"]) / "SonosTabAudio" / "de.local.sonos.json")))
assert native_manifest.exists(), "Zuerst scripts/install.ps1 ausführen"
registry = r"Software\Chromium\NativeMessagingHosts\de.local.sonos"
previous = None
try:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry) as key:
        previous = winreg.QueryValue(key, None)
except FileNotFoundError:
    pass
with winreg.CreateKey(winreg.HKEY_CURRENT_USER, registry) as key:
    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(native_manifest))
try:
    with sync_playwright() as playwright, tempfile.TemporaryDirectory() as profile:
        executables = list((Path(os.environ["LOCALAPPDATA"]) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        assert executables, "Playwright Chromium installieren"
        extension = ROOT / "extension"
        context = playwright.chromium.launch_persistent_context(profile, executable_path=str(sorted(executables)[-1]), headless=True,
            args=["--disable-extensions-except=" + str(extension), "--load-extension=" + str(extension)])
        try:
            worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")
            assert worker.url.startswith("chrome-extension://" + ID)
            worker.evaluate("() => chrome.storage.local.remove('language')")
            page = context.new_page()
            page.set_viewport_size({"width": 342, "height": 600})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto("chrome-extension://" + ID + "/popup.html")
            page.wait_for_function("() => { const s = document.getElementById('status').textContent; return s === 'Connected' || s.startsWith('No devices'); }", timeout=30000)
            assert page.locator("html").get_attribute("lang") == "en"
            assert page.locator("#language").get_attribute("data-language") == "en"
            assert page.locator("#start").inner_text() == "Play on Sonos"
            if os.environ.get("SONOS_SMOKE_MANIFEST") and page.locator("#status").inner_text() == "Connected":
                assert page.locator("#group-main option").count() > 0, "Updated helper did not expose rooms"
            assert not errors, errors
            status = page.locator("#status").inner_text()
            assert "Helfer" not in status and "host" not in status.lower(), status
            result = page.evaluate("""() => new Promise((resolve,reject) => {
                const port = chrome.runtime.connectNative('de.local.sonos');
                port.onMessage.addListener(message => { port.disconnect(); resolve(message); });
                port.onDisconnect.addListener(() => {
                    const error = chrome.runtime.lastError;
                    if (error) reject(new Error(error.message));
                });
                port.postMessage({id:1,type:'ping'});
            })""")
            assert result["result"]["version"] == "0.1.0", result
            assert result["result"]["standalone"], "Installed helper still depends on an external Python interpreter"
            page.locator("body").screenshot(path=str(artifacts / "popup.png"))
            # Render long group names and populated controls without changing a real speaker.
            page.evaluate("() => render({active:false,status:'Verbunden',devices:[{ip:'192.168.178.42',name:'Wohnzimmer + Küche',volume:35}]})")
            assert page.locator("#start").is_enabled()
            assert page.locator("#level").inner_text() == "35 %"
            page.locator("body").screenshot(path=str(artifacts / "popup-connected.png"))
            assert page.evaluate("() => document.body.getBoundingClientRect().height <= 600"), "Default popup exceeds Chrome's height limit"
            assert page.evaluate("() => document.documentElement.scrollWidth <= innerWidth"), "Popup overflows horizontally"
            page.evaluate("() => render({active:true,status:'Übertragung läuft',devices:[{ip:'192.168.178.42',name:'Wohnzimmer + Küche',volume:35}]})")
            assert page.locator("#stop").is_enabled()
            assert not page.locator("#start").is_enabled()
            assert not page.locator("#devices").is_enabled()
            page.locator("body").screenshot(path=str(artifacts / "popup-active.png"))
            # Switch during a simulated active stream. The selector must preserve
            # room, volume, manual input, and disabled controls without native calls.
            worker.evaluate("() => { state = {active:true,status:'Übertragung läuft',devices:[{ip:'192.168.178.42',name:'Wohnzimmer + Küche',volume:35}]}; }")
            page.locator('[data-i18n="manual"]').click()
            page.locator("#ip").fill("192.168.1.123")
            page.locator("#language").click()
            page.wait_for_function("() => document.documentElement.lang === 'de'")
            assert page.locator("#status").inner_text() == "Übertragung läuft"
            assert page.locator("#start").inner_text() == "Auf Sonos abspielen"
            assert page.locator("#devices").input_value() == "192.168.178.42"
            assert page.locator("#volume").input_value() == "35"
            assert page.locator("#ip").input_value() == "192.168.1.123"
            assert worker.evaluate("() => state.active"), "Changing language stopped the stream"
            assert page.locator("#start").is_disabled()
            assert page.locator("#stop").is_enabled()
            page.locator("body").screenshot(path=str(artifacts / "popup-german.png"))
            page.reload()
            page.wait_for_function("() => document.documentElement.lang === 'de' && document.getElementById('status').textContent === 'Übertragung läuft'")
            assert page.locator("#language").get_attribute("data-language") == "de"
            assert page.evaluate("() => document.body.getBoundingClientRect().height <= 600"), "German popup exceeds Chrome's height limit"
            page.locator("#language").click()
            page.wait_for_function("() => document.getElementById('status').textContent === 'Streaming'")
            page.reload()
            page.wait_for_function("() => document.documentElement.lang === 'en' && document.getElementById('status').textContent === 'Streaming'")
            assert page.locator("#language").get_attribute("data-language") == "en"
            # Localize a helper validation error and translate it immediately.
            worker.evaluate("() => { state.active = false; state.status = 'Bitte eine private IPv4-Adresse des Sonos-Geräts eingeben'; }")
            page.wait_for_function("() => document.getElementById('status').textContent.startsWith('Enter a private IPv4')")
            page.locator("#language").click()
            assert page.locator("#status").inner_text().startswith("Bitte eine private IPv4")
            page.locator("#language").click()
            page.locator('[data-i18n="manual"]').click()
            page.locator("body").screenshot(path=str(artifacts / "popup-english.png"))
            # Exercise the group editor end-to-end through the worker, with a
            # simulated native API so no real household grouping is touched.
            worker.evaluate("""() => {
                globalThis.realNative = native;
                globalThis.groupRequests = [];
                const a={ip:'192.168.178.42',name:'Living room',uuid:'A'};
                const b={ip:'192.168.178.43',name:'Kitchen',uuid:'B'};
                const c={ip:'192.168.178.44',name:'Office',uuid:'C'};
                const group = members => ({ip:members[0].ip,name:members.map(r=>r.name).join(' + '),volume:35,members});
                state={active:false,status:'connected',devices:[group([a]),group([b,c])],groupBusy:false};
                native=async(type,data) => {
                    if(type==='discover') return state.devices;
                    if(type!=='set-group') throw new Error('Unexpected test mutation');
                    groupRequests.push(data);
                    if(data.dissolve) return [group([a]),group([b]),group([c])];
                    const members=[a,b,c].filter(r=>data.members.includes(r.ip));
                    return [group(members),...[a,b,c].filter(r=>!data.members.includes(r.ip)).map(r=>group([r]))];
                };
            }""")
            page.evaluate("async () => render(await send('state'))")
            page.locator("#groups > summary").click()
            assert page.locator('#group-rooms input[value="192.168.178.42"]').is_checked()
            assert page.locator('#group-rooms input[value="192.168.178.42"]').is_disabled()
            page.locator('#group-rooms input[value="192.168.178.43"]').check()
            page.locator("#group-apply").click()
            page.wait_for_function("() => document.getElementById('status').textContent === 'Group updated'")
            assert worker.evaluate("() => groupRequests[0].members") == ['192.168.178.43', '192.168.178.42']
            assert page.locator("#devices").input_value() == "192.168.178.42"
            page.locator("#language").click()
            assert page.locator("#group-apply").inner_text() == "Gruppe übernehmen"
            page.locator("body").screenshot(path=str(artifacts / "groups-german.png"))
            page.locator('#group-rooms input[value="192.168.178.43"]').uncheck()
            page.locator("#group-apply").click()
            page.wait_for_function("() => document.getElementById('group-dissolve').disabled")
            assert worker.evaluate("() => groupRequests[1].members") == ['192.168.178.42']
            page.locator('#group-rooms input[value="192.168.178.43"]').check()
            page.locator("#group-apply").click()
            page.wait_for_function("() => !document.getElementById('group-dissolve').disabled")
            page.locator("#group-main").select_option("192.168.178.43")
            page.locator("#group-dissolve").click()
            page.wait_for_function("() => document.getElementById('group-dissolve').disabled")
            assert worker.evaluate("() => groupRequests.at(-1).dissolve")
            assert worker.evaluate("() => state.devices.length") == 3
            worker.evaluate("() => { state.active=true; }")
            page.evaluate("async () => render(await send('state'))")
            assert page.locator("#group-apply").is_disabled()
            assert page.locator("#group-dissolve").is_disabled()
            page.locator("#language").click()
            assert page.locator("#group-hint").inner_text() == "Stop streaming before changing groups."
            page.locator("body").screenshot(path=str(artifacts / "groups-english.png"))
            worker.evaluate("() => { state.active=false; native=realNative; }")
            # Real AudioWorklet + extension-origin HTTP uploads + real FFmpeg.
            # Only Sonos SOAP is mocked: no actual speaker is started by this test.
            with patch.object(host, "group_target", return_value="127.0.0.1"), patch.object(host, "soap", return_value=ET.fromstring("<result/>")):
                session = host.Session("192.168.1.2", os.environ.get("SONOS_TEST_FFMPEG", shutil.which("ffmpeg")), "chrome-extension://" + ID, lambda **event: None)
                try:
                    audio_page = context.new_page()
                    audio_page.on("pageerror", lambda error: errors.append(str(error)))
                    audio_page.goto("chrome-extension://" + ID + "/offscreen.html")
                    audio_page.evaluate("""async () => {
                        const audio = new AudioContext({sampleRate:48000});
                        const oscillator = audio.createOscillator();
                        const destination = audio.createMediaStreamDestination();
                        oscillator.connect(destination); oscillator.start(); await audio.resume();
                        window.testAudio = audio;
                        navigator.mediaDevices.getUserMedia = async () => destination.stream;
                    }""")
                    reply = worker.evaluate("connection => chrome.runtime.sendMessage({target:'offscreen',type:'start',streamId:'synthetic',session:connection})", session.connection())
                    assert reply["ok"], reply
                    assert session.ready.wait(8), "Kein Browser-Audio am Encoder angekommen"
                    uri = "http://127.0.0.1:{}{}".format(session.server.server_port, session.path)
                    with host.HTTP.open(uri, timeout=8) as response:
                        data = response.read(8192)
                    assert len(data) == 8192
                    reply = worker.evaluate("() => chrome.runtime.sendMessage({target:'offscreen',type:'stop'})")
                    assert reply["ok"], reply
                    audio_page.evaluate("() => window.testAudio.close()")
                    audio_page.close()
                    assert not errors, errors
                finally:
                    session.close()
            print(json.dumps({"native_host":"ok", "popup":"ok", "browser_pcm_to_mp3":"ok", "discovery_status":status, "page_errors":errors}, ensure_ascii=False))
        finally:
            context.close()
finally:
    if previous is None:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, registry)
    else:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, previous)
