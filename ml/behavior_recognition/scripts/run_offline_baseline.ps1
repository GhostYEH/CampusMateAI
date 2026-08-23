param(
    [string]$Sources = "configs/sources.yaml",
    [string]$RunName = "v34-roi-seed-20260823",
    [int]$MaxEpochs = 30,
    [switch]$SkipFullTraining,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot

if ($Help) {
    Write-Output "Usage: ./scripts/run_offline_baseline.ps1 [-Sources path] [-RunName name] [-MaxEpochs n] [-SkipFullTraining]"
    Write-Output "-SkipFullTraining limits each class to 64 samples for a smoke run."
    exit 0
}

Push-Location $projectRoot
try {
    $env:PYTHONPATH = "src"
    $env:TORCH_HOME = Join-Path $projectRoot ".torch-cache"

    python -c "import sys,torch,torchvision; print('python',sys.version); print('torch',torch.__version__); print('torchvision',torchvision.__version__); print('cuda',torch.cuda.is_available()); print('gpu',torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
    if ($LASTEXITCODE -ne 0) { throw "Python/PyTorch preflight failed" }

    if (-not (Test-Path -LiteralPath $Sources)) {
        throw "Source configuration does not exist: $Sources"
    }
    $v32Model = Resolve-Path "../../android/app/src/main/assets/models/behavior/campusmate_visible_study_v32.onnx"
    $freeBytes = (Get-PSDrive -Name ([System.IO.Path]::GetPathRoot($projectRoot).Substring(0, 1))).Free
    Write-Output ("free_disk_gb=" + [math]::Round($freeBytes / 1GB, 2))

    python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Behavior recognition tests failed" }

    python -m behavior_recognition.cli audit --sources $Sources --output reports/generated/audit.json
    if ($LASTEXITCODE -ne 0) { throw "Dataset audit failed" }
    python -m behavior_recognition.cli manifest --sources $Sources --output manifests --seed 20260823
    if ($LASTEXITCODE -ne 0) { throw "Manifest generation failed" }

    $trainArguments = @(
        "-m", "behavior_recognition.cli", "train",
        "--config", "configs/mobilenet_v3_small_roi.yaml",
        "--manifests", "manifests",
        "--run-dir", "runs/$RunName",
        "--max-epochs", "$MaxEpochs"
    )
    if ($SkipFullTraining) {
        $trainArguments += @("--limit-per-class", "64")
    }
    python @trainArguments
    if ($LASTEXITCODE -ne 0) { throw "Training failed" }

    python -m behavior_recognition.cli evaluate --checkpoint "runs/$RunName/best.pt" --manifests manifests --output "reports/generated/$RunName.json" --compare-v32 $v32Model
    if ($LASTEXITCODE -ne 0) { throw "Evaluation failed" }
    python -m behavior_recognition.cli export --checkpoint "runs/$RunName/best.pt" --config configs/mobilenet_v3_small_roi.yaml --output "exports/$RunName"
    if ($LASTEXITCODE -ne 0) { throw "ONNX export failed" }

    Write-Output "offline baseline complete: $RunName"
} finally {
    Pop-Location
}
