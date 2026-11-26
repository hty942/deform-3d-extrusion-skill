<#
.SYNOPSIS
  Turn a numbered PNG sequence (DEFORM Post screenshots) into MP4 or GIF.

.DESCRIPTION
  Frames must be numbered in playback order (frame_0001.png, frame_0002.png ...).
  Fixed camera and fixed legend range give a clean animation; changing the
  auto-scaled legend between frames makes it flicker.

.EXAMPLE
  .\frames_to_video.ps1 -FrameDir .\frames -Fps 6 -Out .\extrusion.mp4

.EXAMPLE
  .\frames_to_video.ps1 -FrameDir .\frames -Fps 8 -Out .\extrusion.gif -Gif
#>
param(
  [Parameter(Mandatory = $true)][string]$FrameDir,
  [double]$Fps = 6,
  [Parameter(Mandatory = $true)][string]$Out,
  [string]$Pattern = "*.png",
  [switch]$Gif,
  [string]$Ffmpeg = ""
)

$ErrorActionPreference = "Stop"

if (-not $Ffmpeg) {
  $cmd = Get-Command ffmpeg -ErrorAction SilentlyContinue
  if ($cmd) { $Ffmpeg = $cmd.Source }
}
if (-not $Ffmpeg -or -not (Test-Path $Ffmpeg)) {
  $fallback = Join-Path $env:LOCALAPPDATA "Programs\yt-dlp\ffmpeg.exe"
  if (Test-Path $fallback) { $Ffmpeg = $fallback }
}
if (-not $Ffmpeg -or -not (Test-Path $Ffmpeg)) {
  throw "ffmpeg not found. Install it or pass -Ffmpeg <path>."
}

$dir = (Resolve-Path $FrameDir).Path
$frames = Get-ChildItem $dir -Filter $Pattern | Sort-Object Name
if ($frames.Count -eq 0) { throw "no frames matching $Pattern in $dir" }
Write-Host "frames: $($frames.Count)"

$start = $null
$firstName = $frames[0].Name
if ($firstName -match '(\d+)') {
  $start = [int]$Matches[1]
} else {
  throw "frame names must contain a number, e.g. frame_0001.png"
}
$inputName = [regex]::Replace($firstName, '\d+', '%04d')
$inputPattern = Join-Path $dir $inputName

$args = @("-y", "-framerate", "$Fps", "-start_number", "$start", "-i", $inputPattern)
if ($Gif) {
  $args += @("-vf", "scale=iw:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse", "-loop", "0")
} else {
  $args += @("-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20")
}
$args += $Out

& $Ffmpeg @args
if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed with exit code $LASTEXITCODE" }
Write-Host "written $Out"
