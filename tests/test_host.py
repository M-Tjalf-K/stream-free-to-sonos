import io
import json
import math
import queue
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "helper"))
import host


class ProtocolTests(unittest.TestCase):
    def test_native_framing_unicode_eof_and_truncation(self):
        data = json.dumps({"type": "discover", "name": "Küche"}, ensure_ascii=False).encode()
        self.assertEqual(host.read_message(io.BytesIO(struct.pack("<I", len(data)) + data))["name"], "Küche")
        self.assertIsNone(host.read_message(io.BytesIO()))
        for value in [b"x", struct.pack("<I", 70000), struct.pack("<I", 5) + b"{}"]:
            with self.assertRaises(ValueError):
                host.read_message(io.BytesIO(value))

    def test_only_private_sonos_addresses(self):
        self.assertEqual(host.local_ip("192.168.178.42"), "192.168.178.42")
        for value in ["127.0.0.1", "0.0.0.0", "8.8.8.8", "239.255.255.250", "https://example.org", "169.254.1.1"]:
            with self.assertRaises(ValueError):
                host.local_ip(value)

    def test_group_coordinator_selected(self):
        xml = ET.fromstring('<ZoneGroups><ZoneGroup Coordinator="A"><ZoneGroupMember UUID="B" Location="http://192.168.1.3:1400/x"/><ZoneGroupMember UUID="A" Location="http://192.168.1.2:1400/x"/></ZoneGroup></ZoneGroups>')
        with patch.object(host, "topology", return_value=xml):
            self.assertEqual(host.group_target("192.168.1.3"), "192.168.1.2")

    def test_volume_rejects_invalid_values_without_network(self):
        for value in [-1, 101, True, 3.5, "35"]:
            with self.assertRaises(ValueError):
                host.volume("192.168.1.2", value)


class StreamTests(unittest.TestCase):
    def test_real_ffmpeg_stream_auth_playback_and_cleanup(self):
        import shutil
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            self.skipTest("FFmpeg nicht installiert")
        events, calls = queue.Queue(), []
        def soap(ip, service, action, **values):
            calls.append((action, values))
            # Another controller has taken over: close must not stop its music.
            return ET.fromstring("<result><CurrentURI>http://other/music.mp3</CurrentURI></result>")
        with patch.object(host, "group_target", return_value="127.0.0.1"), patch.object(host, "soap", side_effect=soap):
            session = host.Session("192.168.1.2", ffmpeg, "chrome-extension://test", lambda **event: events.put(event))
            process = session.process
            connection = session.connection()
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            try:
                def upload(data, token=connection["token"], origin="chrome-extension://test"):
                    request = urllib.request.Request(connection["upload"], data=data, headers={"Origin": origin, "X-Session-Token": token, "Content-Type": "application/octet-stream"})
                    return opener.open(request, timeout=5)
                for token, origin in [("bad", "chrome-extension://test"), (connection["token"], "http://evil.test")]:
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        upload(b"\x00" * 4, token, origin)
                    self.assertEqual(error.exception.code, 403)
                with self.assertRaises(urllib.error.HTTPError) as error:
                    upload(b"123")
                self.assertEqual(error.exception.code, 400)
                pcm = b"".join(struct.pack("<hh", int(math.sin(i * 2 * math.pi * 440 / 48000) * 12000), int(math.sin(i * 2 * math.pi * 440 / 48000) * 12000)) for i in range(9600))
                for _ in range(3):
                    with upload(pcm) as response:
                        self.assertEqual(response.status, 204)
                self.assertTrue(session.ready.wait(5))
                self.assertEqual(events.get(timeout=5)["status"], "Übertragung läuft")
                uri = "http://127.0.0.1:{}{}".format(session.server.server_port, session.path)
                with opener.open(uri, timeout=5) as response:
                    self.assertEqual(response.headers["Content-Type"], "audio/mpeg")
                    chunks = [response.read(2048)]
                    for _ in range(12):
                        with upload(pcm):
                            pass
                        chunks.append(response.read(2048))
                with tempfile.TemporaryDirectory() as folder:
                    file = Path(folder) / "test.mp3"
                    file.write_bytes(b"".join(chunks))
                    decoded = subprocess.run([ffmpeg, "-v", "error", "-i", str(file), "-f", "s16le", "-"], capture_output=True, timeout=10)
                    self.assertEqual(decoded.returncode, 0, decoded.stderr.decode())
                    self.assertGreater(len(decoded.stdout), 48000)
                self.assertIn("SetAVTransportURI", [call[0] for call in calls])
                self.assertIn("Play", [call[0] for call in calls])
            finally:
                session.close()
            self.assertIsNotNone(process.poll())
            self.assertNotIn("Stop", [call[0] for call in calls])
            session.close()  # idempotent cleanup


if __name__ == "__main__":
    unittest.main()
