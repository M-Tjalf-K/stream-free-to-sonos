param(
    [ValidatePattern('^[a-p]{32}$')][string]$ExtensionId = 'dpdoiohoioboehbhnnkoogibhgiikigd',
    [string]$HostDirectory,
    [string]$FFmpegPath
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$installRoot = Join-Path $env:LOCALAPPDATA 'SonosTabAudio'
if (!$HostDirectory) {
    $HostDirectory = Join-Path $repoRoot 'helper'
    if (!(Test-Path -LiteralPath (Join-Path $HostDirectory 'sonos-host.exe'))) {
        $HostDirectory = Join-Path $repoRoot 'dist\sonos-host'
    }
}
$HostDirectory = (Resolve-Path -LiteralPath $HostDirectory).Path
$hostExe = Join-Path $HostDirectory 'sonos-host.exe'
if (!(Test-Path -LiteralPath $hostExe) -or !(Test-Path -LiteralPath (Join-Path $HostDirectory '_internal'))) {
    throw 'Standalone helper missing. Use the Windows release ZIP or run scripts/build.ps1 first.'
}
if (Get-Process -Name 'sonos-host' -ErrorAction SilentlyContinue) {
    throw 'Stop streaming and close any running helper before installing or updating.'
}
if (!$FFmpegPath) {
    if (Test-Path -LiteralPath (Join-Path $HostDirectory 'ffmpeg.exe')) { $FFmpegPath = Join-Path $HostDirectory 'ffmpeg.exe' }
    elseif (Test-Path -LiteralPath (Join-Path $installRoot 'ffmpeg.exe')) { $FFmpegPath = Join-Path $installRoot 'ffmpeg.exe' }
    else { throw 'Bundled FFmpeg is missing. Rebuild the package or specify -FFmpegPath.' }
}
$FFmpegPath = (Resolve-Path -LiteralPath $FFmpegPath).Path
$selfTest = & $hostExe --self-test
if ($LASTEXITCODE -ne 0 -or !($selfTest | ConvertFrom-Json).standalone) { throw 'Standalone helper check failed.' }
$encoders = & $FFmpegPath -hide_banner -encoders 2>&1 | Out-String
if ($encoders -notmatch 'libmp3lame') { throw 'FFmpeg must include libmp3lame.' }
New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
Get-ChildItem -LiteralPath $HostDirectory | Copy-Item -Destination $installRoot -Recurse -Force
$extensionDirectory = Join-Path $repoRoot 'extension'
if (Test-Path -LiteralPath $extensionDirectory) {
    Copy-Item -LiteralPath $extensionDirectory -Destination $installRoot -Recurse -Force
}
$installedFFmpeg = Join-Path $installRoot 'ffmpeg.exe'
if ($FFmpegPath -ne $installedFFmpeg) { Copy-Item -LiteralPath $FFmpegPath -Destination $installedFFmpeg -Force }
foreach ($legacyFile in @('host.py', 'python-path.txt')) {
    $legacyPath = Join-Path $installRoot $legacyFile
    if (Test-Path -LiteralPath $legacyPath) { Remove-Item -LiteralPath $legacyPath }
}
$origin = "chrome-extension://$ExtensionId"
$config = @{ origin = $origin } | ConvertTo-Json
[IO.File]::WriteAllText((Join-Path $installRoot 'config.json'), $config)
$launcher = Join-Path $installRoot 'sonos-host.exe'
$manifestPath = Join-Path $installRoot 'de.local.sonos.json'
$manifest = @{ name = 'de.local.sonos'; description = 'Stream to Sonos local audio helper'; path = $launcher; type = 'stdio'; allowed_origins = @("$origin/") } | ConvertTo-Json
[IO.File]::WriteAllText($manifestPath, $manifest)
$registryPath = 'HKCU:\Software\Google\Chrome\NativeMessagingHosts\de.local.sonos'
New-Item -Path $registryPath -Force | Out-Null
Set-Item -Path $registryPath -Value $manifestPath
Write-Host "Installed standalone helper: $installRoot"
Write-Host "In chrome://extensions, load the unpacked extension from: $(Join-Path $installRoot 'extension')"
Write-Host 'Open the Chrome extension and search for devices. Allow helper network access on private networks if Windows asks.'
