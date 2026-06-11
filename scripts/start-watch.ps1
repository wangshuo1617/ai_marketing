param(
    [int]$Port = 8010,
    [int]$RestartDelaySeconds = 3,
    [switch]$KillExistingPortProcess
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $ProjectRoot "logs"
$LogFile = Join-Path $LogDir "web-watch.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $ProjectRoot

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] $Message"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

function Stop-PortProcess {
    param([int]$TargetPort)
    $connections = Get-NetTCPConnection -LocalPort $TargetPort -State Listen -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
        if ($connection.OwningProcess -and $connection.OwningProcess -ne $PID) {
            Write-Log "Stopping process $($connection.OwningProcess) using port $TargetPort"
            Stop-Process -Id $connection.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}

if ($KillExistingPortProcess) {
    Stop-PortProcess -TargetPort $Port
}

$env:WEB_PORT = [string]$Port
Write-Log "Starting AI consulting content workspace watcher on http://127.0.0.1:$Port"
Write-Log "Project root: $ProjectRoot"
Write-Log "Press Ctrl+C to stop. Logs: $LogFile"

while ($true) {
    try {
        Write-Log "Launching web workspace process"
        & python main.py --workflow web
        $exitCode = $LASTEXITCODE
        Write-Log "Web workspace exited with code $exitCode"
    }
    catch {
        Write-Log "Web workspace crashed: $($_.Exception.Message)"
    }

    Write-Log "Restarting in $RestartDelaySeconds seconds"
    Start-Sleep -Seconds $RestartDelaySeconds
}
