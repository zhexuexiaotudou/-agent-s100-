# Release Security Boundary

Stage 10 release defaults:

- loopback/LAN only;
- admin token required for user APIs;
- NAS path allowlist;
- delete disabled;
- overwrite disabled;
- uncontrolled move/rename disabled;
- controlled move/rename requires Auto Organizer plan, approval, execution, and
  rollback evidence;
- Qwen execution authority false;
- hidden chain-of-thought not saved;
- cloud vision/OCR/ASR disabled by default;
- private raw cloud egress false.
- cloud API keys remain in a protected target-only file and are redacted from
  reports;
- cloud mode blocks privacy-classified and NAS-scoped prompts from provider
  egress.
