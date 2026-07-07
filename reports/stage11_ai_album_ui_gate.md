# stage11_ai_album_ui_gate

verdict: `ok_stage11_ai_album_ui_gate`

- PASS: login token available - {'ok': True, 'token': '[redacted-token]', 'expires_at': '2026-07-08T05:19:34.102767+00:00', 'user': {'id': 1, 'username': 'admin', 'role': 'admin'}}
- PASS: /ai-album route serves v2 app - 200
- PASS: AI Album JS page registered - aiAlbumPage
- PASS: AI Album API wiring present - required API markers
- PASS: identity query blocked in UI - front-end local block
- PASS: no destructive AI Album action handlers - delete/overwrite/raw-path actions absent
- PASS: AI Album CSS present - layout classes
- PASS: AI Space status ok - None
- PASS: AI Space has assets - 4
- PASS: facets returned - {'ok': True, 'schema': 'digua_ai_space_v1', 'facets': {'modality': {'image': 4}, 'time_bucket': {'today': 4}, 'object_label': {}, 'category': {'待整理': 4}, 'privacy_level': {'private_local_only': 4}}, 'raw_path_returned': False, 'cloud_used': False}
- PASS: assets returned - 4
- PASS: media photos returned - 22
- PASS: smart categories returned - 20
- PASS: smart categories are not all-asset false positives - []
- PASS: evidence-free assets do not claim person/clothing/pet/vehicle/document labels - []
- PASS: preview hash available - mm_79552d8c46bdcff6fadb874d
- PASS: preview endpoint returns bytes - {'ok': True, 'status': 200, 'bytes': 123788, 'content_type': 'image/png'}
- PASS: AI Space search endpoint ok - {'ok': True, 'schema': 'digua_ai_space_v1', 'query_redacted': '票据发票', 'results': [], 'raw_path_returned': False, 'cloud_used': False}
- PASS: person attribute endpoint ok - {'ok': True, 'schema': 'digua_person_attribute_search_v1', 'query': {'query_redacted': '穿白色上衣的人', 'blocked': False, 'blocked_reason': None, 'require_person': True, 'upper_color': 'white', 'co_occurs_with': None, 'modality': None}, 'blocked': False, 'results': [], 'degraded': True, 'degraded_reason': 'no_matching_person_attribute', 'face_identification_enabled': False, 'biometric_recognition_enabled': False, 'sensitive_attribute_inference_enabled': False, 'cloud_used': False, 'raw_path_returned': False}
- PASS: auto organizer status ok - None
- PASS: auto organizer plan reachable - None
- PASS: delete remains blocked - delete_allowed not true
- PASS: overwrite remains blocked - overwrite_allowed not true
- PASS: Qwen has no execution authority - qwen_execution_authority not true
- PASS: raw paths not returned by product APIs - redacted
- PASS: cloud private processing remains off - False
