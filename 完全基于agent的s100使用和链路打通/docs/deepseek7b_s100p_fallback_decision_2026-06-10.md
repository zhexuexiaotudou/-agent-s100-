# DeepSeek 7B S100P Fallback Decision

Date: 2026-06-10

## Verdict

Official DeepSeek-R1-Distill-Qwen-7B is available as a vendor HBM asset, but it is not a runnable fallback on the current S100P state.

The HBM downloaded successfully and is non-empty:

- HBM: `/mnt/nas/openclaw/models/s100-official-deepseek-r1-distill-qwen-7b/DeepSeek_R1_Distill_Qwen_7B_1024.hbm`
- Size: `7928846896` bytes
- `hbm_size_bytes: 7928846896`
- Probe: `scripts/probes/s100_official_deepseek7b_baseline_probe.sh`
- Latest runtime report: `/mnt/nas/openclaw/reports/models/s100_official_deepseek7b_baseline_20260610-023455/deepseek7b_baseline_probe.json`
- Isolated config: `/mnt/nas/openclaw/reports/models/s100_official_deepseek7b_baseline_20260610-023455/isolated_runtime/deepseek7b_multichat_config.json`

The runtime does not complete:

- `runtime_status: failed`
- `runtime_returncode: 1`
- `runtime_completed: False`
- `hbm_load_success_observed: False`
- `init_model_success_observed: False`
- `memory_alloc_failure_observed: True`
- `bpu_alloc_request_bytes: 7928846896`
- `decision: official_7b_runtime_blocked_common_buffer`

The stderr/stdout logs show the failure occurs while loading the 7B HBM into BPU memory:

- `Cannot malloc bpu memory with length 7928846896 bytes`
- `Load hbm failed! error: HBRT4_STATUS_BAD_DATA`
- `Fail to do ION_IOC_ALLOC(ret=Cannot allocate memory)`
- `Fail to allocate common buffer`

`hrt_ucp_monitor` captured no useful BPU execution because the model fails before inference begins. The monitor shows the relevant ION heaps are far smaller than the requested 7.9GB allocation (`cma_reserved` around 1.0GB, `ion_cma` 512MB, `carveout` 512MB).

## Comparison

- Qwen2.5-1.5B `cache_len=512`, `chunk_size=128`: runnable official baseline, `runtime_returncode: 0`, no memory allocation failure.
- Dream 7B official OELLM: blocked at `registry_missing` because Dream/DreamModel is not in the official SDK registry.
- Dream 7B segmented HBM: real Dream weights run through segmented BPU HBM, but current status remains `hbm_reload_dominated`; latest top-window refresh records `load_to_run_ratio: 9.678265`, worse than current best `9.468172`.
- DeepSeek-R1-Distill-Qwen-7B: official HBM exists, but runtime is blocked by common-buffer/BPU memory allocation on the current board state.

## Decision

Do not treat DeepSeek-R1-Distill-Qwen-7B as the current deployable 7B fallback until the vendor confirms and validates the required S100P memory layout or runtime configuration.

Qwen2.5-1.5B `512/128` remains the verified official runnable fallback. It is currently the only verified official fallback. Dream remains the target model through the segmented HBM route, with the next optimization focused on reducing HBM reload rather than further top-window splitting.

## Questions For Teacher Or Vendor

1. Does `DeepSeek_R1_Distill_Qwen_7B_1024.hbm` require a different S100P memory layout, ION heap allocation, `hb_switch_ion.sh bpu_first`, reboot, or performance-mode setting before it can load?
2. Is a 7.9GB single common-buffer/BPU allocation expected for this HBM, or should the official runtime stream/map it differently?
3. If S100P cannot load this 7B HBM under the current memory layout, what is the official runnable 7B baseline for this board?
4. Should the project continue with Qwen2.5-1.5B as the only verified official fallback while Dream 7B proceeds through segmented HBM optimization?
