# Stage 3 Productization Recommendation

Recommendation: do not enter Stage 3 yet. Continue Stage 2 read-only sidecar trials.

Keep SQLite for current trace and index evidence. Do not add PostgreSQL/pgvector as a production dependency now; use it only in a lab branch if real Zleap requires it. Do not open any write workspace. Do not modify the OpenClaw foreground route, the local Qwen gateway, the dispatcher path, Dream7B ports, or protected ports.

Next route:

1. S100P live preflight: OpenClaw 8765, Qwen 18080, dispatcher hash, and protected ports.
2. Controlled read-only sidecar execution through `ai_nas_allowlisted_tool.sh`.
3. Real Zleap isolated trial if dependency and license checks are acceptable.
4. Trace, redaction, context, and rollback re-run.
5. Only then decide between productized Python harness and real sidecar integration.
