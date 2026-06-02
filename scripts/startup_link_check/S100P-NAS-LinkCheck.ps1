param(
  [switch]$NoGui,
  [switch]$NoDelay,
  [switch]$StartInTray
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
$LogDir = $Config.logging.localDir
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogPath = Join-Path $LogDir ("{0}.jsonl" -f (Get-Date -Format 'yyyy-MM-dd'))
$Global:Steps = New-Object System.Collections.Generic.List[object]
$Global:FixesApplied = New-Object System.Collections.Generic.List[string]
$Global:Failures = New-Object System.Collections.Generic.List[string]

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
      $props = $netShare.NetConnectionProps($conn)
      $cfg = $netShare.INetSharingConfigurationForINetConnection($conn)
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
      $cfg = $netShare.INetSharingConfigurationForINetConnection($conn)
      if ($cfg.SharingEnabled) {
        $cfg.DisableSharing()
      }
    }

    if ($ForceReset.IsPresent) {
      try {
        Restart-Service -Name SharedAccess -Force -ErrorAction Stop
        Start-Sleep -Seconds 3
        $netShare = New-Object -ComObject HNetCfg.HNetShare
        $connections = @($netShare.EnumEveryConnection())
        $publicConn = $null
        $privateConn = $null
        foreach ($conn in $connections) {
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
      $props = $netShare.NetConnectionProps($conn)
      $cfg = $netShare.INetSharingConfigurationForINetConnection($conn)
      $after.Add(("name={0}; enabled={1}; type={2}" -f $props.Name, $cfg.SharingEnabled, $cfg.SharingConnectionType))
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
  return Invoke-External -FilePath 'ssh.exe' -Arguments $args -StandardInput $Command -TimeoutSeconds $TimeoutSeconds
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

  $probe = @'
set -e
ping -c 1 -W 2 __GATEWAY__
ping -c 1 -W 2 __DNS0__
getent hosts __FEISHU_HOST__
echo S100P_INTERNET_OK
'@
  $probe = $probe.Replace('__GATEWAY__', $Config.s100p.defaultGateway)
  $probe = $probe.Replace('__DNS0__', $Config.s100p.dns[0])
  $probe = $probe.Replace('__FEISHU_HOST__', $Config.openclaw.feishuHost)
  $internet = Invoke-S100P -Command $probe -TimeoutSeconds 25
  $internetText = "$($internet.Output)`n$($internet.Error)"
  if ($internet.ExitCode -eq 0 -and $internetText -match 'S100P_INTERNET_OK') {
    Add-Step 'S100P 外网/DNS' 'OK' 'S100P 可访问飞书依赖的 DNS/外网' $internetText
    return $true
  }
  Add-Step 'S100P 外网/DNS' 'FAIL' 'S100P 外网或飞书域名解析失败' $internetText
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
sudo -n chmod 755 __PARENT__ || true
sudo -n sed -i "s#[0-9][0-9.]*:__EXPORT__#${nas_ip}:__EXPORT__#g" /etc/fstab || true
sudo -n systemctl daemon-reload || true
sudo -n systemctl reset-failed mnt-nas-openclaw.mount || true
sudo -n systemctl restart mnt-nas-openclaw.automount || true
mkdir -p __PROBE__
if ! timeout 10 findmnt -T __PROBE__ | grep -q 'nfs'; then
  sudo -n mkdir -p __MOUNT__
  timeout 20 sudo -n mount -t nfs4 "${nas_ip}:__EXPORT__" __MOUNT__ || true
fi
timeout 10 ls -ld __PROBE__
timeout 10 findmnt -T __PROBE__
timeout 10 findmnt -T __PROBE__ | grep -q 'nfs'
test -d __PROBE__
test -w __PROBE__
f=__PROBE__/pc_startup_linkcheck_$(date +%Y%m%d_%H%M%S).txt
echo linkcheck > "$f"
ls -l "$f"
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

function Ensure-OpenClawFeishu {
  param([bool]$NetworkWasTouched)
  $service = $Config.openclaw.serviceName
  $checkScriptPath = Join-Path $ScriptRoot 'check_openclaw_feishu.sh'
  if (Test-Path -LiteralPath $checkScriptPath) {
    $check = Get-Content -LiteralPath $checkScriptPath -Raw -Encoding UTF8
  } else {
    $check = @'
#!/usr/bin/env bash
set +e
state="$(timeout 5 sudo -n env XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-active openclaw-gateway.service 2>/dev/null || true)"
echo "SERVICE_STATE=$state"
log="/tmp/openclaw/openclaw-$(date +%F).log"
ready="$(timeout 5 sudo -n grep 'ws client ready' "$log" 2>/dev/null | tail -20 || true)"
echo "$ready"
if [ "$state" = "active" ] && [ -n "$ready" ]; then
  echo OPENCLAW_READY
  exit 0
fi
exit 1
'@
  }
  $before = Invoke-S100P -Command $check -TimeoutSeconds 20
  $beforeText = "$($before.Output)`n$($before.Error)"
  $needsRestart = $NetworkWasTouched -or ($beforeText -match 'inactive|failed|EAI_AGAIN')
  if ($needsRestart) {
    $restartHeader = @"
timeout 10 sudo -n env XDG_RUNTIME_DIR=$($Config.openclaw.rootUserRuntimeDir) systemctl --user restart $service || true
sleep 18
"@
    $after = Invoke-S100P -Command ($restartHeader + "`n" + $check) -TimeoutSeconds 45
    $afterText = "$($after.Output)`n$($after.Error)"
    if ($after.ExitCode -eq 0 -and $afterText -match 'OPENCLAW_READY') {
      Add-Step 'OpenClaw/飞书' 'FIXED' '已重启 gateway，飞书 WebSocket ready' $afterText
      return $true
    }
    Add-Step 'OpenClaw/飞书' 'FAIL' '重启 gateway 后仍未确认飞书 ready' $afterText
    return $false
  }
  if ($before.ExitCode -eq 0 -and $beforeText -match 'OPENCLAW_READY') {
    Add-Step 'OpenClaw/飞书' 'OK' 'gateway active，飞书链路近期有 ready 或消息记录' $beforeText
    return $true
  }
  Add-Step 'OpenClaw/飞书' 'WARN' 'gateway active 但近期未看到飞书消息，可在飞书发测试消息复核' $beforeText
  return $true
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

请优先检查：Windows 以太网双 IP、PC 到 192.168.127.10 的 SSH、S100P 默认路由/DNS、NAS NFS 挂载、openclaw-gateway.service 和飞书日志。
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
    [void](Ensure-WindowsIcsSharing -ForceReset)
    $windowsOk = Ensure-WindowsNetwork
  }
  $sshOk = $false
  if ($windowsOk) { $sshOk = Test-PCToS100P }
  $netOk = $false
  $nasOk = $false
  $openclawOk = $false
  if ($sshOk) {
    $netOk = Ensure-S100PNetwork
    $nasOk = Ensure-NasLink
    $networkTouchingFixes = @($Global:FixesApplied | Where-Object { $_ -ne 'NAS IP 自动发现' })
    $openclawOk = Ensure-OpenClawFeishu -NetworkWasTouched:($networkTouchingFixes.Count -gt 0)
  }

  $status = if ($Global:Failures.Count -gt 0) { 'FAIL' } elseif ($Global:FixesApplied.Count -gt 0) { 'FIXED' } else { 'OK' }
  Write-JsonLog -Event 'run_end' -Data @{
    status = $status
    failures = @($Global:Failures)
    fixes = @($Global:FixesApplied)
    windowsOk = $windowsOk
    sshOk = $sshOk
    networkOk = $netOk
    nasOk = $nasOk
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

function Start-GuiRun {
  param([bool]$UseStartupDelay = $false)

  $rerun.Enabled = $false
  $menuRerun.Enabled = $false
  $title.Text = '正在检测并修复链路...'
  $box.Text = '运行中，请稍候...'
  Set-TrayStatus 'INFO'
  [System.Windows.Forms.Application]::DoEvents()
  $status = Run-LinkCheck -UseStartupDelay:$UseStartupDelay
  $box.Text = Render-StepsText
  if ($status -eq 'OK') {
    $title.Text = '链路正常：PC -> S100P -> NAS -> OpenClaw/飞书'
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
    $title.Text = '链路仍有异常，请复制给 Codex 继续处理'
    $title.ForeColor = [System.Drawing.Color]::DarkRed
    Set-TrayStatus 'FAIL'
    Show-MainWindow
  }
  $rerun.Enabled = $true
  $menuRerun.Enabled = $true
}

$rerun.Add_Click({ Show-MainWindow; Start-GuiRun -UseStartupDelay:$false })
$copy.Add_Click({ [System.Windows.Forms.Clipboard]::SetText((Get-CodexPrompt)); [System.Windows.Forms.MessageBox]::Show('已复制诊断提示词。') | Out-Null })
$openLog.Add_Click({ Start-Process explorer.exe $LogDir })
$close.Add_Click({ Hide-MainWindow })
$menuOpen.Add_Click({ Show-MainWindow })
$menuRerun.Add_Click({ Show-MainWindow; Start-GuiRun -UseStartupDelay:$false })
$menuCopy.Add_Click({ [System.Windows.Forms.Clipboard]::SetText((Get-CodexPrompt)); [System.Windows.Forms.MessageBox]::Show('已复制诊断提示词。') | Out-Null })
$menuLog.Add_Click({ Start-Process explorer.exe $LogDir })
$menuExit.Add_Click({
  $Script:AllowExit = $true
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
  Start-GuiRun -UseStartupDelay:(-not $NoDelay)
})

try {
  [void][System.Windows.Forms.Application]::Run($form)
} finally {
  $notifyIcon.Visible = $false
  $notifyIcon.Dispose()
}

