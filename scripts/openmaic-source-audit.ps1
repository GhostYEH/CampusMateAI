[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Source,

    [Parameter(Mandatory = $true)]
    [string]$Output,

    [Parameter(Mandatory = $true)]
    [string]$ExpectedCommit,

    [string]$Repository = 'https://github.com/THU-MAIC/OpenMAIC.git',
    [string]$Tag = 'v1.0.3'
)

$ErrorActionPreference = 'Stop'

function Resolve-FullPath([string]$Path) {
    return [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $Path).Path)
}

if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
    throw "OpenMAIC source directory does not exist: $Source"
}

$sourcePath = Resolve-FullPath $Source
New-Item -ItemType Directory -Path $Output -Force | Out-Null
$outputPath = Resolve-FullPath $Output

if ($outputPath.Equals($sourcePath, [System.StringComparison]::OrdinalIgnoreCase) -or
    $outputPath.StartsWith($sourcePath.TrimEnd('\') + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Audit output must not be inside the source checkout'
}

function Invoke-Git([string[]]$Arguments) {
    $result = & git -C $sourcePath @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect OpenMAIC checkout with git: $result"
    }
    return ($result | Out-String).Trim()
}

$actualCommit = Invoke-Git @('rev-parse', 'HEAD')
if ($actualCommit -ne $ExpectedCommit) {
    throw "OpenMAIC source commit mismatch: expected $ExpectedCommit, got $actualCommit"
}

$licensePath = Join-Path $sourcePath 'LICENSE'
if (-not (Test-Path -LiteralPath $licensePath -PathType Leaf)) {
    throw 'OpenMAIC LICENSE is missing'
}

function Get-RelativePath([string]$FullName) {
    return ([System.IO.Path]::GetRelativePath($sourcePath, $FullName)).Replace('\', '/')
}

function Get-CapabilityMapping([string]$RelativePath) {
    if ($RelativePath -match '^app/api/') {
        if ($RelativePath -match '/(stages|stage-meta)/') { return 'workspace/stage' }
        if ($RelativePath -match '/(classroom|generate-classroom)/') { return 'generation/player' }
        if ($RelativePath -match '/(folders)/') { return 'folders' }
        if ($RelativePath -match '/(materials|extract-document|parse-pdf)/') { return 'materials' }
        if ($RelativePath -match '/(generate|pbl)/') { return 'generation' }
        if ($RelativePath -match '/(chat|agent)/') { return 'chat/multi-agent' }
        if ($RelativePath -match '/(web-search)/') { return 'web-search' }
        if ($RelativePath -match '/(provider|server-providers)/') { return 'provider-capabilities' }
        if ($RelativePath -match '/(export-video)/') { return 'video-export' }
        if ($RelativePath -match '/health/') { return 'health' }
        if ($RelativePath -match '/access-code/') { return 'service-auth' }
        return 'campusmate-equivalent'
    }
    if ($RelativePath -match '^packages/@openmaic/dsl/') { return 'dsl' }
    if ($RelativePath -match '^packages/@openmaic/(renderer|editor)/') { return 'editor/player' }
    if ($RelativePath -match '^packages/@openmaic/(importer|storage)/') { return 'import/export' }
    if ($RelativePath -match '^packages/@openmaic/generation/') { return 'generation' }
    if ($RelativePath -match '^packages/(pptxgenjs|mathml2omml)/') { return 'import/export' }
    if ($RelativePath -match '^packages/') { return 'campusmate-equivalent' }
    if ($RelativePath -match '^components/(discovery|workbench)/') { return 'homepage/workspace' }
    if ($RelativePath -match '^components/(classroom|scene-renderers|stage)/') { return 'player' }
    if ($RelativePath -match '^components/(edit)/') { return 'editor' }
    if ($RelativePath -match '^components/(whiteboard|roundtable|audio)/') { return 'whiteboard/tts/multi-agent' }
    if ($RelativePath -match '^components/') { return 'campusmate-equivalent' }
    if ($RelativePath -match '^render-service/') { return 'render-service' }
    if ($RelativePath -match '^skills/') { return 'provider-capabilities' }
    return $null
}

$excludedPattern = '(^|/)(\.git|node_modules|\.next|data|logs?)(/|$)|(^|/)(\.env($|\.)|.*\.(pem|key))'
$files = @()
foreach ($item in (Get-ChildItem -LiteralPath $sourcePath -Recurse -Force -File)) {
    $relative = Get-RelativePath $item.FullName
    if ($relative -match $excludedPattern) { continue }
    if ($item.LinkType) {
        $resolvedTarget = (Resolve-Path -LiteralPath $item.FullName).Path
        $resolvedFull = [System.IO.Path]::GetFullPath($resolvedTarget)
        if (-not $resolvedFull.StartsWith($sourcePath.TrimEnd('\') + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Source symlink escapes checkout: $relative"
        }
    }
    $files += [pscustomobject]@{
        path = $relative
        sha256 = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
$files = @($files | Sort-Object path)

$routes = @(
    $files | Where-Object { $_.path -match '^app/api/.+\.(ts|tsx)$' } | ForEach-Object {
        [pscustomobject]@{ path = $_.path; mapping = Get-CapabilityMapping $_.path }
    }
)
$packagePaths = @(
    $files.path | Where-Object { $_ -match '^packages/([^/]+/)?[^/]+/' } |
        ForEach-Object { if ($_ -match '^(packages/(?:[^/]+/)?[^/]+)') { $Matches[1] } } |
        Sort-Object -Unique | ForEach-Object {
            [pscustomobject]@{ path = $_; mapping = Get-CapabilityMapping "$_/" }
        }
)
$components = @(
    $files.path | Where-Object { $_ -match '^components/[^/]+' } |
        ForEach-Object { if ($_ -match '^(components/[^/]+)') { $Matches[1] } } |
        Sort-Object -Unique | ForEach-Object {
            [pscustomobject]@{ path = $_; mapping = Get-CapabilityMapping "$_/" }
        }
)
$unclassified = @($routes + $packagePaths + $components | Where-Object { -not $_.mapping })
if ($unclassified.Count -gt 0) {
    throw "Unclassified OpenMAIC surfaces: $(($unclassified.path -join ', '))"
}

$manifestLines = $files | ForEach-Object { "$($_.sha256)  $($_.path)" }
Set-Content -LiteralPath (Join-Path $outputPath 'source-manifest.sha256') -Value $manifestLines -Encoding utf8
Copy-Item -LiteralPath $licensePath -Destination (Join-Path $outputPath 'LICENSE') -Force
Set-Content -LiteralPath (Join-Path $outputPath 'NOTICE.md') -Value @"
# OpenMAIC provenance notice

This directory records the audited source boundary for OpenMAIC `$Tag`.

- Repository: `$Repository`
- Commit: `$actualCommit`
- License: MIT; see `LICENSE`.
- The source checkout itself, package managers, build output, runtime data, logs, credentials and local configuration are not vendored here.
"@ -Encoding utf8

$inventory = [ordered]@{
    source = [ordered]@{ repository = $Repository; tag = $Tag; commit = $actualCommit }
    routes = @($routes)
    packages = @($packagePaths)
    components = @($components)
    renderService = @($files | Where-Object { $_.path -match '^render-service/' } | ForEach-Object {
        [pscustomobject]@{ path = $_.path; mapping = 'render-service' }
    })
    skills = @($files | Where-Object { $_.path -match '^skills/' } | ForEach-Object {
        [pscustomobject]@{ path = $_.path; mapping = 'provider-capabilities' }
    })
    unclassified = @($unclassified)
}
Set-Content -LiteralPath (Join-Path $outputPath 'capability-inventory.json') -Value ($inventory | ConvertTo-Json -Depth 20) -Encoding utf8

$upstream = [ordered]@{
    repository = $Repository
    tag = $Tag
    commit = $actualCommit
    auditedAt = [DateTime]::UtcNow.ToString('o')
    files = $files
}
Set-Content -LiteralPath (Join-Path $outputPath 'UPSTREAM.json') -Value ($upstream | ConvertTo-Json -Depth 20) -Encoding utf8
