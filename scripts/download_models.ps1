# Download MediaPipe model files into models/ and verify their SHA-256.
# Source: Google's official MediaPipe model storage. Model files are git-ignored.
param([switch]$Force)
$ErrorActionPreference = 'Stop'
$models = @(
  @{ Name = 'blaze_face_short_range.tflite'
     Url  = 'https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite'
     Sha256 = 'b4578f35940bf5a1a655214a1cce5cab13eba73c1297cd78e1a04c2380b0152f' }
  # hand_landmarker.task is added in milestone 6.1 together with its pinned hash
)
$dir = Join-Path $PSScriptRoot '..\models'
New-Item -ItemType Directory -Force $dir | Out-Null
foreach ($m in $models) {
  $path = Join-Path $dir $m.Name
  if ((Test-Path $path) -and -not $Force) {
    $hash = (Get-FileHash $path -Algorithm SHA256).Hash.ToLower()
    if ($hash -eq $m.Sha256) { Write-Output "OK (already present): $($m.Name)"; continue }
    Write-Warning "$($m.Name) has the wrong hash; re-downloading"
  }
  Invoke-WebRequest -Uri $m.Url -OutFile $path -UseBasicParsing
  $hash = (Get-FileHash $path -Algorithm SHA256).Hash.ToLower()
  if ($hash -ne $m.Sha256) {
    Remove-Item $path -Force
    throw "SHA-256 mismatch for $($m.Name): got $hash, expected $($m.Sha256). File deleted."
  }
  Write-Output "Downloaded and verified: $($m.Name)"
}
