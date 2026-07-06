# Auto Organizer AI-Driven Hardening

## Change

Auto Organizer planning now resolves classification and naming in this priority order:

```text
asset_id -> AI Space asset view -> smart_asset_names -> smart_category_memberships -> YOLO labels -> person_attribute -> OCR tags -> subtitle tags -> fallback filename heuristic
```

When a source file has matching AI index records, `classification_basis.source` is `ai_space_smart_index` or `yolo_person_attribute_index`, and `fallback_used=false`.

If no matching asset/index exists, Auto Organizer still returns a safe plan, but it marks:

```json
{
  "classification_basis": {
    "source": "fallback_filename_heuristic",
    "fallback_used": true
  }
}
```

## Acceptance

Run:

```bash
python3 gates/stage9_auto_organizer_ai_driven_gate.py --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas --personal-root /mnt/nas/openclaw/Personal --demo-image /mnt/nas/openclaw/Personal/Photos/stage7_smart_album_demo/white_shirt_person.jpg --timeout 180
```

Expected verdict:

```text
ok_stage9_auto_organizer_ai_driven_gate
```

Final S100P recording readiness also passed this gate inside:

```text
reports/stage9_final_recording_readiness_gate.json
ok_stage9_final_recording_readiness_gate
```

## Boundaries

- Controlled move and rename require plan, dry-run, approval, execute, and rollback.
- Delete and overwrite remain disabled.
- Qwen has no execution authority.
- If AI recognition does not exist for a neutral filename such as `IMG_0001.jpg`, the gate must block rather than pretend success.
