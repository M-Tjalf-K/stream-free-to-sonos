"""Create a Windows release ZIP without PowerShell's nested-ZIP handling."""
from pathlib import Path
import sys
import zipfile

package = Path(sys.argv[1]).resolve()
destination = Path(sys.argv[2]).resolve()
if destination.is_relative_to(package):
    raise ValueError("The output ZIP must be outside the package directory")
with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(package.rglob("*")):
        if path.is_file():
            archive.write(path, path.relative_to(package).as_posix())
with zipfile.ZipFile(destination) as archive:
    bad_file = archive.testzip()
    if bad_file:
        raise RuntimeError("Corrupt package entry: " + bad_file)
    required = {"helper/sonos-host.exe", "helper/PYTHON-LICENSE.txt", "extension/manifest.json", "scripts/install.ps1", "LICENSE",
                "helper/ffmpeg.exe", "helper/ffmpeg-sources.zip", "helper/FFMPEG-LICENSE.txt", "helper/LAME-LICENSE.txt", "INSTALLATION.txt"}
    if not required.issubset(archive.namelist()):
        raise RuntimeError("Release package is incomplete")
    if not any(name.startswith("helper/_internal/python3") and name.endswith(".dll") for name in archive.namelist()):
        raise RuntimeError("Embedded Python runtime is missing")
print("Verified release ZIP: " + str(destination))
