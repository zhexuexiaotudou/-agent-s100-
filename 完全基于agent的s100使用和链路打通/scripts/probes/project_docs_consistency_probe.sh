#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/tmp/project_docs_consistency}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

mkdir -p "$report_root"

required_files=(
  "README.md"
  "docs/project_reference.md"
  "docs/documentation_audit_runbook.md"
  "docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md"
  "scripts/dream7b-bpu-forward.sh"
  "scripts/dream7b-bpu-fine-forward.sh"
  "scripts/dream7b-bpu-fine-batch-forward.sh"
  "scripts/dream7b-bpu-batch-queue-runner.sh"
  "scripts/dream7b_bpu_batch_queue_runner.py"
  "scripts/dream7b-bpu-batch-queue-service.sh"
  "scripts/dream7b_bpu_batch_queue_service.py"
  "scripts/install_dream7b_bpu_queue_service.sh"
  "scripts/dream7b-bpu-text-forward.sh"
  "scripts/dream7b-bpu-text-queue-submit.sh"
  "scripts/dream7b-bpu-text-queue-run.sh"
  "scripts/dream7b-bpu-diffusion-generate.sh"
  "scripts/dream7b-bpu-diffusion-batch-generate.sh"
  "scripts/dream7b-bpu-selected-pair-batch-forward.sh"
  "scripts/dream7b_bpu_selected_pair_cross_job_queue_runner.py"
  "scripts/dream7b_bpu_selected_pair_cross_job_queue_service.py"
  "scripts/install_dream7b_bpu_selected_pair_cross_job_candidate_service.sh"
  "scripts/dream7b_bpu_segment_major_load_once_queue_runner.py"
  "scripts/install_dream7b_bpu_segment_major_load_once_candidate_service.sh"
  "scripts/dream7b-bpu-resplit-forward.sh"
  "scripts/dream7b-bpu-resplit-batch-forward.sh"
  "scripts/install_dream7b_bpu_selected_pair_candidate_service.sh"
  "scripts/probes/dream7b_segmented_hbm_python_forward.py"
  "scripts/probes/dream7b_bpu_diffusion_loop_probe.sh"
  "scripts/probes/dream7b_bpu_fine_forward_repeat_probe.sh"
  "scripts/probes/dream7b_bpu_fine_forward_long_repeat_probe.sh"
  "scripts/probes/dream7b_bpu_fine_forward_window_batch_probe.sh"
  "scripts/probes/dream7b_bpu_fine_batch_forward_probe.sh"
  "scripts/probes/dream7b_bpu_fine_batch_size_sweep_probe.sh"
  "scripts/probes/dream7b_bpu_batch_capacity_probe.sh"
  "scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh"
  "scripts/probes/dream7b_bpu_hbm_artifact_inventory_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_runner_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_drain_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_control_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_lock_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_service_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_systemd_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_systemd_soak_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_systemd_batch_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_systemd_canary_probe.sh"
  "scripts/probes/dream7b_bpu_text_queue_systemd_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh"
  "scripts/probes/dream7b_bpu_diffusion_generate_telemetry_probe.sh"
  "scripts/probes/dream7b_bpu_diffusion_batch_generate_telemetry_probe.sh"
  "scripts/probes/dream7b_bpu_diffusion_batch_generate_sustained_probe.sh"
  "scripts/probes/dream7b_bpu_utilization_gap_probe.sh"
  "scripts/probes/dream7b_bpu_persistent_pair_cache_probe.sh"
  "scripts/probes/dream7b_bpu_held_pair_residency_matrix_probe.sh"
  "scripts/probes/dream7b_bpu_single_segment_residency_matrix_probe.sh"
  "scripts/probes/dream7b_bpu_persistent_segment_cache_probe.sh"
  "scripts/probes/dream7b_bpu_single_segment_triplet_residency_probe.sh"
  "scripts/probes/dream7b_bpu_seeded_quad_residency_probe.sh"
  "scripts/probes/dream7b_bpu_segment_capacity_planner_probe.sh"
  "scripts/probes/dream7b_bpu_persistent_triplet_topology_probe.sh"
  "scripts/probes/dream7b_bpu_window3_forward_feasibility_probe.sh"
  "scripts/probes/dream7b_bpu_selected_triplet_forward_path_probe.sh"
  "scripts/probes/dream7b_bpu_selected_pair_forward_path_probe.sh"
  "scripts/probes/dream7b_bpu_selected_pair_telemetry_probe.sh"
  "scripts/probes/dream7b_bpu_selected_pair_promotion_gate_probe.sh"
  "scripts/probes/dream7b_bpu_selected_pair_candidate_forward_probe.sh"
  "scripts/probes/dream7b_bpu_selected_pair_candidate_service_probe.sh"
  "scripts/probes/dream7b_bpu_selected_pair_cross_job_queue_telemetry_probe.sh"
  "scripts/probes/dream7b_bpu_selected_pair_cross_job_service_fallback_probe.sh"
  "scripts/probes/dream7b_bpu_selected_pair_cross_job_service_promotion_gate_probe.sh"
  "scripts/probes/dream7b_bpu_cross_job_default_promotion_probe.sh"
  "scripts/probes/dream7b_bpu_cross_job_default_service_telemetry_probe.sh"
  "scripts/probes/compile_dream_segments_seq16_resplit_probe.sh"
  "scripts/probes/dream7b_bpu_resplit_hbm_artifact_inventory_probe.sh"
  "scripts/probes/dream7b_bpu_resplit_segment_residency_probe.sh"
  "scripts/probes/dream7b_bpu_resplit_forward_probe.sh"
  "scripts/probes/dream7b_bpu_resplit_batch_forward_probe.sh"
  "scripts/probes/dream7b_bpu_resplit_batch_telemetry_probe.sh"
  "scripts/probes/dream7b_bpu_resplit_window_cost_probe.sh"
  "scripts/probes/dream7b_bpu_reload_optimization_probe.sh"
  "scripts/probes/dream7b_bpu_phase1_reload_experiment_planner_probe.sh"
  "scripts/probes/dream7b_bpu_phase1_segment_plan_preflight_probe.sh"
  "scripts/probes/dream7b_bpu_cross_job_long_session_telemetry_probe.sh"
  "scripts/probes/dream7b_bpu_phase1_compile_recovery_package_probe.sh"
  "scripts/probes/dream7b_bpu_50pct_candidate_acceptance_probe.sh"
  "scripts/probes/dream7b_bpu_50pct_candidate_soak_probe.sh"
  "scripts/probes/dream7b_bpu_long_running_candidate_acceptance_probe.sh"
  "scripts/probes/dream7b_bpu_50pct_candidate_service_telemetry_probe.sh"
  "scripts/probes/dream7b_bpu_50pct_service_backlog_sweep_summary_probe.sh"
  "scripts/probes/dream7b_bpu_50pct_candidate_service_continuous_prefetch_probe.sh"
  "scripts/probes/dream7b_bpu_segment_major_load_once_forward_probe.sh"
  "scripts/probes/dream7b_bpu_segment_major_candidate_service_telemetry_probe.sh"
  "scripts/probes/dream7b_bpu_segment_major_candidate_soak_probe.sh"
  "scripts/probes/dream7b_90pct_candidate_evidence_package_probe.py"
  "scripts/probes/dream7b_openclaw_candidate_validation_probe.py"
  "scripts/probes/personal_data_sort_probe.sh"
  "scripts/probes/personal_data_sort_dry_run_probe.sh"
  "scripts/probes/s100_official_llm_baseline_probe.sh"
  "scripts/probes/s100_official_qwen_fullflow_probe.sh"
  "scripts/probes/s100_official_deepseek7b_baseline_probe.sh"
  "scripts/probes/s100_official_qwen_runtime_probe.sh"
  "scripts/probes/s100_bpu_memory_pool_probe.sh"
  "scripts/probes/s100_hbmem_common_buffer_matrix_probe.sh"
  "scripts/probes/s100_qwen_backend9_baseline_probe.sh"
  "scripts/probes/s100_qwen_bpu_core_sweep_probe.sh"
  "scripts/probes/dream7b_bpu_scheduling_params_probe.sh"
  "scripts/probes/s100_official_qwen_performance_mode_retest_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh"
  "scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh"
  "scripts/probes/dream7b_oellm_fullflow_feasibility_probe.sh"
  "scripts/probes/openclaw_entry_demo_probe.sh"
  "scripts/probes/ai_nas_movie_sort_demo_probe.sh"
  "scripts/startup_link_check/link-check.config.json"
  "scripts/tool_allowlist.json"
  "docs/teacher_demo_path_2026-06-09.md"
  "docs/dream7b_vendor_support_package_2026-06-10.md"
  "docs/dream7b_s100p_50pct_utilization_goal_2026-06-11.md"
  "docs/dream7b_s100p_long_running_candidate_2026-06-11.md"
  "docs/dream7b_s100p_90pct_utilization_route_2026-06-12.md"
  "docs/dream7b_s100p_90pct_vendor_question_2026-06-12.md"
  "docs/dream7b_s100p_90pct_default_candidate_handoff_2026-06-12.md"
  "docs/dream7b_openclaw_gateway_candidate_2026-06-11.md"
  "docs/personal_data_library_openclaw_policy.md"
  "docs/openclaw_entry_demo_runbook.md"
  "docs/ai_nas_movie_sort_demo_runbook.md"
)

required_readme_strings=(
  "docs/project_reference.md"
  "docs/documentation_audit_runbook.md"
  "scripts/probes/project_docs_consistency_probe.sh"
  "scripts/dream7b-bpu-text-queue-submit.sh"
  "scripts/dream7b-bpu-text-queue-run.sh"
  "scripts/dream7b-bpu-diffusion-generate.sh"
  "scripts/dream7b-bpu-diffusion-batch-generate.sh"
  "scripts/dream7b_bpu_selected_pair_cross_job_queue_runner.py"
  "scripts/probes/dream7b_bpu_diffusion_generate_telemetry_probe.sh"
  "scripts/probes/dream7b_bpu_diffusion_batch_generate_telemetry_probe.sh"
  "scripts/probes/dream7b_bpu_diffusion_batch_generate_sustained_probe.sh"
  "scripts/probes/dream7b_bpu_utilization_gap_probe.sh"
  "scripts/probes/dream7b_bpu_persistent_pair_cache_probe.sh"
  "scripts/probes/dream7b_bpu_held_pair_residency_matrix_probe.sh"
  "scripts/probes/dream7b_bpu_single_segment_residency_matrix_probe.sh"
  "scripts/probes/dream7b_bpu_persistent_segment_cache_probe.sh"
  "scripts/probes/dream7b_bpu_single_segment_triplet_residency_probe.sh"
  "scripts/probes/dream7b_bpu_seeded_quad_residency_probe.sh"
  "scripts/probes/dream7b_bpu_segment_capacity_planner_probe.sh"
  "scripts/probes/dream7b_bpu_persistent_triplet_topology_probe.sh"
  "scripts/probes/dream7b_bpu_window3_forward_feasibility_probe.sh"
  "scripts/probes/dream7b_bpu_selected_triplet_forward_path_probe.sh"
  "scripts/probes/dream7b_bpu_selected_pair_forward_path_probe.sh"
  "scripts/probes/dream7b_bpu_selected_pair_telemetry_probe.sh"
  "scripts/probes/dream7b_bpu_selected_pair_promotion_gate_probe.sh"
  "scripts/probes/dream7b_bpu_selected_pair_candidate_forward_probe.sh"
  "scripts/install_dream7b_bpu_selected_pair_candidate_service.sh"
  "scripts/probes/dream7b_bpu_selected_pair_candidate_service_probe.sh"
  "scripts/dream7b_bpu_selected_pair_cross_job_queue_service.py"
  "scripts/install_dream7b_bpu_selected_pair_cross_job_candidate_service.sh"
  "scripts/probes/dream7b_bpu_selected_pair_cross_job_queue_telemetry_probe.sh"
  "scripts/probes/dream7b_bpu_selected_pair_cross_job_service_fallback_probe.sh"
  "scripts/probes/dream7b_bpu_selected_pair_cross_job_service_promotion_gate_probe.sh"
  "scripts/probes/dream7b_bpu_cross_job_default_promotion_probe.sh"
  "scripts/probes/dream7b_bpu_cross_job_default_service_telemetry_probe.sh"
  "scripts/probes/compile_dream_segments_seq16_resplit_probe.sh"
  "scripts/probes/dream7b_bpu_resplit_hbm_artifact_inventory_probe.sh"
  "scripts/probes/dream7b_bpu_resplit_segment_residency_probe.sh"
  "scripts/dream7b-bpu-resplit-forward.sh"
  "scripts/probes/dream7b_bpu_resplit_forward_probe.sh"
  "scripts/dream7b-bpu-resplit-batch-forward.sh"
  "scripts/probes/dream7b_bpu_resplit_batch_forward_probe.sh"
  "scripts/probes/dream7b_bpu_resplit_batch_telemetry_probe.sh"
  "scripts/probes/dream7b_bpu_resplit_window_cost_probe.sh"
  "docs/dream7b_s100p_50pct_utilization_goal_2026-06-11.md"
  "scripts/probes/dream7b_bpu_phase1_reload_experiment_planner_probe.sh"
  "scripts/probes/dream7b_bpu_phase1_segment_plan_preflight_probe.sh"
  "scripts/probes/dream7b_bpu_cross_job_long_session_telemetry_probe.sh"
  "scripts/probes/dream7b_bpu_phase1_compile_recovery_package_probe.sh"
  "scripts/probes/dream7b_bpu_50pct_candidate_acceptance_probe.sh"
  "scripts/probes/dream7b_bpu_50pct_candidate_soak_probe.sh"
  "scripts/probes/dream7b_bpu_long_running_candidate_acceptance_probe.sh"
  "scripts/probes/dream7b_bpu_50pct_candidate_service_telemetry_probe.sh"
  "scripts/probes/dream7b_bpu_50pct_service_backlog_sweep_summary_probe.sh"
  "scripts/probes/dream7b_bpu_50pct_candidate_service_continuous_prefetch_probe.sh"
  "scripts/probes/dream7b_bpu_segment_major_load_once_forward_probe.sh"
  "scripts/install_dream7b_bpu_segment_major_load_once_candidate_service.sh"
  "scripts/probes/dream7b_bpu_segment_major_candidate_service_telemetry_probe.sh"
  "scripts/probes/dream7b_bpu_segment_major_candidate_soak_probe.sh"
  "scripts/probes/dream7b_90pct_candidate_evidence_package_probe.py"
  "scripts/probes/dream7b_openclaw_candidate_validation_probe.py"
  "scripts/probes/personal_data_sort_dry_run_probe.sh"
  "docs/dream7b_s100p_long_running_candidate_2026-06-11.md"
  "docs/dream7b_s100p_90pct_utilization_route_2026-06-12.md"
  "docs/dream7b_s100p_90pct_vendor_question_2026-06-12.md"
  "docs/dream7b_s100p_90pct_default_candidate_handoff_2026-06-12.md"
  "scripts/probes/s100_official_llm_baseline_probe.sh"
  "scripts/probes/s100_official_qwen_fullflow_probe.sh"
  "scripts/probes/s100_official_qwen_runtime_probe.sh"
  "scripts/probes/s100_bpu_memory_pool_probe.sh"
  "scripts/probes/s100_hbmem_common_buffer_matrix_probe.sh"
  "scripts/probes/s100_qwen_backend9_baseline_probe.sh"
  "scripts/probes/s100_qwen_bpu_core_sweep_probe.sh"
  "scripts/probes/dream7b_bpu_scheduling_params_probe.sh"
  "scripts/probes/dream7b_oellm_fullflow_feasibility_probe.sh"
  "scripts/probes/s100_official_qwen_performance_mode_retest_probe.sh"
  "dream7b_bpu_text_queue_systemd_probe.sh"
  "docs/teacher_demo_path_2026-06-09.md"
  "docs/openclaw_entry_demo_runbook.md"
  "docs/ai_nas_movie_sort_demo_runbook.md"
  "openclaw_entry_demo_probe"
  "ai_nas_movie_sort_demo_probe"
  "/mnt/nas/openclaw/reports/teacher-demos/openclaw-entry"
  "/mnt/nas/openclaw/reports/teacher-demos/ai-nas-movie-sort"
  "/mnt/nas/openclaw/demo/ai-nas-movie-sort"
)

required_reference_strings=(
  "dream7b-bpu-forward"
  "dream7b-bpu-fine-forward"
  "dream7b-bpu-fine-batch-forward"
  "dream7b-bpu-batch-queue-runner"
  "dream7b-bpu-batch-queue-service"
  "dream7b-bpu-fine-batch-size-sweep-probe"
  "dream7b-bpu-fine-forward-long-repeat-probe"
  "dream7b-bpu-batch-capacity-probe"
  "dream7b-bpu-runtime-telemetry-probe"
  "dream7b-bpu-hbm-artifact-inventory-probe"
  "install-dream7b-bpu-queue-service"
  "dream7b-bpu-batch-queue-systemd-probe"
  "dream7b-bpu-batch-queue-systemd-soak-probe"
  "dream7b-bpu-batch-queue-systemd-batch-probe"
  "dream7b-bpu-batch-queue-systemd-drain-probe"
  "dream7b-bpu-batch-queue-systemd-canary-probe"
  "dream7b-bpu-text-queue-submit"
  "dream7b-bpu-text-queue-run"
  "dream7b-bpu-diffusion-generate"
  "dream7b-bpu-diffusion-batch-generate"
  "dream7b-bpu-text-queue-systemd-probe"
  "dream7b-bpu-batch-queue-systemd-telemetry-probe"
  "dream7b-bpu-diffusion-generate-telemetry-probe"
  "dream7b-bpu-diffusion-batch-generate-telemetry-probe"
  "dream7b-bpu-diffusion-batch-generate-sustained-probe"
  "dream7b-bpu-utilization-gap-probe"
  "dream7b-bpu-persistent-pair-cache-probe"
  "dream7b-bpu-held-pair-residency-matrix-probe"
  "dream7b-bpu-single-segment-residency-matrix-probe"
  "dream7b-bpu-persistent-segment-cache-probe"
  "dream7b-bpu-single-segment-triplet-residency-probe"
  "dream7b-bpu-seeded-quad-residency-probe"
  "dream7b-bpu-segment-capacity-planner-probe"
  "dream7b-bpu-persistent-triplet-topology-probe"
  "dream7b-bpu-window3-forward-feasibility-probe"
  "dream7b-bpu-selected-triplet-forward-path-probe"
  "dream7b-bpu-selected-pair-forward-path-probe"
  "dream7b-bpu-selected-pair-telemetry-probe"
  "dream7b-bpu-selected-pair-promotion-gate-probe"
  "dream7b-bpu-selected-pair-batch-forward"
  "dream7b-bpu-selected-pair-candidate-forward-probe"
  "install-dream7b-bpu-selected-pair-candidate-service"
  "dream7b-bpu-selected-pair-candidate-service-probe"
  "dream7b-bpu-resplit-forward"
  "dream7b-bpu-resplit-segment-residency-probe"
  "dream7b-bpu-resplit-forward-probe"
  "dream7b-bpu-resplit-batch-forward"
  "dream7b-bpu-resplit-batch-forward-probe"
  "dream7b-bpu-resplit-batch-telemetry-probe"
  "dream7b-bpu-resplit-window-cost-probe"
  "dream7b_s100p_50pct_utilization_goal_2026-06-11.md"
  "dream7b_bpu_phase1_reload_experiment_planner_probe.sh"
  "dream7b_bpu_phase1_segment_plan_preflight_probe.sh"
  "dream7b_bpu_cross_job_long_session_telemetry_probe.sh"
  "dream7b_bpu_phase1_compile_recovery_package_probe.sh"
  "dream7b_bpu_phase1_compile_recovery_package_20260611-164453"
  "dream7b_bpu_50pct_candidate_soak_probe.sh"
  "dream7b_bpu_long_running_candidate_acceptance_probe.sh"
  "dream7b_bpu_50pct_candidate_service_telemetry_probe.sh"
  "dream7b_bpu_50pct_service_backlog_sweep_summary_probe.sh"
  "dream7b_bpu_50pct_candidate_service_continuous_prefetch_probe.sh"
  "dream7b_bpu_segment_major_load_once_forward_probe.sh"
  "dream7b-bpu-segment-major-load-once-candidate.service"
  "dream7b_bpu_segment_major_candidate_service_telemetry_probe.sh"
  "dream7b_bpu_segment_major_candidate_service_telemetry_20260612-130705"
  "segment_major_service_near_90pct_candidate"
  "avg_bpu_loading: 86.792"
  "load_to_run_ratio: 0.068115"
  "dream7b_bpu_segment_major_candidate_soak_probe.sh"
  "dream7b_bpu_segment_major_candidate_soak_20260612-131931"
  "segment_major_service_soak_near_90pct_candidate"
  "avg_bpu_loading: 86.701"
  "avg_load_to_run_ratio: 0.068132"
  "dream7b_bpu_segment_major_candidate_soak_20260612-133613"
  "avg_bpu_loading: 86.643"
  "avg_load_to_run_ratio: 0.068719"
  "processed_request_count: 11520"
  "dream7b-bpu-segment-major-load-once-candidate-24job.service"
  "dream7b_bpu_segment_major_load_once_forward_20260612-141202"
  "avg_bpu_loading: 88.312"
  "load_to_run_ratio: 0.05209"
  "dream7b_bpu_segment_major_load_once_forward_20260612-142048"
  "avg_bpu_loading: 89.738"
  "load_to_run_ratio: 0.034833"
  "dream7b_bpu_segment_major_candidate_service_telemetry_20260612-143609"
  "avg_bpu_loading: 89.535"
  "load_to_run_ratio: 0.03538"
  "dream7b_bpu_segment_major_candidate_soak_20260612-144904"
  "avg_bpu_loading: 89.471"
  "avg_load_to_run_ratio: 0.034434"
  "dream7b-bpu-segment-major-load-once-candidate-24job-b256.service"
  "dream7b_bpu_segment_major_candidate_service_telemetry_20260612-155626"
  "avg_bpu_loading: 89.9"
  "load_to_run_ratio: 0.029034"
  "dream7b_bpu_segment_major_candidate_service_telemetry_20260612-161133"
  "segment_major_service_meets_90pct_goal"
  "avg_bpu_loading: 90.275"
  "load_to_run_ratio: 0.02602"
  "dream7b_bpu_segment_major_candidate_soak_20260612-162823"
  "segment_major_service_soak_meets_90pct_goal"
  "avg_bpu_loading: 90.327"
  "avg_load_to_run_ratio: 0.025995"
  "personal_data_sort_dry_run_probe"
  "dream7b_s100p_long_running_candidate_2026-06-11.md"
  "dream7b_s100p_90pct_utilization_route_2026-06-12.md"
  "dream7b_s100p_90pct_vendor_question_2026-06-12.md"
  "phase1_compile_recovery_runbook.sh"
  "dream7b_resplit_compile_20260611-104601"
  "hbm_success_count: 4"
  "failed_spec_count: 0"
  "dream7b_bpu_phase1_segment_plan_preflight_20260611-190121"
  "phase1_ready_to_run: True"
  "dream7b_bpu_resplit_batch_telemetry_20260611-190500"
  "segment_plan: phase1-topload-adjacent"
  "segment_event_count: 320"
  "avg_bpu_loading: 6.706"
  "load_to_run_ratio: 12.012308"
  "amortized_wall_ms_per_forward: 2024.617"
  "dream7b_bpu_resplit_window_cost_20260611-190552"
  "dream7b_bpu_utilization_gap_20260611-190552"
  "dream7b_bpu_50pct_candidate_acceptance_probe.sh"
  "dream7b_bpu_selected_pair_cross_job_queue_telemetry_20260611-192528"
  "dream7b_bpu_50pct_candidate_acceptance_20260611-193007"
  "processed_request_count: 384"
  "failed_job_count: 0"
  "avg_bpu_loading: 52.328"
  "load_to_run_ratio: 0.778725"
  "amortized_wall_ms_per_processed_request: 262.083"
  "rollback_status: rollback_safe_candidate_only"
  "default_service_replaced: False"
  "phase1-topload-adjacent"
  "avg_bpu_loading: 9.695"
  "avg_bpu_loading: 9.764"
  "avg_bpu_loading: 9.775"
  "load_to_run_ratio: 8.711317"
  "dream7b-bpu-selected-pair-candidate.service"
  "dream7b_bpu_selected_pair_candidate_service_telemetry"
  "comparison_to_default_systemd_telemetry"
  "candidate_wall_time_improved_vs_default_systemd"
  "s100-official-llm-baseline-probe"
  "s100-official-qwen-fullflow-probe"
  "s100-qwen-backend9-baseline-probe"
  "s100-qwen-bpu-core-sweep-probe"
  "dream7b-bpu-scheduling-params-probe"
  "dream7b-oellm-fullflow-feasibility-probe"
  "dream7b-bpu-batch-queue-retention-probe"
  "dream7b-bpu-deployment-acceptance-probe"
  "openclaw_entry_demo_probe"
  "ai_nas_movie_sort_demo_probe"
  "openclaw_entry_demo.md"
  "openclaw_entry_demo.json"
  "movie_sort_demo.md"
  "movie_sort_demo.json"
  "classification_engine"
  "deterministic_filename_metadata_rules"
  "/mnt/nas/openclaw/reports/teacher-demos/openclaw-entry"
  "/mnt/nas/openclaw/reports/teacher-demos/ai-nas-movie-sort"
  "/mnt/nas/openclaw/demo/ai-nas-movie-sort"
  "dream7b-bpu-batch-queue.service"
  "dream7b-bpu-text-forward"
  "dream7b-bpu-diffusion-loop-probe"
  "DREAM7B_BPU_FINE_CHILD_RUNTIME_MODE"
  "DREAM7B_BPU_FINE_WINDOW_EXECUTION_MODE"
  "DREAM7B_BPU_FINE_BATCH_WINDOW_EXECUTION_MODE"
  "DREAM7B_BPU_FINE_BATCH_SWEEP_COUNTS"
  "DREAM7B_BPU_FINE_BATCH_SWEEP_TIMEOUT_SEC"
  "DREAM7B_BPU_FINE_BATCH_SWEEP_TOP_K"
  "DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_COUNT"
  "DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_MAX_WALL_SPREAD_RATIO"
  "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_SERVICE_NAME"
  "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_MAX_BATCH_SIZE"
  "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_FORWARD_CMD"
  "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_SERVICE_REQUEST_COUNT"
  "DREAM7B_BPU_BATCH_CAPACITY_COUNTS"
  "DREAM7B_BPU_BATCH_CAPACITY_TIMEOUT_SEC"
  "DREAM7B_BPU_BATCH_CAPACITY_TOP_K"
  "DREAM7B_BPU_TELEMETRY_BATCH_COUNT"
  "DREAM7B_BPU_TELEMETRY_MONITOR_DELAY_MS"
  "DREAM7B_BPU_TELEMETRY_MONITOR_SAMPLE_COUNT"
  "DREAM7B_BPU_TELEMETRY_TOP_K"
  "DREAM7B_BPU_TELEMETRY_TIMEOUT_SEC"
  "DREAM7B_BPU_ARTIFACT_INVENTORY_FORWARD_SCRIPT"
  "DREAM7B_BPU_ARTIFACT_INVENTORY_NAS_HBM_DIR"
  "DREAM7B_BPU_ARTIFACT_INVENTORY_NAS_FINE_HBM_DIR"
  "DREAM7B_BPU_ARTIFACT_INVENTORY_LOCAL_HBM_DIR"
  "DREAM7B_BPU_ARTIFACT_INVENTORY_LOCAL_FINE_HBM_DIR"
  "DREAM7B_BPU_ARTIFACT_INVENTORY_VERIFY_MANIFEST"
  "DREAM7B_BPU_BATCH_QUEUE_RUNNER_SCRIPT"
  "DREAM7B_BPU_BATCH_QUEUE_SERVICE_SCRIPT"
  "DREAM7B_BPU_QUEUE_MAX_BATCH_SIZE"
  "DREAM7B_BPU_QUEUE_DRAIN_ALL"
  "DREAM7B_BPU_SYSTEMD_BATCH_REQUEST_COUNT"
  "DREAM7B_BPU_SYSTEMD_DRAIN_REQUEST_COUNT"
  "DREAM7B_BPU_SYSTEMD_DRAIN_TIMEOUT_SEC"
  "DREAM7B_BPU_SYSTEMD_DRAIN_POLL_INTERVAL_SEC"
  "DREAM7B_BPU_SYSTEMD_CANARY_REQUEST_COUNT"
  "DREAM7B_BPU_SYSTEMD_CANARY_TIMEOUT_SEC"
  "DREAM7B_BPU_SYSTEMD_CANARY_POLL_INTERVAL_SEC"
  "DREAM7B_BPU_TEXT_QUEUE_PROMPT"
  "DREAM7B_BPU_TEXT_QUEUE_FIT"
  "DREAM7B_BPU_TEXT_QUEUE_SEQ_LEN"
  "DREAM7B_BPU_TEXT_QUEUE_TIMEOUT_SEC"
  "DREAM7B_BPU_TEXT_QUEUE_POLL_INTERVAL_SEC"
  "DREAM7B_BPU_TEXT_QUEUE_DIR"
  "DREAM7B_BPU_TEXT_QUEUE_SUBMIT_REPORT_ROOT"
  "DREAM7B_BPU_TEXT_QUEUE_SUBMIT_RUN_DIR"
  "DREAM7B_BPU_TEXT_QUEUE_SUBMIT_CMD"
  "DREAM7B_BPU_TEXT_QUEUE_OUTPUT_DIR"
  "DREAM7B_BPU_TEXT_QUEUE_RUN_REPORT_ROOT"
  "DREAM7B_BPU_TEXT_QUEUE_RUN_DIR"
  "DREAM7B_BPU_TEXT_QUEUE_RUN_CMD"
  "DREAM7B_BPU_SYSTEMD_TELEMETRY_JOB_COUNT"
  "DREAM7B_BPU_SYSTEMD_TELEMETRY_REQUEST_COUNT"
  "DREAM7B_BPU_SYSTEMD_TELEMETRY_TIMEOUT_SEC"
  "DREAM7B_BPU_SYSTEMD_TELEMETRY_POLL_INTERVAL_SEC"
  "DREAM7B_BPU_SYSTEMD_TELEMETRY_MONITOR_DELAY_MS"
  "DREAM7B_BPU_SYSTEMD_TELEMETRY_MONITOR_SAMPLE_COUNT"
  "DREAM7B_BPU_DIFFUSION_GENERATE_TELEMETRY_PROMPT"
  "DREAM7B_BPU_DIFFUSION_GENERATE_TELEMETRY_CMD"
  "DREAM7B_BPU_DIFFUSION_GENERATE_TELEMETRY_MONITOR_DELAY_MS"
  "DREAM7B_BPU_DIFFUSION_GENERATE_TELEMETRY_MONITOR_SAMPLE_COUNT"
  "DREAM7B_BPU_DIFFUSION_GENERATE_TELEMETRY_TIMEOUT_SEC"
  "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_REPORT_ROOT"
  "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_RUN_DIR"
  "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_BATCH_COUNT"
  "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SEQ_LEN"
  "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_MIN_MASK_COUNT"
  "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_STEPS"
  "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TOP_K"
  "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_EPS"
  "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_REMASKING"
  "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TEMP"
  "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SEED"
  "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_ENTROPY_THRESHOLD"
  "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_FORWARD_CMD"
  "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TELEMETRY_BATCH_COUNT"
  "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TELEMETRY_CMD"
  "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TELEMETRY_MONITOR_DELAY_MS"
  "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TELEMETRY_MONITOR_SAMPLE_COUNT"
  "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TELEMETRY_TIMEOUT_SEC"
  "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_ROUND_COUNT"
  "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_BATCH_COUNT"
  "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_CMD"
  "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_MONITOR_DELAY_MS"
  "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_MONITOR_SAMPLE_COUNT"
  "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_TIMEOUT_SEC"
  "DREAM7B_BPU_UTILIZATION_GAP_MIN_BATCH_COUNT"
  "DREAM7B_BPU_UTILIZATION_GAP_MIN_SUSTAINED_ROUND_COUNT"
  "DREAM7B_BPU_UTILIZATION_GAP_MIN_SUSTAINED_TOTAL_ITEMS"
  "DREAM7B_BPU_PERSISTENT_PAIR_CACHE_WORKER_HOLD_SECONDS"
  "DREAM7B_BPU_PERSISTENT_PAIR_CACHE_READY_TIMEOUT_SECONDS"
  "DREAM7B_BPU_PERSISTENT_PAIR_CACHE_START_DELAY_SECONDS"
  "DREAM7B_BPU_HELD_PAIR_MATRIX_HOLDER_READY_TIMEOUT_SECONDS"
  "DREAM7B_BPU_HELD_PAIR_MATRIX_CANDIDATE_TIMEOUT_SECONDS"
  "DREAM7B_BPU_SINGLE_SEGMENT_MATRIX_HOLDER_READY_TIMEOUT_SECONDS"
  "DREAM7B_BPU_SINGLE_SEGMENT_MATRIX_CANDIDATE_TIMEOUT_SECONDS"
  "DREAM7B_BPU_PERSISTENT_SEGMENT_CACHE_WORKER_HOLD_SECONDS"
  "DREAM7B_BPU_PERSISTENT_SEGMENT_CACHE_READY_TIMEOUT_SECONDS"
  "DREAM7B_BPU_PERSISTENT_SEGMENT_CACHE_START_DELAY_SECONDS"
  "DREAM7B_BPU_SINGLE_SEGMENT_TRIPLET_READY_TIMEOUT_SECONDS"
  "DREAM7B_BPU_SINGLE_SEGMENT_TRIPLET_START_DELAY_SECONDS"
  "DREAM7B_BPU_SINGLE_SEGMENT_TRIPLET_MAX_COMBINATIONS"
  "DREAM7B_BPU_SEEDED_QUAD_TRIPLET_JSON"
  "DREAM7B_BPU_SEEDED_QUAD_READY_TIMEOUT_SECONDS"
  "DREAM7B_BPU_SEEDED_QUAD_START_DELAY_SECONDS"
  "DREAM7B_BPU_SEEDED_QUAD_MAX_COMBINATIONS"
  "DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_TRIPLET_JSON"
  "DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_HOLD_SECONDS"
  "DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_READY_TIMEOUT_SECONDS"
  "DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_POLL_INTERVAL_SECONDS"
  "DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_START_DELAY_SECONDS"
  "DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_MAX_TRIPLETS"
  "DREAM7B_BPU_WINDOW3_FORWARD_CMD"
  "DREAM7B_BPU_WINDOW3_FORWARD_TIMEOUT_SEC"
  "DREAM7B_BPU_WINDOW3_FORWARD_TOP_K"
  "DREAM7B_BPU_SELECTED_TRIPLET_TOPOLOGY_JSON"
  "DREAM7B_BPU_SELECTED_TRIPLET_BASELINE_FORWARD_CMD"
  "DREAM7B_BPU_SELECTED_TRIPLET_BATCH_COUNT"
  "DREAM7B_BPU_SELECTED_TRIPLET_TOP_K"
  "DREAM7B_BPU_SELECTED_TRIPLET_TIMEOUT_SEC"
  "DREAM7B_BPU_SELECTED_TRIPLET_ALLOW_CRASH_RETRY"
  "DREAM7B_BPU_SELECTED_PAIR_PROMOTION_MIN_BATCH_COUNT"
  "DREAM7B_BPU_SELECTED_PAIR_PROMOTION_MIN_WALL_DELTA_RATIO"
  "DREAM7B_BPU_SELECTED_PAIR_PROMOTION_MIN_AVG_BPU_DELTA"
  "DREAM7B_BPU_SELECTED_PAIR_TOKENS_BATCH_JSON"
  "DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_TOKENS_BATCH_JSON"
  "DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_OUTPUT_DIR"
  "DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_TOP_K"
  "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_FORWARD_CMD"
  "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_BATCH_COUNT"
  "DREAM7B_BPU_RESPLIT_HBM_DIR"
  "DREAM7B_BPU_RESPLIT_WINDOW_SIZE"
  "DREAM7B_BPU_RESPLIT_CHILD_WINDOW_MODE"
  "DREAM7B_BPU_RESPLIT_CHILD_RUNTIME_MODE"
  "DREAM7B_BPU_RESPLIT_WINDOW_EXECUTION_MODE"
  "DREAM7B_BPU_RESPLIT_FORWARD_EXPECTED_RESPLIT_HBM_DIR"
  "DREAM7B_BPU_RESPLIT_BATCH_WINDOW_EXECUTION_MODE"
  "DREAM7B_BPU_RESPLIT_BATCH_FORWARD_COUNT"
  "DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_COUNT"
  "DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_MONITOR_DELAY_MS"
  "DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_MONITOR_SAMPLE_COUNT"
  "DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_TOP_K"
  "DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_TIMEOUT_SEC"
  "DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_FORWARD_CMD"
  "DREAM7B_BPU_RESPLIT_WINDOW_COST_MODEL_REPORT_ROOT"
  "DREAM7B_BPU_RESPLIT_WINDOW_COST_MIN_BATCH_COUNT"
  "DREAM7B_BPU_RESPLIT_WINDOW_COST_EXPECTED_WINDOW_COUNT"
  "DREAM7B_BPU_RESPLIT_WINDOW_COST_EXPECTED_SEGMENT_EVENT_COUNT"
  "S100_OFFICIAL_LLM_SDK_ROOT"
  "S100_OFFICIAL_LLM_DREAM_REPORT_ROOT"
  "S100_OFFICIAL_LLM_DOC_URL"
  "DREAM7B_BPU_QUEUE_RETENTION_DONE_DAYS"
  "DREAM7B_BPU_QUEUE_RETENTION_FAILED_DAYS"
  "DREAM7B_BPU_QUEUE_RETENTION_PENDING_STALE_MINUTES"
  "DREAM7B_BPU_QUEUE_RETENTION_PROCESSING_STALE_MINUTES"
  "DREAM7B_BPU_QUEUE_RETENTION_MAX_LIST"
  "DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_CAPACITY"
  "DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_BATCH_REQUESTS"
  "DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_TELEMETRY_REQUESTS"
  "DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_GENERATE_COUNT"
  "DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_GENERATE_SUSTAINED_ROUND_COUNT"
  "DREAM7B_BPU_ACCEPTANCE_MIN_LONG_REPEAT_COUNT"
  "DREAM7B_BPU_ACCEPTANCE_MAX_LONG_REPEAT_WALL_SPREAD_RATIO"
  "--child-runtime-mode"
  "--window-execution-mode"
  "--tokens-batch-json"
  "--max-batch-size 16"
  "--drain-all"
  "--bpu-lock-path"
  "--bpu-lock-timeout-sec"
  "request_id"
  "tokens"
  "cancelled"
  "not_after_epoch_ms"
  "durable_state"
  "bpu_lock"
  "drain_all"
  "batch_run_count"
  "batch_counts"
  "amortized_wall_ms_per_forward"
  "amortized_load_ms_per_forward"
  "amortized_run_ms_per_forward"
  "load_share"
  "hrt_ucp_monitor"
  "bpu_loading_sample_count"
  "nonzero_bpu_loading_sample_count"
  "max_bpu_loading"
  "avg_bpu_loading"
  "selected_pair_telemetry_probe"
  "ok_dream7b_bpu_selected_pair_telemetry_probe"
  "selected_pair_promotion_gate_probe"
  "ok_dream7b_bpu_selected_pair_promotion_gate_probe"
  "selected_pair_candidate_forward_probe"
  "ok_dream7b_bpu_selected_pair_candidate_forward_probe"
  "selected_pair_candidate"
  "selected-pair-resident"
  "promotion_ready_for_guarded_default_service_candidate"
  "default_service_already_promoted"
  "selected_pair_telemetry"
  "comparison_to_default_runtime_telemetry"
  "wall_ms_delta_ratio_vs_default_runtime"
  "selected_wall_time_improved_vs_default_runtime"
  "selected_avg_bpu_loading_improved_vs_default_runtime"
  "utilization_gap_probe"
  "ok_dream7b_bpu_utilization_gap_probe"
  "diagnosis"
  "next_optimization_target"
  "load_to_run_ratio"
  "max_observed_bpu_loading"
  "avg_observed_bpu_loading_across_reports"
  "batch_scaling_reference"
  "persistent_pair_cache_probe"
  "ok_dream7b_bpu_persistent_pair_cache_probe"
  "pair_worker_count"
  "launched_pair_worker_count"
  "ready_pair_worker_count"
  "failed_pair_worker_count"
  "all_pair_workers_ready"
  "launch_stopped_reason"
  "held_pair_residency_matrix_probe"
  "ok_dream7b_bpu_held_pair_residency_matrix_probe"
  "ready_holder_pair_count"
  "ready_holder_pair_indexes"
  "matrix_entry_count"
  "successful_pair_edge_count"
  "failed_pair_edge_count"
  "successful_pair_edges"
  "failed_pair_edges"
  "max_resident_pair_count_observed"
  "single_segment_residency_matrix_probe"
  "ok_dream7b_bpu_single_segment_residency_matrix_probe"
  "ready_holder_segment_count"
  "ready_holder_segment_indexes"
  "successful_segment_edge_count"
  "failed_segment_edge_count"
  "successful_segment_edges"
  "failed_segment_edges"
  "max_resident_segment_count_observed"
  "persistent_segment_cache_probe"
  "ok_dream7b_bpu_persistent_segment_cache_probe"
  "segment_worker_count"
  "launched_segment_worker_count"
  "ready_segment_worker_count"
  "failed_segment_worker_count"
  "all_segment_workers_ready"
  "single_segment_triplet_residency_probe"
  "ok_dream7b_bpu_single_segment_triplet_residency_probe"
  "total_triplet_combination_count"
  "tested_triplet_combination_count"
  "successful_triplet_count"
  "failed_triplet_count"
  "successful_triplets"
  "failed_triplets"
  "seeded_quad_residency_probe"
  "ok_dream7b_bpu_seeded_quad_residency_probe"
  "source_successful_triplet_count"
  "seeded_quad_candidate_count"
  "tested_seeded_quad_count"
  "successful_seeded_quad_count"
  "failed_seeded_quad_count"
  "successful_seeded_quads"
  "failed_seeded_quads"
  "persistent_triplet_topology_probe"
  "ok_dream7b_bpu_persistent_triplet_topology_probe"
  "tested_triplet_topology_count"
  "stable_triplet_topology_count"
  "failed_triplet_topology_count"
  "stable_triplets"
  "selected_topology"
  "selection_rule"
  "window3_forward_feasibility_probe"
  "ok_dream7b_bpu_window3_forward_feasibility_probe"
  "direct_window3_forward_supported"
  "expected_window3_failure_observed"
  "stderr_contains_memory_alloc_failure"
  "selected_triplet_forward_path_probe"
  "ok_dream7b_bpu_selected_triplet_forward_path_probe"
  "selected_triplet_forward_supported"
  "reboot_or_disconnect_observed"
  "expected_reboot_guard_observed"
  "source_incomplete_run_dir"
  "official_llm_baseline_probe"
  "ok_s100_official_llm_baseline_probe"
  "official_qwen_runtime_probe"
  "ok_s100_official_qwen_runtime_probe"
  "bpu_memory_pool_probe"
  "ok_s100_bpu_memory_pool_probe"
  "hbmem_common_buffer_matrix_probe"
  "ok_s100_hbmem_common_buffer_matrix_probe"
  "performance_mode_retest_probe"
  "ok_s100_official_qwen_performance_mode_retest_probe"
  "supported_model_names_from_resolve_model"
  "qwen_existing_hbm_count"
  "official_qwen_memory_alloc_failure_observed"
  "latest_performance_mode_retest_memory_alloc_failure_observed"
  "ion_all_heap_info_exists"
  "ion_heap_total_sizes"
  "ion_heap_allocated_totals"
  "ion_heap_bpu_allocation_sizes"
  "system_heap_total_size"
  "system_contig_heap_total_size"
  "cma_reserved_heap_total_size"
  "ion_cma_heap_total_size"
  "carveout_heap_total_size"
  "reserved_memory_summary"
  "allocation_failure_interpretation"
  "minimal HBMEM/UCP common-buffer allocation matrix"
  "qwen_log_size_success_count"
  "qwen_log_size_failure_count"
  "ucp_success_count"
  "backend: 9"
  "ion_meminfo_shebang_interpreter_exists"
  "memstat_shebang_interpreter_exists"
  "similar_issue_evidence_available_for_official_qwen"
  "comparison_to_dream"
  "hbm_artifact_inventory"
  "expected_artifact_count"
  "expected_base_count"
  "expected_fine_count"
  "nas_existing_count"
  "local_existing_count"
  "size_match_count"
  "manifest_expected_count"
  "manifest_verified_count"
  "required_manifest_expected_count"
  "policy_mode"
  "apply_supported"
  "archive_plan"
  "pending_stale_count"
  "processing_stale_count"
  "done_archive_candidate_count"
  "failed_archive_candidate_count"
  "deployment_acceptance_probe"
  "resplit_batch_telemetry_probe"
  "ok_dream7b_bpu_resplit_batch_telemetry_probe"
  "resplit_batch_telemetry"
  "resplit_window_cost_probe"
  "ok_dream7b_bpu_resplit_window_cost_probe"
  "resplit_window_cost"
  "passed_check_count"
  "systemd_service"
  "batch_capacity"
  "systemd_batch"
  "systemd_drain"
  "systemd_canary"
  "text_queue_run"
  "text_queue_systemd"
  "diffusion_generate"
  "diffusion_generate_telemetry"
  "diffusion_batch_generate_telemetry"
  "diffusion_batch_generate_sustained"
  "ok_dream7b_bpu_diffusion_generate"
  "ok_dream7b_bpu_diffusion_generate_telemetry_probe"
  "ok_dream7b_bpu_diffusion_batch_generate"
  "ok_dream7b_bpu_diffusion_batch_generate_telemetry_probe"
  "ok_dream7b_bpu_diffusion_batch_generate_sustained_probe"
  "batch_generation_sustained_probe.json"
  "batch_generation_sustained_probe.md"
  "generation_telemetry_probe.json"
  "generation_telemetry_probe.md"
  "batch_generation.json"
  "batch_generation.md"
  "batch_generation_telemetry_probe.json"
  "batch_generation_telemetry_probe.md"
  "generation.json"
  "generation.md"
  "decoded_final"
  "remaining_mask_positions"
  "remaining_mask_positions_by_batch"
  "decoded_final_by_batch"
  "forward_batch_counts"
  "bounded_seq16_generation_entrypoint_not_complete_production_text_service"
  "bounded_seq16_batch_generation_entrypoint_not_complete_production_text_service"
  "ok_dream7b_bpu_text_queue_submit"
  "submit_cmd"
  "submit_verdict"
  "text_queue_submit.json"
  "text_queue_submit.md"
  "text_queue_run.json"
  "text_queue_run.md"
  "ok_dream7b_bpu_text_queue_run"
  "run_cmd"
  "run_verdict"
  "systemd_telemetry"
  "long_repeat"
  "queue_retention"
  "/run/lock/dream7b_bpu_batch_queue_runner.lock"
  "pending"
  "processing"
  "done"
  "failed"
  "accepted_requests.jsonl"
  "deferred_requests.jsonl"
  "skipped_requests.jsonl"
  "results.jsonl"
  "scripts/startup_link_check/link-check.config.json"
  "scripts/tool_allowlist.json"
  "docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_20260603-174608/fine_forward_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_perf_20260603-174745/summary.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_repeat_20260603-180108/summary.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_long_repeat_20260605-163343/long_repeat_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_long_repeat_20260605-163343/long_repeat_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_long_repeat_20260605-163343/repeat/dream7b_bpu_fine_forward_repeat_20260605-163343/summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_window_batch_20260603-181131/summary.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_forward_20260603-183625/fine_batch_forward_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_size_sweep_20260604-181429/batch_size_sweep_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_size_sweep_20260604-181429/batch_1/forward/summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_size_sweep_20260604-181429/batch_2/forward/summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_size_sweep_20260604-181429/batch_4/forward/summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_size_sweep_20260604-181429/batch_8/forward/summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_capacity_20260605-123835/batch_capacity_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_capacity_20260605-123835/batch_8/forward/summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_capacity_20260605-123835/batch_12/forward/summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_capacity_20260605-123835/batch_16/forward/summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_runtime_telemetry_20260604-225030/runtime_telemetry_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_runtime_telemetry_20260604-225030/forward/summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_runtime_telemetry_20260605-132014/runtime_telemetry_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_runtime_telemetry_20260605-132014/forward/summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_hbm_artifact_inventory_20260605-160050/hbm_artifact_inventory_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_hbm_artifact_inventory_20260605-160050/hbm_artifact_inventory_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_runner_20260603-193243/batch_queue_runner_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_drain_20260603-193309/batch_queue_drain_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_control_20260603-193400/batch_queue_control_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_lock_20260603-193209/batch_queue_lock_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_20260603-194437/batch_queue_service_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_real_scp_20260603-194827/output/service_summary.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_20260603-221324/systemd_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/service_summary.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_job_20260603_220710/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_soak_20260604-131223/systemd_soak_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_soak_20260604-131223_001/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_soak_20260604-131223_002/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_batch_20260604-133034/systemd_batch_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_batch_20260604-133034/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_20260604-174953/systemd_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_drain_20260604-174953/systemd_drain_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_drain_20260604-174953/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_drain_20260604-180557/systemd_drain_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_drain_20260604-180557/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_20260604-233926/systemd_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_batch_20260604-235205/systemd_batch_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_batch_20260604-235205/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_drain_20260604-235302/systemd_drain_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_drain_20260604-235302/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_20260605-131550/systemd_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_batch_20260605-131550/systemd_batch_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_batch_20260605-131550/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_drain_20260605-131621/systemd_drain_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_drain_20260605-131621/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_canary_20260605-151715/systemd_canary_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_canary_20260605-151715/systemd_canary_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_canary_20260605-151715/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260605-234555/text_queue_systemd_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_run_20260606-155102/text_queue_run.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_run_20260606-155102/text_queue_run.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/text_queue_run_20260606-155102/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/text_queue_run_20260606-155102/durable_state/results.jsonl"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-155148/text_queue_systemd_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-155148/text_queue_systemd_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-155148/text_queue_run.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-155148/text_queue_submit.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/text_queue_systemd_20260606-155148/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/text_queue_systemd_20260606-155148/durable_state/results.jsonl"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_generate_20260606-161120/generation.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_generate_20260606-161120/generation.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_generate_20260606-161120/step_00/forward/summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_generate_20260606-161120/step_01/forward/summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_telemetry_20260605-133919/systemd_telemetry_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_telemetry_20260605-133919/systemd_telemetry_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_telemetry_20260605-133919_001/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_telemetry_20260605-133919_002/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_telemetry_20260605-133919_003/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_retention_20260605-135448/queue_retention_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_retention_20260605-135448/queue_retention_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_batch_telemetry_20260606-080917/resplit_batch_telemetry_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_batch_telemetry_20260606-080917/resplit_batch_telemetry_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_window_cost_20260606-083152/resplit_window_cost_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_window_cost_20260606-083152/resplit_window_cost_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_utilization_gap_20260606-081136/utilization_gap_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_utilization_gap_20260606-081136/utilization_gap_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-081322/deployment_acceptance_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-081322/deployment_acceptance_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_utilization_gap_20260606-083359/utilization_gap_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_utilization_gap_20260606-083359/utilization_gap_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-083359/deployment_acceptance_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-083359/deployment_acceptance_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-143759/deployment_acceptance_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-143759/deployment_acceptance_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-153747/deployment_acceptance_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-153747/deployment_acceptance_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-161000/deployment_acceptance_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-161000/deployment_acceptance_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-172156/deployment_acceptance_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-172156/deployment_acceptance_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-134314/deployment_acceptance_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-134314/deployment_acceptance_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-142559/deployment_acceptance_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-142559/deployment_acceptance_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-144721/deployment_acceptance_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-144721/deployment_acceptance_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-155233/deployment_acceptance_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-155233/deployment_acceptance_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-161252/deployment_acceptance_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-161252/deployment_acceptance_probe.json"
  "/etc/systemd/system/dream7b-bpu-batch-queue.service"
  "/mnt/nas/openclaw/queues/dream7b-bpu"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_20260603-183906/fine_forward_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_loop_20260603-175030/summary.md"
)

errors=()

for path in "${required_files[@]}"; do
  if [[ ! -e "$path" ]]; then
    errors+=("missing file: $path")
  fi
done

if [[ -f README.md ]]; then
  for text in "${required_readme_strings[@]}"; do
    if ! grep -F -- "$text" README.md >/dev/null; then
      errors+=("README.md missing string: $text")
    fi
  done
fi

if [[ -f docs/project_reference.md ]]; then
  for text in "${required_reference_strings[@]}"; do
    if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
      errors+=("docs/project_reference.md missing string: $text")
    fi
  done
fi

if [[ -f scripts/probes/dream7b_segmented_hbm_python_forward.py ]]; then
  if ! grep -F -- "--child-runtime-mode" scripts/probes/dream7b_segmented_hbm_python_forward.py >/dev/null; then
    errors+=("dream7b_segmented_hbm_python_forward.py missing --child-runtime-mode")
  fi
  if ! grep -F -- "--window-execution-mode" scripts/probes/dream7b_segmented_hbm_python_forward.py >/dev/null; then
    errors+=("dream7b_segmented_hbm_python_forward.py missing --window-execution-mode")
  fi
  if ! grep -F -- "--tokens-batch-json" scripts/probes/dream7b_segmented_hbm_python_forward.py >/dev/null; then
    errors+=("dream7b_segmented_hbm_python_forward.py missing --tokens-batch-json")
  fi
fi

if [[ -f scripts/dream7b-bpu-fine-forward.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_FINE_CHILD_RUNTIME_MODE" scripts/dream7b-bpu-fine-forward.sh >/dev/null; then
    errors+=("dream7b-bpu-fine-forward.sh missing DREAM7B_BPU_FINE_CHILD_RUNTIME_MODE")
  fi
  if ! grep -F -- "DREAM7B_BPU_FINE_WINDOW_EXECUTION_MODE" scripts/dream7b-bpu-fine-forward.sh >/dev/null; then
    errors+=("dream7b-bpu-fine-forward.sh missing DREAM7B_BPU_FINE_WINDOW_EXECUTION_MODE")
  fi
fi

if [[ -f scripts/dream7b-bpu-fine-batch-forward.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_FINE_BATCH_WINDOW_EXECUTION_MODE" scripts/dream7b-bpu-fine-batch-forward.sh >/dev/null; then
    errors+=("dream7b-bpu-fine-batch-forward.sh missing DREAM7B_BPU_FINE_BATCH_WINDOW_EXECUTION_MODE")
  fi
  if ! grep -F -- "DREAM7B_BPU_TOKENS_BATCH_JSON" scripts/dream7b-bpu-fine-batch-forward.sh >/dev/null; then
    errors+=("dream7b-bpu-fine-batch-forward.sh missing DREAM7B_BPU_TOKENS_BATCH_JSON")
  fi
fi

if [[ -f scripts/dream7b-bpu-batch-queue-runner.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_BATCH_QUEUE_RUNNER_SCRIPT" scripts/dream7b-bpu-batch-queue-runner.sh >/dev/null; then
    errors+=("dream7b-bpu-batch-queue-runner.sh missing DREAM7B_BPU_BATCH_QUEUE_RUNNER_SCRIPT")
  fi
fi

if [[ -f scripts/dream7b-bpu-batch-queue-service.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_BATCH_QUEUE_SERVICE_SCRIPT" scripts/dream7b-bpu-batch-queue-service.sh >/dev/null; then
    errors+=("dream7b-bpu-batch-queue-service.sh missing DREAM7B_BPU_BATCH_QUEUE_SERVICE_SCRIPT")
  fi
fi

if [[ -f scripts/dream7b_bpu_batch_queue_runner.py ]]; then
  if ! grep -F -- "request_id" scripts/dream7b_bpu_batch_queue_runner.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_runner.py missing request_id")
  fi
  if ! grep -F -- "tokens" scripts/dream7b_bpu_batch_queue_runner.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_runner.py missing tokens")
  fi
  if ! grep -F -- "--drain-all" scripts/dream7b_bpu_batch_queue_runner.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_runner.py missing --drain-all")
  fi
  if ! grep -F -- "cancelled" scripts/dream7b_bpu_batch_queue_runner.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_runner.py missing cancelled")
  fi
  if ! grep -F -- "not_after_epoch_ms" scripts/dream7b_bpu_batch_queue_runner.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_runner.py missing not_after_epoch_ms")
  fi
  if ! grep -F -- "durable_state" scripts/dream7b_bpu_batch_queue_runner.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_runner.py missing durable_state")
  fi
  if ! grep -F -- "--bpu-lock-path" scripts/dream7b_bpu_batch_queue_runner.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_runner.py missing --bpu-lock-path")
  fi
  if ! grep -F -- "--bpu-lock-timeout-sec" scripts/dream7b_bpu_batch_queue_runner.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_runner.py missing --bpu-lock-timeout-sec")
  fi
  if ! grep -F -- "bpu_lock" scripts/dream7b_bpu_batch_queue_runner.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_runner.py missing bpu_lock")
  fi
fi

if [[ -f scripts/dream7b_bpu_batch_queue_service.py ]]; then
  if ! grep -F -- "pending" scripts/dream7b_bpu_batch_queue_service.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_service.py missing pending")
  fi
  if ! grep -F -- "processing" scripts/dream7b_bpu_batch_queue_service.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_service.py missing processing")
  fi
  if ! grep -F -- "done" scripts/dream7b_bpu_batch_queue_service.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_service.py missing done")
  fi
  if ! grep -F -- "failed" scripts/dream7b_bpu_batch_queue_service.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_service.py missing failed")
  fi
  if ! grep -F -- "service_summary.json" scripts/dream7b_bpu_batch_queue_service.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_service.py missing service_summary.json")
  fi
  if ! grep -F -- "build_summary_payload" scripts/dream7b_bpu_batch_queue_service.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_service.py missing build_summary_payload")
  fi
fi

if [[ -f scripts/install_dream7b_bpu_queue_service.sh ]]; then
  if ! grep -F -- "dream7b-bpu-batch-queue.service" scripts/install_dream7b_bpu_queue_service.sh >/dev/null; then
    errors+=("install_dream7b_bpu_queue_service.sh missing dream7b-bpu-batch-queue.service")
  fi
  if ! grep -F -- "/mnt/nas/openclaw/queues/dream7b-bpu" scripts/install_dream7b_bpu_queue_service.sh >/dev/null; then
    errors+=("install_dream7b_bpu_queue_service.sh missing /mnt/nas/openclaw/queues/dream7b-bpu")
  fi
  if ! grep -F -- "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd" scripts/install_dream7b_bpu_queue_service.sh >/dev/null; then
    errors+=("install_dream7b_bpu_queue_service.sh missing systemd output directory")
  fi
  if ! grep -F -- "/run/lock/dream7b_bpu_batch_queue_runner.lock" scripts/install_dream7b_bpu_queue_service.sh >/dev/null; then
    errors+=("install_dream7b_bpu_queue_service.sh missing /run/lock/dream7b_bpu_batch_queue_runner.lock")
  fi
  if ! grep -F -- "DREAM7B_BPU_QUEUE_DRAIN_ALL" scripts/install_dream7b_bpu_queue_service.sh >/dev/null; then
    errors+=("install_dream7b_bpu_queue_service.sh missing DREAM7B_BPU_QUEUE_DRAIN_ALL")
  fi
  if ! grep -F -- 'DREAM7B_BPU_QUEUE_MAX_BATCH_SIZE:-16' scripts/install_dream7b_bpu_queue_service.sh >/dev/null; then
    errors+=("install_dream7b_bpu_queue_service.sh missing default DREAM7B_BPU_QUEUE_MAX_BATCH_SIZE:-16")
  fi
  if ! grep -F -- "--max-batch-size" scripts/install_dream7b_bpu_queue_service.sh >/dev/null; then
    errors+=("install_dream7b_bpu_queue_service.sh missing --max-batch-size")
  fi
  if ! grep -F -- "--drain-all" scripts/install_dream7b_bpu_queue_service.sh >/dev/null; then
    errors+=("install_dream7b_bpu_queue_service.sh missing --drain-all")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_batch_queue_systemd_probe.sh ]]; then
  if ! grep -F -- "dream7b-bpu-batch-queue.service" scripts/probes/dream7b_bpu_batch_queue_systemd_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_probe.sh missing dream7b-bpu-batch-queue.service")
  fi
  if ! grep -F -- "service_status" scripts/probes/dream7b_bpu_batch_queue_systemd_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_probe.sh missing service_status")
  fi
  if ! grep -F -- "service_enabled" scripts/probes/dream7b_bpu_batch_queue_systemd_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_probe.sh missing service_enabled")
  fi
  if ! grep -F -- "/run/lock/dream7b_bpu_batch_queue_runner.lock" scripts/probes/dream7b_bpu_batch_queue_systemd_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_probe.sh missing /run/lock/dream7b_bpu_batch_queue_runner.lock")
  fi
  if ! grep -F -- "--drain-all" scripts/probes/dream7b_bpu_batch_queue_systemd_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_probe.sh missing --drain-all")
  fi
  if ! grep -F -- "--max-batch-size 16" scripts/probes/dream7b_bpu_batch_queue_systemd_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_probe.sh missing --max-batch-size 16")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_batch_queue_systemd_soak_probe.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_SYSTEMD_SOAK_JOB_COUNT" scripts/probes/dream7b_bpu_batch_queue_systemd_soak_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_soak_probe.sh missing DREAM7B_BPU_SYSTEMD_SOAK_JOB_COUNT")
  fi
  if ! grep -F -- "completed_job_count" scripts/probes/dream7b_bpu_batch_queue_systemd_soak_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_soak_probe.sh missing completed_job_count")
  fi
  if ! grep -F -- "processed_request_count" scripts/probes/dream7b_bpu_batch_queue_systemd_soak_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_soak_probe.sh missing processed_request_count")
  fi
  if ! grep -F -- "final_shape" scripts/probes/dream7b_bpu_batch_queue_systemd_soak_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_soak_probe.sh missing final_shape")
  fi
  if ! grep -F -- "/run/lock/dream7b_bpu_batch_queue_runner.lock" scripts/probes/dream7b_bpu_batch_queue_systemd_soak_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_soak_probe.sh missing /run/lock/dream7b_bpu_batch_queue_runner.lock")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_batch_queue_systemd_batch_probe.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_SYSTEMD_BATCH_REQUEST_COUNT" scripts/probes/dream7b_bpu_batch_queue_systemd_batch_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_batch_probe.sh missing DREAM7B_BPU_SYSTEMD_BATCH_REQUEST_COUNT")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SYSTEMD_BATCH_REQUEST_COUNT:-16' scripts/probes/dream7b_bpu_batch_queue_systemd_batch_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_batch_probe.sh missing default DREAM7B_BPU_SYSTEMD_BATCH_REQUEST_COUNT:-16")
  fi
  if ! grep -F -- "--max-batch-size 16" scripts/probes/dream7b_bpu_batch_queue_systemd_batch_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_batch_probe.sh missing --max-batch-size 16")
  fi
  if ! grep -F -- "batch_count" scripts/probes/dream7b_bpu_batch_queue_systemd_batch_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_batch_probe.sh missing batch_count")
  fi
  if ! grep -F -- "accepted_count" scripts/probes/dream7b_bpu_batch_queue_systemd_batch_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_batch_probe.sh missing accepted_count")
  fi
  if ! grep -F -- "deferred_count" scripts/probes/dream7b_bpu_batch_queue_systemd_batch_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_batch_probe.sh missing deferred_count")
  fi
  if ! grep -F -- "amortized_wall_ms_per_processed_request" scripts/probes/dream7b_bpu_batch_queue_systemd_batch_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_batch_probe.sh missing amortized_wall_ms_per_processed_request")
  fi
  if ! grep -F -- "/run/lock/dream7b_bpu_batch_queue_runner.lock" scripts/probes/dream7b_bpu_batch_queue_systemd_batch_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_batch_probe.sh missing /run/lock/dream7b_bpu_batch_queue_runner.lock")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_SYSTEMD_DRAIN_REQUEST_COUNT" scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_drain_probe.sh missing DREAM7B_BPU_SYSTEMD_DRAIN_REQUEST_COUNT")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SYSTEMD_DRAIN_REQUEST_COUNT:-16' scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_drain_probe.sh missing default DREAM7B_BPU_SYSTEMD_DRAIN_REQUEST_COUNT:-16")
  fi
  if ! grep -F -- "expected_max_batch_size=16" scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_drain_probe.sh missing expected_max_batch_size=16")
  fi
  if ! grep -F -- "expected_batch_counts" scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_drain_probe.sh missing expected_batch_counts")
  fi
  if ! grep -F -- "batch_counts" scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_drain_probe.sh missing batch_counts")
  fi
  if ! grep -F -- "batch_run_count" scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_drain_probe.sh missing batch_run_count")
  fi
  if ! grep -F -- "drain_all" scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_drain_probe.sh missing drain_all")
  fi
  if ! grep -F -- "--drain-all" scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_drain_probe.sh missing --drain-all")
  fi
  if ! grep -F -- "--max-batch-size 16" scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_drain_probe.sh missing --max-batch-size 16")
  fi
  if ! grep -F -- "/run/lock/dream7b_bpu_batch_queue_runner.lock" scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_drain_probe.sh missing /run/lock/dream7b_bpu_batch_queue_runner.lock")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_fine_batch_size_sweep_probe.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_FINE_BATCH_SWEEP_COUNTS" scripts/probes/dream7b_bpu_fine_batch_size_sweep_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_batch_size_sweep_probe.sh missing DREAM7B_BPU_FINE_BATCH_SWEEP_COUNTS")
  fi
  if ! grep -F -- "DREAM7B_BPU_FINE_BATCH_SWEEP_TIMEOUT_SEC" scripts/probes/dream7b_bpu_fine_batch_size_sweep_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_batch_size_sweep_probe.sh missing DREAM7B_BPU_FINE_BATCH_SWEEP_TIMEOUT_SEC")
  fi
  if ! grep -F -- "DREAM7B_BPU_FINE_BATCH_SWEEP_TOP_K" scripts/probes/dream7b_bpu_fine_batch_size_sweep_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_batch_size_sweep_probe.sh missing DREAM7B_BPU_FINE_BATCH_SWEEP_TOP_K")
  fi
  if ! grep -F -- "amortized_wall_ms_per_forward" scripts/probes/dream7b_bpu_fine_batch_size_sweep_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_batch_size_sweep_probe.sh missing amortized_wall_ms_per_forward")
  fi
  if ! grep -F -- "amortized_load_ms_per_forward" scripts/probes/dream7b_bpu_fine_batch_size_sweep_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_batch_size_sweep_probe.sh missing amortized_load_ms_per_forward")
  fi
  if ! grep -F -- "amortized_run_ms_per_forward" scripts/probes/dream7b_bpu_fine_batch_size_sweep_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_batch_size_sweep_probe.sh missing amortized_run_ms_per_forward")
  fi
  if ! grep -F -- "load_share" scripts/probes/dream7b_bpu_fine_batch_size_sweep_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_batch_size_sweep_probe.sh missing load_share")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_batch_capacity_probe.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_BATCH_CAPACITY_COUNTS" scripts/probes/dream7b_bpu_batch_capacity_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_capacity_probe.sh missing DREAM7B_BPU_BATCH_CAPACITY_COUNTS")
  fi
  if ! grep -F -- 'DREAM7B_BPU_BATCH_CAPACITY_COUNTS:-8 12 16' scripts/probes/dream7b_bpu_batch_capacity_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_capacity_probe.sh missing default DREAM7B_BPU_BATCH_CAPACITY_COUNTS:-8 12 16")
  fi
  if ! grep -F -- "DREAM7B_BPU_BATCH_CAPACITY_TIMEOUT_SEC" scripts/probes/dream7b_bpu_batch_capacity_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_capacity_probe.sh missing DREAM7B_BPU_BATCH_CAPACITY_TIMEOUT_SEC")
  fi
  if ! grep -F -- "DREAM7B_BPU_BATCH_CAPACITY_TOP_K" scripts/probes/dream7b_bpu_batch_capacity_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_capacity_probe.sh missing DREAM7B_BPU_BATCH_CAPACITY_TOP_K")
  fi
  if ! grep -F -- "max_passing_count" scripts/probes/dream7b_bpu_batch_capacity_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_capacity_probe.sh missing max_passing_count")
  fi
  if ! grep -F -- "amortized_wall_ms_per_forward" scripts/probes/dream7b_bpu_batch_capacity_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_capacity_probe.sh missing amortized_wall_ms_per_forward")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_TELEMETRY_BATCH_COUNT" scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_runtime_telemetry_probe.sh missing DREAM7B_BPU_TELEMETRY_BATCH_COUNT")
  fi
  if ! grep -F -- 'DREAM7B_BPU_TELEMETRY_BATCH_COUNT:-16' scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_runtime_telemetry_probe.sh missing default DREAM7B_BPU_TELEMETRY_BATCH_COUNT:-16")
  fi
  if ! grep -F -- "DREAM7B_BPU_TELEMETRY_MONITOR_DELAY_MS" scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_runtime_telemetry_probe.sh missing DREAM7B_BPU_TELEMETRY_MONITOR_DELAY_MS")
  fi
  if ! grep -F -- "DREAM7B_BPU_TELEMETRY_MONITOR_SAMPLE_COUNT" scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_runtime_telemetry_probe.sh missing DREAM7B_BPU_TELEMETRY_MONITOR_SAMPLE_COUNT")
  fi
  if ! grep -F -- "DREAM7B_BPU_TELEMETRY_TOP_K" scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_runtime_telemetry_probe.sh missing DREAM7B_BPU_TELEMETRY_TOP_K")
  fi
  if ! grep -F -- "DREAM7B_BPU_TELEMETRY_TIMEOUT_SEC" scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_runtime_telemetry_probe.sh missing DREAM7B_BPU_TELEMETRY_TIMEOUT_SEC")
  fi
  if ! grep -F -- "hrt_ucp_monitor" scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_runtime_telemetry_probe.sh missing hrt_ucp_monitor")
  fi
  if ! grep -F -- "bpu_loading_sample_count" scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_runtime_telemetry_probe.sh missing bpu_loading_sample_count")
  fi
  if ! grep -F -- "max_bpu_loading" scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_runtime_telemetry_probe.sh missing max_bpu_loading")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_hbm_artifact_inventory_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_ARTIFACT_INVENTORY_FORWARD_SCRIPT" \
    "DREAM7B_BPU_ARTIFACT_INVENTORY_NAS_HBM_DIR" \
    "DREAM7B_BPU_ARTIFACT_INVENTORY_NAS_FINE_HBM_DIR" \
    "DREAM7B_BPU_ARTIFACT_INVENTORY_LOCAL_HBM_DIR" \
    "DREAM7B_BPU_ARTIFACT_INVENTORY_LOCAL_FINE_HBM_DIR" \
    "DREAM7B_BPU_ARTIFACT_INVENTORY_VERIFY_MANIFEST" \
    "/mnt/nas/openclaw/runtimes/dream7b-bpu-forward/dream7b_segmented_hbm_python_forward.py" \
    "/mnt/nas/openclaw/models/dream7b-hbm/segments6" \
    "/mnt/nas/openclaw/models/dream7b-hbm/fine-seq16" \
    "/home/sunrise/.cache/openclaw/dream7b-hbm/segments6" \
    "/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16" \
    "SEGMENTS6" \
    "FINE_ADJACENT_SEGMENTS" \
    "hbm_artifact_inventory_probe.json" \
    "hbm_artifact_inventory_probe.md" \
    "ok_dream7b_bpu_hbm_artifact_inventory_probe" \
    "expected_artifact_count" \
    "expected_base_count" \
    "expected_fine_count" \
    "nas_existing_count" \
    "local_existing_count" \
    "size_match_count" \
    "manifest_expected_count" \
    "manifest_verified_count" \
    "required_manifest_expected_count"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_hbm_artifact_inventory_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_hbm_artifact_inventory_probe.sh missing $text")
    fi
  done
fi

if [[ -f scripts/probes/dream7b_bpu_fine_forward_long_repeat_probe.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_COUNT" scripts/probes/dream7b_bpu_fine_forward_long_repeat_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_forward_long_repeat_probe.sh missing DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_COUNT")
  fi
  if ! grep -F -- 'DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_COUNT:-6' scripts/probes/dream7b_bpu_fine_forward_long_repeat_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_forward_long_repeat_probe.sh missing default DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_COUNT:-6")
  fi
  if ! grep -F -- "DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_MAX_WALL_SPREAD_RATIO" scripts/probes/dream7b_bpu_fine_forward_long_repeat_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_forward_long_repeat_probe.sh missing DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_MAX_WALL_SPREAD_RATIO")
  fi
  if ! grep -F -- 'DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_MAX_WALL_SPREAD_RATIO:-0.10' scripts/probes/dream7b_bpu_fine_forward_long_repeat_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_forward_long_repeat_probe.sh missing default DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_MAX_WALL_SPREAD_RATIO:-0.10")
  fi
  if ! grep -F -- "dream7b-bpu-fine-forward-repeat-probe" scripts/probes/dream7b_bpu_fine_forward_long_repeat_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_forward_long_repeat_probe.sh missing dream7b-bpu-fine-forward-repeat-probe")
  fi
  if ! grep -F -- "failure_count" scripts/probes/dream7b_bpu_fine_forward_long_repeat_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_forward_long_repeat_probe.sh missing failure_count")
  fi
  if ! grep -F -- "wall_spread_ratio" scripts/probes/dream7b_bpu_fine_forward_long_repeat_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_forward_long_repeat_probe.sh missing wall_spread_ratio")
  fi
  if ! grep -F -- "repeat_summary_json" scripts/probes/dream7b_bpu_fine_forward_long_repeat_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_forward_long_repeat_probe.sh missing repeat_summary_json")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_SYSTEMD_TELEMETRY_JOB_COUNT" scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing DREAM7B_BPU_SYSTEMD_TELEMETRY_JOB_COUNT")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SYSTEMD_TELEMETRY_JOB_COUNT:-3' scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing default DREAM7B_BPU_SYSTEMD_TELEMETRY_JOB_COUNT:-3")
  fi
  if ! grep -F -- "DREAM7B_BPU_SYSTEMD_TELEMETRY_REQUEST_COUNT" scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing DREAM7B_BPU_SYSTEMD_TELEMETRY_REQUEST_COUNT")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SYSTEMD_TELEMETRY_REQUEST_COUNT:-16' scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing default DREAM7B_BPU_SYSTEMD_TELEMETRY_REQUEST_COUNT:-16")
  fi
  if ! grep -F -- "DREAM7B_BPU_SYSTEMD_TELEMETRY_TIMEOUT_SEC" scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing DREAM7B_BPU_SYSTEMD_TELEMETRY_TIMEOUT_SEC")
  fi
  if ! grep -F -- "DREAM7B_BPU_SYSTEMD_TELEMETRY_POLL_INTERVAL_SEC" scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing DREAM7B_BPU_SYSTEMD_TELEMETRY_POLL_INTERVAL_SEC")
  fi
  if ! grep -F -- "DREAM7B_BPU_SYSTEMD_TELEMETRY_MONITOR_DELAY_MS" scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing DREAM7B_BPU_SYSTEMD_TELEMETRY_MONITOR_DELAY_MS")
  fi
  if ! grep -F -- "DREAM7B_BPU_SYSTEMD_TELEMETRY_MONITOR_SAMPLE_COUNT" scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing DREAM7B_BPU_SYSTEMD_TELEMETRY_MONITOR_SAMPLE_COUNT")
  fi
  if ! grep -F -- "hrt_ucp_monitor" scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing hrt_ucp_monitor")
  fi
  if ! grep -F -- "batch_counts" scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing batch_counts")
  fi
  if ! grep -F -- "processed_request_count" scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing processed_request_count")
  fi
  if ! grep -F -- "max_bpu_loading" scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing max_bpu_loading")
  fi
  for text in \
    "dream7b-bpu-selected-pair-candidate.service" \
    "dream7b_bpu_selected_pair_candidate_service_telemetry" \
    "dream7b-bpu-selected-pair-batch-forward" \
    "selected-pair-resident" \
    "expected_forward_command" \
    "expected_window_execution_mode" \
    "expected_child_process_count" \
    "comparison_to_default_systemd_telemetry" \
    "candidate_wall_time_improved_vs_default_systemd" \
    "candidate_avg_bpu_loading_not_worse_than_default_systemd"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing selected-pair candidate telemetry string $text")
    fi
  done
fi

if [[ -f scripts/probes/dream7b_bpu_diffusion_generate_telemetry_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_DIFFUSION_GENERATE_TELEMETRY_PROMPT" \
    "DREAM7B_BPU_DIFFUSION_GENERATE_TELEMETRY_CMD" \
    "DREAM7B_BPU_DIFFUSION_GENERATE_TELEMETRY_MONITOR_DELAY_MS" \
    "DREAM7B_BPU_DIFFUSION_GENERATE_TELEMETRY_MONITOR_SAMPLE_COUNT" \
    "DREAM7B_BPU_DIFFUSION_GENERATE_TELEMETRY_TIMEOUT_SEC" \
    "dream7b-bpu-diffusion-generate" \
    "hrt_ucp_monitor" \
    "--run-dir" \
    "--prompt" \
    "generation_telemetry_probe.json" \
    "generation_telemetry_probe.md" \
    "ok_dream7b_bpu_diffusion_generate_telemetry_probe" \
    "ok_dream7b_bpu_diffusion_generate" \
    "generation_metrics" \
    "generation_status" \
    "bpu_loading_sample_count" \
    "nonzero_bpu_loading_sample_count" \
    "max_bpu_loading" \
    "avg_bpu_loading" \
    "decoded_final" \
    "remaining_mask_positions" \
    "forward_verdict" \
    "forward_execution_mode" \
    "forward_window_execution_mode" \
    "forward_child_process_count" \
    "forward_final_shape" \
    "bounded_seq16_generation_entrypoint_not_complete_production_text_service"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_diffusion_generate_telemetry_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_diffusion_generate_telemetry_probe.sh missing $text")
    fi
  done
fi

if [[ -f scripts/probes/dream7b_bpu_diffusion_batch_generate_telemetry_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TELEMETRY_BATCH_COUNT" \
    "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TELEMETRY_CMD" \
    "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TELEMETRY_MONITOR_DELAY_MS" \
    "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TELEMETRY_MONITOR_SAMPLE_COUNT" \
    "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TELEMETRY_TIMEOUT_SEC" \
    "dream7b-bpu-diffusion-batch-generate" \
    "hrt_ucp_monitor" \
    "--run-dir" \
    "--batch-count" \
    "batch_generation_telemetry_probe.json" \
    "batch_generation_telemetry_probe.md" \
    "batch_generation.json" \
    "batch_generation.md" \
    "ok_dream7b_bpu_diffusion_batch_generate_telemetry_probe" \
    "ok_dream7b_bpu_diffusion_batch_generate" \
    "generation_metrics" \
    "generation_status" \
    "batch_count" \
    "forward_batch_counts" \
    "remaining_mask_positions_by_batch" \
    "decoded_final_by_batch" \
    "bpu_loading_sample_count" \
    "nonzero_bpu_loading_sample_count" \
    "max_bpu_loading" \
    "avg_bpu_loading" \
    "forward_verdict" \
    "forward_execution_mode" \
    "forward_window_execution_mode" \
    "forward_child_process_count" \
    "forward_batch_count" \
    "forward_final_shapes" \
    "bounded_seq16_batch_generation_entrypoint_not_complete_production_text_service"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_diffusion_batch_generate_telemetry_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_diffusion_batch_generate_telemetry_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TELEMETRY_BATCH_COUNT:-16' scripts/probes/dream7b_bpu_diffusion_batch_generate_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_diffusion_batch_generate_telemetry_probe.sh missing default DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TELEMETRY_BATCH_COUNT:-16")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_diffusion_batch_generate_sustained_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_ROUND_COUNT" \
    "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_BATCH_COUNT" \
    "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_CMD" \
    "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_MONITOR_DELAY_MS" \
    "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_MONITOR_SAMPLE_COUNT" \
    "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_TIMEOUT_SEC" \
    "dream7b-bpu-diffusion-batch-generate" \
    "hrt_ucp_monitor" \
    "batch_generation_sustained_probe.json" \
    "batch_generation_sustained_probe.md" \
    "ok_dream7b_bpu_diffusion_batch_generate_sustained_probe" \
    "ok_dream7b_bpu_diffusion_batch_generate" \
    "round_count" \
    "successful_generation_count" \
    "expected_total_batch_items" \
    "actual_total_batch_items" \
    "generation_statuses" \
    "generation_batch_counts" \
    "generation_forward_batch_counts_by_round" \
    "total_forward_call_count" \
    "bpu_loading_sample_count" \
    "nonzero_bpu_loading_sample_count" \
    "max_bpu_loading" \
    "avg_bpu_loading" \
    "forward_batch_count" \
    "bounded_seq16_batch_generation_entrypoint_not_complete_production_text_service"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_diffusion_batch_generate_sustained_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_diffusion_batch_generate_sustained_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_ROUND_COUNT:-3' scripts/probes/dream7b_bpu_diffusion_batch_generate_sustained_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_diffusion_batch_generate_sustained_probe.sh missing default DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_ROUND_COUNT:-3")
  fi
  if ! grep -F -- 'DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_BATCH_COUNT:-16' scripts/probes/dream7b_bpu_diffusion_batch_generate_sustained_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_diffusion_batch_generate_sustained_probe.sh missing default DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_BATCH_COUNT:-16")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_utilization_gap_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_UTILIZATION_GAP_MIN_BATCH_COUNT" \
    "DREAM7B_BPU_UTILIZATION_GAP_MIN_SUSTAINED_ROUND_COUNT" \
    "DREAM7B_BPU_UTILIZATION_GAP_MIN_SUSTAINED_TOTAL_ITEMS" \
    "dream7b_bpu_fine_batch_size_sweep_*/batch_size_sweep_probe.json" \
    "dream7b_bpu_runtime_telemetry_*/runtime_telemetry_probe.json" \
    "dream7b_bpu_batch_queue_systemd_telemetry_*/systemd_telemetry_probe.json" \
    "dream7b_bpu_selected_pair_candidate_service_telemetry_*/systemd_telemetry_probe.json" \
    "dream7b_bpu_resplit_batch_telemetry_*/resplit_batch_telemetry_probe.json" \
    "dream7b_bpu_resplit_window_cost_*/resplit_window_cost_probe.json" \
    "dream7b_bpu_diffusion_batch_generate_sustained_*/batch_generation_sustained_probe.json" \
    "dream7b_bpu_diffusion_batch_generate_telemetry_*/batch_generation_telemetry_probe.json" \
    "dream7b_bpu_selected_pair_telemetry_*/selected_pair_telemetry_probe.json" \
    "utilization_gap_probe.json" \
    "utilization_gap_probe.md" \
    "ok_dream7b_bpu_utilization_gap_probe" \
    "hbm_reload_dominated" \
    "diagnosis" \
    "next_optimization_target" \
    "max_observed_bpu_loading" \
    "avg_observed_bpu_loading_across_reports" \
    "load_to_run_ratio" \
    "batch_scaling_reference" \
    "max_available_batch_count" \
    "amortized_load_ms_per_forward" \
    "amortized_run_ms_per_forward" \
    "runtime_telemetry" \
    "selected_pair_telemetry" \
    "wall_ms_delta_ratio_vs_default_runtime" \
    "selected_wall_time_improved_vs_default_runtime" \
    "selected_avg_bpu_loading_improved_vs_default_runtime" \
    "systemd_telemetry" \
    "selected_pair_candidate_service_telemetry" \
    "comparison_to_default_systemd_telemetry" \
    "candidate_wall_time_improved_vs_default_systemd" \
    "candidate_avg_bpu_loading_not_worse_than_default_systemd" \
    "selected_pair_candidate_service_load_to_run_ratio" \
    "selected_pair_candidate_service_avg_bpu_delta" \
    "resplit_batch_telemetry" \
    "resplit_batch_telemetry_avg_bpu_loading" \
    "resplit_batch_telemetry_load_to_run_ratio" \
    "resplit_batch_telemetry_amortized_wall_ms_per_forward" \
    "resplit_window_cost" \
    "resplit_expected_segments_per_forward" \
    "resplit_expected_window_count" \
    "resplit_window_cost_load_to_run_ratio" \
    "resplit_window_cost_top_load_window" \
    "resplit_window_cost_top_load_to_run_ratio_window" \
    "sustained_generation" \
    "batch_generate_telemetry"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_utilization_gap_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_utilization_gap_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'DREAM7B_BPU_UTILIZATION_GAP_MIN_BATCH_COUNT:-16' scripts/probes/dream7b_bpu_utilization_gap_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_utilization_gap_probe.sh missing default DREAM7B_BPU_UTILIZATION_GAP_MIN_BATCH_COUNT:-16")
  fi
  if ! grep -F -- 'DREAM7B_BPU_UTILIZATION_GAP_MIN_SUSTAINED_ROUND_COUNT:-3' scripts/probes/dream7b_bpu_utilization_gap_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_utilization_gap_probe.sh missing default DREAM7B_BPU_UTILIZATION_GAP_MIN_SUSTAINED_ROUND_COUNT:-3")
  fi
  if ! grep -F -- 'DREAM7B_BPU_UTILIZATION_GAP_MIN_SUSTAINED_TOTAL_ITEMS:-48' scripts/probes/dream7b_bpu_utilization_gap_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_utilization_gap_probe.sh missing default DREAM7B_BPU_UTILIZATION_GAP_MIN_SUSTAINED_TOTAL_ITEMS:-48")
  fi
  for text in \
    "dream7b_bpu_utilization_gap_20260609-153933" \
    "diagnosis: hbm_reload_dominated" \
    "resplit_batch_telemetry.load_to_run_ratio: 9.468" \
    "resplit_batch_telemetry.avg_bpu_loading: 9.628"; do
    if ! grep -F -- "$text" README.md >/dev/null; then
      errors+=("README.md missing round3 utilization evidence: $text")
    fi
    if ! grep -F -- "$text" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
      errors+=("Dream 7B segmented progress doc missing round3 utilization evidence: $text")
    fi
    if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
      errors+=("docs/project_reference.md missing round3 utilization evidence: $text")
    fi
  done
fi

if [[ -f scripts/probes/dream7b_bpu_persistent_pair_cache_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_PERSISTENT_PAIR_CACHE_WORKER_HOLD_SECONDS" \
    "DREAM7B_BPU_PERSISTENT_PAIR_CACHE_READY_TIMEOUT_SECONDS" \
    "DREAM7B_BPU_PERSISTENT_PAIR_CACHE_START_DELAY_SECONDS" \
    "persistent_pair_cache_probe.json" \
    "persistent_pair_cache_probe.md" \
    "ok_dream7b_bpu_persistent_pair_cache_probe" \
    "pair_worker_count" \
    "launched_pair_worker_count" \
    "ready_pair_worker_count" \
    "failed_pair_worker_count" \
    "ready_pair_indexes" \
    "failed_pair_indexes" \
    "launch_stopped_reason" \
    "all_pair_workers_ready" \
    "next_optimization_target" \
    "seg00_02" \
    "seg02_04" \
    "seg04_07" \
    "seg07_10" \
    "seg10_14" \
    "seg14_17" \
    "seg17_21" \
    "seg21_24" \
    "seg24_26" \
    "seg26_28"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_persistent_pair_cache_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_persistent_pair_cache_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'DREAM7B_BPU_PERSISTENT_PAIR_CACHE_WORKER_HOLD_SECONDS:-20' scripts/probes/dream7b_bpu_persistent_pair_cache_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_persistent_pair_cache_probe.sh missing default DREAM7B_BPU_PERSISTENT_PAIR_CACHE_WORKER_HOLD_SECONDS:-20")
  fi
  if ! grep -F -- 'DREAM7B_BPU_PERSISTENT_PAIR_CACHE_READY_TIMEOUT_SECONDS:-180' scripts/probes/dream7b_bpu_persistent_pair_cache_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_persistent_pair_cache_probe.sh missing default DREAM7B_BPU_PERSISTENT_PAIR_CACHE_READY_TIMEOUT_SECONDS:-180")
  fi
  if ! grep -F -- 'DREAM7B_BPU_PERSISTENT_PAIR_CACHE_START_DELAY_SECONDS:-2' scripts/probes/dream7b_bpu_persistent_pair_cache_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_persistent_pair_cache_probe.sh missing default DREAM7B_BPU_PERSISTENT_PAIR_CACHE_START_DELAY_SECONDS:-2")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_held_pair_residency_matrix_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_HELD_PAIR_MATRIX_HOLDER_READY_TIMEOUT_SECONDS" \
    "DREAM7B_BPU_HELD_PAIR_MATRIX_CANDIDATE_TIMEOUT_SECONDS" \
    "held_pair_residency_matrix_probe.json" \
    "held_pair_residency_matrix_probe.md" \
    "ok_dream7b_bpu_held_pair_residency_matrix_probe" \
    "pair_worker_count" \
    "ready_holder_pair_count" \
    "ready_holder_pair_indexes" \
    "matrix_entry_count" \
    "successful_pair_edge_count" \
    "failed_pair_edge_count" \
    "successful_pair_edges" \
    "failed_pair_edges" \
    "max_resident_pair_count_observed" \
    "next_optimization_target" \
    "seg00_02" \
    "seg02_04" \
    "seg04_07" \
    "seg07_10" \
    "seg10_14" \
    "seg14_17" \
    "seg17_21" \
    "seg21_24" \
    "seg24_26" \
    "seg26_28"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_held_pair_residency_matrix_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_held_pair_residency_matrix_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'DREAM7B_BPU_HELD_PAIR_MATRIX_HOLDER_READY_TIMEOUT_SECONDS:-180' scripts/probes/dream7b_bpu_held_pair_residency_matrix_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_held_pair_residency_matrix_probe.sh missing default DREAM7B_BPU_HELD_PAIR_MATRIX_HOLDER_READY_TIMEOUT_SECONDS:-180")
  fi
  if ! grep -F -- 'DREAM7B_BPU_HELD_PAIR_MATRIX_CANDIDATE_TIMEOUT_SECONDS:-180' scripts/probes/dream7b_bpu_held_pair_residency_matrix_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_held_pair_residency_matrix_probe.sh missing default DREAM7B_BPU_HELD_PAIR_MATRIX_CANDIDATE_TIMEOUT_SECONDS:-180")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_single_segment_residency_matrix_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_SINGLE_SEGMENT_MATRIX_HOLDER_READY_TIMEOUT_SECONDS" \
    "DREAM7B_BPU_SINGLE_SEGMENT_MATRIX_CANDIDATE_TIMEOUT_SECONDS" \
    "single_segment_residency_matrix_probe.json" \
    "single_segment_residency_matrix_probe.md" \
    "ok_dream7b_bpu_single_segment_residency_matrix_probe" \
    "segment_count" \
    "ready_holder_segment_count" \
    "ready_holder_segment_indexes" \
    "matrix_entry_count" \
    "successful_segment_edge_count" \
    "failed_segment_edge_count" \
    "successful_segment_edges" \
    "failed_segment_edges" \
    "max_resident_segment_count_observed" \
    "next_optimization_target" \
    "seg00_02" \
    "seg02_04" \
    "seg04_07" \
    "seg07_10" \
    "seg10_14" \
    "seg14_17" \
    "seg17_21" \
    "seg21_24" \
    "seg24_26" \
    "seg26_28"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_single_segment_residency_matrix_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_single_segment_residency_matrix_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'DREAM7B_BPU_SINGLE_SEGMENT_MATRIX_HOLDER_READY_TIMEOUT_SECONDS:-180' scripts/probes/dream7b_bpu_single_segment_residency_matrix_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_single_segment_residency_matrix_probe.sh missing default DREAM7B_BPU_SINGLE_SEGMENT_MATRIX_HOLDER_READY_TIMEOUT_SECONDS:-180")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SINGLE_SEGMENT_MATRIX_CANDIDATE_TIMEOUT_SECONDS:-180' scripts/probes/dream7b_bpu_single_segment_residency_matrix_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_single_segment_residency_matrix_probe.sh missing default DREAM7B_BPU_SINGLE_SEGMENT_MATRIX_CANDIDATE_TIMEOUT_SECONDS:-180")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_persistent_segment_cache_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_PERSISTENT_SEGMENT_CACHE_WORKER_HOLD_SECONDS" \
    "DREAM7B_BPU_PERSISTENT_SEGMENT_CACHE_READY_TIMEOUT_SECONDS" \
    "DREAM7B_BPU_PERSISTENT_SEGMENT_CACHE_START_DELAY_SECONDS" \
    "persistent_segment_cache_probe.json" \
    "persistent_segment_cache_probe.md" \
    "ok_dream7b_bpu_persistent_segment_cache_probe" \
    "segment_worker_count" \
    "launched_segment_worker_count" \
    "ready_segment_worker_count" \
    "failed_segment_worker_count" \
    "ready_segment_indexes" \
    "failed_segment_indexes" \
    "all_segment_workers_ready" \
    "launch_stopped_reason" \
    "max_resident_segment_count_observed" \
    "next_optimization_target" \
    "seg00_02" \
    "seg02_04" \
    "seg04_07" \
    "seg07_10" \
    "seg10_14" \
    "seg14_17" \
    "seg17_21" \
    "seg21_24" \
    "seg24_26" \
    "seg26_28"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_persistent_segment_cache_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_persistent_segment_cache_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'DREAM7B_BPU_PERSISTENT_SEGMENT_CACHE_WORKER_HOLD_SECONDS:-5' scripts/probes/dream7b_bpu_persistent_segment_cache_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_persistent_segment_cache_probe.sh missing default DREAM7B_BPU_PERSISTENT_SEGMENT_CACHE_WORKER_HOLD_SECONDS:-5")
  fi
  if ! grep -F -- 'DREAM7B_BPU_PERSISTENT_SEGMENT_CACHE_READY_TIMEOUT_SECONDS:-180' scripts/probes/dream7b_bpu_persistent_segment_cache_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_persistent_segment_cache_probe.sh missing default DREAM7B_BPU_PERSISTENT_SEGMENT_CACHE_READY_TIMEOUT_SECONDS:-180")
  fi
  if ! grep -F -- 'DREAM7B_BPU_PERSISTENT_SEGMENT_CACHE_START_DELAY_SECONDS:-1' scripts/probes/dream7b_bpu_persistent_segment_cache_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_persistent_segment_cache_probe.sh missing default DREAM7B_BPU_PERSISTENT_SEGMENT_CACHE_START_DELAY_SECONDS:-1")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_single_segment_triplet_residency_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_SINGLE_SEGMENT_TRIPLET_READY_TIMEOUT_SECONDS" \
    "DREAM7B_BPU_SINGLE_SEGMENT_TRIPLET_START_DELAY_SECONDS" \
    "DREAM7B_BPU_SINGLE_SEGMENT_TRIPLET_MAX_COMBINATIONS" \
    "single_segment_triplet_residency_probe.json" \
    "single_segment_triplet_residency_probe.md" \
    "ok_dream7b_bpu_single_segment_triplet_residency_probe" \
    "segment_count" \
    "total_triplet_combination_count" \
    "tested_triplet_combination_count" \
    "successful_triplet_count" \
    "failed_triplet_count" \
    "successful_triplets" \
    "failed_triplets" \
    "max_resident_segment_count_observed" \
    "next_optimization_target" \
    "seg00_02" \
    "seg02_04" \
    "seg04_07" \
    "seg07_10" \
    "seg10_14" \
    "seg14_17" \
    "seg17_21" \
    "seg21_24" \
    "seg24_26" \
    "seg26_28"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_single_segment_triplet_residency_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_single_segment_triplet_residency_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'DREAM7B_BPU_SINGLE_SEGMENT_TRIPLET_READY_TIMEOUT_SECONDS:-180' scripts/probes/dream7b_bpu_single_segment_triplet_residency_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_single_segment_triplet_residency_probe.sh missing default DREAM7B_BPU_SINGLE_SEGMENT_TRIPLET_READY_TIMEOUT_SECONDS:-180")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SINGLE_SEGMENT_TRIPLET_START_DELAY_SECONDS:-0' scripts/probes/dream7b_bpu_single_segment_triplet_residency_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_single_segment_triplet_residency_probe.sh missing default DREAM7B_BPU_SINGLE_SEGMENT_TRIPLET_START_DELAY_SECONDS:-0")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SINGLE_SEGMENT_TRIPLET_MAX_COMBINATIONS:-120' scripts/probes/dream7b_bpu_single_segment_triplet_residency_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_single_segment_triplet_residency_probe.sh missing default DREAM7B_BPU_SINGLE_SEGMENT_TRIPLET_MAX_COMBINATIONS:-120")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_seeded_quad_residency_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_SEEDED_QUAD_TRIPLET_JSON" \
    "DREAM7B_BPU_SEEDED_QUAD_READY_TIMEOUT_SECONDS" \
    "DREAM7B_BPU_SEEDED_QUAD_START_DELAY_SECONDS" \
    "DREAM7B_BPU_SEEDED_QUAD_MAX_COMBINATIONS" \
    "seeded_quad_residency_probe.json" \
    "seeded_quad_residency_probe.md" \
    "ok_dream7b_bpu_seeded_quad_residency_probe" \
    "source_successful_triplet_count" \
    "seeded_quad_candidate_count" \
    "tested_seeded_quad_count" \
    "successful_seeded_quad_count" \
    "failed_seeded_quad_count" \
    "successful_seeded_quads" \
    "failed_seeded_quads" \
    "max_resident_segment_count_observed" \
    "next_optimization_target" \
    "successful_triplets" \
    "seg00_02" \
    "seg02_04" \
    "seg04_07" \
    "seg07_10" \
    "seg10_14" \
    "seg14_17" \
    "seg17_21" \
    "seg21_24" \
    "seg24_26" \
    "seg26_28"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_seeded_quad_residency_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_seeded_quad_residency_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'DREAM7B_BPU_SEEDED_QUAD_READY_TIMEOUT_SECONDS:-180' scripts/probes/dream7b_bpu_seeded_quad_residency_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_seeded_quad_residency_probe.sh missing default DREAM7B_BPU_SEEDED_QUAD_READY_TIMEOUT_SECONDS:-180")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SEEDED_QUAD_START_DELAY_SECONDS:-0' scripts/probes/dream7b_bpu_seeded_quad_residency_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_seeded_quad_residency_probe.sh missing default DREAM7B_BPU_SEEDED_QUAD_START_DELAY_SECONDS:-0")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SEEDED_QUAD_MAX_COMBINATIONS:-140' scripts/probes/dream7b_bpu_seeded_quad_residency_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_seeded_quad_residency_probe.sh missing default DREAM7B_BPU_SEEDED_QUAD_MAX_COMBINATIONS:-140")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_segment_capacity_planner_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_SEGMENT_CAPACITY_MODEL_REPORT_ROOT" \
    "DREAM7B_BPU_SEGMENT_CAPACITY_BASE_HBM_DIR" \
    "DREAM7B_BPU_SEGMENT_CAPACITY_FINE_HBM_DIR" \
    "dream7b_bpu_segment_capacity_planner_" \
    "segment_capacity_planner_probe.json" \
    "segment_capacity_planner_probe.md" \
    "ok_dream7b_bpu_segment_capacity_planner_probe" \
    "hbm_segment_inventory" \
    "current_split_capacity" \
    "current_split_quad_residency_supported" \
    "triplet_success_appearance_by_segment_index" \
    "triplet_failed_worker_count_by_segment_index" \
    "recommended_anchor_segment_indexes" \
    "recommended_resplit_segment_indexes" \
    "recompile or split weak residency segments"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_segment_capacity_planner_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_segment_capacity_planner_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'DREAM7B_BPU_SEGMENT_CAPACITY_MODEL_REPORT_ROOT:-/mnt/nas/openclaw/reports/models' scripts/probes/dream7b_bpu_segment_capacity_planner_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_segment_capacity_planner_probe.sh missing default DREAM7B_BPU_SEGMENT_CAPACITY_MODEL_REPORT_ROOT:-/mnt/nas/openclaw/reports/models")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_persistent_triplet_topology_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_TRIPLET_JSON" \
    "DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_HOLD_SECONDS" \
    "DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_READY_TIMEOUT_SECONDS" \
    "DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_POLL_INTERVAL_SECONDS" \
    "DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_START_DELAY_SECONDS" \
    "DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_MAX_TRIPLETS" \
    "persistent_triplet_topology_probe.json" \
    "persistent_triplet_topology_probe.md" \
    "ok_dream7b_bpu_persistent_triplet_topology_probe" \
    "source_successful_triplet_count" \
    "tested_triplet_topology_count" \
    "stable_triplet_topology_count" \
    "failed_triplet_topology_count" \
    "stable_triplets" \
    "failed_triplets" \
    "selected_topology" \
    "selection_rule" \
    "max_resident_segment_count_observed" \
    "next_optimization_target" \
    "seg00_02" \
    "seg02_04" \
    "seg04_07" \
    "seg07_10" \
    "seg10_14" \
    "seg14_17" \
    "seg17_21" \
    "seg21_24" \
    "seg24_26" \
    "seg26_28"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_persistent_triplet_topology_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_persistent_triplet_topology_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_HOLD_SECONDS:-10' scripts/probes/dream7b_bpu_persistent_triplet_topology_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_persistent_triplet_topology_probe.sh missing default DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_HOLD_SECONDS:-10")
  fi
  if ! grep -F -- 'DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_READY_TIMEOUT_SECONDS:-180' scripts/probes/dream7b_bpu_persistent_triplet_topology_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_persistent_triplet_topology_probe.sh missing default DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_READY_TIMEOUT_SECONDS:-180")
  fi
  if ! grep -F -- 'DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_POLL_INTERVAL_SECONDS:-2' scripts/probes/dream7b_bpu_persistent_triplet_topology_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_persistent_triplet_topology_probe.sh missing default DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_POLL_INTERVAL_SECONDS:-2")
  fi
  if ! grep -F -- 'DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_START_DELAY_SECONDS:-0' scripts/probes/dream7b_bpu_persistent_triplet_topology_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_persistent_triplet_topology_probe.sh missing default DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_START_DELAY_SECONDS:-0")
  fi
  if ! grep -F -- 'DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_MAX_TRIPLETS:-20' scripts/probes/dream7b_bpu_persistent_triplet_topology_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_persistent_triplet_topology_probe.sh missing default DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_MAX_TRIPLETS:-20")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_window3_forward_feasibility_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_WINDOW3_FORWARD_CMD" \
    "DREAM7B_BPU_WINDOW3_FORWARD_TIMEOUT_SEC" \
    "DREAM7B_BPU_WINDOW3_FORWARD_TOP_K" \
    "window3_forward_feasibility_probe.json" \
    "window3_forward_feasibility_probe.md" \
    "ok_dream7b_bpu_window3_forward_feasibility_probe" \
    "direct_window3_forward_supported" \
    "expected_window3_failure_observed" \
    "stderr_contains_memory_alloc_failure" \
    "window_size" \
    "child_window_mode" \
    "child_runtime_mode" \
    "window_execution_mode" \
    "next_optimization_target"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_window3_forward_feasibility_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_window3_forward_feasibility_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'DREAM7B_BPU_WINDOW3_FORWARD_TIMEOUT_SEC:-240' scripts/probes/dream7b_bpu_window3_forward_feasibility_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_window3_forward_feasibility_probe.sh missing default DREAM7B_BPU_WINDOW3_FORWARD_TIMEOUT_SEC:-240")
  fi
  if ! grep -F -- 'DREAM7B_BPU_WINDOW3_FORWARD_TOP_K:-3' scripts/probes/dream7b_bpu_window3_forward_feasibility_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_window3_forward_feasibility_probe.sh missing default DREAM7B_BPU_WINDOW3_FORWARD_TOP_K:-3")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_selected_triplet_forward_path_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_SELECTED_TRIPLET_TOPOLOGY_JSON" \
    "DREAM7B_BPU_SELECTED_TRIPLET_BASELINE_FORWARD_CMD" \
    "DREAM7B_BPU_SELECTED_TRIPLET_BATCH_COUNT" \
    "DREAM7B_BPU_SELECTED_TRIPLET_TOP_K" \
    "DREAM7B_BPU_SELECTED_TRIPLET_TIMEOUT_SEC" \
    "DREAM7B_BPU_SELECTED_TRIPLET_ALLOW_CRASH_RETRY" \
    "selected_triplet_forward_path_probe.json" \
    "selected_triplet_forward_path_probe.md" \
    "ok_dream7b_bpu_selected_triplet_forward_path_probe" \
    "selected_triplet_forward_supported" \
    "reboot_or_disconnect_observed" \
    "expected_reboot_guard_observed" \
    "source_incomplete_run_dir" \
    "warm_path_load_improved" \
    "total_path_load_improved" \
    "next_optimization_target"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_selected_triplet_forward_path_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_selected_triplet_forward_path_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_TRIPLET_BATCH_COUNT:-4' scripts/probes/dream7b_bpu_selected_triplet_forward_path_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_selected_triplet_forward_path_probe.sh missing default DREAM7B_BPU_SELECTED_TRIPLET_BATCH_COUNT:-4")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_TRIPLET_TOP_K:-3' scripts/probes/dream7b_bpu_selected_triplet_forward_path_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_selected_triplet_forward_path_probe.sh missing default DREAM7B_BPU_SELECTED_TRIPLET_TOP_K:-3")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_TRIPLET_TIMEOUT_SEC:-900' scripts/probes/dream7b_bpu_selected_triplet_forward_path_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_selected_triplet_forward_path_probe.sh missing default DREAM7B_BPU_SELECTED_TRIPLET_TIMEOUT_SEC:-900")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_selected_pair_forward_path_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_SELECTED_PAIR_TRIPLET_JSON" \
    "DREAM7B_BPU_SELECTED_PAIR_INDEXES" \
    "DREAM7B_BPU_SELECTED_PAIR_BASELINE_FORWARD_CMD" \
    "DREAM7B_BPU_SELECTED_PAIR_BATCH_COUNT" \
    "DREAM7B_BPU_SELECTED_PAIR_JOB_COUNT" \
    "DREAM7B_BPU_SELECTED_PAIR_TOP_K" \
    "DREAM7B_BPU_SELECTED_PAIR_TIMEOUT_SEC" \
    "DREAM7B_BPU_SELECTED_PAIR_ONLY" \
    "DREAM7B_BPU_SELECTED_PAIR_TOKENS_BATCHES_BY_JOB_JSON" \
    "successful_triplets" \
    "selected_only" \
    "baseline_skipped" \
    "selected_pair_covers_all_segments" \
    "selected_pair_forward_summary.json" \
    "selected_pair_forward_path_probe.json" \
    "selected_pair_forward_path_probe.md" \
    "ok_dream7b_bpu_selected_pair_forward_path_probe" \
    "selected_pair" \
    "selected_segments" \
    "selected_third_segments" \
    "selected_worker_count" \
    "processed_forward_count" \
    "tokens_batches_by_job_json" \
    "final_shapes_by_job" \
    "selected_resident_load_ms" \
    "forward_load_ms" \
    "selected_total_load_ms" \
    "warm_load_ms_delta_vs_baseline" \
    "warm_load_ms_delta_ratio_vs_baseline" \
    "total_load_ms_delta_vs_baseline" \
    "total_load_ms_delta_ratio_vs_baseline" \
    "warm_path_load_improved" \
    "total_path_load_improved" \
    "promote selected-pair worker path only after batch16 and telemetry probes"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_selected_pair_forward_path_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_selected_pair_forward_path_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_PAIR_BATCH_COUNT:-4' scripts/probes/dream7b_bpu_selected_pair_forward_path_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_selected_pair_forward_path_probe.sh missing default DREAM7B_BPU_SELECTED_PAIR_BATCH_COUNT:-4")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_PAIR_JOB_COUNT:-1' scripts/probes/dream7b_bpu_selected_pair_forward_path_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_selected_pair_forward_path_probe.sh missing default DREAM7B_BPU_SELECTED_PAIR_JOB_COUNT:-1")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_PAIR_JOB_COUNT_LIMIT:-12' scripts/probes/dream7b_bpu_selected_pair_forward_path_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_selected_pair_forward_path_probe.sh missing default DREAM7B_BPU_SELECTED_PAIR_JOB_COUNT_LIMIT:-12")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_PAIR_JOB_COUNT must be an integer from 1 to $job_count_limit' scripts/probes/dream7b_bpu_selected_pair_forward_path_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_selected_pair_forward_path_probe.sh missing dynamic cross-job queue job_count upper bound")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_PAIR_TOP_K:-3' scripts/probes/dream7b_bpu_selected_pair_forward_path_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_selected_pair_forward_path_probe.sh missing default DREAM7B_BPU_SELECTED_PAIR_TOP_K:-3")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_PAIR_TIMEOUT_SEC:-900' scripts/probes/dream7b_bpu_selected_pair_forward_path_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_selected_pair_forward_path_probe.sh missing default DREAM7B_BPU_SELECTED_PAIR_TIMEOUT_SEC:-900")
  fi
fi

if [[ -f scripts/dream7b_bpu_selected_pair_cross_job_queue_runner.py ]]; then
  for text in \
    "ok_dream7b_bpu_selected_pair_cross_job_queue_runner" \
    "DREAM7B_BPU_SELECTED_PAIR_TOKENS_BATCHES_BY_JOB_JSON" \
    "cross_job_queue_summary.json" \
    "cross_job_queue_summary.md" \
    "tokens_batches_by_job.json" \
    "selected_pair_covers_all_segments" \
    "single-job fallback path used" \
    "load_to_run_ratio" \
    "amortized_wall_ms_per_processed_request"; do
    if ! grep -F -- "$text" scripts/dream7b_bpu_selected_pair_cross_job_queue_runner.py >/dev/null; then
      errors+=("dream7b_bpu_selected_pair_cross_job_queue_runner.py missing $text")
    fi
  done
else
  errors+=("missing scripts/dream7b_bpu_selected_pair_cross_job_queue_runner.py")
fi

if [[ -f scripts/dream7b_bpu_selected_pair_cross_job_queue_service.py ]]; then
  for text in \
    "ok_dream7b_bpu_selected_pair_cross_job_queue_service" \
    "cross_job_queue_service_summary.json" \
    "cross_job_queue_service_summary.md" \
    "dream7b_bpu_selected_pair_cross_job_queue_runner.py" \
    "min_job_count" \
    "max_job_count" \
    "single_job_flush_timeout_sec" \
    "bpu_lock_path" \
    "--single-job-flush-timeout-sec" \
    "--bpu-lock-path"; do
    if ! grep -F -- "$text" scripts/dream7b_bpu_selected_pair_cross_job_queue_service.py >/dev/null; then
      errors+=("dream7b_bpu_selected_pair_cross_job_queue_service.py missing $text")
    fi
  done
else
  errors+=("missing scripts/dream7b_bpu_selected_pair_cross_job_queue_service.py")
fi

if [[ -f scripts/install_dream7b_bpu_selected_pair_cross_job_candidate_service.sh ]]; then
  for text in \
    "DREAM7B_BPU_CROSS_JOB_CANDIDATE_SERVICE_NAME" \
    "DREAM7B_BPU_CROSS_JOB_CANDIDATE_MIN_JOB_COUNT" \
    "DREAM7B_BPU_CROSS_JOB_CANDIDATE_MAX_JOB_COUNT" \
    "DREAM7B_BPU_CROSS_JOB_CANDIDATE_SINGLE_JOB_FLUSH_TIMEOUT_SEC" \
    "DREAM7B_BPU_CROSS_JOB_CANDIDATE_BPU_LOCK_PATH" \
    "DREAM7B_BPU_CROSS_JOB_CANDIDATE_REPO_DIR" \
    "dream7b-bpu-selected-pair-cross-job-candidate.service" \
    "/mnt/nas/openclaw/queues/dream7b-bpu-selected-pair-cross-job-candidate" \
    "/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_candidate_service" \
    "dream7b-bpu-batch-queue.service" \
    "default_service_replaced: false" \
    "--single-job-flush-timeout-sec" \
    "--bpu-lock-path" \
    "ExecStart"; do
    if ! grep -F -- "$text" scripts/install_dream7b_bpu_selected_pair_cross_job_candidate_service.sh >/dev/null; then
      errors+=("install_dream7b_bpu_selected_pair_cross_job_candidate_service.sh missing $text")
    fi
  done
else
  errors+=("missing scripts/install_dream7b_bpu_selected_pair_cross_job_candidate_service.sh")
fi

if [[ -f scripts/probes/dream7b_bpu_selected_pair_cross_job_queue_telemetry_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_JOB_COUNT" \
    "DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_MONITOR_SAMPLE_COUNT" \
    "DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_RUNNER_CMD" \
    "cross_job_queue_telemetry_probe.json" \
    "cross_job_queue_telemetry_probe.md" \
    "ok_dream7b_bpu_selected_pair_cross_job_queue_telemetry_probe" \
    "avg_bpu_loading" \
    "load_to_run_ratio" \
    "hrt_ucp_monitor"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_selected_pair_cross_job_queue_telemetry_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_selected_pair_cross_job_queue_telemetry_probe.sh missing $text")
    fi
  done
else
  errors+=("missing scripts/probes/dream7b_bpu_selected_pair_cross_job_queue_telemetry_probe.sh")
fi

if [[ -f scripts/probes/dream7b_bpu_selected_pair_cross_job_service_fallback_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_CROSS_JOB_SERVICE_FALLBACK_QUEUE_DIR" \
    "DREAM7B_BPU_CROSS_JOB_SERVICE_FALLBACK_BPU_LOCK_PATH" \
    "DREAM7B_BPU_CROSS_JOB_SERVICE_FALLBACK_FLUSH_TIMEOUT_SEC" \
    "cross_job_service_fallback_probe.json" \
    "cross_job_service_fallback_probe.md" \
    "ok_dream7b_bpu_selected_pair_cross_job_service_fallback_probe" \
    "single_job_fallback_ok" \
    "single_job_flush_timeout" \
    "--single-job-flush-timeout-sec" \
    "--bpu-lock-path"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_selected_pair_cross_job_service_fallback_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_selected_pair_cross_job_service_fallback_probe.sh missing $text")
    fi
  done
else
  errors+=("missing scripts/probes/dream7b_bpu_selected_pair_cross_job_service_fallback_probe.sh")
fi

if [[ -f scripts/probes/dream7b_bpu_selected_pair_cross_job_service_promotion_gate_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_CROSS_JOB_SERVICE_PROMOTION_MIN_PROCESSED_REQUEST_COUNT" \
    "cross_job_service_promotion_gate_probe.json" \
    "cross_job_service_promotion_gate_probe.md" \
    "ok_dream7b_bpu_selected_pair_cross_job_service_promotion_gate_probe" \
    "promotion_allowed" \
    "ready_for_default_service_replacement" \
    "default_service_replaced" \
    "single_job_fallback_ok" \
    "execstart_enables_single_job_flush" \
    "rollback_plan" \
    "sudo systemctl restart {default_service_name}"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_selected_pair_cross_job_service_promotion_gate_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_selected_pair_cross_job_service_promotion_gate_probe.sh missing $text")
    fi
  done
else
  errors+=("missing scripts/probes/dream7b_bpu_selected_pair_cross_job_service_promotion_gate_probe.sh")
fi

if [[ -f scripts/probes/dream7b_bpu_cross_job_default_promotion_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_CROSS_JOB_DEFAULT_PROMOTION_RUNTIME_DIR" \
    "dream7b-bpu-batch-queue.service" \
    "/mnt/nas/openclaw/runtimes/dream7b-bpu-cross-job-default" \
    "cross_job_default_promotion_probe.json" \
    "cross_job_default_promotion_probe.md" \
    "ok_dream7b_bpu_cross_job_default_promotion_probe" \
    "default_service_replaced" \
    "rollback_verified" \
    "rollback_commands" \
    "dream7b_bpu_selected_pair_cross_job_queue_service.py" \
    "--single-job-flush-timeout-sec"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_cross_job_default_promotion_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_cross_job_default_promotion_probe.sh missing $text")
    fi
  done
else
  errors+=("missing scripts/probes/dream7b_bpu_cross_job_default_promotion_probe.sh")
fi

if [[ -f scripts/probes/dream7b_bpu_cross_job_default_service_telemetry_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_CROSS_JOB_DEFAULT_TELEMETRY_SERVICE_NAME" \
    "dream7b-bpu-batch-queue.service" \
    "/mnt/nas/openclaw/queues/dream7b-bpu" \
    "default_service_telemetry_probe.json" \
    "default_service_telemetry_probe.md" \
    "ok_dream7b_bpu_cross_job_default_service_telemetry_probe" \
    "processed_request_count" \
    "avg_bpu_loading" \
    "load_to_run_ratio" \
    "hrt_ucp_monitor"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_cross_job_default_service_telemetry_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_cross_job_default_service_telemetry_probe.sh missing $text")
    fi
  done
else
  errors+=("missing scripts/probes/dream7b_bpu_cross_job_default_service_telemetry_probe.sh")
fi

if [[ -f scripts/probes/dream7b_bpu_selected_pair_telemetry_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_BATCH_COUNT" \
    "DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_MONITOR_DELAY_MS" \
    "DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_MONITOR_SAMPLE_COUNT" \
    "DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_TOP_K" \
    "DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_TIMEOUT_SEC" \
    "DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_FORWARD_CMD" \
    "DREAM7B_BPU_SELECTED_PAIR_ONLY=1" \
    "hrt_ucp_monitor" \
    "selected_pair_telemetry_probe.json" \
    "selected_pair_telemetry_probe.md" \
    "ok_dream7b_bpu_selected_pair_telemetry_probe" \
    "selected_pair_report_json" \
    "bpu_loading_sample_count" \
    "nonzero_bpu_loading_sample_count" \
    "max_bpu_loading" \
    "avg_bpu_loading" \
    "default_runtime_telemetry" \
    "comparison_to_default_runtime_telemetry" \
    "wall_ms_delta_ratio_vs_default_runtime" \
    "selected_wall_time_improved_vs_default_runtime" \
    "selected_avg_bpu_loading_improved_vs_default_runtime" \
    "rerun default runtime telemetry and selected-pair telemetry back-to-back"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_selected_pair_telemetry_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_selected_pair_telemetry_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_BATCH_COUNT:-16' scripts/probes/dream7b_bpu_selected_pair_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_selected_pair_telemetry_probe.sh missing default DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_BATCH_COUNT:-16")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_MONITOR_DELAY_MS:-100' scripts/probes/dream7b_bpu_selected_pair_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_selected_pair_telemetry_probe.sh missing default DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_MONITOR_DELAY_MS:-100")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_MONITOR_SAMPLE_COUNT:-320' scripts/probes/dream7b_bpu_selected_pair_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_selected_pair_telemetry_probe.sh missing default DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_MONITOR_SAMPLE_COUNT:-320")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_TOP_K:-3' scripts/probes/dream7b_bpu_selected_pair_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_selected_pair_telemetry_probe.sh missing default DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_TOP_K:-3")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_TIMEOUT_SEC:-480' scripts/probes/dream7b_bpu_selected_pair_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_selected_pair_telemetry_probe.sh missing default DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_TIMEOUT_SEC:-480")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_selected_pair_promotion_gate_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_SELECTED_PAIR_PROMOTION_MIN_BATCH_COUNT" \
    "DREAM7B_BPU_SELECTED_PAIR_PROMOTION_MIN_WALL_DELTA_RATIO" \
    "DREAM7B_BPU_SELECTED_PAIR_PROMOTION_MIN_AVG_BPU_DELTA" \
    "selected_pair_promotion_gate_probe.json" \
    "selected_pair_promotion_gate_probe.md" \
    "ok_dream7b_bpu_selected_pair_promotion_gate_probe" \
    "promotion_ready_for_guarded_default_service_candidate" \
    "default_service_already_promoted" \
    "selected_pair_telemetry_path" \
    "utilization_gap_path" \
    "deployment_acceptance_path" \
    "selected_wall_time_improved_vs_default_runtime" \
    "selected_avg_bpu_loading_improved_vs_default_runtime" \
    "wall_ms_delta_ratio_vs_default_runtime" \
    "avg_bpu_loading_delta_vs_default_runtime" \
    "implement a guarded selected-pair default-service candidate"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_selected_pair_promotion_gate_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_selected_pair_promotion_gate_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_PAIR_PROMOTION_MIN_BATCH_COUNT:-16' scripts/probes/dream7b_bpu_selected_pair_promotion_gate_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_selected_pair_promotion_gate_probe.sh missing default DREAM7B_BPU_SELECTED_PAIR_PROMOTION_MIN_BATCH_COUNT:-16")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_PAIR_PROMOTION_MIN_WALL_DELTA_RATIO:-0.05' scripts/probes/dream7b_bpu_selected_pair_promotion_gate_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_selected_pair_promotion_gate_probe.sh missing default DREAM7B_BPU_SELECTED_PAIR_PROMOTION_MIN_WALL_DELTA_RATIO:-0.05")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_PAIR_PROMOTION_MIN_AVG_BPU_DELTA:-1.0' scripts/probes/dream7b_bpu_selected_pair_promotion_gate_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_selected_pair_promotion_gate_probe.sh missing default DREAM7B_BPU_SELECTED_PAIR_PROMOTION_MIN_AVG_BPU_DELTA:-1.0")
  fi
fi

if [[ -f scripts/dream7b-bpu-selected-pair-batch-forward.sh ]]; then
  for text in \
    "DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_TOKENS_BATCH_JSON" \
    "DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_OUTPUT_DIR" \
    "DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_TOP_K" \
    "DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_REPORT_ROOT" \
    "DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_PROBE_CMD" \
    "DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_TIMEOUT_SEC" \
    "DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_TRIPLET_JSON" \
    "DREAM7B_BPU_SELECTED_PAIR_TRIPLET_JSON" \
    "--tokens-batch-json" \
    "--output-dir" \
    "DREAM7B_BPU_SELECTED_PAIR_TOKENS_BATCH_JSON" \
    "selected_pair_candidate" \
    "selected-pair-resident" \
    "summary.json" \
    "ok_dream7b_segmented_hbm_python_forward"; do
    if ! grep -F -- "$text" scripts/dream7b-bpu-selected-pair-batch-forward.sh >/dev/null; then
      errors+=("dream7b-bpu-selected-pair-batch-forward.sh missing $text")
    fi
  done
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_TOP_K:-3' scripts/dream7b-bpu-selected-pair-batch-forward.sh >/dev/null; then
    errors+=("dream7b-bpu-selected-pair-batch-forward.sh missing default DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_TOP_K:-3")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_PROBE_CMD:-dream7b-bpu-selected-pair-forward-path-probe' scripts/dream7b-bpu-selected-pair-batch-forward.sh >/dev/null; then
    errors+=("dream7b-bpu-selected-pair-batch-forward.sh missing default probe command")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_selected_pair_candidate_forward_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_FORWARD_CMD" \
    "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_BATCH_COUNT" \
    "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_TOP_K" \
    "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_TIMEOUT_SEC" \
    "selected_pair_candidate_forward_probe.json" \
    "selected_pair_candidate_forward_probe.md" \
    "ok_dream7b_bpu_selected_pair_candidate_forward_probe" \
    "dream7b-bpu-selected-pair-batch-forward" \
    "selected_pair_candidate" \
    "selected-pair-resident" \
    "selected_pair_covers_all_segments" \
    "wire this selected-pair candidate forward command into a guarded service candidate"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_selected_pair_candidate_forward_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_selected_pair_candidate_forward_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_FORWARD_CMD:-dream7b-bpu-selected-pair-batch-forward' scripts/probes/dream7b_bpu_selected_pair_candidate_forward_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_selected_pair_candidate_forward_probe.sh missing default forward command")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_BATCH_COUNT:-16' scripts/probes/dream7b_bpu_selected_pair_candidate_forward_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_selected_pair_candidate_forward_probe.sh missing default DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_BATCH_COUNT:-16")
  fi
fi

if [[ -f scripts/install_dream7b_bpu_selected_pair_candidate_service.sh ]]; then
  for text in \
    "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_SERVICE_NAME" \
    "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_POLL_INTERVAL_SEC" \
    "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_MAX_BATCH_SIZE" \
    "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_TOP_K" \
    "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_LOCK_PATH" \
    "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_REPO_DIR" \
    "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_FORWARD_CMD" \
    "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_DRAIN_ALL" \
    "dream7b-bpu-selected-pair-candidate.service" \
    "/mnt/nas/openclaw/queues/dream7b-bpu-selected-pair-candidate" \
    "/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_service_systemd" \
    "dream7b-bpu-selected-pair-batch-forward" \
    "/run/lock/dream7b_bpu_batch_queue_runner.lock" \
    "--forward-cmd" \
    "--max-batch-size" \
    "--drain-all" \
    "default_service_replaced: false" \
    "default_service_name: dream7b-bpu-batch-queue.service"; do
    if ! grep -F -- "$text" scripts/install_dream7b_bpu_selected_pair_candidate_service.sh >/dev/null; then
      errors+=("install_dream7b_bpu_selected_pair_candidate_service.sh missing $text")
    fi
  done
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_MAX_BATCH_SIZE:-16' scripts/install_dream7b_bpu_selected_pair_candidate_service.sh >/dev/null; then
    errors+=("install_dream7b_bpu_selected_pair_candidate_service.sh missing default DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_MAX_BATCH_SIZE:-16")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_FORWARD_CMD:-dream7b-bpu-selected-pair-batch-forward' scripts/install_dream7b_bpu_selected_pair_candidate_service.sh >/dev/null; then
    errors+=("install_dream7b_bpu_selected_pair_candidate_service.sh missing default selected-pair forward command")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_selected_pair_candidate_service_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_SERVICE_REQUEST_COUNT" \
    "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_SERVICE_TIMEOUT_SEC" \
    "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_SERVICE_POLL_INTERVAL_SEC" \
    "dream7b-bpu-selected-pair-candidate.service" \
    "/mnt/nas/openclaw/queues/dream7b-bpu-selected-pair-candidate" \
    "/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_service_systemd" \
    "dream7b-bpu-selected-pair-batch-forward" \
    "selected_pair_candidate_service_probe.json" \
    "selected_pair_candidate_service_probe.md" \
    "ok_dream7b_bpu_selected_pair_candidate_service_probe" \
    "selected-pair-resident" \
    "child_process_count" \
    "selected_pair_candidate" \
    "default_service_replaced" \
    "default_service_status" \
    "default_service_enabled" \
    "selected_segments" \
    "selected_pair_covers_all_segments" \
    "amortized_wall_ms_per_processed_request"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_selected_pair_candidate_service_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_selected_pair_candidate_service_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_SERVICE_REQUEST_COUNT:-16' scripts/probes/dream7b_bpu_selected_pair_candidate_service_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_selected_pair_candidate_service_probe.sh missing default DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_SERVICE_REQUEST_COUNT:-16")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_selected_pair_cross_job_reuse_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_MODEL_REPORT_ROOT" \
    "DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_FORWARD_PROBE_CMD" \
    "DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_COUNT" \
    "DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_BATCH_COUNT" \
    "DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_TOP_K" \
    "DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_TIMEOUT_SEC" \
    "dream7b-bpu-selected-pair-forward-path-probe" \
    "dream7b_bpu_selected_pair_cross_job_reuse_" \
    "selected_pair_cross_job_reuse_probe.json" \
    "selected_pair_cross_job_reuse_probe.md" \
    "ok_dream7b_bpu_selected_pair_cross_job_reuse_probe" \
    "candidate_service_telemetry_path" \
    "resident_load_once_amortized_ms_per_forward" \
    "comparison_to_selected_pair_candidate_service" \
    "cross_job_reuses_selected_pair_workers_once" \
    "candidate_service_reloads_selected_pair_per_batch" \
    "cross_job_load_time_improved" \
    "cross_job_wall_time_improved" \
    "do not promote cross-job selected-pair reuse until telemetry shows amortized wall/load improvement"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_selected_pair_cross_job_reuse_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_selected_pair_cross_job_reuse_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_COUNT:-3' scripts/probes/dream7b_bpu_selected_pair_cross_job_reuse_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_selected_pair_cross_job_reuse_probe.sh missing default DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_COUNT:-3")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_BATCH_COUNT:-16' scripts/probes/dream7b_bpu_selected_pair_cross_job_reuse_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_selected_pair_cross_job_reuse_probe.sh missing default DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_BATCH_COUNT:-16")
  fi
fi

if [[ -f scripts/probes/s100_official_llm_baseline_probe.sh ]]; then
  for text in \
    "S100_OFFICIAL_LLM_SDK_ROOT" \
    "S100_OFFICIAL_LLM_DREAM_REPORT_ROOT" \
    "S100_OFFICIAL_LLM_DOC_URL" \
    "official_llm_baseline_probe.json" \
    "official_llm_baseline_probe.md" \
    "ok_s100_official_llm_baseline_probe" \
    "resolve_model_nash-m.txt" \
    "qwen_multichat_config.json" \
    "supported_model_names_from_resolve_model" \
    "official_hbm_download_entry_count" \
    "qwen_existing_hbm_count" \
    "official_qwen_local_runtime_report_present" \
    "similar_issue_evidence_available_for_official_qwen" \
    "comparison_to_dream" \
    "runtime_telemetry.load_to_run_ratio" \
    "systemd_telemetry.load_to_run_ratio" \
    "next_probe_target"; do
    if ! grep -F -- "$text" scripts/probes/s100_official_llm_baseline_probe.sh >/dev/null; then
      errors+=("s100_official_llm_baseline_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'D-Robotics_LLM_S100_1.0.0_SDK' scripts/probes/s100_official_llm_baseline_probe.sh >/dev/null; then
    errors+=("s100_official_llm_baseline_probe.sh missing D-Robotics_LLM_S100_1.0.0_SDK")
  fi
  if ! grep -F -- 'https://developer.d-robotics.cc/rdk_doc/rdk_s/Advanced_development/toolchain_development/LLM_Toolchain/' scripts/probes/s100_official_llm_baseline_probe.sh >/dev/null; then
    errors+=("s100_official_llm_baseline_probe.sh missing official LLM toolchain doc URL")
  fi
fi

if [[ -f scripts/probes/s100_official_qwen_fullflow_probe.sh ]]; then
  for text in \
    "S100_OFFICIAL_QWEN_FULLFLOW_SDK_ROOT" \
    "S100_OFFICIAL_QWEN_FULLFLOW_SOURCE_MODEL_DIR" \
    "S100_OFFICIAL_QWEN_FULLFLOW_OUTPUT_MODEL_PATH" \
    "S100_OFFICIAL_QWEN_FULLFLOW_MODEL_NAME" \
    "S100_OFFICIAL_QWEN_FULLFLOW_MARCH" \
    "S100_OFFICIAL_QWEN_FULLFLOW_CACHE_LEN" \
    "S100_OFFICIAL_QWEN_FULLFLOW_CHUNK_SIZE" \
    "official_qwen_fullflow_probe.json" \
    "official_qwen_fullflow_probe.md" \
    "ok_s100_official_qwen_fullflow_probe" \
    "qwen2_5-1_5b" \
    "nash-m" \
    "/mnt/nas/openclaw/models/s100-official-qwen-fullflow" \
    "/mnt/f/Project/Digua/tmp/s100_llm_sdk/inspect/D-Robotics_LLM_S100_1.0.0_SDK" \
    "/mnt/f/Project/Digua/tmp/models/s100-official-qwen-fullflow" \
    "qwen_fullflow_config.json" \
    "oellm_build.stdout.txt" \
    "oellm_multichat.stdout.txt" \
    "hrt_ucp_monitor.stdout" \
    "build_host_compatible" \
    "compiled_hbm_path" \
    "isolated_runtime_config_written" \
    "runtime_attempted" \
    "fullflow_completed" \
    "memory_alloc_failure_observed" \
    "next_probe_target"; do
    if ! grep -F -- "$text" scripts/probes/s100_official_qwen_fullflow_probe.sh >/dev/null; then
      errors+=("s100_official_qwen_fullflow_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'S100_OFFICIAL_QWEN_FULLFLOW_CACHE_LEN:-512' scripts/probes/s100_official_qwen_fullflow_probe.sh >/dev/null; then
    errors+=("s100_official_qwen_fullflow_probe.sh missing default S100_OFFICIAL_QWEN_FULLFLOW_CACHE_LEN:-512")
  fi
  if ! grep -F -- 'S100_OFFICIAL_QWEN_FULLFLOW_CHUNK_SIZE:-128' scripts/probes/s100_official_qwen_fullflow_probe.sh >/dev/null; then
    errors+=("s100_official_qwen_fullflow_probe.sh missing default S100_OFFICIAL_QWEN_FULLFLOW_CHUNK_SIZE:-128")
  fi
  for text in \
    "qwen_fullflow_wsl_build_report_20260609-081247" \
    "s100_official_qwen_fullflow_20260609-172710" \
    "source_model_exists: true" \
    "compiled_hbm_size_bytes: 1917926648" \
    "isolated_runtime_config_written: true" \
    "runtime_attempted: true" \
    "hbm_load_success_observed: true" \
    "memory_alloc_failure_observed: true"; do
    if ! grep -F -- "$text" README.md >/dev/null; then
      errors+=("README.md missing Qwen fullflow build/runtime evidence: $text")
    fi
    if ! grep -F -- "$text" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
      errors+=("Dream 7B segmented progress doc missing Qwen fullflow build/runtime evidence: $text")
    fi
    if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
      errors+=("docs/project_reference.md missing Qwen fullflow build/runtime evidence: $text")
    fi
  done
  for text in \
    "cache_len: 512" \
    "chunk_size: 128" \
    "/mnt/nas/openclaw/models/s100-official-qwen-fullflow/cache_len_512_chunk_128/qwen2_5-1_5b_chunk_128_cache_512_q8.hbm" \
    "/mnt/nas/openclaw/reports/models/s100_official_qwen_fullflow_20260609-210514/official_qwen_fullflow_probe.json" \
    "/mnt/nas/openclaw/reports/models/s100_qwen15_common_buffer_diagnosis_20260609-211000/s100_qwen15_common_buffer_diagnosis_20260609.md" \
    "runtime_completed: true" \
    "runtime_returncode: 0" \
    "memory_alloc_failure_observed: false" \
    "Performance prefill: 1024.00tokens/s    decode: 25.57tokens/s" \
    "high-context failure"; do
    if ! grep -F -- "$text" README.md >/dev/null; then
      errors+=("README.md missing Qwen 512/128 runnable baseline evidence: $text")
    fi
    if ! grep -F -- "$text" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
      errors+=("Dream 7B segmented progress doc missing Qwen 512/128 runnable baseline evidence: $text")
    fi
    if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
      errors+=("docs/project_reference.md missing Qwen 512/128 runnable baseline evidence: $text")
    fi
    if ! grep -F -- "$text" docs/dream7b_s100p_bpu_handoff_2026-06-09.md >/dev/null; then
      errors+=("Dream 7B handoff doc missing Qwen 512/128 runnable baseline evidence: $text")
    fi
  done
fi

if [[ -f scripts/probes/s100_official_deepseek7b_baseline_probe.sh ]]; then
  for text in \
    "S100_OFFICIAL_DEEPSEEK7B_SDK_ROOT" \
    "S100_OFFICIAL_DEEPSEEK7B_MODEL_DIR" \
    "S100_OFFICIAL_DEEPSEEK7B_HBM_URL" \
    "S100_OFFICIAL_DEEPSEEK7B_RUN_DOWNLOAD" \
    "S100_OFFICIAL_DEEPSEEK7B_RUN_RUNTIME" \
    "S100_OFFICIAL_DEEPSEEK7B_RUNTIME_TIMEOUT_SECONDS" \
    "DeepSeek_R1_Distill_Qwen_7B_1024.hbm" \
    "deepseek7b_baseline_probe.json" \
    "deepseek7b_baseline_probe.md" \
    "isolated_runtime_config" \
    "hrt_ucp_monitor.stdout" \
    "bpu_alloc_request_bytes" \
    "official_7b_runtime_blocked_common_buffer" \
    "qwen_1_5b_512_128" \
    "dream7b_segmented"; do
    if ! grep -F -- "$text" scripts/probes/s100_official_deepseek7b_baseline_probe.sh >/dev/null; then
      errors+=("s100_official_deepseek7b_baseline_probe.sh missing $text")
    fi
  done
  for text in \
    "scripts/probes/s100_official_deepseek7b_baseline_probe.sh" \
    "/mnt/nas/openclaw/reports/models/s100_official_deepseek7b_baseline_20260610-023455/deepseek7b_baseline_probe.json" \
    "/mnt/nas/openclaw/models/s100-official-deepseek-r1-distill-qwen-7b/DeepSeek_R1_Distill_Qwen_7B_1024.hbm" \
    "hbm_size_bytes: 7928846896" \
    "runtime_status: failed" \
    "runtime_returncode: 1" \
    "runtime_completed: False" \
    "hbm_load_success_observed: False" \
    "init_model_success_observed: False" \
    "memory_alloc_failure_observed: True" \
    "bpu_alloc_request_bytes: 7928846896" \
    "decision: official_7b_runtime_blocked_common_buffer" \
    'Qwen2.5-1.5B `512/128` remains the verified official runnable fallback'; do
    if ! grep -F -- "$text" README.md >/dev/null; then
      errors+=("README.md missing DeepSeek 7B fallback evidence: $text")
    fi
    if ! grep -F -- "$text" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
      errors+=("Dream 7B segmented progress doc missing DeepSeek 7B fallback evidence: $text")
    fi
    if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
      errors+=("docs/project_reference.md missing DeepSeek 7B fallback evidence: $text")
    fi
    if ! grep -F -- "$text" docs/dream7b_s100p_bpu_handoff_2026-06-09.md >/dev/null; then
      errors+=("Dream 7B handoff doc missing DeepSeek 7B fallback evidence: $text")
    fi
    if ! grep -F -- "$text" docs/deepseek7b_s100p_fallback_decision_2026-06-10.md >/dev/null; then
      errors+=("DeepSeek 7B decision doc missing fallback evidence: $text")
    fi
  done
fi

if [[ -f scripts/probes/s100_official_qwen_runtime_probe.sh ]]; then
  for text in \
    "S100_OFFICIAL_QWEN_RUNTIME_SDK_ROOT" \
    "S100_OFFICIAL_QWEN_RUNTIME_DREAM_REPORT_ROOT" \
    "S100_OFFICIAL_QWEN_RUNTIME_TIMEOUT_SECONDS" \
    "official_qwen_runtime_probe.json" \
    "official_qwen_runtime_probe.md" \
    "ok_s100_official_qwen_runtime_probe" \
    "qwen_multichat_config.json" \
    "LD_LIBRARY_PATH" \
    "runtime_returncode" \
    "runtime_completed" \
    "hbm_load_success_observed" \
    "prefill_model_load_success_observed" \
    "decode_model_load_success_observed" \
    "init_model_success_observed" \
    "memory_alloc_failure_observed" \
    "ion_alloc_failure_observed" \
    "bpu_mem_pool_alloc_error_observed" \
    "segmentation_fault_observed" \
    "official_qwen_runtime_supported_on_current_s100p_state" \
    "same_failure_class_as_dream" \
    "performance_mode_script_action" \
    "inspected_not_applied" \
    "next_probe_target"; do
    if ! grep -F -- "$text" scripts/probes/s100_official_qwen_runtime_probe.sh >/dev/null; then
      errors+=("s100_official_qwen_runtime_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'S100_OFFICIAL_QWEN_RUNTIME_TIMEOUT_SECONDS:-60' scripts/probes/s100_official_qwen_runtime_probe.sh >/dev/null; then
    errors+=("s100_official_qwen_runtime_probe.sh missing default S100_OFFICIAL_QWEN_RUNTIME_TIMEOUT_SECONDS:-60")
  fi
  if ! grep -F -- 'D-Robotics_LLM_S100_1.0.0_SDK' scripts/probes/s100_official_qwen_runtime_probe.sh >/dev/null; then
    errors+=("s100_official_qwen_runtime_probe.sh missing D-Robotics_LLM_S100_1.0.0_SDK")
  fi
fi

if [[ -f scripts/probes/s100_bpu_memory_pool_probe.sh ]]; then
  for text in \
    "S100_BPU_MEMORY_POOL_SDK_ROOT" \
    "S100_BPU_MEMORY_POOL_RELATED_REPORT_ROOT" \
    "bpu_memory_pool_probe.json" \
    "bpu_memory_pool_probe.md" \
    "ok_s100_bpu_memory_pool_probe" \
    "performance_mode_script_action" \
    "inspected_not_applied" \
    "default_devmem_path" \
    "sudo_devmem_path" \
    "busybox_devmem_returncode" \
    "perf_register_0x2b047000" \
    "perf_register_0x2b047004" \
    "performance_mode_target_applied_from_latest_retest" \
    "latest_performance_mode_retest_memory_alloc_failure_observed" \
    "ion_debug_present" \
    "ion_all_heap_info_exists" \
    "ion_heap_total_sizes" \
    "ion_heap_allocated_totals" \
    "ion_heap_available_estimates" \
    "ion_heap_bpu_allocation_counts" \
    "ion_heap_bpu_allocation_sizes" \
    "system_heap_total_size" \
    "system_contig_heap_total_size" \
    "carveout_heap_total_size" \
    "cma_reserved_heap_total_size" \
    "ion_cma_heap_total_size" \
    "ion_client_bpu_0_total_line" \
    "iovmm_bpu" \
    "iovmm_bpu_hp" \
    "reserved_memory_nodes.json" \
    "reserved_memory_summary" \
    "bpu_region" \
    "ion_reserved" \
    "allocation_failure_interpretation" \
    "minimal HBMEM/UCP common-buffer allocation matrix" \
    "ion_meminfo_shebang" \
    "ion_meminfo_shebang_interpreter_exists" \
    "ion_meminfo_fallback_returncode" \
    "memstat_shebang" \
    "memstat_shebang_interpreter_exists" \
    "memstat_fallback_returncode" \
    "latest_official_qwen_memory_alloc_failure_observed" \
    "latest_dream_diagnosis" \
    "next_probe_target"; do
    if ! grep -F -- "$text" scripts/probes/s100_bpu_memory_pool_probe.sh >/dev/null; then
      errors+=("s100_bpu_memory_pool_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'D-Robotics_LLM_S100_1.0.0_SDK' scripts/probes/s100_bpu_memory_pool_probe.sh >/dev/null; then
    errors+=("s100_bpu_memory_pool_probe.sh missing D-Robotics_LLM_S100_1.0.0_SDK")
  fi
fi

if [[ -f scripts/probes/s100_hbmem_common_buffer_matrix_probe.sh ]]; then
  for text in \
    "S100_HBMEM_MATRIX_SDK_ROOT" \
    "hb_mem_alloc_com_buf" \
    "hb_mem_free_buf" \
    "hbUCPMalloc" \
    "hbUCPMallocCached" \
    "786432" \
    "2359296" \
    "hbmem_common_buffer_matrix.jsonl" \
    "hbmem_common_buffer_matrix_probe.json" \
    "hbmem_common_buffer_matrix_probe.md" \
    "ok_s100_hbmem_common_buffer_matrix_probe" \
    "qwen_log_sizes" \
    "qwen_log_size_success_count" \
    "qwen_log_size_failure_count" \
    "ucp_success_count" \
    "backend: 9" \
    "libhbucp" \
    "HB_MEM_USAGE_HW_BPU" \
    "HB_MEM_USAGE_PRIV_HEAP_DMA" \
    "HB_MEM_USAGE_PRIV_HEAP_RESERVED" \
    "HB_MEM_USAGE_PRIV_HEAP_2_RESERVED"; do
    if ! grep -F -- "$text" scripts/probes/s100_hbmem_common_buffer_matrix_probe.sh >/dev/null; then
      errors+=("s100_hbmem_common_buffer_matrix_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'D-Robotics_LLM_S100_1.0.0_SDK' scripts/probes/s100_hbmem_common_buffer_matrix_probe.sh >/dev/null; then
    errors+=("s100_hbmem_common_buffer_matrix_probe.sh missing D-Robotics_LLM_S100_1.0.0_SDK")
  fi
fi

if [[ -f scripts/probes/s100_qwen_backend9_baseline_probe.sh ]]; then
  for text in \
    "S100_QWEN_BACKEND9_SDK_ROOT" \
    "qwen_multichat_config.json" \
    "oellm_multichat_demo.cc" \
    "libhbucp.so" \
    "/usr/include/hobot/hb_ucp.h" \
    "bpu_core" \
    "XLM_INFER_BACKEND_BPU_ANY" \
    "backend:" \
    "backend_9_equals_hb_ucp_bpu_core_any" \
    "HB_UCP_BPU_CORE_ANY" \
    "Allocate memory failed" \
    "AllocError" \
    "ION_IOC_ALLOC" \
    "qwen_backend9_baseline_probe.json" \
    "qwen_backend9_baseline_probe.md" \
    "ok_s100_qwen_backend9_baseline_probe" \
    "observed_backend_values" \
    "observed_ucp_alloc_failure_sizes" \
    "direct_hbmem_matrix_qwen_sizes_pass" \
    "official_qwen_has_similar_bpu_memory_issue" \
    "official_qwen_issue_not_raw_size_only" \
    "dream_diagnosis" \
    "run a controlled official Qwen bpu_core sweep"; do
    if ! grep -F -- "$text" scripts/probes/s100_qwen_backend9_baseline_probe.sh >/dev/null; then
      errors+=("s100_qwen_backend9_baseline_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'D-Robotics_LLM_S100_1.0.0_SDK' scripts/probes/s100_qwen_backend9_baseline_probe.sh >/dev/null; then
    errors+=("s100_qwen_backend9_baseline_probe.sh missing D-Robotics_LLM_S100_1.0.0_SDK")
  fi
fi

if [[ -f scripts/probes/s100_qwen_bpu_core_sweep_probe.sh ]]; then
  for text in \
    "S100_QWEN_BPU_CORE_SWEEP_SDK_ROOT" \
    "S100_QWEN_BPU_CORE_SWEEP_TIMEOUT_SECONDS" \
    "S100_QWEN_BPU_CORE_SWEEP_CORES" \
    "qwen_multichat_config.json" \
    "oellm_multichat_demo.cc" \
    "/usr/include/hobot/hb_ucp.h" \
    "bpu_core" \
    "-1 0 1 2 3" \
    "qwen_bpu_core_sweep_probe.json" \
    "qwen_bpu_core_sweep_probe.md" \
    "ok_s100_qwen_bpu_core_sweep_probe" \
    "backend_values_by_core" \
    "memory_alloc_failure_by_core" \
    "runtime_completed_by_core" \
    "segmentation_fault_by_core" \
    "functional_failure_by_core" \
    "functional_success_by_core" \
    "prefill_failure_by_core" \
    "all_cases_failed_functionally" \
    "any_case_functional_success" \
    "functional_success_observed" \
    "prefill_failure_observed" \
    "hbUCPSubmitTask" \
    "DnnModelInfer prefill failed" \
    "core pinning alone is not sufficient"; do
    if ! grep -F -- "$text" scripts/probes/s100_qwen_bpu_core_sweep_probe.sh >/dev/null; then
      errors+=("s100_qwen_bpu_core_sweep_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'D-Robotics_LLM_S100_1.0.0_SDK' scripts/probes/s100_qwen_bpu_core_sweep_probe.sh >/dev/null; then
    errors+=("s100_qwen_bpu_core_sweep_probe.sh missing D-Robotics_LLM_S100_1.0.0_SDK")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_scheduling_params_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_SCHEDULING_PARAMS_PYTHON" \
    "DREAM7B_BPU_SCHEDULING_PARAMS_HBM" \
    "DREAM7B_BPU_SCHEDULING_PARAMS_CORES" \
    "DREAM7B_BPU_SCHEDULING_PARAMS_TIMEOUT_SECONDS" \
    "/mnt/nas/openclaw/runtimes/hbm-runtime-venv/bin/python" \
    "/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16/seg00_02/dream7b_segment_0_2_seq16_q8.hbm" \
    "HB_HBMRuntime" \
    "set_scheduling_params" \
    "bpu_cores" \
    "schedule backend unsupported" \
    "scheduling_params_probe.json" \
    "scheduling_params_probe.md" \
    "ok_dream7b_bpu_scheduling_params_probe" \
    "run_ok_by_core" \
    "returncode_by_core" \
    "schedule_backend_unsupported_by_core" \
    "abort_by_core" \
    "core0_explicit_supported" \
    "nonzero_cores_supported" \
    "model-specific scheduling constraint"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_scheduling_params_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_scheduling_params_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'DREAM7B_BPU_SCHEDULING_PARAMS_CORES:-default 0 1 2 3' scripts/probes/dream7b_bpu_scheduling_params_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_scheduling_params_probe.sh missing default DREAM7B_BPU_SCHEDULING_PARAMS_CORES:-default 0 1 2 3")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SCHEDULING_PARAMS_TIMEOUT_SECONDS:-30' scripts/probes/dream7b_bpu_scheduling_params_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_scheduling_params_probe.sh missing default DREAM7B_BPU_SCHEDULING_PARAMS_TIMEOUT_SECONDS:-30")
  fi
fi

if [[ -f scripts/probes/dream7b_oellm_fullflow_feasibility_probe.sh ]]; then
  for text in \
    "DREAM7B_OELLM_FULLFLOW_SDK_OELLM_BUILD" \
    "DREAM7B_OELLM_FULLFLOW_MODEL_DIR" \
    "DREAM7B_OELLM_FULLFLOW_OUTPUT_DIR" \
    "DREAM7B_OELLM_FULLFLOW_COMPILE_SCRIPT" \
    "DREAM7B_OELLM_FULLFLOW_MARCH" \
    "DREAM7B_OELLM_FULLFLOW_CHUNK_SIZE" \
    "DREAM7B_OELLM_FULLFLOW_CACHE_LEN" \
    "DREAM7B_OELLM_FULLFLOW_RUN_COMPILE" \
    "compile_dream_with_deepseek_skeleton.sh" \
    "dream7b_oellm_fullflow_feasibility_probe.json" \
    "dream7b_oellm_fullflow_feasibility_probe.md" \
    "ok_dream7b_oellm_fullflow_feasibility_probe" \
    "leap_llm_model_factory_registry.txt" \
    "dream_registered_in_official_sdk" \
    "supported_models_from_sdk" \
    "dream_config_summary" \
    "build_host_compatible" \
    "compile_status" \
    "compiled_hbm_count" \
    "direct_oellm_migration_supported" \
    "failure_stage" \
    "minimal_failure_package" \
    "next_probe_target"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_oellm_fullflow_feasibility_probe.sh >/dev/null; then
      errors+=("dream7b_oellm_fullflow_feasibility_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'DREAM7B_OELLM_FULLFLOW_MARCH:-nash-m' scripts/probes/dream7b_oellm_fullflow_feasibility_probe.sh >/dev/null; then
    errors+=("dream7b_oellm_fullflow_feasibility_probe.sh missing default DREAM7B_OELLM_FULLFLOW_MARCH:-nash-m")
  fi
  if ! grep -F -- 'DREAM7B_OELLM_FULLFLOW_CACHE_LEN:-512' scripts/probes/dream7b_oellm_fullflow_feasibility_probe.sh >/dev/null; then
    errors+=("dream7b_oellm_fullflow_feasibility_probe.sh missing default DREAM7B_OELLM_FULLFLOW_CACHE_LEN:-512")
  fi
  if ! grep -F -- 'DREAM7B_OELLM_FULLFLOW_CHUNK_SIZE:-128' scripts/probes/dream7b_oellm_fullflow_feasibility_probe.sh >/dev/null; then
    errors+=("dream7b_oellm_fullflow_feasibility_probe.sh missing default DREAM7B_OELLM_FULLFLOW_CHUNK_SIZE:-128")
  fi
  for text in \
    "blocked_registry_missing" \
    "registry_missing" \
    "missing_adapter_evidence" \
    "unable_to_attempt_direct_official_compile_reason"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_oellm_fullflow_feasibility_probe.sh >/dev/null; then
      errors+=("dream7b_oellm_fullflow_feasibility_probe.sh missing registry-missing failure-package field: $text")
    fi
  done
  for text in \
    "dream7b_oellm_fullflow_feasibility_20260609-223754" \
    "build_host_compatible: true" \
    "dream_registered_in_official_sdk: false" \
    "compile_status: blocked_registry_missing" \
    "failure_stage: registry_missing" \
    "compiled_hbm_count: 0" \
    "direct_oellm_migration_supported: false" \
    "missing_adapter_evidence.registry_missing: true" \
    "missing_adapter_evidence.required_adapter: official leap_llm model_factory registration and Dream/DreamModel adapter" \
    "unable_to_attempt_direct_official_compile_reason" \
    "model_type: Dream" \
    "architectures: ['DreamModel']" \
    "hidden_size: 3584" \
    "num_hidden_layers: 28" \
    "num_attention_heads: 28" \
    "num_key_value_heads: 4" \
    "vocab_size: 152064" \
    "mask_token_id: 151666" \
    "torch_dtype: bfloat16" \
    "use_cache: true"; do
    if ! grep -F -- "$text" README.md >/dev/null; then
      errors+=("README.md missing current Dream OELLM registry-missing evidence: $text")
    fi
    if ! grep -F -- "$text" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
      errors+=("Dream 7B segmented progress doc missing current Dream OELLM registry-missing evidence: $text")
    fi
    if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
      errors+=("docs/project_reference.md missing current Dream OELLM registry-missing evidence: $text")
    fi
    if ! grep -F -- "$text" docs/dream7b_s100p_bpu_handoff_2026-06-09.md >/dev/null; then
      errors+=("Dream 7B handoff doc missing current Dream OELLM registry-missing evidence: $text")
    fi
  done
  for text in \
    "deepseek-qwen-1_5b" \
    "deepseek-qwen-7b" \
    "qwen2_5-1_5b" \
    "qwen2_5-7b" \
    "internvl2-2b" \
    "internvl2_5-2b" \
    "internvl2-1b" \
    "internvl2_5-1b" \
    "internlm2-1_8b" \
    "qwen2_5-omni-3b"; do
    if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
      errors+=("docs/project_reference.md missing current Dream OELLM supported model entry: $text")
    fi
  done
fi

if [[ -f scripts/probes/s100_official_qwen_performance_mode_retest_probe.sh ]]; then
  for text in \
    "S100_OFFICIAL_QWEN_PERF_RETEST_RUNTIME_PROBE" \
    "S100_OFFICIAL_QWEN_PERF_RETEST_DEVMEM_BIN" \
    "S100_OFFICIAL_QWEN_PERF_RETEST_TARGET_VALUE" \
    "performance_mode_retest_probe.json" \
    "performance_mode_retest_probe.md" \
    "ok_s100_official_qwen_performance_mode_retest_probe" \
    "0x2b047000" \
    "0x2b047004" \
    "0x00000099" \
    "/usr/bin/devmem" \
    "target_applied" \
    "runtime_completed_after_performance_mode" \
    "memory_alloc_failure_observed_after_performance_mode" \
    "hbm_load_success_observed_after_performance_mode" \
    "init_model_success_observed_after_performance_mode" \
    "next_probe_target"; do
    if ! grep -F -- "$text" scripts/probes/s100_official_qwen_performance_mode_retest_probe.sh >/dev/null; then
      errors+=("s100_official_qwen_performance_mode_retest_probe.sh missing $text")
    fi
  done
  if ! grep -F -- 'S100_OFFICIAL_QWEN_PERF_RETEST_TARGET_VALUE:-0x99' scripts/probes/s100_official_qwen_performance_mode_retest_probe.sh >/dev/null; then
    errors+=("s100_official_qwen_performance_mode_retest_probe.sh missing default S100_OFFICIAL_QWEN_PERF_RETEST_TARGET_VALUE:-0x99")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_QUEUE_RETENTION_DONE_DAYS" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing DREAM7B_BPU_QUEUE_RETENTION_DONE_DAYS")
  fi
  if ! grep -F -- 'DREAM7B_BPU_QUEUE_RETENTION_DONE_DAYS:-14' scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing default DREAM7B_BPU_QUEUE_RETENTION_DONE_DAYS:-14")
  fi
  if ! grep -F -- "DREAM7B_BPU_QUEUE_RETENTION_FAILED_DAYS" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing DREAM7B_BPU_QUEUE_RETENTION_FAILED_DAYS")
  fi
  if ! grep -F -- 'DREAM7B_BPU_QUEUE_RETENTION_FAILED_DAYS:-30' scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing default DREAM7B_BPU_QUEUE_RETENTION_FAILED_DAYS:-30")
  fi
  if ! grep -F -- "DREAM7B_BPU_QUEUE_RETENTION_PENDING_STALE_MINUTES" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing DREAM7B_BPU_QUEUE_RETENTION_PENDING_STALE_MINUTES")
  fi
  if ! grep -F -- "DREAM7B_BPU_QUEUE_RETENTION_PROCESSING_STALE_MINUTES" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing DREAM7B_BPU_QUEUE_RETENTION_PROCESSING_STALE_MINUTES")
  fi
  if ! grep -F -- "DREAM7B_BPU_QUEUE_RETENTION_MAX_LIST" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing DREAM7B_BPU_QUEUE_RETENTION_MAX_LIST")
  fi
  if ! grep -F -- "policy_mode" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing policy_mode")
  fi
  if ! grep -F -- "report_only" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing report_only")
  fi
  if ! grep -F -- "apply_supported" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing apply_supported")
  fi
  if ! grep -F -- "archive_plan" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing archive_plan")
  fi
  if ! grep -F -- "pending_stale_count" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing pending_stale_count")
  fi
  if ! grep -F -- "processing_stale_count" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing processing_stale_count")
  fi
  if ! grep -F -- "done_archive_candidate_count" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing done_archive_candidate_count")
  fi
  if ! grep -F -- "failed_archive_candidate_count" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing failed_archive_candidate_count")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_batch_queue_systemd_canary_probe.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_SYSTEMD_CANARY_REQUEST_COUNT" scripts/probes/dream7b_bpu_batch_queue_systemd_canary_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_canary_probe.sh missing DREAM7B_BPU_SYSTEMD_CANARY_REQUEST_COUNT")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SYSTEMD_CANARY_REQUEST_COUNT:-1' scripts/probes/dream7b_bpu_batch_queue_systemd_canary_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_canary_probe.sh missing default DREAM7B_BPU_SYSTEMD_CANARY_REQUEST_COUNT:-1")
  fi
  if ! grep -F -- "DREAM7B_BPU_SYSTEMD_CANARY_TIMEOUT_SEC" scripts/probes/dream7b_bpu_batch_queue_systemd_canary_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_canary_probe.sh missing DREAM7B_BPU_SYSTEMD_CANARY_TIMEOUT_SEC")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SYSTEMD_CANARY_TIMEOUT_SEC:-180' scripts/probes/dream7b_bpu_batch_queue_systemd_canary_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_canary_probe.sh missing default DREAM7B_BPU_SYSTEMD_CANARY_TIMEOUT_SEC:-180")
  fi
  if ! grep -F -- "DREAM7B_BPU_SYSTEMD_CANARY_POLL_INTERVAL_SEC" scripts/probes/dream7b_bpu_batch_queue_systemd_canary_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_canary_probe.sh missing DREAM7B_BPU_SYSTEMD_CANARY_POLL_INTERVAL_SEC")
  fi
  for text in \
    "systemd_canary_probe.json" \
    "systemd_canary_probe.md" \
    "ok_dream7b_bpu_batch_queue_systemd_canary_probe" \
    "dream7b-bpu-batch-queue.service" \
    "/mnt/nas/openclaw/queues/dream7b-bpu" \
    "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd" \
    "/run/lock/dream7b_bpu_batch_queue_runner.lock" \
    "--max-batch-size 16" \
    "--drain-all" \
    "final_shapes" \
    "bpu_lock_path" \
    "pair_window_batch" \
    "window-batch"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_batch_queue_systemd_canary_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_batch_queue_systemd_canary_probe.sh missing $text")
    fi
  done
fi

if [[ -f scripts/dream7b-bpu-text-queue-submit.sh ]]; then
  for text in \
    "DREAM7B_TOKENIZER_VENV" \
    "DREAM7B_TOKENIZER" \
    "DREAM7B_BPU_TEXT_QUEUE_DIR" \
    "DREAM7B_BPU_TEXT_QUEUE_SUBMIT_REPORT_ROOT" \
    "DREAM7B_BPU_TEXT_QUEUE_SUBMIT_RUN_DIR" \
    "DREAM7B_BPU_TEXT_QUEUE_SEQ_LEN" \
    "DREAM7B_BPU_TEXT_QUEUE_FIT" \
    "--queue-dir" \
    "--report-root" \
    "--run-dir" \
    "--job-stem" \
    "--request-id" \
    "--prompt-file" \
    "tokenizer_input.json" \
    "text_queue_submit.json" \
    "text_queue_submit.md" \
    "ok_dream7b_bpu_text_queue_submit" \
    "queue_pending_path" \
    "/mnt/nas/openclaw/queues/dream7b-bpu" \
    "/mnt/nas/openclaw/reports/models"; do
    if ! grep -F -- "$text" scripts/dream7b-bpu-text-queue-submit.sh >/dev/null; then
      errors+=("dream7b-bpu-text-queue-submit.sh missing $text")
    fi
  done
fi

if [[ -f scripts/dream7b-bpu-text-queue-run.sh ]]; then
  for text in \
    "DREAM7B_BPU_TEXT_QUEUE_DIR" \
    "DREAM7B_BPU_TEXT_QUEUE_OUTPUT_DIR" \
    "DREAM7B_BPU_TEXT_QUEUE_RUN_REPORT_ROOT" \
    "DREAM7B_BPU_TEXT_QUEUE_RUN_DIR" \
    "DREAM7B_BPU_TEXT_QUEUE_SUBMIT_CMD" \
    "DREAM7B_BPU_TEXT_QUEUE_SEQ_LEN" \
    "DREAM7B_BPU_TEXT_QUEUE_FIT" \
    "DREAM7B_BPU_TEXT_QUEUE_TIMEOUT_SEC" \
    "DREAM7B_BPU_TEXT_QUEUE_POLL_INTERVAL_SEC" \
    "--output-dir" \
    "--report-root" \
    "--run-dir" \
    "--job-stem" \
    "--request-id" \
    "--timeout-sec" \
    "--poll-interval-sec" \
    "--prompt-file" \
    "text_queue_run.json" \
    "text_queue_run.md" \
    "text_queue_submit.json" \
    "ok_dream7b_bpu_text_queue_run" \
    "ok_dream7b_bpu_text_queue_submit" \
    "topk_last_position" \
    "topk_last_position_decoded" \
    "token_text" \
    "durable_results_jsonl" \
    "/run/lock/dream7b_bpu_batch_queue_runner.lock" \
    "/mnt/nas/openclaw/queues/dream7b-bpu" \
    "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd"; do
    if ! grep -F -- "$text" scripts/dream7b-bpu-text-queue-run.sh >/dev/null; then
      errors+=("dream7b-bpu-text-queue-run.sh missing $text")
    fi
  done
fi

if [[ -f scripts/dream7b-bpu-diffusion-generate.sh ]]; then
  for text in \
    "DREAM7B_TOKENIZER_VENV" \
    "DREAM7B_TOKENIZER" \
    "DREAM7B_BPU_DIFFUSION_GENERATE_REPORT_ROOT" \
    "DREAM7B_BPU_DIFFUSION_GENERATE_RUN_DIR" \
    "DREAM7B_BPU_DIFFUSION_GENERATE_SEQ_LEN" \
    "DREAM7B_BPU_DIFFUSION_GENERATE_MIN_MASK_COUNT" \
    "DREAM7B_BPU_DIFFUSION_GENERATE_STEPS" \
    "DREAM7B_BPU_DIFFUSION_GENERATE_TOP_K" \
    "DREAM7B_BPU_DIFFUSION_GENERATE_EPS" \
    "DREAM7B_BPU_DIFFUSION_GENERATE_REMASKING" \
    "DREAM7B_BPU_DIFFUSION_GENERATE_TEMP" \
    "DREAM7B_BPU_DIFFUSION_GENERATE_SEED" \
    "DREAM7B_BPU_DIFFUSION_GENERATE_ENTROPY_THRESHOLD" \
    "DREAM7B_BPU_DIFFUSION_GENERATE_FORWARD_CMD" \
    "dream7b-bpu-fine-forward" \
    "--prompt-file" \
    "--forward-cmd" \
    "generation.json" \
    "generation.md" \
    "ok_dream7b_bpu_diffusion_generate" \
    "decoded_final" \
    "remaining_mask_positions" \
    "forward_verdict" \
    "forward_execution_mode" \
    "forward_window_execution_mode" \
    "forward_child_process_count" \
    "forward_final_shape" \
    "bounded_seq16_generation_entrypoint_not_complete_production_text_service"; do
    if ! grep -F -- "$text" scripts/dream7b-bpu-diffusion-generate.sh >/dev/null; then
      errors+=("dream7b-bpu-diffusion-generate.sh missing $text")
    fi
  done
fi

if [[ -f scripts/dream7b-bpu-diffusion-batch-generate.sh ]]; then
  for text in \
    "DREAM7B_TOKENIZER_VENV" \
    "DREAM7B_TOKENIZER" \
    "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_REPORT_ROOT" \
    "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_RUN_DIR" \
    "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_BATCH_COUNT" \
    "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SEQ_LEN" \
    "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_MIN_MASK_COUNT" \
    "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_STEPS" \
    "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TOP_K" \
    "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_EPS" \
    "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_REMASKING" \
    "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TEMP" \
    "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SEED" \
    "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_ENTROPY_THRESHOLD" \
    "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_FORWARD_CMD" \
    "dream7b-bpu-fine-batch-forward" \
    "--prompts-json" \
    "--prompts-jsonl" \
    "--prompt" \
    "--tokens-batch-json" \
    "tokens_batch.json" \
    "batch_generation.json" \
    "batch_generation.md" \
    "ok_dream7b_bpu_diffusion_batch_generate" \
    "batch_count" \
    "decoded_final_by_batch" \
    "remaining_mask_positions_by_batch" \
    "forward_batch_count" \
    "forward_batch_counts" \
    "forward_final_shapes" \
    "pair_window_batch" \
    "window-batch" \
    "bounded_seq16_batch_generation_entrypoint_not_complete_production_text_service"; do
    if ! grep -F -- "$text" scripts/dream7b-bpu-diffusion-batch-generate.sh >/dev/null; then
      errors+=("dream7b-bpu-diffusion-batch-generate.sh missing $text")
    fi
  done
  if ! grep -F -- 'DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_BATCH_COUNT:-16' scripts/dream7b-bpu-diffusion-batch-generate.sh >/dev/null; then
    errors+=("dream7b-bpu-diffusion-batch-generate.sh missing default DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_BATCH_COUNT:-16")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_text_queue_systemd_probe.sh ]]; then
  for text in \
    "DREAM7B_TOKENIZER_VENV" \
    "DREAM7B_TOKENIZER" \
    "DREAM7B_BPU_TEXT_QUEUE_PROMPT" \
    "DREAM7B_BPU_TEXT_QUEUE_FIT" \
    "DREAM7B_BPU_TEXT_QUEUE_SEQ_LEN" \
    "DREAM7B_BPU_TEXT_QUEUE_TIMEOUT_SEC" \
    "DREAM7B_BPU_TEXT_QUEUE_POLL_INTERVAL_SEC" \
    "DREAM7B_BPU_TEXT_QUEUE_SUBMIT_CMD" \
    "DREAM7B_BPU_TEXT_QUEUE_RUN_CMD" \
    "dream7b-bpu-text-queue-submit" \
    "dream7b-bpu-text-queue-run" \
    "text_queue_run.json" \
    "text_queue_run.md" \
    "ok_dream7b_bpu_text_queue_run" \
    "run_cmd" \
    "run_verdict" \
    "text_queue_submit.json" \
    "text_queue_submit.md" \
    "ok_dream7b_bpu_text_queue_submit" \
    "submit_cmd" \
    "submit_json" \
    "submit_verdict" \
    "text_queue_systemd_probe.json" \
    "text_queue_systemd_probe.md" \
    "tokenizer_input.json" \
    "ok_dream7b_bpu_text_queue_systemd_probe" \
    "dream7b-bpu-batch-queue.service" \
    "/mnt/nas/openclaw/queues/dream7b-bpu" \
    "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd" \
    "/run/lock/dream7b_bpu_batch_queue_runner.lock" \
    "--max-batch-size 16" \
    "--top-k 3" \
    "--drain-all" \
    "topk_last_position" \
    "topk_last_position_decoded" \
    "token_text" \
    "durable_results_jsonl" \
    "pair_window_batch" \
    "window-batch"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_text_queue_systemd_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_text_queue_systemd_probe.sh missing $text")
    fi
  done
fi

if [[ -f scripts/probes/compile_dream_segments_seq16_resplit_probe.sh ]]; then
  for text in \
    "DREAM_RESPLIT_VENV" \
    "DREAM_RESPLIT_MODEL_DIR" \
    "DREAM_RESPLIT_OUTPUT_ROOT" \
    "DREAM_RESPLIT_SEQ_LEN" \
    "DREAM_RESPLIT_SPECS" \
    "DREAM_RESPLIT_EXPECTED_SPECS" \
    "DREAM_RESPLIT_ALLOW_PARTIAL" \
    "DREAM_RESPLIT_SKIP_EXISTING" \
    "DREAM_RESPLIT_SKIP_EXISTING:-1" \
    "0:1 1:2 10:12 12:14 17:19 19:21 26:27 27:28" \
    "skipped_existing" \
    "skipped_existing_count" \
    "ok_dream7b_resplit_compile_probe" \
    "manifest.sha256"; do
    if ! grep -F -- "$text" scripts/probes/compile_dream_segments_seq16_resplit_probe.sh >/dev/null; then
      errors+=("compile_dream_segments_seq16_resplit_probe.sh missing $text")
    fi
  done
  if ! grep -F -- "compile_dream_segments_seq16_resplit_probe.sh" README.md >/dev/null; then
    errors+=("README.md missing compile_dream_segments_seq16_resplit_probe.sh")
  fi
  if ! grep -F -- "compile_dream_segments_seq16_resplit_probe.sh" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing compile_dream_segments_seq16_resplit_probe.sh")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_resplit_hbm_artifact_inventory_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_RESPLIT_HBM_DIR" \
    "DREAM7B_BPU_RESPLIT_EXPECTED_SPECS" \
    "DREAM7B_BPU_RESPLIT_VERIFY_MANIFEST" \
    "DREAM7B_BPU_RESPLIT_HBM_DIR:-/mnt/nas/openclaw/models/dream7b-hbm/resplit-seq16" \
    "resplit-topwindow-seq16" \
    "DREAM7B_BPU_RESPLIT_VERIFY_MANIFEST:-1" \
    "0:1 1:2 10:12 12:14 17:19 19:21 26:27 27:28" \
    "ok_dream7b_bpu_resplit_hbm_artifact_inventory_probe" \
    "resplit_hbm_artifact_inventory_probe.json" \
    "manifest_verified_count" \
    "total_hbm_size_bytes" \
    "unexpected_hbm"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_resplit_hbm_artifact_inventory_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_resplit_hbm_artifact_inventory_probe.sh missing $text")
    fi
  done
  if ! grep -F -- "dream7b_bpu_resplit_hbm_artifact_inventory_probe.sh" README.md >/dev/null; then
    errors+=("README.md missing dream7b_bpu_resplit_hbm_artifact_inventory_probe.sh")
  fi
  if ! grep -F -- "dream7b-bpu-resplit-hbm-artifact-inventory-probe" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing dream7b-bpu-resplit-hbm-artifact-inventory-probe")
  fi
  if ! grep -F -- "/mnt/nas/openclaw/models/dream7b-hbm/resplit-seq16" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
    errors+=("Dream 7B segmented progress doc missing NAS resplit HBM path")
  fi
  if ! grep -F -- "/home/sunrise/.cache/openclaw/dream7b-hbm/resplit-seq16" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
    errors+=("Dream 7B segmented progress doc missing local resplit HBM path")
  fi
  for text in \
    "/mnt/nas/openclaw/models/dream7b-hbm/resplit-topwindow-seq16" \
    "/home/sunrise/.cache/openclaw/dream7b-hbm/resplit-topwindow-seq16" \
    "dream7b_bpu_resplit_hbm_artifact_inventory_20260606-110342" \
    "dream7b_bpu_resplit_hbm_artifact_inventory_20260606-110343" \
    "expected_specs: ['7:8', '8:10', '21:22', '22:24']"; do
    if ! grep -F -- "$text" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
      errors+=("Dream 7B segmented progress doc missing top-window artifact evidence: $text")
    fi
  done
  if ! grep -F -- "dream7b_bpu_resplit_hbm_artifact_inventory_20260609-152820" README.md >/dev/null; then
    errors+=("README.md missing top-window resplit HBM inventory evidence")
  fi
  if ! grep -F -- "dream7b_bpu_resplit_hbm_artifact_inventory_20260606-110342" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing top-window resplit HBM inventory evidence")
  fi
  for text in \
    "dream7b_bpu_resplit_hbm_artifact_inventory_20260609-152820" \
    "dream7b_bpu_resplit_hbm_artifact_inventory_20260609-152823" \
    "expected_specs: ['7:8', '8:10', '14:15', '15:17', '17:18', '18:19', '21:22', '22:24']" \
    "expected_hbm_count: 8" \
    "manifest_verified_count: 8" \
    "total_hbm_size_bytes: 2512771264"; do
    if ! grep -F -- "$text" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
      errors+=("Dream 7B segmented progress doc missing round3 top-window artifact evidence: $text")
    fi
    if ! grep -F -- "$text" README.md >/dev/null; then
      errors+=("README.md missing round3 top-window artifact evidence: $text")
    fi
    if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
      errors+=("docs/project_reference.md missing round3 top-window artifact evidence: $text")
    fi
  done
fi

if [[ -f scripts/probes/dream7b_segmented_hbm_python_forward.py ]]; then
  for text in \
    "RESPLIT_ADJACENT_SEGMENTS" \
    "RESPLIT_TOPWINDOW_ADJACENT_SEGMENTS" \
    "--resplit-hbm-dir" \
    "--topwindow-hbm-dir" \
    "resplit-adjacent" \
    "resplit-topwindow-adjacent" \
    "resplit_hbm_dir" \
    "topwindow_hbm_dir" \
    "dream_segment_00_01" \
    "dream_segment_07_08" \
    "dream_segment_14_15" \
    "dream_segment_15_17" \
    "dream_segment_17_18" \
    "dream_segment_18_19" \
    "dream_segment_21_22" \
    "dream_segment_22_24" \
    "dream_segment_27_28"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_segmented_hbm_python_forward.py >/dev/null; then
      errors+=("dream7b_segmented_hbm_python_forward.py missing resplit runtime support text: $text")
    fi
  done
fi

if [[ -f scripts/dream7b-bpu-resplit-forward.sh ]]; then
  for text in \
    "DREAM7B_BPU_RESPLIT_HBM_DIR" \
    "DREAM7B_BPU_TOPWINDOW_HBM_DIR" \
    "DREAM7B_BPU_RESPLIT_SEGMENT_PLAN" \
    "DREAM7B_BPU_RESPLIT_WINDOW_SIZE" \
    "DREAM7B_BPU_RESPLIT_CHILD_WINDOW_MODE" \
    "DREAM7B_BPU_RESPLIT_CHILD_RUNTIME_MODE" \
    "DREAM7B_BPU_RESPLIT_WINDOW_EXECUTION_MODE" \
    "/home/sunrise/.cache/openclaw/dream7b-hbm/resplit-seq16" \
    "/home/sunrise/.cache/openclaw/dream7b-hbm/resplit-topwindow-seq16" \
    "--resplit-hbm-dir" \
    "--topwindow-hbm-dir" \
    "--segment-plan" \
    "--residency-window-size" \
    "--child-window-mode" \
    "--child-runtime-mode" \
    "--window-execution-mode" \
    "dream7b-bpu-forward"; do
    if ! grep -F -- "$text" scripts/dream7b-bpu-resplit-forward.sh >/dev/null; then
      errors+=("dream7b-bpu-resplit-forward.sh missing $text")
    fi
  done
fi

if [[ -f scripts/probes/dream7b_bpu_resplit_segment_residency_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_RESPLIT_BASE_HBM_DIR" \
    "DREAM7B_BPU_RESPLIT_FINE_HBM_DIR" \
    "DREAM7B_BPU_RESPLIT_HBM_DIR" \
    "DREAM7B_BPU_RESPLIT_RESIDENCY_VENV" \
    "/home/sunrise/.cache/openclaw/dream7b-hbm/resplit-seq16" \
    "ok_dream7b_bpu_resplit_segment_residency_probe" \
    "resplit_segment_residency_probe.json" \
    "resplit_adjacent_pair_supported" \
    "ready_prefix_count" \
    "first_prefix_failure" \
    "seg00_01" \
    "seg27_28"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_resplit_segment_residency_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_resplit_segment_residency_probe.sh missing $text")
    fi
  done
  if ! grep -F -- "dream7b_bpu_resplit_segment_residency_probe.sh" README.md >/dev/null; then
    errors+=("README.md missing dream7b_bpu_resplit_segment_residency_probe.sh")
  fi
  if ! grep -F -- "dream7b-bpu-resplit-segment-residency-probe" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing dream7b-bpu-resplit-segment-residency-probe")
  fi
  if ! grep -F -- "dream7b_bpu_resplit_segment_residency_20260606-072919" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
    errors+=("Dream 7B segmented progress doc missing resplit segment residency report")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_resplit_forward_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_RESPLIT_FORWARD_EXPECTED_BASE_HBM_DIR" \
    "DREAM7B_BPU_RESPLIT_FORWARD_EXPECTED_FINE_HBM_DIR" \
    "DREAM7B_BPU_RESPLIT_FORWARD_EXPECTED_RESPLIT_HBM_DIR" \
    "dream7b-bpu-resplit-forward" \
    "ok_dream7b_bpu_resplit_forward_probe" \
    "resplit_forward_probe.json" \
    "resplit-adjacent" \
    "pair_in_process" \
    "topk_last_position" \
    "final_shape" \
    "segment_event_count" \
    "segment_sources" \
    "amortized_load_ms_per_forward"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_resplit_forward_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_resplit_forward_probe.sh missing $text")
    fi
  done
  if ! grep -F -- "dream7b_bpu_resplit_forward_probe.sh" README.md >/dev/null; then
    errors+=("README.md missing dream7b_bpu_resplit_forward_probe.sh")
  fi
  if ! grep -F -- "dream7b-bpu-resplit-forward-probe" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing dream7b-bpu-resplit-forward-probe")
  fi
  if ! grep -F -- "dream7b_bpu_resplit_forward_20260606-074419" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
    errors+=("Dream 7B segmented progress doc missing resplit forward report")
  fi
fi

if [[ -f scripts/dream7b-bpu-resplit-batch-forward.sh ]]; then
  for text in \
    "DREAM7B_BPU_RESPLIT_BATCH_WINDOW_SIZE" \
    "DREAM7B_BPU_RESPLIT_BATCH_CHILD_WINDOW_MODE" \
    "DREAM7B_BPU_RESPLIT_BATCH_CHILD_RUNTIME_MODE" \
    "DREAM7B_BPU_RESPLIT_BATCH_WINDOW_EXECUTION_MODE" \
    "DREAM7B_BPU_RESPLIT_TOKENS_BATCH_JSON" \
    "DREAM7B_BPU_TOPWINDOW_HBM_DIR" \
    "DREAM7B_BPU_RESPLIT_SEGMENT_PLAN" \
    "/home/sunrise/.cache/openclaw/dream7b-hbm/resplit-seq16" \
    "/home/sunrise/.cache/openclaw/dream7b-hbm/resplit-topwindow-seq16" \
    "--resplit-hbm-dir" \
    "--topwindow-hbm-dir" \
    "--segment-plan" \
    "--window-execution-mode" \
    "--tokens-batch-json" \
    "window-batch" \
    "dream7b-bpu-forward"; do
    if ! grep -F -- "$text" scripts/dream7b-bpu-resplit-batch-forward.sh >/dev/null; then
      errors+=("dream7b-bpu-resplit-batch-forward.sh missing $text")
    fi
  done
  if ! grep -F -- "dream7b-bpu-resplit-batch-forward.sh" README.md >/dev/null; then
    errors+=("README.md missing dream7b-bpu-resplit-batch-forward.sh")
  fi
  if ! grep -F -- "dream7b-bpu-resplit-batch-forward" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing dream7b-bpu-resplit-batch-forward")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_resplit_batch_forward_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_RESPLIT_BATCH_FORWARD_COUNT" \
    "DREAM7B_BPU_RESPLIT_BATCH_FORWARD_TOP_K" \
    "DREAM7B_BPU_RESPLIT_BATCH_FORWARD_TIMEOUT_SEC" \
    "DREAM7B_BPU_RESPLIT_BATCH_FORWARD_COUNT:-16" \
    "dream7b-bpu-resplit-batch-forward" \
    "ok_dream7b_bpu_resplit_batch_forward_probe" \
    "resplit_batch_forward_probe.json" \
    "resplit-adjacent" \
    "pair_window_batch" \
    "window-batch" \
    "topk_last_position_by_batch" \
    "final_shape_count" \
    "segment_event_count" \
    "expected_segment_event_count" \
    "load_to_run_ratio" \
    "amortized_load_ms_per_forward"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_resplit_batch_forward_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_resplit_batch_forward_probe.sh missing $text")
    fi
  done
  if ! grep -F -- "dream7b_bpu_resplit_batch_forward_probe.sh" README.md >/dev/null; then
    errors+=("README.md missing dream7b_bpu_resplit_batch_forward_probe.sh")
  fi
  if ! grep -F -- "dream7b-bpu-resplit-batch-forward-probe" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing dream7b-bpu-resplit-batch-forward-probe")
  fi
  if ! grep -F -- "dream7b_bpu_resplit_batch_forward_20260606-075837" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
    errors+=("Dream 7B segmented progress doc missing resplit batch forward report")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_resplit_batch_telemetry_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_COUNT" \
    "DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_MONITOR_DELAY_MS" \
    "DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_MONITOR_SAMPLE_COUNT" \
    "DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_TOP_K" \
    "DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_TIMEOUT_SEC" \
    "DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_FORWARD_CMD" \
    "DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_EXPECTED_SEGMENT_PLAN" \
    "DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_EXPECTED_SEGMENT_EVENT_COUNT" \
    "DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_EXPECTED_SEGMENT_SOURCES" \
    "DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_COUNT:-16" \
    "DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_FORWARD_CMD:-dream7b-bpu-resplit-batch-forward" \
    "hrt_ucp_monitor" \
    "dream7b-bpu-resplit-batch-forward" \
    "ok_dream7b_bpu_resplit_batch_telemetry_probe" \
    "resplit_batch_telemetry_probe.json" \
    "resplit_batch_telemetry_probe.md" \
    "resplit-adjacent" \
    "resplit-topwindow-adjacent" \
    "pair_window_batch" \
    "window-batch" \
    "max_bpu_loading" \
    "avg_bpu_loading" \
    "load_to_run_ratio" \
    "amortized_load_ms_per_forward" \
    "segment_event_count" \
    "expected_segment_event_count" \
    "topwindow_hbm_dir" \
    "topk_last_position_by_batch_count"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_resplit_batch_telemetry_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_resplit_batch_telemetry_probe.sh missing $text")
    fi
  done
  if ! grep -F -- "dream7b_bpu_resplit_batch_telemetry_probe.sh" README.md >/dev/null; then
    errors+=("README.md missing dream7b_bpu_resplit_batch_telemetry_probe.sh")
  fi
  if ! grep -F -- "dream7b-bpu-resplit-batch-telemetry-probe" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing dream7b-bpu-resplit-batch-telemetry-probe")
  fi
  if ! grep -F -- "dream7b_bpu_resplit_batch_telemetry_20260606-080917" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
    errors+=("Dream 7B segmented progress doc missing resplit batch telemetry report")
  fi
  for text in \
    "dream7b_bpu_resplit_batch_telemetry_20260606-112018" \
    "expected_segment_plan: resplit-topwindow-adjacent" \
    "forward_metrics.segment_event_count: 256" \
    "forward_metrics.segment_sources: ['base', 'fine', 'resplit', 'topwindow']" \
    "forward_metrics.load_to_run_ratio: 9.694618"; do
    if ! grep -F -- "$text" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
      errors+=("Dream 7B segmented progress doc missing top-window batch telemetry evidence: $text")
    fi
  done
  if ! grep -F -- "dream7b_bpu_resplit_batch_telemetry_20260609-153118" README.md >/dev/null; then
    errors+=("README.md missing top-window batch telemetry evidence")
  fi
  if ! grep -F -- "dream7b_bpu_resplit_batch_telemetry_20260606-112018" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing top-window batch telemetry evidence")
  fi
  for text in \
    "dream7b_bpu_resplit_batch_telemetry_20260609-153118" \
    "forward_metrics.segment_event_count: 288" \
    "avg_bpu_loading: 9.628" \
    "forward_metrics.load_to_run_ratio: 9.468172"; do
    if ! grep -F -- "$text" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
      errors+=("Dream 7B segmented progress doc missing round3 batch telemetry evidence: $text")
    fi
    if ! grep -F -- "$text" README.md >/dev/null; then
      errors+=("README.md missing round3 batch telemetry evidence: $text")
    fi
    if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
      errors+=("docs/project_reference.md missing round3 batch telemetry evidence: $text")
    fi
  done
fi

if [[ -f scripts/probes/dream7b_bpu_resplit_window_cost_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_RESPLIT_WINDOW_COST_MODEL_REPORT_ROOT" \
    "DREAM7B_BPU_RESPLIT_WINDOW_COST_MIN_BATCH_COUNT" \
    "DREAM7B_BPU_RESPLIT_WINDOW_COST_EXPECTED_WINDOW_COUNT" \
    "DREAM7B_BPU_RESPLIT_WINDOW_COST_EXPECTED_SEGMENT_EVENT_COUNT" \
    "DREAM7B_BPU_RESPLIT_WINDOW_COST_EXPECTED_SEGMENT_PLAN" \
    "DREAM7B_BPU_RESPLIT_WINDOW_COST_MIN_BATCH_COUNT:-16" \
    "DREAM7B_BPU_RESPLIT_WINDOW_COST_EXPECTED_SEGMENT_PLAN:-resplit-adjacent" \
    "dream7b_bpu_resplit_batch_telemetry_*/resplit_batch_telemetry_probe.json" \
    "forward_summary" \
    "ok_dream7b_bpu_resplit_window_cost_probe" \
    "resplit_window_cost_probe.json" \
    "resplit_window_cost_probe.md" \
    "resplit-adjacent" \
    "resplit-topwindow-adjacent" \
    "pair_window_batch" \
    "window-batch" \
    "window_count" \
    "ranked_by_load" \
    "ranked_by_load_to_run_ratio" \
    "top_load_window" \
    "top_load_to_run_ratio_window" \
    "load_to_run_ratio" \
    "amortized_load_ms_per_forward" \
    "next_optimization_target"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_resplit_window_cost_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_resplit_window_cost_probe.sh missing $text")
    fi
  done
  if ! grep -F -- "dream7b_bpu_resplit_window_cost_probe.sh" README.md >/dev/null; then
    errors+=("README.md missing dream7b_bpu_resplit_window_cost_probe.sh")
  fi
  if ! grep -F -- "dream7b-bpu-resplit-window-cost-probe" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing dream7b-bpu-resplit-window-cost-probe")
  fi
  if ! grep -F -- "dream7b_bpu_resplit_window_cost_20260606-083152" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
    errors+=("Dream 7B segmented progress doc missing resplit window cost report")
  fi
  for text in \
    "dream7b_bpu_resplit_window_cost_20260606-112223" \
    "segment_plan: resplit-topwindow-adjacent" \
    "segment_event_count: 256" \
    "window_count: 8" \
    "load_to_run_ratio: 9.694618" \
    "['seg14_17', 'seg17_19']"; do
    if ! grep -F -- "$text" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
      errors+=("Dream 7B segmented progress doc missing top-window window-cost evidence: $text")
    fi
  done
  if ! grep -F -- "dream7b_bpu_resplit_window_cost_20260609-153244" README.md >/dev/null; then
    errors+=("README.md missing top-window window-cost evidence")
  fi
  if ! grep -F -- "dream7b_bpu_resplit_window_cost_20260606-112223" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing top-window window-cost evidence")
  fi
  for text in \
    "dream7b_bpu_resplit_window_cost_20260609-153244" \
    "segment_event_count: 288" \
    "window_count: 9" \
    "load_to_run_ratio: 9.468172" \
    "['seg02_04', 'seg04_07']"; do
    if ! grep -F -- "$text" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
      errors+=("Dream 7B segmented progress doc missing round3 window-cost evidence: $text")
    fi
    if ! grep -F -- "$text" README.md >/dev/null; then
      errors+=("README.md missing round3 window-cost evidence: $text")
    fi
    if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
      errors+=("docs/project_reference.md missing round3 window-cost evidence: $text")
    fi
  done
fi

if [[ -f scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_CAPACITY" scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_deployment_acceptance_probe.sh missing DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_CAPACITY")
  fi
  if ! grep -F -- 'DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_CAPACITY:-16' scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_deployment_acceptance_probe.sh missing default DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_CAPACITY:-16")
  fi
  if ! grep -F -- "DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_BATCH_REQUESTS" scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_deployment_acceptance_probe.sh missing DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_BATCH_REQUESTS")
  fi
  if ! grep -F -- 'DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_BATCH_REQUESTS:-16' scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_deployment_acceptance_probe.sh missing default DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_BATCH_REQUESTS:-16")
  fi
  if ! grep -F -- "DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_TELEMETRY_REQUESTS" scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_deployment_acceptance_probe.sh missing DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_TELEMETRY_REQUESTS")
  fi
  if ! grep -F -- 'DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_TELEMETRY_REQUESTS:-48' scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_deployment_acceptance_probe.sh missing default DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_TELEMETRY_REQUESTS:-48")
  fi
  if ! grep -F -- "DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_GENERATE_COUNT" scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_deployment_acceptance_probe.sh missing DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_GENERATE_COUNT")
  fi
  if ! grep -F -- 'DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_GENERATE_COUNT:-16' scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_deployment_acceptance_probe.sh missing default DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_GENERATE_COUNT:-16")
  fi
  if ! grep -F -- "DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_GENERATE_SUSTAINED_ROUND_COUNT" scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_deployment_acceptance_probe.sh missing DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_GENERATE_SUSTAINED_ROUND_COUNT")
  fi
  if ! grep -F -- 'DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_GENERATE_SUSTAINED_ROUND_COUNT:-3' scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_deployment_acceptance_probe.sh missing default DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_GENERATE_SUSTAINED_ROUND_COUNT:-3")
  fi
  if ! grep -F -- "DREAM7B_BPU_ACCEPTANCE_MIN_LONG_REPEAT_COUNT" scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_deployment_acceptance_probe.sh missing DREAM7B_BPU_ACCEPTANCE_MIN_LONG_REPEAT_COUNT")
  fi
  if ! grep -F -- 'DREAM7B_BPU_ACCEPTANCE_MIN_LONG_REPEAT_COUNT:-6' scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_deployment_acceptance_probe.sh missing default DREAM7B_BPU_ACCEPTANCE_MIN_LONG_REPEAT_COUNT:-6")
  fi
  if ! grep -F -- "DREAM7B_BPU_ACCEPTANCE_MAX_LONG_REPEAT_WALL_SPREAD_RATIO" scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_deployment_acceptance_probe.sh missing DREAM7B_BPU_ACCEPTANCE_MAX_LONG_REPEAT_WALL_SPREAD_RATIO")
  fi
  if ! grep -F -- 'DREAM7B_BPU_ACCEPTANCE_MAX_LONG_REPEAT_WALL_SPREAD_RATIO:-0.10' scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_deployment_acceptance_probe.sh missing default DREAM7B_BPU_ACCEPTANCE_MAX_LONG_REPEAT_WALL_SPREAD_RATIO:-0.10")
  fi
  for text in \
    "dream7b_bpu_batch_queue_systemd_*/systemd_probe.json" \
    "dream7b_bpu_batch_capacity_*/batch_capacity_probe.json" \
    "dream7b_bpu_hbm_artifact_inventory_*/hbm_artifact_inventory_probe.json" \
    "dream7b_bpu_batch_queue_systemd_batch_*/systemd_batch_probe.json" \
    "dream7b_bpu_batch_queue_systemd_drain_*/systemd_drain_probe.json" \
    "dream7b_bpu_batch_queue_systemd_canary_*/systemd_canary_probe.json" \
    "dream7b_bpu_text_queue_run_*/text_queue_run.json" \
    "dream7b_bpu_text_queue_systemd_*/text_queue_systemd_probe.json" \
    "dream7b_bpu_diffusion_generate_*/generation.json" \
    "dream7b_bpu_diffusion_generate_telemetry_*/generation_telemetry_probe.json" \
    "dream7b_bpu_diffusion_batch_generate_telemetry_*/batch_generation_telemetry_probe.json" \
    "dream7b_bpu_diffusion_batch_generate_sustained_*/batch_generation_sustained_probe.json" \
    "dream7b_bpu_utilization_gap_*/utilization_gap_probe.json" \
    "dream7b_bpu_selected_pair_telemetry_*/selected_pair_telemetry_probe.json" \
    "dream7b_bpu_selected_pair_candidate_service_*/selected_pair_candidate_service_probe.json" \
    "dream7b_bpu_selected_pair_candidate_service_telemetry_*/systemd_telemetry_probe.json" \
    "dream7b_bpu_selected_pair_cross_job_reuse_*/selected_pair_cross_job_reuse_probe.json" \
    "resplit_batch_telemetry" \
    "resplit_window_cost" \
    "dream7b_bpu_persistent_pair_cache_*/persistent_pair_cache_probe.json" \
    "dream7b_bpu_held_pair_residency_matrix_*/held_pair_residency_matrix_probe.json" \
    "dream7b_bpu_single_segment_residency_matrix_*/single_segment_residency_matrix_probe.json" \
    "dream7b_bpu_persistent_segment_cache_*/persistent_segment_cache_probe.json" \
    "dream7b_bpu_single_segment_triplet_residency_*/single_segment_triplet_residency_probe.json" \
    "dream7b_bpu_seeded_quad_residency_*/seeded_quad_residency_probe.json" \
    "dream7b_bpu_segment_capacity_planner_*/segment_capacity_planner_probe.json" \
    "dream7b_bpu_persistent_triplet_topology_*/persistent_triplet_topology_probe.json" \
    "dream7b_bpu_window3_forward_feasibility_*/window3_forward_feasibility_probe.json" \
    "dream7b_bpu_selected_triplet_forward_path_*/selected_triplet_forward_path_probe.json" \
    "dream7b_bpu_batch_queue_systemd_telemetry_*/systemd_telemetry_probe.json" \
    "dream7b_bpu_fine_forward_long_repeat_*/long_repeat_probe.json" \
    "dream7b_bpu_batch_queue_retention_*/queue_retention_probe.json" \
    "systemd_service" \
    "batch_capacity" \
    "hbm_artifact_inventory" \
    "systemd_batch" \
    "systemd_drain" \
    "systemd_canary" \
    "text_queue_run" \
    "text_queue_systemd" \
    "diffusion_generate" \
    "diffusion_generate_telemetry" \
    "diffusion_batch_generate_telemetry" \
    "diffusion_batch_generate_sustained" \
    "utilization_gap" \
    "selected_pair_telemetry" \
    "selected_pair_candidate_service" \
    "selected_pair_candidate_service_telemetry" \
    "selected_pair_cross_job_reuse" \
    "persistent_pair_cache" \
    "held_pair_residency_matrix" \
    "single_segment_residency_matrix" \
    "persistent_segment_cache" \
    "single_segment_triplet_residency" \
    "seeded_quad_residency" \
    "segment_capacity_planner" \
    "persistent_triplet_topology" \
    "window3_forward_feasibility" \
    "ok_dream7b_bpu_utilization_gap_probe" \
    "ok_dream7b_bpu_persistent_pair_cache_probe" \
    "ok_dream7b_bpu_held_pair_residency_matrix_probe" \
    "ok_dream7b_bpu_single_segment_residency_matrix_probe" \
    "ok_dream7b_bpu_persistent_segment_cache_probe" \
    "ok_dream7b_bpu_single_segment_triplet_residency_probe" \
    "ok_dream7b_bpu_seeded_quad_residency_probe" \
    "ok_dream7b_bpu_segment_capacity_planner_probe" \
    "ok_dream7b_bpu_persistent_triplet_topology_probe" \
    "ok_dream7b_bpu_window3_forward_feasibility_probe" \
    "ok_dream7b_bpu_selected_triplet_forward_path_probe" \
    "ok_dream7b_bpu_selected_pair_telemetry_probe" \
    "ok_dream7b_bpu_selected_pair_cross_job_reuse_probe" \
    "diagnosis" \
    "next_optimization_target" \
    "max_observed_bpu_loading" \
    "avg_observed_bpu_loading_across_reports" \
    "runtime_load_to_run_ratio" \
    "systemd_load_to_run_ratio" \
    "selected_pair_covers_all_segments" \
    "wall_ms_delta_ratio_vs_default_runtime" \
    "selected_wall_time_improved_vs_default_runtime" \
    "selected_avg_bpu_loading_improved_vs_default_runtime" \
    "ok_dream7b_bpu_selected_pair_candidate_service_probe" \
    "dream7b-bpu-selected-pair-candidate.service" \
    "dream7b-bpu-selected-pair-batch-forward" \
    "selected_pair_candidate" \
    "default_service_replaced" \
    "candidate_wall_time_improved_vs_default_systemd" \
    "comparison_to_default_systemd_telemetry" \
    "comparison_to_selected_pair_candidate_service" \
    "cross_job_load_time_improved" \
    "cross_job_wall_time_improved" \
    "resident_load_once_amortized_ms_per_forward" \
    "resplit_batch_telemetry_batch_count" \
    "resplit_batch_telemetry_avg_bpu_loading" \
    "resplit_batch_telemetry_max_bpu_loading" \
    "resplit_batch_telemetry_load_to_run_ratio" \
    "resplit_batch_telemetry_amortized_wall_ms_per_forward" \
    "resplit_batch_telemetry_segment_event_count" \
    "resplit_window_cost_window_count" \
    "resplit_window_cost_load_to_run_ratio" \
    "resplit_window_cost_top_load_window" \
    "resplit_window_cost_top_load_window_load_ms" \
    "resplit_window_cost_top_load_to_run_ratio_window" \
    "resplit_window_cost_top_load_to_run_ratio" \
    "expected_window_execution_mode" \
    "expected_child_process_count" \
    "all_pair_workers_ready" \
    "launch_stopped_reason" \
    "ready_holder_pair_count" \
    "matrix_entry_count" \
    "successful_pair_edge_count" \
    "failed_pair_edge_count" \
    "max_resident_pair_count_observed" \
    "ready_holder_segment_count" \
    "successful_segment_edge_count" \
    "failed_segment_edge_count" \
    "all_segment_workers_ready" \
    "ready_segment_worker_count" \
    "successful_triplet_count" \
    "failed_triplet_count" \
    "successful_triplets" \
    "tested_triplet_combination_count" \
    "source_successful_triplet_count" \
    "seeded_quad_candidate_count" \
    "tested_seeded_quad_count" \
    "successful_seeded_quad_count" \
    "failed_seeded_quad_count" \
    "successful_seeded_quads" \
    "current_split_quad_residency_supported" \
    "recommended_anchor_segment_indexes" \
    "recommended_resplit_segment_indexes" \
    "selected_pair_matches_anchor_pair" \
    "tested_triplet_topology_count" \
    "stable_triplet_topology_count" \
    "failed_triplet_topology_count" \
    "stable_triplets" \
    "selected_topology" \
    "selection_rule" \
    "max_resident_segment_count_observed" \
    "ok_dream7b_bpu_diffusion_generate" \
    "ok_dream7b_bpu_diffusion_generate_telemetry_probe" \
    "ok_dream7b_bpu_diffusion_batch_generate" \
    "ok_dream7b_bpu_diffusion_batch_generate_telemetry_probe" \
    "ok_dream7b_bpu_diffusion_batch_generate_sustained_probe" \
    "generation_metrics" \
    "generation_status" \
    "generate_cmd" \
    "min_batch_generate_count" \
    "min_batch_generate_sustained_round_count" \
    "batch_count" \
    "forward_batch_counts" \
    "generation_forward_batch_counts_by_round" \
    "actual_total_batch_items" \
    "successful_generation_count" \
    "remaining_mask_positions_by_batch" \
    "decoded_final_by_batch" \
    "decoded_final" \
    "remaining_mask_positions" \
    "forward_verdict" \
    "forward_execution_mode" \
    "forward_window_execution_mode" \
    "forward_child_process_count" \
    "forward_final_shape" \
    "bounded_seq16_generation_entrypoint_not_complete_production_text_service" \
    "bounded_seq16_batch_generation_entrypoint_not_complete_production_text_service" \
    "systemd_telemetry" \
    "long_repeat" \
    "selected_triplet_forward_path" \
    "max_long_repeat_wall_spread_ratio" \
    "max_wall_spread_ratio" \
    "queue_retention" \
    "deployment_acceptance_probe.json" \
    "deployment_acceptance_probe.md" \
    "ok_dream7b_bpu_deployment_acceptance_probe" \
    "ok_dream7b_bpu_text_queue_run" \
    "ok_dream7b_bpu_text_queue_submit" \
    "run_cmd" \
    "run_verdict" \
    "submit_cmd" \
    "submit_verdict" \
    "passed_check_count" \
    "check_count" \
    "max_bpu_loading" \
    "topk_last_position" \
    "topk_last_position_decoded" \
    "token_text" \
    "tokenizer_dir"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_deployment_acceptance_probe.sh missing $text")
    fi
  done
fi

if [[ -f scripts/probes/dream7b_bpu_reload_optimization_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_RELOAD_OPTIMIZATION_BEST_LOAD_TO_RUN_RATIO" \
    "best_load_to_run_ratio" \
    "strategy_matrix" \
    "file_prefetch_or_local_hbm_cache" \
    "persistent_pair_cache" \
    "persistent_segment_cache" \
    "persistent_triplet_topology" \
    "selected_pair_cross_job_cache" \
    "batch16_wall_candidate" \
    "selected_pair_candidate_metrics" \
    "selected_pair_wall_delta_ratio_vs_resplit" \
    "sustained_service_candidate_metrics" \
    "sustained_service_decision" \
    "guarded_sustained_wall_time_candidate" \
    "default_service_replacement_decision" \
    "do_not_replace_default_service_yet" \
    "wall_delta_ratio_vs_resplit_per_request" \
    "window_scheduling_resplit_topwindow" \
    "bpu_core_scheduling" \
    "keep_hbm_reload_dominated" \
    "utilization_progress_candidate" \
    "reload_optimization_probe.json" \
    "reload_optimization_probe.md"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_reload_optimization_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_reload_optimization_probe.sh missing $text")
    fi
  done
fi

if [[ -f scripts/probes/dream7b_bpu_selected_pair_service_promotion_gate_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_SELECTED_PAIR_SERVICE_PROMOTION_MIN_PROCESSED_REQUEST_COUNT" \
    "DREAM7B_BPU_SELECTED_PAIR_SERVICE_PROMOTION_MIN_WALL_DELTA_RATIO" \
    "DREAM7B_BPU_SELECTED_PAIR_SERVICE_PROMOTION_MIN_AVG_BPU_DELTA" \
    "DREAM7B_BPU_SELECTED_PAIR_SERVICE_PROMOTION_MAX_LOAD_TO_RUN_RATIO" \
    "dream7b_bpu_selected_pair_service_promotion_gate" \
    "selected_pair_service_promotion_gate_probe.json" \
    "selected_pair_service_promotion_gate_probe.md" \
    "ok_dream7b_bpu_selected_pair_service_promotion_gate_probe" \
    "promotion_allowed" \
    "promotion_decision" \
    "block_default_service_replacement" \
    "promotion_blockers" \
    "candidate_service_isolated_from_default" \
    "default_service_replaced" \
    "rollback_plan" \
    "sudo systemctl restart dream7b-bpu-batch-queue.service"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_selected_pair_service_promotion_gate_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_selected_pair_service_promotion_gate_probe.sh missing $text")
    fi
  done
else
  errors+=("missing scripts/probes/dream7b_bpu_selected_pair_service_promotion_gate_probe.sh")
fi

if [[ -f scripts/probes/dream7b_bpu_promotion_blocker_diagnosis_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_PROMOTION_BLOCKER_BEST_LOAD_TO_RUN_RATIO" \
    "dream7b_bpu_promotion_blocker_diagnosis" \
    "promotion_blocker_diagnosis_probe.json" \
    "promotion_blocker_diagnosis_probe.md" \
    "ok_dream7b_bpu_promotion_blocker_diagnosis_probe" \
    "promotion_blockers" \
    "blocker_sources" \
    "metric_deltas" \
    "window_bottlenecks" \
    "capacity_boundary" \
    "next_optimization_candidates" \
    "prefix_micro_window_reload_reduction" \
    "seg02_04_seg04_07_window_cost_reduction" \
    "resident_capacity_boundary_experiment" \
    "core0_only_scheduling_control" \
    "keep_candidate_only_until_blockers_clear"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_promotion_blocker_diagnosis_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_promotion_blocker_diagnosis_probe.sh missing $text")
    fi
  done
else
  errors+=("missing scripts/probes/dream7b_bpu_promotion_blocker_diagnosis_probe.sh")
fi

if [[ -f scripts/probes/dream7b_final_optimization_acceptance_probe.sh ]]; then
  for text in \
    "DREAM7B_FINAL_ACCEPTANCE_BEST_LOAD_TO_RUN_RATIO" \
    "DREAM7B_FINAL_ACCEPTANCE_MIN_WALL_DELTA_RATIO" \
    "dream7b_final_optimization_acceptance" \
    "final_optimization_acceptance_probe.json" \
    "final_optimization_acceptance_probe.md" \
    "ok_dream7b_final_optimization_acceptance_probe" \
    "final_goal_satisfied" \
    "dream7b_bpu_optimized_candidate_complete_candidate_only" \
    "deployment_route_closed" \
    "substantial_improvement_observed" \
    "utilization_statement_compliant" \
    "promotion_gate_closed" \
    "dream_oellm_registry_missing" \
    "qwen_fallback_verified" \
    "deepseek7b_blocked_common_buffer" \
    "candidate_service_only" \
    "default_service_replaced"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_final_optimization_acceptance_probe.sh >/dev/null; then
      errors+=("dream7b_final_optimization_acceptance_probe.sh missing $text")
    fi
  done
else
  errors+=("missing scripts/probes/dream7b_final_optimization_acceptance_probe.sh")
fi

if [[ -f scripts/probes/dream7b_bpu_normal_use_acceptance_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_NORMAL_USE_MIN_PROCESSED_REQUEST_COUNT" \
    "DREAM7B_BPU_NORMAL_USE_PREFERRED_PROCESSED_REQUEST_COUNT" \
    "DREAM7B_BPU_NORMAL_USE_MIN_PERFORMANCE_PASS_COUNT" \
    "dream7b_bpu_normal_use_acceptance" \
    "normal_use_acceptance_probe.json" \
    "normal_use_acceptance_probe.md" \
    "ok_dream7b_bpu_normal_use_acceptance_probe" \
    "normal_use_ready" \
    "preferred_96_request_sustained_observed" \
    "performance_floor_met" \
    "reload_relief_observed" \
    "deployable_rollback_safe" \
    "utilization_claim_compliant" \
    "top_ratio_improved" \
    "top_load_improved" \
    "overall_load_to_run_improved"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_normal_use_acceptance_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_normal_use_acceptance_probe.sh missing $text")
    fi
  done
else
  errors+=("missing scripts/probes/dream7b_bpu_normal_use_acceptance_probe.sh")
fi

if [[ -f scripts/probes/dream7b_bpu_default_deployable_acceptance_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_DEFAULT_DEPLOY_MIN_PROCESSED_REQUEST_COUNT" \
    "DREAM7B_BPU_DEFAULT_DEPLOY_PREFERRED_PROCESSED_REQUEST_COUNT" \
    "DREAM7B_BPU_DEFAULT_DEPLOY_MIN_PERFORMANCE_PASS_COUNT" \
    "dream7b_bpu_default_deployable_acceptance" \
    "default_deployable_acceptance_probe.json" \
    "default_deployable_acceptance_probe.md" \
    "ok_dream7b_bpu_default_deployable_acceptance_probe" \
    "default_deployable_ready" \
    "blocked_candidate_only" \
    "service_performance_pass_count_below_3" \
    "cross_job_prototype" \
    "cross_job_queue_candidate" \
    "selected_pair_cross_job_queue_runner" \
    "cross_job_service_candidate" \
    "cross_job_default_service" \
    "cross_job_default_service_telemetry" \
    "ready_for_default_replacement_candidate_only" \
    "default_replaced_and_ready" \
    "rollback_verified" \
    "selected_pair_cross_job_candidate_service_telemetry" \
    "selected_pair_cross_job_service_promotion_gate"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_default_deployable_acceptance_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_default_deployable_acceptance_probe.sh missing $text")
    fi
  done
else
  errors+=("missing scripts/probes/dream7b_bpu_default_deployable_acceptance_probe.sh")
fi

if [[ -f scripts/probes/dream7b_bpu_utilization_gap_probe.sh ]]; then
  for text in \
    "valid_sustained_batch_counts" \
    "batch_counts_valid" \
    "round_count"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_utilization_gap_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_utilization_gap_probe.sh missing sustained batch-count generalization: $text")
    fi
  done
fi

if [[ -f scripts/probes/dream7b_bpu_selected_pair_service_promotion_gate_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_SELECTED_PAIR_SERVICE_PROMOTION_MIN_ROUND_COUNT" \
    "service_batch_counts_valid" \
    "min_sustained_round_count"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_selected_pair_service_promotion_gate_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_selected_pair_service_promotion_gate_probe.sh missing sustained batch-count generalization: $text")
    fi
  done
fi

if [[ -f scripts/probes/dream7b_bpu_resplit_window_cost_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_RESPLIT_WINDOW_COST_EXPECTED_WINDOW_COUNT" \
    "resplit-topwindow-adjacent" \
    "expected_window_count=\"9\"" \
    "expected_segment_event_count=\"288\""; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_resplit_window_cost_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_resplit_window_cost_probe.sh missing top-window default handling: $text")
    fi
  done
fi

for text in \
  "dream7b_bpu_resplit_hbm_artifact_inventory_20260609-224012" \
  "dream7b_bpu_resplit_hbm_artifact_inventory_20260609-224035" \
  "dream7b_bpu_resplit_batch_telemetry_20260609-224100" \
  "dream7b_bpu_resplit_window_cost_20260609-224142" \
  "dream7b_bpu_utilization_gap_20260609-224156" \
  "dream7b_bpu_deployment_acceptance_20260609-224157" \
  "expected_hbm_count: 8" \
  "existing_hbm_count: 8" \
  "manifest_verified_count: 8" \
  "total_hbm_size_bytes: 2512771264" \
  "avg_bpu_loading: 8.97" \
  "forward_metrics.load_to_run_ratio: 9.678265" \
  "load_to_run_ratio: 9.678265" \
  "diagnosis: hbm_reload_dominated" \
  "check_count: 30" \
  "passed_check_count: 30" \
  "9.468172"; do
  if ! grep -F -- "$text" README.md >/dev/null; then
    errors+=("README.md missing latest Dream segmented refresh evidence: $text")
  fi
  if ! grep -F -- "$text" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
    errors+=("Dream 7B segmented progress doc missing latest Dream segmented refresh evidence: $text")
  fi
  if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing latest Dream segmented refresh evidence: $text")
  fi
  if ! grep -F -- "$text" docs/dream7b_s100p_bpu_handoff_2026-06-09.md >/dev/null; then
    errors+=("Dream 7B handoff doc missing latest Dream segmented refresh evidence: $text")
  fi
done

for text in \
  "docs/dream7b_vendor_support_package_2026-06-10.md" \
  "scripts/probes/dream7b_bpu_reload_optimization_probe.sh" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_batch_telemetry_20260610-030740/resplit_batch_telemetry_probe.json" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_window_cost_20260610-030820/resplit_window_cost_probe.json" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_telemetry_20260610-031613/selected_pair_telemetry_probe.json" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_utilization_gap_20260610-031818/utilization_gap_probe.json" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260610-031818/deployment_acceptance_probe.json" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_reload_optimization_20260610-031828/reload_optimization_probe.json" \
  "avg_bpu_loading: 8.811" \
  "max_bpu_loading: 100.0" \
  "forward_metrics.load_to_run_ratio: 9.524202" \
  "forward_metrics.wall_ms: 26007.248" \
  "selected_pair: [1, 8]" \
  "selected_pair_covers_all_segments: True" \
  "selected_pair.wall_ms: 22982.452" \
  "selected_pair.avg_bpu_loading: 8.984" \
  "selected_pair_wall_delta_ratio_vs_resplit: 0.116306" \
  "selected_pair_avg_bpu_delta_vs_resplit: 0.173" \
  "diagnosis: hbm_reload_dominated" \
  "check_count: 30" \
  "passed_check_count: 30" \
  "final_decision: utilization_progress_candidate" \
  "substantial_improvement_observed: True" \
  "best_load_to_run_ratio: 9.468172" \
  "ratio_delta_vs_best: 0.05603"; do
  if ! grep -F -- "$text" README.md >/dev/null; then
    errors+=("README.md missing Dream reload optimization closure evidence: $text")
  fi
  if ! grep -F -- "$text" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
    errors+=("Dream 7B segmented progress doc missing reload optimization closure evidence: $text")
  fi
  if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing reload optimization closure evidence: $text")
  fi
  if ! grep -F -- "$text" docs/dream7b_s100p_bpu_handoff_2026-06-09.md >/dev/null; then
    errors+=("Dream 7B handoff doc missing reload optimization closure evidence: $text")
  fi
done

for text in \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_service_telemetry_20260610-032523/systemd_telemetry_probe.json" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_utilization_gap_20260610-032709/utilization_gap_probe.json" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260610-032709/deployment_acceptance_probe.json" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_reload_optimization_20260610-032926/reload_optimization_probe.json" \
  "processed_request_count: 48" \
  "batch_counts: [16, 16, 16]" \
  "amortized_wall_ms_per_processed_request: 1445.673" \
  "avg_bpu_loading: 8.371" \
  "max_bpu_loading: 98.0" \
  "load_to_run_ratio: 9.859028" \
  "wall_ms_delta_ratio_vs_default_systemd: 0.130546" \
  "candidate_avg_bpu_loading_not_worse_than_default_systemd: False" \
  "final_decision: guarded_sustained_wall_time_candidate" \
  "sustained_service_decision: guarded_sustained_wall_time_candidate" \
  "default_service_replacement_decision: do_not_replace_default_service_yet" \
  "wall_delta_ratio_vs_resplit_per_request: 0.110603" \
  "avg_bpu_delta_vs_resplit: -0.44" \
  "avg_bpu_delta_vs_selected_pair_single: -0.613"; do
  if ! grep -F -- "$text" README.md >/dev/null; then
    errors+=("README.md missing sustained selected-pair service closure evidence: $text")
  fi
  if ! grep -F -- "$text" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
    errors+=("Dream 7B segmented progress doc missing sustained selected-pair service closure evidence: $text")
  fi
  if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing sustained selected-pair service closure evidence: $text")
  fi
  if ! grep -F -- "$text" docs/dream7b_s100p_bpu_handoff_2026-06-09.md >/dev/null; then
    errors+=("Dream 7B handoff doc missing sustained selected-pair service closure evidence: $text")
  fi
done

for text in \
  "scripts/probes/dream7b_bpu_selected_pair_service_promotion_gate_probe.sh" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_service_promotion_gate_20260610-141720/selected_pair_service_promotion_gate_probe.json" \
  "verdict: ok_dream7b_bpu_selected_pair_service_promotion_gate_probe" \
  "promotion_allowed: False" \
  "promotion_decision: block_default_service_replacement" \
  "default_service_replaced: False" \
  "candidate_service_isolated_from_default: True" \
  "candidate_load_to_run_ratio: 9.859028" \
  "wall_delta_ratio_vs_default_systemd: 0.130546" \
  "wall_delta_ratio_vs_resplit_per_request: 0.110603" \
  "avg_bpu_delta_vs_default_systemd: -1.245" \
  "avg_bpu_delta_vs_resplit: -0.44" \
  "utilization_diagnosis: hbm_reload_dominated" \
  "promotion_average_bpu_not_worse_vs_default" \
  "promotion_average_bpu_improved_vs_resplit" \
  "promotion_load_to_run_not_worse_than_best" \
  "promotion_not_hbm_reload_dominated" \
  "reload_gate_allows_default_replacement" \
  "sudo systemctl restart dream7b-bpu-batch-queue.service"; do
  if ! grep -F -- "$text" README.md >/dev/null; then
    errors+=("README.md missing selected-pair service promotion gate evidence: $text")
  fi
  if ! grep -F -- "$text" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
    errors+=("Dream 7B segmented progress doc missing selected-pair service promotion gate evidence: $text")
  fi
  if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing selected-pair service promotion gate evidence: $text")
  fi
  if ! grep -F -- "$text" docs/dream7b_s100p_bpu_handoff_2026-06-09.md >/dev/null; then
    errors+=("Dream 7B handoff doc missing selected-pair service promotion gate evidence: $text")
  fi
done

for text in \
  "scripts/probes/dream7b_bpu_promotion_blocker_diagnosis_probe.sh" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_promotion_blocker_diagnosis_20260610-145739/promotion_blocker_diagnosis_probe.json" \
  "verdict: ok_dream7b_bpu_promotion_blocker_diagnosis_probe" \
  "promotion_decision: keep_candidate_only_until_blockers_clear" \
  "candidate_load_to_run_ratio: 9.859028" \
  "load_to_run_delta_vs_best: 0.390856" \
  "load_to_run_delta_vs_resplit: 0.334826" \
  "service_avg_bpu_loading: 8.371" \
  "avg_bpu_delta_vs_resplit: -0.44" \
  "wall_delta_ratio_vs_resplit_per_request: 0.110603" \
  "top_load_to_run_ratio_window.resident_segments: ['seg00_01', 'seg01_02']" \
  "top_load_to_run_ratio_window.load_to_run_ratio: 18.585073" \
  "top_load_window.resident_segments: ['seg02_04', 'seg04_07']" \
  "top_load_window.load_ms: 3562.79" \
  "max_resident_segment_count_observed: 3" \
  "successful_seeded_quad_count: 0" \
  "recommended_resplit_segment_indexes: [0, 9, 4, 6]" \
  "prefix_micro_window_reload_reduction" \
  "seg02_04_seg04_07_window_cost_reduction"; do
  if ! grep -F -- "$text" README.md >/dev/null; then
    errors+=("README.md missing promotion blocker diagnosis evidence: $text")
  fi
  if ! grep -F -- "$text" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
    errors+=("Dream 7B segmented progress doc missing promotion blocker diagnosis evidence: $text")
  fi
  if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing promotion blocker diagnosis evidence: $text")
  fi
  if ! grep -F -- "$text" docs/dream7b_s100p_bpu_handoff_2026-06-09.md >/dev/null; then
    errors+=("Dream 7B handoff doc missing promotion blocker diagnosis evidence: $text")
  fi
done

for text in \
  "scripts/probes/dream7b_final_optimization_acceptance_probe.sh" \
  "/mnt/nas/openclaw/reports/models/dream7b_final_optimization_acceptance_20260610-161744/final_optimization_acceptance_probe.json" \
  "verdict: ok_dream7b_final_optimization_acceptance_probe" \
  "final_goal_satisfied: True" \
  "final_decision: dream7b_bpu_optimized_candidate_complete_candidate_only" \
  "deployment_route_closed: True" \
  "substantial_improvement_observed: True" \
  "utilization_statement_compliant: True" \
  "promotion_gate_closed: True" \
  "dream_oellm_registry_missing: True" \
  "qwen_fallback_verified: True" \
  "deepseek7b_blocked_common_buffer: True" \
  "candidate_service_only: True" \
  "default_service_replaced: False" \
  "selected_pair_wall_delta_ratio_vs_resplit: 0.116306" \
  "sustained_wall_delta_ratio_vs_resplit_per_request: 0.110603" \
  "sustained_wall_delta_ratio_vs_default_systemd: 0.130546" \
  "sustained_request_count: 48"; do
  if ! grep -F -- "$text" README.md >/dev/null; then
    errors+=("README.md missing final optimization acceptance evidence: $text")
  fi
  if ! grep -F -- "$text" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
    errors+=("Dream 7B segmented progress doc missing final optimization acceptance evidence: $text")
  fi
  if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing final optimization acceptance evidence: $text")
  fi
  if ! grep -F -- "$text" docs/dream7b_s100p_bpu_handoff_2026-06-09.md >/dev/null; then
    errors+=("Dream 7B handoff doc missing final optimization acceptance evidence: $text")
  fi
done

for text in \
  "scripts/probes/dream7b_bpu_normal_use_acceptance_probe.sh" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_normal_use_acceptance_20260610-170005/normal_use_acceptance_probe.json" \
  "verdict: ok_dream7b_bpu_normal_use_acceptance_probe" \
  "normal_use_ready: True" \
  "unmet_requirements: []" \
  "stable_sustained_service: True" \
  "preferred_96_request_sustained_observed: True" \
  "deployment_acceptance_clean: True" \
  "performance_floor_met: True" \
  "reload_relief_observed: True" \
  "deployable_rollback_safe: True" \
  "utilization_claim_compliant: True" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_service_telemetry_20260610-165645/systemd_telemetry_probe.json" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_service_telemetry_20260610-163241/systemd_telemetry_probe.json" \
  "processed_request_count: 48" \
  "failed_job_count: 0" \
  "amortized_wall_ms_per_processed_request: 1448.877" \
  "avg_bpu_loading: 8.578" \
  "max_bpu_loading: 96.0" \
  "wall_delta_ratio_vs_resplit_per_request: 0.102517" \
  "wall_delta_ratio_vs_default_systemd: 0.128619" \
  "load_to_run_ratio: 9.863791" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_batch_telemetry_20260610-165429/resplit_batch_telemetry_probe.json" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_window_cost_20260610-165513/resplit_window_cost_probe.json" \
  "load_to_run_ratio: 9.443895" \
  "9.774037" \
  "top_ratio_improved: True" \
  "top_load_improved: True" \
  "overall_load_to_run_improved: True"; do
  if ! grep -F -- "$text" README.md >/dev/null; then
    errors+=("README.md missing normal-use acceptance evidence: $text")
  fi
  if ! grep -F -- "$text" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
    errors+=("Dream 7B segmented progress doc missing normal-use acceptance evidence: $text")
  fi
  if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing normal-use acceptance evidence: $text")
  fi
  if ! grep -F -- "$text" docs/dream7b_s100p_bpu_handoff_2026-06-09.md >/dev/null; then
    errors+=("Dream 7B handoff doc missing normal-use acceptance evidence: $text")
  fi
done

for text in \
  "scripts/probes/dream7b_bpu_default_deployable_acceptance_probe.sh" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_default_deployable_acceptance_20260610-173758/default_deployable_acceptance_probe.json" \
  "verdict: ok_dream7b_bpu_default_deployable_acceptance_probe" \
  "default_deployable_ready: False" \
  "default_deployable_status: blocked_candidate_only" \
  "processed_request_count: 192" \
  "failed_job_count: 0" \
  "preferred_sustained_observed: True" \
  "deployment_acceptance_clean: True" \
  "promotion_allowed: False" \
  "performance_pass_count: 1" \
  "min_performance_pass_count: 3" \
  "amortized_wall_ms_per_processed_request: 1450.4" \
  "avg_bpu_loading: 8.476" \
  "load_to_run_ratio: 9.873488" \
  "service_performance_pass_count_below_3" \
  "service_avg_bpu_below_default_deploy_threshold" \
  "service_load_to_run_above_default_deploy_threshold" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_service_promotion_gate_20260610-173049/selected_pair_service_promotion_gate_probe.json" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_reload_optimization_20260610-173049/reload_optimization_probe.json" \
  "promotion_decision: block_default_service_replacement" \
  "utilization_diagnosis: hbm_reload_dominated" \
  "default_service_replacement_decision: do_not_replace_default_service_yet" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_reuse_20260610-172408/selected_pair_cross_job_reuse_probe.json" \
  "processed_forward_count: 128" \
  "load_to_run_ratio: 8.895442" \
  "amortized_wall_ms_per_forward: 1448.768" \
  "load_ms_delta_ratio_vs_service: 0.10225" \
  "cross_job_wall_time_improved: True"; do
  if ! grep -F -- "$text" README.md >/dev/null; then
    errors+=("README.md missing default-deployable acceptance evidence: $text")
  fi
  if ! grep -F -- "$text" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
    errors+=("Dream 7B segmented progress doc missing default-deployable acceptance evidence: $text")
  fi
  if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing default-deployable acceptance evidence: $text")
  fi
  if ! grep -F -- "$text" docs/dream7b_s100p_bpu_handoff_2026-06-09.md >/dev/null; then
    errors+=("Dream 7B handoff doc missing default-deployable acceptance evidence: $text")
  fi
done

for text in \
  "scripts/dream7b_bpu_selected_pair_cross_job_queue_runner.py" \
  "DREAM7B_BPU_SELECTED_PAIR_TOKENS_BATCHES_BY_JOB_JSON" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_queue_runner_20260610-175302/cross_job_queue_summary.json" \
  "verdict: ok_dream7b_bpu_selected_pair_cross_job_queue_runner" \
  "processed_job_count: 6" \
  "processed_request_count: 96" \
  "load_to_run_ratio: 8.890613" \
  "amortized_wall_ms_per_processed_request: 1438.937" \
  "amortized_total_load_ms_per_processed_request: 1309.349" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_queue_runner_20260610-175739/cross_job_queue_summary.json" \
  "processed_job_count: 12" \
  "load_to_run_ratio: 8.904793" \
  "amortized_wall_ms_per_processed_request: 1459.145" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260610-180307/deployment_acceptance_probe.json" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_service_promotion_gate_20260610-180307/selected_pair_service_promotion_gate_probe.json" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_default_deployable_acceptance_20260610-180307/default_deployable_acceptance_probe.json" \
  "cross_job_queue_candidate.preferred_sustained_observed: True" \
  "cross_job_queue_candidate.performance_pass_count: 1" \
  "cross_job_queue_candidate.load_to_run_ratio: 8.904793"; do
  if ! grep -F -- "$text" README.md >/dev/null; then
    errors+=("README.md missing cross-job queue runner evidence: $text")
  fi
  if ! grep -F -- "$text" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
    errors+=("Dream 7B segmented progress doc missing cross-job queue runner evidence: $text")
  fi
  if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing cross-job queue runner evidence: $text")
  fi
  if ! grep -F -- "$text" docs/dream7b_s100p_bpu_handoff_2026-06-09.md >/dev/null; then
    errors+=("Dream 7B handoff doc missing cross-job queue runner evidence: $text")
  fi
done

for text in \
  "scripts/install_dream7b_bpu_selected_pair_cross_job_candidate_service.sh" \
  "scripts/dream7b_bpu_selected_pair_cross_job_queue_service.py" \
  "scripts/probes/dream7b_bpu_selected_pair_cross_job_queue_telemetry_probe.sh" \
  "scripts/probes/dream7b_bpu_selected_pair_cross_job_service_fallback_probe.sh" \
  "scripts/probes/dream7b_bpu_selected_pair_cross_job_service_promotion_gate_probe.sh" \
  "dream7b-bpu-selected-pair-cross-job-candidate.service" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_candidate_service_telemetry_20260610-182409/service_telemetry_probe.json" \
  "verdict: ok_dream7b_bpu_selected_pair_cross_job_candidate_service_telemetry_probe" \
  "processed_request_count: 192" \
  "failed_job_count: 0" \
  "load_to_run_ratio: 8.66679" \
  "avg_bpu_loading: 10.108" \
  "max_bpu_loading: 98.0" \
  "amortized_wall_ms_per_processed_request: 1430.794" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_service_promotion_gate_20260610-183109/cross_job_service_promotion_gate_probe.json" \
  "verdict: ok_dream7b_bpu_selected_pair_cross_job_service_promotion_gate_probe" \
  "promotion_allowed: True" \
  "promotion_decision: ready_for_default_service_replacement" \
  "default_service_replaced: False" \
  "promotion_blockers: []" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_default_deployable_acceptance_20260610-183252/default_deployable_acceptance_probe.json" \
  "default_deployable_status: ready_for_default_replacement_candidate_only" \
  "cross_job_service_candidate.performance_pass_count: 3" \
  "cross_job_service_candidate.ready_for_default_replacement: True" \
  "cross_job_service_candidate.default_replaced_and_ready: False"; do
  if ! grep -F -- "$text" README.md >/dev/null; then
    errors+=("README.md missing cross-job candidate service promotion evidence: $text")
  fi
  if ! grep -F -- "$text" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
    errors+=("Dream 7B segmented progress doc missing cross-job candidate service promotion evidence: $text")
  fi
  if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing cross-job candidate service promotion evidence: $text")
  fi
  if ! grep -F -- "$text" docs/dream7b_s100p_bpu_handoff_2026-06-09.md >/dev/null; then
    errors+=("Dream 7B handoff doc missing cross-job candidate service promotion evidence: $text")
  fi
done

for text in \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_service_fallback_20260610-185916/cross_job_service_fallback_probe.json" \
  "verdict: ok_dream7b_bpu_selected_pair_cross_job_service_fallback_probe" \
  "single_job_fallback_ok: True" \
  "run_reason: single_job_flush_timeout" \
  "processed_request_count: 1" \
  "failed_job_count: 0" \
  "load_to_run_ratio: 155.028327" \
  "amortized_wall_ms_per_processed_request: 20577.422" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_service_promotion_gate_20260610-185941/cross_job_service_promotion_gate_probe.json" \
  "promotion_allowed: True" \
  "promotion_blockers: []" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_default_deployable_acceptance_20260610-185941/default_deployable_acceptance_probe.json" \
  "default_deployable_status: ready_for_default_replacement_candidate_only" \
  "default_service_replaced: False"; do
  if ! grep -F -- "$text" README.md >/dev/null; then
    errors+=("README.md missing single-job fallback evidence: $text")
  fi
  if ! grep -F -- "$text" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
    errors+=("Dream 7B segmented progress doc missing single-job fallback evidence: $text")
  fi
  if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing single-job fallback evidence: $text")
  fi
  if ! grep -F -- "$text" docs/dream7b_s100p_bpu_handoff_2026-06-09.md >/dev/null; then
    errors+=("Dream 7B handoff doc missing single-job fallback evidence: $text")
  fi
done

for text in \
  "scripts/probes/dream7b_bpu_cross_job_default_promotion_probe.sh" \
  "scripts/probes/dream7b_bpu_cross_job_default_service_telemetry_probe.sh" \
  "/mnt/nas/openclaw/runtimes/dream7b-bpu-cross-job-default" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_cross_job_default_promotion_20260610-190712/cross_job_default_promotion_probe.json" \
  "verdict: ok_dream7b_bpu_cross_job_default_promotion_probe" \
  "default_service_replaced: True" \
  "rollback_verified: True" \
  "errors: []" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_cross_job_default_service_telemetry_20260610-191115/default_service_telemetry_probe.json" \
  "verdict: ok_dream7b_bpu_cross_job_default_service_telemetry_probe" \
  "processed_request_count: 192" \
  "failed_job_count: 0" \
  "queue_done_count: 12" \
  "queue_failed_count: 0" \
  "load_to_run_ratio: 8.734653" \
  "avg_bpu_loading: 9.915" \
  "max_bpu_loading: 98.0" \
  "amortized_wall_ms_per_processed_request: 1441.545" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260610-192303/deployment_acceptance_probe.json" \
  "verdict: ok_dream7b_bpu_deployment_acceptance_probe" \
  "check_count: 30" \
  "passed_check_count: 30" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_default_deployable_acceptance_20260610-192303/default_deployable_acceptance_probe.json" \
  "default_deployable_ready: True" \
  "default_deployable_status: ready" \
  "cross_job_default_service.performance_pass_count: 3" \
  "cross_job_service_candidate.default_replaced_and_ready: True" \
  "cross_job_service_candidate.rollback_verified: True" \
  "blockers: []" \
  "warnings: []"; do
  if ! grep -F -- "$text" README.md >/dev/null; then
    errors+=("README.md missing default promotion closure evidence: $text")
  fi
  if ! grep -F -- "$text" docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md >/dev/null; then
    errors+=("Dream 7B segmented progress doc missing default promotion closure evidence: $text")
  fi
  if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing default promotion closure evidence: $text")
  fi
  if ! grep -F -- "$text" docs/dream7b_s100p_bpu_handoff_2026-06-09.md >/dev/null; then
    errors+=("Dream 7B handoff doc missing default promotion closure evidence: $text")
  fi
done

for text in \
  "DeepSeek_R1_Distill_Qwen_7B_1024.hbm" \
  "hbm_size_bytes: 7928846896" \
  "Cannot malloc bpu memory with length 7928846896 bytes" \
  "Qwen2.5-1.5B 512/128 remains the verified official runnable fallback" \
  "dream_registered_in_official_sdk: False" \
  "failure_stage: registry_missing" \
  "DeepSeek 7B requires what S100P memory layout" \
  "Dream/DreamModel has an official adapter path"; do
  if ! grep -F -- "$text" docs/dream7b_vendor_support_package_2026-06-10.md >/dev/null; then
    errors+=("docs/dream7b_vendor_support_package_2026-06-10.md missing support package evidence: $text")
  fi
done

for text in \
  "scripts/probes/dream7b_openclaw_candidate_validation_probe.py" \
  "scripts/probes/dream7b_90pct_candidate_evidence_package_probe.py" \
  "/mnt/nas/openclaw/reports/models/dream7b_openclaw_candidate_validation_20260612-172108/openclaw_candidate_validation_probe.json" \
  "verdict: ok_dream7b_openclaw_candidate_validation_probe" \
  "primary_model: dream7b-local/Dream7B-S100P-local" \
  "dream_provider_base_url: http://127.0.0.1:18888/v1" \
  "minimax_fallback_present: true" \
  "recent_trace_has_openclaw_heartbeat: true" \
  "recent_trace_has_sort_trigger: true" \
  "default_service_replaced: false" \
  "docs/dream7b_s100p_90pct_default_candidate_handoff_2026-06-12.md" \
  "dream7b-bpu-segment-major-load-once-candidate-24job-b256.service" \
  "dream7b-bpu-segment-major-load-once-candidate-24job.service" \
  "dream7b-bpu-batch-queue.service" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_soak_20260612-171402/segment_major_candidate_soak_probe.json" \
  "sudo systemctl disable --now dream7b-bpu-segment-major-load-once-candidate-24job-b256.service"; do
  if ! grep -F -- "$text" README.md >/dev/null; then
    errors+=("README.md missing 90pct default-candidate handoff evidence: $text")
  fi
  if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing 90pct default-candidate handoff evidence: $text")
  fi
  if ! grep -F -- "$text" docs/dream7b_s100p_90pct_utilization_route_2026-06-12.md >/dev/null; then
    errors+=("90pct route doc missing default-candidate handoff evidence: $text")
  fi
  if ! grep -F -- "$text" docs/dream7b_s100p_90pct_default_candidate_handoff_2026-06-12.md >/dev/null; then
    errors+=("90pct default candidate handoff doc missing evidence: $text")
  fi
done

for text in \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_soak_20260612-171402/segment_major_candidate_soak_probe.json" \
  "verdict: ok_dream7b_bpu_segment_major_candidate_soak_probe" \
  "decision: segment_major_service_soak_meets_90pct_goal" \
  "elapsed_sec: 7723" \
  "iteration_count: 8" \
  "processed_request_count: 49152" \
  "failed_job_count: 0" \
  "avg_bpu_loading: 90.264" \
  "min_iteration_avg_bpu_loading: 90.155" \
  "avg_load_to_run_ratio: 0.026177" \
  "max_iteration_load_to_run_ratio: 0.027452" \
  "default_service_replaced: False" \
  "rollback_status: rollback_safe_candidate_only" \
  "/mnt/nas/openclaw/reports/models/dream7b_90pct_candidate_evidence_package_final/evidence_package_manifest.json" \
  "verdict: ok_dream7b_90pct_candidate_evidence_package_probe" \
  "service_24x256_reaches_90: True" \
  "soak_30min_reaches_90: True" \
  "soak_2h_reaches_90: True" \
  "services_active: True" \
  "openclaw_local_dream_ok: True" \
  "docs_consistency_ok: True"; do
  if ! grep -F -- "$text" README.md >/dev/null; then
    errors+=("README.md missing final 90pct 2h evidence: $text")
  fi
  if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing final 90pct 2h evidence: $text")
  fi
  if ! grep -F -- "$text" docs/dream7b_s100p_90pct_utilization_route_2026-06-12.md >/dev/null; then
    errors+=("90pct route doc missing final 2h evidence: $text")
  fi
  if ! grep -F -- "$text" docs/dream7b_s100p_90pct_default_candidate_handoff_2026-06-12.md >/dev/null; then
    errors+=("90pct default candidate handoff doc missing final 2h evidence: $text")
  fi
done

for text in \
  "scripts/probes/dream7b_bpu_segment_major_default_promotion_probe.sh" \
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_default_promotion_20260612-210011/segment_major_default_promotion_probe.json" \
  "verdict: ok_dream7b_bpu_segment_major_default_promotion_probe" \
  "service_name: dream7b-bpu-batch-queue.service" \
  "queue_dir: /mnt/nas/openclaw/queues/dream7b-bpu" \
  "runtime_dir: /mnt/nas/openclaw/runtimes/dream7b-bpu-segment-major-default" \
  "default_service_replaced: True" \
  "rollback_verified: True" \
  "smoke_request_id: segment-major-default-smoke-20260612-210011" \
  "--max-batch-size 256"; do
  if ! grep -F -- "$text" README.md >/dev/null; then
    errors+=("README.md missing segment-major default promotion evidence: $text")
  fi
  if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing segment-major default promotion evidence: $text")
  fi
  if ! grep -F -- "$text" docs/dream7b_s100p_90pct_utilization_route_2026-06-12.md >/dev/null; then
    errors+=("90pct route doc missing segment-major default promotion evidence: $text")
  fi
  if ! grep -F -- "$text" docs/dream7b_s100p_90pct_default_candidate_handoff_2026-06-12.md >/dev/null; then
    errors+=("90pct handoff doc missing segment-major default promotion evidence: $text")
  fi
done

for text in \
  "dream7b-default-status" \
  "dream7b-default-rollback" \
  "scripts/install_dream7b_default_ops_tools.sh" \
  "dream7b-default-health.timer" \
  "/etc/logrotate.d/dream7b-default-health" \
  "docs/dream7b_s100p_default_service_ops_runbook_2026-06-12.md"; do
  if ! grep -F -- "$text" README.md >/dev/null; then
    errors+=("README.md missing Dream default ops evidence: $text")
  fi
  if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing Dream default ops evidence: $text")
  fi
  if ! grep -F -- "$text" docs/dream7b_s100p_default_service_ops_runbook_2026-06-12.md >/dev/null; then
    errors+=("default service ops runbook missing ops evidence: $text")
  fi
done

for text in \
  "scripts/dream7b_local_openai_gateway.py" \
  "personal_data_sort_probe" \
  "/mnt/nas/openclaw/reports/personal-data-sort/personal_data_sort_20260612-211115/personal_data_sort.md" \
  "verdict: ok_personal_data_sort_probe" \
  "file_count: 20" \
  "copy_count: 20" \
  "dry_run: False" \
  "upload_performed: True" \
  "delete_or_move_performed: False" \
  "Sorted/Movies"; do
  if ! grep -F -- "$text" README.md >/dev/null; then
    errors+=("README.md missing OpenClaw Dream copy-sort evidence: $text")
  fi
  if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing OpenClaw Dream copy-sort evidence: $text")
  fi
done

for text in \
  "docs/dream7b_s100p_default_promotion_acceptance_2026-06-12.md" \
  "scripts/probes/dream7b_default_promotion_acceptance_probe.py" \
  "/mnt/nas/openclaw/reports/models/dream7b_default_promotion_acceptance_20260612-213745/default_promotion_acceptance_probe.json" \
  "verdict: ok_dream7b_default_promotion_acceptance_probe" \
  "decision: dream7b_24x256_segment_major_default_accepted" \
  "avg_bpu_loading: 90.097" \
  "failed_job_count: 0" \
  "elapsed_sec: 1932" \
  "iteration_count: 2" \
  "load_to_run_ratio: 0.025975" \
  "copy_count: 20" \
  "errors: []"; do
  if ! grep -F -- "$text" README.md >/dev/null; then
    errors+=("README.md missing Dream default promotion final acceptance: $text")
  fi
  if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
    errors+=("docs/project_reference.md missing Dream default promotion final acceptance: $text")
  fi
  if ! grep -F -- "$text" docs/dream7b_s100p_90pct_utilization_route_2026-06-12.md >/dev/null; then
    errors+=("90pct route doc missing Dream default promotion final acceptance: $text")
  fi
  if ! grep -F -- "$text" docs/dream7b_s100p_90pct_default_candidate_handoff_2026-06-12.md >/dev/null; then
    errors+=("90pct handoff doc missing Dream default promotion final acceptance: $text")
  fi
  if ! grep -F -- "$text" docs/dream7b_s100p_default_promotion_acceptance_2026-06-12.md >/dev/null; then
    errors+=("default promotion acceptance doc missing Dream default promotion final acceptance: $text")
  fi
done

summary_json="$report_root/summary.json"
summary_md="$report_root/summary.md"

python3 - "$summary_json" "$summary_md" "${errors[@]}" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

summary_json = Path(sys.argv[1])
summary_md = Path(sys.argv[2])
errors = list(sys.argv[3:])
payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_project_docs_consistency_probe" if not errors else "failed_project_docs_consistency_probe",
    "errors": errors,
}
summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = [
    "# Project Documentation Consistency Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    "",
    "## Errors",
    "",
]
if errors:
    lines.extend(f"- {item}" for item in errors)
else:
    lines.append("- none")
summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(summary_md)
if errors:
    raise SystemExit("; ".join(errors))
PY
