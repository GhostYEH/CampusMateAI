[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Source,

    [Parameter(Mandatory = $true)]
    [string]$Output,

    [Parameter(Mandatory = $true)]
    [string]$ExpectedCommit,

    [string]$Repository = 'https://github.com/THU-MAIC/magicclass.git',
    [string]$Tag = 'v1.0.3'
)

# Thin PowerShell entry point. The audit itself lives in the sibling `.mjs` file
# because Node >=22.19.0 is already required by the managed service, which keeps
# the audit runnable (and testable) on hosts whose PowerShell cannot execute
# child processes or that only ship Windows PowerShell 5.1.
$ErrorActionPreference = 'Stop'

function Resolve-NodeExecutable {
    # Windows PowerShell resolves bare `node` through PATHEXT, which some hardened
    # hosts truncate; fall back to the explicit executable name.
    foreach ($name in @('node', 'node.exe')) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) { return $command.Source }
    }
    throw 'node is required to run the magic class source audit but was not found on PATH'
}

$auditScript = Join-Path $PSScriptRoot 'magicclass-source-audit.mjs'
if (-not (Test-Path -LiteralPath $auditScript -PathType Leaf)) {
    throw "magic class source audit implementation is missing: $auditScript"
}

$nodeExecutable = Resolve-NodeExecutable
& $nodeExecutable $auditScript `
    '--source' $Source `
    '--output' $Output `
    '--expected-commit' $ExpectedCommit `
    '--repository' $Repository `
    '--tag' $Tag
exit $LASTEXITCODE
