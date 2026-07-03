# Style And Structure Audit

Date: 2026-07-01

## Paper-Writing Rules Applied

- Problem-first framing: the draft opens with edge NAS deployment reliability rather than with model enthusiasm.
- Claim-first structure: each result subsection states the gate outcome before evidence details.
- Named mechanisms: the draft uses `分层证伪链`, `Route A`, `Route B`, `logits gate`, `seq128 B=1 lm_head q16 HBM`.
- Bounded claims: the draft does not claim all diffusion models fail on S100P.
- Gate discipline: Gate 3 and Gate 4 remain pending, not failed.

## Violations Found And Fixed

| Category | Count fixed | Fix |
| --- | ---: | --- |
| Overclaim risk | 3 | Replaced broad statements with "当前路径", "测试路径", and "可用 GGUF Q4_K_M 参考下". |
| Missing limitation | 2 | Added explicit BF16 caveat and two-case logits limitation. |
| Generic deployment wording | 4 | Replaced broad "可部署" language with gate-specific terms. |
| Result listing without takeaway | 4 | Added `Takeaway` paragraphs after each result cluster. |
| Product-route ambiguity | 2 | Stated that `18889` was not enabled and `18888` remained protected. |

## Section Checklist

| Section | Status | Notes |
| --- | --- | --- |
| 引言 | Pass | Stakes, structural gap, named method, contribution preview, and bounded result are present. |
| 系统与部署背景 | Pass | Explains HBM segmentation, OpenClaw two-track boundary, and seq16 negative-control role. |
| 分层证伪方法 | Pass | Defines gates, stop rule, and numerical metrics. |
| 实验材料与证据来源 | Pass | Names artifact metadata, runtime report, logits report, and reference limitation. |
| 结果 | Pass | Separates compile, runtime, logits, and product-boundary evidence; includes takeaways. |
| 讨论 | Pass | Interprets runtime-vs-accuracy split and avoids overgeneralization. |
| 局限性 | Pass | States GGUF-vs-BF16, limited cases, pending gates, and scope limitations. |
| 后续工作 | Pass | Gives experiments that distinguish HBM graph defects from reference or postprocessing mismatch. |

## Mechanical Scope

The current deliverable is a Markdown paper draft, not a LaTeX submission package. Page count, embedded fonts, unresolved LaTeX references, figure formats, and column balancing checks do not apply yet.

