# 新用户 AI-NAS 产品级交付验收（2026-07-17）

## 结论

不迁移既有数据的前提下，S100P 与 NAS 的新用户部署路径已经形成可交付的
0.2.0 发布包，并在真实 S100P、真实 NFS NAS 和 Windows 局域网客户端上完成
共存安装、升级、回滚点生成、只读 NAS 发现、模型健康、两次真实重启和入口验收。

本次实机采用 `access-only` 共存方式保护已有身份、索引、模型和 NAS 数据；完整
破坏性 clean install 只在 CI 隔离根目录中模拟，没有在现有产品机上清空重装。

## 精确版本与环境

| 项目 | 实测值 |
| --- | --- |
| 发布版本 | `0.2.0` |
| 运行代码 commit | `3ea557471d657739b777215ae5bcc6f07bebe10d` |
| 该 commit 的 tar.gz SHA256 | `04d058f1bbc8b33dbf0549a3f0d5aba6208316e04599dd66228320e752f54b1a` |
| 发布清单 | 420 个文件，`forbidden_file_count=0`，四项 self-check 全为 true |
| S100P | `digua`，`aarch64`，Ubuntu 22.04，kernel `6.1.158-rt58-DR-4.0.5-2603031328-g9f678e-g6caa4d` |
| 板端用户/IP | `sunrise` / `192.168.127.10` |
| OpenClaw | `2026.6.10 (aa69b12)`，系统网关端口 18765 |
| 本地模型网关 | `Qwen2.5-1.5B-Instruct-S100P-official`，`official-qwen2.5-persistent-bpu-oellm-multichat`，端口 18080 |
| NAS | 只读发现为 `qnap_or_compatible`；精确型号未由匿名协议暴露，不猜测型号 |
| NAS 共享 | `169.254.143.37:/OpenClawWorkspace`，NFS 4.1，挂载到 `/mnt/nas/openclaw` |

发布清单保存在板端
`/opt/digua-ai-nas/releases/0.2.0-3ea55747/release_manifest.json`。部署后的
`security.py`、`server.py` 和 `digua_ai_nas_v2.js` 与该发布目录逐文件比较一致。

## 新用户还需要提供什么

精确发布目录中的只读发现器在第二次重启后重新执行。它从已有挂载和显式 NAS
地址自动选择：

```json
{
  "automatic_selection_safe": true,
  "host": "169.254.143.37",
  "protocol": "nfs",
  "share": "/OpenClawWorkspace",
  "user_required": ["allowed_share_scope_confirmation"]
}
```

发现过程记录 `credentials_attempted=false`、`mount_performed=false`、
`state_changed=false`、`subnet_scan_performed=false`。在这台机器上，用户只需确认
允许访问的共享范围。其他 NAS 若不能匿名证明地址、协议或共享名，才需要用户补充
这些值；SMB 凭据、NFS 后台客户端授权、云端模型地址/模型名/API Key 也只能由
用户提供，模型不得猜测。

板端发现报告：
`/tmp/digua-nas-discovery-3ea55747-second-reboot.json`。`/tmp` 是临时证据目录，
长期事实以本文件和发布清单为准。

## 实机部署与回滚

- 发布目录：`/opt/digua-ai-nas/releases/0.2.0-3ea55747`
- 当前安装模式：`access-only`
- 精确访问层回滚点：
  `/var/backups/digua-ai-nas/access-only-20260717T153721Z`
- 访问层升级报告确认 `existing_backend_preserved=true`、
  `backend_units_touched=[]`。
- 在 NAS 专用共享内执行了有界写入、读取、删除探针；探针文件已删除，没有修改
  用户既有数据。

## 重启时发现并解决的真实失败路径

第一次重启后，系统级 `qwen25-local-openai-gateway.service` 因 18080 被用户级
同名单元占用而进入自动重启。根因是用户级 `openclaw-gateway.service` 对用户级
Qwen 声明了 `Wants=`；因此 Qwen 用户单元即使是 `disabled`，仍会被依赖拉起。

处理方式是保留推荐的系统级生产单元，把用户级单元原文件备份为：

`/home/sunrise/.config/systemd/user/qwen25-local-openai-gateway.service.pre-system-scope-20260717`

随后把原路径 mask 到 `/dev/null`，重启系统级 Qwen。没有删除原单元文件。若需
回滚，应先停止系统级 Qwen，解除 mask，恢复上述备份并只启动用户级或系统级其中
一份；两份单元不得同时监听 18080。

第二次重启的 boot ID 从 `6c1263da-96f6-4a47-8dac-c5f869805960` 变为
`9d14b209-dcd4-425a-b12f-c7fad796b177`。重启后用户级 Qwen 仍为 `masked`，系统级
Qwen 为 `active`，其 `MainPID=5333` 与 18080 监听 PID 一致。

## 第二次重启后的生产验收

板端四个端点均返回 HTTP 200：

- `http://127.0.0.1:18765/health`
- `http://127.0.0.1:8765/api/health`
- `http://127.0.0.1/healthz`
- `http://127.0.0.1:18080/health`

Windows 局域网客户端四个入口也均返回 HTTP 200：

- `http://192.168.127.10/healthz`
- `http://192.168.127.10/readyz`
- `http://digua.local/healthz`
- `http://digua.local/`

发布包内的 S100P 验证套件在
`/tmp/digua-product-validation-3ea55747-second-reboot-final` 执行，18 项全部
PASS：`uname`、`architecture`、`network`、`address`、`nas_mount`、
`portal_loopback`、`facade_health`、`facade_ready`、`lan_home`、`avahi`、
`service_access`、`service_portal`、`service_qwen`、`sockets`、`doctor`、
`tailscale_version`、`tailscale_status`、`tailscale_serve`。

## 本地/云端模型边界

- 本地模式在 S100P 上实测健康，私有 NAS 查询和白名单工具留在本地。
- 云端 OpenAI-compatible 模式已从实际 0.2.0 发布包执行 clean-install gate：
  本地 Qwen 不是云模式必需项，API Key 写入受保护独立文件，报告与环境摘要无
  Key，`cloud_private_raw_egress=false`。
- 云端 gate 使用隔离模拟根和不可用测试端点，只证明安装、安全和路由契约；没有
  配置真实云服务，因此不得声称真实云端调用已通过。

## 未冒充已完成的边界

- 物理手机扫码、一次性管理员认领和 PWA 安装仍需用户终端确认。
- 本轮 Windows Tailscale 客户端处于 `NoState/starting`，无法从该客户端重新验证
  tailnet URL；板端 `tailscale status/serve` 检查通过。这不影响 LAN 交付，但本轮
  不新增“远程 URL 已验证”声明。
- 门户 `/api/health` 的总体 `ok=true`，但载荷仍引用一条 2026-07-08 生成的
  `failed_ai_nas_operator_portal_contract` 历史报告。它未阻断本次新用户部署、健康
  和入口验收，但应在后续门户合同专项复验中刷新，不应描述为全部历史 gate 清零。
- NAS 精确型号未由只读发现协议暴露，需要用户在 NAS 管理页确认；当前只记录
  `qnap_or_compatible`。
- NAS 断电、真实云服务、物理手机和回滚实际执行仍是现场验收项；自动验证脚本
  明确保留这些 manual drills，不把模拟结果当生产结果。

## 建议的下一次现场验收

1. 用用户手机打开 `http://digua.local/setup`，完成一次性认领并安装 PWA。
2. 若启用远程访问，先恢复一台正常的 Tailscale 客户端，再验证允许身份与拒绝
   身份两条路径。
3. 在维护窗口执行一次 NAS 断电降级/恢复和访问层回滚演练。
4. 单独刷新 `operator_portal_contract` 报告，确认历史失败载荷不再被健康页选中。

## 最终主分支收口补充（2026-07-18）

上述 `3ea55747` 是完成第二次真实重启验收时的精确运行快照。随后合入的身份同步、
相册预览兼容和 Python 3.10 兼容修复已形成最终主分支交付基线：

| 项目 | 最终值 |
| --- | --- |
| 实机部署基线 commit | `53649a86950ec1f381c5517d8a1f3948ac5b2cf5` |
| 发布目录 | `/opt/digua-ai-nas/releases/0.2.0-53649a86` |
| tar.gz SHA256 | `ce4a6c0b7abc97ea107e947d57ee0c1e598ec17dd63d1a17e170dd399d76698d` |
| 发布清单 | 423 个文件，`forbidden_file_count=0`，四项 self-check 全为 true |
| 最终访问层回滚点 | `/var/backups/digua-ai-nas/access-only-20260717T165427Z` |
| 本地回归 | 176 项测试通过 |

最终 access-only 升级报告继续确认 `existing_backend_preserved=true`、
`backend_units_touched=[]`。发布目录中的 `security.py`、`server.py` 和前端脚本与
`/opt/digua-ai-nas/app` 逐字节一致；身份、媒体和门户工具与
`/mnt/nas/openclaw/scripts/probes` 的实际运行副本逐字节一致；OpenClaw 单元与
用户级在用单元一致。`/opt/digua-ai-nas/app/scripts/probes` 不是 access-only 安装器
管理的 NAS 工具目标，不能用该遗留路径代替实际 NAS 工作区做一致性判定。

PR #46 增加了发布包内全部 Python 文件的 Python 3.10 语法 gate，修复了 S100P
Python 3.10 不接受的较新 f-string 写法。最终发布目录及 NAS 工作区中的门户脚本均在
板端 Python 3.10 实际编译通过。最终发布目录再次执行 S100P 验证套件，18 项全部
PASS；四个板端健康端点和四个 Windows LAN 入口均返回 HTTP 200。只读发现仍只要求
`allowed_share_scope_confirmation`，并确认未尝试凭据、未执行挂载、未扫描子网、未
改变状态。最终发布目录的云模式隔离安装 gate 也通过；它仍不等同于真实云 API 调用
验收。

本次最终 access-only 升级没有修改 systemd 单元；此前两次真实重启的持久化证据仍
适用。物理手机认领、NAS 断电、真实云服务调用、远程拒绝路径和回滚实际执行等现场
边界保持不变。

在该实机部署基线之后，PR #47 仅修改发布构建器、构建器合同测试及相册验收文档，
补齐 `configs/systemd/openclaw-gateway.service` 在独立 product-access 交付包中的
显式包含关系；它没有修改上述已部署的访问层文件、NAS 工具或 systemd 单元。实机
上的完整 0.2.0 发布包已经包含并逐字节核对该单元，因此该后续构建器修复不要求再次
部署，也不改变 `53649a86` 作为本轮实机运行基线的事实。
