# Chinese Smart Naming Rules

Schema: `digua_smart_naming_v1`.

## Format

`主类别_核心特征_场景或属性_日期_序号`

Example:

`人物照片_白色上衣_室内_20260706_001`

## Allowed Inputs

- Modality: image, video, audio, document, archive, code, other.
- Virtual category names such as `人物照片`, `白色上衣`, `票据发票`, `电子设备`.
- Object labels such as person, cat, dog, car, laptop, book, cup.
- Non-sensitive person attributes only: person present and clothing color tags.
- Redacted source title.
- File mtime or capture date.

## Forbidden Inputs

- Face identity or face recognition result.
- Person name or suspected identity.
- Age, gender, race, emotion, health, disability, or other sensitive traits.
- Face crops or biometric templates.
- Raw absolute paths.
- Phone numbers, ID numbers, addresses, account numbers, or other sensitive identifiers from source names.

## File Handling

The system only writes naming metadata:

- `display_name_zh`
- `suggested_filename_zh`
- `naming_reason_json`
- `risk_flags_json`

It does not physically rename, move, delete, or overwrite any NAS file.
