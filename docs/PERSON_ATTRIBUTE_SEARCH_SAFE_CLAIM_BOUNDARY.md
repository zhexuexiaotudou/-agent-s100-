# Person Attribute Search Safe Claim Boundary

This feature is local-only, non-identifying person attribute search.

Allowed:

- person presence detection
- clothing color search
- object co-occurrence search
- video keyframe person detection
- evidence references
- no raw absolute path return
- `cloud_used=false`

Forbidden:

- face recognition
- face identification
- family member identity recognition
- age, gender, race, ethnicity, emotion, health, or disability inference
- biometric embeddings
- raw face crop storage
- cloud vision egress

Current implementation derives attributes from the local YOLO detection table and
simple color rules over the person bounding box. It does not crop or store faces
and does not output identity fields.
