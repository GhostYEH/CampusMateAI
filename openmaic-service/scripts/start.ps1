$ErrorActionPreference = 'Stop'
$repoRoot = (git -C $PSScriptRoot rev-parse --show-toplevel).Trim()
$serviceRoot = Join-Path $repoRoot 'openmaic-service'
$node = (Get-Command node -ErrorAction Stop).Source
Push-Location $serviceRoot
try {
    & $node '--experimental-strip-types' 'src/main.ts'
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
