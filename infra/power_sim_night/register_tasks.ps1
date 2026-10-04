# register_tasks.ps1 -- register (or remove) the nightly start / stop tasks for the power_sim main run.
#
# Question it answers: "run start_night.ps1 every night at 21:00 and stop_night.ps1 at 06:00".
# YOU run this once (a human decision; an agent does not change scheduler / power settings).
#   register:   powershell -ExecutionPolicy Bypass -File infra\power_sim_night\register_tasks.ps1 -OutName run1 -ThroughStage 1
#   remove:     powershell -ExecutionPolicy Bypass -File infra\power_sim_night\register_tasks.ps1 -Unregister
#   preview:    add -DryRun (prints what would be registered, changes nothing)
# To move on to the next stage, register again with -ThroughStage 2 (it replaces the tasks).
#
# Needs you to stay logged in (screen off / locked / lid closed with "do nothing" on AC is fine; log-off is not).
# ASCII only on purpose (Windows PowerShell 5.1 reads BOM-less files as ANSI).

param(
    [string]$OutName = "",
    [ValidateSet(1, 2, 3)][int]$ThroughStage = 1,
    [int]$Workers = 16,
    [string]$RLibs = "",   # dir that holds lme4 when the scheduler cannot see your R user library
    [string]$StartTime = "21:00",
    [string]$StopTime = "06:00",
    [switch]$Unregister,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$StartTask = "PowerSimNightStart"
$StopTask = "PowerSimNightStop"

if ($Unregister) {
    foreach ($name in @($StartTask, $StopTask)) {
        if ($DryRun) { Write-Host "DRY RUN: would unregister $name"; continue }
        if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
            Unregister-ScheduledTask -TaskName $name -Confirm:$false
            Write-Host "unregistered $name"
        } else {
            Write-Host "$name was not registered"
        }
    }
    exit 0
}

if (-not $OutName) { throw "-OutName is required (for example run1)" }

$ScriptDir = $PSScriptRoot
$pythonPath = (Get-Command python -ErrorAction Stop).Source   # bake the full path in: the task may not see your PATH
$ps = "powershell.exe"
$startArgs = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}" -OutName {1} -ThroughStage {2} -Workers {3} -Python "{4}"' -f `
    (Join-Path $ScriptDir "start_night.ps1"), $OutName, $ThroughStage, $Workers, $pythonPath
if ($RLibs) { $startArgs += (' -RLibs "{0}"' -f $RLibs) }
$stopArgs = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}" -OutName {1}' -f `
    (Join-Path $ScriptDir "stop_night.ps1"), $OutName

if ($DryRun) {
    Write-Host "DRY RUN: would register"
    Write-Host ("  {0} daily {1}: {2} {3}" -f $StartTask, $StartTime, $ps, $startArgs)
    Write-Host ("  {0} daily {1}: {2} {3}" -f $StopTask, $StopTime, $ps, $stopArgs)
    exit 0
}

$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited

# Start: wake the machine for it; start_night.ps1 itself refuses on battery. No StartWhenAvailable:
# a missed 21:00 must not turn into a start at 10:00 the next morning.
$startSettings = New-ScheduledTaskSettingsSet -WakeToRun -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName $StartTask -Force -Principal $principal -Settings $startSettings `
    -Trigger (New-ScheduledTaskTrigger -Daily -At $StartTime) `
    -Action (New-ScheduledTaskAction -Execute $ps -Argument $startArgs) | Out-Null

# Stop: must run on battery too.
$stopSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName $StopTask -Force -Principal $principal -Settings $stopSettings `
    -Trigger (New-ScheduledTaskTrigger -Daily -At $StopTime) `
    -Action (New-ScheduledTaskAction -Execute $ps -Argument $stopArgs) | Out-Null

Write-Host ("registered {0} ({1}) and {2} ({3}); out-dir results/power_sim/{4}, through-stage {5}" -f `
    $StartTask, $StartTime, $StopTask, $StopTime, $OutName, $ThroughStage)
Write-Host "check: Get-ScheduledTask PowerSimNight* | Get-ScheduledTaskInfo"
