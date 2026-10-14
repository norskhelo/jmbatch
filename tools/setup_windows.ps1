$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$environmentPath = Join-Path $projectRoot 'work\venv'
$temporaryPath = Join-Path $projectRoot 'work\builds\python-environment\temp'
$priorTemp = $env:TEMP
$priorTmp = $env:TMP
if (Test-Path -LiteralPath $environmentPath) {
    throw 'work\venv already exists. Check and reuse it manually; this script will not overwrite it.'
}
Push-Location $projectRoot
try {
    New-Item -ItemType Directory -Path $temporaryPath -Force | Out-Null
    $env:TEMP = $temporaryPath
    $env:TMP = $temporaryPath
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    $launcherCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $pythonExecutable = $pythonCommand.Source
        $pythonArguments = @()
        & $pythonExecutable -c 'import struct,sys; sys.exit(0 if sys.version_info[:2] == (3,14) and struct.calcsize("P") == 8 else 1)'
        if ($LASTEXITCODE -ne 0) { $pythonCommand = $null }
    }
    if (-not $pythonCommand) {
        if (-not $launcherCommand) { throw 'Python 3.14 x64 is required; neither a matching python nor py launcher was found.' }
        $pythonExecutable = $launcherCommand.Source
        $pythonArguments = @('-3.14')
    }
    & $pythonExecutable @pythonArguments -m venv $environmentPath
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.14 x64 is required; venv creation failed.' }
    $pythonPath = Join-Path $environmentPath 'Scripts\python.exe'
    & $pythonPath -m pip install -r 'work/jmbatch/requirements.txt' 'pyinstaller==6.22.3' 'pyinstaller-hooks-contrib==2026.8'
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the network and retry manually.' }
    Write-Output 'Python build environment ready. No release was published.'
} finally {
    $env:TEMP = $priorTemp
    $env:TMP = $priorTmp
    Pop-Location
}

