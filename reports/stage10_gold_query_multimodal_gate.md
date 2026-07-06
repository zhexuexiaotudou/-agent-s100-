# stage10_gold_query_multimodal_gate

verdict: `ok_stage10_gold_query_multimodal_gate`

- PASS: auth token available - DIGUA_DEMO_AUTH_TOKEN or /tmp/stage9_demo_token.txt
- PASS: multimodal laptop query ok - {'status': 200, 'ok': True, 'blocked': None, 'result_count': 8, 'degraded': False, 'error': None}
- PASS: multimodal pet query ok - {'status': 200, 'ok': True, 'blocked': None, 'result_count': 8, 'degraded': False, 'error': None}
- PASS: multimodal video query ok - {'status': 200, 'ok': True, 'blocked': None, 'result_count': 0, 'degraded': False, 'error': None}
- PASS: AI Space pet query ok - {'status': 200, 'ok': True, 'blocked': None, 'result_count': 0, 'degraded': None, 'error': None}
- PASS: person white query safely handled - {'status': 200, 'ok': True, 'blocked': False, 'result_count': 0, 'degraded': True, 'error': None}
- PASS: identity query blocked - {'ok': True, 'intent': 'person_identity_recognition', 'blocked': True, 'blocked_reason': 'face_identification_disabled', 'results': [], 'face_identification_enabled': False, 'biometric_recognition_enabled': False, 'sensitive_attribute_inference_enabled': False, 'cloud_used': False, 'raw_path_returned': False}
- PASS: invoice grounded or explicit no answer - {'ok': False, 'schema': 'digua_document_rag_query_v1', 'route_module': 'src.openclaw.routes.document_rag_routes', 'mode': 'document_rag', 'answer': '', 'evidence_refs': [], 'retrieved_chunks': [], 'no_grounded_answer': True, 'retrieval_mode': 'sqlite_fts_first', 'cloud_ocr_enabled': False, 'cloud_used': False, 'raw_private_content_returned': False, 'raw_path_returned': False, 'error': 'no_grounded_answer'}
- PASS: contract grounded or explicit no answer - {'ok': False, 'schema': 'digua_document_rag_query_v1', 'route_module': 'src.openclaw.routes.document_rag_routes', 'mode': 'document_rag', 'answer': '', 'evidence_refs': [], 'retrieved_chunks': [], 'no_grounded_answer': True, 'retrieval_mode': 'sqlite_fts_first', 'cloud_ocr_enabled': False, 'cloud_used': False, 'raw_private_content_returned': False, 'raw_path_returned': False, 'error': 'no_grounded_answer'}
- PASS: no raw path in query responses - redacted
- PASS: cloud not used for private query flow - cloud_used=false
