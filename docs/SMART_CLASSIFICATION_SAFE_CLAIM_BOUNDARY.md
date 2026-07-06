# Smart Classification Safe Claim Boundary

## Can Claim

- The media album API indexes NAS images into a non-empty local media database.
- Uploading an image can trigger local indexing, virtual smart classification, Chinese smart naming, and AI Space refresh.
- Smart albums are virtual category memberships, not physical folders.
- Chinese smart names are metadata suggestions and display names.
- The flow is local-first and returns redacted evidence fields rather than raw absolute paths.

## Cannot Claim

- No claim of face recognition, identity recognition, or finding a named person.
- No claim of age, gender, race, emotion, health, or other sensitive attribute inference.
- No claim that original files are physically organized unless a separate Harness copy execution report exists.
- No claim that unsupported image formats such as HEIC/RAW are decoded; they are counted as unsupported until a decoder is explicitly added.
- No cloud person recognition or raw private image egress is enabled.

## Required Evidence

- `stage7_media_album_nonzero_gate.json`
- `stage7_upload_auto_classify_gate.json`
- `stage7_chinese_smart_naming_gate.json`
- `stage7_smart_album_classification_delivery_gate.json`
- Product smoke report after deployment.
