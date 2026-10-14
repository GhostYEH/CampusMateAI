[CmdletBinding()]
param(
    [ValidateSet('Setup', 'Check', 'Build', 'Start')]
    [string]$Action = 'Check',
    [string]$ToolRoot
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$configPath = Join-Path $repoRoot '.environment.local'
if (-not $ToolRoot) {
    if (-not (Test-Path -LiteralPath $configPath)) {
        throw 'First run: pass -ToolRoot with a writable tool directory on your preferred drive.'
    }
    $ToolRoot = (Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json).ToolRoot
}
$ToolRoot = [IO.Path]::GetFullPath($ToolRoot)
if ([IO.Path]::GetPathRoot($ToolRoot) -eq [IO.Path]::GetPathRoot($env:SystemRoot)) {
    throw 'Choose a tool directory outside the Windows system drive.'
}

function Invoke-Checked {
    param([string]$Command, [string[]]$Arguments)
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Command exited with code $LASTEXITCODE" }
}

foreach ($directory in @('tmp', 'downloads', 'npm-cache', 'pip-cache', 'pnpm-store')) {
    New-Item -ItemType Directory -Force (Join-Path $ToolRoot $directory) | Out-Null
}
$env:TEMP = Join-Path $ToolRoot 'tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $ToolRoot 'pip-cache'
$env:npm_config_cache = Join-Path $ToolRoot 'npm-cache'
$env:PNPM_HOME = Join-Path $ToolRoot 'pnpm'
$env:COREPACK_HOME = Join-Path $ToolRoot 'corepack'
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $ToolRoot 'playwright'
$env:NEXT_TELEMETRY_DISABLED = '1'
$env:PATH = "$(Join-Path $ToolRoot 'pnpm/node_modules/.bin');$env:PATH"
$python = Join-Path $ToolRoot 'python312/tools/python.exe'
$venv = Join-Path $repoRoot 'backend/.venv'
$venvPython = Join-Path $venv 'Scripts/python.exe'
$pnpm = Join-Path $ToolRoot 'pnpm/node_modules/.bin/pnpm.cmd'
$node = (Get-Command node.exe -ErrorAction Stop).Source
$npm = (Get-Command npm.cmd -ErrorAction Stop).Source
$nodeVersionText = & $node --version
if ($LASTEXITCODE -ne 0 -or [version]($nodeVersionText.Trim().TrimStart('v')) -lt [version]'22.19.0') {
    throw 'Node.js 22.19.0 or newer is required.'
}

Push-Location $repoRoot
try {
    if ($Action -eq 'Setup') {
        if (-not (Test-Path -LiteralPath $python)) {
            # Official CPython NuGet distribution: no system installer or PATH changes.
            $archive = Join-Path $ToolRoot 'downloads/python.3.12.10.zip'
            Invoke-WebRequest 'https://api.nuget.org/v3-flatcontainer/python/3.12.10/python.3.12.10.nupkg' -OutFile $archive
            Expand-Archive -LiteralPath $archive -DestinationPath (Join-Path $ToolRoot 'python312') -Force
        }
        $venvWorks = $false
        if (Test-Path -LiteralPath $venvPython) {
            & $venvPython -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)' 2>$null
            $venvWorks = $LASTEXITCODE -eq 0
        }
        if (-not $venvWorks) {
            if (Test-Path -LiteralPath $venv) {
                $resolvedVenv = [IO.Path]::GetFullPath($venv)
                if (-not $resolvedVenv.StartsWith($repoRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
                    throw 'Refusing to move a virtual environment outside this repository.'
                }
                New-Item -ItemType Directory -Force (Join-Path $repoRoot 'tmp') | Out-Null
                Move-Item -LiteralPath $resolvedVenv -Destination (Join-Path $repoRoot "tmp/backend-venv-backup-$(Get-Date -Format yyyyMMddHHmmssfff)")
            }
            Invoke-Checked $python @('-m', 'venv', $venv)
        }
        Invoke-Checked $venvPython @('-m', 'pip', 'install', '-r', 'backend/requirements.txt', '--disable-pip-version-check')
        Invoke-Checked $npm @('install', '--prefix', (Join-Path $ToolRoot 'pnpm'), 'pnpm@10.28.0', '--no-audit', '--no-fund')
        Push-Location (Join-Path $repoRoot 'webreact')
        try { Invoke-Checked $npm @('ci', '--no-audit', '--no-fund') } finally { Pop-Location }
        $previousCI = $env:CI
        $env:CI = 'true'
        Push-Location (Join-Path $repoRoot 'magicclass-app')
        try { Invoke-Checked $pnpm @('install', '--frozen-lockfile', '--store-dir', (Join-Path $ToolRoot 'pnpm-store')) }
        finally { Pop-Location; $env:CI = $previousCI }
        if (-not (Test-Path -LiteralPath 'backend/.env')) { Copy-Item 'backend/.env.example' 'backend/.env' }
        if (-not (Test-Path -LiteralPath 'magicclass-app/.env.local')) { Copy-Item 'magicclass-app/.env.example' 'magicclass-app/.env.local' }
        Invoke-Checked $node @('scripts/magicclass-local.mjs', 'env')
        @{ ToolRoot = $ToolRoot } | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding UTF8
    }
    if ($Action -in @('Setup', 'Check')) {
        Invoke-Checked $venvPython @('--version')
        Invoke-Checked $venvPython @('-m', 'pip', 'check')
        Invoke-Checked $node @('--version')
        Invoke-Checked $pnpm @('--version')
        Invoke-Checked $node @('scripts/magicclass-local.mjs', 'doctor')
    }
    if ($Action -eq 'Build') {
        Push-Location (Join-Path $repoRoot 'magicclass-service')
        try { Invoke-Checked $npm @('run', 'build') } finally { Pop-Location }
        Push-Location (Join-Path $repoRoot 'webreact')
        try { Invoke-Checked $npm @('run', 'build') } finally { Pop-Location }
        Push-Location (Join-Path $repoRoot 'magicclass-app')
        try { Invoke-Checked $pnpm @('run', 'build') } finally { Pop-Location }
    }
    if ($Action -eq 'Start') { Invoke-Checked $node @('scripts/magicclass-local.mjs', 'start') }
}
finally { Pop-Location }
