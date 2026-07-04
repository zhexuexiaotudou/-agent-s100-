# 21220 journal_live_regression_gate

- generated_at: 2026-07-04T08:49:53Z
- status: pass
- verdict: journal_live_regression_gate_passed

```json
{
  "disable_journal_feature_probe": {
    "command": [
      "ssh",
      "-i",
      "%USERPROFILE%\\.ssh\\s100p_linkcheck_ed25519",
      "-o",
      "BatchMode=yes",
      "-o",
      "ConnectTimeout=8",
      "sunrise@192.168.127.10",
      "\nset -eu\ncd '/mnt/nas/openclaw'\npython3 - <<'PY'\nimport json\nfrom pathlib import Path\nsrc = Path(\"configs/journal_feature_flags.json\")\ndst = Path('/mnt/nas/openclaw/reports/qwen25_ai_nas/digua_journal_disable_feature_probe_20260704-164949.json')\ndst.parent.mkdir(parents=True, exist_ok=True)\ndst.write_text(src.read_text(encoding=\"utf-8\"), encoding=\"utf-8\")\nprint(json.dumps({\"ok\": True, \"probe_path\": str(dst)}))\nPY\nJOURNAL_FEATURE_FLAGS='/mnt/nas/openclaw/reports/qwen25_ai_nas/digua_journal_disable_feature_probe_20260704-164949.json' sh scripts/disable_journal_feature.sh\npython3 - <<'PY'\nimport json\nfrom pathlib import Path\npath = Path('/mnt/nas/openclaw/reports/qwen25_ai_nas/digua_journal_disable_feature_probe_20260704-164949.json')\npayload = json.loads(path.read_text(encoding=\"utf-8\"))\nchecks = {\n  \"journal_workspace_enabled_false\": payload.get(\"journal_workspace_enabled\") is False,\n  \"cloud_generation_enabled_false\": payload.get(\"cloud_generation_enabled\") is False,\n  \"qwen_execution_authority_false\": payload.get(\"qwen_execution_authority\") is False,\n  \"real_nas_write_enabled_false\": payload.get(\"real_nas_write_enabled\") is False,\n}\nprint(json.dumps({\"ok\": all(checks.values()), \"probe_path\": str(path), \"checks\": checks, \"payload\": payload}, ensure_ascii=False, sort_keys=True))\nPY\n"
    ],
    "elapsed_ms": 330.772,
    "json": {
      "checks": {
        "cloud_generation_enabled_false": true,
        "journal_workspace_enabled_false": true,
        "qwen_execution_authority_false": true,
        "real_nas_write_enabled_false": true
      },
      "ok": true,
      "payload": {
        "cloud_generation_enabled": false,
        "collect_copy_route": true,
        "collect_document_rag": true,
        "collect_nas_index_diff": true,
        "collect_openclaw": true,
        "collect_reports": true,
        "collect_token_budget": true,
        "collect_workspace_harness": true,
        "feature": "digua_journal",
        "journal_workspace_enabled": false,
        "manual_entry_enabled": true,
        "markdown_export_enabled": true,
        "period_summary_enabled": true,
        "qwen_execution_authority": false,
        "qwen_summary_enabled": true,
        "real_nas_write_enabled": false,
        "screenshots_enabled": false
      },
      "probe_path": "/mnt/nas/openclaw/reports/qwen25_ai_nas/digua_journal_disable_feature_probe_20260704-164949.json"
    },
    "ok": true,
    "returncode": 0,
    "stderr": "",
    "stdout": "{\"ok\": true, \"probe_path\": \"/mnt/nas/openclaw/reports/qwen25_ai_nas/digua_journal_disable_feature_probe_20260704-164949.json\"}\n{\"ok\": true, \"path\": \"/mnt/nas/openclaw/reports/qwen25_ai_nas/digua_journal_disable_feature_probe_20260704-164949.json\", \"journal_workspace_enabled\": false}\n{\"checks\": {\"cloud_generation_enabled_false\": true, \"journal_workspace_enabled_false\": true, \"qwen_execution_authority_false\": true, \"real_nas_write_enabled_false\": true}, \"ok\": true, \"payload\": {\"cloud_generation_enabled\": false, \"collect_copy_route\": true, \"collect_document_rag\": true, \"collect_nas_index_diff\": true, \"collect_openclaw\": true, \"collect_reports\": true, \"collect_token_budget\": true, \"collect_workspace_harness\": true, \"feature\": \"digua_journal\", \"journal_workspace_enabled\": false, \"manual_entry_enabled\": true, \"markdown_export_enabled\": true, \"period_summary_enabled\": true, \"qwen_execution_authority\": false, \"qwen_summary_enabled\": true, \"real_nas_write_enabled\": false, \"screenshots_enabled\": false}, \"probe_path\": \"/mnt/nas/openclaw/reports/qwen25_ai_nas/digua_journal_disable_feature_probe_20260704-164949.json\"}"
  },
  "generated_at": "2026-07-04T08:49:53Z",
  "hard_constraints": {
    "cloud_generation_enabled": false,
    "delete_move_rename_chmod_executed": false,
    "desktop_visual_enabled": false,
    "keyboard_mouse_tracking_enabled": false,
    "openclaw_replaced": false,
    "ports_8765_18080_18888_18889_modified": false,
    "private_nas_raw_content_uploaded": false,
    "qwen_replaced": false,
    "qwen_tool_execution_authority": false,
    "screenshot_enabled": false
  },
  "local_regression": {
    "ok": true,
    "py_compile": {
      "command": [
        "%USERPROFILE%\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe",
        "-m",
        "py_compile",
        "src/digua_journal/__init__.py",
        "src/digua_journal/collectors/__init__.py",
        "src/digua_journal/collectors/copy_route_collector.py",
        "src/digua_journal/collectors/harness_trace_collector.py",
        "src/digua_journal/collectors/nas_index_diff_collector.py",
        "src/digua_journal/collectors/openclaw_collector.py",
        "src/digua_journal/collectors/rag_collector.py",
        "src/digua_journal/collectors/report_collector.py",
        "src/digua_journal/collectors/system_collectors.py",
        "src/digua_journal/collectors/token_budget_collector.py",
        "src/digua_journal/event_model.py",
        "src/digua_journal/journal_db.py",
        "src/digua_journal/journal_exporter.py",
        "src/digua_journal/journal_migrations.py",
        "src/digua_journal/journal_privacy_guard.py",
        "src/digua_journal/journal_retention_policy.py",
        "src/digua_journal/journal_token_trace.py",
        "src/digua_journal/manual_entry.py",
        "src/digua_journal/period_summary_engine.py",
        "src/digua_journal/project_classifier.py",
        "src/digua_journal/summary_templates.py",
        "src/openclaw/routes/journal_routes.py",
        "scripts/probes/ai_nas_operator_portal_server.py",
        "scripts/probes/digua_journal_live_rollout.py"
      ],
      "elapsed_ms": 117.045,
      "ok": true,
      "returncode": 0,
      "stderr": "",
      "stdout": ""
    },
    "pytest": {
      "command": [
        "%USERPROFILE%\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe",
        "-m",
        "pytest",
        "tests/test_journal_event_model.py",
        "tests/test_journal_db.py",
        "tests/test_nas_index_diff_collector.py",
        "tests/test_journal_system_collectors.py",
        "tests/test_manual_entry.py",
        "tests/test_project_classifier.py",
        "tests/test_period_summary_engine.py",
        "tests/test_journal_token_privacy.py",
        "tests/test_journal_exporter.py",
        "tests/test_journal_routes.py",
        "-q"
      ],
      "elapsed_ms": 2039.5,
      "ok": true,
      "returncode": 0,
      "stderr": "",
      "stdout": "............                                                             [100%]\n12 passed in 1.65s"
    }
  },
  "post_rollout_services": {
    "openclaw_active": "active",
    "openclaw_enabled": "enabled",
    "qwen_active": "active",
    "qwen_enabled": "enabled"
  },
  "protected_ports_unchanged": true,
  "remote_compile": {
    "command": [
      "ssh",
      "-i",
      "%USERPROFILE%\\.ssh\\s100p_linkcheck_ed25519",
      "-o",
      "BatchMode=yes",
      "-o",
      "ConnectTimeout=8",
      "sunrise@192.168.127.10",
      "\nset -eu\ncd '/mnt/nas/openclaw'\npython3 - <<'PY'\nimport json, py_compile\nfrom pathlib import Path\n\npaths = [\n    Path(\"scripts/probes/ai_nas_operator_portal_server.py\"),\n    Path(\"scripts/probes/digua_journal_production_deployment.py\"),\n    Path(\"src/openclaw/routes/journal_routes.py\"),\n]\npaths.extend(sorted(Path(\"src/digua_journal\").rglob(\"*.py\")))\ncompiled = []\nerrors = []\nfor path in paths:\n    try:\n        py_compile.compile(str(path), doraise=True)\n        compiled.append(str(path))\n    except Exception as exc:\n        errors.append({\"path\": str(path), \"error\": f\"{type(exc).__name__}: {exc}\"})\nprint(json.dumps({\"ok\": not errors, \"compiled_count\": len(compiled), \"errors\": errors}, ensure_ascii=False, sort_keys=True))\nPY\n"
    ],
    "elapsed_ms": 334.904,
    "json": {
      "compiled_count": 24,
      "errors": [],
      "ok": true
    },
    "ok": true,
    "returncode": 0,
    "stderr": "",
    "stdout": "{\"compiled_count\": 24, \"errors\": [], \"ok\": true}"
  },
  "report_id": 21220,
  "status": "pass",
  "title": "journal_live_regression_gate",
  "verdict": "journal_live_regression_gate_passed"
}
```
