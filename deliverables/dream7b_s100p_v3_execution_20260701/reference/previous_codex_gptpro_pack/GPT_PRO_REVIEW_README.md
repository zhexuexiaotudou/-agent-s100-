# GPT Pro 复核包说明

本包用于让 GPT Pro 复核 Dream7B diffusion 在 S100P 上是否已经达到“准确部署”的证据链要求，并为后续论文写作提供材料。请优先阅读：

1. `GPT_PRO_REVIEW_PROMPT.md`
2. `01_final_evidence/dream7b_s100p_gate_packet_v2.json`
3. `01_final_evidence/dream7b_s100p_final_technical_report_v2.md`
4. `reports/*.json` 与 `reports/*.md`
5. `prompt_pack/` 中的原始提示词和 gate 定义

## 当前结论边界

当前结论是 C 类：`deployment blocked against deployment reference but BF16 unresolved`。

- `compile_feasible`: pass
- `s100p_runtime_valid`: pass
- `logits_numerically_valid`: inconclusive
- `generation_quality_valid`: pending
- `product_route_valid`: pending

这意味着 seq128 HBM 链路可编译、可在 S100P 上加载并运行，但准确部署未被证实。当前路径被 GGUF Q4_K_M deployment reference 阻断，同时 BF16/PyTorch ground truth 未建立，所以不能写成 BF16 ground-truth failure。

## 关键证据文件

- `reports/000_reproduce_existing_evidence.json`: 既有证据复核，含 compile/runtime/GGUF gate。
- `reports/020_s100p_dump_logits_run.json`: S100P 全链路 logits battery dump，记录 logits 异常。
- `reports/030_segment_boundary_compare.json`: boundary compare，因 BF16 boundary 缺失保持 inconclusive。
- `reports/040_final_segment_lmheadq16_audit.json`: final segment isolated audit，真实 BPU seg26 output 进入 final segment 后输出恒定。
- `reports/040a_final_segment_metadata.json`: final segment metadata，HBM 可加载且 dequant scale 可读。
- `reports/050_seq128_input_alignment_audit.json`: input alignment audit。
- `reports/060_dequant_audit.json`: raw/dequant audit，raw output constant cases。
- `reports/070_logits_probe_battery_triplet.json`: BF16/GGUF/BPU triplet compare，BF16 missing。
- `reports/080_generation_quality_gate.json`: Gate 3 blocked/pending，未运行。
- `reports/090_product_route_isolation_gate.json`: Gate 4 blocked/pending，未运行，18888 未改。
- `reports/100_raw_evidence_inventory.json`: 原始 evidence 文件路径、大小、SHA256 清单。

## 原始大文件说明

本紧凑包不包含板端 905MB 原始 `.npy/.bin` 数组。它们保留在 S100P/NAS 路径：

`/mnt/nas/openclaw/reports/models/codex_dream7b_s100p_research_run_20260701/evidence`

对应文件大小和 SHA256 已写入 `reports/100_raw_evidence_inventory.json`。紧凑包内的 `evidence/codex_dream7b_s100p_evidence_metadata_20260701.tgz` 包含板端 evidence/reports/cases 的元数据和日志，但排除了 `.npy/.bin` 大数组。

## 复核注意事项

- 不得把 runtime pass 写成 accurate deployment pass。
- 不得把 GGUF Q4_K_M mismatch 写成 BF16 ground-truth mismatch。
- Gate 3/4 未运行，只能写 pending/blocked，不能写 failed。
- seq16 证据只能作为 negative control 和边界条件。
- 如果要继续执行部署路径，最小下一步是建立 verified BF16/PyTorch Dream7B forward wrapper，并对同一 hidden input 比较 `seg27_28` final projection。
