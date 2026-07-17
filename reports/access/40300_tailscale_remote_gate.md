# 40300 Tailscale Remote Gate

状态：`passed_private_serve_with_host_residuals`。S100P 已加入用户自有 Tailnet，Tailscale 1.98.9 为 `Running`，私有入口为 `https://digua.tail7c6cbb.ts.net/`，只代理到回环地址 `127.0.0.1:8781`。

真实 HTTPS 请求由 Tailscale 注入已批准的 owner 身份，显式映射到本地 `admin`；外部登录名不进入公开证据。未映射身份返回 401，LAN 伪造同名身份头仍保持未登录。`/ui`、manifest 和 service worker 均由 HTTPS 入口返回成功。关闭 helper 后 Serve 清空、8781 停止且 LAN 保持健康；重新启用后入口恢复。S100P 重启后 remote ingress、Serve、NAS、LAN 和业务端口均自动恢复。

`tailscale funnel status` 明确显示 `tailnet only`，Windows 非 Tailnet 客户端不能解析该 MagicDNS 域名，没有公网 Funnel 服务。Tailscale 授权页同时给 Tailnet 添加了 Funnel 使用能力，但板端从未执行 `tailscale funnel`，当前没有公网配置；该能力应在用户完成管理控制台 welcome 流程后从 tailnet policy 的 `nodeAttrs` 中移除。另有 S100P 旧版 iptables legacy `CONNMARK --restore-mark` 健康告警，当前不阻断 Serve，但仍是主机网络加固残余项。独立手机/第二台 Tailnet 客户端的物理验收仍待用户终端。
