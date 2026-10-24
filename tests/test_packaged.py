"""Checks the actual bundled EXE with no Python installation on its PATH."""
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import threading
import queue
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "dist" / "sonos-host"
ORIGIN = "chrome-extension://dpdoiohoioboehbhnnkoogibhgiikigd"


@unittest.skipUnless((BUNDLE / "sonos-host.exe").exists(), "Build the standalone helper first")
class PackagedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="sonos-standalone-")
        cls.folder = Path(cls.temporary.name) / "helper"
        shutil.copytree(BUNDLE, cls.folder)
        (cls.folder / "config.json").write_text(json.dumps({"origin": ORIGIN}), encoding="utf-8")
        cls.environment = dict(os.environ)
        cls.environment["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
        cls.environment["PYTHONHOME"] = str(cls.folder / "nonexistent-python")
        cls.environment["PYTHONPATH"] = str(cls.folder / "nonexistent-packages")
        cls.exe = cls.folder / "sonos-host.exe"

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_self_contained_runtime(self):
        result = subprocess.run([str(self.exe), "--self-test"], env=self.environment, cwd=self.temporary.name, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        self.assertTrue(json.loads(result.stdout)["standalone"])

    def test_native_connection_responds_before_stdin_closes(self):
        process = subprocess.Popen([str(self.exe), ORIGIN + "/"], env=self.environment, cwd=self.temporary.name,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        received = queue.Queue()
        def read_reply():
            try:
                size = struct.unpack("<I", process.stdout.read(4))[0]
                received.put(json.loads(process.stdout.read(size)))
            except Exception as error:
                received.put(error)
        try:
            data = json.dumps({"id": 1, "type": "ping"}).encode()
            process.stdin.write(struct.pack("<I", len(data)) + data)
            process.stdin.flush()
            threading.Thread(target=read_reply, daemon=True).start()
            reply = received.get(timeout=15)
            self.assertIsInstance(reply, dict)
            self.assertTrue(reply["result"]["standalone"])
            # Keep stdin open until a reply arrives: catches buffering regressions.
            process.stdin.close()
            process.wait(timeout=10)
            self.assertEqual(process.returncode, 0, process.stderr.read().decode("utf-8", "replace"))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()

    def test_unregistered_origin_rejected(self):
        result = subprocess.run([str(self.exe), "chrome-extension://wrong/"], env=self.environment,
                                cwd=self.temporary.name, capture_output=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")

    def test_group_command_rejects_public_target(self):
        data = json.dumps({"id": 1, "type": "set-group", "ip": "8.8.8.8", "members": ["8.8.8.8"]}).encode()
        result = subprocess.run([str(self.exe), ORIGIN + "/"], env=self.environment,
                                input=struct.pack("<I", len(data)) + data, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        reply = json.loads(result.stdout[4:])
        self.assertIn("private IPv4", reply["error"])

    def test_bundled_ffmpeg_encodes_pcm_without_external_tools(self):
        ffmpeg = self.folder / "ffmpeg.exe"
        self.assertTrue(ffmpeg.exists(), "Release must include FFmpeg")
        samples = (int(10000 * math.sin(2 * math.pi * 440 * i / 48000)) for i in range(48000))
        pcm = b"".join(struct.pack("<hh", value, value) for value in samples)
        result = subprocess.run([str(ffmpeg), "-hide_banner", "-loglevel", "error",
                                 "-f", "s16le", "-ar", "48000", "-ac", "2", "-i", "pipe:0",
                                 "-c:a", "libmp3lame", "-b:a", "192k", "-f", "mp3", "pipe:1"],
                                input=pcm, env=self.environment, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        self.assertGreater(len(result.stdout), 20000)
        self.assertTrue(result.stdout.startswith(b"ID3"))
        for notice in ("FFMPEG-LICENSE.txt", "LAME-LICENSE.txt", "ffmpeg-sources.zip"):
            self.assertTrue((self.folder / notice).exists(), notice)


if __name__ == "__main__":
    unittest.main()
