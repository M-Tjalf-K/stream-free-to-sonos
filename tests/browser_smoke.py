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
native_manifest = Path(os.environ["LOCALAPPDATA"]) / "SonosTabAudio" / "de.local.sonos.json"
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
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto("chrome-extension://" + ID + "/popup.html")
            page.wait_for_function("() => { const s = document.getElementById('status').textContent; return s === 'Verbunden' || s.startsWith('Keine Geräte'); }", timeout=30000)
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
            page.locator("body").screenshot(path=str(artifacts / "popup.png"))
            # Render long group names and populated controls without changing a real speaker.
            page.evaluate("() => render({active:false,status:'Verbunden',devices:[{ip:'192.168.178.42',name:'Wohnzimmer + Küche',volume:35}]})")
            assert page.locator("#start").is_enabled()
            assert page.locator("#level").inner_text() == "35 %"
            page.locator("body").screenshot(path=str(artifacts / "popup-connected.png"))
            page.evaluate("() => render({active:true,status:'Übertragung läuft',devices:[{ip:'192.168.178.42',name:'Wohnzimmer + Küche',volume:35}]})")
            assert page.locator("#stop").is_enabled()
            assert not page.locator("#start").is_enabled()
            assert not page.locator("#devices").is_enabled()
            page.locator("body").screenshot(path=str(artifacts / "popup-active.png"))
            # Real AudioWorklet + extension-origin HTTP uploads + real FFmpeg.
            # Only Sonos SOAP is mocked: no actual speaker is started by this test.
            with patch.object(host, "group_target", return_value="127.0.0.1"), patch.object(host, "soap", return_value=ET.fromstring("<result/>")):
                session = host.Session("192.168.1.2", shutil.which("ffmpeg"), "chrome-extension://" + ID, lambda **event: None)
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
