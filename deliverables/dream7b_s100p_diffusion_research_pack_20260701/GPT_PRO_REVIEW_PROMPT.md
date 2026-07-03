# Prompt For GPT Pro Review And Paper Drafting

You are reviewing an evidence pack about Dream7B diffusion deployment on S100P. Your task is to independently audit the evidence and then draft a paper only if the evidence supports the claims.

Please proceed in this order:

1. Read `README_FOR_GPT_PRO.md`.
2. Audit the final packet in `01_final_evidence/dream7b_s100p_diffusion_research_packet.json`.
3. Audit the board runtime report in `02_primary_reports/seq128_runtime_gate/seq128_s100p_runtime_gate.json`.
4. Audit the logits comparison report in `02_primary_reports/seq128_logits_compare/seq128_logits_reference_compare.json`.
5. Cross-check prior context in `03_prior_evidence/docs/`, especially:
   - `dream7b_true_batch_hbm_feasibility_2026-06-18.md`
   - `dream7b_bpu_seq16_quality_root_cause_2026-06-22.md`
   - `dream7b_bpu_logits_diagnosis_2026-06-22.md`
   - `dream7b_seq128_cloud_compile_closure_2026-06-23.md`
   - `dream7b_openclaw_two_track_deployment_2026-06-22.md`
6. Inspect the scripts in `04_scripts/` only to judge reproducibility and whether the reported metrics were computed consistently.
7. Check `MANIFEST.csv` and `SHA256SUMS.txt` for package integrity.

Answer these audit questions before drafting:

1. Does the package prove `compile_feasible` for seq128 B=1 lm_head q16?
2. Does the package prove S100P board load/run validity for the tested chain?
3. Does the package falsify numerical validity of the tested BPU logits path?
4. Is the use of GGUF Q4_K_M reference an acceptable deployment-blocking control, and what limitation should be stated?
5. Are Gate 3 and Gate 4 correctly left pending rather than marked failed?
6. Are there any claims in the final research note that are stronger than the evidence permits?
7. What additional experiment would be needed to distinguish an HBM graph defect from a BF16/GGUF reference mismatch?

If the audit passes, draft a Chinese paper with this bounded thesis:

> Dream7B diffusion on S100P reached compile feasibility and board runtime validity for a seq128 segmented HBM chain, but the tested deployment path failed numerical logits validation, showing that runtime success alone is insufficient evidence of accurate deployment.

Required paper sections:

- 标题
- 摘要
- 关键词
- 引言
- 系统与部署背景
- 分层证伪方法
- 实验材料与证据来源
- 结果
- 讨论
- 局限性
- 后续工作
- 结论

Writing constraints:

- Do not claim that all diffusion models are impossible on S100P.
- Do not claim that seq128 generation quality failed; it was not tested after Gate 2 failed.
- Do not claim that product routing failed; it was intentionally not enabled.
- State clearly that the numerical failure is against the available GGUF Q4_K_M reference path, not a completed BF16 CPU reference.
- Treat seq16 evidence as a negative control and boundary condition, not as proof about seq128.
- Prefer evidence-grounded language over promotional or absolute wording.

