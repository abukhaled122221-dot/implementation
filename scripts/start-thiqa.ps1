[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$NoBrowser,
    [switch]$NonInteractive,
    [ValidateRange(1,65535)][int]$SitePort = 3000,
    [ValidateRange(1,65535)][int]$AgentsPort = 8000,
    [ValidateRange(1,65535)][int]$InsurersPort = 8001
)
$ErrorActionPreference = 'Stop'
$Root = if ($env:THIQA_ROOT) { [IO.Path]::GetFullPath($env:THIQA_ROOT) } else { [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')) }
function Stop-Launcher([string]$Message) { Write-Host "ERROR: $Message" -ForegroundColor Red; exit 1 }
function Find-Python {
    $ErrorActionPreference = 'Continue'
    if ($env:THIQA_PYTHON) {
        if (-not (Test-Path -LiteralPath $env:THIQA_PYTHON -PathType Leaf)) { Stop-Launcher "THIQA_PYTHON points to a missing executable: $env:THIQA_PYTHON" }
        $v = & $env:THIQA_PYTHON -c "import sys; print('%d.%d'%sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -ne 0 -or [version]$v -lt [version]'3.10') { Stop-Launcher 'THIQA_PYTHON must be a working Python 3.10+ executable.' }
        return $env:THIQA_PYTHON
    }
    $candidates = @()
    if (Test-Path (Join-Path $Root '.venv\Scripts\python.exe')) { $candidates += (Join-Path $Root '.venv\Scripts\python.exe') }
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        $actual = & $py.Source -3 -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0) { $candidates += $actual }
    }
    foreach ($name in @('python.exe','python3.exe')) { $cmd=Get-Command $name -ErrorAction SilentlyContinue; if ($cmd -and $cmd.Source -notmatch '\\WindowsApps\\') { $candidates += $cmd.Source } }
    $uvRoot = Join-Path $env:APPDATA 'uv\python'
    if (Test-Path $uvRoot) { $candidates += Get-ChildItem $uvRoot -Filter python.exe -File -Recurse -ErrorAction SilentlyContinue | ForEach-Object FullName }
    foreach ($exe in ($candidates | Select-Object -Unique)) {
        if ($exe -eq 'py.exe') { $v = & py.exe -3 -c "import sys; print('%d.%d'%sys.version_info[:2])" 2>$null; if ($LASTEXITCODE -eq 0 -and [version]$v -ge [version]'3.10') { return 'py.exe' } }
        else { $v = & $exe -c "import sys; print('%d.%d'%sys.version_info[:2])" 2>$null; if ($LASTEXITCODE -eq 0 -and [version]$v -ge [version]'3.10') { return $exe } }
    }
    Stop-Launcher 'Python 3.10+ was not found. Install Python from https://www.python.org/downloads/ or set THIQA_PYTHON to python.exe.'
}
function Wait-Service([int]$Port,[string]$Expected,[DateTime]$Deadline) {
    while ([DateTime]::UtcNow -lt $Deadline) {
        if (Probe-Http $Port $Expected) { return }
        # Preflight rejects foreign listeners. A newly started service may take time to initialize.
        # Allow it to become ready until the bounded deadline, without opening a browser.
        Start-Sleep -Milliseconds 500
    }
    $logPath = Join-Path $Root ".runtime\$Port.stderr.log"
    if (Test-Path $logPath) { Get-Content $logPath -Tail 12 | Write-Host }
    Stop-Launcher "Service $Expected did not become healthy on port $Port within 60 seconds. Read $logPath"
}
function Test-PythonDeps([string]$Exe) {
    $ErrorActionPreference = 'Continue'
    $code = "import fastapi,uvicorn,pydantic,httpx; assert int(pydantic.__version__.split('.')[0])>=2"
    if ($Exe -eq 'py.exe') { & py.exe -3 -c $code 2>$null } else { & $Exe -c $code 2>$null }
    return ($LASTEXITCODE -eq 0)
}
function Invoke-Python([string]$Exe,[string[]]$Arguments) {
    $ErrorActionPreference = 'Continue'
    if ($Exe -eq 'py.exe') { & py.exe -3 @Arguments } else { & $Exe @Arguments }
    if ($LASTEXITCODE -ne 0) { Stop-Launcher 'Python setup failed. Read the installation error above. No browser was opened.' }
}
function Find-Node {
    $cmd=Get-Command node.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($p in @((Join-Path $env:ProgramFiles 'nodejs\node.exe'),(Join-Path $env:LOCALAPPDATA 'Programs\nodejs\node.exe'))) { if (Test-Path $p) { return $p } }
    Stop-Launcher 'Node.js was not found. Install Node.js 22.13+ from https://nodejs.org/.'
}
function Probe-Http([int]$Port,[string]$Expected) {
    $healthPath = if ($Expected -eq 'thiqa-node-server') { '/api/health' } else { '/health' }
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:$Port$healthPath" -TimeoutSec 2 -Proxy $null
        return ($r.service -eq $Expected -and $r.status -eq 'ok')
    } catch { return $false }
}
function Test-PortFree([int]$Port,[string]$Expected) {
    if (Probe-Http $Port $Expected) { return 'healthy' }
    $listener=Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    if ($listener) { Stop-Launcher "Port $Port is occupied by a service that is not $Expected. Stop it or choose another port." }
    return 'free'
}
try {
    if (@(@($SitePort,$AgentsPort,$InsurersPort) | Select-Object -Unique).Count -ne 3) { Stop-Launcher 'Choose three different service ports.' }
    foreach ($d in @('server','agents')) { if (-not (Test-Path (Join-Path $Root $d) -PathType Container)) { Stop-Launcher "Project folder missing: $(Join-Path $Root $d). Place this launcher at the project root or set THIQA_ROOT." } }
    # Refuse occupied ports before any installs or launches, including CheckOnly.
    $s=Test-PortFree $SitePort 'thiqa-node-server'; $a=Test-PortFree $AgentsPort 'thiqa-agents'; $i=Test-PortFree $InsurersPort 'thiqa-mock-insurers'
    $python=Find-Python
    $node=Find-Node
    $nv=& $node -p "process.versions.node" 2>$null
    if ($LASTEXITCODE -ne 0 -or [version]$nv -lt [version]'22.13') { Stop-Launcher "Node.js 22.13+ required; found $nv. Install from https://nodejs.org/." }
    & $node --disable-warning=ExperimentalWarning -e "require('node:sqlite')" 2>$null
    if ($LASTEXITCODE -ne 0) { Stop-Launcher 'Node runtime lacks node:sqlite; use Node.js 22.13+.' }
    $env:PATH = (Split-Path $node) + ';' + $env:PATH
    $npm=Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npm) { Stop-Launcher 'npm.cmd not found; reinstall Node.js 22.13+ from https://nodejs.org/.' }
    $siteDeps=$false
    Push-Location (Join-Path $Root 'server')
    try {
        $ErrorActionPreference = 'Continue'
        & $node -e "require('express');require('bcryptjs');require('cookie-parser')" 2>$null
        $siteDeps=($LASTEXITCODE -eq 0)
    } finally { $ErrorActionPreference = 'Stop'; Pop-Location }
    $pyDeps=Test-PythonDeps $python
    if (-not $siteDeps -or -not $pyDeps) {
        if ($CheckOnly) { Stop-Launcher 'CheckOnly: dependencies are missing; no files were changed. Run the launcher normally to install project dependencies.' }
        if (-not $pyDeps) {
            $venv=Join-Path $Root '.venv\Scripts\python.exe'
            if (-not (Test-Path $venv)) { Invoke-Python -Exe $python -Arguments @('-m','venv',(Join-Path $Root '.venv')) }
            $python=$venv
            Invoke-Python -Exe $python -Arguments @('-m','pip','install','-r',(Join-Path $Root 'agents\requirements.txt'))
            if (-not (Test-PythonDeps $python)) { Stop-Launcher 'Python dependencies remain unavailable after installation.' }
        }
        if (-not $siteDeps) { & $npm.Source 'ci' --prefix (Join-Path $Root 'server'); if ($LASTEXITCODE -ne 0) { Stop-Launcher 'npm ci failed. Check server/package-lock.json and network access.' } }
    }
    if ($CheckOnly) { Write-Host "CheckOnly OK: Python $python; Node $nv; dependencies available."; exit 0 }
    $env:THIQA_DB_PATH=if ($env:THIQA_DB_PATH) {$env:THIQA_DB_PATH} else {Join-Path $Root 'database\thiqa.db'}
    $env:INSURERS_DB_PATH=if ($env:INSURERS_DB_PATH) {$env:INSURERS_DB_PATH} else {Join-Path $Root 'database\insurers_mock.db'}
    $env:PORT="$SitePort"; $env:AGENTS_SERVICE_URL="http://127.0.0.1:$AgentsPort"; $env:INSURER_PLATFORM_URL="http://127.0.0.1:$InsurersPort"
    New-Item -ItemType Directory -Path (Join-Path $Root '.runtime') -Force | Out-Null
    Write-Host "Project: $Root`nPython: $python`nNode: $node"
    if ($s -eq 'free') {
        Write-Host "Starting service on port $SitePort..."
        Start-Process -FilePath $node -ArgumentList @('--disable-warning=ExperimentalWarning','server.js') -WorkingDirectory (Join-Path $Root 'server') -RedirectStandardOutput (Join-Path $Root ".runtime\$SitePort.stdout.log") -RedirectStandardError (Join-Path $Root ".runtime\$SitePort.stderr.log")
    }
    Wait-Service $SitePort 'thiqa-node-server' ([DateTime]::UtcNow.AddSeconds(60))
    if ($i -eq 'free') {
        Write-Host "Starting service on port $InsurersPort..."
        Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','mock_insurer_api:app','--host','127.0.0.1','--port',"$InsurersPort") -WorkingDirectory (Join-Path $Root 'agents') -RedirectStandardOutput (Join-Path $Root ".runtime\$InsurersPort.stdout.log") -RedirectStandardError (Join-Path $Root ".runtime\$InsurersPort.stderr.log")
    }
    Wait-Service $InsurersPort 'thiqa-mock-insurers' ([DateTime]::UtcNow.AddSeconds(60))
    if ($a -eq 'free') {
        Write-Host "Starting service on port $AgentsPort..."
        Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','main:app','--host','127.0.0.1','--port',"$AgentsPort") -WorkingDirectory (Join-Path $Root 'agents') -RedirectStandardOutput (Join-Path $Root ".runtime\$AgentsPort.stdout.log") -RedirectStandardError (Join-Path $Root ".runtime\$AgentsPort.stderr.log")
    }
    Wait-Service $AgentsPort 'thiqa-agents' ([DateTime]::UtcNow.AddSeconds(60))
    Write-Host "THIQA ready: http://localhost:$SitePort (agents $AgentsPort; insurers $InsurersPort)."
    if (-not $NoBrowser) { Start-Process "http://localhost:$SitePort"; Start-Process "http://127.0.0.1:$InsurersPort" }
    Write-Host "Admin dashboard: http://localhost:$SitePort/admin/login.html"
} catch { Stop-Launcher $_.Exception.Message }
