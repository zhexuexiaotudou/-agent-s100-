import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
PROBES_ROOT = REPO_ROOT / "scripts" / "probes"
if str(PROBES_ROOT) not in sys.path:
    sys.path.insert(0, str(PROBES_ROOT))

from ai_nas_operator_portal_server import PortalState


class CopilotLocalQwenChatTest(unittest.TestCase):
    def make_state(self, root: Path, *, personal: bool = False) -> PortalState:
        personal_root = root / "Personal" if personal else None
        if personal_root:
            personal_root.mkdir(parents=True)
        return PortalState(
            root / "reports",
            [],
            refresh_on_start=False,
            personal_root=personal_root,
            sqlite_index_path=root / "personal_inventory.sqlite3",
            operation_db_path=root / "operator_portal_operations.sqlite3",
            document_fts_db_path=root / "document_fts.sqlite3",
        )

    def fake_qwen(self, content: str = "Qwen response.") -> dict:
        return {
            "ok": True,
            "status": 200,
            "elapsed_ms": 4.2,
            "payload": {
                "model": "Qwen2.5-1.5B-Instruct-S100P-official",
                "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 8, "completion_tokens": 9},
            },
        }

    def fake_router(self, route: str = "local", privacy_level: str = "none", task_complexity: str = "simple", local_tool_id: str | None = None) -> dict:
        return self.fake_qwen(json.dumps({
            "route": route,
            "privacy_level": privacy_level,
            "task_complexity": task_complexity,
            "reason": "unit-test qwen route",
            "local_tool_id": local_tool_id,
        }))

    def test_ai_nas_capability_prompt_uses_local_qwen_not_curated_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.make_state(Path(tmp))

            with patch(
                "ai_nas_operator_portal_server.http_post_json",
                side_effect=[
                    self.fake_router(),
                    self.fake_qwen("Qwen answered the Digua AI-NAS capability question."),
                ],
            ) as post_json:
                status, payload = state.copilot_chat("Summarize Digua AI-NAS core capabilities.", {"username": "admin"})

            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["assistant_mode"], "local_qwen_chat")
            self.assertEqual(payload["route"], "local_qwen_chat")
            self.assertIn("Qwen answered", payload["answer"])
            self.assertFalse(payload["cloud_used"])
            self.assertFalse(payload["qwen_execution_authority"])
            self.assertFalse(payload["audit"]["tool_execution_performed"])
            self.assertEqual(payload["qwen_router"]["route"], "local")
            self.assertEqual(post_json.call_count, 2)
            router_payload = post_json.call_args_list[0].args[2]
            self.assertEqual(router_payload["metadata"]["purpose"], "edge_cloud_route_classifier")
            self.assertEqual(router_payload["messages"][0]["content"], "Summarize Digua AI-NAS core capabilities.")
            sent_payload = post_json.call_args_list[1].args[2]
            self.assertEqual(sent_payload["messages"], [{"role": "user", "content": "Summarize Digua AI-NAS core capabilities."}])
            self.assertTrue(sent_payload["disable_ai_nas_tools"])
            self.assertTrue(sent_payload["metadata"]["disable_ai_nas_tools"])
            self.assertFalse(sent_payload["metadata"]["qwen_execution_authority"])
            self.assertLessEqual(sent_payload["max_tokens"], 256)

    def test_plain_copilot_prompt_forwards_exact_prompt_to_local_qwen(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.make_state(Path(tmp))

            with patch(
                "ai_nas_operator_portal_server.http_post_json",
                side_effect=[
                    self.fake_router(),
                    self.fake_qwen("I am a local Qwen assistant."),
                ],
            ) as post_json:
                status, payload = state.copilot_chat("Who are you?", {"username": "admin"})

            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["assistant_mode"], "local_qwen_chat")
            self.assertEqual(payload["route"], "local_qwen_chat")
            self.assertIn("local Qwen", payload["answer"])
            self.assertEqual(payload["qwen_router"]["classifier"], "qwen_gateway_structured_router")
            self.assertEqual(post_json.call_count, 2)
            sent_payload = post_json.call_args_list[1].args[2]
            self.assertEqual(sent_payload["messages"], [{"role": "user", "content": "Who are you?"}])
            self.assertTrue(sent_payload["metadata"]["disable_ai_nas_tools"])
            self.assertFalse(sent_payload["metadata"]["qwen_execution_authority"])

    def test_person_photo_search_uses_qwen_router_then_local_yolo_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.make_state(Path(tmp), personal=True)
            assert state.identity_store is not None
            state.identity_store.create_user("admin", "admin123", "admin")
            photo = Path(tmp) / "Personal" / "Photos" / "family_photo_redacted.jpg"
            photo.parent.mkdir(parents=True, exist_ok=True)
            photo.write_bytes(b"fake-local-image")
            photo_hash = hashlib.sha256(str(photo.resolve()).encode("utf-8", errors="replace")).hexdigest()
            photo_stat = photo.stat()
            yolo_payload = {
                "ok": True,
                "query_redacted": "搜索 NAS 里有人的照片",
                "labels": ["person"],
                "results": [
                    {
                        "rank": 1,
                        "asset_id": "asset_person_001",
                        "title_redacted": "family_photo_redacted.jpg",
                        "modality": "image",
                        "file_type": ".jpg",
                        "size_bytes": photo_stat.st_size,
                        "mtime": int(photo_stat.st_mtime),
                        "privacy_level": "private_local_only",
                        "score": 0.91,
                        "matched_by": ["yolo_object"],
                        "object_labels": ["person"],
                        "detections": [
                            {"label": "person", "confidence": 0.91, "bbox": [0.1, 0.2, 0.4, 0.8], "evidence_ref": "yolo_ev_001"}
                        ],
                        "evidence_ref": "yolo_ev_001",
                        "path_hash": photo_hash,
                    }
                ],
                "degraded": False,
                "privacy": {"raw_path_returned": False, "cloud_used": False},
            }

            with patch("ai_nas_operator_portal_server.yolo_route_response", return_value=(200, yolo_payload)) as yolo_route:
                with patch(
                    "ai_nas_operator_portal_server.http_post_json",
                    return_value=self.fake_router(privacy_level="high", local_tool_id="local_nas_search"),
                ) as post_json:
                    status, payload = state.copilot_chat("搜索 NAS 里有人的照片", {"username": "admin"})

            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["assistant_mode"], "local_yolo_search")
            self.assertEqual(payload["route"], "local_yolo_search")
            self.assertIn("找到 1 张相关照片", payload["answer"])
            self.assertIn("不做人脸识别", payload["answer"])
            self.assertEqual(payload["search"]["labels"], ["person"])
            self.assertEqual(payload["search"]["result_count"], 1)
            self.assertEqual(payload["search"]["results"][0]["asset_id"], "asset_person_001")
            self.assertEqual(payload["search"]["results"][0]["display"]["name"], "family_photo_redacted.jpg")
            self.assertEqual(payload["search"]["results"][0]["display"]["privacy_label"], "本地私有")
            self.assertTrue(payload["search"]["results"][0]["preview_url"].startswith("/api/storage/preview-by-hash?path_hash="))
            self.assertNotIn("relative_path", payload["search"]["results"][0])
            self.assertFalse(payload["cloud_used"])
            self.assertFalse(payload["qwen_execution_authority"])
            self.assertFalse(payload["audit"]["direct_nas_write_performed"])
            self.assertFalse(payload["audit"]["cloud_payload_sent"])
            self.assertEqual(payload["nas_action"]["operation"], "search")
            self.assertEqual(payload["qwen_router"]["route"], "local")
            self.assertEqual(payload["qwen_router"]["local_tool_id"], "local_nas_search")
            post_json.assert_called_once()
            router_payload = post_json.call_args.args[2]
            self.assertEqual(router_payload["metadata"]["purpose"], "edge_cloud_route_classifier")
            self.assertEqual(router_payload["messages"][0]["content"], "搜索 NAS 里有人的照片")
            yolo_route.assert_called_once()
            yolo_request = yolo_route.call_args.kwargs["payload"]
            self.assertEqual(yolo_request["query"], "搜索 NAS 里有人的照片")
            self.assertEqual(yolo_request["modality"], "image")

    def test_image_search_empty_result_still_stays_on_local_search_after_qwen_router(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.make_state(Path(tmp), personal=True)
            yolo_payload = {
                "ok": True,
                "query_redacted": "找有人的图片",
                "labels": ["person"],
                "results": [],
                "degraded": True,
                "degraded_reason": "no_matching_yolo_detection",
                "privacy": {"raw_path_returned": False, "cloud_used": False},
            }

            with patch("ai_nas_operator_portal_server.yolo_route_response", return_value=(200, yolo_payload)):
                with patch(
                    "ai_nas_operator_portal_server.http_post_json",
                    return_value=self.fake_router(privacy_level="high", local_tool_id="local_nas_search"),
                ) as post_json:
                    status, payload = state.copilot_chat("找有人的图片", {"username": "admin"})

            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["assistant_mode"], "local_yolo_search")
            self.assertEqual(payload["search"]["result_count"], 0)
            self.assertEqual(payload["nas_action"]["status"], "completed_empty")
            self.assertIn("对象/语义索引", payload["answer"])
            self.assertIn("没有返回匹配图片", payload["answer"])
            self.assertNotIn("文件盘点", payload["answer"])
            post_json.assert_called_once()

    def test_yolo_fixture_preview_hash_is_allowlisted_without_raw_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.make_state(Path(tmp), personal=True)
            assert state.identity_store is not None
            state.identity_store.create_user("admin", "admin123", "admin")
            fixture = Path(tmp) / "yolo_v2_fixture" / "images" / "person_fixture.jpg"
            fixture.parent.mkdir(parents=True, exist_ok=True)
            fixture.write_bytes(b"fixture-image")
            fixture_hash = hashlib.sha256(str(fixture.resolve()).encode("utf-8", errors="replace")).hexdigest()

            path, rel = state.storage_file_by_path_hash(fixture_hash, {"username": "admin"})

            self.assertEqual(path, fixture)
            self.assertIsNone(rel)

    def test_quoted_nas_path_uses_qwen_router_then_existing_readonly_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = self.make_state(root, personal=True)
            assert state.identity_store is not None
            state.identity_store.create_user("admin", "admin123", "admin")
            inbox = root / "Personal" / "Inbox"
            inbox.mkdir()
            (inbox / "note.txt").write_text("hello", encoding="utf-8")

            with patch(
                "ai_nas_operator_portal_server.http_post_json",
                return_value=self.fake_router(privacy_level="high", local_tool_id="local_storage_list"),
            ) as post_json:
                status, payload = state.copilot_chat('list "Inbox"', {"username": "admin", "role": "admin"})

            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["nas_action"]["operation"], "list")
            self.assertEqual(payload["nas_action"]["status"], "completed")
            self.assertEqual(payload["assistant_mode"], "local_storage_list")
            self.assertEqual(payload["qwen_router"]["local_tool_id"], "local_storage_list_or_inspect")
            post_json.assert_called_once()

    def test_document_query_uses_qwen_router_then_local_document_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.make_state(Path(tmp), personal=True)

            with patch(
                "ai_nas_operator_portal_server.http_post_json",
                return_value=self.fake_router(privacy_level="high", local_tool_id="local_document_rag"),
            ):
                with patch.object(
                    state,
                    "document_query_payload",
                    return_value=(200, {"ok": True, "answer": "Local document evidence.", "evidence_count": 1}),
                ) as document_query:
                    status, payload = state.copilot_chat("总结 Documents 里的发票文档", {"username": "admin"})

            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["assistant_mode"], "local_document_query")
            self.assertEqual(payload["route"], "local_document_query")
            self.assertEqual(payload["qwen_router"]["local_tool_id"], "local_document_rag")
            document_query.assert_called_once()

    def test_document_query_uses_local_qwen_to_answer_grounded_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.make_state(Path(tmp), personal=True)
            evidence = [
                {
                    "evidence_ref": "ev_1",
                    "name": "family_expense_bill_20260520_1314.md",
                    "relative_path": "Documents/DemoDocs/family_expense_bill_20260520_1314.md",
                    "extension": ".md",
                    "snippet": "\u8d26\u5355\u65e5\u671f\uff1a2026\u5e745\u670820\u65e5\u3002\u5408\u8ba1\u91d1\u989d\uff1a1314\u5143\u3002",
                }
            ]

            with patch(
                "ai_nas_operator_portal_server.http_post_json",
                side_effect=[
                    self.fake_router(privacy_level="high", local_tool_id="local_document_rag"),
                    self.fake_qwen("\u6839\u636e\u672c\u5730\u6587\u6863\uff0c2026\u5e745\u670820\u65e5\u5bb6\u5ead\u5f00\u652f\u8d26\u5355\u7684\u5408\u8ba1\u91d1\u989d\u662f 1314\u5143\u3002"),
                ],
            ) as post_json:
                with patch.object(
                    state,
                    "document_query_payload",
                    return_value=(
                        200,
                        {
                            "ok": True,
                            "answer": "deterministic fallback",
                            "evidence_count": 1,
                            "evidence": evidence,
                            "evidence_refs": ["ev_1"],
                            "amount_hits": ["1314\u5143"],
                        },
                    ),
                ):
                    status, payload = state.copilot_chat(
                        "2026\u5e745\u670820\u65e5\u5bb6\u5ead\u5f00\u652f\u8d26\u5355\u4fe1\u606f",
                        {"username": "admin", "role": "admin"},
                    )

            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["assistant_mode"], "local_document_query")
            self.assertEqual(payload["document_answer_source"], "local_qwen_grounded_rag")
            self.assertTrue(payload["qwen_document_answer_used"])
            self.assertIn("1314\u5143", payload["answer"])
            self.assertEqual(post_json.call_count, 2)
            grounded_payload = post_json.call_args_list[1].args[2]
            self.assertEqual(grounded_payload["metadata"]["purpose"], "local_document_grounded_answer")
            self.assertFalse(grounded_payload["metadata"]["qwen_execution_authority"])
            self.assertTrue(grounded_payload["disable_ai_nas_tools"])
            grounded_prompt = grounded_payload["messages"][0]["content"]
            self.assertIn("detected_amounts=1314\u5143", grounded_prompt)
            self.assertNotIn("/mnt/nas", grounded_prompt)

    def test_document_query_rejects_generic_qwen_answer_without_grounded_amount(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.make_state(Path(tmp), personal=True)
            evidence = [
                {
                    "evidence_ref": "ev_1",
                    "name": "family_expense_bill_20260520_1314.md",
                    "relative_path": "Documents/DemoDocs/family_expense_bill_20260520_1314.md",
                    "extension": ".md",
                    "snippet": "\u5408\u8ba1\u91d1\u989d\uff1a1314\u5143\u3002",
                }
            ]

            with patch(
                "ai_nas_operator_portal_server.http_post_json",
                side_effect=[
                    self.fake_router(privacy_level="high", local_tool_id="local_document_rag"),
                    self.fake_qwen("\u5f53\u7136\u53ef\u4ee5\uff0c\u8bf7\u95ee\u60a8\u6709\u4ec0\u4e48\u95ee\u9898\u6216\u9700\u8981\u6211\u56de\u7b54\u6216\u5e2e\u52a9\u7684\u5730\u65b9\uff1f"),
                    self.fake_qwen("\u65e0\u6cd5\u786e\u5b9a\u3002"),
                    self.fake_qwen("\u8bf7\u60a8\u63d0\u4f9b\u66f4\u591a\u80cc\u666f\u4fe1\u606f\u3002"),
                    self.fake_qwen("\u7b54\u6848\uff1a\u7ea6\u7b49\u4e8e 1314.68 \u5143\u3002"),
                ],
            ):
                with patch.object(
                    state,
                    "document_query_payload",
                    return_value=(
                        200,
                        {
                            "ok": True,
                            "answer": "\u547d\u4e2d\u91d1\u989d\uff1a1314\u5143\u3002",
                            "evidence_count": 1,
                            "evidence": evidence,
                            "evidence_refs": ["ev_1"],
                            "amount_hits": ["1314\u5143"],
                        },
                    ),
                ):
                    status, payload = state.copilot_chat(
                        "2026\u5e745\u670820\u65e5\u5bb6\u5ead\u5f00\u652f\u8d26\u5355\u91d1\u989d\u662f\u591a\u5c11\uff1f",
                        {"username": "admin", "role": "admin"},
                    )

            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["document_answer_source"], "deterministic_evidence_fallback")
            self.assertFalse(payload["qwen_document_answer_used"])
            self.assertEqual(payload["grounded_qwen_error"], "local_qwen_document_answer_failed_grounding_validation")
            self.assertIn("1314\u5143", payload["answer"])
            self.assertNotIn("\u6709\u4ec0\u4e48\u95ee\u9898", payload["answer"])

    def test_document_query_retries_generic_qwen_answer_with_short_grounding_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.make_state(Path(tmp), personal=True)
            evidence = [
                {
                    "evidence_ref": "ev_1",
                    "name": "family_expense_bill_20260520_1314.md",
                    "relative_path": "Documents/DemoDocs/family_expense_bill_20260520_1314.md",
                    "extension": ".md",
                    "snippet": "\u5408\u8ba1\u91d1\u989d\uff1a1314\u5143\u3002",
                }
            ]

            with patch(
                "ai_nas_operator_portal_server.http_post_json",
                side_effect=[
                    self.fake_router(privacy_level="high", local_tool_id="local_document_rag"),
                    self.fake_qwen("\u5f53\u7136\u53ef\u4ee5\uff0c\u8bf7\u95ee\u60a8\u6709\u4ec0\u4e48\u95ee\u9898\u6216\u9700\u8981\u6211\u56de\u7b54\u6216\u5e2e\u52a9\u7684\u5730\u65b9\uff1f"),
                    self.fake_qwen("\u6839\u636e\u672c\u5730\u6587\u6863\uff0c\u5bb6\u5ead\u5f00\u652f\u8d26\u5355\u91d1\u989d\u662f 1314\u5143\u3002"),
                ],
            ) as post_json:
                with patch.object(
                    state,
                    "document_query_payload",
                    return_value=(
                        200,
                        {
                            "ok": True,
                            "answer": "\u547d\u4e2d\u91d1\u989d\uff1a1314\u5143\u3002",
                            "evidence_count": 1,
                            "evidence": evidence,
                            "evidence_refs": ["ev_1"],
                            "amount_hits": ["1314\u5143"],
                        },
                    ),
                ):
                    status, payload = state.copilot_chat(
                        "2026\u5e745\u670820\u65e5\u5bb6\u5ead\u5f00\u652f\u8d26\u5355\u91d1\u989d\u662f\u591a\u5c11\uff1f",
                        {"username": "admin", "role": "admin"},
                    )

            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["document_answer_source"], "local_qwen_grounded_rag")
            self.assertTrue(payload["qwen_document_answer_used"])
            self.assertTrue(payload["qwen_document_answer_retry_used"])
            self.assertIn("1314\u5143", payload["answer"])
            retry_payload = post_json.call_args_list[2].args[2]
            self.assertEqual(retry_payload["metadata"]["purpose"], "local_document_grounded_answer_retry")
            self.assertIn("detected_amounts=1314\u5143", retry_payload["messages"][0]["content"])

    def test_document_query_retries_approximate_qwen_amount(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.make_state(Path(tmp), personal=True)
            evidence = [
                {
                    "evidence_ref": "ev_1",
                    "name": "family_expense_bill_20260520_1314.md",
                    "relative_path": "Documents/DemoDocs/family_expense_bill_20260520_1314.md",
                    "extension": ".md",
                    "snippet": "\u5408\u8ba1\u91d1\u989d\uff1a1314\u5143\u3002",
                }
            ]

            with patch(
                "ai_nas_operator_portal_server.http_post_json",
                side_effect=[
                    self.fake_router(privacy_level="high", local_tool_id="local_document_rag"),
                    self.fake_qwen("\u7b54\u6848\uff1a\u7ea6\u7b49\u4e8e 1314.68 \u5143\u3002"),
                    self.fake_qwen("\u6839\u636e\u672c\u5730\u6587\u6863\uff0c\u5408\u8ba1\u91d1\u989d\u662f 1314\u5143\u3002"),
                ],
            ):
                with patch.object(
                    state,
                    "document_query_payload",
                    return_value=(
                        200,
                        {
                            "ok": True,
                            "answer": "\u547d\u4e2d\u91d1\u989d\uff1a1314\u5143\u3002",
                            "evidence_count": 1,
                            "evidence": evidence,
                            "evidence_refs": ["ev_1"],
                            "amount_hits": ["1314\u5143"],
                        },
                    ),
                ):
                    status, payload = state.copilot_chat(
                        "2026\u5e745\u670820\u65e5\u5bb6\u5ead\u5f00\u652f\u8d26\u5355\u91d1\u989d\u662f\u591a\u5c11\uff1f",
                        {"username": "admin", "role": "admin"},
                    )

            self.assertEqual(status, 200)
            self.assertTrue(payload["qwen_document_answer_used"])
            self.assertTrue(payload["qwen_document_answer_retry_used"])
            self.assertIn("1314\u5143", payload["answer"])
            self.assertNotIn("1314.68", payload["answer"])

    def test_document_query_retries_cny_only_answer_when_yuan_evidence_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.make_state(Path(tmp), personal=True)
            evidence = [
                {
                    "evidence_ref": "ev_1",
                    "name": "family_expense_bill_20260520_1314.md",
                    "relative_path": "Documents/DemoDocs/family_expense_bill_20260520_1314.md",
                    "extension": ".md",
                    "snippet": "\u5408\u8ba1\u91d1\u989d\uff1a1314\u5143\u3002 Demo ASCII hint: total amount is 1314 CNY.",
                }
            ]

            with patch(
                "ai_nas_operator_portal_server.http_post_json",
                side_effect=[
                    self.fake_router(privacy_level="high", local_tool_id="local_document_rag"),
                    self.fake_qwen("\u597d\u7684\uff0c\u7b54\u6848\u662f 1314 CNY\u3002"),
                    self.fake_qwen("\u6839\u636e\u672c\u5730\u6587\u6863\uff0c\u5408\u8ba1\u91d1\u989d\u662f 1314\u5143\u3002"),
                ],
            ):
                with patch.object(
                    state,
                    "document_query_payload",
                    return_value=(
                        200,
                        {
                            "ok": True,
                            "answer": "\u547d\u4e2d\u91d1\u989d\uff1a1314\u5143\u3002",
                            "evidence_count": 1,
                            "evidence": evidence,
                            "evidence_refs": ["ev_1"],
                            "amount_hits": ["1314\u5143", "1314CNY"],
                        },
                    ),
                ):
                    status, payload = state.copilot_chat(
                        "2026\u5e745\u670820\u65e5\u5bb6\u5ead\u5f00\u652f\u8d26\u5355\u91d1\u989d\u662f\u591a\u5c11\uff1f",
                        {"username": "admin", "role": "admin"},
                    )

            self.assertEqual(status, 200)
            self.assertTrue(payload["qwen_document_answer_used"])
            self.assertTrue(payload["qwen_document_answer_retry_used"])
            self.assertIn("1314\u5143", payload["answer"])
            self.assertNotIn("1314 CNY", payload["answer"])

    def test_document_query_normalizes_renminbi_unit_to_source_yuan(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.make_state(Path(tmp), personal=True)
            evidence = [
                {
                    "evidence_ref": "ev_1",
                    "name": "family_expense_bill_20260520_1314.md",
                    "relative_path": "Documents/DemoDocs/family_expense_bill_20260520_1314.md",
                    "extension": ".md",
                    "snippet": "\u5408\u8ba1\u91d1\u989d\uff1a1314\u5143\u3002",
                }
            ]

            with patch(
                "ai_nas_operator_portal_server.http_post_json",
                side_effect=[
                    self.fake_router(privacy_level="high", local_tool_id="local_document_rag"),
                    self.fake_qwen("1314\u4eba\u6c11\u5e01\u3002"),
                ],
            ):
                with patch.object(
                    state,
                    "document_query_payload",
                    return_value=(
                        200,
                        {
                            "ok": True,
                            "answer": "\u547d\u4e2d\u91d1\u989d\uff1a1314\u5143\u3002",
                            "evidence_count": 1,
                            "evidence": evidence,
                            "evidence_refs": ["ev_1"],
                            "amount_hits": ["1314\u5143"],
                        },
                    ),
                ):
                    status, payload = state.copilot_chat(
                        "2026\u5e745\u670820\u65e5\u5bb6\u5ead\u5f00\u652f\u8d26\u5355\u91d1\u989d\u662f\u591a\u5c11\uff1f",
                        {"username": "admin", "role": "admin"},
                    )

            self.assertEqual(status, 200)
            self.assertTrue(payload["qwen_document_answer_used"])
            self.assertIn("1314\u5143", payload["answer"])
            self.assertNotIn("1314\u4eba\u6c11\u5e01", payload["answer"])

    def test_document_query_retries_clarification_style_qwen_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.make_state(Path(tmp), personal=True)
            evidence = [
                {
                    "evidence_ref": "ev_1",
                    "name": "family_expense_bill_20260520_1314.md",
                    "relative_path": "Documents/DemoDocs/family_expense_bill_20260520_1314.md",
                    "extension": ".md",
                    "snippet": "\u5408\u8ba1\u91d1\u989d\uff1a1314\u5143\u3002",
                }
            ]

            with patch(
                "ai_nas_operator_portal_server.http_post_json",
                side_effect=[
                    self.fake_router(privacy_level="high", local_tool_id="local_document_rag"),
                    self.fake_qwen("\u68c0\u6d4b\u5230\u7684\u91d1\u989d\uff1a1314\u5143\u3002\u8bf7\u60a8\u63d0\u4f9b\u66f4\u591a\u80cc\u666f\u4fe1\u606f\u6216\u8005\u6f84\u6e05\u3002"),
                    self.fake_qwen("2026\u5e745\u670820\u65e5\u5bb6\u5ead\u5f00\u652f\u8d26\u5355\u7684\u5408\u8ba1\u91d1\u989d\u662f 1314\u5143\u3002"),
                ],
            ):
                with patch.object(
                    state,
                    "document_query_payload",
                    return_value=(
                        200,
                        {
                            "ok": True,
                            "answer": "\u547d\u4e2d\u91d1\u989d\uff1a1314\u5143\u3002",
                            "evidence_count": 1,
                            "evidence": evidence,
                            "evidence_refs": ["ev_1"],
                            "amount_hits": ["1314\u5143"],
                        },
                    ),
                ):
                    status, payload = state.copilot_chat(
                        "2026\u5e745\u670820\u65e5\u5bb6\u5ead\u5f00\u652f\u8d26\u5355\u91d1\u989d\u662f\u591a\u5c11\uff1f",
                        {"username": "admin", "role": "admin"},
                    )

            self.assertEqual(status, 200)
            self.assertTrue(payload["qwen_document_answer_used"])
            self.assertTrue(payload["qwen_document_answer_retry_used"])
            self.assertIn("1314\u5143", payload["answer"])
            self.assertNotIn("\u6f84\u6e05", payload["answer"])

    def test_document_query_normalizes_award_style_qwen_phrase_to_bill_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.make_state(Path(tmp), personal=True)
            evidence = [
                {
                    "evidence_ref": "ev_1",
                    "name": "family_expense_bill_20260520_1314.md",
                    "relative_path": "Documents/DemoDocs/family_expense_bill_20260520_1314.md",
                    "extension": ".md",
                    "snippet": "\u8d26\u5355\u65e5\u671f\uff1a2026\u5e745\u670820\u65e5\u3002\u8d26\u5355\u7c7b\u578b\uff1a\u5bb6\u5ead\u5f00\u652f\u3002\u5408\u8ba1\u91d1\u989d\uff1a1314\u5143\u3002",
                }
            ]

            with patch(
                "ai_nas_operator_portal_server.http_post_json",
                side_effect=[
                    self.fake_router(privacy_level="high", local_tool_id="local_document_rag"),
                    self.fake_qwen("\u7b54\u6848\uff1a\u60a8\u5c06\u83b7\u5f971314\u5143\u3002"),
                ],
            ):
                with patch.object(
                    state,
                    "document_query_payload",
                    return_value=(
                        200,
                        {
                            "ok": True,
                            "answer": "\u547d\u4e2d\u91d1\u989d\uff1a1314\u5143\u3002",
                            "evidence_count": 1,
                            "evidence": evidence,
                            "evidence_refs": ["ev_1"],
                            "amount_hits": ["1314\u5143"],
                        },
                    ),
                ):
                    status, payload = state.copilot_chat(
                        "2026\u5e745\u670820\u65e5\u5bb6\u5ead\u5f00\u652f\u8d26\u5355\u4fe1\u606f",
                        {"username": "admin", "role": "admin"},
                    )

            self.assertEqual(status, 200)
            self.assertTrue(payload["qwen_document_answer_used"])
            self.assertIn("2026\u5e745\u670820\u65e5\u5bb6\u5ead\u5f00\u652f\u8d26\u5355", payload["answer"])
            self.assertIn("\u5408\u8ba1\u91d1\u989d\u662f 1314\u5143", payload["answer"])
            self.assertNotIn("\u60a8\u5c06\u83b7\u5f97", payload["answer"])

    def test_document_amount_question_is_not_routed_to_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.make_state(Path(tmp), personal=True)

            with patch(
                "ai_nas_operator_portal_server.http_post_json",
                return_value=self.fake_router(privacy_level="high", local_tool_id="local_document_rag"),
            ):
                with patch.object(
                    state,
                    "document_query_payload",
                    return_value=(
                        200,
                        {
                            "ok": True,
                            "answer": "\u547d\u4e2d\u91d1\u989d\uff1a1314\u5143\u3002",
                            "evidence_count": 1,
                            "amount_hits": ["1314\u5143"],
                        },
                    ),
                ) as document_query:
                    status, payload = state.copilot_chat(
                        "\u8bf7\u67e5\u8be2\u6587\u6863\uff1a2026\u5e745\u670820\u65e5\u5bb6\u5ead\u5f00\u652f\u8d26\u5355\u91d1\u989d\u662f\u591a\u5c11\uff1f",
                        {"username": "admin", "role": "admin"},
                    )

            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["assistant_mode"], "local_document_query")
            self.assertEqual(payload["route"], "local_document_query")
            self.assertIn("1314\u5143", payload["answer"])
            document_query.assert_called_once()

    def test_bill_info_question_without_document_word_uses_document_rag(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.make_state(Path(tmp), personal=True)

            with patch(
                "ai_nas_operator_portal_server.http_post_json",
                return_value=self.fake_router(privacy_level="high", local_tool_id="local_document_rag"),
            ):
                with patch.object(
                    state,
                    "document_query_payload",
                    return_value=(
                        200,
                        {
                            "ok": True,
                            "answer": "\u547d\u4e2d\u91d1\u989d\uff1a1314\u5143\u3002",
                            "evidence_count": 1,
                            "amount_hits": ["1314\u5143"],
                        },
                    ),
                ) as document_query:
                    status, payload = state.copilot_chat(
                        "2026\u5e745\u670820\u65e5\u5bb6\u5ead\u5f00\u652f\u8d26\u5355\u4fe1\u606f",
                        {"username": "admin", "role": "admin"},
                    )

            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["assistant_mode"], "local_document_query")
            self.assertEqual(payload["route"], "local_document_query")
            self.assertIn("1314\u5143", payload["answer"])
            document_query.assert_called_once()


if __name__ == "__main__":
    unittest.main()
