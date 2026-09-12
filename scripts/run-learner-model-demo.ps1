<#
.SYNOPSIS
  CampusMateAI 学习模型演示入口
.DESCRIPTION
  从脚本位置解析仓库根目录，使用独立演示数据库，明确拒绝 production。
  支持四个场景：deadline-pressure, pointer-recovery, stale-source-replan, shadow-model-blocked
  不修改开发者现有数据库，不创建截图、日志、缓存、临时预测文件。
.PARAMETER Action
  seed | start | verify | clear | all
.PARAMETER Scenario
  场景名称，默认 all
.EXAMPLE
  .\scripts\run-learner-model-demo.ps1 -Action all
#>
param(
    [Parameter(Position=0)]
    [ValidateSet("seed","start","verify","clear","all")]
    [string]$Action = "all",

    [Parameter(Position=1)]
    [string]$Scenario = "all"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path "$ScriptDir\..").Path
$BackendDir = Join-Path $RepoRoot "backend"
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Error "Backend venv not found at $VenvPython. Run backend setup first."
    exit 1
}

$DemoDb = Join-Path $RepoRoot "backend\demo_learner_model.db"
if (Test-Path $DemoDb) { Remove-Item $DemoDb -Force }
$DbUrl = "sqlite:///$DemoDb"

$Scenarios = @("deadline-pressure","pointer-recovery","stale-source-replan","shadow-model-blocked")
if ($Scenario -ne "all" -and $Scenarios -notcontains $Scenario) {
    Write-Error "Unknown scenario: $Scenario. Valid: $($Scenarios -join ', ')"
    exit 1
}
$TargetScenarios = if ($Scenario -eq "all") { $Scenarios } else { @($Scenario) }

$Env = @{
    "APP_ENV" = "test"
    "DATABASE_URL" = $DbUrl
    "AUTO_SEED_DEMO_USERS" = "false"
    "AUTO_IMPORT_DEMO" = "false"
    "JWT_SECRET" = "demo_secret_not_for_production_use_only_32chars"
    "EDU_SESSION_STORE" = "memory"
}

function Invoke-Action {
    param([string]$Act, [string]$Scn)
    $Args = @("-m", "app.demo.learner_model")
    if ($Act -eq "seed") { $Args += @("seed", $Scn) }
    elseif ($Act -eq "clear") { $Args += @("clear", $Scn) }
    elseif ($Act -eq "verify") { $Args += @("seed", $Scn) }
    elseif ($Act -eq "start") { $Args += @("seed", $Scn) }

    foreach ($k in $Env.Keys) { Set-Item -Path "Env:$k" -Value $Env[$k] }
    & $VenvPython @Args
    $code = $LASTEXITCODE
    foreach ($k in $Env.Keys) { Remove-Item -Path "Env:$k" -ErrorAction SilentlyContinue }
    return $code
}

$Failed = @()

foreach ($scn in $TargetScenarios) {
    Write-Host "`n=== $Action : $scn ===" -ForegroundColor Cyan

    if ($Action -eq "all") {
        foreach ($act in @("seed","verify","clear")) {
            Write-Host "  $act $scn ..." -NoNewline
            $code = Invoke-Action -Act $act -Scn $scn
            if ($code -eq 0) {
                Write-Host " OK" -ForegroundColor Green
            } else {
                Write-Host " FAIL (exit $code)" -ForegroundColor Red
                $Failed += "$act/$scn"
            }
        }
    } else {
        Write-Host "  $Action $scn ..." -NoNewline
        $code = Invoke-Action -Act $Action -Scn $scn
        if ($code -eq 0) {
            Write-Host " OK" -ForegroundColor Green
        } else {
            Write-Host " FAIL (exit $code)" -ForegroundColor Red
            $Failed += "$Action/$scn"
        }
    }
}

if (Test-Path $DemoDb) { Remove-Item $DemoDb -Force }

if ($Failed.Count -gt 0) {
    Write-Host "`nFAILED: $($Failed -join ', ')" -ForegroundColor Red
    exit 1
} else {
    Write-Host "`nAll demo actions completed successfully." -ForegroundColor Green
    exit 0
}