"""Explicit Windows setup lifecycle test in a temporary folder, restoring Chrome registration.

Run manually after build: .venv-build/Scripts/python tests/installer_smoke.py
The actual installed helper and extension files are never overwritten.
"""
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import time
import winreg

ROOT = Path(__file__).resolve().parents[1]
KEY = r"Software\Google\Chrome\NativeMessagingHosts\de.local.sonos"
ACCESS = winreg.KEY_READ | winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY


def run(executable, *arguments):
    result = subprocess.run([str(executable), *arguments], capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError(f"{executable.name} exited {result.returncode}: {result.stderr!r}")
    return result


def main():
    previous = None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, ACCESS) as key:
            previous = winreg.QueryValueEx(key, "")
    except FileNotFoundError:
        pass
    with tempfile.TemporaryDirectory(prefix="sonos-setup-") as temporary:
        # Also exercise UTF-8 JSON paths used by Chrome on non-ASCII user profiles.
        destination = Path(temporary) / "installed-ä"
        setup = ROOT / "dist/Stream-to-Sonos-Setup.exe"
        # Distinct setup AppId registry state must also be restored after testing.
        uninstall_key = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{D304486A-340F-4B92-9086-21C45381E31D}_is1"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, uninstall_key, 0, ACCESS):
                raise RuntimeError("An Inno Setup installation exists; use a clean Windows account for this test")
        except FileNotFoundError:
            pass
        needs_uninstall = True
        try:
            run(setup, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/NOICONS", "/SP-",
                "/DIR=" + str(destination), "/LOG=" + str(Path(temporary) / "install.log"))
            manifest_path = destination / "de.local.sonos.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            assert manifest["path"] == str(destination / "sonos-host.exe"), manifest
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, ACCESS) as key:
                assert winreg.QueryValueEx(key, "")[0] == str(manifest_path)
            assert (destination / "extension/manifest.json").exists()
            assert (destination / "extension/i18n.js").exists()
            assert (destination / "ffmpeg-sources.zip").exists()
            environment = dict(os.environ, PATH=str(Path(os.environ["SystemRoot"]) / "System32"))
            message = json.dumps({"id": 1, "type": "ping"}).encode()
            reply = subprocess.run([str(destination / "sonos-host.exe"), manifest["allowed_origins"][0]],
                                   input=struct.pack("<I", len(message)) + message,
                                   env=environment, capture_output=True, timeout=20)
            assert reply.returncode == 0, reply.stderr
            assert json.loads(reply.stdout[4:])["result"]["standalone"]
            cache = destination / "known-devices.json"
            cache.write_text('["192.168.1.123"]', encoding="utf-8")
            run(setup, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/NOICONS", "/SP-",
                "/DIR=" + str(destination))
            assert cache.read_text() == '["192.168.1.123"]', "Update lost device cache"
            run(destination / "unins000.exe", "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART")
            needs_uninstall = False
            assert not (destination / "sonos-host.exe").exists()
            assert not manifest_path.exists()
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, ACCESS):
                    raise AssertionError("Native Messaging registration remained after uninstall")
            except FileNotFoundError:
                pass
        finally:
            try:
                if needs_uninstall and (destination / "unins000.exe").exists():
                    run(destination / "unins000.exe", "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART")
            finally:
                if previous is not None:
                    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, KEY, 0, ACCESS) as key:
                        winreg.SetValueEx(key, "", 0, previous[1], previous[0])
                else:
                    try:
                        winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, KEY, winreg.KEY_WOW64_64KEY)
                    except FileNotFoundError:
                        pass
            # Inno finishes deleting its own launcher asynchronously.
            for _ in range(50):
                if not (destination / "unins000.exe").exists():
                    break
                time.sleep(0.1)
    print("PASS: setup, native ping without Python on PATH, update/cache retention, uninstall")


if __name__ == "__main__":
    main()
