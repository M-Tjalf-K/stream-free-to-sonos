param(
    [ValidatePattern('^[a-p]{32}$')][string]$ExtensionId = 'dpdoiohoioboehbhnnkoogibhgiikigd',
    [string]$PythonPath,
    [string]$FFmpegPath
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$installRoot = Join-Path $env:LOCALAPPDATA 'SonosTabAudio'
if (!$PythonPath) { $PythonPath = (Get-Command python -ErrorAction Stop).Source }
if (!$FFmpegPath) { $FFmpegPath = (Get-Command ffmpeg -ErrorAction Stop).Source }
$PythonPath = (Resolve-Path -LiteralPath $PythonPath).Path
$FFmpegPath = (Resolve-Path -LiteralPath $FFmpegPath).Path
& $PythonPath -c 'import sys; assert sys.version_info >= (3, 9), "Python 3.9 oder neuer erforderlich"'
if ($LASTEXITCODE -ne 0) { throw 'Python-Prüfung fehlgeschlagen' }
$encoders = & $FFmpegPath -hide_banner -encoders 2>&1 | Out-String
if ($encoders -notmatch 'libmp3lame') { throw 'FFmpeg benötigt libmp3lame' }
New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $repoRoot 'helper\host.py') -Destination $installRoot -Force
Copy-Item -LiteralPath $FFmpegPath -Destination (Join-Path $installRoot 'ffmpeg.exe') -Force
[IO.File]::WriteAllText((Join-Path $installRoot 'python-path.txt'), $PythonPath)
$origin = "chrome-extension://$ExtensionId"
$config = @{ origin = $origin } | ConvertTo-Json
[IO.File]::WriteAllText((Join-Path $installRoot 'config.json'), $config)
$launcher = Join-Path $installRoot 'sonos-host.exe'
if (Test-Path -LiteralPath $launcher) { Remove-Item -LiteralPath $launcher }
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (!(Test-Path -LiteralPath $compiler)) { $compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe' }
& $compiler /nologo /target:exe "/out:$launcher" (Join-Path $repoRoot 'helper\Launcher.cs')
if ($LASTEXITCODE -ne 0) { throw 'Launcher konnte nicht erstellt werden' }
$manifestPath = Join-Path $installRoot 'de.local.sonos.json'
$manifest = @{ name = 'de.local.sonos'; description = 'Lokaler Sonos-Audiohelfer'; path = $launcher; type = 'stdio'; allowed_origins = @("$origin/") } | ConvertTo-Json
[IO.File]::WriteAllText($manifestPath, $manifest)
$registryPath = 'HKCU:\Software\Google\Chrome\NativeMessagingHosts\de.local.sonos'
New-Item -Path $registryPath -Force | Out-Null
Set-Item -Path $registryPath -Value $manifestPath
Write-Host "Installiert: $installRoot"
Write-Host 'Chrome-Erweiterung oeffnen und Geraete suchen. Falls Windows fragt, Netzwerkzugriff nur im privaten Netz erlauben.'
