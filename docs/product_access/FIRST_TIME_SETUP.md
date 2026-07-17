# 首次部署与认领

1. S100P 与 NAS 通电并接入同一路由器，确认 NAS 共享与模型路径。
2. 在 S100P 执行 `sudo deploy/product_access/preflight.sh`。
3. 执行 `sudo deploy/product_access/install.sh`，按向导逐项输入 NAS 地址、共享目录和现有模型路径；密码不会写入报告。
4. 安装器初始化设备身份、systemd、Avahi、空用户库和访问状态库，不创建默认管理员，也不启用远程访问。
5. 控制台只显示一次 claim code，并生成 `/var/lib/digua-ai-nas/claim-qr.svg` 与 `access-card.html`。普通报告不保存 claim 明文。
6. 手机连接相同 LAN，打开 `http://digua.local/setup` 或备用 `http://<S100P-IP>/setup`，输入 claim code 并创建首个管理员。
7. 成功后 claim 立即失效。再执行 `digua-doctor` 与验证包。

若 claim 丢失且仍无用户，在 S100P 控制台运行 `digua-access claim-create --qr-out /var/lib/digua-ai-nas/claim-qr.svg`。已有用户时该命令拒绝生成新 claim。
