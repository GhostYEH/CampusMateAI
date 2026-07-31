param(
    [string]$Checkpoint = "runs\full_resnet18\best.pt",
    [string]$Manifest = "manifests\included.csv",
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

    & $Python -m expression_recognition.export_litert `
        --checkpoint $Checkpoint `
        --manifest $Manifest `
        --output-dir exports/resnet18 `
        --android-assets ../../android/app/src/main/assets `
        --confidence-threshold 0.70 `
        --model-version expression-resnet18-clean-v1 `
        --converter auto
    if ($LASTEXITCODE -ne 0) { throw "LiteRT export or verification failed." }
} finally {
    Pop-Location
}
