# cloud_egress_redaction_gate

- verdict: `ok_cloud_egress_redaction_gate`
- generated_at: `2026-07-02T23:28:15.875968+08:00`
- passed: `12/12`

## Checks

- `PASS` nas_search_read_only cloud disabled
- `PASS` nas_denied_acl_search cloud disabled
- `PASS` nas_destructive_action_requires_approval cloud disabled
- `PASS` document_report_generation cloud disabled
- `PASS` web cloud scenario is explicitly cloud allowed
- `PASS` web cloud redaction applied
- `PASS` web cloud egress hash exists
- `PASS` web cloud egress leak count is zero
- `PASS` web cloud egress uses configured replacement
- `PASS` ops_health_check cloud disabled
- `PASS` probe reports no protected port modifications
- `PASS` probe reports production path unmodified

## Failures

- none
