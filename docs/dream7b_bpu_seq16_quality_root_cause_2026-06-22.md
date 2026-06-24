# Dream7B BPU seq16 单请求对话路径质量根因分析

Date: 2026-06-22
Author: 本地分析线程（只读代码核验 + 文档产出，不触碰 S100P）
Scope: 回答 goal 核心问题 —— 能否用 BPU 单请求常驻路径替换当前 GGUF/CPU 对话路径？
Status: 结构判断已完成；结论标注"待 live 生成输出交叉验证"（由并行 SSH 线程提供）

---

## 0. 方法和证据来源

本文档全部基于本地 `F:\Project\Digua` 仓库的只读代码核验，不运行任何 SSH / live probe / 服务重启命令，不触碰 S100P 状态，避免与并行 SSH 诊断线程冲突。所有结论附确切文件路径和行号。

核心证据文件：

- `完全基于agent的s100使用和链路打通/scripts/dream7b-bpu-diffusion-generate.sh`（BPU 单请求扩散生成入口，555 行）
- `完全基于agent的s100使用和链路打通/scripts/dream7b-bpu-fine-forward.sh`（BPU 前向，默认 fine-seq16 HBM）
- `scripts/diffuse_resident.cpp`（GGUF/CPU 常驻对话后端，177 行）
- `完全基于agent的s100使用和链路打通/scripts/dream7b_local_openai_gateway.py`（本地 OpenAI 网关，1283 行）
- `docs/dream7b_openclaw_gateway_fix_2026-06-22.md`（6/22 修复文档 + Remaining Boundary）
- `docs/dream7b_s100p_next_work_runbook.md`（§5 Release Package 清单）
- `TODO_dream7b_deployment_route.md`（Guardrail）

已由上游核验、本文不重复验证的事实：网关脚本 SHA256 = `E41C70185AAB63C0C497A8A9C90ED96AAC8BAF3A103FCCE5DF5FB0C8119BBEC6`，与 fix doc 远程哈希一致；`configs/systemd/dream7b-local-openai-gateway.service` 字段（`INLINE_TOKENIZER=0` / `RESIDENT=1` / `RESIDENT_CMD=/mnt/nas/openclaw/runtimes/diffuse-cpp/build/diffuse-resident` / `ExecStart` 走 tokenizer venv `/mnt/nas/openclaw/runtimes/dream7b-tokenizer-venv/bin/python`）与 fix doc 吻合。本地同步无需修。

---

## 1. 根因：为什么 BPU 路径 decoded text 非生产质量（带 token / 截断数学）

### 1.1 BPU 路径硬编码 seq_len=16，且 HBM 产物是 fine-seq16

`dream7b-bpu-diffusion-generate.sh` 第 215-218 行硬性拒绝任何 `seq_len != 16`：

```
215: if (( seq_len != 16 )); then
216:   echo "DREAM7B_BPU_DIFFUSION_GENERATE_SEQ_LEN must be 16 for the current Dream 7B seq16 HBM artifacts." >&2
217:   exit 2
218: fi
```

默认 `seq_len=16`（第 8 行），`min_mask_count=4`（第 9 行）。前向命令 `dream7b-bpu-fine-forward` 默认加载 `fine-seq16` HBM 产物（`dream7b-bpu-fine-forward.sh` 第 5 行：`fine_hbm_dir="${DREAM7B_BPU_FINE_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16}"`）。所以 seq16 不是脚本作者随手选的参数，而是当前 BPU HBM 产物编译窗口的物理约束：前向只能吃 `[1, 16, 152064]` 形状的 logits（脚本第 463 行断言 `forward_final_shape == [1, seq_len, 152064]`）。

### 1.2 对话模板必然使 prompt token 数 >= 16，触发尾部截断

脚本第 323-337 行的 prompt 准备逻辑：

```
323: tok = AutoTokenizer.from_pretrained(tokenizer_dir, trust_remote_code=True, local_files_only=True)
324: if prompt.startswith("<|im_start|>"):
325:     prepared = prompt
326: else:
327:     prepared = f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
329: prompt_ids = tok.encode(prepared)
330: mask_id = int(tok.mask_token_id)
331: prefix_limit = seq_len - min_mask_count
332: if len(prompt_ids) >= seq_len:
333:     prefix_ids = prompt_ids[-prefix_limit:]
334:     fit_mode = "truncate_prompt_keep_min_masks"
335: else:
336:     prefix_ids = prompt_ids
337:     fit_mode = "natural_prompt_then_masks"
339: tokens = prefix_ids + [mask_id] * (seq_len - len(prefix_ids))
```

截断数学（当 `len(prompt_ids) >= seq_len=16` 时，即对话场景的常态）：

- `prefix_limit = seq_len - min_mask_count = 16 - 4 = 12`
- `prefix_ids = prompt_ids[-12:]` —— 只保留 prepared prompt 的【最后 12 个 token】，丢弃前面全部上下文
- `tokens = prefix_ids + [mask_id] * (16 - 12) = 12 个尾部 token + 4 个 mask 位`
- 生成的有效新内容上限 = 4 个 token

对话模板 `<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n` 的固定开销（special tokens + 换行 + role 标记）本身就接近或超过 6-8 个 token；任何非空用户问题都会让 `prompt_ids >= 16`。因此生产对话场景【几乎必然】走 `truncate_prompt_keep_min_masks` 分支。

### 1.3 为什么"最后 12 个无上下文 token + 4 mask 位"结构上不可能产出生产质量对话文本

这是非自回归扩散生成（Dream/Masked Diffusion）的固定窗口约束，与自回归 LLM 有本质区别：

1. **上下文被尾部截断**：`prompt_ids[-12:]` 取的是 prepared prompt 的最后 12 个 token。对于对话模板，这 12 个 token 几乎必然落在 `<|im_end|>\n<|im_start|>assistant\n` 这段尾部模板标记上，用户实际问题内容早已被丢弃。模型前向看到的是一段【没有任何用户问题语义】的模板尾巴。

2. **生成窗口只有 4 个 mask 位**：扩散循环（第 348-431 行）只在 `mask_positions` 上迭代，而 `mask_positions` 上限就是 `min_mask_count=4`。默认 `steps=2`，最终步（第 423-424 行）`transfer_count = len(mask_positions)` 把剩余 mask 全部填掉。无论 prompt 多复杂、用户问什么，BPU 路径最多生成 4 个 token 的"回答"。

3. **非自回归 + 固定窗口**：扩散生成不是 token-by-token 自回归，而是一次性对固定长度窗口里的 mask 位做并行去噪。窗口长度由 HBM 产物编译时的 seq_len 钉死在 16，不能像 GGUF 路径那样随 prompt 长度动态扩展 `n_ctx`。所以即使不考虑截断，16 token 的总窗口也装不下"完整 prompt + 合理长度回答"。

脚本作者自己也在 payload 里标了边界（第 497 行）：`"boundary": "bounded_seq16_generation_entrypoint_not_complete_production_text_service"`，并在 generation.md 末尾写明"This is a bounded seq16 Dream diffusion generation entrypoint using S100P BPU logits. It is not a complete production text service."。这与 fix doc `docs/dream7b_openclaw_gateway_fix_2026-06-22.md` 第 142-143 行记录的"decoded text was still not production-quality"完全一致。

### 1.4 对比：GGUF/CPU 常驻路径为何能产出连贯 identity 文本

`scripts/diffuse_resident.cpp` 第 142-143 行：

```
142: int n_ctx = (int)input_tokens.size() + n_generate;
143: diffuse_context * ctx = diffuse_context_new(model, n_ctx, n_threads);
...
161: std::vector<int32_t> result = diffuse_generate(ctx, input_tokens, n_generate, params, nullptr);
```

- `n_ctx = input_tokens.size() + n_generate` —— 上下文窗口随完整 prompt 长度动态扩展，不绑 seq16
- `input_tokens` 是网关传入的【完整】prompt token 列表（无截断）
- `n_generate` 由网关 `max_tokens` 控制，网关第 820 行 clamp 到 `[1, 512]`，默认 16

网关侧 `dream7b_local_openai_gateway.py` 的 `run_dream_resident`（第 229-270 行）证实完整 prompt 传入、不截断：

```
231: token_arg, tokenizer_meta, tokenizer = prepare_prompt_tokens(prompt)
...
237: line = f"GEN\t{request_id}\t{max_tokens}\t{steps}\t{RESIDENT_SEED}\t{token_arg}\n"
```

`prepare_prompt_tokens`（第 126-139 行）把完整 `prepared_prompt` 一次性 encode 成 `ids`，再用 `",".join(...)` 拼成 `token_arg` 整体下发。`token_arg` 包含【全部】prompt_ids，无 `[-prefix_limit:]` 截断。C++ 侧 `parse_tokens(parts[5])`（第 136 行）还原完整列表后直接喂给 `diffuse_generate`。

这就是 GGUF/CPU 常驻路径能产出连贯 identity 文本（如 fix doc 记录的 "Dream7B-S100P-local" 身份回答）而 BPU 路径不能的根本结构差异：**前者上下文窗口随 prompt 动态扩展且不截断，后者被 seq16 HBM 产物钉死在 16 token 窗口并强制尾部截断到 12 prefix + 4 mask**。

### 1.5 根因小结

BPU 路径 decoded text 非生产质量的根因【不是】tokenizer 版本问题（6/22 的 tokenizer venv 修复已解决 identity 退化，那是 GGUF 路径的问题）。BPU 路径的根因是：

1. HBM 产物编译窗口太短（seq16，总窗口 16 token）
2. 非自回归扩散生成的固定窗口约束（窗口长度由 HBM 产物钉死，不能动态扩展 n_ctx）
3. 这两者共同导致对话场景必然触发 `truncate_prompt_keep_min_masks`，用 12 个无上下文尾部 token + 4 个 mask 位"生成"，结构上不可能产出生产质量对话文本

---

## 2. 对 goal 核心问题的结构判断

**问题**：能否用 BPU 单请求常驻路径替换当前 GGUF/CPU 对话路径？

**结构判断（基于本地代码）**：在当前 seq16 HBM 产物下【不能】。理由：

1. BPU 单请求路径的总生成窗口被 seq16 钉死在 16 token，对话模板开销 + 尾部截断后只剩 4 个 mask 位可用，最多生成 4 token "回答"。
2. 即使把 BPU 路径做成常驻进程（解决进程启动开销），也无法解决"窗口太短 + 必然截断"的结构问题 —— 这不是进程常驻能修的，fix doc 的 Remaining Boundary 已经说"下一个延迟/质量杠杆不再是进程常驻"。
3. 当前 GGUF/CPU 常驻路径（`diffuse-resident` + 网关 `run_dream_resident`）在结构上能产出生产质量文本：`n_ctx` 随完整 prompt 动态扩展，不截断，`n_generate` 可到 512。6/22 的 tokenizer venv 修复已让 identity 文本恢复正常。

**待 live 生成输出交叉验证**：本结论是基于本地代码的结构判断。并行 SSH 线程正在 S100P 上做 live BPU 单请求生成诊断，其 live 生成输出（`generation.md` 的 `decoded_final` 字段、`prompt_token_count`、`prefix_token_count`、`fit_mode`）将做最终确认。预期 live 输出会显示 `fit_mode=truncate_prompt_keep_min_masks`、`prompt_token_count >= 16`、`prefix_token_count=12`、`decoded_final` 为短且无意义片段，与本结构判断一致。若 live 输出意外显示 `fit_mode=natural_prompt_then_masks` 且 `decoded_final` 质量良好，则需重新审视本结论。

---

## 3. 前向选项 + 推荐

要让 BPU 路径能做生产质量对话，以下是三条前向路径，每条附工作量 / 风险 / 是否触及 guardrail：

### 选项 A：为更大 seq_len（如 seq128/seq256）重新编译 BPU HBM 产物

- **做什么**：重新跑 BPU 编译流水线，产出 `fine-seq128` / `fine-seq256` HBM 产物，并放宽 `dream7b-bpu-diffusion-generate.sh` 第 215-218 行的 `seq_len != 16` 硬退出，让 `prefix_limit = seq_len - min_mask_count` 能容纳完整 prompt + 合理 mask 位。
- **工作量**：高。需要重新编译 BPU HBM 产物（记忆显示 `.bc` 中间件曾占 ~341 GB，编译耗时长），重新做形状/正确性验证，并验证大窗口下扩散生成的质量。
- **风险**：中-高。大 seq_len 会显著增加 HBM 占用和前向延迟；扩散生成在大窗口下的收敛性和质量需重新验证。
- **是否触及 guardrail**：不触及，前提是【不删】现有 seq16 队列基线 HBM 产物（`segments6` + `fine-seq16`），新产物作为独立 `fine-seq128/seq256` 目录并存。

### 选项 B：在 BPU 上做滑动窗口 / KV-cache 扩展

- **做什么**：在 BPU 前向层引入滑动窗口或 KV-cache，让前向能处理超过 seq16 的上下文而不必每次重编译整个窗口的 HBM 产物。
- **工作量**：极高。需要修改 BPU 前向实现（底层算子/调度），不是改脚本能完成的。
- **风险**：高。触及 BPU 前向核心，可能影响现有队列基线的稳定性。
- **是否触及 guardrail**：有风险。若改动影响 `dream7b-bpu-batch-queue.service` 依赖的前向路径，可能间接触及"不得替换队列基线"guardrail。需严格隔离实验路径。

### 选项 C：BPU 只保留 throughput/logits 批处理基线，对话继续用 GGUF-resident

- **做什么**：维持现状架构 —— BPU 路径（`dream7b-bpu-batch-queue.service`）只做 throughput/logits 批处理基线，对话路径继续走 GGUF/CPU 常驻（`diffuse-resident` + 网关 18888）。6/22 的 tokenizer venv 修复已让 GGUF 路径产出正常 identity 文本。
- **工作量**：低（主要是维持 + 文档化边界）。
- **风险**：低。不改动任何已验证路径。
- **是否触及 guardrail**：不触及。完全满足所有 guardrail（不替换队列 service、不覆盖 18888、不删 seq16 HBM、不 promote true-batch、BPU 单请求评估不只看 avg_nonzero_bpu_loading）。

### 推荐

**推荐选项 C 作为当前部署路径**，并将选项 A 列为中长期质量提升方向（独立于生产路径做实验，不删 seq16 基线）。理由：

1. 6/22 的 tokenizer venv 修复已解决 GGUF 路径的 identity 退化，对话路径当前可用且已验证。
2. BPU 路径的 seq16 结构限制不是常驻化能修的，强行用 BPU 单请求替换 GGUF 对话会【降低】对话质量。
3. 选项 C 零风险且满足全部 guardrail；选项 A 是正确的长期方向但工作量大，应在生产路径稳定后再独立推进。

---

## 4. 发布包一致性抽查结果（只读）

### 4.1 `docs/dream7b_s100p_next_work_runbook.md` §5 Release Package 文件清单核验

逐项核验本地存在性：

| 清单项 | 本地路径 | 存在 |
| --- | --- | :-: |
| `scripts/probes/dream7b_perf_identity_probe.py` | `scripts/probes/dream7b_perf_identity_probe.py` | ✅ |
| `scripts/probes/dream7b_openclaw_default_latency_probe.py` | `scripts/probes/dream7b_openclaw_default_latency_probe.py` | ✅ |
| `scripts/diffuse_resident.cpp` | `scripts/diffuse_resident.cpp` | ✅ |
| `scripts/probes/ai_nas_edge_cloud_router_probe.py` | `scripts/probes/ai_nas_edge_cloud_router_probe.py` | ✅ |
| `scripts/probes/ai_nas_allowlisted_tool.sh` | `scripts/probes/ai_nas_allowlisted_tool.sh` | ✅ |
| `configs/systemd/*.service` | `configs/systemd/`（含 `dream7b-bpu-batch-queue.service`、`dream7b-local-openai-gateway.service`、`openclaw-gateway.service`、`ai-nas-index-daemon.service`） | ✅ |
| `docs/community/dream7b-s100-bpu-deploy/SKILL.md` | `docs/community/dream7b-s100-bpu-deploy/SKILL.md` | ✅ |

所有 §5 清单项在本地 `F:\Project\Digua` 根下均存在（部分在 `完全基于agent的s100使用和链路打通` 子目录下也有副本）。发布包一致性无缺失。

### 4.2 `truncate_prompt_keep_min_masks` 质量阻断标注缺口（需点出）

`truncate_prompt_keep_min_masks` 这个 `fit_mode` 值【只】出现在脚本和 probe 里作为运行时字段，从未在任何 `.md` 文档中被点名为质量阻断：

- 出现位置（全部是脚本/probe，非文档）：
  - `完全基于agent的s100使用和链路打通/scripts/dream7b-bpu-diffusion-generate.sh`（第 334 行，单请求）
  - `完全基于agent的s100使用和链路打通/scripts/dream7b-bpu-diffusion-batch-generate.sh`（第 425 行，批处理，同样的截断数学）
  - `完全基于agent的s100使用和链路打通/scripts/probes/dream7b_bpu_diffusion_loop_probe.sh`
  - `完全基于agent的s100使用和链路打通/scripts/probes/dream7b_bpu_diffusion_step_probe.sh`
- fix doc `docs/dream7b_openclaw_gateway_fix_2026-06-22.md` 的 "Remaining Boundary"（第 134-153 行）只写了"decoded text was still not production-quality"并指向一个 `generation.md` 产物路径，【没有】解释 `truncate_prompt_keep_min_masks` 这个截断机制是质量阻断的根因。
- 脚本自己只在 payload 里标 `"boundary": "bounded_seq16_generation_entrypoint_not_complete_production_text_service"`（第 497 行）和 generation.md 末尾的 boundary 说明，但 boundary 脚注是泛泛的"not a complete production text service"，【没有】具体说明"12 个尾部 token + 4 mask 位"的截断数学。

**建议**：在 fix doc 或 runbook 里补一句明确的 quality-blocker 标注，说明 `fit_mode=truncate_prompt_keep_min_masks`（`prefix_limit = seq_len - min_mask_count = 12`，对话场景几乎必然触发）是 BPU 单请求路径 decoded text 非生产质量的结构性根因，避免后续读者只看到"boundary"脚注而误以为是尚未完成的工程收尾，而非不可绕过的 seq16 窗口约束。本次只读分析不改动这些文档（避免与并行线程冲突），仅在此点出。

---

## 5. 最终结论

**是否可用 BPU 单请求常驻路径替换当前 GGUF/CPU 对话路径？**

【不能】。在当前 seq16 HBM 产物下，BPU 单请求路径被 16 token 固定窗口 + `truncate_prompt_keep_min_masks`（12 尾部 token + 4 mask 位）结构性地限制，无法产出生产质量对话文本；这不是 tokenizer 版本问题，也不是进程常驻能修复的问题。当前 GGUF/CPU 常驻路径（`diffuse-resident` + 网关 18888）在 6/22 tokenizer venv 修复后已能产出正常 identity 文本，应继续作为对话路径。BPU 路径应保留为 throughput/logits 批处理基线（`dream7b-bpu-batch-queue.service`）。若未来要让 BPU 路径做生产质量对话，需为更大 seq_len 重新编译 BPU HBM 产物（选项 A），但应作为独立实验推进，不删 seq16 基线、不替换生产对话路径。

本结论基于本地代码结构判断，**待并行 SSH 线程的 live 生成输出交叉验证**。
