# Token Budget & Privacy Router

本模块为 Digua AI-NAS 提供本地 token 预算、隐私脱敏、上下文压缩和边云路由能力。

## 处理链路

用户请求 / NAS 上下文
→ Qwen tokenizer 计数
→ privacy redactor
→ context compressor
→ cloud route decider
→ token trace
→ local_only / cloud_allowed_redacted / cloud_blocked_private

## Tokenizer 来源

本项目代码通过本地 Qwen2.5 模型目录加载 tokenizer，例如：

```bash
export DIGUA_QWEN_TOKENIZER_PATH=/path/to/local/Qwen2.5
```

本 repo 默认不重新分发 Qwen tokenizer 或模型权重文件，例如：

- tokenizer.json
- tokenizer_config.json
- vocab.json
- merges.txt
- *.safetensors
- *.bin
- *.gguf

## API

- `POST /api/token-budget/estimate`
- `POST /api/token-budget/route`
- `GET /api/token-budget/trace/{run_id}`
- `GET /api/token-budget/summary`
- `GET /api/token-budget/benchmark-summary`

## Benchmark

当前 evidence package 的 benchmark 结果：

| 指标 | 数值 |
| --- | ---: |
| benchmark cases | 130 |
| average cloud input token reduction | 92.68% |
| median reduction | 100% |
| p90 reduction | 100% |
| cloud call avoidance rate | 61.54% |
| private leak count | 0 |
| quality pass rate | 100% |

说明：这些结果表示本项目 benchmark 中的云端输入 token 对照下降，不等同于真实账单成本下降。

## 安全边界

- 不保存 raw private content。
- redaction map 只留在本地 trace。
- cloud payload 只允许 redacted / optimized 内容。
- private / denied 内容默认 local_only 或 cloud_blocked_private。
- 本模块不执行 NAS 写操作。
- Qwen 不拥有工具执行权。
