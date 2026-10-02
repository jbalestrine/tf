[CmdletBinding()]
param(
    [switch]$InstallOptional,
    [switch]$DownloadModel,
    [switch]$SetupOnly,
    [int]$Port = 8084
)

$ErrorActionPreference = 'Stop'
$repoDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$venvDir = Join-Path $repoDir '.venv'
$venvPython = Join-Path $venvDir 'Scripts\python.exe'

if (-not (Test-Path $venvPython)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $pythonCommand = 'py'
        $pythonArguments = @('-3')
    } elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
        $pythonCommand = 'python3'
        $pythonArguments = @()
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $pythonCommand = 'python'
        $pythonArguments = @()
    } else {
        throw 'Python 3.10 or newer is required. Install Python and rerun MasterchiefRun.ps1.'
    }

    $pythonVersion = & $pythonCommand @pythonArguments --version
    if ($pythonVersion -notmatch 'Python 3\.(\d+)' -or [int]$Matches[1] -lt 10) {
        throw "Python 3.10 or newer is required. Found: $pythonVersion"
    }

    Write-Host 'Creating the project virtual environment...'
    & $pythonCommand @pythonArguments -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the virtual environment.' }
}

Write-Host 'Installing base requirements and the source package...'
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Could not upgrade pip.' }
& $venvPython -m pip install -r (Join-Path $repoDir 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Could not install requirements.txt.' }
& $venvPython -m pip install -e $repoDir
if ($LASTEXITCODE -ne 0) { throw 'Could not install MasterChief from the source checkout.' }

if ($InstallOptional -or $DownloadModel) {
    Write-Host 'Installing optional AI, audio, and integration requirements...'
    & $venvPython -m pip install -r (Join-Path $repoDir 'requirements-optional.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Could not install requirements-optional.txt.' }
}

$envFile = Join-Path $repoDir '.env'
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), 'Process')
        }
    }
}

if ($DownloadModel) {
    $modelsDir = Join-Path $repoDir 'models'
    $modelPath = Join-Path $modelsDir 'mistral-7b-instruct-v0.1.Q4_K_M.gguf'
    $modelUrl = 'https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.1-GGUF/resolve/main/mistral-7b-instruct-v0.1.Q4_K_M.gguf?download=true'
    New-Item -ItemType Directory -Path $modelsDir -Force | Out-Null
    if (-not (Test-Path $modelPath)) {
        Write-Host 'Downloading the optional GGUF model; this is a large download...'
        Invoke-WebRequest -Uri $modelUrl -OutFile "$modelPath.download" -UseBasicParsing
        Move-Item "$modelPath.download" $modelPath -Force
    }
}

if ($SetupOnly) {
    Write-Host 'Setup complete. Run .\.venv\Scripts\python.exe main.py to start MasterChief.'
    exit 0
}

Write-Host "Starting MasterChief on port $Port..."
Push-Location $repoDir
try {
    & $venvPython (Join-Path $repoDir 'main.py') --port $Port
    if ($LASTEXITCODE -ne 0) { throw "MasterChief exited with code $LASTEXITCODE." }
} finally {
    Pop-Location
}