#!/usr/bin/env bash
set -euo pipefail

nas_root="${1:-/mnt/nas/openclaw}"
report_dir="${2:-$nas_root/reports/teacher}"

case "$nas_root" in
  /mnt/nas/openclaw|/mnt/nas/openclaw/*|/root/.openclaw/workspace|/root/.openclaw/workspace/*|/tmp/*) ;;
  *)
    echo "Refusing NAS/workspace root outside approved paths: $nas_root" >&2
    exit 2
    ;;
esac

case "$report_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing report directory outside approved paths: $report_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$report_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$report_dir/teacher_baseline_briefing_$stamp.md"
json="$report_dir/teacher_baseline_briefing_$stamp.json"

python3 - "$nas_root" "$report" "$json" <<'PY'
import json
import re
import sys
from datetime import datetime
from pathlib import Path

nas_root = Path(sys.argv[1])
report = Path(sys.argv[2])
json_path = Path(sys.argv[3])


def latest(relative_glob):
    files = sorted(
        nas_root.glob(relative_glob),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )
    return files[0] if files else None


def read(path):
    if not path:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def table_value(text, label):
    pattern = re.compile(rf"\|\s*{re.escape(label)}\s*\|\s*([^|]+?)\s*\|")
    match = pattern.search(text)
    return match.group(1).strip() if match else "missing"


def meta_value(text, key):
    pattern = re.compile(rf"^-\s*{re.escape(key)}:\s*(.+)$", re.MULTILINE)
    match = pattern.search(text)
    return match.group(1).strip() if match else "missing"


latest_gap = latest("reports/baseline-status/baseline_gap_decision_*.md")
latest_status = latest("reports/baseline-status/baseline_status_*.md")
latest_overnight_summary = latest("reports/baseline-status/overnight_baseline_*_summary.md")
latest_overnight_status = latest("reports/baseline-status/overnight_baseline_*_status.md")
latest_stability = latest("reports/stability/stability_summary_*.md")
latest_dream_readiness = latest("reports/models/dream7b_readiness_*.md")
latest_dream_smoke = latest("reports/models/dream7b_smoke_*.md")
latest_ha = latest("logs/probes/home_assistant_status_*.md")
latest_control = latest("logs/probes/control_action_policy_*.md")
latest_service_preflight = latest("reports/security/service_execution_preflight_*.md")
latest_security = latest("logs/probes/security_audit_*.md")
latest_service_decision = latest("reports/security/service_convergence_decision_*.md")
latest_document_summary = latest("reports/daily-summary/document_daily_summary_*.md")
latest_image_caption = latest("reports/image-captions/image_caption_index_*.md")
latest_vision_readiness = latest("reports/image-captions/vision_caption_readiness_*.md")
latest_experiment = latest("reports/experiments/experiment_report_*.md")
latest_dataset_card = latest("robot_datasets/*/DATASET_CARD.md")

gap_text = read(latest_gap)
status_text = read(latest_status)
overnight_summary_text = read(latest_overnight_summary)
overnight_status_text = read(latest_overnight_status)
stability_text = read(latest_stability)
dream_readiness_text = read(latest_dream_readiness)
dream_smoke_text = read(latest_dream_smoke)
ha_text = read(latest_ha)
control_text = read(latest_control)
service_preflight_text = read(latest_service_preflight)

snapshot_count = table_value(stability_text, "Snapshot count")
elapsed_hours = table_value(stability_text, "Elapsed hours")
stability_verdict = table_value(stability_text, "Verdict")
gateway_status = table_value(status_text, "OpenClaw Gateway")
nas_status = table_value(status_text, "NAS workspace")
artifact_scope = table_value(status_text, "Artifact scope")
tool_count = table_value(status_text, "Allowlisted tool count")
overnight_process = meta_value(overnight_status_text, "process_status")
overnight_iterations = meta_value(overnight_status_text, "completed_iterations_observed")
overnight_failed = meta_value(overnight_status_text, "failed_event_count")
overnight_next = meta_value(overnight_status_text, "next_iteration_after")
overnight_verdict = meta_value(overnight_summary_text, "verdict")

dream_verdict = meta_value(dream_readiness_text, "verdict")
dream_runtime = table_value(dream_readiness_text, "Runtime summary")
dream_model_files = table_value(dream_readiness_text, "Candidate model-like files")
dream_smoke_verdict = meta_value(dream_smoke_text, "verdict")
dream_smoke_runtime = table_value(dream_smoke_text, "Runtime")
ha_verdict = table_value(ha_text, "Verdict")
ha_url = table_value(ha_text, "URL configured")
ha_token = table_value(ha_text, "Token configured")
control_verdict = table_value(control_text, "Verdict")
control_actions = table_value(control_text, "Action count")
control_enabled = table_value(control_text, "Enabled action count")
control_executed = table_value(control_text, "Executed records")
service_preflight_verdict = meta_value(service_preflight_text, "verdict")

nas_backed = nas_status == "mounted" and str(nas_root).startswith("/mnt/nas/openclaw")
if nas_backed:
    workspace_status = "已跑通"
    workspace_wording = f"NAS={nas_status}；报告、日志、数据集持续写入 {nas_root}。"
    opening_wording = (
        "当前 S100P + NAS 已经不是单次手工跑通，而是形成了可恢复、可观测、可持续写 NAS 的 OpenClaw 常驻链路。"
    )
    nas_conclusion = "第一层 NAS-backed 工作流已经成型；第二层本地模型和设备联动仍卡在外部输入。"
else:
    workspace_status = "本地 fallback"
    workspace_wording = f"当前报告写入 {nas_root}；NAS={nas_status}；artifact_scope={artifact_scope}，不能当作 NAS-backed 证据。"
    opening_wording = (
        "当前 S100P 的 OpenClaw 常驻链路仍可观测、可用本地 workspace 继续只读复核；NAS 直连证据暂时保持暂停，不能声明新的 NAS-backed 验收。"
    )
    nas_conclusion = "本轮只刷新了本地 fallback 证据；NAS-backed 工作流需要等 NAS 直连恢复后再验收。"

pc_parity_items = [
    ("常驻入口", "已跑通", f"Gateway={gateway_status}；飞书入口可触发 OpenClaw，Gateway 仍是 loopback 暴露。"),
    ("受控工具执行", "已跑通", f"allowlisted_tools={tool_count}；OpenClaw agent 通过 s100p_run_probe 触发固定工具。"),
    ("NAS 落盘", workspace_status, workspace_wording),
    ("机器人数据读取/采集", "已跑通", "ROS2 状态查询、ROS bag self-test、一次人工批准 named capture 已具备证据。"),
    ("稳定性", "采集中", f"{snapshot_count} snapshots / {elapsed_hours}h / {stability_verdict}；A-010 仍需 168h。"),
    ("桌面/交互替代", "不声明", "S100P 适合常驻自动化和机器人侧任务，不等同于 PC 桌面体验。"),
]

nas_homework_items = [
    ("统一工作区", workspace_status, f"{nas_root} 作为本轮报告根目录；artifact_scope={artifact_scope}。"),
    ("文档/日志/实验报告", "本地 fallback" if not nas_backed else "已跑通", "文档 deterministic summary、log diagnosis、experiment report 有本地证据；NAS-backed 证据需在 NAS 恢复后刷新。" if not nas_backed else "文档 deterministic summary、log diagnosis、experiment report 均有 NAS-backed 证据。"),
    ("图片 caption", "部分跑通", "metadata caption 已跑通；semantic vision 仍缺本地模型/runtime。"),
    ("Dream 7B / 本地 DLM", "未部署", f"readiness={dream_verdict}, runtime={dream_runtime}, model_files={dream_model_files}; smoke={dream_smoke_verdict}."),
    ("设备状态", "等外部输入", f"Home Assistant={ha_verdict}; URL={ha_url}; token={ha_token}."),
    ("低风险控制", "仅预案", f"policy={control_verdict}; actions={control_actions}; enabled={control_enabled}; executed={control_executed}."),
    ("安全/服务收敛", "只读门禁", f"security audit/decision pack present; execution preflight={service_preflight_verdict}."),
]

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "mode": "teacher-facing baseline briefing from latest approved evidence root",
    "nas_root": str(nas_root),
    "report": str(report),
    "evidence": {
        "baseline_gap_decision": str(latest_gap) if latest_gap else None,
        "baseline_status": str(latest_status) if latest_status else None,
        "overnight_summary": str(latest_overnight_summary) if latest_overnight_summary else None,
        "overnight_status": str(latest_overnight_status) if latest_overnight_status else None,
        "stability_summary": str(latest_stability) if latest_stability else None,
        "dream7b_readiness": str(latest_dream_readiness) if latest_dream_readiness else None,
        "dream7b_smoke": str(latest_dream_smoke) if latest_dream_smoke else None,
        "home_assistant": str(latest_ha) if latest_ha else None,
        "control_policy": str(latest_control) if latest_control else None,
        "service_preflight": str(latest_service_preflight) if latest_service_preflight else None,
        "security_audit": str(latest_security) if latest_security else None,
        "service_decision": str(latest_service_decision) if latest_service_decision else None,
        "document_summary": str(latest_document_summary) if latest_document_summary else None,
        "image_caption": str(latest_image_caption) if latest_image_caption else None,
        "vision_readiness": str(latest_vision_readiness) if latest_vision_readiness else None,
        "experiment_report": str(latest_experiment) if latest_experiment else None,
        "dataset_card": str(latest_dataset_card) if latest_dataset_card else None,
    },
    "summary": {
        "snapshot_count": snapshot_count,
        "elapsed_hours": elapsed_hours,
        "stability_verdict": stability_verdict,
        "gateway_status": gateway_status,
        "nas_status": nas_status,
        "artifact_scope": artifact_scope,
        "allowlisted_tool_count": tool_count,
        "overnight_process": overnight_process,
        "overnight_iterations": overnight_iterations,
        "overnight_failed": overnight_failed,
        "dream_verdict": dream_verdict,
        "dream_smoke_verdict": dream_smoke_verdict,
        "ha_verdict": ha_verdict,
        "control_verdict": control_verdict,
        "service_preflight_verdict": service_preflight_verdict,
    },
}

json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

with report.open("w", encoding="utf-8") as out:
    out.write("# S100P + NAS + OpenClaw 双 Baseline 汇报包\n\n")
    out.write(f"- generated_at: {payload['generated_at']}\n")
    out.write("- mode: 从指定证据根目录自动生成；只读，不执行系统修改\n")
    out.write(f"- json: {json_path}\n")
    out.write(f"- source_root: {nas_root}\n\n")

    out.write("## 给导师的一句话\n\n")
    out.write(
        opening_wording +
        "它能替代 PC OpenClaw 的一部分常驻自动化能力，但还不能替代完整 PC 桌面体验；"
        "AI NAS 方向已经抄到了统一工作区、文档/日志/实验报告、ROS 数据集和安全审计，"
        "Dream 7B、Home Assistant 和低风险控制仍需要外部模型文件、凭据或审批输入。\n\n"
    )

    out.write("## 当前关键状态\n\n")
    out.write("| 指标 | 当前值 |\n| --- | --- |\n")
    out.write(f"| Overnight runner | {overnight_process}, iterations={overnight_iterations}, failed={overnight_failed}, verdict={overnight_verdict} |\n")
    out.write(f"| 下一轮采样 | {overnight_next} |\n")
    out.write(f"| A-010 稳定性 | {snapshot_count} snapshots, {elapsed_hours}h, {stability_verdict} |\n")
    out.write(f"| Gateway | {gateway_status} |\n")
    out.write(f"| NAS workspace | {nas_status} |\n")
    out.write(f"| Allowlisted tools | {tool_count} |\n")
    out.write(f"| Dream 7B | readiness={dream_verdict}; smoke={dream_smoke_verdict} |\n")
    out.write(f"| Home Assistant | {ha_verdict} |\n")
    out.write(f"| Control policy | {control_verdict}, enabled={control_enabled}, executed={control_executed} |\n")
    out.write(f"| Service execution preflight | {service_preflight_verdict} |\n\n")

    out.write("## 问题一：S100P 能不能实现 PC OpenClaw 类似效果？\n\n")
    out.write("结论：可以实现 PC OpenClaw 的常驻入口、白名单工具执行和机器人侧数据自动化；NAS 落盘只有在真实 NAS mount 恢复后才能继续声明为 NAS-backed 验收。\n\n")
    out.write("| 能力 | 当前判断 | 汇报口径 |\n| --- | --- | --- |\n")
    for capability, status, wording in pc_parity_items:
        out.write(f"| {capability} | {status} | {wording} |\n")

    out.write("\n## 问题二：高价位 AI NAS / OpenClaw NAS 的作业抄到了什么程度？\n\n")
    out.write(f"结论：{nas_conclusion}\n\n")
    out.write("| NAS 能力 | 当前判断 | 汇报口径 |\n| --- | --- | --- |\n")
    for capability, status, wording in nas_homework_items:
        out.write(f"| {capability} | {status} | {wording} |\n")

    out.write("\n## 不能夸大的边界\n\n")
    out.write(f"- A-010 还不是 7x24 验收，目前只是 {elapsed_hours}h 的 collecting evidence。\n")
    out.write("- Dream 7B 还没有部署成功；当前只是 readiness 和 smoke gate 已接入，缺模型文件和 deployment config。\n")
    out.write("- Home Assistant 还没有真实状态读取，因为缺 URL/token。\n")
    out.write("- B-009 没有执行任何控制动作，enabled=0、executed=0。\n")
    out.write("- B-010 没有执行服务关闭或防火墙修改，仍是只读 preflight。\n\n")

    out.write("## 下一步工作流\n\n")
    out.write("1. 继续让 A-010 跑到 168h，再生成最终稳定性验收摘要。\n")
    out.write("2. 如果 Dream 7B 进入 baseline v1，先把模型放到批准目录并填写 `dream7b_deployment.json`，再跑 bounded smoke。\n")
    out.write("3. 如果要做设备状态，提供 Home Assistant URL/token，先只读 `GET /api/` 和 `GET /api/states`。\n")
    out.write("4. 如果要做低风险控制，先补 reviewed action allowlist、确认语句和 audit retention。\n")
    out.write("5. 如果要做服务收敛，先填 `service_convergence_confirmations.json`，再跑 execution preflight。\n\n")

    out.write("## 证据路径\n\n")
    out.write("| Evidence | Path |\n| --- | --- |\n")
    for key, value in payload["evidence"].items():
        out.write(f"| {key} | {value or 'missing'} |\n")

print(report)
PY
