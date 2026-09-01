$ErrorActionPreference = "Continue"
$moduleRoot = Split-Path -Parent $PSScriptRoot
$py = Join-Path $moduleRoot ".venv\Scripts\python.exe"
Set-Location $moduleRoot
$Manifest = "manifests_v2\included.csv"
$Epochs = 15

$Models = @(
    @{ name = "baseline_cnn";        cfg = "configs\baseline_cnn.yaml" },
    @{ name = "resnet18";            cfg = "configs\resnet18.yaml" },
    @{ name = "mobilenet_v3_small";  cfg = "configs\mobilenet_v3_small.yaml" },
    @{ name = "efficientnet_b0";     cfg = "configs\efficientnet_b0.yaml" }
)

foreach ($m in $Models) {
    $name = $m.name
    $cfg = $m.cfg
    Write-Host "===== TRAIN $name ====="
    & $py -m expression_recognition.train `
        --config $cfg --manifest $Manifest `
        --output-root runs_v2 --run-dir "runs_v2\full_$name" `
        --max-epochs $Epochs *>&1 | Tee-Object -FilePath "runs_v2\full_$name.train.log"
    if ($LASTEXITCODE -ne 0) { Write-Host "TRAIN FAILED: $name"; continue }

    Write-Host "===== EVAL val $name ====="
    & $py -m expression_recognition.evaluate `
        --checkpoint "runs_v2\full_$name\best.pt" --manifest $Manifest `
        --split validation --output-dir "reports\generated_v2\$name" *>&1 | Tee-Object -FilePath "reports\generated_v2\$name.eval.log"
    if ($LASTEXITCODE -ne 0) { Write-Host "VAL EVAL FAILED: $name"; continue }

    Write-Host "===== EVAL test $name ====="
    & $py -m expression_recognition.evaluate `
        --checkpoint "runs_v2\full_$name\best.pt" --manifest $Manifest `
        --split test --output-dir "reports\generated_v2\$name" *>&1 | Tee-Object -FilePath "reports\generated_v2\$name.test.log"
    Write-Host "===== DONE $name ====="
}
Write-Host "ALL TRAINING COMPLETE"
