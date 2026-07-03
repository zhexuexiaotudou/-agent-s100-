param(
  [Parameter(Mandatory)]
  [ValidateSet('install', 'status', 'uninstall', 'start')]
  [string]$Action,

  [string]$TaskName = 'Digua-Baseline-Audit-Watchdog'
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$WatchdogScript = Join-Path $ScriptDir 'baseline-audit-watchdog.ps1'

if (-not (Test-Path -LiteralPath $WatchdogScript)) {
  throw "Watchdog script not found: $WatchdogScript"
}

function Convert-DateValue {
  param(
    [object]$Value
  )
  if ($null -eq $Value) {
    return $null
  }
  if ($Value -is [datetime] -and $Value -eq [datetime]::MinValue) {
    return $null
  }
  return $Value.ToString('o')
}

function Get-TaskSnapshot {
  $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
  if (-not $task) {
    return [pscustomobject]@{
      installed = $false
      taskName = $TaskName
      state = $null
      taskPath = $null
      lastRunTime = $null
      lastTaskResult = $null
      nextRunTime = $null
    }
  }

  $info = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue
  return [pscustomobject]@{
    installed = $true
    taskName = $task.TaskName
    state = $task.State
    taskPath = $task.TaskPath
    lastRunTime = if ($info) { Convert-DateValue $info.LastRunTime } else { $null }
    lastTaskResult = if ($info) { $info.LastTaskResult } else { $null }
    nextRunTime = if ($info) { Convert-DateValue $info.NextRunTime } else { $null }
    actions = @($task.Actions | ForEach-Object {
      [pscustomobject]@{
        execute = $_.Execute
        arguments = $_.Arguments
        workingDirectory = $_.WorkingDirectory
      }
    })
    triggers = @($task.Triggers | ForEach-Object {
      [pscustomobject]@{
        enabled = $_.Enabled
        triggerType = $_.CimClass.CimClassName
        startBoundary = $_.StartBoundary
      }
    })
  }
}

function Install-Task {
  $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
  $taskAction = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -Action ensure' -f $WatchdogScript)

  $trigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser

  $principal = New-ScheduledTaskPrincipal `
    -UserId $currentUser `
    -LogonType Interactive `
    -RunLevel Limited

  $settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

  Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $taskAction `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description 'Ensure the Digua baseline audit watchdog is running after Windows logon.' `
    -Force | Out-Null

  Get-TaskSnapshot
}

function Uninstall-Task {
  $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
  if ($task) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    return [pscustomobject]@{
      status = 'uninstalled'
      taskName = $TaskName
    }
  }
  return [pscustomobject]@{
    status = 'not_installed'
    taskName = $TaskName
  }
}

$result = $null
switch ($Action) {
  'install' {
    $result = Install-Task
  }
  'status' {
    $result = Get-TaskSnapshot
  }
  'uninstall' {
    $result = Uninstall-Task
  }
  'start' {
    Start-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 2
    $result = Get-TaskSnapshot
  }
}

$result | ConvertTo-Json -Depth 6
