# Зупинка воркера за pid-файлом.
param([string]$HomeDir = '')
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')
$VoiceHome = Get-VoiceHome $HomeDir
$p = Get-WorkerProcess $VoiceHome
if (-not $p) { Write-Host 'Воркер не запущений' } else {
    Stop-Process -Id $p.ProcessId -Force
    Write-Host "Воркер зупинено, pid $($p.ProcessId)"
}
$pidFile = Join-Path $VoiceHome 'worker.pid'
if (Test-Path -LiteralPath $pidFile) { Remove-Item -LiteralPath $pidFile -Force }
