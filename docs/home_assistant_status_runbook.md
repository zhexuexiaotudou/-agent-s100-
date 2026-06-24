# Home Assistant Read-Only Status Runbook

This runbook covers B-008: read Home Assistant or device state without issuing
control actions.

## Scope

Allowed:

- Detect whether Home Assistant URL and token are configured.
- Call `GET /api/`.
- Call `GET /api/states`.
- Count entities and summarize entity domains.
- Write a redacted Markdown report.

Not allowed:

- Calling `/api/services`.
- Toggling devices or scenes.
- Writing Home Assistant configuration.
- Printing tokens in reports or logs.

## Configuration

Preferred board-side config file:

```bash
/root/.openclaw/workspace/config/home_assistant.env
```

Expected keys:

```bash
HOME_ASSISTANT_URL=http://homeassistant.local:8123
HOME_ASSISTANT_TOKEN=replace-with-long-lived-token
```

The probe also checks process environment variables and
`/root/.openclaw/credentials/home-assistant.env`. Tokens are never printed.

## Local Runner

```bash
scripts/run_allowlisted_tool.sh home_assistant_status_probe
```

Default output:

```bash
/root/.openclaw/workspace/logs/probes/home_assistant_status_<stamp>.md
```

If `/mnt/nas/openclaw/logs/probes` is mounted and writable, the probe will use
the NAS path by default.

## OpenClaw Tool

Use the narrow plugin tool:

```text
s100p_run_probe tool_id=home_assistant_status_probe
```

The tool accepts only the allowlisted ID; it does not accept shell commands or
arbitrary script paths.

## Acceptance

B-008 is only verified when:

- A report exists.
- `control_api_called: no`.
- `services_api_called: no`.
- `GET /api/ status` is `200`.
- `GET /api/states status` is `200`.
- The report includes an entity count.

Without URL/token, the expected verdict is `blocked_no_config`, which is useful
preflight evidence but not final verification.
