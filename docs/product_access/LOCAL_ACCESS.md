# 局域网访问

首选 `http://digua.local/`，备用为 `http://<S100P-LAN-IP>/`。Avahi 发布 `_http._tcp:80`；`.local` 只提供 LAN 便利性，不是公网域名或 TLS 证明。

`digua-access endpoints` 查看配置端点，`digua-access qr --mode lan --output lan.svg` 生成不含凭据的二维码，`digua-access card --output access-card.html` 生成打印卡。mDNS 失败时不改路由器、不启用 UPnP，直接使用 DHCP 地址或路由器 DHCP 保留地址。

当前 hostname 冲突的最终行为必须在目标网络用 `hostnamectl` 与 Avahi 实测；若冲突，应设置 `digua-<short_device_id>` 后重新生成卡片，不得猜测名称已生效。
