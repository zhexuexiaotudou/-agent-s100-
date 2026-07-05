# digua_ai_nas_multimodal_search_v1_gate_packet

- ok: `True`
- verdict: `multimodal_search_v1_ready_with_optional_ocr_video_audio_disabled`
- indexed_assets: `37`
- image_embeddings: `10`
- eval_case_count: `40`
- no_raw_path_rate: `1.0`
- private_leak_count: `0`
- optional_ocr_video_audio_content: `disabled_by_feature_flag`

```json
{
  "created_at": "20260705_171515",
  "gates": {
    "api": {
      "ok": true,
      "queries": {
        "archive": {
          "degraded": false,
          "degraded_reason": null,
          "feature_flags": {
            "asr_enabled": false,
            "audio_transcript_enabled": false,
            "biometric_recognition_enabled": false,
            "cloud_asr_enabled": false,
            "cloud_ocr_enabled": false,
            "cloud_vision_enabled": false,
            "destructive_actions_enabled": false,
            "document_embedding_enabled": false,
            "face_identification_enabled": false,
            "image_embedding_enabled": true,
            "image_embedding_required_for_delivery": true,
            "multimodal_metadata_index_enabled": true,
            "multimodal_search_enabled": true,
            "ocr_enabled": false,
            "qwen_tool_execution_enabled": false,
            "sensitive_attribute_inference_enabled": false,
            "vector_extension_enabled": "auto",
            "vector_numpy_fallback_enabled": true,
            "video_keyframe_embedding_enabled": false,
            "video_keyframe_enabled": false
          },
          "ok": true,
          "privacy": {
            "cloud_used": false,
            "private_leak_count": 0,
            "raw_path_returned": false
          },
          "query_redacted": "archive bundle zip",
          "results": [
            {
              "asset_id": "mm_32a772dcc32a76abdd8e7854",
              "evidence_ref": "mm_ev_06c28495d7fba4b8c1",
              "matched_by": [
                "metadata"
              ],
              "modality": "archive",
              "path_hash": "1ad86269559a4a2df2c7aa9c5f7a1dfd",
              "privacy_level": "private_local_only",
              "rank": 1,
              "score": 0.366393,
              "score_components": {
                "fts": null,
                "image_embedding": null,
                "metadata": 0.35
              },
              "snippet_redacted": "",
              "thumbnail_url": null,
              "timestamp_sec": null,
              "title_redacted": "handoff_bundle.zip"
            }
          ],
          "retrieval_mode": "fts_first_plus_image_embedding",
          "run_id": "mm_run_61583449bbc74012",
          "trace_id": "mm_trace_0a70f2651f0f456d"
        },
        "audio": {
          "degraded": false,
          "degraded_reason": null,
          "feature_flags": {
            "asr_enabled": false,
            "audio_transcript_enabled": false,
            "biometric_recognition_enabled": false,
            "cloud_asr_enabled": false,
            "cloud_ocr_enabled": false,
            "cloud_vision_enabled": false,
            "destructive_actions_enabled": false,
            "document_embedding_enabled": false,
            "face_identification_enabled": false,
            "image_embedding_enabled": true,
            "image_embedding_required_for_delivery": true,
            "multimodal_metadata_index_enabled": true,
            "multimodal_search_enabled": true,
            "ocr_enabled": false,
            "qwen_tool_execution_enabled": false,
            "sensitive_attribute_inference_enabled": false,
            "vector_extension_enabled": "auto",
            "vector_numpy_fallback_enabled": true,
            "video_keyframe_embedding_enabled": false,
            "video_keyframe_enabled": false
          },
          "ok": true,
          "privacy": {
            "cloud_used": false,
            "private_leak_count": 0,
            "raw_path_returned": false
          },
          "query_redacted": "meeting audio",
          "results": [
            {
              "asset_id": "mm_4eb9cacf5ca091b32765121b",
              "evidence_ref": "mm_ev_94d613b3cce5bc1c17",
              "matched_by": [
                "metadata"
              ],
              "modality": "audio",
              "path_hash": "a0f7b0969e06ca45d07851114743ddd1",
              "privacy_level": "private_local_only",
              "rank": 1,
              "score": 0.366393,
              "score_components": {
                "fts": null,
                "image_embedding": null,
                "metadata": 0.35
              },
              "snippet_redacted": "",
              "thumbnail_url": null,
              "timestamp_sec": null,
              "title_redacted": "meeting_audio_0.wav"
            },
            {
              "asset_id": "mm_dcc129cc3c48fb373c490819",
              "evidence_ref": "mm_ev_88c5ba97836f2c04b7",
              "matched_by": [
                "metadata"
              ],
              "modality": "audio",
              "path_hash": "79126176066932fb654d8087ee228859",
              "privacy_level": "private_local_only",
              "rank": 2,
              "score": 0.191129,
              "score_components": {
                "fts": null,
                "image_embedding": null,
                "metadata": 0.175
              },
              "snippet_redacted": "",
              "thumbnail_url": null,
              "timestamp_sec": null,
              "title_redacted": "meeting_audio_1.wav"
            },
            {
              "asset_id": "mm_49340cdd1f2cfede3ede3e8b",
              "evidence_ref": "mm_ev_fe4031bf366eb498f7",
              "matched_by": [
                "metadata"
              ],
              "modality": "audio",
              "path_hash": "20a187ac1f5862b75bf96fb00e751469",
              "privacy_level": "private_local_only",
              "rank": 3,
              "score": 0.13254,
              "score_components": {
                "fts": null,
                "image_embedding": null,
                "metadata": 0.11666666666666665
              },
              "snippet_redacted": "",
              "thumbnail_url": null,
              "timestamp_sec": null,
              "title_redacted": "meeting_audio_2.wav"
            },
            {
              "asset_id": "mm_e50ebc1340fb4e634251b06b",
              "evidence_ref": "mm_ev_d823b6fe7c672aba3d",
              "matched_by": [
                "metadata"
              ],
              "modality": "audio",
              "path_hash": "ba95cf8d287e916232501f18ceb0b9eb",
              "privacy_level": "private_local_only",
              "rank": 4,
              "score": 0.103125,
              "score_components": {
                "fts": null,
                "image_embedding": null,
                "metadata": 0.0875
              },
              "snippet_redacted": "",
              "thumbnail_url": null,
              "timestamp_sec": null,
              "title_redacted": "meeting_audio_3.wav"
            },
            {
              "asset_id": "mm_cb976c350c7398691d267a0f",
              "evidence_ref": "mm_ev_5e285a3cbe14d391ce",
              "matched_by": [
                "metadata"
              ],
              "modality": "audio",
              "path_hash": "462185e7180a80ef49dd73d1f9086d82",
              "privacy_level": "private_local_only",
              "rank": 5,
              "score": 0.085385,
              "score_components": {
                "fts": null,
                "image_embedding": null,
                "metadata": 0.06999999999999999
              },
              "snippet_redacted": "",
              "thumbnail_url": null,
              "timestamp_sec": null,
              "title_redacted": "meeting_audio_4.wav"
            }
          ],
          "retrieval_mode": "fts_first_plus_image_embedding",
          "run_id": "mm_run_cfe204946bfd44a6",
          "trace_id": "mm_trace_c08d6832d0184d27"
        },
        "code": {
          "degraded": false,
          "degraded_reason": null,
          "feature_flags": {
            "asr_enabled": false,
            "audio_transcript_enabled": false,
            "biometric_recognition_enabled": false,
            "cloud_asr_enabled": false,
            "cloud_ocr_enabled": false,
            "cloud_vision_enabled": false,
            "destructive_actions_enabled": false,
            "document_embedding_enabled": false,
            "face_identification_enabled": false,
            "image_embedding_enabled": true,
            "image_embedding_required_for_delivery": true,
            "multimodal_metadata_index_enabled": true,
            "multimodal_search_enabled": true,
            "ocr_enabled": false,
            "qwen_tool_execution_enabled": false,
            "sensitive_attribute_inference_enabled": false,
            "vector_extension_enabled": "auto",
            "vector_numpy_fallback_enabled": true,
            "video_keyframe_embedding_enabled": false,
            "video_keyframe_enabled": false
          },
          "ok": true,
          "privacy": {
            "cloud_used": false,
            "private_leak_count": 0,
            "raw_path_returned": false
          },
          "query_redacted": "python automation script",
          "results": [
            {
              "asset_id": "mm_50765defc28dcfcbbce1b2f1",
              "evidence_ref": "mm_ev_65430d0c97b54c0874",
              "matched_by": [
                "metadata"
              ],
              "modality": "code",
              "path_hash": "80ed65a2922bd572b4d4e6d626623815",
              "privacy_level": "private_local_only",
              "rank": 1,
              "score": 0.366393,
              "score_components": {
                "fts": null,
                "image_embedding": null,
                "metadata": 0.35
              },
              "snippet_redacted": "",
              "thumbnail_url": null,
              "timestamp_sec": null,
              "title_redacted": "automation_script_0.py"
            },
            {
              "asset_id": "mm_0e593618237a8347f7b4b810",
              "evidence_ref": "mm_ev_52c9fa587a5224e359",
              "matched_by": [
                "metadata"
              ],
              "modality": "code",
              "path_hash": "8ceb11e746bb49ddaea8b7441b61dbac",
              "privacy_level": "private_local_only",
              "rank": 2,
              "score": 0.191129,
              "score_components": {
                "fts": null,
                "image_embedding": null,
                "metadata": 0.175
              },
              "snippet_redacted": "",
              "thumbnail_url": null,
              "timestamp_sec": null,
              "title_redacted": "automation_script_1.py"
            },
            {
              "asset_id": "mm_3037f430ebd95e6348cb3193",
              "evidence_ref": "mm_ev_4e45b07da728f4b5b5",
              "matched_by": [
                "metadata"
              ],
              "modality": "code",
              "path_hash": "f899dc754d994938d166d15ab7090eb6",
              "privacy_level": "private_local_only",
              "rank": 3,
              "score": 0.13254,
              "score_components": {
                "fts": null,
                "image_embedding": null,
                "metadata": 0.11666666666666665
              },
              "snippet_redacted": "",
              "thumbnail_url": null,
              "timestamp_sec": null,
              "title_redacted": "automation_script_2.py"
            },
            {
              "asset_id": "mm_40d330558645c8058ec14e55",
              "evidence_ref": "mm_ev_323ce95e315b0ae68f",
              "matched_by": [
                "metadata"
              ],
              "modality": "code",
              "path_hash": "d50a205ce7e5b0d69b8b35d6b4bb990e",
              "privacy_level": "private_local_only",
              "rank": 4,
              "score": 0.103125,
              "score_components": {
                "fts": null,
                "image_embedding": null,
                "metadata": 0.0875
              },
              "snippet_redacted": "",
              "thumbnail_url": null,
              "timestamp_sec": null,
              "title_redacted": "automation_script_3.py"
            },
            {
              "asset_id": "mm_1f3caae2dd4b08f42dc729d7",
              "evidence_ref": "mm_ev_86f6dbc5a0190e6cee",
              "matched_by": [
                "metadata"
              ],
              "modality": "code",
              "path_hash": "bb8a092afac1af79b85f9a4f79325ba1",
              "privacy_level": "private_local_only",
              "rank": 5,
              "score": 0.085385,
              "score_components": {
                "fts": null,
                "image_embedding": null,
                "metadata": 0.06999999999999999
              },
              "snippet_redacted": "",
              "thumbnail_url": null,
              "timestamp_sec": null,
              "title_redacted": "automation_script_4.py"
            }
          ],
          "retrieval_mode": "fts_first_plus_image_embedding",
          "run_id": "mm_run_d1f3b81a88a1489b",
          "trace_id": "mm_trace_668e417180d04a09"
        },
        "document": {
          "degraded": false,
          "degraded_reason": null,
          "feature_flags": {
            "asr_enabled": false,
            "audio_transcript_enabled": false,
            "biometric_recognition_enabled": false,
            "cloud_asr_enabled": false,
            "cloud_ocr_enabled": false,
            "cloud_vision_enabled": false,
            "destructive_actions_enabled": false,
            "document_embedding_enabled": false,
            "face_identification_enabled": false,
            "image_embedding_enabled": true,
            "image_embedding_required_for_delivery": true,
            "multimodal_metadata_index_enabled": true,
            "multimodal_search_enabled": true,
            "ocr_enabled": false,
            "qwen_tool_execution_enabled": false,
            "sensitive_attribute_inference_enabled": false,
            "vector_extension_enabled": "auto",
            "vector_numpy_fallback_enabled": true,
            "video_keyframe_embedding_enabled": false,
            "video_keyframe_enabled": false
          },
          "ok": true,
          "privacy": {
            "cloud_used": false,
            "private_leak_count": 0,
            "raw_path_returned": false
          },
          "query_redacted": "renovation invoice",
          "results": [
            {
              "asset_id": "mm_954cd7d63b4a24fdd5cfd5a7",
              "evidence_ref": "mm_ev_e669482d0f052184fb",
              "matched_by": [
                "fts",
                "metadata"
              ],
              "modality": "document",
              "path_hash": "e06f184aeaecfbd47df5ce2a1c049176",
              "privacy_level": "private_local_only",
              "rank": 1,
              "score": 1.081319,
              "score_components": {
                "fts": 1.0,
                "image_embedding": null,
                "metadata": 0.049999999999999996
              },
              "snippet_redacted": "renovation invoice receipt paid evidence kitchen cabinet contract",
              "thumbnail_url": null,
              "timestamp_sec": null,
              "title_redacted": "renovation_invoice_receipt.txt"
            },
            {
              "asset_id": "mm_cd7347f3d74e63ff72347eb4",
              "evidence_ref": "mm_ev_ce0195dc3e5e52d6fe",
              "matched_by": [
                "metadata"
              ],
              "modality": "document",
              "path_hash": "af1bbf3c11854cc7309eafe2d73dd0b6",
              "privacy_level": "private_local_only",
              "rank": 2,
              "score": 0.366393,
              "score_components": {
                "fts": null,
                "image_embedding": null,
                "metadata": 0.35
              },
              "snippet_redacted": "",
              "thumbnail_url": null,
              "timestamp_sec": null,
              "title_redacted": "family_trip_plan.txt"
            },
            {
              "asset_id": "mm_ef0a11b63010435f355e9c2a",
              "evidence_ref": "mm_ev_d70541f1a2b7505328",
              "matched_by": [
                "metadata"
              ],
              "modality": "document",
              "path_hash": "f295b24fe572733491cd7fc564aced6a",
              "privacy_level": "private_local_only",
              "rank": 3,
              "score": 0.191129,
              "score_components": {
                "fts": null,
                "image_embedding": null,
                "metadata": 0.175
              },
              "snippet_redacted": "",
              "thumbnail_url": null,
              "timestamp_sec": null,
              "title_redacted": "journal_summary.txt"
            },
            {
              "asset_id": "mm_dee779a4fd7d4e82ad024bd3",
              "evidence_ref": "mm_ev_bed49f90f62b4cf8bc",
              "matched_by": [
                "metadata"
              ],
              "modality": "document",
              "path_hash": "b8233af4a712f44ff24d91880e16a604",
              "privacy_level": "private_local_only",
              "rank": 4,
              "score": 0.13254,
              "score_components": {
                "fts": null,
                "image_embedding": null,
                "metadata": 0.11666666666666665
              },
              "snippet_redacted": "",
              "thumbnail_url": null,
              "timestamp_sec": null,
              "title_redacted": "maintenance_record.txt"
            },
            {
              "asset_id": "mm_6ee8cba9786e40820506397b",
              "evidence_ref": "mm_ev_19837a9d9a443c49e0",
              "matched_by": [
                "metadata"
              ],
              "modality": "document",
              "path_hash": "26c085e455863500ab07337a85c6f5fe",
              "privacy_level": "private_local_only",
              "rank": 5,
              "score": 0.103125,
              "score_components": {
                "fts": null,
                "image_embedding": null,
                "metadata": 0.0875
              },
              "snippet_redacted": "",
              "thumbnail_url": null,
              "timestamp_sec": null,
              "title_redacted": "nas_mount_notes.txt"
            }
          ],
          "retrieval_mode": "fts_first_plus_image_embedding",
          "run_id": "mm_run_e9998e5bde2543cf",
          "trace_id": "mm_trace_7df19d736746455f"
        },
        "image": {
          "degraded": false,
          "degraded_reason": null,
          "feature_flags": {
            "asr_enabled": false,
            "audio_transcript_enabled": false,
            "biometric_recognition_enabled": false,
            "cloud_asr_enabled": false,
            "cloud_ocr_enabled": false,
            "cloud_vision_enabled": false,
            "destructive_actions_enabled": false,
            "document_embedding_enabled": false,
            "face_identification_enabled": false,
            "image_embedding_enabled": true,
            "image_embedding_required_for_delivery": true,
            "multimodal_metadata_index_enabled": true,
            "multimodal_search_enabled": true,
            "ocr_enabled": false,
            "qwen_tool_execution_enabled": false,
            "sensitive_attribute_inference_enabled": false,
            "vector_extension_enabled": "auto",
            "vector_numpy_fallback_enabled": true,
            "video_keyframe_embedding_enabled": false,
            "video_keyframe_enabled": false
          },
          "ok": true,
          "privacy": {
            "cloud_used": false,
            "private_leak_count": 0,
            "raw_path_returned": false
          },
          "query_redacted": "white image",
          "results": [
            {
              "asset_id": "mm_ad07f4dade029b6cf472c62b",
              "evidence_ref": "mm_ev_d4856ca5859d528b2a",
              "matched_by": [
                "image_embedding",
                "metadata"
              ],
              "modality": "image",
              "path_hash": "4f242a1111996fa983b718bcb9d5caed",
              "privacy_level": "private_local_only",
              "rank": 1,
              "score": 0.939233,
              "score_components": {
                "fts": null,
                "image_embedding": 0.8643835783004761,
                "metadata": 0.04375
              },
              "snippet_redacted": "",
              "thumbnail_url": "/api/multimodal-index/item/mm_ad07f4dade029b6cf472c62b",
              "timestamp_sec": null,
              "title_redacted": "white_shirt_photo.png"
            },
            {
              "asset_id": "mm_cca53f95c64e166e7948055e",
              "evidence_ref": "mm_ev_9d2a61ffcc7a584db5",
              "matched_by": [
                "image_embedding",
                "metadata"
              ],
              "modality": "image",
              "path_hash": "3e8771b7fe06e575312e1c7d62bbaa0c",
              "privacy_level": "private_local_only",
              "rank": 2,
              "score": 0.916421,
              "score_components": {
                "fts": null,
                "image_embedding": 0.7974225282669067,
                "metadata": 0.0875
              },
              "snippet_redacted": "",
              "thumbnail_url": "/api/multimodal-index/item/mm_cca53f95c64e166e7948055e",
              "timestamp_sec": null,
              "title_redacted": "gray_box_photo.png"
            },
            {
              "asset_id": "mm_369f4dc8e083031c6383e0c0",
              "evidence_ref": "mm_ev_3fde9838f3935055df",
              "matched_by": [
                "image_embedding",
                "metadata"
              ],
              "modality": "image",
              "path_hash": "33f3c4c4644ac8e509fb184c9389e1d2",
              "privacy_level": "private_local_only",
              "rank": 3,
              "score": 0.891653,
              "score_components": {
                "fts": null,
                "image_embedding": 0.8221422433853149,
                "metadata": 0.03888888888888889
              },
              "snippet_redacted": "",
              "thumbnail_url": "/api/multimodal-index/item/mm_369f4dc8e083031c6383e0c0",
              "timestamp_sec": null,
              "title_redacted": "white_wall_reference.png"
            },
            {
              "asset_id": "mm_5ce80a98f43836edae6c474d",
              "evidence_ref": "mm_ev_e81816d68978286687",
              "matched_by": [
                "image_embedding",
                "metadata"
              ],
              "modality": "image",
              "path_hash": "d00f205c1aa9cc5bf2530830176a699e",
              "privacy_level": "private_local_only",
              "rank": 4,
              "score": 0.867377,
              "score_components": {
                "fts": null,
                "image_embedding": 0.6608636975288391,
                "metadata": 0.175
              },
              "snippet_redacted": "",
              "thumbnail_url": "/api/multimodal-index/item/mm_5ce80a98f43836edae6c474d",
              "timestamp_sec": null,
              "title_redacted": "blue_folder_cover.png"
            },
            {
              "asset_id": "mm_bcca1567f0fd4f22be5ca3ee",
              "evidence_ref": "mm_ev_1c51341722a56d3552",
              "matched_by": [
                "image_embedding",
                "metadata"
              ],
              "modality": "image",
              "path_hash": "fa02420f4c12d481b548b6328868aa68",
              "privacy_level": "private_local_only",
              "rank": 5,
              "score": 0.866191,
              "score_components": {
                "fts": null,
                "image_embedding": 0.48551225662231445,
                "metadata": 0.35
              },
              "snippet_redacted": "",
              "thumbnail_url": "/api/multimodal-index/item/mm_bcca1567f0fd4f22be5ca3ee",
              "timestamp_sec": null,
              "title_redacted": "black_router_photo.png"
            }
          ],
          "retrieval_mode": "fts_first_plus_image_embedding",
          "run_id": "mm_run_c4154b55c53c4761",
          "trace_id": "mm_trace_ce1a30be161443e9"
        },
        "video": {
          "degraded": false,
          "degraded_reason": null,
          "feature_flags": {
            "asr_enabled": false,
            "audio_transcript_enabled": false,
            "biometric_recognition_enabled": false,
            "cloud_asr_enabled": false,
            "cloud_ocr_enabled": false,
            "cloud_vision_enabled": false,
            "destructive_actions_enabled": false,
            "document_embedding_enabled": false,
            "face_identification_enabled": false,
            "image_embedding_enabled": true,
            "image_embedding_required_for_delivery": true,
            "multimodal_metadata_index_enabled": true,
            "multimodal_search_enabled": true,
            "ocr_enabled": false,
            "qwen_tool_execution_enabled": false,
            "sensitive_attribute_inference_enabled": false,
            "vector_extension_enabled": "auto",
            "vector_numpy_fallback_enabled": true,
            "video_keyframe_embedding_enabled": false,
            "video_keyframe_enabled": false
          },
          "ok": true,
          "privacy": {
            "cloud_used": false,
            "private_leak_count": 0,
            "raw_path_returned": false
          },
          "query_redacted": "home video clip",
          "results": [
            {
              "asset_id": "mm_3e983ed3f0a3d14262f7110f",
              "evidence_ref": "mm_ev_97a30225dee7454bbe",
              "matched_by": [
                "metadata"
              ],
              "modality": "video",
              "path_hash": "fc2883c495e6305aaa899b5fa8daafb1",
              "privacy_level": "private_local_only",
              "rank": 1,
              "score": 0.366393,
              "score_components": {
                "fts": null,
                "image_embedding": null,
                "metadata": 0.35
              },
              "snippet_redacted": "",
              "thumbnail_url": null,
              "timestamp_sec": null,
              "title_redacted": "home_clip_0.mp4"
            },
            {
              "asset_id": "mm_581d6010dbca3849f7774223",
              "evidence_ref": "mm_ev_6b8a6f4563b15732f0",
              "matched_by": [
                "metadata"
              ],
              "modality": "video",
              "path_hash": "fafa125fb9f819e144cecfa1dbecb2d8",
              "privacy_level": "private_local_only",
              "rank": 2,
              "score": 0.191129,
              "score_components": {
                "fts": null,
                "image_embedding": null,
                "metadata": 0.175
              },
              "snippet_redacted": "",
              "thumbnail_url": null,
              "timestamp_sec": null,
              "title_redacted": "home_clip_1.mp4"
            },
            {
              "asset_id": "mm_eadf8d146b97633f9c39d3c4",
              "evidence_ref": "mm_ev_5525481b2cd2a3c6f3",
              "matched_by": [
                "metadata"
              ],
              "modality": "video",
              "path_hash": "cbd9daf2c34ad21d5ca65a0a4cd59223",
              "privacy_level": "private_local_only",
              "rank": 3,
              "score": 0.13254,
              "score_components": {
                "fts": null,
                "image_embedding": null,
                "metadata": 0.11666666666666665
              },
              "snippet_redacted": "",
              "thumbnail_url": null,
              "timestamp_sec": null,
              "title_redacted": "home_clip_2.mp4"
            },
            {
              "asset_id": "mm_f5bfbf2ee9a9fb6d487b33bb",
              "evidence_ref": "mm_ev_2f0bd5b98b0e548118",
              "matched_by": [
                "metadata"
              ],
              "modality": "video",
              "path_hash": "dde676bedef7583fb40039d28f255251",
              "privacy_level": "private_local_only",
              "rank": 4,
              "score": 0.103125,
              "score_components": {
                "fts": null,
                "image_embedding": null,
                "metadata": 0.0875
              },
              "snippet_redacted": "",
              "thumbnail_url": null,
              "timestamp_sec": null,
              "title_redacted": "home_clip_3.mp4"
            },
            {
              "asset_id": "mm_3cf550606f0b163882021488",
              "evidence_ref": "mm_ev_2e003366d72c18b389",
              "matched_by": [
                "metadata"
              ],
              "modality": "video",
              "path_hash": "5213c98d881675ab91a75740784630e2",
              "privacy_level": "private_local_only",
              "rank": 5,
              "score": 0.085385,
              "score_components": {
                "fts": null,
                "image_embedding": null,
                "metadata": 0.06999999999999999
              },
              "snippet_redacted": "",
              "thumbnail_url": null,
              "timestamp_sec": null,
              "title_redacted": "home_clip_4.mp4"
            }
          ],
          "retrieval_mode": "fts_first_plus_image_embedding",
          "run_id": "mm_run_a8ecfa2ed35f43a1",
          "trace_id": "mm_trace_9bc531096ab24b49"
        }
      },
      "route_adapter": {
        "rebuild": {
          "counts": {
            "archive": 1,
            "audio": 5,
            "code": 5,
            "document": 10,
            "image": 10,
            "video": 6
          },
          "duration_sec": 0.015,
          "image_embedding_available": true,
          "image_embedding_model": {
            "backend": "pillow_numpy",
            "device": "cpu",
            "local_only": true,
            "model_family": "local_feature_embedding",
            "model_name": "digua-local-visual-text-embedding-v1",
            "precision": "float32",
            "vector_dim": 16,
            "weights_committed_to_repo": false
          },
          "image_embeddings": 10,
          "indexed_assets": 37,
          "ok": true,
          "privacy": {
            "cloud_used": false,
            "private_leak_count": 0,
            "raw_path_rows": 0
          },
          "text_chunks": 15
        },
        "rebuild_status": 200,
        "summary": {
          "ok": true,
          "status": {
            "cloud_used": false,
            "counts": {
              "archive": 1,
              "audio": 5,
              "code": 5,
              "document": 10,
              "image": 10,
              "video": 6
            },
            "degraded": false,
            "degraded_reason": null,
            "embedding_count": 10,
            "feature_flags": {
              "asr_enabled": false,
              "audio_transcript_enabled": false,
              "biometric_recognition_enabled": false,
              "cloud_asr_enabled": false,
              "cloud_ocr_enabled": false,
              "cloud_vision_enabled": false,
              "destructive_actions_enabled": false,
              "document_embedding_enabled": false,
              "face_identification_enabled": false,
              "image_embedding_enabled": true,
              "image_embedding_required_for_delivery": true,
              "multimodal_metadata_index_enabled": true,
              "multimodal_search_enabled": true,
              "ocr_enabled": false,
              "qwen_tool_execution_enabled": false,
              "sensitive_attribute_inference_enabled": false,
              "vector_extension_enabled": "auto",
              "vector_numpy_fallback_enabled": true,
              "video_keyframe_embedding_enabled": false,
              "video_keyframe_enabled": false
            },
            "indexed_count": 37,
            "ok": true,
            "private_leak_count": 0,
            "qwen_tool_execution_enabled": false,
            "raw_path_rows": 0,
            "schema": "digua_multimodal_search_v1"
          }
        },
        "summary_status": 200
      }
    },
    "eval": {
      "case_count": 40,
      "degraded_behavior_pass": true,
      "evidence_ref_rate": 1.0,
      "feature_flag_consistency": true,
      "image_semantic_cases_pass": 1.0,
      "modality_hit_rate": 1.0,
      "no_raw_path_rate": 1.0,
      "ok": true,
      "private_leak_count": 0,
      "query_latency_p50": 7.37,
      "query_latency_p95": 7.81,
      "rows": [
        {
          "case_id": "img_001",
          "evidence_ref": true,
          "latency_ms": 7.06,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "img_002",
          "evidence_ref": true,
          "latency_ms": 6.93,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "img_003",
          "evidence_ref": true,
          "latency_ms": 7.07,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "img_004",
          "evidence_ref": true,
          "latency_ms": 7.04,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "img_005",
          "evidence_ref": true,
          "latency_ms": 7.44,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "img_006",
          "evidence_ref": true,
          "latency_ms": 7.73,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "img_007",
          "evidence_ref": true,
          "latency_ms": 7.17,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "img_008",
          "evidence_ref": true,
          "latency_ms": 7.11,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "img_009",
          "evidence_ref": true,
          "latency_ms": 7.63,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "img_010",
          "evidence_ref": true,
          "latency_ms": 7.14,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "doc_001",
          "evidence_ref": true,
          "latency_ms": 6.8,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "doc_002",
          "evidence_ref": true,
          "latency_ms": 6.71,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "doc_003",
          "evidence_ref": true,
          "latency_ms": 7.65,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "doc_004",
          "evidence_ref": true,
          "latency_ms": 7.2,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "doc_005",
          "evidence_ref": true,
          "latency_ms": 7.49,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "doc_006",
          "evidence_ref": true,
          "latency_ms": 7.72,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "doc_007",
          "evidence_ref": true,
          "latency_ms": 6.95,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "doc_008",
          "evidence_ref": true,
          "latency_ms": 7.22,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "doc_009",
          "evidence_ref": true,
          "latency_ms": 7.65,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "doc_010",
          "evidence_ref": true,
          "latency_ms": 6.89,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "vid_001",
          "evidence_ref": true,
          "latency_ms": 6.96,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "vid_002",
          "evidence_ref": true,
          "latency_ms": 7.54,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "vid_003",
          "evidence_ref": true,
          "latency_ms": 6.67,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "vid_004",
          "evidence_ref": true,
          "latency_ms": 7.5,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "vid_005",
          "evidence_ref": true,
          "latency_ms": 7.46,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "aud_001",
          "evidence_ref": true,
          "latency_ms": 8.39,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "aud_002",
          "evidence_ref": true,
          "latency_ms": 7.23,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "aud_003",
          "evidence_ref": true,
          "latency_ms": 7.53,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "aud_004",
          "evidence_ref": true,
          "latency_ms": 7.68,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "aud_005",
          "evidence_ref": true,
          "latency_ms": 7.67,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "code_001",
          "evidence_ref": true,
          "latency_ms": 7.63,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "code_002",
          "evidence_ref": true,
          "latency_ms": 7.23,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "code_003",
          "evidence_ref": true,
          "latency_ms": 7.19,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "code_004",
          "evidence_ref": true,
          "latency_ms": 8.08,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "code_005",
          "evidence_ref": true,
          "latency_ms": 7.65,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "arc_001",
          "evidence_ref": true,
          "latency_ms": 5.84,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "all_001",
          "evidence_ref": true,
          "latency_ms": 7.81,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "all_002",
          "evidence_ref": true,
          "latency_ms": 7.56,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "all_003",
          "evidence_ref": true,
          "latency_ms": 7.31,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        },
        {
          "case_id": "all_004",
          "evidence_ref": true,
          "latency_ms": 7.57,
          "modality_hit": true,
          "no_raw_path": true,
          "ok": true,
          "private_leak_count": 0
        }
      ]
    },
    "indexer": {
      "ok": true,
      "rebuild": {
        "counts": {
          "archive": 1,
          "audio": 5,
          "code": 5,
          "document": 10,
          "image": 10,
          "video": 6
        },
        "duration_sec": 0.015,
        "image_embedding_available": true,
        "image_embedding_model": {
          "backend": "pillow_numpy",
          "device": "cpu",
          "local_only": true,
          "model_family": "local_feature_embedding",
          "model_name": "digua-local-visual-text-embedding-v1",
          "precision": "float32",
          "vector_dim": 16,
          "weights_committed_to_repo": false
        },
        "image_embeddings": 10,
        "indexed_assets": 37,
        "ok": true,
        "privacy": {
          "cloud_used": false,
          "private_leak_count": 0,
          "raw_path_rows": 0
        },
        "text_chunks": 15
      },
      "vector_store": {
        "backend": "numpy",
        "degraded": false,
        "ok": true,
        "vector_count": 10,
        "vector_dim": 16
      }
    },
    "schema": {
      "feature_flags": {
        "asr_enabled": false,
        "audio_transcript_enabled": false,
        "biometric_recognition_enabled": false,
        "cloud_asr_enabled": false,
        "cloud_ocr_enabled": false,
        "cloud_vision_enabled": false,
        "destructive_actions_enabled": false,
        "document_embedding_enabled": false,
        "face_identification_enabled": false,
        "image_embedding_enabled": true,
        "image_embedding_required_for_delivery": true,
        "multimodal_metadata_index_enabled": true,
        "multimodal_search_enabled": true,
        "ocr_enabled": false,
        "qwen_tool_execution_enabled": false,
        "sensitive_attribute_inference_enabled": false,
        "vector_extension_enabled": "auto",
        "vector_numpy_fallback_enabled": true,
        "video_keyframe_embedding_enabled": false,
        "video_keyframe_enabled": false
      },
      "ok": true,
      "tables": [
        "mm_assets",
        "mm_embeddings",
        "mm_media_metadata",
        "mm_search_results",
        "mm_search_runs",
        "mm_text_chunks",
        "mm_text_chunks_fts",
        "mm_text_chunks_fts_config",
        "mm_text_chunks_fts_content",
        "mm_text_chunks_fts_data",
        "mm_text_chunks_fts_docsize",
        "mm_text_chunks_fts_idx",
        "mm_thumbnails",
        "mm_video_keyframes"
      ]
    },
    "security": {
      "cloud_used": false,
      "destructive_actions_enabled": false,
      "ok": true,
      "optional_content_features": {
        "asr_enabled": false,
        "audio_transcript_enabled": false,
        "ocr_enabled": false,
        "video_keyframe_embedding_enabled": false,
        "video_keyframe_enabled": false
      },
      "private_leak_count": 0,
      "qwen_tool_execution_enabled": false,
      "raw_path_returned": false
    },
    "tests": {
      "ok": true,
      "pytest_multimodal": {
        "cmd": [
          "<python>",
          "-m",
          "pytest",
          "tests/test_multimodal_search_v1.py",
          "-q"
        ],
        "duration_sec": 1.476,
        "returncode": 0,
        "stderr_tail": "",
        "stdout_tail": "..........                                                               [100%]\n10 passed in 1.07s\n"
      },
      "self_check": {
        "cmd": [
          "<python>",
          "SELF_CHECK.py"
        ],
        "duration_sec": 0.049,
        "returncode": 0,
        "stderr_tail": "",
        "stdout_tail": "{\n  \"ok\": true,\n  \"missing\": [],\n  \"checks\": {\n    \"missing_required_count\": 0,\n    \"real_qwen_tokenizer_used\": true,\n    \"private_leak_count\": 0,\n    \"total_cases\": 130,\n    \"quality_pass_rate\": 1.0,\n    \"final_verdict\": \"tokenizer_token_budget_product_deployed_claim_supported\"\n  }\n}\n"
      }
    },
    "ui": {
      "html_bytes": 2803,
      "js_bytes": 8207,
      "node_check": {
        "cmd": [
          "node",
          "--check",
          "web/static/digua_multimodal_search.js"
        ],
        "duration_sec": 0.001,
        "error": "[WinError 2] 系统找不到指定的文件。",
        "returncode": null
      },
      "ok": true
    },
    "ui_browser": {
      "browser_dom_snapshot_error": "in_app_browser_snapshot_api_unavailable",
      "browser_dom_snapshot_ok": false,
      "browser_path": "in_app_browser_locator_evaluate_screenshot",
      "desktop": {
        "auth": "Signed in: mm_ui_admin",
        "body_has_auth_required": false,
        "body_has_request_failed": false,
        "console_error_or_warning_count": 0,
        "evidence_contains_ref": true,
        "first_title": "white_shirt_photo.png",
        "result_count": 10,
        "status": "Results ready",
        "title": "Digua Multimodal Search",
        "url": "http://127.0.0.1:8791/multimodal-search"
      },
      "fallback_reason": "Browser domSnapshot failed in plugin runtime; Python Playwright and Node were unavailable on this host, so validation used the Browser plugin locator, evaluate, and screenshot APIs.",
      "flow": "local multimodal page -> login -> image search -> evidence side panel",
      "mobile": {
        "auth": "Signed in: mm_ui_admin",
        "body_has_auth_required": false,
        "first_title": "renovation_invoice_receipt.txt",
        "has_horizontal_overflow": false,
        "result_count": 10,
        "scroll_width": 375,
        "shell_width": 355,
        "status": "Results ready",
        "viewport_width": 390
      },
      "ok": true,
      "python_playwright_available": false,
      "screenshots_captured": true,
      "temporary_server": {
        "asset_count": 37,
        "image_embeddings": 10,
        "stopped_after_validation": true
      }
    }
  },
  "ok": true,
  "soak_24h_started": false,
  "soak_scope": "not_requested",
  "summary": {
    "eval_case_count": 40,
    "image_embeddings": 10,
    "indexed_assets": 37,
    "no_raw_path_rate": 1.0,
    "optional_ocr_video_audio_content": "disabled_by_feature_flag",
    "private_leak_count": 0
  },
  "verdict": "multimodal_search_v1_ready_with_optional_ocr_video_audio_disabled"
}
```
