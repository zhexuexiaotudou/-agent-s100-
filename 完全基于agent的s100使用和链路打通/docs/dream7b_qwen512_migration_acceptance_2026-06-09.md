# Dream 7B / Qwen 512-128 Migration Acceptance

Date: 2026-06-09

## Verdict

- Qwen official baseline: passed at Qwen2.5-1.5B `cache_len=512`, `chunk_size=128`.
- Dream official OELLM route: blocked before compile because Dream is absent from the official `leap_llm` model registry/model factory.
- Dream segmented HBM route: refreshed and accepted, but no new utilization improvement versus the current best `load_to_run_ratio=9.468172`.
- Current Dream utilization status: still `hbm_reload_dominated`; do not claim sustained 128TOPS utilization success.

## Qwen Official Baseline

The current runnable official LLM baseline is Qwen2.5-1.5B with `cache_len: 512` and `chunk_size: 128`.

- HBM: `/mnt/nas/openclaw/models/s100-official-qwen-fullflow/cache_len_512_chunk_128/qwen2_5-1_5b_chunk_128_cache_512_q8.hbm`
- Runtime report: `/mnt/nas/openclaw/reports/models/s100_official_qwen_fullflow_20260609-210514/official_qwen_fullflow_probe.json`
- Diagnosis report: `/mnt/nas/openclaw/reports/models/s100_qwen15_common_buffer_diagnosis_20260609-211000/s100_qwen15_common_buffer_diagnosis_20260609.md`
- Key runtime fields: `runtime_completed: true`, `runtime_returncode: 0`, `memory_alloc_failure_observed: false`, `max_bpu_loading: 98.0`, `avg_bpu_loading: 2.222`
- Performance line: `Performance prefill: 1024.00tokens/s    decode: 25.57tokens/s`

The earlier Qwen2.5-1.5B `cache_len=1024`, `chunk_size=256` run remains a high-context failure case. It loads/initializes HBM but fails at S100P runtime common-buffer/BPU allocation with `runtime_returncode: -11`, `memory_alloc_failure_observed: true`, and `AllocError { len: 2359296 }`.

## Dream Official OELLM Feasibility

Latest report: `/mnt/nas/openclaw/reports/models/dream7b_oellm_fullflow_feasibility_20260609-223754/dream7b_oellm_fullflow_feasibility_probe.json`

The build host is compatible (`host_machine: x86_64`, `host_has_avx: true`, `build_host_compatible: true`), so the current blocker is not the NAS AVX/SIGILL issue. The blocker is registry/model-adapter coverage:

- `dream_registered_in_official_sdk: false`
- `compile_status: blocked_registry_missing`
- `failure_stage: registry_missing`
- `compiled_hbm_count: 0`
- `direct_oellm_migration_supported: false`
- `missing_adapter_evidence.registry_missing: true`
- `missing_adapter_evidence.required_adapter: official leap_llm model_factory registration and Dream/DreamModel adapter`
- `unable_to_attempt_direct_official_compile_reason`: Dream is absent from the official `leap_llm` model factory registry.

Official SDK registry list captured in the failure package:

`deepseek-qwen-1_5b`, `deepseek-qwen-7b`, `qwen2_5-1_5b`, `qwen2_5-7b`, `internvl2-2b`, `internvl2_5-2b`, `internvl2-1b`, `internvl2_5-1b`, `internlm2-1_8b`, `qwen2_5-omni-3b`

Dream config summary:

- Source/config: `/mnt/f/Project/Digua/tmp/dream_hf/config.json`
- `model_type: Dream`
- `architectures: ['DreamModel']`
- `hidden_size: 3584`
- `num_hidden_layers: 28`
- `num_attention_heads: 28`
- `num_key_value_heads: 4`
- `vocab_size: 152064`
- `mask_token_id: 151666`
- `torch_dtype: bfloat16`
- `use_cache: true`

Conclusion: the official OELLM Dream route is blocked by SDK registry/model-adapter support. It is not yet a model-structure compile failure, HBM generation failure, runtime failure, or build-host failure, because direct compile cannot be legitimately attempted until the official SDK has a Dream/DreamModel adapter or a documented custom-model path.

## Dream Segmented HBM Refresh

Latest refreshed reports:

- Artifact inventory: `/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_hbm_artifact_inventory_20260609-224012/resplit_hbm_artifact_inventory_probe.json`
- Local artifact inventory: `/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_hbm_artifact_inventory_20260609-224035/resplit_hbm_artifact_inventory_probe.json`
- Batch telemetry: `/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_batch_telemetry_20260609-224100/resplit_batch_telemetry_probe.json`
- Window cost: `/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_window_cost_20260609-224142/resplit_window_cost_probe.json`
- Utilization gap: `/mnt/nas/openclaw/reports/models/dream7b_bpu_utilization_gap_20260609-224156/utilization_gap_probe.json`
- Deployment acceptance: `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260609-224157/deployment_acceptance_probe.json`

Key fields:

- Top-window split includes `14:15`, `15:17`, `17:18`, and `18:19`
- `expected_hbm_count: 8`, `existing_hbm_count: 8`, `manifest_verified_count: 8`
- `total_hbm_size_bytes: 2512771264`
- `batch_count: 16`
- `avg_bpu_loading: 8.97`
- `forward_metrics.load_to_run_ratio: 9.678265`
- `load_to_run_ratio: 9.678265`
- `diagnosis: hbm_reload_dominated`
- `check_count: 30`, `passed_check_count: 30`

Comparison:

- Historical top-window ratio: `9.694618`
- Current best ratio: `9.468172`
- Latest refresh ratio: `9.678265`

The latest refresh is better than the historical `9.694618` but worse than the current best `9.468172`, and average BPU loading is lower than the current-best run. This is not a new utilization improvement.

## Questions For Teacher Or Vendor

1. Does the official S100 LLM SDK have a supported path for adding a custom HuggingFace model with `model_type: Dream` and `architectures: ['DreamModel']` into `leap_llm` model_factory, or must D-Robotics provide the adapter?
2. Can the vendor provide the minimum required Dream/DreamModel adapter interface: config parser, model class mapping, attention/KV-cache handling, tokenizer/template expectations, and supported quantization path?
3. Is Qwen2.5-1.5B `cache_len=512`, `chunk_size=128` the recommended S100P production baseline, and is `1024/256` expected to fail on common-buffer/BPU memory without a larger reserved memory layout?
4. For WSL/x86 builds, is there an official `oellm_build` flag to skip host-side HBM load/ION validation after HBM emission, or should final HBM generation always run in native Linux/Docker?
5. For Dream segmented HBM, should the next optimization target be runtime residency/persistent segment caching instead of further top-window splitting, given the unchanged `hbm_reload_dominated` diagnosis?
