[CmdletBinding()]
param([int]$Port = 8080)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$sourceRunner = Join-Path $repoRoot 'MasterchiefRun.ps1'
$sourcePython = Join-Path $repoRoot '.venv\Scripts\python.exe'

function Get-PowerShellExecutable {
    if ($PSVersionTable.PSEdition -eq 'Core') {
        return (Join-Path $PSHOME 'pwsh.exe')
    }
    return (Join-Path $PSHOME 'powershell.exe')
}

function Invoke-SourceRunner {
    param([string[]]$RunnerArguments)

    if (-not (Test-Path $sourceRunner)) {
        throw "Missing source setup script: $sourceRunner"
    }

    $engine = Get-PowerShellExecutable
    & $engine -NoProfile -ExecutionPolicy Bypass -File $sourceRunner @RunnerArguments
    if ($LASTEXITCODE -ne 0) {
        throw "MasterchiefRun.ps1 failed with exit code $LASTEXITCODE."
    }
}

function Ensure-PyPiEnvironment {
    $environmentDir = Join-Path $repoRoot '.venv-pypi'
    $pythonPath = Join-Path $environmentDir 'Scripts\python.exe'
    if (Test-Path $pythonPath) { return $pythonPath }

    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv $environmentDir
    } elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
        & python3 -m venv $environmentDir
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv $environmentDir
    } else {
        throw 'Python 3.10 or newer is required to install the PyPI package.'
    }
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the PyPI virtual environment.' }
    return $pythonPath
}

function Start-SourceApp {
    if (-not (Test-Path $sourcePython)) {
        Write-Host 'No source virtual environment exists yet; running setup first.'
        Invoke-SourceRunner @('-SetupOnly', '-Port', "$Port")
    }

    Push-Location $repoRoot
    try {
        & $sourcePython (Join-Path $repoRoot 'main.py') --host 0.0.0.0 --port $Port
        if ($LASTEXITCODE -ne 0) { throw "MasterChief exited with code $LASTEXITCODE." }
    } finally {
        Pop-Location
    }
}

function Show-OtherSetupScripts {
    Write-Host ''
    Write-Host 'Additional setup-related files in this repository:'
    $scripts = @(
        @('MasterchiefRun.ps1', 'Windows source setup and launch'),
        @('scripts/start.sh', 'POSIX source startup'),
        @('setup.ps1', 'Legacy Windows setup; downloads a large model'),
        @('install.sh', 'Linux system installer; changes packages and /opt, /etc, /var'),
        @('os/iso-builder/scripts/install-platform.sh', 'ISO system installer; writes system configuration'),
        @('setup_structure.sh', 'Legacy directory scaffolder; creates project directories'),
        @('chocolatey/release.ps1', 'Builds or publishes the Chocolatey package')
    )

    foreach ($entry in $scripts) {
        $path = Join-Path $repoRoot $entry[0]
        if (Test-Path $path) {
            Write-Host ("  {0} - {1}" -f $entry[0], $entry[1])
        }
    }
    Write-Host 'System installers and scaffolding are listed for review, not run automatically.'
    Write-Host ''
}

function Get-SetupExtras {
    $setupText = Get-Content (Join-Path $repoRoot 'setup.py') -Raw
    $start = $setupText.IndexOf('extras_require={')
    $end = $setupText.IndexOf('entry_points=', $start)
    if ($start -lt 0 -or $end -lt 0) { return @('ai', 'audio', 'async', 'database', 'cloud', 'ansible', 'extras', 'dev', 'all') }
    $block = $setupText.Substring($start, $end - $start)
    $matches = [regex]::Matches($block, '(?m)^\s{8}"(?<name>[^"]+)":\s*\[')
    return @($matches | ForEach-Object { $_.Groups['name'].Value })
}

function Get-FeatureDefaults {
    $featurePath = Join-Path $repoRoot 'data\feature_flags.json'
    if (Test-Path $featurePath) { return (Get-Content $featurePath -Raw | ConvertFrom-Json) }

    $source = Get-Content (Join-Path $repoRoot 'utils\feature_flags.py') -Raw
    $block = [regex]::Match($source, '(?s)DEFAULT_FEATURE_FLAGS\s*=\s*\{(?<body>.*?)\n\}').Groups['body'].Value
    $defaults = [ordered]@{}
    foreach ($match in [regex]::Matches($block, "(?m)^\s*'(?<name>[^']+)':\s*(?<enabled>True|False),")) {
        $defaults[$match.Groups['name'].Value] = ($match.Groups['enabled'].Value -eq 'True')
    }
    return [pscustomobject]$defaults
}

function Save-JsonConfig {
    param([string]$Path, [object]$Document)
    if (Test-Path $Path) {
        $backupDirectory = Join-Path $env:LOCALAPPDATA 'MasterChief\setup-backups'
        New-Item -ItemType Directory -Path $backupDirectory -Force | Out-Null
        $backupName = (Split-Path $Path -Leaf) + '.' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff') + '.bak'
        Copy-Item -LiteralPath $Path -Destination (Join-Path $backupDirectory $backupName)
    }
    $temporaryPath = "$Path.setup-tmp"
    $Document | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath $temporaryPath -Encoding UTF8
    Move-Item -LiteralPath $temporaryPath -Destination $Path -Force
}

function Set-RuntimeOption {
    param([ValidateSet('module', 'feature')][string]$Kind)

    if ($Kind -eq 'module') {
        $path = Join-Path $repoRoot 'data\modules.json'
        if (-not (Test-Path $path)) { throw "Module config not found: $path" }
        $document = Get-Content $path -Raw | ConvertFrom-Json
        $properties = @($document.PSObject.Properties | Sort-Object Name)
        Write-Host 'Runtime modules:'
        for ($index = 0; $index -lt $properties.Count; $index++) {
            Write-Host ("  {0}. {1} [{2}]" -f ($index + 1), $properties[$index].Name, $(if ($properties[$index].Value.enabled) { 'enabled' } else { 'disabled' }))
        }
    } else {
        $path = Join-Path $repoRoot 'data\feature_flags.json'
        $document = Get-FeatureDefaults
        $properties = @($document.PSObject.Properties | Sort-Object Name)
        Write-Host 'Runtime features/services:'
        for ($index = 0; $index -lt $properties.Count; $index++) {
            Write-Host ("  {0}. {1} [{2}]" -f ($index + 1), $properties[$index].Name, $(if ($properties[$index].Value) { 'enabled' } else { 'disabled' }))
        }
    }

    $selection = Read-Host 'Select a number to toggle, or press Enter to return'
    if (-not $selection) { return }
    $number = 0
    if (-not [int]::TryParse($selection, [ref]$number) -or $number -lt 1 -or $number -gt $properties.Count) {
        throw 'Invalid selection.'
    }
    $selected = $properties[$number - 1]
    $enabled = (Read-Host "Enable $($selected.Name)? [y/N]") -match '^(y|yes)$'
    if ($Kind -eq 'module') {
        $selected.Value | Add-Member -MemberType NoteProperty -Name 'enabled' -Value $enabled -Force
    } else {
        $document | Add-Member -MemberType NoteProperty -Name $selected.Name -Value $enabled -Force
    }
    Save-JsonConfig -Path $path -Document $document
    Write-Host "Updated $($selected.Name); a timestamped backup was saved under $env:LOCALAPPDATA\MasterChief\setup-backups." -ForegroundColor Green
}

function Show-RepositoryInventory {
    Write-Host "`nRepository source inventory: $repoRoot" -ForegroundColor Cyan
    $excluded = @('.git', '.venv', 'venv', 'venv310', 'node_modules', '__pycache__', 'build', 'dist', '.pytest_cache', '.mypy_cache')
    foreach ($directory in Get-ChildItem -LiteralPath $repoRoot -Directory -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notin $excluded } | Sort-Object Name) {
        $childCount = @(Get-ChildItem -LiteralPath $directory.FullName -Force -ErrorAction SilentlyContinue | Select-Object -First 100).Count
        Write-Host ("  {0,-24} {1,3} direct entries" -f ($directory.Name + '/'), $childCount)
    }
    Write-Host "`nSetup and service entry points:"
    Show-OtherSetupScripts
    Write-Host 'Source setup installs the project packages declared by setup.py. Runtime data is preserved; the inventory does not execute files.'
}

function Install-SelectedExtras {
    $extras = @(Get-SetupExtras)
    Write-Host "Available extras: $($extras -join ', ')"
    $selected = (Read-Host 'Enter comma-separated extras').Split(',') | ForEach-Object { $_.Trim().ToLowerInvariant() } | Where-Object { $_ }
    $invalid = @($selected | Where-Object { $_ -notin $extras })
    if ($invalid.Count -gt 0) { throw "Unknown extra(s): $($invalid -join ', ')" }
    if (@($selected).Count -eq 0) { return }

    Invoke-SourceRunner @('-SetupOnly', '-Port', "$Port")
    $editableSpec = "$repoRoot[$($selected -join ',')]"
    & $sourcePython -m pip install -e $editableSpec
    if ($LASTEXITCODE -ne 0) { throw 'Could not install the selected extras.' }
    if ((Read-Host 'Start the web app now? [y/N]') -match '^(y|yes)$') { Start-SourceApp }
}

function Show-AdvancedMenu {
    while ($true) {
        Clear-Host
        Write-Host 'MASTERCHIEF SETUP  /  ADVANCED' -ForegroundColor Cyan
        Write-Host ''
        Write-Host '  1. Install source only'
        Write-Host '  2. Install every optional requirement'
        Write-Host '  3. Select dependency groups'
        Write-Host '  4. Install development/test tools'
        Write-Host '  5. Install latest PyPI package into an isolated environment'
        Write-Host '  6. Enable/disable a runtime module'
        Write-Host '  7. Enable/disable a feature or service route'
        Write-Host '  8. Browse repository components and setup scripts'
        Write-Host '  9. Change web port (current: ' -NoNewline
        Write-Host "$Port)"
        Write-Host '  0. Back'
        Write-Host ''
        $choice = Read-Host 'Select an advanced action'

        try {
            switch ($choice) {
                '1' { Invoke-SourceRunner @('-SetupOnly', '-Port', "$Port") }
                '2' {
                    $arguments = @('-SetupOnly', '-InstallOptional', '-Port', "$Port")
                    if ((Read-Host 'Also download the large optional GGUF model? [y/N]') -match '^(y|yes)$') { $arguments += '-DownloadModel' }
                    Invoke-SourceRunner $arguments
                    if ((Read-Host 'Start the web app now? [y/N]') -match '^(y|yes)$') { Start-SourceApp }
                }
                '3' { Install-SelectedExtras }
                '4' {
                    Invoke-SourceRunner @('-SetupOnly', '-Port', "$Port")
                    & $sourcePython -m pip install -r (Join-Path $repoRoot 'requirements-dev.txt')
                    if ($LASTEXITCODE -ne 0) { throw 'Could not install development requirements.' }
                }
                '5' {
                    $python = Ensure-PyPiEnvironment
                    & $python -m pip install --upgrade pip
                    if ($LASTEXITCODE -ne 0) { throw 'Could not upgrade pip.' }
                    & $python -m pip install --upgrade masterchief
                    if ($LASTEXITCODE -ne 0) { throw 'Could not install masterchief from PyPI.' }
                    $cli = Join-Path (Split-Path $python) 'masterchief.exe'
                    if (Test-Path $cli) { & $cli --help }
                }
                '6' { Set-RuntimeOption -Kind module }
                '7' { Set-RuntimeOption -Kind feature }
                '8' { Show-RepositoryInventory; Read-Host 'Press Enter to return' | Out-Null }
                '9' {
                    $newPort = 0
                    if ([int]::TryParse((Read-Host 'Enter a port from 1 to 65535'), [ref]$newPort) -and $newPort -ge 1 -and $newPort -le 65535) {
                        $script:Port = $newPort
                    } else { throw 'Port must be between 1 and 65535.' }
                }
                '0' { return }
                default { Write-Warning 'Choose one of the listed options.' }
            }
        } catch {
            Write-Host "Action failed: $($_.Exception.Message)" -ForegroundColor Red
        }
        if ($choice -ne '0') { Read-Host 'Press Enter to continue' | Out-Null }
    }
}

while ($true) {
    Clear-Host
    Write-Host '============================================================' -ForegroundColor DarkCyan
    Write-Host ' MASTERCHIEF  /  ONE-CLICK SETUP' -ForegroundColor Cyan
    Write-Host '============================================================' -ForegroundColor DarkCyan
    Write-Host "Repository: $repoRoot"
    Write-Host "Web port:   $Port"
    Write-Host ''
    Write-Host '  1. ONE-CLICK INSTALL + RUN' -ForegroundColor Green
    Write-Host '     Install base requirements, all bundled source packages and CLI, then start the web app.'
    Write-Host '  2. Advanced setup and component options'
    Write-Host '  3. Start an existing source installation'
    Write-Host '  4. Browse all repository components and setup scripts'
    Write-Host '  0. Exit'
    Write-Host ''
    $choice = Read-Host 'Choose 1 for the complete one-click setup'

    try {
        switch ($choice) {
            '1' { Invoke-SourceRunner @('-Port', "$Port") }
            '2' { Show-AdvancedMenu }
            '3' { Start-SourceApp }
            '4' { Show-RepositoryInventory; Read-Host 'Press Enter to return' | Out-Null }
            '0' { return }
            default { Write-Warning 'Choose 1, 2, 3, 4, or 0.' }
        }
    } catch {
        Write-Host "Setup failed: $($_.Exception.Message)" -ForegroundColor Red
    }
    if ($choice -ne '0') { Read-Host 'Press Enter to continue' | Out-Null }
}