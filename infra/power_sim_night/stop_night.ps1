# stop_night.ps1 -- PLAN-040 power_sim main run: stop tonight's run (cleanly enough to resume).
#
# Question it answers: "is anything of the power_sim run still alive, and if so, kill its whole tree".
# Safe to kill at any moment: R writes each fits/*.json to a .tmp and renames (power_sim_fit.R),
# so a kill loses only the replications in flight (<= --workers of them, about 5-20 minutes of work),
# never leaves a half-written JSON. The next start_night.ps1 resumes (appendix A.5).
#
# Run it as the scheduled 06:00 task, or by hand before leaving home. It works on battery too.
# ASCII only on purpose (Windows PowerShell 5.1 reads BOM-less files as ANSI).

param(
    [string]$OutName = "",   # only used to pick the log file name
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$SimDir = Join-Path $RepoRoot "results/power_sim"
$logName = if ($OutName) { "{0}_night_stdout.txt" -f $OutName } else { "night_stdout.txt" }
$NightLog = Join-Path $SimDir $logName

function Write-Night([string]$Message) {
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Write-Host $line
    if (-not $DryRun) {
        New-Item -ItemType Directory -Force $SimDir | Out-Null
        Add-Content -Path $NightLog -Value $line -Encoding UTF8
    }
}

function Get-SimPython {
    Get-CimInstance Win32_Process |
        Where-Object { $_.Name -like "python*" -and $_.CommandLine -like "*code.analysis.power_sim*" -and $_.ProcessId -ne $PID }
}

function Get-SimRscript {
    Get-CimInstance Win32_Process |
        Where-Object { $_.Name -like "Rscript*" -and $_.CommandLine -like "*power_sim_fit.R*" }
}

$pythons = @(Get-SimPython)
$rscripts = @(Get-SimRscript)
if ($pythons.Count -eq 0 -and $rscripts.Count -eq 0) {
    Write-Night "nothing to stop (no power_sim python, no power_sim_fit.R Rscript)"
    exit 0
}

if ($DryRun) {
    Write-Host ("DRY RUN: would kill python pid {0} (with its process tree) and {1} Rscript process(es)" -f `
        (($pythons | ForEach-Object { $_.ProcessId }) -join ","), $rscripts.Count)
    exit 0
}

# the python process first (/T takes the Rscript / R children with it), then any orphaned Rscript
foreach ($p in $pythons) {
    & taskkill.exe /T /F /PID $p.ProcessId | Out-Null
}
Start-Sleep -Seconds 3
foreach ($r in @(Get-SimRscript)) {
    & taskkill.exe /T /F /PID $r.ProcessId | Out-Null
}
Start-Sleep -Seconds 2

$left = @(Get-SimPython).Count + @(Get-SimRscript).Count
$done = (Get-ChildItem -Path (Join-Path $SimDir "*/fits/*.json") -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Night ("stopped: killed python {0} / Rscript {1}; still alive {2}; fits/*.json so far {3}" -f $pythons.Count, $rscripts.Count, $left, $done)
if ($left -gt 0) { exit 1 }
exit 0
