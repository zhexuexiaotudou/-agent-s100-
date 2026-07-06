# Demo 2 Recording Script: OpenClaw AI-NAS Features

## Goal

Show the product path a normal user cares about: upload a neutral photo, let S100P build local indexes, search it through AI Space and multimodal search, verify unsafe identity requests are blocked, ask OCR/RAG, then run controlled Auto Organizer plan, execute, and rollback.

## Setup

Use the dedicated demo user token from the S100P identity store. Do not show the token in the recording.

```bash
export DIGUA_DEMO_AUTH_TOKEN="$(cat /tmp/stage9_demo_token.txt)"
```

## Gate Command

```bash
cd /mnt/nas/openclaw
python3 gates/stage9_demo2_real_user_flow_gate.py \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --personal-root /mnt/nas/openclaw/Personal \
  --base-url http://127.0.0.1:8765 \
  --demo-image /mnt/nas/openclaw/Personal/Photos/stage7_smart_album_demo/white_shirt_person.jpg \
  --timeout 240
```

## User Queries To Show

- `穿白色上衣的人`
- `有电脑的照片`
- `宠物照片`
- `视频里有人`
- `这个人是谁?`
- `这张票据里的金额和日期是什么?`

## Expected Output

- Gate verdict: `ok_stage9_demo2_real_user_flow_gate`
- Upload pipeline jobs are completed.
- `cloud_used=false`.
- AI Space and multimodal APIs return valid product responses.
- The identity query is blocked; face identity and sensitive attribute inference remain disabled.
- OCR/RAG either returns grounded evidence or `no_grounded_answer=true`.
- Auto Organizer uses AI index classification, not filename fallback.
- Move/rename is controlled by plan, dry-run, approval, execute, and rollback.
- Delete and overwrite remain disabled.

## Subtitle

OpenClaw is not just chat. A user upload becomes local AI-NAS indexing, Chinese naming, searchable AI Space evidence, and a controlled organization workflow with rollback.

## Do Not Say

- Do not claim face identity recognition.
- Do not claim age, gender, race, emotion, or health inference.
- Do not claim Qwen autonomously moves files.
- Do not claim delete or overwrite is enabled.
- Do not claim cloud vision, OCR, or ASR is used by default.
