"""Collect notices for the embedded runtime and bootloader during the build."""
import importlib.metadata
from pathlib import Path
import shutil
import sys
import urllib.request

bundle = Path(sys.argv[1])
python_license = Path(sys.base_prefix) / "LICENSE.txt"
shutil.copyfile(python_license, bundle / "PYTHON-LICENSE.txt")
distribution = importlib.metadata.distribution("pyinstaller")
copying = next(path for path in distribution.files if str(path).endswith("licenses/COPYING.txt"))
shutil.copyfile(distribution.locate_file(copying), bundle / "PYINSTALLER-LICENSE.txt")
if any((bundle / "_internal").glob("libssl-3*.dll")):
    with urllib.request.urlopen("https://raw.githubusercontent.com/openssl/openssl/openssl-3.0/LICENSE.txt", timeout=30) as response:
        license_text = response.read()
    if b"Apache License" not in license_text:
        raise RuntimeError("Unexpected OpenSSL license response")
    (bundle / "OPENSSL-LICENSE.txt").write_bytes(license_text)
(bundle / "THIRD-PARTY-NOTICES.txt").write_text(
    "Stream to Sonos embeds the Python runtime and the PyInstaller bootloader.\n"
    "Python and its bundled components: see PYTHON-LICENSE.txt.\n"
    "PyInstaller bootloader: see PYINSTALLER-LICENSE.txt, including its distribution exception.\n"
    "OpenSSL 3 libraries, when present: see OPENSSL-LICENSE.txt (Apache License 2.0).\n"
    "FFmpeg and LAME: see FFMPEG-NOTICES.txt, FFMPEG-LICENSE.txt and LAME-LICENSE.txt.\n"
    "Exact corresponding sources and rebuild instructions: ffmpeg-sources.zip.\n",
    encoding="utf-8")
