param(
    [Parameter(Mandatory = $true)]
    [string]$DatasetRoot,
    [string]$VenvName = ".venv"
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
    & $Python -m expression_recognition.audit `
        --dataset-root $DatasetRoot `
        --output-dir manifests `
        --validation-fraction 0.15 `
        --seed 20260731
    if ($LASTEXITCODE -ne 0) { throw "Dataset audit failed." }

    $Configs = @(
        "configs/baseline_cnn.yaml",
        "configs/resnet18.yaml",
        "configs/mobilenet_v3_small.yaml"
    )
    foreach ($Config in $Configs) {
        & $Python -m expression_recognition.train `
            --config $Config `
            --manifest manifests/included.csv `
            --output-root runs `
            --smoke `
            --max-batches 4
        if ($LASTEXITCODE -ne 0) { throw "Smoke training failed for $Config." }
    }
    foreach ($Config in $Configs) {
        & $Python -m expression_recognition.train `
            --config $Config `
            --manifest manifests/included.csv `
            --output-root runs
        if ($LASTEXITCODE -ne 0) { throw "Full training failed for $Config." }
    }
} finally {
    Pop-Location
}
