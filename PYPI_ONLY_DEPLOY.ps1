[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^v\d+\.\d+\.\d+$')]
    [string]$Tag,
    [string]$PythonPath,
    [switch]$UseVault,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$buildRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("masterchief-pypi-" + [guid]::NewGuid().ToString('N'))
$vaultHelperPath = Join-Path $buildRoot 'read_vault.py'
$originalTwineUsername = [Environment]::GetEnvironmentVariable('TWINE_USERNAME', 'Process')
$originalTwinePassword = [Environment]::GetEnvironmentVariable('TWINE_PASSWORD', 'Process')
$loadedVaultPassword = $false

function Invoke-NativeLogged {
    param(
        [string]$Executable,
        [string[]]$Arguments,
        [string]$LogPath
    )

    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Executable @Arguments *> $LogPath
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorAction
    }

    if ($exitCode -ne 0) {
        Get-Content -LiteralPath $LogPath -Tail 40
        throw "$Executable failed with exit code $exitCode."
    }
}

function Get-VaultPassword {
    param([string]$PythonExecutable)

    $pythonCode = @'
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root))
from managers.vault import VaultManager

vault = VaultManager(
    root / "data/vault.json",
    root / "data/vault.key",
    root / "data/vault_audit.json",
)
secret = next(
    (item for item in vault.list_secrets() if item.get("name") == "TWINE_PASSWORD"),
    None,
)
if secret is None:
    raise SystemExit("Vault secret not found: TWINE_PASSWORD")
sys.stdout.write(vault.get_secret(secret["id"], user="package-deploy")["value"])
'@
    [System.IO.File]::WriteAllText($vaultHelperPath, $pythonCode, [System.Text.UTF8Encoding]::new($false))
    $value = & $PythonExecutable $vaultHelperPath $repositoryRoot 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $value) {
        throw "Could not read Vault secret 'TWINE_PASSWORD'. Add it in /secrets and retry."
    }
    return [string]$value
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'Git is required.'
}

if (-not $PythonPath) {
    $venvCandidates = @(
        (Join-Path $repositoryRoot '.venv\Scripts\python.exe'),
        (Join-Path $repositoryRoot 'venv\Scripts\python.exe'),
        (Join-Path $repositoryRoot 'venv310\Scripts\python.exe')
    )
    $PythonPath = $venvCandidates |
        Where-Object { Test-Path -LiteralPath $_ } |
        Select-Object -First 1
    if (-not $PythonPath) {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if ($pythonCommand) {
            $PythonPath = $pythonCommand.Source
        } else {
            throw 'Python 3.10 or newer is required. Set -PythonPath to its executable.'
        }
    }
}
if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "Python executable not found: $PythonPath"
}

$tagCommit = git -C $repositoryRoot rev-parse "$Tag^{commit}"
if ($LASTEXITCODE -ne 0 -or -not $tagCommit) {
    throw "Release tag not found locally: $Tag. Fetch tags and retry."
}

$tagDescription = git -C $repositoryRoot describe --tags --exact-match $tagCommit
if ($LASTEXITCODE -ne 0 -or $tagDescription -ne $Tag) {
    throw "$Tag must be an exact tag on its target commit."
}

$worktreeChanges = @(git -C $repositoryRoot status --porcelain)
if ($worktreeChanges.Count -gt 0) {
    Write-Warning 'Uncommitted changes exist and will not be included. The deployment is built from the exact tag only.'
}

New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null
try {
    $archivePath = Join-Path $buildRoot 'source.zip'
    & git -C $repositoryRoot archive --format=zip "--output=$archivePath" $Tag
    if ($LASTEXITCODE -ne 0) {
        throw "Could not archive tagged source $Tag."
    }

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
    if ($setupContents -notmatch 'version="([^"]+)"') {
        throw 'Could not read package version from tagged setup.py.'
    }
    $packageVersion = $Matches[1]
    if ($packageVersion -notmatch '^\d+\.\d+\.\d+$') {
        throw "Invalid package version: $packageVersion"
    }
    if ($Tag -ne "v$packageVersion") {
        throw "Tag $Tag does not match package version $packageVersion."
    }

    try {
        $null = Invoke-WebRequest -Uri "https://pypi.org/pypi/masterchief/$packageVersion/json" -UseBasicParsing
        throw "PyPI version $packageVersion already exists; published releases are immutable."
    } catch {
        if ($_.Exception.Message -like 'PyPI version * already exists*') {
            throw
        }
        $statusCode = 0
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            $statusCode = [int]$_.Exception.Response.StatusCode
        }
        if ($statusCode -ne 404) {
            throw "Could not verify PyPI version availability: $($_.Exception.Message)"
        }
    }

    if (-not $DryRun -and -not $env:TWINE_PASSWORD) {
        if (-not $UseVault) {
            throw 'Set TWINE_PASSWORD or pass -UseVault to read it from the application Vault.'
        }
        $env:TWINE_PASSWORD = Get-VaultPassword $PythonPath
        $loadedVaultPassword = $true
    }

    $pythonDist = Join-Path $buildRoot 'dist'
    New-Item -ItemType Directory -Path $pythonDist -Force | Out-Null
    $buildLog = Join-Path $buildRoot 'build.log'
    Push-Location $sourceRoot
    try {
        Invoke-NativeLogged $PythonPath @('-m', 'build', '--outdir', $pythonDist) $buildLog
    } finally {
        Pop-Location
    }

    $artifacts = @(Get-ChildItem -LiteralPath $pythonDist -File)
    if ($artifacts.Count -ne 2) {
        throw "Expected a wheel and source distribution; found $($artifacts.Count) PyPI artifacts."
    }

    $checkLog = Join-Path $buildRoot 'twine-check.log'
    Invoke-NativeLogged $PythonPath (@('-m', 'twine', 'check') + @($artifacts | ForEach-Object { $_.FullName })) $checkLog
    Get-Content -LiteralPath $checkLog
    Write-Host "Validated masterchief $packageVersion from tag $Tag."

    if ($DryRun) {
        Write-Host 'Dry run complete; no files were uploaded.' -ForegroundColor Cyan
        return
    }

    $env:TWINE_USERNAME = '__token__'
    $uploadLog = Join-Path $buildRoot 'upload.log'
    Invoke-NativeLogged $PythonPath (@(
        '-m', 'twine', 'upload', '--non-interactive',
        '--repository-url', 'https://upload.pypi.org/legacy/'
    ) + @($artifacts | ForEach-Object { $_.FullName })) $uploadLog
    Get-Content -LiteralPath $uploadLog
    Write-Host "Published masterchief $packageVersion to PyPI only." -ForegroundColor Green
} catch {
    Write-Error $_
    throw 'PyPI-only deployment stopped. If upload started, check the PyPI project page before retrying.'
} finally {
    if ($loadedVaultPassword) {
        [Environment]::SetEnvironmentVariable('TWINE_PASSWORD', $null, 'Process')
    }
    [Environment]::SetEnvironmentVariable('TWINE_USERNAME', $originalTwineUsername, 'Process')
    if (Test-Path -LiteralPath $buildRoot) {
        Remove-Item -LiteralPath $buildRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
