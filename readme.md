# Stream to Sonos

Ein unabh?ngiges Open-Source-Projekt, das den Ton eines Chrome-Tabs auf Sonos-Lautsprecher im lokalen Netzwerk ?bertr?gt. Geeignet f?r YouTube, Podcasts und Livestreams ? ohne Sonos-Login, Cloud-Server oder Telemetrie.

Die Erweiterung nutzt einen kleinen lokalen Helfer, den Chrome automatisch startet und nach der ?bertragung wieder beendet. Unterst?tzt werden einzelne R?ume und bereits bestehende Sonos-Gruppen inklusive Lautst?rkeregelung.

## Voraussetzungen

- Windows mit .NET Framework 4.x inklusive C#-Compiler
- Google Chrome ab Version 116
- Python ab Version 3.9
- FFmpeg mit `libmp3lame`, vorzugsweise als eigenst?ndige EXE ohne zus?tzliche DLLs
- Rechner und Sonos im selben erreichbaren Netzwerk; UPnP muss in Sonos aktiviert sein

Python und FFmpeg m?ssen im `PATH` verf?gbar sein. Es werden keine zus?tzlichen Python-Pakete f?r den Betrieb ben?tigt.

## Installation

1. Repository klonen oder herunterladen und entpacken.
2. Im Projektordner PowerShell ?ffnen und den Helfer installieren:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1
   ```

   Falls Python oder FFmpeg nicht im `PATH` liegen, ihre Pfade angeben:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 -PythonPath 'C:\Pfad\python.exe' -FFmpegPath 'C:\Pfad\ffmpeg.exe'
   ```

3. In Chrome `chrome://extensions` ?ffnen und **Entwicklermodus** aktivieren.
4. **Entpackte Erweiterung laden** ausw?hlen und den Unterordner `extension` des Projekts ?ffnen.
5. Die Erweiterung bei Bedarf im Chrome-Erweiterungsmen? anheften.

Der Helfer wird f?r den aktuellen Windows-Benutzer installiert. Wenn die Windows-Firewall nach Netzwerkzugriff f?r Python fragt, Zugriff im privaten Netzwerk erlauben.

## Nutzung

1. Einen Tab mit Audio ?ffnen und die Wiedergabe starten.
2. **Stream to Sonos** ?ffnen und einen Raum oder eine bestehende Gruppe ausw?hlen.
3. **Auf Sonos abspielen** anklicken. Das Popup kann anschlie?end geschlossen werden.
4. Mit **?bertragung stoppen** die ?bertragung beenden und den Ton wieder lokal ausgeben.

Pause, Titelauswahl und Springen erfolgen auf der Quellseite. Gruppen werden in der Sonos-App angelegt. Falls die automatische Suche keine Ger?te findet, kann eine Sonos-IP manuell eingegeben werden. Erfolgreich gefundene Ger?te werden lokal f?r sp?tere Suchen gespeichert.

## Hinweise

- Sonos puffert den Ton. Die ?bertragung eignet sich f?r Audio; lippensynchroner Videoton ist nicht gew?hrleistet.
- Chrome, Quell-Tab und Rechner m?ssen w?hrend der ?bertragung laufen. S?mtlicher Ton des ausgew?hlten Tabs wird ?bertragen, einschlie?lich Werbung.
- Eine Quelle und ein Raum beziehungsweise eine bestehende Gruppe werden gleichzeitig unterst?tzt. DRM-gesch?tzte Inhalte sind nicht zugesichert.
- Gast-WLAN, Netzwerkisolation oder Firewall-Regeln k?nnen die Verbindung verhindern. Sonos-UPnP ist kein offiziell unterst?tzter Steuerweg; die Kompatibilit?t kann sich durch Firmware-Updates ?ndern.

## Deinstallation

Die ?bertragung stoppen und im Projektordner ausf?hren:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\uninstall.ps1
```

Anschlie?end die Erweiterung unter `chrome://extensions` entfernen.

## Entwicklung

Beitr?ge, Fehlerberichte und Verbesserungsvorschl?ge sind willkommen. Die Laufzeit besteht aus JavaScript, der Python-Standardbibliothek und FFmpeg.

Tests aus dem Projektordner ausf?hren (Node.js wird f?r die JavaScript-Tests ben?tigt):

```powershell
python -m unittest discover -s tests -v
node --test tests/test_extension.cjs
```

Eine Open-Source-Lizenz ist bisher noch nicht im Repository hinterlegt.
