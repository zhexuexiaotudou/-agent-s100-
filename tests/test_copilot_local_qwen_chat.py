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
            self.assertIn("当前索引没有返回匹配结果", payload["answer"])
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


if __name__ == "__main__":
    unittest.main()
