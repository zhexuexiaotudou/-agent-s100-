import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.multimodal_search.feature_flags import MultimodalFeatureFlags
from src.multimodal_search.hybrid_retriever import HybridRetriever, select_relevant_image_rows
from src.multimodal_search.image_embedding_adapter import load_image_text_model
from src.multimodal_search.indexer import MultimodalIndexer
from src.multimodal_search.query_planner import plan_query, redact_query
from src.multimodal_search.schema import connect, migrate
from src.multimodal_search.search_api import MultimodalSearchService
from src.multimodal_search.vector_store import NumpyVectorStore
from src.openclaw.routes.multimodal_search_routes import multimodal_route_response


REPO_ROOT = Path(__file__).resolve().parents[1]


def seed_multimodal_v1_fixture(root: Path) -> Path:
    from PIL import Image

    root.mkdir(parents=True, exist_ok=True)
    docs = root / "Documents"
    photos = root / "Photos"
    videos = root / "Videos"
    audio = root / "Audio"
    code = root / "Code"
    archives = root / "Archives"
    for folder in [docs, photos, videos, audio, code, archives]:
        folder.mkdir(parents=True, exist_ok=True)

    doc_rows = [
        ("renovation_invoice_receipt.txt", "renovation invoice receipt paid evidence kitchen cabinet contract"),
        ("openclaw_s100p_baseline.txt", "OpenClaw S100P NAS baseline route health qwen local gateway evidence"),
        ("privacy_policy_notes.md", "privacy policy local first no cloud vision no raw path export"),
        ("family_trip_plan.txt", "family trip itinerary train hotel calendar document"),
        ("maintenance_record.txt", "maintenance record router disk fan cleanup"),
        ("report_claim_matrix.txt", "design report claim matrix safe wording evidence refs"),
        ("nas_mount_notes.txt", "NAS mount allowlist workspace harness read only route"),
        ("journal_summary.txt", "journal timeline user events project summary"),
        ("token_budget_report.txt", "token budget compression context pack private redaction"),
        ("shipping_list.csv", "item,count\ncable,3\nadapter,2\n"),
    ]
    for name, content in doc_rows:
        (docs / name).write_text(content, encoding="utf-8")

    color_rows = [
        ("white_shirt_photo.png", (245, 245, 240)),
        ("black_router_photo.png", (15, 15, 20)),
        ("red_receipt_photo.png", (230, 35, 40)),
        ("green_board_photo.png", (30, 180, 70)),
        ("blue_usb_photo.png", (35, 70, 230)),
        ("yellow_label_photo.png", (235, 220, 40)),
        ("gray_box_photo.png", (120, 120, 120)),
        ("white_wall_reference.png", (250, 250, 250)),
        ("blue_folder_cover.png", (40, 80, 210)),
        ("red_warning_sticker.png", (220, 20, 35)),
    ]
    for name, color in color_rows:
        Image.new("RGB", (48, 32), color).save(photos / name)

    for idx in range(6):
        (videos / f"home_clip_{idx}.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + bytes([idx]) * 32)
    for idx in range(5):
        (audio / f"meeting_audio_{idx}.wav").write_bytes(b"RIFF" + bytes([idx]) * 64)
    for idx in range(5):
        (code / f"automation_script_{idx}.py").write_text(f"def task_{idx}():\n    return 'workspace harness policy'\n", encoding="utf-8")
    (archives / "handoff_bundle.zip").write_bytes(b"PK\x03\x04synthetic archive")
    return root


class MultimodalSearchV1Test(unittest.TestCase):
    def test_schema_migrates_required_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "mm.sqlite3"
            migrate(db_path)
            conn = connect(db_path)
            try:
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','virtual table')")}
            finally:
                conn.close()
            self.assertIn("mm_assets", tables)
            self.assertIn("mm_text_chunks", tables)
            self.assertIn("mm_embeddings", tables)
            self.assertIn("mm_search_runs", tables)
            self.assertIn("mm_search_results", tables)

    def test_image_embedding_adapter_is_local_and_16_dimensional(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = seed_multimodal_v1_fixture(Path(tmp) / "Personal")
            model = load_image_text_model()
            identity = model.get_model_identity()
            vector = model.embed_image(root / "Photos" / "white_shirt_photo.png")
            query = model.embed_text("white image")
            self.assertTrue(model.available)
            self.assertEqual(identity["model_name"], "digua-local-visual-text-embedding-v1")
            self.assertEqual(identity["vector_dim"], 16)
            self.assertEqual(vector.shape[0], 16)
            self.assertEqual(query.shape[0], 16)
            self.assertTrue(identity["local_only"])
            self.assertFalse(identity["weights_committed_to_repo"])

    def test_vector_store_filters_by_modality_model_and_privacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = NumpyVectorStore(Path(tmp) / "vectors")
            model_id = "digua-local-visual-text-embedding-v1"
            store.add(
                embedding_id="emb_a",
                asset_id="asset_a",
                modality="image",
                model_id=model_id,
                vector=np.ones(16, dtype=np.float32) / 4,
                privacy_level="private_local_only",
            )
            rows = store.search(np.ones(16, dtype=np.float32) / 4, top_k=3, modality="image", model_id=model_id)
            self.assertEqual(rows[0]["asset_id"], "asset_a")
            self.assertEqual(store.search(np.ones(16, dtype=np.float32) / 4, modality="document", model_id=model_id), [])

    def test_indexer_builds_multimodal_assets_without_raw_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = seed_multimodal_v1_fixture(Path(tmp) / "Personal")
            db_path = Path(tmp) / "mm.sqlite3"
            result = MultimodalIndexer(db_path, vector_dir=Path(tmp) / "vectors").rebuild([root])
            self.assertTrue(result["ok"])
            self.assertGreaterEqual(result["counts"]["document"], 10)
            self.assertGreaterEqual(result["counts"]["image"], 10)
            self.assertGreaterEqual(result["counts"]["video"], 6)
            self.assertGreaterEqual(result["counts"]["audio"], 5)
            self.assertGreaterEqual(result["image_embeddings"], 10)
            self.assertFalse(result["privacy"]["cloud_used"])
            status = MultimodalSearchService(
                db_path=db_path,
                vector_dir=Path(tmp) / "vectors",
                trace_path=Path(tmp) / "trace.jsonl",
                roots=[root],
            ).status()
            self.assertEqual(status["raw_path_rows"], 0)

    def test_service_query_returns_fts_image_evidence_and_no_raw_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = seed_multimodal_v1_fixture(Path(tmp) / "Personal")
            service = MultimodalSearchService(
                db_path=Path(tmp) / "mm.sqlite3",
                vector_dir=Path(tmp) / "vectors",
                trace_path=Path(tmp) / "trace.jsonl",
                roots=[root],
            )
            self.assertTrue(service.rebuild({})["ok"])
            doc = service.query({"query": "renovation invoice", "modality": "document", "top_k": 5})
            img = service.query({"query": "white image", "modality": "image", "top_k": 5})
            encoded = json.dumps({"doc": doc, "img": img}, ensure_ascii=False)
            self.assertTrue(doc["ok"])
            self.assertTrue(img["ok"])
            self.assertIn("fts", doc["results"][0]["matched_by"])
            self.assertTrue(any(row["modality"] == "image" for row in img["results"]))
            self.assertTrue(all(row["evidence_ref"].startswith("mm_ev_") for row in doc["results"] + img["results"]))
            self.assertNotIn(str(root), encoded)
            self.assertNotIn("relative_path", encoded)
            self.assertFalse(doc["privacy"]["cloud_used"])

    def test_hybrid_retriever_respects_non_image_modality_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = seed_multimodal_v1_fixture(Path(tmp) / "Personal")
            db_path = Path(tmp) / "mm.sqlite3"
            MultimodalIndexer(db_path, vector_dir=Path(tmp) / "vectors").rebuild([root])
            plan = plan_query("home video clip", modality="video")
            result = HybridRetriever(db_path, vector_dir=Path(tmp) / "vectors").search(plan, top_k=5)
            self.assertTrue(result["results"])
            self.assertTrue(any(row["modality"] == "video" for row in result["results"]))
            self.assertNotIn("image_embedding", result["results"][0]["matched_by"])

    def test_chinese_flower_or_building_query_uses_separate_clip_concepts(self):
        plan = plan_query("找出有花或者有建筑的照片", modality="image")
        self.assertEqual(
            plan.visual_query_variants_en,
            [
                "a close-up photo of flowers and blossoms",
                "a photo of a building, architecture, or cityscape",
            ],
        )
        self.assertIn("flowers", plan.original_terms)
        self.assertIn("building", plan.original_terms)
        self.assertTrue(plan.visual_semantic_search_supported)

        unsupported = plan_query("找出月球基地里的紫色潜艇照片", modality="image")
        self.assertFalse(unsupported.visual_semantic_search_supported)
        self.assertEqual(unsupported.visual_query_variants_en, [])

    def test_image_relevance_selector_returns_dynamic_count_and_rejects_noise(self):
        selected, policy = select_relevant_image_rows(
            [
                {"asset_id": "a", "score": 0.273},
                {"asset_id": "b", "score": 0.269},
                {"asset_id": "c", "score": 0.260},
                {"asset_id": "d", "score": 0.250},
            ],
            min_score=0.24,
            relative_margin=0.015,
        )
        self.assertEqual([row["asset_id"] for row in selected], ["a", "b", "c"])
        self.assertEqual(policy["selected_count"], 3)
        self.assertEqual(policy["filtered_low_relevance_count"], 1)

        selected, policy = select_relevant_image_rows(
            [{"asset_id": "noise", "score": 0.236}],
            min_score=0.24,
            relative_margin=0.015,
        )
        self.assertEqual(selected, [])
        self.assertEqual(policy["selected_count"], 0)

    def test_modality_filter_does_not_make_every_image_a_metadata_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = seed_multimodal_v1_fixture(Path(tmp) / "Personal")
            db_path = Path(tmp) / "mm.sqlite3"
            vector_dir = Path(tmp) / "vectors"
            MultimodalIndexer(db_path, vector_dir=vector_dir).rebuild([root])
            retriever = HybridRetriever(db_path, vector_dir=vector_dir)
            plan = plan_query("不存在的兰花观测站", modality="image")
            self.assertEqual(retriever._metadata(plan, top_k=20), [])

    def test_api_routes_cover_status_rebuild_query_item_and_eval_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = seed_multimodal_v1_fixture(Path(tmp) / "Personal")
            report_root = Path(tmp) / "reports"
            status, payload = multimodal_route_response(
                "/api/multimodal-index/rebuild",
                method="POST",
                payload={"roots": [str(root)], "max_files": 80},
                report_root=report_root,
                personal_root=root,
            )
            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
            status, query = multimodal_route_response(
                "/api/multimodal-search/query",
                method="POST",
                payload={"query": "OpenClaw baseline", "modality": "document", "top_k": 3},
                report_root=report_root,
                personal_root=root,
            )
            self.assertEqual(status, 200)
            self.assertTrue(query["results"])
            asset_id = query["results"][0]["asset_id"]
            status, item = multimodal_route_response(
                f"/api/multimodal-index/item/{asset_id}",
                method="GET",
                report_root=report_root,
                personal_root=root,
            )
            self.assertEqual(status, 200)
            self.assertFalse(item["raw_path_returned"])
            status, summary = multimodal_route_response(
                "/api/multimodal-search/eval/summary",
                method="GET",
                report_root=report_root,
                personal_root=root,
            )
            self.assertEqual(status, 200)
            self.assertTrue(summary["ok"])

    def test_eval_benchmark_passes_security_and_image_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = seed_multimodal_v1_fixture(Path(tmp) / "Personal")
            service = MultimodalSearchService(
                db_path=Path(tmp) / "mm.sqlite3",
                vector_dir=Path(tmp) / "vectors",
                trace_path=Path(tmp) / "trace.jsonl",
                roots=[root],
            )
            self.assertTrue(service.rebuild({})["ok"])
            result = service.eval_run(REPO_ROOT / "benchmarks" / "multimodal_search_eval_cases.jsonl")
            self.assertTrue(result["ok"])
            self.assertGreaterEqual(result["case_count"], 40)
            self.assertEqual(result["private_leak_count"], 0)
            self.assertEqual(result["no_raw_path_rate"], 1.0)
            self.assertGreaterEqual(result["image_semantic_cases_pass"], 0.7)

    def test_security_boundaries_are_local_first_and_redacted(self):
        flags = MultimodalFeatureFlags()
        redacted = redact_query("token=abc123 find private photo")
        self.assertIn("token=[redacted]", redacted)
        self.assertFalse(flags.cloud_vision_enabled)
        self.assertFalse(flags.cloud_ocr_enabled)
        self.assertFalse(flags.cloud_asr_enabled)
        self.assertFalse(flags.face_identification_enabled)
        self.assertFalse(flags.biometric_recognition_enabled)
        self.assertFalse(flags.qwen_tool_execution_enabled)
        self.assertFalse(flags.destructive_actions_enabled)

    def test_ui_assets_reference_only_local_multimodal_apis(self):
        html = (REPO_ROOT / "web" / "templates" / "multimodal_search.html").read_text(encoding="utf-8")
        js = (REPO_ROOT / "web" / "static" / "digua_multimodal_search.js").read_text(encoding="utf-8")
        self.assertIn("/static/digua_multimodal_search.css", html)
        self.assertIn("/static/digua_multimodal_search.js", html)
        self.assertIn("/api/multimodal-search/status", js)
        self.assertIn("/api/multimodal-search/query", js)
        self.assertIn("/api/multimodal-index/rebuild", js)
        self.assertIn("/api/yolo-index/status", js)
        self.assertIn("/api/yolo-index/search", js)
        self.assertIn("/api/identity/login", js)
        self.assertIn("diguaAiNasToken", js)
        self.assertNotIn("http://", js)
        self.assertNotIn("https://", js)
        server = (REPO_ROOT / "scripts" / "probes" / "ai_nas_operator_portal_server.py").read_text(encoding="utf-8")
        self.assertIn("/multimodal-search", server)
        self.assertIn("digua_multimodal_search.css", server)
        self.assertIn("digua_multimodal_search.js", server)


if __name__ == "__main__":
    unittest.main()
