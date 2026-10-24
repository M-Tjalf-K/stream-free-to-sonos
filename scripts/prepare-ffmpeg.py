"""Fetch pinned source archives; package exact sources and notices with our binary."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    ("ffmpeg-8.1.3.tar.xz", "https://ffmpeg.org/releases/ffmpeg-8.1.3.tar.xz",
     "7138d28c96d9d3e3af4ee3d8cad72741f8ffb40da90c1112235dea3ecd3178a3"),
    ("lame-3.100.tar.gz", "https://deb.debian.org/debian/pool/main/l/lame/lame_3.100.orig.tar.gz",
     "ddfe36cab873794038ae2c1210557ad34857a4b6bdc515785d1da9e175b1da1e"),
)

def main():
    downloads = ROOT / "build/downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    for name, url, digest in SOURCES:
        target = downloads / name
        if not target.exists():
            with urllib.request.urlopen(url, timeout=60) as response, target.open("wb") as output:
                shutil.copyfileobj(response, output)
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise RuntimeError("Source checksum mismatch: " + name)
    if "--sources-only" in sys.argv:
        return
    binary = ROOT / "build/ffmpeg/ffmpeg.exe"
    version = subprocess.check_output([str(binary), "-version"], text=True)
    if not version.startswith("ffmpeg version 8.1.3 ") or "--enable-libmp3lame" not in version:
        raise RuntimeError("Unexpected FFmpeg build; corresponding sources must match")
    if "--enable-gpl" in version or "--enable-nonfree" in version:
        raise RuntimeError("Only our LGPL FFmpeg build may be packaged")
    encoded = subprocess.run([
        str(binary), "-hide_banner", "-loglevel", "error", "-f", "s16le", "-ar", "48000",
        "-ac", "2", "-i", "pipe:0", "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "48000",
        "-write_xing", "0", "-id3v2_version", "0", "-flush_packets", "1", "-f", "mp3", "pipe:1",
    ], input=bytes(192000), capture_output=True, timeout=20)
    if encoded.returncode or len(encoded.stdout) < 20000:
        raise RuntimeError("FFmpeg PCM-to-MP3 check failed: " + encoded.stderr.decode("utf-8", "replace"))
    destination = ROOT / "build/ffmpeg"
    work = ROOT / "build/ffmpeg-work"
    shutil.copyfile(work / "ffmpeg-8.1.3/COPYING.LGPLv2.1", destination / "FFMPEG-LICENSE.txt")
    shutil.copyfile(work / "lame-3.100/COPYING", destination / "LAME-LICENSE.txt")
    (destination / "FFMPEG-BUILD.txt").write_text(version, encoding="utf-8")
    (destination / "FFMPEG-NOTICES.txt").write_text(
        "This software includes FFmpeg 8.1.3 (https://ffmpeg.org), LGPL 2.1 or later,\n"
        "and LAME 3.100 (https://lame.sourceforge.io), LGPL 2 or later.\n"
        "Both are built from unmodified sources. FFmpeg runs as a separate executable.\n"
        "Exact source archives, configuration and rebuild instructions are included\n"
        "in ffmpeg-sources.zip beside this notice. You may modify and replace ffmpeg.exe.\n"
        "See FFMPEG-LICENSE.txt and LAME-LICENSE.txt for terms and warranty disclaimers.\n"
        "MinGW-w64 runtime notices: MINGW-RUNTIME-LICENSE.txt.\n",
        encoding="utf-8")
    with zipfile.ZipFile(destination / "ffmpeg-sources.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for name, _, _ in SOURCES:
            archive.write(downloads / name, name)
        archive.write(destination / "MINGW-RUNTIME-LICENSE.txt", "MINGW-RUNTIME-LICENSE.txt")
        archive.write(ROOT / "scripts/build-ffmpeg.sh", "build-ffmpeg.sh")
        archive.write(ROOT / "scripts/prepare-ffmpeg.py", "prepare-ffmpeg.py")
        archive.writestr("BUILD.txt",
            "Built on Windows x64 with w64devkit 2.10.1, GCC 16.2.0.\n"
            "Toolchain: https://github.com/skeeto/w64devkit/releases/tag/v2.10.1\n"
            "Create an empty working directory, put the two source archives in\n"
            "build/downloads, then run sh build-ffmpeg.sh from that working directory\n"
            "inside the w64devkit shell. Output: build/ffmpeg/ffmpeg.exe.\n"
            "No source patches. All configuration switches are in build-ffmpeg.sh.\n"
            "You may rebuild and replace the installed ffmpeg.exe with your version.\n")
    print("Verified LGPL FFmpeg and packaged corresponding sources")

if __name__ == "__main__":
    main()
