# Автозапуск воркера при вході в Windows (задача Планувальника). Прибрати: autostart.ps1 -Remove
param([switch]$Remove)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')
$TaskName = 'Family Cashflow Voice'
if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Автозапуск вимкнено ($TaskName)"
    exit 0
}
$VoiceHome = Get-VoiceHome ''
$pyw = Join-Path $VoiceHome 'venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $pyw)) { throw "Немає $pyw, спершу запустіть install.ps1" }
$worker = Join-Path $ScriptDir 'worker.py'
# pythonw напряму, без powershell: жодного вікна консолі при вході. Другий екземпляр сам не стартує.
$action = New-ScheduledTaskAction -Execute $pyw -Argument "`"$worker`" --home `"$VoiceHome`"" -WorkingDirectory $ScriptDir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Description 'Мовний сервіс бота: розпізнавання і озвучення' -Force | Out-Null
Write-Host "Автозапуск увімкнено: задача '$TaskName', старт при вході в систему"
