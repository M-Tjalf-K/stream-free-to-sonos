#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#define PackageRoot SourcePath + "..\dist\stream-to-sonos-windows-x64"

[Setup]
AppId={{D304486A-340F-4B92-9086-21C45381E31D}
AppName=Stream to Sonos
AppVersion={#AppVersion}
DefaultDirName={localappdata}\SonosTabAudio
DisableDirPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0
DefaultGroupName=Stream to Sonos
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=Stream-to-Sonos-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
LicenseFile=..\LICENSE
UninstallDisplayName=Stream to Sonos (lokaler Helper)

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
SetupAppTitle=Install Wizard
SetupWindowTitle=%1 - Install Wizard

[Files]
Source: "{#PackageRoot}\helper\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PackageRoot}\extension\*"; DestDir: "{app}\extension"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PackageRoot}\readme.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#PackageRoot}\INSTALLATION.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#PackageRoot}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Registry]
Root: HKCU; Subkey: "Software\Google\Chrome\NativeMessagingHosts\de.local.sonos"; ValueType: string; ValueData: "{app}\de.local.sonos.json"; Flags: uninsdeletekey

[Icons]
Name: "{group}\Installationsanleitung"; Filename: "{app}\INSTALLATION.txt"
Name: "{group}\Chrome-Erweiterungsordner"; Filename: "{app}\extension"
Name: "{group}\Deinstallieren"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\INSTALLATION.txt"; Description: "Anleitung zum manuellen Laden der Chrome-Erweiterung anzeigen"; Flags: postinstall shellexec skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\config.json"
Type: files; Name: "{app}\de.local.sonos.json"
Type: files; Name: "{app}\known-devices.json"
Type: files; Name: "{app}\known-devices.tmp"

[Code]
function JsonPath(Value: String): String;
begin
  StringChangeEx(Value, '\', '\\', True);
  StringChangeEx(Value, '"', '\"', True);
  Result := Value;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Origin, Manifest: String;
  ExitCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    if not Exec(ExpandConstant('{app}\sonos-host.exe'), '--self-test', '', SW_HIDE,
      ewWaitUntilTerminated, ExitCode) or (ExitCode <> 0) then
      RaiseException('Der Helper-Selbsttest ist fehlgeschlagen. Bitte Setup erneut ausfuehren.');
    Origin := 'chrome-extension://dpdoiohoioboehbhnnkoogibhgiikigd';
    if not SaveStringToFile(ExpandConstant('{app}\config.json'),
      '{"origin":"' + Origin + '"}', False) then
      RaiseException('Konfiguration konnte nicht gespeichert werden.');
    Manifest := '{"name":"de.local.sonos","description":"Stream to Sonos local audio helper",' +
      '"path":"' + JsonPath(ExpandConstant('{app}\sonos-host.exe')) + '",' +
      '"type":"stdio","allowed_origins":["' + Origin + '/"]}';
    if not SaveStringToFile(ExpandConstant('{app}\de.local.sonos.json'), UTF8Encode(Manifest), False) then
      RaiseException('Chrome-Registrierung konnte nicht gespeichert werden.');
  end;
end;
