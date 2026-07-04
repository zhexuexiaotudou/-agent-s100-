# stage4_synthetic_sandbox_fixture_gate

- verdict: `ok_stage4_synthetic_sandbox_fixture_gate`
- generated_at: `2026-07-04T11:22:14.079552+08:00`
- passed: `5/5`

## Checks

- `PASS` synthetic sandbox root created under repo tmp
- `PASS` sandbox manifest written
- `PASS` fixture has enough files
- `PASS` fixture is not a real NAS path
- `PASS` sandbox includes source and target dirs

## Failures

- none

## Detail

```json
{
  "manifest": "evidence/write_sandbox_manifest.json",
  "manifest_payload": {
    "generated_at": "2026-07-04T11:22:14.077634+08:00",
    "sandbox_root": "F:\\Project\\Digua\\tmp\\digua_ai_nas_write_sandbox",
    "sandbox_root_relative": "tmp/digua_ai_nas_write_sandbox",
    "real_nas_path": false,
    "file_count": 5,
    "files": [
      {
        "relative_path": "nested/file.md",
        "size": 46,
        "sha256": "f34de816e9dfae640d9a52aada2a94efbce6594eceea673d6fb1b9647d4e56db"
      },
      {
        "relative_path": "source/large_dummy.bin",
        "size": 65536,
        "sha256": "1f8745f0d2d1387ec1af2211a3cf417b2e9e885e853472649c1d979d0e9370e3"
      },
      {
        "relative_path": "source/photo_placeholder.jpg",
        "size": 38,
        "sha256": "818c4dce70cb15d77f74e45026d3953450339e09119d1e50a5b813583bf11ed1"
      },
      {
        "relative_path": "source/private_like_doc.txt",
        "size": 57,
        "sha256": "f39fa1f5076fed2c753ea099c0558960f68179ab8c4265583494203b31bcb3b2"
      },
      {
        "relative_path": "source/public_doc.txt",
        "size": 25,
        "sha256": "3b96300402065947c4d31532645c6baa06cdf27c3b6102da9a72a330aca3b52f"
      }
    ],
    "manifest_hash": "c96409768b8f76fbfe88934159d2f52f27f47efd703185c59547eaafc9d2b5f4"
  }
}
```
