param(
  [switch]$NoGui,
  [switch]$NoDelay,
  [switch]$StartInTray,
  [switch]$SelfTest
)

$ErrorActionPreference = 'Continue'
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigPath = Join-Path $ScriptRoot 'link-check.config.json'

function Get-LinkCheckConfig {
  if (-not (Test-Path -LiteralPath $ConfigPath)) {
    throw "Missing config file: $ConfigPath"
  }
  return Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
}

$Config = Get-LinkCheckConfig
$LogDir = if ($SelfTest) {
  Join-Path ([IO.Path]::GetTempPath()) 's100p-linkcheck-selftest'
} else {
  $Config.logging.localDir
}
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogPath = Join-Path $LogDir ("{0}.jsonl" -f (Get-Date -Format 'yyyy-MM-dd'))
$Global:Steps = New-Object System.Collections.Generic.List[object]
$Global:FixesApplied = New-Object System.Collections.Generic.List[string]
$Global:Failures = New-Object System.Collections.Generic.List[string]

function Assert-LinkCheckConfig {
  $required = @(
    'windows.interfaceAlias',
    's100p.host',
    's100p.user',
    's100p.sshKey',
    's100p.interface',
    's100p.nasInterface',
    'nas.ip',
    'nas.nfsExport',
    'nas.mountPoint',
    'nas.probeDir',
    'openclaw.systemServiceName',
    'openclaw.portalServiceName',
    'openclaw.qwenServiceName',
    'openclaw.systemHealthUrl',
    'openclaw.portalHealthUrl',
    'openclaw.qwenHealthUrl'
  )
  foreach ($path in $required) {
    $value = $Config
    foreach ($part in $path.Split('.')) {
      if ($null -eq $value -or $null -eq $value.PSObject.Properties[$part]) {
        throw "Missing required link-check config value: $path"
      }
      $value = $value.$part
    }
    if ($null -eq $value -or [string]::IsNullOrWhiteSpace([string]$value)) {
      throw "Empty required link-check config value: $path"
    }
  }

  foreach ($ip in @($Config.s100p.host, $Config.nas.ip)) {
    $parsed = $null
    if (-not [Net.IPAddress]::TryParse([string]$ip, [ref]$parsed)) {
      throw "Invalid IP address in link-check config: $ip"
    }
  }
  foreach ($url in @($Config.openclaw.systemHealthUrl, $Config.openclaw.portalHealthUrl, $Config.openclaw.qwenHealthUrl)) {
    $uri = $null
    if (-not [Uri]::TryCreate([string]$url, [UriKind]::Absolute, [ref]$uri) -or $uri.Scheme -ne 'http') {
      throw "Health URL must be an absolute loopback HTTP URL: $url"
    }
    if ($uri.Host -notin @('127.0.0.1', 'localhost', '::1')) {
      throw "Health URL must remain loopback-scoped: $url"
    }
  }
}

Assert-LinkCheckConfig

function Test-IsAdmin {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = [Security.Principal.WindowsPrincipal]::new($identity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Redact-Text {
  param([AllowNull()][string]$Text)
  if ($null -eq $Text) { return '' }
  $patterns = @(
    '(?i)(app_secret["''=: ]+)[^,"''\s}]+',
    '(?i)(secret["''=: ]+)[^,"''\s}]+',
    '(?i)(token["''=: ]+)[^,"''\s}]+',
    '(?i)(authorization["''=: ]+)[^,"''\s}]+',
    '(?i)(password["''=: ]+)[^,"''\s}]+'
  )
  $out = $Text
  foreach ($p in $patterns) {
    $out = [regex]::Replace($out, $p, '$1REDACTED')
  }
  return $out
}

function Write-JsonLog {
  param(
    [string]$Event,
    [hashtable]$Data = @{}
  )
  $record = [ordered]@{
    time = (Get-Date).ToString('o')
    event = $Event
    data = $Data
  }
  ($record | ConvertTo-Json -Depth 8 -Compress) | Add-Content -LiteralPath $LogPath -Encoding UTF8
}

function Add-Step {
  param(
    [string]$Name,
    [ValidateSet('OK','FIXED','WARN','FAIL','INFO')]
    [string]$Status,
    [string]$Message,
    [string]$Details = ''
  )
  $step = [pscustomobject]@{
    Name = $Name
    Status = $Status
    Message = $Message
    Details = (Redact-Text $Details)
  }
  $Global:Steps.Add($step)
  if ($Status -eq 'FIXED') { $Global:FixesApplied.Add($Name) }
  if ($Status -eq 'FAIL') { $Global:Failures.Add("${Name}: $Message") }
  Write-JsonLog -Event 'step' -Data @{
    name = $Name
    status = $Status
    message = $Message
    details = $step.Details
  }
}

function Ensure-WindowsIcsSharing {
  param([switch]$ForceReset)

  $publicName = 'WLAN'
  $privateName = $Config.windows.interfaceAlias

  if (-not (Test-IsAdmin)) {
    Add-Step 'Windows ICS 共享' 'WARN' '当前进程不是管理员，无法自动修复 WLAN -> 以太网 共享上网' ''
    return $false
  }

  try {
    $netShare = New-Object -ComObject HNetCfg.HNetShare
    $connections = @($netShare.EnumEveryConnection())
    $publicConn = $null
    $privateConn = $null
    $states = New-Object System.Collections.Generic.List[string]

    foreach ($conn in $connections) {
      if ($null -eq $conn) { continue }
      try {
        $props = $netShare.NetConnectionProps($conn)
        $cfg = $netShare.INetSharingConfigurationForINetConnection($conn)
      } catch {
        $states.Add(("name=<error>; error={0}" -f $_.Exception.Message))
        continue
      }
      $states.Add(("name={0}; enabled={1}; type={2}" -f $props.Name, $cfg.SharingEnabled, $cfg.SharingConnectionType))
      if ($props.Name -eq $publicName) { $publicConn = $conn }
      if ($props.Name -eq $privateName) { $privateConn = $conn }
    }

    if ($null -eq $publicConn -or $null -eq $privateConn) {
      Add-Step 'Windows ICS 共享' 'FAIL' ("找不到共享网卡：public={0}, private={1}" -f $publicName, $privateName) ($states -join "`n")
      return $false
    }

    $publicCfg = $netShare.INetSharingConfigurationForINetConnection($publicConn)
    $privateCfg = $netShare.INetSharingConfigurationForINetConnection($privateConn)
    $alreadyOk = $publicCfg.SharingEnabled -and $publicCfg.SharingConnectionType -eq 0 -and
      $privateCfg.SharingEnabled -and $privateCfg.SharingConnectionType -eq 1

    if ($alreadyOk -and -not $ForceReset.IsPresent) {
      Add-Step 'Windows ICS 共享' 'OK' ("{0} 已共享到 {1}" -f $publicName, $privateName) ($states -join "`n")
      return $true
    }

    foreach ($conn in $connections) {
      if ($null -eq $conn) { continue }
      try {
        $cfg = $netShare.INetSharingConfigurationForINetConnection($conn)
        if ($cfg.SharingEnabled) {
          $cfg.DisableSharing()
        }
      } catch {
        $states.Add(("disable_error={0}" -f $_.Exception.Message))
      }
    }

    if ($ForceReset.IsPresent) {
      try {
        Restart-Service -Name SharedAccess -Force -ErrorAction Stop
        Start-Sleep -Seconds 3
      } catch {
        $states.Add(("SharedAccess restart skipped: {0}" -f $_.Exception.Message))
      }

      try {
        $netShare = New-Object -ComObject HNetCfg.HNetShare
        $connections = @($netShare.EnumEveryConnection())
        $publicConn = $null
        $privateConn = $null
        foreach ($conn in $connections) {
          if ($null -eq $conn) { continue }
          $props = $netShare.NetConnectionProps($conn)
          if ($props.Name -eq $publicName) { $publicConn = $conn }
          if ($props.Name -eq $privateName) { $privateConn = $conn }
        }
        if ($null -eq $publicConn -or $null -eq $privateConn) {
          throw "Network connection disappeared after SharedAccess restart"
        }
        $publicCfg = $netShare.INetSharingConfigurationForINetConnection($publicConn)
        $privateCfg = $netShare.INetSharingConfigurationForINetConnection($privateConn)
      } catch {
        Add-Step 'Windows ICS 共享' 'FAIL' '重启 SharedAccess 后重新获取共享网卡失败' $_.Exception.ToString()
        return $false
      }
    }

    $publicCfg.EnableSharing(0)
    Start-Sleep -Seconds 1
    $privateCfg.EnableSharing(1)
    Start-Sleep -Seconds 8

    $after = New-Object System.Collections.Generic.List[string]
    foreach ($conn in @($netShare.EnumEveryConnection())) {
      if ($null -eq $conn) { continue }
      try {
        $props = $netShare.NetConnectionProps($conn)
        $cfg = $netShare.INetSharingConfigurationForINetConnection($conn)
        $after.Add(("name={0}; enabled={1}; type={2}" -f $props.Name, $cfg.SharingEnabled, $cfg.SharingConnectionType))
      } catch {
        $after.Add(("name=<error>; error={0}" -f $_.Exception.Message))
      }
    }
    $message = if ($ForceReset.IsPresent) {
      "已重启 SharedAccess 并重新启用 ${publicName} -> ${privateName} 共享上网"
    } else {
      "已启用 ${publicName} -> ${privateName} 共享上网"
    }
    Add-Step 'Windows ICS 共享' 'FIXED' $message ($after -join "`n")
    return $true
  } catch {
    Add-Step 'Windows ICS 共享' 'FAIL' '修复 WLAN -> 以太网 共享上网失败' $_.Exception.ToString()
    return $false
  }
}

function ConvertTo-WindowsCommandLineArgument {
  param([AllowNull()][string]$Argument)
  if ($null -eq $Argument) { return '""' }
  if ($Argument -notmatch '[\s"]') { return $Argument }
  $escaped = $Argument -replace '\\', '\\' -replace '"', '\"'
  return '"' + $escaped + '"'
}

function Invoke-External {
  param(
    [Parameter(Mandatory)][string]$FilePath,
    [string[]]$Arguments = @(),
    [string]$StandardInput = '',
    [int]$TimeoutSeconds = 30
  )
  $psi = [System.Diagnostics.ProcessStartInfo]::new()
  $psi.FileName = $FilePath
  $psi.Arguments = (($Arguments | ForEach-Object { ConvertTo-WindowsCommandLineArgument $_ }) -join ' ')
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.RedirectStandardInput = $true
  $psi.UseShellExecute = $false
  $psi.CreateNoWindow = $true
  $p = [System.Diagnostics.Process]::new()
  $p.StartInfo = $psi
  [void]$p.Start()
  if ($StandardInput) {
    $p.StandardInput.Write($StandardInput)
  }
  $p.StandardInput.Close()
  if (-not $p.WaitForExit($TimeoutSeconds * 1000)) {
    try { $p.Kill($true) } catch {}
    return [pscustomobject]@{ ExitCode = 124; Output = ''; Error = "Timed out after $TimeoutSeconds seconds" }
  }
  return [pscustomobject]@{
    ExitCode = $p.ExitCode
    Output = $p.StandardOutput.ReadToEnd()
    Error = $p.StandardError.ReadToEnd()
  }
}

function Invoke-S100P {
  param(
    [Parameter(Mandatory)][string]$Command,
    [int]$TimeoutSeconds = 30
  )
  $target = "{0}@{1}" -f $Config.s100p.user, $Config.s100p.host
  $args = @(
    '-i', $Config.s100p.sshKey,
    '-o', 'BatchMode=yes',
    '-o', ('ConnectTimeout={0}' -f $Config.s100p.sshConnectTimeoutSeconds),
    '-o', 'StrictHostKeyChecking=accept-new',
    $target,
    'bash',
    '-s'
  )
  $normalizedCommand = $Command.Replace("`r`n", "`n").Replace("`r", "`n")
  return Invoke-External -FilePath 'ssh.exe' -Arguments $args -StandardInput $normalizedCommand -TimeoutSeconds $TimeoutSeconds
}

function Ensure-WindowsNetwork {
  $alias = $Config.windows.interfaceAlias
  $adapter = Get-NetAdapter -Name $alias -ErrorAction SilentlyContinue
  if (-not $adapter) {
    Add-Step 'Windows 网卡' 'FAIL' "找不到网卡 $alias" '检查配置中的 interfaceAlias。'
    return $false
  }
  if ($adapter.Status -ne 'Up') {
    Add-Step 'Windows 网卡' 'FAIL' "$alias 未连接" ($adapter | Out-String)
    return $false
  }
  Add-Step 'Windows 网卡' 'OK' "$alias 已连接，链路速率 $($adapter.LinkSpeed)"

  $isAdmin = Test-IsAdmin
  $ok = $true
  foreach ($ipCfg in $Config.windows.requiredIPv4) {
    $existing = Get-NetIPAddress -InterfaceAlias $alias -AddressFamily IPv4 -ErrorAction SilentlyContinue |
      Where-Object { $_.IPAddress -eq $ipCfg.ip -and $_.PrefixLength -eq [int]$ipCfg.prefixLength }
    if ($existing) {
      Add-Step "Windows IP $($ipCfg.ip)" 'OK' "$alias 已有 $($ipCfg.ip)/$($ipCfg.prefixLength)"
      continue
    }
    if (-not $isAdmin) {
      Add-Step "Windows IP $($ipCfg.ip)" 'FAIL' '缺少管理员权限，无法自动补网卡 IP'
      $ok = $false
      continue
    }
    try {
      New-NetIPAddress -InterfaceAlias $alias -IPAddress $ipCfg.ip -PrefixLength ([int]$ipCfg.prefixLength) -ErrorAction Stop | Out-Null
      Add-Step "Windows IP $($ipCfg.ip)" 'FIXED' "已补齐 $($ipCfg.ip)/$($ipCfg.prefixLength)"
    } catch {
      Add-Step "Windows IP $($ipCfg.ip)" 'FAIL' '自动补 IP 失败' $_.Exception.Message
      $ok = $false
    }
  }
  return $ok
}

function Test-PCToS100P {
  $hostIp = $Config.s100p.host
  $ping = Test-Connection -ComputerName $hostIp -Count 2 -Quiet -ErrorAction SilentlyContinue
  if ($ping) {
    Add-Step 'PC -> S100P ping' 'OK' "$hostIp 可达"
  } else {
    Add-Step 'PC -> S100P ping' 'FAIL' "$hostIp 不可达" '检查 S100P 电源、右侧 eth1 网线、Windows 以太网双 IP。'
    return $false
  }

  $tcp = Test-NetConnection $hostIp -Port 22 -InformationLevel Quiet -WarningAction SilentlyContinue
  if ($tcp) {
    Add-Step 'PC -> S100P SSH 端口' 'OK' "${hostIp}:22 可达"
  } else {
    Add-Step 'PC -> S100P SSH 端口' 'FAIL' "${hostIp}:22 不可达" 'S100P 可能未启动 sshd 或网络只通 ICMP。'
    return $false
  }

  $ssh = Invoke-S100P -Command 'echo S100P_SSH_OK; hostname; whoami' -TimeoutSeconds 12
  $combined = "$($ssh.Output)`n$($ssh.Error)"
  if ($ssh.ExitCode -eq 0 -and $combined -match 'S100P_SSH_OK') {
    Add-Step 'S100P SSH key' 'OK' '免密 SSH 登录成功' $combined
    return $true
  }
  Add-Step 'S100P SSH key' 'FAIL' '免密 SSH 登录失败' $combined
  return $false
}

function Ensure-S100PClock {
  $hostEpoch = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
  $maxSkew = if ($Config.s100p.clockMaxSkewSeconds) { [int]$Config.s100p.clockMaxSkewSeconds } else { 120 }
  $cmd = @'
set -e
host_epoch=__HOST_EPOCH__
max_skew=__MAX_SKEW__
board_epoch="$(date +%s)"
skew=$((board_epoch-host_epoch))
[ "$skew" -lt 0 ] && skew=$((-skew))
echo "CLOCK_BEFORE_EPOCH=$board_epoch"
echo "CLOCK_SKEW_SECONDS=$skew"
if [ "$skew" -gt "$max_skew" ]; then
  sudo -n timedatectl set-ntp false || true
  sudo -n date -u -s "@$host_epoch"
  sudo -n hwclock --systohc >/dev/null 2>&1 || true
  sudo -n timedatectl set-ntp true || true
  echo CLOCK_FIXED
else
  sudo -n timedatectl set-ntp true || true
  echo CLOCK_OK
fi
date -Is
'@
  $cmd = $cmd.Replace('__HOST_EPOCH__', [string]$hostEpoch).Replace('__MAX_SKEW__', [string]$maxSkew)
  $result = Invoke-S100P -Command $cmd -TimeoutSeconds 20
  $combined = "$($result.Output)`n$($result.Error)"
  if ($result.ExitCode -eq 0 -and $combined -match 'CLOCK_FIXED') {
    Add-Step 'S100P 时钟' 'FIXED' '板端时间漂移超限，已按 Windows 主机 UTC 校准并重新启用 NTP' $combined
    return $true
  }
  if ($result.ExitCode -eq 0 -and $combined -match 'CLOCK_OK') {
    Add-Step 'S100P 时钟' 'OK' "板端与 Windows 时间偏差不超过 ${maxSkew}s" $combined
    return $true
  }
  Add-Step 'S100P 时钟' 'FAIL' '无法验证或校准板端时钟；TLS、日志和鉴权可能异常' $combined
  return $false
}

function Get-NetplanYaml {
  $dnsLines = ($Config.s100p.dns | ForEach-Object { "          - $_" }) -join "`n"
  $addresses = ($Config.s100p.requiredIPv4 | ForEach-Object { "        - `"$_`"" }) -join "`n"
  $nasIface = if ($Config.s100p.nasInterface) { $Config.s100p.nasInterface } else { 'eth0' }
  $nasAddress = if ($Config.s100p.nasInterfaceIPv4) { $Config.s100p.nasInterfaceIPv4 } else { '169.254.8.10/16' }
  $yaml = @'
network:
  version: 2
  renderer: NetworkManager
  ethernets:
    __NAS_IFACE__:
      addresses:
        - "__NAS_ADDRESS__"
      dhcp4: false
      dhcp6: false
      link-local: []
      macaddress: "__MAC_ETH0__"
    __IFACE__:
      addresses:
__ADDRESSES__
      routes:
        - to: default
          via: __GATEWAY__
          metric: __METRIC__
      nameservers:
        addresses:
__DNS_LINES__
      macaddress: "__MAC_ETH1__"
'@
  $yaml = $yaml.Replace('__NAS_IFACE__', $nasIface)
  $yaml = $yaml.Replace('__NAS_ADDRESS__', $nasAddress)
  $yaml = $yaml.Replace('__MAC_ETH0__', $Config.s100p.netplanMacEth0)
  $yaml = $yaml.Replace('__IFACE__', $Config.s100p.interface)
  $yaml = $yaml.Replace('__ADDRESSES__', $addresses)
  $yaml = $yaml.Replace('__GATEWAY__', $Config.s100p.defaultGateway)
  $yaml = $yaml.Replace('__METRIC__', [string]$Config.s100p.defaultRouteMetric)
  $yaml = $yaml.Replace('__DNS_LINES__', $dnsLines)
  $yaml = $yaml.Replace('__MAC_ETH1__', $Config.s100p.netplanMacEth1)
  return $yaml
}

function Ensure-S100PNetwork {
  $iface = $Config.s100p.interface
  $nasIface = if ($Config.s100p.nasInterface) { $Config.s100p.nasInterface } else { 'eth0' }
  $nasAddress = if ($Config.s100p.nasInterfaceIPv4) { $Config.s100p.nasInterfaceIPv4 } else { '169.254.8.10/16' }
  $nasIp = $Config.nas.ip
  $dns = ($Config.s100p.dns -join ' ')
  $addrCommands = @()
  foreach ($cidr in $Config.s100p.requiredIPv4) {
    $line = 'ip -4 addr show dev __IFACE__ | grep -q ''__CIDR__'' || sudo -n ip addr add __CIDR__ dev __IFACE__'
    $line = $line.Replace('__IFACE__', $iface).Replace('__CIDR__', $cidr)
    $addrCommands += $line
  }
  $cmd = @'
set -e
__ADDR_COMMANDS__
sudo -n ip link set __NAS_IFACE__ up
ip -4 addr show dev __NAS_IFACE__ | grep -q '__NAS_ADDRESS__' || sudo -n ip addr add __NAS_ADDRESS__ dev __NAS_IFACE__
sudo -n ip route replace 169.254.0.0/16 dev __NAS_IFACE__ src __NAS_SRC__ metric 101
ip route get __NAS_IP__
sudo -n ip route replace default via __GATEWAY__ dev __IFACE__ metric __METRIC__
sudo -n resolvectl dns __IFACE__ __DNS__ || true
sudo -n resolvectl domain __IFACE__ '~.' || true
echo S100P_NETWORK_RUNTIME_OK
ip -4 addr show dev __IFACE__
ip route
'@
  $cmd = $cmd.Replace('__ADDR_COMMANDS__', ($addrCommands -join "`n"))
  $cmd = $cmd.Replace('__NAS_IFACE__', $nasIface)
  $cmd = $cmd.Replace('__NAS_ADDRESS__', $nasAddress)
  $cmd = $cmd.Replace('__NAS_SRC__', ($nasAddress -replace '/.*$', ''))
  $cmd = $cmd.Replace('__NAS_IP__', $nasIp)
  $cmd = $cmd.Replace('__GATEWAY__', $Config.s100p.defaultGateway)
  $cmd = $cmd.Replace('__IFACE__', $iface)
  $cmd = $cmd.Replace('__METRIC__', [string]$Config.s100p.defaultRouteMetric)
  $cmd = $cmd.Replace('__DNS__', $dns)
  $result = Invoke-S100P -Command $cmd -TimeoutSeconds 20
  $combined = "$($result.Output)`n$($result.Error)"
  if ($result.ExitCode -eq 0 -and $combined -match 'S100P_NETWORK_RUNTIME_OK') {
    Add-Step 'S100P 运行时网络' 'OK' 'S100P 双网段、默认路由和 DNS 已就绪' $combined
  } else {
    Add-Step 'S100P 运行时网络' 'FAIL' '无法修复 S100P 运行时网络' $combined
    return $false
  }

  $yaml = Get-NetplanYaml
  $b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($yaml))
  $netplan = @'
set -e
echo '__B64__' | base64 -d | sudo -n tee __NETPLAN_PATH__ >/dev/null
sudo -n chmod 600 __NETPLAN_PATH__
sudo -n netplan generate
echo NETPLAN_OK
'@
  $netplan = $netplan.Replace('__B64__', $b64)
  $netplan = $netplan.Replace('__NETPLAN_PATH__', $Config.s100p.netplanPath)
  $np = Invoke-S100P -Command $netplan -TimeoutSeconds 20
  $npText = "$($np.Output)`n$($np.Error)"
  if ($np.ExitCode -eq 0 -and $npText -match 'NETPLAN_OK') {
    Add-Step 'S100P netplan 持久化' 'OK' 'netplan 已包含双网段、默认路由和 DNS' $npText
  } else {
    Add-Step 'S100P netplan 持久化' 'FAIL' '写入或校验 netplan 失败' $npText
    return $false
  }

  return $true
}

function Test-S100PInternet {
  param([bool]$FinalAttempt = $true)
  $probe = @'
set -e
ping -c 1 -W 2 __GATEWAY__
timeout 6 getent ahostsv4 __CONNECTIVITY_HOST__
timeout 10 curl -sSI --max-time 8 https://__CONNECTIVITY_HOST__ | grep -q '^HTTP/'
echo S100P_INTERNET_OK
'@
  $probe = $probe.Replace('__GATEWAY__', $Config.s100p.defaultGateway)
  $probe = $probe.Replace('__CONNECTIVITY_HOST__', $Config.openclaw.connectivityHost)
  $internet = Invoke-S100P -Command $probe -TimeoutSeconds 25
  $internetText = "$($internet.Output)`n$($internet.Error)"
  if ($internet.ExitCode -eq 0 -and $internetText -match 'S100P_INTERNET_OK') {
    Add-Step 'S100P 外网/DNS' 'OK' 'S100P 默认网关、DNS 和 HTTPS 外网均可用' $internetText
    return $true
  }
  if (-not $FinalAttempt) {
    Add-Step 'S100P 外网/DNS 初检' 'WARN' '外网初检失败，将尝试重建 Windows ICS 后复测' $internetText
    return $false
  }
  Add-Step 'S100P 外网/DNS' 'FAIL' '重建共享网络后，S100P 默认网关、DNS 或 HTTPS 外网仍失败' $internetText
  return $false
}

function Ensure-NasLink {
  $cmd = @'
set +e
echo NAS_DIAG_START
nas_ip=__NAS_IP__
ip -br link show __NAS_IFACE__ || true
ip -4 addr show dev __NAS_IFACE__ || true
ip route get "$nas_ip" || true
sudo -n ip neigh flush dev __NAS_IFACE__ >/dev/null 2>&1 || true
ping -c 1 -W 2 -I __NAS_IFACE__ "$nas_ip"
ping_status=$?
if [ "$ping_status" -ne 0 ]; then
  echo NAS_PING_FAILED_BEFORE_RESET
  ip neigh show dev __NAS_IFACE__ || true
  sudo -n ip link set __NAS_IFACE__ down || true
  sleep 2
  sudo -n ip link set __NAS_IFACE__ up || true
  sleep 4
  sudo -n ip addr replace __NAS_ADDRESS__ dev __NAS_IFACE__ || true
  sudo -n ip route replace 169.254.0.0/16 dev __NAS_IFACE__ src __NAS_SRC__ metric 101 || true
  ip route get "$nas_ip" || true
  ping -c 2 -W 1 -I __NAS_IFACE__ "$nas_ip"
  ping_status=$?
fi
if [ "$ping_status" -ne 0 ]; then
  echo NAS_CONFIGURED_IP_UNREACHABLE
  ip neigh show dev __NAS_IFACE__ || true
  echo "Configured NAS IP did not respond: $nas_ip"
  echo NAS_DISCOVERY_START
  discovered="$(
    sudo -n python3 - <<'PY'
import socket, struct, fcntl, time, select
iface='__NAS_IFACE__'
source_ip='__NAS_SRC__'
export='__EXPORT__'
ranges=[]
for base in ['169.254.110.', '169.254.8.', '169.254.100.', '169.254.1.']:
    ranges.extend(base+str(i) for i in range(1,255))
seen=set(ranges)
for b in range(0,256):
    for c in range(1,255):
        ip=f'169.254.{b}.{c}'
        if ip not in seen:
            ranges.append(ip)
            seen.add(ip)
ranges=[ip for ip in ranges if ip != source_ip]
def if_mac(name):
    s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    info=fcntl.ioctl(s.fileno(), 0x8927, struct.pack('256s', name[:15].encode()))
    return info[18:24]
def ip_bytes(ip):
    return socket.inet_aton(ip)
mac=if_mac(iface)
src_ip=ip_bytes(source_ip)
sock=socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0806))
sock.bind((iface,0))
sock.setblocking(False)
found={}
bcast=b'\xff'*6
eth_type=b'\x08\x06'
arp_hdr=struct.pack('!HHBBH',1,0x0800,6,4,1)
for idx, target in enumerate(ranges, 1):
    packet=bcast+mac+eth_type+arp_hdr+mac+src_ip+(b'\x00'*6)+ip_bytes(target)
    try:
        sock.send(packet)
    except OSError:
        pass
    if idx % 512 == 0:
        end=time.time()+0.03
        while time.time()<end:
            r,_,_=select.select([sock],[],[],0.005)
            if not r:
                continue
            data=sock.recv(65535)
            if len(data) >= 42 and data[12:14] == b'\x08\x06' and data[20:22] == b'\x00\x02':
                found[socket.inet_ntoa(data[28:32])]=':'.join(f'{x:02x}' for x in data[22:28])
end=time.time()+4
while time.time()<end:
    r,_,_=select.select([sock],[],[],0.1)
    if not r:
        continue
    data=sock.recv(65535)
    if len(data) >= 42 and data[12:14] == b'\x08\x06' and data[20:22] == b'\x00\x02':
        found[socket.inet_ntoa(data[28:32])]=':'.join(f'{x:02x}' for x in data[22:28])
for ip, macaddr in sorted(found.items(), key=lambda kv: tuple(map(int, kv[0].split('.')))):
    print(f'{ip} {macaddr}')
PY
  )"
  if [ -n "$discovered" ]; then
    echo "$discovered" | sed 's/^/NAS_DISCOVERY_CANDIDATE /'
    while read -r candidate _mac; do
      [ -z "$candidate" ] && continue
      if timeout 6 showmount -e "$candidate" 2>/dev/null | grep -q "__EXPORT__"; then
        nas_ip="$candidate"
        echo "NAS_DISCOVERED_IP=$nas_ip"
        ping -c 1 -W 1 -I __NAS_IFACE__ "$nas_ip" || true
        ping_status=0
        break
      fi
    done <<EOF
$discovered
EOF
  fi
fi
if [ "$ping_status" -ne 0 ]; then
  echo NAS_L2_UNREACHABLE
  ip neigh show dev __NAS_IFACE__ || true
  echo "Check NAS power, NAS boot state, NAS Ethernet port/cable, or whether NAS IP changed from $nas_ip."
  exit 42
fi
set -e
timeout 8 showmount -e "$nas_ip" | grep -q "^__EXPORT__[[:space:]]"
sudo -n chmod 755 __PARENT__ || true
sudo -n sed -i "s#[0-9][0-9.]*:__EXPORT__#${nas_ip}:__EXPORT__#g" /etc/fstab || true
sudo -n systemctl daemon-reload || true
if ! timeout 10 findmnt -rn -T __MOUNT__ -o SOURCE,FSTYPE | grep -q "^${nas_ip}:__EXPORT__ nfs"; then
  sudo -n mkdir -p __MOUNT__
  sudo -n systemctl reset-failed mnt-nas-openclaw.mount mnt-nas-openclaw.automount || true
  sudo -n systemctl restart mnt-nas-openclaw.automount || true
  timeout 10 ls -ld __MOUNT__ >/dev/null 2>&1 || true
fi
if ! timeout 10 findmnt -rn -T __MOUNT__ -o SOURCE,FSTYPE | grep -q "^${nas_ip}:__EXPORT__ nfs"; then
  sudo -n systemctl reset-failed mnt-nas-openclaw.mount mnt-nas-openclaw.automount || true
  timeout 20 sudo -n systemctl start mnt-nas-openclaw.mount || true
fi
mkdir -p __PROBE__
timeout 10 ls -ld __PROBE__
timeout 10 findmnt -T __PROBE__
timeout 10 findmnt -rn -T __PROBE__ -o SOURCE,FSTYPE | grep -q "^${nas_ip}:__EXPORT__ nfs"
test -d __PROBE__
test -w __PROBE__
f=__PROBE__/pc_startup_linkcheck_$(date +%Y%m%d_%H%M%S)_$$.txt
trap 'rm -f "$f"' EXIT
echo linkcheck > "$f"
grep -qx linkcheck "$f"
rm -f "$f"
trap - EXIT
echo NAS_LINK_OK
'@
  $nasIface = if ($Config.s100p.nasInterface) { $Config.s100p.nasInterface } else { 'eth0' }
  $nasAddress = if ($Config.s100p.nasInterfaceIPv4) { $Config.s100p.nasInterfaceIPv4 } else { '169.254.8.10/16' }
  $cmd = $cmd.Replace('__NAS_IFACE__', $nasIface).
    Replace('__NAS_ADDRESS__', $nasAddress).
    Replace('__NAS_SRC__', ($nasAddress -replace '/.*$', '')).
    Replace('__NAS_IP__', $Config.nas.ip).
    Replace('__PARENT__', $Config.nas.parentDir).
    Replace('__MOUNT__', $Config.nas.mountPoint).
    Replace('__EXPORT__', $Config.nas.nfsExport).
    Replace('__PROBE__', $Config.nas.probeDir)
  $result = Invoke-S100P -Command $cmd -TimeoutSeconds 90
  $combined = "$($result.Output)`n$($result.Error)"
  $discovered = [regex]::Match($combined, 'NAS_DISCOVERED_IP=([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)')
  if ($discovered.Success -and $discovered.Groups[1].Value -ne $Config.nas.ip) {
    $oldNasIp = [string]$Config.nas.ip
    $Config.nas.ip = $discovered.Groups[1].Value
    $Config | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ConfigPath -Encoding UTF8
    Add-Step 'NAS IP 自动发现' 'FIXED' ("NAS IP 已从 {0} 更新为 {1}" -f $oldNasIp, $Config.nas.ip) $combined
  }
  if ($result.ExitCode -eq 0 -and $combined -match 'NAS_LINK_OK') {
    Add-Step 'S100P -> NAS/NFS' 'OK' 'NAS 可达、NFS 已挂载且可写' $combined
    return $true
  }
  if ($combined -match 'NAS_L2_UNREACHABLE') {
    Add-Step 'S100P -> NAS/NFS' 'FAIL' ("NAS 在 eth0 上无 ARP/ICMP 响应；请检查 NAS 电源、启动状态、NAS 网口/网线，或 NAS IP 是否不再是 {0}" -f $Config.nas.ip) $combined
    return $false
  }
  Add-Step 'S100P -> NAS/NFS' 'FAIL' 'NAS 可达性、NFS 挂载或可写检查失败' $combined
  return $false
}

function Test-S100PStorage {
  $cmd = @'
set -e
root_used="$(df -P / | awk 'NR==2 {gsub(/%/,"",$5); print $5}')"
root_available_kb="$(df -Pk / | awk 'NR==2 {print $4}')"
nas_source="$(findmnt -rn -t nfs4 -T __MOUNT__ -o SOURCE)"
nas_used="$(df -P __MOUNT__ | awk 'NR==2 {gsub(/%/,"",$5); print $5}')"
echo "ROOT_USED_PERCENT=$root_used"
echo "ROOT_AVAILABLE_KB=$root_available_kb"
echo "NAS_USED_PERCENT=$nas_used"
echo "NAS_SOURCE=$nas_source"
'@
  $cmd = $cmd.Replace('__MOUNT__', $Config.nas.mountPoint)
  $result = Invoke-S100P -Command $cmd -TimeoutSeconds 15
  $combined = "$($result.Output)`n$($result.Error)"
  $match = [regex]::Match($combined, 'ROOT_USED_PERCENT=([0-9]+)')
  if ($result.ExitCode -ne 0 -or -not $match.Success) {
    Add-Step 'S100P/NAS 容量' 'WARN' '无法读取根分区或 NAS 容量；不阻断链路，但需人工复核' $combined
    return $true
  }
  $rootUsed = [int]$match.Groups[1].Value
  $warn = if ($Config.storage.rootWarnPercent) { [int]$Config.storage.rootWarnPercent } else { 90 }
  $fail = if ($Config.storage.rootFailPercent) { [int]$Config.storage.rootFailPercent } else { 98 }
  if ($rootUsed -ge $fail) {
    Add-Step 'S100P/NAS 容量' 'FAIL' "S100P 根分区已使用 ${rootUsed}%，达到 ${fail}% 阻断阈值" $combined
    return $false
  }
  if ($rootUsed -ge $warn) {
    Add-Step 'S100P/NAS 容量' 'WARN' "S100P 根分区已使用 ${rootUsed}%，链路可用但应尽快清理" $combined
    return $true
  }
  Add-Step 'S100P/NAS 容量' 'OK' "S100P 根分区使用率 ${rootUsed}%，NAS 容量可读取" $combined
  return $true
}

function Ensure-OpenClawStack {
  param([bool]$NetworkWasTouched)
  $checkScriptPath = Join-Path $ScriptRoot 'check_openclaw_feishu.sh'
  if (-not (Test-Path -LiteralPath $checkScriptPath)) {
    Add-Step 'OpenClaw/本地 AI' 'FAIL' "缺少服务检查脚本：$checkScriptPath"
    return $false
  }
  $check = Get-Content -LiteralPath $checkScriptPath -Raw -Encoding UTF8
  $envHeader = @"
export LINKCHECK_SYSTEM_SERVICE='$($Config.openclaw.systemServiceName)'
export LINKCHECK_PORTAL_SERVICE='$($Config.openclaw.portalServiceName)'
export LINKCHECK_QWEN_SERVICE='$($Config.openclaw.qwenServiceName)'
export LINKCHECK_USER_RUNTIME_DIR='$($Config.openclaw.userRuntimeDir)'
export LINKCHECK_SYSTEM_HEALTH='$($Config.openclaw.systemHealthUrl)'
export LINKCHECK_PORTAL_HEALTH='$($Config.openclaw.portalHealthUrl)'
export LINKCHECK_QWEN_HEALTH='$($Config.openclaw.qwenHealthUrl)'
export LINKCHECK_HEALTH_ATTEMPTS=1
"@
  $before = Invoke-S100P -Command ($envHeader + "`n" + $check) -TimeoutSeconds 20
  $beforeText = "$($before.Output)`n$($before.Error)"
  $readyBefore = $before.ExitCode -eq 0 -and $beforeText -match 'OPENCLAW_STACK_READY'
  if ($readyBefore -and -not $NetworkWasTouched) {
    Add-Step 'OpenClaw/本地 AI' 'OK' 'OpenClaw 系统网关、AI-NAS 门户和本地 Qwen 均 active 且健康' $beforeText
    return $true
  }

  $restart = if ($readyBefore -and $NetworkWasTouched) {
    "sudo -n systemctl restart $($Config.openclaw.systemServiceName) || true"
  } else {
    @"
sudo -n systemctl reset-failed $($Config.openclaw.systemServiceName) || true
sudo -n systemctl restart $($Config.openclaw.systemServiceName) || true
systemctl --user reset-failed $($Config.openclaw.portalServiceName) $($Config.openclaw.qwenServiceName) || true
systemctl --user restart $($Config.openclaw.qwenServiceName) || true
systemctl --user restart $($Config.openclaw.portalServiceName) || true
"@
  }
  $afterHeader = $envHeader.Replace('LINKCHECK_HEALTH_ATTEMPTS=1', 'LINKCHECK_HEALTH_ATTEMPTS=12')
  $after = Invoke-S100P -Command ($restart + "`n" + $afterHeader + "`n" + $check) -TimeoutSeconds 60
  $afterText = "$($after.Output)`n$($after.Error)"
  if ($after.ExitCode -eq 0 -and $afterText -match 'OPENCLAW_STACK_READY') {
    Add-Step 'OpenClaw/本地 AI' 'FIXED' '已恢复 OpenClaw 系统网关、AI-NAS 门户和本地 Qwen 健康链路' $afterText
    return $true
  }
  Add-Step 'OpenClaw/本地 AI' 'FAIL' '服务重启后仍未同时通过 active 与健康接口检查' ($beforeText + "`n" + $afterText)
  return $false
}

function Get-CodexPrompt {
  $summary = ($Global:Steps | ForEach-Object {
    "[{0}] {1}: {2}" -f $_.Status, $_.Name, $_.Message
  }) -join "`r`n"
  $prompt = @"
我开机后的 S100P + NAS + OpenClaw 链路自检失败，请继续排查并修复。

工作目录：F:\Project\Digua
本地日志：$LogPath
关键配置：$ConfigPath

自检摘要：
$summary

请优先检查：Windows 网卡/ICS、PC 到 S100P 的 SSH、板端时钟、S100P 默认路由/DNS、NAS NFS mount/automount start-limit、系统 OpenClaw、AI-NAS 门户和本地 Qwen 健康接口。
"@
  return $prompt
}

function Run-LinkCheck {
  param([bool]$UseStartupDelay = $false)

  $Global:Steps.Clear()
  $Global:FixesApplied.Clear()
  $Global:Failures.Clear()
  $runStartData = @{
    noGui = $NoGui.IsPresent
    noDelay = $NoDelay.IsPresent
    startInTray = $StartInTray.IsPresent
    useStartupDelay = $UseStartupDelay
  }
  Write-JsonLog -Event 'run_start' -Data $runStartData

  if ($UseStartupDelay -and $Config.windows.startupDelaySeconds -gt 0) {
    Add-Step '启动延迟' 'INFO' ("等待 {0} 秒，给网卡和 ICS 初始化时间" -f $Config.windows.startupDelaySeconds)
    Start-Sleep -Seconds ([int]$Config.windows.startupDelaySeconds)
  }

  $windowsOk = Ensure-WindowsNetwork
  if ($windowsOk) {
    [void](Ensure-WindowsIcsSharing)
    $windowsOk = Ensure-WindowsNetwork
  }
  $sshOk = $false
  if ($windowsOk) { $sshOk = Test-PCToS100P }
  $clockOk = $false
  $netOk = $false
  $nasOk = $false
  $storageOk = $false
  $openclawOk = $false
  if ($sshOk) {
    $clockOk = Ensure-S100PClock
    $runtimeNetOk = Ensure-S100PNetwork
    if ($runtimeNetOk) {
      $netOk = Test-S100PInternet -FinalAttempt:$false
      if (-not $netOk) {
        [void](Ensure-WindowsIcsSharing -ForceReset)
        Start-Sleep -Seconds 2
        $windowsOk = Ensure-WindowsNetwork
        $netOk = Test-S100PInternet -FinalAttempt:$true
      }
    }
    $nasOk = Ensure-NasLink
    if ($nasOk) { $storageOk = Test-S100PStorage }
    $networkTouchingFixes = @($Global:FixesApplied | Where-Object { $_ -ne 'NAS IP 自动发现' })
    $openclawOk = Ensure-OpenClawStack -NetworkWasTouched:($networkTouchingFixes.Count -gt 0)
  }

  $status = if ($Global:Failures.Count -gt 0) { 'FAIL' } elseif ($Global:FixesApplied.Count -gt 0) { 'FIXED' } else { 'OK' }
  Write-JsonLog -Event 'run_end' -Data @{
    status = $status
    failures = @($Global:Failures)
    fixes = @($Global:FixesApplied)
    windowsOk = $windowsOk
    sshOk = $sshOk
    clockOk = $clockOk
    networkOk = $netOk
    nasOk = $nasOk
    storageOk = $storageOk
    openclawOk = $openclawOk
  }
  return $status
}

function Render-StepsText {
  $lines = New-Object System.Collections.Generic.List[string]
  foreach ($s in $Global:Steps) {
    $lines.Add(("[{0}] {1} - {2}" -f $s.Status, $s.Name, $s.Message))
    if ($s.Details) {
      $detail = ($s.Details -split "`r?`n" | Where-Object { $_.Trim() } | Select-Object -First 8) -join "`r`n"
      if ($detail) { $lines.Add("    $($detail -replace "`r?`n", "`r`n    ")") }
    }
  }
  $lines.Add("")
  $lines.Add("日志：$LogPath")
  return ($lines -join "`r`n")
}

if ($SelfTest) {
  $selfTestFailures = New-Object System.Collections.Generic.List[string]
  $tokens = $null
  $parseErrors = $null
  [void][Management.Automation.Language.Parser]::ParseFile($PSCommandPath, [ref]$tokens, [ref]$parseErrors)
  foreach ($error in @($parseErrors)) { $selfTestFailures.Add("PowerShell parse error: $error") }
  if ((Redact-Text 'token=abc secret:xyz password=q') -match 'abc|xyz|password=q') {
    $selfTestFailures.Add('Secret redaction self-test failed')
  }
  if ([int]$Config.windows.failureRetrySeconds -lt 10 -or [int]$Config.windows.maxAutomaticRetries -lt 1) {
    $selfTestFailures.Add('Automatic retry config is unsafe or disabled')
  }
  if ([int]$Config.storage.rootWarnPercent -ge [int]$Config.storage.rootFailPercent) {
    $selfTestFailures.Add('Storage warning threshold must be lower than failure threshold')
  }
  $source = Get-Content -LiteralPath $PSCommandPath -Raw -Encoding UTF8
  foreach ($marker in @(
    'reset-failed mnt-nas-openclaw.mount mnt-nas-openclaw.automount',
    'NAS_LINK_OK',
    'CLOCK_FIXED',
    'OPENCLAW_STACK_READY',
    '$Command.Replace("`r`n", "`n").Replace("`r", "`n")',
    'Test-S100PInternet -FinalAttempt:$true'
  )) {
    if (-not $source.Contains($marker)) { $selfTestFailures.Add("Missing resilience marker: $marker") }
  }
  $serviceCheck = Join-Path $ScriptRoot 'check_openclaw_feishu.sh'
  $serviceSource = Get-Content -LiteralPath $serviceCheck -Raw -Encoding UTF8
  foreach ($marker in @('SYSTEM_HEALTH_HTTP', 'PORTAL_HEALTH_HTTP', 'QWEN_HEALTH_HTTP', 'OPENCLAW_STACK_READY')) {
    if (-not $serviceSource.Contains($marker)) { $selfTestFailures.Add("Missing service-check marker: $marker") }
  }
  if ($selfTestFailures.Count -gt 0) {
    $selfTestFailures | ForEach-Object { Write-Error $_ }
    exit 1
  }
  Write-Output 'SELFTEST_OK'
  exit 0
}

if ($NoGui) {
  $status = Run-LinkCheck -UseStartupDelay:(-not $NoDelay)
  Render-StepsText | Write-Output
  exit $(if ($status -eq 'FAIL') { 1 } else { 0 })
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

[System.Windows.Forms.Application]::SetUnhandledExceptionMode([System.Windows.Forms.UnhandledExceptionMode]::CatchException)
[System.Windows.Forms.Application]::add_ThreadException({
  param($sender, $eventArgs)
  $message = if ($eventArgs -and $eventArgs.Exception) { $eventArgs.Exception.ToString() } else { 'Unknown WinForms thread exception' }
  Write-JsonLog -Event 'gui_exception' -Data @{ message = (Redact-Text $message) }
  [System.Windows.Forms.MessageBox]::Show("托盘程序界面发生异常，已记录日志：`r`n$LogPath`r`n`r`n$message", 'S100P 链路托盘程序') | Out-Null
})
[AppDomain]::CurrentDomain.add_UnhandledException({
  param($sender, $eventArgs)
  $message = if ($eventArgs -and $eventArgs.ExceptionObject) { $eventArgs.ExceptionObject.ToString() } else { 'Unknown unhandled exception' }
  Write-JsonLog -Event 'gui_unhandled_exception' -Data @{ message = (Redact-Text $message) }
})

$form = [System.Windows.Forms.Form]::new()
$form.Text = 'S100P + NAS + OpenClaw 链路自检'
$form.Width = 920
$form.Height = 700
$form.StartPosition = 'CenterScreen'
$form.ShowInTaskbar = $false

$title = [System.Windows.Forms.Label]::new()
$title.Left = 12
$title.Top = 12
$title.Width = 880
$title.Height = 32
$title.Font = [System.Drawing.Font]::new('Microsoft YaHei UI', 13, [System.Drawing.FontStyle]::Bold)
$title.Text = '正在准备链路自检...'
$form.Controls.Add($title)

$box = [System.Windows.Forms.RichTextBox]::new()
$box.Left = 12
$box.Top = 52
$box.Width = 880
$box.Height = 545
$box.ReadOnly = $true
$box.Font = [System.Drawing.Font]::new('Consolas', 10)
$box.Text = '等待启动...'
$form.Controls.Add($box)

$rerun = [System.Windows.Forms.Button]::new()
$rerun.Text = '重新检测'
$rerun.Left = 12
$rerun.Top = 610
$rerun.Width = 110
$form.Controls.Add($rerun)

$copy = [System.Windows.Forms.Button]::new()
$copy.Text = '复制给 Codex'
$copy.Left = 132
$copy.Top = 610
$copy.Width = 130
$form.Controls.Add($copy)

$openLog = [System.Windows.Forms.Button]::new()
$openLog.Text = '打开日志目录'
$openLog.Left = 272
$openLog.Top = 610
$openLog.Width = 130
$form.Controls.Add($openLog)

$close = [System.Windows.Forms.Button]::new()
$close.Text = '隐藏到托盘'
$close.Left = 782
$close.Top = 610
$close.Width = 110
$form.Controls.Add($close)

$notifyIcon = [System.Windows.Forms.NotifyIcon]::new()
$notifyIcon.Icon = [System.Drawing.SystemIcons]::Information
$notifyIcon.Text = 'S100P/NAS/OpenClaw 链路：正在检测'
$notifyIcon.Visible = $true

$trayMenu = [System.Windows.Forms.ContextMenuStrip]::new()
$menuOpen = [System.Windows.Forms.ToolStripMenuItem]::new('打开状态窗口')
$menuRerun = [System.Windows.Forms.ToolStripMenuItem]::new('重新检测')
$menuCopy = [System.Windows.Forms.ToolStripMenuItem]::new('复制给 Codex')
$menuLog = [System.Windows.Forms.ToolStripMenuItem]::new('打开日志目录')
$menuExit = [System.Windows.Forms.ToolStripMenuItem]::new('退出托盘程序')
[void]$trayMenu.Items.Add($menuOpen)
[void]$trayMenu.Items.Add($menuRerun)
[void]$trayMenu.Items.Add($menuCopy)
[void]$trayMenu.Items.Add($menuLog)
[void]$trayMenu.Items.Add([System.Windows.Forms.ToolStripSeparator]::new())
[void]$trayMenu.Items.Add($menuExit)
$notifyIcon.ContextMenuStrip = $trayMenu

$Script:AllowExit = $false
$Script:CurrentStatus = 'INFO'
$Script:RetryTimer = $null
$Script:AutomaticRetryCount = 0

function Show-MainWindow {
  $form.Show()
  if ($form.WindowState -eq [System.Windows.Forms.FormWindowState]::Minimized) {
    $form.WindowState = [System.Windows.Forms.FormWindowState]::Normal
  }
  $form.Activate()
}

function Hide-MainWindow {
  $form.Hide()
}

function Set-TrayStatus {
  param([string]$Status)
  $Script:CurrentStatus = $Status
  if ($Status -eq 'OK') {
    $notifyIcon.Icon = [System.Drawing.SystemIcons]::Information
    $notifyIcon.Text = 'S100P/NAS/OpenClaw 链路：正常'
  } elseif ($Status -eq 'FIXED') {
    $notifyIcon.Icon = [System.Drawing.SystemIcons]::Warning
    $notifyIcon.Text = 'S100P/NAS/OpenClaw 链路：已自动修复'
  } elseif ($Status -eq 'FAIL') {
    $notifyIcon.Icon = [System.Drawing.SystemIcons]::Error
    $notifyIcon.Text = 'S100P/NAS/OpenClaw 链路：异常，打开查看'
  } else {
    $notifyIcon.Icon = [System.Drawing.SystemIcons]::Information
    $notifyIcon.Text = 'S100P/NAS/OpenClaw 链路：正在检测'
  }
}

function Stop-RetryTimer {
  if ($null -ne $Script:RetryTimer) {
    $Script:RetryTimer.Stop()
    $Script:RetryTimer.Dispose()
    $Script:RetryTimer = $null
  }
}

function Start-GuiRun {
  param(
    [bool]$UseStartupDelay = $false,
    [bool]$Automatic = $false
  )

  Stop-RetryTimer
  if (-not $Automatic) { $Script:AutomaticRetryCount = 0 }

  $rerun.Enabled = $false
  $menuRerun.Enabled = $false
  $title.Text = '正在检测并修复链路...'
  $box.Text = '运行中，请稍候...'
  Set-TrayStatus 'INFO'
  [System.Windows.Forms.Application]::DoEvents()
  $status = Run-LinkCheck -UseStartupDelay:$UseStartupDelay
  $box.Text = Render-StepsText
  if ($status -eq 'OK') {
    $Script:AutomaticRetryCount = 0
    $title.Text = '链路正常：PC -> S100P -> NAS -> OpenClaw/本地 AI'
    $title.ForeColor = [System.Drawing.Color]::DarkGreen
    Set-TrayStatus 'OK'
    $timer = [System.Windows.Forms.Timer]::new()
    $timer.Interval = [int]$Config.windows.autoCloseSuccessSeconds * 1000
    $timer.Add_Tick({
      param($sender, $eventArgs)
      if ($sender) { $sender.Stop(); $sender.Dispose() }
      Hide-MainWindow
    })
    $timer.Start()
  } elseif ($status -eq 'FIXED') {
    $Script:AutomaticRetryCount = 0
    $title.Text = '链路已自动修复'
    $title.ForeColor = [System.Drawing.Color]::DarkOrange
    Set-TrayStatus 'FIXED'
    $timer = [System.Windows.Forms.Timer]::new()
    $timer.Interval = [int]$Config.windows.autoCloseFixedSeconds * 1000
    $timer.Add_Tick({
      param($sender, $eventArgs)
      if ($sender) { $sender.Stop(); $sender.Dispose() }
      Hide-MainWindow
    })
    $timer.Start()
  } else {
    $retrySeconds = [int]$Config.windows.failureRetrySeconds
    $maxRetries = [int]$Config.windows.maxAutomaticRetries
    if ($Script:AutomaticRetryCount -lt $maxRetries) {
      $nextAttempt = $Script:AutomaticRetryCount + 1
      $title.Text = "链路仍有异常，${retrySeconds}s 后自动重试（${nextAttempt}/${maxRetries}）"
      $Script:RetryTimer = [System.Windows.Forms.Timer]::new()
      $Script:RetryTimer.Interval = $retrySeconds * 1000
      $Script:RetryTimer.Add_Tick({
        param($sender, $eventArgs)
        if ($sender) { $sender.Stop(); $sender.Dispose() }
        $Script:RetryTimer = $null
        $Script:AutomaticRetryCount++
        Start-GuiRun -UseStartupDelay:$false -Automatic:$true
      })
      $Script:RetryTimer.Start()
    } else {
      $title.Text = '链路仍有异常，自动重试已耗尽，请复制给 Codex 继续处理'
    }
    $title.ForeColor = [System.Drawing.Color]::DarkRed
    Set-TrayStatus 'FAIL'
    Show-MainWindow
  }
  $rerun.Enabled = $true
  $menuRerun.Enabled = $true
}

$rerun.Add_Click({ Show-MainWindow; Start-GuiRun -UseStartupDelay:$false -Automatic:$false })
$copy.Add_Click({ [System.Windows.Forms.Clipboard]::SetText((Get-CodexPrompt)); [System.Windows.Forms.MessageBox]::Show('已复制诊断提示词。') | Out-Null })
$openLog.Add_Click({ Start-Process explorer.exe $LogDir })
$close.Add_Click({ Hide-MainWindow })
$menuOpen.Add_Click({ Show-MainWindow })
$menuRerun.Add_Click({ Show-MainWindow; Start-GuiRun -UseStartupDelay:$false -Automatic:$false })
$menuCopy.Add_Click({ [System.Windows.Forms.Clipboard]::SetText((Get-CodexPrompt)); [System.Windows.Forms.MessageBox]::Show('已复制诊断提示词。') | Out-Null })
$menuLog.Add_Click({ Start-Process explorer.exe $LogDir })
$menuExit.Add_Click({
  $Script:AllowExit = $true
  Stop-RetryTimer
  $notifyIcon.Visible = $false
  $form.Close()
})
$notifyIcon.Add_DoubleClick({ Show-MainWindow })
$form.Add_FormClosing({
  param($sender, $eventArgs)
  if (-not $Script:AllowExit) {
    $eventArgs.Cancel = $true
    Hide-MainWindow
  }
})
$form.Add_Resize({
  if ($form.WindowState -eq [System.Windows.Forms.FormWindowState]::Minimized) {
    Hide-MainWindow
  }
})
$form.Add_Shown({
  if ($StartInTray) { Hide-MainWindow }
  Start-GuiRun -UseStartupDelay:(-not $NoDelay) -Automatic:$false
})

try {
  [void][System.Windows.Forms.Application]::Run($form)
} finally {
  $notifyIcon.Visible = $false
  $notifyIcon.Dispose()
}

