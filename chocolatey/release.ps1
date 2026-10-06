[CmdletBinding()]
param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot 'dist'),
    [string]$SourceRef,
    [string]$PackageVersion,
    [switch]$Push
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$packageName = 'masterchief'
$packageSource = 'https://push.chocolatey.org/'

if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
    throw 'Chocolatey CLI (choco) is required to build the package.'
}

if ($Push -and -not $env:CHOCOLATEY_API_KEY) {
    throw 'Set CHOCOLATEY_API_KEY in the environment before using -Push.'
}

$setupContent = Get-Content (Join-Path $repositoryRoot 'setup.py') -Raw
if (-not $PackageVersion) {
    if ($setupContent -notmatch 'version="([^"]+)"') {
        throw 'Could not read the package version from setup.py.'
    }
    $PackageVersion = $Matches[1]
}
if ($PackageVersion -notmatch '^\d+\.\d+\.\d+$') {
    throw "Invalid Chocolatey package version: $PackageVersion"
}
$packageVersion = $PackageVersion

if (-not $SourceRef) {
    $SourceRef = git -C $repositoryRoot describe --tags --exact-match HEAD 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $SourceRef) {
        $SourceRef = git -C $repositoryRoot rev-parse HEAD
        if ($LASTEXITCODE -ne 0 -or -not $SourceRef) {
            throw 'Could not determine a Git tag or commit for the source archive.'
        }
    }
}

if ($SourceRef -match '^v') {
    $archiveUrl = "https://github.com/jbalestrine/masterchief/archive/refs/tags/$SourceRef.zip"
} else {
    $archiveUrl = "https://github.com/jbalestrine/masterchief/archive/$SourceRef.zip"
}

if (-not [System.IO.Path]::IsPathRooted($OutputDirectory)) {
    $OutputDirectory = Join-Path $repositoryRoot $OutputDirectory
}
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

$stagingDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("masterchief-choco-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stagingDirectory -Force | Out-Null

try {
    $toolsDirectory = Join-Path $stagingDirectory 'tools'
    New-Item -ItemType Directory -Path $toolsDirectory -Force | Out-Null
    Copy-Item (Join-Path $PSScriptRoot 'masterchief.nuspec') $stagingDirectory
    Copy-Item (Join-Path $PSScriptRoot 'tools\*') $toolsDirectory -Recurse -Force

    $archivePath = Join-Path $stagingDirectory 'masterchief-source.zip'
    Invoke-WebRequest -Uri $archiveUrl -OutFile $archivePath -UseBasicParsing
    $archiveChecksum = (Get-FileHash -Path $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()

    $nuspecPath = Join-Path $stagingDirectory 'masterchief.nuspec'
    $nuspecContent = Get-Content $nuspecPath -Raw
    $nuspecContent = [regex]::Replace($nuspecContent, '<version>[^<]+</version>', "<version>$packageVersion</version>")
    Set-Content -Path $nuspecPath -Value $nuspecContent -Encoding UTF8

    $installPath = Join-Path $toolsDirectory 'chocolateyinstall.ps1'
    $installContent = Get-Content $installPath -Raw
    $installContent = $installContent.Replace('__MASTERCHIEF_ARCHIVE_URL__', $archiveUrl)
    $installContent = $installContent.Replace('__MASTERCHIEF_ARCHIVE_SHA256__', $archiveChecksum)
    Set-Content -Path $installPath -Value $installContent -Encoding UTF8

    Push-Location $stagingDirectory
    try {
        & choco pack 'masterchief.nuspec' --outputdirectory $OutputDirectory
        if ($LASTEXITCODE -ne 0) {
            throw "choco pack failed with exit code $LASTEXITCODE."
        }
    } finally {
        Pop-Location
    }

    $packagePath = Join-Path $OutputDirectory "$packageName.$packageVersion.nupkg"
    if (-not (Test-Path $packagePath)) {
        throw "Chocolatey package was not created at $packagePath."
    }
    Write-Host "Built $packagePath from $SourceRef (SHA-256 $archiveChecksum)."

    if ($Push) {
        & choco push $packagePath --source $packageSource "--api-key=$($env:CHOCOLATEY_API_KEY)"
        if ($LASTEXITCODE -ne 0) {
            throw "Chocolatey push failed with exit code $LASTEXITCODE. Check the API key and package version on Chocolatey.org."
        }
        Write-Host "Published $packageName $packageVersion to Chocolatey Community Repository."
    }
} finally {
    Remove-Item -Path $stagingDirectory -Recurse -Force -ErrorAction SilentlyContinue
}