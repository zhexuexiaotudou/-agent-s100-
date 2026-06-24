# OpenClaw 官方 NAS 管理器入口发现与闭环

## 当前机器结论

- NAS 厂商管理器链路：QNAP TS-264C / QTS 类 Web 管理器。
- S100P 地址：`192.168.127.10`。
- NAS 在 S100P 侧的地址：`169.254.143.37`。
- NAS 工作区挂载：`169.254.143.37:/OpenClawWorkspace -> /mnt/nas/openclaw`。
- S100P 侧可访问的官方管理端口：
  - `http://169.254.143.37:8080/`
  - `https://169.254.143.37:5001/`
- Windows 当前不能直接访问 `169.254.143.37`，所以 OpenClaw 门户使用本机 SSH 转发：
  - 门户按钮 URL：`http://127.0.0.1:18090/`
  - 转发链路：Windows `127.0.0.1:18090` -> S100P `192.168.127.10` -> NAS `169.254.143.37:8080`

本地配置写在：

```text
configs/openclaw_nas_portal.local.json
```

该文件只保存 URL 和路由信息，不保存 QTS/QNAP 管理员密码。该文件是
机器本地配置，public repo 只提交 `configs/openclaw_nas_portal.example.json`
作为模板。

## 当前验证命令

发现并写入本地配置：

```powershell
$py = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py scripts/probes/openclaw_official_nas_manager_discovery.py `
  --write-config configs/openclaw_nas_portal.local.json `
  --local-port 18090
```

启动产品栈时，脚本会读取上面的本地配置；如果需要 SSH 转发且 `18090` 没有监听，会自动拉起：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File scripts/probes/start_ai_nas_s100_clip_product_stack.ps1 `
  -RestartPortal
```

门户地址：

```text
http://127.0.0.1:53306/
```

点击顶部“官方 NAS 管理器”按钮后，应打开：

```text
http://127.0.0.1:18090/cgi-bin/
```

## 新用户初始化流程

这个流程应并入 S100P 快速部署 / 链路检查，而不是做成孤立的 NAS 设置页。

1. 确认 S100P 基础链路
   - Windows 能 SSH 到 S100P。
   - S100P 有固定或可发现地址。
   - `scripts/startup_link_check/S100P-NAS-LinkCheck.ps1` 先通过。

2. 确认 NAS 数据链路
   - 从 S100P 查询 `findmnt -T /mnt/nas/openclaw`，或读取链路配置里的 NAS host/export。
   - 验证专用共享 `/OpenClawWorkspace` 可读写。
   - 这一步对应“先成为可用 NAS”的底座，不依赖 AI。

3. 发现官方管理器 URL
   - 优先读取已保存配置：`configs/openclaw_nas_portal.local.json`。
   - 没有配置时按端口探测：
     - QNAP/QTS：`8080`, `5001`, `443`
     - Synology DSM：`5000`, `5001`
     - UGREEN/其他：`80`, `443`, 厂商默认端口
   - 只检查 TCP/HTTP 和页面特征，不尝试登录，不保存管理员密码。

4. 判断浏览器是否能直连
   - 如果 Windows/浏览器能直接访问 NAS 管理端口，按钮使用真实 URL，例如 `http://<NAS_IP>:8080/`。
   - 如果只有 S100P 能访问 NAS，建立本机 SSH 转发，按钮使用 `http://127.0.0.1:<local_port>/`。
   - 本项目当前属于第二种。

5. 写入 OpenClaw 门户配置
   - 写入 `official_manager_url` 和 `official_manager_route`。
   - 后端 `/api/portal/config` 返回 `official_manager_configured=true`。
   - 产品栈启动脚本自动确保转发存在，并在旧门户仍使用过期 URL 时重启门户。

6. 验收
   - 门户登录成功。
   - `/api/portal/config` 返回正确 URL。
   - 点击按钮打开厂商管理器登录页。
   - OpenClaw 文件、搜索、上传、权限 gate 仍通过。

## 和 S100P 快速部署的闭环关系

S100P 快速部署最初解决的是“板子能不能接入 Windows、能不能 SSH、能不能访问 NAS”。官方 NAS 管理器入口补上最后一环：

```text
Windows 浏览器
  -> OpenClaw NAS 门户
  -> 官方 NAS 管理器按钮
  -> 直连 NAS 或经 S100P 转发
  -> QNAP/QTS 等厂商管理器
```

这样新用户初始化时不需要自己猜 NAS IP。系统先通过 S100P/NAS 链路检查确认真实存储地址，再通过管理端口探测确认官方 Web 管理入口，最后把结果写进 OpenClaw 门户。OpenClaw 负责统一入口和 AI 操作；厂商页面继续负责 RAID、存储池、快照、官方账号、Container Station 等底层能力。
