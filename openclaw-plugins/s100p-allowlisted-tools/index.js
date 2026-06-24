import { execFile } from "node:child_process";
import { readFile } from "node:fs/promises";
import { promisify } from "node:util";
import { definePluginEntry } from "file:///root/.npm-global/lib/node_modules/openclaw/dist/plugin-sdk/plugin-entry.js";

const execFileAsync = promisify(execFile);
const runnerPath = "/root/.openclaw/workspace/scripts/run_allowlisted_tool.sh";
const probeOutDir = "/root/.openclaw/workspace/logs/probes";
const logsDir = "/root/.openclaw/workspace/logs";
const documentsDir = "/root/.openclaw/workspace/documents";
const photosDir = "/root/.openclaw/workspace/photos";
const reportsDir = "/root/.openclaw/workspace/reports";
const dailySummaryReportsDir = "/root/.openclaw/workspace/reports/daily-summary";
const stabilityReportsDir = "/root/.openclaw/workspace/reports/stability";
const imageCaptionReportsDir = "/root/.openclaw/workspace/reports/image-captions";
const modelReportsDir = "/root/.openclaw/workspace/reports/models";
const browserReportsDir = "/root/.openclaw/workspace/reports/browser-smoke";
const teacherReportsDir = "/root/.openclaw/workspace/reports/teacher";
const robotDatasetsDir = "/root/.openclaw/workspace/robot_datasets";
const nasReportsDir = "/mnt/nas/openclaw/reports";
const nasTeacherDemoEntryReportsDir = "/mnt/nas/openclaw/reports/teacher-demos/openclaw-entry";
const nasTeacherDemoMovieSortReportsDir = "/mnt/nas/openclaw/reports/teacher-demos/ai-nas-movie-sort";
const nasTeacherDemoMovieSortDir = "/mnt/nas/openclaw/demo/ai-nas-movie-sort";
const nasPersonalSortReportsDir = "/mnt/nas/openclaw/reports/personal-data-sort";
const allowedTools = new Map([
  ["openclaw_status_probe", [probeOutDir]],
  ["nas_discovery_probe", [probeOutDir]],
  ["ros2_status_probe", [probeOutDir]],
  ["sandbox_status_probe", [probeOutDir]],
  ["security_audit_probe", [probeOutDir]],
  ["service_policy_probe", [probeOutDir]],
  ["service_hardening_plan_probe", [probeOutDir]],
  ["service_convergence_decision_probe", [probeOutDir, `${reportsDir}/security`]],
  ["service_execution_preflight_probe", [`${reportsDir}/security`]],
  ["stability_snapshot_probe", [probeOutDir]],
  ["stability_summary_probe", [probeOutDir, stabilityReportsDir]],
  ["image_caption_probe", [photosDir, imageCaptionReportsDir]],
  ["vision_caption_readiness_probe", [photosDir, imageCaptionReportsDir]],
  ["dream7b_readiness_probe", [modelReportsDir]],
  ["dream7b_smoke_probe", [modelReportsDir]],
  ["home_assistant_status_probe", [probeOutDir]],
  ["control_action_policy_probe", [probeOutDir]],
  ["browser_smoke_probe", [browserReportsDir]],
  ["rosbag_snapshot_probe", [robotDatasetsDir, probeOutDir]],
  ["rosbag_session_probe", [robotDatasetsDir, probeOutDir]],
  ["rosbag_capture_policy_probe", [probeOutDir]],
  ["experiment_report_probe", [`${reportsDir}/experiments`]],
  ["baseline_status_probe", ["/root/.openclaw/workspace", `${reportsDir}/baseline-status`]],
  ["baseline_gap_decision_probe", ["/mnt/nas/openclaw", `${reportsDir}/baseline-status`]],
  ["baseline_acceptance_probe", ["/mnt/nas/openclaw", `${reportsDir}/baseline-status`]],
  ["baseline_acceptance_trend_probe", ["/mnt/nas/openclaw", `${reportsDir}/baseline-status`]],
  ["baseline_evidence_manifest_probe", ["/mnt/nas/openclaw", `${reportsDir}/baseline-status`]],
  ["teacher_baseline_briefing_probe", ["/mnt/nas/openclaw", teacherReportsDir]],
  ["log_diagnose", [logsDir, probeOutDir]],
  ["index_documents", [documentsDir, reportsDir]],
  ["document_daily_summary_probe", [documentsDir, dailySummaryReportsDir]],
  ["openclaw_entry_demo_probe", [nasTeacherDemoEntryReportsDir]],
  ["ai_nas_movie_sort_demo_probe", [nasTeacherDemoMovieSortDir, nasTeacherDemoMovieSortReportsDir]],
  ["ai_nas_personal_inventory", []],
  ["ai_nas_personal_inventory_probe", []],
  ["ai_nas_file_search", []],
  ["ai_nas_file_search_probe", []],
  ["ai_nas_index_status", []],
  ["ai_nas_index_status_probe", []],
  ["ai_nas_index_daemon_readiness", []],
  ["ai_nas_index_daemon_readiness_probe", []],
  ["ai_nas_index_daemon_smoke", []],
  ["ai_nas_index_daemon_smoke_probe", []],
  ["ai_nas_index_daemon_resident", []],
  ["ai_nas_index_daemon_resident_probe", []],
  ["ai_nas_index_systemd_daemon_install", []],
  ["ai_nas_index_systemd_daemon_install_probe", []],
  ["ai_nas_index_rename_detection", []],
  ["ai_nas_index_rename_detection_probe", []],
  ["ai_nas_index_observability_contract", []],
  ["ai_nas_index_observability_contract_probe", []],
  ["ai_nas_sqlite_index_integrity_contract", []],
  ["ai_nas_sqlite_index_integrity_contract_probe", []],
  ["ai_nas_incremental_scan_efficiency_contract", []],
  ["ai_nas_incremental_scan_efficiency_contract_probe", []],
  ["ai_nas_index_search_isolation_slo", []],
  ["ai_nas_index_search_isolation_slo_probe", []],
  ["ai_nas_perf_benchmark", []],
  ["ai_nas_perf_benchmark_probe", []],
  ["ai_nas_concurrency_stability", []],
  ["ai_nas_concurrency_stability_probe", []],
  ["ai_nas_continuous_task_soak", []],
  ["ai_nas_continuous_task_soak_probe", []],
  ["ai_nas_nas_backed_long_soak", []],
  ["ai_nas_nas_backed_long_soak_probe", []],
  ["ai_nas_soak_checkpoint_resume", []],
  ["ai_nas_soak_checkpoint_resume_probe", []],
  ["ai_nas_queue_backpressure_slo", []],
  ["ai_nas_queue_backpressure_slo_probe", []],
  ["ai_nas_user_facing_tail_latency", []],
  ["ai_nas_user_facing_tail_latency_probe", []],
  ["ai_nas_bpu_headroom_slo", []],
  ["ai_nas_bpu_headroom_slo_probe", []],
  ["ai_nas_operational_slo_rollup_contract", []],
  ["ai_nas_operational_slo_rollup_contract_probe", []],
  ["ai_nas_allowlist_governance_audit", []],
  ["ai_nas_allowlist_governance_audit_probe", []],
  ["ai_nas_task_queue", []],
  ["ai_nas_task_queue_probe", []],
  ["ai_nas_case_packet", []],
  ["ai_nas_case_packet_probe", []],
  ["ai_nas_appliance_experience_acceptance", []],
  ["ai_nas_appliance_experience_acceptance_probe", []],
  ["ai_nas_operator_portal_contract", []],
  ["ai_nas_operator_portal_contract_probe", []],
  ["ai_nas_production_dependency_bundle", []],
  ["ai_nas_production_dependency_bundle_probe", []],
  ["ai_nas_production_blocker_runbook_contract", []],
  ["ai_nas_production_blocker_runbook_contract_probe", []],
  ["ai_nas_evidence_catalog_contract", []],
  ["ai_nas_evidence_catalog_contract_probe", []],
  ["ai_nas_objective_traceability_contract", []],
  ["ai_nas_objective_traceability_contract_probe", []],
  ["ai_nas_goal_completion_audit", []],
  ["ai_nas_goal_completion_audit_probe", []],
  ["ai_nas_goal_completion_finalizer", []],
  ["ai_nas_goal_completion_finalizer_probe", []],
  ["ai_nas_evidence_freshness_contract", []],
  ["ai_nas_evidence_freshness_contract_probe", []],
  ["ai_nas_portable_nas_adapter_contract", []],
  ["ai_nas_portable_nas_adapter_contract_probe", []],
  ["ai_nas_production_readiness_gate", []],
  ["ai_nas_production_readiness_gate_probe", []],
  ["ai_nas_search_evidence_contract", []],
  ["ai_nas_search_evidence_contract_probe", []],
  ["ai_nas_search_confidence_calibration_contract", []],
  ["ai_nas_search_confidence_calibration_contract_probe", []],
  ["ai_nas_multimodal_intent_routing_contract", []],
  ["ai_nas_multimodal_intent_routing_contract_probe", []],
  ["ai_nas_semantic_query_acceptance", []],
  ["ai_nas_semantic_query_acceptance_probe", []],
  ["ai_nas_action_approval_manifest", []],
  ["ai_nas_action_approval_manifest_probe", []],
  ["ai_nas_action_manifest_integrity", []],
  ["ai_nas_action_manifest_integrity_probe", []],
  ["ai_nas_operator_approval_inbox", []],
  ["ai_nas_operator_approval_inbox_probe", []],
  ["ai_nas_action_execute_copy", []],
  ["ai_nas_action_execute_copy_probe", []],
  ["ai_nas_action_rollback_copy", []],
  ["ai_nas_action_rollback_copy_probe", []],
  ["ai_nas_destructive_action_governance", []],
  ["ai_nas_destructive_action_governance_probe", []],
  ["ai_nas_audit_trail_contract", []],
  ["ai_nas_audit_trail_contract_probe", []],
  ["ai_nas_permission_aware_search", []],
  ["ai_nas_permission_aware_search_probe", []],
  ["ai_nas_acl_mapping_readiness", []],
  ["ai_nas_acl_mapping_readiness_probe", []],
  ["ai_nas_evidence_report", []],
  ["ai_nas_evidence_report_probe", []],
  ["ai_nas_embedding_search", []],
  ["ai_nas_embedding_search_probe", []],
  ["ai_nas_embedding_backend_readiness", []],
  ["ai_nas_embedding_backend_readiness_probe", []],
  ["ai_nas_embedding_runtime_contract", []],
  ["ai_nas_embedding_runtime_contract_probe", []],
  ["ai_nas_model_service_resilience", []],
  ["ai_nas_model_service_resilience_probe", []],
  ["ai_nas_model_service_recovery_drill", []],
  ["ai_nas_model_service_recovery_drill_probe", []],
  ["ai_nas_model_service_recovery_manifest", []],
  ["ai_nas_model_service_recovery_manifest_probe", []],
  ["ai_nas_model_service_real_recovery_drill", []],
  ["ai_nas_model_service_real_recovery_drill_probe", []],
  ["ai_nas_ocr_runtime_contract", []],
  ["ai_nas_ocr_runtime_contract_probe", []],
  ["ai_nas_ocr_readiness", []],
  ["ai_nas_ocr_readiness_probe", []],
  ["ai_nas_ocr_extract", []],
  ["ai_nas_ocr_extract_probe", []],
  ["ai_nas_document_pipeline_acceptance", []],
  ["ai_nas_document_pipeline_acceptance_probe", []],
  ["ai_nas_folder_rag", []],
  ["ai_nas_folder_rag_probe", []],
  ["ai_nas_folder_rag_grounding_contract", []],
  ["ai_nas_folder_rag_grounding_contract_probe", []],
  ["ai_nas_folder_summary", []],
  ["ai_nas_folder_summary_probe", []],
  ["ai_nas_duplicate_report", []],
  ["ai_nas_duplicate_report_probe", []],
  ["ai_nas_photo_similarity", []],
  ["ai_nas_photo_similarity_probe", []],
  ["ai_nas_image_embedding_extract", []],
  ["ai_nas_image_embedding_extract_probe", []],
  ["ai_nas_photo_semantic_search", []],
  ["ai_nas_photo_semantic_search_probe", []],
  ["ai_nas_photo_pipeline_acceptance", []],
  ["ai_nas_photo_pipeline_acceptance_probe", []],
  ["ai_nas_photo_privacy_governance", []],
  ["ai_nas_photo_privacy_governance_probe", []],
  ["ai_nas_movie_sort_enhanced", []],
  ["ai_nas_movie_sort_enhanced_probe", []],
  ["personal_data_sort_probe", ["Personal", "Movies", "Sorted", nasPersonalSortReportsDir]]
]);

const allowedToolIds = [...allowedTools.keys()];
const queryEnabledToolIds = new Set([
  "ai_nas_file_search",
  "ai_nas_file_search_probe",
  "ai_nas_evidence_report",
  "ai_nas_evidence_report_probe",
  "ai_nas_case_packet",
  "ai_nas_case_packet_probe",
  "ai_nas_action_approval_manifest",
  "ai_nas_action_approval_manifest_probe",
  "ai_nas_permission_aware_search",
  "ai_nas_permission_aware_search_probe",
  "ai_nas_embedding_search",
  "ai_nas_embedding_search_probe",
  "ai_nas_photo_semantic_search",
  "ai_nas_photo_semantic_search_probe",
  "ai_nas_folder_rag",
  "ai_nas_folder_rag_probe"
]);
const folderEnabledToolIds = new Set([
  "ai_nas_folder_rag",
  "ai_nas_folder_rag_probe"
]);
const principalEnabledToolIds = new Set([
  "ai_nas_permission_aware_search",
  "ai_nas_permission_aware_search_probe"
]);
const manifestEnabledToolIds = new Set([
  "ai_nas_action_execute_copy",
  "ai_nas_action_execute_copy_probe"
]);
const realRecoveryEnabledToolIds = new Set([
  "ai_nas_model_service_real_recovery_drill",
  "ai_nas_model_service_real_recovery_drill_probe"
]);
const longRunningToolIds = new Set([
  "ai_nas_nas_backed_long_soak",
  "ai_nas_nas_backed_long_soak_probe"
]);
const rollbackEnabledToolIds = new Set([
  "ai_nas_action_rollback_copy",
  "ai_nas_action_rollback_copy_probe"
]);

function jsonResult(payload) {
  return {
    content: [
      {
        type: "text",
        text: JSON.stringify(payload, null, 2)
      }
    ],
    details: payload
  };
}

function readToolId(rawParams) {
  const value = rawParams?.tool_id;
  if (typeof value !== "string" || !allowedTools.has(value)) {
    throw new Error(`tool_id must be one of: ${allowedToolIds.join(", ")}`);
  }
  return value;
}

function readOptionalQuery(toolId, rawParams) {
  const value = rawParams?.query;
  if (value === undefined || value === null || value === "") {
    return undefined;
  }
  if (!queryEnabledToolIds.has(toolId)) {
    throw new Error(`query is only accepted for: ${[...queryEnabledToolIds].join(", ")}`);
  }
  if (typeof value !== "string") {
    throw new Error("query must be a string.");
  }
  if (value.length > 240) {
    throw new Error("query must be at most 240 characters.");
  }
  if (/[\r\n\0]/.test(value)) {
    throw new Error("query must be a single-line string.");
  }
  return value;
}

function readOptionalFolder(toolId, rawParams) {
  const value = rawParams?.folder;
  if (value === undefined || value === null || value === "") {
    return undefined;
  }
  if (!folderEnabledToolIds.has(toolId)) {
    throw new Error(`folder is only accepted for: ${[...folderEnabledToolIds].join(", ")}`);
  }
  if (typeof value !== "string") {
    throw new Error("folder must be a string.");
  }
  if (value.length > 160) {
    throw new Error("folder must be at most 160 characters.");
  }
  if (/[\r\n\0]/.test(value) || value.includes("..") || value.startsWith("/") || value.startsWith("\\")) {
    throw new Error("folder must be a relative single-line folder path.");
  }
  return value;
}

function readOptionalPrincipal(toolId, rawParams, query) {
  const value = rawParams?.principal;
  if (value === undefined || value === null || value === "") {
    return undefined;
  }
  if (!principalEnabledToolIds.has(toolId)) {
    throw new Error(`principal is only accepted for: ${[...principalEnabledToolIds].join(", ")}`);
  }
  if (!query) {
    throw new Error("query is required when principal is provided.");
  }
  if (typeof value !== "string") {
    throw new Error("principal must be a string.");
  }
  const allowed = new Set(["admin", "family_member", "accountant", "guest", "child"]);
  if (!allowed.has(value)) {
    throw new Error("principal must be one of: admin, family_member, accountant, guest, child.");
  }
  return value;
}

function readOptionalManifestPath(toolId, rawParams) {
  const value = rawParams?.manifest_path;
  if (value === undefined || value === null || value === "") {
    if (realRecoveryEnabledToolIds.has(toolId)) {
      throw new Error("manifest_path is required for ai_nas_model_service_real_recovery_drill.");
    }
    return undefined;
  }
  if (!manifestEnabledToolIds.has(toolId) && !realRecoveryEnabledToolIds.has(toolId)) {
    throw new Error(`manifest_path is only accepted for: ${[...manifestEnabledToolIds, ...realRecoveryEnabledToolIds].join(", ")}`);
  }
  if (typeof value !== "string") {
    throw new Error("manifest_path must be a string.");
  }
  if (value.length > 260 || /[\r\n\0]/.test(value)) {
    throw new Error("manifest_path must be a single-line path at most 260 characters.");
  }
  if (!value.startsWith("/tmp/") && !value.startsWith("/mnt/nas/openclaw/reports/ai_nas_mvp/") && !value.startsWith("/root/.openclaw/workspace/reports/ai_nas_mvp/")) {
    throw new Error("manifest_path must be under an approved AI-NAS report directory.");
  }
  return value;
}

function readOptionalApprovalPhrase(toolId, rawParams, manifestPath) {
  const value = rawParams?.approval_phrase;
  if (value === undefined || value === null || value === "") {
    return undefined;
  }
  if (!manifestEnabledToolIds.has(toolId) && !realRecoveryEnabledToolIds.has(toolId)) {
    throw new Error(`approval_phrase is only accepted for: ${[...manifestEnabledToolIds, ...realRecoveryEnabledToolIds].join(", ")}`);
  }
  if (!manifestPath) {
    throw new Error("manifest_path is required when approval_phrase is provided.");
  }
  if (typeof value !== "string" || value.length > 80 || /[\r\n\0]/.test(value)) {
    throw new Error("approval_phrase must be a single-line string at most 80 characters.");
  }
  if (manifestEnabledToolIds.has(toolId) && !/^APPROVE apm-[a-f0-9]{16}$/.test(value)) {
    throw new Error("approval_phrase must match APPROVE apm-<16 hex chars>.");
  }
  if (realRecoveryEnabledToolIds.has(toolId) && !/^APPROVE-RECOVERY msr-[a-f0-9]{16}$/.test(value)) {
    throw new Error("approval_phrase must match APPROVE-RECOVERY msr-<16 hex chars>.");
  }
  return value;
}

function readOptionalExecutionMode(toolId, rawParams, approvalPhrase) {
  const value = rawParams?.execution_mode;
  if (value === undefined || value === null || value === "") {
    return undefined;
  }
  if (!realRecoveryEnabledToolIds.has(toolId)) {
    throw new Error(`execution_mode is only accepted for: ${[...realRecoveryEnabledToolIds].join(", ")}`);
  }
  if (typeof value !== "string" || value.length > 16 || /[\r\n\0]/.test(value)) {
    throw new Error("execution_mode must be a single-line string at most 16 characters.");
  }
  if (value !== "dry_run" && value !== "execute") {
    throw new Error("execution_mode must be dry_run or execute.");
  }
  if (value === "execute" && !approvalPhrase) {
    throw new Error("approval_phrase is required when execution_mode=execute.");
  }
  return value === "execute" ? "--execute" : undefined;
}

function readOptionalRollbackManifestPath(toolId, rawParams) {
  const value = rawParams?.rollback_manifest_path;
  if (value === undefined || value === null || value === "") {
    return undefined;
  }
  if (!rollbackEnabledToolIds.has(toolId)) {
    throw new Error(`rollback_manifest_path is only accepted for: ${[...rollbackEnabledToolIds].join(", ")}`);
  }
  if (typeof value !== "string") {
    throw new Error("rollback_manifest_path must be a string.");
  }
  if (value.length > 260 || /[\r\n\0]/.test(value)) {
    throw new Error("rollback_manifest_path must be a single-line path at most 260 characters.");
  }
  if (!value.startsWith("/tmp/") && !value.startsWith("/mnt/nas/openclaw/reports/ai_nas_mvp/") && !value.startsWith("/root/.openclaw/workspace/reports/ai_nas_mvp/")) {
    throw new Error("rollback_manifest_path must be under an approved AI-NAS report directory.");
  }
  return value;
}

function readOptionalRollbackPhrase(toolId, rawParams, rollbackManifestPath) {
  const value = rawParams?.rollback_phrase;
  if (value === undefined || value === null || value === "") {
    return undefined;
  }
  if (!rollbackEnabledToolIds.has(toolId)) {
    throw new Error(`rollback_phrase is only accepted for: ${[...rollbackEnabledToolIds].join(", ")}`);
  }
  if (!rollbackManifestPath) {
    throw new Error("rollback_manifest_path is required when rollback_phrase is provided.");
  }
  if (typeof value !== "string" || value.length > 80 || /[\r\n\0]/.test(value)) {
    throw new Error("rollback_phrase must be a single-line string at most 80 characters.");
  }
  if (!/^ROLLBACK apm-[a-f0-9]{16}$/.test(value)) {
    throw new Error("rollback_phrase must match ROLLBACK apm-<16 hex chars>.");
  }
  return value;
}

function assertSafeReportPath(path) {
  if (!path.startsWith(`${probeOutDir}/`) && !path.startsWith(`${reportsDir}/`) && !path.startsWith(`${nasReportsDir}/`)) {
    throw new Error(`probe returned an unexpected report path: ${path}`);
  }
}

async function runProbe(toolId, query, folder, principal, manifestPath, approvalPhrase, executionFlag, rollbackManifestPath, rollbackPhrase) {
  const args = [toolId, ...allowedTools.get(toolId)];
  if (folder) {
    args.push(folder);
  }
  if (manifestPath) {
    args.push(manifestPath);
  }
  if (approvalPhrase) {
    args.push(approvalPhrase);
  }
  if (executionFlag) {
    args.push(executionFlag);
  }
  if (rollbackManifestPath) {
    args.push(rollbackManifestPath);
  }
  if (rollbackPhrase) {
    args.push(rollbackPhrase);
  }
  if (query) {
    args.push(query);
  }
  if (principal) {
    args.push(principal);
  }
  const { stdout, stderr } = await execFileAsync(runnerPath, args, {
    timeout: longRunningToolIds.has(toolId) ? 3700 * 1000 : 45000,
    maxBuffer: 1024 * 1024,
    env: {
      PATH: "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    }
  });
  const reportPath = stdout.trim().split(/\r?\n/).filter(Boolean).at(-1) || "";
  assertSafeReportPath(reportPath);
  const report = await readFile(reportPath, "utf8");
  return {
    tool_id: toolId,
    report_path: reportPath,
    stderr: stderr.trim() || undefined,
    report_preview: report.slice(0, 6000)
  };
}

const S100pRunProbeSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    tool_id: {
      type: "string",
      enum: allowedToolIds,
      description: "Allowlisted S100P probe ID to run."
    },
    query: {
      type: "string",
      maxLength: 240,
      description: "Optional single-line natural-language query. Accepted only by AI-NAS search/evidence tools."
    },
    folder: {
      type: "string",
      maxLength: 160,
      description: "Optional relative folder path. Accepted only by ai_nas_folder_rag."
    },
    principal: {
      type: "string",
      enum: ["admin", "family_member", "accountant", "guest", "child"],
      description: "Optional permission principal. Accepted only by ai_nas_permission_aware_search and requires query."
    },
    manifest_path: {
      type: "string",
      maxLength: 260,
      description: "Approval manifest JSON path. Accepted by ai_nas_action_execute_copy and ai_nas_model_service_real_recovery_drill."
    },
    approval_phrase: {
      type: "string",
      maxLength: 80,
      description: "Exact approval phrase from the manifest. Accepted by ai_nas_action_execute_copy and ai_nas_model_service_real_recovery_drill."
    },
    execution_mode: {
      type: "string",
      maxLength: 16,
      enum: ["dry_run", "execute"],
      description: "Use execute only for ai_nas_model_service_real_recovery_drill after operator approval; dry_run or omitted performs no service restart."
    },
    rollback_manifest_path: {
      type: "string",
      maxLength: 260,
      description: "Rollback manifest JSON path. Accepted only by ai_nas_action_rollback_copy."
    },
    rollback_phrase: {
      type: "string",
      maxLength: 80,
      description: "Exact rollback phrase derived from the manifest id. Accepted only by ai_nas_action_rollback_copy."
    }
  },
  required: ["tool_id"]
};

function createS100pRunProbeTool() {
  return {
    name: "s100p_run_probe",
    label: "S100P Run Probe",
    description: "Run one approved S100P read-only probe through the local allowlist runner. Does not accept shell commands or arbitrary script paths.",
    parameters: S100pRunProbeSchema,
    execute: async (_toolCallId, rawParams) => {
      const toolId = readToolId(rawParams);
      const query = readOptionalQuery(toolId, rawParams);
      const folder = readOptionalFolder(toolId, rawParams);
      const principal = readOptionalPrincipal(toolId, rawParams, query);
      const manifestPath = readOptionalManifestPath(toolId, rawParams);
      const approvalPhrase = readOptionalApprovalPhrase(toolId, rawParams, manifestPath);
      const executionFlag = readOptionalExecutionMode(toolId, rawParams, approvalPhrase);
      const rollbackManifestPath = readOptionalRollbackManifestPath(toolId, rawParams);
      const rollbackPhrase = readOptionalRollbackPhrase(toolId, rawParams, rollbackManifestPath);
      return jsonResult(await runProbe(toolId, query, folder, principal, manifestPath, approvalPhrase, executionFlag, rollbackManifestPath, rollbackPhrase));
    }
  };
}

export default definePluginEntry({
  id: "s100p-allowlisted-tools",
  name: "S100P Allowlisted Tools",
  description: "Narrow OpenClaw tools for approved S100P probes.",
  register(api) {
    api.registerTool(createS100pRunProbeTool());
  }
});
