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
const robotDatasetsDir = "/root/.openclaw/workspace/robot_datasets";
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
  ["home_assistant_status_probe", [probeOutDir]],
  ["control_action_policy_probe", [probeOutDir]],
  ["browser_smoke_probe", [browserReportsDir]],
  ["rosbag_snapshot_probe", [robotDatasetsDir, probeOutDir]],
  ["rosbag_session_probe", [robotDatasetsDir, probeOutDir]],
  ["rosbag_capture_policy_probe", [probeOutDir]],
  ["experiment_report_probe", [`${reportsDir}/experiments`]],
  ["baseline_status_probe", ["/root/.openclaw/workspace", `${reportsDir}/baseline-status`]],
  ["baseline_gap_decision_probe", ["/mnt/nas/openclaw", `${reportsDir}/baseline-status`]],
  ["log_diagnose", [logsDir, probeOutDir]],
  ["index_documents", [documentsDir, reportsDir]],
  ["document_daily_summary_probe", [documentsDir, dailySummaryReportsDir]]
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
    throw new Error("tool_id must be one of: openclaw_status_probe, nas_discovery_probe, ros2_status_probe, sandbox_status_probe, security_audit_probe, service_policy_probe, service_hardening_plan_probe, service_convergence_decision_probe, service_execution_preflight_probe, stability_snapshot_probe, stability_summary_probe, image_caption_probe, vision_caption_readiness_probe, dream7b_readiness_probe, home_assistant_status_probe, control_action_policy_probe, browser_smoke_probe, rosbag_snapshot_probe, rosbag_session_probe, rosbag_capture_policy_probe, experiment_report_probe, baseline_status_probe, baseline_gap_decision_probe, log_diagnose, index_documents, document_daily_summary_probe");
  }
  return value;
}

function assertSafeReportPath(path) {
  if (!path.startsWith(`${probeOutDir}/`) && !path.startsWith(`${reportsDir}/`)) {
    throw new Error(`probe returned an unexpected report path: ${path}`);
  }
}

async function runProbe(toolId) {
  const args = [toolId, ...allowedTools.get(toolId)];
  const { stdout, stderr } = await execFileAsync(runnerPath, args, {
    timeout: 45000,
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
      enum: ["openclaw_status_probe", "nas_discovery_probe", "ros2_status_probe", "sandbox_status_probe", "security_audit_probe", "service_policy_probe", "service_hardening_plan_probe", "service_convergence_decision_probe", "service_execution_preflight_probe", "stability_snapshot_probe", "stability_summary_probe", "image_caption_probe", "vision_caption_readiness_probe", "dream7b_readiness_probe", "home_assistant_status_probe", "control_action_policy_probe", "browser_smoke_probe", "rosbag_snapshot_probe", "rosbag_session_probe", "rosbag_capture_policy_probe", "experiment_report_probe", "baseline_status_probe", "baseline_gap_decision_probe", "log_diagnose", "index_documents", "document_daily_summary_probe"],
      description: "Allowlisted S100P probe ID to run."
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
      return jsonResult(await runProbe(toolId));
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
