<#
.SYNOPSIS
  Export a DEFORM-3D database to a keyword file without the GUI.

.DESCRIPTION
  Drives DEF_PRE_64.exe through its text menu by feeding a fixed stdin script:
      <blank>      consume the startup "Hit <CR>" prompt
      2            File Input
      2            Input DEFORM Data Base
      <DB path>
      <step>       step number to export (must exist in the DB)
      <blank>      consume the post-read "Hit <CR>"
      E            back to main menu
      8            Keyword Values Save
      <out.KEY>
      E
      Y

  Notes
    * The exported KEY can be very large (a 613k-element model -> ~284 MB).
    * DB files can only be read when no solver is running on them.
    * The exported KEY contains RZ / URZ / NDTMP / ELMCON / STRAIN / STRESS blocks,
      which scripts/key_metrics.py understands.

.EXAMPLE
  .\export_db_key.ps1 -CaseDir C:\cases\c10 -Database c10.DB -Out c10_out.KEY
#>
param(
  [Parameter(Mandatory = $true)][string]$CaseDir,
  [Parameter(Mandatory = $true)][string]$Database,
  [Parameter(Mandatory = $true)][string]$Out,
  [int]$Step = 1,
  [string]$DeformRoot = "D:\Program Files\SFTC\DEFORM\v11.0"
)

$ErrorActionPreference = "Stop"

$caseDirFull = (Resolve-Path $CaseDir).Path
$dbFull = Join-Path $caseDirFull $Database
if (-not (Test-Path $dbFull)) {
  if (Test-Path (Join-Path $caseDirFull "FOR003")) {
    throw "DB not found: $dbFull (FOR003 exists - a run is in progress or was killed; restore FOR003 first)"
  }
  throw "DB not found: $dbFull"
}

$pre = Join-Path $DeformRoot "DEF_PRE_64.exe"
if (-not (Test-Path $pre)) { throw "DEF_PRE_64.exe not found: $pre" }

$outFull = if ([IO.Path]::IsPathRooted($Out)) { $Out } else { Join-Path $caseDirFull $Out }

$tmpIn = Join-Path $env:TEMP ("defpre_in_" + [guid]::NewGuid().ToString("N") + ".txt")
$tmpLog = Join-Path $env:TEMP ("defpre_out_" + [guid]::NewGuid().ToString("N") + ".txt")

$lines = @(
  "",
  "2",
  "2",
  $dbFull,
  "$Step",
  "",
  "E",
  "8",
  $outFull,
  "E",
  "Y"
)
[IO.File]::WriteAllText($tmpIn, ($lines -join "`r`n") + "`r`n", [Text.Encoding]::ASCII)

Write-Host "Exporting $dbFull (step $Step) -> $outFull"
Write-Host "This can take several minutes for large databases..."

$p = Start-Process -FilePath $pre -WorkingDirectory $caseDirFull `
  -RedirectStandardInput $tmpIn -RedirectStandardOutput $tmpLog `
  -NoNewWindow -PassThru -Wait

Write-Host "DEF_PRE_64 exit code: $($p.ExitCode)"

# A nonexistent step does NOT fail: DEF_PRE_64 still writes a ~2 KB skeleton KEY
# with no mesh. So "file exists" is not enough - require an RZ block.
$hasRz = $false
if (Test-Path $outFull) {
  $sr = New-Object IO.StreamReader($outFull)
  try {
    for ($i = 0; $i -lt 5000 -and -not $sr.EndOfStream; $i++) {
      if ($sr.ReadLine() -match '^RZ\s') { $hasRz = $true; break }
    }
  } finally { $sr.Close() }
}

if ($hasRz) {
  $mb = [math]::Round((Get-Item $outFull).Length / 1MB, 1)
  Write-Host "OK: $outFull ($mb MB)"
  Write-Host "Menu log: $tmpLog"
} else {
  Write-Host "FAILED: no RZ block in the exported KEY."
  Write-Host "Most likely step $Step does not exist in this database."
  Write-Host "Open the database in Post, read the Step list, and pass an existing step with -Step."
  Write-Host "Menu log below:"
  Get-Content $tmpLog -Tail 40
  exit 1
}
