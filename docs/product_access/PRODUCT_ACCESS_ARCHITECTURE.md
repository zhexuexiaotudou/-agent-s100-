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

## 生命周期

`network-online -> NAS mount -> Qwen/OpenClaw/portal -> LAN facade -> optional remote ingress`。LAN 服务启用；remote ingress 没有 `WantedBy`，必须显式配置。NAS 或互联网不可用时，访问门面仍可返回 health、setup 与诊断状态，远程故障不关闭 LAN。

## 当前证据边界

截至 2026-07-17，S100P 与 NAS 未通电。本分支仅支持代码、Windows 本机 HTTP 集成测试与 Linux 容器 clean-install 模拟；mDNS、端口 80、systemd、NAS mount、Tailscale、Cloudflare、重启和手机实机均待验证包上板执行。
