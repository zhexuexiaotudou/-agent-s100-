# Cloud web-search recovery — 2026-07-18

## Failure path

- The AI assistant returned a local-model disclaimer instead of live results.
- The loopback bridge health endpoint was green, but a real completion returned
  `openclaw_web_research_failed` and OpenClaw reported `network connection error`.
- S100P could reach the Windows ICS gateway at `192.168.137.1`, while the gateway
  returned `Destination Net Unreachable` for public IPs and DNS could not resolve
  `api.minimax.chat`.
- Windows had Internet on `以太网 2`; the startup repair script still assumed
  `WLAN`, which was disconnected.
- After Internet recovery, the short request `请联网搜索并列出今天最新的三条AI新闻，每条附来源链接。`
  still conflicted with the unconditional local `list` intent, and the policy
  vocabulary did not classify web/news phrases as public cloud work.

## Recovery

- Windows ICS was changed to share `以太网 2` to the S100P-facing `以太网`.
- The startup repair now selects the current non-private interface whose IPv4
  connectivity is `Internet`, falling back to `WLAN` only when no live profile is
  available.
- Public web phrases such as `联网`, `互联网`, `新闻`, `实时`, and their English
  equivalents are recognized as cloud-eligible public work.
- Generic list wording invokes NAS storage only when NAS/file context is present.
  NAS and local-file requests retain local-tool precedence.

## Acceptance evidence

- PC private interface: `192.168.127.2/24` and `192.168.137.1/24`.
- S100P: public IP ping succeeded; `api.minimax.chat` resolved; HTTPS connected.
- OpenClaw bridge: model `MiniMax-M2.7`, agent `web-research`.
- Live query: `tavily_search` plus `tavily_extract`, 2 calls, 0 failures, 3 source URLs.
- Regression: `py -3 -m unittest tests.test_copilot_local_qwen_chat`.

## Recheck commands

```powershell
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 `
  "ping -c 2 1.1.1.1; getent ahostsv4 api.minimax.chat; curl -sS http://127.0.0.1:18082/health"
```
