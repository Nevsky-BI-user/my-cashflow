param()
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    & python -m venv (Join-Path $projectRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Не вдалося створити .venv' }
}
& $pythonPath -m pip install -r (Join-Path $projectRoot 'requirements-dev.txt')
if ($LASTEXITCODE -ne 0) { throw 'Не вдалося встановити інструменти перевірки' }
& $pythonPath -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw 'Не вдалося підготувати Chromium' }
Write-Output 'Готово. Перевірки: .\.venv\Scripts\python.exe spec/run.py'
Write-Output 'Перегляд застосунку: .\.venv\Scripts\python.exe scripts/dev-preview.py --target app'
