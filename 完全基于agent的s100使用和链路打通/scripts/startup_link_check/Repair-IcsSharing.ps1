param(
  [string]$PublicInterface = 'WLAN',
  [string]$PrivateInterface = '以太网',
  [string]$LogPath = 'F:\Project\Digua\logs\link-check\repair-ics.log'
)

$ErrorActionPreference = 'Stop'

function Write-Log {
  param([string]$Message)
  $dir = Split-Path -Parent $LogPath
  if (-not (Test-Path -LiteralPath $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
  }
  $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
  Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
  Write-Host $line
}

function Get-SharingConnection {
  param(
    [object]$NetShare,
    [string]$Name
  )

  foreach ($conn in @($NetShare.EnumEveryConnection())) {
    $props = $NetShare.NetConnectionProps($conn)
    if ($props.Name -eq $Name) {
      return $conn
    }
  }
  throw "Network connection not found: $Name"
}

Write-Log "Repair ICS start: public=$PublicInterface private=$PrivateInterface"

$netShare = New-Object -ComObject HNetCfg.HNetShare

foreach ($conn in @($netShare.EnumEveryConnection())) {
  $props = $netShare.NetConnectionProps($conn)
  $cfg = $netShare.INetSharingConfigurationForINetConnection($conn)
  if ($cfg.SharingEnabled) {
    Write-Log "Disable existing sharing: $($props.Name)"
    $cfg.DisableSharing()
  }
}

$publicConn = Get-SharingConnection -NetShare $netShare -Name $PublicInterface
$privateConn = Get-SharingConnection -NetShare $netShare -Name $PrivateInterface

$publicCfg = $netShare.INetSharingConfigurationForINetConnection($publicConn)
$privateCfg = $netShare.INetSharingConfigurationForINetConnection($privateConn)

Write-Log "Enable public sharing on $PublicInterface"
$publicCfg.EnableSharing(0)

Write-Log "Enable private sharing on $PrivateInterface"
$privateCfg.EnableSharing(1)

Start-Sleep -Seconds 3

foreach ($conn in @($netShare.EnumEveryConnection())) {
  $props = $netShare.NetConnectionProps($conn)
  $cfg = $netShare.INetSharingConfigurationForINetConnection($conn)
  Write-Log ("State: name={0}; enabled={1}; type={2}" -f $props.Name, $cfg.SharingEnabled, $cfg.SharingConnectionType)
}

Write-Log 'Repair ICS done'
