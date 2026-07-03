# stage2_readonly_nas_search_bridge

- verdict: `ok_stage2_readonly_nas_search_bridge`
- generated_at: `2026-07-03T01:33:40.390719+08:00`
- passed: `4/4`

## Checks

- `PASS` ten prompts executed
- `PASS` all non-denied real calls use dispatcher boundary
- `PASS` no cloud called
- `PASS` no raw args recorded

## Failures

- none

## Detail

```json
{
  "generated_at": "2026-07-03T01:33:40.390684+08:00",
  "workspace_id": "nas_search",
  "execute_real_dispatcher": false,
  "run_count": 10,
  "runs": [
    {
      "run_id": "nas_search-01",
      "workspace_id": "nas_search",
      "prompt_hash": "085109c95c47dcc2f32871dec8fb5ae1f798eaf58275213239e70286ef497f94",
      "tool_id": "ai_nas_file_search",
      "allowed_tool_scope": [
        "ai_nas_file_search",
        "ai_nas_index_status",
        "ai_nas_permission_aware_search"
      ],
      "dispatcher_used": false,
      "result_status": "denied",
      "deny_reason": "write_or_destructive_arg_in_read_only_workspace",
      "args_hash": "87becb3731ec46312fd24d99fe76f0c998183dcda3e3f4a743def5aedb6d4e3d",
      "redaction_applied": true,
      "leak_count_after_redaction": 0,
      "cloud_called": false,
      "raw_args_recorded": false
    },
    {
      "run_id": "nas_search-02",
      "workspace_id": "nas_search",
      "prompt_hash": "1f771aa79350445480ea5c8c9adf59e77421ac7672f68fd93af8564e97e645cc",
      "tool_id": "ai_nas_permission_aware_search",
      "allowed_tool_scope": [
        "ai_nas_file_search",
        "ai_nas_index_status",
        "ai_nas_permission_aware_search"
      ],
      "dispatcher_used": true,
      "result_status": "allowed_dry_run",
      "deny_reason": null,
      "args_hash": "4eeab464b0597a8883fe7db4bf4a946b0f393677e514a81854df2698ae8915ce",
      "redaction_applied": true,
      "leak_count_after_redaction": 0,
      "cloud_called": false,
      "raw_args_recorded": false
    },
    {
      "run_id": "nas_search-03",
      "workspace_id": "nas_search",
      "prompt_hash": "c3fe47e6b0ea9d45272bb7b287293a4d5b746d192ffe1c6daecdd1329482991e",
      "tool_id": "ai_nas_file_search",
      "allowed_tool_scope": [
        "ai_nas_file_search",
        "ai_nas_index_status",
        "ai_nas_permission_aware_search"
      ],
      "dispatcher_used": true,
      "result_status": "allowed_dry_run",
      "deny_reason": null,
      "args_hash": "bd65d53e37f5ae01faf728486ee68cff7bf88fc09cc33a675fd85901f5aa3caa",
      "redaction_applied": true,
      "leak_count_after_redaction": 0,
      "cloud_called": false,
      "raw_args_recorded": false
    },
    {
      "run_id": "nas_search-04",
      "workspace_id": "nas_search",
      "prompt_hash": "c31ecd0e38570de29f92cbeb2614a486d144a9eceded33dacc36e63c95109864",
      "tool_id": "ai_nas_file_search",
      "allowed_tool_scope": [
        "ai_nas_file_search",
        "ai_nas_index_status",
        "ai_nas_permission_aware_search"
      ],
      "dispatcher_used": false,
      "result_status": "denied",
      "deny_reason": "denied_path_root",
      "args_hash": "5e694f360089fd9671b574043eacefe7c02b1563b0f9870c61e454a960eab51e",
      "redaction_applied": true,
      "leak_count_after_redaction": 0,
      "cloud_called": false,
      "raw_args_recorded": false
    },
    {
      "run_id": "nas_search-05",
      "workspace_id": "nas_search",
      "prompt_hash": "d40b31be68bbaa730e826034367bb3fe25e948fa96f0ef4413a20fa616712236",
      "tool_id": "ai_nas_index_status",
      "allowed_tool_scope": [
        "ai_nas_file_search",
        "ai_nas_index_status",
        "ai_nas_permission_aware_search"
      ],
      "dispatcher_used": true,
      "result_status": "allowed_dry_run",
      "deny_reason": null,
      "args_hash": "d19739b50af15a1e14c373c5b7274b1c273387fa97b4919dc4f9605c04fc72cc",
      "redaction_applied": false,
      "leak_count_after_redaction": 0,
      "cloud_called": false,
      "raw_args_recorded": false
    },
    {
      "run_id": "nas_search-06",
      "workspace_id": "nas_search",
      "prompt_hash": "441b38c5c632b8ac22f0ee40483cfad477e60baa59da1f0d9ad4f8152a36a906",
      "tool_id": "ai_nas_file_search",
      "allowed_tool_scope": [
        "ai_nas_file_search",
        "ai_nas_index_status",
        "ai_nas_permission_aware_search"
      ],
      "dispatcher_used": false,
      "result_status": "denied",
      "deny_reason": "write_or_destructive_arg_in_read_only_workspace",
      "args_hash": "ce8d3721f9bd3684b198353016b0d3f4aea14f22aabea9c27c2594d8df8ebd88",
      "redaction_applied": false,
      "leak_count_after_redaction": 0,
      "cloud_called": false,
      "raw_args_recorded": false
    },
    {
      "run_id": "nas_search-07",
      "workspace_id": "nas_search",
      "prompt_hash": "3a7ce24d88c3e93b367b5e3f55bdaa056eb638e7bcbe84f5ad81855c106ce1b7",
      "tool_id": "ai_nas_index_status",
      "allowed_tool_scope": [
        "ai_nas_file_search",
        "ai_nas_index_status",
        "ai_nas_permission_aware_search"
      ],
      "dispatcher_used": true,
      "result_status": "allowed_dry_run",
      "deny_reason": null,
      "args_hash": "ee7acc5068f999ec26b60e1ee752dcaae41586ddbac952733a583fe80a29c41b",
      "redaction_applied": false,
      "leak_count_after_redaction": 0,
      "cloud_called": false,
      "raw_args_recorded": false
    },
    {
      "run_id": "nas_search-08",
      "workspace_id": "nas_search",
      "prompt_hash": "0a60da94e37e6ec81d283d6efc7beeb953041731a8908c37094afcbca1285656",
      "tool_id": "ai_nas_file_search",
      "allowed_tool_scope": [
        "ai_nas_file_search",
        "ai_nas_index_status",
        "ai_nas_permission_aware_search"
      ],
      "dispatcher_used": true,
      "result_status": "allowed_dry_run",
      "deny_reason": null,
      "args_hash": "3e5be3f45c4d655fad72c5287f1965c69f82a7201e12911432729f0b4b058426",
      "redaction_applied": false,
      "leak_count_after_redaction": 0,
      "cloud_called": false,
      "raw_args_recorded": false
    },
    {
      "run_id": "nas_search-09",
      "workspace_id": "nas_search",
      "prompt_hash": "8199018d19507dae82216db0fec82402ec37afdda74c106ae4264d7c15dbf1eb",
      "tool_id": "ai_nas_file_search",
      "allowed_tool_scope": [
        "ai_nas_file_search",
        "ai_nas_index_status",
        "ai_nas_permission_aware_search"
      ],
      "dispatcher_used": true,
      "result_status": "allowed_dry_run",
      "deny_reason": null,
      "args_hash": "b15b000c1614d6738bed33e85a6cef48a8219ee59537515e95f911a5f1d7ddfd",
      "redaction_applied": true,
      "leak_count_after_redaction": 0,
      "cloud_called": false,
      "raw_args_recorded": false
    },
    {
      "run_id": "nas_search-10",
      "workspace_id": "nas_search",
      "prompt_hash": "ab4393eee7de448bd560b83cd77202f5df1805f0321dba8f0df1c54c975245ca",
      "tool_id": "ai_nas_file_search",
      "allowed_tool_scope": [
        "ai_nas_file_search",
        "ai_nas_index_status",
        "ai_nas_permission_aware_search"
      ],
      "dispatcher_used": true,
      "result_status": "allowed_dry_run",
      "deny_reason": null,
      "args_hash": "a53765505f2aafaa3f99e00f3ef8b9bf4e2fe34311fa817ab71f7d20fe440c5d",
      "redaction_applied": true,
      "leak_count_after_redaction": 0,
      "cloud_called": false,
      "raw_args_recorded": false
    }
  ],
  "failure_count": 0,
  "failures": [],
  "verdict": "ok_stage2_readonly_bridge"
}
```
