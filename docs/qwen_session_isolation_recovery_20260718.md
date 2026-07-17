# Local Qwen session isolation recovery (2026-07-18)

## Problem verified

The authenticated assistant page returned an answer about the previous
"2026-05-20" diary query when the next independent request was "你是谁". A
second live reproduction returned the model control token `<|im_end|>` as the
visible answer.

The portal and browser already sent only the current message. The context leak
was below that layer: the deployed Qwen gateway kept one
`oellm_multichat` process alive across HTTP requests, while the SDK demo changes
`new_chat` to false after its first turn. The demo's supported cache-clear
protocol is an input line containing `reset`, but the gateway never sent it.
Consequently, unrelated HTTP requests shared the same accelerator KV cache.

## Implementation

- Serialize access to the single local BPU runtime and send `reset` before
  every independent HTTP request.
- Wait for the runtime's next user prompt after reset before sending the new
  request, so reset completion and request input cannot be interleaved.
- Strip Qwen protocol markers such as `<|im_start|>`, `<|im_end|>`, and
  `<|endoftext|>` from local output. A control-token-only response is treated as
  a failed generation and retried once with a fresh process.
- Answer exact assistant-identity questions deterministically in the portal.
  The reply identifies the local S100P assistant and its authorization/privacy
  boundary without invoking the intent router, Qwen, NAS tools, or cloud
  services. This check is at the assistant entry point so a model-generated
  cloud classification cannot override the appliance's own identity.
- Keep ordinary general-chat questions on the local Qwen route. Document,
  album, storage, and other existing assistant routes are unchanged.

## Safety boundary

The fix does not grant the model any new tool or filesystem authority. Identity
answers report `cloud_used=false` and `qwen_execution_authority=false`. Local
documents remain behind the portal's existing ACL checks and are not sent to a
cloud model.

## Local verification

- Python compile checks passed for the gateway and portal.
- Dedicated session-isolation tests verify reset-before-prompt behavior across
  consecutive requests and control-token filtering.
- Portal tests verify that Chinese identity questions return the deterministic
  local identity without calling Qwen and without leaking a previous date.
- Full regression suite: 190/190 tests passed.

## Deployment acceptance

Merged delivery:

- Session isolation and deterministic identity response: PR #57, merge commit
  `35d491f186b10b32f04324ad3a5f56e64218f9b8`.
- Identity entry-point routing correction: PR #58, merge commit
  `ae1de4cb994055d4c1704788a6336bba01ea7f75`.
- Both PRs passed the required `offline-regression` and
  `startup-link-check-contract` GitHub checks before merge.

S100P deployment:

- Qwen gateway SHA-256:
  `80cb27ab109a376e56ed61684c063623c7d72798805770193fa68eb324d4ed45`.
- Portal SHA-256:
  `9d3a82f31737d853ea4be6f711c36688d8dd3cfbdd39b95e570d57a68c83e07c`.
- Initial rollback directory:
  `/mnt/nas/openclaw/deployment/backups/qwen-session-isolation-20260718-024211`.
- Identity entry-point rollback directory:
  `/mnt/nas/openclaw/deployment/backups/qwen-identity-entrypoint-20260718-025500`.
- The system-scoped `qwen25-local-openai-gateway.service` and user-scoped
  `openclaw-gateway.service` were active after deployment. Both loopback health
  endpoints returned HTTP 200. The separate 18081 shadow runtime was not
  changed.

Live request-isolation gate:

- Two consecutive general-chat requests returned `session_reset=true` and
  `runtime_retry_count=0`.
- The first response referred to blue; the second referred only to green and
  did not inherit the first request. Neither response exposed a Qwen protocol
  marker.

Authenticated product-path gate:

- A temporary user exercised the real
  `digua.local:80 -> product access -> 127.0.0.1:8765` login, CSRF, identity
  bridge, and assistant-chat path.
- The first deployment exposed a remaining issue: the intent router classified
  the identity question as cloud overflow before the identity branch. PR #58
  moved identity handling ahead of routing.
- After the follow-up deployment, `你是谁` returned the deterministic S100P
  identity with `assistant_mode=local_qwen_chat`,
  `identity_answer_source=deterministic_local_identity`, `cloud_used=false`,
  and `qwen_execution_authority=false`.
- Logout completed and the temporary username count was verified as `[0, 0]`
  across the product-access and upstream portal identity databases.

The existing authenticated Chrome page remained readable and screenshotable,
but automation clicks timed out before dispatching a request. Therefore the
authenticated port-80 HTTP path above is the production acceptance evidence;
an automated post-fix browser screenshot is not claimed.
