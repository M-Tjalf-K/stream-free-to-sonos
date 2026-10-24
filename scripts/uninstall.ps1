$ErrorActionPreference = 'Stop'
$setupUninstaller = Join-Path $env:LOCALAPPDATA 'SonosTabAudio\unins000.exe'
if (Test-Path -LiteralPath $setupUninstaller) {
    # Keep Windows' installed-app entry consistent when setup owns the files.
    & $setupUninstaller
    return
}
$registryPath = 'HKCU:\Software\Google\Chrome\NativeMessagingHosts\de.local.sonos'
if (Test-Path $registryPath) { Remove-Item -LiteralPath $registryPath }
$installRoot = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'SonosTabAudio'))
$expectedParent = [IO.Path]::GetFullPath($env:LOCALAPPDATA).TrimEnd('\')
if ((Split-Path $installRoot -Parent) -ne $expectedParent -or (Split-Path $installRoot -Leaf) -ne 'SonosTabAudio') { throw 'Unerwarteter Installationspfad' }
if (Test-Path -LiteralPath $installRoot) { Remove-Item -LiteralPath $installRoot -Recurse }
Write-Host 'Helfer entfernt. Die Erweiterung kann separat in Chrome entfernt werden.'
