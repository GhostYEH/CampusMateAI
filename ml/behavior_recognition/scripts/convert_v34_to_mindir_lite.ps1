param(
    [string]$InputModel = "D:\File\demo1\ml\behavior_recognition\exports\v34-roi-seed-20260823\campusmate_behavior_v34_candidate.onnx",
    [string]$OutputDirectory = "D:\File\demo1\harmony\entry\src\main\resources\rawfile\models\behavior",
    [string]$ToolCache = "$env:LOCALAPPDATA\CampusMateAI\tools\mindspore-lite-2.1.0"
)

$ErrorActionPreference = "Stop"
$downloadUrl = "https://ms-release.obs.cn-north-4.myhuaweicloud.com/2.1.0/MindSpore/lite/release/windows/mindspore-lite-2.1.0-win-x64.zip"
$archiveHash = "5B32178F2BCB57C1A0D33F3D99A7A966527D41F0745D5879FE3AE011704F93F6"
$inputHash = "9ABE029D18E1BFC1F0E1E47217F575153AF966BF013500DD66E8DDA0592C5740"
$compatibleHash = "8FF821CFA506C47BA96DA75750E5BF09E3EC5029A2093D38715CFE11367B8CF9"

if (!(Test-Path -LiteralPath $InputModel)) { throw "V3.4 ONNX not found: $InputModel" }
if ((Get-FileHash -LiteralPath $InputModel -Algorithm SHA256).Hash -ne $inputHash) {
    throw "V3.4 ONNX SHA-256 mismatch"
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
if ($null -eq $converter) { throw "converter_lite.exe not found after extraction" }
$converterLib = Join-Path $converter.Directory.Parent.FullName "lib"
$env:PATH = "$converterLib;$env:PATH"

# MindSpore Lite 2.1 accepts ONNX HardSwish during parsing but serializes it
# incorrectly. Expand it to the mathematically identical HardSigmoid + Mul form.
$compatibleModel = Join-Path $ToolCache "campusmate_behavior_v34_mslite21.onnx"
$rewriter = Join-Path $PSScriptRoot "prepare_v34_for_mindspore.py"
& python $rewriter $InputModel $compatibleModel
if ($LASTEXITCODE -ne 0) { throw "Failed to prepare ONNX for MindSpore Lite 2.1" }
if ((Get-FileHash -LiteralPath $compatibleModel -Algorithm SHA256).Hash -ne $compatibleHash) {
    throw "Prepared ONNX SHA-256 mismatch"
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$outputBase = Join-Path $OutputDirectory "campusmate_behavior_v34"
& $converter.FullName --fmk=ONNX --modelFile=$compatibleModel --outputFile=$outputBase `
    --inputShape="input:1,3,224,224" --inputDataFormat=NCHW --outputDataType=FLOAT `
    --optimize=none --infer=true
if ($LASTEXITCODE -ne 0) { throw "MindSpore Lite conversion failed with exit code $LASTEXITCODE" }

$outputModel = "$outputBase.ms"
if (!(Test-Path -LiteralPath $outputModel)) { throw "Converted model not produced" }

$benchmark = Get-ChildItem -LiteralPath $expanded -Recurse -Filter "benchmark.exe" | Select-Object -First 1
if ($null -eq $benchmark) { throw "benchmark.exe not found after extraction" }
$parityDirectory = Join-Path $ToolCache "v34-parity"
$fixtureScript = Join-Path $PSScriptRoot "create_v34_parity_fixture.py"
& python $fixtureScript $InputModel $parityDirectory
if ($LASTEXITCODE -ne 0) { throw "Failed to create V3.4 parity fixture" }
$packageRoot = $benchmark.Directory.Parent.Parent.FullName
$runtimeLib = Join-Path $packageRoot "runtime\lib"
$glogLib = Join-Path $packageRoot "runtime\third_party\glog"
$jpegLib = Join-Path $packageRoot "runtime\third_party\libjpeg-turbo\lib"
$env:PATH = "$runtimeLib;$glogLib;$jpegLib;$env:PATH"
$inputFile = Join-Path $parityDirectory "input.bin"
$expectedFile = Join-Path $parityDirectory "expected.txt"
& $benchmark.FullName --modelFile=$outputModel `
    --inDataFile=$inputFile --benchmarkDataFile=$expectedFile `
    --accuracyThreshold=0.0001 --loopCount=1 --warmUpLoopCount=0 --numThreads=2
if ($LASTEXITCODE -ne 0) { throw "ONNX/MindIR Lite parity verification failed" }

Get-FileHash -LiteralPath $outputModel -Algorithm SHA256
