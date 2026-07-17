# Cloudflare Tunnel + Access

该模式代码已完成但外部验证待定。先在 Cloudflare 创建 self-hosted Access 应用、默认 deny 与显式 Allow，再创建 named tunnel。origin 只能是 `http://127.0.0.1:8781`，不能开放路由器端口。

credential 放在 `/etc/cloudflared/digua-credentials.json`，权限 0600。team domain 与 audience 放 root-owned 环境文件；credential/token 不写 unit、Git、SQLite 或报告。应用使用 `Cf-Access-Jwt-Assertion`，验证 RS256 signature、issuer、audience、expiry 和 subject，并缓存/轮换 JWKS。

```bash
bash release/install/configure_remote_access.sh --provider cloudflare --hostname nas.example.com --tunnel-id UUID --team-domain team.cloudflareaccess.com --audience AUD --dry-run
sudo bash release/install/configure_remote_access.sh --provider cloudflare --hostname nas.example.com --tunnel-id UUID --team-domain team.cloudflareaccess.com --audience AUD --apply --confirm 'ENABLE CLOUDFLARE ACCESS TUNNEL'
```

上板验收必须覆盖未授权身份、正确身份、错误 audience、过期 JWT、错误签名、origin 直连失败、禁用 tunnel 后 LAN 继续可用。
