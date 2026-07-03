# Dream7B diffusion 在 S100P 上的分层证实/证伪研究

## 摘要

本文复核并扩展 Dream7B diffusion 在 S100P 上的 seq128 B=1 segmented HBM、lm_head q16、last-token logits 部署证据。当前最终结论是 **C 类：deployment blocked against deployment reference but BF16 unresolved**。换言之，已支持“seq128 HBM 链路可编译、可在 S100P 上加载并运行”，但尚不支持“准确部署可用”。证据：`01_final_evidence/dream7b_s100p_gate_packet_v2.json` 字段 `verdict, verdict_class, gate_status`。

## 关键词

Dream7B；diffusion language model；S100P；BPU；HBM；GGUF；BF16；logits numerical validation；分层证伪。

## 引言

本研究不把问题简化为“扩散模型能不能上 S100P”，而是拆成 compile feasibility、board load/run/shape validity、logits numerical validity、generation quality、product route validity 五个 gate。任一 gate 未通过，只能说明该层被阻断，不能外推为全部 diffusion model 不适配 S100P。证据：`prompt_pack/GATE_DEFINITIONS.md` 字段 `Gate 0-4 definitions`。

## 系统与部署背景

被测对象是 `seq128, B=1, segmented HBM, lm_head q16, last-token logits`。既有证据包显示 manifest 和关键 artifact 已复核，compile gate 为 `pass`，S100P runtime gate 为 `pass`。证据：`reports/000_reproduce_existing_evidence.json` 字段 `gate_status.compile_feasible, gate_status.s100p_runtime_valid`。

产品边界保持不变：本轮没有改动前台 `OpenClaw -> 18888 -> diffuse-resident/GGUF` 路径，也没有启用 foreground BPU route。Gate 3/4 在 Gate 2 未通过时保持 pending/blocked，而不是 failed。证据：`reports/080_generation_quality_gate.json` 字段 `gate_status, product_route_changed`。证据：`reports/090_product_route_isolation_gate.json` 字段 `foreground_18888_changed, experimental_18889_enabled`。

## 分层证伪方法

Gate 0/1 检查 artifact、manifest、板端 load/run 和 final shape；Gate 2 对同一输入比较 BPU logits 与 BF16/PyTorch reference，并同时记录 GGUF Q4_K_M deployment reference 结果；Gate 3 只在 Gate 2 pass 后检查生成质量；Gate 4 只在 Gate 3 pass 后验证隔离产品路由。当前 BF16/PyTorch forward wrapper 未建立，因此 BF16 ground-truth failure 不能成立。证据：`reports/070_logits_probe_battery_triplet.json` 字段 `verdict, errors`。证据：`evidence/bf16_reference_probe/bf16_reference_export.json` 字段 `status`。

## 实验设计

本轮按提示词包执行了七类工作：复核既有 evidence package；生成 seq128 probe cases；建立 BF16/GGUF/BPU 三路对齐框架；在 S100P 保存 BPU raw/dequant logits；审计 seq128 输入对齐；定位 final segment 与 dequant；扩展 logits probe battery 并聚合 gate packet v2。原始证据文件已登记 inventory，共 `192` 个文件，累计 `948018244` bytes。证据：`reports/100_raw_evidence_inventory.json` 字段 `file_count, total_size_bytes, files[].sha256`。

## 结果

### Gate 0/1：编译与板端运行

既有证据复核支持 compile feasible 和 S100P runtime valid；这只证明低层链路可编译、可加载、可运行，并不等同于准确部署。证据：`reports/000_reproduce_existing_evidence.json` 字段 `gate_status`。

本轮重新执行的 S100P logits dump 覆盖 10 个 probe cases，命令能跑完整链路并输出 final logits，但报告 verdict 为 `blocked_s100p_dump_logits_anomaly`，原因是输出 softmax 接近均匀且 raw/dequant logits 对输入不敏感。证据：`reports/020_s100p_dump_logits_run.json` 字段 `verdict, cases[].softmax.normalized_entropy, cases[].top5`。

### Gate 2：数值正确性

Gate 2 当前为 `inconclusive`。GGUF Q4_K_M deployment reference 仍阻断当前路径，但 BF16/PyTorch ground truth 未建立，因此不能写成 BF16 mismatch 或 BF16 证伪。证据：`01_final_evidence/dream7b_s100p_gate_packet_v2.json` 字段 `gate_status.logits_numerically_valid, deployment_reference_status, bf16_reference_status`。

扩展 logits battery 的三路比较报告 verdict 为 `inconclusive_triplet_compare_bf16_missing`。这说明当前已有 BPU 与 GGUF 对比证据，但缺少能决定模型数学真值的 BF16/PyTorch reference。证据：`reports/070_logits_probe_battery_triplet.json` 字段 `verdict, cases, errors`。

输入对齐审计没有发现 token length、position id、last-token index 的结构性错误，`input_alignment_valid` 为 `pass`；但 tokenizer decode 仍属于待补强证据。证据：`reports/050_seq128_input_alignment_audit.json` 字段 `input_alignment_valid, checks`。

dequant audit verdict 为 `upstream_graph_or_runtime_issue_raw_constant`，10 个 battery cases 的 raw output 均进入 raw_constant_cases；这更像 upstream graph/runtime/final input 问题，而不是单一 dequant scale 公式问题。证据：`reports/060_dequant_audit.json` 字段 `verdict, raw_constant_cases, cases[].variants`。

final segment isolated audit verdict 为 `blocked_final_segment_constant_or_uniform`：合成 hidden 输入可以产生非恒定 logits，但真实 BPU seg26 输出进入 final segment 后出现恒定 logits、normalized entropy=1。该结果把疑点推进到真实链路激活、segment 接口解释或 final input 分布，而不是简单归因于 lm_head HBM 文件不存在。证据：`reports/040_final_segment_lmheadq16_audit.json` 字段 `verdict, cases[input_kind=real_bpu_seg26_output].raw_stats.constant, cases[].softmax.normalized_entropy`。

final segment metadata 可正常加载并读到 q16 lm_head 的输出量化 metadata，`040a` verdict 为 `ok_final_segment_metadata`。证据：`reports/040a_final_segment_metadata.json` 字段 `verdict, output_quant_metadata.scale_first, model_names`。

### Boundary localization

boundary activation compare verdict 为 `inconclusive_boundary_compare_bf16_missing`，主要限制是 BF16 boundary 缺失；S100P boundary dump 还在 final segment 加载阶段出现过 resource exhausted。因此 boundary 证据目前只能支持“定位受阻”，不能支持“BF16 对齐失败”。证据：`reports/030_segment_boundary_compare.json` 字段 `verdict, errors`。证据：`reports/030_s100p_boundary_dump.json` 字段 `verdict, errors`。

### Gate 3/4

由于 Gate 2 未 pass，generation quality gate 未执行，状态是 pending/blocked；product route isolation gate 也未执行，`18888` foreground route 未改变，`18889` 未启用。证据：`reports/080_generation_quality_gate.json` 字段 `gate_status, reason`。证据：`reports/090_product_route_isolation_gate.json` 字段 `gate_status, foreground_18888_changed, experimental_18889_enabled`。

## 根因定位

当前最小可信定位是：编译和板端运行成立，但 BPU logits 在 available GGUF deployment reference 下失败，同时 BF16/PyTorch 真值缺失；raw/dequant audit 和 final segment isolated audit 表明问题更可能发生在真实 segmented chain 激活传递、runtime output interpretation、或 final segment 输入分布上。证据：`01_final_evidence/dream7b_s100p_gate_packet_v2.json` 字段 `blocking_issues, next_minimal_experiment`。

## 讨论

本轮证据避免了两个常见误判。第一，runtime pass 不是 accurate deployment pass；第二，GGUF Q4_K_M mismatch 不是 BF16 ground-truth mismatch。当前更稳妥的论文表述是：Dream7B seq128 HBM 在 S100P 上具备低层部署可行性，但准确部署被 logits numerical gate 阻断，且 BF16 ground truth 仍待建立。证据：`01_final_evidence/dream7b_s100p_gate_packet_v2.md` 字段 `Claim Boundary`。

## 局限性

第一，缺少 verified Dream7B BF16/PyTorch forward wrapper；第二，semantic prompt 仍以 token-id proxy 方式进入 probe battery，tokenizer decode 证据需补；第三，boundary dump 在 final segment 处曾遇到 resource exhaustion，完整 boundary localization 尚未完成；第四，Gate 3/4 因 Gate 2 未通过而未运行。证据：`reports/030_bf16_boundary_export.json` 字段 `verdict, reason`。证据：`reports/030_s100p_boundary_dump.json` 字段 `verdict, errors`。

## 后续工作

下一步最小实验是建立 verified BF16/PyTorch Dream7B forward wrapper，在相同 hidden input 上比较 `seg27_28` final projection，并重新运行 `compare_logits_triplet.py` 与 `build_dream7b_s100p_gate_packet.py`。如果 BF16 对齐通过，再进入 generation quality；如果 BF16 对齐失败，才可写成 deployment falsified against BF16 reference。证据：`01_final_evidence/dream7b_s100p_gate_packet_v2.json` 字段 `next_minimal_experiment`。

## 结论

本轮结论为 **C 类：deployment blocked against deployment reference but BF16 unresolved**。Dream7B seq128 HBM chain 已通过 compile 与 S100P load/run/shape gate；但当前 BPU logits 路径被 GGUF Q4_K_M deployment reference 阻断，BF16 ground truth 尚未建立，Gate 3/4 保持 pending/blocked，前台 `18888` 路由未改变。证据：`01_final_evidence/dream7b_s100p_gate_packet_v2.json` 字段 `verdict, gate_status, blocking_issues`。
