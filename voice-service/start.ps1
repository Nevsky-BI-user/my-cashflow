# Запуск воркера у фоні без вікна (pythonw).
param([string]$HomeDir = '')
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')
$VoiceHome = Get-VoiceHome $HomeDir
$pyw = Join-Path (Get-VoiceHome '') 'venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $pyw)) { throw "Немає $pyw, спершу запустіть install.ps1" }
if (-not (Test-Path -LiteralPath (Join-Path $VoiceHome 'config.json'))) { throw "Немає config.json у $VoiceHome" }
$running = Get-WorkerProcess $VoiceHome
if ($running) { Write-Host "Воркер уже працює, pid $($running.ProcessId)"; exit 0 }
$worker = Join-Path $ScriptDir 'worker.py'
Start-Process -FilePath $pyw -ArgumentList @("`"$worker`"", '--home', "`"$VoiceHome`"") -WindowStyle Hidden -WorkingDirectory $ScriptDir
Write-Host 'Воркер запущено. Моделі вантажаться до хвилини, стан: status.ps1'
