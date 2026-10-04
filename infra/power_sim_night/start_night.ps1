# start_night.ps1 -- PLAN-040 power_sim main run: start (or resume) one night's worth.
#
# Question it answers: "can tonight's run start safely, and if so, start it detached?"
# The run resumes from fits/*.json already on disk (PLAN-040 appendix A.5), so calling this
# every night with the same -OutName / -ThroughStage continues where the last night stopped.
#
# Never start it from an agent session. Run it yourself, or let the scheduled task run it
# (register_tasks.ps1). ASCII only on purpose: Windows PowerShell 5.1 reads BOM-less files as ANSI.
#
# Exit codes: 0 = started / already running / nothing left to do, 1 = refused (reason printed + logged)

param(
    [Parameter(Mandatory = $true)][string]$OutName,
    [Parameter(Mandatory = $true)][ValidateSet(1, 2, 3)][int]$ThroughStage,
    [int]$Workers = 16,
    [string]$Python = "python",
    [string]$RLibs = "",   # extra R library dir (-> R_LIBS). Needed when the task cannot see the lme4 you installed
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# stage index -> cumulative n_rep (configs/power_sim.yaml: stages [100, 300, 1000])
$StageReps = @{ 1 = 100; 2 = 300; 3 = 1000 }
# Win32_Battery.BatteryStatus values that mean "plugged in" (2 AC, 3 full, 6-9 charging)
$AcStatuses = @(2, 3, 6, 7, 8, 9)

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot
$SimDir = Join-Path $RepoRoot "results/power_sim"
$OutDir = "results/power_sim/$OutName"
$NightLog = Join-Path $SimDir ("{0}_night_stdout.txt" -f $OutName)   # matches .gitignore *_stdout.txt

function Write-Night([string]$Message) {
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Write-Host $line
    if (-not $DryRun) {
        New-Item -ItemType Directory -Force $SimDir | Out-Null
        Add-Content -Path $NightLog -Value $line -Encoding UTF8
    }
}

function Stop-Refused([string]$Reason) {
    Write-Night ("REFUSED: " + $Reason)
    exit 1
}

# 1. already running? (match on the command line, no pid file to keep in sync)
$running = Get-CimInstance Win32_Process |
    Where-Object { $_.Name -like "python*" -and $_.CommandLine -like "*code.analysis.power_sim*" -and $_.CommandLine -notlike "*--dry-run*" }
if ($running) {
    Write-Night ("already running (pid {0}); nothing to do" -f (($running | ForEach-Object { $_.ProcessId }) -join ","))
    exit 0
}

# 2. is the requested stage already finished, or did the misspecification gate close?
$summaryPath = Join-Path $RepoRoot "$OutDir/power_sim_summary.json"
if (Test-Path $summaryPath) {
    $summary = Get-Content -Raw -Encoding UTF8 $summaryPath | ConvertFrom-Json
    if ($summary.stopped_at_gate) {
        Write-Night "the misspecification gate is closed (stopped_at_gate). Do NOT rerun: next is the Section 3.2 review PLAN (appendix A.4)"
        exit 0
    }
    if ([int]$summary.n_rep -ge $StageReps[$ThroughStage]) {
        Write-Night ("stage {0} (n_rep {1}) is already finished; nothing to do. A human decides the next stage (A.6)" -f $ThroughStage, $StageReps[$ThroughStage])
        exit 0
    }
}

# 3. A.1 checks that a script can do. Sleep / hibernate / Windows Update stay a human's job.
$battery = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue
if ($battery) {
    $status = [int](@($battery)[0].BatteryStatus)
    if ($AcStatuses -notcontains $status) {
        Stop-Refused ("on battery (BatteryStatus={0}). Plug in AC first (A.1 item 1)" -f $status)
    }
}
$leftover = Get-CimInstance Win32_Process | Where-Object { $_.Name -like "Rscript*" -and $_.CommandLine -like "*power_sim_fit.R*" }
if ($leftover) {
    Stop-Refused "Rscript (power_sim_fit.R) is still running; run stop_night.ps1 first (A.1 item 5)"
}
$dirty = git status --porcelain --untracked-files=no
if ($dirty) {
    Stop-Refused ("tracked files have changes; commit or stash first (A.1 item 6): " + (($dirty | Select-Object -First 3) -join " | "))
}

if ($RLibs) { $env:R_LIBS = $RLibs }   # the child python / Rscript inherit it
$rscriptExe = (Get-Command Rscript -ErrorAction SilentlyContinue).Source
if (-not $rscriptExe) {
    $rscriptExe = Get-ChildItem "C:/Program Files/R/R-*/bin/Rscript.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName | Select-Object -Last 1 -ExpandProperty FullName
}
if (-not $rscriptExe) { Stop-Refused "Rscript not found (PATH and C:/Program Files/R/R-*/bin)" }
& $rscriptExe -e "quit(status = as.integer(!requireNamespace('lme4', quietly = TRUE)))" 2>$null
if ($LASTEXITCODE -ne 0) {
    Stop-Refused ("R cannot load lme4 as this user/task (R_LIBS='{0}'). Pass -RLibs <dir containing lme4> (see register_tasks.ps1)" -f $RLibs)
}

# 4. launch detached, one stdout/stderr pair per night (outside the out-dir, as in A.2)
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$stdout = "results/power_sim/{0}_{1}_stdout.txt" -f $OutName, $stamp
$stderr = "results/power_sim/{0}_{1}_stderr.txt" -f $OutName, $stamp
$argList = @(
    "-m", "code.analysis.power_sim",
    "--config", "configs/power_sim.yaml",
    "--out-dir", $OutDir,
    "--through-stage", "$ThroughStage",
    "--workers", "$Workers"
)

if ($DryRun) {
    Write-Host "DRY RUN: all checks passed. Would launch:"
    Write-Host ("  {0} {1}" -f $Python, ($argList -join " "))
    Write-Host ("  stdout -> {0}" -f $stdout)
    exit 0
}

New-Item -ItemType Directory -Force $SimDir | Out-Null
$proc = Start-Process -FilePath $Python -ArgumentList $argList -WorkingDirectory $RepoRoot `
    -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
Write-Night ("started pid {0}: out-dir {1}, through-stage {2}, workers {3}; stdout {4}" -f $proc.Id, $OutDir, $ThroughStage, $Workers, $stdout)
exit 0
