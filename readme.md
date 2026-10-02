# Sonos Tab Audio

Eine minimale Chrome-Erweiterung für Tab-Ton auf Sonos im Heimnetz. Keine Anmeldung, kein externer Server, keine Telemetrie. Chrome startet den lokalen Helfer bei Bedarf über Native Messaging. Nach Stop oder Verlust der Browserverbindung endet er wieder. Die Gerätesuche startet kurzzeitig ebenfalls einen Helfer.

## Auf diesem Rechner loslegen

Der Helfer wurde bereits nach `%LOCALAPPDATA%\SonosTabAudio` installiert und für Chrome registriert.

1. In Chrome `chrome://extensions` öffnen und **Entwicklermodus** einschalten.
2. **Entpackte Erweiterung laden** wählen und diesen Ordner auswählen:
   `C:\GitRep\sonos-chrome\extension`
3. Die Erweiterung über Chromes Erweiterungsmenü anheften.
4. YouTube oder einen anderen Audio-Tab öffnen und die Wiedergabe starten.
5. Erweiterung anklicken, Raum bzw. bestehende Gruppe auswählen und **Auf Sonos abspielen** drücken.

Die Suche startet beim ersten Öffnen automatisch. Bei Bedarf **Geräte suchen** erneut drücken oder die private IPv4-Adresse eines Sonos-Geräts manuell eingeben. Gruppen und Stereopaare werden aus der Sonos-Topologie übernommen; die Lautstärke steuert die ausgewählte Gruppe. Neue Gruppen legt man zunächst in der Sonos-App an.

Das Popup darf während der Übertragung geschlossen werden. Pause, Titelauswahl und Springen bedient man auf der Quellseite. **Übertragung stoppen** beendet Stream und Erfassung; der Tab-Ton wird anschließend wieder lokal ausgegeben. Der Helfer stoppt keine andere Audioquelle, die inzwischen durch einen anderen Controller gestartet wurde. Die vorherige Sonos-Wiedergabe wird nicht automatisch wiederhergestellt.

## Installation auf einem anderen Windows-Rechner

Voraussetzungen: Chrome 116 oder neuer, Python 3.9 oder neuer, FFmpeg mit `libmp3lame`, Windows .NET Framework 4.x inklusive C#-Compiler. Python und FFmpeg müssen im PATH liegen oder explizit angegeben werden. Es werden keine Python-Laufzeitpakete benötigt.

Im Projektordner in PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

Alternativ mit festen Pfaden:

```powershell
.\scripts\install.ps1 -PythonPath 'C:\Pfad\python.exe' -FFmpegPath 'C:\Pfad\ffmpeg.exe'
```

Danach die Erweiterung wie oben laden. Der Installer kopiert Helfer und FFmpeg, erstellt den Windows-Launcher und registriert den Native-Messaging-Host nur für den aktuellen Benutzer unter `HKCU`. Kein Autostart und kein Windows-Dienst. Der Python-Interpreter bleibt am angegebenen Installationsort erforderlich. Eine FFmpeg-Version mit zusätzlichen DLLs benötigt diese DLLs im Installationsordner; getestet wurde hier die eigenständige vorhandene FFmpeg-EXE.

Die öffentliche `key` im Extension-Manifest hält die Erweiterungs-ID stabil: `dpdoiohoioboehbhnnkoogibhgiikigd`. Das ist kein geheimer Schlüssel. Wird sie geändert, muss der Helfer mit `-ExtensionId <neue-ID>` neu registriert werden. Bei Codeänderungen Helfer erneut installieren und die Erweiterung auf `chrome://extensions` neu laden; vorher eine laufende Übertragung stoppen.

Deinstallation:

```powershell
.\scripts\uninstall.ps1
```

Vorher die Übertragung stoppen. Die Erweiterung anschließend in Chrome entfernen. Die Deinstallation entfernt nur den Helfer und seine Chrome-Registrierung, nicht die bestehende Python-Installation.

## Netzwerk und Grenzen

- Rechner und Sonos müssen sich erreichen können. Gast-WLAN/Client-Isolation und getrennte VLANs können Suche oder Streaming verhindern. Bei mehreren Netzwerkadaptern hilft eine manuell eingetragene Sonos-IP.
- In Sonos muss **UPnP** erlaubt sein: Konto → Rechtliches und Datenschutz → Datenschutz und Sicherheit → Verbindungssicherheit. Sonos bezeichnet UPnP als nicht offiziell unterstützten Steuerweg; Firmware-Kompatibilität muss an den eigenen Geräten geprüft werden.
- Wenn Windows nach Netzwerkzugriff für Python fragt, Zugriff im **privaten Netzwerk** erlauben. Der Stream läuft auf einem zufälligen Port. Eine Firewall kann sonst verhindern, dass Sonos den Stream abholt. Keine Router-Portfreigabe einrichten.
- Musik, Podcasts und Livestream-Audio sind der Zielanwendungsfall. Sonos puffert den Stream; Verzögerung und Videoton-Synchronität sind hier noch nicht am Gerät gemessen.
- Tab, Chrome und Rechner müssen während der Übertragung laufen. Werbung und sämtliche weiteren Geräusche desselben Tabs werden mit übertragen. DRM-geschützte Inhalte sind nicht zugesichert.
- MVP: eine Audioquelle und ein Raum/eine bestehende Gruppe gleichzeitig. Kein Systemaudio, keine Playlistverwaltung, keine automatische Gruppierung.

## Aufbau

```text
Tab-Ton → tabCapture → Offscreen Document → AudioWorklet
       → 48-kHz-Stereo-PCM über localhost → Python-Helfer
       → FFmpeg: MP3 mit 192 kbit/s → HTTP-Abruf durch Sonos

Popup → Service Worker → Native Messaging → Helfer
                                         → SSDP / lokale Sonos-SOAP-Steuerung
```

Audio wird in 200-ms-Blöcken über HTTP an localhost geschickt. Der Upload akzeptiert ausschließlich localhost, die registrierte Erweiterungs-Origin und einen zufälligen Sitzungstoken. Steuerbefehle laufen ausschließlich über Native Messaging. Der MP3-Endpunkt hat eine zufällige URL und akzeptiert nur die IP des ausgewählten Sonos-Gruppenkoordinators. Audiodaten werden nicht dauerhaft gespeichert. Der Helfer beendet bei ausbleibendem Browser-Audio die Sitzung; die Erweiterung bricht bei einem wachsenden Übertragungsrückstand ab.

Die lokale Sonos-Steuerung ist bewusst mit der Python-Standardbibliothek implementiert. Dadurch entfällt für dieses kleine Tool eine zusätzliche SoCo-Installation; Discovery und Gruppensteuerung verwenden die gleichen lokalen UPnP-Dienste.

## Validierung

```powershell
python -m unittest discover -s tests -v
node --test tests/test_extension.cjs
```

Diese Tests prüfen Nachrichtenframing, IP-/Lautstärkevalidierung, Gruppenkoordinatoren, Audio-Worklet-Konvertierung, Extension-Start/Stop und einen echten FFmpeg-/HTTP-Stream inklusive Dekodierung, Zugriffsschutz und Prozessende. Nur die Sonos-Geräteantworten werden simuliert.

Optionaler Browser-Test unter Windows (Playwright und Chromium benötigt):

```powershell
.\.venv\Scripts\python.exe tests\browser_smoke.py
```

Er lädt die echte Erweiterung in einem separaten Chromium-Testprofil, prüft den installierten Native-Messaging-Launcher, rendert das Popup und überträgt synthetisches Browser-Audio durch den echten AudioWorklet-/HTTP-/FFmpeg-Pfad. Er startet keinen realen Sonos-Lautsprecher. Screenshots liegen unter `.test-artifacts`. Für Chromium wird eine temporäre Native-Host-Registrierung angelegt und anschließend zurückgesetzt.

**Stand der Geräteprüfung:** Automatische Suche auf diesem Rechner hat keine Sonos-Geräte gefunden. Echte Tab-Erfassung nach Toolbar-Klick und Wiedergabe, Latenz sowie Langzeitstabilität am Sonos sind daher noch ausstehend. Der Browser-Audiotest verwendet eine synthetische Quelle statt einer echten `tabCapture`-Freigabe.

Für den ersten Gerätetest: Stream starten, Wiedergabe mindestens 30 Minuten laufen lassen, Pause/Sprung auf der Quellseite ausprobieren, Popup schließen/öffnen und Stop sowie Schließen des Quell-Tabs prüfen. Bei Fehlern zuerst Statusmeldung, Sonos-UPnP-Einstellung und Windows-Firewall prüfen.

## Referenzen

- [Chrome: Tab-Audio und Offscreen Document](https://developer.chrome.com/docs/extensions/how-to/web-platform/screen-capture)
- [Chrome: Native Messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging)
- [Sonos: unterstützte Audioformate](https://docs.sonos.com/docs/supported-audio-formats)
- [Sonos: Verbindungssicherheit / UPnP](https://support.sonos.com/en/article/adjust-connection-security-settings)
- [SoCo: Gruppensteuerung als Protokollreferenz](https://github.com/SoCo/SoCo/blob/master/soco/groups.py)
