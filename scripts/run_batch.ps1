<#
.SYNOPSIS
  Run a DEFORM-3D problem in batch mode (DEF_ARM.COM) and optionally wait.

.DESCRIPTION
  Always creates the empty "64bit.dat" marker first: without it DEF_ARM.COM
  silently runs the 32-bit solver and exits within a second.

  Progress is read from <name>.LOG / <name>.MSG.

.EXAMPLE
  .\run_batch.ps1 -CaseDir C:\cases\c10 -Name c10 -Wait

.EXAMPLE
  .\run_batch.ps1 -CaseDir C:\cases\c10 -Name c10 -DryRun
#>
param(
  [Parameter(Mandatory = $true)][string]$CaseDir,
  [Parameter(Mandatory = $true)][string]$Name,
  [string]$DeformRoot = "D:\Program Files\SFTC\DEFORM\v11.0",
  [switch]$Wait,
  [int]$PollSeconds = 30,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$dir = (Resolve-Path $CaseDir).Path
$arm = Join-Path $DeformRoot "3D\DEF_ARM.COM"
if (-not (Test-Path $arm)) { throw "DEF_ARM.COM not found: $arm" }

$db = Join-Path $dir "$Name.DB"
if (-not (Test-Path $db)) {
  if (Test-Path (Join-Path $dir "FOR003")) {
    throw "DB not found: $db (FOR003 exists - a run is in progress or was killed; restore FOR003 to $Name.DB first)"
  }
  throw "DB not found: $db"
}

$marker = Join-Path $dir "64bit.dat"
if (-not (Test-Path $marker)) {
  if (-not $DryRun) { New-Item -ItemType File -Path $marker | Out-Null }
  Write-Host "created 64bit.dat"
}

$log = Join-Path $dir "$Name.LOG"
$msg = Join-Path $dir "$Name.MSG"

Write-Host "DEF_ARM.COM $Name B  (cwd: $dir)"
if ($DryRun) { return }

$p = Start-Process -FilePath $arm -ArgumentList @($Name, "B") -WorkingDirectory $dir -PassThru -WindowStyle Hidden
Write-Host "started PID $($p.Id)"

if (-not $Wait) {
  Write-Host "not waiting; monitor $log"
  return
}

$lastPrint = Get-Date
while (-not $p.HasExited) {
  Start-Sleep -Seconds $PollSeconds
  $step = ""
  if (Test-Path $msg) {
    $m = Select-String -Path $msg -Pattern "STEP NUMBER\s*=\s*(-?\d+)" -ErrorAction SilentlyContinue |
         Select-Object -Last 1
    if ($m) { $step = $m.Matches[0].Groups[1].Value }
  }
  $stroke = ""
  $simTime = ""
  if (Test-Path $log) {
    $s = Select-String -Path $log -Pattern "UPDATED TIME/STROKE\s*=\s*([-0-9.E+]+)\s+([-0-9.E+]+)" -ErrorAction SilentlyContinue |
         Select-Object -Last 1
    if ($s) {
      $simTime = $s.Matches[0].Groups[1].Value
      $stroke = $s.Matches[0].Groups[2].Value
    }
  }
  Write-Host ("[{0:HH:mm:ss}] PID {1} alive  step={2}  time={3}  stroke={4}" -f (Get-Date), $p.Id, $step, $simTime, $stroke)
}

Write-Host "finished with exit code $($p.ExitCode)"
if (Test-Path $log) {
  Write-Host "--- last lines of $log ---"
  Get-Content $log -Tail 12
}
