# 40100 LAN Discovery Gate

结论：实机通过。S100P 为 aarch64 Ubuntu 22.04.5，`digua-product-access.service` 在端口 80 active；Windows 端 `digua.local` 解析到 `192.168.127.10` 与兼容地址 `192.168.137.10`，mDNS URL 与备用 IP 均返回 HTTP 200。Avahi 可发现 `Digua AI-NAS on digua`。

NAS 实际挂载为 `169.254.143.37:/OpenClawWorkspace`、NFS4、可写。移除互联网默认路由后，本地入口、鉴权、NAS、门户和 Qwen 仍通过，恢复路由后外网连通恢复。

板端 `digua-access qr` 与 `card` 已生成 5096 字节 SVG 和 7819 字节打印 HTML，命令明确报告 `contains_secret=false`。首次验收发现 CLI 错用系统 Python，已在 PR #28 修复并实机复验。物理手机扫码和强制 hostname 冲突演练仍需人工终端配合，不影响当前 LAN 门禁结论。
