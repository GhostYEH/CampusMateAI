param(
    [string]$ExportDirectory = "artifacts/mobile_multitask_20261004",
    [string]$ToolCache = "$env:LOCALAPPDATA\CampusMateAI\tools\mindspore-lite-2.1.0"
)

$ErrorActionPreference = "Stop"
$ModuleRoot = Split-Path -Parent $PSScriptRoot
$ExportPath = Join-Path $ModuleRoot $ExportDirectory
$downloadUrl = "https://ms-release.obs.cn-north-4.myhuaweicloud.com/2.1.0/MindSpore/lite/release/windows/mindspore-lite-2.1.0-win-x64.zip"
$archiveHash = "5B32178F2BCB57C1A0D33F3D99A7A966527D41F0745D5879FE3AE011704F93F6"

foreach ($name in @("campusmate_multitask_expression_mindspore.onnx", "mindspore_input.bin", "mindspore_expected.txt", "model_metadata.json")) {
    if (!(Test-Path -LiteralPath (Join-Path $ExportPath $name))) { throw "Required export file is missing: $name" }
}

New-Item -ItemType Directory -Force -Path $ToolCache | Out-Null
$archive = Join-Path $ToolCache "mindspore-lite-2.1.0-win-x64.zip"
$expanded = Join-Path $ToolCache "expanded"
if (!(Test-Path -LiteralPath $archive)) { Invoke-WebRequest -Uri $downloadUrl -OutFile $archive }
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $archiveHash) {
    throw "MindSpore Lite converter archive SHA-256 mismatch"
}
if (!(Test-Path -LiteralPath $expanded)) { Expand-Archive -LiteralPath $archive -DestinationPath $expanded }

$converter = Get-ChildItem -LiteralPath $expanded -Recurse -Filter "converter_lite.exe" | Select-Object -First 1
$benchmark = Get-ChildItem -LiteralPath $expanded -Recurse -Filter "benchmark.exe" | Select-Object -First 1
if ($null -eq $converter -or $null -eq $benchmark) { throw "MindSpore Lite converter/benchmark tools are missing" }
$converterLib = Join-Path $converter.Directory.Parent.FullName "lib"
$runtimeLib = Join-Path $benchmark.Directory.Parent.Parent.FullName "runtime\lib"
$glogLib = Join-Path $benchmark.Directory.Parent.Parent.FullName "runtime\third_party\glog"
$jpegLib = Join-Path $benchmark.Directory.Parent.Parent.FullName "runtime\third_party\libjpeg-turbo\lib"
$env:PATH = "$converterLib;$runtimeLib;$glogLib;$jpegLib;$env:PATH"

$modelBase = Join-Path $ExportPath "campusmate_multitask_expression"
$mindSporeModel = "$modelBase.ms"
if (Test-Path -LiteralPath $mindSporeModel) { throw "MindSpore model already exists; use a fresh export directory" }
$onnxFile = Join-Path $ExportPath "campusmate_multitask_expression_mindspore.onnx"
$parityInput = Join-Path $ExportPath "mindspore_input.bin"
$expectedOutput = Join-Path $ExportPath "mindspore_expected.txt"
& $converter.FullName --fmk=ONNX --modelFile=$onnxFile `
    --outputFile=$modelBase --inputShape="input:1,3,96,96" --inputDataFormat=NCHW `
    --outputDataType=FLOAT --optimize=none --infer=true
if ($LASTEXITCODE -ne 0) { throw "MindSpore Lite conversion failed with exit code $LASTEXITCODE" }
if (!(Test-Path -LiteralPath $mindSporeModel)) { throw "MindSpore Lite model was not produced" }

& $benchmark.FullName --modelFile=$mindSporeModel `
    --inDataFile=$parityInput `
    --benchmarkDataFile=$expectedOutput `
    --accuracyThreshold=0.001 --loopCount=1 --warmUpLoopCount=0 --numThreads=2
if ($LASTEXITCODE -ne 0) { throw "ONNX/MindSpore Lite parity failed with exit code $LASTEXITCODE" }

$metadataPath = Join-Path $ExportPath "model_metadata.json"
$metadata = Get-Content -LiteralPath $metadataPath -Raw | ConvertFrom-Json -AsHashtable
$metadata.conversion.mindspore_parity = @{
    runtime = "MindSpore Lite 2.1.0 Windows benchmark"
    passed = $true
    sample_count = 1
    input_shape = @(1, 3, 96, 96)
    output_shape = @(1, 10)
    accuracy_threshold = 0.001
    reference = "ONNX Runtime CPU; first validation crop"
}
$metadata.artifacts.mindspore = @{
    file = [System.IO.Path]::GetFileName($mindSporeModel)
    sha256 = (Get-FileHash -LiteralPath $mindSporeModel -Algorithm SHA256).Hash.ToLowerInvariant()
    size_bytes = (Get-Item -LiteralPath $mindSporeModel).Length
}
$metadata | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $metadataPath -Encoding utf8
Get-FileHash -LiteralPath $mindSporeModel -Algorithm SHA256
