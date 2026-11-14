# Встановлення: venv, пакети, config.json із секретом. Повторний запуск безпечний.
param([string]$Python = '')
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')
$Root = Get-RepoRoot
$VoiceHome = Get-VoiceHome ''
New-Item -ItemType Directory -Force -Path (Join-Path $VoiceHome 'logs') | Out-Null

# 1. Python 3.13
$pyArgs = @()
if (-not $Python) {
    if (Get-Command py -ErrorAction SilentlyContinue) { $Python = 'py'; $pyArgs = @('-3.13') }
    else { $Python = 'python' }
}
$ver = & $Python @pyArgs -c 'import sys; print(str(sys.version_info[0]) + chr(46) + str(sys.version_info[1]))'
if ($ver -ne '3.13') { throw "Потрібен Python 3.13, знайдено '$ver'. Вкажіть шлях: install.ps1 -Python C:\...\python.exe" }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Потрібен git: частина пакетів ставиться з GitHub' }

# 2. Віртуальне середовище і пакети
$venv = Join-Path $VoiceHome 'venv'
$vpy = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $vpy)) {
    Write-Host "Створюю venv: $venv"
    & $Python @pyArgs -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'Не вдалося створити venv' }
}
Write-Host 'Ставлю пакети (уперше кілька хвилин, близько 3 ГБ)...'
& $vpy -m pip install --disable-pip-version-check -r (Join-Path $ScriptDir 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'pip install завершився з помилкою' }
if (-not (Test-Path -LiteralPath (Join-Path $venv 'Scripts\pythonw.exe'))) { throw 'У venv немає pythonw.exe' }

# 3. Код сервісу в .local: запуск не залежить від того, яка гілка зараз відкрита в робочій теці
foreach ($f in @('worker.py', '_common.ps1', 'start.ps1', 'stop.ps1', 'status.ps1', 'autostart.ps1')) {
    Copy-Item -LiteralPath (Join-Path $ScriptDir $f) -Destination (Join-Path $VoiceHome $f) -Force
}
Write-Host "Код сервісу скопійовано в $VoiceHome"

# 4. Конфіг із секретом
$cfgPath = Join-Path $VoiceHome 'config.json'
$voiceNpy = Join-Path $Root '.local\voice\voice.npy'
if (-not (Test-Path -LiteralPath $cfgPath)) {
    $bytes = New-Object byte[] 24
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $rng.Dispose()
    $secret = -join ($bytes | ForEach-Object { $_.ToString('x2') })
    $cfg = [ordered]@{
        supabase_url = 'https://lisedsqwdzshsxydghag.supabase.co'
        voice_secret = $secret
        voice_npy    = $voiceNpy
        device       = 'auto'
    }
    [IO.File]::WriteAllText($cfgPath, ($cfg | ConvertTo-Json), (New-Object Text.UTF8Encoding $false))
    Write-Host ''
    Write-Host "Створено $cfgPath"
    Write-Host 'Секрет показується один раз. Покладіть його в секрети Supabase:'
    Write-Host "  supabase secrets set VOICE_SECRET=$secret"
    Write-Host 'Без цього сервер відповідатиме воркеру 401.'
    Write-Host ''
} else {
    Write-Host "config.json уже є, секрет не змінюю: $cfgPath"
    $voiceNpy = (Get-Content -LiteralPath $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json).voice_npy
}

# 5. Вектор голосу
if (Test-Path -LiteralPath $voiceNpy) { Write-Host "Вектор голосу на місці: $voiceNpy" }
else { Write-Warning "Немає вектора голосу ${voiceNpy}: озвучення не запуститься. Шлях задається в config.json (voice_npy)." }
Write-Host "Готово. Запуск, стан і зупинка: start.ps1, status.ps1, stop.ps1 у теці $VoiceHome"
