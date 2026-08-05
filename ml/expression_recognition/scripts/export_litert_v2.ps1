param(
    [string]$Checkpoint = "runs_v2\full_resnet18\best.pt",
    [string]$Manifest = "manifests_v2\included.csv",
    [string]$VenvName = ".venv-export"
)

$ErrorActionPreference = "Stop"
$ModuleRoot = Split-Path -Parent $PSScriptRoot
$VenvPath = Join-Path $ModuleRoot $VenvName
$Python = Join-Path $VenvPath "Scripts\python.exe"
$Uv = (Get-Command uv -ErrorAction Stop).Source

Push-Location $ModuleRoot
try {
    if (-not (Test-Path -LiteralPath $Python)) {
        & $Uv venv --python 3.12 $VenvPath
        if ($LASTEXITCODE -ne 0) { throw "Failed to create the export environment." }
    }
    & $Uv pip install --python $Python -r requirements-export.txt
    if ($LASTEXITCODE -ne 0) { throw "Failed to install export dependencies." }
    & $Uv pip install --python $Python -e .
    if ($LASTEXITCODE -ne 0) { throw "Failed to install the local package." }

    Write-Host "===== EXPORT ResNet18 to LiteRT/TFLite (v2) ====="
    & $Python -m expression_recognition.export_litert `
        --checkpoint $Checkpoint `
        --manifest $Manifest `
        --output-dir exports_v2/resnet18 `
        --android-assets ../../android/app/src/main/assets `
        --confidence-threshold 0.70 `
        --model-version expression-resnet18-multiv2-v1 `
        --converter auto
    if ($LASTEXITCODE -ne 0) { throw "LiteRT export or verification failed." }
    Write-Host "===== EXPORT COMPLETE ====="
} finally {
    Pop-Location
}
