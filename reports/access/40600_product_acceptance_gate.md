# 40600 Product Acceptance Gate

当前结论：`product_access_lan_tailscale_pass_cloudflare_ready_for_external_validation`。

LAN、鉴权、NAS、重启、自愈、互联网断路、NFS 断挂、网络自动回滚、access-only 回滚/升级、二维码/访问卡、真实 S100P 四档移动 viewport 均已验收。PR #32 修复 remote unit 无法 enable 与板端 helper 不可执行问题，其两项 GitHub CI 全绿并合并到主线 `2db2ea3b385810f98ced5d3b415fc1a3e3e35255`；板端升级回滚点为 `/var/backups/digua-ai-nas/access-only-20260717T141432Z`，原 OpenClaw/Qwen unit 哈希保持不变。

Tailscale 私有 Serve 已完成真实 HTTPS、映射身份、未映射拒绝、LAN 伪造拒绝、重启保持、关闭回滚与重新启用验收；非 Tailnet Windows 客户端不能解析该域名，板端状态明确为 `tailnet only`。Cloudflare 按提示词允许停在代码与 dry-run 完成、外部域名/Access 待接入。物理手机扫码、第二台 Tailnet 客户端与浏览器 PWA 安装仍待用户终端。残余主机项为 iptables legacy connmark 告警、重复 Qwen system/user unit 状态冲突，以及已获授权但未使用的 Tailnet Funnel capability；当前没有公网 Funnel。没有改动 Dream7B。
