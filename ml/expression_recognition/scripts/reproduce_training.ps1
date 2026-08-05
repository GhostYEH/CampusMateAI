param(
    [Parameter(Mandatory = $true)]
    [string]$DatasetRoot,
    [string]$VenvName = ".venv",
    [int]$MaxEpochs = 0,
    [switch]$SmokeOnly
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
        if ($LASTEXITCODE -ne 0) { throw "Failed to create the Python 3.12 environment." }
    }
    & $Uv pip install --python $Python --index-url https://download.pytorch.org/whl/cu130 torch==2.12.1 torchvision==0.27.1
    if ($LASTEXITCODE -ne 0) { throw "Failed to install the CUDA PyTorch runtime." }
    & $Uv pip install --python $Python -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Failed to install training dependencies." }
    & $Uv pip install --python $Python -e .
    if ($LASTEXITCODE -ne 0) { throw "Failed to install the local package." }

    & $Python -m expression_recognition.env_report --output reports/generated/environment.json
    & $Python -m pytest
    if ($LASTEXITCODE -ne 0) { throw "pytest failed." }

    # 1. Auto-detect and merge every dataset under the root into one manifest.
    & $Python -m expression_recognition.unified_manifest `
        --dataset-root $DatasetRoot `
        --output-dir manifests_v2
    if ($LASTEXITCODE -ne 0) { throw "Unified manifest build failed." }

    $Manifest = "manifests_v2\included.csv"
    $EpochArg = if ($MaxEpochs -gt 0) { @("--max-epochs", $MaxEpochs) } else { @() }

    # 2. Smoke train every model to validate the full pipeline on the unified data.
    $Configs = @(
        "configs\baseline_cnn.yaml",
        "configs\resnet18.yaml",
        "configs\mobilenet_v3_small.yaml",
        "configs\efficientnet_b0.yaml"
    )
    foreach ($Config in $Configs) {
        & $Python -m expression_recognition.train `
            --config $Config `
            --manifest $Manifest `
            --output-root runs_v2 `
            --smoke --max-batches 4 --allow-cpu
        if ($LASTEXITCODE -ne 0) { throw "Smoke training failed for $Config." }
    }

    if ($SmokeOnly) { return }

    # 3. Full training of every candidate; results land in runs_v2 (never overwriting old runs/).
    foreach ($Config in $Configs) {
        $Model = [IO.Path]::GetFileNameWithoutExtension($Config)
        & $Python -m expression_recognition.train `
            --config $Config `
            --manifest $Manifest `
            --output-root runs_v2 `
            --run-dir "runs_v2\full_$Model" @EpochArg
        if ($LASTEXITCODE -ne 0) { throw "Full training failed for $Config." }
    }

    # 4. Evaluate each on validation and the independent test split.
    foreach ($Config in $Configs) {
        $Model = [IO.Path]::GetFileNameWithoutExtension($Config)
        & $Python -m expression_recognition.evaluate `
            --checkpoint "runs_v2\full_$Model\best.pt" `
            --manifest $Manifest --split validation `
            --output-dir "reports\generated_v2\$Model"
        if ($LASTEXITCODE -ne 0) { throw "Validation eval failed for $Model." }
        & $Python -m expression_recognition.evaluate `
            --checkpoint "runs_v2\full_$Model\best.pt" `
            --manifest $Manifest --split test `
            --output-dir "reports\generated_v2\$Model"
        if ($LASTEXITCODE -ne 0) { throw "Test eval failed for $Model." }
    }

    Write-Host "Done. Select best model by reports/generated_v2/<model>/validation_metrics.json macro_f1."

    # 5. Export the best model (ResNet18) to LiteRT/TFLite for Android.
    #    The export uses a separate .venv-export environment with TensorFlow.
    & powershell -ExecutionPolicy Bypass -File "$PSScriptRoot\export_litert_v2.ps1"
    if ($LASTEXITCODE -ne 0) { Write-Host "WARNING: LiteRT export failed. See exports_v2/resnet18/litert_verification.json if present." }
} finally {
    Pop-Location
}
