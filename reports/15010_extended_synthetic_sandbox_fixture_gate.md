# stage4_1_extended_synthetic_sandbox_fixture_gate

- verdict: `ok_stage4_1_extended_synthetic_sandbox_fixture_gate`
- generated_at: `2026-07-04T11:38:47.624120+08:00`
- passed: `6/6`

## Checks

- `PASS` sandbox root isolated under repo tmp
- `PASS` all requested synthetic files exist
- `PASS` target/archive/conflict dirs exist
- `PASS` all manifest entries synthetic
- `PASS` no real NAS path in manifest
- `PASS` manifest hash and cleanup rollback plan recorded

## Failures

- none

## Detail

```json
{
  "manifest": "evidence/stage4_1_write_sandbox_manifest.json",
  "manifest_payload": {
    "generated_at": "2026-07-04T11:38:47.621925+08:00",
    "sandbox_root": "F:\\Project\\Digua\\tmp\\digua_ai_nas_stage4_1_write_sandbox",
    "sandbox_root_relative": "tmp/digua_ai_nas_stage4_1_write_sandbox",
    "sandbox_root_isolated": true,
    "real_nas_path": false,
    "file_count": 10,
    "files": [
      {
        "path": "conflict/duplicate_name.txt",
        "path_hash": "5f015e70ff34f40e3401b00d82a626021de48cd7951a35767ddaafc7d75fe11f",
        "sha256": "767e1ac9c035e898ccbfd1356e59afd80414bf688e97532388e540cf91e8f1f6",
        "size": 26,
        "synthetic": true
      },
      {
        "path": "source/batch/a.txt",
        "path_hash": "c53e6b9d1698828a7b966e126ca902664d7ceb0902f95075e01a83df409f28bb",
        "sha256": "2c632798a4f621f9fcc952c5d2f07407739a6452913328153111cbb31b088f07",
        "size": 9,
        "synthetic": true
      },
      {
        "path": "source/batch/b.txt",
        "path_hash": "5d8a38563f69349860ec7dc541b11d391b57fcdf2f4da0a012f0e0944f1d1efa",
        "sha256": "4acc9d799effec8573597298bf17ff185c4a40a9caa3fcbac8e33c6e3662b175",
        "size": 9,
        "synthetic": true
      },
      {
        "path": "source/batch/c.txt",
        "path_hash": "805cbf672422e05e2387fb394b3b99ec92ca0722d4cc9e3208aa4dabdbbfb427",
        "sha256": "b4eee0602b7c78068264c862517bfc2c3f60fb1b0617c4acd23410326e631d49",
        "size": 9,
        "synthetic": true
      },
      {
        "path": "source/duplicate_name.txt",
        "path_hash": "dd3d883f869d47e3ea012a48344f380459cd247a5fb488fb1df74d782dc4d4a9",
        "sha256": "e0d0fb9ee125d3f3328240c9dcc6980fa992f97cab1834ee5fc90ac3f239edfc",
        "size": 28,
        "synthetic": true
      },
      {
        "path": "source/nested/deep/file.md",
        "path_hash": "be4b0ba9da038f034e37c9f6fe882c02054c659a6f8e84dd3bc34ab45bf32ad0",
        "sha256": "65ef19a61c905cf4f2bcef89c84c181ae77d261c8fb77dbcd37c754cd975b234",
        "size": 23,
        "synthetic": true
      },
      {
        "path": "source/photo_placeholder.jpg",
        "path_hash": "bb595e96584e6bfaa680a5e99c4ed5beca2733cf131ecd24b35d7cd2a959f7de",
        "sha256": "9857f4db3b50244fe5c1a08c4df57b568b53763bd5830d7c1c621d7973e7da52",
        "size": 39,
        "synthetic": true
      },
      {
        "path": "source/private_like_doc.txt",
        "path_hash": "8290a554b6b739a680fde3709feb461eb5f19539dcf7db9d05d2f76ece5ad167",
        "sha256": "3f83fd743896d344fddb69605e3a3cb000799155a3a8276e586479517c104cd1",
        "size": 58,
        "synthetic": true
      },
      {
        "path": "source/public_doc.txt",
        "path_hash": "73a0afebaaae67221733da034857d9005c6a84e6ee9324ae64faa149274561c9",
        "sha256": "fe1dea5d9e1bab0732eaf1908d023023e87b8c805c622ee65e3fb71d20a46fac",
        "size": 40,
        "synthetic": true
      },
      {
        "path": "source/中文资料.txt",
        "path_hash": "804b846f6d11eb962f0f0090936716d0e0c64a7048f21f22594238c3b161308b",
        "sha256": "d4118428d66ed32e6f0cee0bb37d2c0b64dc9aa25d86df0feecb4e31211205e2",
        "size": 36,
        "synthetic": true
      }
    ],
    "manifest_hash": "dc36dddc3f153e8ea87f9f449061fa964fa08743798c0a2e3067d98d93e16733",
    "cleanup_rollback_plan": {
      "reset_command": "regenerate synthetic sandbox from stage4_1 fixture builder",
      "rollback_scope": "local_synthetic_sandbox_only"
    }
  }
}
```
