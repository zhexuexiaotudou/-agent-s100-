# Baseline Progress: B-008 Home Assistant Template Local Refresh

Date: 2026-05-30

The active audit lane is still `continue-non-nas-readonly-only`, so this pass
only added a B-008 configuration template artifact and reran the existing
read-only status probe. It did not write credentials, call Home Assistant, or
enable any control path.

## Implementation

```text
script: scripts/probes/home_assistant_config_template_probe.sh
allowlist id: home_assistant_config_template_probe
windows action: refresh-baseline-local-readonly
output: /root/.openclaw/workspace/reports/home-assistant
runtime target not written: /root/.openclaw/workspace/config/home_assistant.env
```

The template records the expected environment variables and the read-only API
contract:

```text
HOME_ASSISTANT_URL=http://homeassistant.local:8123
HOME_ASSISTANT_TOKEN=replace_with_long_lived_access_token
allowed: GET /api/, GET /api/states
blocked: POST /api/services/*, POST /api/states/*, WebSocket control commands
```

## Latest Evidence

```text
config template: /root/.openclaw/workspace/reports/home-assistant/home_assistant_config_template_20260530-162335.md
status probe: /root/.openclaw/workspace/logs/probes/home_assistant_status_20260530-162335.md
baseline status: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-162335.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-162335.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-162336.md
manifest entry: home_assistant_template true sha256=157a04e234999bf1
```

The status probe reported:

```text
mode: read-only
control_api_called: no
services_api_called: no
URL configured: no
Token configured: no
GET /api/ status: not_attempted
GET /api/states status: not_attempted
Verdict: blocked_no_config
```

## Tracking Impact

B-008 remains `blocked_external_config`. The missing step is now precise:
create `/root/.openclaw/workspace/config/home_assistant.env` deliberately with
the HA URL and long-lived token, then rerun the read-only status probe. This
change does not authorize B-009 control actions.
