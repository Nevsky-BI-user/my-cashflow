# Спільне для скриптів: де лежить сервіс і його локальні файли.
$ScriptDir = $PSScriptRoot

function Get-RepoRoot {
    # Перша тека вгору з каталогом .git: у робочій копії гілки .git це файл, її пропускаємо
    $d = Get-Item -LiteralPath $ScriptDir
    while ($d) {
        if (Test-Path -LiteralPath (Join-Path $d.FullName '.git') -PathType Container) { return $d.FullName }
        $d = $d.Parent
    }
    throw 'Не знайшов корінь репозиторію'
}

function Get-VoiceHome([string]$HomeDir) {
    if ($HomeDir) { return $HomeDir }
    if ($env:VOICE_HOME) { return $env:VOICE_HOME }
    return (Join-Path (Get-RepoRoot) '.local\voice-service')
}

function Get-WorkerProcess([string]$VoiceHome) {
    # Живий процес воркера за pid-файлом; чужий процес із тим самим pid не рахується
    $pidFile = Join-Path $VoiceHome 'worker.pid'
    if (-not (Test-Path -LiteralPath $pidFile)) { return $null }
    $procId = (Get-Content -LiteralPath $pidFile -Raw).Trim()
    if (-not $procId) { return $null }
    $p = Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue
    if ($p -and $p.CommandLine -match 'worker\.py') { return $p }
    return $null
}
