param(
    [string]$InputModel = "",
    [string]$OutputDirectory = "",
    [string]$ToolCache = "$env:LOCALAPPDATA\CampusMateAI\tools\mindspore-lite-2.1.0"
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
if ([string]::IsNullOrWhiteSpace($InputModel)) {
    $InputModel = Join-Path $repositoryRoot "android\app\src\main\assets\models\behavior\campusmate_tsm_mobilenetv2_v4.onnx"
}
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $repositoryRoot "harmony\entry\src\main\resources\rawfile\models\behavior"
}

$downloadUrl = "https://ms-release.obs.cn-north-4.myhuaweicloud.com/2.1.0/MindSpore/lite/release/windows/mindspore-lite-2.1.0-win-x64.zip"
$archiveHash = "5B32178F2BCB57C1A0D33F3D99A7A966527D41F0745D5879FE3AE011704F93F6"
$inputHash = "F5ACC4E5614A9FBFA75CD24EFC550A42AA3FA56AA8C0DA5C57CD7B7511EB7A66"
$outputHash = "D70B2A5C3C3D8D5A0508124E697C5B823E344DF1149BB6A1A1DC24825ABDBE03"

if (!(Test-Path -LiteralPath $InputModel)) { throw "TSM V4 ONNX not found: $InputModel" }
if ((Get-FileHash -LiteralPath $InputModel -Algorithm SHA256).Hash -ne $inputHash) {
    throw "TSM V4 ONNX SHA-256 mismatch"
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

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$outputBase = Join-Path $OutputDirectory "campusmate_tsm_mobilenetv2_v4"
& $converter.FullName --fmk=ONNX --modelFile=$InputModel --outputFile=$outputBase `
    --inputShape="frames:1,8,3,224,224" --inputDataFormat=NCHW --outputDataType=FLOAT `
    --optimize=none --infer=true
if ($LASTEXITCODE -ne 0) { throw "MindSpore Lite conversion failed with exit code $LASTEXITCODE" }

$outputModel = "$outputBase.ms"
if (!(Test-Path -LiteralPath $outputModel)) { throw "Converted TSM V4 model not produced" }
if ((Get-FileHash -LiteralPath $outputModel -Algorithm SHA256).Hash -ne $outputHash) {
    throw "Converted TSM V4 MindIR Lite SHA-256 mismatch"
}

$benchmark = Get-ChildItem -LiteralPath $expanded -Recurse -Filter "benchmark.exe" | Select-Object -First 1
if ($null -eq $benchmark) { throw "benchmark.exe not found after extraction" }
$parityDirectory = Join-Path $ToolCache "tsm-v4-parity"
$fixtureScript = Join-Path $PSScriptRoot "create_tsm_v4_parity_fixture.py"
& python $fixtureScript $InputModel $parityDirectory
if ($LASTEXITCODE -ne 0) { throw "Failed to create TSM V4 parity fixture" }

$packageRoot = $benchmark.Directory.Parent.Parent.FullName
$runtimeLib = Join-Path $packageRoot "runtime\lib"
$glogLib = Join-Path $packageRoot "runtime\third_party\glog"
$jpegLib = Join-Path $packageRoot "runtime\third_party\libjpeg-turbo\lib"
$env:PATH = "$runtimeLib;$glogLib;$jpegLib;$env:PATH"
$inputFile = Join-Path $parityDirectory "input.bin"
$expectedFile = Join-Path $parityDirectory "expected.txt"
& $benchmark.FullName --modelFile=$outputModel `
    --inDataFile=$inputFile --benchmarkDataFile=$expectedFile `
    --accuracyThreshold=0.001 --loopCount=1 --warmUpLoopCount=0 --numThreads=2
if ($LASTEXITCODE -ne 0) { throw "TSM V4 ONNX/MindIR Lite parity verification failed with exit code $LASTEXITCODE" }

Get-FileHash -LiteralPath $outputModel -Algorithm SHA256
