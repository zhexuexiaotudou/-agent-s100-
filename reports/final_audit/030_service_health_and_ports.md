# 030 Service Health And Ports

- S100P was checked through SSH as `sunrise@192.168.127.10`; no service exposure was widened.
- The UI v2 `/ui` route responded on both 18766 and 8765 during this audit, but fresh Playwright could not be rerun locally because Node/npm are absent from PATH.

| check | value |
| --- | --- |
| default_service_live | True |
| harness_live | True |
| qwen_live | True |
| temp_service_live | True |
| ui_v2_live_on_18766 | True |
| ui_v2_live_on_8765 | True |
| agent_runtime_status_ok | True |
