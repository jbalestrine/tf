[CmdletBinding()]
param(
    [string]$PythonPath,
    [string]$PyPIRepositoryUrl = 'https://upload.pypi.org/legacy/',
    [string]$ChocolateySource = 'https://push.chocolatey.org/',
    [switch]$UseVault,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$chocoBuilder = Join-Path $repositoryRoot 'chocolatey\release.ps1'
$buildRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("masterchief-dual-release-" + [guid]::NewGuid().ToString('N'))
$loadedVaultSecretNames = @()

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Executable @Arguments
    } finally {
        $ErrorActionPreference = $previousErrorAction
    }
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable failed with exit code $LASTEXITCODE."
    }
}

function Get-StatusCode {
    param($ErrorRecord)
    if ($ErrorRecord.Exception.Response -and $ErrorRecord.Exception.Response.StatusCode) {
        return [int]$ErrorRecord.Exception.Response.StatusCode
    }
    return 0
}

function Get-VaultSecretValue {
    param([string]$Name)

    $pythonCode = @'
import sys
from pathlib import Path
from managers.vault import VaultManager

root = Path(sys.argv[1])
name = sys.argv[2]
vault = VaultManager(root / "data/vault.json", root / "data/vault.key", root / "data/vault_audit.json")
secret = next((item for item in vault.list_secrets() if item.get("name") == name), None)
if secret is None:
    raise SystemExit(f"Vault secret not found: {name}")
sys.stdout.write(vault.get_secret(secret["id"], user="package-deploy")["value"])
'@
    $value = & $PythonPath -c $pythonCode $repositoryRoot $Name 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $value) {
        throw "Could not read Vault secret '$Name'. Add it in /secrets and retry."
    }
    return [string]$value
}

if (-not $PythonPath) {
    $venvPython = Join-Path $repositoryRoot '.venv\Scripts\python.exe'
    if (Test-Path $venvPython) {
        $PythonPath = $venvPython
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        $PythonPath = (Get-Command py).Source
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $PythonPath = (Get-Command python).Source
    } else {
        throw 'Python 3.10 or newer is required.'
    }
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git is required.' }
if (-not (Get-Command choco -ErrorAction SilentlyContinue)) { throw 'Chocolatey CLI is required.' }
if (-not (Test-Path $chocoBuilder)) { throw "Missing Chocolatey builder: $chocoBuilder" }

$releaseTag = git -C $repositoryRoot describe --tags --exact-match HEAD 2>$null
if ($LASTEXITCODE -ne 0 -or -not $releaseTag -or $releaseTag -notmatch '^v\d+\.\d+\.\d+$') {
    throw 'Deploy from a commit with an exact semantic v* release tag at HEAD. Uncommitted source changes are not deployed.'
}

$worktreeChanges = @(git -C $repositoryRoot status --porcelain)
if ($worktreeChanges.Count -gt 0) {
    Write-Warning 'Uncommitted changes exist and will not be included. The deployment is built from the exact tag only.'
}

New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null
try {
    $archivePath = Join-Path $buildRoot 'source.zip'
    Invoke-Checked 'git' @('-C', $repositoryRoot, 'archive', '--format=zip', "--output=$archivePath", $releaseTag)
    $sourceDirectory = Join-Path $buildRoot 'source'
    Expand-Archive -LiteralPath $archivePath -DestinationPath $sourceDirectory -Force
    $sourceRoot = $sourceDirectory
    if (-not (Test-Path (Join-Path $sourceRoot 'setup.py'))) {
        $sourceRoot = Get-ChildItem -LiteralPath $sourceDirectory -Directory |
            Where-Object { Test-Path (Join-Path $_.FullName 'setup.py') } |
            Select-Object -First 1 -ExpandProperty FullName
    }
    if (-not $sourceRoot -or -not (Test-Path (Join-Path $sourceRoot 'setup.py'))) {
        throw 'Could not locate setup.py in the tagged source archive.'
    }

    $setupContents = Get-Content (Join-Path $sourceRoot 'setup.py') -Raw
    if ($setupContents -notmatch 'version="([^"]+)"') { throw 'Could not read package version from tagged setup.py.' }
    $packageVersion = $Matches[1]
    if ($packageVersion -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid package version: $packageVersion" }

    try {
        $null = Invoke-WebRequest -Uri "https://pypi.org/pypi/masterchief/$packageVersion/json" -UseBasicParsing
        throw "PyPI version $packageVersion already exists; published releases are immutable."
    } catch {
        if ($_.Exception.Message -like 'PyPI version * already exists*') { throw }
        if ((Get-StatusCode $_) -ne 404) { throw "Could not verify PyPI version availability: $($_.Exception.Message)" }
    }

    $chocoVersionUrl = "https://community.chocolatey.org/api/v2/Packages(Id='masterchief',Version='$packageVersion')"
    try {
        $null = Invoke-WebRequest -Uri $chocoVersionUrl -UseBasicParsing
        throw "Chocolatey version $packageVersion already exists; package versions are immutable."
    } catch {
        if ($_.Exception.Message -like 'Chocolatey version * already exists*') { throw }
        if ((Get-StatusCode $_) -ne 404) { throw "Could not verify Chocolatey version availability: $($_.Exception.Message)" }
    }

    if (-not $DryRun) {
        if ($UseVault) {
            if (-not $env:TWINE_PASSWORD) {
                $env:TWINE_PASSWORD = Get-VaultSecretValue 'TWINE_PASSWORD'
                $loadedVaultSecretNames += 'TWINE_PASSWORD'
            }
            if (-not $env:CHOCOLATEY_API_KEY) {
                $env:CHOCOLATEY_API_KEY = Get-VaultSecretValue 'CHOCOLATEY_API_KEY'
                $loadedVaultSecretNames += 'CHOCOLATEY_API_KEY'
            }
        }
        if (-not $env:TWINE_PASSWORD) { throw 'Set TWINE_PASSWORD in this PowerShell process before publishing.' }
        if (-not $env:CHOCOLATEY_API_KEY) { throw 'Set CHOCOLATEY_API_KEY in this PowerShell process before publishing.' }
    }

    if (-not (Get-Command choco -ErrorAction SilentlyContinue)) { throw 'Chocolatey CLI is required to build the .nupkg.' }
    Invoke-Checked $PythonPath @('-m', 'pip', 'install', '--disable-pip-version-check', 'build', 'twine')

    $pythonDist = Join-Path $buildRoot 'pypi-dist'
    New-Item -ItemType Directory -Path $pythonDist -Force | Out-Null
    Push-Location $sourceRoot
    try {
        Invoke-Checked $PythonPath @('-m', 'build', '--outdir', $pythonDist)
    } finally {
        Pop-Location
    }
    $pythonArtifacts = @(Get-ChildItem -LiteralPath $pythonDist -File)
    if ($pythonArtifacts.Count -ne 2) { throw "Expected wheel and sdist; found $($pythonArtifacts.Count) PyPI artifacts." }
    Invoke-Checked $PythonPath (@('-m', 'twine', 'check') + @($pythonArtifacts | ForEach-Object { $_.FullName }))

    $chocoDist = Join-Path $buildRoot 'chocolatey-dist'
    & (Join-Path $sourceRoot 'chocolatey\release.ps1') -SourceRef $releaseTag -OutputDirectory $chocoDist
    if ($LASTEXITCODE -ne 0) { throw 'Chocolatey package build failed.' }
    $chocoPackage = Join-Path $chocoDist "masterchief.$packageVersion.nupkg"
    if (-not (Test-Path $chocoPackage)) { throw "Chocolatey artifact not found: $chocoPackage" }

    Write-Host "Validated release $releaseTag / masterchief $packageVersion."
    Write-Host "PyPI artifacts: $pythonDist"
    Write-Host "Chocolatey artifact: $chocoPackage"
    if ($DryRun) {
        Write-Host 'Dry run complete; no packages were uploaded.' -ForegroundColor Cyan
        return
    }

    $env:TWINE_USERNAME = '__token__'
    Write-Host 'Uploading to PyPI...'
    Invoke-Checked $PythonPath (@('-m', 'twine', 'upload', '--non-interactive', '--repository-url', $PyPIRepositoryUrl) + @($pythonArtifacts | ForEach-Object { $_.FullName }))

    Write-Host 'Uploading to Chocolatey...'
    $chocoArguments = @('push', $chocoPackage, '--source', $ChocolateySource, "--api-key=$($env:CHOCOLATEY_API_KEY)")
    Invoke-Checked 'choco' $chocoArguments

    Write-Host "Published masterchief $packageVersion to PyPI and Chocolatey." -ForegroundColor Green
} catch {
    Write-Error $_
    throw 'Combined deployment stopped. If the first registry accepted its upload, that release cannot be rolled back; check both package pages before retrying.'
} finally {
    foreach ($secretName in $loadedVaultSecretNames) {
        [Environment]::SetEnvironmentVariable($secretName, $null, 'Process')
    }
    Remove-Item -LiteralPath $buildRoot -Recurse -Force -ErrorAction SilentlyContinue
}