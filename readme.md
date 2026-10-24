# Stream to Sonos

An independent open-source project that streams audio from a Chrome tab to Sonos speakers on your local network. Use it for YouTube, podcasts, and live streams without a Sonos login, cloud server, or telemetry.

The extension uses a small local helper that Chrome starts automatically and shuts down when streaming ends. It supports individual rooms and existing Sonos groups, including volume control.

## Requirements

- 64-bit Windows 10 or 11
- Google Chrome 116 or later
- Your computer and Sonos devices must be able to reach each other on the local network, with UPnP enabled in Sonos

The Windows setup includes the standalone helper, Python runtime, and a small LGPL FFmpeg build with LAME MP3 encoding. No separate Python or FFmpeg installation is required.

## Installation

1. Download `Stream-to-Sonos-Setup.exe` and run it by double-clicking. Setup installs for the current Windows user without requesting administrator rights.
2. Open `chrome://extensions` in Chrome and enable **Developer mode**.
3. Click **Load unpacked** and select this installed folder. You can paste the path into the Windows folder picker:

   ```text
   %LOCALAPPDATA%\SonosTabAudio\extension
   ```

   Alternatively, use **Stream to Sonos > Chrome-Erweiterungsordner** in the Start menu and copy the folder's full path.
4. Optionally pin the extension in Chrome's extensions menu.

Setup copies the extension files but does not install or enable the extension in Chrome. The manual Chrome step is required. An English walkthrough is included as [INSTALLATION.txt](INSTALLATION.txt) and can be opened at the end of setup.

The helper and its embedded runtime are installed for the current Windows user. Chrome starts `sonos-host.exe` directly when needed. If Windows Firewall asks whether the helper may access the network, allow access on private networks.

To update, stop streaming and run the new setup. Previously discovered device addresses are retained. Then click **Reload** for the extension at `chrome://extensions`. If migrating from an extension loaded from an extracted ZIP or source checkout, remove that extension once and load the installed folder shown above. Keep that installed folder in place: Chrome reads the extension from it.

For scripted installation, the alternative ZIP `stream-to-sonos-windows-x64.zip` includes `scripts/install.ps1` and the same bundled FFmpeg. Extract it and run `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1`. This is an optional developer route; normal setup does not run PowerShell or change execution policy.

## Usage

1. Open a tab with audio and start playback.
2. Open **Stream to Sonos** and select a room or an existing group.
3. Click **Play on Sonos**. You can then close the popup.
4. Click **Stop streaming** to end streaming and restore local audio playback.

The interface defaults to English. Use the **Language** selector to switch between **English** and **Deutsch**; the choice is saved locally and applies when the popup is reopened. Switching language also updates status and error messages without stopping a stream or changing the selected room or volume. Device names and source-tab titles are kept as provided.

Pause, select tracks, and seek using the source website. Create groups in the Sonos app. If automatic discovery finds no devices, enter a Sonos device's IP address manually. Successfully discovered devices are saved locally for future searches.

## Limitations

- Sonos buffers audio, so streaming introduces a delay. Lip-synced video playback is not guaranteed.
- Chrome, the source tab, and your computer must remain running. All audio from the selected tab is streamed, including advertisements.
- One source and one room or existing group are supported at a time. Support for DRM-protected content is not guaranteed.
- Guest Wi-Fi, network isolation, or firewall rules may prevent connections. Sonos UPnP is not an officially supported control interface, and firmware updates may affect compatibility.

## Uninstallation

Stop streaming and remove the extension at `chrome://extensions`. Then open **Windows Settings > Apps > Installed apps** and uninstall **Stream to Sonos (lokaler Helper)**. A Start menu uninstall shortcut is also available.

For a legacy script-only installation, run `scripts/uninstall.ps1` from the extracted ZIP instead.

## Development

Contributions, bug reports, and suggestions are welcome. The source uses JavaScript, the Python standard library, and FFmpeg. Python is required only for development and building the Windows helper.

To build the helper and installer, use 64-bit Windows with Python 3.12 or later and [Inno Setup 6.7.3 or later](https://jrsoftware.org/isinfo.php). Create the build environment:

```powershell
python -m venv .venv-build
```

Build the bundled FFmpeg as described below, then create the Windows packages:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

If Inno Setup is not found automatically, pass `-ISCCPath 'C:\Path\ISCC.exe'`. The compiler is a build-time dependency only. The setup is unsigned unless signed separately with a trusted publisher certificate; packaging alone does not provide a verified Windows publisher identity.

The build script installs the pinned build dependencies and creates:

- `dist/sonos-host/`: standalone helper and embedded runtime
- `dist/Stream-to-Sonos-Setup.exe`: per-user Windows setup, including FFmpeg and extension files
- `dist/stream-to-sonos-windows-x64.zip`: alternative scripted package
- `dist/ffmpeg-sources.zip`: exact FFmpeg/LAME source archives and rebuild instructions (also embedded in the setup)
- `dist/SHA256SUMS.txt`: SHA-256 hashes of these release artifacts

The setup registers only the Native Messaging helper under `HKCU`; it does not add Chrome extension policies, change browser settings, install a service, create an autorun task, or add firewall rules. Windows may still ask for network access when streaming. The extension itself is loaded manually.

### Building the bundled FFmpeg

Use [w64devkit 2.10.1 x64](https://github.com/skeeto/w64devkit/releases/tag/v2.10.1). From the repository root:

1. Run `.\.venv-build\Scripts\python.exe scripts/prepare-ffmpeg.py --sources-only`. This downloads pinned FFmpeg 8.1.3 and LAME 3.100 sources and verifies their SHA-256 checksums.
2. In the w64devkit shell, change to the repository root and run `sh scripts/build-ffmpeg.sh`.
3. Back in PowerShell, run `.\.venv-build\Scripts\python.exe scripts/prepare-ffmpeg.py` to collect notices and package the corresponding sources.
4. Run `scripts/build.ps1` as shown above.

The minimal build supports raw signed 16-bit PCM input through a pipe and MP3 output through a pipe, with no FFmpeg networking or video codecs. Both components use unmodified upstream sources. All configure switches are recorded in `scripts/build-ffmpeg.sh`; `FFMPEG-BUILD.txt` records the binary's configuration. The build rejects GPL/nonfree FFmpeg configurations. Users may rebuild and replace the installed `ffmpeg.exe`.

When publishing a release, upload the setup, ZIP, `ffmpeg-sources.zip`, and `SHA256SUMS.txt` together. Keep corresponding sources available alongside every published binary version. Include the FFmpeg/LAME license and source notice on the download page. Do not substitute an arbitrary FFmpeg binary without updating its exact sources, build configuration, notices and dependency licenses.

Run the tests from the project directory. Node.js is required for the JavaScript tests. Packaged-helper tests run when `dist/sonos-host` exists:

```powershell
python -m unittest discover -s tests -v
node --test tests/test_extension.cjs
```

To verify the encoder in the actual streaming pipeline, set `SONOS_TEST_FFMPEG` to the absolute path of `build/ffmpeg/ffmpeg.exe` before running the Python tests. A full FFmpeg installation is used only by this development test to decode and check the resulting MP3.

Run `.\.venv-build\Scripts\python.exe tests/installer_smoke.py` to explicitly test setup, Native Messaging, an update retaining the device cache, and uninstall. It uses a temporary installation folder and restores the previous Chrome helper registration afterward. It refuses to run if an installation with this setup's AppId already exists.

## License

This project's source is licensed under the [MIT License](LICENSE). The Windows package includes separate license notices for Python, the PyInstaller bootloader, and OpenSSL libraries. It also includes [FFmpeg](https://ffmpeg.org) under LGPL 2.1 or later and [LAME](https://lame.sourceforge.io) under LGPL 2 or later, distributed as a separate executable. See the installed `FFMPEG-LICENSE.txt`, `LAME-LICENSE.txt`, `FFMPEG-NOTICES.txt`, and `ffmpeg-sources.zip`. These components retain their own licenses.
