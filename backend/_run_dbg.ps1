$log = "f:\demo1\backend\start_backend.log"
Remove-Item $log -ErrorAction SilentlyContinue
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "cmd.exe"
$psi.Arguments = "/c `"f:\demo1\start_backend.bat`" > `"$log`" 2>&1"
$psi.UseShellExecute = $false
$p = [System.Diagnostics.Process]::Start($psi)
Start-Sleep -Seconds 45
if (-not $p.HasExited) { $p.Kill() }
Start-Sleep -Seconds 1
Write-Host "===== LOG START ====="
Get-Content $log
Write-Host "===== LOG END ====="
