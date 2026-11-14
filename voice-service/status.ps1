# Чи працює воркер і що він писав останнім.
param([string]$HomeDir = '', [int]$Lines = 15)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')
$VoiceHome = Get-VoiceHome $HomeDir
$p = Get-WorkerProcess $VoiceHome
if ($p) {
    $mb = [math]::Round($p.WorkingSetSize / 1MB)
    Write-Host "Працює: pid $($p.ProcessId), памʼять $mb МБ, запущено $($p.CreationDate)"
} else { Write-Host 'Не працює' }
$logFile = Join-Path $VoiceHome 'logs\worker.log'
if (Test-Path -LiteralPath $logFile) {
    Write-Host "--- останні рядки $logFile"
    Get-Content -LiteralPath $logFile -Tail $Lines -Encoding UTF8
}
