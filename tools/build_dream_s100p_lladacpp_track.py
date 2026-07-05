from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TRACK = ROOT / "dream_s100p_lladacpp"


def read_json(path: str) -> dict[str, Any]:
    target = ROOT / path
    if not target.exists():
        return {"missing": True, "path": path}
    with target.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def artifact(path: str) -> dict[str, Any]:
    target = ROOT / path
    return {
        "path": path,
        "exists": target.exists(),
        "size_bytes": target.stat().st_size if target.exists() else 0,
    }


def compact_v21() -> dict[str, Any]:
    packet = read_json("01_final_evidence/dream7b_s100p_gate_packet_v21.json")
    hf = read_json("reports/2010_semantic_hf_truth_loader_gate.json")
    islands = read_json("reports/2020_semantic_bpu_island_battery.json")
    return {
        "packet_verdict": packet.get("final_verdict"),
        "full_bpu_logits_state": packet.get("logits_numerical_validity_current_full_bpu_path"),
        "semantic_hf_truth": hf.get("hf_truth_summary", {}),
        "semantic_island_verdict": islands.get("verdict"),
        "semantic_island_summary": islands.get("island_summary", {}),
        "safety": packet.get("safety", {}),
        "product_route": packet.get("product_route"),
        "openclaw_foreground": packet.get("openclaw_foreground"),
        "ports_18888_18889": packet.get("ports_18888_18889"),
        "current_product_route": packet.get("current_product_route"),
    }


LLADACPP_POINTS = [
    {
        "id": "block_wise_static_window",
        "lladacpp_design_point": "Use block-wise denoising windows instead of treating every step as arbitrary-length decoding.",
        "why_it_matters_for_dllm": "A dLLM has many masked positions early and fewer later; block windows expose dense work to an accelerator.",
        "s100p_equivalent_implementation": "Define fixed block sizes 16, 32, and 64 with static input/output tensor contracts before any full-model graph attempt.",
        "required_tests": ["truth case can enter a fixed block driver", "block tensor shapes are static", "no generation claim"],
        "risk": "A fixed block driver can still be numerically wrong if token masks, position ids, or timestep semantics differ from HF truth.",
        "fallback_plan": "Keep the PyTorch block driver as the only runnable path and hold BPU compilation.",
        "implementation_status": "planned",
    },
    {
        "id": "multi_block_speculative_decoding",
        "lladacpp_design_point": "Admit future-block draft tokens when current-block masked-token count becomes too small.",
        "why_it_matters_for_dllm": "Late denoising steps underfill NPU/BPU compute; speculative draft work keeps dense kernels useful.",
        "s100p_equivalent_implementation": "Represent draft tokens in the scheduler but forbid them from updating committed prefix state until accepted by strict rules.",
        "required_tests": ["draft tokens do not alter commit order", "latency trace records admitted draft count", "quality gate compares against full logits"],
        "risk": "Speculation can hurt quality if draft state leaks into stable tokens.",
        "fallback_plan": "Disable speculation and run one-block denoising only.",
        "implementation_status": "planned_after_phase3",
    },
    {
        "id": "dual_path_progressive_revision",
        "lladacpp_design_point": "Keep early visible tokens revisable and refresh unstable tokens through a sparse side path.",
        "why_it_matters_for_dllm": "dLLM tokens may become visible before they are truly stable; correctness needs revision without stalling dense accelerator passes.",
        "s100p_equivalent_implementation": "Track visible, stable, and revisable masks in CPU-side state; let BPU focus on dense block denoising until a verified sparse path exists.",
        "required_tests": ["revision mask trace", "stable token never silently changes", "unstable token revision budget enforced"],
        "risk": "Revision state bugs can make output appear stable while logits truth disagrees.",
        "fallback_plan": "Require all visible tokens to be stable before commit, accepting lower speed.",
        "implementation_status": "planned_after_truth",
    },
    {
        "id": "prefix_kv_cache_reuse",
        "lladacpp_design_point": "Reuse prefix KV state across denoising steps and invalidate only the affected sparse regions.",
        "why_it_matters_for_dllm": "Repeated denoising revisits the same prefix; recomputing it wastes CPU and BPU time.",
        "s100p_equivalent_implementation": "Start with CPU reference cache hashes and version ids; only promote to BPU visible buffers after layer-level truth passes.",
        "required_tests": ["cache hit rate recorded", "cache invalidation on revision", "full recompute comparison"],
        "risk": "Bad invalidation can preserve stale hidden state and pass only synthetic cases.",
        "fallback_plan": "Disable cache reuse for correctness gates.",
        "implementation_status": "planned_after_phase5",
    },
    {
        "id": "selective_logits_skipping",
        "lladacpp_design_point": "Skip redundant logits for tokens already stable, especially when lm_head pressure dominates.",
        "why_it_matters_for_dllm": "Vocabulary-sized logits are expensive and memory-heavy; stable positions do not need repeated output projection.",
        "s100p_equivalent_implementation": "Compute logits only for active or uncertain positions after a full-logits comparison proves identical decisions.",
        "required_tests": ["full-vs-selective logits comparison", "top1/top5 unchanged for skipped positions", "speedup recorded"],
        "risk": "Skipping logits before truth exists can hide correctness failures.",
        "fallback_plan": "Use full logits for every correctness gate.",
        "implementation_status": "planned_after_phase3",
    },
    {
        "id": "swap_optimized_memory_runtime",
        "lladacpp_design_point": "Use graph-guided NPU-visible memory mapping and pipelined staging.",
        "why_it_matters_for_dllm": "Repeated denoising makes remap and transfer cost part of the inner loop, not only model load.",
        "s100p_equivalent_implementation": "Define S100P BPU buffer classes for weights, KV/revision state, token state, logits/confidence, and double-buffered staging.",
        "required_tests": ["preallocated buffers", "inner loop allocation count", "copy/remap timing trace"],
        "risk": "Memory staging can make a numerically wrong graph look like a performance issue.",
        "fallback_plan": "Run with explicit per-step allocation for debug, then optimize after truth gates pass.",
        "implementation_status": "planned_after_phase7",
    },
    {
        "id": "operator_library_before_full_graph",
        "lladacpp_design_point": "Treat accelerator support as a library of validated ops, not a single opaque full graph.",
        "why_it_matters_for_dllm": "Current Dream7B evidence localizes failures around early segment contracts; full-graph pass/fail is too coarse.",
        "s100p_equivalent_implementation": "Build per-op and per-layer gates for embedding, position/RoPE, RMSNorm, QKV, attention, MLP, residual, and lm_head.",
        "required_tests": ["per-op manifest entry", "cosine/max_abs/relative_l2", "official scale/layout only"],
        "risk": "Missing vendor source graph or quant metadata can block closure.",
        "fallback_plan": "Hold at operator alignment and request vendor/compiler metadata for seg00_01.",
        "implementation_status": "next_after_phase2",
    },
    {
        "id": "low_bit_quant_with_activation_calibration",
        "lladacpp_design_point": "Treat quantization as a runtime and quality loop, not only offline weight compression.",
        "why_it_matters_for_dllm": "Low-bit paths can change confidence, token stability, and final logits decisions.",
        "s100p_equivalent_implementation": "Start with W8A16, record activation ranges by layer, then try W4 only after W8 passes logits gates.",
        "required_tests": ["calibration samples >= 64", "top1/top5 degradation", "quality loss bound or blocker"],
        "risk": "Current seg00_01 failures could be worsened by unverified activation scaling.",
        "fallback_plan": "Keep sensitive layers and lm_head higher precision.",
        "implementation_status": "blocked_until_op_layer_truth",
    },
    {
        "id": "fixed_task_validation_before_chat",
        "lladacpp_design_point": "Validate on fixed output lengths and block tasks before claiming broad generation.",
        "why_it_matters_for_dllm": "A block runtime can pass narrow tensor tests but still fail format, stability, or semantic quality.",
        "s100p_equivalent_implementation": "Use eight fixed tasks: command, JSON plan, NAS intent, summary, infill, rewrite, Chinese normalization, and safety refusal.",
        "required_tests": ["task count >= 8", "format pass rate", "latency and fallback ratio", "no OpenClaw foreground route"],
        "risk": "Fixed-task success can be overclaimed as general dialogue.",
        "fallback_plan": "Report fixed-task-only success and keep product route locked.",
        "implementation_status": "phase11_only",
    },
]


def build_phase0(now: str) -> dict[str, Any]:
    v21 = compact_v21()
    data = {
        "schema_version": "dream7b_s100p_lladacpp_phase0_baseline_lock",
        "created_at_utc": now,
        "track": "Dream7B S100P llada.cpp-style correctness-first research track",
        "status": "phase0_baseline_locked",
        "latest_local_evidence": {
            "current_full_bpu_path": "falsified_against_HF_PyTorch_BF16_logits_truth",
            "semantic_truth_rows_status": "v21 has 8/8 original semantic HF/PyTorch BF16 truth rows; full llada-style 31-row truth_cases.jsonl is not yet exported",
            "seg00_01_status": "strongest localized contract-fault locus from prior v14-v21 route; exact closure remains vendor/compiler metadata blocked",
            "generation_quality_status": "not_run_by_design",
            "product_route_status": "not_run_by_design; Qwen + OpenClaw remains current product route",
            "semantic_bpu_island_status": v21.get("semantic_island_verdict"),
            "semantic_island_detail": "islands [1], [2], and [1,2] show partial diagnostic signal only, no deployable logits-correct island",
            "safety": v21.get("safety", {}),
        },
        "available_artifacts": [
            artifact("docs/DREAM7B_S100P_SEQ128_LOGITS_VALIDITY_ROUTE_STATUS_20260704.md"),
            artifact("01_final_evidence/dream7b_s100p_gate_packet_v21.json"),
            artifact("reports/2010_semantic_hf_truth_loader_gate.json"),
            artifact("reports/2020_semantic_bpu_island_battery.json"),
            artifact("reports/2060_final_v21_gate_packet_and_package.json"),
            artifact("evidence_for_gptpro/dream7b_s100p_v21_for_gptpro_20260704_122503.zip"),
            artifact("evidence/semantic_hf_truth_v21/semantic_truth_export_report.json"),
            artifact("evidence/semantic_island_battery_v21/hf_boundaries_and_island_eval_report.json"),
        ],
        "missing_artifacts": [
            "reference/truth_cases.jsonl with >=31 llada-style semantic/canonical/block/revision/infill/control rows",
            "official seg00_01 source graph and quant metadata",
            "per-op BPU reference inputs/outputs for Dream7B operator library",
            "compiled static block graph for block_size=16",
            "S100P block-wise runtime trace for fixed block tasks",
        ],
        "exact_blockers": [
            "Current full-BPU segmented-HBM path is logits-invalid.",
            "No semantic BPU island passed all original semantic prompts under strict logits gates.",
            "The llada-style block driver cannot be truth-gated until the full 31-row reference truth set exists.",
            "No product or generation route may be touched before logits and fixed-task gates pass.",
        ],
        "allowed_claim": "Dream7B is in research/evidence mode; v21 provides semantic HF truth but no deployable BPU route.",
        "forbidden_claims": [
            "Dream7B is deployed as OpenClaw foreground model.",
            "Fixed block success implies general dialogue success.",
            "CPU/GGUF resident execution is a BPU deployment success.",
            "Partial semantic island passes are deployable.",
        ],
    }
    return data


def build_phase1(now: str) -> dict[str, Any]:
    return {
        "schema_version": "dream7b_s100p_lladacpp_phase1_translation_requirements",
        "created_at_utc": now,
        "source_review": {
            "primary_source": "Efficient On-Device Diffusion LLM Inference with Mobile NPU",
            "source_url": "https://arxiv.org/html/2606.13740v1",
            "code_status": "No project-specific llada.cpp code repository was added to this repo in this run; Phase 1 uses the paper-level design constraints and records code review as pending.",
        },
        "design_points": LLADACPP_POINTS,
        "directly_actionable_now": [
            "Create the isolated track directory and safety boundaries.",
            "Freeze the v21 baseline into Phase 0 reports.",
            "Define truth-case schema and operator manifest requirements.",
            "Keep generation, product routing, 18888/18889, and OpenClaw foreground untouched.",
        ],
        "requires_new_implementation": [
            "PyTorch block-wise diffusion driver with token state trace.",
            "BPU per-op and layer alignment harness.",
            "Static block graph compiler path for S100P.",
            "BPU visible memory staging runtime.",
        ],
        "hold_conditions": [
            "If full 31-row PyTorch truth is missing, hold at external_truth_missing_hold.",
            "If position, embedding, or lm_head op alignment fails, stop block runtime.",
            "If only fixed tasks pass, do not claim general dialogue deployment.",
        ],
    }


def build_phase2_gate(now: str) -> dict[str, Any]:
    return {
        "schema_version": "dream7b_s100p_lladacpp_phase2_truth_export_gate",
        "created_at_utc": now,
        "verdict": "external_truth_missing_hold",
        "required_truth_rows": 31,
        "available_truth_status": {
            "v21_original_semantic_rows": 8,
            "v21_total_island_eval_truth_rows": 11,
            "llada_style_truth_cases_jsonl_exists": False,
            "block_truth_rows": 0,
            "revision_truth_rows": 0,
            "fixed_output_truth_rows": 0,
            "prompt_infill_truth_rows": 0,
            "control_command_truth_rows": 0,
        },
        "reason": "v21 unblocks original semantic HF truth, but this track still lacks the full 31-row PyTorch reference truth set required before any BPU runtime claim.",
        "next_action": "Export reference/truth_cases.jsonl on an x86/GPU torch2 environment using semantic, canonical, block-wise, revision, fixed-output, infill, and control-command cases.",
        "safety": {
            "bpu_runtime_claim_allowed": False,
            "generation_allowed": False,
            "openclaw_product_route_allowed": False,
        },
    }


def build_configs() -> dict[str, dict[str, Any]]:
    return {
        "model_identity.json": {
            "model_family": "Dream7B",
            "track_scope": "S100P llada.cpp-style research only",
            "truth_dtype_policy": "HF/PyTorch BF16 or FP32 reference truth first",
            "product_route": "not_allowed",
            "current_product_route_elsewhere": "Qwen + OpenClaw AI-NAS harness",
        },
        "block_runtime_config.json": {
            "block_sizes_to_test": [16, 32, 64],
            "initial_batch": 1,
            "max_steps": "fixed_per_truth_case",
            "commit_policy": "confidence_based_after_truth",
            "draft_tokens": "disabled_until_phase3",
            "generation_route": "locked",
        },
        "quant_config.json": {
            "first_quant_target": "W8A16",
            "w4_attempt_allowed_after": "W8A16 logits gate pass",
            "activation_calibration_required": True,
            "sensitive_layers_policy": "keep higher precision until quantified",
            "lm_head_policy": "higher precision or CPU side until truth-proven",
        },
        "bpu_operator_manifest.json": {
            "status": "specification_only",
            "required_ops": [
                "embedding_lookup",
                "position_or_rotary_path",
                "rmsnorm_or_layernorm",
                "linear_matmul",
                "qkv_projection",
                "attention_score",
                "softmax_or_equivalent",
                "attention_value",
                "mlp_up_gate_down",
                "activation_function",
                "residual_add",
                "lm_head",
                "mask_update_or_confidence",
                "dequant_quant_path",
            ],
            "alignment_metrics": ["cosine_similarity", "max_abs_error", "relative_l2", "topk_if_logits_related"],
            "forbidden_alignment": "target_affine_or_per_case_fitting",
        },
        "memory_layout_config.json": {
            "status": "planned",
            "buffer_classes": [
                "input_tokens",
                "attention_or_diffusion_mask",
                "kv_revision_state",
                "token_state",
                "logits_or_confidence",
                "graph_io_binding",
                "double_buffered_staging",
            ],
            "inner_loop_allocation_target": 0,
            "trace_required": ["copy_time_ms", "remap_count", "staging_timeline", "buffer_overwrite_check"],
        },
    }


def build_readme(now: str) -> str:
    return f"""# Dream7B S100P llada.cpp-Style Research Track

Created: {now}

This directory is an isolated Dream7B research track. It does not modify the
current Qwen + OpenClaw AI-NAS product path, the OpenClaw foreground, or ports
18888/18889.

## Current Verdict

`external_truth_missing_hold`

v21 has useful HF/PyTorch BF16 semantic truth evidence, but this llada.cpp-style
track still lacks the complete 31-row `reference/truth_cases.jsonl` required for
block-wise, revision, fixed-output, infill, and control-command truth gates.

## Completed In This Track

- Phase 0 baseline lock: `reports/30000_baseline_lock.*`
- Phase 1 llada.cpp-to-S100P translation plan:
  `reports/30010_lladacpp_to_s100p_requirements.*`
- Phase 2 hold gate: `reports/30020_pytorch_truth_export_gate.*`
- Config skeletons for model identity, block runtime, quantization, BPU operator
  manifest, and memory layout.

## Safety Boundary

- No generation quality run.
- No OpenClaw foreground route.
- No default Qwen replacement.
- No 18888/18889 route modification.
- No BPU deployment claim until PyTorch truth, per-op/layer alignment, runtime,
  and fixed-task gates pass.

## Next Command

After exporting the required external truth rows, rerun:

```powershell
py -3 tools\\build_dream_s100p_lladacpp_track.py
py -3 -m unittest discover -s dream_s100p_lladacpp\\tests
```
"""


def build_phase0_md(data: dict[str, Any]) -> str:
    return f"""# Phase 0 Baseline Lock

Verdict: `{data["status"]}`

Current full-BPU path: `{data["latest_local_evidence"]["current_full_bpu_path"]}`

Semantic truth: {data["latest_local_evidence"]["semantic_truth_rows_status"]}

Seg00_01 status: {data["latest_local_evidence"]["seg00_01_status"]}

Generation quality: `{data["latest_local_evidence"]["generation_quality_status"]}`

Product route: `{data["latest_local_evidence"]["product_route_status"]}`

## Blockers

""" + "\n".join(f"- {item}" for item in data["exact_blockers"]) + """

## Claim Boundary

Allowed: Dream7B is in research/evidence mode; v21 provides semantic HF truth
but no deployable BPU route.

Forbidden: do not claim OpenClaw foreground deployment, general dialogue
deployment, BPU success from CPU/GGUF residency, or deployability from partial
semantic island passes.
"""


def build_phase1_md(data: dict[str, Any]) -> str:
    rows = []
    for point in data["design_points"]:
        rows.append(
            "| `{id}` | {design} | {mapping} | `{status}` |".format(
                id=point["id"],
                design=point["lladacpp_design_point"],
                mapping=point["s100p_equivalent_implementation"],
                status=point["implementation_status"],
            )
        )
    return """# llada.cpp To S100P Translation Plan

Primary source: [Efficient On-Device Diffusion LLM Inference with Mobile NPU](https://arxiv.org/html/2606.13740v1)

This is a correctness-first translation plan. It extracts design constraints
from llada.cpp and maps them to S100P, but does not copy any phone-NPU code into
this repo.

| ID | llada.cpp design point | S100P equivalent | Status |
| --- | --- | --- | --- |
""" + "\n".join(rows) + """

## Directly Actionable Now

""" + "\n".join(f"- {item}" for item in data["directly_actionable_now"]) + """

## Requires New Implementation

""" + "\n".join(f"- {item}" for item in data["requires_new_implementation"]) + """

## Hold Conditions

""" + "\n".join(f"- {item}" for item in data["hold_conditions"]) + "\n"


def build_phase2_md(data: dict[str, Any]) -> str:
    return f"""# Phase 2 PyTorch Truth Export Gate

Verdict: `{data["verdict"]}`

Required truth rows: `{data["required_truth_rows"]}`

Available status:

- v21 original semantic rows: `{data["available_truth_status"]["v21_original_semantic_rows"]}`
- v21 total island-eval truth rows: `{data["available_truth_status"]["v21_total_island_eval_truth_rows"]}`
- block truth rows: `{data["available_truth_status"]["block_truth_rows"]}`
- revision truth rows: `{data["available_truth_status"]["revision_truth_rows"]}`
- fixed-output truth rows: `{data["available_truth_status"]["fixed_output_truth_rows"]}`
- prompt/infill truth rows: `{data["available_truth_status"]["prompt_infill_truth_rows"]}`
- control-command truth rows: `{data["available_truth_status"]["control_command_truth_rows"]}`

Reason: {data["reason"]}

Next action: {data["next_action"]}
"""


def build_decision_doc(now: str) -> str:
    return f"""# Dream7B S100P llada.cpp-Style Decision

Updated: {now}

The next Dream7B route is not another full-BPU segmented-HBM compile and not an
OpenClaw product integration. The route is a correctness-first, llada.cpp-style
block runtime track:

1. Freeze the v21 negative/partial evidence.
2. Export a complete PyTorch reference truth set.
3. Implement a PyTorch block-wise diffusion driver.
4. Validate BPU operators and layers before static block graphs.
5. Add quantization, KV/revision/logits optimizations, and memory staging only
   after numeric truth gates pass.
6. Validate fixed block tasks before any broader generation claim.

Current decision: `external_truth_missing_hold`.

The available v21 semantic truth removes the old v20 blocker for 8 original
semantic prompts, but it does not satisfy the full 31-row truth contract for
this track. BPU runtime claims stay locked.

Product boundary: Qwen + OpenClaw remains the current AI-NAS product route.
Dream7B must stay out of OpenClaw foreground traffic until a future candidate
passes logits, block, fixed-task, and quality gates.
"""


def build_tests() -> str:
    return """import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TRACK = ROOT / "dream_s100p_lladacpp"


class LladaCppTrackArtifactsTest(unittest.TestCase):
    def load_json(self, rel):
        with (TRACK / rel).open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def test_phase0_claim_boundary(self):
        data = self.load_json("reports/30000_baseline_lock.json")
        self.assertEqual(data["status"], "phase0_baseline_locked")
        self.assertIn("logits-invalid", data["exact_blockers"][0])
        self.assertIn("OpenClaw foreground model", data["forbidden_claims"][0])

    def test_phase1_has_required_design_points(self):
        data = self.load_json("reports/30010_lladacpp_to_s100p_requirements.json")
        self.assertGreaterEqual(len(data["design_points"]), 8)
        for point in data["design_points"]:
            self.assertTrue(point["s100p_equivalent_implementation"])
            self.assertTrue(point["required_tests"])

    def test_phase2_holds_without_full_truth_set(self):
        data = self.load_json("reports/30020_pytorch_truth_export_gate.json")
        self.assertEqual(data["verdict"], "external_truth_missing_hold")
        self.assertFalse(data["safety"]["generation_allowed"])
        self.assertFalse(data["safety"]["openclaw_product_route_allowed"])


if __name__ == "__main__":
    unittest.main()
"""


def main() -> None:
    now = datetime.now(timezone.utc).isoformat()
    phase0 = build_phase0(now)
    phase1 = build_phase1(now)
    phase2 = build_phase2_gate(now)

    write_text(TRACK / "README.md", build_readme(now))
    for name, data in build_configs().items():
        write_json(TRACK / "configs" / name, data)

    write_json(TRACK / "reports" / "30000_baseline_lock.json", phase0)
    write_text(TRACK / "reports" / "30000_baseline_lock.md", build_phase0_md(phase0))

    write_json(TRACK / "reports" / "30010_lladacpp_to_s100p_requirements.json", phase1)
    write_text(TRACK / "reports" / "30010_lladacpp_to_s100p_requirements.md", build_phase1_md(phase1))

    write_json(TRACK / "reports" / "30020_pytorch_truth_export_gate.json", phase2)
    write_text(TRACK / "reports" / "30020_pytorch_truth_export_gate.md", build_phase2_md(phase2))

    write_text(ROOT / "docs" / "LLADACPP_TO_S100P_TRANSLATION_PLAN.md", build_phase1_md(phase1))
    write_text(ROOT / "docs" / "DREAM7B_S100P_LLADACPP_STYLE_DECISION.md", build_decision_doc(now))
    write_text(TRACK / "tests" / "test_phase0_phase1_artifacts.py", build_tests())

    reference_readme = """# Reference Truth

Do not place synthetic success rows here. `truth_cases.jsonl` must be exported
from an x86/GPU HF/PyTorch reference environment and must contain at least 31
rows before Phase 2 can pass.
"""
    write_text(TRACK / "reference" / "README.md", reference_readme)

    print(f"wrote {TRACK}")


if __name__ == "__main__":
    main()
