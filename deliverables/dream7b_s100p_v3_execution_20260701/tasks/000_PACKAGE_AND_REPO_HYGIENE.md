# Task 000 — Package and repo hygiene

## Goal

Ensure the v3 work starts from a clean, auditable repo state and produces POSIX-path archives.

## Actions

1. Locate the active Dream7B/S100P research repo.
2. Confirm that the repo contains prior reports or copy them from `reference/previous_codex_gptpro_pack/`.
3. Create required directories if missing:

```bash
mkdir -p reports tools evidence 01_final_evidence cases logs
```

4. Copy scaffold scripts only if useful. Do not blindly overwrite working tools:

```bash
bash COPY_SCAFFOLD_TO_REPO.sh .
```

5. Run or adapt `tools_scaffold/package_hygiene_check.py` to check:
   - zip names use POSIX `/`, not Windows `\`
   - report JSON files are parseable
   - raw evidence references are either present or listed as missing
   - current git commit/status if repo is git-backed

## Outputs

- `reports/105_package_hygiene_v3.json`
- `reports/105_package_hygiene_v3.md`

## Required verdict field

```json
{
  "package_hygiene_valid": "pass|fail|inconclusive",
  "posix_paths_required": true,
  "raw_evidence_subset_available": "pass|fail|partial|unknown"
}
```
