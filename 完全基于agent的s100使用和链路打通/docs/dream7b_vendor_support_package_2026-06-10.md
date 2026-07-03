# Dream 7B / Official 7B S100P Vendor Support Package

Date: 2026-06-10

## Forwardable Question

老师/厂商您好，我们现在在 S100P 上推进 Dream 7B 和官方 7B 兜底路线，遇到两个明确卡点，需要确认是否属于官方支持边界或板端内存配置问题。

第一，官方 DeepSeek-R1-Distill-Qwen-7B 的 HBM 可以下载并识别，但在当前 S100P 上加载失败。失败发生在 HBM load 阶段，还没有进入推理。请确认 `DeepSeek_R1_Distill_Qwen_7B_1024.hbm` 是否需要特殊的 S100P 内存布局、ION heap 配置、`hb_switch_ion.sh bpu_first`、重启顺序或 performance-mode 设置才能加载；如果当前板端不适合加载这个 7B HBM，请推荐一个官方确认可在该 S100P 状态下跑通的 7B LLM 兜底模型。

第二，Dream 7B 走官方 `oellm_build/leap_llm` 路线时卡在模型注册表阶段：Dream/DreamModel 不在官方 SDK registry 中。请确认官方是否有 Dream/DreamModel adapter、插件式接入接口，或可提供最小 adapter 要求；如果没有，我们就把 Dream 官方 OELLM 迁移判定为 SDK 适配缺失，继续走 segmented HBM 路线。

Exact vendor questions for tracking:

```text
DeepSeek 7B requires what S100P memory layout or runtime settings to load DeepSeek_R1_Distill_Qwen_7B_1024.hbm?
Dream/DreamModel has an official adapter path for oellm_build/leap_llm?
```

## Minimal Reproduction Evidence

### 1. Official DeepSeek 7B HBM Load Failure

Probe:

```text
scripts/probes/s100_official_deepseek7b_baseline_probe.sh
```

Latest report:

```text
/mnt/nas/openclaw/reports/models/s100_official_deepseek7b_baseline_20260610-023455/deepseek7b_baseline_probe.json
```

HBM:

```text
/mnt/nas/openclaw/models/s100-official-deepseek-r1-distill-qwen-7b/DeepSeek_R1_Distill_Qwen_7B_1024.hbm
hbm_size_bytes: 7928846896
```

Observed result:

```text
runtime_status: failed
runtime_returncode: 1
runtime_completed: False
hbm_load_success_observed: False
init_model_success_observed: False
memory_alloc_failure_observed: True
bpu_alloc_request_bytes: 7928846896
decision: official_7b_runtime_blocked_common_buffer
avg_bpu_loading: 0.0
```

Key log lines:

```text
Cannot malloc bpu memory with length 7928846896 bytes
Load hbm failed! error: HBRT4_STATUS_BAD_DATA
Fail to do ION_IOC_ALLOC(ret=Cannot allocate memory)
Fail to allocate common buffer(ret=-16777211)
```

Relevant memory state captured by `hrt_ucp_monitor`:

```text
cma_reserved: total 1.0G, used 7.9M, free 1016.1M
ion_cma: total 512.0M, used 0.0, free 512.0M
carveout: total 512.0M, used 2.0M, free 510.0M
```

Kernel cmdline and `/proc/meminfo` snapshot:

```text
cmdline has no explicit cma= setting
MemTotal: 22305984 kB
CmaTotal: 0 kB
CmaFree: 0 kB
```

Interpretation: the official 7B HBM asset exists, but this board state cannot allocate the required 7.9GB BPU/common-buffer region. This is not a tokenizer or HBM path issue.

### 2. Official Qwen 1.5B Success Control

Latest runnable official baseline:

```text
/mnt/nas/openclaw/reports/models/s100_official_qwen_fullflow_20260609-210514/official_qwen_fullflow_probe.json
```

Configuration:

```text
model_name: qwen2_5-1_5b
cache_len: 512
chunk_size: 128
```

Observed result:

```text
runtime_status: completed
runtime_returncode: 0
runtime_completed: True
hbm_load_success_observed: True
init_model_success_observed: True
memory_alloc_failure_observed: False
prefill: 1024.00 tokens/s
decode: 25.57 tokens/s
```

Interpretation: the SDK/runtime/board path is not globally broken. A smaller official model can run; the DeepSeek 7B failure is tied to the 7B HBM memory requirement or required board memory layout.

### 3. Dream 7B Official OELLM Registry Block

Latest Dream OELLM feasibility report:

```text
/mnt/nas/openclaw/reports/models/dream7b_oellm_fullflow_feasibility_20260609-223754/dream7b_oellm_fullflow_feasibility_probe.json
```

Observed result:

```text
build_host_compatible: True
dream_registered_in_official_sdk: False
compile_status: blocked_registry_missing
failure_stage: registry_missing
compiled_hbm_count: 0
direct_oellm_migration_supported: False
```

Dream config summary:

```text
model_type: Dream
architectures: ['DreamModel']
hidden_size: 3584
num_hidden_layers: 28
num_attention_heads: 28
num_key_value_heads: 4
vocab_size: 152064
mask_token_id: 151666
torch_dtype: bfloat16
use_cache: true
```

SDK registry summary includes official Qwen/DeepSeek/InternVL families, but not Dream/DreamModel.

Interpretation: Dream official OELLM migration is blocked before graph compilation. The current evidence points to missing official model adapter/registry support, not an AVX/build-host issue.

## Current Internal Fallback Decision

Until official feedback changes the above:

```text
Qwen2.5-1.5B 512/128 remains the verified official runnable fallback.
DeepSeek-R1-Distill-Qwen-7B is staged but not deployable on the current S100P memory layout.
Dream 7B remains the target model through segmented HBM, but current performance diagnosis is hbm_reload_dominated.
```

The latest Dream segmented refresh records:

```text
avg_bpu_loading: 8.97
load_to_run_ratio: 9.678265
current_best_load_to_run_ratio: 9.468172
diagnosis: hbm_reload_dominated
```

We will not claim 128TOPS utilization progress unless average BPU loading, load/run ratio, batch16 wall time, or sustained telemetry materially improves.
