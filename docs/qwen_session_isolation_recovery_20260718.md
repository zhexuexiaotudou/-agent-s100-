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

The merged revision, service hashes, rollback backup, and real S100P browser
evidence will be recorded here after the required PR, CI, deployment, and live
verification gates complete.
