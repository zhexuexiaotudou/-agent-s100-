# 26020_multimodal_search_api_gate

- ok: `True`

```json
{
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
          "asset_id": "mm_fd5a8a0d53d2e21794cefc7f",
          "evidence_ref": "mm_ev_82c72cfbbf49d53967",
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
      "run_id": "mm_run_a8419b6361904c02",
      "trace_id": "mm_trace_4f7f95fac7024307"
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
          "asset_id": "mm_b7f5a6b42ce2f2fd4844d317",
          "evidence_ref": "mm_ev_3b4c3d5151153942c8",
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
          "asset_id": "mm_d7ae79fdf0b0188244b86753",
          "evidence_ref": "mm_ev_7435ef27d8c1922d3d",
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
          "asset_id": "mm_d6055c8d036b2c96ecb012d8",
          "evidence_ref": "mm_ev_5fa02b28db56214f6a",
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
          "asset_id": "mm_eedbba66f45016f1d6d17fe7",
          "evidence_ref": "mm_ev_427a7235542c87f1b2",
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
          "asset_id": "mm_11e417678037c656138074df",
          "evidence_ref": "mm_ev_d837eefceef2a9355e",
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
      "run_id": "mm_run_3d2cbd5ba0224507",
      "trace_id": "mm_trace_1b3a545505d44a63"
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
          "asset_id": "mm_f8a480360ffc5e5b0a737234",
          "evidence_ref": "mm_ev_e6701ef0323ee12dd9",
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
          "asset_id": "mm_a7f09c636a42cf4252e6b564",
          "evidence_ref": "mm_ev_4b11facf372f40428f",
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
          "asset_id": "mm_9cc1a48a59b44f1f21717f40",
          "evidence_ref": "mm_ev_84178ddcf2638fcde7",
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
          "asset_id": "mm_666c9e405afeb2e00c75aedb",
          "evidence_ref": "mm_ev_62ef9e8faf3e4b0a94",
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
          "asset_id": "mm_2434767fbb4a6096a029df59",
          "evidence_ref": "mm_ev_3eae262cc740e1cbaa",
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
      "run_id": "mm_run_f58d4f01908f49b4",
      "trace_id": "mm_trace_d11ffd26233e48c9"
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
          "asset_id": "mm_7b96b8f0953b1ea8b63ffa74",
          "evidence_ref": "mm_ev_1384d29195b6c041c0",
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
          "asset_id": "mm_d2b2f9bab511906ae02bf913",
          "evidence_ref": "mm_ev_5e83a99ee989b25f05",
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
          "asset_id": "mm_f3802d72df8b40c2e90c4286",
          "evidence_ref": "mm_ev_53bdd0cf2d2a7da80a",
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
          "asset_id": "mm_9607baa8c19fd76697dddd67",
          "evidence_ref": "mm_ev_ead5d231d24af53e79",
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
          "asset_id": "mm_965bc751ab6bc8bef8d73dea",
          "evidence_ref": "mm_ev_9cd627863ea2450467",
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
      "run_id": "mm_run_5e6b63ade3ec4350",
      "trace_id": "mm_trace_d3c1d48267a74814"
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
          "asset_id": "mm_ceac7b2762330f402ece30c4",
          "evidence_ref": "mm_ev_9782fbdc6d21acf6eb",
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
          "thumbnail_url": "/api/multimodal-index/item/mm_ceac7b2762330f402ece30c4",
          "timestamp_sec": null,
          "title_redacted": "white_shirt_photo.png"
        },
        {
          "asset_id": "mm_13f5224ca2ffe10b5938ddf3",
          "evidence_ref": "mm_ev_253b012fc46fd0b57d",
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
          "thumbnail_url": "/api/multimodal-index/item/mm_13f5224ca2ffe10b5938ddf3",
          "timestamp_sec": null,
          "title_redacted": "gray_box_photo.png"
        },
        {
          "asset_id": "mm_09c8fa080d089739a46884a3",
          "evidence_ref": "mm_ev_ac148bf46c76dfba8c",
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
          "thumbnail_url": "/api/multimodal-index/item/mm_09c8fa080d089739a46884a3",
          "timestamp_sec": null,
          "title_redacted": "white_wall_reference.png"
        },
        {
          "asset_id": "mm_dc621c5f7b6b67d22d5e3170",
          "evidence_ref": "mm_ev_836d05c2cc7f412652",
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
          "thumbnail_url": "/api/multimodal-index/item/mm_dc621c5f7b6b67d22d5e3170",
          "timestamp_sec": null,
          "title_redacted": "blue_folder_cover.png"
        },
        {
          "asset_id": "mm_b35b7183d8b3ef2604379b02",
          "evidence_ref": "mm_ev_d3d5916fe6fe639e2e",
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
          "thumbnail_url": "/api/multimodal-index/item/mm_b35b7183d8b3ef2604379b02",
          "timestamp_sec": null,
          "title_redacted": "black_router_photo.png"
        }
      ],
      "retrieval_mode": "fts_first_plus_image_embedding",
      "run_id": "mm_run_00e1c9e49e734f36",
      "trace_id": "mm_trace_a060cb45594f4044"
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
          "asset_id": "mm_ce97f7696fcfa671c0ed1e5b",
          "evidence_ref": "mm_ev_2c5f63c32ea5c17908",
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
          "asset_id": "mm_c6104e5751607a35be83124d",
          "evidence_ref": "mm_ev_e7589aefbcc856b2fe",
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
          "asset_id": "mm_eac794d0f4101098048920f6",
          "evidence_ref": "mm_ev_ffcce1997d7285f2cd",
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
          "asset_id": "mm_70ebfe0efef65fcc206bfe20",
          "evidence_ref": "mm_ev_26d62ebbe2669c1853",
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
          "asset_id": "mm_dc22be3f2a5a8b23d41d034e",
          "evidence_ref": "mm_ev_a9b6f5079c04ad94ec",
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
      "run_id": "mm_run_e25e5007f5d14295",
      "trace_id": "mm_trace_121af50a8b5f45b4"
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
}
```
