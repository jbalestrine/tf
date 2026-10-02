$ErrorActionPreference = 'Stop'

$packageName = 'masterchief'
$toolsDir = "$(Split-Path -parent $MyInvocation.MyCommand.Definition)"
$installDir = Join-Path $env:ChocolateyInstall 'lib\masterchief\masterchief'

# Package version
$packageVersion = $env:ChocolateyPackageVersion
if (-not $packageVersion) { $packageVersion = 'main' }

$zipUrl = '__MASTERCHIEF_ARCHIVE_URL__'
$zipChecksum = '__MASTERCHIEF_ARCHIVE_SHA256__'

Write-Host "Installing MasterChief DevOps Platform v$packageVersion..."

# Verify Python 3.10+ is available
Write-Host "Checking Python installation..."
$pythonCmd = $null
foreach ($cmd in @('python3', 'python', 'py -3')) {
    try {
        $version = & $cmd.Split()[0] ($cmd.Split() | Select-Object -Skip 1) --version 2>&1
        if ($version -match 'Python (\d+)\.(\d+)') {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -ge 3 -and $minor -ge 10) {
                $pythonCmd = $cmd
                Write-Host "Found $version"
                break
            }
        }
    } catch {
        continue
    }
}

if (-not $pythonCmd) {
    throw "Python 3.10 or higher is required but was not found. Please install Python first: choco install python"
}

# Create installation directory
if (-not (Test-Path $installDir)) {
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
}

# Download and extract the package
$zipFile = Join-Path $env:TEMP 'masterchief.zip'
Get-ChocolateyWebFile -PackageName $packageName -FileFullPath $zipFile -Url $zipUrl -Checksum $zipChecksum -ChecksumType 'sha256'

# Extract to installation directory
Get-ChocolateyUnzip -FileFullPath $zipFile -Destination $installDir

# Find the extracted folder (it will be masterchief-main)
$extractedDir = Get-ChildItem -Path $installDir -Directory | Where-Object { $_.Name -like 'masterchief-*' } | Select-Object -First 1

if ($extractedDir) {
    # Move contents up one level
    Get-ChildItem -Path $extractedDir.FullName | Move-Item -Destination $installDir -Force
    Remove-Item -Path $extractedDir.FullName -Recurse -Force
}

# Install Python dependencies
Write-Host "Installing Python dependencies..."
$requirementsFile = Join-Path $installDir 'requirements.txt'
if (Test-Path $requirementsFile) {
    & $pythonCmd.Split()[0] ($pythonCmd.Split() | Select-Object -Skip 1) -m pip install -r $requirementsFile --quiet
}

# Install the package in development mode
Write-Host "Installing MasterChief package..."
Push-Location $installDir
try {
    & $pythonCmd.Split()[0] ($pythonCmd.Split() | Select-Object -Skip 1) -m pip install -e . --quiet
} finally {
    Pop-Location
}

# Store the Python command used for uninstall
$pythonPathFile = Join-Path $installDir '.python_cmd'
Set-Content -Path $pythonPathFile -Value $pythonCmd -Encoding ASCII

# Create shim for masterchief command (uses the entry point from setup.py)
$shimSource = @"
@echo off
masterchief %*
"@
$shimPath = Join-Path $env:ChocolateyInstall 'bin\masterchief.cmd'
Set-Content -Path $shimPath -Value $shimSource -Encoding ASCII

Write-Host "MasterChief has been installed successfully!"
Write-Host "Run 'masterchief --help' to get started."
