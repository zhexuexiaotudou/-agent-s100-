# AI-NAS 新用户部署说明

## 产品目标

用户拿到已经刷好系统的 S100P 后，只需要把 S100P 与 NAS 接入同一局域网、
在 NAS 上准备一个专用共享，并选择本地模型或云端模型。其余可验证信息由
S100P 的确定性工具采集，模型只负责解释结果，不负责猜测地址、密码或权限。

```text
NAS 专用共享 -> S100P 系统挂载 -> AI-NAS 白名单工具 -> OpenClaw -> 本地/云端模型
```

模型不会直接登录 NAS，也不需要 NAS 管理员密码。

## 用户开始前必须完成

1. 将 S100P、NAS 和首次配置用的手机或电脑接入同一局域网。
2. 在 NAS 管理页面创建专用共享，建议命名为 `OpenClawWorkspace`。
3. 启用 NFS 或 SMB：
   - NFS：允许 S100P 的 IP/客户端身份读写该共享；
   - SMB：创建专用低权限用户，不使用 NAS 管理员账号。
4. 明确确认 AI-NAS 只能访问这个专用共享，不能访问整个 NAS。
5. 选择模型模式：S100P 本地模型，或者 OpenAI-compatible 云端 API。

## 系统会自动获取的信息

- S100P 网卡、路由和现有 NAS 挂载；
- 邻居表和 mDNS 中可见的 NAS 候选；
- NAS 的 NFS/SMB 和常见管理端口；
- 无凭据即可公开枚举的 NFS export 或 SMB share；
- 挂载后的容量、可用空间、文件系统类型和当前服务用户读写能力；
- 本地模型/BPU runtime 或云端 API 的实际健康状态；
- OpenClaw、索引、身份、产品状态和安全 gate。

发现阶段不会扫描整个网段、尝试密码、挂载共享或修改设备。

## 只有无法自动获取时才询问用户

- NAS IP 或主机名；
- 已启用的 NFS/SMB 协议；
- 专用 export/share 名称；
- SMB 专用凭据文件，或 NAS 后台的 NFS 客户端授权；
- 云端 API 地址、模型名和 API Key；
- 对最终允许目录范围的明确确认。

系统不得通过模型猜测这些值，也不得自动扩大授权范围。

## 推荐安装入口

```bash
sudo ./deploy/product_access/install.sh
```

安装器依次完成：NAS 发现、用户范围确认、S100P 严格预检、真实挂载、重启
持久化配置、服务用户写入测试、模型配置、应用和 venv 安装、systemd 启动、
LAN 首次认领及验收。

只查看发现结果：

```bash
python3 release/install/deploy_wizard.py --discover-only
```

## 模型模式

### 本地模式

用户提供已安装的 Qwen/BPU runtime 和模型路径。私有请求、NAS 检索和工具调用
全部留在 S100P。

### 云端模式

用户提供 HTTPS OpenAI-compatible API base URL、模型名和 API Key。API Key 只
保存到 S100P 受保护文件，不进入配置模板、安装报告、systemd unit 或发布包。
NAS/隐私请求不会发送给云端；云端只处理非隐私、非 NAS 范围的普通请求。

## 安装完成标准

- `/mnt/nas/openclaw` 的实际 SOURCE/FSTYPE 与用户选择一致；
- `Personal` 对运行服务的非 root 用户可写；
- 重启后 automount 仍能恢复；
- portal 和 model gateway 健康检查为 2xx 且 `inference_ready=true`；
- 手机可通过 `http://digua.local/setup` 完成一次性管理员认领；
- 带身份认证的产品 smoke 通过；
- 删除、覆盖、任意移动、整个 NAS 访问和私有原始数据出云保持关闭；
- 安装报告包含回滚点和仍需人工处理的事项，但不包含任何密码或 API Key。
