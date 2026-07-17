# Product Access Threat Model

| Asset | Attacker | Attack path | Mitigation | Residual risk | Test |
|---|---|---|---|---|---|
| First admin | LAN malicious user |抢先使用 claim|短期随机 token、hash-only、错误次数限制、仅无用户和 LAN、成功即失效|访问卡被替换仍可能抢占|并发 claim、重放、过期与 remote claim 测试|
| Local session | XSS/盗机者 |窃取 session|HttpOnly、SameSite、Secure on HTTPS、CSP、logout/revoke|已解锁手机仍有风险|Cookie flags、logout/revoke 回归|
| State changes | malicious site |CSRF POST|所有 Cookie 状态变更校验 CSRF|浏览器扩展可见页面 token|无/错误 CSRF 必须 403|
| Login | LAN/remote brute force |重复密码猜测|PBKDF2 310k、窗口锁定、统一失败|分布式慢速尝试|速率限制测试|
| Role boundary | viewer/operator |调用管理员 API|admin-only API、viewer mutation deny、既有 ACL|读取型 POST 需持续维护 allowlist|角色矩阵测试|
| Tailscale identity | LAN user |伪造 identity headers|独立 loopback remote ingress、LAN 剥离同名 header、未映射拒绝|已取得 S100P 本地代码执行且能连接 8781 的进程仍可伪造；设备不向用户提供 shell，并应最小化本机进程|header spoof 集成测试与本机威胁复审|
| Cloudflare identity | origin bypass attacker |伪造 Access header/JWT|origin 仅 loopback、Access default deny、RS256/iss/aud/exp/signature 校验|Cloudflare/IdP 配置错误|错误 audience/expiry/signature 测试|
| Tunnel credential | local reader/Git leak |读取 token/credential|root-only file、DB/Git/unit/API 禁止 secret|root compromise|mode 0600 与 secret scan|
| NAS data | remote user |路径遍历或直连 NAS|统一入口、现有 normalize/ACL、无 NAS 服务代理|既有业务路由缺陷|遍历与 ACL 下载测试|
| Internal services | LAN/Internet attacker |直连 8765/18080/调试口|后端回环、只开放产品入口、proxy allow boundary|错误部署可能改 bind|socket/bind 实机检查|
| Browser data | shared device |Service Worker 缓存私有 API|API/download network-only，shell-only cache，logout 清客户端状态|浏览器自身历史|SW contract 与 Cache Storage 检查|
| UI integrity | XSS attacker |未转义 endpoint/文件名|CSP、现有 escape helper、安全 JSON|第三方浏览器扩展|XSS payload 回归|
| Name discovery | LAN attacker |mDNS 欺骗或名称冲突|访问卡显示 short ID 与备用 IP，claim 仍需 token|用户可能忽略 ID|冲突网络与假 mDNS 演练|
| QR/card | physical attacker |替换二维码|QR 不含永久 session/secret，claim 短期，显示设备 short ID|首次 claim 仍需人工核对|QR 内容和过期测试|
| Network availability | admin mistake |错误静态 IP 导致失联|先快照、明确确认、systemd 定时回滚、console rollback|systemd-run 不可用时只剩手动恢复|隔离网络 rollback 演练|
| Logs/audit | support operator |日志泄露密码/token/IP|字段 allowlist、secret key 丢弃、结果脱敏|异常库可能打印内容|secret grep 与异常测试|
| Degraded mode | unauthenticated user |NAS/remote 故障时绕过鉴权|health 最小化、业务仍需 session/ACL、远程故障不改变 LAN auth|未知旧路由|NAS off/Internet off/remote off 矩阵|

Trust boundary: the LAN listener never trusts forwarded identity headers. The remote listener accepts Tailscale headers only on its loopback-only socket and still requires explicit local identity mapping; Cloudflare additionally requires JWT verification. Any local code-execution foothold able to reach 8781 is therefore inside the Tailscale header trust boundary; local root can additionally change services or databases. This residual risk must be reviewed on the final appliance image.
