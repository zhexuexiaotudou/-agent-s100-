# 地瓜 AI-NAS 产品访问架构

## 结论

产品日常拓扑是手机、路由器、S100P 与 TS-264C。现有门户继续监听 `127.0.0.1:8765`，Qwen 继续监听 `127.0.0.1:18080`；新增 `digua-product-access.service` 作为唯一 LAN Web 入口，监听 80 并只转发到门户。Dream7B 与 18888/18889 不进入本产品面。

远程访问走独立的 `127.0.0.1:8781` 受控入口。Tailscale Serve 或 cloudflared 只能指向该入口，远程入口服务默认不启用。LAN 监听器会删除 Tailscale、Cloudflare 和自定义代理身份头，远程监听器才会验证并映射身份。

```text
phone -- LAN HTTP --> :80 product access facade -- bearer translation --> 127.0.0.1:8765
phone -- Tailscale/Cloudflare HTTPS --> 127.0.0.1:8781 remote ingress --> same facade
portal --> 127.0.0.1:18080 Qwen / existing policy and ACL layers --> NAS allowlisted roots
```

## 状态与数据

- `/var/lib/digua-ai-nas/identity.sqlite3` 保留用户、会话与目录 ACL，使 NAS 离线时仍能登录并查看降级状态；安装器只在本地库不存在时复制旧 NAS 侧 identity DB。会话值继续只存 SHA-256 哈希。
- `product_access.sqlite3` 保存稳定设备身份、端点、claim 哈希、非秘密身份映射、审计与网络快照。
- 密码、claim 明文、Tailscale key、Cloudflare credential、NAS credential 和私钥不进入数据库、Git、前端或普通日志。
- 设备公开 ID 为随机 UUID，不使用 MAC 或硬件序列号。
- access-only 共存部署保留本地身份库，同时配置既有 8765 门户所使用的上游身份库。仅当已认证请求需要代理业务 API 时，访问层才在内存中建立短期上游会话；新增用户、角色变更和会话撤销必须同步到两侧。
- 访问层直接提供 `/ui` 与静态资源，并对页面响应设置 CSP。`img-src` 仅允许同源、`data:` 和 `blob:`；`blob:` 用于把鉴权后读取的本地图片响应交给浏览器预览，不允许外部图片源。已认证会话在渲染任何入口页前读取 `/api/storage/status`，因此侧栏容量不依赖用户先进入首页或设置页。

## 生命周期

`network-online -> NAS mount -> Qwen/OpenClaw/portal -> LAN facade -> optional remote ingress`。LAN 服务随安装启用；remote ingress 虽可挂入 `multi-user.target`，但安装后保持 disabled，只有远程 helper 完成 provider preflight 和明确确认后才 enable。NAS 或互联网不可用时，访问门面仍可返回 health、setup 与诊断状态，远程故障不关闭 LAN。

## 当前证据边界

截至 2026-07-17，S100P 与 NAS 已通电并完成 LAN 实机验收。S100P 为 aarch64 Ubuntu 22.04.5，NAS 通过 NFS4 挂载到 `/mnt/nas/openclaw`；Windows 局域网主机可解析并打开 `http://digua.local/`，备用地址 `http://192.168.127.10/` 同样可用。端口 80 是产品入口，既有门户 8765 与 Qwen 18080 保持回环监听。

已实测开机恢复、NAS 断挂降级与恢复、互联网默认路由断开时的本地能力、NetworkManager 变更 30 秒自动回滚、鉴权/角色/CSRF/撤销矩阵、二维码与打印卡、四个移动 viewport。物理手机扫码与 PWA 安装仍需用户侧终端确认；LAN HTTP 不是 secure context，PWA 安装应在 Tailscale 或 Cloudflare HTTPS 入口验证。

Tailscale 1.98.9 已加入用户 Tailnet，`https://digua.tail7c6cbb.ts.net/` 以 tailnet-only Serve 代理到 `127.0.0.1:8781`。真实 HTTPS 身份映射、未映射拒绝、LAN 伪造拒绝、重启保持及禁用/重启用均已通过；未配置公网 Funnel。当前残余为旧 iptables legacy connmark 健康告警，以及 Tailnet policy 已有但板端未使用的 Funnel capability，后者应在管理员完成控制台 welcome 后移除。Cloudflare 是可选入口，代码、JWT 测试和板端 dry-run 已通过，但没有真实域名、Access 应用、tunnel credential，外部验证不得宣称通过。
