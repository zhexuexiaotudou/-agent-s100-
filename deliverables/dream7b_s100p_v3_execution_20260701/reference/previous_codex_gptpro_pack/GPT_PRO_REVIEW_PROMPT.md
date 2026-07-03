# 给 GPT Pro 的复核提示词

请基于我上传的整个压缩包，严格复核 Dream7B diffusion 在 S100P 上“准确部署”的证据链，并为论文写作准备审稿级结论。

你的任务不是直接给出“能/不能”，而是按 gate 判定：

1. `compile_feasible`
2. `s100p_runtime_valid`
3. `logits_numerically_valid`
4. `generation_quality_valid`
5. `product_route_valid`

请重点读取：

- `01_final_evidence/dream7b_s100p_gate_packet_v2.json`
- `01_final_evidence/dream7b_s100p_final_technical_report_v2.md`
- `reports/*.json`
- `reports/*.md`
- `prompt_pack/GATE_DEFINITIONS.md`
- `prompt_pack/VERDICT_MATRIX.md`
- `GPT_PRO_REVIEW_README.md`

请完成以下复核：

1. 检查最终结论 `deployment_blocked_against_deployment_reference_but_bf16_unresolved` 是否被证据支持。
2. 检查是否有任何地方把 GGUF Q4_K_M mismatch 错写成 BF16 ground-truth failure。
3. 检查是否有任何地方把 Gate 3/4 未运行错写成 failed。
4. 检查 `reports/020_s100p_dump_logits_run.json`、`reports/060_dequant_audit.json`、`reports/040_final_segment_lmheadq16_audit.json` 是否共同支持“BPU logits 路径存在数值阻断，但根因仍需 BF16 reference 进一步定位”。
5. 检查 `reports/100_raw_evidence_inventory.json` 是否足以说明原始证据文件存在、大小和 SHA256。
6. 给出论文可用的最终判定，必须在以下四类中选一类：
   - A. accurate deployment supported
   - B. deployment falsified against BF16 reference
   - C. deployment blocked against deployment reference but BF16 unresolved
   - D. inconclusive due to missing artifact/reference/input alignment
7. 如果发现证据不足，请指出缺少哪个最小实验、哪个 report 字段不能支持对应 claim。

写作约束：

- 不得泛化为“所有 diffusion model 都不能部署到 S100P”。
- 不得把“可运行”写成“准确可用”。
- 每个关键 claim 后必须引用包内 report 文件名和字段名。
- 论文中的 seq16 证据只能作为 negative control，不得作为 seq128 准确部署结论的直接证据。
