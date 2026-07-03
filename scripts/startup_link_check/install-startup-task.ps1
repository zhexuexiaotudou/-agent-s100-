param(
  [string]$TaskName = 'S100P-NAS-OpenClaw-LinkCheck'
)

$ErrorActionPreference = 'Stop'
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$MainScript = Join-Path $ScriptRoot 'S100P-NAS-LinkCheck.ps1'

if (-not (Test-Path -LiteralPath $MainScript)) {
  throw "Main script not found: $MainScript"
}

$principalIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$currentUser = $principalIdentity.Name

$action = New-ScheduledTaskAction `
  -Execute 'powershell.exe' `
  -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -STA -File "{0}" -StartInTray' -f $MainScript)

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser

$principal = New-ScheduledTaskPrincipal `
  -UserId $currentUser `
  -LogonType Interactive `
  -RunLevel Highest

$settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -StartWhenAvailable `
  -MultipleInstances IgnoreNew `
  -ExecutionTimeLimit (New-TimeSpan -Seconds 0)

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $action `
  -Trigger $trigger `
  -Principal $principal `
  -Settings $settings `
  -Description 'Check and repair PC -> S100P -> NAS -> OpenClaw Feishu link after Windows logon.' `
  -Force | Out-Null

Write-Host "Installed scheduled task: $TaskName"
Get-ScheduledTask -TaskName $TaskName | Format-List TaskName,TaskPath,State




