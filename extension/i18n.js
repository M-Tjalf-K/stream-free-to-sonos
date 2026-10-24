// Keep statuses independent of the UI language. Also accept older native helpers.
const SonosI18n = (() => {
  const strings = {
    en: {
      switchLanguage: "English – switch to German",
      manageGroups: "Manage groups", groupMain: "Main room", groupApply: "Apply group", groupDissolve: "Dissolve group",
      groupHelp: "Choose a main room, then check the rooms to play together. Uncheck a room to remove it. Changing groups can interrupt current Sonos playback.",
      groupMainHint: "The main room stays selected. Choose another main room to remove it. Stereo and surround rooms stay together.",
      groupNoRooms: "Find devices first. If rooms are missing, update the local helper using the new setup.",
      groupWhileStreaming: "Stop streaming before changing groups.", groupBusy: "A group change is in progress.",
      groupUpdating: "Updating group…", groupUpdated: "Group updated", invalidGroupRooms: "Select known rooms from the same Sonos system, including the main room.",
      groupNotConfirmed: "Sonos did not confirm the requested group.",
      groupChangeFailed: "The group change failed. Some rooms may have moved. Check the refreshed room list.",
      language: "Language", subtitle: "Tab audio straight to your home network",
      devices: "Room or existing group", refresh: "Find devices", manual: "Add a device manually",
      add: "Add", ip: "Sonos IP address", source: "Source:", currentTab: "Current tab",
      start: "Play on Sonos", stop: "Stop streaming", volume: "Volume",
      footer: "Local · no account · audio delay applies",
      ready: "Ready", searching: "Searching your home network…", starting: "Starting…",
      connected: "Connected", noDevices: "No devices found – enter an IP address manually",
      streamStarting: "Audio stream is starting…", streaming: "Streaming", stopped: "Streaming stopped",
      noReply: "No response", helperDisconnected: "Connection to the helper closed",
      helperTimeout: "The helper is not responding", discoveryWhileStreaming: "Cannot search for devices while streaming",
      alreadyStreaming: "A stream is already running", captureFailed: "Audio capture failed",
      unknownCommand: "Unknown command", streamTooSlow: "Audio upload is too slow", sourceClosed: "Source tab closed",
      invalidIP: "Enter a private IPv4 address for the Sonos device", notSonos: "No Sonos device found at this address",
      invalidVolume: "Volume must be between 0 and 100", noCoordinator: "Sonos group coordinator not found",
      noAudio: "No audio signal received from the browser", browserDisconnected: "Audio connection to the browser lost",
      incompleteHeader: "Incomplete message header", invalidMessageSize: "Invalid message size",
      incompleteMessage: "Incomplete message", forbiddenExtension: "Extension not allowed",
      helperMissing: "Local helper not found. Run the Windows setup first.", nativeExited: "The local helper has exited",
      ffmpegExited: "FFmpeg exited: ", audioInterrupted: "Audio connection interrupted (HTTP {code})",
      sonosRejected: "Sonos rejected {action} (HTTP {code}). Check the UPnP setting. {detail}",
    },
    de: {
      switchLanguage: "Deutsch – zu Englisch wechseln",
      manageGroups: "Gruppen verwalten", groupMain: "Hauptraum", groupApply: "Gruppe übernehmen", groupDissolve: "Gruppe auflösen",
      groupHelp: "Hauptraum wählen und die gemeinsam spielenden Räume anhaken. Haken entfernen, um einen Raum zu lösen. Änderungen können die aktuelle Sonos-Wiedergabe unterbrechen.",
      groupMainHint: "Der Hauptraum bleibt ausgewählt. Zum Entfernen einen anderen Hauptraum wählen. Stereo- und Surroundräume bleiben zusammen.",
      groupNoRooms: "Zuerst Geräte suchen. Falls Räume fehlen, den lokalen Helfer mit dem neuen Setup aktualisieren.",
      groupWhileStreaming: "Vor Gruppenänderungen die Übertragung stoppen.", groupBusy: "Eine Gruppenänderung läuft bereits.",
      groupUpdating: "Gruppe wird geändert …", groupUpdated: "Gruppe aktualisiert", invalidGroupRooms: "Bekannte Räume desselben Sonos-Systems einschließlich Hauptraum auswählen.",
      groupNotConfirmed: "Sonos hat die gewünschte Gruppe nicht bestätigt.",
      groupChangeFailed: "Die Gruppenänderung ist fehlgeschlagen. Einzelne Räume können bereits verschoben sein. Die aktualisierte Raumliste prüfen.",
      language: "Sprache", subtitle: "Tab-Ton direkt ins Heimnetz",
      devices: "Raum oder bestehende Gruppe", refresh: "Geräte suchen", manual: "Gerät manuell hinzufügen",
      add: "Hinzufügen", ip: "Sonos-IP-Adresse", source: "Quelle:", currentTab: "Aktueller Tab",
      start: "Auf Sonos abspielen", stop: "Übertragung stoppen", volume: "Lautstärke",
      footer: "Lokal · ohne Konto · mit Audioverzögerung",
      ready: "Bereit", searching: "Suche im Heimnetz …", starting: "Starte …",
      connected: "Verbunden", noDevices: "Keine Geräte gefunden – IP manuell eingeben",
      streamStarting: "Audiostream startet …", streaming: "Übertragung läuft", stopped: "Übertragung beendet",
      noReply: "Keine Antwort", helperDisconnected: "Verbindung zum Helfer beendet",
      helperTimeout: "Helfer antwortet nicht", discoveryWhileStreaming: "Gerätesuche während einer Übertragung nicht möglich",
      alreadyStreaming: "Eine Übertragung läuft bereits", captureFailed: "Audioerfassung fehlgeschlagen",
      unknownCommand: "Unbekannter Befehl", streamTooSlow: "Audioübertragung zu langsam", sourceClosed: "Quell-Tab geschlossen",
      invalidIP: "Bitte eine private IPv4-Adresse des Sonos-Geräts eingeben", notSonos: "Unter dieser Adresse wurde kein Sonos gefunden",
      invalidVolume: "Lautstärke muss zwischen 0 und 100 liegen", noCoordinator: "Sonos-Gruppenkoordinator wurde nicht gefunden",
      noAudio: "Kein Audiosignal vom Browser empfangen", browserDisconnected: "Audioverbindung zum Browser abgebrochen",
      incompleteHeader: "Unvollständiger Nachrichtenkopf", invalidMessageSize: "Ungültige Nachrichtengröße",
      incompleteMessage: "Unvollständige Nachricht", forbiddenExtension: "Nicht erlaubte Erweiterung",
      helperMissing: "Lokaler Helfer nicht gefunden. Bitte zuerst das Windows-Setup ausführen.", nativeExited: "Der lokale Helfer wurde beendet",
      ffmpegExited: "FFmpeg beendet: ", audioInterrupted: "Audioverbindung unterbrochen (HTTP {code})",
      sonosRejected: "Sonos lehnt {action} ab (HTTP {code}). UPnP-Einstellung prüfen. {detail}",
    },
  };
  const aliases = new Map();
  for (const messages of Object.values(strings)) {
    for (const [key, value] of Object.entries(messages)) aliases.set(value, key);
  }
  aliases.set("Übertragung läuft bereits", "alreadyStreaming");
  aliases.set("Specified native messaging host not found.", "helperMissing");
  aliases.set("Native host has exited.", "nativeExited");
  function translate(message, language = "en") {
    const messages = strings[language] || strings.en;
    const key = aliases.get(message) || message;
    if (Object.hasOwn(messages, key)) return messages[key];
    if (typeof message !== "string") return messages.ready;
    if (message.startsWith("groupChangeFailed: ")) return messages.groupChangeFailed + " " + translate(message.slice(19), language);
    const ffmpeg = message.match(/^FFmpeg (?:beendet|exited): (.*)$/s);
    if (ffmpeg) return messages.ffmpegExited + ffmpeg[1];
    const http = message.match(/^(?:Audioverbindung unterbrochen|Audio connection interrupted) \((?:HTTP )?(\d+)\)$/);
    if (http) return messages.audioInterrupted.replace("{code}", http[1]);
    const sonos = message.match(/^Sonos (?:lehnt (.+) ab|rejected (.+)) \(HTTP (\d+)\)\. (?:UPnP-Einstellung prüfen\.|Check the UPnP setting\.) (.*)$/s);
    if (sonos) return messages.sonosRejected.replace("{action}", () => sonos[1] || sonos[2]).replace("{code}", () => sonos[3]).replace("{detail}", () => sonos[4]);
    return message; // Preserve diagnostics from Chrome, the OS, and FFmpeg.
  }
  return {translate};
})();
