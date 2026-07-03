# Open Source Release Checklist

Use this checklist before publishing the Dream7B S100P / AI-NAS package.

## Required Checks

```bash
python3 -m py_compile scripts/probes/dream7b_perf_identity_probe.py scripts/probes/ai_nas_edge_cloud_router_probe.py
python3 scripts/probes/dream7b_perf_identity_probe.py --mock --report-root /tmp/dream7b_release_check
python3 scripts/probes/ai_nas_edge_cloud_router_probe.py --report-root /tmp/dream7b_release_check
bash scripts/probes/ai_nas_allowlisted_tool.sh dream7b_perf_identity --mock --report-root /tmp/dream7b_release_check
bash scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_edge_cloud_router --report-root /tmp/dream7b_release_check
```

On S100P, additionally run:

```bash
python3 scripts/probes/dream7b_perf_identity_probe.py --base-url http://127.0.0.1:18888
python3 scripts/probes/ai_nas_edge_cloud_router_probe.py --use-dream-classifier
python3 scripts/probes/ai_nas_appliance_experience_acceptance_probe.py
```

## Files To Keep

- Core Dream7B gateway, queue, benchmark, and rollback scripts.
- AI-NAS allowlisted probes and dispatcher.
- systemd templates for Dream7B queue, Dream7B gateway, OpenClaw gateway, and AI-NAS index daemon.
- `docs/community/dream7b-s100-bpu-deploy/SKILL.md`.
- Demo runbooks and anonymized benchmark reports.

## Files To Remove Or Redact

- SSH keys, API keys, access tokens, cookies, and `.env` secrets.
- Real personal NAS files, private screenshots, invoices, family photos, and chat logs.
- Local machine usernames if not needed for reproduction.
- Large HBM/model artifacts unless the release target explicitly supports large files.
- Raw transient logs under `tmp/`, `logs/`, and generated report folders that contain private paths.

## Claim Rules

- Only quote Dream7B performance numbers from the latest `dream7b_perf_identity` and BPU telemetry reports.
- State that Dream7B is diffusion-style; standard prefill/decode numbers are compatibility metrics unless native phase timing is available.
- Do not claim sustained 100 percent average BPU utilization.
- Keep the AI-NAS positioning clear: cheap NAS handles storage; S100P provides the local intelligence layer.

