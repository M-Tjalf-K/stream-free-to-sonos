param([string]$PythonPath, [string]$ISCCPath, [string]$FFmpegDirectory)
$ErrorActionPreference = 'Stop'
function Invoke-BuildCommand([string]$Executable, [string[]]$Arguments) {
    $previousPreference = $ErrorActionPreference
    try {
        # PowerShell 5 otherwise treats redirected native progress on stderr as fatal.
        $ErrorActionPreference = 'Continue'
        & $Executable @Arguments 2>&1 | ForEach-Object { Write-Host $_.ToString() }
        $commandExitCode = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousPreference }
    if ($commandExitCode -ne 0) { throw "Build command failed with exit code $commandExitCode" }
}
$repoRoot = Split-Path $PSScriptRoot -Parent
if (!$FFmpegDirectory) { $FFmpegDirectory = Join-Path $repoRoot 'build\ffmpeg' }
foreach ($name in @('ffmpeg.exe', 'ffmpeg-sources.zip', 'FFMPEG-LICENSE.txt', 'LAME-LICENSE.txt', 'MINGW-RUNTIME-LICENSE.txt', 'FFMPEG-NOTICES.txt', 'FFMPEG-BUILD.txt')) {
    if (!(Test-Path -LiteralPath (Join-Path $FFmpegDirectory $name))) {
        throw "Bundled FFmpeg file missing: $name. See the FFmpeg build instructions in readme.md."
    }
}
$ffmpegVersion = & (Join-Path $FFmpegDirectory 'ffmpeg.exe') -version | Out-String
if ($LASTEXITCODE -ne 0 -or $ffmpegVersion -notmatch '^ffmpeg version 8\.1\.3 ' -or $ffmpegVersion -match '--enable-(gpl|nonfree)' -or $ffmpegVersion -notmatch '--enable-libmp3lame') {
    throw 'Expected the pinned LGPL FFmpeg 8.1.3 build with libmp3lame.'
}
if (!$ISCCPath) {
    $compiler = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($compiler) { $ISCCPath = $compiler.Source }
    else {
        foreach ($candidate in @((Join-Path $repoRoot 'build\inno-current\{app}\ISCC.exe'), "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe")) {
            if (Test-Path -LiteralPath $candidate) { $ISCCPath = $candidate; break }
        }
    }
}
if (!$ISCCPath) { throw 'Inno Setup 6.7.3+ is required to build the installer. Specify -ISCCPath.' }
if (!$PythonPath) {
    $venvPython = Join-Path $repoRoot '.venv-build\Scripts\python.exe'
    if (Test-Path -LiteralPath $venvPython) { $PythonPath = $venvPython }
    else { $PythonPath = (Get-Command python -ErrorAction Stop).Source }
}
$PythonPath = (Resolve-Path -LiteralPath $PythonPath).Path
& $PythonPath -c "import sys, struct; assert sys.platform == 'win32' and struct.calcsize('P') == 8 and sys.version_info >= (3, 12), '64-bit Windows Python 3.12+ is required'"
if ($LASTEXITCODE -ne 0) { throw 'Build platform check failed.' }
Invoke-BuildCommand $PythonPath @('-m', 'pip', 'install', '-r', (Join-Path $repoRoot 'requirements-build.txt'))
$distRoot = Join-Path $repoRoot 'dist'
$workRoot = Join-Path $repoRoot 'build'
New-Item -ItemType Directory -Path $workRoot -Force | Out-Null
Invoke-BuildCommand $PythonPath @('-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--console', '--noupx', '--name', 'sonos-host', '--distpath', $distRoot, '--workpath', $workRoot, '--specpath', $workRoot, (Join-Path $repoRoot 'helper\host.py'))
$bundle = Join-Path $distRoot 'sonos-host'
Get-ChildItem -LiteralPath $FFmpegDirectory -File | Copy-Item -Destination $bundle -Force
& (Join-Path $bundle 'sonos-host.exe') --self-test
if ($LASTEXITCODE -ne 0) { throw 'Standalone helper self-test failed.' }
& $PythonPath (Join-Path $PSScriptRoot 'collect_licenses.py') $bundle
if ($LASTEXITCODE -ne 0) { throw 'Runtime license collection failed.' }
$packageRoot = [IO.Path]::GetFullPath((Join-Path $distRoot 'stream-to-sonos-windows-x64'))
if ((Split-Path $packageRoot -Parent) -ne [IO.Path]::GetFullPath($distRoot) -or (Split-Path $packageRoot -Leaf) -ne 'stream-to-sonos-windows-x64') { throw 'Unexpected package directory.' }
if (Test-Path -LiteralPath $packageRoot) { Remove-Item -LiteralPath $packageRoot -Recurse -Force }
New-Item -ItemType Directory -Path $packageRoot -Force | Out-Null
Copy-Item -LiteralPath $bundle -Destination (Join-Path $packageRoot 'helper') -Recurse
Copy-Item -LiteralPath (Join-Path $repoRoot 'extension') -Destination $packageRoot -Recurse
New-Item -ItemType Directory -Path (Join-Path $packageRoot 'scripts') | Out-Null
foreach ($name in @('install.ps1', 'uninstall.ps1')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $packageRoot 'scripts')
}
foreach ($name in @('readme.md', 'INSTALLATION.txt', 'LICENSE')) { Copy-Item -LiteralPath (Join-Path $repoRoot $name) -Destination $packageRoot }
$zip = Join-Path $distRoot 'stream-to-sonos-windows-x64.zip'
& $PythonPath (Join-Path $PSScriptRoot 'package.py') $packageRoot $zip
if ($LASTEXITCODE -ne 0) { throw 'Release ZIP creation failed.' }
Write-Host "Release package: $zip"
$version = (Get-Content -LiteralPath (Join-Path $repoRoot 'extension\manifest.json') -Raw | ConvertFrom-Json).version
Invoke-BuildCommand $ISCCPath @("/DAppVersion=$version", (Join-Path $PSScriptRoot 'setup.iss'))
Copy-Item -LiteralPath (Join-Path $FFmpegDirectory 'ffmpeg-sources.zip') -Destination $distRoot -Force
$artifacts = @('Stream-to-Sonos-Setup.exe', 'stream-to-sonos-windows-x64.zip', 'ffmpeg-sources.zip')
$checksums = foreach ($name in $artifacts) { "$( (Get-FileHash -LiteralPath (Join-Path $distRoot $name) -Algorithm SHA256).Hash.ToLower() )  $name" }
[IO.File]::WriteAllLines((Join-Path $distRoot 'SHA256SUMS.txt'), $checksums)
Write-Host "Windows setup: $(Join-Path $distRoot 'Stream-to-Sonos-Setup.exe')"
