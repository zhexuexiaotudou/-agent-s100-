# 21200 journal_live_rollout_gate

- generated_at: 2026-07-04T08:49:53Z
- status: pass
- verdict: journal_live_rollout_service_gate_passed

```json
{
  "after": {
    "health": {
      "openclaw": {
        "ok": true,
        "payload": {
          "ok": true,
          "operator_portal_contract": {
            "filename": "operator_portal_contract.json",
            "found": true,
            "generated_at": "2026-06-18T16:04:08.346324+08:00",
            "path": "/mnt/nas/openclaw/reports/ai_nas_mvp/operator_portal_contract_20260618-160406-445747/operator_portal_contract.json",
            "selection_policy": "generated_at_then_mtime",
            "verdict": "ok_ai_nas_operator_portal_contract"
          },
          "portal_html": "/mnt/nas/openclaw/reports/ai_nas_mvp/operator_portal_contract_20260618-160406-445747/operator_portal.html",
          "refresh_on_start": null,
          "tool_id": "ai_nas_operator_portal_server"
        },
        "returncode": 0,
        "stderr": ""
      },
      "qwen": {
        "ok": true,
        "payload": {
          "active_hbm": {
            "exists": false,
            "path": "/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_runtime/model/Qwen2.5_1.5B_Instruct_512.hbm",
            "size_bytes": 0
          },
          "active_profile": "qwen25_7b_instruct_cache_len_1024_q8",
          "backend": "official-qwen2.5-oellm-multichat-plus-ai-nas-tools",
          "model": "Qwen2.5-1.5B-Instruct-S100P-official",
          "ok": true,
          "port": 18080,
          "priority_hbm": {
            "exists": false,
            "path": "/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_runtime/model/Qwen2.5_1.5B_Instruct_512.hbm",
            "size_bytes": 0
          },
          "priority_profile": "qwen25_7b_instruct_cache_len_1024_q8_vendor_default",
          "priority_status": "promoted_from_shadow_18081",
          "report_root": "/mnt/nas/openclaw/reports/qwen25_ai_nas",
          "tool_dispatcher": "/mnt/nas/openclaw/scripts/probes/ai_nas_allowlisted_tool.sh"
        },
        "returncode": 0,
        "stderr": ""
      }
    },
    "hostname": "ubuntu",
    "ip_addr": "lo               UNKNOWN        127.0.0.1/8 ::1/128 \neth0             UP             169.254.8.10/16 fe80::6c75:dfff:fe40:9cbc/64 \neth1             UP             192.168.127.10/24 192.168.137.10/24 \ndocker0          DOWN           172.17.0.1/16",
    "ip_route": "default via 192.168.137.1 dev eth1 metric 50 \ndefault via 192.168.137.1 dev eth1 proto static metric 50 \n169.254.0.0/16 dev eth0 proto kernel scope link src 169.254.8.10 metric 100 \n169.254.0.0/16 dev eth0 scope link src 169.254.8.10 metric 101 \n172.17.0.0/16 dev docker0 proto kernel scope link src 172.17.0.1 linkdown \n192.168.127.0/24 dev eth1 proto kernel scope link src 192.168.127.10 metric 101 \n192.168.127.0/24 dev eth0 metric 700 \n192.168.137.0/24 dev eth1 proto kernel scope link src 192.168.137.10 metric 101",
    "label": "after_live_rollout",
    "linger": "Linger=yes",
    "ok": true,
    "protected_ports": {
      "hash": "4d1d8e449477939a131ae2e101458ca7f3e1bd6a53f2181bfa39c38c26d86ccb",
      "normalized": [
        "127.0.0.1:18080",
        "127.0.0.1:18888",
        "127.0.0.1:8765"
      ],
      "raw": [
        "LISTEN 0      5          127.0.0.1:18888 0.0.0.0:*                                     ",
        "LISTEN 0      5          127.0.0.1:18080 0.0.0.0:* users:((\"python3\",pid=1028631,fd=3))",
        "LISTEN 0      5          127.0.0.1:8765  0.0.0.0:* users:((\"python3\",pid=1064456,fd=3))"
      ]
    },
    "services": {
      "openclaw_active": "active",
      "openclaw_enabled": "enabled",
      "qwen_active": "active",
      "qwen_enabled": "enabled"
    },
    "user": "sunrise"
  },
  "after_restart": {
    "health": {
      "openclaw": {
        "ok": true,
        "payload": {
          "ok": true,
          "operator_portal_contract": {
            "filename": "operator_portal_contract.json",
            "found": true,
            "generated_at": "2026-06-18T16:04:08.346324+08:00",
            "path": "/mnt/nas/openclaw/reports/ai_nas_mvp/operator_portal_contract_20260618-160406-445747/operator_portal_contract.json",
            "selection_policy": "generated_at_then_mtime",
            "verdict": "ok_ai_nas_operator_portal_contract"
          },
          "portal_html": "/mnt/nas/openclaw/reports/ai_nas_mvp/operator_portal_contract_20260618-160406-445747/operator_portal.html",
          "refresh_on_start": null,
          "tool_id": "ai_nas_operator_portal_server"
        },
        "returncode": 0,
        "stderr": ""
      },
      "qwen": {
        "ok": true,
        "payload": {
          "active_hbm": {
            "exists": false,
            "path": "/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_runtime/model/Qwen2.5_1.5B_Instruct_512.hbm",
            "size_bytes": 0
          },
          "active_profile": "qwen25_7b_instruct_cache_len_1024_q8",
          "backend": "official-qwen2.5-oellm-multichat-plus-ai-nas-tools",
          "model": "Qwen2.5-1.5B-Instruct-S100P-official",
          "ok": true,
          "port": 18080,
          "priority_hbm": {
            "exists": false,
            "path": "/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_runtime/model/Qwen2.5_1.5B_Instruct_512.hbm",
            "size_bytes": 0
          },
          "priority_profile": "qwen25_7b_instruct_cache_len_1024_q8_vendor_default",
          "priority_status": "promoted_from_shadow_18081",
          "report_root": "/mnt/nas/openclaw/reports/qwen25_ai_nas",
          "tool_dispatcher": "/mnt/nas/openclaw/scripts/probes/ai_nas_allowlisted_tool.sh"
        },
        "returncode": 0,
        "stderr": ""
      }
    },
    "hostname": "ubuntu",
    "ip_addr": "lo               UNKNOWN        127.0.0.1/8 ::1/128 \neth0             UP             169.254.8.10/16 fe80::6c75:dfff:fe40:9cbc/64 \neth1             UP             192.168.127.10/24 192.168.137.10/24 \ndocker0          DOWN           172.17.0.1/16",
    "ip_route": "default via 192.168.137.1 dev eth1 metric 50 \ndefault via 192.168.137.1 dev eth1 proto static metric 50 \n169.254.0.0/16 dev eth0 proto kernel scope link src 169.254.8.10 metric 100 \n169.254.0.0/16 dev eth0 scope link src 169.254.8.10 metric 101 \n172.17.0.0/16 dev docker0 proto kernel scope link src 172.17.0.1 linkdown \n192.168.127.0/24 dev eth1 proto kernel scope link src 192.168.127.10 metric 101 \n192.168.127.0/24 dev eth0 metric 700 \n192.168.137.0/24 dev eth1 proto kernel scope link src 192.168.137.10 metric 101",
    "label": "after_openclaw_restart",
    "linger": "Linger=yes",
    "ok": true,
    "protected_ports": {
      "hash": "4d1d8e449477939a131ae2e101458ca7f3e1bd6a53f2181bfa39c38c26d86ccb",
      "normalized": [
        "127.0.0.1:18080",
        "127.0.0.1:18888",
        "127.0.0.1:8765"
      ],
      "raw": [
        "LISTEN 0      5          127.0.0.1:18888 0.0.0.0:*                                     ",
        "LISTEN 0      5          127.0.0.1:18080 0.0.0.0:* users:((\"python3\",pid=1028631,fd=3))",
        "LISTEN 0      5          127.0.0.1:8765  0.0.0.0:* users:((\"python3\",pid=1064456,fd=3))"
      ]
    },
    "services": {
      "openclaw_active": "active",
      "openclaw_enabled": "enabled",
      "qwen_active": "active",
      "qwen_enabled": "enabled"
    },
    "user": "sunrise"
  },
  "approval": {
    "approval_file": "operator_approval/digua_journal_live_rollout_approved.json",
    "approval_file_exists": false,
    "approval_file_payload": null,
    "approved": true,
    "env_name": "AI_NAS_OPERATOR_APPROVED_DIGUA_JOURNAL_LIVE_ROLLOUT",
    "env_value_is_1": true
  },
  "before": {
    "health": {
      "openclaw": {
        "ok": true,
        "payload": {
          "ok": true,
          "operator_portal_contract": {
            "filename": "operator_portal_contract.json",
            "found": true,
            "generated_at": "2026-06-18T16:04:08.346324+08:00",
            "path": "/mnt/nas/openclaw/reports/ai_nas_mvp/operator_portal_contract_20260618-160406-445747/operator_portal_contract.json",
            "selection_policy": "generated_at_then_mtime",
            "verdict": "ok_ai_nas_operator_portal_contract"
          },
          "portal_html": "/mnt/nas/openclaw/reports/ai_nas_mvp/operator_portal_contract_20260618-160406-445747/operator_portal.html",
          "refresh_on_start": null,
          "tool_id": "ai_nas_operator_portal_server"
        },
        "returncode": 0,
        "stderr": ""
      },
      "qwen": {
        "ok": true,
        "payload": {
          "active_hbm": {
            "exists": false,
            "path": "/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_runtime/model/Qwen2.5_1.5B_Instruct_512.hbm",
            "size_bytes": 0
          },
          "active_profile": "qwen25_7b_instruct_cache_len_1024_q8",
          "backend": "official-qwen2.5-oellm-multichat-plus-ai-nas-tools",
          "model": "Qwen2.5-1.5B-Instruct-S100P-official",
          "ok": true,
          "port": 18080,
          "priority_hbm": {
            "exists": false,
            "path": "/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_runtime/model/Qwen2.5_1.5B_Instruct_512.hbm",
            "size_bytes": 0
          },
          "priority_profile": "qwen25_7b_instruct_cache_len_1024_q8_vendor_default",
          "priority_status": "promoted_from_shadow_18081",
          "report_root": "/mnt/nas/openclaw/reports/qwen25_ai_nas",
          "tool_dispatcher": "/mnt/nas/openclaw/scripts/probes/ai_nas_allowlisted_tool.sh"
        },
        "returncode": 0,
        "stderr": ""
      }
    },
    "hostname": "ubuntu",
    "ip_addr": "lo               UNKNOWN        127.0.0.1/8 ::1/128 \neth0             UP             169.254.8.10/16 fe80::6c75:dfff:fe40:9cbc/64 \neth1             UP             192.168.127.10/24 192.168.137.10/24 \ndocker0          DOWN           172.17.0.1/16",
    "ip_route": "default via 192.168.137.1 dev eth1 metric 50 \ndefault via 192.168.137.1 dev eth1 proto static metric 50 \n169.254.0.0/16 dev eth0 proto kernel scope link src 169.254.8.10 metric 100 \n169.254.0.0/16 dev eth0 scope link src 169.254.8.10 metric 101 \n172.17.0.0/16 dev docker0 proto kernel scope link src 172.17.0.1 linkdown \n192.168.127.0/24 dev eth1 proto kernel scope link src 192.168.127.10 metric 101 \n192.168.127.0/24 dev eth0 metric 700 \n192.168.137.0/24 dev eth1 proto kernel scope link src 192.168.137.10 metric 101",
    "label": "before_live_rollout",
    "linger": "Linger=yes",
    "ok": true,
    "protected_ports": {
      "hash": "4d1d8e449477939a131ae2e101458ca7f3e1bd6a53f2181bfa39c38c26d86ccb",
      "normalized": [
        "127.0.0.1:18080",
        "127.0.0.1:18888",
        "127.0.0.1:8765"
      ],
      "raw": [
        "LISTEN 0      5          127.0.0.1:18888 0.0.0.0:*                                     ",
        "LISTEN 0      5          127.0.0.1:18080 0.0.0.0:* users:((\"python3\",pid=1028631,fd=3))",
        "LISTEN 0      5          127.0.0.1:8765  0.0.0.0:* users:((\"python3\",pid=1062596,fd=3))"
      ]
    },
    "services": {
      "openclaw_active": "active",
      "openclaw_enabled": "enabled",
      "qwen_active": "active",
      "qwen_enabled": "enabled"
    },
    "user": "sunrise"
  },
  "feature_flags": {
    "command": [
      "ssh",
      "-i",
      "%USERPROFILE%\\.ssh\\s100p_linkcheck_ed25519",
      "-o",
      "BatchMode=yes",
      "-o",
      "ConnectTimeout=8",
      "sunrise@192.168.127.10",
      "python3 - <<'PY'\nimport json\nfrom pathlib import Path\n\npath = Path('/mnt/nas/openclaw') / \"configs\" / \"journal_feature_flags.json\"\nflags = json.loads(path.read_text(encoding=\"utf-8\"))\nchecks = {\n    \"journal_workspace_enabled\": flags.get(\"journal_workspace_enabled\") is True,\n    \"cloud_generation_enabled_false\": flags.get(\"cloud_generation_enabled\") is False,\n    \"qwen_execution_authority_false\": flags.get(\"qwen_execution_authority\") is False,\n    \"screenshots_enabled_false\": flags.get(\"screenshots_enabled\") is False,\n    \"real_nas_write_enabled_false\": flags.get(\"real_nas_write_enabled\") is False,\n}\nprint(json.dumps({\"ok\": all(checks.values()), \"path\": str(path), \"feature_flags\": flags, \"checks\": checks}, ensure_ascii=False, sort_keys=True))\nPY"
    ],
    "elapsed_ms": 272.22,
    "json": {
      "checks": {
        "cloud_generation_enabled_false": true,
        "journal_workspace_enabled": true,
        "qwen_execution_authority_false": true,
        "real_nas_write_enabled_false": true,
        "screenshots_enabled_false": true
      },
      "feature_flags": {
        "cloud_generation_enabled": false,
        "collect_copy_route": true,
        "collect_document_rag": true,
        "collect_nas_index_diff": true,
        "collect_openclaw": true,
        "collect_reports": true,
        "collect_token_budget": true,
        "collect_workspace_harness": true,
        "feature": "digua_journal",
        "journal_workspace_enabled": true,
        "manual_entry_enabled": true,
        "markdown_export_enabled": true,
        "period_summary_enabled": true,
        "qwen_execution_authority": false,
        "qwen_summary_enabled": true,
        "real_nas_write_enabled": false,
        "screenshots_enabled": false
      },
      "ok": true,
      "path": "/mnt/nas/openclaw/configs/journal_feature_flags.json"
    },
    "ok": true,
    "returncode": 0,
    "stderr": "",
    "stdout": "{\"checks\": {\"cloud_generation_enabled_false\": true, \"journal_workspace_enabled\": true, \"qwen_execution_authority_false\": true, \"real_nas_write_enabled_false\": true, \"screenshots_enabled_false\": true}, \"feature_flags\": {\"cloud_generation_enabled\": false, \"collect_copy_route\": true, \"collect_document_rag\": true, \"collect_nas_index_diff\": true, \"collect_openclaw\": true, \"collect_reports\": true, \"collect_token_budget\": true, \"collect_workspace_harness\": true, \"feature\": \"digua_journal\", \"journal_workspace_enabled\": true, \"manual_entry_enabled\": true, \"markdown_export_enabled\": true, \"period_summary_enabled\": true, \"qwen_execution_authority\": false, \"qwen_summary_enabled\": true, \"real_nas_write_enabled\": false, \"screenshots_enabled\": false}, \"ok\": true, \"path\": \"/mnt/nas/openclaw/configs/journal_feature_flags.json\"}"
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
  "journal_db": "/mnt/nas/openclaw/reports/qwen25_ai_nas/digua_journal.sqlite3",
  "migration": {
    "command": [
      "ssh",
      "-i",
      "%USERPROFILE%\\.ssh\\s100p_linkcheck_ed25519",
      "-o",
      "BatchMode=yes",
      "-o",
      "ConnectTimeout=8",
      "sunrise@192.168.127.10",
      "python3 - <<'PY'\nimport json, sys\nfrom pathlib import Path\n\nroot = Path('/mnt/nas/openclaw')\nsys.path.insert(0, str(root))\nfrom src.digua_journal.journal_db import JournalDB\n\ndb = JournalDB('/mnt/nas/openclaw/reports/qwen25_ai_nas/digua_journal.sqlite3')\nmigration = db.migrate()\nprint(json.dumps({\"ok\": True, \"migration\": migration, \"stats\": db.stats()}, ensure_ascii=False, sort_keys=True))\nPY"
    ],
    "elapsed_ms": 344.207,
    "json": {
      "migration": {
        "db_path": "/mnt/nas/openclaw/reports/qwen25_ai_nas/digua_journal.sqlite3",
        "ok": true,
        "schema_version": 1
      },
      "ok": true,
      "stats": {
        "journal_events": 80,
        "journal_exports": 4,
        "journal_manual_entries": 4,
        "journal_project_map": 0,
        "journal_summary_runs": 16,
        "journal_token_privacy_traces": 16
      }
    },
    "ok": true,
    "returncode": 0,
    "stderr": "",
    "stdout": "{\"migration\": {\"db_path\": \"/mnt/nas/openclaw/reports/qwen25_ai_nas/digua_journal.sqlite3\", \"ok\": true, \"schema_version\": 1}, \"ok\": true, \"stats\": {\"journal_events\": 80, \"journal_exports\": 4, \"journal_manual_entries\": 4, \"journal_project_map\": 0, \"journal_summary_runs\": 16, \"journal_token_privacy_traces\": 16}}"
  },
  "openclaw_reload_attempted": true,
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
  "remote_report_root": "/mnt/nas/openclaw/reports/qwen25_ai_nas",
  "remote_root": "/mnt/nas/openclaw",
  "report_id": 21200,
  "restart": {
    "command": [
      "ssh",
      "-i",
      "%USERPROFILE%\\.ssh\\s100p_linkcheck_ed25519",
      "-o",
      "BatchMode=yes",
      "-o",
      "ConnectTimeout=8",
      "sunrise@192.168.127.10",
      "\nset -eu\nsystemctl --user restart openclaw-gateway.service\npython3 - <<'PY'\nimport json, subprocess, time\n\nattempts = []\nok = False\nfor index in range(30):\n    health = subprocess.run([\"curl\", \"-fsS\", \"http://127.0.0.1:8765/api/health\"], text=True, capture_output=True)\n    service = subprocess.run([\"systemctl\", \"--user\", \"is-active\", \"openclaw-gateway.service\"], text=True, capture_output=True)\n    attempts.append({\n        \"index\": index,\n        \"curl_returncode\": health.returncode,\n        \"service\": service.stdout.strip(),\n        \"stderr\": health.stderr.strip()[-500:],\n    })\n    if health.returncode == 0 and service.stdout.strip() == \"active\":\n        ok = True\n        break\n    time.sleep(1)\nenabled = subprocess.run([\"systemctl\", \"--user\", \"is-enabled\", \"openclaw-gateway.service\"], text=True, capture_output=True)\nprint(json.dumps({\"ok\": ok, \"attempts\": attempts[-5:], \"enabled\": enabled.stdout.strip()}, ensure_ascii=False, sort_keys=True))\nPY\n"
    ],
    "elapsed_ms": 1996.928,
    "json": {
      "attempts": [
        {
          "curl_returncode": 7,
          "index": 0,
          "service": "active",
          "stderr": "curl: (7) Failed to connect to 127.0.0.1 port 8765 after 0 ms: Connection refused"
        },
        {
          "curl_returncode": 0,
          "index": 1,
          "service": "active",
          "stderr": ""
        }
      ],
      "enabled": "enabled",
      "ok": true
    },
    "ok": true,
    "returncode": 0,
    "stderr": "",
    "stdout": "{\"attempts\": [{\"curl_returncode\": 7, \"index\": 0, \"service\": \"active\", \"stderr\": \"curl: (7) Failed to connect to 127.0.0.1 port 8765 after 0 ms: Connection refused\"}, {\"curl_returncode\": 0, \"index\": 1, \"service\": \"active\", \"stderr\": \"\"}], \"enabled\": \"enabled\", \"ok\": true}"
  },
  "s100p_host": "sunrise@192.168.127.10",
  "s100p_service_mutation_attempted": true,
  "status": "pass",
  "sync": {
    "files": [
      "configs/journal_feature_flags.json",
      "configs/journal_workspace.json",
      "migrations/create_digua_journal_tables.sql",
      "scripts/check_journal_service_status.sh",
      "scripts/disable_journal_feature.sh",
      "scripts/probes/ai_nas_operator_portal_server.py",
      "scripts/probes/digua_journal_production_deployment.py",
      "scripts/run_journal_collectors_once.sh",
      "scripts/run_journal_e2e_smoke.sh",
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
      "src/openclaw/__init__.py",
      "src/openclaw/routes/__init__.py",
      "src/openclaw/routes/journal_routes.py",
      "web/digua_journal.html",
      "web/static/digua_journal.css",
      "web/static/digua_journal.js"
    ],
    "mkdir": {
      "command": [
        "ssh",
        "-i",
        "%USERPROFILE%\\.ssh\\s100p_linkcheck_ed25519",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=8",
        "sunrise@192.168.127.10",
        "set -eu\nmkdir -p '/mnt/nas/openclaw/configs'\nmkdir -p '/mnt/nas/openclaw/migrations'\nmkdir -p '/mnt/nas/openclaw/scripts'\nmkdir -p '/mnt/nas/openclaw/scripts/probes'\nmkdir -p '/mnt/nas/openclaw/src/digua_journal'\nmkdir -p '/mnt/nas/openclaw/src/digua_journal/collectors'\nmkdir -p '/mnt/nas/openclaw/src/openclaw'\nmkdir -p '/mnt/nas/openclaw/src/openclaw/routes'\nmkdir -p '/mnt/nas/openclaw/web'\nmkdir -p '/mnt/nas/openclaw/web/static'"
      ],
      "elapsed_ms": 216.553,
      "ok": true,
      "returncode": 0,
      "stderr": "",
      "stdout": ""
    },
    "ok": true,
    "transfers": [
      {
        "bytes": 564,
        "ok": true,
        "path": "configs/journal_feature_flags.json",
        "sha256": "5871be01140d8633736a1e0ba203208933da10a18ac068876395c0b8a86ef22e",
        "stderr": ""
      },
      {
        "bytes": 828,
        "ok": true,
        "path": "configs/journal_workspace.json",
        "sha256": "15ab5a527ae01ee239e0b79921cb61352b109002ecedadfef4dfcce7759832c3",
        "stderr": ""
      },
      {
        "bytes": 2790,
        "ok": true,
        "path": "migrations/create_digua_journal_tables.sql",
        "sha256": "51bc07277cbef2c608044a5c8b60b25e988b18076b6eeec79f5b6446b6ac9ed0",
        "stderr": ""
      },
      {
        "bytes": 122,
        "ok": true,
        "path": "scripts/check_journal_service_status.sh",
        "sha256": "a078efabc132890997ef1d3bfa2a77e1218904fc976480daa13c269dba873ff1",
        "stderr": ""
      },
      {
        "bytes": 640,
        "ok": true,
        "path": "scripts/disable_journal_feature.sh",
        "sha256": "0054d14347f372d3bc5cb33c389887d097669c9946cf7f6551bb052784a1b16f",
        "stderr": ""
      },
      {
        "bytes": 96073,
        "ok": true,
        "path": "scripts/probes/ai_nas_operator_portal_server.py",
        "sha256": "6f674646f090f0138c036ad33075a38dc5b73c2d2da0ba8cf02958de97b9b7e4",
        "stderr": ""
      },
      {
        "bytes": 25789,
        "ok": true,
        "path": "scripts/probes/digua_journal_production_deployment.py",
        "sha256": "e60c3783de3212ba69aecce608d2abbf0e6f96bcaf16d2917aadbc39ae458998",
        "stderr": ""
      },
      {
        "bytes": 1309,
        "ok": true,
        "path": "scripts/run_journal_collectors_once.sh",
        "sha256": "12b604d2d51684dab3f7ca0229c80af42f587d35e94257a6e9d0403f887595c8",
        "stderr": ""
      },
      {
        "bytes": 100,
        "ok": true,
        "path": "scripts/run_journal_e2e_smoke.sh",
        "sha256": "7a11e088d5071b5d8623bf2cc396ebaf6238578ad918e965c1d06a367a83f445",
        "stderr": ""
      },
      {
        "bytes": 255,
        "ok": true,
        "path": "src/digua_journal/__init__.py",
        "sha256": "713b0da082f811b6b561ce13cab90924abae734d9d8418ee998af63e1325054d",
        "stderr": ""
      },
      {
        "bytes": 255,
        "ok": true,
        "path": "src/digua_journal/collectors/__init__.py",
        "sha256": "54254b0ebfd41a07f287fd2f0551f55b0c0298d79ed6cda0cf3a12c88bc931e3",
        "stderr": ""
      },
      {
        "bytes": 1048,
        "ok": true,
        "path": "src/digua_journal/collectors/copy_route_collector.py",
        "sha256": "168c57afe0b885d92ad0a9411b9efd593bc53a69168f0ab81ecea2aef3e8d0c6",
        "stderr": ""
      },
      {
        "bytes": 1197,
        "ok": true,
        "path": "src/digua_journal/collectors/harness_trace_collector.py",
        "sha256": "96e99cb733531828a030d57ae73d77ada3862e5c404f0c344c4e008c21cb0b35",
        "stderr": ""
      },
      {
        "bytes": 3832,
        "ok": true,
        "path": "src/digua_journal/collectors/nas_index_diff_collector.py",
        "sha256": "98888d28c95b1fedd7cc8f0f7af1903b57d65e0ef381e6056895fd1fc238bab5",
        "stderr": ""
      },
      {
        "bytes": 1215,
        "ok": true,
        "path": "src/digua_journal/collectors/openclaw_collector.py",
        "sha256": "30827362365ae96e6f4116a94037dfff4a3fc7f0a27600bbb3db95a6cee048b4",
        "stderr": ""
      },
      {
        "bytes": 1171,
        "ok": true,
        "path": "src/digua_journal/collectors/rag_collector.py",
        "sha256": "14455f49f2712b447503bdfd6478e632c03f0842d3dbbf65d7c6567f8b3dfd4b",
        "stderr": ""
      },
      {
        "bytes": 1130,
        "ok": true,
        "path": "src/digua_journal/collectors/report_collector.py",
        "sha256": "dcf8afb718fc7bc967230600f3ae45f3974a7bfc3e63c2152da52f4291ff01ed",
        "stderr": ""
      },
      {
        "bytes": 891,
        "ok": true,
        "path": "src/digua_journal/collectors/system_collectors.py",
        "sha256": "bf467c0488ed4d9bc1ce7f1a321931bbf4cb89bbcfa42229dfc8f1062977f4d9",
        "stderr": ""
      },
      {
        "bytes": 1133,
        "ok": true,
        "path": "src/digua_journal/collectors/token_budget_collector.py",
        "sha256": "aceab2099a1fbaa5f3db8792eb6c7bb0053c0cbe866753f0f43c28f7bfa2a81a",
        "stderr": ""
      },
      {
        "bytes": 6043,
        "ok": true,
        "path": "src/digua_journal/event_model.py",
        "sha256": "454f0bdef6e9885d051807a2f7f21265d119afbb51d9dbb4d3c20235c4539838",
        "stderr": ""
      },
      {
        "bytes": 12215,
        "ok": true,
        "path": "src/digua_journal/journal_db.py",
        "sha256": "529613fea303b61eaf5c0a1c0cd87fae6fc5cb680a6df11e189d22610a63f197",
        "stderr": ""
      },
      {
        "bytes": 3230,
        "ok": true,
        "path": "src/digua_journal/journal_exporter.py",
        "sha256": "3600ba4f4790fb01e372ae290ac217a3b0f6310f3349267057167b58a3d232e6",
        "stderr": ""
      },
      {
        "bytes": 275,
        "ok": true,
        "path": "src/digua_journal/journal_migrations.py",
        "sha256": "ba2f255bc7ba98104ec05444c24992301e17db5b35b3dee15ca18cf00e0795b8",
        "stderr": ""
      },
      {
        "bytes": 1380,
        "ok": true,
        "path": "src/digua_journal/journal_privacy_guard.py",
        "sha256": "1f749a9edbf0b192d2b63f35a0ab042424e1f86613de9345fdf6cf980fafeb02",
        "stderr": ""
      },
      {
        "bytes": 252,
        "ok": true,
        "path": "src/digua_journal/journal_retention_policy.py",
        "sha256": "9c212ef0721b6675f510de0aad57be80c64ca80c26f1e8246854e463b58de163",
        "stderr": ""
      },
      {
        "bytes": 1714,
        "ok": true,
        "path": "src/digua_journal/journal_token_trace.py",
        "sha256": "475fa211507172937d8d12289874ef906300b2360e33cadb4ccfedb6b3ee17a5",
        "stderr": ""
      },
      {
        "bytes": 1144,
        "ok": true,
        "path": "src/digua_journal/manual_entry.py",
        "sha256": "c2ee8dca038b47ec180889a112d440bc91dd941305632c1e4d692e8aa5002667",
        "stderr": ""
      },
      {
        "bytes": 3653,
        "ok": true,
        "path": "src/digua_journal/period_summary_engine.py",
        "sha256": "d6b034193fbf008e234be6796757ab348276ea73eac996d08f97c46a4d047258",
        "stderr": ""
      },
      {
        "bytes": 2394,
        "ok": true,
        "path": "src/digua_journal/project_classifier.py",
        "sha256": "a0ba7df135b309b1ab75cf211c79123d6d93ea1cf164d8a40b7b804f0601ea85",
        "stderr": ""
      },
      {
        "bytes": 1763,
        "ok": true,
        "path": "src/digua_journal/summary_templates.py",
        "sha256": "096d7138c67b729a1332f7c3e84c379bd6fc949d09039db87b557f2626306aaa",
        "stderr": ""
      },
      {
        "bytes": 65,
        "ok": true,
        "path": "src/openclaw/__init__.py",
        "sha256": "e5c9e7d763e9fb6ebe8909ee9e444291121900d062cce77ce0893d1de198bea1",
        "stderr": ""
      },
      {
        "bytes": 66,
        "ok": true,
        "path": "src/openclaw/routes/__init__.py",
        "sha256": "cc71a31e681cce644e5a0ff3bea3ebccbb154abd0d5e3397b38e4a4b4a650fc7",
        "stderr": ""
      },
      {
        "bytes": 5055,
        "ok": true,
        "path": "src/openclaw/routes/journal_routes.py",
        "sha256": "e960d59e75454c800d5a1f990b6bc9335f5487736df1b0e608151b4b88d4f033",
        "stderr": ""
      },
      {
        "bytes": 2897,
        "ok": true,
        "path": "web/digua_journal.html",
        "sha256": "d23498f258ea8cbc8f1dae1b192ccd8b8f0219f569718a7abfa9b843e3c9fe85",
        "stderr": ""
      },
      {
        "bytes": 2494,
        "ok": true,
        "path": "web/static/digua_journal.css",
        "sha256": "db9563c192bf397dc7bc7e7713838620de7d2424f33c1eabc1b13f5375ec10d3",
        "stderr": ""
      },
      {
        "bytes": 3458,
        "ok": true,
        "path": "web/static/digua_journal.js",
        "sha256": "c15e50620f1fdcb371c5739a15ab398b4d5b79d397dc64bcb453bf08c2255deb",
        "stderr": ""
      }
    ]
  },
  "title": "journal_live_rollout_gate",
  "verdict": "journal_live_rollout_service_gate_passed"
}
```
