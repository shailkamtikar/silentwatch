# Hardware baseline audit for SILENTWATCH. Writes docs/hardware-baseline.md.
# Redacts serial numbers, MAC addresses and personal device names.
$ErrorActionPreference = 'SilentlyContinue'
$out = Join-Path $PSScriptRoot '..\docs\hardware-baseline.md'

$os = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$ram = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
$gpus = (Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name }) -join '; '
$cams = Get-PnpDevice -Class Camera, Image | Where-Object { $_.Status -eq 'OK' } | ForEach-Object { $_.FriendlyName }
$bt = Get-PnpDevice -Class Bluetooth | Where-Object { $_.FriendlyName -match 'Adapter|Radio' } | ForEach-Object { $_.FriendlyName }
$sensors = Get-PnpDevice -Class Sensor | ForEach-Object { $_.FriendlyName }
$bio = Get-PnpDevice -Class Biometric | ForEach-Object { $_.FriendlyName }
$bat = Get-CimInstance Win32_Battery | Select-Object -First 1
$priv = (Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\webcam').Value
$presence = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\SensorPresence'

function NA($v) { if ($v) { $v } else { 'not available' } }

$lines = @(
  '# Hardware baseline',
  '',
  "Generated: $((Get-Date).ToString('yyyy-MM-dd HH:mm')) by scripts/audit_hardware.ps1 (identifiers redacted).",
  '',
  "- OS: $($os.Caption) build $($os.BuildNumber) ($($os.OSArchitecture))",
  "- CPU: $($cpu.Name) ($($cpu.NumberOfCores) cores / $($cpu.NumberOfLogicalProcessors) threads)",
  "- RAM: $ram GB",
  "- GPU: $gpus",
  "- Camera(s): $(NA ($cams -join '; '))",
  "- Bluetooth adapter: $(NA ($bt -join '; '))",
  "- Motion/accelerometer sensors: $(NA ($sensors -join '; '))",
  "- Biometric/presence devices: $(NA ($bio -join '; '))",
  "- Windows presence-sensing registry key present: $presence",
  "- Battery present: $([bool]$bat)",
  "- Camera privacy (apps allowed): $(NA $priv)"
)
$lines | Set-Content -Path $out -Encoding utf8
Write-Output "Wrote $out"
