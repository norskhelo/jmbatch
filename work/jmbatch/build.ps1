param(
    [string]$RunId = '',
    [string]$BuildDir = ''
)
$ErrorActionPreference = 'Stop'
$workRoot = Split-Path -Parent $PSScriptRoot
$projectRoot = Split-Path -Parent $workRoot
$pythonExe = Join-Path $workRoot 'venv/Scripts/python.exe'
$checker = Join-Path $workRoot 'scripts/maintenance/check_development.py'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw 'Run tools/setup_windows.ps1 from the project root to create work/venv first.'
}
$versionMatch = [regex]::Match((Get-Content -LiteralPath (Join-Path $PSScriptRoot 'core.py') -Raw), '(?m)^VERSION\s*=\s*[''"](\d+\.\d+\.\d+)[''"]')
if (-not $versionMatch.Success) { throw 'Cannot read the Windows application version.' }
$version = $versionMatch.Groups[1].Value
if (-not $BuildDir) { $BuildDir = Join-Path $workRoot "builds/windows-$version" }
$arguments = @($checker, 'windows', '--build-dir', $BuildDir)
if ($RunId) { $arguments += @('--run-id', $RunId) }
Push-Location -LiteralPath $projectRoot
try {
    & $pythonExe @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Windows checks or build failed; see outputs/reports/<run-id>.' }
} finally { Pop-Location }
Write-Output "Built and self-tested: $BuildDir/dist/JMBatch/JMBatch.exe"
Write-Output 'Use work/package_network_update.py for signed local delivery into Win/<version>.'
