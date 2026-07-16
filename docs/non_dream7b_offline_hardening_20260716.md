# 非 Dream 7B 功能离线加固记录（2026-07-16）

## 结论

本轮只处理 Digua 已实现的非 Dream 7B 功能。S100P 与 NAS 当前均不在线，因此代码、契约、临时本地目录、SQLite 和本地 HTTP 链路可以验收；板端模型、真实 NAS 数据、systemd 持久化、重启恢复和端到端性能不能验收，也没有被写成“已通过”。

## 已完成的修复

1. 身份与 Web 安全
   - 移除前端默认 `admin/admin123` 自动登录；令牌只保存在浏览器会话存储中。
   - 首用户管理员创建改为 SQLite 原子事务；密码 PBKDF2 迭代数提升到 310000；增加 15 分钟内 5 次失败的登录限流。
   - 新会话令牌只以 SHA-256 摘要落库；旧明文会话首次使用时自动迁移，不强制全部用户退出。
   - 除 `/api/health` 和身份注册/登录入口外，产品 API 均要求认证；任务队列读取、入队和取消仅管理员可用。
   - AI 索引、媒体列表、文档问答和私有文件路径按当前用户 ACL 过滤；高风险全局重建和自动整理保持管理员边界。
   - 增加 CSP、防嵌套、防 MIME 猜测、Referrer 与 Permissions Policy；动态 HTML 值统一转义。

2. 文档与文件链路
   - 新增只读、虚拟的文档分类模块；不移动原文件，校验 Personal 根目录、符号链接和逐文件 ACL。
   - 修正文档分类 UI 与服务端契约，返回真实 `items` 和分类计数。
   - 普通文件与文档上传改为原始字节流，不再整文件 Base64；服务端分块写临时文件、校验大小与截断、无覆写落盘。
   - 下载改为分块输出；JSON 请求增加 8 MiB 全局上限、非法长度、UTF-8 和截断检查。

3. 后台任务与能力真实性
   - 产品任务队列增加原子 claim、租约超时回收、尝试次数和终态失败；worker 可以连续轮询并执行已有路由。
   - 尚无 ACL 安全实现的 OCR rebuild 不再接受新任务；历史遗留 OCR 任务会明确失败，不会永久卡在 queued。
   - `faster_whisper`、`vosk`、`whisper_cpp` 在没有执行实现时不再仅凭依赖或模型目录宣称可用。
   - 安全攻击探针把网络失败、401 和网关不可达记为 `inconclusive`，不再伪装成 blocked/pass。
   - 指标汇总排除过期证据，把失败 gate、warning 和 degraded 纳入分母与阻断项。

4. 发布与运维
   - 发布包包含可运行的 `src/`、`web/`、门户、Qwen 网关、任务 worker、指标与安全探针和依赖清单，不包含 Dream 7B 模型或产物。
   - 安装脚本复制完整应用、创建隔离 venv、渲染实际安装/NAS/报告路径，并传播目录、复制、pip 与 systemd 失败。
   - worker 改为常驻服务；删除会重复激活常驻 worker 的过期 nightly timer。
   - 移除两份未被运行时使用的过期发布配置，以及两份历史 `.recovered` / `.utf8_fixed` 源文件。
   - 新增非 Dream 7B GitHub Actions：Python 3.13 编译、全部离线单元测试、全部静态 JS 语法和无模型发布包构建。

## 当前离线证据

- 修改前基线：114 个测试通过。
- 修改后全量：131 个测试通过。
- 本地 HTTP：未认证敏感 API 返回 401；普通用户不能查看任务队列；双用户媒体 ACL 隔离通过；认证后的流式上传与分块下载内容一致。
- 静态检查：`src/`、`scripts/`、`gates/` 编译通过；`web/static/*.js` 全部通过 `node --check`；Git diff whitespace 检查通过。
- 发布构建：模型无关 tar/zip/sha256/manifest 成功生成，manifest 为 `ok=true`，禁入文件为 0。

这些证据只证明本地、离线和契约层通过，不证明 S100P/NAS 当前可用。

## 延期的真实链路验收门

设备恢复后必须按顺序执行，不允许跳过前项后宣称生产就绪：

1. `s100p_connectivity_verified`
   - 确认当前板端 IP、SSH 用户、主机指纹、系统版本、磁盘空间和时间同步。
2. `nas_mount_acl_verified`
   - 确认真实挂载点、专用 Personal 共享、读写权限、符号链接边界和两个普通用户的交叉 ACL 负测。
3. `clean_install_verified`
   - 在 Linux/S100P 上运行 clean-install gate；检查 venv、完整应用文件、渲染后的 systemd 单元和失败回滚点。
4. `services_persistent_verified`
   - 检查 Qwen、门户和任务 worker `active/enabled`；重启 S100P 后再次检查；确认门户仍只监听 loopback。
5. `real_data_paths_verified`
   - 使用用户批准的小型真实样本依次验证上传、列表、下载、文档分类、FTS/RAG、媒体索引、相册/搜索和软删除恢复。
6. `local_model_paths_verified`
   - 验证当前实际 Qwen、embedding、YOLO、OCR 和唯一声明为可用的 ASR 后端；无模型或无执行实现时必须显示 degraded/unavailable。
7. `probe_truth_verified`
   - 使用有效管理员令牌运行安全探针和指标检测；网络失败或认证失败只能是 inconclusive。
8. `upgrade_rollback_verified`
   - 记录部署 commit、旧包和数据库备份，验证升级、服务重启和回滚。
9. `production_acceptance_verified`
   - 跑产品 smoke 与关键用户路径，保存板端命令、日志、报告和截图；之后才允许更新生产就绪结论。

## 仍然生效的边界

- Gateway 不暴露公网，默认只监听 `127.0.0.1`。
- OpenClaw 不访问整个 NAS，只访问专用 Personal 范围。
- 删除、覆写、非受控移动/重命名、任意 shell 和 Qwen 自主工具执行仍保持禁用或受控。
- 本记录不修改、验证或评价 Dream 7B 路线。
