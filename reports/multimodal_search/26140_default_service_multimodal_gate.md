# 26140_default_service_multimodal_gate

- ok: `True`

```json
{
  "clip_18182_ready": false,
  "default_service_scope": "GET status only; POST routes remain behind existing portal identity auth",
  "host": "sunrise@192.168.127.10",
  "multimodal_status_present": true,
  "ok": true,
  "openclaw_active": true,
  "ssh": {
    "cmd": [
      "C:\\Windows\\System32\\OpenSSH\\ssh.EXE",
      "-i",
      "C:\\Users\\zhexu\\.ssh\\s100p_linkcheck_ed25519",
      "-o",
      "BatchMode=yes",
      "-o",
      "ConnectTimeout=6",
      "sunrise@192.168.127.10",
      "echo USER=$(whoami); echo HOST=$(hostname); echo ADDR_START; ip -br addr; echo ADDR_END; echo ROUTE_START; ip route; echo ROUTE_END; echo OPENCLAW_ACTIVE=$(systemctl --user is-active openclaw-gateway.service 2>/dev/null || true); echo HEALTH_START; curl -fsS --max-time 5 http://127.0.0.1:8765/api/health; echo; echo HEALTH_END; echo MM_STATUS_START; curl -fsS --max-time 5 http://127.0.0.1:8765/api/multimodal-search/status; echo; echo MM_STATUS_END; echo CLIP_HEALTH_START; curl -fsS --max-time 5 http://127.0.0.1:18182/health || true; echo; echo CLIP_HEALTH_END"
    ],
    "duration_sec": 1.071,
    "returncode": 0,
    "stderr_tail": "curl: (7) Failed to connect to 127.0.0.1 port 18182 after 0 ms: Connection refused\n",
    "stdout_tail": "USER=sunrise\nHOST=ubuntu\nADDR_START\nlo               UNKNOWN        127.0.0.1/8 ::1/128 \neth0             UP             169.254.8.10/16 fe80::6c75:dfff:fe40:9cbc/64 \neth1             UP             192.168.127.10/24 192.168.137.10/24 \ndocker0          DOWN           172.17.0.1/16 \nADDR_END\nROUTE_START\ndefault via 192.168.137.1 dev eth1 metric 50 \ndefault via 192.168.137.1 dev eth1 proto static metric 50 \n169.254.0.0/16 dev eth0 proto kernel scope link src 169.254.8.10 metric 100 \n169.254.0.0/16 dev eth0 scope link src 169.254.8.10 metric 101 \n172.17.0.0/16 dev docker0 proto kernel scope link src 172.17.0.1 linkdown \n192.168.127.0/24 dev eth1 proto kernel scope link src 192.168.127.10 metric 101 \n192.168.127.0/24 dev eth0 metric 700 \n192.168.137.0/24 dev eth1 proto kernel scope link src 192.168.137.10 metric 101 \nROUTE_END\nOPENCLAW_ACTIVE=active\nHEALTH_START\n{\n  \"ok\": true,\n  \"tool_id\": \"ai_nas_operator_portal_server\",\n  \"operator_portal_contract\": {\n    \"found\": true,\n    \"filename\": \"operator_portal_contract.json\",\n    \"path\": \"/mnt/nas/openclaw/reports/ai_nas_mvp/operator_portal_contract_20260618-160406-445747/operator_portal_contract.json\",\n    \"verdict\": \"ok_ai_nas_operator_portal_contract\",\n    \"generated_at\": \"2026-06-18T16:04:08.346324+08:00\",\n    \"selection_policy\": \"generated_at_then_mtime\"\n  },\n  \"portal_html\": \"/mnt/nas/openclaw/reports/ai_nas_mvp/operator_portal_contract_20260618-160406-445747/operator_portal.html\",\n  \"refresh_on_start\": null\n}\nHEALTH_END\nMM_STATUS_START\n{\n  \"ok\": true,\n  \"schema\": \"digua_multimodal_search_v1\",\n  \"feature_flags\": {\n    \"multimodal_search_enabled\": true,\n    \"multimodal_metadata_index_enabled\": true,\n    \"image_embedding_enabled\": true,\n    \"image_embedding_required_for_delivery\": true,\n    \"document_embedding_enabled\": false,\n    \"ocr_enabled\": false,\n    \"video_keyframe_enabled\": false,\n    \"video_keyframe_embedding_enabled\": false,\n    \"audio_transcript_enabled\": false,\n    \"asr_enabled\": false,\n    \"vector_extension_enabled\": \"auto\",\n    \"vector_numpy_fallback_enabled\": true,\n    \"cloud_vision_enabled\": false,\n    \"cloud_ocr_enabled\": false,\n    \"cloud_asr_enabled\": false,\n    \"face_identification_enabled\": false,\n    \"biometric_recognition_enabled\": false,\n    \"sensitive_attribute_inference_enabled\": false,\n    \"qwen_tool_execution_enabled\": false,\n    \"destructive_actions_enabled\": false\n  },\n  \"counts\": {},\n  \"indexed_count\": 0,\n  \"embedding_count\": 0,\n  \"raw_path_rows\": 0,\n  \"private_leak_count\": 0,\n  \"cloud_used\": false,\n  \"qwen_tool_execution_enabled\": false,\n  \"degraded\": true,\n  \"degraded_reason\": \"image_embeddings_missing\"\n}\nMM_STATUS_END\nCLIP_HEALTH_START\n\nCLIP_HEALTH_END\n"
  }
}
```
