# Stream to Sonos

An independent open-source project that streams audio from a Chrome tab to Sonos speakers on your local network. Use it for YouTube, podcasts, and live streams without a Sonos login, cloud server, or telemetry.

The extension uses a small local helper that Chrome starts automatically and shuts down when streaming ends. It supports individual rooms and existing Sonos groups, including volume control.

## Requirements

- Windows with .NET Framework 4.x, including the C# compiler
- Google Chrome 116 or later
- Python 3.9 or later
- FFmpeg with `libmp3lame`, preferably a standalone executable without additional DLLs
- Your computer and Sonos devices must be able to reach each other on the local network, with UPnP enabled in Sonos

Python and FFmpeg must be available in your `PATH`, or their paths must be provided during installation. No additional Python packages are required to run the helper.

## Installation

1. Clone the repository or download and extract it.
2. Open PowerShell in the project directory and install the helper:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1
   ```

   If Python or FFmpeg is not in your `PATH`, provide their paths:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 -PythonPath 'C:\Path\python.exe' -FFmpegPath 'C:\Path\ffmpeg.exe'
   ```

3. Open `chrome://extensions` in Chrome and enable **Developer mode**.
4. Click **Load unpacked** and select the project's `extension` directory.
5. Optionally pin the extension in Chrome's extensions menu.

The helper is installed for the current Windows user. If Windows Firewall asks whether Python may access the network, allow access on private networks.

## Usage

1. Open a tab with audio and start playback.
2. Open **Stream to Sonos** and select a room or an existing group.
3. Click **Auf Sonos abspielen** (Play on Sonos). You can then close the popup.
4. Click **Übertragung stoppen** (Stop streaming) to end streaming and restore local audio playback.

The extension's controls currently use German labels. Pause, select tracks, and seek using the source website. Create groups in the Sonos app. If automatic discovery finds no devices, enter a Sonos device's IP address manually. Successfully discovered devices are saved locally for future searches.

## Limitations

- Sonos buffers audio, so streaming introduces a delay. Lip-synced video playback is not guaranteed.
- Chrome, the source tab, and your computer must remain running. All audio from the selected tab is streamed, including advertisements.
- One source and one room or existing group are supported at a time. Support for DRM-protected content is not guaranteed.
- Guest Wi-Fi, network isolation, or firewall rules may prevent connections. Sonos UPnP is not an officially supported control interface, and firmware updates may affect compatibility.

## Uninstallation

Stop streaming, then run this command from the project directory:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\uninstall.ps1
```

Then remove the extension at `chrome://extensions`.

## Development

Contributions, bug reports, and suggestions are welcome. The application uses JavaScript, the Python standard library, and FFmpeg.

Run the tests from the project directory. Node.js is required for the JavaScript tests:

```powershell
python -m unittest discover -s tests -v
node --test tests/test_extension.cjs
```

## License

This project is licensed under the [MIT License](LICENSE). FFmpeg is an external dependency and remains subject to its own license.
