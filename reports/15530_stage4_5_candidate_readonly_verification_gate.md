# stage4_5_candidate_readonly_verification_gate

- verdict: `ok_stage4_5_candidate_readonly_verification_gate`
- generated_at: `2026-07-04T13:57:37.513442+08:00`
- passed: `5/5`

## Checks

- `PASS` candidate loaded from JSON
- `PASS` readonly verification helper ran
- `PASS` source hash still matches candidate
- `PASS` target still absent before execute
- `PASS` source and target parent are not symlinks

## Failures

- none

## Detail

```json
{
  "remote_run": {
    "returncode": 0,
    "elapsed_ms": 247.298,
    "stdout_hash": "c130ff5998cd4df896f65e774e0820e29dbd3aa639f83655d2d18aaa205a8bf9",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stdout_tail": "{\"source_exists\": true, \"source_is_file\": true, \"source_is_symlink\": false, \"source_relative_path\": \"Collections/CodexPreflight/source/stage4_5_self_created_route_canary_20260704-135733.txt\", \"source_sha256\": \"7c17e4552a221e467550974c8007f3a1fabb75ab30b1f75908f675c7482cb09c\", \"source_sha256_matches\": true, \"source_size_bytes\": 199, \"target_exists\": false, \"target_is_symlink\": false, \"target_parent_exists\": true, \"target_parent_is_symlink\": false, \"target_relative_path\": \"Collections/CodexPreflight/target/stage4_5_self_created_route_canary_20260704-135733_copied.txt\"}\n"
  },
  "verification": {
    "source_exists": true,
    "source_is_file": true,
    "source_is_symlink": false,
    "source_relative_path": "Collections/CodexPreflight/source/stage4_5_self_created_route_canary_20260704-135733.txt",
    "source_sha256": "7c17e4552a221e467550974c8007f3a1fabb75ab30b1f75908f675c7482cb09c",
    "source_sha256_matches": true,
    "source_size_bytes": 199,
    "target_exists": false,
    "target_is_symlink": false,
    "target_parent_exists": true,
    "target_parent_is_symlink": false,
    "target_relative_path": "Collections/CodexPreflight/target/stage4_5_self_created_route_canary_20260704-135733_copied.txt"
  },
  "note": "This gate reads source/target metadata only; it performs no copy/delete/move."
}
```
