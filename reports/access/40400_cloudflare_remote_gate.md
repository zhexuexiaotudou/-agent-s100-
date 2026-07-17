# 40400 Cloudflare Remote Gate

按产品定义保持 `configured_but_external_validation_pending`。已实现出站 tunnel 计划、Access 默认拒绝清单、root-only credential 路径、默认 disabled 服务，以及应用侧 RS256/JWKS signature、issuer、audience、expiry、subject 验证；错误 key/signature/audience/expiry 由自动测试覆盖。

最新 access-only 部署已把 `configure_remote_access.sh` 安装到板端；使用 `.invalid` 占位域名做 dry-run 返回 ok，确认不会改路由器、UPnP、Funnel 或数据库。当前未安装 cloudflared，也没有真实域名、Access application、IdP、tunnel credential，外部成功不作声明。
