import json
import os
import tempfile
import unittest
from pathlib import Path

from src.openclaw.routes.yolo_index_routes import yolo_route_response
from src.yolo_index.backend import SyntheticYoloBackend, parse_yolo_log
from src.yolo_index.labels import labels_from_query
from src.yolo_index.service import YoloIndexService


REPO_ROOT = Path(__file__).resolve().parents[1]


def seed_yolo_fixture(root: Path) -> Path:
    from PIL import Image

    root.mkdir(parents=True, exist_ok=True)
    fixtures = {
        "person_car_photo.jpg": (220, 220, 220),
        "laptop_book_keyboard_mouse_office.png": (80, 120, 180),
        "bus_stop_sign_photo.jpg": (120, 100, 80),
        "kite_person_scene.jpg": (160, 200, 240),
    }
    for name, color in fixtures.items():
        Image.new("RGB", (128, 96), color).save(root / name)
    return root


class YoloIndexCoreTest(unittest.TestCase):
    def test_parse_s100p_yolo_log(self):
        log = """
        [example] det rect: 138.323 182.210 226.229 531.821, det type: person, score:0.899599
        [example] det rect: 44.000 30.000 120.000 88.000, det type: car, score:0.554
        """
        rows = parse_yolo_log(log, evidence_ref="ev_test", image_size=(640, 640))
        self.assertEqual([row.label for row in rows], ["person", "car"])
        self.assertAlmostEqual(rows[0].bbox_x1 or 0, 138.323 / 640, places=4)
        self.assertEqual(rows[0].evidence_ref, "ev_test")

    def test_parse_s100p_image_utils_roi_log(self):
        log = """
        [example-1] [INFO] [ImageUtils]: target type: bus, rois.size: 1
        [example-1] [INFO] [ImageUtils]: roi.type: bus, x_offset: 9 y_offset: 136 width: 461 height: 311
        [example-1] [INFO] [ImageUtils]: target type: person, rois.size: 1
        [example-1] [INFO] [ImageUtils]: roi.type: person, x_offset: 29 y_offset: 235 width: 113 height: 300
        [example-1] [INFO] [ImageUtils]: target type: stop sign, rois.size: 1
        [example-1] [INFO] [ImageUtils]: roi.type: stop sign, x_offset: 0 y_offset: 150 width: 19 height: 41
        """
        rows = parse_yolo_log(log, evidence_ref="ev_roi", image_size=(640, 640))
        self.assertEqual([row.label for row in rows], ["bus", "person", "stop sign"])
        self.assertAlmostEqual(rows[1].bbox_x1 or 0, 29 / 640, places=4)
        self.assertAlmostEqual(rows[1].bbox_x2 or 0, (29 + 113) / 640, places=4)
        self.assertEqual(rows[1].confidence, 0.5)
        self.assertEqual(rows[1].evidence_ref, "ev_roi")

    def test_chinese_and_english_label_mapping(self):
        self.assertEqual(labels_from_query("找所有汽车和电脑截图"), ["car", "laptop"])
        self.assertEqual(labels_from_query("videos with person and bus"), ["person", "bus"])
        self.assertEqual(labels_from_query("书、本子、杯子"), ["book", "cup"])

    def test_rebuild_search_item_and_eval_without_raw_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = seed_yolo_fixture(Path(tmp) / "Personal")
            service = YoloIndexService(
                db_path=Path(tmp) / "reports" / "yolo_index" / "runtime" / "yolo_index.db",
                report_root=Path(tmp) / "reports",
                roots=[root],
                backend=SyntheticYoloBackend(),
                max_files=20,
            )
            rebuilt = service.rebuild({"max_files": 20, "include_video": False})
            self.assertTrue(rebuilt["ok"])
            self.assertGreaterEqual(rebuilt["counts"]["detections"], 8)
            result = service.search({"query": "找所有电脑和书", "top_k": 5})
            encoded = json.dumps(result, ensure_ascii=False)
            self.assertTrue(result["ok"])
            self.assertTrue(result["results"])
            self.assertIn("yolo_object", result["results"][0]["matched_by"])
            self.assertNotIn(str(root), encoded)
            self.assertNotIn("/mnt/", encoded)
            item = service.item(result["results"][0]["asset_id"])
            self.assertTrue(item["ok"])
            self.assertFalse(item["raw_path_returned"])

    def test_route_adapter_covers_status_rebuild_search_item_and_eval(self):
        old_backend = os.environ.get("DIGUA_YOLO_BACKEND")
        os.environ["DIGUA_YOLO_BACKEND"] = "synthetic"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = seed_yolo_fixture(Path(tmp) / "Personal")
                report_root = Path(tmp) / "reports"
                status, payload = yolo_route_response(
                    "/api/yolo-index/rebuild",
                    method="POST",
                    payload={"roots": [str(root)], "max_files": 20, "include_video": False},
                    report_root=report_root,
                    personal_root=root,
                )
                self.assertEqual(status, 200)
                self.assertTrue(payload["ok"])
                status, query = yolo_route_response(
                    "/api/yolo-index/search",
                    method="POST",
                    payload={"query": "找出现人的图片", "top_k": 3},
                    report_root=report_root,
                    personal_root=root,
                )
                self.assertEqual(status, 200)
                self.assertTrue(query["results"])
                status, item = yolo_route_response(
                    f"/api/yolo-index/item/{query['results'][0]['asset_id']}",
                    method="GET",
                    report_root=report_root,
                    personal_root=root,
                )
                self.assertEqual(status, 200)
                self.assertFalse(item["raw_path_returned"])
                cases = Path(tmp) / "cases.jsonl"
                cases.write_text(
                    "\n".join(
                        [
                            json.dumps({"query": "找所有汽车", "expected_labels": ["car"], "expect_min_results": 1}, ensure_ascii=False),
                            json.dumps({"query": "找所有电脑", "expected_labels": ["laptop"], "expect_min_results": 1}, ensure_ascii=False),
                        ]
                    ),
                    encoding="utf-8",
                )
                status, eval_result = yolo_route_response(
                    "/api/yolo-index/eval/run",
                    method="POST",
                    payload={"cases_path": str(cases)},
                    report_root=report_root,
                    personal_root=root,
                )
                self.assertEqual(status, 200)
                self.assertTrue(eval_result["ok"])
        finally:
            if old_backend is None:
                os.environ.pop("DIGUA_YOLO_BACKEND", None)
            else:
                os.environ["DIGUA_YOLO_BACKEND"] = old_backend


if __name__ == "__main__":
    unittest.main()
