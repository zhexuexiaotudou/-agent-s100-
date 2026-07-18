import hashlib
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from PIL import Image as PILImage


REPO_ROOT = Path(__file__).resolve().parents[1]
PROBES_ROOT = REPO_ROOT / "scripts" / "probes"
if str(PROBES_ROOT) not in sys.path:
    sys.path.insert(0, str(PROBES_ROOT))

from ai_nas_operator_portal_server import (
    PortalHandler,
    PortalState,
    copilot_policy_route,
    image_thumbnail_payload,
    infer_copilot_action_intent,
)


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

    def test_large_album_photo_uses_bounded_browser_thumbnail(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "large.jpg"
            PILImage.new("RGB", (1200, 800), (20, 80, 140)).save(source, format="JPEG", quality=92)

            raw, content_type, transformed = image_thumbnail_payload(source, max_edge=480)

            self.assertTrue(transformed)
            self.assertEqual(content_type, "image/jpeg")
            self.assertLess(len(raw), source.stat().st_size)
            thumbnail = Path(tmp) / "thumbnail.jpg"
            thumbnail.write_bytes(raw)
            with PILImage.open(thumbnail) as image:
                self.assertLessEqual(max(image.size), 480)

    def test_thumbnail_resampling_keeps_pillow_9_fallback(self):
        source = (REPO_ROOT / "scripts" / "probes" / "ai_nas_operator_portal_server.py").read_text(encoding="utf-8")

        self.assertIn('resampling = getattr(Image, "Resampling", Image)', source)
        self.assertIn("image.thumbnail((max_edge, max_edge), resampling.LANCZOS)", source)
        self.assertNotIn("Image.Resampling.LANCZOS", source)

    def test_album_frontend_separates_thumbnail_and_full_preview(self):
        source = (REPO_ROOT / "web" / "static" / "digua_ai_nas_v2.js").read_text(encoding="utf-8")

        self.assertIn("function thumbnailPreviewUrl", source)
        self.assertIn("variant=thumbnail", source)
        self.assertIn("function decodePreviewObjectUrl", source)
        self.assertIn("preview_decode_failed", source)
        self.assertNotIn('card.querySelector(".search-preview-image")?.src', source)

    def test_album_list_only_returns_photos_the_user_can_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = self.make_state(root, personal=True)
            assert state.identity_store is not None
            assert state.media_center is not None
            state.identity_store.create_user("admin", "admin123", "admin")
            state.identity_store.create_user("viewer", "viewer123", "user")
            state.identity_store.set_acl("Public", "user", "viewer", "read")
            public_photo = root / "Personal" / "Public" / "visible.jpg"
            private_photo = root / "Personal" / "Private" / "hidden.jpg"
            public_photo.parent.mkdir(parents=True)
            private_photo.parent.mkdir(parents=True)
            public_photo.write_bytes(b"public-photo")
            private_photo.write_bytes(b"private-photo")
            state.media_center.index_photos(root / "Personal", asset_root=root / "Personal")

            photos = state.media_center.list_photos(limit=20)
            viewer_photos = state.visible_media_photos(photos, {"username": "viewer", "role": "user"})
            admin_photos = state.visible_media_photos(photos, {"username": "admin", "role": "admin"})

            self.assertEqual(len(viewer_photos), 1)
            self.assertEqual(viewer_photos[0]["title_redacted"], "visible.jpg")
            self.assertEqual(len(admin_photos), 2)

    def test_media_preview_thumbnail_route_keeps_full_image_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = self.make_state(root, personal=True)
            assert state.identity_store is not None
            assert state.media_center is not None
            state.identity_store.create_user("admin", "admin123", "admin")
            login = state.identity_store.login("admin", "admin123")
            source = root / "Personal" / "Photos" / "large.jpg"
            source.parent.mkdir(parents=True)
            PILImage.new("RGB", (1600, 900), (120, 40, 80)).save(source, format="JPEG", quality=92)
            state.media_center.index_photos(root / "Personal", asset_root=root / "Personal")
            photo = state.media_center.list_photos(limit=1)[0]
            server = ThreadingHTTPServer(("127.0.0.1", 0), PortalHandler)
            server.state = state  # type: ignore[attr-defined]
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                request = urllib.request.Request(
                    f"http://127.0.0.1:{server.server_port}/api/media/preview?path_hash={photo['path_hash']}&variant=thumbnail",
                    headers={"Authorization": f"Bearer {login['token']}"},
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    raw = response.read()
                    self.assertEqual(response.headers.get_content_type(), "image/jpeg")
                thumbnail = root / "route-thumbnail.jpg"
                thumbnail.write_bytes(raw)
                with PILImage.open(thumbnail) as image:
                    self.assertLessEqual(max(image.size), 480)
                self.assertLess(len(raw), source.stat().st_size)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=5)

    def fake_router(self, route: str = "local", privacy_level: str = "none", task_complexity: str = "simple", local_tool_id: str | None = None) -> dict:
        return self.fake_qwen(json.dumps({
            "route": route,
            "privacy_level": privacy_level,
            "task_complexity": task_complexity,
            "reason": "unit-test qwen route",
            "local_tool_id": local_tool_id,
        }))

    def test_short_explicit_web_news_prompt_routes_to_cloud(self):
        prompt = "\u8bf7\u8054\u7f51\u641c\u7d22\u5e76\u5217\u51fa\u4eca\u5929\u6700\u65b0\u7684\u4e09\u6761AI\u65b0\u95fb\uff0c\u6bcf\u6761\u9644\u6765\u6e90\u94fe\u63a5\u3002"

        action_intent = infer_copilot_action_intent(prompt)
        route = copilot_policy_route(prompt, action_intent)

        self.assertIsNone(action_intent)
        self.assertEqual(route["route"], "cloud")
        self.assertEqual(route["privacy_level"], "none")
        self.assertEqual(route["task_complexity"], "complex")

    def test_web_terms_do_not_override_private_nas_guardrail(self):
        prompt = "\u8bf7\u8054\u7f51\u641c\u7d22 NAS \u672c\u5730\u6587\u4ef6\u91cc\u7684\u6700\u65b0\u65b0\u95fb\u3002"

        route = copilot_policy_route(prompt, infer_copilot_action_intent(prompt))

        self.assertEqual(route["route"], "local")
        self.assertEqual(route["local_tool_id"], "local_nas_search")

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

    def test_moved_album_photo_relinks_stale_search_result_to_current_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = self.make_state(root, personal=True)
            assert state.identity_store is not None
            assert state.media_center is not None
            state.identity_store.create_user("admin", "admin123", "admin")

            old_photo = root / "Personal" / "Photos" / "football_match.jpg"
            old_photo.parent.mkdir(parents=True, exist_ok=True)
            old_photo.write_bytes(b"same-football-photo-content")
            state.media_center.index_photos(root / "Personal", asset_root=root / "Personal")
            stale_item = state.media_center.item_for_path(old_photo, asset_root=root / "Personal")
            assert stale_item is not None

            current_photo = root / "Personal" / "Albums" / "sports" / "match_001.jpg"
            current_photo.parent.mkdir(parents=True, exist_ok=True)
            old_photo.replace(current_photo)
            state.media_center.index_photos(root / "Personal", asset_root=root / "Personal")
            current_item = state.media_center.item_for_path(current_photo, asset_root=root / "Personal")
            assert current_item is not None

            stale_result = {
                "rank": 1,
                "asset_id": stale_item["asset_id"],
                "title_redacted": "football_match.jpg",
                "modality": "image",
                "file_type": ".jpg",
                "size_bytes": len(b"same-football-photo-content"),
                "mtime": int(current_photo.stat().st_mtime),
                "score": 0.93,
                "matched_by": ["image_embedding"],
                "evidence_ref": "mm_ev_stale_football",
                "path_hash": stale_item["path_hash"],
                "privacy_level": "private_local_only",
            }

            status, payload = state._copilot_search_response(
                mode="local_multimodal_search",
                intent={"query": "find football photos", "modality": "image", "labels": []},
                result={
                    "ok": True,
                    "query_redacted": "find football photos",
                    "results": [stale_result],
                    "degraded": False,
                    "privacy": {"raw_path_returned": False, "cloud_used": False},
                },
                source="local multimodal index",
                retrieval_mode="image_embedding",
                user={"username": "admin"},
            )
            self.assertEqual(status, 200)
            self.assertEqual(payload["search"]["result_count"], 1)
            self.assertFalse(payload["search"]["degraded"])
            enriched = payload["search"]["results"][0]

            self.assertTrue(enriched["display"]["preview_available"])
            self.assertEqual(enriched["display"]["name"], "match_001.jpg")
            self.assertEqual(enriched["path_hash"], current_item["path_hash"])
            self.assertEqual(enriched["preview_resolution"], "content_digest_relinked")
            self.assertEqual(
                enriched["preview_url"],
                f"/api/media/preview?path_hash={current_item['path_hash']}",
            )
            serialized = json.dumps(enriched)
            self.assertNotIn(str(old_photo), serialized)
            self.assertNotIn(str(current_photo), serialized)
            self.assertNotIn("sha256", serialized)

    def test_multimodal_content_identity_resolves_current_album_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = self.make_state(root, personal=True)
            assert state.identity_store is not None
            assert state.media_center is not None
            state.identity_store.create_user("admin", "admin123", "admin")

            current_photo = root / "Personal" / "Albums" / "sports" / "football_current.jpg"
            current_photo.parent.mkdir(parents=True, exist_ok=True)
            photo_bytes = b"current-football-photo-content"
            current_photo.write_bytes(photo_bytes)
            state.media_center.index_photos(root / "Personal", asset_root=root / "Personal")
            current_item = state.media_center.item_for_path(current_photo, asset_root=root / "Personal")
            assert current_item is not None

            multimodal_db = root / "reports" / "multimodal_search" / "runtime" / "multimodal_search.db"
            multimodal_db.parent.mkdir(parents=True, exist_ok=True)
            con = sqlite3.connect(str(multimodal_db))
            try:
                con.execute(
                    """
                    CREATE TABLE mm_assets(
                        asset_id TEXT PRIMARY KEY,
                        path_hash TEXT NOT NULL,
                        sha256 TEXT
                    )
                    """
                )
                con.execute(
                    "INSERT INTO mm_assets(asset_id,path_hash,sha256) VALUES(?,?,?)",
                    (
                        "mm_legacy_football",
                        "0123456789abcdef0123456789abcdef",
                        hashlib.sha256(photo_bytes).hexdigest(),
                    ),
                )
                con.commit()
            finally:
                con.close()

            stale_result = {
                "rank": 1,
                "asset_id": "mm_legacy_football",
                "title_redacted": "football_old_location.jpg",
                "modality": "image",
                "file_type": ".jpg",
                "size_bytes": len(photo_bytes),
                "mtime": int(current_photo.stat().st_mtime),
                "score": 0.96,
                "matched_by": ["image_embedding"],
                "evidence_ref": "mm_ev_legacy_football",
                "path_hash": "0123456789abcdef0123456789abcdef",
                "privacy_level": "private_local_only",
            }

            status, payload = state._copilot_search_response(
                mode="local_multimodal_search",
                intent={"query": "find football photos", "modality": "image", "labels": []},
                result={
                    "ok": True,
                    "query_redacted": "find football photos",
                    "results": [stale_result],
                    "degraded": False,
                    "privacy": {"raw_path_returned": False, "cloud_used": False},
                },
                source="local multimodal index",
                retrieval_mode="image_embedding",
                user={"username": "admin"},
            )

            self.assertEqual(status, 200)
            self.assertEqual(payload["search"]["result_count"], 1)
            result = payload["search"]["results"][0]
            self.assertEqual(result["path_hash"], current_item["path_hash"])
            self.assertEqual(result["preview_resolution"], "content_digest_relinked")
            self.assertTrue(result["display"]["preview_available"])
            self.assertNotIn("sha256", json.dumps(payload))

            state.identity_store.create_user("viewer", "viewer123", "viewer")
            denied = state.enrich_copilot_search_result(stale_result, {"username": "viewer"}, {})
            self.assertFalse(denied["display"]["preview_available"])
            self.assertNotIn("preview_url", denied)

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
