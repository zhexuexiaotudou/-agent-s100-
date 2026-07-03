# Gate Definitions

## Gate 0: compile_feasible

Pass 条件：

- artifact manifest complete。
- expected HBM/HBO count present。
- hashes verified，或 excluded artifacts 被明确记录。
- seq_len、batch_size、segment_count、lm_head bits、final_logits_mode 都可追溯。

不能推导：

- 不能推出 numerical correctness。
- 不能推出 generation quality。
- 不能推出 product route validity。

## Gate 1: s100p_runtime_valid

Pass 条件：

- representative segments on S100P load/run。
- full chain executes expected segment count。
- final shape matches expected `[1,152064]`。
- no resource exhaustion。
- errors empty。

不能推导：

- 不能推出 logits correctness。
- 不能推出准确部署。

## Gate 2: logits_numerically_valid

Pass 条件：

- input alignment verified。
- dequant/postprocess verified。
- BPU logits match BF16/PyTorch reference above thresholds。
- deployment reference mismatch, if present, has documented explanation。
- no all-zero/constant logits anomaly for semantic cases。

Fail 条件：

- input alignment and dequant verified 后，BPU still mismatches BF16 reference。
- top-k、cosine、entropy、probability metrics fail beyond thresholds。

Inconclusive 条件：

- BF16 reference unavailable。
- input alignment unresolved。
- dequant metadata missing。
- required artifacts missing.

## Gate 3: generation_quality_valid

只允许在 Gate 2 pass 后运行。

Pending / blocked 条件：

- Gate 2 not pass。

## Gate 4: product_route_valid

只允许在 Gate 3 pass 后运行。

必须保持：

- 18888 foreground route unchanged。
- 18889 experimental route isolated。
- rollback/fallback/health/queue drain/latency/failure-rate evidence complete。
